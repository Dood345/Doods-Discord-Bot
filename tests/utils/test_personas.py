from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from commands.character_commands import CharacterCommands
from config import BotConfig
from utils.personas import load_personas


def test_persona_file_is_complete():
    personas = load_personas()
    assert len(personas) >= 9 and BotConfig.PERSONAS.keys() == personas.keys()
    for key, p in personas.items():
        assert p.name and p.emoji and p.prompt and p.description
        assert "{target}" in p.roast and "{target}" in p.compliment, key
        assert p.roast.format(target="Wheatley") and p.compliment.format(target="Wheatley")
    assert not personas["alexjones"].in_rotation
    assert BotConfig.CHARACTER_INFO["hank"]["name"] == personas["hank"].label


def test_missing_persona_file_is_empty_not_fatal(tmp_path):
    assert load_personas(str(tmp_path / "nope.json")) == {}


def cog():
    ai = MagicMock()
    ai.is_available.return_value = True
    ai.get_character_response = AsyncMock(return_value="I tell you what.")
    bot = SimpleNamespace(config=BotConfig, ai_handler=ai, dialogue=MagicMock())
    return CharacterCommands(bot), ai


def interaction():
    return SimpleNamespace(response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
                           followup=SimpleNamespace(send=AsyncMock()))


async def test_ask_by_key_or_name_and_unknown():
    c, ai = cog()
    i = interaction()
    await CharacterCommands.ask_command.callback(c, i, "Hank Hill", "propane or charcoal?")
    ai.get_character_response.assert_awaited_once_with("hank", "propane or charcoal?")
    assert i.followup.send.call_args.args[0] == f"{BotConfig.PERSONAS['hank'].label}: I tell you what."

    i = interaction()
    await CharacterCommands.ask_command.callback(c, i, "wheatley", "hi")
    assert i.response.send_message.call_args.kwargs["ephemeral"] is True


async def test_autocomplete_matches_names():
    c, _ = cog()
    choices = await c.character_autocomplete(None, "grib")
    assert [ch.value for ch in choices] == ["dale"]
    assert len(await c.character_autocomplete(None, "")) == len(BotConfig.PERSONAS)


async def test_roast_prompt_comes_from_persona_file(temp_db, mock_config, mocker):
    from utils.ai_handler import AIHandler
    h = AIHandler(temp_db, None)
    h.config, h.client = mock_config, True
    gen = mocker.patch.object(h, "_generate", AsyncMock(return_value="ok"))
    await h.get_compliment_response("dante", "Wheatley")
    prompt = gen.call_args.args[0]
    assert BotConfig.PERSONAS["dante"].prompt in prompt and "'Wheatley'" in prompt and "redemption" in prompt
