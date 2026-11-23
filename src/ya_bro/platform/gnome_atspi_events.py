"""UiEventSource on GNOME: AT-SPI events of the allowed, struggle-enabled apps only (ADR-0010).

Needs PyGObject (system python3, like the perceiver). The AT-SPI registry delivers events of every
app on the desktop to a listener; nothing is filtered at the source, so the first thing every
callback does is look up the app's process in the bridge's window list and drop the event unless the
app is allowed (the extension lists only allowed windows) and enabled for struggle. Nothing else of
a dropped event is read. For kept events only roles, states, counts and indexes are read; the text
inserted or deleted (`any_data`) is never touched, and a dialog title is hashed on the spot with a
per-run random salt (the same dialog gets the same key all run, the hash is not reversible without
the salt, and nothing is stored or logged).
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
from collections.abc import AsyncIterator, Callable

import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi, GLib  # noqa: E402

from ya_bro.platform.gnome_adapters import GnomeBridge  # noqa: E402
from ya_bro.types import UiEvent  # noqa: E402
from ya_bro.ui_events import RawEvent, Translator  # noqa: E402

REGISTERED = (
    "object:state-changed:expanded",
    "object:children-changed:add",
    "object:children-changed:remove",
    "object:text-changed:insert",
    "object:text-changed:delete",
)
WINDOW_REFRESH = 2.0  # seconds between reads of the bridge's window list (pid -> app)
TICK = 0.05


class AtspiUiEvents:
    def __init__(
        self,
        bridge: GnomeBridge,
        watching: Callable[[str], bool],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._bridge = bridge
        self._watching = watching
        self._clock = clock
        self._salt = os.urandom(16)
        self._pids: dict[int, str] = {}
        self._app_pid: dict[int, tuple[Atspi.Accessible, int]] = {}  # keeps the object alive
        self._translator = Translator()
        self._queue: asyncio.Queue[UiEvent] = asyncio.Queue()
        self._listener: Atspi.EventListener | None = None

    def _token(self, *parts: str) -> str:
        h = hashlib.sha256(self._salt + "\0".join(parts).encode())
        return "k" + h.hexdigest()[:10]

    def _pid_of(self, source) -> int | None:
        try:
            app = source.get_application()
            if app is None:
                return None
            cached = self._app_pid.get(id(app))
            if cached is None:
                if len(self._app_pid) > 256:
                    self._app_pid.clear()
                cached = self._app_pid[id(app)] = (app, app.get_process_id())
            return cached[1]
        except GLib.Error:
            return None

    def _raw(self, e, app: str) -> RawEvent | None:
        """Only roles, states, counts and indexes; never `any_data` of a text event."""
        t = self._clock()
        src = e.source
        try:
            role = src.get_role_name()
            if e.type.startswith("object:state-changed:expanded"):
                states = src.get_state_set()
                popup = states.contains(Atspi.StateType.HAS_POPUP) or states.contains(
                    Atspi.StateType.EXPANDABLE
                )
                key = self._token(src.path) if role != "menu item" else ""
                return RawEvent(t, app, "expanded", role, key, e.detail1, popup=popup)
            if e.type.startswith("object:text-changed"):
                kind = "text_inserted" if e.type.endswith("insert") else "text_deleted"
                return RawEvent(t, app, kind, role, length=e.detail2)
            if role != "application":
                return None
            kind = "child_added" if e.type.endswith("add") else "child_removed"
            if kind == "child_removed":  # the child is already gone
                return RawEvent(t, app, kind, role, slot=e.detail1)
            child = e.any_data
            if child is None:
                return None
            child_role = child.get_role_name()
            modal = child.get_state_set().contains(Atspi.StateType.MODAL)
            key = self._token(child_role, child.get_name() or "")
            return RawEvent(t, app, kind, role, key, child_role=child_role, modal=modal,
                            slot=e.detail1)  # fmt: skip
        except GLib.Error:
            return None

    def _on_event(self, e) -> None:
        pid = self._pid_of(e.source)
        app = self._pids.get(pid) if pid is not None else None
        if app is None or not self._watching(app):
            return  # not allowed, or not enabled: nothing else is read
        raw = self._raw(e, app)
        if raw is not None:
            for ui in self._translator.feed(raw):
                self._queue.put_nowait(ui)

    def _refresh(self) -> None:
        try:
            self._pids = {int(w["pid"]): str(w["app_id"]) for w in self._bridge.raw_windows()}
        except GLib.Error:
            self._pids = {}  # the extension is gone: watch nothing

    async def events(self) -> AsyncIterator[UiEvent]:
        # The first call connects to the accessibility bus. Run in the loop's own thread, or as a
        # bare `Atspi.init()`, it aborted the process in the isolated shell; this way it holds.
        await asyncio.to_thread(lambda: Atspi.get_desktop(0).get_child_count())
        self._listener = Atspi.EventListener.new(self._on_event)
        for t in REGISTERED:
            self._listener.register(t)
        next_refresh = 0.0
        try:
            while True:
                now = self._clock()
                if now >= next_refresh:
                    await asyncio.to_thread(self._refresh)
                    next_refresh = now + WINDOW_REFRESH
                # libatspi dispatches on the default main context; the asyncio loop runs its own.
                ctx = GLib.MainContext.default()
                while ctx.iteration(False):
                    pass
                for ui in self._translator.flush(self._clock()):
                    self._queue.put_nowait(ui)
                try:
                    yield await asyncio.wait_for(self._queue.get(), TICK)
                except TimeoutError:
                    continue
        finally:
            listener, self._listener = self._listener, None
            for t in REGISTERED:
                listener.deregister(t)
