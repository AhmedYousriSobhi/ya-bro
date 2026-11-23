"""`broctl struggle watch` on GNOME: the detector fed by every source at once, offers printed.

Runs under the system python3 (it needs PyGObject for AT-SPI); `broctl` starts it the way it starts
the step loop. Nothing here ever answers or acts: an offer is printed, never shown to anyone.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import sys
import time

import gi

gi.require_version("Gio", "2.0")
import gi.events  # noqa: E402
from gi.repository import Gio  # noqa: E402

from ya_bro import packs, struggle, struggle_host, targets  # noqa: E402
from ya_bro.platform.gnome_adapters import GnomeBridge  # noqa: E402
from ya_bro.platform.gnome_atspi_events import AtspiUiEvents  # noqa: E402
from ya_bro.platform.gnome_idle import GnomeIdleSource  # noqa: E402
from ya_bro.shell_spool import ShellSpool  # noqa: E402


async def run(seconds: int) -> int:
    det = struggle.Detector(time.time, struggle.default_state_path())
    commands = struggle_host.command_apps(targets.load_all())
    gui = sorted(a for a in det._opted_in if det.is_watching(a) and a not in commands.values())
    watched = sorted({a for a in commands.values() if det.is_watching(a)} | set(gui))
    if not watched:
        print("watching nothing: `broctl struggle enable APP` first")
        return 1
    found, _problems = packs.load_all()
    struggle_host.tune_from_packs(det, found, commands, gui)
    bridge = GnomeBridge(Gio.bus_get_sync(Gio.BusType.SESSION, None))

    async def focused() -> str | None:
        win = await bridge.focused_window()
        return win.app_id if win else None

    spool = ShellSpool()
    shell_cmds = sorted(c for c, a in commands.items() if det.is_watching(a))
    if shell_cmds:
        spool.open(shell_cmds)
    host = struggle_host.StruggleHost(
        det,
        commands,
        shell=spool if shell_cmds else None,
        idle=GnomeIdleSource(),
        focused_app=focused,
        on_offer=lambda o: print(f"OFFER ({o.score:.1f}): {o.why}", flush=True),
        ui=AtspiUiEvents(bridge, det.is_watching),
    )
    print(
        f"watching {', '.join(watched)} for {seconds} s (menus, dialogs, alerts, undo as counts "
        "only; apps must also be allowed with `broctl apps allow`); you are never interrupted here",
        flush=True,
    )
    try:
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(host.run(), seconds)
    finally:
        if shell_cmds:
            spool.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="broctl struggle watch")
    ap.add_argument("--seconds", type=int, default=300)
    args = ap.parse_args(argv)
    try:
        return asyncio.run(
            run(args.seconds), loop_factory=gi.events.GLibEventLoopPolicy().new_event_loop
        )
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
