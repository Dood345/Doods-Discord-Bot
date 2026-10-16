"""DMs with Cave stay private: in a server they're as if they never happened, unless the user
explicitly asks about their DMs."""

import sqlite3
from array import array
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from utils.agent import ToolContext
from utils.agent_tools import build_cave_tools
from utils.ai_handler import CHAT_HISTORY_TURNS, DM_REFERENCE, SUMMARY_BATCH, AIHandler
from utils.database import DatabaseHandler

USER = SimpleNamespace(id=1, name="tester", display_name="Tester")
GUILD = SimpleNamespace(id=5)


def handler(db):
    h = AIHandler(db)
    h.client = True
    h._chat = AsyncMock(return_value={"content": "Noted."})
    return h


def system_prompt(h):
    return h._chat.call_args.args[0][0]["content"]


def prompt_text(h):
    return "\n".join(m["content"] for m in h._chat.call_args.args[0])


async def seed(db):
    await db.add_ai_message(1, None, "user", "my secret crush is Wheatley")    # DM
    await db.add_ai_message(1, None, "model", "Your secret is safe.")
    await db.add_ai_message(1, 5, "user", "I like Valheim")                    # server
    await db.add_ai_message(1, 5, "model", "Excellent taste.")
    await db.add_user_fact(1, "has a crush on Wheatley", is_dm=True)
    await db.add_user_fact(1, "likes Valheim")
    await db.set_ai_summary(1, "Talks about their crush on Wheatley.", 2, dm=True)
    await db.set_ai_summary(1, "Plays Valheim.", 4)


def test_explicit_dm_references():
    for text in ("what did I tell you in DMs?", "remember our dm", "from our private chat", "I told you privately"):
        assert DM_REFERENCE.search(text), text
    for text in ("what did I tell you?", "admin stuff", "game night at 9 pm", "random"):
        assert not DM_REFERENCE.search(text), text


async def test_server_chat_never_sees_dms(temp_db):
    await seed(temp_db)
    h = handler(temp_db)
    await h.get_chat_response(1, "what do you know about me?", guild_id=5, user=USER, guild=GUILD)
    text = prompt_text(h)
    assert "Valheim" in text
    assert "Wheatley" not in text and "secret" not in text


async def test_server_chat_sees_dms_when_asked(temp_db):
    await seed(temp_db)
    h = handler(temp_db)
    await h.get_chat_response(1, "remember what I told you in DMs?", guild_id=5, user=USER, guild=GUILD)
    text = prompt_text(h)
    assert "my secret crush is Wheatley" in text and "has a crush on Wheatley" in text
    assert "PRIVATE DM CONVERSATIONS" in system_prompt(h) and "explicitly asked" in system_prompt(h)


async def test_dms_see_everything(temp_db):
    await seed(temp_db)
    h = handler(temp_db)
    await h.get_chat_response(1, "hey", user=USER)
    text = prompt_text(h)
    assert "Wheatley" in text and "Valheim" in text and "explicitly asked" not in text


async def test_remember_fact_in_dm_is_private(temp_db):
    tools = build_cave_tools()
    await tools.dispatch("remember_fact", {"fact": "is afraid of turrets"},
                         ToolContext(bot=SimpleNamespace(db=temp_db), user=USER, guild=None))
    await tools.dispatch("remember_fact", {"fact": "mains Dwarf"},
                         ToolContext(bot=SimpleNamespace(db=temp_db), user=USER, guild=GUILD))
    assert await temp_db.get_user_facts(1, include_dms=False) == ["mains Dwarf"]
    assert await temp_db.get_user_facts(1) == ["is afraid of turrets", "mains Dwarf"]


@pytest.mark.real_summaries
async def test_summaries_and_recall_are_split_by_scope(temp_db):
    for i in range(CHAT_HISTORY_TURNS + SUMMARY_BATCH):
        await temp_db.add_ai_message(1, None, "user" if i % 2 == 0 else "model", f"dm {i}")
    for i in range(CHAT_HISTORY_TURNS + SUMMARY_BATCH):
        await temp_db.add_ai_message(1, 5, "user" if i % 2 == 0 else "model", f"server {i}")
    h = handler(temp_db)
    h._generate = AsyncMock(side_effect=lambda prompt: "DM SUMMARY" if "dm 0" in prompt else "SERVER SUMMARY")
    await h._summarize_history(1)
    assert (await temp_db.get_ai_summary(1))[0] == "SERVER SUMMARY"
    assert (await temp_db.get_ai_summary(1, dm=True))[0] == "DM SUMMARY"
    for call in h._generate.call_args_list:  # no batch mixes the two
        prompt = call.args[0]
        assert not ("dm 0" in prompt and "server 0" in prompt)

    # Embeddings remember where each exchange happened
    h.embed_model, h.embed_url = "nomic", "http://x"
    h._embed = AsyncMock(side_effect=lambda texts: [[1.0, 0.0] for _ in texts])
    await h._index_history(1)
    assert {t.split("\n")[0][6:9] for _, t, _ in await temp_db.get_embeddings(1, include_dms=False)} == {"ser"}
    assert len(await temp_db.get_embeddings(1)) > len(await temp_db.get_embeddings(1, include_dms=False))


async def test_old_databases_are_upgraded(tmp_path):
    path = str(tmp_path / "old.db")
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE ai_history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, guild_id INTEGER,
                role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE ai_embeddings (history_id INTEGER PRIMARY KEY, user_id INTEGER, text TEXT, vector BLOB);
            CREATE TABLE user_facts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, fact TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE ai_summaries (user_id INTEGER PRIMARY KEY, summary TEXT, last_id INTEGER,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP);
            INSERT INTO ai_history (id, user_id, guild_id, role, content) VALUES (1, 1, NULL, 'user', 'dm'), (3, 1, 5, 'user', 'srv');
            INSERT INTO user_facts (user_id, fact) VALUES (1, 'old note');
            INSERT INTO ai_summaries VALUES (1, 'mixed summary', 3, CURRENT_TIMESTAMP);
        """)
        vec = array("f", [1.0]).tobytes()
        conn.executemany("INSERT INTO ai_embeddings VALUES (?, 1, ?, ?)", [(1, "User: dm", vec), (3, "User: srv", vec)])

    db = DatabaseHandler(db_path=path)
    await db.setup_tables()
    await db.setup_tables()
    assert [t for _, t, _ in await db.get_embeddings(1, include_dms=False)] == ["User: srv"]
    assert await db.get_user_facts(1, include_dms=False) == ["old note"]   # origin unknown: stays visible
    assert await db.get_ai_summary(1) == (None, 0)                         # mixed summary rebuilt per scope
