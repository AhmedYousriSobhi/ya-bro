"""The docked overlay on a real frame (#3): bubble text, real clicks on its buttons, Stop, RTL.
Run in headless-shell.sh with the docked app id allowed."""

import asyncio
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "..", "src")]
import gi  # noqa: E402
import gi.events  # noqa: E402
from shellkit import Shell  # noqa: E402

from ya_bro.platform.docked_overlay import APP_ID, DockedOverlay  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}".rstrip(), flush=True)


async def until(pred, limit=15.0):
    end = asyncio.get_running_loop().time() + limit
    while asyncio.get_running_loop().time() < end:
        if await pred():
            return True
        await asyncio.sleep(0.2)
    return await pred()


async def main():
    sh = Shell()
    sh.start_input()
    overlay = DockedOverlay()
    got = []

    async def collect():
        async for e in overlay.events():
            got.append(e)

    task = asyncio.create_task(collect())
    await overlay.show_step(None, "(1/2) Press 7.", ("next", "why", "stop"))

    async def window():
        return any(w["app_id"] == APP_ID for w in sh.windows())

    check("the bubble window appears", await until(window))
    await asyncio.sleep(2)
    # The window lives in this process, so AT-SPI would be asking ourselves: ask GTK where the
    # buttons are instead (position inside the window) and the Shell where the window is.

    def buttons():
        out, child = {}, overlay._row.get_first_child()
        while child is not None:
            out[child.get_label()] = child
            child = child.get_next_sibling()
        return out

    check(
        "the three buttons are there",
        sorted(buttons()) == ["Next", "Stop", "Why?"],
        str(sorted(buttons())),
    )
    win = next(w for w in sh.windows() if w["app_id"] == APP_ID)
    for _ in range(10):  # the first press after a window opens is spent on activating it
        sh.click(win["frame"][0] + 20, win["frame"][1] + 5)
        await asyncio.sleep(0.3)

    async def press(name):
        ok, bounds = buttons()[name].compute_bounds(overlay._win)
        w = next(w for w in sh.windows() if w["app_id"] == APP_ID)
        x = w["frame"][0] + int(bounds.get_x() + bounds.get_width() / 2)
        y = w["frame"][1] + int(bounds.get_y() + bounds.get_height() / 2)
        print(
            "      ..",
            name,
            "frame",
            w["frame"],
            "buffer",
            w["buffer"],
            "bounds",
            bounds.get_x(),
            bounds.get_y(),
            bounds.get_width(),
            bounds.get_height(),
            flush=True,
        )
        sh.move(x, y)
        await asyncio.sleep(0.3)
        sh.click(x, y)

    await press("Why?")
    check("a click on Why? is an event", await until(lambda: _has(got, "why")), str(got))
    await overlay.show_step(None, "من فضلك اضغط على الزر", ("next", "stop"))
    await asyncio.sleep(1)
    await press("Stop")
    check("a click on Stop is an event", await until(lambda: _has(got, "stop")), str(got))
    await overlay.hide()
    check("hide removes the window", await until(lambda: _gone(sh)))
    task.cancel()


async def _has(got, e):
    return e in got


async def _gone(sh):
    return not any(w["app_id"] == APP_ID for w in sh.windows())


asyncio.run(main(), loop_factory=gi.events.GLibEventLoopPolicy().new_event_loop)
sys.exit(0 if all(results) else 1)
