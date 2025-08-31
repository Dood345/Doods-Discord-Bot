import discord
from discord.ext import commands
import asyncio
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# Import our custom modules
from config import BotConfig
from utils.ai_handler import AIHandler
from utils.reaction_handler import ReactionHandler
from commands.character_commands import CharacterCommands
from commands.social_commands import SocialCommands
from commands.game_commands import GameCommands
from commands.misc_commands import MiscCommands


# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# KEEP ALIVE for free hosting solutions
app = Flask('')

@app.route('/')
def home():
    return "I'm alive"

def run():
  # Cloud Run provides the PORT environment variable
  port = int(os.environ.get("PORT", 8080))
  app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()


class DoodsBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            case_insensitive=True,
            help_command=None  # We'll use custom help
        )
        
        # Initialize components
        self.config = BotConfig()
        self.ai_handler = AIHandler()
        self.reaction_handler = ReactionHandler()
        
        # User conversation histories for AI
        self.user_histories = {}
        
    async def setup_hook(self):
        """Called when the bot is starting up"""
        # Add cogs
        await self.add_cog(CharacterCommands(self))
        await self.add_cog(SocialCommands(self))
        await self.add_cog(GameCommands(self))
        await self.add_cog(MiscCommands(self))
        
        logger.info("All cogs loaded successfully")
    
    async def on_ready(self):
        """Called when bot connects to Discord"""
        logger.info(f'{self.user} has landed and is ready for shenanigans!')
        logger.info(f'Servers: {len(self.guilds)}')
        
        # Set bot status
        await self.change_presence(
            activity=discord.Game(name="with propane accessories")
        )
    
    async def on_message(self, message):
        """Handle all messages"""
        if message.author == self.user:
            return
        
        # Handle reactions
        await self.reaction_handler.handle_message(message)
        
        # Process commands
        await self.process_commands(message)
    
    async def on_command_error(self, ctx, error):
        """Global error handler"""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore unknown commands
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Missing required argument! Try `!help` to see how to use commands.")
        else:
            logger.error(f"Command error: {error}")
            await ctx.send("🤖 Something went wrong! The error has been logged.")

if __name__ == "__main__":
    """Main function to run the bot"""
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("DISCORD_TOKEN not found in .env file")
        exit(1)
    
    keep_alive() # Starts the web server

    bot = DoodsBot()
    
    try:
        logger.info("Starting bot...")
        bot.run(token, log_handler=None)  # We handle logging ourselves
    except KeyboardInterrupt:
        logger.info("Bot interrupted by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
    finally:
        logger.info("Bot shutdown complete!")