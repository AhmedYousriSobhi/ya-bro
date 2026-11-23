"""Pointing on real apps' accessibility trees (#19): record, point, click, see the app react.

Needs gnome-shell and the apps; runs in the isolated headless shell (private display and bus).
Calculator: every digit key, pointed at by name and clicked in the middle of the ring, types that
digit, then 7 x 6 = 42. Settings and Files: pointed sidebar rows open their page when clicked.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.gnome
APPS = ("gnome-calculator", "nautilus", "gnome-control-center")


@pytest.mark.skipif(shutil.which("gnome-shell") is None, reason="gnome-shell not installed")
@pytest.mark.skipif(any(shutil.which(a) is None for a in APPS), reason="apps not installed")
def test_pointing_on_real_apps(tmp_path):
    allowed = (
        '["org.gnome.Calculator","org.gnome.TextEditor","org.gnome.Nautilus","org.gnome.Settings"]'
    )
    r = subprocess.run(
        [
            str(ROOT / "scripts/dev/headless-shell.sh"),
            "/usr/bin/python3",
            str(ROOT / "tests/fixtures/shell_pointing.py"),
        ],
        capture_output=True,
        text=True,
        timeout=360,
        env={**os.environ, "YB_ALLOWED": allowed, "YB_SNAP_DIR": str(tmp_path)},
    )
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith(("PASS", "FAIL"))]
    assert lines, f"no checks ran:\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}"
    assert r.returncode == 0, "\n".join(ln for ln in lines if ln.startswith("FAIL"))
    assert sum("pointed" in ln for ln in lines) >= 3  # calculator x2, settings, files
    from ya_bro import pointing_eval

    report = pointing_eval.run(tmp_path)  # what was just recorded scores above the gate too
    assert report.passes, report.text(verbose=True)
