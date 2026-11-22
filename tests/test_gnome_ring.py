"""Ring pixels in an isolated headless shell (interior must stay untinted, #59)."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.gnome


@pytest.mark.skipif(shutil.which("gnome-shell") is None, reason="gnome-shell not installed")
def test_ring_does_not_tint_interior():
    r = subprocess.run(
        [
            str(ROOT / "scripts/dev/headless-shell.sh"),
            "/usr/bin/python3",
            str(ROOT / "tests/fixtures/shell_ring.py"),
        ],
        capture_output=True,
        text=True,
        timeout=240,
    )
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith(("PASS", "FAIL"))]
    assert lines, f"no checks ran:\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}"
    assert r.returncode == 0, "\n".join(ln for ln in lines if ln.startswith("FAIL"))
