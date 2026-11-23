"""`broctl struggle watch`: the struggle detector with the offer bubble on GNOME (ADR-0010 §4).

Runs under the system python3 (PyGObject), like `gnome_show`:

    PYTHONPATH=<repo>/src python3 -m ya_bro.platform.gnome_offers [--seconds N]

The extension only talks to the process that owns the Core bus name, and `broctl show` owns it
while a step loop runs. So this process takes the name only while a bubble is up, and treats
"someone else owns Core" as "a step loop is running": it asks nothing then.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import sys
import time

import gi
import gi.events

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

from ya_bro import config, packs, struggle, struggle_host, targets  # noqa: E402
from ya_bro.offers import OfferBubble, Result  # noqa: E402
from ya_bro.persona import Persona  # noqa: E402
from ya_bro.platform.gnome_adapters import PREFIX, GnomeBridge, GnomeOverlay, own_perceiver  # noqa: E402
from ya_bro.platform.gnome_atspi_events import AtspiUiEvents  # noqa: E402
from ya_bro.platform.gnome_idle import GnomeIdleSource  # noqa: E402
from ya_bro.shell_spool import ShellSpool  # noqa: E402
from ya_bro.struggle import Offer  # noqa: E402

CORE = f"{PREFIX}.Core"
SETTLE = 0.4  # seconds for the extension to notice the new owner (gnome_show waits 0.5)


def owner_of(bus: Gio.DBusConnection, name: str) -> str:
    try:
        reply = bus.call_sync(
            "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
            "GetNameOwner", GLib.Variant("(s)", (name,)), None, Gio.DBusCallFlags.NONE, 2000, None,
        )  # fmt: skip
    except GLib.Error:
        return ""
    return reply.unpack()[0]


class CoreLease:
    """The Core name, held only while a bubble is on screen."""

    def __init__(self, bus: Gio.DBusConnection) -> None:
        self._bus = bus
        self._id = 0
        self._got = False
        self._lost = False

    async def acquire(self) -> bool:
        self._got = self._lost = False
        self._id = Gio.bus_own_name_on_connection(
            self._bus, CORE, Gio.BusNameOwnerFlags.DO_NOT_QUEUE,
            lambda *_: setattr(self, "_got", True),
            lambda *_: setattr(self, "_lost", True),
        )  # fmt: skip
        for _ in range(20):
            if self._got or self._lost:
                break
            await asyncio.sleep(0.05)
        if not self._got:
            self.release()
            return False
        await asyncio.sleep(SETTLE)
        return True

    def release(self) -> None:
        if self._id:
            Gio.bus_unown_name(self._id)
            self._id = 0


async def run(seconds: int) -> int:
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    det = struggle.Detector(time.time, struggle.default_state_path())
    found = targets.load_all()
    commands = struggle_host.command_apps(found)
    gui = sorted(a for a in det._opted_in if det.is_watching(a) and a not in commands.values())
    watched = sorted({a for a in commands.values() if det.is_watching(a)} | set(gui))
    if not watched:
        print("watching nothing: `broctl struggle enable APP` first")
        return 1
    if owner_of(bus, f"{PREFIX}.Shell") == "":
        print("cannot reach the Bro extension; run: broctl doctor")
        return 1
    cfg = config.load()
    persona = Persona(humour=cfg.humour, locale="ar" if cfg.language == "ar" else "en",
                      less_chatty=cfg.less_chatty)  # fmt: skip
    perceiver = own_perceiver(bus)  # read the allowed windows; Core is held only for a bubble
    bridge = GnomeBridge(bus)
    overlay = GnomeOverlay(bus, bridge)
    packs_found, _problems = packs.load_all()
    struggle_host.tune_from_packs(det, packs_found, commands, gui)

    async def focused() -> str | None:
        win = await bridge.focused_window()
        return win.app_id if win else None

    lease = CoreLease(bus)

    def log(event: str, **fields) -> None:
        print(f"{event} " + " ".join(f"{k}={v}" for k, v in fields.items()), flush=True)

    def accepted(offer: Offer) -> None:
        # The hand-over: the bro greets and the user says what they want (`broctl ask "..."`).
        log("struggle_accepted", app=offer.app)

    bubble = OfferBubble(det, overlay, persona, on_accept=accepted)

    async def present(offer: Offer) -> Result:
        if not await lease.acquire():  # a step loop owns Core: stay out of its way
            det.withdraw(offer)
            return Result("withdrawn")
        try:
            return await bubble.present(offer)
        finally:
            lease.release()

    spool = ShellSpool()
    shell_cmds = sorted(c for c, a in commands.items() if det.is_watching(a))
    if shell_cmds:
        spool.open(shell_cmds)
    host = struggle_host.StruggleHost(
        det, commands, shell=spool if shell_cmds else None, sink=log, present=present,
        idle=GnomeIdleSource(), focused_app=focused, ui=AtspiUiEvents(bridge, det.is_watching),
        on_offer=lambda o: print(f"OFFER ({o.score:.1f}): {o.why}", flush=True),
        busy=lambda: owner_of(bus, CORE) != "",
    )  # fmt: skip
    print(
        f"watching {', '.join(watched)} for {seconds} s. Stop: the No button or Super+Shift+Esc.",
        flush=True,
    )
    try:
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(host.run(), seconds)
    finally:
        if shell_cmds:
            spool.close()
        lease.release()
        Gio.bus_unown_name(perceiver)
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
