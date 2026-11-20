# Architecture Decision Records

One file per decision, numbered and never renumbered. A superseded ADR stays in place with its status changed to `Superseded by ADR-XXXX`.

**Status values:**
- **Proposed:** written, not yet validated.
- **Accepted:** the spike or eval passed, or the maintainer approved it.
- **Rejected**
- **Superseded**

**Format:** Context, Decision drivers, Options considered, Decision, Consequences, Validation plan, Revisit if, Sources (see [ADR-0002](0002-platform-targets-and-session-strategy.md) for an example).

The set 0002–0023 was produced for issue #13 on 2026-11-20. The same day the maintainer chose **GNOME Wayland first** (ADR-0002): 0002, 0022 and 0023 were rewritten or added, and the other ADRs carry short "Amended for GNOME-first" notes. It rests on the research landscape:
- [docs/research/ai-tools.md](../research/ai-tools.md): how AI guiders, doers, recorders and proactive tools work inside, plus grounding benchmarks.
- [docs/research/non-ai-tools.md](../research/non-ai-tools.md): screen readers, input tools, tour libraries, DAPs, annotators, desktop pets, voice engines, terminal tooling.
- [docs/research/linux-platform.md](../research/linux-platform.md): the hard X11/Wayland/compositor/portal/AT-SPI facts, including what is broken.
- [docs/research/factsheet.md](../research/factsheet.md): licences, HCI research on proactive help, Arabic voice facts, packaging facts.

## Index

| ADR | Title | Status | Headline decision |
|---|---|---|---|
| [0001](0001-language-and-toolkit.md) | Language and toolkit | Accepted | Python 3.12 + GTK4 (PyGObject), uv, pytest, ruff |
| [0002](0002-platform-targets-and-session-strategy.md) | Platform targets and session strategy | Proposed (maintainer-decided) | **GNOME 50 Wayland is the reference platform, via a GNOME Shell extension that is both bridge and overlay. KWin Wayland is the second target (v0.2). X11 is CI-only.** |
| [0003](0003-process-model-and-architecture.md) | Process model | Proposed | Core daemon (asyncio on the GLib loop) + GTK process (ask window, docked mode; layer-shell overlay on KWin) + AT-SPI perceiver + on-demand actuator + Wyoming voice services + in-compositor bridge (GNOME extension first, which also draws the overlay). D-Bus control plane, bulk data via runtime files. |
| [0004](0004-window-geometry-and-coordinate-pipeline.md) | Window geometry and coordinate pipeline | Proposed | Never trust AT-SPI SCREEN coordinates. Screen rect = compositor window origin (GNOME Shell extension first, then KWin script; sway/hyprland best-effort; EWMH in CI) + per-toolkit CSD offset + AT-SPI WINDOW extents. |
| [0005](0005-perception-strategy.md) | Perception strategy | Proposed | Layered resolvers: pack hooks → AT-SPI → terminal/browser structured sources → OCR on crop → vision. DAP-style element fingerprints. Event-based step verification. |
| [0006](0006-overlay-rendering.md) | Overlay rendering | Proposed | GNOME: the Shell extension draws (St actors via `addTopChrome`, non-reactive except avatar and buttons). KWin/wlroots: GTK4 layer-shell (v0.2). Docked fallback everywhere else. X11 overlay only as a CI double. |
| [0007](0007-grounding-and-pointing-accuracy.md) | Grounding and pointing | Proposed | The LLM selects among candidates and never emits pixels when candidates exist. High, Medium and Low confidence tiers change what is drawn. Do-it acts only on High. |
| [0008](0008-brain-llm-strategy-and-step-plan.md) | Brain / LLM strategy | Proposed | Claude Opus 5.5 on all routes at tuned effort (one cache namespace). Strict-tool step plans with predicates. A pack fast path skips the LLM. Prompt-cache layout. Struggle gating stays local. |
| [0009](0009-actuation-do-it-mode.md) | Actuation (Do-it) | Proposed | AT-SPI semantic actions first, then the RemoteDesktop portal + libei on GNOME (fake-input on KWin 6.8, v0.2). No extension-side injection. Ghost cursor, paced narration, R0–R3 risk tiers. R3 is always the user's own click. |
| [0010](0010-struggle-detection-and-back-off.md) | Struggle detection and back-off | Proposed | Content-free, Wayland-observable signals (GNOME first: AT-SPI, Mutter IdleMonitor, extension focus) feed a decaying heuristic score, offered at breakpoints. Lumière-style back-off, rate caps and a sensitivity slider. A learned gate comes later from local labels. |
| [0011](0011-voice-pipeline-arabic-english.md) | Voice pipeline | Proposed (STT/TTS engine pending S8) | Push-to-talk by default, self-trained wake word opt-in. Silero VAD, Wyoming services, local Whisper for English. Arabic STT/TTS is decided by a bake-off, with Azure ar-EG as the only verified Egyptian voice. |
| [0012](0012-app-knowledge-packs.md) | App knowledge packs | Proposed | Data-only pack directory: task graphs, knowledge, docs, selectors, signals, fix-its, hooks. Task match first, then cached docs or BM25. Live MCP and `--help` sources. A workbench pack sketch. |
| [0013](0013-personality-tone-and-humor.md) | Personality and humour | Proposed | A core persona module: tone guide, bilingual template library for frequent moments, LLM lines under a style contract. Humour is never used in risk, error or privacy contexts. A user slider. |
| [0014](0014-privacy-security-trust-model.md) | Privacy, security and trust | Proposed | Threat model. Local `Policy` engine gates every action. Data minimisation and redaction. Per-app consent, visible state indicators, kill switch, short retention. The GNOME extension is a trust boundary: caller check, no capture/injection export. |
| [0015](0015-packaging-and-distribution.md) | Packaging and distribution | Proposed | `uv tool` / pipx with system site-packages now, .deb later. The GNOME extension ships in v0.1 and is enabled after consent plus one re-login. No Flatpak, Snap or AppImage, because sandboxes block cross-app AT-SPI. |
| [0016](0016-testing-and-evaluation-strategy.md) | Testing and evaluation | Proposed | Fakes per interface. Headless GNOME 50 shell in an `ubuntu:26.04` container (primary), AT-SPI on Xvfb, Sway headless for v0.2. Record-replay of events and LLM cassettes. Versioned eval sets with gates. Flake quarantine. |
| [0017](0017-configuration-state-and-observability.md) | Config, state, observability | Proposed | TOML config, SQLite state, content-free JSONL logs with correlation ids, opt-in time-limited content debug, local stats, `ya-bro doctor`. No telemetry. |
| [0018](0018-extensibility-and-portability.md) | Extensibility and portability | Proposed | Protocol interfaces with entry-point backends and data-only packs. Platform imports are banned from core. A macOS/Windows mapping table. |
| [0019](0019-internationalization-and-rtl.md) | i18n and RTL | Proposed | gettext for UI strings, Pango bidi with an explicit base direction, Unicode isolates for embedded names and commands, mirrored bubble, Noto Arabic fonts. |
| [0020](0020-licensing-governance-and-release.md) | Licensing, governance, release | Proposed | MIT OR Apache-2.0. GPL/AGPL only out of process and optional. Model licence register. DCO. SemVer 0.x. dev → main release gates. |
| [0021](0021-terminal-and-browser-integration.md) | Terminal and browser integration | Proposed | Shell hook writes a content-free spool, plus OSC 133. VTE/Ptyxis adapter first (Konsole with KWin, kitty, WezTerm). Fix-it rules. Browser uses AT-SPI first and a WebExtension in v0.3. No CDP. |
| [0022](0022-mvp-build-plan.md) | MVP build plan | Proposed | GNOME-first and risk-first: S1 is the GNOME extension bridge + overlay. Then S2 (AT-SPI) and S3 (headless GNOME CI), then milestones M0–M7 mapped to issues with go/no-go gates. KWin port in v0.2. |
| [0023](0023-gnome-shell-extension-bridge.md) | GNOME Shell extension bridge and overlay | Proposed | A dumb in-compositor renderer + geometry bridge in GJS. Versioned `Bridge1`/`Overlay1` D-Bus API, caller-checked, content-free, with no capture or injection. Dead-man switch, `user` session mode only. Supports GNOME 48–51 where CI is green. |

## MVP build plan

The full table is in [ADR-0022](0022-mvp-build-plan.md). Reference platform: GNOME 50 Wayland (Ubuntu 26.04). Summary:

| Order | Work | Issue | Go/no-go |
|---|---|---|---|
| 0 | **M0 Foundations:** skeleton, interfaces and fakes, IPC, CI with an AT-SPI fixture app, `doctor` v0 (incl. extension state) | new ×2 | CI green with a headless AT-SPI test |
| 1 | **S1 GNOME Shell extension: bridge + overlay** (*riskiest*) | new | median ≤ 4 px, p95 ≤ 12 px; 0/1,000 clicks blocked; ring above maximized/fullscreen; stop key hide < 150 ms; dead-man ≤ 6 s |
| 1 | **S2 AT-SPI coverage on GNOME** (GNOME Settings, Ptyxis, Firefox Snap/workbench, Qt6, Arabic locale) | #2 | ≥ 80% found/unique in ≥ 4 of 6 apps |
| 1 | **S3 Headless GNOME CI + nested `--devkit` dev loop** | new (extension skeleton issue) | extension loads in a headless GNOME 50 container; PR pipeline ≤ 10 min |
| 2 | **M2 Perception + GNOME bridge** | #4 + new | lookup p95 ≤ 50 ms; S1 bounds hold |
| 3 | **M3 Overlay** (extension renderer, ask window, docked fallback) | #3 (retitled) | S1 overlay criteria in product code |
| 4 | **M4 Step loop (Show-me)** + S5 latency + pointing eval + policy v0 | #5 + new ×2 | p50 ≤ 2 s, p95 ≤ 3 s; ≥ 80% pointed; ≤ 2% confidently wrong |
| 5 | **M5 Packs + terminal (VTE/Ptyxis) + workbench** (S4, S9) | #8 + new ×2 (+ workbench cross-repo) | task match ≥ 85%; S9 ≥ 80% steps |
| 6 | **M6 Struggle detector + persona** (S5b on GNOME) | #9 + new ×2 | precision ≥ 0.6, recall ≥ 0.5 on replays; ≤ 1 offer per active hour |
| 7 | **M7 Hardening + v0.1** | new ×2 | SPEC §8 + injection eval 0 violations + no extension-caused session crash in the dogfood week |
| v0.15 | **M8 Do-it on GNOME** (S7) | new | ≥ 85% of R0–R1 actions succeed, 0 R3 injected |
| v0.2 | **M9 KWin port** (S6), **M10 Voice** (S8) | new ×2 | S1 thresholds on KWin 6.6; Arabic WER thresholds |

**Proposed new issues:**
1. Spike S1: GNOME Shell extension bridge + overlay.
2. Project skeleton, interfaces and CI (including a headless GNOME 50 container job).
3. `ya-bro doctor` and setup (a11y + extension consent, re-login flow).
4. GNOME Shell extension: skeleton, `Bridge1`, setup and CI (includes S3 and the nested dev loop; `Overlay1` is built under #3). Replaces "CompositorBridge (KWin script + X11 EWMH)".
5. Pointing eval harness.
6. Policy engine + redaction.
7. Shell hook + terminal adapters (VTE/Ptyxis first).
8. Workbench pack.
9. Persona and tone system.
10. Struggle replay eval set.
11. Consent UX and kill switch.
12. Licence files + compliance gate.
13. Do-it actuator on GNOME: AT-SPI actions + portal/libei (v0.15).
14. KWin port: KWin script bridge + layer-shell overlay + Konsole adapter (v0.2). Replaces "GNOME Shell extension (v0.2)".
15. Voice bake-off and pipeline (v0.2).
16. GNOME extension version matrix: 48, 49 and 51 CI jobs (after v0.1).
17. Cross-repo, workbench: a generic, contract-versioned `GET /api/state` endpoint that includes the last CLI error code. It must be generic, per workbench's "never fit it to one app" rule.

**Edits to existing issues:**
- #3: retitle from "Overlay (X11/KDE)" to "Overlay: GNOME Shell extension renderer (`Overlay1`), ask window and docked fallback (layer-shell in v0.2)".
- #2: target GNOME 50. Add GNOME Settings, Ptyxis, Firefox (Snap) on workbench, a Qt6 app and an Arabic locale. Enable `toolkit-accessibility` first. KDE System Settings moves to the KWin port.
- #4: the bridge is the GNOME extension. Coordinates use a per-toolkit origin table from S1.
- #9: S5b on GNOME (Mutter IdleMonitor, extension focus/fullscreen signals).

## Cross-cutting risks (ranked, GNOME-first)

| # | Risk | Likelihood × impact | Where handled | Early signal |
|---|---|---|---|---|
| 1 | **Pointing coordinates wrong.** No toolkit gives AT-SPI screen coordinates on Wayland. On GNOME the origin (`frame` versus `buffer` rect) differs per toolkit (GTK4 CSD shadows), popups are `xdg_popup` surfaces of unknown visibility to the extension, and XWayland apps run under `xwayland-native-scaling`. | High × Critical | ADR-0004, 0007, 0023; S1 | S1 p95 error |
| 2 | **Extension in the compositor.** A bug, exception or hang in GJS takes the maintainer's whole Wayland session down. Every install or update needs a re-login. | Medium × Critical | ADR-0023 §7 (dumb renderer, no sync calls, try/catch), nested `--devkit` loop | Shell crashes or `GetExtensionErrors` entries during dev |
| 3 | **Proactive mode annoys (the Clippy effect),** or recall is too low because Wayland hides click and key signals. | Medium × Critical (headline feature) | ADR-0010, 0013; S5b, replay eval | Acceptance rate < 25%, "not for this app" > 20% |
| 4 | **GNOME extension API churn.** 48, 49 and 51 each removed APIs we would touch (e.g. `Meta.Rectangle`, `ClickAction`, St `vertical`, async `disable()`). `shell-version` gating means an untested GNOME release turns Ya-Bro into docked mode. | High × Medium | ADR-0023 §8; version CI matrix | A new gjs.guide port guide each March/September |
| 5 | **AT-SPI coverage and enablement gaps.** at-spi2-core 2.60 on Ubuntu 26.04 needs the persistent `toolkit-accessibility` key. Ptyxis a11y is "experimental" (enabled by an Ubuntu override). Electron needs flags, Firefox/Chromium are Snaps, and GTK4 popovers and canvas UIs (workbench SVG) are weak. | Medium × High | ADR-0005, 0007, 0021; S2 | S2 found-rate |
| 6 | **Prompt injection, over-collection, or overlay spoofing.** Screen, terminal and web content; no access control on the AT-SPI bus; the extension's session-bus API could be abused to draw fake prompts. | Medium × High | ADR-0014, 0009, 0023 §11 | Injection eval violations; non-core caller test |
| 7 | **Stacking edge cases on Mutter:** fullscreen direct scanout skipping the ring, overview, lock screen, multi-monitor with mixed scale. | Medium × Medium | ADR-0023 §5; S1 | S1 stacking checks |
| 8 | **Arabic voice quality.** Local Whisper Egyptian WER is about 30–60% depending on the test set. There is no permissive Egyptian TTS, so Arabic voice may be cloud-only. | High × Medium | ADR-0011; S8 | S8 WER and RTF |
| 9 | **Portal friction for Do-it and capture on GNOME:** no silent injection path, restore-token quirks, unknown visible-cursor behaviour, Screenshot portal on 26.04 lacks `target` (x-d-p 1.21.1). | Medium × Medium | ADR-0009, 0005; S7 | Dialogs per session; S7 cursor check |
| 10 | **Latency budget** (< 3 s per step) missed on vision-tier steps. | Medium × Medium | ADR-0008, 0007 | S5 p95 |
| 11 | **Distribution limits.** EGO rejects AI-generated code. This is irrelevant for local/.deb install, but it blocks one-click distribution until the code is human-written or reviewed. The re-login step adds onboarding friction. | Medium × Medium | ADR-0015, 0023 §9; Q4 | Drop-off at the setup step |
| 12 | **Single-maintainer scope** with a second language (GJS): about 10 spikes and 10 milestones. | High × Medium | ADR-0022 ordering; struggle detection behind a toggle | Milestone slip > 2× |
| 13 | **KWin port drift (v0.2):** the KWin scripting API, and Ubuntu's Plasma 6.6 versus upstream 6.8 permission differences. | Medium × Low | ADR-0004, 0006 | S6 |
| 14 | **Licence traps** in models and voices (NC weights, GPL engines in-process). | Low × Medium | ADR-0020 | CI licence gate |

## Open questions (for the maintainer)
1. ~~**Q1: dogfooding desktop.**~~ **Resolved 2026-11-20:** GNOME Wayland first (ADR-0002). KWin is the v0.2 port.
2. **Q2: a11y enablement.** On Ubuntu 26.04 (at-spi2-core 2.60.4) Ya-Bro must set `org.gnome.desktop.interface toolkit-accessibility` persistently. Is a first-run consent screen that sets it acceptable?
3. **Q3: cloud voice.** Is an Azure (or Deepgram) account acceptable for Arabic voice if S8 shows local is not good enough?
4. **Q4: GNOME extension authorship.** v0.1 installs the extension locally only (repo, `uv tool`, .deb). Will the maintainer hand-write or line-review it later so it can go on extensions.gnome.org?
5. **Q5: reverse-DNS app id** for D-Bus names, the extension UUID and the desktop file (proposal: `io.github.ahmedyousrisobhi.YaBro`, UUID `ya-bro@ahmedyousrisobhi.github.io`).
6. **Q6: one re-login on install.** Is a one-time logout during setup (and after extension updates) acceptable, or should setup offer to finish on the next login without asking?
