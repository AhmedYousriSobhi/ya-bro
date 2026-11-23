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
| M4 Step loop | in progress | #5 (scripted Show-me loop done, ADR-0026; Claude brain built against a stand-in, live API untested), #19 (harness and synthetic corpus done, real recordings open), #20 (engine and redaction done, not yet wired to any LLM request) |
| M5 Packs + terminal | in progress | #8 (format v1 and loader done, ADR-0027), #22 (workbench pack, terminal part done), #21 (bash hook, spool and VTE reading done), #31 |
| M6 Struggle + persona | in progress | #9 (core detector, shell, idle and AT-SPI sources done; the bubble and some signals open), #23 (persona done; nothing generates lines and the offer bubble is not built yet), #24 (replay eval done: 62 scenarios, passes the gates) |
| M7 MVP hardening | in progress | #25 (consent screen, sent ledger, forget, panic, state dots done; wiring to a real request waits for #5), #26 (licence gate done) |
| v0.15 Do-it / v0.2 KWin + voice | todo | #27, #28, #29, #30 |

## Log
### 2026-11-23: #5 Claude brain
Done: `ya_bro.brain` (`ClaudeBrain`, `FallbackBrain`, key loading, observation framing, plan validation), `broctl ask`, `[brain]` config, the consent gate and sent ledger now used by a real request path, 31 unit tests over a local HTTP stand-in, and a real-Calculator test in the isolated shell (an empty observation made it fail before I added the focus click).
Decided: plain `urllib` instead of the `anthropic` SDK (ADR-0008 named the SDK): no new dependency or licence entry, and the whole wire format is visible in one file. Trade-off: no streaming and no SDK-side retries.
Then added: plan preview with Next/Stop, re-planning when a control stays missing (`revise`, capped at 2, validated like a plan), token and cache-hit totals after a run, and the persona moments for both. A separate "why?" model route was not built: the plan's own `why` field already answers Why?, and a mismatch is explained by the persona.
Not done: **never run against the live API** (no key here), so the request shape, strict-tool schema, `tool_choice: auto` behaviour on the 5.5 models and cache hits are unverified; run `uv run pytest -m live` with a key. No streaming (first words in the bubble), re-planning only for a missing control (not for a wrong screen state), no struggle-offer wording (no offer bubble), no screenshots, no libsecret key storage, `expect` predicates only role/name/text, the cost and latency budgets and the ten-task eval are unmeasured (the usage line is the start), the preview shows only the first step, and the new Arabic lines are drafts.

### 2026-11-23: #25 consent UX and kill switch
Done: `ya_bro.privacy` (first-run consent screen in `broctl setup`, `consent.toml`, `may_send` gate; content-free sent ledger; `forget` with preview and `--everything`; 7-day log pruning; `panic` that SIGKILLs Bro's long-running processes), `broctl consent|sent|forget|panic`, state dots in the overlay (`indicators`, `SetIndicators`, `GetState`), `tests/conftest.py` isolating XDG dirs, 21 unit tests (panic on real processes including a SIGSTOPped one) and a real-frame test in the isolated shell (mutating the stylesheet makes it fail).
Found: a `broctl struggle status` run by someone else matched a naive "broctl struggle" panic pattern; only the verbs that keep running are matched now.
Not done: nothing calls `may_send` or `record_sent` yet (no LLM request exists, #5); no "listening", "sending" or "acting" source yet (only "watching" is shown); the screen is terminal text, not a GUI; panic cannot revoke a portal session or close a mic because neither exists yet; the stop key under a SIGSTOPped core is covered by the extension's dead-man test only; `prune_logs` is not scheduled; no per-app screenshot toggle or capture-deny app list.

### 2026-11-23: #23 persona
Done: `ya_bro.persona` (14 moments, 79 EN and 79 AR lines, humour ceilings, sensitive moments, frustration drop, less chatty, bro once per task, recency, bidi isolates, language following, the vet filter for generated lines, a tone guide, `lint`), `Tone` now a thin face over it, the step loop's risky-step line and the humour-gated teasing face, config `language` and `less_chatty`, `dir = rtl` to the overlay, `broctl persona say|list|lint|style`, 46 unit tests, and a real-frame test in the isolated shell (Arabic renders as real text; the RTL bubble mirrors its buttons).
Found: the banned-topic filter missed Arabic words with the article (`الموت`); a test caught it. Arabic text direction inside a label follows its content, not the widget, so only the button strip mirrors with `dir`.
Not done: the rubric eval and dogfood rule (nothing is generated yet), the humour slider and less-chatty toggle UIs, native review of the Arabic (drafts), 10 to 30 variants per moment (2 to 9 now), code-switching, MSA for TTS, the struggle offer bubble that would use the offer lines, language from the user's request (no request input yet).

### 2026-11-23: #96 the bro's look, README and demo GIF
Done: identity study by an Opus agent (5 candidates, scored, ranked; the maintainer rejected Yaya and Fenn, artwork removed), Brim as the provisional look, six SVG moods drawn by the extension (a real-frame pixel test: all six drawn, all different, mood reported, unknown mood falls back, avatar=false hides it), `mood` in `ShowStep` and `Overlay.show_step`, moods in the step loop, a happy finish, README restructured, demo GIF re-recorded from the real overlay at 2× with a moving camera (centred wide shots, zooms onto the bubble, popping title and end cards; 90 frames, 560 x 640, 1.3 MB, about 29 s).
Found: my own stylesheet edit emptied `extension/stylesheet.css` (opened for writing before reading); the first re-recorded GIF showed an unstyled bubble and no ring, which is how I noticed; fixed and the GIF re-recorded.
Not done: the maintainer has not chosen the look (Pip, Orbit and Brim remain); gaze rotation, RTL mirroring, cross-fade and hop; no teasing at humour 0 is not enforced; `quiet` is not wired to the struggle detector; the Arabic lines in the design note need review; the SVGs were rendered with cairosvg and in the real Shell, not in librsvg or on GitHub's dark theme; the bro is 48 px, so only the zoomed shots show it large; the GIF is 29 s long (the story needs the holds to be readable); the first re-record had an unstyled bubble and a left-heavy crop, which the maintainer spotted.

### 2026-11-23: #26 licence gate
Done: `scripts/check_licences.py` (project, packs, the uv.lock closure with extras and dev tools, forbidden names, installed-metadata cross-check, copyleft imports under `src/`), the policy `docs/licences.toml`, `docs/LICENCES.md` (table checked for drift), a `licence-gate` job in the CI draft, a step in `scripts/check.sh`, pack `license` field, 34 tests that break a small project tree every way the gate guards against. The real project passes (11 packages, none at runtime). A test caught that free-text licence names ("GNU General Public License v3") were not recognised; fixed.
Not done: model register (no model yet), SPDX headers, DCO enforcement, CODE_OF_CONDUCT, SECURITY and CONTRIBUTING files, checking the built wheel, system packages; CI is not active so the job has never run.

### 2026-11-23: #24 struggle replay eval
Done: `struggle_eval` (second-by-second replay on a fake clock, 8 s bubble fade, answers, idle spans; precision, recall, time to offer, false offers per hour of calm, back-off conformance, by kind and source), `broctl eval struggle [-v] [--sensitivity] [--sweep]`, 62 scenarios (54 scripted, 8 recorded from a real bash with the hook), and 32 tests that include breaking the back-off or the threshold and seeing the eval fail. Default sensitivity: precision 97%, recall 74%, median time to offer 20 s (p90 57 s), 0.31 false offers per hour, back-off 7/7; sweep: sensitivity 1 recall 6%, 3 and 4 recall 91% at 0.62 false offers per hour.
Found: a first version of the hourly-cap scenario answered after the bubble had faded (so the eval counted a soft "no") and the mutation test caught that it proved nothing; fixed. Misses are single weak signals (dialog bounce, menu thrash, focus ping-pong, undo, an idle pause); the one false offer is three quick failures that then succeed.
Not done: **the labels and 54 of the 62 scenarios are ours, so this measures consistency with our own idea of "stuck", not real people**; the ADR's 40 scenarios from two people recording real work; AT-SPI-driven recordings (menus, dialogs: no source emits them yet); no tuning (defaults kept, the sweep is for the maintainer); recorded scenarios are real bash but seconds long; offers per hour is measured on calm time only; no learned gate.

### 2026-11-23: #9 struggle detector
Done: `struggle.py` (observations without content, nine signals, decaying score, context gate, breakpoints, the full back-off policy, opt-in per app, sensitivity, private state file), `struggle_host.py` (shell hook plus idle into the detector), `platform/gnome_idle.py`, pack `signals.toml` (bounded; workbench ships one), `broctl struggle ...`, 50 tests. Real runs: real bash with the hook, the real spool and host (3 failures give one offer with a plain reason; a success or an un-allowed command gives none; a "no" keeps it quiet); real Mutter idle in the isolated shell (0.5 s after a key, 4.5 s after 4 s, a real pause after a failure is one idle signal with one offer). The real run found a re-arm bug, fixed with a regression test.
Not done: AT-SPI sources (menu thrash, dialog bounce, error dialogs, undo, help, typing; S5b open), focus ping-pong from the bridge, fullscreen and do-not-disturb inputs, the offer bubble and its persona line (#23), "why did you offer?" in the UI, the learned gate, the replay eval set (#24, so precision and recall are unmeasured), persisting the quiet timers and the hour and day caps, `broctl struggle watch` prints offers but never gets an answer. Thresholds, weights and cooldowns are the ADR's starting values, untuned.

### 2026-11-23: #9 AT-SPI struggle sources
Done: `UiEventSource` interface and fake, `ui_events` (pure translator from raw accessibility events to menu, dialog, alert, undo and typing kinds, unit-tested on sequences captured from real GTK4), `platform/gnome_atspi_events.py` (scoped to allowed and enabled apps, salted-hash keys, never reads typed text), `StruggleHost(ui=...)`, `broctl struggle watch` with the AT-SPI source and pack `signals.toml` tuning (`tune_from_packs`; before this the CLI never applied packs). Real test in the isolated shell: GTK4 fixture with real pointer and keys, GTK3 error dialogs, a not-enabled app and a not-allowed app both unseen, and a mutation run that fails. Six recorded scenarios added; eval 68 scenarios, precision 97%, recall 70% (was 74%: the new real weak-signal struggles cannot reach the threshold alone), gates pass.
Found: no `window:create` or `destroy` on GTK4; GTK4 menus report `expanded` on the MenuButton and the item-click event arrives only the first time per item; Cancel and OK close a dialog identically; GTK4 and Adwaita error dialogs are plain `dialog`; undo is a text delete; libatspi needs the default GLib context pumped and its first call in a thread.
Not done: help-seeking and focus ping-pong sources; menu activation is not observable after an item's first use (repeated use of one menu can look like thrash); Cancel versus OK; GTK4/Adwaita error dialogs are not told from other dialogs; context and keyboard menus; GTK3 and Qt menus unmeasured; undo is a multi-character delete (cut counts too); not measured on KWin; the labels of the recorded scenarios are what the scripts meant, from one person's script, not real use; the offer bubble and its answers (#23) are other work. The listener receives every app's events and drops them by process before reading any.

### 2026-11-23: #21 shell hook and terminal reading (bash)
Done: `shell/ya-bro.bash` (name, exit code, duration, tty per allowed command; allowlist in the hook; silent without core), `shell_spool` (private files, strict validation, partial lines, truncation), `terminal` (VTE text over AT-SPI, redacted; pack fix-it for `CODE: message | fix: COMMAND`; rc-file block), `broctl hook ...` and `broctl shell watch`, 40 tests. Real runs: interactive bash on a pty (100 commands exact, under 5 ms per command, silent without core, existing DEBUG trap and PROMPT_COMMAND kept) and a real VTE terminal in the isolated shell (spool, AT-SPI text, redaction, fix-it, scope).
Findings: `trap -p DEBUG` is empty inside a sourced file or function, so the hook reads it at the first prompt; Ptyxis cannot spawn its shell in the isolated session (no systemd user bus), so the real test uses a bare VTE window; the first key after a window opens is eaten (again).
Not done: zsh and fish, OSC 133 and OSC 7, typing a suggestion into the terminal (R2), kitty, WezTerm and Konsole adapters, generic fix-it rules, the S9 end to end with the real `benchctl`, inotify (polls at 0.2 s), Ptyxis itself and GNOME Terminal not exercised, `broctl hook install` was only run against a temporary HOME.

### 2026-11-23: #19 pointing eval harness
Done: `grounding.point` (high, medium, none; names normalised for case, spacing, Arabic letter variants and diacritics; ring centre must be inside the focused window), used by the step loop (medium gets a hedged bubble), `pointing_eval`, `broctl eval pointing`, 300 synthetic cases, and **real recordings** from GNOME Calculator (36 elements), Files (5) and Settings (22) with 219 cases. Real checks, isolated headless shell (`tests/test_gnome_pointing.py`, repeated runs): Calculator 10/10 digit keys pointed High and a click in the ring types that digit; 7 × 6 = 42 by pointing at each key; Settings 3/3 and Files 3/3 pointed rows open their page when clicked. Eval over everything: 519 cases, 98.8% pointed-correct, 0.0% confidently wrong, medium precision 94.2%; the 6 misses are all synthetic (twins, one close sibling).
Findings: GNOME Text Editor exposes no buttons in its tree (0 usable elements), so nothing can be pointed at by name there; Files' sidebar rows are `list item`, Settings' are `button`; the first press after a window opens is spent on activating it, so a harness must click the title bar first; GTK4 rows need the pointer over them before the press.
Not done: the recorded cases are built from each element's own name (exact, case, drop-a-letter, wrong role, missing), so they are circular; the click checks above are what really validate the rects, and only 4 apps were tried, English only, one window size, scale 1; GIMP, Inkscape, LibreOffice, Firefox/workbench and Ptyxis not recorded (not installed or not accessible); vision and OCR tiers do not exist; no tokens, LLM cassettes or nightly run (no LLM request exists); the 0.3 margin and 0.6 floor are untuned; a duplicate name still cannot be told apart.

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
