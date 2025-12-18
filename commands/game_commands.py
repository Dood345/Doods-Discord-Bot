"""Game-related commands for the Discord bot"""

import discord
from discord import app_commands
from discord.ext import commands
import random
import logging

logger = logging.getLogger(__name__)

class GameCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
    
    @app_commands.command(name='whatgame', description="Pick a random game to play")
    async def random_game(self, interaction: discord.Interaction):
        """Pick a random game to play"""
        game = random.choice(self.config.GAMES_LIST)
        emojis = ["🎮", "🕹️", "🎯", "🏆", "⚔️", "🎲", "🌟"]
        await interaction.response.send_message(f"{random.choice(emojis)} **Game Night Selection:** {game}")
    
    @app_commands.command(name='gamevote', description="Vote on games (separate with commas)")
    async def game_vote(self, interaction: discord.Interaction, games_list: str = None):
        """Start a vote for what game to play"""
        if not games_list:
            # If no games specified, pick 4 random ones
            games = random.sample(self.config.GAMES_LIST, min(4, len(self.config.GAMES_LIST)))
        else:
            # Parse comma separated list
            games = [g.strip() for g in games_list.split(',') if g.strip()]
        
        if len(games) > 10:
            await interaction.response.send_message("⚠️ Whoa there, cowboy! Max 10 games for voting.", ephemeral=True)
            return
        
        if not games:
            await interaction.response.send_message("❌ Please provide at least one game!", ephemeral=True)
            return

        # Create embed
        embed = discord.Embed(
            title="🗳️ Game Night Vote!",
            description="React to vote for what game to play!",
            color=0x00ff00
        )
        
        # Number emojis for voting
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        
        # Add fields for each game
        for i, game in enumerate(games):
            embed.add_field(
                name=f"{emojis[i]} {game}",
                value="",
                inline=False
            )
        
        embed.set_footer(text="Vote ends when someone gets bored of waiting!")
        
        # Send message and add reactions
        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        
        for i in range(len(games)):
            try:
                await message.add_reaction(emojis[i])
            except Exception as e:
                logger.error(f"Failed to add reaction {emojis[i]}: {e}")
    
    @app_commands.command(name='addgame', description="Suggest a game to add")
    async def add_game(self, interaction: discord.Interaction, game_name: str):
        """Suggest a game to add to the list"""
        if not game_name or len(game_name) > 50:
            await interaction.response.send_message("❌ Game name must be between 1-50 characters!", ephemeral=True)
            return
        
        responses = [
            f"🎮 '{game_name}' has been noted for potential addition to the games list!",
            f"🤔 '{game_name}'? Interesting choice! I'll consider it.",
            f"📝 Added '{game_name}' to the 'maybe someday' pile.",
            f"🎯 '{game_name}' - now that's what I call a suggestion!",
            f"⭐ '{game_name}' could be fun! Good thinking."
        ]
        
        await interaction.response.send_message(random.choice(responses))
    
    @app_commands.command(name='gameslist', description="Show all available games")
    async def list_games(self, interaction: discord.Interaction):
        """Show all available games"""
        embed = discord.Embed(
            title="🎮 Available Games",
            description="Here are all the games I can randomly select:",
            color=0x0099ff
        )
        
        # Split games into chunks for better display
        games_text = ", ".join(self.config.GAMES_LIST)
        
        # Discord embed field limit is 1024 characters
        if len(games_text) <= 1024:
            embed.add_field(name="Games", value=games_text, inline=False)
        else:
            # Split into multiple fields if too long
            words = self.config.GAMES_LIST
            current_field = ""
            field_count = 1
            
            for game in words:
                if len(current_field + game + ", ") <= 1024:
                    current_field += game + ", "
                else:
                    # Remove trailing comma and space
                    embed.add_field(
                        name=f"Games (Part {field_count})",
                        value=current_field.rstrip(", "),
                        inline=False
                    )
                    current_field = game + ", "
                    field_count += 1
            
            # Add the last field
            if current_field:
                embed.add_field(
                    name=f"Games (Part {field_count})",
                    value=current_field.rstrip(", "),
                    inline=False
                )
        
        embed.set_footer(text=f"Total: {len(self.config.GAMES_LIST)} games")
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(GameCommands(bot))