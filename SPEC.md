# Ya-Bro — Product Spec

Status: **draft v0.1** · Platform: **Linux** (X11 + Wayland) · Updated whenever behavior changes (see CLAUDE.md workflow)

## 1. Problem
Builders who use many apps often can't learn them from written guides or video tutorials: the docs are out of date, assume context, or don't match what's on screen. They need a companion that learns the app, then walks alongside them in the real UI.

## 2. Vision
A Navi-style sidekick that **hovers on screen**. Ask in voice or text: *"Ya bro, how do I export this as PNG in GIMP?"* The bro shows the **next single step**, pointing at the real control, explaining briefly, and either waits for you to do it or does it itself while you watch. Then the next step. Like pair-programming, but for using apps.

## 3. Users
Primary: the maintainer — an app builder who struggles with guides/tutorials and learns best by doing with a guide present. Secondary: anyone onboarding to unfamiliar software on Linux.

## 4. Core experience
1. **Summon**: hotkey or voice wake word; a small floating avatar appears (always-on-top, click-through except the avatar and its bubble).
2. **Ask**: voice or text. The bro confirms the goal and the target app.
3. **Learn the app**: the bro inspects the running app (UI tree, screenshots, `--help`/docs, MCP servers, skills) to build a plan. No per-app hardcoding.
4. **Guide step by step**: for each step the bro
   - highlights/points at the target element on the live screen,
   - says one short sentence about what and why,
   - waits (**Show me** mode) or acts (**Do it** mode),
   - verifies the screen changed as expected, then moves on.
5. **Control**: "next", "repeat", "why?", "do it for me", "let me try", "stop", "go back". Stop is instant.
6. **Recover**: if the UI doesn't match expectations (dialog, different version), re-perceive and re-plan out loud instead of failing silently.

### Modes
| Mode | Bro acts? | User acts? | Use when |
|---|---|---|---|
| Show me | no (points only) | yes | learning |
| Do it | yes, paced and narrated | watches | just get it done / demo |
| Auto-follow | detects user's action | yes | bro tracks progress and advances automatically |

## 5. Scope
**MVP (v0.1):** target **KDE Plasma and X11 first** (see PRIOR_ART). Text chat + floating overlay; point-and-highlight; **Show-me mode with automatic step verification** (UI tree diff / screenshot) for GUI apps exposing AT-SPI; one LLM backend (Claude). Proven on 3–5 accessible apps (GIMP, Inkscape, LibreOffice, system settings).
**v0.15:** Do-it mode (X11 XTest first, then portal + libei on Wayland).
**v0.2:** GNOME overlay strategy; voice in/out (local-first STT/TTS), hotkey summon, multi-monitor.
**v0.3:** app-knowledge sources: docs ingestion, MCP/skill integration, per-app memory of learned workflows.
**v1.0:** stable on GNOME + KDE, X11 + Wayland; plugin API.
**Later:** macOS, Windows (hence the interface boundaries below).
**Non-goals:** replacing Claude computer use / general automation; unattended agents; cloud-hosted service; mobile.

## 6. Architecture
```
 user ──voice/text──► [Voice] ─► [Brain: planner/LLM] ◄── app knowledge (UI tree, docs, MCP, skills)
                                      │ next step
          ┌───────────────────────────┼───────────────────────────┐
     [Perception]                 [Overlay]                   [Actuator]
   AT-SPI, screenshot           pointer, highlight,          click/type/scroll
   (portal), vision             speech bubble                (only in Do-it mode)
```
All five components sit behind interfaces so they can be swapped per OS/display server.

| Component | Linux plan (proposed, validate via ADRs) |
|---|---|
| Perception | AT-SPI (`pyatspi`/`libatspi`) primary; screenshot via xdg-desktop-portal + vision LLM fallback |
| Overlay | X11: transparent override-redirect window. Wayland: `wlr-layer-shell` (wlroots/KDE); GNOME needs a Shell extension or fallback window — **top technical risk** |
| Actuator | X11: XTest/`xdotool`. Wayland: RemoteDesktop portal / libei; `ydotool` as last resort |
| Voice | STT: whisper.cpp (local) with cloud option; TTS: Piper (local) with cloud option |
| Brain | Claude API (tool use); step loop with explicit state; model configurable |
| Language/UI | Python 3.12 + GTK4 (PyGObject), `uv`, `pytest`, `ruff` — decided in [ADR-0001](docs/adr/0001-language-and-toolkit.md) |

### Step loop
`perceive → plan (ordered goal steps, re-planned each iteration) → present step → [act|wait] → verify → next`. Each step has: intent, target element reference, narration text, expected-result check, and risk level.

## 7. Safety and trust
- Visible, interruptible actions; global stop hotkey.
- Never enters passwords/secrets; confirmation required for destructive or outward-facing controls (send, buy, delete, publish).
- Screen/app text is untrusted data; it cannot change the bro's instructions.
- Screenshots/UI trees go only to the configured LLM; local-only mode is a roadmap goal. No telemetry by default.

## 8. Success criteria (MVP)
- Completes a 5–10 step task in 3 target apps (e.g. GIMP, LibreOffice Writer, a browser) in Show-me mode with ≥80% steps correctly pointed.
- Step latency (step done → next highlight) under 3 s with cloud LLM.
- User can interrupt within 500 ms of "stop".

## 9. Open questions
1. ~~Implementation language/toolkit~~ — resolved by ADR-0001.
2. GNOME-on-Wayland overlay strategy (extension vs. fallback).
3. How well AT-SPI covers Electron, GTK4, Qt, and web content — measure in a spike.
4. Wake-word vs hotkey-only for v0.2.
5. License (proposal: MIT or Apache-2.0).

## 10. Delivery process
Feature = GitHub issue → branch → PR to `dev` (docs updated first) → periodic release PR `dev` → `main` with tag and changelog. Details in [CLAUDE.md](CLAUDE.md). Prior art (the concept exists on macOS/Windows; Linux-native + paced teach/do hybrid does not) and differentiation: [docs/PRIOR_ART.md](docs/PRIOR_ART.md).
