"""Show-me step loop (SPEC §6): point at one step at a time, wait for the user, verify, advance.

Written against the interfaces only; nothing here knows an app, a toolkit or a compositor. Narration
and `why` text come from the plan, never from text read off the screen.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum

from ya_bro import grounding, shell_command
from ya_bro.command_watch import CommandWatch
from ya_bro.grounding import Tier
from ya_bro.interfaces import Actuator, CompositorBridge, Overlay, Perception, Policy
from ya_bro.terminal_write import TerminalWriter
from ya_bro.tone import Tone
from ya_bro.types import Mode, Plan, Rect, Step

MAX_REPLANS = 2  # per task; a plan that keeps missing is the user's cue to rephrase

BUTTONS = ("next", "repeat", "why", "stop")
COMMAND_BUTTONS = ("copy", "write", "next", "why", "stop")


def _joined(fp: tuple[str, ...] | None) -> str:
    return " ".join(t for t in (fp or ()) if t)


class Outcome(StrEnum):
    DONE = "done"
    STOPPED = "stopped"
    BLOCKED = "blocked"  # Policy refused a step


@dataclass(frozen=True)
class Timing:
    poll: float = 0.3  # how often to re-check the screen
    settle: float = 0.6  # a changed screen must hold this long before we call it a wrong action
    nudge: float = 90.0  # after this long, say we are still waiting (never skips on its own)
    lost: float = 4.0  # a target missing this long counts as a plan that no longer fits the screen
    done_hold: float = 0.0  # how long a happy "all done" bubble stays at the end (0: just hide)
    act_pause: float = 1.0  # Do-it: the pointer is shown on the target this long before the press
    verify: float = 3.0  # Do-it: how long to wait for the screen to show the step's result


Log = Callable[..., object]
# (steps already done, the step whose target is gone) -> the steps to use from here, or None
Replan = Callable[[list[Step], Step], Awaitable[list[Step] | None]]


class StepLoop:
    def __init__(
        self,
        perception: Perception,
        overlay: Overlay,
        bridge: CompositorBridge,
        policy: Policy,
        timing: Timing | None = None,
        log: Log | None = None,
        tone: Tone | None = None,
        replan: Replan | None = None,
        actuator: Actuator | None = None,
        writer: TerminalWriter | None = None,
        commands: CommandWatch | None = None,
    ) -> None:
        self._writer = writer  # "Write it": puts a step's command at the shell prompt
        self._commands = commands  # a step's command finishing moves the plan on
        self._actuator = actuator  # None: Show-me only
        self._replan = replan
        self._replans = 0
        self._tone = tone or Tone()
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

    async def _preview(self, plan: Plan) -> bool:
        """Show a model-written plan and wait: True to go on, False when the user stopped."""
        text = self._tone.plan_preview(len(plan.steps), plan.steps[0].narration)
        await self._overlay.show_step(None, text, ("next", "stop"), mood="idle")
        while True:
            event = await self._events.get()
            if event in ("next", "stop"):
                self._log("plan_preview", kind=event)
                return event == "next"

    async def run(self, plan: Plan, app_id: str, preview: bool = False) -> Outcome:
        pump = asyncio.create_task(self._pump_events())
        self._tone.begin_task()
        steps = list(plan.steps)
        self._replans = 0
        try:
            if preview and steps and not await self._preview(plan):
                return Outcome.STOPPED
            index = 0
            can_replan = True
            while index < len(steps):
                step = steps[index]
                decision = self._policy.check(step, Mode.SHOW_ME)
                if not decision.allowed:
                    await self._overlay.show_step(None, "I can't help with this step.", ())
                    self._log("step_blocked", step=index)
                    return Outcome.BLOCKED
                note = ""
                if self._actuator is not None:
                    outcome = await self._try_do_it(step, app_id, index, len(steps))
                    if outcome == "stop":
                        return Outcome.STOPPED
                    if outcome == "done":
                        self._tone.note_progress()
                        index += 1
                        continue
                    note = outcome  # "" or a line saying Do-it handed the step back
                # A step the user must take themselves is never joked about (ADR-0013 §3).
                self._tone.set_sensitive(decision.needs_confirmation)
                try:
                    result = await self._present(
                        step,
                        app_id,
                        index,
                        len(steps),
                        decision.needs_confirmation,
                        can_replan=can_replan
                        and self._replan is not None
                        and self._replans < MAX_REPLANS,
                        note=note,
                    )
                finally:
                    self._tone.set_sensitive(False)
                if result == "stop":
                    return Outcome.STOPPED
                if result == "replan":
                    await self._overlay.show_step(
                        None, self._tone.replanning(), ("stop",), mood="thinking"
                    )
                    self._replans += 1
                    fresh = await self._replan(steps[:index], step) if self._replan else None
                    self._log("replan", step=index, ok=int(bool(fresh)))
                    if fresh:
                        steps[index:] = fresh
                    else:
                        can_replan = False  # keep waiting for the user on this step
                    continue
                can_replan = True
                self._tone.note_progress()
                index += 1
            if self._timing.done_hold > 0:
                await self._overlay.show_step(None, self._tone.done(), (), mood="happy")
                await asyncio.sleep(self._timing.done_hold)
            return Outcome.DONE
        finally:
            pump.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pump
            await self._overlay.hide()

    async def _wait_stop(self) -> None:
        while await self._events.get() != "stop":
            pass

    async def _pause(self, seconds: float) -> bool:
        """Wait, True when the user stopped meanwhile."""
        try:
            await asyncio.wait_for(self._wait_stop(), seconds)
        except TimeoutError:
            return False
        return True

    async def _verified(self, step: Step, app_id: str, was_done: bool) -> bool:
        if step.expect is None or was_done:
            return True  # nothing to check, or the screen could not tell us apart
        loop = asyncio.get_running_loop()
        end = loop.time() + self._timing.verify
        while True:
            if await self._satisfied(step, app_id):
                return True
            if loop.time() >= end:
                return False
            await asyncio.sleep(self._timing.poll)

    async def _try_do_it(self, step: Step, app_id: str, index: int, total: int) -> str:
        """Do-it (ADR-0009): narrate, point, press, check. Returns "done", "stop", or what Show-me
        should say first ("" when Do-it simply does not apply to this step). Anything Do-it cannot
        do safely goes back to the user: Show-me then points and the user presses it."""
        decision = self._policy.check(step, Mode.DO_IT)
        if not decision.allowed or step.target is None:
            return ""
        count = f"({index + 1}/{total})"
        for attempt in range(2):
            rect, tier = await self._locate(step, app_id)
            if rect is None or tier is not Tier.HIGH:
                return ""  # never press on a guess
            if decision.needs_confirmation and attempt == 0:
                self._tone.set_sensitive(True)
                ask = (
                    self._tone.act_type_confirm(step.target.name, step.text)
                    if step.text
                    else self._tone.act_confirm(step.target.name)
                )
                text = f"{count} {ask} {step.narration}"
                self._tone.set_sensitive(False)
                await self._overlay.show_step(rect, text, ("next", "stop"), mood="pointing")
                while (event := await self._events.get()) not in ("next", "stop"):
                    pass
                if event == "stop":
                    return "stop"
            await self._overlay.show_step(rect, f"{count} {step.narration}", ("stop",), "pointing")
            await self._overlay.fly_pointer(rect)
            if await self._pause(self._timing.act_pause):
                return "stop"
            rect, tier = await self._locate(step, app_id)  # it may have moved while we looked
            if rect is None or tier is not Tier.HIGH:
                return ""
            was_done = await self._satisfied(step, app_id)
            act = asyncio.create_task(self._actuator.act(step))  # type: ignore[union-attr]
            stop = asyncio.create_task(self._wait_stop())
            await asyncio.wait({act, stop}, return_when=asyncio.FIRST_COMPLETED)
            if stop.done():
                await self._actuator.abort()  # type: ignore[union-attr]
                act.cancel()
                self._log("act_stopped", step=index)
                return "stop"
            stop.cancel()
            ok = act.result()
            self._log("act", step=index, ok=int(ok), attempt=attempt)
            if (ok or step.expect is not None) and await self._verified(step, app_id, was_done):
                return "done"
        self._log("act_gave_up", step=index)
        return self._tone.act_failed()

    async def _pump_events(self) -> None:
        async for event in self._overlay.events():
            self._events.put_nowait(event)

    async def _locate(self, step: Step, app_id: str) -> tuple[Rect | None, Tier]:
        if step.target is None:
            return None, Tier.NONE
        window = await self._bridge.focused_window()
        p = await grounding.point(
            self._perception,
            app_id,
            step.target.role,
            step.target.name,
            window.rect if window else None,
        )
        return p.rect, p.tier

    async def _satisfied(self, step: Step, app_id: str) -> bool:
        if step.expect is None:
            return False
        found = await self._perception.find(
            app_id, step.expect.role, step.expect.name, step.expect.text
        )
        return bool(found) == step.expect.appears

    async def _fingerprint(self, step: Step, app_id: str) -> tuple[str, ...] | None:
        """What the step's expect element(s) show now; None when there is no text to watch."""
        e = step.expect
        if e is None or not e.text or not e.appears:
            return None
        refs = await self._perception.find(app_id, e.role, e.name)
        return tuple([await self._perception.read_text(r) for r in refs])

    def _text(
        self,
        step: Step,
        rect: Rect | None,
        count: str,
        tier: Tier = Tier.HIGH,
        confirm: bool = False,
    ) -> str:
        if step.target is not None and rect is not None and tier is Tier.MEDIUM:
            return f"{count} {self._tone.unsure(step.target.name)} {step.narration}"
        if confirm and step.target is not None and rect is not None:
            return f"{count} {self._tone.risky(step.target.name)} {step.narration}"
        if step.target is None or rect is not None:
            return f"{count} {step.narration}"
        return f"{count} {self._tone.cant_find(step.target.name)}"

    async def _in_scope(self) -> bool:
        return await self._bridge.focused_window() is not None

    async def _present(
        self,
        step: Step,
        app_id: str,
        index: int,
        total: int,
        confirm: bool = False,
        can_replan: bool = False,
        note: str = "",
    ) -> str:
        count = f"({index + 1}/{total})"
        shown: tuple | None = None
        cmd = step.command
        cmd_name = shell_command.argv0(cmd)
        started = self._commands.now() if self._commands else 0.0
        last_code: int | None = None
        hidden = False
        loop = asyncio.get_running_loop()
        since = loop.time()
        nudged = False
        extra = f"{count} {note}" if note else ""
        # A step that is already "done" when it appears must not advance by itself (the screen may
        # simply still show an old result): it waits for Next until it was seen not done.
        armed = False
        predone = False
        warned = False
        baseline: tuple[str, ...] | None = None
        changed_since: float | None = None
        mismatch = False
        why_is_mistake = False
        lost_since: float | None = None
        mismatch_text: str | None = None  # picked once per mismatch so the line does not flicker
        fp: tuple[str, ...] | None = None
        want_text = step.expect.text if step.expect else ""
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
                done = await self._satisfied(step, app_id)
                if done and armed:
                    self._log("step_verified", step=index)
                    return "verified"
                if not done:
                    if (
                        predone
                    ):  # the old result was cleared: what is on screen now is the new start
                        baseline = None
                    armed, predone = True, False
                elif not armed and not predone:
                    predone = True
                    self._log("step_predone", step=index)
                fp = await self._fingerprint(step, app_id)
                if fp is not None and baseline is None:
                    baseline = fp
                if fp is not None and not done and fp != baseline:
                    # The screen changed, but not to what this step wants: say so once it settles.
                    changed_since = changed_since if changed_since is not None else loop.time()
                    if not mismatch and loop.time() - changed_since >= self._timing.settle:
                        mismatch = True
                        self._log("step_mismatch", step=index)
                else:
                    changed_since, mismatch, mismatch_text = None, False, None
                    if why_is_mistake:  # the mistake was undone: its explanation no longer applies
                        extra, shown, why_is_mistake = "", None, False
                if cmd and self._commands is not None:
                    code = self._commands.finished(cmd_name, started)
                    if code == 0:
                        self._log("command_ran", step=index)
                        return "verified"
                    if code is not None and code != last_code:
                        last_code = code
                        extra, shown = f"{count} {self._tone.cmd_failed(code)}", None
                rect, tier = await self._locate(step, app_id)
                if step.target is not None and rect is None:
                    lost_since = lost_since if lost_since is not None else loop.time()
                    if can_replan and loop.time() - lost_since >= self._timing.lost:
                        self._log("step_lost", step=index)
                        return "replan"
                else:
                    lost_since = None
                text = extra or self._text(step, rect, count, tier, confirm)
                if predone and not extra:
                    text = f"{count} {self._tone.pre_done()}"
                if mismatch and not extra:
                    if mismatch_text is None:
                        mismatch_text = self._tone.mismatch(want_text, _joined(fp))
                    text = f"{count} {mismatch_text}"
                mood = "pointing"
                if step.target is not None and rect is None:
                    mood = "thinking"  # it cannot find the thing: it is working it out
                if (extra or predone) and not why_is_mistake:
                    mood = "idle"
                if (mismatch or why_is_mistake) and self._tone.can_tease():
                    mood = "teasing"  # never at humour 0, on a risky step, or after repeated slips
                buttons = BUTTONS
                if cmd:
                    ok = self._writer is not None and self._writer.can_write(cmd).ok
                    buttons = tuple(b for b in COMMAND_BUTTONS if ok or b != "write")
                if (rect, text, mood, buttons) != shown:
                    extra_args = {"snippet": cmd} if cmd else {}
                    await self._overlay.show_step(rect, text, buttons, mood=mood, **extra_args)
                    shown = (rect, text, mood, buttons)
                if not nudged and not extra and loop.time() - since > self._timing.nudge:
                    nudged, extra = True, f"{count} {self._tone.still_here()}"
            try:
                event = await asyncio.wait_for(self._events.get(), self._timing.poll)
            except TimeoutError:
                continue
            self._log("step_event", step=index, kind=event)
            if event == "stop":
                return "stop"
            if event == "next":
                if step.expect is None or predone or warned or mismatch:
                    return "next"
                # Next on a step the screen does not show done: ask once, skip on the second press.
                warned = True
                extra = f"{count} {self._tone.not_yet()}"
                shown = None
            elif event == "copy" and cmd:
                extra, shown = f"{count} {self._tone.copied()}", None
            elif event == "write" and cmd and self._writer is not None:
                done = await asyncio.to_thread(self._writer.write, cmd)
                note = self._tone.written() if done.ok else done.reason
                extra, shown = f"{count} {note}", None
            elif event == "repeat":
                extra, shown, warned, why_is_mistake = "", None, False, False
            elif event == "why":
                if mismatch and step.expect is not None:
                    extra = f"{count} {self._tone.why_mismatch(want_text, _joined(fp), step.why)}"
                    why_is_mistake = True
                else:
                    extra = f"{count} {step.why or 'No extra reason for this one.'}"
