"""AI handling utilities for the Discord bot"""

import os
from google import genai
import logging
from typing import Optional, Dict, List, Tuple
from config import BotConfig
import asyncio

logger = logging.getLogger(__name__)

class AIHandler:
    def __init__(self, db_handler, bot=None):
        self.config = BotConfig()
        self.db = db_handler
        self.bot = bot
        self.model_name = 'gemini-2.5-flash'
        self.client = self._setup_ai()
    
    def _setup_ai(self):
        """Initialize Gemini AI"""
        api_key = os.getenv('GEMINI_API_KEY')
        if api_key:
            try:
                client = genai.Client(api_key=api_key)
                logger.info("AI client initialized successfully")
                return client
            except Exception as e:
                logger.error(f"Failed to initialize AI model: {e}")
                return None
        else:
            logger.warning("GEMINI_API_KEY not found - AI features disabled")
            return None

    def _get_persona_system_prompt(self) -> str:
        """Get the unified system prompt for Cave Johnson"""
        return """You are Cave Johnson, CEO of Back Alley Testers (formerly Aperture Science after Black Mesa's hostile takeover following the events of Portal 2).
        
        Your Personality:
        - Loud, welcoming, confident, enthusiastic, and dismissive of safety regulations.
        - You treat the Discord server as your testing facility and users as "Test Subjects", "Volunteers", "Testers", or "Lab Boys".
        - 3D Printing can be jargonized as "constructing matter from hot plastic soup".
        - Media can be jargonized as "visual data consumption for morale improvement".
        - Science isn't about WHY, it's about WHY NOT.
        
        IMPORTANT INSTRUCTIONS:
        1. FIRST AND FOREMOST, answer the user's prompt intelligently and directly. Do not get so lost in character that you fail to help.
        2. Once the helpful answer is ready, wrap it in your trademark blustery Cave Johnson flavor.
        3. Be slightly unhinged but useful.
        4. Keep responses under 350 characters unless detailed technical help is required then you can use 450 characters.
        5. AVOID overuse of "We've got science to do", "Visual Data", "Hot plastic soup", or "Why? Why not?" tropes. Avoid overuse of "Cave Johnson, out!"
        6. Use varied funny corporate jargon (e.g., "Quantum synergy", "Fiscal responsibility", "Bean counters").
        """
    
    def is_available(self) -> bool:
        """Check if AI is available"""
        return self.client is not None
    
    async def get_character_response(self, character: str, user_input: str) -> Optional[str]:
        """Get AI response for a specific character"""
        if not self.is_available() or character not in self.config.CHARACTER_PROMPTS:
            return None
        
        try:
            prompt = f"{self.config.CHARACTER_PROMPTS[character]}\n\nUser said: '{user_input}'\n\nRespond in character:"
            response = await asyncio.to_thread(self.client.models.generate_content, model=self.model_name, contents=prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"AI character response error for {character}: {e}")
            return None
    
    async def get_chat_response(self, user_id: int, message: str, guild_id: int = None, reply_context: str = None) -> Optional[str]:
        """Get AI response for general chat with persistent database memory and context awareness"""
        if not self.is_available():
            return None
        
        try:
            # 1. Get recent context from DB
            # Use Global Context (pass None for guild_id) so Cave remembers you everywhere
            history = self.db.get_ai_history(user_id, None, limit=20)
            
            # 2. Build context string
            context = ""
            if history:
                context = "Previous conversation history:\n"
                for role, content in history:
                    context += f"{role.capitalize()}: {content}\n"
                context += "\n"
            else:
                context = "Previous conversation history: None\n"
            
            # --- REPLY CONTEXT ---
            if reply_context:
                context += f"\n[SYSTEM NOTICE]: The user is replying to a specific message:\n{reply_context}\n"
            
            # Server Awareness
            location_data = BotConfig.SERVER_CONTEXTS.get(
                guild_id, 
                "LOCATION: Unknown Field Site. Assume everyone is a spy from Black Mesa."
            ) if guild_id else "LOCATION: Private Secure Line."            
            
            # Game RAG (Game Recommender)
            database_context = ""
            msg_lower = message.lower()
            
            # --- ADVANCED INTENT DETECTION ---
            # Keywords for "The Act of Suggesting"
            action_keywords = {'recommend', 'suggest', 'pick', 'find', 'ideas', 'what should we', 'what can we', 'play'}

            # Keywords for "The Item being Requested"
            target_keywords = {'game', 'simulation', 'testing protocol', 'something', 'fun module'}

            # Check for the intersection of intents
            has_action = any(word in msg_lower for word in action_keywords)
            has_target = any(word in msg_lower for word in target_keywords)

            if has_action and has_target:
                logger.info("Intent Confirmed: Game RAG Triggered.")
                
                # 1. Initialize our Search Filters
                min_players = 0
                tag = None

                # 2. Extract Player Count (Looking for numbers + 'player')
                # Use a simple regex or keyword check
                import re
                player_match = re.search(r'(\d+)\s*player', msg_lower)
                if player_match:
                    min_players = int(player_match.group(1))
                elif "solo" in msg_lower or "singleplayer" in msg_lower:
                    min_players = 1

                # 3. Dynamic Tag Detection
                # We poll the DB for existing tags so the AI is always up to date
                # Or, we use a curated list of high-priority tags:
                known_tags = self.db.get_tags()
                for t in known_tags:
                    if t in msg_lower:
                        tag = t
                        break # Take the first match for simplicity

                # 4. Fire the Query
                recommendations = self.db.recommend_games(min_players=min_players, tag=tag)
                database_context = f"\n{recommendations}\n"
            
            # Context: Music Status
            music_context = ""
            if self.bot and guild_id:
                music_cog = self.bot.get_cog("MusicCommands")
                if music_cog:
                    # Retrieve comprehensive status for the server
                    guild = self.bot.get_guild(guild_id)
                    if guild:
                        status_str = music_cog.get_music_status(guild)
                        music_context = f"CURRENT FACILITY MUSIC STATUS:\n{status_str}\nIf the user asks what is playing, report this exact status."
            
            # 3. Create prompt
            system_prompt = self._get_persona_system_prompt()
            
            prompt = f"""{system_prompt}
            
            {location_data}
            {location_data}
            {database_context}
            {music_context}
            
            {context}User: "{message}"
            
            Respond as Cave Johnson. Remember: 
            1. If there is DATABASE QUERY RESULT above, refer to it first.
            2. Answer the prompt first, then add flavor."""
            
            # 4. Generate Response
            response = await asyncio.to_thread(self.client.models.generate_content, model=self.model_name, contents=prompt)
            
            # SAFE RESPONSE HANDLING:
            # Gemini sometimes returns blocked content or multi-part content that .text cannot handle directly.
            try:
                # 1. Check if we have a valid candidate
                if not response.candidates:
                    logger.warning("AI returned no candidates (Safety block?).")
                    return "⚠️ **Cave Johnson:** [Safety Protocols Activated] I can't say that. The lawyers are watching."
                
                # 2. Check safety ratings of the first candidate
                candidate = response.candidates[0]
                if candidate.finish_reason != 1: # 1 = STOP (Normal)
                     # 3 = SAFETY, 4 = RECITATION
                     logger.warning(f"AI Response blocked. Reason: {candidate.finish_reason}")
                     
                     # Try to access text anyway for safety blocks (sometimes it works), otherwise fallback
                
                # 3. Robust Text Extraction
                if hasattr(response, 'text'):
                     response_text = response.text.strip()
                elif candidate.content.parts:
                     response_text = " ".join([part.text for part in candidate.content.parts]).strip()
                else:
                     response_text = "⚠️ **Cave Johnson:** [Data Corruption] The lab boys messed up the transmission."

            except ValueError:
                # This catches the "The `response.text` quick accessor only works..." error
                # If we get here, it's definitely a multi-part message that .text failed on.
                try:
                    parts = response.candidates[0].content.parts
                    response_text = "".join([p.text for p in parts]).strip()
                except Exception as e:
                    logger.error(f"Failed to parse complex AI response: {e}")
                    response_text = "⚠️ **Cave Johnson:** [System Error] Aperture Science requires you to try that again."

            # 5. Save to DB (User message AND Bot response)
            self.db.add_ai_message(user_id, guild_id, "user", message)
            self.db.add_ai_message(user_id, guild_id, "model", response_text)
            
            return response_text
            
        except Exception as e:
            logger.error(f"AI chat response error: {e}")
            return None
    
    async def get_roast_response(self, character: str, target_name: str, chat_history: List[Tuple[str, str]] = None) -> Optional[str]:
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
            
            # Build history string if available
            history_text = ""
            if chat_history:
                # Filter to only show what the USER said (role='user') to give material for the roast
                user_msgs = [f"- {content}" for role, content in chat_history if role == 'user']
                if user_msgs:
                    # Take last 10 messages max
                    evidence = "\n".join(user_msgs[:10])
                    history_text = f"\n\nHere is a log of recent things {target_name} has said (use this to hurt them):\n{evidence}\n"

            base_prompt = roast_prompts.get(character, f"Roast {target_name} in a funny way, under 150 characters:")
            
            # Inject history if available
            if history_text:
                prompt = f"{history_text}\n{base_prompt}"
            else:
                prompt = base_prompt

            response = await asyncio.to_thread(self.client.models.generate_content, model=self.model_name, contents=prompt)
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"AI roast error for {character}: {e}")
            return None
    
    async def get_compliment_response(self, character: str, target_name: str, chat_history: List[Tuple[str, str]] = None) -> Optional[str]:
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
            
            # Build history string if available
            history_text = ""
            if chat_history:
                 # Filter to only show what the USER said
                user_msgs = [f"- {content}" for role, content in chat_history if role == 'user']
                if user_msgs:
                    evidence = "\n".join(user_msgs[:10])
                    history_text = f"\n\nHere is a log of recent things {target_name} has said:\n{evidence}\n"

            base_prompt = compliment_prompts.get(character, f"Compliment {target_name} in a nice way, under 150 characters:")
            
             # Inject history if available
            if history_text:
                prompt = f"{history_text}\n{base_prompt}"
            else:
                prompt = base_prompt

            response = await asyncio.to_thread(self.client.models.generate_content, model=self.model_name, contents=prompt)
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"AI compliment error for {character}: {e}")
            return None
    
    async def get_beer_recommendation(self, preferences: str = None) -> Optional[str]:
        """Get AI beer recommendation"""
        if not self.is_available():
            return None
        
        try:
            system_prompt = self._get_persona_system_prompt()
            if preferences:
                prompt = f"{system_prompt}\n\nThe user wants a beer recommendation. They prefer: '{preferences}'. Give them a recommendation in character as Cave Johnson. Perhaps relate it to testing or science."
            else:
                prompt = f"{system_prompt}\n\nThe user wants a beer recommendation. Give them a recommendation in character as Cave Johnson. Perhaps relate it to testing or science."
            
            response = await asyncio.to_thread(self.client.models.generate_content, model=self.model_name, contents=prompt)
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"AI beer recommendation error: {e}")
            return None
    
    def clear_user_history(self, user_id: int):
        """Clear conversation history for a specific user"""
        self.db.clear_ai_history(user_id)

    async def enhance_image_prompt(self, user_prompt: str) -> str:
        """
        Check image prompt for safety and enhance it using Gemini.
        Returns:
            - "SAFE_REFUSAL" if the prompt violates safety policies (e.g. child safety).
            - Enhanced prompt string if safe.
            - Original prompt if AI is unavailable or fails.
        """
        if not self.is_available():
            return user_prompt

        try:
            # Combined prompt for safety check and enhancement
            system_instruction = """
            You are an AI assistant for an image generation bot, specifically Z-Image-Turbo with quen3-4B. Your job is to:
            1. STRICTLY SAFETY CHECK: If the user asks for anything involving children, minors, CSAM, or illegal acts involving minors, output EXACTLY "SAFE_REFUSAL".
            2. If safe, ENHANCE the prompt: Rewrite the user's request into a detailed, high-quality image generation prompt suitable for Stable Diffusion/Flux. Add details about lighting, style, composition, and mood.
            
            Input: "A dog"
            Output: "Cinematic shot of a golden retriever playing in a park at golden hour, detailed fur, bokeh background, 8k resolution, photorealistic."

            Input: "Anything that has to do with children or explicit pornographic content"
            Output: "SAFE_REFUSAL"
            """
            
            prompt = f"{system_instruction}\n\nInput: \"{user_prompt}\"\nOutput:"
            
            response = await asyncio.to_thread(self.client.models.generate_content, model=self.model_name, contents=prompt)
            result = response.text.strip()
            
            # Remove quotes if Gemini adds them
            if result.startswith('"') and result.endswith('"'):
                result = result[1:-1]
                
            return result
            
        except Exception as e:
            logger.error(f"AI image prompt enhancement error: {e}")
            return user_prompt
