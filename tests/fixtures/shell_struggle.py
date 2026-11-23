"""The AT-SPI struggle source on real GTK apps in the isolated shell (#9).

Real menus, dialogs and a text view in a GTK4 fixture, driven by real pointer and key input through
Mutter (and AT-SPI actions where a window has no focus yet); a GTK3 app that raises error dialogs;
two more copies of the fixture that must stay unseen (one not enabled for struggle, one not allowed
in the extension). Every check reads what the source really emitted. `--mutate` breaks the
translator on purpose; the test then expects those checks to fail.
"""

import asyncio
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "..", "src")]
import gi  # noqa: E402
import gi.events  # noqa: E402

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi  # noqa: E402
from shellkit import App, Shell  # noqa: E402

from ya_bro import ui_events  # noqa: E402
from ya_bro.platform.gnome_adapters import AtspiPerception, GnomeBridge  # noqa: E402
from ya_bro.platform.gnome_atspi_events import AtspiUiEvents  # noqa: E402
from ya_bro.struggle import Detector  # noqa: E402
from ya_bro.struggle_host import StruggleHost  # noqa: E402

BASE = "io.github.ahmedyousrisobhi.YaBroStruggle"
A, B, C, D = BASE, BASE + "B", BASE + "C", BASE + "Gtk3"
MUTATE = "--mutate" in sys.argv
RECORD = sys.argv[sys.argv.index("--record") + 1] if "--record" in sys.argv else ""
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}".rstrip(), flush=True)


class Tee:
    """Wraps the real source and remembers what it emitted, for the checks."""

    def __init__(self, inner):
        self.inner, self.seen, self.times = inner, [], []

    async def events(self):
        async for e in self.inner.events():
            self.seen.append(e)
            self.times.append(time.monotonic())
            yield e


def press(pid, role, name, nth=0):
    """Do the default accessibility action of an element of this process (what a screen reader does)."""
    found = []

    def walk(node, depth=0):
        if depth > 14 or node is None:
            return
        try:
            if node.get_role_name() == role and (not name or node.get_name() == name):
                found.append(node)
            for i in range(node.get_child_count()):
                walk(node.get_child_at_index(i), depth + 1)
        except Exception:  # noqa: BLE001  (a tree that changes while walking)
            pass

    desktop = Atspi.get_desktop(0)
    for i in range(desktop.get_child_count()):
        try:
            app = desktop.get_child_at_index(i)
            ok = app is not None and app.get_process_id() == pid
        except Exception:  # noqa: BLE001  (an app that just went away)
            continue
        if ok:
            walk(app)
    if len(found) <= nth:
        return False
    found[nth].get_action_iface().do_action(0)
    return True


async def until(pred, limit=8.0):
    end = time.monotonic() + limit
    while time.monotonic() < end:
        if pred():
            return True
        await asyncio.sleep(0.05)
    return pred()


async def main():
    if MUTATE:  # the item event is never seen, and nothing counts as a quick dialog
        real_init = ui_events.Translator.__init__

        def deaf_init(self):
            real_init(self)
            self._item_closed = type("Deaf", (dict,), {"__setitem__": lambda *a: None})()

        ui_events.Translator.__init__ = deaf_init
        ui_events.QUICK_DIALOG = 0.0
    fixture = os.path.join(HERE, "apps", "struggle_fixture.py")
    apps = [App(fixture, env={"STRUGGLE_APP_ID": C}), App(fixture, env={"STRUGGLE_APP_ID": B})]
    await asyncio.sleep(4)
    app_a = App(fixture)  # last, so it is on top where the pointer goes
    sh = Shell()
    sh.start_input()
    bridge = GnomeBridge(sh.conn)
    per = AtspiPerception(bridge)

    def ids():
        return {w["app_id"] for w in sh.windows()}

    check("A and B are reported, C (not allowed) is not", await until(
        lambda: {A, B} <= ids() and C not in ids(), 30), str(ids()))  # fmt: skip
    await asyncio.sleep(3)
    pids = {w["app_id"]: w["pid"] for w in sh.windows()}

    det = Detector(time.time)
    for who in (A, C, D):  # B is allowed in the extension but not enabled for struggle
        det.opt_in(who)
    tee = Tee(AtspiUiEvents(bridge, det.is_watching))
    log = []
    host = StruggleHost(det, {}, ui=tee, sink=lambda n, **f: log.append((n, f)))
    task = asyncio.create_task(host.run())
    await asyncio.sleep(2)

    def mark():
        return len(tee.seen), len(log)

    segments = []

    def cut(name, kind, label, m):
        """Remember what the source emitted since mark `m` as an eval scenario (--record)."""
        segments.append((name, kind, label, m[0], len(tee.seen)))

    def got(m, kind):
        return [e for e in tee.seen[m[0] :] if e.kind == kind]

    def signals(m):
        return [f["signal"] for n, f in log[m[1] :] if n == "struggle_signal"]

    async def click(role, name, nth=0):
        refs = await per.find(A, role, name)
        r = await per.locate(refs[nth])
        sh.click(*r.center)
        await asyncio.sleep(0.9)

    async def menu_button(name):  # its name flips to "Edit Edit" while open
        for n in (name, f"{name} {name}"):
            if await per.find(A, "button", n):
                return n

    async def open_menu(name):
        await click("button", await menu_button(name))

    # -- 1. menus that chose an item are not a thrash. GTK4 reports an item's click only the first
    # time that item is used (measured), so each of the two items is used once.
    m = mark()
    for item in (0, 1):
        await open_menu("Edit")
        await click("menu item", "", item)
        await asyncio.sleep(0.5)
    await asyncio.sleep(0.5)
    check("a menu item's first click is menu_activated", len(got(m, "menu_activated")) == 2,
          str([e.kind for e in tee.seen[m[0]:]]))  # fmt: skip
    check("menus that chose an item are not a menu thrash",
          "menu_thrash" not in signals(m), str(signals(m)))  # fmt: skip

    cut("menu-items-used", "menu_thrash", "not_struggle", m)
    # -- 2. three menus opened and toggled shut with nothing chosen are
    m = mark()
    for _ in range(3):
        await open_menu("Edit")
        await open_menu("Edit")
        await asyncio.sleep(0.3)
    await asyncio.sleep(0.5)
    check("dismissed menus are shown then hidden, never activated",
          len(got(m, "menu_shown")) == 3 and len(got(m, "menu_hidden")) == 3
          and not got(m, "menu_activated"), str([e.kind for e in tee.seen[m[0]:]]))  # fmt: skip
    check("three of them make the menu thrash signal", "menu_thrash" in signals(m), str(signals(m)))

    cut("menu-dismissed-thrice", "menu_thrash", "struggle", m)
    # -- 3. a dialog cancelled the moment it opens, twice, is a bounce
    m = mark()
    for i in range(2):
        await open_menu("File")
        await click("menu item", "", 0)  # Export
        await until(lambda n=i + 1: len(got(m, "dialog_opened")) >= n, 6)
        press(pids[A], "button", "Cancel")
        await until(lambda n=i + 1: len(got(m, "dialog_cancelled")) >= n, 6)
        await asyncio.sleep(1)
    opened, cancelled = got(m, "dialog_opened"), got(m, "dialog_cancelled")
    check("an Export dialog opens and is cancelled twice", len(opened) == 2 and len(cancelled) == 2,
          str([e.kind for e in tee.seen[m[0]:]]))  # fmt: skip
    check(
        "the same dialog has the same key each time", len({e.key for e in opened + cancelled}) == 1
    )
    check("two bounced dialogs make the dialog bounce signal", "dialog_bounce" in signals(m),
          str(signals(m)))  # fmt: skip

    cut("dialog-bounce-twice", "dialog_bounce", "struggle", m)
    # -- 4. a dialog the user kept is a close, not a bounce
    m = mark()
    await open_menu("File")
    await click("menu item", "", 0)
    await until(lambda: got(m, "dialog_opened"), 6)
    await asyncio.sleep(ui_events.QUICK_DIALOG + 1.0)
    press(pids[A], "button", "OK")
    await until(lambda: got(m, "dialog_closed") or got(m, "dialog_cancelled"), 6)
    check("a dialog kept open past 3 s is dialog_closed", len(got(m, "dialog_closed")) == 1
          and not got(m, "dialog_cancelled"), str([e.kind for e in tee.seen[m[0]:]]))  # fmt: skip
    await asyncio.sleep(1)

    cut("dialog-kept-open", "dialog_bounce", "not_struggle", m)
    # -- 5. undo is a multi-character delete; backspace and typing are not
    await click("text", "")
    m = mark()
    for sym in (0x71, 0x7A, 0x78):  # q z x
        sh.tap(sym)
        await asyncio.sleep(0.4)
    for _ in range(2):
        sh.tap(0xFF08)  # backspace
        await asyncio.sleep(0.3)
    await asyncio.sleep(0.5)
    check("typing and backspace are not undo", not got(m, "undo") and got(m, "typing"),
          str([e.kind for e in tee.seen[m[0]:]]))  # fmt: skip
    m = mark()
    sh.tap(0x77)
    sh.tap(0x65)
    await asyncio.sleep(1.2)  # a new undo group
    sh.key("ctrl", True)
    sh.tap(0x7A)
    sh.key("ctrl", False)
    await until(lambda: got(m, "undo"), 5)
    check("Ctrl+Z (a delete of several characters) is an undo", len(got(m, "undo")) == 1,
          str([e.kind for e in tee.seen[m[0]:]]))  # fmt: skip

    cut("typing-and-one-undo", "undo_loop", "not_struggle", m)
    # -- 6. content-free: keys are salted hashes, numbers are zero, no typed letter anywhere
    every = " ".join(f"{e.app}|{e.kind}|{e.key}|{e.value}" for e in tee.seen)
    check("every key is an opaque token or empty",
          all(re.fullmatch(r"k[0-9a-f]{10}|", e.key) and e.value == 0 for e in tee.seen))  # fmt: skip
    check("no name or typed text reaches an event",
          not any(w in every for w in ("Export", "Edit", "File", "qzx", "Fixture")))  # fmt: skip

    # -- 7. a GTK3 error dialog is an alert, and two make the error loop
    m = mark()
    app_d = App(os.path.join(HERE, "apps", "struggle_gtk3_fixture.py"))
    apps.append(app_d)
    await until(lambda: len(got(m, "alert")) >= 2, 25)
    check("two GTK3 error dialogs are two alerts", len(got(m, "alert")) == 2
          and not got(m, "dialog_opened"), str([e.kind for e in tee.seen[m[0]:]]))  # fmt: skip
    check("and make the error loop signal", "error_loop" in signals(m), str(signals(m)))

    cut("two-error-dialogs", "error_loop", "struggle", m)

    # -- 8. scope: the same menus in an app not enabled (B) and one not allowed (C) are never seen
    m = mark()
    procs = {C: apps[0].proc.pid, B: apps[1].proc.pid}
    for _ in range(3):
        for pid in procs.values():
            for _i in range(2):  # open and shut
                press(pid, "toggle button", "Edit") or press(pid, "toggle button", "Edit Edit")
                await asyncio.sleep(0.6)
    await asyncio.sleep(1)
    other = [e for e in tee.seen[m[0] :] if e.app in (B, C)]
    check("nothing from the app not enabled or the app not allowed", not other, str(other))
    check("and the detector never remembered them", det.score(B) == 0.0 and det.score(C) == 0.0)

    if RECORD:
        write_scenarios(RECORD, tee, segments)
    task.cancel()
    for a in (*apps, app_a):
        a.close()


def write_scenarios(out_dir, tee, segments):
    """What the real source emitted, as replay scenarios: the labels are what each script meant."""
    import json
    from pathlib import Path

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    for name, kind, label, lo, hi in segments:
        evs, ts = tee.seen[lo:hi], tee.times[lo:hi]
        if not evs:
            continue
        t0 = ts[0]
        out = []
        for e, t in zip(evs, ts, strict=True):
            row = {"t": round(t - t0, 1), "kind": e.kind}
            if e.key:
                row["key"] = e.key
            out.append(row)
        data = {"id": "atspi-" + name, "kind": kind, "source": "recorded", "label": label,
                "app": "gtk-fixture", "duration": round(out[-1]["t"] + 30, 1), "events": out}  # fmt: skip
        if label == "struggle":
            data["onset"] = 0.0
        Path(out_dir, f"recorded-atspi-{name}.json").write_text(json.dumps(data, indent=1) + "\n")


asyncio.run(main(), loop_factory=gi.events.GLibEventLoopPolicy().new_event_loop)
sys.exit(0 if all(results) else 1)
