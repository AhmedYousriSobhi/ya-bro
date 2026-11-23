"""The offer bubble on real frames, real clicks, and a mutation that must fail it (ADR-0010)."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = [
    pytest.mark.gnome,
    pytest.mark.skipif(shutil.which("gnome-shell") is None, reason="gnome-shell not installed"),
]


def run_fixture(script="shell_offer.py", **env):
    r = subprocess.run(
        [
            str(ROOT / "scripts/dev/headless-shell.sh"),
            "/usr/bin/python3",
            str(ROOT / "tests/fixtures" / script),
        ],
        capture_output=True,
        text=True,
        timeout=280,
        env={**os.environ, "YB_ALLOWED": "[]", **env},
    )
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith(("PASS", "FAIL"))]
    assert lines, f"no checks ran:\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}"
    return r.returncode, lines


def test_each_button_is_clicked_on_screen_and_the_detector_answers():
    code, lines = run_fixture()
    assert code == 0, "\n".join(ln for ln in lines if ln.startswith("FAIL"))
    assert len(lines) >= 25


def test_the_real_test_can_fail_yes_and_no_wired_the_wrong_way_round():
    code, lines = run_fixture(YB_MUTATE="swap")
    failed = [ln for ln in lines if ln.startswith("FAIL")]
    assert code != 0 and failed, "a swapped Yes and No went unnoticed"


def test_the_real_watcher_process_stays_quiet_while_a_step_loop_runs_then_offers_and_is_answered():
    code, lines = run_fixture("shell_offer_watch.py")
    assert code == 0, "\n".join(ln for ln in lines if ln.startswith("FAIL"))
    assert len(lines) >= 7
