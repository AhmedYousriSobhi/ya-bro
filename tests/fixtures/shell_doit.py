"""Do-it on the real Calculator (#27): the bro presses 7 x 6 = itself, with no injected click.
Run in headless-shell.sh."""

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
    AtspiActuator,
    AtspiPerception,
    GnomeBridge,
    GnomeOverlay,
)
from ya_bro.policy import LocalPolicy  # noqa: E402
from ya_bro.steps import Outcome, StepLoop, Timing  # noqa: E402
from ya_bro.types import ElementRef, Step  # noqa: E402

APP = "org.gnome.Calculator"
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}".rstrip(), flush=True)


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
        sh.click(fx + fw // 2, fy + 150)  # focus via the empty display area (the only click)
        await asyncio.sleep(0.5)
        if any(w["focused"] for w in sh.windows()):
            break
    plan, _app, _ = plans.load(
        os.path.join(HERE, "..", "..", "examples", "plans", "calculator.toml"), APP
    )
    perception = AtspiPerception(bridge, plan.extents_offset)
    actuator = AtspiActuator(perception)
    overlay = GnomeOverlay(sh.conn, bridge)

    async def display():
        (ref,) = (await perception.find(APP, "text"))[:1] or [None]
        return await perception.read_text(ref) if ref else ""

    loop = StepLoop(
        perception,
        overlay,
        bridge,
        LocalPolicy(do_it=True),
        Timing(poll=0.2, act_pause=0.5, verify=4.0),
        actuator=actuator,
    )
    outcome = await asyncio.wait_for(loop.run(plan, APP), 60)
    check("the plan finishes with no user click", outcome is Outcome.DONE, str(outcome))
    check("the display shows 42", "42" in await display(), await display())

    unknown = Step("x", "n", ElementRef(APP, "button", "No such key"))
    check("a missing control is not pressed", await actuator.act(unknown) is False)
    secret = Step("x", "n", ElementRef(APP, "password text", ""))
    check("a password field is never acted on", await actuator.act(secret) is False)
    calc.terminate()


asyncio.run(main(), loop_factory=gi.events.GLibEventLoopPolicy().new_event_loop)
sys.exit(0 if all(results) else 1)
