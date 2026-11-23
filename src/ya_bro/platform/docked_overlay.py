"""Docked overlay (ADR-0006, #3): the bubble as a small GTK4 window, with no ring and no pointer.

For sessions where the Shell extension is missing or not loaded. It cannot point at the live app,
so a step that has a target says so in words; everything else (narration, buttons, Stop) is the same
Overlay contract the step loop already uses. Needs PyGObject and a GLib-driven asyncio loop.
"""

from __future__ import annotations

import asyncio

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from ya_bro.persona import is_rtl  # noqa: E402
from ya_bro.types import Rect  # noqa: E402

APP_ID = "io.github.ahmedyousrisobhi.YaBro.Docked"
LABELS = {
    "next": "Next",
    "repeat": "Repeat",
    "why": "Why?",
    "stop": "Stop",
    "copy": "Copy",
    "write": "Write it",
}


class DockedOverlay:
    def __init__(self) -> None:
        GLib.set_prgname(APP_ID)  # the Wayland app id, so the window can be told apart
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self.indicators: tuple[str, ...] = ("watching",)
        self.last_target: Rect | None = None
        self._pump: asyncio.Task | None = None
        self._copyable = ""
        self._win = Gtk.Window(title="Bro", resizable=False, default_width=360)
        self._win.set_hide_on_close(True)
        self._label = Gtk.Label(wrap=True, xalign=0, max_width_chars=44, selectable=False)
        self._label.set_margin_start(12)
        self._label.set_margin_end(12)
        self._label.set_margin_top(12)
        self._snippet = Gtk.Label(xalign=0, selectable=True, visible=False, wrap=False)
        self._snippet.add_css_class("monospace")
        self._snippet.set_margin_start(12)
        self._snippet.set_margin_end(12)
        self._row = Gtk.Box(spacing=6, margin_start=12, margin_end=12, margin_bottom=12)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.append(self._label)
        box.append(self._snippet)
        box.append(self._row)
        self._win.set_child(box)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self._win.add_controller(keys)
        self._win.connect("close-request", self._on_close)

    def _on_key(self, _c, keyval, _code, _state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self._queue.put_nowait("stop")
            return True
        return False

    def _on_close(self, _w) -> bool:
        self._queue.put_nowait("stop")  # closing the window counts as stop
        return False

    def _clicked(self, name: str) -> None:
        if name == "copy" and self._copyable:
            self._win.get_clipboard().set(
                self._copyable
            )  # the window has focus: it was just clicked
        self._queue.put_nowait(name)

    def _buttons(self, names: tuple[str, ...]) -> None:
        child = self._row.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._row.remove(child)
            child = nxt
        for name in names:
            b = Gtk.Button(label=LABELS.get(name, name))
            b.connect("clicked", lambda _b, n=name: self._clicked(n))
            self._row.append(b)

    async def show_step(
        self,
        target: Rect | None,
        bubble_text: str,
        buttons: tuple[str, ...] = (),
        mood: str = "",
        snippet: str = "",
    ) -> None:
        self.last_target = target
        self._label.set_text(bubble_text)
        self._snippet.set_text(snippet)
        self._snippet.set_direction(Gtk.TextDirection.LTR)
        self._snippet.set_visible(bool(snippet))
        self._copyable = snippet
        direction = Gtk.TextDirection.RTL if is_rtl(bubble_text) else Gtk.TextDirection.LTR
        self._win.set_direction(direction)
        self._buttons(buttons)
        if self._pump is None:
            self._pump = asyncio.get_running_loop().create_task(self._drive())
        self._win.present()  # takes focus: a docked window is the user's to use

    async def _drive(self) -> None:
        # Measured: under the GLib asyncio loop GTK's Wayland source is not serviced while the
        # loop sleeps (the window stays at 0 x 0), so iterate the default context ourselves.
        ctx = GLib.MainContext.default()
        while True:
            while ctx.iteration(False):
                pass
            await asyncio.sleep(0.01)

    async def set_indicators(self, names: tuple[str, ...]) -> None:
        self.indicators = names

    async def fly_pointer(self, to: Rect) -> None:
        return None  # nothing to fly: there is no overlay layer to draw on

    async def hide(self) -> None:
        self._win.set_visible(False)

    async def events(self):
        while True:
            yield await self._queue.get()
