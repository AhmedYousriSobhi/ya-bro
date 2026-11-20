# Changelog

All notable changes are documented here. Format: [Keep a Changelog](https://keepachangelog.com/), versioning: [SemVer](https://semver.org/).

## [Unreleased]
### Added
- Concept sketch (`docs/assets/ya-bro-concept.png` and SVG source).
- Architecture ADR set (0002–0023), ADR index with ranked risks and MVP build plan, and research docs on AI tools, non-AI tools and the Linux platform.
- Platform re-plan: GNOME 50 Wayland is the reference platform (maintainer decision), KWin Wayland moves to v0.2, X11 becomes CI-only. ADR-0023 designs the GNOME Shell extension bridge + overlay, and ADR-0022 re-orders the spikes so that extension is S1.
- ADR-0001: Python 3.12 + GTK4 chosen as implementation stack.
- README title no longer has an emoji.
- Spec: proactive "you stuck?" mode, global core + app packs (workbench first), monitoring privacy rules.
- Initial repo scaffold: `CLAUDE.md`, `SPEC.md`, issue/PR templates, prior-art survey.
