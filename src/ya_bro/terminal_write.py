"""Write it for me in a terminal (ADR-0029): put a command at the bash prompt, never run it.

How: core leaves the command in a private file and writes the terminal status query (ESC [ 5 n) to
the terminal's tty. The terminal answers (ESC [ 0 n) on the shell's input, the hook's key binding
fires, and the hook puts the file's line at the prompt when the line is empty. Nothing is typed as
key presses and the extension is not involved; the user's own Enter is the confirmation.

Every write passes these checks first, and any failure writes nothing to the tty:
the command is one printable line and not R3; the hook has marked exactly one terminal idle
(prompt showing, shell process alive, still attached to that tty); the tty is a character device
under /dev/pts owned by the user.
"""

from __future__ import annotations

import os
import re
import stat
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ya_bro import dirs, policy, shell_command
from ya_bro.types import Risk

_MARK = re.compile(r"prompt\.(pts_\d{1,6})$")
QUERY = b"\x1b[5n"  # the terminal answers ESC [ 0 n


@dataclass(frozen=True, slots=True)
class WriteResult:
    ok: bool
    reason: str = ""  # a short sentence for the bubble when not ok


def _real_open(path: str) -> int:
    if "PYTEST_CURRENT_TEST" in os.environ:
        raise RuntimeError("tests must pass their own tty opener; a real terminal is never written")
    return os.open(path, os.O_WRONLY | os.O_NOCTTY | os.O_NONBLOCK)


class TerminalWriter:
    def __init__(
        self,
        root: Path | None = None,
        opener: Callable[[str], int] = _real_open,
        wait: float = 2.0,
    ) -> None:
        self._root = root or dirs.runtime_dir()
        self._open = opener
        self._wait = wait

    def idle_terminals(self) -> list[str]:
        """ttys (like `pts_3`) whose hook says the prompt shows, shell alive and still attached."""
        out = []
        for mark in sorted(self._root.glob("prompt.pts_*")):
            m = _MARK.search(mark.name)
            try:
                state, pid = mark.read_text().split()
                pid_n = int(pid)
                tty = "/dev/pts/" + m.group(1).split("_")[1] if m else ""
                alive = os.readlink(f"/proc/{pid_n}/fd/0") == tty
            except (OSError, ValueError):
                continue
            if m and state == "idle" and alive:
                out.append(m.group(1))
        return out

    def can_write(self, command: str) -> WriteResult:
        if not shell_command.valid(command):
            return WriteResult(False, "that is not a command I can write")
        if policy.command_risk(command) is Risk.R3:
            return WriteResult(False, "this one is yours to type")
        found = self.idle_terminals()
        if not found:
            return WriteResult(False, "I don't see an idle prompt with my hook; use Copy")
        if len(found) > 1:
            return WriteResult(False, "I see more than one terminal; use Copy")
        return WriteResult(True)

    def _device(self) -> tuple[str, str] | WriteResult:
        """(tty name, device path) of the one idle terminal, checked, or why not."""
        found = self.idle_terminals()
        if len(found) != 1:
            return WriteResult(False, "no single idle terminal")
        tty = found[0]
        dev = "/dev/pts/" + tty.split("_")[1]
        try:
            st = os.stat(dev)
        except OSError:
            return WriteResult(False, "that terminal is gone")
        if not stat.S_ISCHR(st.st_mode) or st.st_uid != os.getuid():
            return WriteResult(False, "that terminal is not yours")
        return tty, dev

    def announce(self) -> bool:
        """Nudge the one idle terminal so its hook sets the scope token in the title now, not at the
        next prompt. Same query and guards as write, with no suggestion; the line is left alone."""
        target = self._device()
        if isinstance(target, WriteResult):
            return False
        tty, dev = target
        suggest = self._root / f"suggest.{tty}"
        suggest.unlink(missing_ok=True)  # nothing stale may be inserted by this nudge
        try:
            tfd = self._open(dev)
            try:
                os.write(tfd, QUERY)
            finally:
                os.close(tfd)
        except OSError:
            return False
        return True

    def write(self, command: str) -> WriteResult:
        check = self.can_write(command)
        if not check.ok:
            return check
        target = self._device()
        if isinstance(target, WriteResult):
            return target
        tty, dev = target
        suggest = self._root / f"suggest.{tty}"
        result = self._root / f"suggest.{tty}.result"
        result.unlink(missing_ok=True)
        fd = os.open(suggest, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(command + "\n")
        try:
            tfd = self._open(dev)
            try:
                os.write(tfd, QUERY)
            finally:
                os.close(tfd)
        except OSError:
            suggest.unlink(missing_ok=True)
            return WriteResult(False, "I could not reach that terminal; use Copy")
        end = time.monotonic() + self._wait
        while time.monotonic() < end:
            if result.exists():
                outcome = result.read_text().strip()
                if outcome == "ok":
                    return WriteResult(True)
                if outcome == "line-not-empty":
                    return WriteResult(
                        False, "there is already text at your prompt; clear it first"
                    )
                break
            time.sleep(0.02)
        suggest.unlink(missing_ok=True)  # a late answer must not insert something stale
        return WriteResult(False, "your terminal did not answer; use Copy")
