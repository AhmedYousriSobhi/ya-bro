# Progress

Living status sheet. Update it in every PR (see CLAUDE.md workflow). Plan: [ADR-0022](adr/0022-mvp-build-plan.md).

Legend: done · in progress · todo

## Milestones
| Milestone | Status | Issues |
|---|---|---|
| M0 Foundations | in progress | #16 skeleton (done, #37), #17 doctor and setup (done, PR open), #36 config and log API (todo) |
| M1 Spikes S1, S2, S3 | in progress | #15 (S1 measured and merged in #38, go/no-go open), #2, #18 |
| M2 Perception + bridge | todo | #4, #18 |
| M3 Overlay | todo | #3 |
| M4 Step loop | todo | #5, #19, #20 |
| M5 Packs + terminal | todo | #8, #21, #22, #31 |
| M6 Struggle + persona | todo | #9, #23, #24 |
| M7 MVP hardening | todo | #25, #26 |
| v0.15 Do-it / v0.2 KWin + voice | todo | #27, #28, #29, #30 |

## Log
### 2026-11-22: #17 doctor and setup
Done: `ya-bro doctor` (session type, `toolkit-accessibility`, a11y bus, extension state via `GetExtensionInfo`, API key presence without the value) and `ya-bro setup` (each persistent change asks for an explicit yes: toolkit-accessibility, copy + enable the Shell extension, then one re-login). Probes shell out through an injectable runner in `platform/linux_setup.py`; tests never touch the real session.
Not done: per-app scoping (#43; setup text now says access is system-wide), `GetExtensionErrors` and API-version match (needs Bridge1 `GetInfo` from #18), PipeWire AEC, portal capabilities, library versions, Arabic font check, `.deb` install path. Not exercised on a real desktop (`setup` has only run against fakes).

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
- No `config.toml` loader or typed log API (ADR-0017): tracked in #36.
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
