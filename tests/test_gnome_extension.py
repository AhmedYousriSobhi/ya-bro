"""Integration: Ya-Bro Shell extension contract, inside an isolated headless gnome-shell."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.gnome


@pytest.mark.skipif(shutil.which("gnome-shell") is None, reason="gnome-shell not installed")
@pytest.mark.skipif(shutil.which("dbus-run-session") is None, reason="dbus-run-session missing")
def test_extension_contract_in_headless_shell():
    r = subprocess.run(
        [
            str(ROOT / "scripts/dev/headless-shell.sh"),
            "/usr/bin/python3",
            str(ROOT / "tests/fixtures/shell_contract.py"),
        ],
        capture_output=True,
        text=True,
        timeout=240,
    )
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith(("PASS", "FAIL"))]
    assert lines, f"no checks ran:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}"
    assert r.returncode == 0, (
        "\n".join(ln for ln in lines if ln.startswith("FAIL")) or r.stderr[-2000:]
    )
