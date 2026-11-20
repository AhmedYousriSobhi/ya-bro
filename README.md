# Ya-Bro

> *"Ya bro!"* — call your companion when an app confuses you.

Ya-Bro is a Linux desktop sidekick that hovers on your screen. It notices when you're stuck ("you stuck, bro?") or you can just ask it (by voice or text) how to do something in any app, and it walks you through the **real app, one step at a time** — pointing at the exact button, explaining why, and doing the step for you whenever you'd rather just watch.

**Status:** pre-alpha, spec phase. See [SPEC.md](SPEC.md).

## Docs
- [SPEC.md](SPEC.md) — what we're building and why
- [docs/PRIOR_ART.md](docs/PRIOR_ART.md) — who else is doing this
- [docs/adr/](docs/adr/README.md) — architecture decisions, risks and MVP build plan
- [docs/research/](docs/research/) — how other AI and non-AI tools work, and Linux platform facts
- [CLAUDE.md](CLAUDE.md) — contributor/agent workflow (issues → PR to `dev` → release to `main`)
- [CHANGELOG.md](CHANGELOG.md)

## Platform
Linux only for now: GNOME on Wayland first (through a small GNOME Shell extension), KDE Plasma Wayland next. X11 is used only in CI. macOS/Windows later.
