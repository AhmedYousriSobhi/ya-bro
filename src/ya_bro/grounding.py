"""Pointing from the accessibility tree (ADR-0007 tiers 1 to 3 of the cascade, AT-SPI only).

Scores every element of the wanted role against the wanted name and says how sure it is:
HIGH (exact name, clear margin) gets a solid ring, MEDIUM a hedged one, NONE nothing. LOW (vision
only) and OCR do not exist yet. Pure core: it asks `Perception` and nothing else.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import StrEnum

from ya_bro.interfaces import Perception
from ya_bro.types import ElementRef, Rect

MIN_SCORE = 0.6  # below this nothing counts as found
HIGH_MARGIN = 0.3  # ADR-0007 §3: the best must beat the next by this much for a solid ring
_TRY = 3  # candidates whose rectangle we are willing to look up
_FOLD = str.maketrans({"إ": "ا", "أ": "ا", "آ": "ا", "ى": "ي", "ة": "ه", "ـ": ""})
_SPACE = re.compile(r"\s+")


class Tier(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    NONE = "none"


@dataclass(frozen=True)
class Pointing:
    tier: Tier
    ref: ElementRef | None = None
    rect: Rect | None = None
    score: float = 0.0
    margin: float = 0.0


def normalise(name: str) -> str:
    """Case, spacing, Arabic letter variants and diacritics must not make a name miss."""
    text = unicodedata.normalize("NFKC", name).casefold().translate(_FOLD)
    text = "".join(c for c in text if not unicodedata.category(c) == "Mn")
    return _SPACE.sub(" ", text).strip()


def score(want: str, got: str) -> float:
    """1.0 only for the same name after normalising; otherwise below 0.9 however close."""
    a, b = normalise(want), normalise(got)
    if not a or not b:
        return 0.0
    return 1.0 if a == b else 0.9 * SequenceMatcher(None, a, b).ratio()


def _usable(rect: Rect | None, bounds: Rect | None) -> bool:
    """ADR-0004 sanity: a real size, and (when the window is known) its centre inside the window."""
    if rect is None or rect.w <= 0 or rect.h <= 0:
        return False
    if bounds is None:
        return True
    cx, cy = rect.center
    return bounds.x <= cx < bounds.x + bounds.w and bounds.y <= cy < bounds.y + bounds.h


async def point(
    perception: Perception, app_id: str, role: str, name: str, bounds: Rect | None = None
) -> Pointing:
    scored = sorted(
        ((score(name, ref.name), ref) for ref in await perception.find(app_id, role)),
        key=lambda pair: -pair[0],
    )
    scored = [pair for pair in scored if pair[0] >= MIN_SCORE]
    for i, (best, ref) in enumerate(scored[:_TRY]):
        rect = await perception.locate(ref)
        if not _usable(rect, bounds):
            continue
        rest = [s for j, (s, _) in enumerate(scored) if j != i]
        margin = best - max(rest, default=0.0)
        high = best == 1.0 and margin >= HIGH_MARGIN
        return Pointing(Tier.HIGH if high else Tier.MEDIUM, ref, rect, best, margin)
    return Pointing(Tier.NONE)
