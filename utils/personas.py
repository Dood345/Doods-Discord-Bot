"""Character personas, loaded from content/personas.json.

Adding a character = adding an entry there (plus optional fallback/roast/compliment lines
under the same key in content/dialogue.json). /ask, roasts, compliments, /debate and the
legacy per-character commands all read from here.
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Dict

logger = logging.getLogger(__name__)

PERSONAS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "content", "personas.json")


@dataclass(frozen=True)
class Persona:
    key: str
    name: str
    emoji: str
    description: str
    prompt: str          # character instructions for the model
    roast: str           # roast instruction; {target} is the person's display name
    compliment: str      # compliment instruction; {target} as above
    in_rotation: bool = True  # eligible for random roasts/compliments/debates

    @property
    def label(self) -> str:
        return f"{self.emoji} **{self.name}**"


def load_personas(path: str = PERSONAS_FILE) -> Dict[str, Persona]:
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        return {key: Persona(key=key, **data) for key, data in raw.items()}
    except (OSError, ValueError, TypeError) as e:
        logger.error(f"Could not load personas from {path}: {e}")
        return {}
