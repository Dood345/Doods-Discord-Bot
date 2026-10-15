import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import services.image_service as image_mod
from services.image_service import ImageService
from utils.agent import ToolContext
from utils.agent_tools import build_cave_tools
from utils.ai_handler import AIHandler


@pytest.fixture
def comfy(monkeypatch):
    """Fake ComfyUI: online, returns PNG bytes."""
    state = SimpleNamespace(online=True, prompts=[])

    def fake_generate(prompt):
        state.prompts.append(prompt)
        return b"PNG"
    monkeypatch.setattr(image_mod, "is_comfy_online", lambda: state.online)
    monkeypatch.setattr(image_mod, "generate_image", fake_generate)
    return state


def fake_ai(result="enhanced prompt", available=True):
    return SimpleNamespace(is_available=lambda: available,
                           enhance_image_prompt=AsyncMock(return_value=result))


async def test_generates_with_enhanced_prompt_then_cools_down(comfy):
    svc = ImageService(fake_ai())
    result = await svc.generate(1, "a cat")
    assert result.status == "ok" and result.image == b"PNG"
    assert comfy.prompts == ["enhanced prompt"]
    assert (await svc.generate(1, "another cat")).status == "cooldown"
    assert (await svc.generate(2, "a dog")).status == "ok"


async def test_one_job_at_a_time(comfy):
    svc = ImageService(fake_ai())
    await svc._lock.acquire()
    try:
        assert (await svc.generate(1, "a cat")).status == "busy"
    finally:
        svc._lock.release()


async def test_refusal_and_offline(comfy):
    assert (await ImageService(fake_ai("SAFE_REFUSAL")).generate(1, "bad")).status == "refused"
    assert comfy.prompts == []
    comfy.online = False
    assert (await ImageService(fake_ai()).generate(1, "a cat")).status == "offline"


async def test_enhancer_fails_closed_for_chat(temp_db):
    handler = AIHandler(temp_db, None)
    # AI disabled: /imagine passes the prompt through, chat-initiated requests are refused
    assert await handler.enhance_image_prompt("a cat") == "a cat"
    assert await handler.enhance_image_prompt("a cat", fail_closed=True) == "SAFE_REFUSAL"

    handler.client = True
    handler._generate = AsyncMock(side_effect=RuntimeError("ollama down"))
    assert await handler.enhance_image_prompt("a cat", fail_closed=True) == "SAFE_REFUSAL"
    handler._generate = AsyncMock(return_value="I can't do that. SAFE_REFUSAL")
    assert await handler.enhance_image_prompt("a cat") == "SAFE_REFUSAL"


async def test_tool_starts_background_job_and_posts_image(comfy):
    svc = ImageService(fake_ai())
    channel = MagicMock()
    channel.send = AsyncMock()
    bot = SimpleNamespace(image_service=svc, dialogue=MagicMock(get=lambda *a, **k: "msg"))
    ctx = ToolContext(bot=bot, user=SimpleNamespace(id=5, name="x"), guild=None, channel=channel)

    result = await build_cave_tools().dispatch("generate_image", {"prompt": "a robot"}, ctx)
    assert result.startswith("STARTED")
    await asyncio.gather(*svc._tasks)
    assert channel.send.call_args.kwargs["file"].filename == "generated.png"

    again = await build_cave_tools().dispatch("generate_image", {"prompt": "another"}, ctx)
    assert "less than a minute" in again
