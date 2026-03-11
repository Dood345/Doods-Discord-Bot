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
        # DB init is handled in main.py via bot.db.setup_tables()

    @app_commands.command(name="gift-add", description="Add an item to your wishlist")
    async def gift_add(self, interaction: discord.Interaction, item: str, link: str = "No Link"):
        try:
            async with self.bot.db.get_connection() as conn:
                await conn.execute("INSERT INTO gifts (user_id, item_name, link, claimed_by) VALUES (?, ?, ?, NULL)", 
                        (interaction.user.id, item, link))
                await conn.commit()
            await interaction.response.send_message(f"🎁 Added **{item}** to your list!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error adding gift: {e}")
            await interaction.response.send_message("❌ Failed to add gift. Please try again.", ephemeral=True)

    @app_commands.command(name="gift-view", description="View a friend's wishlist")
    async def gift_view(self, interaction: discord.Interaction, user: discord.User):
        try:
            async with self.bot.db.get_connection() as conn:
                async with conn.execute("SELECT id, item_name, link, claimed_by FROM gifts WHERE user_id = ?", (user.id,)) as cursor:
                    items = await cursor.fetchall()

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
        except Exception as e:
            logger.error(f"Error viewing gifts: {e}")
            await interaction.response.send_message("❌ Failed to load wishlist.", ephemeral=True)

    @app_commands.command(name="gift-claim", description="Mark an item as purchased (The owner won't know it was you)")
    async def gift_claim(self, interaction: discord.Interaction, item_id: int):
        try:
            async with self.bot.db.get_connection() as conn:
                # Check if already claimed
                async with conn.execute("SELECT claimed_by, user_id FROM gifts WHERE id = ?", (item_id,)) as cursor:
                    result = await cursor.fetchone()
                
                if not result:
                    await interaction.response.send_message("That item ID doesn't exist.", ephemeral=True)
                elif result[1] == interaction.user.id:
                     await interaction.response.send_message("You can't claim your own gift! 🤦‍♂️", ephemeral=True)
                elif result[0] is not None:
                    await interaction.response.send_message("Someone else already claimed this!", ephemeral=True)
                else:
                    await conn.execute("UPDATE gifts SET claimed_by = ? WHERE id = ?", (interaction.user.id, item_id))
                    await conn.commit()
                    await interaction.response.send_message("🎉 You claimed this item! The owner will see it as claimed, but not by whom.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error claiming gift: {e}")
            await interaction.response.send_message("❌ Failed to claim gift.", ephemeral=True)

    @app_commands.command(name="gift-remove", description="Remove an item from your wishlist")
    async def gift_remove(self, interaction: discord.Interaction, item_id: int):
        try:
            async with self.bot.db.get_connection() as conn:
                # Check if item exists and belongs to user
                async with conn.execute("SELECT user_id FROM gifts WHERE id = ?", (item_id,)) as cursor:
                    result = await cursor.fetchone()
                
                if not result:
                    await interaction.response.send_message("Item not found.", ephemeral=True)
                elif result[0] != interaction.user.id:
                    await interaction.response.send_message("You can only remove items from your own list!", ephemeral=True)
                else:
                    await conn.execute("DELETE FROM gifts WHERE id = ?", (item_id,))
                    await conn.commit()
                    await interaction.response.send_message(f"🗑️ Removed item {item_id} from your list.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error removing gift: {e}")
            await interaction.response.send_message("❌ Failed to remove gift.", ephemeral=True)

    @app_commands.command(name="gift-unclaim", description="Unclaim an item you previously claimed")
    async def gift_unclaim(self, interaction: discord.Interaction, item_id: int):
        try:
            async with self.bot.db.get_connection() as conn:
                # Check if item exists and was claimed by user
                async with conn.execute("SELECT claimed_by FROM gifts WHERE id = ?", (item_id,)) as cursor:
                    result = await cursor.fetchone()
                
                if not result:
                    await interaction.response.send_message("Item not found.", ephemeral=True)
                elif result[0] != interaction.user.id:
                    await interaction.response.send_message("You haven't claimed this item!", ephemeral=True)
                else:
                    await conn.execute("UPDATE gifts SET claimed_by = NULL WHERE id = ?", (item_id,))
                    await conn.commit()
                    await interaction.response.send_message("↩️ Unclaimed item. It is now available for others.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error unclaiming gift: {e}")
            await interaction.response.send_message("❌ Failed to unclaim gift.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(GiftCommands(bot))
