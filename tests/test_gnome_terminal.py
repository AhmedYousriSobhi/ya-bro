"""A real VTE terminal, a real bash with the hook, read back over AT-SPI (#21)."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.gnome


def _has_vte() -> bool:
    r = subprocess.run(
        ["/usr/bin/python3", "-c", "import gi; gi.require_version('Vte','2.91')"],
        capture_output=True,
    )
    return r.returncode == 0


@pytest.mark.skipif(shutil.which("gnome-shell") is None, reason="gnome-shell not installed")
@pytest.mark.skipif(not _has_vte(), reason="libvte (gir1.2-vte-2.91) not installed")
def test_hook_and_terminal_text_on_real_vte():
    r = subprocess.run(
        [
            str(ROOT / "scripts/dev/headless-shell.sh"),
            "/usr/bin/python3",
            str(ROOT / "tests/fixtures/shell_terminal.py"),
        ],
        capture_output=True,
        text=True,
        timeout=240,
        env={**os.environ, "YB_ALLOWED": '["io.github.ahmedyousrisobhi.YaBroVte"]'},
    )
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith(("PASS", "FAIL"))]
    assert lines, f"no checks ran:\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}"
    assert r.returncode == 0, "\n".join(ln for ln in lines if ln.startswith("FAIL"))
    assert len(lines) >= 8
