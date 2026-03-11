import pytest

@pytest.mark.asyncio
async def test_database_initialization(temp_db):
    """Test that the database initializes and tables are created correctly."""
    # If setup_tables() in conftest.py failed, this would error out.
    # Let's verify we can get a connection.
    async with temp_db.get_connection() as conn:
        # Check if the 'games' table exists
        async with conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='games'") as cursor:
            result = await cursor.fetchone()
            assert result is not None, "Games table was not created."

@pytest.mark.asyncio
async def test_add_and_retrieve_game(temp_db):
    """Test adding a game and retrieving it via the library wrapper."""
    # 1. Add Game
    game_id = await temp_db.add_game(
        title="Portal",
        added_by=123,
        min_players=1,
        max_players=1,
        category="Puzzle"
    )
    assert game_id > 0, "Failed to return a valid game ID."

    # 2. Add Duplicate Game (Should return -1 due to UNIQUE constraint handled in try/except)
    duplicate_id = await temp_db.add_game(title="Portal", added_by=456)
    assert duplicate_id == -1, "Duplicate game insertion did not return -1 as expected."

    # 3. Retrieve Library
    library = await temp_db.get_game_library()
    assert len(library) == 1, "Library should contain exactly 1 game."
    
    game = library[0]
    assert game["title"] == "Portal"
    assert game["added_by"] == 123
    assert game["min_players"] == 1

@pytest.mark.asyncio
async def test_game_tags(temp_db):
    """Test the normalized tagging system."""
    game_id = await temp_db.add_game(
        title="Half-Life 2",
        added_by=123,
        tags=["FPS", "Sci-Fi", "Classic"]
    )
    
    # Verify tags exist globally
    all_tags = await temp_db.get_tags()
    assert "FPS" in all_tags
    assert "Sci-Fi" in all_tags
    assert len(all_tags) == 3

    # Verify game library returns the concatenated tags
    library = await temp_db.get_game_library()
    tags_str = library[0]["tags"]
    assert "FPS" in tags_str
    assert "Sci-Fi" in tags_str

@pytest.mark.asyncio
async def test_game_ratings(temp_db):
    """Test submitting and averaging game ratings."""
    game_id = await temp_db.add_game(title="Left 4 Dead 2", added_by=123)
    guild_id = 999
    
    # 1. Add two ratings from different users in the same guild
    await temp_db.rate_game(game_id, user_id=1, guild_id=guild_id, rating=10)
    await temp_db.rate_game(game_id, user_id=2, guild_id=guild_id, rating=8)
    
    # 2. Retrieve library with guild context to get the average rating
    library = await temp_db.get_game_library(guild_id=guild_id)
    game = library[0]
    
    # Average of 10 and 8 is 9.0
    assert game["avg_rating"] == 9.0

@pytest.mark.asyncio
async def test_update_game(temp_db):
    """Test updating arbitrary generic fields on a game entry."""
    await temp_db.add_game(title="Factorio", added_by=123, status="wishlist")
    
    # Update status and a metric
    success = await temp_db.update_game("Factorio", status="playing", min_players=1)
    assert success is True
    
    # Verify the update took hold
    library = await temp_db.get_game_library()
    assert library[0]["status"] == "playing"
    assert library[0]["min_players"] == 1

@pytest.mark.asyncio
async def test_search_game_titles(temp_db):
    """Test autocomplete prefix searching."""
    await temp_db.add_game(title="Super Smash Bros", added_by=123)
    await temp_db.add_game(title="Super Mario 64", added_by=123)
    await temp_db.add_game(title="Halo", added_by=123)
    
    results = await temp_db.search_game_titles("Super")
    assert len(results) == 2
    assert "Super Smash Bros" in results
    assert "Super Mario 64" in results

@pytest.mark.asyncio
async def test_ai_history(temp_db):
    """Test the AI Context window history storage and retrieval."""
    user_id = 42
    guild_id = 999
    
    # Add messages
    await temp_db.add_ai_message(user_id, guild_id, "user", "Hello cave")
    await temp_db.add_ai_message(user_id, guild_id, "model", "Hello test subject")
    await temp_db.add_ai_message(user_id, guild_id, "user", "How are you?")
    
    # Retrieve with limit 2 (Should get the LAST two messages, returned chronologically)
    history = await temp_db.get_ai_history(user_id, guild_id, limit=2)
    assert len(history) == 2
    
    # Check chronological ordering (oldest FIRST in the returned list)
    assert history[0][0] == "model"
    assert history[1][1] == "How are you?"
    
    # Test clearing history
    await temp_db.clear_ai_history(user_id)
    history_after = await temp_db.get_ai_history(user_id, guild_id)
    assert len(history_after) == 0

@pytest.mark.asyncio
async def test_recommend_games(temp_db):
    """Test the RAG formatted string generator."""
    await temp_db.add_game(title="Coop Game A", added_by=123, min_players=2, max_players=4, tags=["Co-op"], notes="Fun")
    await temp_db.add_game(title="Solo Game B", added_by=123, min_players=1, max_players=1, notes="Lonely")
    
    # Search for Co-op
    result = await temp_db.recommend_games(min_players=3, tag="Co-op")
    assert "Coop Game A" in result
    assert "Solo Game B" not in result
    
    # Search for non-existent
    result_empty = await temp_db.recommend_games(min_players=10)
    assert "No simulations found" in result_empty
