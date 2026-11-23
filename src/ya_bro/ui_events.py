"""Raw accessibility events to content-free UI events (ADR-0010 §1, measured in #9).

Pure logic, no `gi`: a platform source turns each AT-SPI event into a `RawEvent` (a type, a role,
a few numbers and an opaque key, never a name or text) and this turns a stream of them into the
detector's menu, dialog, alert, undo and typing kinds. What GTK4 on GNOME 50 really sends is
different from what the ADR's table assumed, and the rules below follow what was measured:

- A popover menu has no `showing` event. Its MenuButton (role button, state `expandable` while open,
  never HAS_POPUP) reports `expanded` 1 on open and 0 on close,
  and its items have no accessible name. A click on an item makes the item report `expanded` 0 a few
  milliseconds *after* the button did, so a close is held for `MENU_GRACE` before it is called a
  plain dismissal. Toggle-closing or clicking away never sends the item event.
- A dialog is a `children-changed` "add" on the application node (role frame and modal, dialog or
  alert), and its close is a "remove" whose child is already gone. Cancel and OK look the same, so a
  dialog that is closed within `QUICK_DIALOG` of opening counts as bounced.
- Undo has no event. It shows as a `text-changed` delete, as backspace does; only a delete of two or
  more characters in one event is counted, so backspacing does not look like undo.
"""

from __future__ import annotations

from dataclasses import dataclass

from ya_bro.types import UiEvent

MENU_GRACE = 0.15  # seconds a menu close waits for the item event that follows an activation
QUICK_DIALOG = 3.0  # a dialog closed within this long of opening was bounced (detector: 3 s)
TYPING_EVERY = 1.0  # typing is reported at most this often, so it cannot flood the detector
BULK_DELETE = 2  # a delete of this many characters or more in one event is an undo, not backspace
MENU_BUTTON_ROLES = frozenset({"button", "toggle button", "menu button"})
DIALOG_ROLES = frozenset({"dialog", "alert"})


@dataclass(frozen=True, slots=True)
class RawEvent:
    """One accessibility event, reduced to what the rules need.

    `kind` is expanded, child_added, child_removed, text_inserted or text_deleted. `key` is an
    opaque token (a salted hash) naming a menu button or a dialog; `slot` is a child event's index.
    """

    t: float
    app: str
    kind: str
    role: str = ""  # of the source
    key: str = ""
    detail: int = 0  # expanded: 1 open, 0 closed
    length: int = 0  # characters inserted or deleted
    child_role: str = ""
    modal: bool = False
    popup: bool = (
        False  # on open: the source is expandable (GTK4 MenuButton: EXPANDABLE, no HAS_POPUP)
    )
    slot: int = -1


@dataclass
class _Menu:
    closed_at: float | None = None  # waiting out the grace period


class Translator:
    """Feed it `RawEvent`s in time order; call `flush(now)` regularly to release held closes."""

    def __init__(self) -> None:
        self._open: dict[tuple[str, str], _Menu] = {}
        self._item_closed: dict[str, float] = {}  # app -> when a menu item last collapsed
        self._dialogs: dict[tuple[str, int], tuple[str, str, float]] = {}  # (app, slot) -> kind...
        self._last_typing: dict[str, float] = {}

    def feed(self, e: RawEvent) -> list[UiEvent]:
        out = self.flush(e.t)
        if e.kind == "expanded":
            out += self._expanded(e)
        elif e.kind == "child_added":
            out += self._added(e)
        elif e.kind == "child_removed":
            out += self._removed(e)
        elif e.kind in ("text_inserted", "text_deleted"):
            out += self._text(e)
        return out

    def flush(self, now: float) -> list[UiEvent]:
        out: list[UiEvent] = []
        for (app, key), menu in list(self._open.items()):
            if menu.closed_at is not None and now - menu.closed_at >= MENU_GRACE - 1e-9:
                out += self._close(app, key, menu)
        return out

    def _close(self, app: str, key: str, menu: _Menu) -> list[UiEvent]:
        assert menu.closed_at is not None
        del self._open[(app, key)]
        item = self._item_closed.get(app)
        activated = item is not None and abs(item - menu.closed_at) <= MENU_GRACE
        out = [UiEvent(app, "menu_activated", key)] if activated else []
        return [*out, UiEvent(app, "menu_hidden", key)]

    def _expanded(self, e: RawEvent) -> list[UiEvent]:
        if e.role == "menu item":
            if e.detail == 0:
                self._item_closed[e.app] = e.t
            return []
        if e.role not in MENU_BUTTON_ROLES or (e.detail == 1 and not e.popup):
            return []  # not a menu button (the close event no longer carries the flag)
        slot = (e.app, e.key)
        if e.detail == 1:
            out = self._close(*slot, self._open[slot]) if slot in self._open else []
            self._open[slot] = _Menu()
            return [*out, UiEvent(e.app, "menu_shown", e.key)]
        menu = self._open.get(slot)
        if menu is not None and menu.closed_at is None:
            menu.closed_at = e.t
        return []

    def _shift(self, app: str, slot: int, by: int) -> None:
        moved = {
            (a, s + by if s >= slot else s): v for (a, s), v in self._dialogs.items() if a == app
        }
        self._dialogs = {k: v for k, v in self._dialogs.items() if k[0] != app} | moved

    def _added(self, e: RawEvent) -> list[UiEvent]:
        if e.role != "application":
            return []
        self._shift(e.app, e.slot, +1)
        if e.child_role == "alert":
            self._dialogs[(e.app, e.slot)] = ("alert", e.key, e.t)
            return [UiEvent(e.app, "alert", e.key)]
        if e.child_role in DIALOG_ROLES or (e.child_role == "frame" and e.modal):
            self._dialogs[(e.app, e.slot)] = ("dialog", e.key, e.t)
            return [UiEvent(e.app, "dialog_opened", e.key)]
        return []

    def _removed(self, e: RawEvent) -> list[UiEvent]:
        if e.role != "application":
            return []
        found = self._dialogs.pop((e.app, e.slot), None)
        self._shift(e.app, e.slot + 1, -1)
        if found is None or found[0] != "dialog":
            return []
        _kind, key, opened = found
        bounced = e.t - opened <= QUICK_DIALOG
        return [UiEvent(e.app, "dialog_cancelled" if bounced else "dialog_closed", key)]

    def _text(self, e: RawEvent) -> list[UiEvent]:
        if e.kind == "text_deleted" and e.length >= BULK_DELETE:
            return [UiEvent(e.app, "undo")]
        last = self._last_typing.get(e.app, -1e9)
        if e.t - last < TYPING_EVERY:
            return []
        self._last_typing[e.app] = e.t
        return [UiEvent(e.app, "typing")]
