import asyncio

import pytest

from tests.fakes import (
    FakeCompositorBridge,
    FakeOverlay,
    FakePerception,
    FakePolicy,
)
from ya_bro.steps import Outcome, StepLoop, Timing
from ya_bro.types import ElementRef, Expect, Plan, Rect, Risk, Step, WindowInfo

APP = "org.example.App"
CREATE = ElementRef(APP, "button", "Create")
CONFIRM = ElementRef(APP, "button", "Confirm")
WIN = WindowInfo("1", APP, "w", Rect(0, 0, 800, 600), focused=True)
FAST = Timing(poll=0.01, nudge=30.0)
NUDGE = Timing(poll=0.01, nudge=0.1)


def step(**kw):
    return Step(intent="x", narration="Click Create.", target=CREATE, **kw)


def build(elements, steps, windows=(WIN,), policy=None, timing=FAST):
    perception = FakePerception(dict(elements))
    overlay = FakeOverlay()
    loop = StepLoop(
        perception,
        overlay,
        FakeCompositorBridge(list(windows)),
        policy or FakePolicy(),
        timing,
    )
    return perception, overlay, loop, Plan("g", list(steps))


async def settle(n=5):
    for _ in range(n):
        await asyncio.sleep(0.02)


async def test_points_at_the_target_and_advances_when_the_expected_element_appears():
    elements = {CREATE: Rect(10, 20, 80, 30)}
    perception, overlay, loop, plan = build(elements, [step(expect=Expect("button", "Confirm"))])
    task = asyncio.create_task(loop.run(plan, APP))
    await settle()
    assert overlay.calls[0] == ("show_step", Rect(10, 20, 80, 30), "(1/1) Click Create.")
    assert not task.done()
    perception.elements[CONFIRM] = Rect(0, 0, 1, 1)  # the user clicked: the next screen shows
    assert await asyncio.wait_for(task, 2) is Outcome.DONE
    assert overlay.calls[-1] == ("hide",)


async def test_missing_target_shows_a_bubble_only_never_a_guessed_ring():
    perception, overlay, loop, plan = build({}, [step(expect=Expect("button", "Confirm"))])
    task = asyncio.create_task(loop.run(plan, APP))
    await settle()
    kind, rect, text = overlay.calls[0]
    assert rect is None and "can't find" in text and "Create" in text
    perception.elements[CREATE] = Rect(5, 5, 10, 10)  # it appears: now the ring shows
    await settle()
    assert overlay.calls[-1][1] == Rect(5, 5, 10, 10)
    task.cancel()


async def test_next_skips_verification_and_buttons_are_offered():
    _, overlay, loop, plan = build({CREATE: Rect(1, 1, 2, 2)}, [step(), step()])
    task = asyncio.create_task(loop.run(plan, APP))
    await settle()
    assert overlay.buttons[0] == ("next", "repeat", "why", "stop")
    overlay.push("next")
    await settle()
    assert overlay.calls[-1][2].startswith("(2/2)")
    overlay.push("next")
    assert await asyncio.wait_for(task, 2) is Outcome.DONE


async def test_why_uses_the_plan_text_and_repeat_restores_the_narration():
    _, overlay, loop, plan = build({CREATE: Rect(1, 1, 2, 2)}, [step(why="Creating starts it.")])
    task = asyncio.create_task(loop.run(plan, APP))
    await settle()
    overlay.push("why")
    await settle()
    assert overlay.calls[-1][2] == "(1/1) Creating starts it."
    overlay.push("repeat")
    await settle()
    assert overlay.calls[-1][2] == "(1/1) Click Create."
    task.cancel()


async def test_stop_ends_at_once_and_hides():
    _, overlay, loop, plan = build({CREATE: Rect(1, 1, 2, 2)}, [step(), step()])
    task = asyncio.create_task(loop.run(plan, APP))
    await settle()
    overlay.push("stop")
    assert await asyncio.wait_for(task, 2) is Outcome.STOPPED
    assert overlay.calls[-1] == ("hide",)


async def test_cancel_hides_the_overlay():
    _, overlay, loop, plan = build({CREATE: Rect(1, 1, 2, 2)}, [step()])
    task = asyncio.create_task(loop.run(plan, APP))
    await settle()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert overlay.calls[-1] == ("hide",)


async def test_policy_is_checked_before_every_step():
    class Deny(FakePolicy):
        def check(self, s, mode):
            from ya_bro.types import PolicyDecision

            return PolicyDecision(False, reason="no")

    _, overlay, loop, plan = build({CREATE: Rect(1, 1, 2, 2)}, [step()], policy=Deny())
    assert await loop.run(plan, APP) is Outcome.BLOCKED
    assert overlay.calls[0][1] is None and "can't help" in overlay.calls[0][2]


async def test_scope_loss_hides_the_overlay_and_it_returns_with_focus():
    bridge_windows = [WIN]
    perception = FakePerception({CREATE: Rect(1, 1, 2, 2)})
    overlay = FakeOverlay()
    bridge = FakeCompositorBridge(bridge_windows)
    loop = StepLoop(perception, overlay, bridge, FakePolicy(), FAST)
    task = asyncio.create_task(loop.run(Plan("g", [step()]), APP))
    await settle()
    shows = len([c for c in overlay.calls if c[0] == "show_step"])
    bridge._windows = []  # focus left the allowed app
    await settle()
    assert overlay.calls[-1] == ("hide",)
    bridge._windows = [WIN]
    await settle()
    assert len([c for c in overlay.calls if c[0] == "show_step"]) > shows
    task.cancel()


async def test_the_ring_follows_the_element_when_it_moves():
    perception, overlay, loop, plan = build({CREATE: Rect(1, 1, 2, 2)}, [step()])
    task = asyncio.create_task(loop.run(plan, APP))
    await settle()
    perception.elements[CREATE] = Rect(50, 60, 2, 2)
    await settle()
    assert overlay.calls[-1][1] == Rect(50, 60, 2, 2)
    task.cancel()


async def test_gone_expectation_and_nudge_without_auto_skip():
    perception, overlay, loop, plan = build(
        {CREATE: Rect(1, 1, 2, 2)},
        [step(expect=Expect("button", "Create", appears=False))],
        timing=NUDGE,
    )
    task = asyncio.create_task(loop.run(plan, APP))
    await asyncio.sleep(0.3)
    assert "Still here" in overlay.calls[-1][2] and not task.done()
    del perception.elements[CREATE]
    assert await asyncio.wait_for(task, 2) is Outcome.DONE


async def test_r3_step_is_still_only_shown_never_acted():
    _, overlay, loop, plan = build({CREATE: Rect(1, 1, 2, 2)}, [step(risk=Risk.R3)])
    task = asyncio.create_task(loop.run(plan, APP))
    await settle()
    assert overlay.calls[0][0] == "show_step"  # show-me mode: the user does the click
    task.cancel()
