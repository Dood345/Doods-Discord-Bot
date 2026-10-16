import io
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from PIL import Image

from commands.image_cog import ImageCog
from services.image_service import ImageResult
from utils.image_compose import clearance_for, id_badge, poster_caption, subject_number


def png(w=512, h=640, color=(200, 50, 50)):
    out = io.BytesIO()
    Image.new("RGB", (w, h), color).save(out, format="PNG")
    return out.getvalue()


def test_badge_and_poster_render():
    badge = Image.open(io.BytesIO(id_badge(png(), "A Very Long Display Name Indeed", "04217", "EXPENDABLE")))
    assert badge.size == (900, 560)
    poster = Image.open(io.BytesIO(poster_caption(png(768, 1024), "Science: we do what we must because we can")))
    assert poster.size == (768, 1024)
    assert poster.getpixel((384, 1010)) != (200, 50, 50)   # banner drawn at the bottom


def test_subject_number_is_stable_and_not_the_id():
    uid = 987654321
    assert subject_number(uid) == subject_number(uid) and len(subject_number(uid)) == 5
    assert str(uid) not in subject_number(uid) and clearance_for(uid) == clearance_for(uid)


def cog(result):
    images = MagicMock()
    images.check_available.return_value = None
    images.generate = AsyncMock(return_value=result)
    ai = SimpleNamespace(complete=AsyncMock(return_value='"Testing Is Mandatory"\nextra'), _get_persona_system_prompt=lambda: "Cave")
    bot = SimpleNamespace(image_service=images, ai_handler=ai, dialogue=SimpleNamespace(get=lambda *a, **k: a[1]))
    return ImageCog(bot), images


def interaction():
    status = SimpleNamespace(edit=AsyncMock(), delete=AsyncMock())
    return SimpleNamespace(user=SimpleNamespace(id=7, display_name="Rando"),
                           response=SimpleNamespace(defer=AsyncMock()),
                           followup=SimpleNamespace(send=AsyncMock(return_value=status)),
                           channel=SimpleNamespace(send=AsyncMock())), status


async def test_portrait_prompt_has_no_personal_info():
    c, images = cog(ImageResult("ok", image=png()))
    i, _ = interaction()
    target = SimpleNamespace(id=42, display_name="GLaDOS")
    await ImageCog.portrait.callback(c, i, target)
    prompt = images.generate.call_args.args[1]
    assert "GLaDOS" not in prompt and "42" not in prompt
    assert i.channel.send.call_args.kwargs["file"].filename == "badge.png"


async def test_poster_slogan_and_refusal():
    c, images = cog(ImageResult("ok", image=png()))
    i, _ = interaction()
    await ImageCog.poster.callback(c, i, "mandatory fun")
    assert "Testing Is Mandatory" in i.channel.send.call_args.args[0]

    c, images = cog(ImageResult("refused"))
    i, status = interaction()
    await ImageCog.poster.callback(c, i, "something awful")
    status.edit.assert_awaited_once_with(content="image_denied")
    i.channel.send.assert_not_awaited()
