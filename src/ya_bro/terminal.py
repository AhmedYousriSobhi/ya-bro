"""Reading a terminal after the user accepted help (ADR-0021 §2, §4), and the hook's rc-file block.

The terminal text comes from the accessibility tree (VTE exposes its buffer as AT-SPI Text), so
this is core code over `Perception`. It is only called after the user asked for help; the text is
redacted before anything else sees it, and it is data, never instructions.
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ya_bro.interfaces import Perception
from ya_bro.packs import Fixit, Pack
from ya_bro.redact import redact

MAX_LINES = 40
MAX_LINE_CHARS = 300
_ERROR = re.compile(r"\b([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+):\s*(.*?)(?:\s*\|\s*fix:\s*(.+))?$")
BEGIN = "# >>> ya-bro hook (remove with: broctl hook uninstall)"
END = "# <<< ya-bro hook"


async def last_output(perception: Perception, app_id: str, lines: int = MAX_LINES) -> str:
    """The last lines of the first terminal widget of the app, redacted and bounded."""
    refs = await perception.find(app_id, "terminal")
    if not refs:
        return ""
    text = await perception.read_text(refs[0])
    shown = [ln.rstrip()[:MAX_LINE_CHARS] for ln in text.splitlines()]
    while shown and not shown[-1]:
        shown.pop()
    return redact("\n".join(shown[-max(1, min(lines, MAX_LINES)) :])).text


@dataclass(frozen=True)
class ErrorLine:
    code: str
    message: str
    fix: str  # the app's own suggestion, to be offered, never run


def find_error(text: str) -> ErrorLine | None:
    """The last `CODE: message | fix: COMMAND` line (workbench's agent format) in terminal text."""
    for line in reversed(text.splitlines()):
        m = _ERROR.search(line.strip())
        if m:
            return ErrorLine(m.group(1), m.group(2).strip(), (m.group(3) or "").strip())
    return None


def explain(packs: list[Pack], argv0: str, text: str) -> tuple[ErrorLine, Fixit] | None:
    """A pack's explanation for the error in this text, from the packs that own this command."""
    err = find_error(text)
    if err is None:
        return None
    for pack in packs:
        if pack.matches(argv0=argv0) and err.code in pack.fixits:
            return err, pack.fixits[err.code]
    return None


EMBEDDED_HINT = "its window title never changes, so Bro cannot tell which window it is"
EMBEDDED_FIX = (
    "open Ptyxis, GNOME Terminal or Console as its own window and run Bro there, "
    "or allow the app with `broctl apps allow <id>`"
)


def terminal_kind(env: dict[str, str]) -> str:
    """`window` for a VTE terminal (Ptyxis, GNOME Terminal, Console sets VTE_VERSION), else what it
    looks like: a terminal inside VS Code, or one Bro cannot identify (an Electron app's panel)."""
    if env.get("TERM_PROGRAM") == "vscode":
        return "this is VS Code's terminal"
    if env.get("VTE_VERSION"):
        return "window"
    return "this terminal is not a VTE window"


def hook_block(script: Path) -> str:
    return f'{BEGIN}\n[ -r "{script}" ] && . "{script}"\n{END}\n'


def install_block(rc: Path, script: Path) -> bool:
    """Add the hook block to an rc file; False when it was already there."""
    text = rc.read_text() if rc.exists() else ""
    if BEGIN in text:
        return False
    sep = "" if not text or text.endswith("\n") else "\n"
    _write(rc, text + sep + hook_block(script))
    return True


def remove_block(rc: Path) -> bool:
    if not rc.exists():
        return False
    text = rc.read_text()
    start = text.find(BEGIN)
    end = text.find(END)
    if start < 0 or end < start:
        return False
    end = text.find("\n", end)
    end = len(text) if end < 0 else end + 1
    _write(rc, text[:start] + text[end:])
    return True


def _write(path: Path, text: str) -> None:
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".ya-bro-")
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.chmod(tmp, mode)
    os.replace(tmp, path)
