"""Show-me step loop (SPEC §6): point at one step at a time, wait for the user, verify, advance.

Written against the interfaces only; nothing here knows an app, a toolkit or a compositor. Narration
and `why` text come from the plan, never from text read off the screen.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from ya_bro.interfaces import CompositorBridge, Overlay, Perception, Policy
from ya_bro.types import Mode, Plan, Rect, Step

BUTTONS = ("next", "repeat", "why", "stop")


class Outcome(StrEnum):
    DONE = "done"
    STOPPED = "stopped"
    BLOCKED = "blocked"  # Policy refused a step


@dataclass(frozen=True)
class Timing:
    poll: float = 0.3  # how often to re-check the screen
    nudge: float = 90.0  # after this long, say we are still waiting (never skips on its own)


Log = Callable[..., object]


class StepLoop:
    def __init__(
        self,
        perception: Perception,
        overlay: Overlay,
        bridge: CompositorBridge,
        policy: Policy,
        timing: Timing | None = None,
        log: Log | None = None,
    ) -> None:
        self._perception = perception
        self._overlay = overlay
        self._bridge = bridge
        self._policy = policy
        self._timing = timing or Timing()
        self._sink = log or (lambda *a, **k: None)
        self._events: asyncio.Queue[str] = asyncio.Queue()

    def _log(self, name: str, **fields: int | str) -> None:
        # Logging is a side channel: whatever the sink does, the loop keeps going.
        with contextlib.suppress(Exception):
            self._sink(name, **fields)

    async def run(self, plan: Plan, app_id: str) -> Outcome:
        pump = asyncio.create_task(self._pump_events())
        try:
            for index, step in enumerate(plan.steps):
                decision = self._policy.check(step, Mode.SHOW_ME)
                if not decision.allowed:
                    await self._overlay.show_step(None, "I can't help with this step.", ())
                    self._log("step_blocked", step=index)
                    return Outcome.BLOCKED
                if await self._present(step, app_id, index, len(plan.steps)) == "stop":
                    return Outcome.STOPPED
            return Outcome.DONE
        finally:
            pump.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pump
            await self._overlay.hide()

    async def _pump_events(self) -> None:
        async for event in self._overlay.events():
            self._events.put_nowait(event)

    async def _locate(self, step: Step, app_id: str) -> Rect | None:
        if step.target is None:
            return None
        found = await self._perception.find(app_id, step.target.role, step.target.name)
        if not found:
            return None
        return await self._perception.locate(found[0])

    async def _satisfied(self, step: Step, app_id: str) -> bool:
        if step.expect is None:
            return False
        found = await self._perception.find(app_id, step.expect.role, step.expect.name)
        return bool(found) == step.expect.appears

    def _text(self, step: Step, rect: Rect | None, count: str) -> str:
        if step.target is None or rect is not None:
            return f"{count} {step.narration}"
        name = step.target.name
        return (
            f"{count} I can't find “{name}” here yet. Open the right screen and I'll point at it."
        )

    async def _in_scope(self) -> bool:
        return await self._bridge.focused_window() is not None

    async def _present(self, step: Step, app_id: str, index: int, total: int) -> str:
        count = f"({index + 1}/{total})"
        shown: tuple[Rect | None, str] | None = None
        hidden = False
        loop = asyncio.get_running_loop()
        since = loop.time()
        nudged = False
        extra = ""
        self._log("step_start", step=index)
        while True:
            if not await self._in_scope():
                # The allowed window lost focus or left scope: show nothing until it is back.
                if not hidden:
                    await self._overlay.hide()
                    hidden, shown = True, None
                    self._log("step_paused", step=index)
            else:
                hidden = False
                rect = await self._locate(step, app_id)
                text = extra or self._text(step, rect, count)
                if (rect, text) != shown:
                    await self._overlay.show_step(rect, text, BUTTONS)
                    shown = (rect, text)
                if await self._satisfied(step, app_id):
                    self._log("step_verified", step=index)
                    return "verified"
                if not nudged and not extra and loop.time() - since > self._timing.nudge:
                    nudged, extra = True, f"{count} Still here. Press Next when you've done it."
            try:
                event = await asyncio.wait_for(self._events.get(), self._timing.poll)
            except TimeoutError:
                continue
            self._log("step_event", step=index, kind=event)
            if event == "stop":
                return "stop"
            if event == "next":
                return "next"
            if event == "repeat":
                extra, shown = "", None
            elif event == "why":
                extra = f"{count} {step.why or 'No extra reason for this one.'}"
