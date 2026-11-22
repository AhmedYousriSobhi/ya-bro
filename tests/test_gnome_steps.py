"""Show-me loop end to end in a headless shell: GTK4 fixture, click where the ring points."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.gnome


@pytest.mark.skipif(shutil.which("gnome-shell") is None, reason="gnome-shell not installed")
def test_show_me_loop_end_to_end():
    env = dict(
        os.environ,
        YB_ALLOWED='["io.github.ahmedyousrisobhi.YaBroSteps"]',
    )
    r = subprocess.run(
        [
            str(ROOT / "scripts/dev/headless-shell.sh"),
            "/usr/bin/python3",
            str(ROOT / "tests/fixtures/shell_steps.py"),
        ],
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
    )
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith(("PASS", "FAIL"))]
    assert lines, f"no checks ran:\n{r.stdout[-1500:]}\n{r.stderr[-2500:]}"
    assert r.returncode == 0, (
        "\n".join(ln for ln in lines if ln.startswith("FAIL")) + r.stderr[-800:]
    )
