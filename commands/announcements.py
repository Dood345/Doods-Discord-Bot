"""Facility announcements (opt-in): new media, birthdays, and printer-finished DMs to the owner."""

import io
import logging

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import BotConfig
from services.announcement_service import AnnouncementService
from utils.members import find_member

logger = logging.getLogger(__name__)


class Announcements(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.service = AnnouncementService(bot.db, bot.homelab_service)

    async def cog_load(self):
        self.tick.start()

    async def cog_unload(self):
        self.tick.cancel()

    # --- Server opt-in ---

    group = app_commands.Group(name="announcements", description="Facility announcements (server managers)",
                               default_permissions=discord.Permissions(manage_guild=True), guild_only=True)

    @group.command(name="channel", description="Post new media arrivals and birthday shout-outs here")
    async def set_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("⛔ Server managers only.", ephemeral=True)
            return
        perms = channel.permissions_for(interaction.guild.me)
        if not (perms.view_channel and perms.send_messages):
            await interaction.response.send_message(f"⚠️ I can't post in {channel.mention}.", ephemeral=True)
            return
        await self.service.set_channel(interaction.guild_id, channel.id)
        await interaction.response.send_message(
            f"📣 Facility announcements will go to {channel.mention}: new arrivals in the media archives and "
            "birthday shout-outs (for people who opt in with `/birthday set`).")

    @group.command(name="off", description="Stop facility announcements in this server")
    async def turn_off(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("⛔ Server managers only.", ephemeral=True)
            return
        await self.service.set_channel(interaction.guild_id, None)
        await interaction.response.send_message("📣 Facility announcements silenced.")

    # --- Birthdays (each user opts themselves in, per server) ---

    birthday = app_commands.Group(name="birthday", description="Birthday shout-outs (opt-in)", guild_only=True)

    @birthday.command(name="set", description="Get a shout-out on your birthday in this server (only month and day are stored)")
    async def birthday_set(self, interaction: discord.Interaction, month: app_commands.Range[int, 1, 12],
                           day: app_commands.Range[int, 1, 31]):
        try:
            await self.service.set_birthday(interaction.guild_id, interaction.user.id, month, day)
        except ValueError:
            await interaction.response.send_message("📅 That date doesn't exist, even in Aperture's calendar.", ephemeral=True)
            return
        note = "" if interaction.guild_id in await self.service.channels() else \
            " (This server hasn't turned on announcements yet, so a manager needs to run `/announcements channel`.)"
        await interaction.response.send_message(f"🎂 Noted: {month}/{day}. Cake will be promised.{note}", ephemeral=True)

    @birthday.command(name="remove", description="Stop birthday shout-outs for you in this server")
    async def birthday_remove(self, interaction: discord.Interaction):
        await self.service.remove_birthday(interaction.guild_id, interaction.user.id)
        await interaction.response.send_message("🎂 Birthday removed from the facility records.", ephemeral=True)

    # --- Periodic work ---

    @tasks.loop(minutes=2)
    async def tick(self):
        for step in (self.announce_media, self.announce_birthdays, self.check_printer):
            try:
                await step()
            except Exception as e:
                logger.exception(f"Announcement step {step.__name__} failed: {e}")

    @tick.before_loop
    async def before_tick(self):
        await self.bot.wait_until_ready()

    async def _post(self, guild_id: int, text: str, mention=None):
        channel_id = (await self.service.channels()).get(guild_id)
        channel = self.bot.get_channel(channel_id) if channel_id else None
        if channel is None:
            return
        allowed = discord.AllowedMentions(users=[mention] if mention else False, everyone=False, roles=False)
        try:
            await channel.send(text[:2000], allowed_mentions=allowed)
        except discord.HTTPException as e:
            logger.warning(f"Announcement failed in guild {guild_id}: {e}")

    async def announce_media(self):
        titles = await self.service.new_media()
        if not titles:
            return
        text = "🎬 **New in the facility archives:** " + ", ".join(f"**{t}**" for t in titles[:10])
        for guild_id in await self.service.channels():
            await self._post(guild_id, text)

    async def announce_birthdays(self):
        for guild_id, user_id in await self.service.due_birthdays():
            member = await find_member(self.bot.get_guild(guild_id), user_id)
            if member is None:
                continue
            line = await self.bot.ai_handler.complete(
                f"{self.bot.ai_handler._get_persona_system_prompt()}\n\nWish a test subject a happy birthday in "
                "character, under 200 characters, talking to them directly as 'you'. Promise cake. "
                "Don't invent a name; their mention is added in front of your line.")
            line = line or "Happy birthday from Aperture Science! There will be cake. Probably."
            await self._post(guild_id, f"🎂 {member.mention} {line}", mention=member)

    async def check_printer(self):
        status = await self.service.printer_finished()
        if status is None or not BotConfig.OWNER_ID:
            return
        printer = self.bot.homelab_service.printer
        job = await printer.last_job() or {}
        snap = await printer.snapshot()
        files = [discord.File(io.BytesIO(snap), filename="print.jpg")] if snap else []
        name = job.get("filename") or status.get("filename") or "your print"
        duration = job.get("duration") or status["duration"]
        filament = f", {job['filament_m']} m of filament" if job.get("filament_m") else ""
        if status["state"] == "complete":
            text = (f"🖨️ **Print finished:** {name} ({duration}{filament}). Matter has been constructed from hot "
                    "plastic soup.")
        else:
            reason = f" ({status['message']})" if status.get("message") else ""
            text = f"⚠️ **Print {status['state']}:** {name} after {duration}{reason}. Go check on it."
        owner = self.bot.get_user(BotConfig.OWNER_ID) or await self.bot.fetch_user(BotConfig.OWNER_ID)
        await owner.send(text, files=files)

async def setup(bot):
    await bot.add_cog(Announcements(bot))
