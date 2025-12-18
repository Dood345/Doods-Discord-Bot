import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
import asyncio
import logging
import io
from ping3 import ping
from config import BotConfig

logger = logging.getLogger(__name__)

class RequestView(discord.ui.View):
    def __init__(self, title, media_id, media_type, api_key, url):
        super().__init__(timeout=60)
        self.title = title
        self.media_id = media_id
        self.media_type = media_type
        self.api_key = api_key
        self.url = url

    @discord.ui.button(label="Request This", style=discord.ButtonStyle.green, emoji="📥")
    async def request_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Disable button after click
        button.disabled = True
        await interaction.response.edit_message(view=self)
        
        # Send request to Overseerr
        # Endpoint: /api/v1/request
        headers = {'X-Api-Key': self.api_key}
        payload = {
            "mediaId": self.media_id,
            "mediaType": self.media_type,
            "is4k": False,
            "seasons": "all" if self.media_type == 'tv' else [] # Default to all seasons for simplicity
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.url}/api/v1/request", headers=headers, json=payload) as resp:
                    if resp.status == 201:
                        await interaction.followup.send(f"✅ Successfully requested **{self.title}**!", ephemeral=True)
                    elif resp.status == 409: # Already requested
                        await interaction.followup.send(f"⚠️ **{self.title}** is already requested!", ephemeral=True)
                    else:
                        error_text = await resp.text()
                        logger.error(f"Overseerr Request Failed: {resp.status} - {error_text}")
                        await interaction.followup.send(f"❌ Failed to request. Check logs.", ephemeral=True)
        except Exception as e:
            logger.error(f"Request Exception: {e}")
            await interaction.followup.send("❌ Error contacting Overseerr.", ephemeral=True)

class HomeLabCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.update_printer_status.start()
        
    def cog_unload(self):
        self.update_printer_status.cancel()

    async def check_auth(self, interaction: discord.Interaction) -> bool:
        """Check if user is authorized to use homelab commands"""
        user_id = interaction.user.id
        username = interaction.user.name.lower()
        
        # Check ID match or Username match
        if user_id == BotConfig.OWNER_ID or username in BotConfig.ALLOWED_USERS:
            return True
            
        await interaction.response.send_message("❌ **Access Denied**: Authorized Personnel Only ⛔", ephemeral=True)
        return False

    @tasks.loop(seconds=60)
    async def update_printer_status(self):
        """Monitor 3D printer status"""
        if not BotConfig.PRINTER_HOST:
            return

        url = f"http://{BotConfig.PRINTER_HOST}/printer/objects/query?print_stats"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        state = data.get('result', {}).get('status', {}).get('print_stats', {}).get('state', 'unknown')
                        
                        if state == "printing":
                            status_text = f"Printing on Voron 🖨️"
                            await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=status_text))
                        else:
                            await self.bot.change_presence(activity=discord.Game(name="with propane accessories"))
        except Exception as e:
            logger.debug(f"Could not connect to printer: {e}")

    @update_printer_status.before_loop
    async def before_printer_status(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="doodlab", description="Check status of Doodlab internal services")
    async def doodlab_status(self, interaction: discord.Interaction):
        """Check status of internal services"""
        if not await self.check_auth(interaction):
            return

        await interaction.response.defer()
        
        embed = discord.Embed(
            title="🏠 Doodlab Status Center",
            description="Checking internal service connectivity...",
            color=0x2ecc71
        )
        
        results = []
        for service in BotConfig.HOMELAB_SERVICES:
            try:
                response_time = ping(service['ip'], timeout=1)
                status = "🟢 Online" if response_time else "🔴 Offline"
                ping_ms = f"({response_time*1000:.0f}ms)" if response_time else ""
                results.append(f"**{service['name']}** ({service['ip']}): {status} {ping_ms}")
            except Exception:
                results.append(f"**{service['name']}** ({service['ip']}): 🔴 Offline (Error)")
        
        embed.description = "\n".join(results)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="printer", description="Check 3D Printer Status")
    async def printer_status(self, interaction: discord.Interaction):
        """Check actual 3D printer status"""
        if not await self.check_auth(interaction):
            return

        if not BotConfig.PRINTER_HOST:
            await interaction.response.send_message("❌ Printer Host not configured!", ephemeral=True)
            return

        await interaction.response.defer()
        
        url = f"http://{BotConfig.PRINTER_HOST}/printer/objects/query?print_stats"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        stats = data.get('result', {}).get('status', {}).get('print_stats', {})
                        state = stats.get('state', 'Unknown')
                        filename = stats.get('filename', 'None')
                        print_duration = stats.get('print_duration', 0)
                        
                        # Format duration
                        hours = int(print_duration // 3600)
                        minutes = int((print_duration % 3600) // 60)
                        time_str = f"{hours}h {minutes}m"
                        
                        color = 0x2ecc71 if state == "printing" else 0x95a5a6
                        
                        embed = discord.Embed(title="🖨️ 3D Printer Status", color=color)
                        embed.add_field(name="State", value=state.upper(), inline=True)
                        
                        if state == "printing":
                            embed.add_field(name="File", value=filename, inline=True)
                            embed.add_field(name="Duration", value=time_str, inline=True)
                        
                        # Try to get snapshot
                        files = []
                        if BotConfig.PRINTER_WEBCAM_URL:
                            try:
                                async with session.get(BotConfig.PRINTER_WEBCAM_URL, timeout=2) as img_resp:
                                    if img_resp.status == 200:
                                        data = await img_resp.read()
                                        files.append(discord.File(io.BytesIO(data), filename="snapshot.jpg"))
                                        embed.set_image(url="attachment://snapshot.jpg")
                            except Exception as e:
                                logger.debug(f"Failed to fetch snapshot: {e}")

                        await interaction.followup.send(embed=embed, files=files)
                    else:
                        await interaction.followup.send(f"⚠️ Could not reach printer (Status: {response.status})")
        except Exception as e:
            logger.error(f"Printer Check Failed: {e}")
            await interaction.followup.send(f"❌ Error checking printer: {str(e)}")

    @app_commands.command(name="request", description="Search & Request media from Overseerr")
    async def request_media(self, interaction: discord.Interaction, query: str):
        """Search Overseerr and request media"""
        if not await self.check_auth(interaction):
            return

        if not BotConfig.OVERSEERR_API_KEY:
            await interaction.response.send_message("❌ Overseerr API Key not configured!", ephemeral=True)
            return

        await interaction.response.defer()
        
        url = f"{BotConfig.OVERSEERR_URL}/api/v1/search?query={query}"
        headers = {'X-Api-Key': BotConfig.OVERSEERR_API_KEY}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        await interaction.followup.send(f"❌ Error talking to Overseerr: {resp.status}")
                        return
                    
                    data = await resp.json()
                    results = data.get('results', [])
                    
                    if not results:
                        await interaction.followup.send(f"🔍 No results found for '{query}'")
                        return
                    
                    # Take the first result
                    first = results[0]
                    title = first.get('title', first.get('name', 'Unknown'))
                    overview = first.get('overview', 'No description.')[:200] + "..."
                    poster = f"https://image.tmdb.org/t/p/w500{first.get('posterPath')}" if first.get('posterPath') else None
                    media_type = first.get('mediaType')
                    media_id = first.get('id')
                    
                    embed = discord.Embed(title=f"🎬 Found: {title}", description=overview, color=0xf1c40f)
                    if poster:
                        embed.set_thumbnail(url=poster)
                    embed.add_field(name="Type", value=media_type.upper(), inline=True)
                    embed.add_field(name="Date", value=first.get('releaseDate', first.get('firstAirDate', 'Unknown')), inline=True)
                    
                    # Create View with Button
                    view = RequestView(title, media_id, media_type, BotConfig.OVERSEERR_API_KEY, BotConfig.OVERSEERR_URL)
                    await interaction.followup.send(embed=embed, view=view)
                    
        except Exception as e:
            logger.error(f"Search failed: {e}")
            await interaction.followup.send(f"❌ Something went wrong: {e}")

    @app_commands.command(name="queue", description="View active downloads in valid *arr apps")
    async def view_queue(self, interaction: discord.Interaction):
        """View active downloads across *arr apps"""
        if not await self.check_auth(interaction):
            return
            
        await interaction.response.defer()
        
        embed = discord.Embed(title="📉 Download Queue", color=0x3498db)
        activities = []
        
        # Helper to check queue
        async def check_queue(name, url, key):
            if not url or not key: return []
            try:
                async with aiohttp.ClientSession() as session:
                    # Sonarr/Radarr use /api/v3/queue, Lidarr uses /api/v1/queue
                    api_ver = "v1" if "lidarr" in name.lower() else "v3"
                    endpoint = f"{url}/api/{api_ver}/queue"
                    
                    async with session.get(endpoint, headers={'X-Api-Key': key}, timeout=5) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            records = data.get('records', [])
                            return [(name, r) for r in records]
            except Exception:
                return []
            return []

        # Gather all queues concurrently
        tasks = [
            check_queue("📺 Sonarr", BotConfig.SONARR_URL, BotConfig.SONARR_API_KEY),
            check_queue("🎬 Radarr", BotConfig.RADARR_URL, BotConfig.RADARR_API_KEY),
            check_queue("🎵 Lidarr", BotConfig.LIDARR_URL, BotConfig.LIDARR_API_KEY)
        ]
        
        results = await asyncio.gather(*tasks)
        
        flat_results = [item for sublist in results for item in sublist]
        
        if not flat_results:
            embed.description = "✅ No active downloads right now."
        else:
            for source, record in flat_results:
                title = record.get('title', 'Unknown')
                status = record.get('status', 'Unknown')
                
                # Try to get progress
                size = record.get('size', 0)
                sizeleft = record.get('sizeleft', 0)
                if size > 0:
                    percent = 100 - (sizeleft / size * 100)
                    progress = f"{percent:.1f}%"
                else:
                    progress = "Importing" if status == 'Completed' else "Unknown"

                activities.append(f"**{source}**: {title}\n└ `{status}` ({progress})")
            
            embed.description = "\n\n".join(activities)
            
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(HomeLabCommands(bot))
