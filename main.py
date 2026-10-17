import discord
from discord import app_commands
from discord.ext import commands
import os
import sys
import logging
from dotenv import load_dotenv

from utils.logger import setup_logging


# Load environment variables FIRST before importing config
load_dotenv()

# Import our custom modules
from config import BotConfig
from utils.ai_handler import AIHandler
from utils.reaction_handler import ReactionHandler
from utils.database import DatabaseHandler
from utils.dialogue_manager import DialogueManager
from utils.error_reporting import ErrorReporter, handle_app_command_error
from utils.config_report import log_report as log_config_report
from commands.maintenance import write_ready_marker
from utils.hot_reload import EXTENSIONS, Reload
from services.gift_service import GiftService
from services.game_service import GameService
from services.homelab_service import HomelabService
from services.image_service import ImageService
from services.music_library import MusicLibrary
from services.points_service import PointsService
from services.ai_backlog import ERROR_REPLY, QUEUED_NOTE, AIBacklog, answer_mention
from services.test_chamber_service import TestChamberService

# Setup logging
setup_logging()
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
        
        # Initialize Service Layer abstractions
        self.dialogue = DialogueManager()
        
        self.gift_service = GiftService(self.db)
        self.game_service = GameService(self.db, self.dialogue)
        self.homelab_service = HomelabService()
        self.music_library = MusicLibrary()
        self.points_service = PointsService(self.db)
        self.ai_backlog = AIBacklog(self.db, self)
        self.test_chamber = TestChamberService(self.db, self.points_service)
        
        self.ai_handler = AIHandler(self.db, self)
        self.image_service = ImageService(self.ai_handler)
        self.reaction_handler = ReactionHandler(self.dialogue)
        
        # User conversation histories for AI
        self.user_histories = {}
        
    async def setup_hook(self):
        """Called when the bot is starting up"""
        self.errors = ErrorReporter(self, BotConfig.OWNER_ID)
        log_config_report()
        self.tree.on_error = self.on_app_command_error
        # Setup Database Tables
        await self.db.setup_tables()
        
        # Add cogs: each commands/ module is an extension so `!reload` can swap it live (utils/hot_reload.py)
        for extension in EXTENSIONS:
            await self.load_extension(extension)
        await self.add_cog(Reload(self))  # not an extension: it must never reload itself away
        
        logger.info("All cogs loaded successfully")
    
    async def on_ready(self):
        """Called when bot connects to Discord"""
        logger.info(f'🚀 {self.user} is online! Serving {len(self.guilds)} guilds.')
        try:
            write_ready_marker(guilds=len(self.guilds))  # the deploy's health check waits for this
        except OSError as e:
            logger.warning(f"Couldn't write the ready marker: {e}")
        
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

        # Science Points: +1 for showing up (first message of the day per server)
        if message.guild and not message.author.bot:
            try:
                if await self.points_service.record_activity(message.guild.id, message.author.id):
                    await message.add_reaction("🏆")  # new achievement; details in /points
            except Exception as e:
                logger.warning(f"Activity points failed: {e}")

        # Handle mentions (AI Chat)
        if self.user.mentioned_in(message) and not message.mention_everyone:
            if self.ai_handler.is_available():
                async def failed() -> str:
                    # Answered later, in order, once the model is back (services/ai_backlog.py)
                    return ERROR_REPLY + (QUEUED_NOTE if await self.ai_backlog.add(message) else "")

                outcome = await answer_mention(self, message, on_fail=failed)
                if outcome.status == "ok":
                    await self.ai_backlog.after_success(message)
            else:
                await message.reply("🤖 AI features are currently disabled (Missing API Key).")
        
        # Process commands (if any legacy ones remain)
        await self.process_commands(message)
    
    async def on_command_error(self, ctx, error):
        """Global error handler for prefix commands"""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore unknown commands
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Missing required argument! Try `!help` to see how to use commands.")
        else:
            await self.errors.report(f"!{ctx.command}", getattr(error, "original", error), str(ctx.author))
            await ctx.send("🤖 Something went wrong! The error has been logged.")

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Slash commands and context menus: tell the user, report the real cause to the owner."""
        await handle_app_command_error(self.errors, interaction, error)

    async def on_error(self, event_method: str, *args, **kwargs):
        """Exceptions escaping event handlers (on_message, tasks started from events, ...)."""
        _, error, _ = sys.exc_info()
        if error is not None:
            await self.errors.report(f"event {event_method}", error)

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
            # Instant sync to current server. Every command is global, so the server's own list is
            # empty until the global commands are copied into it.
            ctx.bot.tree.copy_global_to(guild=ctx.guild)
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
            await ctx.send(f"⚡ Synced {len(synced)} commands to **this server** instantly. "
                           "(If commands also show up twice after a global `!sync`, run `!sync clear` here.)")
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