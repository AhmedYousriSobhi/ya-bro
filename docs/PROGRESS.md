# Progress

Living status sheet. Update it in every PR (see CLAUDE.md workflow). Plan: [ADR-0022](adr/0022-mvp-build-plan.md).

Legend: done · in progress · todo

## Milestones
| Milestone | Status | Issues |
|---|---|---|
| M0 Foundations | in progress | #16 skeleton (done, #37), #17 doctor and setup (done, PR #42), #36 config and log API (done, #41) |
| M1 Spikes S1, S2, S3 | in progress | #15 (S1 measured and merged in #38, go/no-go open), #2, #18 |
| M2 Perception + bridge | todo | #4, #18 |
| M3 Overlay | todo | #3 |
| M4 Step loop | todo | #5, #19, #20 |
| M5 Packs + terminal | todo | #8, #21, #22, #31 |
| M6 Struggle + persona | todo | #9, #23, #24 |
| M7 MVP hardening | todo | #25, #26 |
| v0.15 Do-it / v0.2 KWin + voice | todo | #27, #28, #29, #30 |

## Log
### 2026-11-22: #66 Show-me step loop
Done: `StepLoop` (core, interfaces only), TOML plans + `ScriptedBrain`, `ShowMePolicy`, GNOME adapters (`GnomeBridge`, `GnomeOverlay` with user events and 2 s keepalive, `AtspiPerception` enforcing scope itself), `broctl show`. Overlay interface gained buttons and an event stream. 11 unit tests with fakes; headless-shell end to end (15 checks, 3 runs in a row): scope, ring on the right button (the click at its centre advances the plan), the bubble's Stop button, hidden at the end.
Not done: the Claude brain (#5 stays open), Do-it, voice; non-GTK apps and browsers are unmeasured (browsers need the page to report its state, #31, or a11y flags); multi-window apps pick the focused window; popups and menus; not run on the live desktop yet.

### 2026-11-22: #61 tab-scoped web targets (workbench)
Done: `broctl targets list|allow|revoke`; a loopback token endpoint in `broctl` (127.0.0.1:47800, token only for an allowed `Origin` + `X-Scope-Token` header + loopback `Host`); `point` and `scope watch` pass the token to the stand-in core over stdin. workbench merged its opt-in title token (workbench#984, off by default, two switches). Verified end to end in the isolated shell with a real Chrome and the real workbench page: flag off, tab invisible; flag on, tab in scope; another tab active, out of scope; back, in scope again (6 of 6, no CSP errors).
Not done: Firefox and the live desktop (your Firefox must be revoked from `apps` first, then restart workbench with `WORKBENCH_DESKTOP_HELPER=1`); CLI commands are stored but not enforced (needs #21); the port is fixed at 47800; no real core yet issues the token.

### 2026-11-22: #57 hot-load
Done: `broctl load` (Looking Glass snippet, clipboard, wait for ENABLED); isolated-shell test with injected keys loads a late-installed extension and `Bridge1` answers; harness option `YB_LATE_EXT=1`. Not done: not yet run on the real desktop (the extension has never been loaded in the live session); Looking Glass layout on your GNOME may differ from the test shell.

### 2026-11-22: hot-loading the extension
Measured in the isolated shell: no supported route loads a newly installed extension without a Shell restart (directory, gsettings, `gnome-extensions enable`, `disable-user-extensions` toggle all failed). Open options: one logout (current), a Looking Glass paste (manual, untested), publication, or a no-extension overlay (needs research).

### 2026-11-22: #53 point and scope watch
Done: `broctl point` and `broctl scope watch` (stand-in core, `platform/gnome_demo.py`); overlay shown, followed and hidden in the isolated headless shell. Not done: not run on the real desktop yet (the extension has never been loaded in the live session); no voice, no step logic, no text input.

### 2026-11-22: #51 setup app picker
Done: `broctl setup` searches installed apps by name or id, lists up to 15, picks by number, and stores the window class when present. Not done: listing apps that are running right now (the extension is default-deny, so it cannot say what is open); the window-class-versus-desktop-id match is unverified on a real desktop.

### 2026-11-22: #47 pack-scoped targets (design + apps available)
Done: `broctl apps available` (app id, name, window class) and ADR-0025 (proposed).
Spike S8 (title token, [findings](research/spikes/S8-active-tab-scope.md)): works in the isolated shell with a stand-in window (listed and dropped in about 25 ms, removal emitted, 3 runs). Also verified with a real browser (Chrome for Testing, non-snap, isolated shell): in scope on tab A, out about 20 ms after switching to another origin, token unreadable from the other origin. Not verified: Firefox, core-side token issuance.
Not done here: CLI-command scoping, #8 packs and #21 shell hook (web targets landed in #61, below).

### 2026-11-22: #45 broctl
Done: `broctl` entry point with `version`, `doctor`, `setup`, `apps list|allow|revoke`; docs and ADRs renamed from `ya-bro <cmd>`; ADR-0024.
Not done: `config`, `stats`, `sent`, `forget`, `pack` verbs (planned in ADR-0024); the `ya-bro` agent binary does not exist yet.

### 2026-11-22: #43 per-app scoping
Done: extension `allowed-apps` (gsettings, default empty), enforced in Bridge1 (`ListWindows`, signals, `GetWindowTitle`, `GetPointer` only while an allowed app is focused); `broctl setup` asks for the app id; `doctor` shows the allowlist; contract test checks empty-list denial (passes in the isolated headless shell).
Not done: the overlay still draws wherever core says (core only knows allowed windows); an app id that appears after `window-created` is not announced until its first geometry change; the Python perceiver/Policy enforcement (#4, #20) and a real-desktop run; the measurement suite uses fixtures not on the default allowlist (set `YB_ALLOWED`).

### 2026-11-22: #17 doctor and setup
Done: `broctl doctor` (session type, `toolkit-accessibility`, a11y bus, extension state via `GetExtensionInfo`, API key presence without the value) and `broctl setup` (each persistent change asks for an explicit yes: toolkit-accessibility, copy + enable the Shell extension, then one re-login). Probes shell out through an injectable runner in `platform/linux_setup.py`; tests never touch the real session.
Not done: per-app scoping (#43; setup text now says access is system-wide), `GetExtensionErrors` and API-version match (needs Bridge1 `GetInfo` from #18), PipeWire AEC, portal capabilities, library versions, Arabic font check, `.deb` install path. Not exercised on a real desktop (`setup` has only run against fakes).
### 2026-11-22: #36 config loader and log API
Done: `ya_bro.config` (stdlib dataclasses + `tomllib`, global `config.toml` with per-app `apps/<id>.toml` overrides, unknown keys and bad values warn and fall back to defaults) and `ya_bro.logs` (typed JSONL records, short tokens and numbers only, free text raises `ContentError`, file mode 0600). Tests in `tests/test_config_logs.py`.
Not done: `broctl config get/set/edit` CLI, live reload, `--debug-content`, SQLite state, retention (later issues). Pydantic was not added; dataclasses keep core dependency-free.

### 2026-11-22: #16 project skeleton
Done:
- `src/` layout, `pyproject.toml` (uv, Python 3.12, ruff, pytest).
- 12 interface Protocols (`src/ya_bro/interfaces/`) and shared types, **provisional**.
- In-memory fakes for all 12 in `tests/fakes/`, each checked against its Protocol.
- `ipc/` interface-name helper and `IpcAdapter` Protocol; `dirs.py` XDG helper; `ya-bro --version`.
- Portability rule: ruff bans `gi`, `dbus`, `Xlib` outside `src/ya_bro/platform/**`; a test proves it fires.
- GTK4 fixture app + AT-SPI probe, run on an isolated bus with `dbus-run-session`.
- `scripts/check.sh` (lint, format, unit, integration) and a CI workflow draft at `docs/ci/ci.yml`.

Not done (deliberately deferred, no silent drops):
- No real D-Bus adapter (Gio) yet: needs the first process that uses it.
- ~~No `config.toml` loader or typed log API~~ (done in #36).
- GTK3 and Qt6 fixture apps (ADR-0016): only GTK4 exists.
- Policy, Brain and the rest are fakes only; no real implementations.

Verification:
- `scripts/check.sh` passes locally (25 unit tests, 1 AT-SPI integration test) on Ubuntu with Wayland + system Python 3.14 for the fixture.
- **CI is not active.** The push of `.github/workflows/ci.yml` was rejected (token lacks `workflow` scope). To enable: `mkdir -p .github/workflows && cp docs/ci/ci.yml .github/workflows/ci.yml`, push with a token that has `workflow` scope (or add the file in the GitHub UI), then confirm the first run is green. The workflow has never run. Trigger: push to `main` only (maintainer decision), so PRs into `dev` get no CI; run `scripts/check.sh` before opening them.
- Wiki: `Home` and `Development` pages published (mirrors of `docs/`; `docs/` stays the source of truth).

### 2026-11-22: #15 spike S1 (measured, go/no-go open)
Done: extension prototype and an isolated headless-shell harness, plus measurements at 100% and 150% ([findings](research/spikes/S1-gnome-extension.md)). Passing: click-through 0/1000 blocked, focus safety, ring placement 1.5 px, ring above popover/maximized/fullscreen and hidden in the overview, GTK4/libadwaita (frame origin) and GTK3 Wayland (buffer origin) coordinates within 0.6 px, caller checks, dead-man switch.

Update (nested real-display run with `mutter-dev-bin`): same extension on the real GPU, frame interval median 8.4 ms (about 119 fps). The stop key binding failed in about half of fresh sessions (headless and nested); a stage `captured-event` fallback fixed it (10/10 headless, 5/5 nested). A real-keyboard check by the maintainer in the nested shell recorded 8 stop-key events (confirmed).

Open (S1 stays open): XWayland GTK3 (a client-area rect was tried and does not explain the offset) (needs frame + (0, 37)) and fractional-scale X11; Qt6 and Firefox not covered; `layout_mode` unknown to the extension; nothing verified on a real desktop (fps, scanout, lock screen); the portal + libei path (S7) not exercised. The extension has never been loaded in the live session.

Incidents (disclosed in the findings): token printed once (rotate it), a test window probably reached the real display, and a harness WirePlumber probably lit the webcam LED. Fixed in the harness with a private display, a private Xwayland, and a camera-masked WirePlumber.
