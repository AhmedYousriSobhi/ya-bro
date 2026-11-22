"""S1 measurements in an isolated headless gnome-shell (slow, several minutes; not part of check.sh).

Run: uv run pytest -m gnome_measure -s
Writes raw numbers to docs/research/spikes/S1-measurements-scale-<s>.json.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/research/spikes"
pytestmark = pytest.mark.gnome_measure


def _run(scale: str, monitor: str):
    out = OUT / f"S1-measurements-scale-{scale}.json"
    env = dict(os.environ, YB_X11="1", YB_SCALE=scale, YB_MONITOR=monitor)
    r = subprocess.run(
        [
            str(ROOT / "scripts/dev/headless-shell.sh"),
            "/usr/bin/python3",
            str(ROOT / "tests/fixtures/measure.py"),
            str(out),
            "--scale",
            scale,
        ],
        capture_output=True,
        text=True,
        timeout=900,
        env=env,
    )
    assert out.exists(), f"no result file:\n{r.stdout[-3000:]}\n{r.stderr[-1500:]}"
    return json.loads(out.read_text())


@pytest.mark.skipif(shutil.which("gnome-shell") is None, reason="gnome-shell not installed")
@pytest.mark.parametrize(("scale", "monitor"), [("1", "1280x800"), ("1.5", "1920x1200")])
def test_measurements_run(scale, monitor):
    data = _run(scale, monitor)
    # Go criteria that are objectively checkable here (ADR-0023 validation plan):
    ct = data["click_through"]
    assert ct["blocked"] == 0, ct
    assert ct["focus_events"] == 0 and ct["app_still_focused"], ct
    assert data["signal_unicast"]["non_peer_match_rule_received"] == 0
    # Known open problem (S1 findings): the stop key binding fires in only some headless sessions.
    if data["stop_key"]["received"] != 50:
        pytest.xfail(f"stop key unreliable in headless shell: {data['stop_key']}")
