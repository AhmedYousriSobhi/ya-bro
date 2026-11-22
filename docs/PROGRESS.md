# Progress

Living status sheet. Update it in every PR (see CLAUDE.md workflow). Plan: [ADR-0022](adr/0022-mvp-build-plan.md).

Legend: done · in progress · todo

## Milestones
| Milestone | Status | Issues |
|---|---|---|
| M0 Foundations | in progress | #16 skeleton (PR open), #17 doctor and setup (todo) |
| M1 Spikes S1, S2, S3 | todo | #15, #2, #18 |
| M2 Perception + bridge | todo | #4, #18 |
| M3 Overlay | todo | #3 |
| M4 Step loop | todo | #5, #19, #20 |
| M5 Packs + terminal | todo | #8, #21, #22, #31 |
| M6 Struggle + persona | todo | #9, #23, #24 |
| M7 MVP hardening | todo | #25, #26 |
| v0.15 Do-it / v0.2 KWin + voice | todo | #27, #28, #29, #30 |

## Log
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
- **CI is not active.** The push of `.github/workflows/ci.yml` was rejected (token lacks `workflow` scope). To enable: `mkdir -p .github/workflows && cp docs/ci/ci.yml .github/workflows/ci.yml`, push with a token that has `workflow` scope (or add the file in the GitHub UI), then confirm the first run is green. The workflow has never run.
- The wiki repo does not exist for this GitHub repo; guides live in `docs/` instead.
