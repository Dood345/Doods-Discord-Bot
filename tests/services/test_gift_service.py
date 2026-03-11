import pytest
from services.gift_service import GiftService

@pytest.mark.asyncio
async def test_gift_service_workflow(temp_db):
    """Test GiftService operations."""
    service = GiftService(temp_db)
    user_id = 1
    guild_id = 99
    
    # 1. Add gift
    success = await service.add_gift(user_id, guild_id, "Test Gift", "http://link")
    assert success is True
    
    # 2. Get wishlist
    wishlist = await service.get_wishlist(user_id, guild_id)
    assert len(wishlist) == 1
    item_id = wishlist[0][0]
    
    # 3. Claim gift (cannot claim own)
    success, msg = await service.claim_gift(user_id, guild_id, item_id)
    assert success is False
    assert "own gift" in msg.lower() or "own" in msg.lower()
    
    # 4. Claim gift (success)
    other_user = 2
    success, msg = await service.claim_gift(other_user, guild_id, item_id)
    assert success is True
    
    # 5. Claim already claimed
    third_user = 3
    success, msg = await service.claim_gift(third_user, guild_id, item_id)
    assert success is False
    assert "already claimed" in msg.lower()
    
    # 6. Unclaim gift
    success, msg = await service.unclaim_gift(other_user, guild_id, item_id)
    assert success is True
    
    # 7. Remove gift
    success, msg = await service.remove_gift(user_id, guild_id, item_id)
    assert success is True
    
    # 8. Verify removal
    wishlist_after = await service.get_wishlist(user_id, guild_id)
    assert len(wishlist_after) == 0
