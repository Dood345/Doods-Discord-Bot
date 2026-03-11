import pytest
import aiosqlite
import os
import asyncio
from unittest.mock import MagicMock

from utils.database import DatabaseHandler
from config import BotConfig

# -----------------------------------------------------------------------------
# Pytest Asyncio Configuration
# -----------------------------------------------------------------------------
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

# -----------------------------------------------------------------------------
# Database Fixtures
# -----------------------------------------------------------------------------
@pytest.fixture
async def temp_db(tmp_path):
    """
    Spins up an isolated DatabaseHandler instance using a temporary SQLite DB
    file for pristine testing environments.
    """
    test_db_path = tmp_path / "test_doodlab.db"
    db = DatabaseHandler(db_path=str(test_db_path))
    await db.setup_tables()
    
    yield db
    
# (Deleted redundant real_temp_db)

# -----------------------------------------------------------------------------
# Config / Mock Fixtures
# -----------------------------------------------------------------------------
@pytest.fixture
def mock_config():
    """Provides a safely mocked BotConfig so tests don't hit real APIs or leak Keys."""
    config = MagicMock(spec=BotConfig)
    config.GEMINI_API_KEY = "TEST_FAKE_KEY_12345"
    config.BOT_TOKEN = "TEST_BOT_TOKEN_XXXX"
    config.GUILD_ID = 1234567890
    config.SYSTEM_INSTRUCTION = "You are Cave Johnson. Do science."
    config.CHARACTER_PROMPTS = {
        "hank": "You are Hank.",
        "dale": "You are Dale.",
        "cartman": "You are Cartman.",
        "redgreen": "You are Red Green.",
        "trek": "You are Star Trek.",
        "alexjones": "You are Alex Jones.",
        "snake": "You are Solid Snake.",
        "kratos": "You are Kratos.",
        "dante": "You are Dante."
    }
    return config
