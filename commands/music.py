import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import logging
import os
import edge_tts

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
        self.queue = []      # List of (url, title) tuples
        self.current = None  # Currently playing track info
        self.volume = 0.5    # Default volume
        self.history = []    # History of played tracks (url, title)
        self.tts_enabled = False # Default to OFF (Safety first)
        self.music_channel = None # We need to remember where to speak
        
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
        self.queue = []
        self.history = []
        self.current = None
        
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

    async def play_next(self, interaction):
        """Callback to play the next song in the queue"""
        # STOP if bot is shutting down
        if self.bot.is_closed():
            return

        if self.queue:
            # Save previous track to history if it finished naturally
            if self.current:
                self.history.append(self.current)
                # Keep history limited to last 20 songs to save memory
                if len(self.history) > 20: 
                    self.history.pop(0)

            # Pop the next song
            url, title = self.queue.pop(0)
            self.current = (url, title)
            
            voice_client = interaction.guild.voice_client
            if not voice_client:
                return

            try:
                # 1. Get Stream URL (JIT)
                loop = self.bot.loop or asyncio.get_event_loop()
                data = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(YDL_OPTIONS).extract_info(url, download=False))
                
                if 'entries' in data:
                    data = data['entries'][0]
                
                stream_url = data['url']
                
                # 2. Update Facility Status (Local Voice Channel)
                # Local Channel Status
                vc_channel = interaction.guild.voice_client.channel
                
                # Check for permissions first so we don't crash if we can't edit
                if vc_channel.permissions_for(interaction.guild.me).manage_channels:
                    # Discord status supports emojis, so we add a music note
                    await vc_channel.edit(status=f"🎶 {title}")
                else:
                    logger.warning("Missing 'Manage Channels' permission. Cannot update VC status.")

                # --- THE PLAYBACK CHAIN ---
                
                # Define the Final Step: The Callback when song ends
                def after_song_ends(error):
                    if error: logger.error(f"Song Error: {error}")
                    asyncio.run_coroutine_threadsafe(self.play_next(interaction), self.bot.loop)

                # Define Step 2: Play the Song
                def play_song(error=None):
                    if error: logger.error(f"TTS Error: {error}")
                    
                    # Create Song Source
                    song_source = discord.PCMVolumeTransformer(
                        discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS), 
                        volume=self.volume
                    )
                    voice_client.play(song_source, after=after_song_ends)

                # Define Step 1: TTS Announcement (Optional)
                if self.tts_enabled:
                    # Clean title: "Song Name (Official Video)" -> "Song Name"
                    clean_title = title.split('(')[0].split('[')[0]
                    announcement_text = f"Now playing: {clean_title}"
                    
                    # NEW: Await the async generator directly
                    # (No need for loop.run_in_executor anymore because edge_tts is native async)
                    success = await self.generate_announcement(announcement_text)
                    
                    if success and os.path.exists("tts_announcement.mp3"):
                        # Play TTS, then call play_song
                        tts_source = discord.PCMVolumeTransformer(
                            discord.FFmpegPCMAudio("tts_announcement.mp3"), 
                            volume=self.volume + 0.2 # Make TTS slightly louder
                        )
                        voice_client.play(tts_source, after=play_song)
                    else:
                        # Fallback if TTS fails
                        play_song(None)
                else:
                    # TTS Disabled: Skip straight to song
                    play_song(None)

            except Exception as e:
                logger.error(f"Failed to play {title}: {e}")
                self.current = None
                await self.play_next(interaction)
        else:
            self.current = None
            await self.bot.change_presence(activity=discord.Game(name="Science | /help"))

    @app_commands.command(name="play-tts", description="Toggle the vocal announcement system")
    async def toggle_tts(self, interaction: discord.Interaction):
        self.tts_enabled = not self.tts_enabled
        state = "ONLINE" if self.tts_enabled else "OFFLINE"
        await interaction.response.send_message(f"🎙️ **Facility Announcer {state}.**")

    @app_commands.command(name="play", description="Play audio from YouTube (Search or Link)")
    @app_commands.describe(query="Search term (e.g. 'lofi hip hop')", url="Direct YouTube Link", force_play="Play immediately (interrupt current)")
    @app_commands.rename(force_play="force-play")
    async def play(self, interaction: discord.Interaction, query: str = None, url: str = None, force_play: bool = False):
        """Robust YouTube Player"""
        await interaction.response.defer()
        
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
                 target = f"ytsearch:{target}"

        # 1. Voice Channel Check
        if not interaction.user.voice:
            await interaction.followup.send("🎙️ **Cave here.** You need to be in a voice channel. I can't pipe audio directly into your brain... yet.")
            return

        vc = interaction.guild.voice_client
        if not vc:
            vc = await interaction.user.voice.channel.connect()

        # 2. Search / Extraction
        if is_direct_link:
            msg = await interaction.followup.send(f"**Loading Link:** `{target}`...")
        else:
            msg = await interaction.followup.send(f"🔍 **Searching:** `{target}`...")
        
        try:
            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                # "extract_flat" is fast for playlists
                info = ydl.extract_info(target, download=False)

            # 3. Handle Results (Single vs Playlist)
            added_songs = []
            
            if 'entries' in info:
                # It's a Playlist or a Search Result
                if info.get('_type') == 'playlist' and len(info['entries']) > 1:
                    # It is an ACTUAL playlist
                    for entry in info['entries']:
                        added_songs.append((entry['url'], entry['title']))
                    await msg.edit(content=f"📝 **Playlist Queued:** Added {len(added_songs)} tracks from *{info['title']}*.")
                else:
                    # It is a Search Result (take the first one)
                    entry = info['entries'][0]
                    added_songs.append((entry['url'], entry['title']))
                    if is_direct_link:
                        await msg.edit(content=f"🎵 **Added:** {entry['title']}")
                    else:
                        await msg.edit(content=f"🎵 **Found:** {entry['title']}")
            else:
                # Direct Link
                added_songs.append((info['url'], info['title']))
                await msg.edit(content=f"🎵 **Added:** {info['title']}")

            # 4. Add to Queue (Normal or Play Now)
            if force_play:
                 # Interrupt Priority: [NewSong, CurrentSong, RestOfQueue...]
                self.queue[0:0] = added_songs # Prepend new songs
                
                if vc.is_playing() and self.current:
                    # If playing, we need to save the current song right after the new one
                    # self.current is (url, title) tuple now
                    self.queue.insert(len(added_songs), self.current)
                    
                    # Stopping triggers 'after_playing' -> play_next() -> pops index 0 (NewSong)
                    vc.stop()
                    await msg.edit(content=f"🚨 **Interrupted!** Playing {added_songs[0][1]} immediately.")
                else:
                    # If idle, just start playing
                    if not vc.is_playing():
                        await self.play_next(interaction)
            else:
                # Normal Queue
                self.queue.extend(added_songs)

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
        if not vc:
             await interaction.response.send_message("I'm not connected.", ephemeral=True)
             return

        if not self.history:
             await interaction.response.send_message("❌ **No history.** We can only move forward, not backward.", ephemeral=True)
             return

        # Get last song
        last_track = self.history.pop()
        
        # If something is currently playing, put it back at the start of queue (so 'Skip' goes back to it)
        # OR should we put it back in history? 
        # Let's put it in queue pos 0 so it's "next" again.
        if self.current:
             self.queue.insert(0, self.current)
        
        # Put the previous track at SUPER priority (index 0)
        self.queue.insert(0, last_track)
        
        # Stop current track to trigger play_next() which will pick up the previous track we just pushed
        # Note: play_next normally saves current to history.
        # We don't want to duplicate the "current" song into history if we just manually moved it to queue.
        # So we clear current before stopping?
        # Actually play_next saves "if self.current".
        # If we set self.current = None here, play_next won't save it.
        # But we ALREADY pushed it to queue. So that's correct.
        
        self.current = None 
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
        if not self.queue and not self.current:
            await interaction.response.send_message("The queue is empty. Silence is inefficient.")
            return

        # Handle tuple vs string (compatibility)
        current_title = self.current[1] if isinstance(self.current, tuple) else str(self.current)
        
        desc = f"**Now Playing:** {current_title}\n\n**Up Next:**\n"
        for i, (url, title) in enumerate(self.queue[:10], 1):
            desc += f"`{i}.` {title}\n"
        
        if len(self.queue) > 10:
            desc += f"*...and {len(self.queue)-10} more.*"

        embed = discord.Embed(title="🎧 Audio Testing Queue", description=desc, color=0xFFA500)
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="stop", description="Clear queue and disconnect")
    async def stop(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc:
            # --- NEW CLEANUP LOGIC ---
            channel = vc.channel
            if channel.permissions_for(interaction.guild.me).manage_channels:
                 # Setting status to None removes it
                 await channel.edit(status=None) 
            # -------------------------

            self.queue = []
            self.current = None
            vc.stop()
            await vc.disconnect()
            
            await interaction.response.send_message("🛑 **Testing Concluded.**")
        else:
            await interaction.response.send_message("I'm not connected.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(MusicCommands(bot))