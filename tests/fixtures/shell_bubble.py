"""The bubble stays inside the monitor wherever the target is (#69). Run in headless-shell.sh."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shellkit import GLib, Shell, pump  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}".rstrip(), flush=True)


sh = Shell()
_, mx, my, mw, mh, _scale, _primary = sh.call(
    "io.github.ahmedyousrisobhi.YaBro.Shell.Bridge1", "GetMonitors"
)[0][0]
TEXT = "(4/4) Press = to see the answer. " * 6  # long enough to wrap to several lines
TS = 120
cases = {
    "top-left": (mx, my),
    "top-right": (mx + mw - TS, my),
    "bottom-left": (mx, my + mh - TS),
    "bottom-right": (mx + mw - TS, my + mh - TS),
    "bottom-middle": (mx + mw // 2, my + mh - TS),
    "middle": (mx + mw // 2, my + mh // 2),
}
for name, (tx, ty) in cases.items():
    args = {
        "target": GLib.Variant("(iiii)", (tx, ty, TS, TS)),
        "ring": GLib.Variant("s", "confident"),
        "text": GLib.Variant("s", TEXT),
        "buttons": GLib.Variant("as", ["next", "repeat", "why", "stop"]),
    }
    sh.call(
        "io.github.ahmedyousrisobhi.YaBro.Shell.Overlay1",
        "ShowStep",
        GLib.Variant("(a{sv})", (args,)),
    )
    pump(0.3)
    bx, by, bw, bh = sh.state()["bubble"]
    inside = bx - 40 >= mx and by >= my and bx + bw <= mx + mw and by + bh <= my + mh
    check(f"{name}: bubble and avatar inside the monitor", inside, f"bubble={(bx, by, bw, bh)}")
    apart = bx + bw <= tx or bx >= tx + TS or by + bh <= ty or by >= ty + TS
    check(f"{name}: bubble does not cover the target", apart, f"target={(tx, ty, TS, TS)}")

# No target, and an explicit position off-screen: still clamped.
args = {
    "text": GLib.Variant("s", "hello"),
    "bubble_at": GLib.Variant("(ii)", (mx + mw + 500, my + mh + 500)),
}
sh.call(
    "io.github.ahmedyousrisobhi.YaBro.Shell.Overlay1", "ShowStep", GLib.Variant("(a{sv})", (args,))
)
pump(0.3)
bx, by, bw, bh = sh.state()["bubble"]
check(
    "explicit off-screen position is clamped",
    bx + bw <= mx + mw and by + bh <= my + mh and bx >= mx and by >= my,
    str((bx, by, bw, bh)),
)
sh.hide()
pump(0.3)
check("hidden: no bubble rect", sh.state()["bubble"] == (0, 0, 0, 0))
sys.exit(0 if all(results) else 1)
