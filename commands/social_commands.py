"""Social interaction commands for the Discord bot"""

import discord
from discord import app_commands
from discord.ext import commands
import random
import logging

logger = logging.getLogger(__name__)

class SocialCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
        self.ai_handler = bot.ai_handler
    
    def _get_random_character(self):
        """Get a random character for roasts/compliments"""
        characters = list(self.config.CHARACTER_INFO.keys())
        # Remove alexjones from general rotation (too intense for regular roasts)
        if 'alexjones' in characters:
            characters.remove('alexjones')
        return random.choice(characters)
    
    @app_commands.command(name='roast', description="Roast a server member")
    async def roast_member(self, interaction: discord.Interaction, member: discord.Member = None):
        """Roast a server member (or yourself if no one specified)"""
        await interaction.response.defer()
        
        if member is None:
            member = interaction.user
        
        # Don't roast the bot itself
        if member == self.bot.user:
            await interaction.followup.send("🤖 Nice try, but I'm unroastable. I'm made of pure digital perfection!")
            return
        
        # Select random character
        character = self._get_random_character()
        char_info = self.config.CHARACTER_INFO[character]
        
        # Try AI first
        if self.ai_handler.is_available():
            # fetch history for context
            history = await self.bot.db.get_ai_history(member.id, interaction.guild.id if interaction.guild else None, limit=15)
            
            ai_response = await self.ai_handler.get_roast_response(character, member.display_name, chat_history=history)
            if ai_response:
                await interaction.followup.send(f"{member.mention} {char_info['name']}: {ai_response}")
                return
        
        roast = self.bot.dialogue.get(character, 'roasts', fallback="{user} is... special.", user=member.mention)
        await interaction.followup.send(f"{char_info['name']}: {roast}")
    
    @app_commands.command(name='compliment', description="Give someone a compliment")
    async def compliment_member(self, interaction: discord.Interaction, member: discord.Member = None):
        """Give someone a compliment (because we're not all mean!)"""
        await interaction.response.defer()

        if member is None:
            member = interaction.user
        
        if member == self.bot.user:
            await interaction.followup.send("🤖 Aww, thanks! You're pretty great yourself!")
            return
        
        # Select random character
        character = self._get_random_character()
        char_info = self.config.CHARACTER_INFO[character]
        
        # Try AI first
        if self.ai_handler.is_available():
            # fetch history for context
            history = await self.bot.db.get_ai_history(member.id, interaction.guild.id if interaction.guild else None, limit=15)

            ai_response = await self.ai_handler.get_compliment_response(character, member.display_name, chat_history=history)
            if ai_response:
                await interaction.followup.send(f"{char_info['name']}: {ai_response}")
                return
        
        compliment = self.bot.dialogue.get(character, 'compliments', fallback="{user} is pretty cool, I guess.", user=member.display_name)
        await interaction.followup.send(f"{char_info['name']}: {compliment}")
    
    @app_commands.command(name='roastme', description="Roast yourself")
    async def roast_self(self, interaction: discord.Interaction):
        """Roast yourself, you masochist"""
        # Forward to main roast function
        await self.roast_member(interaction, interaction.user)

async def setup(bot):
    await bot.add_cog(SocialCommands(bot))