import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
import asyncio
import logging
from ping3 import ping
from config import BotConfig

logger = logging.getLogger(__name__)

class HomeLabCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Start the background task
        self.update_printer_status.start()
        
    def cog_unload(self):
        self.update_printer_status.cancel()

    @tasks.loop(seconds=60)
    async def update_printer_status(self):
        """Monitor 3D printer status"""
        if not BotConfig.PRINTER_HOST:
            return

        # Handle the Qidi/Fluidd port
        url = f"http://{BotConfig.PRINTER_HOST}/printer/objects/query?print_stats"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        state = data.get('result', {}).get('status', {}).get('print_stats', {}).get('state', 'unknown')
                        
                        if state == "printing":
                            # Could query display_status for % but keeping it simple for now
                            status_text = f"Printing on Voron 🖨️"
                            await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=status_text))
                        else:
                            # Reset to default status if not printing
                            await self.bot.change_presence(activity=discord.Game(name="with propane accessories"))
                    else:
                        logger.warning(f"Printer returned status {response.status}")
        except Exception as e:
            logger.debug(f"Could not connect to printer: {e}")

    @update_printer_status.before_loop
    async def before_printer_status(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="doodlab", description="Check status of Doodlab internal services")
    async def doodlab_status(self, interaction: discord.Interaction):
        """Check status of internal services"""
        await interaction.response.defer()
        
        embed = discord.Embed(
            title="🏠 Doodlab Status Center",
            description="Checking internal service connectivity...",
            color=0x2ecc71
        )
        
        results = []
        for service in BotConfig.HOMELAB_SERVICES:
            try:
                # Use ping for simple reachability
                response_time = ping(service['ip'], timeout=1)
                status = "🟢 Online" if response_time else "🔴 Offline"
                ping_ms = f"({response_time*1000:.0f}ms)" if response_time else ""
                results.append(f"**{service['name']}** ({service['ip']}): {status} {ping_ms}")
            except Exception:
                results.append(f"**{service['name']}** ({service['ip']}): 🔴 Offline (Error)")
        
        embed.description = "\n".join(results)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="request", description="Request media via *arr stack (Placeholder)")
    async def request_media(self, interaction: discord.Interaction, query: str, type: str):
        """Placeholder for Sonarr/Radarr requests"""
        # This requires API keys for Sonarr/Radarr, leaving as placeholder pattern for now
        embed = discord.Embed(title="💾 Media Request", color=0x3498db)
        embed.add_field(name="Request", value=query, inline=True)
        embed.add_field(name="Type", value=type, inline=True)
        embed.add_field(name="Status", value="Received (Not actually connected to *arr yet)", inline=False)
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(HomeLabCommands(bot))
