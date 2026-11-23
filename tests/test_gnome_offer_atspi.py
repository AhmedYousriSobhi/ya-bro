"""An error loop in a real GTK3 app becomes a clickable bubble (#9: AT-SPI sources + offer bubble)."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.gnome


@pytest.mark.skipif(shutil.which("gnome-shell") is None, reason="gnome-shell not installed")
def test_two_real_error_dialogs_make_a_bubble_that_answers_a_click():
    r = subprocess.run(
        [
            str(ROOT / "scripts/dev/headless-shell.sh"),
            "/usr/bin/python3",
            str(ROOT / "tests/fixtures/shell_offer_atspi.py"),
        ],
        capture_output=True,
        text=True,
        timeout=300,
        env={**os.environ, "YB_ALLOWED": '["io.github.ahmedyousrisobhi.YaBroStruggleGtk3"]'},
    )
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith(("PASS", "FAIL"))]
    assert lines, f"no checks ran:\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}"
    assert r.returncode == 0, "\n".join(ln for ln in lines if ln.startswith("FAIL"))
    assert len(lines) >= 6
