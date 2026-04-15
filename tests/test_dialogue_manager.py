import pytest
import os
import json
from unittest.mock import patch, mock_open
from utils.dialogue_manager import DialogueManager

@pytest.fixture
def mock_dialogue_data():
    return {
        "cave_johnson": {
            "roasts": ["You are fired.", "Box up your desk."],
            "compliments": ["Good work, {user}."],
            "greeting": "Welcome to Aperture Science."
        },
        "glados": {
            "roasts": ["You are a horrible person."],
            "cake": "The cake is a lie."
        }
    }

@pytest.fixture
def dialogue_manager(mock_dialogue_data, tmp_path):
    config_file = tmp_path / "dialogue.json"
    config_file.write_text(json.dumps(mock_dialogue_data))
    
    with patch.dict(os.environ, {"DIALOGUE_CONFIG_PATH": str(config_file)}):
        manager = DialogueManager(config_path=str(config_file))
        return manager

# --- load_dialogue() tests ---

def test_load_dialogue_success(dialogue_manager, mock_dialogue_data):
    """Test that the dialogue manager loads JSON successfully."""
    assert dialogue_manager.dialogue == mock_dialogue_data

def test_load_dialogue_file_not_found():
    """Test that the dialogue manager handles missing files gracefully."""
    manager = DialogueManager(config_path="nonexistent_file.json")
    assert manager.dialogue == {}

@patch("builtins.open", new_callable=mock_open, read_data="invalid json data")
def test_load_dialogue_invalid_json(mock_file):
    """Test that the dialogue manager handles invalid JSON gracefully."""
    manager = DialogueManager(config_path="dummy_path.json")
    assert manager.dialogue == {}

# --- get() tests ---

def test_get_success_string(dialogue_manager):
    """Test retrieving a simple string response."""
    response = dialogue_manager.get("cave_johnson", "greeting")
    assert response == "Welcome to Aperture Science."

def test_get_success_list(dialogue_manager):
    """Test retrieving a response from a list (should return one of the items)."""
    response = dialogue_manager.get("cave_johnson", "roasts")
    assert response in ["You are fired.", "Box up your desk."]

def test_get_with_formatting(dialogue_manager):
    """Test retrieving a string that requires formatting variables."""
    response = dialogue_manager.get("cave_johnson", "compliments", user="Chell")
    assert response == "Good work, Chell."

def test_get_missing_character(dialogue_manager):
    """Test retrieving a response for a character that doesn't exist."""
    response = dialogue_manager.get("wheatley", "greeting", fallback="Error")
    assert response == "Error"

def test_get_missing_response_type(dialogue_manager):
    """Test retrieving a response type that doesn't exist for a valid character."""
    response = dialogue_manager.get("cave_johnson", "apology", fallback="Never.")
    assert response == "Never."

def test_get_default_fallback_used(dialogue_manager):
    """Test that the default fallback is used if no fallback is provided."""
    response = dialogue_manager.get("wheatley", "greeting")
    assert response == "..."

def test_get_with_missing_format_kwargs(dialogue_manager):
    """Test formatting when required kwargs are missing. Should return raw string."""
    response = dialogue_manager.get("cave_johnson", "compliments") # Missing 'user' kwarg
    assert response == "Good work, {user}."

# --- get_list() tests ---

def test_get_list_success(dialogue_manager, mock_dialogue_data):
    """Test retrieving a raw list of responses."""
    raw_list = dialogue_manager.get_list("cave_johnson", "roasts")
    assert raw_list == ["You are fired.", "Box up your desk."]

def test_get_list_string_returns_string(dialogue_manager):
    """Test get_list on a string value (should probably return the string, or an empty list if it enforces list return type. Based on implementation, it returns whatever value is there)."""
    # Currently implementation returns the value directly, so a string is returned
    val = dialogue_manager.get_list("cave_johnson", "greeting")
    assert val == "Welcome to Aperture Science."

def test_get_list_missing_character(dialogue_manager):
    """Test get_list for a missing character returns an empty list."""
    val = dialogue_manager.get_list("wheatley", "roasts")
    assert val == []

def test_get_list_missing_response_type(dialogue_manager):
    """Test get_list for a missing response type returns an empty list."""
    val = dialogue_manager.get_list("cave_johnson", "apology")
    assert val == []
