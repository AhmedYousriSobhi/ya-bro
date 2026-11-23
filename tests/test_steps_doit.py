"""Do-it in the step loop (ADR-0009, #27): the bro presses, checks, and hands back what it must."""

import asyncio

from tests.fakes import FakeCompositorBridge, FakeOverlay, FakePerception
from ya_bro.policy import LocalPolicy, ShowMePolicy
from ya_bro.steps import Outcome, StepLoop, Timing
from ya_bro.tone import Tone
from ya_bro.types import ElementRef, Expect, Plan, Rect, Risk, Step, WindowInfo

APP = "org.example.App"
CREATE = ElementRef(APP, "button", "Create")
DONE = ElementRef(APP, "label", "Result")
WIN = WindowInfo("1", APP, "w", Rect(0, 0, 800, 600), focused=True)
TIMING = Timing(poll=0.01, nudge=30.0, act_pause=0.05, verify=0.15)
RECT = Rect(10, 20, 80, 30)


class Presser:
    """An actuator that, when it works, makes the screen show the step's result."""

    def __init__(self, perception, works=True, hang=False):
        self.perception, self.works, self.hang = perception, works, hang
        self.pressed, self.aborted = [], False

    async def act(self, step):
        self.pressed.append(step)
        if self.hang:
            await asyncio.sleep(30)
        if self.works:
            self.perception.elements[DONE] = Rect(0, 0, 1, 1)
        return self.works

    async def abort(self):
        self.aborted = True


def step(**kw):
    kw.setdefault("expect", Expect("label", "Result"))
    return Step(intent="x", narration="Click Create.", target=kw.pop("target", CREATE), **kw)


def build(steps, elements=None, **actuator):
    perception = FakePerception({CREATE: RECT} if elements is None else elements)
    overlay = FakeOverlay()
    presser = Presser(perception, **actuator)
    loop = StepLoop(
        perception,
        overlay,
        FakeCompositorBridge([WIN]),
        LocalPolicy(do_it=True),
        TIMING,
        tone=Tone(0),
        actuator=presser,
    )
    return overlay, presser, loop, Plan("g", list(steps))


def texts(overlay):
    return [c[2] for c in overlay.calls if c[0] == "show_step"]


async def test_presses_the_control_checks_the_result_and_advances_alone():
    overlay, presser, loop, plan = build([step()])
    assert await asyncio.wait_for(loop.run(plan, APP), 3) is Outcome.DONE
    assert len(presser.pressed) == 1
    assert ("fly_pointer", RECT) in overlay.calls  # the pointer goes there first, visibly
    assert overlay.buttons[0] == ("stop",)


async def test_a_step_with_nothing_to_check_trusts_the_press():
    overlay, presser, loop, plan = build([step(expect=None)])
    assert await asyncio.wait_for(loop.run(plan, APP), 3) is Outcome.DONE
    assert len(presser.pressed) == 1


async def test_r3_is_never_pressed_the_bro_points_and_waits_for_the_user():
    overlay, presser, loop, plan = build([step(risk=Risk.R3)])
    task = asyncio.create_task(loop.run(plan, APP))
    await asyncio.sleep(0.3)
    assert presser.pressed == [] and not task.done()
    assert any("yours" in t or "yourself" in t for t in texts(overlay))
    overlay.push("stop")
    assert await asyncio.wait_for(task, 2) is Outcome.STOPPED


async def test_a_dangerous_name_is_never_pressed_even_when_the_plan_says_r0():
    delete = ElementRef(APP, "button", "Delete")
    overlay, presser, loop, plan = build([step(target=delete)], {delete: RECT})
    task = asyncio.create_task(loop.run(plan, APP))
    await asyncio.sleep(0.3)
    assert presser.pressed == []
    task.cancel()


async def test_r2_asks_first_and_presses_only_after_ok():
    overlay, presser, loop, plan = build([step(risk=Risk.R2)])
    task = asyncio.create_task(loop.run(plan, APP))
    await asyncio.sleep(0.2)
    assert presser.pressed == []
    assert overlay.buttons[0] == ("next", "stop") and "OK" in texts(overlay)[0]
    overlay.push("next")
    assert await asyncio.wait_for(task, 3) is Outcome.DONE
    assert len(presser.pressed) == 1


async def test_stop_at_the_r2_question_presses_nothing():
    overlay, presser, loop, plan = build([step(risk=Risk.R2)])
    task = asyncio.create_task(loop.run(plan, APP))
    await asyncio.sleep(0.2)
    overlay.push("stop")
    assert await asyncio.wait_for(task, 2) is Outcome.STOPPED
    assert presser.pressed == []


async def test_stop_while_the_pointer_travels_presses_nothing():
    slow = Timing(poll=0.01, act_pause=5.0, verify=0.1)
    overlay, presser, loop, plan = build([step()])
    loop._timing = slow
    task = asyncio.create_task(loop.run(plan, APP))
    await asyncio.sleep(0.2)
    overlay.push("stop")
    assert await asyncio.wait_for(task, 2) is Outcome.STOPPED
    assert presser.pressed == []


async def test_stop_during_the_press_aborts_the_actuator():
    overlay, presser, loop, plan = build([step()], hang=True)
    task = asyncio.create_task(loop.run(plan, APP))
    await asyncio.sleep(0.3)
    assert len(presser.pressed) == 1
    overlay.push("stop")
    assert await asyncio.wait_for(task, 2) is Outcome.STOPPED
    assert presser.aborted


async def test_two_failed_presses_hand_the_step_back_to_the_user():
    overlay, presser, loop, plan = build([step()], works=False)
    task = asyncio.create_task(loop.run(plan, APP))
    await asyncio.sleep(0.8)
    assert len(presser.pressed) == 2  # one retry, then it stops acting
    assert not task.done()
    assert any("Over to you" in t or "yours" in t for t in texts(overlay))
    assert overlay.buttons[-1] == ("next", "repeat", "why", "stop")  # now the Show-me bubble
    task.cancel()


async def test_a_missing_target_is_not_pressed():
    overlay, presser, loop, plan = build([step()], elements={})
    task = asyncio.create_task(loop.run(plan, APP))
    await asyncio.sleep(0.3)
    assert presser.pressed == []
    task.cancel()


async def test_without_an_actuator_nothing_is_ever_pressed():
    perception = FakePerception({CREATE: RECT})
    overlay = FakeOverlay()
    loop = StepLoop(
        perception, overlay, FakeCompositorBridge([WIN]), ShowMePolicy(), TIMING, tone=Tone(0)
    )
    task = asyncio.create_task(loop.run(Plan("g", [step()]), APP))
    await asyncio.sleep(0.3)
    assert not task.done() and ("fly_pointer", RECT) not in overlay.calls
    task.cancel()


async def test_a_screen_that_already_shows_the_result_is_trusted_after_one_press():
    overlay, presser, loop, plan = build([step()])
    presser.perception.elements[DONE] = Rect(0, 0, 1, 1)  # cannot tell before from after
    assert await asyncio.wait_for(loop.run(plan, APP), 3) is Outcome.DONE
    assert len(presser.pressed) == 1
