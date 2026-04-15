import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import logging
import os
import edge_tts
import time
from config import BotConfig

logger = logging.getLogger(__name__)

# OPTIMIZED YOUTUBE CONFIGURATION
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': False,          # CHANGED: Allow playlists!
    'extract_flat': 'in_playlist',# Optimization: Don't download playlist details until needed
    'quiet': True,
    'default_search': 'ytsearch', # Default to searching YouTube
    'source_address': '0.0.0.0',
    # 'match_filter': yt_dlp.utils.match_filter_func('!is_live'), # Optional: Skip livestreams
    'cookies': 'www.youtube.com_cookies.txt',
    'js_runtimes': {
        'node': {}
    },
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

class GuildPlayer:
    def __init__(self, channel_id: int):
        self.channel_id: int = channel_id
        self.queue: list[tuple[str, str, str]] = []
        self.history: list[tuple[str, str, str]] = []
        self.current_track: tuple[str, str, str] | None = None
        self.start_time: float | None = None
        self.pause_start_time: float | None = None
        self.seek_position: float | None = None
        self.notification_channel: discord.TextChannel | None = None

class MusicCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.players: dict[int, GuildPlayer] = {} # {channel_id: GuildPlayer}
        self.volume: float = BotConfig.MUSIC_DEFAULT_VOLUME 
        self.tts_settings: dict[int, bool] = {} # {guild_id: bool} (TTS preference per server)
        
    async def cog_load(self):
        """Check for FFmpeg availability on load"""
        try:
            process = await asyncio.create_subprocess_exec(
                'ffmpeg', '-version',
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await process.wait()
        except FileNotFoundError:
            logger.warning("⚠️ FFmpeg binary NOT found in PATH. Music playback will fail!")
        except Exception as e:
            logger.warning(f"⚠️ Error checking FFmpeg: {e}")

    def cog_unload(self) -> None:
        """Cleanup when cog is unloaded (or bot shuts down)"""
        self.players.clear()
        
        # Disconnect from all voice channels
        for vc in self.bot.voice_clients:
            try:
                self.bot.loop.create_task(vc.disconnect(force=True))
            except Exception as e:
                logger.error(f"Failed to disconnect cleanly: {e}")

    async def generate_announcement(self, text):
        """Generates a TTS mp3 file using Edge TTS (Natural Voice)"""
        try:
            # "en-US-ChristopherNeural" is a great 'stern male' voice
            communicate = edge_tts.Communicate(text, "en-US-ChristopherNeural")
            await communicate.save("tts_announcement.mp3")
            return True
        except Exception as e:
            logger.error(f"TTS Generation failed: {e}")
            return False

    def get_music_status(self, guild: discord.Guild) -> str:
        """Returns a string describing what is playing in the guild's channels"""
        if not guild: return "No active guild."

        status_reports = []
        vc = guild.voice_client
        
        # Verify bot is actually connected and has a channel
        if vc and getattr(vc, 'channel', None):
            cid = vc.channel.id
            player = self.players.get(cid)
            
            if player:
                current = player.current_track
                queue = player.queue
                
                # Check actual playback status to avoid ghosts
                if current and (vc.is_playing() or vc.is_paused()):
                    title = current[1]
                    uploader = current[2]
                    status = f"🔊 In {vc.channel.name}: Playing '{title}' by {uploader}"
                    if queue:
                        status += f" (with {len(queue)} more in queue)"
                    status_reports.append(status)
                elif queue:
                    # Not playing but has queue? (Paused or stopped but not cleared)
                    status_reports.append(f"⏱️ In {vc.channel.name}: {len(queue)} tracks queued (Formatted/Paused)")
        
        if not status_reports:
            return "Nothing is currently playing in this facility."
            
        return "\n".join(status_reports)

    async def play_next(self, interaction: discord.Interaction) -> None:
        """Callback to play the next song in the queue"""
        # STOP if bot is shutting down
        if self.bot.is_closed():
            return

        # Dynamically determine which channel we are servicing
        # The bot can be in multiple guilds, so we need to find the voice_client context
        # Since this method is passed 'interaction', we can trust interaction.guild
        if not interaction.guild:
            return
            
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.channel:
            return

        channel_id = voice_client.channel.id
        
        # Ensure we have a player state for this channel
        if channel_id not in self.players:
            self.players[channel_id] = GuildPlayer(channel_id)
        player = self.players[channel_id]
        
        queue = player.queue
        history = player.history
        
        # CHECK FOR SEEK (Fast Forward)
        seek_time = player.seek_position
        player.seek_position = None
        
        if seek_time is not None:
             # We are seeking! Use the CURRENT track (don't pop new one)
             # And don't save to history yet
             current_data = player.current_track
             if current_data:
                 url, title, uploader = current_data
             else:
                 # Weird state, fallback to queue
                 if queue:
                     url, title, uploader = queue.pop(0)
                     player.current_track = (url, title, uploader)
                 else:
                     await self.bot.change_presence(activity=discord.Game(name="Science | /help"))
                     return
        elif queue:
            # Normal Playback
            # Save previous track to history if it finished naturally
            current = player.current_track
            if current:
                history.append(current)
                if len(history) > 20: history.pop(0)

            url, title, uploader = queue.pop(0)
            player.current_track = (url, title, uploader)
        else:
            player.current_track = None
            await self.bot.change_presence(activity=discord.Game(name="Science | /help"))
            return
            
        try:
            # 1. Get Stream URL (JIT)
            loop = self.bot.loop or asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(YDL_OPTIONS).extract_info(url, download=False))
            
            if data and 'entries' in data:
                data = data['entries'][0]
            
            stream_url = data['url']
            
            # 2. Update Facility Status
            vc_channel = voice_client.channel
            if vc_channel.permissions_for(interaction.guild.me).manage_channels:
                if seek_time:
                    await vc_channel.edit(status=f"⏩ {title} (+{int(seek_time)}s)")
                else:
                    await vc_channel.edit(status=f"🎶 {title}")
            else:
                logger.warning("Missing 'Manage Channels' permission. Cannot update VC status.")

            # --- THE PLAYBACK CHAIN ---
            
            def after_song_ends(error: Exception | None) -> None:
                if error: logger.error(f"Song Error: {error}")
                asyncio.run_coroutine_threadsafe(self.play_next(interaction), self.bot.loop)

            def play_song(error: Exception | None = None) -> None:
                if error: logger.error(f"TTS Error: {error}")
                
                # Dynamic FFMPEG Options for Seeking
                current_opts = FFMPEG_OPTIONS.copy()
                if seek_time:
                    # Inject -ss before_options
                    # We append it to existing options
                    current_opts['before_options'] = str(current_opts.get('before_options', '')) + f" -ss {seek_time}"
                
                # Create Song Source
                song_source = discord.PCMVolumeTransformer(
                    discord.FFmpegPCMAudio(stream_url, **current_opts), 
                    volume=self.volume
                )
                voice_client.play(song_source, after=after_song_ends)
                
                # Record Start Time (Adjusted for seek so Elapsed Time logic works)
                # If we seek to 30s, we pretend we started 30s ago.
                player.start_time = time.time() - (seek_time if seek_time else 0)

            # Define Step 1: TTS Announcement (Skip if Seeking)
            if not seek_time and self.tts_settings.get(interaction.guild.id, False):
                clean_title = title.split('(')[0].split('[')[0]
                announcement_text = f"Now playing: {clean_title}"
                
                success = await self.generate_announcement(announcement_text)
                
                if success and os.path.exists("tts_announcement.mp3"):
                    tts_source = discord.PCMVolumeTransformer(
                        discord.FFmpegPCMAudio("tts_announcement.mp3"), 
                        volume=self.volume + 0.2
                    )
                    voice_client.play(tts_source, after=play_song)
                else:
                    play_song(None)
            else:
                play_song(None)

        except yt_dlp.utils.DownloadError as e:
            logger.error(f"YTDL DownloadError for {title}: {e}")
            player.current_track = None
            await self.play_next(interaction)
        except Exception as e:
            logger.error(f"Failed to play {title}: {e}")
            # If seek fails, just move next
            player.current_track = None
            await self.play_next(interaction)

    async def _ensure_voice_connection(self, interaction: discord.Interaction) -> discord.VoiceClient | None:
        """Helper to ensure the bot is connected to the right voice channel."""
        if not interaction.user or not isinstance(interaction.user, discord.Member) or not interaction.user.voice:
            await interaction.followup.send("🎙️ **Cave here.** You need to be in a voice channel. I can't pipe audio directly into your brain... yet.")
            return None

        target_channel = interaction.user.voice.channel
        target_channel_id = target_channel.id
        
        # Check if the bot is actually in the guild
        if not interaction.guild:
            return None

        vc = interaction.guild.voice_client
        
        if vc and vc.channel.id != target_channel_id:
             if vc.is_playing():
                 vc.stop()
             await vc.move_to(target_channel)
             vc = interaction.guild.voice_client
        elif not vc:
            vc = await target_channel.connect()
            
        return vc # type: ignore

    async def _fetch_youtube_data(self, target: str) -> dict:
        """Helper to fetch YouTube data asynchronously"""
        loop = self.bot.loop or asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(YDL_OPTIONS).extract_info(target, download=False)) # type: ignore

    @app_commands.command(name="play-tts", description="Toggle the vocal announcement system")
    async def toggle_tts(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        guild_id = interaction.guild.id
        current_setting = self.tts_settings.get(guild_id, False)
        self.tts_settings[guild_id] = not current_setting
        
        state = "ONLINE" if self.tts_settings[guild_id] else "OFFLINE"
        await interaction.response.send_message(f"🎙️ **Facility Announcer {state}.**")

    @app_commands.command(name="play", description="Play audio from YouTube (Search or Link)")
    @app_commands.describe(
        query="Search term (e.g. 'lofi hip hop')", 
        url="Direct YouTube Link", 
        force_play="Play immediately (interrupt current)",
        playlist_only="Search specifically for playlists (Default: False)"
    )
    @app_commands.rename(force_play="force-play", playlist_only="playlist-only")
    async def play(self, interaction: discord.Interaction, query: str | None = None, url: str | None = None, force_play: bool = False, playlist_only: bool = False) -> None:
        """Robust YouTube Player"""
        await interaction.response.defer()
        
        vc = await self._ensure_voice_connection(interaction)
        if not vc or not vc.channel:
            return

        target_channel_id = vc.channel.id

        if target_channel_id not in self.players:
            self.players[target_channel_id] = GuildPlayer(target_channel_id)
        player = self.players[target_channel_id]
        
        # Update Notification Channel for this voice channel
        if isinstance(interaction.channel, discord.TextChannel):
            player.notification_channel = interaction.channel

        # 0. Input Validation
        if not query and not url:
            await interaction.followup.send("⚠️ **Cave here.** You need to give me something to play. A search term or a URL. I'm not a mind reader.", ephemeral=True)
            return

        target = url if url else query
        is_direct_link = True if url else False
        
        if not is_direct_link and target and not target.startswith(('http://', 'https://')):
             if playlist_only:
                 import urllib.parse
                 encoded_query = urllib.parse.quote(target)
                 target = f"https://www.youtube.com/results?search_query={encoded_query}&sp=EgIQAw%253D%253D"
             else:
                 target = f"ytsearch:{target}"

        # 2. Search / Extraction
        if is_direct_link:
            msg = await interaction.followup.send(f"**Loading Link:** `{target}`...")
        elif playlist_only:
             msg = await interaction.followup.send(f"🔍 **Searching for Playlist:** `{query}`...")
        else:
            msg = await interaction.followup.send(f"🔍 **Searching:** `{target}`...")
        
        try:
            if target:
                info = await self._fetch_youtube_data(target)
            else:
                return

            # 3. Handle Results (Single vs Playlist)
            added_songs = []

            # Handle our custom valid playlist search results
            if playlist_only and not is_direct_link:
                if 'entries' in info:
                    entries = list(info['entries'])
                    if not entries:
                        await msg.edit(content=f"❌ **No Playlists Found** for `{query}`.")
                        return
                    
                    found_playlist = entries[0]
                    playlist_url = found_playlist['url']
                    
                    info = await self._fetch_youtube_data(playlist_url)
            
            if 'entries' in info:
                if info.get('_type') == 'playlist':
                    for entry in info['entries']:
                         if entry:
                            uploader = entry.get('uploader', 'Unknown Artist')
                            added_songs.append((entry['url'], entry['title'], uploader))
                    
                    queue_len = len(added_songs)
                    await msg.edit(content=f"📝 **Playlist Queued:** Added {queue_len} tracks from *{info['title']}*.")
                else:
                    entry = info['entries'][0]
                    uploader = entry.get('uploader', 'Unknown Artist')
                    added_songs.append((entry['url'], entry['title'], uploader))
                    if is_direct_link:
                        await msg.edit(content=f"🎵 **Added:** {entry['title']} by {uploader}")
                    else:
                        await msg.edit(content=f"🎵 **Found:** {entry['title']} by {uploader}")
            else:
                uploader = info.get('uploader', 'Unknown Artist')
                added_songs.append((info['url'], info['title'], uploader))
                await msg.edit(content=f"🎵 **Added:** {info['title']} by {uploader}")

            # 4. Add to Queue
            if not added_songs:
                 await msg.edit(content="❌ **Error:** No playable tracks found.")
                 return

            queue = player.queue

            if force_play:
                player.queue = added_songs + queue
                
                current_track_info = player.current_track

                if vc.is_playing() and current_track_info:
                    queue.insert(len(added_songs), current_track_info)
                    vc.stop()
                    await msg.edit(content=f"🚨 **Interrupted!** Playing {added_songs[0][1]} immediately.")
                else:
                    if not vc.is_playing():
                        await self.play_next(interaction)
            else:
                queue.extend(added_songs)

                if not vc.is_playing():
                    await self.play_next(interaction)

        except yt_dlp.utils.DownloadError as e:
            logger.error(f"YTDL Error: {e}")
            await msg.edit(content="⚠️ **Error:** The audio processor caught fire (DownloadError). Check the link.")
        except Exception as e:
            logger.error(f"Unexpected Error in play: {e}")
            await msg.edit(content="⚠️ **Error:** The audio processor caught fire. Something unexpected happened.")

    @app_commands.command(name="previous", description="Go back to the previous song")
    async def previous(self, interaction: discord.Interaction) -> None:
        """Go back to the previous song"""
        vc = interaction.guild.voice_client if interaction.guild else None
        if not vc or not getattr(vc, 'channel', None):
             await interaction.response.send_message("I'm not connected.", ephemeral=True)
             return

        channel_id = vc.channel.id
        player = self.players.get(channel_id)
        if not player:
             await interaction.response.send_message("I'm not connected.", ephemeral=True)
             return

        history = player.history
        queue = player.queue

        if not history:
             await interaction.response.send_message("❌ **No history.** We can only move forward, not backward.", ephemeral=True)
             return

        # Get last song
        last_track = history.pop()
        
        # If something is currently playing, put it back at the start of queue
        current = player.current_track
        if current:
             queue.insert(0, current)
        
        # Put the previous track at SUPER priority (index 0)
        queue.insert(0, last_track)
        
        player.current_track = None 
        vc.stop()
        
        title = last_track[1]
        uploader = last_track[2]
        await interaction.response.send_message(f"⏮️ **Rewinding.** Playing previous track: {title} by {uploader}")

    @app_commands.command(name="skip", description="Vote to skip the current track")
    async def skip(self, interaction: discord.Interaction) -> None:
        vc = interaction.guild.voice_client if interaction.guild else None
        if vc and vc.is_playing():
            vc.stop() # This triggers the 'after' callback, which calls play_next()
            await interaction.response.send_message("⏭️ **Skipped.** Protocol advanced.")
        else:
            await interaction.response.send_message("Nothing is playing, genius.", ephemeral=True)

    @app_commands.command(name="queue", description="View the upcoming audio tests")
    async def view_queue(self, interaction: discord.Interaction) -> None:
        # View queue for the channel the user is in, OR the bot is in
        target_channel_id = None
        if interaction.user and isinstance(interaction.user, discord.Member) and interaction.user.voice and interaction.user.voice.channel:
            target_channel_id = interaction.user.voice.channel.id
        elif interaction.guild and interaction.guild.voice_client and getattr(interaction.guild.voice_client, 'channel', None):
            target_channel_id = interaction.guild.voice_client.channel.id
            
        if not target_channel_id:
             await interaction.response.send_message("No active audio session found.", ephemeral=True)
             return

        player = self.players.get(target_channel_id)
        if not player:
            await interaction.response.send_message("The queue is empty. Silence is inefficient.")
            return

        queue = player.queue
        current = player.current_track

        if not queue and not current:
            await interaction.response.send_message("The queue is empty. Silence is inefficient.")
            return

        current_title = f"{current[1]} by {current[2]}" if current else "Nothing"
        
        desc = f"**Now Playing:** {current_title}\n\n**Up Next:**\n"
        for i, (url, title, uploader) in enumerate(list(queue)[:10], 1):
            desc += f"`{i}.` {title} by {uploader}\n"
        
        if len(queue) > 10:
            desc += f"*...and {len(queue)-10} more.*"

        embed = discord.Embed(title="🎧 Audio Testing Queue", description=desc, color=0xFFA500)
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="clear", description="Clear the upcoming tracks")
    async def clear(self, interaction: discord.Interaction) -> None:
        vc = interaction.guild.voice_client if interaction.guild else None
        if not vc or not getattr(vc, 'channel', None):
            await interaction.response.send_message("I'm not connected.", ephemeral=True)
            return
            
        channel_id = vc.channel.id
        player = self.players.get(channel_id)
        if player:
            count = len(player.queue)
            player.queue.clear()
            player.current_track = None
            if vc.is_playing() or vc.is_paused():
                vc.stop()
            
            if count > 0:
                await interaction.response.send_message(f"🗑️ **Testing Halted.** Cleared {count} upcoming tracks and stopped the current track.")
            else:
                await interaction.response.send_message("🗑️ **Testing Halted.** Stopped the current track.")
        else:
            await interaction.response.send_message("The testing queue is already empty.", ephemeral=True)

    @app_commands.command(name="list", description="List specific songs in the queue")
    async def list_queue(self, interaction: discord.Interaction) -> None:
        """Alias for queue"""
        await self.view_queue.callback(self, interaction) # type: ignore

    @app_commands.command(name="stop", description="Clear queue and disconnect")
    async def stop(self, interaction: discord.Interaction) -> None:
        vc = interaction.guild.voice_client if interaction.guild else None
        if vc:
            # --- CLEANUP LOGIC ---
            channel = getattr(vc, 'channel', None)
            if channel and isinstance(channel, discord.VoiceChannel) and interaction.guild and interaction.guild.me:
                if channel.permissions_for(interaction.guild.me).manage_channels:
                     # Setting status to None removes it
                     await channel.edit(status=None) 
            # -------------------------
            
            # Clear state for this channel
            if channel:
                channel_id = channel.id
                player = self.players.get(channel_id)
                if player:
                    player.queue.clear()
                    player.current_track = None
                self.players.pop(channel_id, None)
             
            vc.stop()
            await vc.disconnect()
            
            await interaction.response.send_message("🛑 **Testing Concluded.**")
        else:
            await interaction.response.send_message("I'm not connected.", ephemeral=True)

    @app_commands.command(name="fast-forward", description="Skip forward in the current track")
    @app_commands.describe(seconds="Seconds to skip (Default: 30)")
    async def fast_forward(self, interaction: discord.Interaction, seconds: int = 30) -> None:
        vc = interaction.guild.voice_client if interaction.guild else None
        if not getattr(vc, 'is_playing', lambda: False)() or not getattr(vc, 'channel', None): # type: ignore
            await interaction.response.send_message("❌ **Nothing is playing.** cannot fast forward silence.", ephemeral=True)
            return

        channel_id = vc.channel.id
        player = self.players.get(channel_id)
        if not player or not player.start_time:
             await interaction.response.send_message("⚠️ **Time Error.** Cannot determine current track position.", ephemeral=True)
             return
             
        # Calculate current position
        start_time = player.start_time or 0.0
        current_pos = time.time() - start_time
        target_pos = current_pos + seconds
        
        # Set seek target
        player.seek_position = float(target_pos)
        
        await interaction.response.send_message(f"⏩ **Fast Forwarding** {seconds}s... (Target: {int(target_pos)}s)")
        
        # Stop current track to trigger 'after' -> 'play_next' -> sees seek_position -> seeks
        vc.stop()

    @app_commands.command(name="play-pause", description="Pause or Resume playback")
    async def play_pause(self, interaction: discord.Interaction) -> None:
        vc = interaction.guild.voice_client if interaction.guild else None
        if not vc or not getattr(vc, 'channel', None):
             await interaction.response.send_message("I'm not connected.", ephemeral=True)
             return
             
        channel_id = vc.channel.id
        player = self.players.get(channel_id)
        if not player:
            await interaction.response.send_message("❌ **Nothing is playing.**", ephemeral=True)
            return
        
        if vc.is_paused():
            # RESUME
            vc.resume()
            
            # Adjust start time so elapsed time calculation remains correct
            # We effectively "shift" the start time forward by the duration we were paused
            if player.pause_start_time:
                pause_duration = time.time() - float(player.pause_start_time)
                if player.start_time:
                    player.start_time += pause_duration
                player.pause_start_time = None
            
            await interaction.response.send_message("▶️ **Resumed.**")
            
        elif vc.is_playing():
            # PAUSE
            vc.pause()
            
            # Record when we paused
            player.pause_start_time = time.time()
            
            await interaction.response.send_message("II **Paused.**")
        else:
            await interaction.response.send_message("❌ **Nothing is playing.**", ephemeral=True)

async def setup(bot):
    await bot.add_cog(MusicCommands(bot))