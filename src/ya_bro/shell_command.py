"""A command Bro shows for the user to run (ADR-0029): what one may contain, and its name.

One line, printable, bounded. Bro never executes it; the user presses Enter themselves.
"""

from __future__ import annotations

import re

MAX_COMMAND = 200
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def valid(command: str) -> bool:
    return bool(command.strip()) and len(command) <= MAX_COMMAND and not _CONTROL.search(command)


def argv0(command: str) -> str:
    """The name the shell hook records for this command: its first word without the path."""
    words = command.split()
    return words[0].rsplit("/", 1)[-1] if words else ""
