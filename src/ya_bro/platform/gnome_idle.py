"""IdleSource on GNOME: Mutter's IdleMonitor (ADR-0010 §1), asked through `gdbus`.

No gi import: one short subprocess per read, once a second at most, on the session bus.
"""

from __future__ import annotations

import asyncio
import re

_CALL = [
    "gdbus", "call", "--session", "--dest", "org.gnome.Mutter.IdleMonitor",
    "--object-path", "/org/gnome/Mutter/IdleMonitor/Core",
    "--method", "org.gnome.Mutter.IdleMonitor.GetIdletime",
]  # fmt: skip
_REPLY = re.compile(r"\(uint64 (\d+),\)")


def parse_idle(reply: str) -> float | None:
    m = _REPLY.search(reply)
    return int(m.group(1)) / 1000 if m else None


class GnomeIdleSource:
    async def idle_seconds(self) -> float:
        """Seconds since the last input; 0 when the monitor cannot be reached (never "idle")."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *_CALL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
            )
            out, _ = await asyncio.wait_for(proc.communicate(), 3)
        except (OSError, TimeoutError):
            return 0.0
        secs = parse_idle(out.decode(errors="replace")) if proc.returncode == 0 else None
        return secs if secs is not None else 0.0
