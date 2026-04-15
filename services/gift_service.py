import logging
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

class GiftService:
    """Service layer for handling Discord gift exchanges and wishlists."""
    
    def __init__(self, db):
        self.db = db

    async def add_gift(self, user_id: int, guild_id: int, item_name: str, link: str = "No Link") -> bool:
        """Add an item to a user's wishlist."""
        try:
            async with self.db.get_connection() as conn:
                await conn.execute(
                    "INSERT INTO gifts (user_id, guild_id, item_name, link, claimed_by) VALUES (?, ?, ?, ?, NULL)", 
                    (user_id, guild_id, item_name, link)
                )
                await conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error in GiftService.add_gift: {e}")
            return False

    async def get_wishlist(self, user_id: int, guild_id: int) -> List[Tuple]:
        """Retrieve a user's wishlist."""
        try:
            async with self.db.get_connection() as conn:
                async with conn.execute(
                    "SELECT id, item_name, link, claimed_by FROM gifts WHERE user_id = ? AND guild_id = ?", 
                    (user_id, guild_id)
                ) as cursor:
                    items = await cursor.fetchall()
            return items
        except Exception as e:
            logger.error(f"Error in GiftService.get_wishlist: {e}")
            return []

    async def claim_gift(self, user_id: int, guild_id: int, item_id: int) -> Tuple[bool, str]:
        """Claim a gift for another user."""
        try:
            async with self.db.get_connection() as conn:
                async with conn.execute(
                    "SELECT claimed_by, user_id FROM gifts WHERE id = ? AND guild_id = ?", 
                    (item_id, guild_id)
                ) as cursor:
                    result = await cursor.fetchone()
                
                if not result:
                    return False, "That item ID doesn't exist."
                elif result[1] == user_id:
                    return False, "You can't claim your own gift! 🤦‍♂️"
                elif result[0] is not None:
                    return False, "Someone else already claimed this!"
                else:
                    await conn.execute(
                        "UPDATE gifts SET claimed_by = ? WHERE id = ? AND guild_id = ?", 
                        (user_id, item_id, guild_id)
                    )
                    await conn.commit()
                    return True, "🎉 You claimed this item! The owner will see it as claimed, but not by whom."
        except Exception as e:
            logger.error(f"Error in GiftService.claim_gift: {e}")
            return False, "❌ Failed to claim gift due to a database error."
        return False, "Unknown Error"

    async def remove_gift(self, user_id: int, guild_id: int, item_id: int) -> Tuple[bool, str]:
        """Remove a gift from your own wishlist."""
        try:
            async with self.db.get_connection() as conn:
                async with conn.execute(
                    "SELECT user_id FROM gifts WHERE id = ? AND guild_id = ?", 
                    (item_id, guild_id)
                ) as cursor:
                    result = await cursor.fetchone()
                
                if not result:
                    return False, "Item not found."
                elif result[0] != user_id:
                    return False, "You can only remove items from your own list!"
                else:
                    await conn.execute(
                        "DELETE FROM gifts WHERE id = ? AND guild_id = ?", 
                        (item_id, guild_id)
                    )
                    await conn.commit()
                    return True, f"🗑️ Removed item {item_id} from your list."
        except Exception as e:
            logger.error(f"Error in GiftService.remove_gift: {e}")
            return False, "❌ Failed to remove gift due to a database error."
        return False, "Unknown Error"

    async def unclaim_gift(self, user_id: int, guild_id: int, item_id: int) -> Tuple[bool, str]:
        """Unclaim a gift you previously claimed."""
        try:
            async with self.db.get_connection() as conn:
                async with conn.execute(
                    "SELECT claimed_by FROM gifts WHERE id = ? AND guild_id = ?", 
                    (item_id, guild_id)
                ) as cursor:
                    result = await cursor.fetchone()
                
                if not result:
                    return False, "Item not found."
                elif result[0] != user_id:
                    return False, "You haven't claimed this item!"
                else:
                    await conn.execute(
                        "UPDATE gifts SET claimed_by = NULL WHERE id = ? AND guild_id = ?", 
                        (item_id, guild_id)
                    )
                    await conn.commit()
                    return True, "↩️ Unclaimed item. It is now available for others."
        except Exception as e:
            logger.error(f"Error in GiftService.unclaim_gift: {e}")
            return False, "❌ Failed to unclaim gift due to a database error."
        return False, "Unknown Error"
