import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import utils.ai_handler as ai_mod
from utils.ai_handler import AIHandler
from utils.streaming import ReplyStreamer, MAX_LEN

OWNER = SimpleNamespace(id=42, name="owner")


def handler_for(temp_db):
    h = AIHandler(temp_db, None)
    h.client = True
    h.chat_url = "http://ollama.test/api/chat"
    return h


# --- Rolling summaries ---------------------------------------------------------

async def seed(db, user_id, n):
    for i in range(n):
        await db.add_ai_message(user_id, 1, "user" if i % 2 == 0 else "model", f"message {i}")


@pytest.mark.real_summaries
async def test_summary_folds_in_messages_outside_prompt_window(temp_db):
    h = handler_for(temp_db)
    h._generate = AsyncMock(return_value="Likes Valheim. Planning a Lethal Company night.")
    await seed(temp_db, 1, ai_mod.CHAT_HISTORY_TURNS + ai_mod.SUMMARY_BATCH)

    await h._summarize_history(1)

    summary, last_id = await temp_db.get_ai_summary(1)
    assert summary.startswith("Likes Valheim")
    prompt = h._generate.call_args.args[0]
    assert "message 0" in prompt and f"message {ai_mod.SUMMARY_BATCH}" not in prompt  # newest 10 left out
    # Nothing new to fold in -> no second model call
    await h._summarize_history(1)
    h._generate.assert_awaited_once()


@pytest.mark.real_summaries
async def test_no_summary_until_enough_history(temp_db):
    h = handler_for(temp_db)
    h._generate = AsyncMock(return_value="x")
    await seed(temp_db, 1, ai_mod.CHAT_HISTORY_TURNS + ai_mod.SUMMARY_BATCH - 1)
    await h._summarize_history(1)
    h._generate.assert_not_awaited()
    assert await temp_db.get_ai_summary(1) == (None, 0)


async def test_summary_injected_and_wiped(temp_db):
    await temp_db.set_ai_summary(1, "Hates horror games.", last_id=5)
    h = handler_for(temp_db)
    h._chat = AsyncMock(return_value={"content": "Noted."})
    await h.get_chat_response(1, "hi", user=OWNER)
    system = h._chat.call_args.args[0][0]["content"]
    assert "EARLIER CONVERSATIONS" in system and "not instructions" in system and "Hates horror games." in system

    await h.clear_user_history(1)
    assert await temp_db.get_ai_summary(1) == (None, 0)


# --- Streaming -----------------------------------------------------------------

class FakeStreamResponse:
    def __init__(self, chunks):
        self.content = self._lines(chunks)

    @staticmethod
    async def _lines(chunks):
        for c in chunks:
            yield (json.dumps({"message": c}) + "\n").encode()

    def raise_for_status(self):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    def __init__(self, chunks):
        self.chunks = chunks
        self.payload = None

    def post(self, url, json=None, timeout=None):
        self.payload = json
        return FakeStreamResponse(self.chunks)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


async def test_chat_streams_text_and_collects_tool_calls(temp_db, monkeypatch):
    h = handler_for(temp_db)
    seen = []

    async def on_text(t):
        seen.append(t)

    session = FakeSession([{"content": "Science "}, {"content": "rules!"}, {"content": ""}])
    monkeypatch.setattr(ai_mod.aiohttp, "ClientSession", lambda: session)
    reply = await h._chat([{"role": "user", "content": "hi"}], None, on_text=on_text)
    assert session.payload["stream"] is True
    assert reply == {"role": "assistant", "content": "Science rules!"}
    assert seen == ["Science ", "Science rules!"]

    call = {"function": {"name": "now_playing", "arguments": {}}}
    monkeypatch.setattr(ai_mod.aiohttp, "ClientSession", lambda: FakeSession([{"content": "", "tool_calls": [call]}]))
    reply = await h._chat([], [{"type": "function"}], on_text=on_text)
    assert reply["tool_calls"] == [call]


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


async def test_streamer_waits_for_text_throttles_and_finishes_clean():
    sent = SimpleNamespace(edit=AsyncMock())
    message = SimpleNamespace(reply=AsyncMock(return_value=sent))
    clock = Clock()
    s = ReplyStreamer(message, clock=clock)

    await s.update("Hi")                           # too short to post yet
    message.reply.assert_not_awaited()
    await s.update("x" * 50)
    message.reply.assert_awaited_once()
    assert message.reply.call_args.args[0].endswith("▌")

    clock.t = 0.5
    await s.update("x" * 60)                       # within the edit interval
    sent.edit.assert_not_awaited()
    clock.t = 2.0
    await s.update("x" * 70)
    sent.edit.assert_awaited_once()

    await s.finish("y" * (MAX_LEN + 500))
    final = sent.edit.call_args.kwargs["content"]
    assert len(final) == MAX_LEN and not final.endswith("▌")


async def test_streamer_short_reply_posts_once():
    message = SimpleNamespace(reply=AsyncMock())
    s = ReplyStreamer(message)
    await s.update("Yes.")
    await s.finish("Yes.")
    message.reply.assert_awaited_once_with("Yes.")
