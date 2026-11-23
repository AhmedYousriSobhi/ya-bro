"""Record the Calculator Show-me example as an animated GIF. Run inside scripts/dev/headless-shell.sh:

    YB_MONITOR=2560x2000 YB_SCALE=2 YB_ALLOWED='["org.gnome.Calculator"]' \\
        scripts/dev/headless-shell.sh /usr/bin/python3 scripts/dev/record_demo.py out.gif

Isolated shell at 2x, real gnome-calculator, the real step loop, the real overlay and bro; the "user"
clicks where the ring points. Every beat is a real full-resolution screen grab; the GIF is a camera
moving over those grabs (centred wide shots, smooth zooms onto the bro's bubble so its words are
readable), with a title card and an end card that pop in. Nothing on screen is faked.
"""

# ruff: noqa: E402, I001
import asyncio
import os
import subprocess
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path[:0] = [os.path.join(ROOT, "tests", "fixtures"), os.path.join(ROOT, "src")]
import gi  # noqa: E402
import gi.events  # noqa: E402
from gi.repository import GLib  # noqa: E402
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
SCALE = float(os.environ.get("YB_SCALE", "2"))
BRO = Path(ROOT) / "docs" / "assets" / "identity" / "preview"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
INK = (14, 15, 24)
BAR = (20, 22, 33)
AMBER = (245, 165, 36)
WHITE = (240, 241, 247)
GREY = (160, 166, 190)

W, H = 560, 640  # the GIF
HEAD, CAP = 52, 116  # header and caption heights
VW, VH = W - 24, H - HEAD - CAP - 12  # the camera's window onto the screen
VX, VY = 12, HEAD + 4
FPS_MS = 50  # one animation frame
frames: list[tuple[Image.Image, int]] = []


# ---- composition ------------------------------------------------------------------------------

BG = None


def background() -> Image.Image:
    img = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img)
    for y in range(H):  # a quiet vertical gradient
        k = 1 - y / H
        d.line((0, y, W, y), fill=(int(18 + 8 * k), int(20 + 8 * k), int(32 + 12 * k)))
    return img


def header(img: Image.Image) -> None:
    d = ImageDraw.Draw(img)
    mark = Image.open(BRO / "bro-idle-240.png").convert("RGBA").resize((34, 34), Image.LANCZOS)
    img.paste(mark, (16, 9), mark)
    d.text((58, 10), "Ya-Bro", font=ImageFont.truetype(FONT_BOLD, 20), fill=WHITE)
    d.text((58, 32), "walks you through real apps", font=ImageFont.truetype(FONT, 12), fill=GREY)
    d.rounded_rectangle((W - 118, 14, W - 14, 38), radius=12, outline=AMBER, width=2)
    d.text((W - 105, 18), "real overlay", font=ImageFont.truetype(FONT_BOLD, 13), fill=AMBER)


def caption(img: Image.Image, narrator: str, aside: str = "") -> None:
    d = ImageDraw.Draw(img)
    d.rectangle((0, H - CAP, W, H), fill=BAR)
    d.rectangle((0, H - CAP, W, H - CAP + 3), fill=AMBER)
    big, small = ImageFont.truetype(FONT_BOLD, 24), ImageFont.truetype(FONT, 17)
    y = H - CAP + (24 if aside else 38)
    d.text(((W - d.textlength(narrator, font=big)) / 2, y), narrator, font=big, fill=WHITE)
    if aside:
        d.text(((W - d.textlength(aside, font=small)) / 2, y + 38), aside, font=small, fill=AMBER)


def compose(shot, rect, narrator="", aside="") -> Image.Image:
    """The canvas with the camera's view of the screen (rect in physical pixels) in the window."""
    global BG
    BG = BG or background()
    img = BG.copy()
    header(img)
    x0, y0, x1, y1 = rect
    view = shot["img"].resize((VW, VH), Image.LANCZOS, box=(x0, y0, x1, y1))
    mask = Image.new("L", (VW, VH), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, VW - 1, VH - 1), radius=16, fill=255)
    img.paste(view, (VX, VY), mask)
    ImageDraw.Draw(img).rounded_rectangle(
        (VX, VY, VX + VW - 1, VY + VH - 1), radius=16, outline=(60, 64, 92), width=1
    )
    caption(img, narrator, aside)
    return img


def fit(cx, cy, w, shot) -> tuple[float, float, float, float]:
    """A camera rectangle of this width (aspect of the window), centred, kept inside the screen."""
    sw, sh_ = shot["img"].size
    w = min(w, sw)
    h = w * VH / VW
    if h > sh_:
        w, h = sh_ * VW / VH, sh_
    x0 = min(max(cx - w / 2, 0), sw - w)
    y0 = min(max(cy - h / 2, 0), sh_ - h)
    return (x0, y0, x0 + w, y0 + h)


def wide(shot):
    """The whole Calculator, centred, with room for the bro on its left."""
    x, y, w, h = shot["window"]
    m = 56 * shot["ratio"]  # room for the bro, who sits up to 48 px left of the window
    width = max(w + 2 * m, (h + 2 * m) * VW / VH)
    return fit(x + w / 2, y + h / 2, width, shot)


def focus(shot):
    """The ring and the bubble (with the bro to its left), big enough to read."""
    r = shot["ratio"]
    parts = [p for p in (shot["target"], shot["bubble"]) if p]
    if shot["target"] is None:  # a bubble on its own: show the display it is talking about too
        x, y, w, h = shot["window"]
        parts.append((x, y, w, 0.42 * h))
    x0 = min(p[0] for p in parts) - 64 * r  # the bro sits 56 logical px left of the bubble
    y0 = min(p[1] for p in parts) - 24 * r
    x1 = max(p[0] + p[2] for p in parts) + 24 * r
    y1 = max(p[1] + p[3] for p in parts) + 24 * r
    return fit((x0 + x1) / 2, (y0 + y1) / 2, max(x1 - x0, (y1 - y0) * VW / VH, 360 * r), shot)


def ease(t: float) -> float:
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(4))


class Camera:
    def __init__(self):
        self.rect = None

    def hold(self, shot, rect, ms, narrator="", aside=""):
        """Stay on `rect` for ms (one long frame)."""
        frames.append((compose(shot, rect, narrator, aside), ms))
        self.rect = rect

    def move(self, shot, rect, narrator="", aside="", steps=8):
        """Glide from where the camera was to `rect`, one animation frame at a time."""
        start = self.rect or rect
        for i in range(1, steps + 1):
            frame = compose(shot, lerp(start, rect, ease(i / steps)), narrator, aside)
            frames.append((frame, FPS_MS))
        self.rect = rect


def pop_card(png: str, lines, ms_hold: int) -> None:
    """A card where the bro pops in (a little overshoot), then the words fade in."""
    bro = Image.open(BRO / png).convert("RGBA")
    big = ImageFont.truetype(FONT_BOLD, 56)
    mid, small = ImageFont.truetype(FONT, 21), ImageFont.truetype(FONT, 17)
    rows = ((lines[0], big, 78, WHITE), (lines[1], mid, 34, GREY), (lines[2], mid, 34, AMBER),
            (lines[3], small, 0, GREY))  # fmt: skip

    def card(scale: float, alpha: float) -> Image.Image:
        img = Image.new("RGB", (W, H), BAR)
        s = max(1, int(220 * scale))
        b = bro.resize((s, s), Image.LANCZOS)
        img.paste(b, ((W - s) // 2, 90 + (220 - s) // 2), b)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        td = ImageDraw.Draw(layer)
        y = 330
        for text, font, gap, fill in rows:
            x = (W - td.textlength(text, font=font)) / 2
            td.text((x, y), text, font=font, fill=(*fill, int(255 * alpha)))
            y += gap
        td.rectangle((W * 0.36, 318, W * 0.64, 322), fill=(*AMBER, int(255 * alpha)))
        img.paste(layer, (0, 0), layer)
        ImageDraw.Draw(img).rectangle((0, H - 4, W, H), fill=AMBER)
        return img

    for scale in (0.35, 0.7, 1.12, 1.04, 1.0):
        frames.append((card(scale, 0.0), FPS_MS))
    for alpha in (0.35, 0.7, 1.0):
        frames.append((card(1.0, alpha), FPS_MS))
    frames.append((card(1.0, 1.0), ms_hold))


def save(path: str) -> None:
    """One shared 192-colour palette for every frame: crisp, no flicker, small."""
    imgs = [f for f, _ in frames]
    sample = imgs[:: max(1, len(imgs) // 12)]
    mosaic = Image.new("RGB", (W, H * len(sample)))
    for i, im in enumerate(sample):
        mosaic.paste(im, (0, i * H))
    pal = mosaic.quantize(colors=192, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    out = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in imgs]
    out[0].save(
        path, save_all=True, append_images=out[1:], duration=[d for _, d in frames],
        loop=0, optimize=True, disposal=1,
    )  # fmt: skip


# ---- the real session -------------------------------------------------------------------------


def set_scale(sh, scale, width, height):
    """Mutter DisplayConfig: the monitor at this scale (the harness enables fractional scaling)."""
    dc = ("org.gnome.Mutter.DisplayConfig", "/org/gnome/Mutter/DisplayConfig")
    serial, monitors = sh.call(dc[0], "GetCurrentState", None, dc[0], dc[1])[:2]
    connector, modes = monitors[0][0][0], monitors[0][1]
    mode = next(m for m in modes if m[1] == width and m[2] == height)
    chosen = min(mode[5], key=lambda s: abs(s - scale))
    config = [(0, 0, chosen, 0, True, [(connector, mode[0], {})])]
    sh.call(
        dc[0], "ApplyMonitorsConfig",
        GLib.Variant("(uua(iiduba(ssa{sv}))a{sv})", (serial, 1, config, {})), dc[0], dc[1],
    )  # fmt: skip
    return chosen


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
    sh = Shell()
    mw, mh = (int(v) for v in os.environ.get("YB_MONITOR", "2560x2000").split("x"))
    if SCALE != 1:
        print("monitor scale:", set_scale(sh, SCALE, mw, mh), flush=True)
        await asyncio.sleep(2)
    sh.start_input()  # after the scale change: a reconfigured monitor invalidates earlier streams
    ratio = sh.ratio
    calc = subprocess.Popen(
        ["gnome-calculator"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
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
        async def show_step(self, target, bubble_text, buttons=(), mood=""):
            texts.append(bubble_text)
            await super().show_step(target, bubble_text, buttons, mood)

    overlay = Recording(sh.conn, bridge)  # the bro is drawn by the extension (ADR-0028)
    timing = Timing(poll=0.2, settle=0.8, done_hold=4.0)
    loop = StepLoop(perception, overlay, bridge, ShowMePolicy(), timing)

    def phys(rect):
        return tuple(v * ratio for v in rect) if rect else None

    def shot():
        """A real grab plus where things were, in physical pixels."""
        pb = sh.grab()
        mode = "RGB" if pb.get_n_channels() == 3 else "RGBA"
        size = (pb.get_width(), pb.get_height())
        img = Image.frombytes(mode, size, pb.get_pixels(), "raw", mode, pb.get_rowstride())
        w = next(w for w in sh.windows() if w["app_id"] == APP)["frame"]
        t = overlay.last_target
        state = sh.state()
        return {
            "img": img.convert("RGB"), "ratio": ratio, "window": phys(w),
            "target": phys((t.x, t.y, t.w, t.h)) if t else None,
            "bubble": phys(state["bubble"]) if state["visible"] else None,
        }  # fmt: skip

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
        await asyncio.sleep(0.7)

    shots: dict = {}
    task = asyncio.create_task(loop.run(plan, APP))
    await at_step(1)
    shots["step1"] = shot()
    await press("5")  # on purpose: the wrong key
    await until(lambda: any("warned" in t or "Wrong one" in t or "Bro..." in t for t in texts))
    await asyncio.sleep(0.8)
    shots["wrong"] = shot()
    overlay._queue.put_nowait("why")  # the Why? button (same event the extension sends)
    await until(lambda: any("That's the mistake" in t for t in texts))
    await asyncio.sleep(0.8)
    shots["why"] = shot()
    await press("C")
    await until(lambda: texts[-1] == "(1/4) Press 7.")
    await asyncio.sleep(0.9)
    shots["undo"] = shot()
    await press("7")
    await at_step(2)
    shots["step2"] = shot()
    await press("×")
    await at_step(3)
    await press("6")
    await at_step(4)
    shots["step4"] = shot()
    await press("=")
    await until(lambda: texts[-1].startswith("Done, bro"))  # the bro finishes happy
    await asyncio.sleep(1.0)
    shots["done"] = shot()
    await asyncio.wait_for(task, 20)
    await asyncio.sleep(1.0)
    sh.move(fx - 59, fy + fh // 2)  # force a repaint so the grab is not a stale frame
    await asyncio.sleep(0.5)
    print("overlay visible after the plan:", sh.state()["visible"], flush=True)
    shots["end"] = shot()
    calc.terminate()

    S, cam = shots, Camera()
    T = "Today's task: 7 × 6."
    pop_card("bro-idle-240.png", ("Ya-Bro", T, "What could possibly go wrong?", ""), 1500)
    a, b = "It points at the real key.", "Step 1 of 4: press 7."
    cam.hold(
        S["step1"],
        wide(S["step1"]),
        900,
        "Calculator open. The bro arrives.",
        "It only sees the app you allow.",
    )
    cam.move(S["step1"], focus(S["step1"]), a, b)
    cam.hold(S["step1"], focus(S["step1"]), 2200, a, b)
    a, b = "You press 5. On purpose.", "Bold choice."
    cam.move(S["wrong"], wide(S["wrong"]), a, b, steps=6)
    cam.hold(S["wrong"], wide(S["wrong"]), 700, a, b)
    a, b = "The bro notices. And has opinions.", "Read it. It is not impressed."
    cam.move(S["wrong"], focus(S["wrong"]), a, b)
    cam.hold(S["wrong"], focus(S["wrong"]), 2900, a, b)
    cam.hold(
        S["why"],
        focus(S["why"]),
        3700,
        "Why? It explains the mistake.",
        "Plainly. Okay, a bit smugly.",
    )
    a, b = "You undo it. All forgiven.", "Probably."
    cam.move(S["undo"], focus(S["undo"]), a, b, steps=5)
    cam.hold(S["undo"], focus(S["undo"]), 1600, a, b)
    a, b = "Right key. It moves on by itself.", "No Next button needed."
    cam.move(S["step2"], focus(S["step2"]), a, b, steps=6)
    cam.hold(S["step2"], focus(S["step2"]), 1900, a, b)
    a, b = "×, then 6. One step at a time.", "Almost there."
    cam.move(S["step4"], wide(S["step4"]), a, b, steps=7)
    cam.hold(S["step4"], wide(S["step4"]), 1000, a, b)
    cam.move(S["step4"], focus(S["step4"]), a, b, steps=6)
    cam.hold(S["step4"], focus(S["step4"]), 1500, a, b)
    a, b = "7 × 6 = 42. The bro is delighted.", "So is the Calculator."
    cam.move(S["done"], focus(S["done"]), a, b, steps=6)
    cam.hold(S["done"], focus(S["done"]), 2300, a, b)
    cam.move(S["done"], wide(S["done"]), a, b, steps=8)
    cam.hold(S["done"], wide(S["done"]), 900, a, b)
    cam.hold(S["end"], wide(S["end"]), 1700, "Then it leaves.", "No stickers. No tray icon.")
    end = (
        "Ya-Bro",
        "Your Linux desktop sidekick.",
        "Ask. Watch. Learn.",
        "github.com/AhmedYousriSobhi/ya-bro",
    )
    pop_card("bro-happy-240.png", end, 2600)
    save(OUT)
    kb = os.path.getsize(OUT) // 1024
    print("wrote", OUT, len(frames), "frames", (W, H), kb, "KB", flush=True)


asyncio.run(main(), loop_factory=gi.events.GLibEventLoopPolicy().new_event_loop)
