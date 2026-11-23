"""Real Mutter idle time through GnomeIdleSource, then the host on it (#9). Run in headless-shell.sh."""

import asyncio
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "..", "src")]
import gi  # noqa: E402
import gi.events  # noqa: E402
from shellkit import Shell  # noqa: E402

from ya_bro import struggle  # noqa: E402
from ya_bro.platform.gnome_idle import GnomeIdleSource  # noqa: E402
from ya_bro.struggle import Detector, Observation  # noqa: E402
from ya_bro.struggle_host import StruggleHost  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}".rstrip(), flush=True)


async def main():
    sh = Shell()
    sh.start_input()
    idle = GnomeIdleSource()
    sh.tap(0x20)
    await asyncio.sleep(0.5)
    fresh = await idle.idle_seconds()
    check("right after a key the idle time is small", fresh < 1.5, f"{fresh:.2f} s")
    await asyncio.sleep(4)
    later = await idle.idle_seconds()
    check("it grows while nothing is pressed", 3.5 <= later < 8, f"{later:.2f} s")
    sh.tap(0x20)
    await asyncio.sleep(0.5)
    again = await idle.idle_seconds()
    check("and drops back on the next key", again < 1.5, f"{again:.2f} s")

    # The host on the real idle clock: a failed command, then a real pause of 3 s counts as one.
    struggle.IDLE_SECONDS = 3.0  # the real 20 s would make the test slow, not different
    det = Detector(lambda: asyncio.get_running_loop().time() + 1e6)
    det.opt_in("workbench")
    det.set_sensitivity(4)
    det.observe(Observation(det._clock(), "workbench", "command_exit", "benchctl", 1))
    log, offers = [], []

    async def focused():
        return "workbench"

    host = StruggleHost(
        det, {}, idle=idle, focused_app=focused, on_offer=offers.append,
        sink=lambda name, **f: log.append((name, f)), clock=det._clock,
    )  # fmt: skip
    task = asyncio.create_task(host.run())
    sh.tap(0x20)
    await asyncio.sleep(7)
    task.cancel()
    signals = [f["signal"] for n, f in log if n == "struggle_signal"]
    check(
        "a real pause after a failure is the idle-in-context signal",
        "idle_in_context" in signals,
        str(log),
    )
    check(
        "and, once, with an offer at that breakpoint",
        len(offers) == 1 and signals.count("idle_in_context") == 1,
        str(log),
    )


asyncio.run(main(), loop_factory=gi.events.GLibEventLoopPolicy().new_event_loop)
sys.exit(0 if all(results) else 1)
