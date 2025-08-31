"""Miscellaneous commands for the Discord bot"""

import discord
from discord.ext import commands
import random
import logging

logger = logging.getLogger(__name__)

class MiscCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
        self.ai_handler = bot.ai_handler
    
    @commands.command(name='beer')
    async def beer_recommendation(self, ctx, *, preferences: str = None):
        """Get a beer recommendation, with AI power!"""
        # Try AI first
        if self.ai_handler.is_available():
            ai_response = await self.ai_handler.get_beer_recommendation(preferences)
            if ai_response:
                await ctx.send(f"🍺 **Bartender AI:** {ai_response}")
                return
        
        # Fallback beers
        fallback_beers = [
            "Alamo Beer (if you can find it)",
            "A nice cold Budweiser",
            "Whatever's cheapest",
            "Something with more alcohol",
            "Beer? In this economy?",
            "The one in your hand",
            "Red Green's homemade brew (proceed with caution)",
            "Duff Beer - it's what Homer would drink",
            "Propane-flavored beer (Hank Hill's dream)",
            "Something that pairs well with conspiracy theories"
        ]
        
        await ctx.send(f"🍺 **Beer Recommendation:** {random.choice(fallback_beers)}")
    
    @commands.command(name='flubber')
    async def flubberfy(self, ctx, *, text):
        """Make text bouncy like Flubber!"""
        if len(text) > 100:
            await ctx.send("❌ Text too long! Flubber can't bounce that much!")
            return
        
        bouncy_text = ""
        for i, char in enumerate(text):
            if char.isalpha():
                if i % 2 == 0:
                    bouncy_text += char.upper()
                else:
                    bouncy_text += char.lower()
            else:
                bouncy_text += char
        
        await ctx.send(f"🟢 **FLUBBER BOUNCE:** {bouncy_text} *boing boing boing*")
    
    @commands.command(name='emote', aliases=['react', 'emoji'])
    async def test_emote(self, ctx, *, keyword):
        """Test what emotes a keyword would trigger"""
        keyword = keyword.lower()
        
        if keyword in self.config.KEYWORD_REACTIONS:
            emojis = " ".join(self.config.KEYWORD_REACTIONS[keyword])
            await ctx.send(f"**'{keyword}'** triggers: {emojis}")
            
            # Actually react to demonstrate
            for emoji in self.config.KEYWORD_REACTIONS[keyword][:3]:  # Limit to 3 reactions
                try:
                    await ctx.message.add_reaction(emoji)
                except Exception as e:
                    logger.debug(f"Failed to add reaction {emoji}: {e}")
        else:
            sample_keywords = random.sample(list(self.config.KEYWORD_REACTIONS.keys()), 5)
            keywords_text = ", ".join(sample_keywords)
            await ctx.send(f"**'{keyword}'** doesn't trigger any special reactions.\n"
                          f"Try keywords like: {keywords_text}")
    
    @commands.command(name='keywords', aliases=['reactions'])
    async def list_keywords(self, ctx):
        """Show all available reaction keywords"""
        embed = discord.Embed(
            title="🎭 Reaction Keywords",
            description="These keywords can trigger emoji reactions:",
            color=0xff9900
        )
        
        # Group keywords by category
        categories = {
            "King of the Hill": ["propane", "hank", "dale", "texas", "lawn"],
            "South Park": ["cartman", "kenny", "respect", "authoritah"],
            "Characters": ["snake", "kratos", "dante", "redgreen"],
            "Sci-Fi": ["ai", "robot", "alien", "predator", "quantum"],
            "Games": ["valheim", "minecraft", "survival", "gaming"],
            "Fun": ["beer", "america", "freedom", "pizza", "coffee"]
        }
        
        for category, keywords in categories.items():
            # Only show keywords that actually exist in our config
            valid_keywords = [k for k in keywords if k in self.config.KEYWORD_REACTIONS]
            if valid_keywords:
                embed.add_field(
                    name=category,
                    value=", ".join(valid_keywords),
                    inline=True
                )
        
        embed.add_field(
            name="📊 Stats",
            value=f"Total keywords: {len(self.config.KEYWORD_REACTIONS)}\n"
                  f"Reaction chance: {self.config.REACTION_CHANCE}%",
            inline=False
        )
        
        embed.set_footer(text="Use !emote <keyword> to test specific reactions!")
        await ctx.send(embed=embed)
    
    @commands.command(name='ping')
    async def ping(self, ctx):
        """Check bot latency"""
        latency = round(self.bot.latency * 1000)
        
        if latency < 100:
            status = "🟢 Excellent"
        elif latency < 200:
            status = "🟡 Good"
        elif latency < 300:
            status = "🟠 Fair"
        else:
            status = "🔴 Poor"
        
        await ctx.send(f"🏓 Pong! {status} - {latency}ms")
    
    @commands.command(name='about', aliases=['info'])
    async def about(self, ctx):
        """Show information about the bot"""
        embed = discord.Embed(
            title="🤖 Satan's Shenanigans Bot",
            description="A character-based Discord bot with AI personality responses!",
            color=0xff6600
        )
        
        # Bot stats
        embed.add_field(
            name="📊 Stats",
            value=f"Servers: {len(self.bot.guilds)}\n"
                  f"Characters: {len(self.config.CHARACTER_INFO)}\n"
                  f"Commands: {len(self.bot.commands)}",
            inline=True
        )
        
        # AI status
        ai_status = "🟢 Active" if self.ai_handler.is_available() else "🔴 Disabled"
        embed.add_field(
            name="🧠 AI Status",
            value=ai_status,
            inline=True
        )
        
        # Features
        embed.add_field(
            name="✨ Features",
            value="• Character AI responses\n"
                  "• Conversation memory\n"
                  "• Keyword reactions\n"
                  "• Game voting\n"
                  "• Social commands",
            inline=True
        )
        
        embed.set_footer(text="Made for maximum shenanigans! Use !help for commands.")
        await ctx.send(embed=embed)
    
    # Custom help command
    @commands.command(name='help')
    async def custom_help(self, ctx, *, command_name=None):
        """Show all available commands or details about a specific command"""
        if command_name:
            # Show help for specific command
            command = self.bot.get_command(command_name.lower())
            if command:
                embed = discord.Embed(
                    title=f"📖 Help: !{command.name}",
                    description=command.help or "No description available.",
                    color=0x0099ff
                )
                
                if command.aliases:
                    embed.add_field(
                        name="Aliases",
                        value=", ".join([f"!{alias}" for alias in command.aliases]),
                        inline=False
                    )
                
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"❌ Command '!{command_name}' not found. Use `!help` to see all commands.")
            return
        
        # Show all commands
        embed = discord.Embed(
            title="🤖 Jesus' Shenanigans Bot Commands",
            description="All characters use AI responses when possible, with fallbacks!",
            color=0xff6600
        )
        
        embed.add_field(
            name="👥 Social Features", 
            value="`!roast @user` - Roast someone\n"
                  "`!roastme` - Roast yourself\n"
                  "`!compliment @user` - Be nice for once", 
            inline=False
        )
        
        embed.add_field(
            name="🎭 Character AI (use with messages!)", 
            value="`!hank [message]` - Hank Hill wisdom\n"
                  "`!dale [message]` - Conspiracy theories\n"
                  "`!cartman [message]` - Cartman being Cartman\n"
                  "`!redgreen [problem]` - Duct tape solutions\n"
                  "`!trek [problem]` - Star Trek tech support\n"
                  "`!snake [message]` - Solid Snake tactics\n"
                  "`!kratos [message]` - God of War rage\n"
                  "`!dante [message]` - Infernal wisdom", 
            inline=False
        )
        
        embed.add_field(
            name="🎮 Games & Fun", 
            value="`!whatgame` - Pick a random game\n"
                  "`!gamevote [games]` - Vote on games\n"
                  "`!gameslist` - Show all available games\n"
                  "`!flubber <text>` - Bouncy text\n"
                  "`!beer [preferences]` - Beer recommendations", 
            inline=False
        )
        
        embed.add_field(
            name="🤖 AI & Tech", 
            value="`!ai <question>` - Ask AI anything (with memory!)\n"
                  "`!clearhistory` - Clear your AI chat history\n"
                  "`!terminate [target]` - Threat assessment\n"
                  "`!conspiracy [topic]` - Generate theories", 
            inline=False
        )
        
        embed.add_field(
            name="😄 Extras", 
            value="`!propane` - Propane facts\n"
                  "`!emote <keyword>` - Test emoji reactions\n"
                  "`!keywords` - Show all reaction keywords\n"
                  "`!ping` - Check bot latency\n"
                  "`!about` - Bot information", 
            inline=False
        )
        
        embed.add_field(
            name="🎯 Pro Tips", 
            value="• Bot reacts with emojis to keywords like 'propane', 'beer', 'ai', etc.\n"
                  "• AI responses have conversation memory - it remembers your chats!\n"
                  "• All commands are case-insensitive\n"
                  "• Characters get funnier when you talk TO them with messages!", 
            inline=False
        )
        
        embed.set_footer(text="Use !help <command> for detailed info about specific commands")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(MiscCommands(bot))