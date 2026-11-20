# Architecture Decision Records

One file per decision, numbered and never renumbered. A superseded ADR stays in place with its status changed to `Superseded by ADR-XXXX`.

**Status values:**
- **Proposed:** written, not yet validated.
- **Accepted:** the spike or eval passed, or the maintainer approved it.
- **Rejected**
- **Superseded**

**Format:** Context, Decision drivers, Options considered, Decision, Consequences, Validation plan, Revisit if, Sources (see [ADR-0002](0002-platform-targets-and-session-strategy.md) for an example).

The set 0002–0022 was produced for issue #13 on 2026-11-20. It rests on the research landscape:
- [docs/research/ai-tools.md](../research/ai-tools.md): how AI guiders, doers, recorders and proactive tools work inside, plus grounding benchmarks.
- [docs/research/non-ai-tools.md](../research/non-ai-tools.md): screen readers, input tools, tour libraries, DAPs, annotators, desktop pets, voice engines, terminal tooling.
- [docs/research/linux-platform.md](../research/linux-platform.md): the hard X11/Wayland/compositor/portal/AT-SPI facts, including what is broken.
- [docs/research/factsheet.md](../research/factsheet.md): licences, HCI research on proactive help, Arabic voice facts, packaging facts.

## Index

| ADR | Title | Status | Headline decision |
|---|---|---|---|
| [0001](0001-language-and-toolkit.md) | Language and toolkit | Accepted | Python 3.12 + GTK4 (PyGObject), uv, pytest, ruff |
| [0002](0002-platform-targets-and-session-strategy.md) | Platform targets and session strategy | Proposed | **KWin Wayland (Plasma ≥ 6.6) is the reference platform. X11 is demoted to secondary, CI and LTS. GNOME comes via a Shell extension in v0.2. The maintainer's dogfooding setup is an open question.** |
| [0003](0003-process-model-and-architecture.md) | Process model | Proposed | Core daemon (asyncio on the GLib loop) + GTK overlay process + AT-SPI perceiver + on-demand actuator + Wyoming voice services + in-compositor bridge. D-Bus control plane, bulk data via runtime files. |
| [0004](0004-window-geometry-and-coordinate-pipeline.md) | Window geometry and coordinate pipeline | Proposed | Never trust AT-SPI SCREEN coordinates. Screen rect = compositor window origin (KWin script, Shell extension, sway/hyprland IPC, EWMH) + CSD offset + AT-SPI WINDOW extents. |
| [0005](0005-perception-strategy.md) | Perception strategy | Proposed | Layered resolvers: pack hooks → AT-SPI → terminal/browser structured sources → OCR on crop → vision. DAP-style element fingerprints. Event-based step verification. |
| [0006](0006-overlay-rendering.md) | Overlay rendering | Proposed | One GTK4 overlay with layer-shell (KWin, wlroots) and X11 (Xlib hints + empty input region) backends. GNOME draws in its Shell extension. Docked fallback everywhere else. |
| [0007](0007-grounding-and-pointing-accuracy.md) | Grounding and pointing | Proposed | The LLM selects among candidates and never emits pixels when candidates exist. High, Medium and Low confidence tiers change what is drawn. Do-it acts only on High. |
| [0008](0008-brain-llm-strategy-and-step-plan.md) | Brain / LLM strategy | Proposed | Claude Opus 5.5 on all routes at tuned effort (one cache namespace). Strict-tool step plans with predicates. A pack fast path skips the LLM. Prompt-cache layout. Struggle gating stays local. |
| [0009](0009-actuation-do-it-mode.md) | Actuation (Do-it) | Proposed | AT-SPI semantic actions first, then XTest / fake-input / portal + libei / wlr virtual input. Ghost cursor, paced narration, R0–R3 risk tiers. R3 is always the user's own click. |
| [0010](0010-struggle-detection-and-back-off.md) | Struggle detection and back-off | Proposed | Content-free, Wayland-observable signals feed a decaying heuristic score, offered at breakpoints. Lumière-style back-off, rate caps and a sensitivity slider. A learned gate comes later from local labels. |
| [0011](0011-voice-pipeline-arabic-english.md) | Voice pipeline | Proposed (STT/TTS engine pending S8) | Push-to-talk by default, self-trained wake word opt-in. Silero VAD, Wyoming services, local Whisper for English. Arabic STT/TTS is decided by a bake-off, with Azure ar-EG as the only verified Egyptian voice. |
| [0012](0012-app-knowledge-packs.md) | App knowledge packs | Proposed | Data-only pack directory: task graphs, knowledge, docs, selectors, signals, fix-its, hooks. Task match first, then cached docs or BM25. Live MCP and `--help` sources. A workbench pack sketch. |
| [0013](0013-personality-tone-and-humor.md) | Personality and humour | Proposed | A core persona module: tone guide, bilingual template library for frequent moments, LLM lines under a style contract. Humour is never used in risk, error or privacy contexts. A user slider. |
| [0014](0014-privacy-security-trust-model.md) | Privacy, security and trust | Proposed | Threat model. Local `Policy` engine gates every action. Data minimisation and redaction. Per-app consent, visible state indicators, kill switch, short retention. |
| [0015](0015-packaging-and-distribution.md) | Packaging and distribution | Proposed | `uv tool` / pipx with system site-packages now, .deb later. No Flatpak, Snap or AppImage, because sandboxes block cross-app AT-SPI. |
| [0016](0016-testing-and-evaluation-strategy.md) | Testing and evaluation | Proposed | Fakes per interface. Headless AT-SPI, Xvfb and Sway sessions. Record-replay of events and LLM cassettes. Versioned eval sets with gates. Flake quarantine. |
| [0017](0017-configuration-state-and-observability.md) | Config, state, observability | Proposed | TOML config, SQLite state, content-free JSONL logs with correlation ids, opt-in time-limited content debug, local stats, `ya-bro doctor`. No telemetry. |
| [0018](0018-extensibility-and-portability.md) | Extensibility and portability | Proposed | Protocol interfaces with entry-point backends and data-only packs. Platform imports are banned from core. A macOS/Windows mapping table. |
| [0019](0019-internationalization-and-rtl.md) | i18n and RTL | Proposed | gettext for UI strings, Pango bidi with an explicit base direction, Unicode isolates for embedded names and commands, mirrored bubble, Noto Arabic fonts. |
| [0020](0020-licensing-governance-and-release.md) | Licensing, governance, release | Proposed | MIT OR Apache-2.0. GPL/AGPL only out of process and optional. Model licence register. DCO. SemVer 0.x. dev → main release gates. |
| [0021](0021-terminal-and-browser-integration.md) | Terminal and browser integration | Proposed | Shell hook writes a content-free spool, plus OSC 133. Konsole, kitty, WezTerm and VTE adapters. Fix-it rules. Browser uses AT-SPI first and a WebExtension in v0.3. No CDP. |
| [0022](0022-mvp-build-plan.md) | MVP build plan | Proposed | Risk-first spikes S1–S3, then vertical milestones M0–M7 mapped to issues, with explicit go/no-go gates. |

## MVP build plan

The full table is in [ADR-0022](0022-mvp-build-plan.md). Summary:

| Order | Work | Issue | Go/no-go |
|---|---|---|---|
| 0 | **M0 Foundations:** skeleton, interfaces and fakes, IPC, CI with an AT-SPI fixture app, `doctor` v0 | new ×2 | CI green with a headless AT-SPI test |
| 1 | **S1 Coordinate pipeline** (KWin script + WINDOW extents), *riskiest* | new | median ≤ 4 px, p95 ≤ 12 px |
| 1 | **S2 AT-SPI coverage** (+ Firefox/workbench, Qt6, Arabic locale) | #2 | ≥ 80% found/unique in ≥ 4 of 6 apps |
| 1 | **S3 Overlay click-through and stacking** (layer-shell + X11) | #3 | 0/1,000 clicks blocked, 60 fps, stop < 150 ms |
| 2 | **M2 Perception + CompositorBridge** | #4 + new | lookup p95 ≤ 50 ms; S1 bounds hold |
| 3 | **M3 Overlay feature** | #3 | S3 criteria in product code |
| 4 | **M4 Step loop (Show-me)** + S5 latency + pointing eval + policy v0 | #5 + new ×2 | p50 ≤ 2 s, p95 ≤ 3 s; ≥ 80% pointed; ≤ 2% confidently wrong |
| 5 | **M5 Packs + terminal + workbench** (S4, S9) | #8 + new ×2 (+ workbench cross-repo) | task match ≥ 85%; S9 ≥ 80% steps |
| 6 | **M6 Struggle detector + persona** (S5b) | #9 + new ×2 | precision ≥ 0.6, recall ≥ 0.5 on replays; ≤ 1 offer per active hour |
| 7 | **M7 Hardening + v0.1** | new ×2 | SPEC §8 + injection eval 0 violations |
| v0.15 | **M8 Do-it** (S7) | new | ≥ 85% of R0–R1 actions succeed, 0 R3 injected |
| v0.2 | **M9 GNOME extension** (S6), **M10 Voice** (S8) | new ×2 | S1/S3 thresholds on GNOME; Arabic WER thresholds |

**Proposed new issues:**
1. Spike S1: coordinate pipeline.
2. Project skeleton, interfaces and CI.
3. `ya-bro doctor`.
4. CompositorBridge (KWin script + X11 EWMH).
5. Pointing eval harness.
6. Policy engine + redaction.
7. Shell hook + terminal adapters.
8. Workbench pack.
9. Persona and tone system.
10. Struggle replay eval set.
11. Consent UX and kill switch.
12. Licence files + compliance gate.
13. Do-it actuator (v0.15).
14. GNOME Shell extension (v0.2).
15. Voice bake-off and pipeline (v0.2).
16. Cross-repo, workbench: a generic, contract-versioned `GET /api/state` endpoint that includes the last CLI error code. It must be generic, per workbench's "never fit it to one app" rule.

**Edits to existing issues:**
- #3: retitle from "(X11/KDE)" to "(layer-shell + X11)".
- #2: add Firefox/workbench, a Qt6 app and an Arabic locale; name "KDE System Settings".

## Cross-cutting risks (ranked)

| # | Risk | Likelihood × impact | Where handled | Early signal |
|---|---|---|---|---|
| 1 | **Pointing coordinates wrong on Wayland.** No toolkit gives AT-SPI screen coordinates; GTK4 doesn't even on X11. If the compositor-origin pipeline misaligns (CSD, popups, fractional scale), Show-me loses trust. | High × Critical | ADR-0004, 0007; spike S1 | S1 p95 error |
| 2 | **Platform mismatch.** The maintainer runs GNOME 50 Wayland, which has no X11 session and no layer-shell, while the plan targets KWin. Dogfooding of proactive mode slips, or GNOME needs a hand-written Shell extension early. extensions.gnome.org rejects AI-generated code. | High × High | ADR-0002, 0006; Q1 below | Maintainer's choice of option (a), (b) or (c) |
| 3 | **Proactive mode annoys (the Clippy effect),** or recall is too low because Wayland hides click and key signals. | Medium × Critical (headline feature) | ADR-0010, 0013; S5b, replay eval | Acceptance rate < 25%, "not for this app" > 20% |
| 4 | **AT-SPI coverage gaps** (Electron flags, GTK4 popovers, canvas UIs such as the workbench SVG diagram) force the slow vision path. | Medium × High | ADR-0005, 0007; S2 | S2 found-rate |
| 5 | **Prompt injection or over-collection** through screen, terminal and web content, given the AT-SPI bus's lack of access control. | Medium × High | ADR-0014, 0009 | Injection eval violations |
| 6 | **Arabic voice quality.** Local Whisper Egyptian WER is about 30–60% depending on the test set. There is no permissive Egyptian TTS, so Arabic voice may be cloud-only. | High × Medium | ADR-0011; S8 | S8 WER and RTF |
| 7 | **Latency budget** (< 3 s per step) missed on vision-tier steps. | Medium × Medium | ADR-0008, 0007 | S5 p95 |
| 8 | **Platform churn:** KWin scripting API changes, GNOME extension breakage each release, GTK X11 backend deprecation (since 4.18), Ubuntu's Plasma 6.6 versus upstream 6.8 permission differences. | High × Medium | ADR-0002, 0004, 0006, 0018 | CI on two Plasma versions |
| 9 | **Single-maintainer scope:** about 10 spikes and 10 milestones. | High × Medium | ADR-0022 ordering; struggle detection behind a toggle | Milestone slip > 2× |
| 10 | **Licence traps** in models and voices (NC weights, GPL engines in-process). | Low × Medium | ADR-0020 | CI licence gate |

## Open questions (for the maintainer)
1. **Q1: dogfooding desktop.**
   - (a) Install a Plasma 6.6 session on Ubuntu 26.04 (`kwin-wayland` and `kwin-x11` are in the archive), recommended for development.
   - (b) Develop in a nested or virtual KWin on GNOME.
   - (c) Switch to GNOME-first and build the Shell extension in M1.

   This decides when S6 runs.
2. **Q2: a11y bus enablement.** It is currently off on the maintainer's machine. Is a first-run prompt that sets it persistently acceptable?
3. **Q3: cloud voice.** Is an Azure (or Deepgram) account acceptable for Arabic voice if S8 shows local is not good enough?
4. **Q4: GNOME extension authorship.** Will the maintainer hand-write or review the extension to satisfy extensions.gnome.org, or distribute it from the repo only?
5. **Q5: reverse-DNS app id** for D-Bus names and the desktop file (proposal: `io.github.ahmedyousrisobhi.YaBro`).
