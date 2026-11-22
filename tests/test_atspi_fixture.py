"""Integration: GTK4 fixture app is discoverable through AT-SPI on an isolated session bus."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).parent
SYSTEM_PY = "/usr/bin/python3"
pytestmark = pytest.mark.atspi


def _have_gi() -> bool:
    if not Path(SYSTEM_PY).exists():
        return False
    code = "import gi;gi.require_version('Gtk','4.0');gi.require_version('Atspi','2.0')"
    return subprocess.run([SYSTEM_PY, "-c", code], capture_output=True).returncode == 0


@pytest.mark.skipif(shutil.which("dbus-run-session") is None, reason="dbus-run-session missing")
@pytest.mark.skipif(not _have_gi(), reason="system python3 lacks PyGObject/GTK4/Atspi")
@pytest.mark.skipif(
    not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")),
    reason="no display (use xvfb-run in CI)",
)
def test_fixture_button_visible_via_atspi():
    script = f"""
set -e
/usr/libexec/at-spi-bus-launcher --launch-immediately &
sleep 1
GTK_A11Y=atspi {SYSTEM_PY} {HERE}/fixtures/apps/gtk4_fixture.py &
APP=$!
trap 'kill $APP 2>/dev/null' EXIT
{SYSTEM_PY} {HERE}/fixtures/atspi_probe.py
"""
    r = subprocess.run(
        ["dbus-run-session", "--", "bash", "-c", script],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, f"{r.stdout}\n{r.stderr}"
    assert "Fixture Button" in r.stdout
