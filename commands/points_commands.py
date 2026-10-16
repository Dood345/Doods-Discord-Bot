"""Science Points: /points and /leaderboard."""

import discord
from discord import app_commands
from discord.ext import commands

from services.points_service import DISABLED_MSG
from utils.layouts import leaderboard_card, points_card
from utils.members import member_name




class PointsCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.points = bot.points_service

    group = app_commands.Group(name="sciencepoints", description="Science Points for this server (server managers)",
                               default_permissions=discord.Permissions(manage_guild=True), guild_only=True)

    @group.command(name="on", description="Start awarding Science Points in this server")
    async def turn_on(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("⛔ Server managers only.", ephemeral=True)
            return
        await self.points.set_enabled(interaction.guild_id, True)
        await interaction.response.send_message(
            "🧪 Science Points online! Everyone earns a point for showing up each day, plus Test Chamber "
            "winnings. Check `/points` and `/leaderboard`.")

    @group.command(name="off", description="Stop awarding Science Points in this server")
    async def turn_off(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("⛔ Server managers only.", ephemeral=True)
            return
        await self.points.set_enabled(interaction.guild_id, False)
        await interaction.response.send_message("🧪 Science Points paused. Existing points are kept on file.")

    async def _require_enabled(self, interaction: discord.Interaction) -> bool:
        if await self.points.is_enabled(interaction.guild_id):
            return True
        await interaction.response.send_message(f"🧪 {DISABLED_MSG}", ephemeral=True)
        return False

    @app_commands.command(name="points", description="Check Science Points and achievements")
    @app_commands.describe(member="Whose file to pull (default: yours)")
    @app_commands.guild_only()
    async def points_command(self, interaction: discord.Interaction, member: discord.Member = None):
        if not await self._require_enabled(interaction):
            return
        member = member or interaction.user
        points, rank, achievements = await self.points.profile(interaction.guild_id, member.id)
        if points <= 0:
            text = self.bot.dialogue.get("cave_johnson", "points_empty", fallback="{name} has no Science Points yet.",
                                         name=member.display_name)
            await interaction.response.send_message(text, allowed_mentions=discord.AllowedMentions.none())
            return
        locked = [a for a in self.points.achievements if a not in achievements]
        card = points_card(member.display_name, getattr(getattr(member, "display_avatar", None), "url", None), points, rank, achievements,
                           next_up=locked[0] if locked else None)
        await interaction.response.send_message(view=card, allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(name="leaderboard", description="Top test subjects in this facility")
    @app_commands.guild_only()
    async def leaderboard_command(self, interaction: discord.Interaction):
        if not await self._require_enabled(interaction):
            return
        await interaction.response.defer()  # name lookups can hit the API, past Discord's 3 s ack window
        board = await self.points.leaderboard(interaction.guild_id)
        if not board:
            await interaction.followup.send(self.bot.dialogue.get(
                "cave_johnson", "leaderboard_empty", fallback="Nobody has earned a single Science Point. Disgraceful."))
            return
        rows = [(await member_name(interaction.guild, uid), pts) for uid, pts in board]
        await interaction.followup.send(view=leaderboard_card(rows), allowed_mentions=discord.AllowedMentions.none())


async def setup(bot):
    await bot.add_cog(PointsCommands(bot))
