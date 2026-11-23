"""Mutter's real IdleMonitor behind IdleSource, feeding the struggle host (#9)."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.gnome


@pytest.mark.skipif(shutil.which("gnome-shell") is None, reason="gnome-shell not installed")
@pytest.mark.skipif(shutil.which("gdbus") is None, reason="gdbus not installed")
def test_real_idle_time_and_host():
    r = subprocess.run(
        [
            str(ROOT / "scripts/dev/headless-shell.sh"),
            "/usr/bin/python3",
            str(ROOT / "tests/fixtures/shell_idle.py"),
        ],
        capture_output=True,
        text=True,
        timeout=180,
        env={**os.environ, "YB_ALLOWED": "[]"},
    )
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith(("PASS", "FAIL"))]
    assert lines, f"no checks ran:\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}"
    assert r.returncode == 0, "\n".join(ln for ln in lines if ln.startswith("FAIL"))
    assert len(lines) >= 5
