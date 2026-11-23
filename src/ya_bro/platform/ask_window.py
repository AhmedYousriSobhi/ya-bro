"""The ask window (#3): a small GTK4 window with one text field, for `broctl ask` with no goal.

Returns what the user typed, or None when they cancel (Cancel, Esc, closing the window). The text
goes nowhere until the caller sends it; nothing is logged here.
"""

from __future__ import annotations

import asyncio

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from ya_bro.platform.docked_overlay import APP_ID  # noqa: E402


class AskWindow:
    def __init__(self, placeholder: str = "What do you want to do?") -> None:
        GLib.set_prgname(APP_ID)
        self._result: asyncio.Future[str | None] | None = None
        self.win = Gtk.Window(title="Ask Bro", resizable=False, default_width=420)
        self.entry = Gtk.Entry(placeholder_text=placeholder, hexpand=True)
        self.entry.connect("activate", lambda _e: self._finish(True))
        self.go = Gtk.Button(label="Go")
        self.go.connect("clicked", lambda _b: self._finish(True))
        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda _b: self._finish(False))
        row = Gtk.Box(spacing=6, margin_start=12, margin_end=12, margin_top=12, margin_bottom=12)
        for w in (self.entry, self.go, cancel):
            row.append(w)
        self.win.set_child(row)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.win.add_controller(keys)
        self.win.connect("close-request", lambda _w: self._finish(False) or False)

    def _on_key(self, _c, keyval, _code, _state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self._finish(False)
            return True
        return False

    def _finish(self, accepted: bool) -> None:
        text = self.entry.get_text().strip()
        if self._result is not None and not self._result.done():
            self._result.set_result(text if accepted and text else None)

    async def get(self) -> str | None:
        self._result = asyncio.get_running_loop().create_future()
        ctx = GLib.MainContext.default()

        async def drive() -> None:  # see DockedOverlay._drive: GTK is not serviced otherwise
            while True:
                while ctx.iteration(False):
                    pass
                await asyncio.sleep(0.01)

        pump = asyncio.create_task(drive())
        self.win.present()
        try:
            return await self._result
        finally:
            pump.cancel()
            self.win.set_visible(False)
            while ctx.iteration(False):
                pass
