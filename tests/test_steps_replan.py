"""A model plan is shown for approval, and re-planned when its controls are not there (#5)."""

import asyncio

from tests.fakes import FakeCompositorBridge, FakeOverlay, FakePerception, FakePolicy
from ya_bro.steps import MAX_REPLANS, Outcome, StepLoop, Timing
from ya_bro.tone import Tone
from ya_bro.types import ElementRef, Plan, Rect, Step, WindowInfo

APP = "org.example.App"
A, B, C = (ElementRef(APP, "button", n) for n in "ABC")
WIN = WindowInfo("1", APP, "w", Rect(0, 0, 800, 600), focused=True)
FAST = Timing(poll=0.01, nudge=30.0, lost=0.1)


def step(ref):
    return Step(intent=ref.name, narration=f"Press {ref.name}.", target=ref)


def build(elements, steps, replan=None):
    perception = FakePerception(dict(elements))
    overlay = FakeOverlay()
    loop = StepLoop(
        perception,
        overlay,
        FakeCompositorBridge([WIN]),
        FakePolicy(),
        FAST,
        tone=Tone(0),
        replan=replan,
    )
    return perception, overlay, loop, Plan("g", list(steps))


async def settle(seconds=0.15):
    await asyncio.sleep(seconds)


def shows(overlay):
    return [c[2] for c in overlay.calls if c[0] == "show_step"]


# --- approval --------------------------------------------------------------------------------


async def test_a_model_plan_waits_for_next_before_pointing_at_anything():
    _, overlay, loop, plan = build({A: Rect(1, 1, 5, 5)}, [step(A)])
    task = asyncio.create_task(loop.run(plan, APP, preview=True))
    await settle()
    assert overlay.buttons[0] == ("next", "repeat", "why", "stop")[:0] + ("next", "stop")
    assert "1 steps" in shows(overlay)[0] and "Press A." in shows(overlay)[0]
    assert overlay.calls[0][1] is None  # no ring yet
    overlay.push("repeat")  # other buttons do not start it
    await settle()
    assert len(shows(overlay)) == 1
    overlay.push("next")
    await settle()
    assert overlay.calls[-1][1] == Rect(1, 1, 5, 5) and "(1/1)" in shows(overlay)[-1]
    task.cancel()


async def test_stop_on_the_preview_cancels_without_pointing():
    _, overlay, loop, plan = build({A: Rect(1, 1, 5, 5)}, [step(A)])
    task = asyncio.create_task(loop.run(plan, APP, preview=True))
    await settle()
    overlay.push("stop")
    assert await asyncio.wait_for(task, 2) is Outcome.STOPPED
    assert len(shows(overlay)) == 1  # only the preview was ever drawn


async def test_a_pack_or_file_plan_has_no_preview():
    _, overlay, loop, plan = build({A: Rect(1, 1, 5, 5)}, [step(A)])
    task = asyncio.create_task(loop.run(plan, APP))
    await settle()
    assert "(1/1)" in shows(overlay)[0]
    task.cancel()


# --- re-planning -----------------------------------------------------------------------------


async def test_a_missing_control_asks_for_new_steps_and_carries_on():
    calls = []
    holder = []

    async def replan(done, stuck):
        calls.append(([s.target.name for s in done], stuck.target.name))
        holder[0].elements[C] = Rect(9, 9, 5, 5)  # the new plan's control is on screen
        return [step(C)]

    perception, overlay, loop, plan = build({A: Rect(1, 1, 5, 5)}, [step(A), step(B)], replan)
    holder.append(perception)
    task = asyncio.create_task(loop.run(plan, APP))
    await settle()
    overlay.push("next")  # A is done
    await settle(0.4)  # B is not on screen: after `lost` seconds the plan is revised
    assert calls == [(["A"], "B")]
    assert any("another way" in t or "new plan" in t for t in shows(overlay))
    await settle()
    assert overlay.calls[-1][1] == Rect(9, 9, 5, 5) and "Press C." in shows(overlay)[-1]
    overlay.push("next")
    assert await asyncio.wait_for(task, 2) is Outcome.DONE


async def test_a_revised_step_goes_through_policy_like_any_other():
    from ya_bro.types import Mode, PolicyDecision

    class Refuses(FakePolicy):
        def check(self, s, mode: Mode):
            if s.target == C:
                return PolicyDecision(False, False, "no")
            return super().check(s, mode)

    async def replan(done, stuck):
        return [step(C)]

    perception = FakePerception({})
    overlay = FakeOverlay()
    loop = StepLoop(
        perception,
        overlay,
        FakeCompositorBridge([WIN]),
        Refuses(),
        FAST,
        tone=Tone(0),
        replan=replan,
    )
    assert await asyncio.wait_for(loop.run(Plan("g", [step(A)]), APP), 3) is Outcome.BLOCKED


async def test_no_hook_means_no_replanning():
    _, overlay, loop, plan = build({}, [step(A)])
    task = asyncio.create_task(loop.run(plan, APP))
    await settle(0.4)
    assert not any("another way" in t for t in shows(overlay)) and not task.done()
    task.cancel()


async def test_a_hook_that_cannot_help_is_asked_once_per_step_and_the_step_waits():
    calls = []

    async def replan(done, stuck):
        calls.append(1)

    perception, overlay, loop, plan = build({}, [step(A)], replan)
    task = asyncio.create_task(loop.run(plan, APP))
    await settle(0.5)
    assert len(calls) == 1 and not task.done()
    perception.elements[A] = Rect(2, 2, 4, 4)  # the user opens the right screen: it points again
    await settle()
    assert overlay.calls[-1][1] == Rect(2, 2, 4, 4)
    task.cancel()


async def test_replanning_is_capped_per_task():
    calls = []

    async def replan(done, stuck):
        calls.append(1)
        return [step(B)]  # also not on screen: the plan keeps missing

    _, overlay, loop, plan = build({}, [step(A)], replan)
    task = asyncio.create_task(loop.run(plan, APP))
    await settle(1.0)
    assert len(calls) == MAX_REPLANS and not task.done()
    task.cancel()


async def test_a_control_that_is_there_never_triggers_it():
    calls = []

    async def replan(done, stuck):
        calls.append(1)

    _, overlay, loop, plan = build({A: Rect(1, 1, 5, 5)}, [step(A)], replan)
    task = asyncio.create_task(loop.run(plan, APP))
    await settle(0.5)
    assert calls == []
    task.cancel()
