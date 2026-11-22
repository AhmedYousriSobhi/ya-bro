"""The ring must not tint the window interior (box-shadow filled it, #59). Run in headless-shell.sh."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shellkit import GLib, Shell, pump  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}".rstrip(), flush=True)


def px(pb, x, y):
    n, rs, d = pb.get_n_channels(), pb.get_rowstride(), pb.get_pixels()
    i = y * rs + x * n
    return tuple(d[i : i + 3])


sh = Shell()
sh.start_input()
base = sh.grab()
args = {
    "target": GLib.Variant("(iiii)", (300, 200, 600, 400)),
    "ring": GLib.Variant("s", "confident"),
    "text": GLib.Variant("s", "x"),
    "buttons": GLib.Variant("as", ["stop"]),
}
sh.call(
    "io.github.ahmedyousrisobhi.YaBro.Shell.Overlay1", "ShowStep", GLib.Variant("(a{sv})", (args,))
)
pump(1.0)
pb = sh.grab()
check("ring interior is unchanged", px(pb, 600, 400) == px(base, 600, 400), str(px(pb, 600, 400)))
check("outside the ring is unchanged", px(pb, 150, 100) == px(base, 150, 100))
check("ring border is drawn", px(pb, 301, 400) == (245, 165, 36), str(px(pb, 301, 400)))
sys.exit(0 if all(results) else 1)
