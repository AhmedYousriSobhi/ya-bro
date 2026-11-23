"""The offer bubble over fakes: each button reaches the detector's back-off (ADR-0010)."""

import asyncio
import contextlib

import pytest

from tests.fakes import FakeOverlay, FakeShellHook
from ya_bro import privacy, struggle_host
from ya_bro.offers import BUTTONS, OfferBubble
from ya_bro.persona import Persona
from ya_bro.struggle import OFFER_COOLDOWN, Detector, Observation

APP = "workbench"


class Clock:
    t = 1_000_000.0

    def __call__(self):
        return self.t


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def det(clock):
    d = Detector(clock)
    d.opt_in(APP)
    return d


def make_offer(det, clock):
    for _ in range(3):
        det.observe(Observation(clock.t, APP, "command_exit", "benchctl", 1))
        clock.t += 1
    offer = det.poll()
    assert offer is not None
    return offer


def bubble(det, overlay, **kw):
    kw.setdefault("fade", 5.0)
    kw.setdefault("say_for", 0)
    return OfferBubble(det, overlay, Persona(humour=1), **kw)


async def answer_with(overlay, det, offer, event, **kw):
    b = bubble(det, overlay, **kw)
    task = asyncio.create_task(b.present(offer))
    await asyncio.sleep(0.01)
    if event:
        overlay.push(event)
    return await task


async def test_the_bubble_shows_the_persona_line_with_exactly_the_three_buttons(det, clock):
    overlay, offer = FakeOverlay(), make_offer(det, clock)
    await answer_with(overlay, det, offer, "no")
    assert overlay.buttons[0] == BUTTONS == ("yes", "no", "not_for_app")
    assert overlay.calls[0][2]  # a real line, not empty
    assert overlay.calls[-1] == ("hide",)


async def test_yes_is_counted_clears_the_score_and_calls_the_hand_over(det, clock):
    overlay, offer, accepted = FakeOverlay(), make_offer(det, clock), []
    r = await answer_with(overlay, det, offer, "yes", on_accept=accepted.append)
    assert r.outcome == "yes" and accepted == [offer]
    assert det.stats()["yes"] == 1 and det.score(APP) == 0.0
    assert overlay.buttons[-1] == ()  # the greeting has no buttons


async def test_no_is_a_soft_decline_that_silences_those_signals(det, clock):
    overlay, offer = FakeOverlay(), make_offer(det, clock)
    r = await answer_with(overlay, det, offer, "no")
    assert r.outcome == "no" and not r.quiet and det.stats()["no"] == 1
    assert det.score(APP) == 0.0  # the failing-commands signal no longer counts
    clock.t += OFFER_COOLDOWN + 1
    assert det.poll() is None  # and more failures right away do not bring it back
    for _ in range(3):
        det.observe(Observation(clock.t, APP, "command_exit", "benchctl", 1))
    assert det.poll() is None


async def test_two_noes_in_a_row_silence_the_app_and_the_bro_says_so(det, clock):
    overlay, offer = FakeOverlay(), make_offer(det, clock)
    await answer_with(overlay, det, offer, "no")
    clock.t += OFFER_COOLDOWN + 1
    det.observe(Observation(clock.t, APP, "context"))
    second = make_offer(det, clock)
    overlay.calls.clear()
    r = await answer_with(overlay, det, second, "no")
    assert r.quiet and det.is_quiet(APP)
    quiet_line = overlay.calls[1][2]
    persona = Persona(humour=1)
    assert quiet_line in {ln.text for ln in persona.data.lines["en"]["back_off_long"]}
    clock.t += OFFER_COOLDOWN + 1
    det.observe(Observation(clock.t, APP, "context"))
    assert det.poll() is None  # silent for 30 minutes
    clock.t += 31 * 60
    for _ in range(3):
        det.observe(Observation(clock.t, APP, "command_exit", "benchctl", 1))
    # (a fresh detector run would offer again; the quiet timer is what held it back above)
    assert not det.is_quiet(APP)


async def test_not_for_this_app_opts_the_app_out(det, clock):
    overlay, offer = FakeOverlay(), make_offer(det, clock)
    r = await answer_with(overlay, det, offer, "not_for_app")
    assert r.outcome == "never" and det.stats()["never"] == 1
    assert not det.is_watching(APP)
    declined = Persona(humour=1).data.lines["en"]["offer_declined"]
    assert overlay.calls[1][2] in {ln.text for ln in declined}


async def test_a_bubble_nobody_answers_fades_and_counts_as_a_soft_decline(det, clock):
    overlay, offer = FakeOverlay(), make_offer(det, clock)
    b = bubble(det, overlay, fade=0.05)
    r = await b.present(offer)
    assert r.outcome == "ignored" and det.stats()["ignored"] == 1
    assert len(overlay.calls) == 2  # shown, then hidden: no extra line for a fade
    assert overlay.calls[-1] == ("hide",)


async def test_the_stop_key_hides_the_bubble_and_counts_as_a_no(det, clock):
    overlay, offer = FakeOverlay(), make_offer(det, clock)
    r = await answer_with(overlay, det, offer, "stop")
    assert r.outcome == "no" and overlay.calls[-1] == ("hide",)


async def test_other_events_do_not_answer_the_offer(det, clock):
    overlay, offer = FakeOverlay(), make_offer(det, clock)
    b = bubble(det, overlay, fade=0.2)
    task = asyncio.create_task(b.present(offer))
    await asyncio.sleep(0.01)
    overlay.push("next")
    overlay.push("do_it")
    assert (await task).outcome == "ignored"


async def test_an_offer_is_withdrawn_unshown_while_a_step_loop_runs(det, clock):
    overlay, offer = FakeOverlay(), make_offer(det, clock)
    b = bubble(det, overlay, busy=lambda: True)
    assert (await b.present(offer)).outcome == "withdrawn"
    assert overlay.calls == [] and sum(det.stats().values()) == 0  # shown nothing, counted nothing
    clock.t += OFFER_COOLDOWN + 1
    for _ in range(3):
        det.observe(Observation(clock.t, APP, "command_exit", "benchctl", 1))
        clock.t += 1
    assert det.poll() is not None  # the pending slot was freed


async def test_only_one_offer_is_pending_until_it_is_answered(det, clock):
    offer = make_offer(det, clock)
    clock.t += OFFER_COOLDOWN + 1
    for _ in range(3):
        det.observe(Observation(clock.t, APP, "command_exit", "benchctl", 1))
        clock.t += 1
    assert det.poll() is None
    det.answer(offer, "no")


# ---- through the host ----------------------------------------------------------------------


def events(*codes):
    return [{"argv0": "benchctl", "exit": c, "ms": 5, "ts": 0, "tty": "pts/1"} for c in codes]


async def run_host(host, seconds=0.4):
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(host.run(), seconds)


async def test_the_host_shows_the_bubble_and_the_answer_reaches_the_detector(det, clock):
    overlay, log, seen = FakeOverlay(), [], []
    b = bubble(det, overlay)

    async def present(offer):
        seen.append(offer)
        overlay.push("not_for_app")
        return await b.present(offer)

    host = struggle_host.StruggleHost(
        det, {"benchctl": APP}, shell=FakeShellHook(events(1, 1, 1)), clock=clock,
        sink=lambda n, **f: log.append((n, f)), present=present,
    )  # fmt: skip
    await run_host(host)
    assert len(seen) == 1 and not det.is_watching(APP)
    assert ("struggle_answer", {"app": APP, "outcome": "never"}) in log


async def test_the_host_takes_no_offer_while_busy_and_offers_when_it_is_over(det, clock):
    overlay, shown = FakeOverlay(), []
    state = {"busy": True}
    b = bubble(det, overlay)

    async def present(offer):
        shown.append(offer)
        return await b.present(offer)

    host = struggle_host.StruggleHost(
        det, {"benchctl": APP}, shell=FakeShellHook(events(1, 1, 1)), clock=clock,
        present=present, busy=lambda: state["busy"],
    )  # fmt: skip
    await run_host(host, 0.2)
    assert shown == [] and det._pending is None  # not even taken: still due
    state["busy"] = False
    await run_host(host, 0.2)
    assert len(shown) == 1


async def test_a_broken_overlay_does_not_stop_the_detector_and_frees_the_slot(det, clock):
    log = []

    async def present(offer):
        raise RuntimeError("overlay gone")

    host = struggle_host.StruggleHost(
        det, {"benchctl": APP}, shell=FakeShellHook(events(1, 1, 1)), clock=clock,
        sink=lambda n, **f: log.append(n), present=present,
    )  # fmt: skip
    await run_host(host)
    assert "struggle_bubble_failed" in log and det._pending is None
    assert det.stats()["ignored"] == 1


def test_panic_finds_the_bubble_watcher():
    assert privacy._is_yabro(["python3", "-m", "ya_bro.platform.gnome_offers", "--seconds", "9"])
