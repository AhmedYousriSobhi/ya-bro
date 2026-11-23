"""An Arabic persona line in the real overlay: drawn, and laid out right-to-left (#23, ADR-0019).

Run in headless-shell.sh. The same Arabic line is shown with dir=ltr and dir=rtl. On a real frame the
text must be real ink (not empty boxes), and the right-to-left bubble must mirror its buttons: the
longer label ("Repeat") sits on the right when left-to-right and on the left when right-to-left.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "..", "src")]
from shellkit import Shell, pump  # noqa: E402

from ya_bro.persona import Persona, detect_locale, is_rtl  # noqa: E402

results = []
TEXT = (235, 235, 245)
BUTTON_BG = (58, 58, 82)  # .yabro-button in extension/stylesheet.css


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}".rstrip(), flush=True)


sh = Shell()
sh.start_input()


def draw(text, direction):
    """Show the bubble; return the ink pixel count and which edge the buttons hug (px)."""
    sh.show_step(
        text=("s", "(1/4) " + text),
        bubble_at=("(ii)", (300, 120)),
        dir=("s", direction),
        buttons=("as", ["next", "repeat"]),
    )
    pump(0.7)
    sh.ping()
    bx, by, bw, bh = sh.state()["bubble"]
    pb = sh.grab()
    r, stride, ch, px = sh.ratio, pb.get_rowstride(), pb.get_n_channels(), pb.get_pixels()

    def near(x, y, colour, tol):
        i = y * stride + x * ch
        return all(abs(px[i + k] - colour[k]) < tol for k in range(3))

    width = range(int(bx * r), int((bx + bw) * r))
    ink = sum(
        near(x, y, TEXT, 22)
        for y in range(int((by + 8) * r), int((by + bh * 0.55) * r))  # above the buttons
        for x in width
    )
    band = range(int((by + bh * 0.4) * r), int((by + bh) * r))  # the buttons' rows
    cols = [x for x in width if any(near(x, y, BUTTON_BG, 6) for y in band)]
    lo, hi = min(cols), max(cols)  # the strip of buttons
    # Negative: the strip hugs the left edge of the bubble; positive: the right edge.
    side = ((lo - bx * r) - ((bx + bw) * r - hi)) / r
    return ink, side


line = Persona(humour=1, locale="ar").say("mismatch", want="7", got="5")
check(
    "the Arabic line is Arabic and is right-to-left", detect_locale(line) == "ar" and is_rtl(line)
)
ltr_ink, ltr_side = draw(line, "ltr")
rtl_ink, rtl_side = draw(line, "rtl")
check(
    "the Arabic bubble carries real text, not boxes",
    ltr_ink > 60 and rtl_ink > 60,
    f"{ltr_ink} {rtl_ink}",
)
check(
    "left-to-right: the buttons start at the left (Next, Repeat)",
    ltr_side < -10,
    f"{ltr_side:.0f}px",
)
check("right-to-left mirrors them: at the right (Repeat, Next)", rtl_side > 10, f"{rtl_side:.0f}px")
sys.exit(0 if all(results) else 1)
