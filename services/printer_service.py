"""3D printer on Klipper + Moonraker (Mainsail/Fluidd, e.g. FreeDi), configured with just PRINTER_IP/PRINTER_PORT.

Webcam URLs are discovered from Moonraker (/server/webcams/list): the snapshot URL gives stills,
the stream URL (MJPEG) is recorded into a short clip with ffmpeg. Nothing returned here contains
an address, so results are safe to show in Discord.
"""

import asyncio
import logging
import os
import tempfile
import time
from typing import Dict, Optional, Tuple
from urllib.parse import urljoin

import aiohttp

from config import BotConfig

logger = logging.getLogger(__name__)

STATUS_OBJECTS = "print_stats&virtual_sdcard&display_status&extruder&heater_bed&heater_generic%20chamber" \
                 "&filament_switch_sensor%20filament"
WEBCAM_CACHE_SECONDS = 600
CLIP_SECONDS = 6
FAILED_STATES = ("error", "cancelled")


def _duration(seconds: float) -> str:
    seconds = int(seconds or 0)
    return f"{seconds // 3600}h {(seconds % 3600) // 60}m"


def parse_status(status: Dict) -> Dict:
    """Moonraker object query -> a friendly status dict (no addresses)."""
    stats = status.get("print_stats") or {}
    state = stats.get("state", "unknown")
    info = stats.get("info") or {}
    progress = (status.get("display_status") or {}).get("progress") or (status.get("virtual_sdcard") or {}).get("progress") or 0.0
    elapsed = stats.get("print_duration") or 0.0
    remaining = elapsed / progress - elapsed if state == "printing" and progress >= 0.02 else None
    temps = {}
    for key, label in (("extruder", "nozzle"), ("heater_bed", "bed"), ("heater_generic chamber", "chamber")):
        heater = status.get(key)
        if heater and heater.get("temperature") is not None:
            temps[label] = (round(heater["temperature"]), round(heater.get("target") or 0))
    sensor = status.get("filament_switch_sensor filament") or {}
    filename = (stats.get("filename") or "").rsplit("/", 1)[-1]
    return {
        "state": state,
        "filename": filename[:-6] if filename.endswith(".gcode") else (filename or None),
        "progress": round(progress * 100),
        "duration": _duration(elapsed),
        "remaining": _duration(remaining) if remaining is not None else None,
        "layer": (info.get("current_layer"), info.get("total_layer")) if info.get("total_layer") else None,
        "temps": temps,
        "filament_detected": sensor.get("filament_detected") if sensor.get("enabled", True) else None,
        "message": stats.get("message") or None,
    }


def describe(status: Dict) -> str:
    """One readable line for Cave's tool / DMs."""
    if status["state"] == "printing":
        parts = [f"printing {status['filename'] or 'a file'}: {status['progress']}% done", f"{status['duration']} elapsed"]
        if status["remaining"]:
            parts.append(f"about {status['remaining']} left")
        if status["layer"]:
            parts.append(f"layer {status['layer'][0]}/{status['layer'][1]}")
        text = ", ".join(parts)
    else:
        text = status["state"]
    if status["temps"]:
        text += ". " + ", ".join(f"{name} {cur}°C" + (f"/{tgt}°C" if tgt else "") for name, (cur, tgt) in status["temps"].items())
    if status["filament_detected"] is False:
        text += ". ⚠️ Filament sensor reports NO filament"
    return text + "."


class PrinterService:
    def __init__(self, ip: Optional[str] = None, port: Optional[int] = None):
        self.ip = ip if ip is not None else BotConfig.PRINTER_IP
        self.port = port if port is not None else BotConfig.PRINTER_PORT
        self._webcam: Tuple[float, Optional[Dict]] = (0.0, None)

    @property
    def configured(self) -> bool:
        return bool(self.ip)

    @property
    def base_url(self) -> str:
        return f"http://{self.ip}:{self.port}"

    async def _get_json(self, path: str, timeout: float = 5) -> Optional[Dict]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}{path}", timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    if resp.status != 200:
                        return None
                    return (await resp.json(content_type=None)).get("result")
        except Exception as e:
            logger.debug(f"Printer request {path} failed: {e!r}")
            return None

    async def status(self) -> Optional[Dict]:
        """Parsed status, or None if the printer isn't configured/reachable."""
        if not self.configured:
            return None
        result = await self._get_json(f"/printer/objects/query?{STATUS_OBJECTS}")
        return parse_status(result.get("status", {})) if result else None

    async def last_job(self) -> Optional[Dict]:
        """Most recent job from Moonraker's history: filename, status (completed/cancelled/error...), durations."""
        result = await self._get_json("/server/history/list?limit=1&order=desc")
        jobs = (result or {}).get("jobs") or []
        if not jobs:
            return None
        job = jobs[0]
        name = (job.get("filename") or "").rsplit("/", 1)[-1]
        return {"filename": name[:-6] if name.endswith(".gcode") else name, "status": job.get("status"),
                "duration": _duration(job.get("print_duration")),
                "filament_m": round((job.get("filament_used") or 0) / 1000, 1)}

    async def webcam(self) -> Optional[Dict]:
        """{'snapshot': url, 'stream': url} for the first enabled webcam (cached), or None.
        PRINTER_WEBCAM_URL overrides discovery (a ?action=stream URL is turned into its snapshot twin)."""
        if BotConfig.PRINTER_WEBCAM_URL:
            url = BotConfig.PRINTER_WEBCAM_URL
            return {"snapshot": url.replace("action=stream", "action=snapshot"),
                    "stream": url.replace("action=snapshot", "action=stream")}
        fetched_at, cached = self._webcam
        if cached and time.monotonic() - fetched_at < WEBCAM_CACHE_SECONDS:
            return cached
        result = await self._get_json("/server/webcams/list")
        cams = [c for c in (result or {}).get("webcams", []) if c.get("enabled", True)]
        cam = None
        if cams:
            c = cams[0]
            cam = {"snapshot": urljoin(self.base_url + "/", c.get("snapshot_url") or "/webcam/?action=snapshot"),
                   "stream": urljoin(self.base_url + "/", c.get("stream_url") or "/webcam/?action=stream")}
        elif self.configured:
            cam = {"snapshot": f"{self.base_url}/webcam/?action=snapshot", "stream": f"{self.base_url}/webcam/?action=stream"}
        self._webcam = (time.monotonic(), cam)
        return cam

    async def snapshot(self) -> Optional[bytes]:
        """One JPEG from the webcam, or None."""
        cam = await self.webcam()
        if not cam:
            return None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(cam["snapshot"], timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status != 200 or not resp.content_type.startswith("image/"):
                        return None
                    return await resp.read()
        except Exception as e:
            logger.debug(f"Printer snapshot failed: {e!r}")
            return None

    async def clip(self, seconds: int = CLIP_SECONDS) -> Optional[bytes]:
        """A short MP4 recorded from the MJPEG stream with ffmpeg (Discord can't play the stream itself)."""
        cam = await self.webcam()
        if not cam:
            return None
        fd, path = tempfile.mkstemp(suffix=".mp4", prefix="printer_clip_")
        os.close(fd)
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-loglevel", "error", "-use_wallclock_as_timestamps", "1", "-i", cam["stream"], "-t", str(seconds),
                "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-preset", "veryfast",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", path,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
            try:
                _, err = await asyncio.wait_for(proc.communicate(), timeout=seconds + 20)
            except asyncio.TimeoutError:
                proc.kill()
                return None
            if proc.returncode != 0:
                logger.warning(f"Printer clip failed: {err.decode(errors='replace')[:200]}")
                return None
            with open(path, "rb") as f:
                data = f.read()
            return data or None
        finally:
            os.remove(path)
