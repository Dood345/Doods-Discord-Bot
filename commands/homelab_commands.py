import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
import asyncio
import logging
import io
from config import BotConfig
from utils.auth import is_authorized

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
        
        # Prepare payload, userId = 2 for discordBot user
        headers = {'X-Api-Key': self.api_key}
        payload = {
            "mediaId": self.media_id,
            "mediaType": self.media_type,
            "is4k": False,
            "userId": 2
        }

        # Handling for TV Shows (Must specify seasons)
        if self.media_type == 'tv':
            try:
                # We need to fetch the show details to know the season numbers!
                # Result from /search doesn't always have full season data
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{self.url}/api/v1/tv/{self.media_id}", headers=headers) as detail_resp:
                        if detail_resp.status == 200:
                            details = await detail_resp.json()
                            # Extract season numbers (exclude specials/season 0 if desired, but let's include all > 0)
                            seasons_list = [s['seasonNumber'] for s in details.get('seasons', []) if s['seasonNumber'] > 0]
                            payload['seasons'] = seasons_list
                        else:
                            # Fallback if fetch fails (unsafe, but better than nothing)
                            logger.error(f"Failed to fetch TV details: {detail_resp.status}")
                            payload['seasons'] = [1] 
            except Exception as e:
                logger.error(f"Error fetching TV details: {e}")
                payload['seasons'] = [1] # Fallback
        
        # Send Request
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
                        await interaction.followup.send(f"❌ Failed to request. Check logs for details ({resp.status}).", ephemeral=True)
        except Exception as e:
            logger.error(f"Request Exception: {e}")
            await interaction.followup.send("❌ Error contacting Overseerr.", ephemeral=True)

class HomeLabCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.homelab = bot.homelab_service
        self.update_printer_status.start()
        
    def cog_unload(self):
        self.update_printer_status.cancel()

    async def check_auth(self, interaction: discord.Interaction) -> bool:
        """Check if user is authorized to use homelab commands"""
        if is_authorized(interaction.user):
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
                            status_text = f"Printing at doodlab 🖨️"
                            await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=status_text))
                        else:
                            await self.bot.change_presence(activity=discord.Game(name="Playing with propane accessories"))
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
        for svc in await self.homelab.service_status():
            status = "🟢 Online" if svc["online"] else "🔴 Offline"
            ping_ms = f"({svc['ms']}ms)" if svc["online"] else ""
            results.append(f"**{svc['name']}**: {status} {ping_ms}")
        
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
        
        # Strip trailing slash just in case
        base_url = BotConfig.OVERSEERR_URL.rstrip('/')
        
        # Manually encode query to ensure compliance with strict Overseerr validation
        # The error "Parameter 'query' must be url encoded" suggests it hates raw spaces or specific chars
        from urllib.parse import quote
        encoded_query = quote(query)
        
        url = f"{base_url}/api/v1/search?query={encoded_query}&page=1&language=en"
        headers = {
            'X-Api-Key': BotConfig.OVERSEERR_API_KEY,
            'Accept': 'application/json'
        }
        # params = {} # We are putting everything in the URL string now to be safe
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.error(f"Overseerr Search Error: {resp.status} - {text}")
                        await interaction.followup.send(f"❌ Error talking to Overseerr ({resp.status}). Check logs.")
                        return
                    
                    data = await resp.json()
                    results = data.get('results', [])
                    
                    if not results:
                        await interaction.followup.send(f"🔍 No results found for '{query}'")
                        return
                    
                    # Limit to top 5 results for the dropdown
                    top_results = results[:5]
                    
                    # Create Select Menu Options
                    options = []
                    for res in top_results:
                        # Extract info
                        media_type = res.get('mediaType', 'unknown')
                        title = res.get('title', res.get('name', 'Unknown'))
                        year = res.get('releaseDate', res.get('firstAirDate', '????'))[:4]
                        tmdb_id = res.get('id')
                        
                        # Emoji based on type
                        emoji = "🎬" if media_type == 'movie' else "📺"
                        
                        # Value must be a string unique identifier
                        # We'll pack the data into the value: "id|type|title"
                        # But title might have pipes, so just use ID and Type
                        value = f"{tmdb_id}|{media_type}|{title[:50]}" 
                        
                        label = f"{title} ({year})"
                        desc = f"{media_type.upper()} - ID: {tmdb_id}"
                        
                        options.append(discord.SelectOption(label=label[:100], value=value, description=desc, emoji=emoji))

                    # Create View with Select Menu
                    select_view = MediaSelectView(options, BotConfig.OVERSEERR_API_KEY, base_url)
                    await interaction.followup.send(f"🔍 Found {len(results)} results for '**{query}**'. Select one:", view=select_view)
                    
        except Exception as e:
            logger.error(f"Search failed: {e}")
            await interaction.followup.send(f"❌ Something went wrong: {e}")

    @app_commands.command(name="dl-queue", description="View active downloads in valid *arr apps")
    async def view_queue(self, interaction: discord.Interaction):
        """View active downloads across *arr apps"""
        if not await self.check_auth(interaction):
            return
            
        await interaction.response.defer()
        
        embed = discord.Embed(title="📉 Download Queue", color=0x3498db)
        activities = []
        
        flat_results = await self.homelab.download_queue()
        
        if not flat_results:
            embed.description = "✅ No active downloads right now."
        else:
            for item in flat_results:
                activities.append(f"**{item['source']}**: {item['title']}\n└ `{item['status']}` ({item['progress']})")
            
            embed.description = "\n\n".join(activities)
            
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="requests", description="View recent Overseerr requests")
    async def view_requests(self, interaction: discord.Interaction):
        """View recent media requests on Overseerr"""
        if not await self.check_auth(interaction):
            return
            
        if not BotConfig.OVERSEERR_API_KEY:
            await interaction.response.send_message("❌ Overseerr API Key not configured!", ephemeral=True)
            return

        await interaction.response.defer()
        
        base_url = BotConfig.OVERSEERR_URL.rstrip('/')
        url = f"{base_url}/api/v1/request"
        headers = {'X-Api-Key': BotConfig.OVERSEERR_API_KEY}
        params = {
            'take': 6, # User requested top 6
            'skip': 0,
            'sort': 'added'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as resp:
                    if resp.status != 200:
                        await interaction.followup.send(f"❌ Error fetching requests: {resp.status}")
                        return
                    
                    data = await resp.json()
                    results = data.get('results', [])
                    
                    if not results:
                        await interaction.followup.send("📭 No active requests found.")
                        return
                    
                    embed = discord.Embed(title="📋 Recent Media Requests (Last 6)", color=0x9b59b6)
                    
                    # Helper function to fetch media details for title
                    async def fetch_details(req):
                        media = req.get('media', {})
                        tmdb_id = media.get('tmdbId')
                        media_type = req.get('type', media.get('mediaType', 'movie'))
                        
                        # Check Download Status
                        download_progress = ""
                        downloads = media.get('downloadStatus', [])
                        if downloads:
                            for d in downloads:
                                # We care about downloading state or just show progress if exists
                                s = d.get('size', 0)
                                sl = d.get('sizeLeft', d.get('sizeleft', 0))
                                if s > 0:
                                    pct = ((s - sl) / s) * 100
                                    # specific visual for downloading
                                    if d.get('status') == 'downloading':
                                        download_progress = f" ⬇️ {pct:.1f}%"
                                        break
                                    elif sl == 0:
                                        # Likely finished
                                        pass
                        
                        # Default info
                        info = {
                            'title': 'Unknown Title',
                            'year': '????',
                            'status': req.get('status', 1), # Request Status
                            'requester': req.get('requestedBy', {}).get('displayName', 'Unknown'),
                            'type': media_type,
                            'progress': download_progress
                        }
                        
                        if tmdb_id:
                             # Fetch full details to get the Title
                             try:
                                 detail_url = f"{base_url}/api/v1/{media_type}/{tmdb_id}"
                                 async with session.get(detail_url, headers=headers) as d_resp:
                                     if d_resp.status == 200:
                                         d_data = await d_resp.json()
                                         info['title'] = d_data.get('title', d_data.get('name', 'Unknown'))
                                         info['year'] = d_data.get('releaseDate', d_data.get('firstAirDate', '????'))[:4]
                             except Exception as e:
                                 logger.debug(f"Failed to fetch details for {tmdb_id}: {e}")
                        return info

                    # Fetch all details in parallel
                    tasks = [fetch_details(req) for req in results]
                    details_list = await asyncio.gather(*tasks)
                    
                    for item in details_list:
                        # Map Status Code
                        # 1=PENDING, 2=APPROVED, 3=DECLINED, 4=AVAILABLE, 5=PROCESSING
                        status_map = {
                            1: "⏳ Pending",
                            2: "✅ Approved", 
                            3: "❌ Declined",
                            4: "💿 Available",
                            5: "⚙️ Processing"
                        }
                        status_text = status_map.get(item['status'], f"Status: {item['status']}")
                        
                        # Append progress if downloading
                        if item['progress']:
                            status_text += item['progress']
                        
                        # Format: Title (Year) - Type
                        #         Status | Requester
                        embed.add_field(
                            name=f"{item['title']} ({item['year']})", 
                            value=f"{status_text} | 👤 {item['requester']}", 
                            inline=False
                        )
                    
                    await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Requests fetch failed: {e}")
            await interaction.followup.send(f"❌ Something went wrong: {e}")

class MediaSelectView(discord.ui.View):
    def __init__(self, options, api_key, url):
        super().__init__(timeout=60)
        self.api_key = api_key
        self.url = url
        
        # Add the select menu
        self.add_item(MediaSelect(options, api_key, url))

class MediaSelect(discord.ui.Select):
    def __init__(self, options, api_key, url):
        self.api_key = api_key
        self.url = url
        super().__init__(placeholder="Select media to request...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        # Decode the selected value
        selection = self.values[0]
        media_id, media_type, title = selection.split('|')
        media_id = int(media_id)
        
        # Defer update
        await interaction.response.defer()
        
        # Create the Request Embed and Button (reusing logic from before essentially)
        # But we need to fetch details for the embed to look nice? 
        # Or just show the generic RequestView we had.
        # Let's show a "Ready to Request" embed.
        
        embed = discord.Embed(title=f"🎬 Selected: {title}", description="Click the button below to confirm request.", color=0xf1c40f)
        embed.add_field(name="Type", value=media_type.upper(), inline=True)
        
        # Create Request View
        view = RequestView(title, media_id, media_type, self.api_key, self.url)
        
        # Edit the original message to show the selection and request button
        await interaction.edit_original_response(content="", embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(HomeLabCommands(bot))
