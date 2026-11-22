"""XDG path helper (ADR-0017, ADR-0018 §5). All filesystem locations come from here."""

from __future__ import annotations

import os
from pathlib import Path

APP = "ya-bro"


def _xdg(var: str, default: str) -> Path:
    value = os.environ.get(var)
    return Path(value) if value and os.path.isabs(value) else Path.home() / default


def config_dir() -> Path:
    return _xdg("XDG_CONFIG_HOME", ".config") / APP


def state_dir() -> Path:
    return _xdg("XDG_STATE_HOME", ".local/state") / APP


def data_dir() -> Path:
    return _xdg("XDG_DATA_HOME", ".local/share") / APP


def cache_dir() -> Path:
    return _xdg("XDG_CACHE_HOME", ".cache") / APP


def runtime_dir() -> Path:
    """Sockets, shell-hook spool, screenshot handles. Spec requires mode 0700, tmpfs."""
    base = os.environ.get("XDG_RUNTIME_DIR")
    if not base or not os.path.isabs(base):
        raise RuntimeError("XDG_RUNTIME_DIR is not set; refusing to use a world-readable path")
    return Path(base) / APP
