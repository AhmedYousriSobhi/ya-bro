"""In-memory fakes for every interface (ADR-0016). Record calls so tests can assert on them."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

from ya_bro.types import (
    ElementRef,
    Mode,
    Plan,
    PolicyDecision,
    Rect,
    Risk,
    Step,
    UiEvent,
    WindowInfo,
)


class FakePerception:
    def __init__(
        self,
        elements: dict[ElementRef, Rect] | None = None,
        texts: dict[ElementRef, str] | None = None,
    ) -> None:
        self.elements = elements or {}
        self.texts = texts or {}

    async def find(
        self, app_id: str, role: str, name: str = "", text: str = ""
    ) -> list[ElementRef]:
        return [
            r
            for r in self.elements
            if (r.app_id, r.role) == (app_id, role)
            and (not name or r.name == name)
            and (not text or text in self.texts.get(r, ""))
        ]

    async def locate(self, ref: ElementRef) -> Rect | None:
        return self.elements.get(ref)

    async def read_text(self, ref: ElementRef) -> str:
        return self.texts.get(ref, "")


class FakeCompositorBridge:
    def __init__(self, windows: list[WindowInfo] | None = None) -> None:
        self._windows = windows or []

    async def windows(self) -> list[WindowInfo]:
        return list(self._windows)

    async def focused_window(self) -> WindowInfo | None:
        return next((w for w in self._windows if w.focused), None)


class FakeOverlay:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.buttons: list[tuple[str, ...]] = []
        self.moods: list[str] = []
        self._events: asyncio.Queue[str] = asyncio.Queue()

    async def show_step(
        self,
        target: Rect | None,
        bubble_text: str,
        buttons: tuple[str, ...] = (),
        mood: str = "",
    ) -> None:
        self.calls.append(("show_step", target, bubble_text))
        self.buttons.append(buttons)
        self.moods.append(mood)

    def push(self, event: str) -> None:
        self._events.put_nowait(event)

    async def events(self) -> AsyncIterator[str]:
        while True:
            yield await self._events.get()

    async def fly_pointer(self, to: Rect) -> None:
        self.calls.append(("fly_pointer", to))

    async def hide(self) -> None:
        self.calls.append(("hide",))


class FakeActuator:
    def __init__(self) -> None:
        self.acted: list[Step] = []
        self.aborted = False

    async def act(self, step: Step) -> bool:
        if self.aborted:
            return False
        self.acted.append(step)
        return True

    async def abort(self) -> None:
        self.aborted = True


class FakeCapture:
    async def grab(self, region: Rect | None = None) -> Path:
        return Path("/dev/null")


class FakeIdleSource:
    def __init__(self, seconds: float = 0.0) -> None:
        self.seconds = seconds

    async def idle_seconds(self) -> float:
        return self.seconds


class FakeHotkeys:
    def __init__(self, queued: list[str] | None = None) -> None:
        self.queued = list(queued or [])

    async def events(self) -> AsyncIterator[str]:
        for e in self.queued:
            yield e


class FakeShellHook:
    def __init__(self, queued: list[dict[str, int | str]] | None = None) -> None:
        self.queued = list(queued or [])

    async def events(self) -> AsyncIterator[dict[str, int | str]]:
        for e in self.queued:
            yield e


class FakeUiEvents:
    def __init__(self, queued: list[UiEvent] | None = None) -> None:
        self.queued = list(queued or [])

    async def events(self) -> AsyncIterator[UiEvent]:
        for e in self.queued:
            yield e


class FakeVoice:
    def __init__(self, heard: str = "") -> None:
        self.heard = heard
        self.spoken: list[str] = []

    async def listen(self) -> str:
        return self.heard

    async def speak(self, text: str) -> None:
        self.spoken.append(text)


class FakeSecretStore:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def put(self, key: str, value: str) -> None:
        self._data[key] = value


class FakePolicy:
    """R3 steps always need the user's own click (ADR-0009); everything else is allowed."""

    def check(self, step: Step, mode: Mode) -> PolicyDecision:
        if step.risk is Risk.R3 and mode is Mode.DO_IT:
            return PolicyDecision(False, True, "R3 is the user's own click")
        return PolicyDecision(True)


class FakeBrain:
    def __init__(self, plan: Plan | None = None) -> None:
        self._plan = plan

    async def plan(self, goal: str, app_id: str) -> Plan:
        return self._plan or Plan(goal=goal)
