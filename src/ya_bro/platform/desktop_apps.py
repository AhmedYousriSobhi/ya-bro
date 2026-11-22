"""Installed apps from XDG .desktop files, for `broctl apps available` (#47)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ya_bro import dirs


@dataclass(frozen=True, slots=True)
class DesktopApp:
    app_id: str  # file name without .desktop; matches GTK/Flatpak app ids
    name: str
    wm_class: str = ""  # StartupWMClass; the id some apps (Chromium, Zoom) actually present


def search_dirs() -> list[Path]:
    home = dirs.data_dir().parent
    extra = [Path(p) / "applications" for p in os.environ.get("XDG_DATA_DIRS", "").split(":") if p]
    return [
        home / "applications",
        home / "flatpak/exports/share/applications",
        *(extra or [Path("/usr/local/share/applications"), Path("/usr/share/applications")]),
        Path("/var/lib/flatpak/exports/share/applications"),
    ]


def _parse(path: Path) -> DesktopApp | None:
    keys: dict[str, str] = {}
    in_entry = False
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in lines:
        if line.startswith("["):
            in_entry = line.strip() == "[Desktop Entry]"
        elif in_entry and "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            keys.setdefault(k.strip(), v.strip())
    if keys.get("Type") != "Application" or keys.get("NoDisplay") == "true":
        return None
    if keys.get("Hidden") == "true":
        return None
    return DesktopApp(path.stem, keys.get("Name", path.stem), keys.get("StartupWMClass", ""))


def available(roots: list[Path] | None = None) -> list[DesktopApp]:
    seen: dict[str, DesktopApp] = {}
    for root in roots if roots is not None else search_dirs():
        for path in sorted(root.glob("*.desktop")) if root.is_dir() else []:
            app = _parse(path)
            if app:
                seen.setdefault(app.app_id, app)  # earlier (user) dirs win
    return sorted(seen.values(), key=lambda a: a.name.lower())
