"""Content-free JSONL log API (ADR-0017 §3).

Records carry event type, ids, numbers and short tokens only. There is no way to pass free
text, so typed text or screen content cannot end up in a log by accident.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from ya_bro import dirs

# Error classes, tiers, hashes, enum names. Whitespace and long strings are rejected.
_TOKEN = re.compile(r"[A-Za-z0-9_.:+-]{1,64}")
_EVENT = re.compile(r"[a-z][a-z0-9_.]{0,63}")
_KEY = re.compile(r"[a-z][a-z0-9_]{0,31}")


class ContentError(ValueError):
    """A log field could hold free text or content."""


@dataclass(frozen=True, slots=True)
class Ids:
    session_id: str
    task_id: str = ""
    step_id: str = ""
    corr_id: str = ""  # propagated across D-Bus calls (ADR-0003)


def _clean_id(name: str, value: str) -> str:
    if value and not _TOKEN.fullmatch(value):
        raise ContentError(f"{name} must be a short token")
    return value


def make_record(event: str, ids: Ids, **fields: int | float | bool | str) -> dict:
    if not _EVENT.fullmatch(event):
        raise ContentError(f"bad event name: {event!r}")
    record: dict = {"ts": round(time.time(), 3), "event": event}
    for name in ("session_id", "task_id", "step_id", "corr_id"):
        record[name] = _clean_id(name, getattr(ids, name))
    for key, value in fields.items():
        if not _KEY.fullmatch(key) or key in record:
            raise ContentError(f"bad field name: {key!r}")
        if isinstance(value, str) and not _TOKEN.fullmatch(value):
            raise ContentError(f"field {key!r} is not a short token (free text is not allowed)")
        if not isinstance(value, int | float | str):  # bool is an int
            raise ContentError(f"field {key!r} has unsupported type {type(value).__name__}")
        record[key] = value
    return record


class JsonlLog:
    """Append-only JSONL file under `dirs.state_dir()/logs` (0600)."""

    def __init__(self, ids: Ids, path: Path | None = None) -> None:
        self.ids = ids
        self.path = path or dirs.state_dir() / "logs" / f"{time.strftime('%Y%m%d')}.jsonl"
        self._fh: IO[str] | None = None

    def write(self, event: str, **fields: int | float | bool | str) -> dict:
        record = make_record(event, self.ids, **fields)
        if self._fh is None:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            self._fh = open(self.path, "a", encoding="utf-8", opener=_private)
        self._fh.write(json.dumps(record, separators=(",", ":")) + "\n")
        self._fh.flush()
        return record

    def close(self) -> None:
        if self._fh:
            self._fh.close()
            self._fh = None


def _private(path: str, flags: int) -> int:
    return os.open(path, flags, 0o600)
