"""`broctl ask --pack workbench` on a real frame (#3): the workbench task walks through three
plain steps; real clicks on Next move through them and the plan finishes. Run in headless-shell.sh
with the docked app id allowed."""

import asyncio
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "..", "src")]
import gi  # noqa: E402
import gi.events  # noqa: E402
from shellkit import Shell  # noqa: E402

from ya_bro.platform.docked_overlay import APP_ID, DockedOverlay  # noqa: E402
from ya_bro.platform.gnome_show import run_pack  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}".rstrip(), flush=True)


def button(overlay, label):
    child = overlay._row.get_first_child()
    while child is not None:
        if child.get_label() == label:
            return child
        child = child.get_next_sibling()
    return None


async def click_next(sh, overlay):
    for _ in range(60):
        w = next((w for w in sh.windows() if w["app_id"] == APP_ID), None)
        b = button(overlay, "Next")
        if w and w["frame"][2] > 0 and b is not None and b.compute_bounds(overlay._win)[0]:
            break
        await asyncio.sleep(0.2)
    await asyncio.sleep(0.8)
    _ok, bb = button(overlay, "Next").compute_bounds(overlay._win)
    x = w["frame"][0] + int(bb.get_x() + bb.get_width() / 2)
    y = w["frame"][1] + int(bb.get_y() + bb.get_height() / 2)
    sh.move(x, y)
    await asyncio.sleep(0.3)
    sh.click(x, y)
    await asyncio.sleep(0.8)


async def main():
    sh = Shell()
    sh.start_input()
    overlay = DockedOverlay()
    shown, snippets = [], []
    real_show = overlay.show_step

    async def spy(target, text, buttons=(), mood="", snippet=""):
        shown.append(text)
        snippets.append(snippet)
        await real_show(target, text, buttons, mood, snippet)

    overlay.show_step = spy
    task = asyncio.create_task(run_pack("workbench", "start the cluster", overlay))
    for n in (1, 2, 3):
        for _ in range(60):
            if any(t.startswith(f"({n}/3)") for t in shown):
                break
            await asyncio.sleep(0.2)
        check(
            f"step {n} of 3 is shown", any(t.startswith(f"({n}/3)") for t in shown), str(shown[-1:])
        )
        await click_next(sh, overlay)
    check("the plan finishes after the third Next", await asyncio.wait_for(task, 30) == 0)
    check(
        "the commands are the pack's own", "./scripts/benchctl plan" in snippets, str(snippets[:1])
    )


asyncio.run(main(), loop_factory=gi.events.GLibEventLoopPolicy().new_event_loop)
sys.exit(0 if all(results) else 1)
