"""`broctl ask --pack workbench` on a real frame (#3); needs gnome-shell."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.gnome


@pytest.mark.skipif(shutil.which("gnome-shell") is None, reason="gnome-shell not installed")
def test_terminal_companion_copy_write_and_advance_on_a_real_terminal():
    r = subprocess.run(
        [
            str(ROOT / "scripts/dev/headless-shell.sh"),
            "/usr/bin/python3",
            str(ROOT / "tests/fixtures/shell_terminal_assist.py"),
        ],
        capture_output=True,
        text=True,
        timeout=240,
        env={k: v for k, v in os.environ.items() if k != "YB_ALLOWED"},
    )
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith(("PASS", "FAIL"))]
    assert lines, f"no checks ran:\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}"
    assert r.returncode == 0, "\n".join(ln for ln in lines if ln.startswith("FAIL"))
