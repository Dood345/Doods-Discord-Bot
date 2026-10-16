"""Components v2 message layouts (discord.ui.LayoutView) for the bot's richer replies.

Pure builders: each takes plain data and returns a `Card`, so they're testable without Discord.
A v2 message can't also carry `content` or embeds: send it as `send(view=card)`. Unlike embeds, mentions in
a TextDisplay DO ping, so always pass `allowed_mentions=discord.AllowedMentions.none()` with a card (plus `files=` for attachments
referenced as `attachment://name`). Discord caps a message at 40 components and 4000 characters of text across
all TextDisplays; `fit_lines` keeps lists inside a budget and `Card` checks the total.
"""

import re
import time
from urllib.parse import urlparse
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

import discord
from discord import ui

APERTURE_ORANGE = 0xFFA500
MAX_TEXT = 4000
YOUTUBE_ID = re.compile(r"(?:youtu\.be/|[?&]v=|/shorts/)([A-Za-z0-9_-]{11})")
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}

Track = Tuple[str, str, str]  # (url, title, uploader)


class Card(ui.LayoutView):
    """One accent-coloured container. Static (no buttons), so it isn't kept in the view store."""

    def __init__(self, *items: ui.Item, accent: Optional[int] = APERTURE_ORANGE):
        super().__init__(timeout=None)
        self.container = ui.Container(*items, accent_colour=accent)
        self.add_item(self.container)
        if self.content_length() > MAX_TEXT:  # builders budget their text; this catches a builder bug early
            raise ValueError(f"layout text is {self.content_length()} chars (max {MAX_TEXT})")


def card_text(view: ui.LayoutView) -> str:
    """All the text of a v2 card, in order (for tests and logs)."""
    return "\n".join(item.content for item in view.walk_children() if isinstance(item, ui.TextDisplay))


def text(content: str) -> ui.TextDisplay:
    return ui.TextDisplay(content)


def separator(large: bool = False) -> ui.Separator:
    return ui.Separator(spacing=discord.SeparatorSpacing.large if large else discord.SeparatorSpacing.small)


def clip(value: str, limit: int) -> str:
    value = str(value)
    return value if len(value) <= limit else value[: limit - 1] + "…"


def fit_lines(lines: Sequence[str], budget: int, more: str = "-# …and {n} more") -> str:
    """Join as many lines as fit in `budget` characters, then a '…and N more' line for the rest."""
    out: List[str] = []
    used = 0
    for i, line in enumerate(lines):
        tail = more.format(n=len(lines) - i - 1) if i < len(lines) - 1 else ""
        if used + len(line) + 1 + (len(tail) + 1 if tail else 0) > budget:
            out.append(more.format(n=len(lines) - i))
            break
        out.append(line)
        used += len(line) + 1
    return "\n".join(out)


def fmt_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def progress_bar(fraction: float, width: int = 12) -> str:
    filled = round(max(0.0, min(1.0, fraction)) * width)
    return "▰" * filled + "▱" * (width - filled)


def youtube_thumbnail(url: str) -> Optional[str]:
    """Public thumbnail for a YouTube video link (fetched by Discord, not by the bot); None for anything else."""
    if (urlparse(url or "").hostname or "").lower() not in YOUTUBE_HOSTS:
        return None
    match = YOUTUBE_ID.search(url)
    return f"https://i.ytimg.com/vi/{match.group(1)}/hqdefault.jpg" if match else None


# --- Music -------------------------------------------------------------------------

def queue_card(current: Optional[Track], queue: Sequence[Track], *, channel_name: Optional[str] = None,
               elapsed: Optional[float] = None, paused: bool = False,
               source: Optional[Callable[[str], str]] = None, shown: int = 10) -> Card:
    """/queue: what's playing (with the YouTube thumbnail when there is one), then what's up next."""
    items: List[ui.Item] = [text("## 🎧 Audio Testing Queue")]
    if current:
        url, title, uploader = current
        details = [f"by {clip(uploader, 100)}" if uploader else None,
                   source(url) if source else None,
                   (("⏸️ paused at " if paused else "⏱️ ") + fmt_duration(elapsed)) if elapsed is not None else None]
        now = text(f"**Now playing**\n### {clip(title, 200)}\n" + " · ".join(d for d in details if d))
        thumb = youtube_thumbnail(url)
        items.append(ui.Section(now, accessory=ui.Thumbnail(thumb)) if thumb else now)
    else:
        items.append(text("**Now playing:** nothing"))
    items.append(separator())
    if queue:
        lines = [f"`{i}.` {clip(title, 120)}" + (f" · {clip(uploader, 60)}" if uploader else "")
                 for i, (_, title, uploader) in enumerate(list(queue)[:shown], 1)]
        if len(queue) > shown:
            lines.append(f"-# …and {len(queue) - shown} more")
        items.append(text(f"**Up next** ({len(queue)})\n" + fit_lines(lines, 3000)))
    else:
        items.append(text("**Up next:** nothing queued. Silence is inefficient."))
    if channel_name:
        items.append(text(f"-# 🔊 {clip(channel_name, 80)} · /skip · /play-pause · /clear"))
    return Card(*items)


# --- Science Points ----------------------------------------------------------------

def points_card(name: str, avatar_url: Optional[str], points: int, rank: int,
                achievements: Iterable, next_up=None) -> Card:
    """/points: the personnel file. `achievements`/`next_up` are services.points_service.Achievement."""
    header = text(f"## 🧪 {clip(name, 80)}\n**{points:,}** Science Points · rank **#{rank}** in this facility")
    items: List[ui.Item] = [ui.Section(header, accessory=ui.Thumbnail(avatar_url)) if avatar_url else header]
    earned = list(achievements)
    if earned:
        items.append(separator())
        lines = [f"{a.emoji} **{clip(a.name, 60)}** · {clip(a.description, 120)}" for a in earned]
        items.append(text(f"**Achievements** ({len(earned)})\n" + fit_lines(lines, 2500)))
    if next_up is not None:
        items.append(separator())
        items.append(text(f"-# Next up: {next_up.emoji} {clip(next_up.name, 60)} ({clip(next_up.description, 120)})"))
    return Card(*items)


MEDALS = ["🥇", "🥈", "🥉"]


def leaderboard_card(board: Sequence[Tuple[str, int]]) -> Card:
    """/leaderboard: medals for the podium, the rest below a divider. Names are display names, never pings."""
    podium = [f"{MEDALS[i]} **{clip(name, 60)}** · {pts:,}" for i, (name, pts) in enumerate(board[:3])]
    items: List[ui.Item] = [text("## 🏆 Science Points Leaderboard"), text("\n".join(podium))]
    rest = [f"`#{i}` {clip(name, 60)} · {pts:,}" for i, (name, pts) in enumerate(board[3:], 4)]
    if rest:
        items += [separator(), text(fit_lines(rest, 3000))]
    return Card(*items)


# --- Games -------------------------------------------------------------------------

def game_night_card(when: int, players: Optional[int], intro: str, picks: Sequence[dict],
                    event_note: Optional[str] = None) -> Card:
    """/gamenight: Cave's announcement and the candidates (the poll follows as its own message)."""
    lines = []
    for g in picks:
        rating = f" · ⭐ {g['avg_rating']:.1f}" if g.get("avg_rating") else ""
        lines.append(f"🎮 **{clip(g['title'], 100)}** · {g['min_players']}-{g['max_players']} players{rating}")
    items: List[ui.Item] = [
        text(f"## 🎮 Game Night\n<t:{when}:F> (<t:{when}:R>)" + (f" · {players} players" if players else "")),
        text(clip(intro, 600)),
        separator(),
        text("**Candidates** (vote in the poll below)\n" + "\n".join(lines)),
    ]
    if event_note:
        items.append(text(clip(event_note, 300)))
    return Card(*items)


GAME_STATUS_ORDER = ["playing", "wishlisted", "unknown", "played", "avoid"]


def _game_line(g: dict) -> str:
    rating = f"{g['avg_rating']:.1f}/10" if g.get("avg_rating") else "unrated"
    ideal = f" (ideal {g['ideal_players']})" if g.get("ideal_players") else ""
    state = f" · {g['release_state']}" if g.get("release_state") else ""
    return f"• **{clip(g['title'], 80)}** · ⭐ {rating} · {g['min_players']}-{g['max_players']} players{ideal}{state}"


def game_library_card(games: Sequence[dict], filters: Sequence[str], grouped: bool) -> Card:
    """/game list: grouped by status (or a flat list when filtered by status), inside the 4000-char limit."""
    summary = clip(" · ".join(filters), 300)  # tag: is free text
    items: List[ui.Item] = [text("## 🔬 Aperture Science Mandatory Fun Modules\n"
                                 + (f"{summary}\n" if summary else "") + f"-# {len(games)} simulations on file")]
    if grouped:
        groups = [(s, [g for g in games if (g.get("status") or "unknown").lower() == s]) for s in GAME_STATUS_ORDER]
        groups = [(s, gs) for s, gs in groups if gs]
    else:
        groups = [("", list(games))]
    budget = 3200 // max(1, len(groups)) - 40  # minus each group's heading
    for status, group in groups:
        items.append(separator())
        title = f"**📂 {status.title()}** ({len(group)})\n" if status else ""
        items.append(text(title + fit_lines([_game_line(g) for g in group], budget)))
    items.append(text("-# Testing must continue indefinitely."))
    return Card(*items)


# --- 3D printer --------------------------------------------------------------------

PRINTER_ACCENTS = {"printing": 0x2ECC71, "paused": 0xF1C40F, "error": 0xE74C3C}


def printer_card(status: dict, media_filename: Optional[str] = None, media_note: Optional[str] = None) -> Card:
    """/printer: state, progress bar, temps and the webcam still/clip (an attachment shown in a MediaGallery)."""
    state = status["state"]
    items: List[ui.Item] = [text(f"## 🖨️ 3D Printer · {state.upper()}")]
    if state in ("printing", "paused"):
        lines = [f"**{clip(status.get('filename') or '?', 120)}**",
                 f"{progress_bar((status.get('progress') or 0) / 100)} **{status.get('progress', 0)}%**"]
        timing = [f"⏱️ {status['duration']} elapsed" if status.get("duration") else None,
                  f"⌛ ~{status['remaining']} left" if status.get("remaining") else None,
                  f"🧱 layer {status['layer'][0]}/{status['layer'][1]}" if status.get("layer") else None]
        lines.append(" · ".join(t for t in timing if t))
        items.append(text("\n".join(line for line in lines if line)))
    if status.get("temps"):
        temps = " · ".join(f"🌡️ {name.title()} {cur}°C" + (f" → {tgt}°C" if tgt else "")
                           for name, (cur, tgt) in status["temps"].items())
        items.append(text(clip(temps, 500)))
    if status.get("filament_detected") is False:
        items.append(text("⚠️ **Filament:** the sensor reports no filament"))
    if media_filename:
        items.append(ui.MediaGallery(discord.MediaGalleryItem(f"attachment://{media_filename}")))
    notes = [n for n in (status.get("message"), media_note) if n]
    if notes:
        items.append(text("-# " + clip(" · ".join(notes), 300)))
    return Card(*items, accent=PRINTER_ACCENTS.get(state, 0x95A5A6))


def elapsed_seconds(start_time: Optional[float], pause_start: Optional[float], now: Optional[float] = None) -> Optional[float]:
    """Playback position from GuildPlayer's start/pause timestamps (None when unknown)."""
    if not start_time:
        return None
    return (pause_start or now or time.time()) - start_time
