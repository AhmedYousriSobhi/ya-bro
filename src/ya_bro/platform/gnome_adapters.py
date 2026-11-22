"""GNOME adapters for the step loop (ADR-0004, ADR-0023): bridge, overlay and AT-SPI perceiver.

Needs PyGObject, so it runs under the system python3 (`broctl show`). Scope is enforced here too:
the perceiver only walks applications that own a window the extension reports, and the extension
reports only allowed windows.
"""

from __future__ import annotations

import asyncio
import contextlib

import gi

gi.require_version("Gio", "2.0")
gi.require_version("Atspi", "2.0")
from gi.repository import Atspi, Gio, GLib  # noqa: E402

from ya_bro.types import ElementRef, Rect, WindowInfo  # noqa: E402

PREFIX = "io.github.ahmedyousrisobhi.YaBro"
DEST = f"{PREFIX}.Shell"
PATH = "/io/github/ahmedyousrisobhi/YaBro/Shell"
BRIDGE = f"{DEST}.Bridge1"
OVERLAY = f"{DEST}.Overlay1"
ROLE_ALIASES = {"button": {"button", "push button"}}
MAX_DEPTH = 16
MAX_NODES = 4000


def _call(bus, iface, method, params=None):
    return bus.call_sync(
        DEST, PATH, iface, method, params, None, Gio.DBusCallFlags.NONE, 3000, None
    )


class GnomeBridge:
    def __init__(self, bus: Gio.DBusConnection) -> None:
        self._bus = bus

    def raw_windows(self) -> list[dict]:
        return _call(self._bus, BRIDGE, "ListWindows").unpack()[0]

    async def windows(self) -> list[WindowInfo]:
        return [
            WindowInfo(str(w["id"]), w["app_id"], "", Rect(*w["frame"]), w["focused"])
            for w in self.raw_windows()
        ]

    async def focused_window(self) -> WindowInfo | None:
        return next((w for w in await self.windows() if w.focused), None)


class GnomeOverlay:
    """Overlay1 over D-Bus. Pings every 2 s (the extension hides after ~6 s of silence)."""

    def __init__(self, bus: Gio.DBusConnection, bridge: GnomeBridge) -> None:
        self._bus = bus
        self._bridge = bridge
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._serial = 0
        self._ping: asyncio.Task | None = None
        self.last_target: Rect | None = None
        bus.signal_subscribe(
            DEST, OVERLAY, "UserEvent", PATH, None, Gio.DBusSignalFlags.NONE, self._on_event
        )

    def _on_event(self, _c, _s, _p, _i, _sig, params) -> None:
        kind = params.unpack()[0]
        if kind == "stop_key":
            self._queue.put_nowait("stop")
        elif kind.startswith("button:"):
            self._queue.put_nowait(kind.split(":", 1)[1])

    def _window_for(self, target: Rect | None) -> int:
        wins = self._bridge.raw_windows()
        if target is not None:
            cx, cy = target.center
            for w in wins:
                x, y, ww, hh = w["frame"]
                if x <= cx < x + ww and y <= cy < y + hh:
                    return w["id"]
        return next((w["id"] for w in wins if w["focused"]), 0)

    async def show_step(
        self, target: Rect | None, bubble_text: str, buttons: tuple[str, ...] = ()
    ) -> None:
        self.last_target = target
        args = {
            "ring": GLib.Variant("s", "confident" if target else "none"),
            "text": GLib.Variant("s", bubble_text),
            "buttons": GLib.Variant("as", list(buttons)),
            "follow_window": GLib.Variant("t", self._window_for(target)),
        }
        if target:
            args["target"] = GLib.Variant("(iiii)", (target.x, target.y, target.w, target.h))
        else:
            # Bubble-only: park it by the focused allowed window rather than a screen corner.
            win = next((w for w in self._bridge.raw_windows() if w["focused"]), None)
            if win:
                x, y, w, _h = win["frame"]
                args["bubble_at"] = GLib.Variant("(ii)", (x + 20, y + 20))
        _call(self._bus, OVERLAY, "ShowStep", GLib.Variant("(a{sv})", (args,)))
        if self._ping is None:
            self._ping = asyncio.get_running_loop().create_task(self._keepalive())

    async def _keepalive(self) -> None:
        while True:
            self._serial += 1
            with contextlib.suppress(GLib.Error):
                _call(self._bus, OVERLAY, "Ping", GLib.Variant("(u)", (self._serial,)))
            await asyncio.sleep(2)

    async def fly_pointer(self, to: Rect) -> None:
        x, y = to.center
        _call(self._bus, OVERLAY, "FlyPointer", GLib.Variant("((ii)u)", ((x, y), 600)))

    async def hide(self) -> None:
        with contextlib.suppress(GLib.Error):
            _call(self._bus, OVERLAY, "Hide")

    async def events(self):
        while True:
            yield await self._queue.get()


def _text_of(node) -> str:
    try:
        return Atspi.Text.get_text(node, 0, Atspi.Text.get_character_count(node)) or ""
    except GLib.Error:
        return ""


def _matches(node, role: str, name: str, text: str = "") -> bool:
    try:
        if node.get_role_name() not in ROLE_ALIASES.get(role, {role}):
            return False
        if name and (node.get_name() or "") != name:
            return False
    except GLib.Error:
        return False
    return not text or text in _text_of(node)


def _child(node, index: int):
    try:
        return node.get_child_at_index(index)
    except GLib.Error:
        return None


class AtspiPerception:
    def __init__(self, bridge: GnomeBridge, offset: tuple[int, int] = (0, 0)) -> None:
        self._bridge = bridge
        self._offset = offset

    def _pids(self, app_id: str) -> dict[int, dict]:
        """Allowed windows of this app by pid. Nothing else is ever walked."""
        out: dict[int, dict] = {}
        for w in self._bridge.raw_windows():
            if w["app_id"] == app_id:
                if w["pid"] not in out or w["focused"]:
                    out[w["pid"]] = w
        return out

    @staticmethod
    def _apps(pids):
        desktop = Atspi.get_desktop(0)
        for i in range(desktop.get_child_count()):
            app = _child(desktop, i)
            try:
                if app and app.get_process_id() in pids:
                    yield app
            except GLib.Error:
                continue

    def _find(self, app_id: str, role: str, name: str, text: str) -> list[ElementRef]:
        pids = self._pids(app_id)
        found: list[ElementRef] = []
        budget = [MAX_NODES]

        def walk(node, trail, pid, depth):
            if depth > MAX_DEPTH or budget[0] <= 0 or node is None:
                return
            budget[0] -= 1
            if depth and _matches(node, role, name, text):
                found.append(ElementRef(app_id, role, name, f"{pid}:" + "/".join(map(str, trail))))
            try:
                count = node.get_child_count()
            except GLib.Error:
                return
            for i in range(count):
                walk(_child(node, i), [*trail, i], pid, depth + 1)

        for app in self._apps(pids):
            walk(app, [], app.get_process_id(), 0)
        return found

    def _resolve(self, ref: ElementRef):
        """(app, node, window) for a ref, or None when it moved, vanished or left scope."""
        try:
            pid_s, trail = ref.path.split(":", 1)
            pid = int(pid_s)
            idx = [int(p) for p in trail.split("/") if p != ""]
        except ValueError:
            return None
        win = self._pids(ref.app_id).get(pid)
        if win is None:  # the app's window left scope: never answer for it
            return None
        for app in self._apps({pid}):
            node = app
            for i in idx:
                node = _child(node, i)
                if node is None:
                    return None
            return (app, node, win) if _matches(node, ref.role, ref.name) else None
        return None

    def _read_text(self, ref: ElementRef) -> str:
        found = self._resolve(ref)
        return _text_of(found[1]) if found else ""

    def _locate(self, ref: ElementRef) -> Rect | None:
        found = self._resolve(ref)
        if found is None:
            return None
        app, node, win = found
        ext = node.get_extents(Atspi.CoordType.WINDOW)
        if ext.width <= 0 or ext.height <= 0:
            return None
        try:
            toolkit = (app.get_toolkit_version() or "").split(".")[0]
            name = (app.get_toolkit_name() or "").lower()
        except GLib.Error:
            toolkit, name = "", ""
        # S1 measured: GTK4 and libadwaita extents start at the frame, GTK3 at the buffer.
        origin = win["buffer"] if name == "gtk" and toolkit == "3" else win["frame"]
        dx, dy = self._offset
        return Rect(origin[0] + ext.x + dx, origin[1] + ext.y + dy, ext.width, ext.height)

    async def find(
        self, app_id: str, role: str, name: str = "", text: str = ""
    ) -> list[ElementRef]:
        return await asyncio.to_thread(self._find, app_id, role, name, text)

    async def locate(self, ref: ElementRef) -> Rect | None:
        return await asyncio.to_thread(self._locate, ref)

    async def read_text(self, ref: ElementRef) -> str:
        return await asyncio.to_thread(self._read_text, ref)
