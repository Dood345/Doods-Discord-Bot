"""Pillow overlays for generated images: the model draws the picture, we draw the text (reliably)."""

import hashlib
import io
import textwrap

from PIL import Image, ImageDraw, ImageFont

ORANGE = (255, 140, 0)
BLUE = (0, 140, 255)
INK = (25, 25, 30)
PAPER = (240, 240, 235)
CLEARANCES = ["MINIMAL", "PROVISIONAL", "EXPENDABLE", "CAKE-ELIGIBLE", "DO NOT RESUSCITATE", "REASONABLY TRUSTED"]


def _font(size: int):
    return ImageFont.load_default(size=size)


def subject_number(user_id: int) -> str:
    """Stable fake test-subject number (never the real Discord ID)."""
    return f"{int(hashlib.sha256(str(user_id).encode()).hexdigest(), 16) % 100000:05d}"


def clearance_for(user_id: int) -> str:
    return CLEARANCES[int(hashlib.sha256(f"c{user_id}".encode()).hexdigest(), 16) % len(CLEARANCES)]


def _png(img: Image.Image) -> bytes:
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def id_badge(photo: bytes, name: str, number: str, clearance: str) -> bytes:
    """An Aperture Science test-subject ID card around a generated portrait."""
    w, h = 900, 560
    card = Image.new("RGB", (w, h), PAPER)
    draw = ImageDraw.Draw(card)
    draw.rectangle([0, 0, w, 90], fill=INK)
    draw.text((30, 22), "APERTURE SCIENCE", font=_font(44), fill=PAPER)
    draw.text((w - 300, 34), "ENRICHMENT CENTER", font=_font(26), fill=ORANGE)

    pic = Image.open(io.BytesIO(photo)).convert("RGB")
    side = min(pic.size)
    pic = pic.crop(((pic.width - side) // 2, (pic.height - side) // 2,
                    (pic.width + side) // 2, (pic.height + side) // 2)).resize((380, 380))
    card.paste(pic, (30, 130))
    draw.rectangle([28, 128, 412, 512], outline=INK, width=3)

    x = 450
    draw.text((x, 135), "TEST SUBJECT", font=_font(28), fill=BLUE)
    name_lines = textwrap.wrap(name, width=18)[:2] or ["UNKNOWN"]
    y = 175
    for line in name_lines:
        draw.text((x, y), line.upper(), font=_font(46), fill=INK)
        y += 56
    draw.text((x, y + 20), f"SUBJECT #{number}", font=_font(32), fill=INK)
    draw.text((x, y + 70), "CLEARANCE", font=_font(22), fill=BLUE)
    draw.text((x, y + 98), clearance, font=_font(30), fill=ORANGE)
    draw.rectangle([0, h - 40, w, h], fill=ORANGE)
    draw.text((30, h - 34), "PROPERTY OF APERTURE SCIENCE. IF FOUND, DO NOT RETURN.", font=_font(22), fill=INK)
    return _png(card)


def poster_caption(image: bytes, slogan: str) -> bytes:
    """Bold slogan banner across the bottom of a generated poster."""
    img = Image.open(io.BytesIO(image)).convert("RGB")
    draw = ImageDraw.Draw(img)
    size = max(28, img.width // 16)
    lines = textwrap.wrap(slogan.upper(), width=max(10, img.width // (size // 2 + 4)))[:2]
    band = (size + 14) * len(lines) + 30
    draw.rectangle([0, img.height - band, img.width, img.height], fill=INK)
    y = img.height - band + 15
    for line in lines:
        tw = draw.textlength(line, font=_font(size))
        draw.text(((img.width - tw) / 2, y), line, font=_font(size), fill=ORANGE)
        y += size + 14
    return _png(img)
