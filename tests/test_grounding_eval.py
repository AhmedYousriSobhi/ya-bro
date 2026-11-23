import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

from ya_bro import cli, grounding, pointing_eval
from ya_bro.grounding import Tier, normalise, score
from ya_bro.pointing_eval import EvalError, Report, Result, SnapshotPerception

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "evals" / "pointing"


def el(i, role, name, rect=(0, 0, 50, 20)):
    return {"id": i, "role": role, "name": name, "rect": list(rect)}


def point(elements, role, name):
    return asyncio.run(grounding.point(SnapshotPerception("app", elements), "app", role, name))


@pytest.mark.parametrize(
    "a,b",
    [
        ("Save", "  SAVE "),
        ("إرسال", "ارسال"),
        ("حفظ", "حَفْظ"),
        ("الإعدادات", "الاعدادات"),
        ("Save  As", "save as"),
    ],
)
def test_normalised_names_match_exactly(a, b):
    assert normalise(a) == normalise(b) and score(a, b) == 1.0


def test_close_names_never_score_as_exact():
    assert score("Save", "Save As…") < 0.9
    assert score("Export", "Export…") < 1.0
    assert score("", "x") == 0.0


def test_tiers():
    els = [el("a", "button", "Save"), el("b", "button", "Save As…"), el("c", "menu item", "Open")]
    high = point(els, "button", "Save")
    assert (high.tier, high.ref.path) == (Tier.HIGH, "a") and high.rect.w == 50
    assert point(els, "button", "Save As").tier is Tier.MEDIUM  # close, not exact
    assert point(els, "button", "Mirror").tier is Tier.NONE
    assert point(els, "button", "Open").tier is Tier.NONE  # right name, wrong role
    twins = point([el("a", "button", "Go"), el("b", "button", "Go")], "button", "Go")
    assert twins.tier is Tier.MEDIUM and twins.margin == 0  # nothing tells them apart


def test_unusable_rectangles_are_skipped():
    els = [el("a", "button", "Go", (0, 0, 0, 0)), el("b", "button", "Gone")]
    p = point(els, "button", "Go")
    assert p.ref.path == "b" and p.tier is Tier.MEDIUM
    assert point([el("a", "button", "Go", (0, 0, 0, 0))], "button", "Go").tier is Tier.NONE


def result(tier, correct, case="c"):
    return Result(case, "app", "en", "k", tier, "x", "y", correct, 0.1)


def test_scoring_and_gates():
    ok = [result(Tier.HIGH, True)] * 97 + [result(Tier.MEDIUM, False)] * 3
    r = Report(ok)
    assert r.correct_rate == 0.97 and r.confidently_wrong_rate == 0 and r.passes
    assert r.medium_precision == 0 and not r.blocks_release
    bad = Report([result(Tier.HIGH, True)] * 97 + [result(Tier.HIGH, False)] * 3)
    assert bad.confidently_wrong_rate == 0.03 and not bad.passes and not bad.blocks_release
    worse = Report([result(Tier.HIGH, True)] * 90 + [result(Tier.HIGH, False)] * 10)
    assert worse.blocks_release and "RELEASE BLOCKED" in worse.text()
    low = Report([result(Tier.MEDIUM, True)] * 70 + [result(Tier.MEDIUM, False)] * 30)
    assert not low.passes and "FAIL" in low.text()
    assert not Report().passes


def snapshot(tmp_path, cases, name="s.json", elements=None):
    data = {"app": "app", "locale": "en", "elements": elements or [el("a", "button", "Go")]}
    (tmp_path / name).write_text(json.dumps({**data, "cases": cases}))


def test_run_counts_nothing_found_as_right_only_when_truth_is_none(tmp_path):
    snapshot(
        tmp_path,
        [
            {"id": "1", "role": "button", "name": "Go", "truth": "a"},
            {"id": "2", "role": "button", "name": "Mirror", "truth": None},
            {"id": "3", "role": "button", "name": "Mirror", "truth": "a"},
            {"id": "4", "role": "button", "name": "Go", "truth": None},
        ],
    )
    r = pointing_eval.run(tmp_path)
    assert [x.correct for x in r.results] == [True, True, False, False]
    assert r.results[3].confidently_wrong  # a solid ring where nothing should be pointed at


@pytest.mark.parametrize(
    "cases,elements",
    [
        ([{"id": "1", "role": "button", "name": "Go", "truth": "zzz"}], None),
        ([{"id": "1", "name": "Go", "truth": None}], None),
        ([], None),
        (
            [{"id": "1", "role": "button", "name": "x", "truth": None}],
            [el("a", "b", "x"), el("a", "b", "y")],
        ),
    ],
)
def test_bad_snapshots_are_refused(tmp_path, cases, elements):
    snapshot(tmp_path, cases, elements=elements)
    with pytest.raises(EvalError):
        pointing_eval.run(tmp_path)


def test_empty_folder_is_refused(tmp_path):
    with pytest.raises(EvalError, match="no snapshots"):
        pointing_eval.run(tmp_path)


def test_shipped_corpus_is_300_cases_in_both_locales_and_passes():
    r = pointing_eval.run(CORPUS)
    assert r.total == 300
    assert set(r.by("locale")) == {"en", "ar"} and len(r.by("app")) == 6
    assert {"exact", "drift", "duplicate", "missing", "spelling"} <= set(r.by("kind"))
    assert r.passes and not r.blocks_release


def test_corpus_matches_its_generator(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "gen", ROOT / "scripts/dev/make_pointing_corpus.py"
    )
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    monkeypatch.setattr(gen, "OUT", tmp_path)
    gen.main()
    for fresh in tmp_path.glob("*.json"):
        assert fresh.read_text() == (CORPUS / fresh.name).read_text(), fresh.name
    assert len(list(tmp_path.glob("*.json"))) == len(list(CORPUS.glob("synthetic-*.json")))


def test_broctl_eval(tmp_path, capsys):
    assert cli.main(["eval", "pointing"]) == 0
    assert "PASS" in capsys.readouterr().out
    assert cli.main(["eval", "pointing", "--dir", str(tmp_path)]) == 2
    snapshot(tmp_path, [{"id": "1", "role": "button", "name": "Mirror", "truth": "a"}])
    assert cli.main(["eval", "pointing", "--dir", str(tmp_path), "-v"]) == 1
    assert "miss app/en/1" in capsys.readouterr().out
