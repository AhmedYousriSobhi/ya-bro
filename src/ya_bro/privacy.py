"""Consent record, the "what was sent" ledger, `forget` and `panic` (ADR-0014 §2, §3, §6, §7).

Everything here is content-free: the ledger holds a category, a size and a destination, never the
text itself, and `forget` and `panic` only delete or stop.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import tempfile
import time
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ya_bro import dirs, keystore, logs, struggle, terminal

CONSENT_VERSION = 1
KINDS = ("question", "elements", "screenshot", "terminal", "pack")  # what a request may carry
LOG_DAYS = 7  # ADR-0014 §7


# --- consent -----------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Consent:
    version: int = 0
    send_to_llm: bool = False  # question + redacted element list to the configured model
    screenshots: bool = False  # cropped screenshots, only when the element list is not enough

    @property
    def given(self) -> bool:
        return self.version >= CONSENT_VERSION


def _consent_path(config_dir: Path | None) -> Path:
    return (config_dir or dirs.config_dir()) / "consent.toml"


def load_consent(config_dir: Path | None = None) -> Consent:
    """Nothing is consented to until the user has answered; a damaged file counts as no."""
    try:
        data = tomllib.loads(_consent_path(config_dir).read_text()).get("consent", {})
        return Consent(
            int(data.get("version", 0)),
            data.get("send_to_llm") is True,
            data.get("screenshots") is True,
        )
    except (OSError, tomllib.TOMLDecodeError, ValueError):
        return Consent()


def save_consent(consent: Consent, config_dir: Path | None = None) -> Path:
    path = _consent_path(config_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic(
        path,
        "[consent]\n"
        f"version = {CONSENT_VERSION}\n"
        f"send_to_llm = {str(consent.send_to_llm).lower()}\n"
        f"screenshots = {str(consent.screenshots).lower()}\n",
    )
    return path


def may_send(kind: str, config_dir: Path | None = None) -> bool:
    """The gate every outgoing request passes (the Brain checks it before building one)."""
    c = load_consent(config_dir)
    if not c.given or not c.send_to_llm:
        return False
    return c.screenshots if kind == "screenshot" else True


def ask_consent(ask: Callable[[str], str], say: Callable[[str], None]) -> Consent:
    """The first-run screen (ADR-0014 §3). Every default is no; Enter keeps it."""
    say("What Bro reads and what it sends")
    say("  Reads, only from the app you named: its on-screen controls (names and positions).")
    say("  Never reads: password fields, or anything from an app you did not name.")
    say("  Keeps on your machine: logs of event types and counts. Never typed text or content.")
    say("  Sends nowhere today. When plain-words requests arrive, a request would carry:")
    say("    your question, the controls of the focused window, and the last few terminal lines")
    say("    when you ask about a command. All of it is scrubbed of keys and tokens first.")
    say("    `broctl sent` lists every request (kind and size); `broctl panic` stops it.")
    send = ask("Allow sending that to Claude when you ask in plain words? [y/N] ").strip().lower()
    shots = "n"
    if send in ("y", "yes"):
        shots = ask("Also allow a cropped screenshot when controls are not enough? [y/N] ")
    return Consent(
        CONSENT_VERSION,
        send in ("y", "yes"),
        send in ("y", "yes") and shots.strip().lower() in ("y", "yes"),
    )


def describe_consent(c: Consent) -> str:
    if not c.given:
        return "no answer yet (run `broctl setup`): nothing is sent"
    send = "on" if c.send_to_llm else "off"
    return f"sending to the model: {send}; screenshots: {'on' if c.screenshots else 'off'}"


# --- what was sent -----------------------------------------------------------------------------


def sent_path() -> Path:
    return dirs.state_dir() / "sent.jsonl"


def record_sent(
    kind: str,
    size: int,
    dest: str,
    ids: logs.Ids | None = None,
    path: Path | None = None,
) -> dict:
    """Append one request to the ledger. Short tokens only, no free text."""
    if kind not in KINDS:
        raise logs.ContentError(f"unknown kind {kind!r}")
    log = logs.JsonlLog(ids or logs.Ids("sent"), path or sent_path())
    try:
        return log.write("sent", kind=kind, bytes=int(size), dest=dest)
    finally:
        log.close()


def read_sent(path: Path | None = None) -> list[dict]:
    try:
        lines = (path or sent_path()).read_text().splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue  # a half-written last line
    return out


def format_sent(records: list[dict]) -> str:
    if not records:
        return "nothing has been sent: no request has left this machine"
    lines = []
    for r in records:
        when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r.get("ts", 0)))
        lines.append(
            f"{when}  {r.get('kind', '?'):10} {r.get('bytes', 0):>7} bytes  to {r.get('dest', '?')}"
        )
    total = sum(int(r.get("bytes", 0)) for r in records)
    return "\n".join([*lines, f"{len(records)} requests, {total} bytes"])


# --- forget ------------------------------------------------------------------------------------


def forget_plan(
    everything: bool = False,
    rc: Path | None = None,
    store: Callable[[], keystore.Backend] | None = None,
) -> list[tuple[str, Callable[[], bool]]]:
    """What `forget` would remove, as (description, action). Settings go only with `everything`."""
    plan: list[tuple[str, Callable[[], bool]]] = [
        (f"logs, offers and the sent list in {dirs.state_dir()}", lambda: _rm(dirs.state_dir())),
        (f"cache in {dirs.cache_dir()}", lambda: _rm(dirs.cache_dir())),
    ]
    try:
        plan.append((f"the shell spool in {dirs.runtime_dir()}", lambda: _rm(dirs.runtime_dir())))
    except RuntimeError:
        pass  # no runtime dir means no spool
    if everything:
        rcfile = rc or Path.home() / ".bashrc"
        plan += [
            ("your answer to the consent screen", lambda: _rm(_consent_path(None))),
            ("allowed targets", lambda: _rm(dirs.config_dir() / "targets")),
            ("allowed-app records", lambda: _rm(dirs.config_dir() / "apps")),
            ("the shell hook lines in ~/.bashrc", lambda: terminal.remove_block(rcfile)),
            (
                "the API key stored in your keyring (a key in .env or the environment stays)",
                lambda: _clear_key(store or keystore.default_store),
            ),
        ]
    return plan


def _clear_key(store: Callable[[], keystore.Backend]) -> bool:
    try:
        return store().clear()
    except keystore.KeyStoreError:
        return False  # no keyring here, so nothing of ours is in one


def _rm(path: Path) -> bool:
    if not path.exists():
        return False
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return True


def prune_logs(now: float | None = None, days: int = LOG_DAYS) -> int:
    """Delete logs older than the retention cap; returns how many went."""
    cutoff = (now or time.time()) - days * 86400
    gone = 0
    for f in (dirs.state_dir() / "logs").glob("*.jsonl"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                gone += 1
        except OSError:
            continue
    return gone


# --- panic -------------------------------------------------------------------------------------

# `broctl` commands that keep running (noun -> the verb that does, or None for any); the rest
# return at once, and a panic must not touch a `broctl struggle status` someone else is running.
_LONG = {"show": None, "point": None, "scope": "watch", "struggle": "watch", "shell": "watch"}


def _is_yabro(argv: list[str]) -> bool:
    names = [os.path.basename(a) for a in argv]
    cores = {"ya_bro.platform.gnome_show", "ya_bro.platform.gnome_offers"}
    if cores & set(argv) or "gnome_demo.py" in names[:3]:
        return True
    # `broctl`, `python broctl`, `uv run broctl`: the name sits near the front, so an editor that
    # has a file called broctl open is left alone.
    if "broctl" in names[:4]:
        rest = argv[names.index("broctl") + 1 :]
        words = [a for a in rest if not a.startswith("-")]
        return bool(words) and words[0] in _LONG and _LONG[words[0]] in (None, *words[1:2])
    return False


def _ancestors(pid: int) -> set[int]:
    out: set[int] = set()
    while pid > 1:
        out.add(pid)
        try:
            fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
            pid = int(fields[1])
        except (OSError, IndexError, ValueError):
            break
    return out


def find_processes(proc: Path = Path("/proc")) -> list[int]:
    """Bro's own long-running processes. Never this one nor the shell that launched it."""
    skip = _ancestors(os.getpid())
    found = []
    for entry in proc.iterdir():
        if not entry.name.isdigit() or int(entry.name) in skip:
            continue
        try:
            argv = (entry / "cmdline").read_bytes().decode(errors="replace").split("\0")
        except OSError:
            continue
        if _is_yabro([a for a in argv if a]):
            found.append(int(entry.name))
    return found


def panic(
    proc: Path = Path("/proc"), kill: Callable[[int, int], None] = os.kill
) -> tuple[list[int], list[str]]:
    """Stop everything now. SIGKILL, so a wedged or stopped core cannot refuse; then undo state.

    The extension hides the overlay on its own once the core's bus name disappears (dead-man,
    ADR-0023), so killing the core is also what clears the screen.
    """
    killed = []
    for pid in find_processes(proc):
        try:
            kill(pid, signal.SIGKILL)
            killed.append(pid)
        except ProcessLookupError:
            continue
        except PermissionError:
            continue
    notes = []
    try:
        if _rm(dirs.runtime_dir()):
            notes.append("removed the shell spool (the hook goes silent)")
    except RuntimeError:
        pass
    try:
        det = struggle.Detector(time.time, struggle.default_state_path())
        if det.enabled_globally:
            det.set_enabled(False)
            notes.append("turned proactive mode off")
    except Exception:  # noqa: BLE001 - a damaged state file must not stop a panic
        notes.append("could not read the struggle state (left as it was)")
    return killed, notes


def _atomic(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".consent-")
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
