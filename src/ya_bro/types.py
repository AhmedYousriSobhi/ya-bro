"""Shared value types passed across the interfaces (provisional, see ADR-0018)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, StrEnum


@dataclass(frozen=True, slots=True)
class Rect:
    """Screen rectangle in logical pixels, origin top-left (ADR-0004)."""

    x: int
    y: int
    w: int
    h: int

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.w // 2, self.y + self.h // 2)


@dataclass(frozen=True, slots=True)
class ElementRef:
    """Stable-enough handle to a UI element; fingerprint is role + name based (ADR-0005)."""

    app_id: str
    role: str
    name: str
    path: str = ""


class Risk(IntEnum):
    """Risk tiers R0-R3 (ADR-0009); R3 is always the user's own click."""

    R0 = 0
    R1 = 1
    R2 = 2
    R3 = 3


class Mode(StrEnum):
    SHOW_ME = "show_me"
    DO_IT = "do_it"
    AUTO_FOLLOW = "auto_follow"


@dataclass(frozen=True, slots=True)
class Expect:
    """What the screen should show once the user did the step (verified through Perception)."""

    role: str
    name: str
    appears: bool = True  # False: the element is gone when the step is done


@dataclass(frozen=True, slots=True)
class Step:
    """One step of the loop: intent, target, narration, expected result, risk (SPEC §6)."""

    intent: str
    narration: str
    target: ElementRef | None = None
    expected: str = ""
    risk: Risk = Risk.R0
    expect: Expect | None = None
    why: str = ""


@dataclass(frozen=True, slots=True)
class WindowInfo:
    window_id: str
    app_id: str
    title: str
    rect: Rect
    focused: bool = False


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    needs_confirmation: bool = False
    reason: str = ""


@dataclass(slots=True)
class Plan:
    goal: str
    steps: list[Step] = field(default_factory=list)
