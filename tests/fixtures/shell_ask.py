"""The ask window on a real frame (#3): a real click on Go returns the text, Cancel returns None,
an empty field returns None. Run in headless-shell.sh with the docked app id allowed."""

import asyncio
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "..", "src")]
import gi  # noqa: E402
import gi.events  # noqa: E402
from shellkit import Shell  # noqa: E402

from ya_bro.platform.ask_window import AskWindow  # noqa: E402
from ya_bro.platform.docked_overlay import APP_ID  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}".rstrip(), flush=True)


async def click_widget(sh, win, widget):
    for _ in range(40):  # wait until the window is mapped and laid out
        w = next((w for w in sh.windows() if w["app_id"] == APP_ID), None)
        if w and w["frame"][2] > 0 and widget.compute_bounds(win.win)[0]:
            break
        await asyncio.sleep(0.2)
    await asyncio.sleep(0.5)
    _ok, b = widget.compute_bounds(win.win)
    x = w["frame"][0] + int(b.get_x() + b.get_width() / 2)
    y = w["frame"][1] + int(b.get_y() + b.get_height() / 2)
    for _ in range(6):  # the first press after a window opens only activates it
        sh.move(x, y)
        await asyncio.sleep(0.3)
        sh.click(x, y)
        await asyncio.sleep(0.3)


async def main():
    sh = Shell()
    sh.start_input()

    ask = AskWindow()
    ask.entry.set_text("multiply 7 by 6")
    task = asyncio.create_task(ask.get())
    await click_widget(sh, ask, ask.go)
    check("a click on Go returns the text", await asyncio.wait_for(task, 20) == "multiply 7 by 6")

    ask = AskWindow()
    ask.entry.set_text("   ")
    task = asyncio.create_task(ask.get())
    await click_widget(sh, ask, ask.go)
    check("an empty field returns nothing", await asyncio.wait_for(task, 20) is None)

    ask = AskWindow()
    ask.entry.set_text("something")
    task = asyncio.create_task(ask.get())
    await asyncio.sleep(2)
    ask.win.close()
    check("closing the window cancels", await asyncio.wait_for(task, 10) is None)


asyncio.run(main(), loop_factory=gi.events.GLibEventLoopPolicy().new_event_loop)
sys.exit(0 if all(results) else 1)
