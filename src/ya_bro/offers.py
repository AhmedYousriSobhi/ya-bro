"""The offer bubble: asks "you stuck, bro?" and hands the answer to the detector (ADR-0010 §4).

Written against the `Overlay` interface and the persona only. The detector decides *when* to offer;
this decides how it looks and what each answer does. Yes, No and "Not for this app" go to
`Detector.answer`, so the whole back-off policy (cooldown, a "no" silencing a signal, two in a row
silencing the app, "never") runs for real. A bubble nobody answers fades and counts as a soft "no".

Never interrupts: if a step loop is running the offer is withdrawn unshown. The stop key hides the
bubble and counts as a "no". Nothing here acts on the user's behalf.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from ya_bro.interfaces import Overlay
from ya_bro.persona import Persona
from ya_bro.struggle import Detector, Offer

BUTTONS = ("yes", "no", "not_for_app")  # the extension's fixed labels (overlay.js)
ANSWERS = {"yes": "yes", "no": "no", "not_for_app": "never", "stop": "no"}
FADE_SECONDS = 20.0  # unanswered this long counts as "ignored"
SAY_SECONDS = 2.5  # how long the closing line stays up


@dataclass(frozen=True)
class Result:
    outcome: str  # yes, no, ignored, never, or "withdrawn" (never shown)
    quiet: bool = False  # the app is now silenced for a while


class OfferBubble:
    def __init__(
        self,
        detector: Detector,
        overlay: Overlay,
        persona: Persona,
        busy: Callable[[], bool] = lambda: False,
        on_accept: Callable[[Offer], Awaitable[None] | None] | None = None,
        fade: float = FADE_SECONDS,
        say_for: float = SAY_SECONDS,
    ) -> None:
        self._d = detector
        self._overlay = overlay
        self._persona = persona
        self._busy = busy
        self._on_accept = on_accept
        self._fade = fade
        self._say_for = say_for

    async def present(self, offer: Offer) -> Result:
        """Show one offer and wait for the answer. Always leaves the screen clear."""
        if self._busy():
            self._d.withdraw(offer)
            return Result("withdrawn")
        text = self._persona.say("offer_stuck", app=offer.app)
        await self._overlay.show_step(None, text, BUTTONS, mood="idle")
        answer = await self._wait()
        outcome = ANSWERS.get(answer, "ignored")
        self._d.answer(offer, outcome)
        quiet = outcome == "no" and self._d.is_quiet(offer.app)
        try:
            if outcome == "yes":
                await self._overlay.show_step(None, self._persona.say("greeting"), (), mood="happy")
                if self._on_accept is not None:
                    done = self._on_accept(offer)
                    if inspect.isawaitable(done):
                        await done
                await asyncio.sleep(self._say_for)
            elif outcome in ("no", "never") or quiet:
                moment = "back_off_long" if quiet else "offer_declined"
                await self._overlay.show_step(None, self._persona.say(moment), (), mood="quiet")
                await asyncio.sleep(self._say_for)
            # "ignored": the bubble just fades; saying something would be another interruption
        finally:
            await self._overlay.hide()
        return Result(outcome, quiet)

    async def _wait(self) -> str:
        """The first answer event, or "" when the fade time runs out. Other events are ignored."""
        events = self._overlay.events()
        try:
            async with asyncio.timeout(self._fade):
                async for e in events:
                    if e in ANSWERS:
                        return e
        except TimeoutError:
            pass
        finally:
            aclose = getattr(events, "aclose", None)
            if aclose is not None:
                with contextlib.suppress(Exception):
                    await aclose()
        return ""
