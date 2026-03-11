"""Message reaction handling for the Discord bot"""

import random
import re
import logging
from config import BotConfig

logger = logging.getLogger(__name__)

class ReactionHandler:
    def __init__(self, dialogue_manager):
        self.config = BotConfig()
        self.dialogue = dialogue_manager
    
    async def handle_message(self, message):
        """Handle emoji reactions and random responses to messages"""
        content_lower = message.content.lower()
        
        # Check for keywords and react
        await self._handle_keyword_reactions(message, content_lower)
        
        # Random chance responses (1% to not be annoying)
        await self._handle_random_responses(message, content_lower)
    
    async def _handle_keyword_reactions(self, message, content_lower: str):
        """Add emoji reactions based on keywords"""
        for keyword, emojis in self.config.KEYWORD_REACTIONS.items():
            # Use regex to match whole words only
            if re.search(r'\b' + re.escape(keyword) + r'\b', content_lower):
                # Random chance to react based on config
                if random.randint(1, 100) <= self.config.REACTION_CHANCE:
                    emoji = random.choice(emojis)
                    try:
                        await message.add_reaction(emoji)
                        logger.debug(f"Reacted with {emoji} to keyword '{keyword}'")
                    except Exception as e:
                        logger.debug(f"Failed to react with {emoji}: {e}")
                break  # Only react to first matching keyword
    
    async def _handle_random_responses(self, message, content_lower: str):
        """Send random text responses to certain keywords"""
        if random.randint(1, 100) <= 1:  # 1% chance
            for keyword in ['ai', 'bot', 'skynet', 'terminator', 'help']:
                if re.search(r'\b' + re.escape(keyword) + r'\b', content_lower):
                    response = self.dialogue.get('system', f'keyword_{keyword}')
                    try:
                        await message.channel.send(response)
                        logger.debug(f"Sent random response for keyword '{keyword}'")
                    except Exception as e:
                        logger.debug(f"Failed to send random response: {e}")
                    break