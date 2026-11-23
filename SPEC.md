# Ya-Bro — Product Spec

Status: **draft v0.1** · Platform: **Linux**: GNOME 50 Wayland reference, KWin Wayland second, X11 CI-only (see [ADR-0002](docs/adr/0002-platform-targets-and-session-strategy.md), maintainer-decided) · Updated whenever behavior changes (see CLAUDE.md workflow)

## 1. Problem
Builders who use many apps often can't learn them from written guides or video tutorials: the docs are out of date, assume context, or don't match what's on screen. They need a companion that learns the app, then walks alongside them in the real UI.

## 2. Vision
A Navi-style sidekick that **hovers on screen**. Ask in voice or text: *"Ya bro, how do I export this as PNG in GIMP?"* The bro shows the **next single step**, pointing at the real control, explaining briefly, and either waits for you to do it or does it itself while you watch. Then the next step. Like pair-programming, but for using apps.

See [how it works](docs/assets/how-it-works.svg) for the loop and the [Show-me demo](docs/assets/show-me-calculator.gif) for what runs today. The bro's look is **provisional**: a round teal head with a cap ("Brim") from the [identity study](docs/design/BRO_IDENTITY.md), drawn by the extension in six moods ([ADR-0028](docs/adr/0028-the-bros-look.md)); the maintainer makes the final choice.

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
   *As built (ADR-0026, scripted plans, GNOME):* the bro reads the real element's text through AT-SPI, so a step advances by itself once the screen shows the result; Next on a step that is not done asks first; a wrong action is named and **Why?** explains the mistake; the tone is playful unless `humour = 0`.
5. **Control**: "next", "repeat", "why?", "do it for me", "let me try", "stop", "go back". Stop is instant.
6. **Recover**: if the UI doesn't match expectations (dialog, different version), re-perceive and re-plan out loud instead of failing silently.

### Proactive mode ("Ya bro, you stuck?")
The headline feature. The bro watches for **struggle patterns** and offers help unprompted, with personality: opening and closing the same menu repeatedly, long idle with the app focused, repeated undo, repeated error dialogs, a shell command failing several times. It asks once ("you stuck, bro?"). If the user says no it may say "I don't think so, but I'm here", then **backs off**: after repeated refusals it stays quiet for a long time and learns which patterns were false alarms. The user can disable it globally or per app at any time.

### Modes
| Mode | Bro acts? | User acts? | Use when |
|---|---|---|---|
| Show me | no (points only) | yes | learning |
| Do it | yes, paced and narrated | watches | just get it done / demo |
| Auto-follow | detects user's action | yes | bro tracks progress and advances automatically |

## 5. Scope
**MVP (v0.1):** target **GNOME 50 on Wayland** (Ubuntu 26.04 LTS), through a Ya-Bro GNOME Shell extension that supplies window geometry and draws the overlay ([ADR-0002](docs/adr/0002-platform-targets-and-session-strategy.md), [ADR-0023](docs/adr/0023-gnome-shell-extension-bridge.md)). Without the extension, docked mode (no live ring). X11 is CI-only: GNOME 50 and Plasma 6.8 have no X11 session. Text chat + floating overlay; point-and-highlight; **Show-me mode with automatic step verification** (UI tree diff / screenshot) for GUI apps exposing AT-SPI; one LLM backend (Claude). Proven on 3–5 accessible apps (GIMP, Inkscape, LibreOffice, system settings) plus the workbench pack (terminal + web UI). Proactive struggle detection with back-off ships in the MVP, behind a toggle.

**Scope (default-deny):** Ya-Bro sees no window until the user allows it. The user picks an app (`broctl setup`, `broctl apps allow`) or a *target* such as a web tool by origin (`broctl targets allow`, [ADR-0025](docs/adr/0025-pack-scoped-targets.md)); the extension reports only those windows, and a browser tab only while it proves its origin by a title token. A CLI-command target is seen only through the bash shell hook, which records an allowed command's name, exit code and duration when it finishes and nothing else ([ADR-0021](docs/adr/0021-terminal-and-browser-integration.md), `broctl hook install`); zsh and fish are not built yet.
**v0.15:** Do-it mode (accessibility actions first, then input injection via the RemoteDesktop portal + libei, with consent).
**v0.2:** KWin Wayland (Plasma ≥ 6.6) via a KWin script bridge and a layer-shell overlay; voice in/out (local only where the Arabic/English bake-off passes), hotkey summon. Multi-monitor and mixed scale are already in the MVP on GNOME (ADR-0023). Opt-in wake word moves to v0.3.
**v0.3:** more packs, docs ingestion, MCP/skill integration, per-app memory of learned workflows.
**v1.0:** stable on GNOME and KDE Wayland; plugin API.
**Later:** macOS, Windows (hence the interface boundaries below).
**Non-goals:** a workbench-only tool; replacing Claude computer use / general automation; unattended agents; cloud-hosted service; mobile.

## 6. Architecture
Full detail: [docs/adr/](docs/adr/README.md) (ADR-0002 to 0023). Additional components introduced there: CompositorBridge, Capture, IdleSource, Hotkeys, ShellHook, SecretStore, Policy, run as a core daemon plus separate overlay, perceiver, actuator and voice processes over D-Bus ([ADR-0003](docs/adr/0003-process-model-and-architecture.md)). On GNOME the CompositorBridge and the always-on-top drawing are one Shell extension ([ADR-0023](docs/adr/0023-gnome-shell-extension-bridge.md)).
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
| Perception | AT-SPI first, then OCR, then vision ([ADR-0005](docs/adr/0005-perception-strategy.md)). AT-SPI screen coordinates are unusable on Wayland, so the window origin comes from the compositor: the GNOME Shell extension first, a KWin script in v0.2 ([ADR-0004](docs/adr/0004-window-geometry-and-coordinate-pipeline.md), [ADR-0023](docs/adr/0023-gnome-shell-extension-bridge.md)) |
| Overlay | GNOME: drawn inside the Ya-Bro Shell extension (St actors above all windows, click-through except the avatar and bubble). KWin/wlroots (v0.2): GTK4 + `wlr-layer-shell`. Docked fallback elsewhere ([ADR-0006](docs/adr/0006-overlay-rendering.md), [ADR-0023](docs/adr/0023-gnome-shell-extension-bridge.md)). **Top technical risk** (spike S1). |
| Actuator | AT-SPI semantic actions first; then the RemoteDesktop portal + libei (GNOME, with consent), KWin fake-input in v0.2. The extension never injects input. `ydotool` is not shipped ([ADR-0009](docs/adr/0009-actuation-do-it-mode.md)) |
| Voice | Push-to-talk default (GlobalShortcuts portal on GNOME; the stop key is bound in the extension); local Whisper for English; Arabic engines decided by a bake-off. Piper is GPL, so it runs out-of-process ([ADR-0011](docs/adr/0011-voice-pipeline-arabic-english.md), [ADR-0020](docs/adr/0020-licensing-governance-and-release.md)) |
| Brain | Claude API (strict tool-use step plans); pack fast path skips the LLM for known tasks ([ADR-0008](docs/adr/0008-brain-llm-strategy-and-step-plan.md)) |
| Language/UI | Python 3.12 + GTK4 (PyGObject), `uv`, `pytest`, `ruff` — decided in [ADR-0001](docs/adr/0001-language-and-toolkit.md) |

### Global core + app packs
Ya-Bro is **one global tool**. The core (overlay, voice/text, personality, struggle detection, step loop) knows nothing about any specific app. App-specific help lives in **packs**: a folder per app holding its docs, tutorials, common tasks, CLI help and pointers to an `AGENTS.md`, `llms.txt` or MCP server. Apps without a pack fall back to generic screen/AT-SPI guessing (lower accuracy).
- **Rule:** no app-specific code in the core; it goes in that app's pack.
- **First pack: [workbench](https://github.com/AhmedYousriSobhi/workbench)** (CLI `benchctl` + web UI; ships `AGENTS.md`, `llms.txt`, an MCP server, a manual and 40+ scenarios). This makes the first demo terminal + browser, not only GTK apps.
- Terminal apps get struggle signals from shell history/exit codes; web UIs we own can report their state directly, since AT-SPI is weak inside web pages.

### Step loop
`perceive → plan (ordered goal steps, re-planned each iteration) → present step → [act|wait] → verify → next`. Each step has: intent, target element reference, narration text, expected-result check, and risk level.

## 7. Safety and trust
- Visible, interruptible actions; global stop hotkey. Do-it actions are gated by risk tiers R0–R3; **R3 is always the user's own click** ([ADR-0009](docs/adr/0009-actuation-do-it-mode.md), [ADR-0014](docs/adr/0014-privacy-security-trust-model.md)).
- Never enters passwords/secrets; confirmation required for destructive or outward-facing controls (send, buy, delete, publish).
- Screen/app text is untrusted data; it cannot change the bro's instructions.
- **Monitoring is opt-in per app, visible, and local.** Struggle detection uses event types and counts (e.g. menu opened/closed, exit codes), never typed text or screen content. Global input hooks are off by default everywhere; text is read only after the user accepts help ([ADR-0010](docs/adr/0010-struggle-detection-and-back-off.md)).
- Screenshots/UI trees go only to the configured LLM; local-only mode is a roadmap goal. No telemetry by default.

## 8. Success criteria (MVP)
- Completes a 5–10 step task in 3 target apps (e.g. GIMP, LibreOffice Writer, a browser) in Show-me mode with ≥80% steps correctly pointed.
- Step latency (step done → next highlight) under 3 s with cloud LLM.
- User can interrupt within 500 ms of "stop".
- Confidently wrong pointing ≤ 2% ([ADR-0007](docs/adr/0007-grounding-and-pointing-accuracy.md)).

## 9. Open questions
1. ~~Implementation language/toolkit~~ — resolved by ADR-0001.
2. ~~GNOME-on-Wayland overlay strategy~~ — resolved by ADR-0006 and ADR-0023 (Shell extension, now in the MVP).
3. How well AT-SPI covers Electron, GTK4, Qt, and web content — spike S2 ([ADR-0022](docs/adr/0022-mvp-build-plan.md)).
4. ~~Wake word vs hotkey~~ — resolved by ADR-0011 (push-to-talk default, wake word opt-in later).
5. ~~License~~ — resolved by ADR-0020 (the maintainer chose MIT only, 2026-11-22).
6. ~~Which desktop does the maintainer dogfood on?~~ — resolved 2026-11-20: the maintainer chose GNOME Wayland first; KWin is the v0.2 port (ADR-0002).

## 10. Delivery process
Feature = GitHub issue → branch → PR to `dev` (docs updated first) → periodic release PR `dev` → `main` with tag and changelog. Details in [CLAUDE.md](CLAUDE.md). Prior art (the concept exists on macOS/Windows; Linux-native + paced teach/do hybrid does not) and differentiation: [docs/PRIOR_ART.md](docs/PRIOR_ART.md).
