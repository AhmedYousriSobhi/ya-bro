"""Which allowed commands finished, and how (from the shell hook's spool), for a step to wait on."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol


class _Spool(Protocol):
    def poll(self) -> list[dict[str, int | str]]: ...


class CommandWatch:
    """Keeps every record the spool yields (name, exit code, when); asks are by name and time."""

    def __init__(self, spool: _Spool, clock: Callable[[], float] = time.time) -> None:
        self._spool = spool
        self._clock = clock
        self._seen: list[tuple[float, str, int]] = []

    def now(self) -> float:
        return self._clock()

    def finished(self, name: str, since: float) -> int | None:
        """Exit code of the latest `name` that finished after `since`, else None."""
        for rec in self._spool.poll():
            self._seen.append((self._clock(), str(rec["argv0"]), int(rec["exit"])))
        return next((c for t, n, c in reversed(self._seen) if n == name and t >= since), None)
