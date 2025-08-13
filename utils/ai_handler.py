"""AI handling utilities for the Discord bot"""

import os
import google.generativeai as genai
import logging
from typing import Optional, Dict, List, Tuple
from config import BotConfig

logger = logging.getLogger(__name__)

class AIHandler:
    def __init__(self):
        self.config = BotConfig()
        self.model = self._setup_ai()
        self.conversation_histories: Dict[int, List[Tuple[str, str]]] = {}
        self.max_history_length = 10  # Keep last 10 exchanges per user
    
    def _setup_ai(self):
        """Initialize Gemini AI"""
        api_key = os.getenv('GEMINI_API_KEY')
        if api_key:
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-2.5-flash')
                logger.info("AI model initialized successfully")
                return model
            except Exception as e:
                logger.error(f"Failed to initialize AI model: {e}")
                return None
        else:
            logger.warning("GEMINI_API_KEY not found - AI features disabled")
            return None
    
    def is_available(self) -> bool:
        """Check if AI is available"""
        return self.model is not None
    
    async def get_character_response(self, character: str, user_input: str) -> Optional[str]:
        """Get AI response for a specific character"""
        if not self.is_available() or character not in self.config.CHARACTER_PROMPTS:
            return None
        
        try:
            prompt = f"{self.config.CHARACTER_PROMPTS[character]}\n\nUser said: '{user_input}'\n\nRespond in character:"
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"AI character response error for {character}: {e}")
            return None
    
    async def get_chat_response(self, user_id: int, message: str) -> Optional[str]:
        """Get AI response for general chat with conversation history"""
        if not self.is_available():
            return None
        
        try:
            # Get user's conversation history
            history = self.conversation_histories.get(user_id, [])
            
            # Build context from history
            context = ""
            if history:
                context = "Previous 5 messages in conversation history:\n"
                for user_msg, bot_msg in history[-5:]:  # Last 5 exchanges for context
                    context += f"User: {user_msg}\nBot: {bot_msg}\n"
                context += "\n"
            else:
                context = "Previous 5 messages in conversation history: NULL\n"
            
            # Create prompt
            prompt = f"""You are a sassy, somewhat unhinged but helpful AI assistant for a Discord server. 
            You're not worried about being politically correct and can be a bit edgy, but you're still helpful and engaging.
            
            {context}Current user message: "{message}"
            
            Respond in a conversational, slightly sarcastic way while actually trying to help or engage with their question/statement:"""
            
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Update conversation history
            self._update_conversation_history(user_id, message, response_text)
            
            return response_text
            
        except Exception as e:
            logger.error(f"AI chat response error: {e}")
            return None
    
    async def get_roast_response(self, character: str, target_name: str) -> Optional[str]:
        """Generate a character-based roast"""
        if not self.is_available() or character not in self.config.CHARACTER_PROMPTS:
            return None
        
        try:
            roast_prompts = {
                'hank': f"{self.config.CHARACTER_PROMPTS['hank']}\n\nRoast this Discord user named '{target_name}' in a friendly, playful way. Make fun of their lawn care, propane usage, or compare them to Bobby. Keep it PG-13, under 150 characters:",
                
                'dale': f"{self.config.CHARACTER_PROMPTS['dale']}\n\nRoast this Discord user named '{target_name}' in a paranoid, conspiracy-focused way. Suggest they're a government agent or part of some conspiracy. Keep it playful, under 150 characters:",
                
                'cartman': f"{self.config.CHARACTER_PROMPTS['cartman']}\n\nRoast this Discord user named '{target_name}' in Cartman's selfish, dramatic style. Call them lame or compare them to Kyle. Keep it PG-13, under 150 characters:",
                
                'redgreen': f"{self.config.CHARACTER_PROMPTS['redgreen']}\n\nRoast this Discord user named '{target_name}' using Red Green's practical, Canadian humor. Compare their usefulness to broken tools or government programs. Under 150 characters:",
                
                'trek': f"{self.config.CHARACTER_PROMPTS['trek']}\n\nRoast this Discord user named '{target_name}' using Star Trek technical language. Analyze their 'intelligence readings' or 'logic systems'. Keep it sci-fi and under 150 characters:",
                
                'alexjones': f"{self.config.CHARACTER_PROMPTS['alexjones']}\n\nRoast this Discord user named '{target_name}' by claiming they're part of some ridiculous conspiracy. Keep it over-the-top and under 200 characters:",
                
                'snake': f"{self.config.CHARACTER_PROMPTS['snake']}\n\nRoast this Discord user named '{target_name}' using military/tactical language. Suggest they'd be terrible at stealth missions. Under 150 characters:",
                
                'kratos': f"{self.config.CHARACTER_PROMPTS['kratos']}\n\nRoast this Discord user named '{target_name}' with godly disdain and disappointment. Compare them to weak mortals or failed warriors. Under 150 characters:",
                
                'dante': f"{self.config.CHARACTER_PROMPTS['dante']}\n\nRoast this Discord user named '{target_name}' by assigning them to an appropriate circle of hell for their sins. Keep it poetic and under 150 characters:"
            }
            
            prompt = roast_prompts.get(character, f"Roast {target_name} in a funny way, under 150 characters:")
            response = self.model.generate_content(prompt)
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"AI roast error for {character}: {e}")
            return None
    
    async def get_compliment_response(self, character: str, target_name: str) -> Optional[str]:
        """Generate a character-based compliment"""
        if not self.is_available() or character not in self.config.CHARACTER_PROMPTS:
            return None
        
        try:
            compliment_prompts = {
                'hank': f"{self.config.CHARACTER_PROMPTS['hank']}\n\nCompliment this Discord user named '{target_name}' in a wholesome, Hank Hill way. Mention propane, lawn care, or Texas values. Under 150 characters:",
                
                'dale': f"{self.config.CHARACTER_PROMPTS['dale']}\n\nGive a backhanded compliment to '{target_name}' suggesting they have good survival skills for the coming apocalypse. Under 150 characters:",
                
                'cartman': f"{self.config.CHARACTER_PROMPTS['cartman']}\n\nGive a self-serving compliment to '{target_name}' about how they're almost as cool as you. Under 150 characters:",
                
                'redgreen': f"{self.config.CHARACTER_PROMPTS['redgreen']}\n\nCompliment '{target_name}' by comparing them to useful tools or successful duct tape repairs. Under 150 characters:",
                
                'trek': f"{self.config.CHARACTER_PROMPTS['trek']}\n\nCompliment '{target_name}' using Star Trek technical language about their 'efficiency readings' or 'logic systems'. Under 150 characters:",
                
                'alexjones': f"{self.config.CHARACTER_PROMPTS['alexjones']}\n\nCompliment '{target_name}' by saying they're one of the few people who truly understand what's going on. Under 150 characters:",
                
                'snake': f"{self.config.CHARACTER_PROMPTS['snake']}\n\nCompliment '{target_name}' on their tactical awareness and potential as a soldier. Under 150 characters:",
                
                'kratos': f"{self.config.CHARACTER_PROMPTS['kratos']}\n\nGive grudging respect to '{target_name}' as a warrior worthy of acknowledgment. Under 150 characters:",
                
                'dante': f"{self.config.CHARACTER_PROMPTS['dante']}\n\nCompliment '{target_name}' by suggesting they have the potential for redemption and paradise. Under 150 characters:"
            }
            
            prompt = compliment_prompts.get(character, f"Compliment {target_name} in a nice way, under 150 characters:")
            response = self.model.generate_content(prompt)
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"AI compliment error for {character}: {e}")
            return None
    
    async def get_beer_recommendation(self, preferences: str = None) -> Optional[str]:
        """Get AI beer recommendation"""
        if not self.is_available():
            return None
        
        try:
            if preferences:
                prompt = f"You are a sassy, slightly unhinged but knowledgeable bartender. A user wants a beer recommendation. They prefer: '{preferences}'. Give them a funny, in-character recommendation for a real or fictional beer that fits their preference. Keep it short and witty."
            else:
                prompt = "You are a sassy, slightly unhinged but knowledgeable bartender. A user wants a beer recommendation. Give them a funny, in-character recommendation for a real or fictional beer. Keep it short and witty."
            
            response = self.model.generate_content(prompt)
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"AI beer recommendation error: {e}")
            return None
    
    def _update_conversation_history(self, user_id: int, user_message: str, bot_response: str):
        """Update conversation history for a user"""
        if user_id not in self.conversation_histories:
            self.conversation_histories[user_id] = []
        
        # Add new exchange
        self.conversation_histories[user_id].append((user_message, bot_response))
        
        # Trim history if too long
        if len(self.conversation_histories[user_id]) > self.max_history_length:
            self.conversation_histories[user_id] = self.conversation_histories[user_id][-self.max_history_length:]
    
    def clear_user_history(self, user_id: int):
        """Clear conversation history for a specific user"""
        if user_id in self.conversation_histories:
            del self.conversation_histories[user_id]