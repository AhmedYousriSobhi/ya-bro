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
WHITE = (240, 241, 247)
GREY = (170, 176, 198)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
CAPTION_H = 92
frames: list[tuple[Image.Image, int]] = []
SIZE = [0, 0]


def captioned(img, narrator, aside=""):
    """The narrator track: what is happening, in the voice of a nature documentary."""
    w, h = img.size
    out = Image.new("RGB", (w, h + CAPTION_H), BAR)
    out.paste(img, (0, 0))
    d = ImageDraw.Draw(out)
    d.rectangle((0, h, w, h + 3), fill=AMBER)
    big, small = ImageFont.truetype(FONT_BOLD, 21), ImageFont.truetype(FONT, 17)
    y = h + (22 if aside else 34)
    d.text(((w - d.textlength(narrator, font=big)) / 2, y), narrator, font=big, fill=WHITE)
    if aside:
        d.text(((w - d.textlength(aside, font=small)) / 2, y + 34), aside, font=small, fill=AMBER)
    return out


def snap(sh, crop, ms, narrator, aside=""):
    pb = sh.grab()
    mode = "RGB" if pb.get_n_channels() == 3 else "RGBA"
    img = Image.frombytes(
        mode, (pb.get_width(), pb.get_height()), pb.get_pixels(), "raw", mode, pb.get_rowstride()
    ).convert("RGB")
    frames.append((captioned(img.crop(crop), narrator, aside), ms))
    SIZE[:] = frames[0][0].size


def title_card(ms):
    w, h = SIZE
    img = Image.new("RGB", (w, h), BAR)
    d = ImageDraw.Draw(img)
    big, small = ImageFont.truetype(FONT_BOLD, 64), ImageFont.truetype(FONT, 22)
    for text, font, y, fill in (
        ("Ya-Bro", big, h * 0.34, WHITE),
        ("Today's task: 7 \u00d7 6.", small, h * 0.52, GREY),
        ("What could possibly go wrong?", small, h * 0.52 + 34, AMBER),
    ):
        d.text(((w - d.textlength(text, font=font)) / 2, y), text, font=font, fill=fill)
    d.rectangle((w * 0.38, h * 0.47, w * 0.62, h * 0.47 + 4), fill=AMBER)
    frames.insert(0, (img, ms))


def save(path):
    """One shared 256-colour palette for every frame: crisp, no flicker, no resizing."""
    imgs = [f for f, _ in frames]
    w, h = imgs[0].size
    mosaic = Image.new("RGB", (w, h * len(imgs)))
    for i, im in enumerate(imgs):
        mosaic.paste(im, (0, i * h))
    pal = mosaic.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    out = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in imgs]
    out[0].save(
        path,
        save_all=True,
        append_images=out[1:],
        duration=[d for _, d in frames],
        loop=0,
        optimize=True,
        disposal=1,
    )


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
    crop = (fx - 16, fy - 12, fx + fw + 230, fy + fh + 78)

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
    snap(sh, crop, 2400, "The bro points at the key it wants.", "Press 7.")
    await press("5")  # on purpose: the wrong key
    await until(lambda: any("warned" in t or "Wrong one" in t or "Bro..." in t for t in texts))
    await asyncio.sleep(0.6)
    snap(sh, crop, 3400, "You press 5 instead. Bold choice.", "The bro is not amused.")
    overlay._queue.put_nowait("why")  # the Why? button (same event the extension sends)
    await until(lambda: any("That's the mistake" in t for t in texts))
    await asyncio.sleep(0.6)
    snap(sh, crop, 4200, "Why? The bro explains your mistake.", "Gently. Mostly.")
    await press("C")
    await until(lambda: texts[-1] == "(1/4) Press 7.")
    await asyncio.sleep(0.8)
    snap(sh, crop, 2200, "You undo it. The bro forgives you.", "Probably.")
    await press("7")
    await at_step(2)
    snap(sh, crop, 2200, "You press 7. The bro moves on by itself.", "No Next button needed.")
    await press("\u00d7")
    await at_step(3)
    await press("6")
    await at_step(4)
    snap(sh, crop, 1800, "Then \u00d7 and 6. One step at a time.", "Almost there.")
    await press("=")
    await asyncio.wait_for(task, 20)
    await asyncio.sleep(1.5)
    sh.move(fx - 59, fy + fh // 2)  # force a repaint so the grab is not a stale frame
    await asyncio.sleep(0.5)
    print("overlay visible after the plan:", sh.state()["visible"], flush=True)
    snap(sh, crop, 3600, "7 \u00d7 6 = 42. The bro leaves.", "You owe it a coffee.")
    calc.terminate()
    title_card(2600)
    save(OUT)
    print("wrote", OUT, len(frames), "frames", SIZE, flush=True)


asyncio.run(main(), loop_factory=gi.events.GLibEventLoopPolicy().new_event_loop)
