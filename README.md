# Ya-Bro

> *"Ya bro!"* — call your companion when an app confuses you.

Ya-Bro is a Linux desktop sidekick that hovers on your screen. It notices when you're stuck ("you stuck, bro?") or you can just ask it (by voice or text) how to do something in any app, and it walks you through the **real app, one step at a time** — pointing at the exact button, explaining why, and doing the step for you whenever you'd rather just watch.

![Ya-Bro concept sketch](docs/assets/ya-bro-concept.png)

*Concept sketch (source: `docs/assets/ya-bro-concept.svg`), not a final design.*

**Status:** pre-alpha. Project skeleton in place (interfaces, fakes, CI); no user-facing features yet. Progress: [docs/PROGRESS.md](docs/PROGRESS.md). See [SPEC.md](SPEC.md).

## Docs
- [SPEC.md](SPEC.md) — what we're building and why
- [docs/PRIOR_ART.md](docs/PRIOR_ART.md) — who else is doing this
- [docs/adr/](docs/adr/README.md) — architecture decisions, risks and MVP build plan
- [docs/research/](docs/research/) — how other AI and non-AI tools work, and Linux platform facts
- [CLAUDE.md](CLAUDE.md) — contributor/agent workflow (issues → PR to `dev` → release to `main`)
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — setup, validation script, layout
- [docs/PROGRESS.md](docs/PROGRESS.md) — milestone and issue status
- [CHANGELOG.md](CHANGELOG.md)

## Doctor and setup
`ya-bro doctor` reports what works and how to fix what does not (its output is safe to paste in a bug report). `ya-bro setup` asks before each persistent change (GNOME accessibility setting, Shell extension install) and needs one logout/login afterwards. The doctor checks only whether the `ANTHROPIC_API_KEY` environment variable is set, never its value; `.env` loading is not implemented yet.

## Platform
Linux only for now: GNOME on Wayland first (through a small GNOME Shell extension), KDE Plasma Wayland next. X11 is used only in CI. macOS/Windows later.
