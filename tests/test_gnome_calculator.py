"""A wrong key on the real GNOME Calculator is noticed (#74); needs gnome-shell and calculator."""

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
def test_wrong_key_is_noticed_on_calculator():
    env = {"YB_ALLOWED": '["org.gnome.Calculator"]'}
    r = subprocess.run(
        [
            str(ROOT / "scripts/dev/headless-shell.sh"),
            "/usr/bin/python3",
            str(ROOT / "tests/fixtures/shell_calc.py"),
        ],
        capture_output=True,
        text=True,
        timeout=240,
        env={**os.environ, **env},
    )
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith(("PASS", "FAIL"))]
    assert lines, f"no checks ran:\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}"
    assert r.returncode == 0, "\n".join(ln for ln in lines if ln.startswith("FAIL"))
