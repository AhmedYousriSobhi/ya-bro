import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from ya_bro import cli, struggle_eval
from ya_bro.struggle_eval import EvalError, Offered, Replay, Report, replay

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "evals" / "struggle"


def scenario(events, label="struggle", duration=200, onset=0, **kw):
    return {"id": "s", "kind": "k", "label": label, "app": "workbench", "duration": duration,
            "onset": onset, "events": events, **kw}  # fmt: skip


def fails(*times, name="benchctl"):
    return [{"t": t, "kind": "command_exit", "key": name, "value": 1} for t in times]


# ---- the replay mechanics ----------------------------------------------------------------------


def test_three_failures_make_an_offer_at_the_third():
    r = replay(scenario(fails(10, 20, 30)))
    assert [o.t for o in r.offers] == [30.0] and r.time_to_offer == 30.0
    assert r.offers[0].why == "In workbench I saw 3 failed commands of the same name."


def test_two_failures_make_none():
    assert replay(scenario(fails(10, 20))).offers == []


def test_an_unanswered_offer_fades_after_eight_seconds_and_counts_as_ignored():
    # The same loop again at once is silenced because the ignored offer was a soft "no".
    r = replay(scenario(fails(10, 20, 30, 60, 70, 80)))
    assert len(r.offers) == 1
    # Answered "yes" before it fades: a loop after the cooldown is offered again.
    again = fails(10, 20, 30) + [{"t": 32, "kind": "answer", "key": "yes"}] + fails(200, 210, 220)
    assert len(replay(scenario(again, duration=300)).offers) == 2


def test_answers_with_nothing_pending_are_harmless():
    r = replay(scenario([{"t": 5, "kind": "answer", "key": "no"}, *fails(10, 20, 30)]))
    assert len(r.offers) == 1


def test_idle_span_is_read_second_by_second_like_the_host():
    events = [*fails(5), {"t": 10, "kind": "idle_span", "value": 40}]
    r = replay(scenario(events, duration=100), sensitivity=4)
    assert len(r.offers) == 1 and "pause" in r.offers[0].why
    assert 30 <= r.offers[0].t <= 31  # the 20 s pause is seen 20 s after it began


def test_sensitivity_moves_the_threshold():
    events = [{"t": 5, "kind": "help_opened"}, {"t": 6, "kind": "idle_span", "value": 8}]
    assert replay(scenario(events, duration=60), 2).offers == []
    assert len(replay(scenario(events, duration=60), 4).offers) == 1


def test_offers_before_the_onset_are_not_good():
    r = replay(scenario(fails(10, 20, 30), onset=100))
    assert len(r.offers) == 1 and r.good == [] and r.bad == r.offers
    assert replay(scenario(fails(10, 20, 30), label="not_struggle")).good == []


# ---- the metrics -------------------------------------------------------------------------------


def rep(label="struggle", offers=(), onset=0.0, duration=100.0, expect=None, kind="k"):
    return Replay("x", kind, "scripted", label, onset, duration, expect,
                  [Offered(t, "a", 2.0, "w") for t in offers])  # fmt: skip


def test_precision_recall_time_and_hourly_rate():
    report = Report([
        rep(offers=[30]), rep(offers=[50], onset=10), rep(), rep(offers=[5], onset=10),
        rep("not_struggle", offers=[7], duration=1800), rep("not_struggle", duration=1800),
    ])  # fmt: skip
    # offers: 30 good, 50 good, 5 early (bad), 7 in calm (bad) -> 2 of 4 good
    assert report.offers == 4 and report.precision == 0.5
    assert report.recall == 0.5  # 2 of 4 struggle scenarios got a good offer
    assert report.median_time_to_offer == 35.0  # 30 and 40 seconds after onset
    # calm time: 3600 s of calm + 20 s of pre-onset; two bad offers in it
    assert report.false_offers_per_hour == pytest.approx(2 / (3620 / 3600))


@pytest.mark.parametrize(
    "report",
    [
        Report(
            [rep(offers=[30]), rep("not_struggle", offers=[5]), rep("not_struggle", offers=[6])]
        ),
        Report([rep(offers=[30]), rep(), rep(), rep()]),
        Report([rep(offers=[80])]),
        Report([rep(offers=[30]), rep("not_struggle", offers=[1], duration=100)]),
        Report([rep(offers=[30], expect=2)]),
        Report([]),
    ],
    ids=["precision", "recall", "slow", "false-rate", "backoff", "empty"],
)
def test_each_gate_can_fail_alone(report):
    assert not report.passes


def test_a_good_report_passes_and_reads_well():
    report = Report([rep(offers=[30], expect=1), rep("not_struggle", duration=3600)])
    assert report.passes and "PASS" in report.text()
    assert "missed x" in Report([rep()]).text(verbose=True)
    assert "false offer x" in Report([rep("not_struggle", offers=[3])]).text(verbose=True)


# ---- the shipped scenarios ---------------------------------------------------------------------


def test_the_shipped_set_is_labelled_mixed_and_passes_the_gates():
    r = struggle_eval.run(CORPUS)
    assert len(r.replays) >= 40
    assert sum(x.struggle for x in r.replays) >= 15 and sum(not x.struggle for x in r.replays) >= 15
    assert {x.source for x in r.replays} == {"scripted", "recorded"}
    assert len(r.by_kind()) >= 8
    assert r.passes, r.text(verbose=True)


def test_every_scripted_signal_has_a_case_and_the_back_off_rules_are_all_exercised():
    r = struggle_eval.run(CORPUS)
    kinds = set(r.by_kind())
    signals = {"failing_commands", "app_error_code", "error_loop", "dialog_bounce", "menu_thrash"}
    signals |= {"focus_pingpong", "undo_loop", "idle_in_context", "help_seeking", "backoff"}
    assert signals <= kinds
    assert r.backoff == (7, 7)


def test_more_sensitivity_never_means_fewer_offers_or_less_recall():
    runs = [struggle_eval.run(CORPUS, s) for s in (1, 2, 3, 4)]
    assert [x.offers for x in runs] == sorted(x.offers for x in runs)
    assert [x.recall for x in runs] == sorted(x.recall for x in runs)
    assert runs[0].recall < runs[1].recall  # the quiet end really is quieter


def test_scripted_scenarios_match_their_generator(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "gen", ROOT / "scripts/dev/make_struggle_corpus.py"
    )
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    monkeypatch.setattr(gen, "OUT", tmp_path)
    gen.main()
    fresh = sorted(tmp_path.glob("scripted-*.json"))
    assert len(fresh) == len(list(CORPUS.glob("scripted-*.json"))) >= 40
    for f in fresh:
        assert f.read_text() == (CORPUS / f.name).read_text(), f.name


def test_scenarios_hold_no_text_only_kinds_tokens_and_numbers():
    for f in CORPUS.glob("*.json"):
        for e in json.loads(f.read_text())["events"]:
            assert set(e) <= {"t", "kind", "key", "value"}, f.name
            assert len(e.get("key", "")) <= 64 and not any(c.isspace() for c in e.get("key", ""))


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")
def test_scenarios_recorded_from_a_real_bash_replay_as_labelled(tmp_path):
    from tests import record_struggle

    recorded = record_struggle.record(tmp_path)
    assert len(recorded) == len(record_struggle.SCRIPTS)
    report = struggle_eval.run(tmp_path)
    for r in report.replays:
        right = bool(r.good) if r.struggle else not r.offers
        assert right, f"{r.id}: {r.label}, offers {r.offers}"
    assert all(d["source"] == "recorded" and d["events"] for d in recorded)


# ---- bad input and the command -----------------------------------------------------------------


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.pop("label"),
        lambda d: d.update(label="maybe"),
        lambda d: d.pop("onset"),
        lambda d: d["events"].append({"t": 1, "kind": "typed_text"}),
        lambda d: d["events"].append({"kind": "undo"}),
    ],
)
def test_bad_scenarios_are_refused(tmp_path, mutate):
    d = scenario(fails(1, 2, 3))
    mutate(d)
    (tmp_path / "bad.json").write_text(json.dumps(d))
    with pytest.raises(EvalError):
        struggle_eval.run(tmp_path)


def test_empty_or_unreadable_folders_are_refused(tmp_path):
    with pytest.raises(EvalError, match="no scenarios"):
        struggle_eval.run(tmp_path)
    (tmp_path / "x.json").write_text("{nope")
    with pytest.raises(EvalError, match="cannot read"):
        struggle_eval.run(tmp_path)


def test_broctl_eval_struggle(tmp_path, capsys):
    assert cli.main(["eval", "struggle"]) == 0
    assert "PASS" in capsys.readouterr().out
    assert cli.main(["eval", "struggle", "--sweep"]) == 0
    sweep = capsys.readouterr().out.strip().splitlines()
    assert [ln.split(":")[0] for ln in sweep] == [f"sensitivity {i}" for i in (1, 2, 3, 4)]
    assert cli.main(["eval", "struggle", "--dir", str(tmp_path)]) == 2
    (tmp_path / "s.json").write_text(json.dumps(scenario(fails(1))))
    assert cli.main(["eval", "struggle", "--dir", str(tmp_path), "-v"]) == 1
    assert "missed s" in capsys.readouterr().out


# ---- the eval has teeth: break the detector and it must notice ---------------------------------


@pytest.mark.parametrize(
    "attr,value,what",
    [
        ("OFFER_COOLDOWN", 0.0, "back-off"),  # no cooldown
        ("MAX_PER_HOUR", 99, "back-off"),  # no hourly cap
        ("QUIET_AFTER_TWO_NOS", 0.0, "back-off"),  # the 30 quiet minutes are gone
    ],
)
def test_breaking_the_back_off_fails_the_eval(monkeypatch, attr, value, what):
    assert struggle_eval.run(CORPUS).passes
    monkeypatch.setattr(f"ya_bro.struggle.{attr}", value)
    broken = struggle_eval.run(CORPUS)
    assert broken.backoff[0] < broken.backoff[1] and not broken.passes


def test_a_detector_that_is_too_jumpy_or_too_deaf_fails_the_eval(monkeypatch):
    from dataclasses import replace

    from ya_bro import struggle
    from ya_bro.struggle import Signal

    # Jumpy: one failed command is already "a loop", and a heavy one.
    jumpy_rule = replace(struggle.RULES[Signal.FAILING_COMMANDS], count=1, weight=3.0)
    monkeypatch.setitem(struggle.RULES, Signal.FAILING_COMMANDS, jumpy_rule)
    jumpy = struggle_eval.run(CORPUS)
    assert not jumpy.passes and (jumpy.precision < 0.6 or jumpy.false_offers_per_hour > 1), (
        jumpy.text()
    )
    monkeypatch.undo()
    monkeypatch.setitem(struggle.SENSITIVITY_THETA, 2, 50.0)  # deaf: never offers
    deaf = struggle_eval.run(CORPUS)
    assert deaf.recall == 0 and not deaf.passes
