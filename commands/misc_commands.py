"""Miscellaneous commands for the Discord bot"""

import discord
from discord import app_commands
from discord.ext import commands
import random
import logging
import qrcode
import io
import asyncio
from ping3 import ping

logger = logging.getLogger(__name__)

class MiscCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
        self.ai_handler = bot.ai_handler
    
    @app_commands.command(name='beer', description="Get a beer recommendation")
    async def beer_recommendation(self, interaction: discord.Interaction, preferences: str = None):
        """Get a beer recommendation, with AI power!"""
        await interaction.response.defer()
        
        # Try AI first
        if self.ai_handler.is_available():
            ai_response = await self.ai_handler.get_beer_recommendation(preferences)
            if ai_response:
                await interaction.followup.send(f"🍺 **Bartender AI:** {ai_response}")
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
        
        await interaction.followup.send(f"🍺 **Beer Recommendation:** {random.choice(fallback_beers)}")
    
    @app_commands.command(name='flubber', description="Make text bouncy like Flubber")
    async def flubberfy(self, interaction: discord.Interaction, text: str):
        """Make text bouncy like Flubber!"""
        if len(text) > 100:
            await interaction.response.send_message("❌ Text too long! Flubber can't bounce that much!", ephemeral=True)
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
        
        await interaction.response.send_message(f"🟢 **FLUBBER BOUNCE:** {bouncy_text} *boing boing boing*")
    
    @app_commands.command(name='emote', description="Test emoji reactions for a keyword")
    async def test_emote(self, interaction: discord.Interaction, keyword: str):
        """Test what emotes a keyword would trigger"""
        keyword = keyword.lower()
        
        if keyword in self.config.KEYWORD_REACTIONS:
            emojis = " ".join(self.config.KEYWORD_REACTIONS[keyword])
            await interaction.response.send_message(f"**'{keyword}'** triggers: {emojis}")
        else:
            sample_keywords = random.sample(list(self.config.KEYWORD_REACTIONS.keys()), 5)
            keywords_text = ", ".join(sample_keywords)
            await interaction.response.send_message(f"**'{keyword}'** doesn't trigger any special reactions.\n"
                          f"Try keywords like: {keywords_text}", ephemeral=True)
    
    @app_commands.command(name='keywords', description="Show all reaction keywords")
    async def list_keywords(self, interaction: discord.Interaction):
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
        
        embed.set_footer(text="Use /emote <keyword> to test specific reactions!")
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name='ping', description="Check bot latency")
    async def ping(self, interaction: discord.Interaction):
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
        
        await interaction.response.send_message(f"🏓 Pong! {status} - {latency}ms")
    
    @app_commands.command(name='about', description="Bot info")
    async def about(self, interaction: discord.Interaction):
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
                #   f"Commands: {len(self.bot.tree.get_commands())}",
                  f"Commands: {len([c for c in self.bot.tree.walk_commands()])}",
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
        
        embed.set_footer(text="Made for maximum shenanigans! Use /help for commands.")
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="qr", description="Generates a QR code for text or a link")
    async def qr(self, interaction: discord.Interaction, content: str):
        """Generate a QR code"""
        # Generate QR in memory (no file saved to laptop)
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(content)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        with io.BytesIO() as image_binary:
            img.save(image_binary, 'PNG')
            image_binary.seek(0)
            await interaction.response.send_message(
                f"Here is your QR code for: `{content}`",
                file=discord.File(fp=image_binary, filename='qrcode.png')
            )

    @app_commands.command(name="isup", description="Checks if a website or IP is reachable")
    async def isup(self, interaction: discord.Interaction, target: str):
        """Check if a site/IP is up"""
        await interaction.response.defer() # Give us time to ping
        try:
            # Simple ping check
            response_time = ping(target, timeout=2)
            if response_time:
                await interaction.followup.send(f"🟢 **{target}** is UP! (Response: {response_time*1000:.0f}ms)")
            else:
                await interaction.followup.send(f"🔴 **{target}** appears to be DOWN.")
        except Exception as e:
            await interaction.followup.send(f"⚠️ Error checking {target}: {str(e)}")

    # Custom help command
    @app_commands.command(name='help', description="Show all available commands")
    async def custom_help(self, interaction: discord.Interaction):
        """Show all available commands"""
        embed = discord.Embed(
            title="🤖 Doodlab Assistant Commands",
            description="Use `/` to see all commands in detail!",
            color=0xff6600
        )
        
        embed.add_field(
            name="👥 Social Features", 
            value="`/roast @user` - Roast someone\n"
                  "`/roastme` - Roast yourself\n"
                  "`/compliment @user` - Be nice for once", 
            inline=False
        )
        
        embed.add_field(
            name="🎭 Character AI", 
            value="`/hank`, `/dale`, `/cartman`\n"
                  "`/redgreen`, `/trek`, `/snake`\n"
                  "`/kratos`, `/dante`", 
            inline=False
        )
        
        embed.add_field(
            name="🎮 Games & Fun", 
            value="`/whatgame` - Pick a random game\n"
                  "`/gamevote` - Vote on games\n"
                  "`/gameslist` - Show all games\n"
                  "`/flubber` - Bouncy text\n"
                  "`/beer` - Beer recommendations", 
            inline=False
        )
        
        embed.add_field(
            name="🤖 AI & Tech", 
            value="`/ai` - Ask AI anything\n"
                  "`/clearhistory` - Clear chat memory\n"
                  "`/terminate` - Threat assessment\n"
                  "`/conspiracy` - Generate theories", 
            inline=False
        )
        
        embed.add_field(
            name="🏠 Doodlab", 
            value="`/gift_add`, `/gift_view`\n"
                  "`/gift_claim`, `/gift_remove`\n"
                  "`/qr` - Generate QR code\n"
                  "`/isup` - Check website status\n"
                  "`/doodlab` - Internal status\n"
                  "`/request` - Movie/TV requests\n"
                  "`/printer` - Check 3D printer status", 
            inline=False
        )
        
        embed.set_footer(text="Pro Tip: You can begin typing a command to see options!")
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(MiscCommands(bot))