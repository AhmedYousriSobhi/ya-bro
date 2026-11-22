"""ADR-0018 §5: platform imports are banned outside ya_bro/platform/** (enforced by ruff TID251)."""

import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RUFF = shutil.which("ruff")


def _lint(path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [RUFF, "check", "--config", str(ROOT / "pyproject.toml"), "--select", "TID251", str(path)],
        capture_output=True,
        text=True,
    )


@pytest.mark.skipif(RUFF is None, reason="ruff not on PATH (run via uv run)")
def test_gi_import_banned_in_core(tmp_path):
    bad = tmp_path / "core_mod.py"
    bad.write_text("import gi\n")
    assert _lint(bad).returncode != 0


@pytest.mark.skipif(RUFF is None, reason="ruff not on PATH (run via uv run)")
def test_repo_core_is_clean():
    r = _lint(ROOT / "src")
    assert r.returncode == 0, r.stdout


def test_ban_is_scoped_to_platform_in_config():
    cfg = (ROOT / "pyproject.toml").read_text()
    assert textwrap.dedent('"src/ya_bro/platform/**" = ["TID251"]') in cfg
