"""Character-based commands for the Discord bot"""

import discord
from discord.ext import commands
import random
import logging

logger = logging.getLogger(__name__)

class CharacterCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
        self.ai_handler = bot.ai_handler
    
    async def _get_character_response(self, character: str, user_input: str = None):
        """Get a response from a character, AI first then fallback"""
        if user_input and self.ai_handler.is_available():
            ai_response = await self.ai_handler.get_character_response(character, user_input)
            if ai_response:
                return ai_response
        
        # Fallback to static quotes
        quotes = self.config.FALLBACK_QUOTES.get(character, ["*character malfunctioned*"])
        return random.choice(quotes)
    
    # KING OF THE HILL CHARACTERS
    @commands.command(name='hank', aliases=['hankhill'])
    async def hank_command(self, ctx, *, user_input=None):
        """Get a Hank Hill response - now with AI!"""
        response = await self._get_character_response('hank', user_input)
        char_info = self.config.CHARACTER_INFO['hank']
        await ctx.send(f"{char_info['name']}: {response}")
    
    @commands.command(name='dale', aliases=['dalegribble', 'gribble'])
    async def dale_command(self, ctx, *, user_input=None):
        """Dale Gribble conspiracy wisdom - now with AI!"""
        response = await self._get_character_response('dale', user_input)
        char_info = self.config.CHARACTER_INFO['dale']
        await ctx.send(f"{char_info['name']}: {response}")
    
    @commands.command(name='propane')
    async def propane_wisdom(self, ctx):
        """Sweet Lady Propane knowledge"""
        facts = [
            "Propane burns clean with a blue flame!",
            "Butane is a bastard gas!",
            "Taste the meat, not the heat!",
            "That's a clean burning hell, I tell you what!",
            "I sell propane and propane accessories, I tell you what!",
            "Propane is the future, I tell you what!"
        ]
        await ctx.send(f"🔥 **Propane Fact:** {random.choice(facts)}")
    
    # SOUTH PARK CHARACTERS
    @commands.command(name='cartman', aliases=['eric', 'ericcartman'])
    async def cartman_command(self, ctx, *, user_input=None):
        """Cartman being Cartman - now with AI!"""
        response = await self._get_character_response('cartman', user_input)
        char_info = self.config.CHARACTER_INFO['cartman']
        await ctx.send(f"{char_info['name']}: {response}")
    
    # RED GREEN SHOW
    @commands.command(name='redgreen', aliases=['red', 'green', 'redgreenshow'])
    async def red_green_command(self, ctx, *, problem=None):
        """Get Red Green's handy advice - now with AI!"""
        response = await self._get_character_response('redgreen', problem)
        char_info = self.config.CHARACTER_INFO['redgreen']
        await ctx.send(f"{char_info['name']}: {response}")
    
    # STAR TREK
    @commands.command(name='trek', aliases=['startrek', 'spock', 'kirk'])
    async def trek_command(self, ctx, *, problem=None):
        """Get a Star Trek technical solution - now with AI!"""
        response = await self._get_character_response('trek', problem)
        char_info = self.config.CHARACTER_INFO['trek']
        await ctx.send(f"{char_info['name']}: {response}")
    
    # ALEX JONES PARODY
    @commands.command(name='conspiracy', aliases=['alexjones'])
    async def conspiracy_command(self, ctx, *, topic=None):
        """Generate a ridiculous conspiracy theory"""
        if topic and self.ai_handler.is_available():
            ai_response = await self.ai_handler.get_character_response('alexjones', topic)
            if ai_response:
                char_info = self.config.CHARACTER_INFO['alexjones']
                await ctx.send(f"{char_info['name']}: {ai_response}")
                return
        
        # Fallback to static generator
        subjects = ["The globalists", "The deep state", "The new world order", "The interdimensional vampires", "Big Pharma"]
        actions = ["are turning", "have infiltrated", "are controlling", "are putting chemicals in"]
        objects = ["the water supply", "the school lunches", "the 5G towers", "the birds", "our DNA"]
        reasons = ["to make us docile", "to create a one-world government", "to lower our testosterone", "to harvest our life-force", "to turn the frogs gay"]
        
        theory = f"Folks, listen to me! {random.choice(subjects)} {random.choice(actions)} {random.choice(objects)} {random.choice(reasons)}! It's a war for your mind!"
        await ctx.send(f"🚨 **INFOWARS ALERT:** {theory}")
    
    # NEW CHARACTERS
    @commands.command(name='snake', aliases=['solidsnake', 'metalgear'])
    async def snake_command(self, ctx, *, user_input=None):
        """Solid Snake tactical wisdom"""
        response = await self._get_character_response('snake', user_input)
        char_info = self.config.CHARACTER_INFO['snake']
        await ctx.send(f"{char_info['name']}: {response}")
    
    @commands.command(name='kratos', aliases=['godofwar', 'boy'])
    async def kratos_command(self, ctx, *, user_input=None):
        """Kratos godly wisdom and rage"""
        response = await self._get_character_response('kratos', user_input)
        char_info = self.config.CHARACTER_INFO['kratos']
        await ctx.send(f"{char_info['name']}: {response}")
    
    @commands.command(name='dante', aliases=['dantesinferno', 'inferno'])
    async def dante_command(self, ctx, *, user_input=None):
        """Dante's wisdom from the depths of hell"""
        response = await self._get_character_response('dante', user_input)
        char_info = self.config.CHARACTER_INFO['dante']
        await ctx.send(f"{char_info['name']}: {response}")
    
    # TERMINATOR (Special case - not in the main character system)
    @commands.command(name='terminate')
    async def threat_assessment(self, ctx, *, target=None):
        """Terminator threat assessment"""
        if target:
            threat_levels = ["LOW", "MODERATE", "HIGH", "EXTREME", "DOES NOT COMPUTE"]
            recommendations = ['TERMINATE', 'MONITOR', 'IGNORE', 'OFFER BEER', 'RECRUIT FOR RESISTANCE']
            threat_level = random.choice(threat_levels)
            recommendation = random.choice(recommendations)
            
            await ctx.send(f"🤖 **THREAT ASSESSMENT:** {target.upper()}\n**THREAT LEVEL:** {threat_level}\n**RECOMMENDATION:** {recommendation}")
        else:
            await ctx.send("🤖 **T-800:** I need your clothes, your boots, and your motorcycle.")
    
    # GENERAL AI CHAT
    @commands.command(name='ai', aliases=['chat', 'ask'])
    async def ai_chat(self, ctx, *, question):
        """Ask the AI anything with conversation memory"""
        if not self.ai_handler.is_available():
            await ctx.send("🤖 AI is not configured. Add your GEMINI_API_KEY to .env file!")
            return
        
        try:
            response = await self.ai_handler.get_chat_response(ctx.author.id, question)
            if response:
                await ctx.send(f"🤖 **AI:** {response}")
            else:
                await ctx.send("🤖 Sorry, I'm having trouble processing that right now. Try again later!")
                
        except Exception as e:
            logger.error(f"AI chat error: {e}")
            await ctx.send("🤖 Something went wrong! Try again later.")
    
    @commands.command(name='clearhistory', aliases=['clearchat'])
    async def clear_history(self, ctx):
        """Clear your AI conversation history"""
        self.ai_handler.clear_user_history(ctx.author.id)
        await ctx.send("🤖 Your conversation history has been cleared!")

async def setup(bot):
    await bot.add_cog(CharacterCommands(bot))