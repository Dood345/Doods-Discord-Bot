"""Voice Cave: /speak makes Cave answer out loud in your voice channel (edge-tts)."""

import asyncio
import logging
import os
import re
import tempfile

import discord
import edge_tts
from discord import app_commands
from discord.ext import commands

from config import BotConfig

logger = logging.getLogger(__name__)

MAX_SPOKEN_CHARS = 600
SPEAK_TIMEOUT = 90  # seconds of audio at most


def speakable(text: str) -> str:
    """Strip markdown, links, custom emoji and symbols that TTS would read out literally."""
    text = re.sub(r"<a?:\w+:\d+>", "", text)              # custom emoji
    text = re.sub(r"<[@#][!&]?\d+>", "", text)             # mentions
    text = re.sub(r"https?://\S+", "a link", text)
    text = re.sub(r"[*_`~>|#]+", "", text)                 # markdown
    text = re.sub(r"[^\w\s.,!?;:'\"()\-%$&/]", "", text)   # emoji and other symbols
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > MAX_SPOKEN_CHARS:
        text = text[:MAX_SPOKEN_CHARS].rsplit(" ", 1)[0] + "..."
    return text


class VoiceCave(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._speaking = set()  # guild ids

    async def synthesize(self, text: str) -> str:
        """Write speech to a temp mp3 and return its path (caller deletes it)."""
        fd, path = tempfile.mkstemp(suffix=".mp3", prefix="cave_tts_")
        os.close(fd)
        await edge_tts.Communicate(text, BotConfig.MUSIC_TTS_VOICE).save(path)
        return path

    def _voice_problem(self, member, guild) -> str | None:
        voice = getattr(member, "voice", None)
        if not voice or not voice.channel:
            return "🎙️ Join a voice channel first and I'll say it to your face."
        vc = guild.voice_client
        if vc and vc.channel and (vc.is_playing() or vc.is_paused()):
            if vc.channel.id != voice.channel.id:
                return f"🎙️ I'm busy broadcasting in {vc.channel.name}."
            return "🎵 I won't talk over the music. Pause it (or wait) and ask again."
        if guild.id in self._speaking:
            return "🎙️ One speech at a time. I'm not a choir."
        return None

    async def speak(self, member: discord.Member, text: str) -> str | None:
        """Say `text` in the member's voice channel. Returns an error string, or None once spoken."""
        guild = member.guild
        problem = self._voice_problem(member, guild)
        if problem:
            return problem
        spoken = speakable(text)
        if not spoken:
            return None
        self._speaking.add(guild.id)
        path = None
        joined = False
        try:
            path = await self.synthesize(spoken)
            vc = guild.voice_client
            target = member.voice.channel
            if vc is None:
                vc = await target.connect()
                joined = True
            elif vc.channel.id != target.id:
                await vc.move_to(target)
            done = asyncio.Event()
            loop = asyncio.get_running_loop()
            music = self.bot.get_cog("MusicCommands")
            volume = (music.volume if music else BotConfig.MUSIC_DEFAULT_VOLUME) + 0.2
            source = discord.FFmpegOpusAudio(path, bitrate=BotConfig.MUSIC_BITRATE, options=f"-filter:a volume={volume:.2f}")
            vc.play(source, after=lambda e: loop.call_soon_threadsafe(done.set))
            await asyncio.wait_for(done.wait(), SPEAK_TIMEOUT)
            return None
        except Exception as e:
            logger.error(f"Voice Cave failed: {e}")
            return "🎙️ My vocal cords (a 1950s ham radio) are on the fritz."
        finally:
            self._speaking.discard(guild.id)
            if path and os.path.exists(path):
                os.remove(path)
            vc = guild.voice_client
            if joined and vc and not vc.is_playing() and not vc.is_paused():
                await vc.disconnect()

    @app_commands.command(name="speak", description="Ask Cave something and he answers out loud in your voice channel")
    @app_commands.describe(prompt="What to ask Cave")
    @app_commands.guild_only()
    async def speak_command(self, interaction: discord.Interaction, prompt: str):
        problem = self._voice_problem(interaction.user, interaction.guild)
        if problem:
            await interaction.response.send_message(problem, ephemeral=True)
            return
        await interaction.response.defer()
        reply = await self.bot.ai_handler.get_chat_response(
            interaction.user.id, prompt, interaction.guild_id, user=interaction.user,
            guild=interaction.guild, channel=interaction.channel)
        reply = reply or "🤖 *confused processing noises*"
        await interaction.followup.send(f"🎙️ {reply}"[:2000])
        error = await self.speak(interaction.user, reply)
        if error:
            await interaction.followup.send(error, ephemeral=True)


async def setup(bot):
    await bot.add_cog(VoiceCave(bot))
