import pytest
from unittest.mock import AsyncMock, patch
from utils.ai_handler import AIHandler

@pytest.mark.asyncio
async def test_get_chat_response(temp_db, mock_config, mocker):
    """
    Test the flow of generating an AI response without hitting the real Google API.
    We mock the `gemini` client call inside the handler.
    """
    # Initialize the handler. It takes (db, bot) but we don't need a real bot here.
    # Pass None for the bot since most AI handler methods only use the db wrapper here.
    handler = AIHandler(temp_db, None)
    # Inject our mock config specifically for testing
    handler.config = mock_config 
    
    # Because there's no GEMINI_API_KEY in the test environment, client is None.
    # We must construct a mock client structure for it to hit.
    handler.client = mocker.MagicMock()

    # Mock the internal gemini API call
    # The actual call is: self.client.models.generate_content(...)
    mock_response = mocker.MagicMock()
    mock_response.text = "Mocked AI Response: Science!"
    
    # We patch the google genai client object created inside __init__
    mocker.patch.object(handler.client.models, 'generate_content', return_value=mock_response)

    # Add some dummy history to test the RAG building logic
    await temp_db.add_ai_message(user_id=1, guild_id=999, role="user", content="Hello AI")
    
    # 1. Execute the main path
    response = await handler.get_chat_response(
        user_id=1,
        message="Tell me a joke.",
        guild_id=999
    )
    
    assert response == "Mocked AI Response: Science!"
    
    # 2. Verify history was written properly
    history = await temp_db.get_ai_history(user_id=1, guild_id=999)
    assert len(history) == 3 # 1 Old user prompt, 1 New prompt, 1 New model response
    assert history[-2][0] == "user"
    assert history[-2][1] == "Tell me a joke."
    assert history[-1][0] == "model"
    assert history[-1][1] == "Mocked AI Response: Science!"

@pytest.mark.asyncio
async def test_clear_user_history(temp_db, mock_config):
    """Test the handler correctly forwards the clear history command."""
    handler = AIHandler(temp_db, None)
    
    await temp_db.add_ai_message(user_id=1, guild_id=999, role="user", content="I exist")
    await handler.clear_user_history(user_id=1)
    
    history = await temp_db.get_ai_history(user_id=1, guild_id=999)
    assert len(history) == 0

@pytest.mark.asyncio
async def test_roast_response(temp_db, mock_config, mocker):
    """Test generating a specific AI prompt (Roast)."""
    handler = AIHandler(temp_db, None)
    handler.config = mock_config
    handler.client = mocker.MagicMock()
    
    # Mock generation
    mock_response = mocker.MagicMock()
    mock_response.text = "You are terrible at science."
    mocker.patch.object(handler.client.models, 'generate_content', return_value=mock_response)
    
    response = await handler.get_roast_response(
        character="hank",
        target_name="Wheatley"
    )
    
    assert "terrible at science" in response
    
    # Verify the internal API call received the target correctly
    handler.client.models.generate_content.assert_called_once()
    args, kwargs = handler.client.models.generate_content.call_args
    assert "Wheatley" in kwargs['contents'] # Check our generated prompt contents
