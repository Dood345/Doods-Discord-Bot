import discord
from discord.ext import commands
import asyncio
import os
import logging
from datetime import datetime
from dotenv import load_dotenv


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
from commands.music import MusicCommands

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)





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
        
        # Initialize Database
        self.db = DatabaseHandler()
        
        self.ai_handler = AIHandler(self.db, self)
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
        await self.add_cog(MusicCommands(self))
        
        logger.info("All cogs loaded successfully")
    
    async def on_ready(self):
        """Called when bot connects to Discord"""
        logger.info(f'🚀 {self.user} is online! Serving {len(self.guilds)} guilds.')
        
        # Set bot status
        await self.change_presence(
            activity=discord.Game(name="Science | /help")
        )
        
        # NOTE: Auto-sync logic removed. Use !sync . to sync.
    
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
                    # Get guild ID if available (for context awareness)
                    guild_id = message.guild.id if message.guild else None
                    response = await self.ai_handler.get_chat_response(message.author.id, content, guild_id)
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

    bot = DoodsBot()

    # --- THE MAGIC SYNC COMMAND ---
    # Only the owner (you) can run this.
    # Usage: 
    #   !sync        -> Syncs globally (takes 1 hour to appear everywhere)
    #   !sync .      -> Syncs to THIS server instantly (for testing)
    @bot.command()
    @commands.is_owner()
    async def sync(ctx, spec: str = None):
        if spec == ".":
            # Instant sync to current server
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
            await ctx.send(f"⚡ Synced {len(synced)} commands to **this server** instantly.")
        elif spec == "clear":
            # Nuke commands (if you made a mess)
            ctx.bot.tree.clear_commands(guild=ctx.guild)
            await ctx.bot.tree.sync(guild=ctx.guild)
            await ctx.send("🗑️ Cleared local guild commands.")
        else:
            # Standard Global Sync
            synced = await ctx.bot.tree.sync()
            await ctx.send(f"🌍 Synced {len(synced)} commands **Globally**. (Updates in ~1 hour).")
    
    try:
        logger.info("Starting bot...")
        bot.run(token, log_handler=None)  # We handle logging ourselves
    except KeyboardInterrupt:
        logger.info("Bot interrupted by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
    finally:
        logger.info("Bot shutdown complete!")