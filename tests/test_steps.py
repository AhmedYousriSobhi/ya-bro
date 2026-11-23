import asyncio

import pytest

from tests.fakes import (
    FakeCompositorBridge,
    FakeOverlay,
    FakePerception,
    FakePolicy,
)
from ya_bro.steps import Outcome, StepLoop, Timing
from ya_bro.tone import Tone
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
        tone=Tone(0),
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


async def test_logging_uses_the_cli_signature_and_can_never_kill_the_loop():
    seen = []

    def cli_log(event, **fields):  # the shape broctl show uses: the first parameter is called event
        seen.append((event, fields))

    def broken_log(event, **fields):
        raise RuntimeError("sink exploded")

    for sink in (cli_log, broken_log):
        perception = FakePerception({CREATE: Rect(1, 1, 2, 2)})
        overlay = FakeOverlay()
        loop = StepLoop(
            perception, overlay, FakeCompositorBridge([WIN]), FakePolicy(), FAST, log=sink
        )
        task = asyncio.create_task(loop.run(Plan("g", [step()]), APP))
        await settle()
        overlay.push("next")
        assert await asyncio.wait_for(task, 2) is Outcome.DONE
    assert ("step_event", {"step": 0, "kind": "next"}) in seen


DISPLAY = ElementRef(APP, "text", "")


def text_step(shown, **kw):
    return Step(
        intent="x",
        narration="Press 7.",
        target=CREATE,
        expect=Expect("text", text=shown),
        **kw,
    )


def build_text(display, steps):
    perception = FakePerception(
        {CREATE: Rect(1, 1, 2, 2), DISPLAY: Rect(0, 0, 9, 9)}, {DISPLAY: display}
    )
    overlay = FakeOverlay()
    loop = StepLoop(
        perception, overlay, FakeCompositorBridge([WIN]), FakePolicy(), FAST, tone=Tone(0)
    )
    return perception, overlay, loop, Plan("g", list(steps))


async def test_a_step_verifies_from_element_text_and_advances_by_itself():
    perception, overlay, loop, plan = build_text("", [text_step("7")])
    task = asyncio.create_task(loop.run(plan, APP))
    await settle()
    assert not task.done()
    perception.texts[DISPLAY] = "7"  # the user pressed the key: the display shows it
    assert await asyncio.wait_for(task, 2) is Outcome.DONE


async def test_next_on_an_undone_step_asks_once_then_skips_on_the_second_press():
    _, overlay, loop, plan = build_text("", [text_step("7"), text_step("7x")])
    task = asyncio.create_task(loop.run(plan, APP))
    await settle()
    overlay.push("next")
    await settle()
    assert "don't see that yet" in overlay.calls[-1][2] and overlay.calls[-1][2].startswith("(1/2)")
    assert not task.done()
    overlay.push("next")
    await settle()
    assert overlay.calls[-1][2].startswith("(2/2)")  # the second Next skipped to step 2
    task.cancel()


async def test_repeat_forgets_the_warning():
    _, overlay, loop, plan = build_text("", [text_step("7"), text_step("7x")])
    task = asyncio.create_task(loop.run(plan, APP))
    await settle()
    overlay.push("next")
    await settle()
    overlay.push("repeat")
    await settle()
    overlay.push("next")
    await settle()
    assert overlay.calls[-1][2].startswith("(1/2)") and "don't see" in overlay.calls[-1][2]
    task.cancel()


async def test_a_step_that_is_already_done_waits_instead_of_advancing_by_itself():
    perception, overlay, loop, plan = build_text("7", [text_step("7"), text_step("7x")])
    task = asyncio.create_task(loop.run(plan, APP))
    await settle()
    assert "already looks done" in overlay.calls[-1][2] and overlay.calls[-1][2].startswith("(1/2)")
    assert not task.done()
    overlay.push("next")  # no warning: the screen does show it
    await settle()
    assert overlay.calls[-1][2].startswith("(2/2)")
    task.cancel()


async def test_a_pre_done_step_arms_once_it_is_seen_undone():
    perception, overlay, loop, plan = build_text("7", [text_step("7")])
    task = asyncio.create_task(loop.run(plan, APP))
    await settle()
    perception.texts[DISPLAY] = ""  # cleared
    await settle()
    assert not task.done()
    perception.texts[DISPLAY] = "7"  # now typed by the user
    assert await asyncio.wait_for(task, 2) is Outcome.DONE


SETTLE = Timing(poll=0.01, nudge=30.0, settle=0.05)


def build_watch(display, steps):
    perception = FakePerception(
        {CREATE: Rect(1, 1, 2, 2), DISPLAY: Rect(0, 0, 9, 9)}, {DISPLAY: display}
    )
    overlay = FakeOverlay()
    loop = StepLoop(
        perception, overlay, FakeCompositorBridge([WIN]), FakePolicy(), SETTLE, tone=Tone(0)
    )
    return perception, overlay, loop, Plan("g", list(steps))


async def test_a_wrong_action_is_noticed_and_corrected_without_skipping():
    perception, overlay, loop, plan = build_watch("", [text_step("7")])
    task = asyncio.create_task(loop.run(plan, APP))
    await settle()
    perception.texts[DISPLAY] = "5"  # pressed the wrong key
    await asyncio.sleep(0.2)
    last = overlay.calls[-1][2]
    assert "not what I asked" in last and "“7”" in last and not task.done()
    perception.texts[DISPLAY] = ""  # undone: the message goes away
    await asyncio.sleep(0.2)
    assert overlay.calls[-1][2] == "(1/1) Press 7."
    perception.texts[DISPLAY] = "7"
    assert await asyncio.wait_for(task, 2) is Outcome.DONE


async def test_a_wrong_action_is_not_flagged_before_it_settles():
    perception, overlay, loop, plan = build_watch("", [text_step("75")])
    task = asyncio.create_task(loop.run(plan, APP))
    await settle()
    perception.texts[DISPLAY] = "7"  # on the way to "75": the first digit is fine
    await asyncio.sleep(0.02)
    perception.texts[DISPLAY] = "75"
    assert await asyncio.wait_for(task, 2) is Outcome.DONE
    assert not any("not what I asked" in c[2] for c in overlay.calls if c[0] == "show_step")


async def test_next_after_a_wrong_action_goes_on_without_a_second_press():
    perception, overlay, loop, plan = build_watch("", [text_step("7"), text_step("7x")])
    task = asyncio.create_task(loop.run(plan, APP))
    await settle()
    perception.texts[DISPLAY] = "5"
    await asyncio.sleep(0.2)
    overlay.push("next")
    await settle()
    assert overlay.calls[-1][2].startswith("(2/2)")
    task.cancel()


async def test_clearing_an_old_result_is_not_a_wrong_action():
    perception, overlay, loop, plan = build_watch("7", [text_step("7")])  # already done at start
    task = asyncio.create_task(loop.run(plan, APP))
    await settle()
    assert "already looks done" in overlay.calls[-1][2]
    perception.texts[DISPLAY] = ""  # the user clears it, as asked
    await asyncio.sleep(0.2)
    assert not any("not what I asked" in c[2] for c in overlay.calls if c[0] == "show_step")
    perception.texts[DISPLAY] = "7"
    assert await asyncio.wait_for(task, 2) is Outcome.DONE


async def test_why_after_a_wrong_key_explains_the_mistake_and_clears_when_undone():
    perception, overlay, loop, plan = build_watch(
        "", [text_step("7", why="7 is the first number.")]
    )
    task = asyncio.create_task(loop.run(plan, APP))
    await settle()
    perception.texts[DISPLAY] = "5"
    await asyncio.sleep(0.2)
    overlay.push("why")
    await asyncio.sleep(0.1)
    why = overlay.calls[-1][2]
    assert "“5”" in why and "“7”" in why and "7 is the first number." in why and "Undo" in why
    perception.texts[DISPLAY] = ""  # undone: the mistake explanation must not linger
    await asyncio.sleep(0.2)
    assert overlay.calls[-1][2] == "(1/1) Press 7."
    task.cancel()


async def test_playful_tone_by_default_and_plain_at_zero():
    perception = FakePerception(
        {CREATE: Rect(1, 1, 2, 2), DISPLAY: Rect(0, 0, 9, 9)}, {DISPLAY: ""}
    )
    for humour, marker in ((1, "I warned you"), (0, "That's not what I asked for")):
        overlay = FakeOverlay()
        loop = StepLoop(
            perception,
            overlay,
            FakeCompositorBridge([WIN]),
            FakePolicy(),
            SETTLE,
            tone=Tone(humour),
        )
        perception.texts[DISPLAY] = ""
        task = asyncio.create_task(loop.run(Plan("g", [text_step("7")]), APP))
        await settle()
        perception.texts[DISPLAY] = "5"
        await asyncio.sleep(0.2)
        assert marker in overlay.calls[-1][2]
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


def test_tone_lines_cap_screen_text_and_rotate():
    tone = Tone(1)
    long = "9" * 200
    line = tone.mismatch("7", long)
    assert long not in line and "…" in line
    seen = set()
    for _ in range(3):
        tone.note_progress()  # (a run of wrong actions makes the bro drop a level: tested below)
        seen.add(tone.mismatch("7", "5"))
    assert len(seen) == 3  # three different lines in a row
    assert "warned" not in Tone(0).mismatch("7", "5")
    # Three wrong actions in a row: the bro stops teasing (ADR-0013: humour drops a level).
    tone = Tone(1)
    lines = [tone.mismatch("7", "5") for _ in range(4)]
    assert (
        "That's not what I asked for" in lines[3] and "That's not what I asked for" not in lines[0]
    )
    tone.note_progress()
    assert "That's not what I asked for" not in tone.mismatch("7", "5")
    assert Tone(0).why_mismatch("7", "", "").startswith("The screen shows something else")


async def test_close_but_not_exact_name_is_pointed_at_with_a_hedge():
    near = ElementRef(APP, "button", "Create…")
    perception, overlay, loop, plan = build({near: Rect(10, 20, 80, 30)}, [step()])
    task = asyncio.create_task(loop.run(plan, APP))
    await settle()
    _, rect, text = overlay.calls[0]
    assert rect == Rect(10, 20, 80, 30)
    assert text == "(1/1) I think it's this one, “Create”: Click Create."
    task.cancel()


async def test_two_elements_with_the_same_name_get_the_hedge_too():
    twin = ElementRef(APP, "button", "Create", "other")
    perception, overlay, loop, plan = build(
        {CREATE: Rect(10, 20, 80, 30), twin: Rect(10, 80, 80, 30)}, [step()]
    )
    task = asyncio.create_task(loop.run(plan, APP))
    await settle()
    assert "I think it's this one" in overlay.calls[0][2]
    task.cancel()


async def test_a_ring_outside_the_focused_window_is_never_drawn():
    elements = {CREATE: Rect(2000, 20, 80, 30)}  # centre is off the 800x600 window
    perception, overlay, loop, plan = build(elements, [step()])
    task = asyncio.create_task(loop.run(plan, APP))
    await settle()
    _, rect, text = overlay.calls[0]
    assert rect is None and "can't find" in text
    task.cancel()


# ---- how the bro looks (moods, ADR-0028) ------------------------------------------------------


async def test_the_bro_points_while_a_step_waits_and_looks_puzzled_when_it_cannot_find_it():
    perception, overlay, loop, plan = build({}, [step(expect=Expect("button", "Confirm"))])
    task = asyncio.create_task(loop.run(plan, APP))
    await settle()
    assert overlay.moods[-1] == "thinking"  # nothing to point at yet
    perception.elements[CREATE] = Rect(5, 5, 10, 10)
    await settle()
    assert overlay.moods[-1] == "pointing"
    task.cancel()


async def test_a_wrong_action_makes_the_bro_tease_only_when_humour_allows_it():
    for humour, mood, marker in (
        (1, "teasing", "I warned you"),
        (0, "pointing", "That's not what I"),
    ):
        perception = FakePerception(
            {CREATE: Rect(1, 1, 2, 2), DISPLAY: Rect(0, 0, 9, 9)}, {DISPLAY: ""}
        )
        overlay = FakeOverlay()
        tone = Tone(humour)
        loop = StepLoop(
            perception, overlay, FakeCompositorBridge([WIN]), FakePolicy(), SETTLE, tone=tone
        )
        task = asyncio.create_task(loop.run(Plan("g", [text_step("7")]), APP))
        await settle()
        assert overlay.moods[-1] == "pointing"
        perception.texts[DISPLAY] = "5"  # the wrong key
        await asyncio.sleep(0.3)
        assert overlay.moods[-1] == mood and marker in overlay.calls[-1][2]
        perception.texts[DISPLAY] = ""  # undone: back to pointing
        await asyncio.sleep(0.3)
        assert overlay.moods[-1] == "pointing"
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_the_bro_is_happy_when_everything_is_done_and_only_if_asked_to_stay():
    elements = {CREATE: Rect(10, 20, 80, 30)}
    perception, overlay, loop, plan = build(elements, [step()])
    task = asyncio.create_task(loop.run(plan, APP))
    await settle()
    overlay.push("next")
    assert await asyncio.wait_for(task, 2) is Outcome.DONE
    assert "happy" not in overlay.moods  # the default is to just leave
    perception, overlay, loop, plan = build(
        elements, [step()], timing=Timing(poll=0.01, nudge=30.0, done_hold=0.05)
    )
    task = asyncio.create_task(loop.run(plan, APP))
    await settle()
    overlay.push("next")
    assert await asyncio.wait_for(task, 2) is Outcome.DONE
    assert overlay.moods[-1] == "happy" and overlay.calls[-2] == (
        "show_step",
        None,
        "That's all the steps.",
    )
    assert overlay.calls[-1] == ("hide",)
