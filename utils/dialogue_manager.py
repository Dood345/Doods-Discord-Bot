import json
import random
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class DialogueManager:
    """Manages bot dialogue and character responses from a centralized JSON configuration."""
    
    def __init__(self, config_path: str = "data/dialogue.json"):
        self.config_path = Path(config_path)
        self.dialogue = {}
        self.load_dialogue()
        
    def load_dialogue(self):
        """Loads or reloads the dialogue configuration from disk."""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.dialogue = json.load(f)
                logger.info(f"Successfully loaded dialogue from {self.config_path}")
            else:
                logger.warning(f"Dialogue configuration file not found at {self.config_path}")
                self.dialogue = {}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse dialogue JSON: {e}")
            self.dialogue = {}
        except Exception as e:
            logger.error(f"Unexpected error loading dialogue: {e}")
            self.dialogue = {}
            
    def get(self, character: str, response_type: str, fallback: str = "...", **kwargs) -> str:
        """
        Retrieves a formatted dialogue string for a given character and response type.
        If multiple strings exist in an array, one is chosen at random.
        
        Args:
            character: The key of the character (e.g., 'cave_johnson', 'hank')
            response_type: The sub-key defining the response (e.g., 'roasts', 'game_added_success')
            fallback: An optional string to return if the path doesn't exist.
            **kwargs: Dynamic arguments to format into the string (e.g., user="Cave", score=10)
        """
        try:
            if not self.dialogue:
                return fallback
                
            char_data = self.dialogue.get(character)
            if not char_data:
                return fallback
                
            responses = char_data.get(response_type)
            if not responses:
                return fallback
                
            # Most dialogue blocks are lists
            if isinstance(responses, list):
                if not responses:
                    return fallback
                template = random.choice(responses)
            else:
                template = responses
                
            # Format the template with dynamic parameters
            return template.format(**kwargs)
            
        except KeyError as e:
            logger.warning(f"Dialogue format failed for {character}.{response_type}: Missing key {e}")
            return template  # Return unformatted if keys bind incorrectly
        except Exception as e:
            logger.error(f"Error fetching dialogue {character}.{response_type}: {e}")
            return fallback

    def get_list(self, character: str, response_type: str) -> list:
        """Retrieves a raw unformatted list of responses."""
        if not self.dialogue:
            return []
        
        char_data = self.dialogue.get(character, {})
        return char_data.get(response_type, [])
