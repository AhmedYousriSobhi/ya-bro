"""The bro is drawn by the extension from assets/bro/<mood>.svg (ADR-0028). Run in headless-shell.sh.

Pixel checks on a real frame: each of the six moods shows the teal head and the dark cap, no two
moods look alike, the mood is reported back, an unknown mood falls back, and avatar=false hides it.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shellkit import Shell, find_pixels, pump  # noqa: E402

results = []
TEAL, CAP = (46, 196, 182), (43, 45, 66)
MOODS = ["idle", "pointing", "thinking", "happy", "teasing", "quiet"]


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}".rstrip(), flush=True)


sh = Shell()
sh.start_input()
AT = (500, 300)


def show(mood=None, avatar=True, target=None):
    kw = {
        "text": ("s", "hello"),
        "bubble_at": ("(ii)", AT),
        "avatar": ("b", avatar),
    }
    if mood is not None:
        kw["mood"] = ("s", mood)
    if target:
        kw["target"] = ("(iiii)", target)
        kw["ring"] = ("s", "confident")
    sh.show_step(**kw)
    pump(0.6)
    sh.ping()


def region():
    bx, by, _bw, _bh = sh.state()["bubble"]
    return range(by, by + 48), range(bx - 56, bx - 8)


def signature(pb, rows, cols, n=8):
    """A coarse picture of the avatar box: mean colour of each of n x n cells."""
    stride, ch, px = pb.get_rowstride(), pb.get_n_channels(), pb.get_pixels()
    ys, xs = list(rows), list(cols)
    sig = []
    for gy in range(n):
        for gx in range(n):
            cells = [
                px[y * stride + x * ch : y * stride + x * ch + 3]
                for y in ys[gy * len(ys) // n : (gy + 1) * len(ys) // n]
                for x in xs[gx * len(xs) // n : (gx + 1) * len(xs) // n]
            ]
            sig.append(tuple(sum(c[i] for c in cells) // len(cells) // 24 for i in range(3)))
    return tuple(sig)


sigs = {}
for mood in MOODS:
    show(mood)
    pb = sh.grab()
    rows, cols = region()
    teal = len(find_pixels(pb, TEAL, 30, rows, cols))
    cap = len(find_pixels(pb, CAP, 18, rows, cols))
    sigs[mood] = signature(pb, rows, cols)
    if os.environ.get("YB_SHOT"):  # for looking at it: YB_SHOT=/some/dir
        bx, by, bw, bh = sh.state()["bubble"]
        pb.new_subpixbuf(bx - 70, by - 12, bw + 90, 72).savev(
            f"{os.environ['YB_SHOT']}/{mood}.png", "png", [], []
        )
    check(
        f"{mood}: the teal head and the dark cap are drawn",
        teal > 120 and cap > 250,
        f"teal={teal} cap={cap}",
    )
    check(f"{mood}: the overlay reports it", sh.state()["mood"] == mood, str(sh.state()["mood"]))
check(
    "no two moods look the same",
    len(set(sigs.values())) == len(MOODS),
    f"{len(set(sigs.values()))} of 6",
)

show("../../etc/passwd")
check(
    "an unknown mood falls back to idle, never a path",
    sh.state()["mood"] == "idle",
    sh.state()["mood"],
)
show(None, target=(900, 500, 100, 60))
check(
    "a step with a target and no mood points", sh.state()["mood"] == "pointing", sh.state()["mood"]
)
show("happy", avatar=False)
pb = sh.grab()
rows, cols = region()
check("avatar = false leaves the bro out", len(find_pixels(pb, TEAL, 30, rows, cols)) == 0)
sh.hide()
pump(0.3)
check("hidden: no mood reported", sh.state()["mood"] == "")
sys.exit(0 if all(results) else 1)
