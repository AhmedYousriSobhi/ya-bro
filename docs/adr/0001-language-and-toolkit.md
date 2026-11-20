# ADR-0001: Implementation language and toolkit

- Status: Accepted
- Date: 2026-11-20
- Issue: #1

## Context
Ya-Bro needs: AT-SPI access, a transparent click-through overlay (X11 now, Wayland layer-shell on KDE/Sway/Hyprland, GNOME later), input injection, audio I/O, and LLM calls. The MVP goal is to validate the teaching experience fast on KDE/X11; performance is not the bottleneck (LLM round-trips dominate step latency). OS-specific code must sit behind interfaces so macOS/Windows can follow.

## Options considered
| Option | For | Against |
|---|---|---|
| **Python 3.12 + GTK4 (PyGObject)** | `Atspi` via GObject introspection, `gtk4-layer-shell` has Python bindings, official Anthropic SDK, fastest iteration, whisper/piper bindings | Packaging/distribution harder; GIL irrelevant at this scale |
| Python + Qt6 (PySide6) | Trivial click-through (`WindowTransparentForInput`), native on KDE | No first-class layer-shell binding; AT-SPI still via GI anyway; heavier |
| Rust (gtk4-rs / iced) | Fast, single binary | Slower iteration, thinner AT-SPI ecosystem (`atspi` crate is fine), more boilerplate for an unvalidated UX |
| TypeScript / Electron | Web UI skills | Poor overlay control on Wayland, no good AT-SPI, heavy |

## Decision
**Python 3.12 + GTK4 (PyGObject)** for the MVP, managed with `uv`, tests with `pytest`, lint/format with `ruff`. Components stay behind the interfaces in SPEC.md section 6 (`Perception`, `Overlay`, `Actuator`, `Voice`, `Brain`), so any one can be rewritten in another language or toolkit.

## Consequences
- Positive: fastest path to validating Show-me mode; Atspi and layer-shell are directly usable.
- Negative: distribution needs work later (Flatpak/AppImage/pipx); GNOME overlay still needs a separate Shell extension (JS) regardless of this choice.
- Revisit if: overlay latency or click-through behavior in GTK4 proves unreliable on X11/KDE (then try PySide6), or if packaging becomes the main blocker (then consider porting the hot path to Rust).
