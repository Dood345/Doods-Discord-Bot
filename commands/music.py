import discord
from discord import app_commands
from discord.ext import commands, tasks
import yt_dlp
import asyncio
import logging
import os
import edge_tts
import re
import shutil
import tempfile
import time
from urllib.parse import urlparse
from config import BotConfig
from services.music_library import PLEX_PREFIX, MATCH_THRESHOLD, match_score
from services.music_sessions import REWIND, MusicSessionStore, fmt_time, is_stale, place_request, snapshot

logger = logging.getLogger(__name__)


def _js_runtimes() -> dict:
    try:
        import deno
        return {'deno': {'path': deno.find_deno_bin()}}
    except Exception:
        return {'node': {}}


# OPTIMIZED YOUTUBE CONFIGURATION
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': False,          # CHANGED: Allow playlists!
    'extract_flat': 'in_playlist',# Optimization: Don't download playlist details until needed
    'quiet': True,
    'default_search': 'ytsearch', # Default to searching YouTube
    'source_address': '0.0.0.0',
    # 'match_filter': yt_dlp.utils.match_filter_func('!is_live'), # Optional: Skip livestreams
    # Python-API name is 'cookiefile' ('cookies' was silently ignored, so cookies were never used)
    'cookiefile': 'www.youtube.com_cookies.txt',
    # YouTube's JS challenges (EJS) need a supported runtime; the server's Node 20 is too old,
    # so use the Deno binary from the `deno` PyPI package (installed into the venv)
    'js_runtimes': _js_runtimes(),
    # Proof-of-Origin tokens from the bgutil provider container (see CLAUDE.md > Music)
    'extractor_args': {
        'youtubepot-bgutilhttp': {'base_url': [BotConfig.YT_POT_PROVIDER_URL]},
    },
}

YOUTUBE_HOSTS = {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtu.be'}

VARIANT_WORDS = {'remix', 'cover', 'live', 'nightcore', 'sped', 'slowed', 'reverb', 'instrumental', 'karaoke', 'mashup', 'edit', 'bootleg'}

YOUTUBE_BLOCKED_MSG = ("YouTube is blocking the server with a 'confirm you're not a bot' check. "
                       "The owner needs to refresh the YouTube cookies file on the server.")


def is_youtube_bot_check(error: Exception) -> bool:
    """YouTube's anti-bot wall (stale/missing cookies) rather than a problem with one video."""
    text = str(error).lower()
    return "not a bot" in text or "page needs to be reloaded" in text or "cookies" in text

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

# HLS streams (most SoundCloud tracks now) make ffmpeg fetch each segment only when it needs it: playback
# stalls at every segment boundary and discord.py then rushes to catch up, so the music audibly slows
# down and speeds up. Those tracks are downloaded first (a few seconds for a song) and played from disk.
BUFFER_DIR = os.path.join(tempfile.gettempdir(), "doodlab_music")
BUFFER_MAX_SECONDS = 3 * 60 * 60   # longer than this (marathon mixes): stream instead of downloading


def needs_buffering(info: dict) -> bool:
    return str(info.get('protocol') or '').startswith('m3u8') and (info.get('duration') or 0) <= BUFFER_MAX_SECONDS


def buffer_to_disk(url: str, info: dict) -> str:
    """Download the already-chosen format of `url` into BUFFER_DIR (blocking; run in an executor)."""
    os.makedirs(BUFFER_DIR, exist_ok=True)
    opts = dict(YDL_OPTIONS, format=info['format_id'], noplaylist=True, extract_flat=False, noprogress=True,
                outtmpl=os.path.join(BUFFER_DIR, '%(extractor)s-%(id)s.%(ext)s'))
    with yt_dlp.YoutubeDL(opts) as ydl:
        result = ydl.extract_info(info.get('webpage_url') or url, download=True)
        downloads = result.get('requested_downloads') or []
        return downloads[0]['filepath'] if downloads else ydl.prepare_filename(result)


def discard_buffer(path: str | None) -> None:
    if path and path.startswith(BUFFER_DIR):
        try:
            os.remove(path)
        except OSError:
            pass

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
        self.last_active: float | None = None  # last time a track started or was queued

class MusicCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.players: dict[int, GuildPlayer] = {} # {channel_id: GuildPlayer}
        self.volume: float = BotConfig.MUSIC_DEFAULT_VOLUME 
        self.tts_settings: dict[int, bool] = {} # {guild_id: bool} (TTS preference per server)
        self.sessions = MusicSessionStore(bot.db) if getattr(bot, "db", None) else None
        
    async def cog_load(self):
        """Check for FFmpeg availability on load"""
        if self.sessions:
            self.save_sessions.start()
        # Leftover buffered tracks from before a restart
        shutil.rmtree(BUFFER_DIR, ignore_errors=True)
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
        # Stop saving first, so the last snapshot (what was playing) survives the shutdown
        self.save_sessions.cancel()
        self.players.clear()
        
        # Disconnect from all voice channels
        for vc in self.bot.voice_clients:
            try:
                self.bot.loop.create_task(vc.disconnect(force=True))
            except Exception as e:
                logger.error(f"Failed to disconnect cleanly: {e}")

    # --- Resume after a restart -------------------------------------------------

    def _active_sessions(self) -> list:
        """Snapshots of players that are actually connected and have something on."""
        by_channel = {vc.channel.id: vc.guild for vc in self.bot.voice_clients if getattr(vc, "channel", None)}
        snaps = []
        for channel_id, player in self.players.items():
            guild = by_channel.get(channel_id)
            snap = snapshot(player, guild.id) if guild else None
            if snap:
                snaps.append(snap)
        return snaps

    @tasks.loop(seconds=10)
    async def save_sessions(self):
        if self.bot.is_closed():
            return
        try:
            # Forget players that lost voice and haven't been used for a day (their queue would be a surprise)
            connected = {vc.channel.id for vc in self.bot.voice_clients if getattr(vc, "channel", None)}
            for channel_id in [c for c, p in self.players.items() if c not in connected and is_stale(p)]:
                del self.players[channel_id]
            snaps = self._active_sessions()
            await self.sessions.save_all(snaps)
            summary = (len(snaps), len(self.players), len(self.bot.voice_clients))
            if summary != getattr(self, "_last_save_summary", None):
                self._last_save_summary = summary
                logger.info(f"Music sessions saved: {summary[0]} (players: {summary[1]}, "
                            f"voice connections: {summary[2]}, playing: "
                            f"{[bool(p.current_track) for p in self.players.values()]})")
        except Exception as e:
            logger.warning(f"Saving music sessions failed: {e}")

    @save_sessions.before_loop
    async def before_save_sessions(self):
        await self.bot.wait_until_ready()
        # Resume before the first save, which would otherwise overwrite what was playing
        try:
            await self.restore_sessions()
        except Exception as e:
            logger.exception(f"Resuming music failed: {e}")

    async def restore_sessions(self) -> int:
        """Rejoin voice and resume each recent session whose channel still has people in it."""
        resumed = 0
        for s in await self.sessions.load_recent():
            channel = self.bot.get_channel(s.channel_id)
            if not isinstance(channel, discord.VoiceChannel) or not any(not m.bot for m in channel.members):
                continue  # everyone left while we were down
            guild = channel.guild
            try:
                vc = guild.voice_client
                if vc and vc.channel and vc.channel.id != channel.id:
                    continue  # already busy elsewhere in this server
                if not vc:
                    await channel.connect()
                player = GuildPlayer(channel.id)
                player.queue = list(s.queue)
                player.current_track = s.current
                text = self.bot.get_channel(s.text_channel_id) if s.text_channel_id else None
                player.notification_channel = text if isinstance(text, discord.TextChannel) else None
                player.seek_position = max(0.0, s.position - REWIND)
                self.players[channel.id] = player
                await self.play_next(guild)
                if s.paused and guild.voice_client and guild.voice_client.is_playing():
                    guild.voice_client.pause()
                    player.pause_start_time = time.time()
                resumed += 1
                logger.info(f"Resumed music in guild {guild.id} at {fmt_time(s.position)}")
                if player.notification_channel:
                    state = "paused at" if s.paused else "picking up at"
                    more = f" (+{len(s.queue)} queued)" if s.queue else ""
                    await player.notification_channel.send(
                        f"🔁 **Facility rebooted.** Back in {channel.mention}, {state} {fmt_time(s.position)} in "
                        f"**{s.current[1]}**{more}.")
            except Exception as e:
                logger.warning(f"Couldn't resume music in channel {s.channel_id}: {e}")
        return resumed

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

    @staticmethod
    def _opus_source(source: str, volume: float, before_options: str | None = None, options: str = "") -> discord.FFmpegOpusAudio:
        """ffmpeg applies volume and encodes Opus once at full bitrate; discord.py just sends the packets.

        (The old FFmpegPCMAudio + PCMVolumeTransformer path re-encoded in Python with discord.py's
        encoder, which reserves bitrate for 15% packet-loss recovery and sounds noticeably worse.)
        """
        return discord.FFmpegOpusAudio(
            source,
            bitrate=BotConfig.MUSIC_BITRATE,
            before_options=before_options,
            options=f"{options} -filter:a volume={volume:.2f}".strip(),
        )

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

    async def play_next(self, guild: discord.Guild | None) -> None:
        """Callback to play the next song in the queue"""
        # STOP if bot is shutting down
        if self.bot.is_closed():
            return

        # Dynamically determine which channel we are servicing
        # The bot can be in multiple guilds, so we need to find the voice_client context
        if not guild:
            return
            
        voice_client = guild.voice_client
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
            
        player.last_active = time.time()
        try:
            # 1. Get Stream URL (JIT)
            extra_before = ""
            local_file = None
            if url.startswith(PLEX_PREFIX):
                # Library track: stream straight from Plex (token sent as a header)
                stream_url, extra_before = self.bot.music_library.stream_source(url)
            else:
                loop = self.bot.loop or asyncio.get_event_loop()
                data = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(YDL_OPTIONS).extract_info(url, download=False))

                if data and 'entries' in data:
                    data = data['entries'][0]

                stream_url = data['url']
                if needs_buffering(data):
                    stream_url = await loop.run_in_executor(None, lambda: buffer_to_disk(url, data))
                    local_file = stream_url
            
            # 2. Update Facility Status
            vc_channel = voice_client.channel
            if vc_channel.permissions_for(guild.me).manage_channels:
                if seek_time:
                    await vc_channel.edit(status=f"⏩ {title} (+{int(seek_time)}s)")
                else:
                    await vc_channel.edit(status=f"🎶 {title}")
            else:
                logger.warning("Missing 'Manage Channels' permission. Cannot update VC status.")

            # --- THE PLAYBACK CHAIN ---
            
            def after_song_ends(error: Exception | None) -> None:
                if error: logger.error(f"Song Error: {error}")
                discard_buffer(local_file)
                asyncio.run_coroutine_threadsafe(self.play_next(guild), self.bot.loop)

            def play_song(error: Exception | None = None) -> None:
                if error: logger.error(f"TTS Error: {error}")
                
                # Dynamic FFMPEG Options for Seeking
                current_opts = FFMPEG_OPTIONS.copy()
                if local_file:
                    current_opts['before_options'] = ''  # reconnect flags only apply to network input
                if extra_before:
                    current_opts['before_options'] = f"{current_opts['before_options']} {extra_before}"
                if seek_time:
                    # Inject -ss before_options
                    # We append it to existing options
                    current_opts['before_options'] = str(current_opts.get('before_options', '')) + f" -ss {seek_time}"
                
                voice_client.play(self._opus_source(stream_url, self.volume, **current_opts), after=after_song_ends)
                
                # Record Start Time (Adjusted for seek so Elapsed Time logic works)
                # If we seek to 30s, we pretend we started 30s ago.
                player.start_time = time.time() - (seek_time if seek_time else 0)

            # Define Step 1: TTS Announcement (Skip if Seeking)
            if not seek_time and self.tts_settings.get(guild.id, False):
                clean_title = title.split('(')[0].split('[')[0]
                announcement_text = f"Now playing: {clean_title}"
                
                success = await self.generate_announcement(announcement_text)
                
                if success and os.path.exists("tts_announcement.mp3"):
                    voice_client.play(self._opus_source("tts_announcement.mp3", self.volume + 0.2), after=play_song)
                else:
                    play_song(None)
            else:
                play_song(None)

        except yt_dlp.utils.DownloadError as e:
            logger.error(f"YTDL DownloadError for {title}: {e}")
            player.current_track = None
            if is_youtube_bot_check(e):
                # Every track would fail the same way; stop instead of burning through the queue
                if player.notification_channel:
                    await player.notification_channel.send(f"⚠️ **Couldn't play {title}.** {YOUTUBE_BLOCKED_MSG}")
                await self.bot.change_presence(activity=discord.Game(name="Science | /help"))
                return
            await self.play_next(guild)
        except Exception as e:
            logger.error(f"Failed to play {title}: {e}")
            # If seek fails, just move next
            player.current_track = None
            await self.play_next(guild)

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

    # --- Chat (AI tool) entry points: one track at a time, no interaction object ---

    async def resolve_track(self, query: str, skip_library: bool = False) -> tuple[str, str, str] | str:
        """Find a single track. Returns (url, title, uploader) or an error string.

        YouTube links play from YouTube. Anything else is a song request, tried in order:
        the owner's Plex library, then SoundCloud, then a YouTube search (most likely to be bot-blocked).
        """
        query = query.strip()
        if query.startswith(('http://', 'https://')):
            # The bot runs inside the LAN and yt-dlp fetches any URL, so only allow YouTube links from chat
            host = (urlparse(query).hostname or '').lower()
            if host not in YOUTUBE_HOSTS:
                return "Only YouTube links or search terms are allowed."
            target = query
        else:
            library = None if skip_library else getattr(self.bot, "music_library", None)
            if library is not None and library.available:
                track = await library.find(query)
                if track:
                    return track
            track = await self._search_soundcloud(query)
            if track:
                return track
            target = f"ytsearch:{query}"

        try:
            info = await self._fetch_youtube_data(target)
        except yt_dlp.utils.DownloadError as e:
            logger.warning(f"resolve_track failed for {query!r}: {e}")
            if is_youtube_bot_check(e):
                return YOUTUBE_BLOCKED_MSG
            return "YouTube couldn't load that one (it may be private, age-restricted or removed)."
        if not info:
            return "No playable tracks found."
        if 'entries' in info:
            if target != f"ytsearch:{query}" and info.get('_type') == 'playlist':
                return "That's a playlist. Use /play for playlists; I only queue single tracks from chat."
            entries = [e for e in info['entries'] if e]
            if not entries:
                return "No playable tracks found."
            info = entries[0]
        return (info['url'], info['title'], info.get('uploader', 'Unknown Artist'))

    async def _search_soundcloud(self, query: str) -> tuple[str, str, str] | None:
        """First SoundCloud result whose title/uploader actually matches the request (skips random remixes)."""
        try:
            info = await self._fetch_youtube_data(f"scsearch5:{query}")
        except Exception as e:
            logger.info(f"SoundCloud search failed for {query!r}: {e}")
            return None
        wanted_variants = VARIANT_WORDS & set(query.lower().split())
        candidates = []
        for rank, entry in enumerate((info or {}).get('entries') or []):
            if not entry or not entry.get('url'):
                continue
            uploader = entry.get('uploader') or 'Unknown Artist'
            title = entry.get('title', 'Unknown')
            if match_score(query, f"{title} {uploader}") < MATCH_THRESHOLD:
                continue
            # Prefer the original over remixes/covers/live cuts unless the request asks for one
            is_variant = bool((VARIANT_WORDS - wanted_variants) & set(re.findall(r"[a-z]+", title.lower())))
            candidates.append((is_variant, rank, (entry['url'], title, uploader)))
        return min(candidates)[2] if candidates else None

    @staticmethod
    def track_source(url: str) -> str:
        if url.startswith(PLEX_PREFIX):
            return "📀 the facility archives"
        if "soundcloud.com" in url:
            return "☁️ SoundCloud"
        return "▶️ YouTube"

    async def resolve_request(self, query: str, radio: bool = False) -> tuple[list[tuple[str, str, str]], str] | str:
        """What a chat song request should queue: ([tracks], description) or an error string.

        Library requests can become an artist mix or a radio station; everything else is one track.
        """
        query = query.strip()
        if not query.startswith(('http://', 'https://')):
            library = getattr(self.bot, "music_library", None)
            if library is not None and library.available:
                planned = await library.plan(query, radio=radio)
                if planned:
                    return planned
        track = await self.resolve_track(query, skip_library=True)
        if isinstance(track, str):
            return track
        return [track], f"**{track[1]}** by {track[2]}"

    async def enqueue_track(self, member: discord.Member, text_channel, track: tuple[str, str, str]) -> str:
        return await self.enqueue_tracks(member, text_channel, [track])

    async def enqueue_tracks(self, member: discord.Member, text_channel, tracks: list[tuple[str, str, str]]) -> str:
        """Queue resolved tracks in the member's voice channel; joins voice if needed."""
        if not member.voice or not member.voice.channel:
            return "🎙️ You need to be in a voice channel for me to pipe audio at you."
        guild = member.guild
        target = member.voice.channel
        vc = guild.voice_client
        if vc and vc.channel and vc.channel.id != target.id:
            if vc.is_playing() or vc.is_paused():
                # Don't hijack a session already running in another channel
                return f"🎙️ I'm already broadcasting in {vc.channel.name}. Join that channel or use /play."
            await vc.move_to(target)
            vc = guild.voice_client
        elif not vc:
            vc = await target.connect()

        player = self.players.setdefault(target.id, GuildPlayer(target.id))
        if isinstance(text_channel, discord.TextChannel):
            player.notification_channel = text_channel
        first = tracks[0]
        idle = not vc.is_playing() and not vc.is_paused()
        leftover = place_request(player, tracks, idle)
        more = f" (+{len(tracks) - 1} more queued)" if len(tracks) > 1 else ""

        if idle:
            await self.play_next(guild)
            return self._started_message(player, tracks, more, leftover)
        if len(tracks) > 1:
            return f"🎵 Queued {len(tracks)} tracks, starting with **{first[1]}** by {first[2]}."
        return f"🎵 Queued **{first[1]}** by {first[2]} (#{len(player.queue)} in line)."

    @staticmethod
    def _started_message(player: GuildPlayer, tracks: list, more: str, leftover: int) -> str:
        """What actually started after an idle request (Cave repeats this, so it must be true)."""
        current = player.current_track
        if not current:
            return "⚠️ Couldn't start that one; the audio processor refused it."
        if current not in tracks:
            return f"🎵 Couldn't play your request, so the queue moved on: now playing **{current[1]}** by {current[2]}."
        after = f" Then picking up the {leftover} track{'s' if leftover != 1 else ''} left from earlier." if leftover else ""
        return f"🎵 Now playing **{current[1]}** by {current[2]}{more}.{after}"

    @app_commands.command(name="play-tts", description="Toggle the vocal announcement system")
    async def toggle_tts(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        guild_id = interaction.guild.id
        current_setting = self.tts_settings.get(guild_id, False)
        self.tts_settings[guild_id] = not current_setting
        
        state = "ONLINE" if self.tts_settings[guild_id] else "OFFLINE"
        await interaction.response.send_message(f"🎙️ **Facility Announcer {state}.**")

    @app_commands.command(name="play", description="Play a song, artist or link (facility archives first, then SoundCloud/YouTube)")
    @app_commands.describe(
        query="Song or artist (e.g. 'kryptonite' or '3 doors down')",
        url="Direct YouTube Link",
        force_play="Play immediately (interrupt current)",
        playlist_only="Search YouTube specifically for playlists (Default: False)",
        radio="Start a radio station of similar music from this song or artist"
    )
    @app_commands.rename(force_play="force-play", playlist_only="playlist-only")
    async def play(self, interaction: discord.Interaction, query: str | None = None, url: str | None = None, force_play: bool = False, playlist_only: bool = False, radio: bool = False) -> None:
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

        # Plain song/artist requests go library-first (Plex -> SoundCloud -> YouTube), like Cave's queue_song
        if not is_direct_link and not playlist_only and query and not query.startswith(('http://', 'https://')):
            msg = await interaction.followup.send(f"🔍 **Searching:** `{query}`...")
            try:
                planned = await self.resolve_request(query, radio=radio)
            except Exception as e:
                logger.error(f"Unexpected Error in play: {e}")
                planned = "The audio processor caught fire. Something unexpected happened."
            if isinstance(planned, str):
                await msg.edit(content=f"⚠️ **Error:** {planned}")
                return
            tracks, description = planned
            await msg.edit(content=f"🎵 **Found:** {description} ({self.track_source(tracks[0][0])})")
            await self._add_to_queue(interaction.guild, vc, player, tracks, force_play, msg)
            return

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

            await self._add_to_queue(interaction.guild, vc, player, added_songs, force_play, msg)

        except yt_dlp.utils.DownloadError as e:
            logger.error(f"YTDL Error: {e}")
            await msg.edit(content="⚠️ **Error:** The audio processor caught fire (DownloadError). Check the link.")
        except Exception as e:
            logger.error(f"Unexpected Error in play: {e}")
            await msg.edit(content="⚠️ **Error:** The audio processor caught fire. Something unexpected happened.")

    async def _add_to_queue(self, guild, vc, player: GuildPlayer, added_songs, force_play: bool, msg) -> None:
        if force_play:
            player.queue = added_songs + player.queue
            current_track_info = player.current_track
            if vc.is_playing() and current_track_info:
                player.queue.insert(len(added_songs), current_track_info)
                vc.stop()
                await msg.edit(content=f"🚨 **Interrupted!** Playing {added_songs[0][1]} immediately.")
            elif not vc.is_playing() and not vc.is_paused():
                await self.play_next(guild)
        else:
            idle = not vc.is_playing() and not vc.is_paused()
            leftover = place_request(player, added_songs, idle)
            if idle:
                await self.play_next(guild)
                if leftover or player.current_track not in added_songs:
                    await msg.edit(content=self._started_message(player, added_songs, "", leftover))

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
        if self.skip_current(interaction.guild):
            await interaction.response.send_message("⏭️ **Skipped.** Protocol advanced.")
        else:
            await interaction.response.send_message("Nothing is playing, genius.", ephemeral=True)

    def skip_current(self, guild: discord.Guild | None) -> tuple[str, str, str] | None:
        """Skip the playing (or paused) track; returns the skipped track, or None if nothing was on."""
        vc = guild.voice_client if guild else None
        if not vc or not (vc.is_playing() or vc.is_paused()):
            return None
        player = self.players.get(vc.channel.id) if getattr(vc, "channel", None) else None
        track = player.current_track if player else None
        vc.stop()  # triggers the 'after' callback, which calls play_next()
        return track or ("", "the current track", "")

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