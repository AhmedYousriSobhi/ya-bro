"""Targets (ADR-0025): a tool with a web UI and/or CLI that Bro may see, not a whole browser.

One file per target in `$XDG_CONFIG_HOME/ya-bro/targets/<id>.toml`; having the file is the consent.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from ya_bro import dirs

_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")
_ORIGIN = re.compile(r"https?://(?:[A-Za-z0-9.-]{1,253}|\[[0-9a-fA-F:]{2,39}\])(?::\d{1,5})?")
_COMMAND = re.compile(r"[A-Za-z0-9_.-]{1,32}")


class TargetError(ValueError):
    pass


@dataclass(frozen=True)
class Target:
    id: str
    origins: tuple[str, ...] = field(default_factory=tuple)
    commands: tuple[str, ...] = field(default_factory=tuple)


def _clean(target: Target) -> Target:
    if not _ID.fullmatch(target.id):
        raise TargetError(f"bad target id {target.id!r}: use a-z, 0-9, - and _ (max 32)")
    origins = tuple(o.rstrip("/").lower() for o in target.origins)
    for origin in origins:
        if not _ORIGIN.fullmatch(origin):
            raise TargetError(f"bad origin {origin!r}: use scheme://host[:port], no path")
    for command in target.commands:
        if not _COMMAND.fullmatch(command):
            raise TargetError(f"bad command name {command!r}")
    if not origins and not target.commands:
        raise TargetError("a target needs at least one --origin or --command")
    return Target(target.id, tuple(dict.fromkeys(origins)), tuple(dict.fromkeys(target.commands)))


def _dir(config_dir: Path | None) -> Path:
    return (config_dir or dirs.config_dir()) / "targets"


def save(target: Target, config_dir: Path | None = None) -> Path:
    t = _clean(target)
    path = _dir(config_dir) / f"{t.id}.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["[target]", f"id = {json.dumps(t.id)}"]
    if t.origins:
        lines += ["[web]", f"origins = {json.dumps(list(t.origins))}"]
    if t.commands:
        lines += ["[cli]", f"commands = {json.dumps(list(t.commands))}"]
    path.write_text("\n".join(lines) + "\n")
    return path


def remove(target_id: str, config_dir: Path | None = None) -> bool:
    if not _ID.fullmatch(target_id):
        raise TargetError(f"bad target id {target_id!r}")
    path = _dir(config_dir) / f"{target_id}.toml"
    if not path.exists():
        return False
    path.unlink()
    return True


def load_all(config_dir: Path | None = None) -> list[Target]:
    """Valid targets, sorted by id. A malformed file is skipped (never widens scope)."""
    out = []
    for path in sorted(_dir(config_dir).glob("*.toml")):
        try:
            data = tomllib.loads(path.read_text())
            out.append(
                _clean(
                    Target(
                        data["target"]["id"],
                        tuple(data.get("web", {}).get("origins", ())),
                        tuple(data.get("cli", {}).get("commands", ())),
                    )
                )
            )
        except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError, TargetError):
            continue
    return out


def allowed_origins(config_dir: Path | None = None) -> frozenset[str]:
    return frozenset(o for t in load_all(config_dir) for o in t.origins)
