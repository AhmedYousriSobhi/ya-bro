# Changelog

All notable changes are documented here. Format: [Keep a Changelog](https://keepachangelog.com/), versioning: [SemVer](https://semver.org/).

## [Unreleased]
### Added
- Spike S8 (#47): the Shell extension can scope a window by a secret title token pushed by core (`Bridge1.SetScopeTokens`, core only, memory only; the window leaves scope when its title changes), and windows re-evaluate when `allowed-apps` changes. Verified with a stand-in window only, not a real browser. Findings in `docs/research/spikes/S8-active-tab-scope.md`.
- `broctl apps available` lists installed apps (id, name, window class) from `.desktop` files (#47). ADR-0025 (proposed): pack-scoped targets so a tool with a web UI and a CLI, like workbench, can be allowed without exposing the whole browser or every shell.
- `broctl`, a kubectl-style control CLI (`broctl <noun> <verb>`, ADR-0024, #45): `version`, `doctor`, `setup`, `apps list|allow|revoke`. It replaces the `ya-bro` management commands; `ya-bro` stays the product and agent name.
- Per-app scoping (#43): the Shell extension is default-deny. Only windows of apps in its `allowed-apps` setting are listed, tracked, announced or measured; the title and pointer calls are refused otherwise. `broctl setup` asks which one app to allow (and writes `apps/<id>.toml`), and `broctl doctor` reports the allowlist. The accessibility setting itself stays system-wide (GNOME has no per-app switch).
- `broctl doctor` (session, accessibility bus, extension state, API key presence) and consent-gated `broctl setup` (accessibility setting, Shell extension install and enable) (#17).
- Config loader (`ya_bro.config`, `config.toml` plus per-app overrides, warns on unknown keys) and content-free typed JSONL log API (`ya_bro.logs`) per ADR-0017 (#36).
- Working rules for agents and contributors in CLAUDE.md (watch background jobs, harness safety).
- Spike S1 (#15, go/no-go still open): GNOME Shell extension prototype in `extension/` (`Bridge1`, `Overlay1`, peer checks, dead-man switch, stop key, Bézier pointer flight), isolated headless-shell harness `scripts/dev/headless-shell.sh` (private bus, display, runtime dir, Xwayland, camera-masked WirePlumber), contract test (`pytest -m gnome`) and a measurement suite (`pytest -m gnome_measure`) with raw JSON and findings in `docs/research/spikes/`. Measured per-toolkit window origins (GTK4/libadwaita frame, GTK3 buffer). ADR-0023 corrected (`GetMonitors` signature, `GetState`, `layout_mode`); stop key needs a stage `captured-event` fallback because Mutter dropped the binding in about half of test sessions (fixed: 10/10 headless, 5/5 nested). `YB_DEVKIT=1` runs the harness in a nested `mutter-devkit` window on the real desktop.
- Project skeleton (#16): `src/` layout, uv/ruff/pytest config, 12 provisional interface Protocols with in-memory fakes, IPC name helper, XDG `dirs`, `ya-bro --version`, GTK4 AT-SPI fixture test, `scripts/check.sh`, CI workflow drafted at `docs/ci/ci.yml` (not active: the maintainer's token lacks `workflow` scope, so it must be copied to `.github/workflows/` by hand; never run), `docs/PROGRESS.md`, `docs/DEVELOPMENT.md`.
- Concept sketch (`docs/assets/ya-bro-concept.png` and SVG source).
- Architecture ADR set (0002–0023), ADR index with ranked risks and MVP build plan, and research docs on AI tools, non-AI tools and the Linux platform.
- Platform re-plan: GNOME 50 Wayland is the reference platform (maintainer decision), KWin Wayland moves to v0.2, X11 becomes CI-only. ADR-0023 designs the GNOME Shell extension bridge + overlay, and ADR-0022 re-orders the spikes so that extension is S1.
- ADR-0001: Python 3.12 + GTK4 chosen as implementation stack.
- README title no longer has an emoji.
- Spec: proactive "you stuck?" mode, global core + app packs (workbench first), monitoring privacy rules.
- Initial repo scaffold: `CLAUDE.md`, `SPEC.md`, issue/PR templates, prior-art survey.
