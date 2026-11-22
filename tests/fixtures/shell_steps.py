"""Show-me loop end to end in the headless shell: point, click where the ring points, advance, stop."""

import asyncio
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "..", "src")]
import gi  # noqa: E402
import gi.events  # noqa: E402
from shellkit import App, Shell, find_pixels, pump_until  # noqa: E402

from ya_bro import plans  # noqa: E402
from ya_bro.platform.gnome_adapters import (  # noqa: E402
    AtspiPerception,
    GnomeBridge,
    GnomeOverlay,
)
from ya_bro.policy import ShowMePolicy  # noqa: E402
from ya_bro.steps import Outcome, StepLoop, Timing  # noqa: E402

BUTTON_BG = (0x3A, 0x3A, 0x52)  # .yabro-button in extension/stylesheet.css
ALLOWED = "io.github.ahmedyousrisobhi.YaBroSteps"
OTHER = "io.github.ahmedyousrisobhi.YaBroOther"
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}".rstrip(), flush=True)


def inside(rect, pt):
    return rect and rect.x <= pt[0] < rect.x + rect.w and rect.y <= pt[1] < rect.y + rect.h


async def until(pred, limit=15.0):
    end = asyncio.get_running_loop().time() + limit
    while asyncio.get_running_loop().time() < end:
        if pred():
            return True
        await asyncio.sleep(0.05)
    return pred()


async def main():
    fixture = os.path.join(HERE, "apps", "steps_fixture.py")
    # Both windows open at the same spot: start the decoy first so the allowed one ends up on top.
    other = App(fixture, env={"STEPS_APP_ID": OTHER})
    await asyncio.sleep(5)
    allowed = App(fixture)
    sh = Shell()
    sh.start_input()
    bridge = GnomeBridge(sh.conn)
    perception = AtspiPerception(bridge)
    win = None
    for _ in range(300):
        ws = [w for w in sh.windows() if w["app_id"] == ALLOWED and w["frame"][2] > 0]
        if ws:
            win = ws[0]
            break
        await asyncio.sleep(0.1)
    check("allowed fixture window is reported", win is not None)
    check("other fixture window is not", not any(w["app_id"] == OTHER for w in sh.windows()))
    await asyncio.sleep(3)  # AT-SPI tree settles

    # Scope: the same role+name exists in both apps; only the allowed one is ever found.
    found = await perception.find(ALLOWED, "button", "Create")
    check("perceiver finds the allowed app's button", len(found) == 1, str(found))
    check(
        "perceiver finds nothing in the not-allowed app",
        await perception.find(OTHER, "button", "Create") == [],
    )
    check(
        "the ref locates while its window is in scope",
        found and await perception.locate(found[0]) is not None,
    )

    fx, fy, fw, fh = win["frame"]
    for _ in range(10):  # focus the window without hitting the button (the margin, not the centre)
        sh.click(fx + 20, fy + 150)
        await asyncio.sleep(0.5)
        if any(w["focused"] for w in sh.windows()):
            break
    check("allowed window is focused", any(w["focused"] for w in sh.windows()))

    plan, _app, _ = plans.load(os.path.join(HERE, "steps_plan.toml"), ALLOWED)
    texts = []

    class Recording(GnomeOverlay):
        async def show_step(self, target, bubble_text, buttons=()):
            texts.append(bubble_text)
            await super().show_step(target, bubble_text, buttons)

    overlay = Recording(sh.conn, bridge)
    loop = StepLoop(perception, overlay, bridge, ShowMePolicy(), Timing(poll=0.2))
    task = asyncio.create_task(loop.run(plan, ALLOWED))

    check("ring shown on step 1", await until(lambda: overlay.last_target is not None))
    t1 = overlay.last_target
    check("overlay visible", sh.state()["visible"] is True)
    # Next before doing the step: the bro asks instead of skipping.
    px = find_pixels(sh.grab(), BUTTON_BG, 6)
    left = min(p[0] for p in px)
    ys = [p[1] for p in px if p[0] < left + 6]
    sh.click((left + 20) / sh.ratio, sum(ys) / len(ys) / sh.ratio)
    check(
        "Next on an undone step asks first",
        await until(lambda: any("don't see" in t for t in texts)),
        str(texts[-1:]),
    )
    check("it stayed on step 1", not any(t.startswith("(2/2)") for t in texts))
    sh.click(*t1.center)  # the user follows the ring
    # Confirm sits where Create was, so the proof of advance is the narration, not the rectangle.
    check(
        "step 2 shown after the click (verified by the screen)",
        await until(lambda: any(t.startswith("(2/2)") for t in texts)),
        str(texts[-1:]),
    )
    t2 = overlay.last_target
    sh.click(*t2.center)
    outcome = await asyncio.wait_for(task, 20)
    check("plan finishes", outcome is Outcome.DONE, str(outcome))
    await asyncio.sleep(0.5)
    check("overlay hidden at the end", sh.state()["visible"] is False)

    # Stop button: a plan whose step never verifies; the bubble's Stop ends it and hides the overlay.
    # (The stop key itself is covered by the extension tests; key injection is flaky, S1.)
    plan2, _, _ = plans.load(os.path.join(HERE, "steps_plan.toml"), ALLOWED)
    plan2.steps[:] = [plan2.steps[1].__class__(intent="x", narration="Look here.", target=None)]
    task = asyncio.create_task(loop.run(plan2, ALLOWED))
    check("bubble-only step shown", await until(lambda: sh.state()["visible"] is True, 10))
    # The buttons sit side by side (Next, Repeat, Why, Stop): click just inside the right edge of the row.
    await asyncio.sleep(1.0)
    px = find_pixels(sh.grab(), BUTTON_BG, 6)
    check("bubble buttons are drawn", len(px) > 200, str(len(px)))
    if px:
        right = max(p[0] for p in px)
        ys = [p[1] for p in px if p[0] > right - 6]
        sh.click((right - 20) / sh.ratio, sum(ys) / len(ys) / sh.ratio)
    outcome = await asyncio.wait_for(task, 10)
    check("Stop button ends the loop", outcome is Outcome.STOPPED, str(outcome))
    check("overlay hidden after stop", sh.state()["visible"] is False)
    allowed.close()
    other.close()


asyncio.run(main(), loop_factory=gi.events.GLibEventLoopPolicy().new_event_loop)
pump_until(lambda: True, 0)
sys.exit(0 if all(results) else 1)
