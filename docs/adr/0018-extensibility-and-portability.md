# ADR-0018: Extensibility and cross-platform portability plan

- Status: Proposed
- Date: 2026-11-20
- Issue: #13
- Depends on: ADR-0001, ADR-0003, ADR-0004, ADR-0012
- Implementation status (#16): Protocols in `src/ya_bro/interfaces/` (provisional surfaces, no entry-point registry yet); the `gi`/`dbus`/`Xlib` import ban is enforced by ruff `TID251` with a test; `dirs` helper and `IpcAdapter` Protocol exist. Not yet built: `ya_bro.backends` entry points and `probe()`.

## Context
Ya-Bro is Linux-only for now, with macOS and Windows planned "later". CLAUDE.md requires OS-specific code to sit behind interfaces. SPEC v1.0 also promises a plugin API.

Research added several interfaces that SPEC did not list:
- `CompositorBridge` (ADR-0004);
- `Hotkeys`, `IdleSource` and `ShellHook`;
- `SecretStore` and `Policy`.

On other platforms, the equivalents of the Linux mechanisms are well known from prior art ([ai-tools.md §2.1](../research/ai-tools.md)):
- **Clicky (macOS):** `NSPanel`.
- **Navisual (Windows):** UIA, a Tauri overlay and SendInput.
- **ChatGPT (macOS):** reads apps through the AX API.

## Decision drivers
- Port without rewriting the brain.
- Let contributors add backends (a new compositor, a new terminal) without touching core.
- Keep packs portable across OSes where the app is the same: Firefox, LibreOffice, VS Code.
- Avoid a premature plugin API.

## Options considered
| Option | For | Against |
|---|---|---|
| **Interfaces + entry-point backends + data-only packs (recommended)** | Standard Python mechanism (`importlib.metadata` entry points); backends discoverable; packs safe | Entry points need packaging discipline |
| **Dynamic plugin loading of arbitrary Python from packs** | Maximum flexibility | Security hole (ADR-0014); packs become code |
| **Cross-platform toolkit for everything now (e.g. Qt)** | One overlay for all OSes | Contradicts ADR-0001; layer-shell support is weaker; premature |

## Decision
1. **Interfaces** live in `ya_bro/interfaces/` as `typing.Protocol` classes with async methods. Each implementation lives under `ya_bro/platform/<os>/<impl>/`.

   | Interface | Linux implementations | macOS (later) | Windows (later) |
   |---|---|---|---|
   | `Perception` | AT-SPI (`gi.repository.Atspi`), OCR, vision | AX API (`AXUIElement`) | UI Automation |
   | `CompositorBridge` | GNOME extension (reference), KWin script (v0.2), sway/hyprland IPC, EWMH (CI) | `CGWindowListCopyWindowInfo` | `EnumWindows` / DWM frame bounds |
   | `Overlay` | GNOME extension (reference); GTK4 + layer-shell (v0.2); docked | `NSPanel` non-activating, `ignoresMouseEvents` | Layered window `WS_EX_TRANSPARENT \| WS_EX_TOPMOST` |
   | `Actuator` | AT-SPI Action, XTest, portal + libei, fake-input, wlr virtual | AX actions, `CGEvent` | UIA patterns, `SendInput` |
   | `Capture` | Portal + PipeWire, XShm, KWin ScreenShot2 | ScreenCaptureKit | Windows.Graphics.Capture |
   | `Hotkeys` | XGrabKey, kglobalaccel, GlobalShortcuts portal | `RegisterEventHotKey` / CGEventTap | `RegisterHotKey` |
   | `IdleSource` | Mutter IdleMonitor, ext-idle-notify, XScreenSaver | `CGEventSourceSecondsSinceLastEventType` | `GetLastInputInfo` |
   | `ShellHook` | bash/zsh/fish snippets → spool | same (zsh default) | PowerShell profile hook |
   | `Voice` | Wyoming services; PipeWire AEC | Wyoming; CoreAudio voice processing | Wyoming; WASAPI AEC |
   | `SecretStore` (as built: `keystore.Backend`, one API key, #5) | libsecret via a helper under the system python3 | Keychain | Credential Manager |
   | `Brain`, `Policy`, `Persona`, `StruggleDetector`, `PackRegistry` | OS-independent | same | same |

   The macOS and Windows columns are orientation only. They are unverified and would each get their own ADR at port time.
2. **Backend registration.** Implementations register through the `ya_bro.backends` entry-point group, with a `probe()` that reports capability and priority. The session probe (ADR-0002) picks the best available backend per interface. Third-party backends, such as a new compositor bridge or a terminal adapter, ship as separate Python packages.
3. **Packs are portable data.** `pack.toml` `match` rules can name per-OS identifiers, and fingerprints use role and name, which map across AT-SPI, AX and UIA with a role table (to be defined at port time).
4. **No arbitrary-code plugin API before v1.0.** The SPEC v1.0 "plugin API" means the stable interface Protocols plus entry points above. Pack-level executable hooks remain out-of-process (MCP / HTTP / D-Bus) under trust rules (ADR-0012).
5. **Portability hygiene rules** (lint-enforced where possible):
   - core modules may not import `gi`, `Xlib`, `dbus` or platform packages;
   - only `ya_bro/platform/**` may;
   - D-Bus IPC sits behind an `ipc` adapter, so a port can switch to another local IPC (XPC or named pipes) without touching components;
   - paths come from a `dirs` helper (XDG on Linux).
6. **The GTK4 overlay is expected not to port.** Each OS gets a native overlay backend. That is acceptable because the overlay is a thin renderer driven by declarative draw commands (ADR-0003).

## Consequences
- **Positive:** clear seams, safe contribution points, and a port that means writing backends rather than a rewrite.
- **Negative:** more abstraction up front. Some interfaces may change once a second OS exposes different capabilities (macOS AX coordinates are global, so the bridge becomes trivial there).
- **Risks:** interfaces over-fitted to Linux quirks, such as the coordinate pipeline. Keep the quirk inside the backend: `Perception` returns screen rects, and the bridge is an internal helper of the Linux perception backend.

## Validation plan
- An import-linter or ruff rule in CI blocks platform imports in core.
- A "fake OS" backend set (ADR-0016 fakes) runs the full step loop in tests, which proves core is OS-independent.
- At port time, a 2-week macOS spike implements `Perception` + `Overlay` + `CompositorBridge` and runs the pointing eval unchanged.

## Revisit if
- A port starts.
- Contributors need code plugins that cannot fit out-of-process.

## Sources
- Python entry points: https://packaging.python.org/en/latest/specifications/entry-points/
- [docs/research/ai-tools.md](../research/ai-tools.md): §2.1 Clicky (macOS NSPanel), Navisual (Windows UIA/Tauri), ChatGPT Work with Apps (macOS AX)
- [docs/research/linux-platform.md](../research/linux-platform.md): matrix (Linux mechanisms)
