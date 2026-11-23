"""Feeds the struggle detector from the real sources and hands back offers (ADR-0010 §1, §3).

Written against the interfaces only: `ShellHook` (a command finished), `IdleSource`, and a
function saying which allowed app has focus. Packs tune the detector per app through `signals.toml`.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Awaitable, Callable
from typing import Protocol

from ya_bro.interfaces import IdleSource, ShellHook
from ya_bro.packs import Pack
from ya_bro.struggle import Detector, Observation, Offer
from ya_bro.targets import Target

POLL = 1.0  # seconds between idle reads and offer checks


class Sink(Protocol):
    def __call__(self, name: str, **fields: int | str) -> None: ...


def command_apps(targets: list[Target]) -> dict[str, str]:
    """Which target (the "app" the detector counts under) owns each allowed command name."""
    return {c: t.id for t in targets for c in t.commands}


def apply_packs(detector: Detector, packs: list[Pack], app_ids: dict[str, dict[str, str]]) -> None:
    """Give an app its pack's tuning. `app_ids` maps app -> the matchers to test it against."""
    for app, who in app_ids.items():
        for pack in packs:
            if pack.matches(**who) and (pack.signal_weights or pack.signal_counts):
                detector.tune(app, pack.signal_weights, pack.signal_counts)


class StruggleHost:
    def __init__(
        self,
        detector: Detector,
        commands: dict[str, str],
        shell: ShellHook | None = None,
        idle: IdleSource | None = None,
        focused_app: Callable[[], Awaitable[str | None]] | None = None,
        on_offer: Callable[[Offer], None] = lambda _o: None,
        sink: Sink | None = None,
        clock: Callable[[], float] = time.time,
        present: Callable[[Offer], Awaitable[object]] | None = None,
        busy: Callable[[], bool] = lambda: False,
    ) -> None:
        self._d = detector
        self._commands = commands
        self._shell = shell
        self._idle = idle
        self._focused = focused_app
        self._on_offer = on_offer
        self._sink = sink
        self._clock = clock
        self._present = present  # shows the offer and answers the detector (ya_bro.offers)
        self._busy = busy  # a step loop is running: ask nothing, and do not even take an offer
        self._showing: set[asyncio.Task] = set()

    def _log(self, name: str, **fields: int | str) -> None:
        if self._sink is not None:  # a log failure never stops the detector
            with contextlib.suppress(Exception):
                self._sink(name, **fields)

    async def _shell_loop(self) -> None:
        assert self._shell is not None
        async for e in self._shell.events():
            app = self._commands.get(str(e["argv0"]))
            if app is None:
                continue  # a command nobody allowed: not even counted
            fired = self._d.observe(
                Observation(self._clock(), app, "command_exit", str(e["argv0"]), int(e["exit"]))
            )
            for sig in fired:
                self._log("struggle_signal", signal=sig.value)
            self._offer()

    async def _tick_loop(self) -> None:
        while True:
            if self._idle is not None and self._focused is not None:
                app = await self._focused()
                if app:
                    secs = await self._idle.idle_seconds()
                    for sig in self._d.observe(
                        Observation(self._clock(), app, "idle", "", int(secs))
                    ):
                        self._log("struggle_signal", signal=sig.value)
            self._offer()
            await asyncio.sleep(POLL)

    def _offer(self) -> None:
        if self._busy():
            return  # never interrupt a step loop; the offer stays due until it is over
        offer = self._d.poll()
        if offer is not None:
            self._log("struggle_offer", app=offer.app, score=round(offer.score, 2))
            self._on_offer(offer)
            if self._present is not None:  # poll() holds one pending offer, so one task at most
                task = asyncio.create_task(self._show(offer))
                self._showing.add(task)
                task.add_done_callback(self._showing.discard)

    async def _show(self, offer: Offer) -> None:
        assert self._present is not None
        try:
            result = await self._present(offer)
        except Exception as e:  # noqa: BLE001 - a broken bubble must not stop the detector
            self._d.answer(offer, "ignored")  # no-op if it was already answered or withdrawn
            self._log("struggle_bubble_failed", error=type(e).__name__)
            return
        outcome = getattr(result, "outcome", "")
        if outcome and outcome != "withdrawn":
            self._log("struggle_answer", app=offer.app, outcome=outcome)

    async def run(self) -> None:
        tasks = [asyncio.create_task(self._tick_loop())]
        if self._shell is not None:
            tasks.append(asyncio.create_task(self._shell_loop()))
        try:
            await asyncio.gather(*tasks)
        finally:
            for t in [*tasks, *self._showing]:
                t.cancel()
