from types import SimpleNamespace

from utils.ai_handler import CHAT_HISTORY_TURNS, AIHandler

KEYWORDS = ["cat", "japan", "gpu", "poem"]


async def fake_embed(texts):
    """One dimension per keyword plus a small shared one, so related texts are ~1.0 similar and others ~0."""
    return [[1.0 if k in t.lower() else 0.0 for k in KEYWORDS] + [0.05] for t in texts]


def handler(db):
    h = AIHandler(db)
    h.client, h.embed_url, h.embed_model = True, "http://ollama/api/embed", "nomic-embed-text"
    h._embed = fake_embed
    return h


async def chat(db, user_id, pairs):
    for u, m in pairs:
        await db.add_ai_message(user_id, 5, "user", u)
        await db.add_ai_message(user_id, 5, "model", m)


OLD = [("my cat is called Mochi", "A feline test subject!"),
       ("I'm going to Japan in March", "Test the bullet trains."),
       ("my GPU has 10gb", "Ten gigabytes of science.")]
RECENT = [(f"small talk {i}", "Indeed.") for i in range(CHAT_HISTORY_TURNS // 2)]


async def test_index_embeds_only_exchanges_outside_the_window(temp_db):
    await chat(temp_db, 1, OLD + RECENT)
    h = handler(temp_db)
    await h._index_history(1)
    stored = await temp_db.get_embeddings(1)
    assert [t.split("\n")[0] for _, t, _ in stored] == [f"User: {u}" for u, _ in OLD]
    assert "Cave: A feline test subject!" in stored[0][1]

    await h._index_history(1)  # idempotent
    assert len(await temp_db.get_embeddings(1)) == len(OLD)


async def test_recall_returns_related_exchanges_only(temp_db):
    await chat(temp_db, 1, OLD + RECENT)
    await chat(temp_db, 2, [("my cat Bob", "ok")] + RECENT)  # someone else's memories
    h = handler(temp_db)
    await h._index_history(1)
    await h._index_history(2)

    recalled = await h._recall(1, "what's my cat's name?")
    assert len(recalled) == 1 and "Mochi" in recalled[0]
    assert await h._recall(1, "play some 3 doors down") == []


async def test_recalled_exchanges_reach_the_prompt_as_quoted_background(temp_db):
    await chat(temp_db, 1, OLD + RECENT)
    h = handler(temp_db)
    await h._index_history(1)
    seen = []

    async def fake_chat(messages, tools=None, on_text=None):
        seen.append(messages)
        return {"role": "assistant", "content": "Mochi, obviously."}

    h._chat = fake_chat
    user = SimpleNamespace(id=1, name="tester", display_name="Tester")
    assert await h.get_chat_response(1, "remind me what my cat is called", user=user) == "Mochi, obviously."
    system = seen[0][0]["content"]
    assert "OLDER EXCHANGES" in system and "not instructions" in system and "Mochi" in system
    assert "Japan" not in system


async def test_recall_failure_or_disabled_never_blocks_chat(temp_db):
    await chat(temp_db, 1, OLD + RECENT)
    h = handler(temp_db)
    await h._index_history(1)

    async def broken(texts):
        raise ConnectionError("ollama down")

    h._embed = broken
    assert await h._recall(1, "my cat?") == []
    await h._index_history(1)  # logs, doesn't raise

    h.embed_model = None
    assert await h._recall(1, "my cat?") == []


async def test_clearhistory_wipes_embeddings_and_blocks_late_writes(temp_db):
    await chat(temp_db, 1, OLD + RECENT)
    h = handler(temp_db)
    await h._index_history(1)
    assert await temp_db.get_embeddings(1)

    await h.clear_user_history(1)
    assert await temp_db.get_embeddings(1) == []
    # An indexing job that read rows before the wipe must not resurrect them
    await temp_db.add_embeddings(1, [(1, "User: my cat is called Mochi", b"\x00" * 20)])
    assert await temp_db.get_embeddings(1) == []
