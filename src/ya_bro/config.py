"""Typed `config.toml` loader (ADR-0017 §2). Unknown keys and bad values warn, never crash."""

from __future__ import annotations

import logging
import re
import tomllib
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import Any

from ya_bro import dirs

log = logging.getLogger(__name__)

SENSITIVITIES = ("low", "normal", "high")
LANGUAGES = ("auto", "en", "ar")


@dataclass(frozen=True, slots=True)
class Proactive:
    enabled: bool = False  # opt-in (SPEC §7)
    sensitivity: str = "normal"


@dataclass(frozen=True, slots=True)
class Capture:
    allowed: bool = False


@dataclass(frozen=True, slots=True)
class DoIt:
    allowed: bool = False


@dataclass(frozen=True, slots=True)
class Brain:
    model: str = "claude-opus-5-5"  # ADR-0008: IDs live in config, never in code paths
    max_calls: int = 30  # per task


@dataclass(frozen=True, slots=True)
class Config:
    proactive: Proactive = field(default_factory=Proactive)
    capture: Capture = field(default_factory=Capture)
    do_it: DoIt = field(default_factory=DoIt)
    brain: Brain = field(default_factory=Brain)
    humour: int = 1  # 0 = off .. 3 = chatty
    language: str = "auto"  # auto (English until the user writes Arabic), en or ar
    less_chatty: bool = False  # mute optional lines and all humour


def _check(section: str, key: str, value: Any, default: Any) -> bool:
    ok = type(value) is type(default)  # bool is not an int here
    if ok and key == "sensitivity":
        ok = value in SENSITIVITIES
    if ok and key == "language":
        ok = value in LANGUAGES
    if ok and key == "model":
        ok = bool(re.fullmatch(r"[a-z0-9][a-z0-9.-]{2,63}", value))
    if ok and key == "max_calls":
        ok = 1 <= value <= 200
    if ok and section == "" and key == "humour":
        ok = 0 <= value <= 3
    if not ok:
        name = f"{section}.{key}" if section else key
        log.warning("config: bad value for %s, using default", name)
    return ok


def _merge(base: Config, data: dict[str, Any], where: str) -> Config:
    updates: dict[str, Any] = {}
    for key, value in data.items():
        current = getattr(base, key, None)
        if current is None:
            log.warning("config: unknown key %r in %s", key, where)
        elif isinstance(value, dict) and hasattr(current, "__dataclass_fields__"):
            known = {f.name for f in fields(current)}
            sub: dict[str, Any] = {}
            for k, v in value.items():
                if k not in known:
                    log.warning("config: unknown key %r in %s", f"{key}.{k}", where)
                elif _check(key, k, v, getattr(current, k)):
                    sub[k] = v
            updates[key] = replace(current, **sub)
        elif isinstance(current, dict | tuple) or hasattr(current, "__dataclass_fields__"):
            log.warning("config: %r in %s must be a table", key, where)
        elif _check("", key, value, current):
            updates[key] = value
    return replace(base, **updates)


def _read(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except FileNotFoundError:
        return {}
    except (tomllib.TOMLDecodeError, OSError) as exc:
        log.warning("config: cannot read %s (%s), ignoring it", path, type(exc).__name__)
        return {}


def load(app_id: str | None = None, config_dir: Path | None = None) -> Config:
    """Global config, then `apps/<app_id>.toml` on top (per-app overrides win)."""
    root = config_dir or dirs.config_dir()
    cfg = _merge(Config(), _read(root / "config.toml"), "config.toml")
    if app_id:
        if "/" in app_id or app_id.startswith("."):
            raise ValueError(f"invalid app id: {app_id!r}")
        cfg = _merge(cfg, _read(root / "apps" / f"{app_id}.toml"), f"apps/{app_id}.toml")
    return cfg
