"""The bro is drawn by the Shell extension from its own SVG moods (ADR-0028)."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MOODS = ["idle", "pointing", "thinking", "happy", "teasing", "quiet"]


def test_the_extensions_moods_are_the_designed_artwork_and_nothing_else():
    shipped = ROOT / "extension" / "assets" / "bro"
    designed = ROOT / "docs" / "assets" / "identity" / "states"
    assert sorted(p.stem for p in shipped.glob("*.svg")) == sorted(MOODS)
    for mood in MOODS:
        assert (shipped / f"{mood}.svg").read_bytes() == (designed / f"{mood}.svg").read_bytes()


def test_the_artwork_is_plain_vector_with_no_scripts_images_or_links():
    for path in (ROOT / "extension" / "assets" / "bro").glob("*.svg"):
        text = path.read_text().lower()
        assert path.stat().st_size < 6000, path
        for bad in ("<script", "<image", "href=", "xlink", "data:", "<foreignobject", "@import"):
            assert bad not in text, (path.name, bad)


@pytest.mark.gnome
@pytest.mark.skipif(shutil.which("gnome-shell") is None, reason="gnome-shell not installed")
def test_every_mood_is_drawn_on_a_real_frame():
    r = subprocess.run(
        [
            str(ROOT / "scripts/dev/headless-shell.sh"),
            "/usr/bin/python3",
            str(ROOT / "tests/fixtures/shell_avatar.py"),
        ],
        capture_output=True,
        text=True,
        timeout=180,
        env={**os.environ, "YB_ALLOWED": "[]"},
    )
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith(("PASS", "FAIL"))]
    assert lines, f"no checks ran:\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}"
    assert r.returncode == 0, "\n".join(ln for ln in lines if ln.startswith("FAIL"))
    assert len(lines) >= 17
