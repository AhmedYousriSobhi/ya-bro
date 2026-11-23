"""The offer bubble on a real frame (ADR-0010 §4). Run in headless-shell.sh with the system python3.

A real extension draws the bubble; the real `StruggleHost`, `Detector`, `OfferBubble` and persona
drive it. Each answer is a real pointer click on the button's pixels, and the check is the
detector's own state afterwards: yes, no, two noes in a row (the app goes quiet), "not for this
app", and a bubble nobody answers. `YB_MUTATE=swap` wires the Yes and No buttons the wrong way
round in the presenter, which the clicks must catch (tests/test_gnome_offer.py runs both).
"""

import asyncio
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "..", "src")]
import gi.events  # noqa: E402
from shellkit import Shell, find_pixels  # noqa: E402

from ya_bro import offers  # noqa: E402
from ya_bro.persona import Persona  # noqa: E402
from ya_bro.platform.gnome_adapters import GnomeBridge, GnomeOverlay  # noqa: E402
from ya_bro.struggle import OFFER_COOLDOWN, Detector, Observation, Signal  # noqa: E402
from ya_bro.struggle_host import StruggleHost  # noqa: E402

BUTTON_BG = (0x3A, 0x3A, 0x52)  # .yabro-button in extension/stylesheet.css
APP = "workbench"
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}".rstrip(), flush=True)


class Clock:
    t = time.time()

    def __call__(self):
        return self.t


class Feed:
    """A shell hook the test types into."""

    def __init__(self):
        self.q = asyncio.Queue()

    def fail(self, n=3):
        for _ in range(n):
            self.q.put_nowait({"argv0": "benchctl", "exit": 1, "ms": 5, "ts": 0, "tty": "pts/1"})

    async def events(self):
        while True:
            yield await self.q.get()


async def until(pred, limit=25.0):
    end = asyncio.get_running_loop().time() + limit
    while asyncio.get_running_loop().time() < end:
        if pred():
            return True
        await asyncio.sleep(0.1)
    return pred()


def clusters(sh):
    """The button pixels in the bubble as left-to-right (x0, x1, y) runs, in logical pixels."""
    bx, by, bw, bh = sh.state()["bubble"]
    r = sh.ratio
    pb = sh.grab()
    pts = find_pixels(
        pb, BUTTON_BG, 6, rows=range(int(by * r), int((by + bh) * r)),
        cols=range(int(bx * r), min(pb.get_width(), int((bx + bw) * r))),
    )  # fmt: skip
    xs = sorted({x for x, _y in pts})
    runs = []
    for x in xs:
        if runs and x - runs[-1][1] <= 3:
            runs[-1][1] = x
        else:
            runs.append([x, x])
    ys = [y for _x, y in pts]
    y = sum(ys) / len(ys) / r if ys else 0
    return [(a / r, b / r, y) for a, b in runs]


async def main():
    sh = Shell()
    sh.start_input()
    clock, feed, log, accepted = Clock(), Feed(), [], []
    state = os.path.join(tempfile.mkdtemp(), "struggle.json")
    det = Detector(clock, __import__("pathlib").Path(state))
    det.opt_in(APP)
    overlay = GnomeOverlay(sh.conn, GnomeBridge(sh.conn))
    bubble = offers.OfferBubble(
        det, overlay, Persona(humour=1), on_accept=accepted.append, fade=60.0, say_for=0.8
    )
    if os.environ.get("YB_MUTATE") == "swap":  # the bug the test must catch
        offers.ANSWERS.update({"yes": "no", "no": "yes"})
    host = StruggleHost(
        det, {"benchctl": APP}, shell=feed, clock=clock,
        sink=lambda n, **f: log.append((n, f)), present=bubble.present,
    )  # fmt: skip
    task = asyncio.create_task(host.run())

    async def round_(index, label, wait_clear=True):
        """Three failures, wait for the bubble, click button `index`, wait for the answer."""
        before = sum(det.stats().values())
        feed.fail()
        shown = await until(lambda: sh.state()["visible"] and bool(sh.state()["bubble"][2]))
        check(f"{label}: the bubble appears after three failures", shown)
        if not shown:
            st = det._apps[APP]
            print(
                "DEBUG",
                det.score(APP),
                det.theta,
                clock.t - det._last_offer,
                len(det._offers),
                st.suppressed,
                st.quiet_until - clock.t,
                clock.t - st.breakpoint,
                det._pending,
                flush=True,
            )
        await asyncio.sleep(0.7)
        runs = clusters(sh)
        check(f"{label}: three buttons are drawn", len(runs) == 3, f"{len(runs)} runs {runs}")
        if len(runs) != 3:
            return False
        a, b, y = runs[index]
        sh.click((a + b) / 2, y)
        answered = await until(lambda: sum(det.stats().values()) > before)
        check(f"{label}: the click reaches the detector", answered, str(det.stats()))
        if wait_clear:
            gone = await until(lambda: not sh.state()["visible"])
            check(f"{label}: the screen is clear afterwards", gone)
        return answered

    def next_offer_due(extra=0.0):
        clock.t += OFFER_COOLDOWN + 1 + extra
        det.observe(Observation(clock.t, APP, "context"))  # earlier "no"s no longer apply

    # 1. No: counted, and that signal stays quiet
    await round_(1, "No")
    check(
        "No is one soft decline",
        det.stats()["no"] == 1 and det.stats()["yes"] == 0,
        str(det.stats()),
    )
    check(
        "No leaves the app watched and not yet quiet",
        det.is_watching(APP) and not det.is_quiet(APP),
    )

    # 2. a second No in a row: the app goes quiet for 30 minutes
    next_offer_due()
    await round_(1, "second No")
    check("two Noes in a row silence the app", det.stats()["no"] == 2 and det.is_quiet(APP))

    # 3. Yes after the quiet time: counted, the hand-over fires, the score clears
    next_offer_due(30 * 60)
    await round_(0, "Yes")
    check(
        "Yes is counted and hands over",
        det.stats()["yes"] == 1 and len(accepted) == 1,
        str(det.stats()),
    )
    check("Yes clears the score", det.score(APP) == 0.0)

    # 4. a bubble nobody answers fades and is a soft decline
    next_offer_due(30 * 60)  # (the hourly cap of 3 counts on this fake clock too)
    bubble._fade = 3.0
    feed.fail()
    await until(lambda: det.stats()["ignored"] == 1, 30)
    check("an unanswered bubble counts as ignored", det.stats()["ignored"] == 1, str(det.stats()))
    check("and the screen clears", await until(lambda: not sh.state()["visible"], 10))
    bubble._fade = 60.0
    # No, No and the fade are three soft refusals in a week: the weight halves (ADR-0010 §5).
    check("three soft refusals halve the weight", det.weight(APP, Signal.FAILING_COMMANDS) == 0.75)
    det.reset_learning(APP)

    # 5. Not for this app: opted out for good
    next_offer_due(30 * 60)
    await round_(2, "Not for this app")
    check(
        "Not for this app opts the app out", det.stats()["never"] == 1 and not det.is_watching(APP)
    )
    check("the answers are logged without content", all(
        set(f) <= {"signal", "app", "score", "outcome"} for _n, f in log
    ))  # fmt: skip

    # 6. never while a step loop shows something: the host takes no offer
    det.opt_in(APP)
    next_offer_due()
    host._busy = lambda: True
    feed.fail()
    await asyncio.sleep(3)
    check("nothing is drawn while a step loop is running", not sh.state()["visible"])
    host._busy = lambda: False
    check("and it is offered once the loop is over", await until(lambda: sh.state()["visible"]))
    sh.hide()
    task.cancel()
    return 0 if all(results) else 1


rc = asyncio.run(main(), loop_factory=gi.events.GLibEventLoopPolicy().new_event_loop)
sys.exit(rc)
