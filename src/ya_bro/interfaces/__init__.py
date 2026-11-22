"""Component interfaces as typing.Protocol (ADR-0003, ADR-0018).

Method surfaces are provisional: minimal, derived from the ADRs, and expected to change
as the first real backends land.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Protocol, runtime_checkable

from ya_bro.types import ElementRef, Mode, Plan, PolicyDecision, Rect, Step, WindowInfo


@runtime_checkable
class Perception(Protocol):
    async def find(self, app_id: str, role: str, name: str) -> list[ElementRef]: ...
    async def locate(self, ref: ElementRef) -> Rect | None: ...


@runtime_checkable
class CompositorBridge(Protocol):
    async def windows(self) -> list[WindowInfo]: ...
    async def focused_window(self) -> WindowInfo | None: ...


@runtime_checkable
class Overlay(Protocol):
    async def show_step(
        self, target: Rect | None, bubble_text: str, buttons: tuple[str, ...] = ()
    ) -> None: ...
    def events(self) -> AsyncIterator[str]:
        """User choices from the bubble: next, repeat, why, stop (stop also from the stop key)."""
        ...

    async def fly_pointer(self, to: Rect) -> None: ...
    async def hide(self) -> None: ...


@runtime_checkable
class Actuator(Protocol):
    async def act(self, step: Step) -> bool: ...
    async def abort(self) -> None: ...


@runtime_checkable
class Capture(Protocol):
    async def grab(self, region: Rect | None = None) -> Path: ...


@runtime_checkable
class IdleSource(Protocol):
    async def idle_seconds(self) -> float: ...


@runtime_checkable
class Hotkeys(Protocol):
    def events(self) -> AsyncIterator[str]: ...


@runtime_checkable
class ShellHook(Protocol):
    def events(self) -> AsyncIterator[dict[str, int | str]]: ...


@runtime_checkable
class Voice(Protocol):
    async def listen(self) -> str: ...
    async def speak(self, text: str) -> None: ...


@runtime_checkable
class SecretStore(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def put(self, key: str, value: str) -> None: ...


@runtime_checkable
class Policy(Protocol):
    def check(self, step: Step, mode: Mode) -> PolicyDecision: ...


@runtime_checkable
class Brain(Protocol):
    async def plan(self, goal: str, app_id: str) -> Plan: ...
