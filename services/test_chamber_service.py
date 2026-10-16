"""Daily Test Chamber: one multiple-choice trivia question per opted-in server per day.

State lives in the DB (`trivia_questions`, `trivia_answers`, `guild_settings`) so a restart
or deploy mid-question loses nothing; the cog's periodic tick posts what's due and closes
what's expired. Questions come from Open Trivia DB (CC BY-SA 4.0), shared by every server
for the day, with a small built-in bank as fallback.
"""

import json
import logging
import os
import random
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Callable, Dict, List, Optional
from urllib.parse import unquote
from zoneinfo import ZoneInfo

import aiohttp

from config import BotConfig

logger = logging.getLogger(__name__)

SETTING_CHANNEL = "test_chamber_channel"
POST_TIME = time(18, 0)        # local
ANSWER_HOURS = 20              # closes at 14:00 the next day, before the next post
FIRST_POINTS = 10
CORRECT_POINTS = 3
OPENTDB_URL = "https://opentdb.com/api.php?amount=1&type=multiple&encode=url3986"
FALLBACK_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "content", "trivia_fallback.json")
ATTRIBUTION = "Questions from Open Trivia DB (CC BY-SA 4.0)"


@dataclass
class Question:
    category: str
    question: str
    choices: List[str]
    correct_index: int


@dataclass
class OpenQuestion:
    id: int
    guild_id: int
    channel_id: int
    message_id: Optional[int]
    question: Question
    closes_at: datetime


@dataclass
class ClosedResult:
    question: OpenQuestion
    first: Optional[int]           # user id of the first correct answer
    correct: List[int]             # all correct user ids, in answer order
    total_answers: int
    achievements: Dict[int, list]  # user id -> newly earned achievements


def shuffle_choices(correct: str, wrong: List[str], rng=random) -> (List[str], int):
    choices = [correct] + list(wrong)[:3]
    rng.shuffle(choices)
    return choices, choices.index(correct)


async def fetch_opentdb() -> Optional[Question]:
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(OPENTDB_URL) as resp:
                data = await resp.json(content_type=None)
        if data.get("response_code") != 0 or not data.get("results"):
            return None
        q = data["results"][0]
        choices, idx = shuffle_choices(unquote(q["correct_answer"]), [unquote(w) for w in q["incorrect_answers"]])
        return Question(unquote(q["category"]), unquote(q["question"]), choices, idx)
    except Exception as e:
        logger.warning(f"Open Trivia DB fetch failed: {e!r}")
        return None


def fallback_question(rng=random) -> Question:
    with open(FALLBACK_FILE, encoding="utf-8") as f:
        q = rng.choice(json.load(f))
    choices, idx = shuffle_choices(q["correct"], q["wrong"], rng)
    return Question(q["category"], q["question"], choices, idx)


class TestChamberService:
    __test__ = False  # not a pytest class

    def __init__(self, db, points, tz: Optional[ZoneInfo] = None,
                 fetcher: Callable = fetch_opentdb, clock: Optional[Callable[[], datetime]] = None):
        self.db = db
        self.points = points
        self.tz = tz or ZoneInfo(BotConfig.BOT_TIMEZONE)
        self.fetcher = fetcher
        self.clock = clock or (lambda: datetime.now(self.tz))
        self._daily: Dict[str, Question] = {}  # local date -> today's shared question

    def now(self) -> datetime:
        return self.clock().astimezone(self.tz)

    # --- Settings ---

    async def set_channel(self, guild_id: int, channel_id: Optional[int]):
        async with self.db.get_connection() as conn:
            if channel_id is None:
                await conn.execute("DELETE FROM guild_settings WHERE guild_id = ? AND key = ?", (guild_id, SETTING_CHANNEL))
            else:
                await conn.execute("INSERT OR REPLACE INTO guild_settings (guild_id, key, value) VALUES (?, ?, ?)",
                                   (guild_id, SETTING_CHANNEL, str(channel_id)))
            await conn.commit()

    async def channels(self) -> Dict[int, int]:
        async with self.db.get_connection() as conn:
            async with conn.execute("SELECT guild_id, value FROM guild_settings WHERE key = ?", (SETTING_CHANNEL,)) as cur:
                return {g: int(v) for g, v in await cur.fetchall()}

    # --- Posting ---

    async def todays_question(self) -> Question:
        date = self.now().date().isoformat()
        if date not in self._daily:
            self._daily = {date: await self.fetcher() or fallback_question()}
        return self._daily[date]

    async def create_due(self, force_guild: Optional[int] = None) -> List[OpenQuestion]:
        """Create today's question rows for opted-in servers once it's past post time (or right away for
        `force_guild`). Rows have no message_id until the cog posts them; unposted rows are returned too."""
        now = self.now()
        date = now.date().isoformat()
        due = []
        for guild_id, channel_id in (await self.channels()).items():
            if now.time() < POST_TIME and guild_id != force_guild:
                continue
            q = await self.todays_question()
            closes = now.replace(hour=POST_TIME.hour, minute=POST_TIME.minute, second=0, microsecond=0) + timedelta(hours=ANSWER_HOURS)
            if closes <= now:
                closes = now + timedelta(hours=ANSWER_HOURS)
            async with self.db.get_connection() as conn:
                await conn.execute(
                    "INSERT OR IGNORE INTO trivia_questions (guild_id, local_date, question, choices, correct_index, "
                    "category, channel_id, closes_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (guild_id, date, q.question, json.dumps(q.choices), q.correct_index, q.category, channel_id,
                     closes.isoformat()))
                await conn.commit()
        async with self.db.get_connection() as conn:
            async with conn.execute("SELECT * FROM trivia_questions WHERE message_id IS NULL AND closed = 0") as cur:
                cols = [c[0] for c in cur.description]
                for row in await cur.fetchall():
                    due.append(self._open_question(dict(zip(cols, row))))
        return due

    def _open_question(self, row: Dict) -> OpenQuestion:
        q = Question(row["category"], row["question"], json.loads(row["choices"]), row["correct_index"])
        return OpenQuestion(row["id"], row["guild_id"], row["channel_id"], row["message_id"], q,
                            datetime.fromisoformat(row["closes_at"]))

    async def mark_posted(self, question_id: int, message_id: int):
        async with self.db.get_connection() as conn:
            await conn.execute("UPDATE trivia_questions SET message_id = ? WHERE id = ?", (message_id, question_id))
            await conn.commit()

    async def drop_unpostable(self, question_id: int):
        """The channel vanished or the bot lost access: forget the question (and the opt-in is left as is)."""
        async with self.db.get_connection() as conn:
            await conn.execute("UPDATE trivia_questions SET closed = 1 WHERE id = ?", (question_id,))
            await conn.commit()

    # --- Answering ---

    async def answer(self, question_id: int, user_id: int, choice: int) -> str:
        """'correct', 'wrong', 'duplicate', 'closed' or 'missing'."""
        async with self.db.get_connection() as conn:
            async with conn.execute("SELECT correct_index, closed, closes_at FROM trivia_questions WHERE id = ?",
                                    (question_id,)) as cur:
                row = await cur.fetchone()
            if row is None:
                return "missing"
            correct_index, closed, closes_at = row
            if closed or datetime.fromisoformat(closes_at) <= self.now():
                return "closed"
            correct = int(choice == correct_index)
            cur = await conn.execute(
                "INSERT OR IGNORE INTO trivia_answers (question_id, user_id, choice, correct) VALUES (?, ?, ?, ?)",
                (question_id, user_id, choice, correct))
            await conn.commit()
            if cur.rowcount != 1:
                return "duplicate"
        return "correct" if correct else "wrong"

    # --- Closing ---

    async def close_due(self) -> List[ClosedResult]:
        now = self.now()
        results = []
        async with self.db.get_connection() as conn:
            async with conn.execute("SELECT * FROM trivia_questions WHERE closed = 0 AND message_id IS NOT NULL") as cur:
                cols = [c[0] for c in cur.description]
                rows = [dict(zip(cols, r)) for r in await cur.fetchall()]
        for row in rows:
            q = self._open_question(row)
            if q.closes_at > now:
                continue
            async with self.db.get_connection() as conn:
                cur = await conn.execute("UPDATE trivia_questions SET closed = 1 WHERE id = ? AND closed = 0", (q.id,))
                await conn.commit()
                if cur.rowcount != 1:
                    continue  # closed by someone else
                async with conn.execute("SELECT user_id, correct FROM trivia_answers WHERE question_id = ? ORDER BY id",
                                        (q.id,)) as c2:
                    answers = await c2.fetchall()
            correct = [uid for uid, ok in answers if ok]
            earned = {}
            for i, uid in enumerate(correct):
                first = i == 0
                _, new = await self.points.award(q.guild_id, uid, FIRST_POINTS if first else CORRECT_POINTS,
                                                 "trivia_first" if first else "trivia_correct", f"trivia:{q.id}:{uid}")
                if new:
                    earned[uid] = new
            results.append(ClosedResult(q, correct[0] if correct else None, correct, len(answers), earned))
        return results
