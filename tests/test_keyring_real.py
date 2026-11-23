"""The key store against a REAL Secret Service: gnome-keyring-daemon on a private session bus,
private HOME and XDG dirs, inside a bwrap namespace that hides /run/user, so the maintainer's
own keyring and session bus are neither reachable nor touched (#5). Skips, with the reason, when
the tools are missing."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.keyring

NEEDED = ("bwrap", "dbus-run-session", "gnome-keyring-daemon")
SESSION = """
set -u
printf pw | timeout 15 gnome-keyring-daemon --login --components=secrets >/dev/null 2>&1
timeout 15 gnome-keyring-daemon --start --components=secrets >/dev/null 2>&1
exec "$PY" "$FIXTURE"
"""


@pytest.mark.skipif(
    any(shutil.which(t) is None for t in NEEDED) or not Path("/usr/bin/python3").exists(),
    reason=f"needs {', '.join(NEEDED)} and /usr/bin/python3 with PyGObject (Secret typelib)",
)
def test_real_secret_service_in_a_private_session(tmp_path):
    home = tmp_path / "home"
    (home / "run").mkdir(parents=True, mode=0o700)
    env = {  # a fresh environment: no GNOME_KEYRING_CONTROL, no session bus address of the user
        "PATH": "/usr/bin:/bin",
        "HOME": str(home),
        "XDG_DATA_HOME": str(home / "data"),
        "XDG_CONFIG_HOME": str(home / "config"),
        "XDG_STATE_HOME": str(home / "state"),
        "XDG_CACHE_HOME": str(home / "cache"),
        "XDG_RUNTIME_DIR": str(home / "run"),
        "PYTHONPATH": str(ROOT / "src"),
        "PY": sys.executable,
        "FIXTURE": str(ROOT / "tests/fixtures/keyring_real.py"),
    }
    r = subprocess.run(
        [
            "bwrap",
            "--dev-bind",
            "/",
            "/",
            "--tmpfs",
            "/run/user",
            "--unshare-pid",
            "--proc",
            "/proc",
            "--die-with-parent",
            "dbus-run-session",
            "--",
            "bash",
            "-c",
            SESSION,
        ],  # fmt: skip
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
        stdin=subprocess.DEVNULL,
    )
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith(("PASS", "FAIL"))]
    if not lines and ("Operation not permitted" in r.stderr or "bwrap:" in r.stderr):
        pytest.skip(f"bwrap cannot make a namespace here: {r.stderr.strip()[:200]}")
    assert lines, f"no checks ran:\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}"
    fails = [ln for ln in lines if ln.startswith("FAIL")]
    assert r.returncode == 0 and not fails, "\n".join(fails) or r.stderr[-1500:]
    assert len(lines) >= 12
