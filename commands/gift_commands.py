import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import logging
import os

logger = logging.getLogger(__name__)

class GiftCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Inject the gift service from the bot
        self.gift_service = bot.gift_service

    @app_commands.command(name="gift-add", description="Add an item to your wishlist")
    async def gift_add(self, interaction: discord.Interaction, item: str, link: str = "No Link"):
        success = await self.gift_service.add_gift(
            interaction.user.id, interaction.guild_id, item, link
        )
        if success:
            await interaction.response.send_message(f"🎁 Added **{item}** to your list!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Failed to add gift. Please try again.", ephemeral=True)

    @app_commands.command(name="gift-view", description="View a friend's wishlist")
    async def gift_view(self, interaction: discord.Interaction, user: discord.User):
        items = await self.gift_service.get_wishlist(user.id, interaction.guild_id)

        if not items:
            await interaction.response.send_message(f"{user.display_name} hasn't added any gifts yet.", ephemeral=True)
            return

        embed = discord.Embed(title=f"🎁 {user.display_name}'s Wishlist", color=discord.Color.green())
        
        for item_id, name, link, claimed_by in items:
            status = "✅ AVAILABLE"
            if claimed_by:
                status = "❌ CLAIMED (Already bought)"
            
            # We assume users want to claim items, so we show the ID
            embed.add_field(name=f"ID: {item_id} | {status}", value=f"**{name}**\n[Link]({link})", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="gift-claim", description="Mark an item as purchased (The owner won't know it was you)")
    async def gift_claim(self, interaction: discord.Interaction, item_id: int):
        success, message = await self.gift_service.claim_gift(
            interaction.user.id, interaction.guild_id, item_id
        )
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="gift-remove", description="Remove an item from your wishlist")
    async def gift_remove(self, interaction: discord.Interaction, item_id: int):
        success, message = await self.gift_service.remove_gift(
            interaction.user.id, interaction.guild_id, item_id
        )
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="gift-unclaim", description="Unclaim an item you previously claimed")
    async def gift_unclaim(self, interaction: discord.Interaction, item_id: int):
        success, message = await self.gift_service.unclaim_gift(
            interaction.user.id, interaction.guild_id, item_id
        )
        await interaction.response.send_message(message, ephemeral=True)

async def setup(bot):
    await bot.add_cog(GiftCommands(bot))
