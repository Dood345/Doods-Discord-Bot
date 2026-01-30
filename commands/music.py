import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import logging
import os
import edge_tts
import time

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

class MusicCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # State now keyed by Voice Channel ID (int)
        self.queues = {}          # {channel_id: [(url, title)]}
        self.current_tracks = {}  # {channel_id: (url, title)}
        self.histories = {}       # {channel_id: [(url, title)]}
        self.notification_channels = {} # {channel_id: text_channel}
        
        self.start_times = {}       # {channel_id: timestamp}
        self.pause_start_times = {} # {channel_id: timestamp}
        self.seek_positions = {}    # {channel_id: seconds_to_seek_to}

        self.volume = 0.5    # Default volume
        self.tts_settings = {} # {guild_id: bool} (TTS preference per server)
        
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

    def cog_unload(self):
        """Cleanup when cog is unloaded (or bot shuts down)"""
        self.queues = {}
        self.histories = {}
        self.current_tracks = {}
        self.notification_channels = {}
        
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

    def get_music_status(self, guild) -> str:
        """Returns a string describing what is playing in the guild's channels"""
        if not guild: return "No active guild."

        status_reports = []
        
        # Check all voice channels in the guild
        for channel in guild.voice_channels:
            cid = channel.id
            
            # 1. Check Now Playing
            current = self.current_tracks.get(cid)
            queue = self.queues.get(cid, [])
            
            if current:
                title = current[1]
                status = f"🔊 In {channel.name}: Playing '{title}'"
                if queue:
                    status += f" (with {len(queue)} more in queue)"
                status_reports.append(status)
            elif queue:
                # Not playing but has queue? (Paused or stopped but not cleared)
                status_reports.append(f"⏱️ In {channel.name}: {len(queue)} tracks queued (Formatted/Paused)")
        
        if not status_reports:
            return "Nothing is currently playing in this facility."
            
        return "\n".join(status_reports)

    async def play_next(self, interaction):
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
        
        # Ensure we have state lists for this channel
        if channel_id not in self.queues: self.queues[channel_id] = []
        if channel_id not in self.histories: self.histories[channel_id] = []
        
        queue = self.queues[channel_id]
        history = self.histories[channel_id]
        
        # CHECK FOR SEEK (Fast Forward)
        seek_time = self.seek_positions.pop(channel_id, None)
        
        if seek_time is not None:
             # We are seeking! Use the CURRENT track (don't pop new one)
             # And don't save to history yet
             current_data = self.current_tracks.get(channel_id)
             if current_data:
                 url, title = current_data
             else:
                 # Weird state, fallback to queue
                 if queue:
                     url, title = queue.pop(0)
                     self.current_tracks[channel_id] = (url, title)
                 else:
                     await self.bot.change_presence(activity=discord.Game(name="Science | /help"))
                     return
        elif queue:
            # Normal Playback
            # Save previous track to history if it finished naturally
            current = self.current_tracks.get(channel_id)
            if current:
                history.append(current)
                if len(history) > 20: history.pop(0)

            url, title = queue.pop(0)
            self.current_tracks[channel_id] = (url, title)
        else:
            self.current_tracks[channel_id] = None
            await self.bot.change_presence(activity=discord.Game(name="Science | /help"))
            return
            
        try:
            # 1. Get Stream URL (JIT)
            loop = self.bot.loop or asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(YDL_OPTIONS).extract_info(url, download=False))
            
            if 'entries' in data:
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
            
            def after_song_ends(error):
                if error: logger.error(f"Song Error: {error}")
                asyncio.run_coroutine_threadsafe(self.play_next(interaction), self.bot.loop)

            def play_song(error=None):
                if error: logger.error(f"TTS Error: {error}")
                
                # Dynamic FFMPEG Options for Seeking
                current_opts = FFMPEG_OPTIONS.copy()
                if seek_time:
                    # Inject -ss before_options
                    # We append it to existing options
                    current_opts['before_options'] += f" -ss {seek_time}"
                
                # Create Song Source
                song_source = discord.PCMVolumeTransformer(
                    discord.FFmpegPCMAudio(stream_url, **current_opts), 
                    volume=self.volume
                )
                voice_client.play(song_source, after=after_song_ends)
                
                # Record Start Time (Adjusted for seek so Elapsed Time logic works)
                # If we seek to 30s, we pretend we started 30s ago.
                self.start_times[channel_id] = time.time() - (seek_time if seek_time else 0)

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

        except Exception as e:
            logger.error(f"Failed to play {title}: {e}")
            # If seek fails, just move next
            self.current_tracks[channel_id] = None
            await self.play_next(interaction)

    @app_commands.command(name="play-tts", description="Toggle the vocal announcement system")
    async def toggle_tts(self, interaction: discord.Interaction):
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
        playlist_only="Search specifically for playlists (Default: False)",
        radio="Play a YouTube Mix based on the search term"
    )
    @app_commands.rename(force_play="force-play", playlist_only="playlist-only")
    async def play(self, interaction: discord.Interaction, query: str = None, url: str = None, force_play: bool = False, playlist_only: bool = False):
        """Robust YouTube Player"""
        await interaction.response.defer()
        
        # 1. Voice Channel Check
        if not interaction.user.voice:
            await interaction.followup.send("🎙️ **Cave here.** You need to be in a voice channel. I can't pipe audio directly into your brain... yet.")
            return

        # Determine Target Channel (Where the USER is)
        target_channel = interaction.user.voice.channel
        target_channel_id = target_channel.id
        # --- SAVE THE CHANNEL ---
        self.music_channel = interaction.channel

        # 0. Input Validation
        if not query and not url:
            await interaction.followup.send("⚠️ **Cave here.** You need to give me something to play. A search term or a URL. I'm not a mind reader.", ephemeral=True)
            return

        target = url if url else query
        is_direct_link = True if url else False
        
        # FIX: If using 'query' and it's not a link, force ytsearch: prefix
        # This prevents yt-dlp from thinking "re:..." is a URL scheme
        if not is_direct_link:
            if not target.startswith(('http://', 'https://')):
                 # NEW: Custom Playlist Search Logic
                 if playlist_only:
                     import urllib.parse
                     encoded_query = urllib.parse.quote(target)
                     # sp=EgIQAw%253D%253D is the "Type: Playlist" filter
                     target = f"https://www.youtube.com/results?search_query={encoded_query}&sp=EgIQAw%253D%253D"
                 else:
                     target = f"ytsearch:{target}"

        # 1. Voice Channel Check
        if not interaction.user.voice:
            await interaction.followup.send("🎙️ **Cave here.** You need to be in a voice channel. I can't pipe audio directly into your brain... yet.")
            return

        vc = interaction.guild.voice_client
        if not vc:
            vc = await interaction.user.voice.channel.connect()

        # Update Notification Channel for this voice channel
        self.notification_channels[vc.channel.id] = interaction.channel
        
        # 2. Search / Extraction
        if is_direct_link:
            msg = await interaction.followup.send(f"**Loading Link:** `{target}`...")
        elif playlist_only:
             msg = await interaction.followup.send(f"🔍 **Searching for Playlist:** `{query}`...")
        elif radio:
             msg = await interaction.followup.send(f"📻 **Tuning Radio:** `{query}`...")
        else:
            msg = await interaction.followup.send(f"🔍 **Searching:** `{target}`...")
        
        try:
            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                # "extract_flat" is fast for playlists
                info = ydl.extract_info(target, download=False)

            # 3. Handle Results (Single vs Playlist)
            added_songs = []

            # NEW: Handle our custom valid playlist search results
            if playlist_only and not is_direct_link:
                # The 'info' from our custom URL will be a list of search results (playlists)
                if 'entries' in info:
                    # Filter out non-playlist results just in case, or take the first one
                    entries = list(info['entries']) # resolve generator
                    if not entries:
                        await msg.edit(content=f"❌ **No Playlists Found** for `{query}`.")
                        return
                    
                    # The first entry IS the playlist we want, but it's just a reference url
                    found_playlist = entries[0]
                    playlist_url = found_playlist['url']
                    
                    # We must EXTRACT the actual playlist now
                    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                         info = ydl.extract_info(playlist_url, download=False)
                    
                    # Update info to be the playlist info now
            
            # NEW: Radio / Mix Logic
            if radio:
                video_id = None
                
                # Check directly if we have an ID (direct link)
                if info.get('id'):
                    video_id = info['id']
                # Or check entries (search result)
                elif 'entries' in info:
                     entries = list(info['entries'])
                     if entries:
                         video_id = entries[0].get('id')
                
                if video_id:
                     # Construct Mix URL
                     mix_url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"
                     
                     # Extract Mix
                     with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                         info = ydl.extract_info(mix_url, download=False)
                         await msg.edit(content=f"📻 **Radio Station Found:** *{info.get('title', 'Mix')}*")
                else:
                     await msg.edit(content="❌ **Radio Error:** Could not identify a seed video for the radio.")
                     return

            if 'entries' in info:
                # It's a Playlist or a Search Result
                if info.get('_type') == 'playlist':
                    # It is an ACTUAL playlist (either direct link OR our found playlist OR our Radio Mix)
                    for entry in info['entries']:
                         if entry: # sometimes entries can be None
                            added_songs.append((entry['url'], entry['title']))
                    
                    queue_len = len(added_songs)
                    if radio:
                        await msg.edit(content=f"📻 **Radio Tuned:** Queued {queue_len} tracks based on *{query if query else 'Link'}*.")
                    else:
                        await msg.edit(content=f"📝 **Playlist Queued:** Added {queue_len} tracks from *{info['title']}*.")
                else:
                    # It is a Search Result (take the first one)
                    # Note: If playlist_only/radio, we shouldn't get here because we re-extracted
                    entry = info['entries'][0]
                    added_songs.append((entry['url'], entry['title']))
                    if is_direct_link:
                        await msg.edit(content=f"🎵 **Added:** {entry['title']}")
                    else:
                        await msg.edit(content=f"🎵 **Found:** {entry['title']}")
            else:
                # Direct Link to video
                added_songs.append((info['url'], info['title']))
                await msg.edit(content=f"🎵 **Added:** {info['title']}")

            # 4. Add to Queue (Channel Specific)
            if not added_songs:
                 await msg.edit(content="❌ **Error:** No playable tracks found.")
                 return

            # Ensure queue exists
            if target_channel_id not in self.queues: self.queues[target_channel_id] = []
            queue = self.queues[target_channel_id]

            if force_play:
                 # Interrupt Priority: [NewSong, CurrentSong, RestOfQueue...]
                queue[0:0] = added_songs # Prepend new songs
                
                current_track_info = self.current_tracks.get(target_channel_id)

                if vc.is_playing() and current_track_info:
                    # If playing, we need to save the current song right after the new one
                    queue.insert(len(added_songs), current_track_info)
                    
                    # Stopping triggers 'after_playing' -> play_next() -> pops index 0 (NewSong)
                    vc.stop()
                    await msg.edit(content=f"🚨 **Interrupted!** Playing {added_songs[0][1]} immediately.")
                else:
                    # If idle, just start playing (assuming we are in the right channel)
                    if not vc.is_playing():
                        await self.play_next(interaction)
            else:
                # Normal Queue
                queue.extend(added_songs)

                # 5. Start Playback if Idle
                if not vc.is_playing():
                    await self.play_next(interaction)

        except Exception as e:
            logger.error(f"YTDL Error: {e}")
            await msg.edit(content="⚠️ **Error:** The audio processor caught fire. Check the link or try a different search.")

    @app_commands.command(name="previous", description="Go back to the previous song")
    async def previous(self, interaction: discord.Interaction):
        """Go back to the previous song"""
        vc = interaction.guild.voice_client
        if not vc or not vc.channel:
             await interaction.response.send_message("I'm not connected.", ephemeral=True)
             return

        channel_id = vc.channel.id
        history = self.histories.get(channel_id, [])
        queue = self.queues.get(channel_id, [])

        if not history:
             await interaction.response.send_message("❌ **No history.** We can only move forward, not backward.", ephemeral=True)
             return

        # Get last song
        last_track = history.pop()
        
        # If something is currently playing, put it back at the start of queue
        current = self.current_tracks.get(channel_id)
        if current:
             queue.insert(0, current)
        
        # Put the previous track at SUPER priority (index 0)
        queue.insert(0, last_track)
        
        self.current_tracks[channel_id] = None 
        vc.stop()
        
        title = last_track[1]
        await interaction.response.send_message(f"⏮️ **Rewinding.** Playing previous track: {title}")

    @app_commands.command(name="skip", description="Vote to skip the current track")
    async def skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop() # This triggers the 'after' callback, which calls play_next()
            await interaction.response.send_message("⏭️ **Skipped.** Protocol advanced.")
        else:
            await interaction.response.send_message("Nothing is playing, genius.", ephemeral=True)

    @app_commands.command(name="queue", description="View the upcoming audio tests")
    async def view_queue(self, interaction: discord.Interaction):
        # View queue for the channel the user is in, OR the bot is in
        target_channel_id = None
        if interaction.user.voice:
            target_channel_id = interaction.user.voice.channel.id
        elif interaction.guild.voice_client:
            target_channel_id = interaction.guild.voice_client.channel.id
            
        if not target_channel_id:
             await interaction.response.send_message("No active audio session found.", ephemeral=True)
             return

        queue = self.queues.get(target_channel_id, [])
        current = self.current_tracks.get(target_channel_id)

        if not queue and not current:
            await interaction.response.send_message("The queue is empty. Silence is inefficient.")
            return

        current_title = current[1] if current else "Nothing"
        
        desc = f"**Now Playing:** {current_title}\n\n**Up Next:**\n"
        for i, (url, title) in enumerate(queue[:10], 1):
            desc += f"`{i}.` {title}\n"
        
        if len(queue) > 10:
            desc += f"*...and {len(queue)-10} more.*"

        embed = discord.Embed(title="🎧 Audio Testing Queue", description=desc, color=0xFFA500)
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="clear", description="Clear the upcoming tracks")
    async def clear(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc or not vc.channel:
            await interaction.response.send_message("I'm not connected.", ephemeral=True)
            return
            
        channel_id = vc.channel.id
        if channel_id in self.queues:
            count = len(self.queues[channel_id])
            self.queues[channel_id] = []
            await interaction.response.send_message(f"🗑️ **Queue Cleared.** Removed {count} upcoming tracks.")
        else:
            await interaction.response.send_message("Queue is already empty.", ephemeral=True)

    @app_commands.command(name="list", description="List specific songs in the queue")
    async def list_queue(self, interaction: discord.Interaction):
        """Alias for queue"""
        await self.view_queue(interaction)

    @app_commands.command(name="stop", description="Clear queue and disconnect")
    async def stop(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc:
            # --- NEW CLEANUP LOGIC ---
            channel = vc.channel
            channel_id = channel.id
            if channel.permissions_for(interaction.guild.me).manage_channels:
                 # Setting status to None removes it
                 await channel.edit(status=None) 
            # -------------------------
            
            # Clear state for this channel
            if channel_id in self.queues: self.queues[channel_id] = []
            if channel_id in self.current_tracks: self.current_tracks[channel_id] = None
            if channel_id in self.start_times: del self.start_times[channel_id]
            if channel_id in self.pause_start_times: del self.pause_start_times[channel_id]
            if channel_id in self.seek_positions: del self.seek_positions[channel_id]
             
            vc.stop()
            await vc.disconnect()
            
            await interaction.response.send_message("🛑 **Testing Concluded.**")
        else:
            await interaction.response.send_message("I'm not connected.", ephemeral=True)

    @app_commands.command(name="fast-forward", description="Skip forward in the current track")
    @app_commands.describe(seconds="Seconds to skip (Default: 30)")
    async def fast_forward(self, interaction: discord.Interaction, seconds: int = 30):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_playing():
            await interaction.response.send_message("❌ **Nothing is playing.** cannot fast forward silence.", ephemeral=True)
            return

        channel_id = vc.channel.id
        
        start_time = self.start_times.get(channel_id)
        if not start_time:
             await interaction.response.send_message("⚠️ **Time Error.** Cannot determine current track position.", ephemeral=True)
             return
             
        # Calculate current position
        current_pos = time.time() - start_time
        target_pos = current_pos + seconds
        
        # Set seek target
        self.seek_positions[channel_id] = target_pos
        
        await interaction.response.send_message(f"⏩ **Fast Forwarding** {seconds}s... (Target: {int(target_pos)}s)")
        
        # Stop current track to trigger 'after' -> 'play_next' -> sees seek_positions -> seeks
        vc.stop()

    @app_commands.command(name="play-pause", description="Pause or Resume playback")
    async def play_pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc:
             await interaction.response.send_message("I'm not connected.", ephemeral=True)
             return
             
        channel_id = vc.channel.id
        
        if vc.is_paused():
            # RESUME
            vc.resume()
            
            # Adjust start time so elapsed time calculation remains correct
            # We effectively "shift" the start time forward by the duration we were paused
            if channel_id in self.pause_start_times:
                pause_duration = time.time() - self.pause_start_times[channel_id]
                if channel_id in self.start_times:
                    self.start_times[channel_id] += pause_duration
                del self.pause_start_times[channel_id]
            
            await interaction.response.send_message("▶️ **Resumed.**")
            
        elif vc.is_playing():
            # PAUSE
            vc.pause()
            
            # Record when we paused
            self.pause_start_times[channel_id] = time.time()
            
            await interaction.response.send_message("II **Paused.**")
        else:
            await interaction.response.send_message("❌ **Nothing is playing.**", ephemeral=True)

async def setup(bot):
    await bot.add_cog(MusicCommands(bot))