# Progress

Living status sheet. Update it in every PR (see CLAUDE.md workflow). Plan: [ADR-0022](adr/0022-mvp-build-plan.md).

Legend: done · in progress · todo

## Milestones
| Milestone | Status | Issues |
|---|---|---|
| M0 Foundations | in progress | #16 skeleton (done, #37), #17 doctor and setup (done, PR #42), #36 config and log API (done, #41) |
| M1 Spikes S1, S2, S3 | in progress | #15 (S1 measured and merged in #38, go/no-go open), #2, #18 |
| M2 Perception + bridge | in progress | #4 (AT-SPI perceiver done for GTK, scope enforced, text read), #18 (extension and bridge done) |
| M3 Overlay | in progress | #3 (ring, bubble, buttons, placement done; avatar and pointer flight are basic) |
| M4 Step loop | in progress | #5 (scripted Show-me loop done, ADR-0026; Claude brain open), #19 (harness and synthetic corpus done, real recordings open), #20 (engine and redaction done, not yet wired to any LLM request) |
| M5 Packs + terminal | in progress | #8 (format v1 and loader done, ADR-0027), #22 (workbench pack, terminal part done), #21, #31 |
| M6 Struggle + persona | todo | #9, #23, #24 |
| M7 MVP hardening | todo | #25, #26 |
| v0.15 Do-it / v0.2 KWin + voice | todo | #27, #28, #29, #30 |

## Log
### 2026-11-23: #19 pointing eval harness
Done: `grounding.point` (AT-SPI tiers: high, medium, none; names normalised for case, spacing, Arabic letter variants and diacritics), `pointing_eval` (snapshot format, scoring, gates, report), `broctl eval pointing`, a 300-case synthetic corpus (6 made-up apps x EN and AR) and its generator; 18 tests including one that the committed corpus equals its generator's output. Current result: 98.0% pointed-correct, 0.0% confidently wrong, medium precision 90.5%; all 6 misses are twins (the same name twice, nothing tells them apart) or a close sibling, and were shown as medium.
Not done: **no recorded snapshots from real apps** (GIMP, Inkscape, LibreOffice, GNOME Settings, Firefox/workbench, Ptyxis), so the gate says nothing yet about real accuracy; the synthetic cases are ones we imagined and mostly easy by design; tiers low (vision) and OCR do not exist; the loop does not use `grounding.point` yet (it still takes the first `find` hit); the ADR-0004 sanity checks (rect inside the window) and the sibling-near-miss "disagreement" rule are not applied; no tokens, no LLM cassettes, no nightly run; ADR-0007's confidence thresholds are untuned.

### 2026-11-23: #20 policy engine and redaction
Done: `policy.py` (`effective_risk` = max of planner, pack and heuristics; whole-word EN and AR deny-list, so `Payload` is R0; `LocalPolicy` for Show-me and a switched-off Do-it; `command_risk`), pack-declared element risk and secrets (`[[element]]`, ADR-0027), `redact.py` (9 secret shapes, counts per kind, the value never kept) applied to the echoed screen text in `tone.snippet`, the ADR-0014 tables: 177 names x 2 modes and 50 injected texts, and a no-R3-without-confirmation check over every mode.
Not done: no LLM request exists, so nothing else calls `redact` (log records are already free-text-free); the deny-list is a word list and still misses synonyms and phrases ("place order"); the injection eval covers the policy and redaction only, not model behaviour or real pages and terminals; terminal commands reach `command_risk` only once #21 exists; no pack ships `[[element]]` rows yet; the 177 names and 50 texts are written by us, not an independent corpus.

### 2026-11-23: #22 workbench pack
Done: `packs/workbench` (match on `benchctl`, knowledge from AGENTS.md, four narration-only terminal tasks, 32 `fixits.toml` rows copied from ERROR-CODES.md contract 2.5); loader reads and checks `fixits.toml`; 8 new tests.
Not done: web-UI selectors and `signals.toml` (no format yet; signals need #9), `hooks.toml` and the `/api/state` hook (#31), tasks cannot point at or verify anything in a terminal until #21, no GIMP pack, no English/Arabic phrase-matching eval, Arabic text; fixits were copied by hand-run script and will drift from workbench's file; depends on PR #89.

### 2026-11-23: #8 pack format v1
Done: `ya_bro.packs` (load, validate, resolve by app id, window class, argv0 or URL), ADR-0027, `broctl pack list|check`, `packs/gnome-calculator`, 12 unit tests. Tasks are TOML, not YAML.
Not done: selectors, signals, fixits, hooks, docs retrieval, toolkit packs, auto-pack fallback, `pack new|test|doctor`, version ranges; the Brain does not read packs yet; the workbench and GIMP packs and the 30-phrasing match eval from ADR-0012 (#22).

### 2026-11-22: #86 release v0.1.0
Done: version 0.1.0 (pyproject, `__version__`, test, guide), CHANGELOG moved under 0.1.0, release PR dev to main, tag v0.1.0, GitHub release.

### 2026-11-22: #82, #84 narrated demo GIF
Done: `show-me-calculator.gif` is 8 frames, 606 x 798, 86 KB: native resolution (no upscaling), one shared 256-colour palette, a narrator caption track, title card, and the wrong key, the tease, the Why? explanation and the forgiveness. Not done: no sound or cursor; Calculator only; the Why? press is sent as the overlay's own event (the click path is covered by the e2e tests).

### 2026-11-22: #80 README, licence, user guide, artwork
Done: README rewritten; `LICENSE` (MIT) and pyproject metadata; ADR-0020 and SPEC updated for MIT only; GitHub topics and description set; `docs/guides/getting-started.md` (install, setup, load, demo, own plan, troubleshooting, privacy, undo) checked from a fresh clone (`uv sync`, `broctl --version`, `broctl doctor`); neutral diagram and avatar-free GIF; old mascot sketch removed.
Not done: the user guide's setup and load steps were not re-run from scratch on a clean machine (they touch the live session; the commands match the code); no screenshots of the setup prompts; no `broctl uninstall` (manual undo steps are documented); Apache-2.0 dropped, so no express patent grant; the licence CI gate is still #26.

### 2026-11-22: #78 documentation audit
Done: ADR-0026 (step loop), README status and logout wording, ADR-0024 commands, SPEC as-built paragraph, milestone table, CLAUDE.md repo map, config docs for `humour`.
Not done: a user guide beyond the README and DEVELOPMENT (no `docs/guides/` yet); the SPEC roadmap sections are unchanged.

### 2026-11-22: #76 tone and Why? after a mistake
Done: `tone.py` (plain at humour 0, playful from 1, three rotating mismatch lines), wired to `config.humour`; Why? after a wrong key names what is on screen versus what was needed and clears when undone; screen text echoed back is capped at 24 characters. Unit tests and the headless runs updated. Found in the live trial.
Not done: English only (no Arabic lines, ADR-0019); humour 2 and 3 are the same as 1; lines are fixed templates (the LLM brain will write more); not re-run on the live desktop.

### 2026-11-22: #74 wrong action
Done: the loop watches a step's expect element text; if it changes to something else and holds for 0.6 s the bubble says what was expected; clearing it removes the message; Next then goes on at once. `Perception.read_text`. 4 unit tests and a real-Calculator headless test (6 checks). Found in the live trial (pressed another key).
Not done: "contains" accepts a wrong key typed before the right one (57 contains 7); only text expectations can see a wrong action (button and presence checks cannot); other apps and web text unmeasured; not re-run on the live desktop.

### 2026-11-22: #72 verify steps from element text
Done: `Expect.text` (contains) read through AT-SPI's Text interface; steps advance by themselves; Next on an undone step asks once, a second Next skips; a step already done when it appears waits for Next. Found in the live trial (Next pressed without pressing the key). Unit tests (5 new) and the headless end-to-end (17 checks, the fixture label's text verifies the last step). Calculator example verifies from the display; GIF re-recorded.
Not done: checking text beyond "contains" (no equals, no numbers); text of web pages and non-GTK apps is unmeasured; not re-run on the live desktop yet.

### 2026-11-22: #69 bubble placement
Done: the bubble is placed below the target, above it when there is no room, and clamped inside the monitor with the avatar's gap; `Overlay1.GetState` reports `bubble`; headless test at four corners, bottom edge, middle and an off-screen explicit position (14 checks). Not done: not seen on the live desktop yet (the installed extension needs the new `overlay.js`); the bubble can still cover other widgets near the target (it only avoids the target itself); multi-monitor placement is checked on one monitor only; RTL is untouched.

### 2026-11-22: #68 live trial of Show-me (GNOME Calculator)
Done: ran `broctl show examples/plans/calculator.toml` on the real desktop; the maintainer followed the ring through 7 × 6 = 42 and it left when the plan ended. Two bugs found and fixed: a logging crash on the first button press, and Calculator's extents 12 px off (S9, `extents_offset`). Reference GIF recorded.
Not done: the 12 px cause is unknown and only Calculator is corrected (Text Editor and Files exposed no buttons to the probe); the bubble could hang off the screen (fixed in #69); steps in the example advanced only on Next (fixed in #72).

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
