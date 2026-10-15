import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import List

logger = logging.getLogger(__name__)

class GiftCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Inject the gift service from the bot
        self.gift_service = bot.gift_service

    def _owner_name(self, interaction: discord.Interaction, owner_id: int) -> str:
        member = interaction.guild.get_member(owner_id) if interaction.guild else None
        return member.display_name if member else "someone"

    @staticmethod
    def _choices(items, current: str, label) -> List[app_commands.Choice[int]]:
        """Autocomplete shows item names; the item ID stays hidden as the choice value."""
        current = current.lower()
        return [app_commands.Choice(name=label(item)[:100], value=item[0])
                for item in items if current in label(item).lower()][:25]

    async def own_items_autocomplete(self, interaction: discord.Interaction, current: str):
        items = await self.gift_service.get_wishlist(interaction.user.id, interaction.guild_id)
        return self._choices(items, current, lambda i: i[1])

    async def claimable_autocomplete(self, interaction: discord.Interaction, current: str):
        items = await self.gift_service.get_claimable(interaction.user.id, interaction.guild_id)
        return self._choices(items, current, lambda i: f"{i[1]} (for {self._owner_name(interaction, i[2])})")

    async def my_claims_autocomplete(self, interaction: discord.Interaction, current: str):
        items = await self.gift_service.get_my_claims(interaction.user.id, interaction.guild_id)
        return self._choices(items, current, lambda i: f"{i[1]} (for {self._owner_name(interaction, i[2])})")

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

        own_list = user.id == interaction.user.id
        embed = discord.Embed(title=f"🎁 {user.display_name}'s Wishlist", color=discord.Color.green())

        for item_id, name, link, claimed_by in items:
            if own_list:
                # Never show the owner what's been claimed: that spoils the surprise
                status = "🎁 On your list"
            else:
                status = "❌ CLAIMED (Already bought)" if claimed_by else "✅ AVAILABLE"
            embed.add_field(name=status, value=f"**{name}**\n[Link]({link})", inline=False)

        if own_list:
            embed.set_footer(text="Claims are hidden from you so gifts stay a surprise.")
        else:
            embed.set_footer(text="Use /gift-claim and pick the item by name.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="gift-claim", description="Mark an item as purchased (The owner won't know it was you)")
    @app_commands.rename(item_id="item")
    @app_commands.describe(item_id="Start typing the gift's name")
    @app_commands.autocomplete(item_id=claimable_autocomplete)
    async def gift_claim(self, interaction: discord.Interaction, item_id: int):
        success, message = await self.gift_service.claim_gift(
            interaction.user.id, interaction.guild_id, item_id
        )
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="gift-remove", description="Remove an item from your wishlist")
    @app_commands.rename(item_id="item")
    @app_commands.describe(item_id="Start typing the gift's name")
    @app_commands.autocomplete(item_id=own_items_autocomplete)
    async def gift_remove(self, interaction: discord.Interaction, item_id: int):
        success, message = await self.gift_service.remove_gift(
            interaction.user.id, interaction.guild_id, item_id
        )
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="gift-unclaim", description="Unclaim an item you previously claimed")
    @app_commands.rename(item_id="item")
    @app_commands.describe(item_id="Start typing the gift's name")
    @app_commands.autocomplete(item_id=my_claims_autocomplete)
    async def gift_unclaim(self, interaction: discord.Interaction, item_id: int):
        success, message = await self.gift_service.unclaim_gift(
            interaction.user.id, interaction.guild_id, item_id
        )
        await interaction.response.send_message(message, ephemeral=True)

async def setup(bot):
    await bot.add_cog(GiftCommands(bot))
