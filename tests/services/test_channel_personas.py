"""Channel personas: who answers where, and memories that never cross between characters."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

from config import BotConfig
from services.persona_service import PersonaService
from utils.ai_handler import AIHandler


def handler_for(db):
    h = AIHandler(db, SimpleNamespace(db=db, dialogue=None, get_cog=lambda n: None))
    h.client = True
    h._chat = AsyncMock(return_value={"content": "I tell you what."})
    return h


def prompt_text(h) -> str:
    return "\n".join(m["content"] for m in h._chat.call_args.args[0])


async def seed(db):
    await db.add_ai_message(1, 5, "user", "CAVE-ONLY: my cat is Gizmo")
    await db.add_ai_message(1, 5, "model", "CAVE-ONLY: noted, volunteer")
    await db.add_user_fact(1, "CAVE-NOTE: mains Dwarf")
    await db.set_ai_summary(1, "CAVE-SUMMARY: likes Valheim", 2)
    await db.add_ai_message(1, 5, "user", "HANK-ONLY: my lawn is brown", persona="hank")
    await db.add_ai_message(1, 5, "model", "HANK-ONLY: dang it", persona="hank")
    await db.add_user_fact(1, "HANK-NOTE: grills with charcoal", persona="hank")
    await db.set_ai_summary(1, "HANK-SUMMARY: needs propane", 4, persona="hank")


async def test_persona_and_cave_never_see_each_others_memory(temp_db):
    await seed(temp_db)
    h = handler_for(temp_db)
    guild = SimpleNamespace(id=5)

    await h.get_chat_response(1, "what do you know about me?", 5, user=SimpleNamespace(id=1, name="x"), guild=guild,
                              persona="hank")
    text = prompt_text(h)
    assert "HANK-ONLY" in text and "HANK-NOTE" in text and "HANK-SUMMARY" in text
    assert "CAVE-" not in text and "Cave Johnson" not in text
    assert BotConfig.PERSONAS["hank"].prompt[:40] in text

    h._last_chat.clear()
    await h.get_chat_response(1, "what do you know about me?", 5, user=SimpleNamespace(id=1, name="x"), guild=guild)
    text = prompt_text(h)
    assert "CAVE-ONLY" in text and "CAVE-NOTE" in text and "CAVE-SUMMARY" in text
    assert "HANK-" not in text

    # The new exchange was saved to the right memory
    hank = [c for _, c, _ in await temp_db.get_ai_history_with_scope(1, persona="hank")]
    cave = [c for _, c, _ in await temp_db.get_ai_history_with_scope(1)]
    assert hank[-2:] == ["what do you know about me?", "I tell you what."] and len(cave) == 4


async def test_persona_notes_and_dms(temp_db):
    h = handler_for(temp_db)
    assert await temp_db.add_user_fact(1, "likes propane", persona="hank") == "added"
    assert await temp_db.add_user_fact(1, "likes propane") == "added"           # Cave's file is separate
    assert await temp_db.get_user_facts(1, persona="hank") == ["likes propane"]
    # Personas are server-channel only: in DMs it's always Cave
    await h.get_chat_response(1, "hi", None, user=SimpleNamespace(id=1, name="x"), guild=None, persona="hank")
    assert "Cave Johnson" in prompt_text(h)


async def test_channel_choice_persists_and_threads_follow(temp_db):
    svc = PersonaService(temp_db, BotConfig.PERSONAS)
    await svc.set(5, 100, "hank")
    reloaded = PersonaService(temp_db, BotConfig.PERSONAS)
    assert await reloaded.load() == 1                                          # survives a restart
    assert reloaded.for_channel(SimpleNamespace(id=100)) == "hank"
    assert reloaded.for_channel(SimpleNamespace(id=101, parent_id=100)) == "hank"   # a thread in that channel
    assert reloaded.for_channel(SimpleNamespace(id=200)) is None
    assert await reloaded.reset(5, 100) == "hank"
    assert reloaded.for_channel(SimpleNamespace(id=100)) is None
    assert await PersonaService(temp_db, BotConfig.PERSONAS).load() == 0


async def test_mentions_in_a_persona_channel_are_signed_and_routed(temp_db):
    from services.ai_backlog import answer_mention
    svc = PersonaService(temp_db, BotConfig.PERSONAS)
    await svc.set(5, 100, "hank")

    class Channel:
        id = 100

        def typing(self):
            class T:
                async def __aenter__(s): return None
                async def __aexit__(s, *a): return False
            return T()
    seen = {}

    async def chat(user_id, text, guild_id, **kw):
        seen.update(kw)
        return "Propane and propane accessories."
    bot = SimpleNamespace(user=SimpleNamespace(id=42), persona_service=svc,
                          ai_handler=SimpleNamespace(get_chat_response=chat, _busy_users=set(), would_cooldown=lambda u: False))
    message = SimpleNamespace(id=1, content="<@42> what do you sell?", channel=Channel(), guild=SimpleNamespace(id=5),
                              author=SimpleNamespace(id=1), reference=None, reply=AsyncMock())
    await answer_mention(bot, message)
    assert seen["persona"] == "hank"
    assert message.reply.call_args.args[0].startswith(f"**{svc.label('hank')}:** Propane")


async def test_recall_index_keeps_persona_exchanges_apart(temp_db):
    await temp_db.add_ai_message(1, 5, "user", "cave q")          # id 1
    await temp_db.add_ai_message(1, 5, "user", "hank q", persona="hank")   # id 2
    await temp_db.add_embeddings(1, [(1, "User: cave q", b"\x00"), (2, "User: hank q", b"\x00")])
    assert [t for _, t, _ in await temp_db.get_embeddings(1)] == ["User: cave q"]
    assert [t for _, t, _ in await temp_db.get_embeddings(1, persona="hank")] == ["User: hank q"]
    assert await temp_db.get_last_embedded_id(1) == 1 and await temp_db.get_last_embedded_id(1, persona="hank") == 2
