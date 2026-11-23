"""The AT-SPI struggle source on real GTK apps in the isolated headless shell (#9, ADR-0010 S5b)."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.gnome
ALLOWED = (
    '["io.github.ahmedyousrisobhi.YaBroStruggle", "io.github.ahmedyousrisobhi.YaBroStruggleB",'
    ' "io.github.ahmedyousrisobhi.YaBroStruggleGtk3"]'
)


def run_shell(*args):
    return subprocess.run(
        [
            str(ROOT / "scripts/dev/headless-shell.sh"),
            "/usr/bin/python3",
            str(ROOT / "tests/fixtures/shell_struggle.py"),
            *args,
        ],
        capture_output=True,
        text=True,
        timeout=420,
        env={**os.environ, "YB_ALLOWED": ALLOWED},
    )


def checks(r):
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith(("PASS", "FAIL"))]
    assert lines, f"no checks ran:\n{r.stdout[-2000:]}\n{r.stderr[-2500:]}"
    return lines


@pytest.mark.skipif(shutil.which("gnome-shell") is None, reason="gnome-shell not installed")
def test_real_menus_dialogs_undo_and_alerts_become_observations():
    r = run_shell()
    lines = checks(r)
    assert r.returncode == 0, (
        "\n".join(ln for ln in lines if ln.startswith("FAIL")) + r.stderr[-800:]
    )
    assert len(lines) >= 14


@pytest.mark.skipif(shutil.which("gnome-shell") is None, reason="gnome-shell not installed")
def test_the_same_run_fails_when_the_translator_is_broken():
    """The mutation check: with menu activations unseen and no quick-dialog rule, checks fail."""
    r = run_shell("--mutate")
    failed = [ln for ln in checks(r) if ln.startswith("FAIL")]
    assert r.returncode != 0
    text = "\n".join(failed)
    assert "menu item's first click is menu_activated" in text
    assert "dialog bounce signal" in text
