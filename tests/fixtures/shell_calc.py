"""Wrong key then the right one on the real Calculator (#74). Run in headless-shell.sh."""

import asyncio
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "..", "src")]
import gi  # noqa: E402
import gi.events  # noqa: E402
from shellkit import Shell  # noqa: E402

from ya_bro import plans  # noqa: E402
from ya_bro.platform.gnome_adapters import (  # noqa: E402
    AtspiPerception,
    GnomeBridge,
    GnomeOverlay,
)
from ya_bro.policy import ShowMePolicy  # noqa: E402
from ya_bro.steps import Outcome, StepLoop, Timing  # noqa: E402

APP = "org.gnome.Calculator"
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}".rstrip(), flush=True)


async def until(pred, limit=15.0):
    end = asyncio.get_running_loop().time() + limit
    while asyncio.get_running_loop().time() < end:
        if pred():
            return True
        await asyncio.sleep(0.1)
    return pred()


async def main():
    env = dict(os.environ, GTK_A11Y="atspi")
    env.pop("DISPLAY", None)
    calc = subprocess.Popen(
        ["gnome-calculator"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    sh = Shell()
    sh.start_input()
    bridge = GnomeBridge(sh.conn)
    await asyncio.sleep(9)
    win = next(w for w in sh.windows() if w["app_id"] == APP)
    fx, fy, fw, _fh = win["frame"]
    for _ in range(20):
        sh.click(fx + fw // 2, fy + 150)  # focus via the empty display area
        await asyncio.sleep(0.5)
        if any(w["focused"] for w in sh.windows()):
            break
    plan, _app, _ = plans.load(
        os.path.join(HERE, "..", "..", "examples", "plans", "calculator.toml"), APP
    )
    perception = AtspiPerception(bridge, plan.extents_offset)
    texts = []

    class Recording(GnomeOverlay):
        async def show_step(self, target, bubble_text, buttons=()):
            texts.append(bubble_text)
            await super().show_step(target, bubble_text, buttons)

    overlay = Recording(sh.conn, bridge)
    loop = StepLoop(perception, overlay, bridge, ShowMePolicy(), Timing(poll=0.2, settle=0.8))
    task = asyncio.create_task(loop.run(plan, APP))
    check("step 1 shown", await until(lambda: any(t.startswith("(1/4)") for t in texts)))

    async def press(name):
        ref = (await perception.find(APP, "button", name))[0]
        sh.click(*(await perception.locate(ref)).center)
        await asyncio.sleep(0.4)

    await press("5")  # the wrong key
    check(
        "a wrong key is noticed",
        await until(lambda: any("I warned you" in t for t in texts)),
        str(texts[-1:]),
    )
    check("and it did not advance", not any(t.startswith("(2/4)") for t in texts))
    await press("C")  # undo
    n = len(texts)
    await asyncio.sleep(1.5)
    check(
        "clearing it removes the complaint", texts[-1] == "(1/4) Press 7.", str(texts[n - 1 :][-2:])
    )
    await press("7")
    check(
        "the right key advances by itself",
        await until(lambda: any(t.startswith("(2/4)") for t in texts)),
    )
    await press("×")
    await press("6")
    await press("=")
    outcome = await asyncio.wait_for(task, 20)
    check("plan finishes", outcome is Outcome.DONE, str(outcome))
    calc.terminate()


asyncio.run(main(), loop_factory=gi.events.GLibEventLoopPolicy().new_event_loop)
sys.exit(0 if all(results) else 1)
