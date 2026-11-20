# ADR-0015: Packaging and distribution

- Status: Proposed
- Date: 2026-11-20
- Issue: #13
- Depends on: ADR-0002, ADR-0003, ADR-0006, ADR-0020

## Context
Ya-Bro needs four things from the system that sandboxes restrict:
- read access to *other* apps' AT-SPI trees;
- a layer-shell or X11 overlay;
- D-Bus access to KWin scripting or a GNOME extension;
- optionally, portals or XTest.

Facts ([factsheet.md D](../research/factsheet.md); [linux-platform.md §0, §3.13](../research/linux-platform.md)):

- **Flatpak.**
  - Its default a11y access is a filtered `xdg-dbus-proxy` that lets an app *expose* its own tree, not read others' trees (read from the Flatpak source).
  - Workarounds (`--talk-name=org.a11y.Bus`, `--no-a11y-bus`) effectively unsandbox the app and invite Flathub review friction.
  - KWin 6.8 hides fake-input, ScreenShot2 and window-management protocols **only** from Flatpak/Snap clients.
- **Snap.** Strict confinement is insufficient for cross-app AT-SPI, so it would need classic confinement.
- **PyGObject / pycairo on PyPI** ship **no Linux wheels** (sdist only; PyGObject ≥ 3.52 needs GLib ≥ 2.80). **pyatspi is not on PyPI.**
  - Typelibs (GTK4, Atspi, Gtk4LayerShell) always come from the system.
  - Practical installs therefore use distro `python3-gi` plus a venv with `--system-site-packages` (supported by `uv venv`).
- **AppImage.** GTK4 and GLib bundling is fragile; the excludelist warns about GLib.
- **Debian `dh-python` / pybuild.** A clean path for native packages with plain `Depends:` on `python3-gi`, `gir1.2-gtk-4.0`, `gir1.2-atspi-2.0`, `gir1.2-gtk4layershell-1.0` (in the Ubuntu 26.04 archive at 1.3.0).
- **Autostart.** Per the XDG autostart spec: `~/.config/autostart/*.desktop`, honouring `Hidden=true`.

## Decision drivers
- Works fully on the reference platform (unsandboxed).
- Easy for the maintainer and early adopters.
- Low upkeep.
- Clear about permissions.

## Options considered
| Option | For | Against |
|---|---|---|
| **`uv tool` / `pipx` install with `--system-site-packages` + documented distro deps (recommended for v0.x)** | Fast iteration; matches ADR-0001 tooling; full capability | The user must install system packages; less polished |
| **Native .deb (then rpm/AUR)** | Cleanest dependency story, autostart and desktop files, KWin script and GNOME extension shipped together | Per-distro packaging work |
| **Flatpak** | Discoverability, auto-updates | Cannot read other apps' a11y trees without unsandboxing. Loses KWin privileged protocols on 6.8. Review friction. |
| **Snap** | Ubuntu default store | Needs classic confinement |
| **AppImage** | Single file | GTK4/GLib bundling issues; heavy |

## Decision
1. **v0.x: source install.**
   - `uv tool install ya-bro` (or `pipx install --system-site-packages`) on top of a `scripts/install-deps.sh` that prints and, after confirmation, runs the distro package command:
     - Ubuntu/Debian: `python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-atspi-2.0 gir1.2-gtk4layershell-1.0 at-spi2-core`, plus optional `tesseract-ocr tesseract-ocr-ara`;
     - Fedora and Arch equivalents.
   - Python ≥ 3.12 is required. Note that PyGObject from the distro must match the interpreter, which is why the system Python is used.
2. **v0.3+: native `.deb`** built with dh-python/pybuild, installed to a private dir.
   - The package ships the desktop file, the autostart template (not enabled), the KWin script (loaded at runtime, so it also works from a source install) and the GNOME Shell extension.
   - rpm and AUR follow when there is demand.
3. **Not supported:** Flatpak, Snap and AppImage. The README states why: the sandbox blocks cross-app accessibility, and a reduced Flatpak build would mislead users. Revisit when Newton or a11y portals exist.
4. **Voice engines** are separate optional installs, each carrying its own licence:
   - `ya-bro[voice]` for the Python-side Wyoming client, Silero and faster-whisper;
   - Piper (GPL) through its own package or the Wyoming Piper server, as the user chooses.

   Model weights download on first use, with checksums and licence display (ADR-0020).
5. **GNOME extension** (v0.2): shipped in the repo and in the deb, installed per user with `gnome-extensions install`. Publication on extensions.gnome.org only once a human has reviewed or written the code (their guidelines reject AI-generated code).
6. **Autostart.** Off by default. The settings toggle writes `~/.config/autostart/ya-bro.desktop`; turning it off writes `Hidden=true` or removes the file. Optional systemd `--user` unit later, for restart-on-crash.
7. **Permissions disclosure.** `ya-bro doctor` lists every capability, its status and how to grant it:
   - the a11y bus;
   - layer-shell;
   - the KWin script;
   - the portal (RemoteDesktop / ScreenCast / GlobalShortcuts);
   - the shell hook;
   - PipeWire AEC.

## Consequences
- **Positive:** full capability, minimal packaging work early on, and honest positioning.
- **Negative:** no app-store presence, and manual dependency installs.
- **Risks:**
  - A distro PyGObject that is too old for the asyncio API (≥ 3.50).
  - A distro GTK older than 4.14 lacking needed APIs.

  `doctor` checks both versions.

## Validation plan
- Install test in clean containers or VMs: Ubuntu 26.04 and 24.04, Fedora (current), Debian 13. `ya-bro doctor` must pass on the reference platform after following the README in ≤ 10 minutes.
- Track in CI by building the venv against the system site-packages in an Ubuntu 26.04 container (ADR-0016).

## Revisit if
- Flatpak gains a proper "assistive technology" permission.
- Demand appears for an app-store release.
- Packaging becomes the main adoption blocker. ADR-0001 also names this as a revisit trigger.

## Sources
- [docs/research/factsheet.md](../research/factsheet.md): Part D
- [docs/research/linux-platform.md](../research/linux-platform.md): §0 item 6, §3.13
- Flatpak command reference (`--a11y-bus`): https://docs.flatpak.org/en/latest/flatpak-command-reference.html
- Flatpak `flatpak-run-dbus.c`: https://github.com/flatpak/flatpak/blob/main/common/flatpak-run-dbus.c
- PyGObject getting started: https://pygobject.gnome.org/getting_started.html
- XDG autostart: https://specifications.freedesktop.org/autostart/latest/
- Debian pybuild: https://wiki.debian.org/Python/Pybuild
