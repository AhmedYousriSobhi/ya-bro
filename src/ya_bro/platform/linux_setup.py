"""Linux/GNOME probes for `ya-bro doctor` and consent-gated `ya-bro setup` (ADR-0005, ADR-0023 §9).

Everything shells out through an injectable `Runner`, so tests never touch the real session
bus, gsettings or the filesystem outside a temp dir (CLAUDE.md harness rules).
"""

from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ya_bro import dirs

EXT_UUID = "ya-bro@ahmedyousrisobhi.github.io"
SCHEMA_IFACE = "org.gnome.desktop.interface"
SCHEMA_SHELL = "org.gnome.shell"
SCHEMA_EXT = "org.gnome.shell.extensions.ya-bro"
APP_ID = re.compile(r"[A-Za-z0-9_.+-]{1,128}")

Runner = Callable[[list[str]], tuple[int, str]]


def run(cmd: list[str]) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""
    return p.returncode, p.stdout.strip()


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    status: str  # ok | warn | fail | info
    detail: str
    fix: str = ""


def session_type(env: dict[str, str]) -> Check:
    kind = env.get("XDG_SESSION_TYPE", "")
    desktop = env.get("XDG_CURRENT_DESKTOP", "unknown")
    if kind == "wayland" and "GNOME" in desktop:
        return Check("session", "ok", f"{desktop} on Wayland")
    if kind == "wayland":
        return Check("session", "warn", f"{desktop} on Wayland (KWin is v0.2)", "docked mode only")
    return Check("session", "fail", f"{kind or 'unknown'} session; GNOME Wayland is required")


def a11y_bus(runner: Runner) -> list[Check]:
    rc, out = runner(["gsettings", "get", SCHEMA_IFACE, "toolkit-accessibility"])
    toolkit = out == "true"
    checks = [
        Check(
            "toolkit-accessibility",
            "ok" if toolkit else "warn",
            out or ("gsettings unavailable" if rc else "unknown"),
            "" if toolkit else "run `ya-bro setup` (asks first)",
        )
    ]
    rc, out = runner(
        ["gdbus", "call", "--session", "--dest", "org.a11y.Bus", "--object-path", "/org/a11y/bus"]
        + ["--method", "org.freedesktop.DBus.Properties.Get", "org.a11y.Status", "IsEnabled"]
    )
    enabled = rc == 0 and "true" in out
    checks.append(
        Check(
            "a11y bus",
            "ok" if enabled else "warn",
            "IsEnabled=true" if enabled else "not enabled or unreachable",
            "" if enabled else "enable toolkit-accessibility, then log out and in",
        )
    )
    return checks


def extension_state(runner: Runner) -> Check:
    rc, out = runner(
        ["gdbus", "call", "--session", "--dest", "org.gnome.Shell.Extensions"]
        + ["--object-path", "/org/gnome/Shell/Extensions"]
        + ["--method", "org.gnome.Shell.Extensions.GetExtensionInfo", EXT_UUID]
    )
    if rc != 0 or "'state'" not in out:
        return Check(
            "extension", "warn", "not known to the shell", "run `ya-bro setup`, then re-login"
        )
    states = {1: "ENABLED", 2: "DISABLED", 3: "ERROR", 4: "OUT_OF_DATE", 5: "DOWNLOADING"}
    m = re.search(r"'state': <(?:double )?(\d+)(?:\.0)?>", out)
    if not m:
        return Check("extension", "warn", "state unreadable")
    state = int(m.group(1))
    name = states.get(state, str(state))
    return Check("extension", "ok" if state == 1 else "warn", name)


def api_key(env: dict[str, str]) -> Check:
    present = bool(env.get("ANTHROPIC_API_KEY"))  # never print the value
    return Check("api key", "ok" if present else "warn", "present" if present else "missing")


def run_all(env: dict[str, str] | None = None, runner: Runner | None = None) -> list[Check]:
    runner = runner or run
    env = dict(os.environ) if env is None else env
    return [
        session_type(env),
        *a11y_bus(runner),
        extension_state(runner),
        allowed_apps_check(runner),
        api_key(env),
    ]


# --- setup -------------------------------------------------------------------------------


def extension_source() -> Path | None:
    for base in (Path(__file__).resolve().parents[3], Path(__file__).resolve().parents[2]):
        if (base / "extension" / "metadata.json").is_file():
            return base / "extension"
    return None


def extension_target() -> Path:
    return dirs.data_dir().parent / "gnome-shell" / "extensions" / EXT_UUID


def enable_a11y(runner: Runner) -> str:
    rc, _ = runner(["gsettings", "set", SCHEMA_IFACE, "toolkit-accessibility", "true"])
    return "toolkit-accessibility enabled" if rc == 0 else "failed to set toolkit-accessibility"


def install_extension(
    runner: Runner, source: Path | None = None, target: Path | None = None
) -> str:
    source = source or extension_source()
    target = target or extension_target()
    if source is None:
        return "extension sources not found (not a source checkout)"
    shutil.copytree(source, target, dirs_exist_ok=True)
    if (target / "schemas").is_dir():
        runner(["glib-compile-schemas", str(target / "schemas")])
    rc, out = runner(["gsettings", "get", SCHEMA_SHELL, "enabled-extensions"])
    if rc != 0:
        return f"copied to {target}; could not read enabled-extensions"
    try:
        current = ast.literal_eval(out.removeprefix("@as ")) if out else []
    except (ValueError, SyntaxError):
        return f"copied to {target}; enabled-extensions unreadable, enable it by hand"
    if EXT_UUID not in current:
        runner(["gsettings", "set", SCHEMA_SHELL, "enabled-extensions", str([*current, EXT_UUID])])
    return f"installed to {target} and enabled; log out and in once to load it"


# --- per-app scoping (#43): the user names the one app Ya-Bro may see ---------------------


def valid_app_id(app_id: str) -> bool:
    return bool(APP_ID.fullmatch(app_id)) and not app_id.startswith(".")


def _ext_gsettings(target: Path) -> list[str]:
    return ["gsettings", "--schemadir", str(target / "schemas")]


def allow_app(
    runner: Runner, app_id: str, target: Path | None = None, config_dir: Path | None = None
) -> str:
    """Allowlist exactly this app in the extension and mark it allowed in its app config."""
    if not valid_app_id(app_id):
        return f"invalid app id {app_id!r}; nothing allowed"
    target = target or extension_target()
    rc, _ = runner([*_ext_gsettings(target), "set", SCHEMA_EXT, "allowed-apps", str([app_id])])
    if rc != 0:
        return "could not write the extension allowlist (install the extension first)"
    root = (config_dir or dirs.config_dir()) / "apps"
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{app_id}.toml").write_text("[capture]\nallowed = true\n")
    return f"Ya-Bro may now see only: {app_id}"


def allowed_apps_check(runner: Runner, target: Path | None = None) -> Check:
    target = target or extension_target()
    rc, out = runner([*_ext_gsettings(target), "get", SCHEMA_EXT, "allowed-apps"])
    if rc != 0:
        return Check("allowed apps", "warn", "extension schema not installed", "run `ya-bro setup`")
    try:
        apps = ast.literal_eval(out.removeprefix("@as ")) if out else []
    except (ValueError, SyntaxError):
        return Check("allowed apps", "warn", "unreadable")
    if not apps:
        return Check(
            "allowed apps", "warn", "none: Ya-Bro sees no app", "run `ya-bro setup` and name one"
        )
    return Check("allowed apps", "ok", ", ".join(apps))
