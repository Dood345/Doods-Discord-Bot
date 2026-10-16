"""Science Points: /points and /leaderboard."""

import discord
from discord import app_commands
from discord.ext import commands

from utils.members import member_name

MEDALS = ["🥇", "🥈", "🥉"]




class PointsCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.points = bot.points_service

    @app_commands.command(name="points", description="Check Science Points and achievements")
    @app_commands.describe(member="Whose file to pull (default: yours)")
    @app_commands.guild_only()
    async def points_command(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        points, rank, achievements = await self.points.profile(interaction.guild_id, member.id)
        if points <= 0:
            text = self.bot.dialogue.get("cave_johnson", "points_empty", fallback="{name} has no Science Points yet.",
                                         name=member.display_name)
            await interaction.response.send_message(text, allowed_mentions=discord.AllowedMentions.none())
            return
        lines = [f"🧪 **{member.display_name}**: {points} Science Points (rank #{rank} in this facility)"]
        if achievements:
            lines.append("**Achievements:** " + ", ".join(a.label for a in achievements))
        locked = [a for a in self.points.achievements if a not in achievements]
        if locked:
            lines.append(f"-# Next up: {locked[0].emoji} {locked[0].name} ({locked[0].description})")
        await interaction.response.send_message("\n".join(lines), allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(name="leaderboard", description="Top test subjects in this facility")
    @app_commands.guild_only()
    async def leaderboard_command(self, interaction: discord.Interaction):
        await interaction.response.defer()  # name lookups can hit the API, past Discord's 3 s ack window
        board = await self.points.leaderboard(interaction.guild_id)
        if not board:
            await interaction.followup.send(self.bot.dialogue.get(
                "cave_johnson", "leaderboard_empty", fallback="Nobody has earned a single Science Point. Disgraceful."))
            return
        rows = [f"{MEDALS[i] if i < 3 else f'`#{i + 1}`'} {await member_name(interaction.guild, uid)}: **{pts}**"
                for i, (uid, pts) in enumerate(board)]
        await interaction.followup.send("🏆 **SCIENCE POINTS LEADERBOARD**\n" + "\n".join(rows),
                                        allowed_mentions=discord.AllowedMentions.none())


async def setup(bot):
    await bot.add_cog(PointsCommands(bot))
