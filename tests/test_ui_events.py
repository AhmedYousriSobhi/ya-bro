"""AT-SPI event sequences to content-free UI events. The sequences are what a real GTK4 app on
GNOME 50 sent in the isolated shell (tests/test_struggle_atspi.py reproduces them for real)."""

import asyncio
import contextlib

from tests.fakes import FakeUiEvents
from ya_bro import struggle_host
from ya_bro.struggle import Detector, Signal
from ya_bro.types import UiEvent
from ya_bro.ui_events import MENU_GRACE, RawEvent, Translator

APP = "org.example.App"


def ev(t, kind, **kw):
    return RawEvent(t, APP, kind, **kw)


def run(translator, events, until=None):
    out = []
    for e in events:
        out += translator.feed(e)
    return out + translator.flush(until if until is not None else events[-1].t + 1)


def kinds(out):
    return [(u.kind, u.key) for u in out]


def menu(t, key="m1", close_by="away"):
    """A GTK4 popover opens and closes; an item click adds the item's own event after."""
    seq = [ev(t, "expanded", role="button", key=key, detail=1, popup=True)]
    seq.append(ev(t + 1, "expanded", role="button", key=key, detail=0, popup=True))
    if close_by == "item":
        seq.append(ev(t + 1.014, "expanded", role="menu item", detail=0))
    return seq


def test_a_menu_closed_by_clicking_away_is_shown_then_hidden():
    out = run(Translator(), menu(0))
    assert kinds(out) == [("menu_shown", "m1"), ("menu_hidden", "m1")]


def test_a_menu_closed_by_an_item_is_activated_then_hidden():
    out = run(Translator(), menu(0, close_by="item"))
    assert kinds(out) == [("menu_shown", "m1"), ("menu_activated", "m1"), ("menu_hidden", "m1")]


def test_the_close_is_held_until_the_item_event_could_arrive():
    tr = Translator()
    tr.feed(ev(0, "expanded", role="button", key="m1", detail=1, popup=True))
    assert tr.feed(ev(1, "expanded", role="button", key="m1", detail=0, popup=True)) == []
    assert tr.flush(1 + MENU_GRACE / 2) == []
    assert kinds(tr.flush(1 + MENU_GRACE)) == [("menu_hidden", "m1")]


def test_an_old_item_event_does_not_make_a_later_dismissal_an_activation():
    seq = menu(0, close_by="item") + menu(10)
    out = run(Translator(), seq)
    assert [k for k, _ in kinds(out)].count("menu_activated") == 1


def test_expanders_and_combos_without_a_popup_are_not_menus():
    seq = [ev(0, "expanded", role="button", key="x", detail=1)]  # no HAS_POPUP
    seq += [ev(1, "expanded", role="button", key="x", detail=0)]
    assert run(Translator(), seq) == []


def test_a_close_without_an_open_is_ignored():
    assert (
        run(Translator(), [ev(0, "expanded", role="button", key="m", detail=0, popup=True)]) == []
    )


def dialog(t, closed_after, key="d1", role="frame", modal=True, slot=1):
    return [
        ev(t, "child_added", role="application", key=key, child_role=role, modal=modal, slot=slot),
        ev(t + closed_after, "child_removed", role="application", slot=slot),
    ]


def test_a_dialog_closed_at_once_is_a_bounce_and_one_kept_open_is_a_close():
    assert kinds(run(Translator(), dialog(0, 1.0))) == [
        ("dialog_opened", "d1"),
        ("dialog_cancelled", "d1"),
    ]
    assert kinds(run(Translator(), dialog(0, 20.0))) == [
        ("dialog_opened", "d1"),
        ("dialog_closed", "d1"),
    ]


def test_a_gtk4_alert_dialog_is_a_plain_dialog_and_a_gtk3_alert_is_an_alert():
    assert kinds(run(Translator(), dialog(0, 9, role="dialog")))[0] == ("dialog_opened", "d1")
    out = run(Translator(), dialog(0, 1, role="alert"))
    assert kinds(out) == [("alert", "d1")]  # closing an alert is not a bounced dialog


def test_a_second_non_modal_window_is_not_a_dialog():
    assert run(Translator(), dialog(0, 1, modal=False)) == []


def test_removing_the_main_window_is_not_a_dialog_closing():
    seq = [ev(0, "child_added", role="application", key="w", child_role="frame", slot=0)]
    seq += dialog(1, 1.0, slot=1)
    seq += [ev(5, "child_removed", role="application", slot=0)]
    assert [k for k, _ in kinds(run(Translator(), seq))] == ["dialog_opened", "dialog_cancelled"]


def test_dialogs_are_followed_when_other_windows_shift_the_indexes():
    tr = Translator()
    tr.feed(ev(0, "child_added", role="application", key="d1", child_role="dialog", slot=1))
    tr.feed(ev(1, "child_added", role="application", key="w2", child_role="frame", slot=0))
    out = tr.feed(ev(2, "child_removed", role="application", slot=2))  # the dialog, now at 2
    assert kinds(out) == [("dialog_cancelled", "d1")]


def test_undo_is_a_multi_character_delete_and_backspace_is_only_typing():
    tr = Translator()
    assert kinds(tr.feed(ev(0, "text_deleted", role="text", length=3))) == [("undo", "")]
    assert kinds(tr.feed(ev(5, "text_deleted", role="text", length=1))) == [("typing", "")]
    assert tr.feed(ev(5.2, "text_deleted", role="text", length=1)) == []  # at most 1 a second


def test_typing_is_reported_once_a_second_and_carries_no_text():
    tr = Translator()
    out = []
    for i in range(30):
        out += tr.feed(ev(i * 0.1, "text_inserted", role="text", length=1))
    assert [u.kind for u in out] == ["typing"] * 3
    assert all(u.key == "" and u.value == 0 for u in out)


def test_a_dialog_event_in_another_app_has_its_own_slots():
    tr = Translator()
    tr.feed(RawEvent(0, "a.one", "child_added", "application", "d", child_role="dialog", slot=1))
    out = tr.feed(RawEvent(1, "a.two", "child_removed", "application", slot=1))
    assert out == []


# -- through the detector: the sequences make the signals the ADR names ---------------------


def detector_for(events):
    d = Detector(lambda: 0.0)
    d.opt_in(APP)
    fired = []
    from ya_bro.struggle import Observation

    for t, u in events:
        fired += d.observe(Observation(t, u.app, u.kind, u.key, u.value))
    return fired


def test_three_quick_menu_dismissals_are_a_menu_thrash():
    tr = Translator()
    out = []
    for i in range(3):
        for e in menu(i * 4, close_by="away"):
            out += [(e.t, u) for u in tr.feed(e)]
        out += [(i * 4 + 1.2, u) for u in tr.flush(i * 4 + 1.3)]
    assert Signal.MENU_THRASH in detector_for(out)


def test_three_menus_that_chose_an_item_are_not():
    tr = Translator()
    out = []
    for i in range(3):
        for e in menu(i * 4, close_by="item"):
            out += [(e.t, u) for u in tr.feed(e)]
        out += [(i * 4 + 1.2, u) for u in tr.flush(i * 4 + 1.3)]
    assert Signal.MENU_THRASH not in detector_for(out)


def test_two_bounced_dialogs_are_a_dialog_bounce():
    tr = Translator()
    out = []
    for i in range(2):
        for e in dialog(i * 10, 1.0):
            out += [(e.t, u) for u in tr.feed(e)]
    assert Signal.DIALOG_BOUNCE in detector_for(out)


# -- the host ---------------------------------------------------------------------------


class Clock:
    t = 1_000_000.0

    def __call__(self):
        return self.t


async def test_the_host_feeds_the_detector_from_a_ui_source_and_logs_names_only():
    clock = Clock()
    d = Detector(clock)
    d.opt_in(APP)
    d.opt_in("not.in.the.list")
    ui = [UiEvent(APP, "dialog_opened", "k1"), UiEvent(APP, "dialog_cancelled", "k1")] * 2
    ui += [UiEvent("someone.else", "alert", "k9")]  # not opted in below
    d.opt_out("not.in.the.list")
    offers, log = [], []
    host = struggle_host.StruggleHost(
        d, {}, ui=FakeUiEvents(ui), on_offer=offers.append,
        sink=lambda name, **f: log.append((name, f)), clock=clock,
    )  # fmt: skip
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(host.run(), 0.3)
    assert ("struggle_signal", {"signal": "dialog_bounce"}) in log
    assert all(set(f) <= {"signal", "app", "score"} for _n, f in log)
    assert d.score("someone.else") == 0.0


async def test_a_bad_token_from_a_source_never_stops_the_watch():
    clock = Clock()
    d = Detector(clock)
    d.opt_in(APP)
    ui = [UiEvent(APP, "dialog_opened", "has a space and text")] + [
        UiEvent(APP, "dialog_opened", "k1"),
        UiEvent(APP, "dialog_cancelled", "k1"),
    ] * 2
    log = []
    host = struggle_host.StruggleHost(
        d, {}, ui=FakeUiEvents(ui), sink=lambda n, **f: log.append((n, f)), clock=clock
    )
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(host.run(), 0.3)
    assert ("struggle_signal", {"signal": "dialog_bounce"}) in log


def test_a_pack_that_tunes_menu_thrash_changes_that_apps_weight(tmp_path):
    from ya_bro import packs

    root = tmp_path / "myapp"
    root.mkdir()
    (root / "pack.toml").write_text(
        '[pack]\nid = "myapp"\nname = "My app"\nversion = "0.1.0"\nlicense = "MIT"\n'
        f'locales = ["en"]\n[match]\ndesktop_ids = ["{APP}"]\n'
    )
    (root / "knowledge.md").write_text("A test app.\n")
    (root / "signals.toml").write_text("[weights]\nmenu_thrash = 0.0\n")
    found, problems = packs.load_all([tmp_path])
    assert not problems and found
    d = Detector(lambda: 0.0)
    d.opt_in(APP)
    struggle_host.tune_from_packs(d, found, {}, [APP])
    assert d.weight(APP, Signal.MENU_THRASH) == 0.0
    assert d.weight(APP, Signal.UNDO_LOOP) > 0.0
