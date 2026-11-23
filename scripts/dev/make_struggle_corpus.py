#!/usr/bin/env python3
"""Build the SCRIPTED struggle scenarios in evals/struggle/ (deterministic; rerun to regenerate).

Each scenario is a content-free event stream (the detector's kinds, a short token, a number) with a
label we decided by reading the script: was the person stuck or not. They are written the way the
ADR describes ("scripted stuck and not-stuck scenarios"), with seeded jitter on the timings. They
are NOT recordings of real people, and the labels are ours. `recorded-*.json` files come from
`tests/fixtures/record_struggle.py` (a real bash with the hook) and are not touched here.
"""

import json
import random
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "evals" / "struggle"
APP = "workbench"


class S:
    """A scenario under construction: `at(t)` moves the clock, the helpers add events."""

    def __init__(self, sid, kind, label, duration, onset=None, expect=None, app=APP, seed=0):
        self.d = {"id": sid, "kind": kind, "source": "scripted", "label": label, "app": app,
                  "duration": duration, "events": []}  # fmt: skip
        if onset is not None:
            self.d["onset"] = onset
        if expect is not None:
            self.d["expect_offers"] = expect
        self.t = 0.0
        self.rng = random.Random(f"{sid}-{seed}")

    def at(self, t):
        self.t = t
        return self

    def wait(self, lo, hi=None):
        self.t += lo if hi is None else self.rng.uniform(lo, hi)
        return self

    def ev(self, kind, key="", value=0):
        e = {"t": round(self.t, 1), "kind": kind}
        if key:
            e["key"] = key
        if value:
            e["value"] = value
        self.d["events"].append(e)
        return self

    def cmd(self, name="benchctl", code=1):
        return self.ev("command_exit", name, code)

    def fails(self, n, gap=(8, 25), name="benchctl"):
        for i in range(n):
            self.cmd(name, 1)
            if i < n - 1:
                self.wait(*gap)
        return self

    def idle(self, seconds):
        return self.ev("idle_span", value=seconds)

    def answer(self, outcome):
        return self.ev("answer", outcome)

    def done(self):
        self.d["events"].sort(key=lambda e: e["t"])
        return self.d


def scenarios():
    out = []
    add = out.append

    # ---- struggling: the detector should offer ------------------------------------------------
    for i, (name, gap) in enumerate([("benchctl", (6, 15)), ("make", (10, 30)), ("cargo", (15, 40)),
                                     ("git", (30, 70))]):  # fmt: skip
        s = S(f"fail-loop-{i}", "failing_commands", "struggle", 300, onset=10, seed=i)
        add(s.at(10).fails(3, gap, name).done())
    add(
        S("fail-loop-long", "failing_commands", "struggle", 400, onset=10)
        .at(10)
        .fails(5, (20, 50))
        .done()
    )
    s = S("fail-loop-slow", "failing_commands", "struggle", 400, onset=10).at(10)
    add(s.fails(3, (100, 140)).done())  # three in under five minutes, just
    s = S("error-code-twice", "app_error_code", "struggle", 200, onset=10).at(10)
    s.cmd().ev("error_code", "WB-REFUSED-MEMORY").wait(20, 40)
    s.cmd().ev("error_code", "WB-REFUSED-MEMORY")
    add(s.done())
    s = S("error-code-then-loop", "app_error_code", "struggle", 300, onset=10).at(10)
    for _ in range(3):
        s.cmd().ev("error_code", "WB-REFUSED-MEMORY").wait(15, 30)
    add(s.done())
    s = S("alerts-twice", "error_loop", "struggle", 200, onset=10).at(10)
    s.ev("alert", "e1").wait(30, 60).ev("alert", "e2")
    add(s.done())
    s = S("alerts-thrice", "error_loop", "struggle", 200, onset=10).at(10)
    s.ev("alert", "e1").wait(20, 40).ev("alert", "e2").wait(20, 40).ev("alert", "e3")
    add(s.done())
    s = S("dialog-bounce", "dialog_bounce", "struggle", 120, onset=10).at(10)
    for _ in range(2):
        s.ev("dialog_opened", "export").wait(0.8, 2).ev("dialog_cancelled", "export").wait(3, 8)
    add(s.done())
    s = S("dialog-bounce-then-error", "dialog_bounce", "struggle", 120, onset=10).at(10)
    for _ in range(2):
        s.ev("dialog_opened", "export").wait(1, 2).ev("dialog_cancelled", "export").wait(2, 5)
    s.ev("alert", "failed")
    add(s.done())
    s = S("menu-thrash-and-help", "menu_thrash", "struggle", 120, onset=5).at(5)
    for _ in range(3):
        s.ev("menu_shown", "File").wait(0.5, 1.5).ev("menu_hidden", "File").wait(2, 4)
    s.ev("help_opened").wait(2).idle(8)
    add(s.done())
    s = S("menu-thrash-twice", "menu_thrash", "struggle", 120, onset=5).at(5)
    for _round in range(2):
        for _ in range(3):
            s.ev("menu_shown", "Edit").wait(0.5, 1.2).ev("menu_hidden", "Edit").wait(1.5, 3)
        s.wait(10)
    s.idle(8)
    add(s.done())
    s = S("menu-thrash-alone", "menu_thrash", "struggle", 90, onset=5).at(5)
    for _ in range(4):
        s.ev("menu_shown", "File").wait(0.5, 1.5).ev("menu_hidden", "File").wait(2, 4)
    add(s.done())  # weak on its own: the eval should say whether we catch it
    s = S("pingpong-and-undo", "focus_pingpong", "struggle", 120, onset=5).at(5)
    for i in range(9):
        s.ev("focus", "w1" if i % 2 == 0 else "w2").wait(2, 5)
    for _ in range(4):
        s.ev("undo").wait(2, 5)
    s.wait(3).idle(7)
    add(s.done())
    s = S("pingpong-alone", "focus_pingpong", "struggle", 120, onset=5).at(5)
    for i in range(10):
        s.ev("focus", "w1" if i % 2 == 0 else "w2").wait(2, 5)
    add(s.done())
    s = S("undo-and-help", "undo_loop", "struggle", 120, onset=5).at(5)
    for _ in range(5):
        s.ev("undo").wait(2, 5)
    s.ev("help_opened").wait(2).idle(8)
    add(s.done())
    s = S("undo-alone", "undo_loop", "struggle", 90, onset=5).at(5)
    for _ in range(6):
        s.ev("undo").wait(2, 4)
    add(s.done())
    s = S("stuck-in-dialog", "idle_in_context", "struggle", 120, onset=5).at(5)
    s.ev("dialog_opened", "settings").wait(2).idle(40)
    add(s.done())  # a dialog sat open: a pause with something unfinished
    s = S("failed-then-staring", "idle_in_context", "struggle", 150, onset=5).at(5)
    s.fails(2, (5, 10)).wait(5).idle(45)
    add(s.done())
    s = S("loop-and-staring", "failing_commands", "struggle", 200, onset=5).at(5)
    s.fails(3, (8, 20)).wait(10).idle(40)
    add(s.done())
    s = S("error-and-help", "error_loop", "struggle", 150, onset=5).at(5)
    s.ev("alert", "e1").wait(10).ev("help_opened").wait(20).ev("alert", "e2")
    add(s.done())
    s = S("after-ten-calm-minutes", "failing_commands", "struggle", 900, onset=610)
    s.at(10)
    for _ in range(12):
        s.cmd("ls", 0).wait(20, 70)
    s.at(610).fails(3, (8, 20))
    add(s.done())

    # ---- not struggling: the detector should stay quiet ------------------------------------
    add(
        S("one-failure", "failing_commands", "not_struggle", 120)
        .at(10)
        .cmd()
        .wait(15)
        .cmd(code=0)
        .done()
    )
    s = S("typo-fixed", "failing_commands", "not_struggle", 120).at(10)
    add(s.cmd().wait(10, 20).cmd().wait(10, 20).cmd(code=0).done())
    s = S("different-commands-fail", "failing_commands", "not_struggle", 200).at(10)
    for name in ("make", "git", "ls"):
        s.cmd(name, 1).wait(10, 30)
    add(s.done())
    s = S("failures-spread-out", "failing_commands", "not_struggle", 1500).at(10)
    for _ in range(3):
        s.cmd().wait(350, 450)
    add(s.done())
    s = S("failure-then-success-then-failure", "failing_commands", "not_struggle", 200).at(10)
    s.cmd().wait(10).cmd().wait(10).cmd(code=0).wait(15).cmd()
    add(s.done())
    s = S("menu-used-normally", "menu_thrash", "not_struggle", 120).at(5)
    for _ in range(8):
        s.ev("menu_shown", "File").wait(0.6, 1.2).ev("menu_activated", "File")
        s.ev("menu_hidden", "File").wait(3, 8)
    add(s.done())
    s = S("dialogs-used-normally", "dialog_bounce", "not_struggle", 200).at(5)
    for _ in range(3):
        s.ev("dialog_opened", "export").wait(15, 30).ev("dialog_closed", "export").wait(10, 20)
    add(s.done())
    add(S("one-alert", "error_loop", "not_struggle", 120).at(10).ev("alert", "e1").done())
    add(S("long-read", "idle_in_context", "not_struggle", 300).at(5).idle(150).done())
    s = S("pause-after-success", "idle_in_context", "not_struggle", 300).at(5)
    add(s.cmd(code=0).wait(5).idle(120).done())
    s = S("quick-undos-while-drawing", "undo_loop", "not_struggle", 90).at(5)
    for _ in range(6):
        s.ev("undo").wait(2, 5)
    add(s.done())
    s = S("copy-paste-between-windows", "focus_pingpong", "not_struggle", 120).at(5)
    for i in range(10):
        s.ev("focus", "w1" if i % 2 == 0 else "w2").wait(2, 6)
    add(s.done())
    add(
        S("looks-up-help-once", "help_seeking", "not_struggle", 120).at(10).ev("help_opened").done()
    )
    s = S("typing-through-a-failure", "typing", "not_struggle", 120).at(5)
    for _ in range(20):
        s.ev("typing").wait(1)
    s.cmd().wait(1).ev("typing")
    for _ in range(10):
        s.wait(1).ev("typing")
    add(s.done())
    s = S("settings-dialog-reviewed", "idle_in_context", "not_struggle", 200).at(5)
    s.ev("dialog_opened", "prefs").wait(25).ev("dialog_closed", "prefs").wait(5)
    add(s.done())
    s = S("copy-then-paste-wait", "mixed", "not_struggle", 200).at(5)
    s.ev("focus", "w1").wait(5).ev("focus", "w2").wait(8).ev("undo").wait(20).ev("help_opened")
    add(s.done())
    s = S("slow-build-and-wait", "failing_commands", "not_struggle", 300).at(5)
    s.cmd("make", 0).wait(30).idle(100)
    add(s.done())
    s = S("fix-cycle-with-edits", "failing_commands", "not_struggle", 300).at(10)
    for _ in range(3):  # fail, edit for a while, retry: three tries, then it works
        s.cmd("make", 1)
        for _ in range(25):
            s.wait(1).ev("typing")
        s.wait(2)
    s.cmd("make", 0)
    add(s.done())
    s = S("fix-cycle-quick", "failing_commands", "not_struggle", 200).at(10)
    for _ in range(3):
        s.cmd("make", 1).wait(12, 20)
    s.cmd("make", 0)
    add(s.done())
    s = S("test-driven-red-green", "failing_commands", "not_struggle", 300).at(10)
    for _ in range(2):
        s.cmd("pytest", 1).wait(30, 50).cmd("pytest", 0).wait(20, 40)
    add(s.done())

    # ---- a whole working half hour, with ordinary hiccups ------------------------------------
    for n in range(3):
        s = S(f"workday-{n}", "workday", "not_struggle", 1800, seed=n)
        t = 10.0
        r = s.rng
        while t < 1750:
            s.at(t)
            pick = r.random()
            if pick < 0.35:
                s.cmd(r.choice(["ls", "git", "make", "benchctl"]), 0)
            elif pick < 0.45:
                s.cmd(r.choice(["make", "git"]), 1).wait(8, 20).cmd(code=0)
            elif pick < 0.6:
                s.ev("menu_shown", "File").wait(0.8).ev("menu_activated", "File").ev(
                    "menu_hidden", "File"
                )
            elif pick < 0.7:
                s.ev("dialog_opened", "open").wait(10, 25).ev("dialog_closed", "open")
            elif pick < 0.8:
                s.ev("focus", r.choice(["w1", "w2", "w3"]))
            elif pick < 0.9:
                s.ev("undo")
            else:
                s.idle(r.randint(15, 60))
            t += r.uniform(25, 90)
        add(s.done())

    # ---- back-off: what happens after the user answers ---------------------------------------
    def loop(s, at, name="benchctl"):
        """Three failures 6 s apart: the offer comes 12 s in, so an answer at 14 s is in time."""
        return s.at(at).fails(3, (6, 6), name)

    def reply(s, at, outcome):
        return s.at(at + 14).answer(outcome)  # inside the 8 s the bubble stays up

    s = S("backoff-no-then-same-loop", "backoff", "struggle", 500, onset=10, expect=1)
    loop(s, 10)
    reply(s, 10, "no")
    loop(s, 200)
    add(s.done())
    s = S("backoff-no-then-it-works-then-loop", "backoff", "struggle", 700, onset=10, expect=2)
    loop(s, 10)
    reply(s, 10, "no")
    s.at(100).cmd("benchctl", 0)
    loop(s, 300)
    add(s.done())
    s = S("backoff-two-nos-then-quiet", "backoff", "struggle", 1500, onset=10, expect=2)
    loop(s, 10)
    reply(s, 10, "no")
    s.at(100).cmd("benchctl", 0)
    loop(s, 200)
    reply(s, 200, "no")
    s.at(300).cmd("benchctl", 0)
    loop(s, 600)  # ten minutes later: still inside the 30 quiet minutes
    add(s.done())
    s = S("backoff-yes-then-loop", "backoff", "struggle", 700, onset=10, expect=2)
    loop(s, 10)
    reply(s, 10, "yes")
    loop(s, 300)
    add(s.done())
    s = S("backoff-never", "backoff", "struggle", 700, onset=10, expect=1)
    loop(s, 10)
    reply(s, 10, "never")
    loop(s, 300)
    add(s.done())
    s = S("backoff-cooldown", "backoff", "struggle", 300, onset=10, expect=1)
    loop(s, 10)
    s.at(60).ev("alert", "e1").at(70).ev("alert", "e2")  # a second pattern inside the 2 minutes
    add(s.done())
    s = S("backoff-hourly-cap", "backoff", "struggle", 1200, onset=10, expect=3)
    for i in range(5):
        loop(s, 10 + i * 200, ["benchctl", "make", "git", "cargo", "npm"][i])
        reply(s, 10 + i * 200, "yes")
    add(s.done())
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("scripted-*.json"):
        old.unlink()
    for d in scenarios():
        (OUT / f"scripted-{d['id']}.json").write_text(json.dumps(d, indent=1) + "\n")


if __name__ == "__main__":
    main()
