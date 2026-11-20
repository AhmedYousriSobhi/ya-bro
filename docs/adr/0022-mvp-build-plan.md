# ADR-0022: MVP build plan, spikes and go/no-go gates (GNOME-first)

- Status: Proposed
- Date: 2026-11-20 (re-planned the same day for GNOME-first, after the maintainer's decision in ADR-0002)
- Issue: #13
- Depends on: ADR-0002 to ADR-0021, ADR-0023
- Mirrored in: [docs/adr/README.md](README.md#mvp-build-plan)

## Context
Existing GitHub issues:

| Issue | Title |
|---|---|
| #2 | AT-SPI coverage spike |
| #3 | Overlay (X11/KDE) |
| #4 | Perception module |
| #5 | Step loop with Show-me mode and verification |
| #8 | Pack format |
| #9 | Struggle detector |

**What changed.** The first version of this plan targeted KWin Wayland. It ran a KWin-script coordinate spike (S1) and a layer-shell overlay spike (S3), and pushed GNOME (S6) to v0.2. The maintainer has now chosen **GNOME 50 Wayland first** (ADR-0002). On GNOME the window geometry and the always-on-top overlay both come from **one GNOME Shell extension** ([ADR-0023](0023-gnome-shell-extension-bridge.md)). That extension is now the riskiest unknown, so it becomes spike S1. KWin becomes a v0.2 port, and X11 is CI-only.

## Decision drivers
- Retire the biggest technical risks before writing features.
- Every milestone ends in something demoable on GNOME 50 Wayland, the maintainer's daily desktop.
- Keep the in-compositor code small, so a bug never costs the maintainer their session.
- Respect the CLAUDE.md flow: one issue per unit of work, docs first.

## Options considered
| Option | For | Against |
|---|---|---|
| **Feature-first in issue-number order (#2 → #9)** | Simple | #3/#4 would be built on X11/KDE assumptions and on the AT-SPI SCREEN coordinates that the research disproved |
| **Risk-first spikes, GNOME extension first, then vertical slices (recommended)** | Kills the coordinate, click-through, stacking and coverage unknowns in about 2–3 weeks, on the desktop that is used daily | Throwaway spike code. GJS has to be learned early. |
| **Docked mode first, extension later** | No compositor code at first | Not "on the live app". Postpones the headline risk. |

## Decision

### Spikes, ordered by risk

| # | Spike | Issue | Question | Go criterion | If no-go |
|---|---|---|---|---|---|
| **S1** | **GNOME Shell extension: bridge + overlay** (ADR-0023) | **new** | Can a small extension on GNOME 50 give correct screen rects *and* draw a click-through ring above all windows? | **Coordinates:** median ≤ 4 px, p95 ≤ 12 px for in-window widgets (GTK3, GTK4/libadwaita, Qt6, Firefox, one XWayland app) at 100% and 150%; popups ≥ 70% within 12 px. **Overlay:** 0/1,000 clicks blocked; avatar and buttons clickable; focus never moves; ring visible above maximized, popover and fullscreen windows; hidden in overview and on lock; 60 fps pointer flight; stop key → hidden < 150 ms p95; core killed → hidden ≤ 6 s. Clicks are generated through the RemoteDesktop portal + libei from a test script (one consent; Python libei binding on 26.04 unverified) | Coordinates fail: Medium/Low tiers plus vision calibration (ADR-0007). Overlay fails: docked mode on GNOME, and reconsider KWin-first. |
| **S2** | AT-SPI coverage on GNOME | **#2** (extend: GNOME Settings, Ptyxis, Firefox Snap/workbench, a Qt6 app, Arabic locale; `toolkit-accessibility` enabled first) | How much resolves without vision? | ≥ 80% of 20 named controls found and unique in ≥ 4 of 6 apps; p95 lookup ≤ 50 ms | Promote the vision tier, budget for a local grounder, narrow the app list |
| **S3** | Headless GNOME CI + nested dev loop | part of **new** "GNOME Shell extension: skeleton, Bridge1, setup and CI" | Can the extension load and be tested without a real desktop? | Extension ENABLED in `gnome-shell --headless --wayland --virtual-monitor` inside an `ubuntu:26.04` container; D-Bus contract tests pass; PR pipeline ≤ 10 min; `--devkit` loop documented | Self-hosted runner, or manual extension checks before release |
| **S4** | Pack format prototype | **#8** (spike part) | Can the workbench and GIMP packs express 5 tasks each? | Task match ≥ 85% over 30 EN/AR phrasings | Simplify the format |
| **S5** | Step-loop latency | **#5** (spike part) | Can AT-SPI-tier steps hit SPEC latency with Claude? | p50 ≤ 2 s, p95 ≤ 3 s; cache hits on ≥ 90% of steps | Pack fast path only; reduce context; revisit model routes |
| **S5b** | Struggle signals on GNOME Wayland | **#9** (spike part) | Which signals actually arrive on GNOME 50? | ≥ 5 of 8 Wayland-observable signals detected ≥ 95% in scripted runs | Narrow proactive mode to terminal + dialog + menu signals |
| **S6** | KWin port (KWin script + layer-shell) | **new** (v0.2) | Do the S1 thresholds hold on KWin Wayland 6.6? | Same thresholds as S1 | KWin docked mode |
| **S7** | Actuation on GNOME (AT-SPI actions, portal + libei) | **new** (v0.15) | Do-it success rate, consent friction, visible cursor | ≥ 85% of R0–R1 actions succeed; 0 R3 injected; ≤ 1 consent dialog per login with a restore token | Show-me only for injection-needing steps |
| **S8** | Arabic/English voice bake-off | **new** (v0.2) | Local versus cloud STT/TTS on the maintainer's speech | Egyptian WER ≤ 25%, code-switched ≤ 30%, RTF ≤ 0.3 on GPU | Arabic voice is cloud-only and opt-in |
| **S9** | Workbench end-to-end (Ptyxis + Firefox) | **new** | Terminal and browser steps with hooks and fix-its | ≥ 80% of steps pointed and verified | Fix the weakest layer before MVP |

**Riskiest first: S1, then S2 and S3 in parallel (weeks 1–2).** S1 decides whether live pointing works on the maintainer's desktop at all. The go/no-go numbers from the KWin plan are kept: they are about trust in the ring, not about the compositor. Three were added: stop-key latency, dead-man hide and focus safety. They are only measurable now that the overlay lives in the compositor.

**GNOME extension work items.** Items 1, 2, 4, 5, 7, 8 and 9 belong to the new issue "GNOME Shell extension: skeleton, Bridge1, setup and CI". Items 3 and 6 (overlay half) belong to #3:
1. Skeleton: `metadata.json` (`session-modes: ["user"]`, `shell-version: ["50"]`), ESM `extension.js`, an `enable()`/`disable()` with no leaks.
2. `Bridge1`: windows, geometry, focus, monitors, pointer and stacking signals, coalesced per frame.
3. `Overlay1`: per-monitor `addTopChrome` containers, ring/pointer/bubble/avatar actors, fixed button enum, dead-man switch.
4. Stop key binding (GSettings schema in `schemas/`).
5. Security: caller check against the core's name owner, rate limits, plain-text bubble.
6. Python side: the `GnomeShellOverlay` and `GnomeShellBridge` backends, the docked fallback, doctor checks.
7. Setup flow: install files, consent, add to `enabled-extensions`, one re-login, verify.
8. **Nested dev loop:** `mutter-dev-bin` + `dbus-run-session gnome-shell --devkit --wayland`, documented in `CONTRIBUTING`/README.
9. Headless CI job (S3), then the 48/49/51 matrix after MVP.

### Milestones (dependency order)

```
M0 Foundations ──► M1 Spikes S1,S2,S3 ──go──► M2 Perception + GNOME bridge ──► M3 Overlay (extension + docked) ──► M4 Step loop (Show-me)
                                                                                                                       │
                              M5 Packs + terminal + workbench (S4, S9) ◄────────────────────────────────────────────────┤
                              M6 Struggle detector + persona (S5b) ◄────────────────────────────────────────────────────┘
                                                   └──► M7 MVP hardening ──► v0.1 release (GNOME 50)
v0.15: M8 Do-it on GNOME (S7)        v0.2: M9 KWin port (S6) + M10 Voice (S8)
```

| Milestone | Contents | Issues |
|---|---|---|
| **M0 Foundations** | `src/ya_bro/` skeleton; interfaces + fakes (ADR-0018); D-Bus IPC skeleton (ADR-0003); config/log scaffolding (ADR-0017); CI with ruff + pytest + `dbus-run-session` AT-SPI fixture app (ADR-0016); `ya-bro doctor` v0 (session probe, a11y status, GNOME extension state) | **new:** "Project skeleton, interfaces and CI"; **new:** "ya-bro doctor and setup" |
| **M1 Spikes** | S1, S2, S3 with written findings in `docs/research/spikes/` and ADR status updates (Proposed → Accepted/Rejected) | **new:** "Spike S1: GNOME Shell extension bridge + overlay"; **#2**; S3 inside the extension issue |
| **M2 Perception + bridge** | AT-SPI resolver, fingerprint matcher, `CompositorBridge` = GNOME extension `Bridge1` + Python client, per-toolkit origin table from S1, OCR tier stub, verification predicates | **#4**; **new:** "GNOME Shell extension: skeleton, Bridge1, setup and CI" |
| **M3 Overlay** | Extension `Overlay1` renderer, `GnomeShellOverlay` backend, GTK ask window, `DockedOverlay`, bubble UX, RTL bubble in St (ADR-0019), stop key | **#3** (retitled: `Overlay1` renderer, ask window, docked fallback) |
| **M4 Step loop** | Brain (plan tools, caching), confidence tiers, Show-me with automatic verification, controls (next/repeat/why/stop), policy engine v0, pointing eval harness | **#5**; **new:** "Pointing eval harness"; **new:** "Policy engine + redaction" |
| **M5 Packs + terminal** | Pack loader + format v1, workbench pack, GIMP pack, shell hook + VTE/Ptyxis adapter, fix-it rules, S9 | **#8**; **new:** "Shell hook + terminal adapters (VTE first)"; **new:** "Workbench pack"; cross-repo: "workbench: generic contract-versioned `/api/state` endpoint (incl. last CLI error code)" |
| **M6 Struggle + persona** | Detector with back-off (ADR-0010) on GNOME signals (IdleMonitor, extension focus), replay eval set, persona module + EN/AR templates (ADR-0013), per-app opt-in UX | **#9**; **new:** "Persona and tone system"; **new:** "Struggle replay eval set" |
| **M7 MVP hardening** | First-run consent UX (a11y + extension + re-login), `ya-bro sent/forget/panic`, extension security review (ADR-0023 §11), licence files + CI licence gate (ADR-0020), install docs (ADR-0015), dogfood week, release v0.1 | **new:** "Consent UX and kill switch"; **new:** "Licence files and compliance gate" |
| v0.15 **M8 Do-it** | Actuator: AT-SPI actions, RemoteDesktop portal + libei with restore token, risk-tier gating, ghost cursor, S7 | **new** |
| v0.2 **M9 KWin port** | KWin script bridge, `LayerShellOverlay`, Konsole adapter, S6 | **new** |
| v0.2 **M10 Voice** | S8, Wyoming pipeline, PTT via the GlobalShortcuts portal, Piper EN, cloud ar-EG option, AEC | **new** |

### MVP exit criteria (v0.1, measured on GNOME 50 Wayland, Ubuntu 26.04)
- The SPEC §8 criteria: a 5–10 step task in 3 apps with ≥ 80% of steps correctly pointed; step latency < 3 s; stop < 500 ms.
- Plus a **confidently-wrong rate ≤ 2%** (ADR-0007).
- Plus a struggle detector with precision ≥ 0.6 on the replay set and ≤ 1 offer per active hour in a dogfood week (ADR-0010).
- Plus zero policy violations on the injection eval (ADR-0014).
- Plus **no session crash caused by the extension** during the dogfood week, and every S1 overlay criterion holding in product code.

## Consequences
- **Positive:**
  - The maintainer dogfoods on their real desktop from M1.
  - The single riskiest dependency (the extension) is measured in week 1.
  - The KWin work later reuses the same draw protocol and bridge interface.
- **Negative:**
  - GJS has to be learned up front.
  - The first install and each extension update need a re-login. The nested-session dev loop limits this to real installs.
  - Several new issues need to be created, and two are re-scoped.
- **Risks:**
  - Extension crashes during development can end the maintainer's session. Mitigation: develop only in the nested `--devkit` shell, and install in the real session only from tagged builds.
  - The MVP scope is large for one person. M6 can ship behind a toggle, as SPEC already says.

## Validation plan
Each spike's findings document ends with a go/no-go line and updates the relevant ADR status. A milestone is closed only when its issue's acceptance criteria and docs updates are merged into `dev`.

## Revisit if
- S1 fails on coordinates or overlay. Then re-plan around docked mode plus vision, or KWin-first.
- Headless GNOME CI (S3) proves unworkable. Then use a self-hosted runner.
- GNOME 51+ breaks the extension in ways that cost more than about a day per release.

## Sources
- Existing issues #2, #3, #4, #5, #8, #9 (read via `gh issue view`, 2026-11-20)
- ADR-0002 through ADR-0021 and ADR-0023 in this directory
- gjs.guide debugging (nested devkit): https://gjs.guide/extensions/development/debugging.html
