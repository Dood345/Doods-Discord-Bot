"""Character-based commands for the Discord bot"""

import discord
from discord import app_commands
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
    @app_commands.command(name='hank', description="Get a Hank Hill response")
    async def hank_command(self, interaction: discord.Interaction, user_input: str = None):
        await interaction.response.defer()
        response = await self._get_character_response('hank', user_input)
        char_info = self.config.CHARACTER_INFO['hank']
        await interaction.followup.send(f"{char_info['name']}: {response}")
    
    @app_commands.command(name='dale', description="Dale Gribble conspiracy wisdom")
    async def dale_command(self, interaction: discord.Interaction, user_input: str = None):
        await interaction.response.defer()
        response = await self._get_character_response('dale', user_input)
        char_info = self.config.CHARACTER_INFO['dale']
        await interaction.followup.send(f"{char_info['name']}: {response}")
    
    @app_commands.command(name='propane', description="Sweet Lady Propane knowledge")
    async def propane_wisdom(self, interaction: discord.Interaction):
        facts = [
            "Propane burns clean with a blue flame!",
            "Butane is a bastard gas!",
            "Taste the meat, not the heat!",
            "That's a clean burning hell, I tell you what!",
            "I sell propane and propane accessories, I tell you what!",
            "Propane is the future, I tell you what!"
        ]
        await interaction.response.send_message(f"🔥 **Propane Fact:** {random.choice(facts)}")
    
    # SOUTH PARK CHARACTERS
    @app_commands.command(name='cartman', description="Cartman being Cartman")
    async def cartman_command(self, interaction: discord.Interaction, user_input: str = None):
        await interaction.response.defer()
        response = await self._get_character_response('cartman', user_input)
        char_info = self.config.CHARACTER_INFO['cartman']
        await interaction.followup.send(f"{char_info['name']}: {response}")
    
    # RED GREEN SHOW
    @app_commands.command(name='redgreen', description="Get Red Green's handy advice")
    async def red_green_command(self, interaction: discord.Interaction, problem: str = None):
        await interaction.response.defer()
        response = await self._get_character_response('redgreen', problem)
        char_info = self.config.CHARACTER_INFO['redgreen']
        await interaction.followup.send(f"{char_info['name']}: {response}")
    
    # STAR TREK
    @app_commands.command(name='trek', description="Get a Star Trek technical solution")
    async def trek_command(self, interaction: discord.Interaction, problem: str = None):
        await interaction.response.defer()
        response = await self._get_character_response('trek', problem)
        char_info = self.config.CHARACTER_INFO['trek']
        await interaction.followup.send(f"{char_info['name']}: {response}")
    
    # ALEX JONES PARODY
    @app_commands.command(name='conspiracy', description="Generate a ridiculous conspiracy theory")
    async def conspiracy_command(self, interaction: discord.Interaction, topic: str = None):
        await interaction.response.defer()
        if topic and self.ai_handler.is_available():
            ai_response = await self.ai_handler.get_character_response('alexjones', topic)
            if ai_response:
                char_info = self.config.CHARACTER_INFO['alexjones']
                await interaction.followup.send(f"{char_info['name']}: {ai_response}")
                return
        
        # Fallback to static generator
        subjects = ["The globalists", "The deep state", "The new world order", "The interdimensional vampires", "Big Pharma"]
        actions = ["are turning", "have infiltrated", "are controlling", "are putting chemicals in"]
        objects = ["the water supply", "the school lunches", "the 5G towers", "the birds", "our DNA"]
        reasons = ["to make us docile", "to create a one-world government", "to lower our testosterone", "to harvest our life-force", "to turn the frogs gay"]
        
        theory = f"Folks, listen to me! {random.choice(subjects)} {random.choice(actions)} {random.choice(objects)} {random.choice(reasons)}! It's a war for your mind!"
        await interaction.followup.send(f"🚨 **INFOWARS ALERT:** {theory}")
    
    # NEW CHARACTERS
    @app_commands.command(name='snake', description="Solid Snake tactical wisdom")
    async def snake_command(self, interaction: discord.Interaction, user_input: str = None):
        await interaction.response.defer()
        response = await self._get_character_response('snake', user_input)
        char_info = self.config.CHARACTER_INFO['snake']
        await interaction.followup.send(f"{char_info['name']}: {response}")
    
    @app_commands.command(name='kratos', description="Kratos godly wisdom and rage")
    async def kratos_command(self, interaction: discord.Interaction, user_input: str = None):
        await interaction.response.defer()
        response = await self._get_character_response('kratos', user_input)
        char_info = self.config.CHARACTER_INFO['kratos']
        await interaction.followup.send(f"{char_info['name']}: {response}")
    
    @app_commands.command(name='dante', description="Dante's wisdom from the depths of hell")
    async def dante_command(self, interaction: discord.Interaction, user_input: str = None):
        await interaction.response.defer()
        response = await self._get_character_response('dante', user_input)
        char_info = self.config.CHARACTER_INFO['dante']
        await interaction.followup.send(f"{char_info['name']}: {response}")
    
    # TERMINATOR
    @app_commands.command(name='terminate', description="Terminator threat assessment")
    async def threat_assessment(self, interaction: discord.Interaction, target: str = None):
        if target:
            threat_levels = ["LOW", "MODERATE", "HIGH", "EXTREME", "DOES NOT COMPUTE"]
            recommendations = ['TERMINATE', 'MONITOR', 'IGNORE', 'OFFER BEER', 'RECRUIT FOR RESISTANCE']
            threat_level = random.choice(threat_levels)
            recommendation = random.choice(recommendations)
            
            await interaction.response.send_message(f"🤖 **THREAT ASSESSMENT:** {target.upper()}\n**THREAT LEVEL:** {threat_level}\n**RECOMMENDATION:** {recommendation}")
        else:
            await interaction.response.send_message("🤖 **T-800:** I need your clothes, your boots, and your motorcycle.")
    


async def setup(bot):
    await bot.add_cog(CharacterCommands(bot))