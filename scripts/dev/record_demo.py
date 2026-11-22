"""Record the Calculator Show-me example as a GIF. Run inside scripts/dev/headless-shell.sh:

    YB_MONITOR=1280x1000 YB_ALLOWED='["org.gnome.Calculator"]' scripts/dev/headless-shell.sh /usr/bin/python3 scripts/dev/record_demo.py out.gif

Isolated shell, real gnome-calculator, the real step loop; the "user" clicks where the ring points.
"""

# ruff: noqa: E402, I001
import asyncio
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path[:0] = [os.path.join(ROOT, "tests", "fixtures"), os.path.join(ROOT, "src")]
import gi  # noqa: E402
import gi.events  # noqa: E402
from PIL import Image  # noqa: E402
from shellkit import Shell, find_pixels  # noqa: E402

from ya_bro import plans  # noqa: E402
from ya_bro.platform.gnome_adapters import (  # noqa: E402
    AtspiPerception,
    GnomeBridge,
    GnomeOverlay,
)
from ya_bro.policy import ShowMePolicy  # noqa: E402
from ya_bro.steps import StepLoop, Timing  # noqa: E402

APP = "org.gnome.Calculator"
OUT = sys.argv[1] if len(sys.argv) > 1 else "show-me-calculator.gif"
frames: list[tuple[Image.Image, int]] = []


def snap(sh, crop, ms):
    pb = sh.grab()
    img = Image.frombytes(
        "RGB" if pb.get_n_channels() == 3 else "RGBA",
        (pb.get_width(), pb.get_height()),
        pb.get_pixels(),
        "raw",
        "RGB" if pb.get_n_channels() == 3 else "RGBA",
        pb.get_rowstride(),
    ).convert("RGB")
    frames.append((img.crop(crop), ms))


BUTTON_BG = (0x3A, 0x3A, 0x52)  # .yabro-button in extension/stylesheet.css


def click_next(sh):
    """Press the bubble's Next button: the left end of the button row (Next, Repeat, Why?, Stop)."""
    px = find_pixels(sh.grab(), BUTTON_BG, 6)
    left = min(p[0] for p in px)
    ys = [p[1] for p in px if p[0] < left + 6]
    sh.click((left + 20) / sh.ratio, sum(ys) / len(ys) / sh.ratio)


async def main():
    env = dict(os.environ, GTK_A11Y="atspi")
    env.pop("DISPLAY", None)
    calc = subprocess.Popen(
        ["gnome-calculator"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    sh = Shell()
    sh.start_input()
    bridge = GnomeBridge(sh.conn)
    await asyncio.sleep(10)
    win = next(w for w in sh.windows() if w["app_id"] == APP)
    fx, fy, fw, fh = win["frame"]
    for _ in range(20):  # focus the window by clicking its empty display area
        sh.click(fx + fw // 2, fy + 150)
        await asyncio.sleep(0.5)
        if any(w["focused"] for w in sh.windows()):
            break
    else:
        raise SystemExit("calculator never took focus")
    plan, _app, _ = plans.load(os.path.join(ROOT, "examples", "plans", "calculator.toml"), APP)
    overlay = GnomeOverlay(sh.conn, bridge)
    loop = StepLoop(
        AtspiPerception(bridge, plan.extents_offset),
        overlay,
        bridge,
        ShowMePolicy(),
        Timing(poll=0.2),
    )
    # Wide enough for the bubble, which hangs below the target.
    crop = (fx - 40, fy - 20, fx + fw + 280, fy + fh + 110)
    snap(sh, crop, 1200)  # the app before the bro is there
    task = asyncio.create_task(loop.run(plan, APP))
    last = None
    for _ in range(len(plan.steps)):
        for _ in range(100):
            await asyncio.sleep(0.1)
            if overlay.last_target is not None and overlay.last_target != last:
                break
        await asyncio.sleep(0.5)
        target = overlay.last_target
        snap(sh, crop, 1600)  # ring and bubble on the step
        last = target
        sh.click(*target.center)  # the user presses the key the ring points at
        await asyncio.sleep(0.9)
        snap(sh, crop, 900)  # the key was pressed; the bubble still waits
        click_next(sh)
        await asyncio.sleep(0.4)  # let the click finish before moving away
        sh.move(fx - 60, fy + fh // 2)  # park the pointer: no tooltip over the keys
        await asyncio.sleep(0.6)
    await asyncio.wait_for(task, 20)
    await asyncio.sleep(1.5)
    sh.move(fx - 59, fy + fh // 2)  # force a repaint so the grab is not a stale frame
    await asyncio.sleep(0.5)
    print("overlay visible after the plan:", sh.state()["visible"], flush=True)
    snap(sh, crop, 2500)  # done: the bro leaves, the answer stays
    calc.terminate()
    imgs = [f for f, _ in frames]
    imgs[0].save(
        OUT,
        save_all=True,
        append_images=imgs[1:],
        duration=[d for _, d in frames],
        loop=0,
        optimize=True,
    )
    print("wrote", OUT, len(frames), "frames", flush=True)


asyncio.run(main(), loop_factory=gi.events.GLibEventLoopPolicy().new_event_loop)
