import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

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

    # --- Overseerr -------------------------------------------------------------

    def _overseerr(self) -> Optional[Tuple[str, Dict]]:
        if not BotConfig.OVERSEERR_URL or not BotConfig.OVERSEERR_API_KEY:
            return None
        return BotConfig.OVERSEERR_URL.rstrip('/'), {'X-Api-Key': BotConfig.OVERSEERR_API_KEY, 'Accept': 'application/json'}

    async def search_media(self, query: str, limit: int = 5) -> Optional[List[Dict]]:
        """Movies/TV matching query, or None if Overseerr is unavailable."""
        conf = self._overseerr()
        if conf is None:
            return None
        base, headers = conf
        # Overseerr rejects queries that aren't strictly URL-encoded
        url = f"{base}/api/v1/search?query={quote(query)}&page=1&language=en"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        logger.error(f"Overseerr search error: {resp.status} - {await resp.text()}")
                        return None
                    results = (await resp.json()).get('results', [])
        except Exception as e:
            logger.error(f"Overseerr search failed: {e}")
            return None

        media = []
        for r in results:
            if r.get('mediaType') not in ('movie', 'tv'):
                continue
            media.append({
                "tmdb_id": r.get('id'),
                "media_type": r.get('mediaType'),
                "title": r.get('title') or r.get('name') or 'Unknown',
                "year": (r.get('releaseDate') or r.get('firstAirDate') or '????')[:4],
            })
        return media[:limit]

    async def media_details(self, tmdb_id: int, media_type: str) -> Optional[Dict]:
        """Title/year (and season numbers for TV) for one TMDB entry."""
        conf = self._overseerr()
        if conf is None or media_type not in ('movie', 'tv'):
            return None
        base, headers = conf
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{base}/api/v1/{media_type}/{int(tmdb_id)}", headers=headers,
                                       timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        return None
                    d = await resp.json()
        except Exception as e:
            logger.error(f"Overseerr details failed: {e}")
            return None
        return {
            "title": d.get('title') or d.get('name') or 'Unknown',
            "year": (d.get('releaseDate') or d.get('firstAirDate') or '????')[:4],
            "seasons": [x['seasonNumber'] for x in d.get('seasons', []) if x.get('seasonNumber', 0) > 0],
        }

    async def request_media(self, tmdb_id: int, media_type: str) -> Tuple[str, str]:
        """Submit an Overseerr request. Returns (status, title) with status in requested/duplicate/error."""
        conf = self._overseerr()
        if conf is None:
            return "error", "Overseerr is not configured"
        base, headers = conf
        details = await self.media_details(tmdb_id, media_type)
        title = details["title"] if details else str(tmdb_id)
        # userId 2 is the discordBot user in Overseerr
        payload = {"mediaId": int(tmdb_id), "mediaType": media_type, "is4k": False, "userId": 2}
        if media_type == 'tv':
            # TV requests must list seasons; fall back to season 1 if details failed
            payload['seasons'] = (details or {}).get('seasons') or [1]
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{base}/api/v1/request", headers=headers, json=payload,
                                        timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 201:
                        return "requested", title
                    if resp.status == 409:
                        return "duplicate", title
                    logger.error(f"Overseerr request failed: {resp.status} - {await resp.text()}")
                    return "error", title
        except Exception as e:
            logger.error(f"Overseerr request exception: {e}")
            return "error", title
