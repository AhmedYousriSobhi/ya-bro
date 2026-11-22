"""IPC contract: versioned D-Bus names (ADR-0003) behind an adapter boundary (ADR-0018 §5).

Skeleton only: names and the adapter Protocol. The Gio-based adapter lands under
``ya_bro/platform/`` with the first process that needs it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

# The reverse-DNS prefix is a proposal in ADR-0003.
BUS_PREFIX = "io.github.ahmedyousrisobhi.YaBro"

SERVICES = ("Core", "Overlay", "Perceiver", "Actuator", "Bridge")


def interface_name(service: str, version: int = 1) -> str:
    """Return e.g. ``io.github.ahmedyousrisobhi.YaBro.Overlay1``."""
    if service not in SERVICES:
        raise ValueError(f"unknown service {service!r}; expected one of {SERVICES}")
    if version < 1:
        raise ValueError("version must be >= 1")
    return f"{BUS_PREFIX}.{service}{version}"


class IpcAdapter(Protocol):
    """Local IPC seam so a port can swap D-Bus for XPC or named pipes."""

    async def call(self, interface: str, method: str, *args: object) -> object: ...
    def subscribe(self, interface: str, signal: str, handler: Callable[..., None]) -> None: ...
