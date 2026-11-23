import json
import os
import stat

import pytest

from ya_bro.struggle import (
    MAX_PER_DAY,
    ContentError,
    Detector,
    Observation,
    Signal,
)

APP = "workbench"
OTHER = "gimp"


class Clock:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t

    def tick(self, s):
        self.t += s


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def det(clock):
    d = Detector(clock)
    d.opt_in(APP)
    d.opt_in(OTHER)
    return d


def see(det, clock, kind, key="", value=0, app=APP):
    return det.observe(Observation(clock(), app, kind, key, value))


def fail(det, clock, key="benchctl", app=APP, code=1):
    return see(det, clock, "command_exit", key, code, app)


def fail_loop(det, clock, n=3, gap=5, **kw):
    for _ in range(n):
        fail(det, clock, **kw)
        clock.tick(gap)
    clock.tick(-gap)


# ---- the signals -----------------------------------------------------------------------------


def test_three_failures_of_one_command_in_five_minutes_offer_at_the_breakpoint(det, clock):
    fail(det, clock)
    clock.tick(30)
    fail(det, clock)
    assert det.poll() is None  # two is not a loop
    clock.tick(30)
    assert fail(det, clock) == [Signal.FAILING_COMMANDS]
    offer = det.poll()  # the command just finished: a breakpoint
    assert offer and offer.app == APP and offer.signals == {"failing_commands": 3}
    assert offer.why == "In workbench I saw 3 failed commands of the same name."


def test_failures_spread_over_more_than_five_minutes_are_not_a_loop(det, clock):
    for _ in range(3):
        assert fail(det, clock) == []
        clock.tick(200)
    assert det.poll() is None


def test_different_commands_do_not_add_up_and_a_success_ends_the_loop(det, clock):
    for name in ("a", "b", "c"):
        assert fail(det, clock, name) == []
        clock.tick(5)
    fail(det, clock, "benchctl")
    fail(det, clock, "benchctl")
    see(det, clock, "command_exit", "benchctl", 0)  # it worked
    assert fail(det, clock, "benchctl") == []  # counting starts over


def test_nothing_is_remembered_or_offered_for_an_app_that_is_not_opted_in(clock):
    d = Detector(clock)
    fail_loop(d, clock, app="stranger")
    assert d.poll() is None and d.score("stranger") == 0.0
    d.opt_in("stranger")
    assert d.is_watching("stranger")


def test_menu_thrash_needs_three_opens_and_closes_without_choosing(det, clock):
    fired = []
    for _ in range(3):
        see(det, clock, "menu_shown", "File")
        clock.tick(1)
        fired += see(det, clock, "menu_hidden", "File")
        clock.tick(2)
    assert fired == [Signal.MENU_THRASH]
    for _ in range(4):  # but choosing an item is just using the menu
        see(det, clock, "menu_shown", "Edit")
        see(det, clock, "menu_activated", "Edit")
        assert see(det, clock, "menu_hidden", "Edit") == []
        clock.tick(2)


def test_dialog_bounce_error_loop_undo_help_and_focus_pingpong(det, clock):
    out = []
    for _ in range(2):
        see(det, clock, "dialog_opened", "Export")
        clock.tick(1)
        out += see(det, clock, "dialog_cancelled", "Export")
        clock.tick(1)
    assert out == [Signal.DIALOG_BOUNCE]
    assert see(det, clock, "alert", "e1") == [] and see(det, clock, "alert", "e2") == [
        Signal.ERROR_LOOP
    ]
    assert [see(det, clock, "undo") for _ in range(4)][-1] == [Signal.UNDO_LOOP]
    assert see(det, clock, "help_opened") == [Signal.HELP_SEEKING]
    ping = []
    for i in range(7):
        ping += see(det, clock, "focus", "w1" if i % 2 == 0 else "w2")
        clock.tick(3)
    assert ping == [Signal.FOCUS_PINGPONG]


def test_a_slow_dialog_cancel_is_not_a_bounce(det, clock):
    for _ in range(3):
        see(det, clock, "dialog_opened", "Export")
        clock.tick(10)
        assert see(det, clock, "dialog_cancelled", "Export") == []


def test_idle_counts_only_with_something_unfinished_and_once_per_pause(det, clock):
    assert see(det, clock, "idle", value=30) == []  # nothing open, nothing failed
    fail(det, clock)
    clock.tick(5)
    assert see(det, clock, "idle", value=25) == [Signal.IDLE_IN_CONTEXT]
    assert see(det, clock, "idle", value=30) == []  # same pause
    see(det, clock, "idle", value=0)  # the user is back
    assert see(det, clock, "idle", value=25) == [Signal.IDLE_IN_CONTEXT]
    see(det, clock, "dialog_opened", "Save")
    see(det, clock, "idle", value=0)
    assert see(det, clock, "idle", value=22) == [Signal.IDLE_IN_CONTEXT]  # a dialog is open


# ---- when it may speak -----------------------------------------------------------------------


def test_no_offer_without_a_breakpoint_while_typing_or_in_fullscreen(det, clock):
    fail_loop(det, clock)
    assert det.poll() is not None
    det._pending = None
    det._last_offer = -1e9
    det._offers.clear()
    clock.tick(30)  # no longer a breakpoint
    assert det.poll() is None
    see(det, clock, "command_exit", "benchctl", 2)  # a command finished: breakpoint again
    see(det, clock, "typing")
    assert det.poll() is None  # typing
    clock.tick(3.5)
    det.fullscreen = True
    assert det.poll() is None
    det.fullscreen = False
    det.do_not_disturb = True
    assert det.poll() is None
    det.do_not_disturb = False
    fail_loop(det, clock)  # struggling again, at a breakpoint, and the typing is long past
    assert det.poll() is not None


def test_one_pending_offer_and_a_two_minute_cooldown(det, clock):
    fail_loop(det, clock)
    offer = det.poll()
    assert offer and det.poll() is None  # pending until answered
    det.answer(offer, "yes")
    fail_loop(det, clock)
    assert det.poll() is None  # cooling down
    clock.tick(121)
    fail_loop(det, clock)
    assert det.poll() is not None


def test_at_most_three_offers_an_hour_and_ten_a_day(det, clock):
    taken = 0
    for _ in range(40):
        fail_loop(det, clock, gap=1)
        offer = det.poll()
        if offer:
            taken += 1
            det.answer(offer, "yes")
        clock.tick(125)
        if taken == 3:
            break
    assert taken == 3
    fail_loop(det, clock)
    assert det.poll() is None  # the hour is used up
    clock.tick(3600)
    fail_loop(det, clock)
    assert det.poll() is not None
    day = 0
    det._offers.clear()
    det._offers.extend(clock() - i * 4000 for i in range(MAX_PER_DAY))
    fail_loop(det, clock)
    assert det.poll() is None and day == 0


def test_score_decays_with_a_ninety_second_half_life(det, clock):
    fail_loop(det, clock)
    first = det.score(APP)
    clock.tick(90)
    assert det.score(APP) == pytest.approx(first / 2, rel=0.01)
    clock.tick(400)
    see(det, clock, "alert", "e")
    assert det.poll() is None  # long ago: not struggling now


def test_a_weak_signal_alone_does_not_offer_but_two_do(det, clock):
    see(det, clock, "help_opened")
    assert det.poll() is None  # 0.8 < 1.4
    for _ in range(3):
        see(det, clock, "menu_shown", "File")
        see(det, clock, "menu_hidden", "File")
        clock.tick(1)
    see(det, clock, "alert", "x")  # a breakpoint
    offer = det.poll()
    assert offer and set(offer.signals) == {"help_seeking", "menu_thrash"}


def test_sensitivity_is_the_volume(clock):
    d = Detector(clock, sensitivity=4)
    d.opt_in(APP)
    see(d, clock, "help_opened")
    see(d, clock, "alert", "x")
    assert d.poll() is not None
    q = Detector(Clock(), sensitivity=1)
    q.opt_in(APP)
    fail_loop(q, q._clock)
    assert q.poll() is None  # 1.5 < 2.5
    with pytest.raises(ValueError):
        q.set_sensitivity(5)


def test_the_strongest_app_is_the_one_offered(det, clock):
    fail_loop(det, clock)
    fail_loop(det, clock, app=OTHER)
    fail_loop(det, clock, app=OTHER, key="convert")
    assert det.poll().app == OTHER  # two loops outweigh one


# ---- back-off --------------------------------------------------------------------------------


def refuse(det, clock):
    fail_loop(det, clock)
    offer = det.poll()
    assert offer
    det.answer(offer, "no")
    clock.tick(121)


def test_no_suppresses_that_signal_until_the_context_changes(det, clock):
    refuse(det, clock)
    fail_loop(det, clock)
    assert det.poll() is None  # same signal, same app, same context
    assert det.score(APP) == 0.0
    see(det, clock, "context")  # the task changed
    fail_loop(det, clock)
    assert det.poll() is not None


def test_a_success_counts_as_the_context_changing(det, clock):
    refuse(det, clock)
    see(det, clock, "command_exit", "benchctl", 0)
    fail_loop(det, clock)
    assert det.poll() is not None


def test_two_nos_in_a_row_silence_the_app_for_half_an_hour(det, clock):
    refuse(det, clock)
    see(det, clock, "context")
    refuse(det, clock)
    see(det, clock, "context")
    clock.tick(600)
    fail_loop(det, clock)
    assert det.poll() is None
    clock.tick(30 * 60)
    fail_loop(det, clock)
    assert det.poll() is not None


def test_ignoring_the_bubble_is_a_soft_no(det, clock):
    fail_loop(det, clock)
    det.answer(det.poll(), "ignored")
    assert det.stats()["ignored"] == 1
    clock.tick(121)
    fail_loop(det, clock)
    assert det.poll() is None


def test_yes_clears_the_score_and_the_streak(det, clock):
    refuse(det, clock)
    see(det, clock, "context")
    fail_loop(det, clock)
    det.answer(det.poll(), "yes")
    assert det.score(APP) == 0.0 and det.stats()["yes"] == 1


def test_three_nos_in_a_week_halve_that_weight_until_reset(tmp_path, clock):
    path = tmp_path / "struggle.json"
    d = Detector(clock, path)
    d.opt_in(APP)
    for _ in range(3):
        refuse(d, clock)
        see(d, clock, "context")
        clock.tick(24 * 3600)
    assert d.weight(APP, Signal.FAILING_COMMANDS) == 0.75
    again = Detector(clock, path)  # it remembers
    assert again.weight(APP, Signal.FAILING_COMMANDS) == 0.75
    assert again.weight(OTHER, Signal.FAILING_COMMANDS) == 1.5
    again.reset_learning(APP)
    assert again.weight(APP, Signal.FAILING_COMMANDS) == 1.5


def test_nos_older_than_a_week_do_not_count(tmp_path, clock):
    d = Detector(clock, tmp_path / "s.json")
    d.opt_in(APP)
    for _ in range(3):
        refuse(d, clock)
        see(d, clock, "context")
        clock.tick(8 * 24 * 3600)
    assert d.weight(APP, Signal.FAILING_COMMANDS) == 1.5


def test_not_for_this_app_turns_it_off_and_persists(tmp_path, clock):
    path = tmp_path / "s.json"
    d = Detector(clock, path)
    d.opt_in(APP)
    fail_loop(d, clock)
    d.answer(d.poll(), "never")
    assert not d.is_watching(APP) and d.stats()["never"] == 1
    assert not Detector(clock, path).is_watching(APP)
    d.opt_in(APP)  # until the user turns it back on
    assert Detector(clock, path).is_watching(APP)


def test_global_off_and_per_app_opt_out(det, clock):
    fail_loop(det, clock)
    det.enabled_globally = False
    assert det.poll() is None
    det.enabled_globally = True
    det.opt_out(APP)
    assert det.poll() is None


# ---- pack tuning, content rule, state --------------------------------------------------------


def test_a_pack_can_tune_weights_and_counts_within_bounds(det, clock):
    det.tune(APP, weights={"failing_commands": 0.5}, counts={"failing_commands": (2, 60.0)})
    fail(det, clock)
    clock.tick(5)
    assert fail(det, clock) == [Signal.FAILING_COMMANDS]  # two within a minute now
    assert det.weight(APP, Signal.FAILING_COMMANDS) == 0.5
    assert det.weight(OTHER, Signal.FAILING_COMMANDS) == 1.5
    for bad in ({"weights": {"failing_commands": 9}}, {"counts": {"undo_loop": (1, 5.0)}},
                {"weights": {"nonsense": 1}}):  # fmt: skip
        with pytest.raises(ValueError):
            det.tune(APP, **bad)


@pytest.mark.parametrize(
    "obs",
    [
        Observation(0, APP, "typed_text", "hello"),
        Observation(0, APP, "command_exit", "rm -rf /home/me/secret"),
        Observation(0, APP, "command_exit", "x" * 65),
        Observation(0, "bad app!", "undo"),
        Observation(0, APP, "alert", "Your password is hunter2"),
    ],
)
def test_free_text_never_enters_the_detector(det, obs):
    with pytest.raises(ContentError):
        det.observe(obs)


def test_the_state_file_is_private_and_holds_no_observations(tmp_path, clock):
    path = tmp_path / "s" / "struggle.json"
    d = Detector(clock, path)
    d.opt_in(APP)
    fail_loop(d, clock)
    d.answer(d.poll(), "no")
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    raw = path.read_text()
    assert "benchctl" not in raw and set(json.loads(raw)) == {
        "opted_in", "never", "nos", "halved", "outcomes", "sensitivity", "enabled",
    }  # fmt: skip


def test_a_corrupt_state_file_is_ignored(tmp_path, clock):
    path = tmp_path / "s.json"
    path.write_text("{not json")
    d = Detector(clock, path)
    assert not d.is_watching(APP)
    path.write_text('{"opted_in": 5}')
    assert not Detector(clock, path).is_watching(APP)


def test_a_short_pause_threshold_still_fires_once_per_pause(det, clock, monkeypatch):
    monkeypatch.setattr("ya_bro.struggle.IDLE_SECONDS", 3.0)
    fail(det, clock)
    fired = [see(det, clock, "idle", value=v) for v in (3, 3.5, 4, 4.5, 5, 7)]
    assert sum(len(f) for f in fired) == 1  # seen on real Mutter idle: it fired every second
    see(det, clock, "idle", value=0)
    assert see(det, clock, "idle", value=3) == [Signal.IDLE_IN_CONTEXT]


def test_the_explanation_reads_naturally_for_every_signal(det, clock):
    from ya_bro.struggle import _why

    text = _why(APP, {s.value: 3 for s in Signal}, struggle_rules())
    assert text.startswith("In workbench I saw ") and text.endswith(".")
    assert "None" not in text and "{" not in text


def struggle_rules():
    from ya_bro.struggle import RULES

    return RULES
