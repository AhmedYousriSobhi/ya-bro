"""The shell hook's spool, core side (ADR-0021 §1-2, ADR-0025).

$XDG_RUNTIME_DIR/ya-bro/ (0700, tmpfs) holds `commands`, one allowed command name per line, and
`shell.spool`, the file the hook appends to. Core creates both when it starts and removes them when
it stops, so the hook is silent while Ya-Bro is not running. A command that is not allowed is never
written at all; core checks again on read anyway.

Record, one JSON line: {"v":1,"ts":ms,"argv0":name,"exit":code,"ms":duration,"tty":"pts/3"}.
Nothing else is ever read from the file: no arguments, no output.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import shutil
from collections.abc import AsyncIterator, Iterable
from pathlib import Path

from ya_bro import dirs

SPOOL = "shell.spool"
COMMANDS = "commands"
MAX_READ = 64 * 1024  # bytes taken per poll; the rest waits for the next one
MAX_LINE = 512
TRUNCATE_AT = 256 * 1024  # a spool this large, fully read, is emptied
_NAME = re.compile(r"[A-Za-z0-9_.-]{1,32}")
_TTY = re.compile(r"[a-z0-9/]{0,32}")
_WEEK_MS = 7 * 24 * 3600 * 1000


class ShellSpool:
    def __init__(self, root: Path | None = None) -> None:
        self._root = root or dirs.runtime_dir()
        self._offset = 0
        self._tail = b""
        self._allowed: frozenset[str] = frozenset()

    @property
    def spool_path(self) -> Path:
        return self._root / SPOOL

    def open(self, commands: Iterable[str]) -> None:
        self._root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self._root, 0o700)
        fd = os.open(self.spool_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.close(fd)
        self._offset, self._tail = 0, b""
        self.set_commands(commands)

    def set_commands(self, commands: Iterable[str]) -> None:
        """The names the hook may record. Anything that is not a plain command name is dropped."""
        self._allowed = frozenset(c for c in commands if _NAME.fullmatch(c))
        path = self._root / COMMANDS
        tmp = path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write("".join(f"{c}\n" for c in sorted(self._allowed)))
        os.replace(tmp, path)

    def close(self) -> None:
        shutil.rmtree(self._root, ignore_errors=True)

    def poll(self) -> list[dict[str, int | str]]:
        """New, valid records since the last poll; malformed or disallowed lines are skipped."""
        try:
            size = self.spool_path.stat().st_size
            if size < self._offset:  # someone emptied it
                self._offset, self._tail = 0, b""
            with open(self.spool_path, "rb") as f:
                f.seek(self._offset)
                data = f.read(MAX_READ)
        except OSError:
            return []
        self._offset += len(data)
        data = self._tail + data
        *lines, self._tail = data.split(b"\n")
        if len(self._tail) > MAX_LINE:
            self._tail = b""
        events = [e for e in (self._parse(line) for line in lines) if e is not None]
        if self._offset >= TRUNCATE_AT and not self._tail:
            with contextlib.suppress(OSError):
                os.truncate(self.spool_path, 0)
                self._offset = 0
        return events

    def _parse(self, line: bytes) -> dict[str, int | str] | None:
        if not line or len(line) > MAX_LINE:
            return None
        try:
            rec = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            return None
        if not isinstance(rec, dict) or rec.get("v") != 1:
            return None
        argv0, code, ms, ts, tty = (rec.get(k) for k in ("argv0", "exit", "ms", "ts", "tty"))
        ints = all(isinstance(x, int) and not isinstance(x, bool) for x in (code, ms, ts))
        if not (isinstance(argv0, str) and argv0 in self._allowed and ints):
            return None
        if not (isinstance(tty, str) and _TTY.fullmatch(tty)):
            return None
        if not (0 <= code <= 255 and 0 <= ms <= _WEEK_MS and ts >= 0):
            return None
        return {"argv0": argv0, "exit": code, "ms": ms, "ts": ts, "tty": tty}

    async def events(self, interval: float = 0.2) -> AsyncIterator[dict[str, int | str]]:
        """The ShellHook interface. Polls, as the stdlib has no inotify; 0.2 s is not felt."""
        while True:
            for event in self.poll():
                yield event
            await asyncio.sleep(interval)
