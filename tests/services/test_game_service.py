import pytest
from services.game_service import GameService

@pytest.mark.asyncio
async def test_game_service_workflow(temp_db):
    """Test GameService high-level operations."""
    service = GameService(temp_db)
    user_id = 1
    guild_id = 88
    
    # 1. Add Game
    success, msg = await service.add_game("Portal", user_id, guild_id, 1, 1, tags="Puzzle, Classic")
    assert success is True
    assert "secured a new simulation" in msg
    
    # 2. Duplicate Game
    success, msg = await service.add_game("Portal", user_id, guild_id, 1, 1)
    assert success is False
    assert "already exists" in msg
    
    # 3. Search and Tags
    titles = await service.search_game_titles("Port", guild_id)
    assert "Portal" in titles
    
    # 4. Filtered Tags
    tags = await service.get_filtered_tags("Puz", guild_id)
    assert "Puzzle" in tags
    
    # 5. Update Game
    success, msg = await service.update_game("Portal", guild_id, {"status": "playing"})
    assert success is True
    
    # 6. Rate Game
    success, msg = await service.rate_game("Portal", 10, user_id, guild_id)
    assert success is True
    
    # Rate out of bounds
    success, msg = await service.rate_game("Portal", 11, user_id, guild_id)
    assert success is False
    
    # 7. Get Library
    library = await service.get_library(guild_id)
    assert len(library) == 1
    assert library[0]["status"] == "playing"
    assert library[0]["avg_rating"] == 10.0
