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
    state = SimpleNamespace(online=True, prompts=[], events=[], result=b"PNG")

    def fake_generate(prompt, width=1024, height=1024, model="z-image"):
        state.prompts.append(prompt)
        state.calls = getattr(state, "calls", []) + [(width, height, model)]
        state.events.append("generate")
        return state.result
    monkeypatch.setattr(image_mod, "free_comfy_memory", lambda: state.events.append("free"))
    monkeypatch.setattr(image_mod, "is_comfy_online", lambda: state.online)
    monkeypatch.setattr(image_mod, "generate_image", fake_generate)
    return state


def fake_ai(result="enhanced prompt", available=True):
    return SimpleNamespace(is_available=lambda: available,
                           enhance_image_prompt=AsyncMock(return_value=result), unload_models=AsyncMock())


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


async def test_gpu_is_handed_to_comfy_and_back(comfy):
    ai = fake_ai()
    ai.unload_models = AsyncMock(side_effect=lambda: comfy.events.append("unload ollama"))
    svc = ImageService(ai)
    assert (await svc.generate(1, "a robot")).status == "ok"
    assert comfy.events == ["unload ollama", "generate", "free"]

    comfy.events.clear()
    comfy.result = None                                  # a failed job still gives the GPU back
    assert (await svc.generate(2, "a robot")).status == "failed"
    assert comfy.events == ["unload ollama", "generate", "free"]


async def test_shape_model_and_template_mode_reach_comfy(comfy):
    ai = fake_ai()
    svc = ImageService(ai)
    await svc.generate(1, "a lighthouse", shape="tall", model="flux2-klein")
    assert comfy.calls[-1] == (832, 1216, "flux2-klein")
    assert ai.enhance_image_prompt.call_args.kwargs["enhance"] is True
    await svc.generate(2, "poster template", enhance=False, shape="nonsense", model="nope")
    assert comfy.calls[-1] == (1024, 1024, "z-image")                  # unknown values fall back to defaults
    assert ai.enhance_image_prompt.call_args.kwargs["enhance"] is False


def test_workflows_get_prompt_seed_and_size():
    from utils.image_gen import MODELS, build_workflow
    for model, spec in MODELS.items():
        wf = build_workflow("a red fox", 832, 1216, model)
        node, field = spec["prompt"]
        assert wf[node]["inputs"][field] == "a red fox"
        assert all(wf[n]["inputs"]["width"] == 832 and wf[n]["inputs"]["height"] == 1216 for n in spec["size"])
        node, field = spec["seed"]
        assert wf[node]["inputs"][field] < 10 ** 17                       # stays clear of the privacy guard


async def test_template_mode_only_screens_the_prompt():
    handler = AIHandler(None, SimpleNamespace(db=None, dialogue=None, get_cog=lambda n: None))
    handler.client = True
    handler._generate = AsyncMock(return_value="SAFE")
    assert await handler.enhance_image_prompt("poster about cake", enhance=False) == "poster about cake"
    handler._generate = AsyncMock(return_value="SAFE_REFUSAL")
    assert await handler.enhance_image_prompt("bad", enhance=False) == "SAFE_REFUSAL"
    handler._generate = AsyncMock(return_value="")
    assert await handler.enhance_image_prompt("x", enhance=False, fail_closed=True) == "SAFE_REFUSAL"


async def test_prompts_about_minors_are_refused_before_the_model():
    handler = AIHandler(None, SimpleNamespace(db=None, dialogue=None, get_cog=lambda n: None))
    handler.client = True
    handler._generate = AsyncMock(return_value="A lovely enhanced prompt")
    for prompt in ("teenage girls in bikinis", "a kid at the beach", "a 12 year old", "schoolgirl outfit", "toddlers"):
        assert await handler.enhance_image_prompt(prompt) == "SAFE_REFUSAL"
        assert await handler.enhance_image_prompt(prompt, enhance=False) == "SAFE_REFUSAL"
    handler._generate.assert_not_awaited()
    for prompt in ("a kidney bean salad", "a 30 year old woman at the beach", "goat kidneys"):
        assert await handler.enhance_image_prompt(prompt) == "A lovely enhanced prompt"   # no false hits
