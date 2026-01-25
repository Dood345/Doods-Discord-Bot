import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import logging

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

    async def play_next(self, interaction):
        """Callback to play the next song in the queue"""
        if self.queue:
            # Pop the next song
            url, title = self.queue.pop(0)
            self.current = title
            
            voice_client = interaction.guild.voice_client
            if not voice_client:
                return

            try:
                # 1. Get the stream URL (We do this JIT - Just In Time - to prevent expiry)
                loop = self.bot.loop or asyncio.get_event_loop()
                data = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(YDL_OPTIONS).extract_info(url, download=False))
                
                if 'entries' in data: # Handle edge case where search returns a list
                    data = data['entries'][0]
                    
                stream_url = data['url']
                
                # 2. Play
                source = discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS)
                
                def after_playing(e):
                    if e: logger.error(f"Playback error: {e}")
                    # Recursive call to keep the queue moving
                    asyncio.run_coroutine_threadsafe(self.play_next(interaction), self.bot.loop)

                voice_client.play(source, after=after_playing)
                
                # Optional: Send a "Now Playing" update
                # (Note: sending messages from a callback is tricky, usually we skip it or update a status)
                
            except Exception as e:
                logger.error(f"Failed to play {title}: {e}")
                self.current = None
                await self.play_next(interaction) # Skip to next
        else:
            self.current = None
            # Auto-disconnect if queue empty? Optional.
            # await interaction.guild.voice_client.disconnect()

    @app_commands.command(name="play", description="Play audio from YouTube (Search or Link)")
    async def play(self, interaction: discord.Interaction, query: str):
        """Robust YouTube Player"""
        await interaction.response.defer()

        # 1. Voice Channel Check
        if not interaction.user.voice:
            await interaction.followup.send("🎙️ **Cave here.** You need to be in a voice channel. I can't pipe audio directly into your brain... yet.")
            return

        vc = interaction.guild.voice_client
        if not vc:
            vc = await interaction.user.voice.channel.connect()

        # 2. Search / Extraction
        msg = await interaction.followup.send(f"🔍 **Searching:** `{query}`...")
        
        try:
            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                # "extract_flat" is fast for playlists
                info = ydl.extract_info(query, download=False)

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
                    await msg.edit(content=f"🎵 **Found:** {entry['title']}")
            else:
                # Direct Link
                added_songs.append((info['url'], info['title']))
                await msg.edit(content=f"🎵 **Found:** {info['title']}")

            # 4. Add to Queue
            self.queue.extend(added_songs)

            # 5. Start Playback if Idle
            if not vc.is_playing():
                await self.play_next(interaction)

        except Exception as e:
            logger.error(f"YTDL Error: {e}")
            await msg.edit(content="⚠️ **Error:** The audio processor caught fire. Check the link or try a different search.")

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

        desc = f"**Now Playing:** {self.current}\n\n**Up Next:**\n"
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
            self.queue = [] # Wipe queue
            self.current = None
            vc.stop()
            await vc.disconnect()
            await interaction.response.send_message("🛑 **Testing Concluded.**")
        else:
            await interaction.response.send_message("I'm not connected.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(MusicCommands(bot))