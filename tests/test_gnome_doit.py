"""Do-it on the real GNOME Calculator through AT-SPI actions (#27); needs gnome-shell."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.gnome


@pytest.mark.skipif(shutil.which("gnome-shell") is None, reason="gnome-shell not installed")
@pytest.mark.skipif(
    shutil.which("gnome-calculator") is None, reason="gnome-calculator not installed"
)
def test_the_bro_presses_seven_times_six_itself():
    r = subprocess.run(
        [
            str(ROOT / "scripts/dev/headless-shell.sh"),
            "/usr/bin/python3",
            str(ROOT / "tests/fixtures/shell_doit.py"),
        ],
        capture_output=True,
        text=True,
        timeout=240,
        env={**os.environ, "YB_ALLOWED": '["org.gnome.Calculator"]'},
    )
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith(("PASS", "FAIL"))]
    assert lines, f"no checks ran:\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}"
    assert r.returncode == 0, "\n".join(ln for ln in lines if ln.startswith("FAIL"))
