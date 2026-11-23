"""Real apps, real accessibility trees: record snapshots, and check pointing by clicking (#19).

Run in headless-shell.sh with YB_ALLOWED listing the apps. For every app that opens a window it
records the buttons, tabs, menu items, toggles and check boxes with their real names and rectangles
into $YB_SNAP_DIR/recorded-<app>.json (cases built from them: see cases()). On the Calculator it
also presses every key it points at and reads the display, so a wrong ring would show.
"""

import asyncio
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "..", "src")]
import gi  # noqa: E402
import gi.events  # noqa: E402
from shellkit import Shell  # noqa: E402

from ya_bro import grounding  # noqa: E402
from ya_bro.grounding import Tier  # noqa: E402
from ya_bro.platform.gnome_adapters import AtspiPerception, GnomeBridge  # noqa: E402

APPS = {
    "org.gnome.Calculator": "gnome-calculator",
    "org.gnome.TextEditor": "gnome-text-editor",
    "org.gnome.Nautilus": "nautilus",
    "org.gnome.Settings": "gnome-control-center",
}
ROLES = [
    "button", "toggle button", "menu item", "page tab", "check box", "radio button", "list item",
]  # fmt: skip
OFFSETS = {"org.gnome.Calculator": (-12, -12)}  # S9
OUT = os.environ.get("YB_SNAP_DIR", "")
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}".rstrip(), flush=True)


def cases(elements):
    """Labelled cases from what was really on screen. Duplicates get an arbitrary member as truth:
    nothing but position tells them apart, so a name cannot find the right one."""
    names = {}
    for e in elements:
        names.setdefault((e["role"], e["name"]), []).append(e)
    taken = {e["name"] for e in elements}
    out = []

    def add(kind, role, name, truth):
        out.append({"id": f"c{len(out)}", "kind": kind, "role": role, "name": name, "truth": truth})

    for (role, name), group in names.items():
        if not name.strip():
            continue  # icon-only: no name to ask for
        if len(group) > 1:
            add("duplicate", role, name, group[-1]["id"])
            continue
        e = group[0]
        add("exact", role, name, e["id"])
        if name.upper() != name:
            add("spelling", role, f"  {name.upper()}  ", e["id"])
        if name.endswith("…"):
            add("drift", role, name.rstrip("…"), e["id"])
        elif len(name) > 3 and name[:-1] not in taken:
            add("drift", role, name[:-1], e["id"])
        other = next((r for r in ROLES if r != role and (r, name) not in names), None)
        if other:
            add("wrong-role", other, name, None)
    for ghost in ("Mirror the universe", "Teleport", "Flux capacitor"):
        add("missing", "button", ghost, None)
    return out


async def settle(sh, app_id, seconds=25):
    end = asyncio.get_running_loop().time() + seconds
    while asyncio.get_running_loop().time() < end:
        win = next((w for w in sh.windows() if w["app_id"] == app_id), None)
        if win:
            return win
        await asyncio.sleep(0.5)
    return None


def say(msg):
    print(f"      .. {msg}", flush=True)


async def record(sh, bridge, app_id, proc):
    try:
        win = await settle(sh, app_id)
        if win is None:
            print(f"SKIP  {app_id}: no window", flush=True)
            return None
        say(f"{app_id} window up")
        await asyncio.sleep(6)
        fx, fy, fw, fh = win["frame"]
        for _ in range(20):
            sh.click(fx + fw // 2, fy + 15)
            await asyncio.sleep(0.4)
            if any(w["focused"] and w["app_id"] == app_id for w in sh.windows()):
                break
        say("focused")
        perception = AtspiPerception(bridge, OFFSETS.get(app_id, (0, 0)))
        elements = []
        for role in ROLES:
            say(f"walking {role}")
            for ref in await perception.find(app_id, role):
                rect = await perception.locate(ref)
                if rect is not None:
                    elements.append(
                        {"id": ref.path, "role": role, "name": ref.name,
                         "rect": [rect.x, rect.y, rect.w, rect.h]}
                    )  # fmt: skip
        win = next((w for w in sh.windows() if w["app_id"] == app_id), win)
        return perception, elements, list(win["frame"])
    except Exception:
        proc.terminate()
        raise


async def calculator_keys(sh, perception, app_id):
    """Point at each key by name, click the middle of the ring, and read the display."""

    async def display():
        return [await perception.read_text(r) for r in await perception.find(app_id, "text")]

    async def press(name):
        p = await grounding.point(perception, app_id, "button", name)
        if p.rect is None:
            return p
        sh.click(*p.rect.center)
        await asyncio.sleep(0.5)
        return p

    await press("C")
    good = 0
    for digit in "0123456789":
        await press("C")
        before = await display()
        p = await press(digit)
        after = await display()
        ok = p.tier is Tier.HIGH and any(digit in t for t in after) and before != after
        good += ok
        if not ok:
            print(f"      key {digit}: tier {p.tier}, before {before}, after {after}", flush=True)
    check(
        "Calculator: all 10 digits pointed High and the click lands on that key",
        good == 10,
        f"{good}/10",
    )
    await press("C")
    await press("7")
    await press("×")
    await press("6")
    await press("=")
    after = await display()
    check(
        "Calculator: 7 × 6 = 42 by pointing at each key", any("42" in t for t in after), str(after)
    )


async def sidebar_clicks(sh, perception, app_id, role, targets, shows):
    """Point at sidebar rows by name, click the middle of the ring, and see the app navigate."""
    good = 0
    # The first press after the window opens is spent on activating it (seen on Files): spend it on
    # the title bar, so what is measured is where the ring points, not that press.
    fx, fy, fw, _fh = next(w for w in sh.windows() if w["app_id"] == app_id)["frame"]
    sh.click(fx + fw // 2, fy + 15)
    await asyncio.sleep(1)
    for name in targets:
        before = await shows(name)
        p = await grounding.point(perception, app_id, role, name)
        if p.rect is not None:
            sh.move(*p.rect.center)  # GTK4 rows need the pointer over them before the press
            await asyncio.sleep(0.5)
            sh.click(*p.rect.center)
        for _ in range(20):
            await asyncio.sleep(0.3)
            if await shows(name):
                break
        ok = p.tier is Tier.HIGH and not before and await shows(name)
        print(f"      {name}: {p.tier} rect {p.rect} ok={ok}", flush=True)
        good += ok
        if not ok:
            print(f"      {name}: tier {p.tier}, was showing {before}", flush=True)
    return good


async def main():
    sh = Shell()
    sh.start_input()
    bridge = GnomeBridge(sh.conn)
    recorded = {}
    only = os.environ.get("YB_APPS")
    for app_id, cmd in APPS.items():
        if only and app_id not in only:
            continue
        env = dict(os.environ, GTK_A11Y="atspi")
        env.pop("DISPLAY", None)
        # Only the process we started is ever stopped: never `pkill` by name (the live desktop).
        proc = subprocess.Popen(
            [cmd], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        got = await record(sh, bridge, app_id, proc)
        if got is None:
            proc.terminate()
            continue
        perception, elements, frame = got
        if len(elements) < 3:  # a finding, not a failure: some apps expose almost nothing (S2)
            print(f"NOTE  {app_id}: only {len(elements)} usable elements in its tree", flush=True)
            proc.terminate()
            continue
        recorded[app_id] = (elements, frame)
        check(f"{app_id}: real elements recorded", True, f"{len(elements)}")
        if app_id == "org.gnome.Calculator":
            await calculator_keys(sh, perception, app_id)
        if app_id == "org.gnome.Settings":

            async def shows(name, perception=perception, app_id=app_id):
                return bool(await perception.find(app_id, "grouping", name))

            rows = ("Bluetooth", "Sound", "Power")
            good = await sidebar_clicks(sh, perception, app_id, "button", rows, shows)
            check("Settings: pointed rows open their page when clicked", good == 3, f"{good}/3")
        if app_id == "org.gnome.Nautilus":

            async def shows(name, perception=perception, app_id=app_id):
                titles = [r.name for r in await perception.find(app_id, "frame")]
                print(f"      frames: {titles}", flush=True)
                want = {"Recent Files": "Recent", "Starred Files": "Starred", "Open Trash": "Trash"}
                return want[name] in " ".join(titles)

            good = await sidebar_clicks(
                sh,
                perception,
                app_id,
                "list item",
                ("Recent Files", "Starred Files", "Open Trash"),
                shows,
            )
            check("Files: pointed rows open their folder when clicked", good == 3, f"{good}/3")
        if OUT:
            os.makedirs(OUT, exist_ok=True)
            data = {
                "app": app_id, "locale": os.environ.get("LANG", "en")[:2] or "en",
                "source": "recorded", "window": frame, "elements": elements, "cases": cases(elements),
            }  # fmt: skip
            with open(
                os.path.join(OUT, f"recorded-{app_id.split('.')[-1].lower()}.json"), "w"
            ) as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
                f.write("\n")
        proc.terminate()
        await asyncio.sleep(2)
    check("Calculator was recorded", "org.gnome.Calculator" in recorded)
    check("at least two real apps were recorded", len(recorded) >= 2, str(sorted(recorded)))


asyncio.run(main(), loop_factory=gi.events.GLibEventLoopPolicy().new_event_loop)
sys.exit(0 if all(results) else 1)
