"""Find named widgets of the GTK4 fixture via AT-SPI; prints found names as JSON. System python3."""

import json
import sys
import time

import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi  # noqa: E402

WANT = {"Fixture Button": "button"}


def walk(node, out, depth=0):
    if depth > 12 or node is None:
        return
    try:
        out.append((node.get_name(), node.get_role_name()))
        for i in range(node.get_child_count()):
            walk(node.get_child_at_index(i), out, depth + 1)
    except Exception:  # app may be mid-update; retry loop below
        pass


deadline = time.time() + 20
found = {}
while time.time() < deadline and len(found) < len(WANT):
    desktop = Atspi.get_desktop(0)
    nodes = []
    for i in range(desktop.get_child_count()):
        walk(desktop.get_child_at_index(i), nodes)
    found = {n: r for n, r in nodes if n in WANT and r == WANT[n]}
    time.sleep(0.5)

print(json.dumps(found))
sys.exit(0 if len(found) == len(WANT) else 1)
