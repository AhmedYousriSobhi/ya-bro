# Changelog

All notable changes are documented here. Format: [Keep a Changelog](https://keepachangelog.com/), versioning: [SemVer](https://semver.org/).

## [Unreleased]
### Added
- Spike S1 (#15, go/no-go still open): GNOME Shell extension prototype in `extension/` (`Bridge1`, `Overlay1`, peer checks, dead-man switch, stop key, Bézier pointer flight), isolated headless-shell harness `scripts/dev/headless-shell.sh` (private bus, display, runtime dir, Xwayland, camera-masked WirePlumber), contract test (`pytest -m gnome`) and a measurement suite (`pytest -m gnome_measure`) with raw JSON and findings in `docs/research/spikes/`. Measured per-toolkit window origins (GTK4/libadwaita frame, GTK3 buffer). ADR-0023 corrected (`GetMonitors` signature, `GetState`, `layout_mode`); stop key needs a stage `captured-event` fallback because Mutter dropped the binding in about half of test sessions (fixed: 10/10 headless, 5/5 nested). `YB_DEVKIT=1` runs the harness in a nested `mutter-devkit` window on the real desktop.
- Project skeleton (#16): `src/` layout, uv/ruff/pytest config, 12 provisional interface Protocols with in-memory fakes, IPC name helper, XDG `dirs`, `ya-bro --version`, GTK4 AT-SPI fixture test, `scripts/check.sh`, CI workflow drafted at `docs/ci/ci.yml` (not active: the maintainer's token lacks `workflow` scope, so it must be copied to `.github/workflows/` by hand; never run), `docs/PROGRESS.md`, `docs/DEVELOPMENT.md`.
- Concept sketch (`docs/assets/ya-bro-concept.png` and SVG source).
- Architecture ADR set (0002–0023), ADR index with ranked risks and MVP build plan, and research docs on AI tools, non-AI tools and the Linux platform.
- Platform re-plan: GNOME 50 Wayland is the reference platform (maintainer decision), KWin Wayland moves to v0.2, X11 becomes CI-only. ADR-0023 designs the GNOME Shell extension bridge + overlay, and ADR-0022 re-orders the spikes so that extension is S1.
- ADR-0001: Python 3.12 + GTK4 chosen as implementation stack.
- README title no longer has an emoji.
- Spec: proactive "you stuck?" mode, global core + app packs (workbench first), monitoring privacy rules.
- Initial repo scaffold: `CLAUDE.md`, `SPEC.md`, issue/PR templates, prior-art survey.
