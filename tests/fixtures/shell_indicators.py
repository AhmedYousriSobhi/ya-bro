"""State dots under the bro: watching, listening, sending, acting (#25, ADR-0014 §3).

Run in headless-shell.sh. Real-frame pixel checks: each named state draws its own colour, an unknown
word draws nothing, a live SetIndicators call changes them, they stay when the bro is left out, and
nothing is drawn or reported once the overlay is hidden.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gi.repository import GLib  # noqa: E402
from shellkit import OVERLAY, Shell, find_pixels, pump  # noqa: E402

results = []
COLOURS = {
    "watching": (77, 163, 255),
    "listening": (53, 196, 107),
    "sending": (255, 93, 93),
    "acting": (245, 165, 36),
}


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}".rstrip(), flush=True)


sh = Shell()
sh.start_input()


def show(names, avatar=True):
    kw = {"text": ("s", "hello"), "bubble_at": ("(ii)", (500, 300)), "avatar": ("b", avatar)}
    if names is not None:
        kw["indicators"] = ("as", names)
    sh.show_step(**kw)
    pump(0.6)
    sh.ping()


def drawn():
    """Which state colours are on the frame, in the row of dots under the bro."""
    bx, by, _bw, _bh = sh.state()["bubble"]
    pb = sh.grab()
    rows, cols = range(by + 50, by + 68), range(bx - 56, bx - 8)
    return {k for k, c in COLOURS.items() if len(find_pixels(pb, c, 12, rows, cols)) > 20}


show(["watching"])
check("watching is blue and alone", drawn() == {"watching"}, str(drawn()))
check("the overlay reports it", list(sh.state()["indicators"]) == ["watching"])
show(["watching", "sending"])
check("two states, two dots", drawn() == {"watching", "sending"}, str(drawn()))
show(["watching", "listening", "sending", "acting"])
check("all four at once", drawn() == set(COLOURS), str(drawn()))
show(["rm -rf", "../x", "Sending"])
check("unknown words draw nothing", drawn() == set() and sh.state()["indicators"] == [])
show(["watching"])
sh.call(OVERLAY, "SetIndicators", GLib.Variant("(as)", (["acting"],)))
pump(0.4)
check("a live change swaps them", drawn() == {"acting"}, str(drawn()))
show(["sending"], avatar=False)
check("they stay when the bro itself is left out", drawn() == {"sending"}, str(drawn()))
sh.hide()
pump(0.4)
check("hidden: nothing reported", list(sh.state()["indicators"]) == [])
show(["acting"])
sh.hide()
pump(0.4)
check("hidden: nothing drawn", len(find_pixels(sh.grab(), COLOURS["acting"], 12)) < 20)
sys.exit(0 if all(results) else 1)
