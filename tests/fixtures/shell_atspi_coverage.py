"""Spike S2 (#2): how much of a real app's UI can be found by role and name over AT-SPI?

Run in headless-shell.sh with YB_ALLOWED listing the window app ids to try. For each app that opens
a window it walks the whole tree (up to a node budget) and reports, per role we act on, how many
elements exist, how many have a name, and how many have usable rectangles inside the window. Output:
one JSON line per app (`COVERAGE {...}`). Observation only: nothing here fails a build.
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "..", "src")]
import gi  # noqa: E402
import gi.events  # noqa: E402
from shellkit import Shell  # noqa: E402

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi, GLib  # noqa: E402

from ya_bro.platform.gnome_adapters import AtspiPerception, GnomeBridge  # noqa: E402

ACT_ROLES = (
    "push button", "toggle button", "menu item", "page tab", "check box", "radio button",
    "list item", "text", "entry", "combo box", "link", "check menu item", "radio menu item",
)  # fmt: skip
BUDGET = 30000
TMP = tempfile.mkdtemp(prefix="yb-s2-")

# name -> command; the window's app id is discovered, not assumed
APPS = {
    "libreoffice-writer": ["soffice", "--writer", "--norestore", f"-env:UserInstallation=file://{TMP}/lo"],
    "vscode": ["/usr/share/code/code", "--new-window", "--user-data-dir", f"{TMP}/code", "--extensions-dir", f"{TMP}/ext",
               "--disable-gpu", "--ozone-platform=wayland", "--force-renderer-accessibility"],
    "firefox": ["firefox", "--no-remote", "--profile", f"{TMP}/ff", "about:blank"],
}  # fmt: skip


def walk(app, win_frame, budget=BUDGET):
    roles, named, rect_ok, total, depth_max = Counter(), Counter(), Counter(), 0, 0
    stack = [(app, 0)]
    while stack and total < budget:
        node, depth = stack.pop()
        total += 1
        depth_max = max(depth_max, depth)
        try:
            role = node.get_role_name()
            if role in ACT_ROLES:
                roles[role] += 1
                if (node.get_name() or "").strip():
                    named[role] += 1
                e = node.get_extents(Atspi.CoordType.WINDOW)
                x, y, w, h = win_frame
                if 0 < e.width <= w and 0 < e.height <= h and -50 <= e.x <= w and -50 <= e.y <= h:
                    rect_ok[role] += 1
            for i in range(node.get_child_count()):
                c = node.get_child_at_index(i)
                if c is not None:
                    stack.append((c, depth + 1))
        except GLib.Error:
            continue
    return {"nodes": total, "truncated": total >= budget, "depth": depth_max,
            "roles": {r: {"found": roles[r], "named": named[r], "rect_ok": rect_ok[r]} for r in roles}}  # fmt: skip


async def main():
    sh = Shell()
    sh.start_input()
    bridge = GnomeBridge(sh.conn)
    perception = AtspiPerception(bridge)
    only = os.environ.get("YB_APPS", "")
    for name, cmd in APPS.items():
        if only and name not in only:
            continue
        if shutil.which(cmd[0]) is None and not os.path.exists(cmd[0]):
            print(f"SKIP {name}: {cmd[0]} not installed", flush=True)
            continue
        os.makedirs(f"{TMP}/ff", exist_ok=True)
        env = dict(
            os.environ,
            GTK_A11Y="atspi",
            GNOME_ACCESSIBILITY="1",
            MOZ_ENABLE_WAYLAND="1",
            ACCESSIBILITY_ENABLED="1",
        )
        env.pop("DISPLAY", None)
        before = {w["id"] for w in sh.windows()}
        errf = open(f"{TMP}/{name}.err", "w")
        proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=errf)
        win = None
        for _ in range(120):
            await asyncio.sleep(0.5)
            win = next((w for w in sh.windows() if w["id"] not in before), None)
            if win:
                break
        if win is None:
            print(
                f"COVERAGE {json.dumps({'app': name, 'window': False, 'exit': proc.poll(), 'stderr': open(f'{TMP}/{name}.err').read()[-400:]})}",
                flush=True,
            )
            proc.terminate()
            continue
        await asyncio.sleep(15)  # big apps build their accessible tree lazily
        win = next((w for w in sh.windows() if w["id"] == win["id"]), win)
        frame = list(win["frame"])
        found = []

        def collect(pid=win["pid"], found=found, frame=frame):
            for app in perception._apps({pid}):
                found.append(walk(app, frame))

        await asyncio.to_thread(collect)
        out = {"app": name, "window_app_id": win["app_id"], "frame": frame,
               "tree": found[0] if found else None}  # fmt: skip
        print(f"COVERAGE {json.dumps(out)}", flush=True)
        proc.terminate()
        await asyncio.sleep(3)
        proc.kill()


asyncio.run(main(), loop_factory=gi.events.GLibEventLoopPolicy().new_event_loop)
shutil.rmtree(TMP, ignore_errors=True)
