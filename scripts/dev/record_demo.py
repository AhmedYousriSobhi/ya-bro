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
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from shellkit import Shell  # noqa: E402

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
BG = (27, 29, 42)
BAR = (20, 22, 31)
AMBER = (245, 165, 36)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
CAPTION_H = 76
SCALE = 1.4  # the bubble text is small at 1:1
frames: list[tuple[Image.Image, int]] = []
SIZE = [0, 0]


def captioned(img, caption):
    w, h = img.size
    out = Image.new("RGB", (w, h + CAPTION_H), BAR)
    out.paste(img, (0, 0))
    d = ImageDraw.Draw(out)
    d.rectangle((0, h, w, h + 3), fill=AMBER)
    font = ImageFont.truetype(FONT_BOLD, 24)
    tw = d.textlength(caption, font=font)
    d.text(((w - tw) / 2, h + 24), caption, font=font, fill=(240, 241, 247))
    return out


def snap(sh, crop, ms, caption):
    pb = sh.grab()
    mode = "RGB" if pb.get_n_channels() == 3 else "RGBA"
    img = Image.frombytes(
        mode, (pb.get_width(), pb.get_height()), pb.get_pixels(), "raw", mode, pb.get_rowstride()
    ).convert("RGB")
    shot = img.crop(crop)
    shot = shot.resize((int(shot.width * SCALE), int(shot.height * SCALE)), Image.LANCZOS)
    frames.append((captioned(shot, caption), ms))
    SIZE[:] = frames[0][0].size


def title_card(ms):
    w, h = SIZE
    img = Image.new("RGB", (w, h), BAR)
    d = ImageDraw.Draw(img)
    big, small = ImageFont.truetype(FONT_BOLD, 72), ImageFont.truetype(FONT, 28)
    for text, font, y, fill in (
        ("Ya-Bro", big, h * 0.34, (240, 241, 247)),
        ("walks you through the real app,", small, h * 0.54, (180, 185, 205)),
        ("one step at a time.", small, h * 0.54 + 42, (180, 185, 205)),
    ):
        d.text(((w - d.textlength(text, font=font)) / 2, y), text, font=font, fill=fill)
    d.rectangle((w * 0.38, h * 0.50, w * 0.62, h * 0.50 + 4), fill=AMBER)
    frames.insert(0, (img, ms))


async def main():
    env = dict(os.environ, GTK_A11Y="atspi")
    env.pop("DISPLAY", None)
    # A plain dark desktop: no wallpaper to distract from the app.
    for key, val in (
        ("picture-options", "none"),
        ("primary-color", "#1b1d2a"),
        ("secondary-color", "#1b1d2a"),
    ):
        subprocess.run(["gsettings", "set", "org.gnome.desktop.background", key, val], check=False)
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
    perception = AtspiPerception(bridge, plan.extents_offset)
    texts: list[str] = []

    class Recording(GnomeOverlay):
        async def show_step(self, target, bubble_text, buttons=()):
            texts.append(bubble_text)
            await super().show_step(target, bubble_text, buttons)

    overlay = Recording(sh.conn, bridge, avatar=False)  # the bro has no shape yet
    loop = StepLoop(perception, overlay, bridge, ShowMePolicy(), Timing(poll=0.2, settle=0.8))
    crop = (fx - 24, fy - 16, fx + fw + 270, fy + fh + 84)

    async def until(pred, limit=15.0):
        end = asyncio.get_running_loop().time() + limit
        while asyncio.get_running_loop().time() < end:
            if pred():
                return True
            await asyncio.sleep(0.1)
        return pred()

    async def press(name):
        ref = (await perception.find(APP, "button", name))[0]
        sh.click(*(await perception.locate(ref)).center)
        await asyncio.sleep(0.4)  # let the click finish before moving away
        sh.move(fx - 60, fy + fh // 2)  # park the pointer: no tooltip over the keys

    async def at_step(n):
        await until(lambda: any(t.startswith(f"({n}/4)") for t in texts))
        await asyncio.sleep(0.6)

    task = asyncio.create_task(loop.run(plan, APP))
    await at_step(1)
    snap(sh, crop, 2200, "It points at the real key")
    await press("5")  # on purpose: the wrong key
    await until(
        lambda: any("I warned you" in t or "Wrong one" in t or "Bro..." in t for t in texts)
    )
    await asyncio.sleep(0.6)
    snap(sh, crop, 3000, "Press the wrong one and it notices")
    await press("C")
    await asyncio.sleep(1.0)
    await press("7")
    await at_step(2)
    snap(sh, crop, 2000, "Right key: it moves on by itself")
    for step, key in ((2, "×"), (3, "6")):
        await press(key)
        await at_step(step + 1)
        snap(sh, crop, 1800, f"Step {step + 1} of 4")
    await press("=")
    await asyncio.wait_for(task, 20)
    await asyncio.sleep(1.5)
    sh.move(fx - 59, fy + fh // 2)  # force a repaint so the grab is not a stale frame
    await asyncio.sleep(0.5)
    print("overlay visible after the plan:", sh.state()["visible"], flush=True)
    snap(sh, crop, 3000, "7 × 6 = 42. The bro leaves")
    calc.terminate()
    title_card(2200)
    imgs = [f.quantize(colors=96, method=Image.Quantize.MEDIANCUT) for f, _ in frames]
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
