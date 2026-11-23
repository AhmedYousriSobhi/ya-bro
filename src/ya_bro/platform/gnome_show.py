"""`broctl show`: run the Show-me loop on GNOME. Runs under the system python3 (PyGObject).

    PYTHONPATH=<repo>/src python3 -m ya_bro.platform.gnome_show <plan.toml> [--app ID]

Reads an optional web-target token from stdin (one line, may be empty), like gnome_demo.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import gi
import gi.events

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

from ya_bro import config, plans  # noqa: E402
from ya_bro.platform.gnome_adapters import (  # noqa: E402
    BRIDGE,
    PREFIX,
    AtspiPerception,
    GnomeBridge,
    GnomeOverlay,
    _call,
)
from ya_bro.policy import ShowMePolicy  # noqa: E402
from ya_bro.steps import StepLoop, Timing  # noqa: E402
from ya_bro.tone import Tone  # noqa: E402


async def run(plan_path: Path, app_override: str, token: str) -> int:
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    try:
        plan, app, _ = plans.load(plan_path, app_override)
    except plans.PlanError as e:
        print(e)
        return 2
    Gio.bus_own_name_on_connection(bus, f"{PREFIX}.Core", Gio.BusNameOwnerFlags.NONE, None, None)
    await asyncio.sleep(0.5)  # let the extension notice the new owner
    if token:
        _call(bus, BRIDGE, "SetScopeTokens", GLib.Variant("(as)", ([token],)))
    bridge = GnomeBridge(bus)
    try:
        wins = bridge.raw_windows()
    except GLib.Error as e:
        print(f"cannot reach the Ya-Bro extension ({e.message}); run: broctl doctor")
        return 1
    if not app:
        focused = next((w for w in wins if w["focused"]), wins[0] if wins else None)
        app = focused["app_id"] if focused else ""
    if not app:
        print("no allowed window is open; open the app you allowed (broctl apps list)")
        return 1
    plan = plans.rebind(plan, app)
    overlay = GnomeOverlay(bus, bridge)

    def log(event: str, **fields) -> None:
        print(f"{event} " + " ".join(f"{k}={v}" for k, v in fields.items()), flush=True)

    loop = StepLoop(
        AtspiPerception(bridge, plan.extents_offset),
        overlay,
        bridge,
        ShowMePolicy(),
        Timing(done_hold=1.5),
        log=log,
        tone=Tone(config.load(app).humour),
    )
    print(f"showing {len(plan.steps)} steps on {app}. Stop: bubble button or Super+Shift+Esc.")
    outcome = await loop.run(plan, app)
    print(f"finished: {outcome}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="broctl show")
    ap.add_argument("plan", type=Path)
    ap.add_argument("--app", default="")
    args = ap.parse_args(argv)
    token = sys.stdin.readline().strip()
    return asyncio.run(
        run(args.plan, args.app, token), loop_factory=gi.events.GLibEventLoopPolicy().new_event_loop
    )


if __name__ == "__main__":
    sys.exit(main())
