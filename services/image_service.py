import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional

from utils.image_gen import generate_image, is_comfy_online

logger = logging.getLogger(__name__)

USER_COOLDOWN = 60  # seconds between images per user


@dataclass
class ImageResult:
    status: str                      # ok | busy | cooldown | offline | refused | failed
    image: Optional[bytes] = None
    enhanced_prompt: Optional[str] = None


class ImageService:
    """ComfyUI image generation shared by /imagine and Cave's generate_image tool.

    One image at a time: ComfyUI and Ollama share the GPU, so parallel jobs just thrash it.
    """

    def __init__(self, ai_handler):
        self.ai = ai_handler
        self._lock = asyncio.Lock()
        self._last_by_user = {}
        self._tasks = set()  # strong refs so background jobs aren't garbage-collected

    def check_available(self, user_id: int) -> Optional[str]:
        """'busy' / 'cooldown' if a new job can't start right now, else None."""
        if self._lock.locked():
            return "busy"
        if time.monotonic() - self._last_by_user.get(user_id, -USER_COOLDOWN) < USER_COOLDOWN:
            return "cooldown"
        return None

    async def generate(self, user_id: int, prompt: str, fail_closed: bool = False) -> ImageResult:
        blocked = self.check_available(user_id)
        if blocked:
            return ImageResult(blocked)
        async with self._lock:
            self._last_by_user[user_id] = time.monotonic()
            if not await asyncio.to_thread(is_comfy_online):
                return ImageResult("offline")

            enhanced = prompt
            if self.ai is not None and (self.ai.is_available() or fail_closed):
                enhanced = await self.ai.enhance_image_prompt(prompt, fail_closed=fail_closed)
            if enhanced == "SAFE_REFUSAL":
                logger.info(f"Image prompt refused for user {user_id}")
                return ImageResult("refused")

            image = await asyncio.to_thread(generate_image, enhanced)
            if not image:
                return ImageResult("failed", enhanced_prompt=enhanced)
            return ImageResult("ok", image=image, enhanced_prompt=enhanced)

    def run_in_background(self, coro):
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task
