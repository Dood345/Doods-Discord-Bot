"""/persona: hand a channel over to another character (with its own memory) until someone hands it back."""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from config import BotConfig

logger = logging.getLogger(__name__)


class Personas(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.service = bot.persona_service

    async def cog_load(self):
        try:
            count = await self.service.load()
            if count:
                logger.info(f"Channel personas loaded: {count}")
        except Exception as e:
            logger.warning(f"Couldn't load channel personas: {e}")

    group = app_commands.Group(name="persona", description="Who answers @mentions in this channel",
                               default_permissions=discord.Permissions(manage_channels=True), guild_only=True)

    async def _can_manage(self, interaction: discord.Interaction) -> bool:
        perms = interaction.channel.permissions_for(interaction.user) if interaction.channel else None
        if perms and perms.manage_channels:
            return True
        await interaction.response.send_message("⛔ Only people who can manage this channel can swap who runs it.",
                                                ephemeral=True)
        return False

    @group.command(name="set", description="Have a character answer @mentions here instead of Cave")
    @app_commands.describe(character="Who takes over this channel (they keep their own memories)")
    @app_commands.choices(character=[app_commands.Choice(name=f"{p.emoji} {p.name}"[:100], value=key)
                                     for key, p in list(BotConfig.PERSONAS.items())[:25]])
    async def set_persona(self, interaction: discord.Interaction, character: str):
        if not await self._can_manage(interaction):
            return
        channel_id = getattr(interaction.channel, "parent_id", None) if isinstance(interaction.channel, discord.Thread) \
            else interaction.channel_id
        await self.service.set(interaction.guild_id, channel_id or interaction.channel_id, character)
        name = self.service.label(character)
        await interaction.response.send_message(
            f"🎭 **{name}** has taken over this channel. Mention the bot here to talk to them. They keep their own "
            "memories (Cave's stay with Cave). `/persona reset` hands it back.",
            allowed_mentions=discord.AllowedMentions.none())

    @group.command(name="reset", description="Hand this channel back to Cave")
    async def reset_persona(self, interaction: discord.Interaction):
        if not await self._can_manage(interaction):
            return
        channel_id = getattr(interaction.channel, "parent_id", None) if isinstance(interaction.channel, discord.Thread) \
            else interaction.channel_id
        old = await self.service.reset(interaction.guild_id, channel_id or interaction.channel_id)
        if old:
            await interaction.response.send_message(
                f"🧪 **Cave Johnson** is back in charge here. {self.service.label(old)}'s memories are kept for "
                "next time.")
        else:
            await interaction.response.send_message("Cave is already running this channel.", ephemeral=True)

    @group.command(name="show", description="Who answers @mentions in this channel")
    async def show_persona(self, interaction: discord.Interaction):
        persona = self.service.for_channel(interaction.channel)
        await interaction.response.send_message(f"🎭 This channel is run by **{self.service.label(persona)}**.",
                                                ephemeral=True)


async def setup(bot):
    await bot.add_cog(Personas(bot))
