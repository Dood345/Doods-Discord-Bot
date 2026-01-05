import discord
from discord.ext import commands
import asyncio
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# Load environment variables FIRST before importing config
load_dotenv()

# Import our custom modules
from config import BotConfig
from utils.ai_handler import AIHandler
from utils.reaction_handler import ReactionHandler
from utils.database import DatabaseHandler
from commands.character_commands import CharacterCommands
from commands.social_commands import SocialCommands
from commands.game_commands import GameCommands
from commands.misc_commands import MiscCommands
from commands.gift_commands import GiftCommands
from commands.homelab_commands import HomeLabCommands
from commands.image_cog import ImageCog

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
  port = int(os.environ.get("PORT", 6969))
  app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()


class DoodsBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(
            command_prefix='/',
            intents=intents,
            case_insensitive=True,
            help_command=None  # We'll use custom help
        )
        
        # Initialize components
        self.config = BotConfig()
        
        # Initialize Database
        self.db = DatabaseHandler()
        
        self.ai_handler = AIHandler(self.db)
        self.reaction_handler = ReactionHandler()
        
        # User conversation histories for AI
        self.user_histories = {}
        
    async def setup_hook(self):
        """Called when the bot is starting up"""
        # Setup Database Tables
        self.db.setup_tables()
        
        # Add cogs
        await self.add_cog(CharacterCommands(self))
        await self.add_cog(SocialCommands(self))
        await self.add_cog(GameCommands(self))
        await self.add_cog(MiscCommands(self))
        await self.add_cog(GiftCommands(self))
        await self.add_cog(HomeLabCommands(self))
        await self.add_cog(ImageCog(self))
        
        logger.info("All cogs loaded successfully")
    
    async def on_ready(self):
        """Called when bot connects to Discord"""
        logger.info(f'{self.user} has landed and is ready for shenanigans!')
        logger.info(f'Servers: {len(self.guilds)}')
        
        # Set bot status
        await self.change_presence(
            activity=discord.Game(name="Playing with propane accessories")
        )
        
        # Sync Slash Commands
        # Sync Slash Commands
        try:
            if self.config.SERVER_IDS:
                # 1. Sync to specific servers (Dev/Home Mode)
                logger.info(f"Syncing to {len(self.config.SERVER_IDS)} servers...")
                for server_id in self.config.SERVER_IDS:
                    try:
                        guild = discord.Object(id=server_id)
                        self.tree.copy_global_to(guild=guild)
                        await self.tree.sync(guild=guild)
                        logger.info(f"⚡ Slash commands synced to guild {server_id}")
                    except Exception as e:
                        logger.error(f"Failed to sync to guild {server_id}: {e}")
                
                # 2. CLEAR Global commands to avoid duplicates
                # This ensures commands only appear once (as Guild commands)
                # and don't linger as "Global" commands from previous runs
                self.tree.clear_commands(guild=None)
                await self.tree.sync()
                logger.info("🗑️ Cleared global commands to prevent duplicates")
            else:
                # 3. If no Server IDs, sync globally (Public Bot Mode)
                await self.tree.sync()
                logger.info(f"🌍 Global slash commands synced (may take up to 1 hour to propagate)")
            
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")
    
    async def on_message(self, message):
        """Handle all messages"""
        if message.author == self.user:
            return
        
        # Handle reactions
        await self.reaction_handler.handle_message(message)

        # Handle mentions (AI Chat)
        if self.user.mentioned_in(message) and not message.mention_everyone:
            # Strip the mention to get the actual message (handling nickname mentions too)
            content = message.content.replace(f'<@{self.user.id}>', '').replace(f'<@!{self.user.id}>', '').strip()
            
            if not content:
                content = "Hello!" # Default if just mentioned
                
            if self.ai_handler.is_available():
                async with message.channel.typing():
                    response = await self.ai_handler.get_chat_response(message.author.id, content)
                    if response:
                        await message.reply(response)
                    else:
                        await message.reply("🤖 *confused processing noises* (AI error)")
            else:
                await message.reply("🤖 AI features are currently disabled (Missing API Key).")
        
        # Process commands (if any legacy ones remain)
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