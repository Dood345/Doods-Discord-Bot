import asyncio
import logging
from typing import Dict, List, Optional

import aiohttp
from ping3 import ping

from config import BotConfig

logger = logging.getLogger(__name__)


class HomelabService:
    """Data access for homelab status, shared by slash commands and Cave's AI tools.

    Results never include IPs/hostnames so they are safe to repeat in a public channel.
    """

    async def _ping(self, service: Dict) -> Dict:
        try:
            # ping3 is blocking; keep it off the event loop
            response_time = await asyncio.to_thread(ping, service['ip'], timeout=1)
        except Exception:
            response_time = None
        return {
            "name": service['name'],
            "online": bool(response_time),
            "ms": round(response_time * 1000) if response_time else None,
        }

    async def service_status(self) -> List[Dict]:
        """Ping every configured homelab service concurrently."""
        services = [s for s in BotConfig.HOMELAB_SERVICES if s.get('ip')]
        return list(await asyncio.gather(*(self._ping(s) for s in services)))

    async def printer_status(self) -> Optional[Dict]:
        """Moonraker print stats, or None if the printer isn't configured/reachable."""
        if not BotConfig.PRINTER_HOST:
            return None
        url = f"http://{BotConfig.PRINTER_HOST}/printer/objects/query?print_stats"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status != 200:
                        return None
                    data = await response.json()
        except Exception as e:
            logger.debug(f"Could not connect to printer: {e}")
            return None

        stats = data.get('result', {}).get('status', {}).get('print_stats', {})
        duration = stats.get('print_duration', 0) or 0
        return {
            "state": stats.get('state', 'unknown'),
            "filename": stats.get('filename') or None,
            "duration": f"{int(duration // 3600)}h {int((duration % 3600) // 60)}m",
        }

    async def _arr_queue(self, name: str, url: Optional[str], key: Optional[str]) -> List[Dict]:
        if not url or not key:
            return []
        # Sonarr/Radarr use /api/v3/queue, Lidarr uses /api/v1/queue
        api_ver = "v1" if "lidarr" in name.lower() else "v3"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url}/api/{api_ver}/queue", headers={'X-Api-Key': key},
                                       timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status != 200:
                        return []
                    records = (await resp.json()).get('records', [])
        except Exception:
            return []

        items = []
        for r in records:
            status = r.get('status', 'Unknown')
            size, sizeleft = r.get('size', 0), r.get('sizeleft', 0)
            if size > 0:
                progress = f"{100 - (sizeleft / size * 100):.1f}%"
            else:
                progress = "Importing" if status == 'Completed' else "Unknown"
            items.append({"source": name, "title": r.get('title', 'Unknown'), "status": status, "progress": progress})
        return items

    async def download_queue(self) -> List[Dict]:
        """Active downloads across Sonarr, Radarr and Lidarr."""
        results = await asyncio.gather(
            self._arr_queue("📺 Sonarr", BotConfig.SONARR_URL, BotConfig.SONARR_API_KEY),
            self._arr_queue("🎬 Radarr", BotConfig.RADARR_URL, BotConfig.RADARR_API_KEY),
            self._arr_queue("🎵 Lidarr", BotConfig.LIDARR_URL, BotConfig.LIDARR_API_KEY),
        )
        return [item for sub in results for item in sub]
