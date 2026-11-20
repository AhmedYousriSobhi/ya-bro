# ADR-0022: MVP build plan, spikes and go/no-go gates

- Status: Proposed
- Date: 2026-11-20
- Issue: #13
- Depends on: ADR-0002 to ADR-0021
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

The ADRs added new risks and dependencies:
- the coordinate pipeline and compositor bridge (ADR-0004);
- the platform pivot to KWin Wayland (ADR-0002);
- the shell hook (ADR-0021);
- the eval harness (ADR-0016);
- Arabic voice feasibility (ADR-0011).

The plan must run the riskiest unknowns first, with explicit go/no-go criteria, so no feature work is built on a false assumption.

## Decision drivers
- Retire the biggest technical risks before writing features.
- Every milestone ends in something demoable on the reference platform.
- Respect the CLAUDE.md flow: one issue per unit of work, docs first.

## Options considered
| Option | For | Against |
|---|---|---|
| **Feature-first in issue-number order (#2 → #9)** | Simple | #3 and #4 would be built on X11 assumptions and on the AT-SPI SCREEN coords that this research disproved |
| **Risk-first spikes, then vertical slices (recommended)** | Kills the coordinate, overlay and coverage unknowns in about 2–3 weeks; later work builds on measured facts | Spikes produce throwaway code |

## Decision

### Spikes, ordered by risk

| # | Spike | Issue | Question | Go criterion | If no-go |
|---|---|---|---|---|---|
| **S1** | Coordinate pipeline (KWin script + AT-SPI WINDOW extents) | **new** | Can we compute correct screen rects on KWin Wayland and X11? | Median ≤ 4 px, p95 ≤ 12 px for in-window widgets at 100/150% scale; popups ≥ 70% within 12 px | Wayland Show-me falls back to Medium/Low tiers plus vision calibration; reconsider the GNOME-first or X11-only MVP |
| **S2** | AT-SPI coverage (extended) | **#2** (add Firefox/workbench, Qt6, Arabic locale; drop "KDE Settings" → use "KDE System Settings") | How much resolves without vision? | ≥ 80% of 20 named controls found and unique in ≥ 4 of 6 apps; p95 lookup ≤ 50 ms | Promote vision tier; budget for local grounder; narrow the MVP app list |
| **S3** | Overlay click-through and stacking | **#3** (retitle: "layer-shell + X11 overlay") | Click-through, above fullscreen, 60 fps, multi-monitor, stop latency | 0/1,000 clicks blocked; avatar clickable; 60 fps flight; stop → hidden < 150 ms p95 | Try KWin-effect overlay; ADR-0001 revisit (PySide6) |
| **S4** | Pack format prototype | **#8** (spike part) | Can the workbench + GIMP packs express 5 tasks each? | Task-match ≥ 85% over 30 EN/AR phrasings | Simplify the format |
| **S5** | Step-loop latency | **#5** (spike part) | Can AT-SPI-tier steps hit SPEC latency with Claude? | p50 ≤ 2 s, p95 ≤ 3 s; cache hits on ≥ 90% of steps | Pack fast path only; reduce context; revisit model routes |
| **S5b** | Struggle-signal observability on Wayland | **#9** (spike part) | Which signals actually arrive on KWin Wayland (and GNOME)? | ≥ 5 of 8 Wayland-observable signals detected ≥ 95% in scripted runs | Narrow proactive mode to the terminal + dialog + menu signals |
| **S6** | GNOME Shell extension (geometry + ring) | **new** (v0.2, earlier if the maintainer chooses GNOME-first) | Same as S1/S3 on GNOME 50 | Same thresholds as S1/S3 | Docked fallback on GNOME |
| **S7** | Actuation (AT-SPI actions, portal + libei) | **new** (v0.15) | Do-it success rate, consent friction, visible cursor | ≥ 85% of R0–R1 actions succeed; 0 R3 injected | Show-me only on that session |
| **S8** | Arabic/English voice bake-off | **new** (v0.2) | Local vs cloud STT/TTS on the maintainer's speech | Egyptian WER ≤ 25%, code-switched ≤ 30%, RTF ≤ 0.3 GPU | Arabic voice is cloud-only, opt-in |
| **S9** | Workbench end-to-end | **new** | Terminal + browser steps with hooks and fix-its | ≥ 80% steps pointed and verified | Fix the weakest layer before MVP |

**Riskiest first: S1, S2 and S3.** They can run in parallel in week 1–2. S1 decides whether Show-me works on Wayland at all.

### Milestones (dependency order)

```
M0 Foundations ──► M1 Spikes S1,S2,S3 ──go──► M2 Perception+Bridge ──► M3 Overlay ──► M4 Step loop (Show-me)
                                                                                            │
                         M5 Packs + terminal + workbench (S4, S9) ◄──────────────────────────┤
                         M6 Struggle detector + persona (S5b) ◄──────────────────────────────┘
                                              └──► M7 MVP hardening ──► v0.1 release
v0.15: M8 Do-it (S7)        v0.2: M9 GNOME extension (S6) + M10 Voice (S8)
```

| Milestone | Contents | Issues |
|---|---|---|
| **M0 Foundations** | `src/ya_bro/` skeleton, interfaces + fakes (ADR-0018), D-Bus IPC skeleton (ADR-0003), config/log scaffolding (ADR-0017), CI with ruff + pytest + `dbus-run-session` AT-SPI fixture app (ADR-0016), `ya-bro doctor` v0 (session probe, a11y status) | **new:** "Project skeleton, interfaces and CI"; **new:** "ya-bro doctor" |
| **M1 Spikes** | S1, S2, S3 with written findings in `docs/research/spikes/` and ADR status updates (Proposed → Accepted/Rejected) | **new** S1; **#2**; **#3** (spike part) |
| **M2 Perception + bridge** | AT-SPI resolver, fingerprint matcher, `CompositorBridge` (KWin script, EWMH), OCR tier stub, verification predicates | **#4**; **new:** "CompositorBridge: KWin script + X11 EWMH" |
| **M3 Overlay** | `LayerShellOverlay`, `X11Overlay`, `DockedOverlay`, bubble UX, RTL bubble (ADR-0019) | **#3** |
| **M4 Step loop** | Brain (plan tools, caching), confidence tiers, Show-me with automatic verification, controls (next/repeat/why/stop), policy engine v0, pointing eval harness | **#5**; **new:** "Pointing eval harness"; **new:** "Policy engine + redaction" |
| **M5 Packs + terminal** | Pack loader + format v1, workbench pack, GIMP pack, shell hook + Konsole adapter, fix-it rules, S9 | **#8**; **new:** "Shell hook + terminal adapters"; **new:** "Workbench pack"; cross-repo: "workbench: generic contract-versioned `/api/state` endpoint (incl. last CLI error code)" |
| **M6 Struggle + persona** | Detector with back-off (ADR-0010), replay eval set, persona module + templates EN/AR (ADR-0013), per-app opt-in UX | **#9**; **new:** "Persona and tone system"; **new:** "Struggle replay eval set" |
| **M7 MVP hardening** | First-run consent UX, `ya-bro sent/forget/panic`, licence files + CI licence gate (ADR-0020), install docs (ADR-0015), dogfood week, release v0.1 | **new:** "Consent UX and kill switch"; **new:** "Licence files and compliance gate" |
| v0.15 **M8 Do-it** | Actuator backends, risk-tier gating, ghost cursor, S7 | **new** |
| v0.2 **M9 GNOME** | Shell extension (overlay + bridge), S6 | **new** |
| v0.2 **M10 Voice** | S8, Wyoming pipeline, PTT, Piper EN, cloud ar-EG option, AEC | **new** |

### MVP exit criteria (v0.1, measured on KWin Wayland 6.6+)
- The SPEC §8 criteria: a 5–10 step task in 3 apps with ≥ 80% of steps correctly pointed; step latency < 3 s; stop < 500 ms.
- Plus a **confidently-wrong rate ≤ 2%** (ADR-0007).
- Plus a struggle detector with precision ≥ 0.6 on the replay set and ≤ 1 offer per active hour in a dogfood week (ADR-0010).
- Plus zero policy violations on the injection eval (ADR-0014).

## Consequences
- **Positive:** the highest-risk assumptions get measured in the first 2–3 weeks, issues map cleanly to milestones, and each milestone is demoable.
- **Negative:** throwaway spike code. Several new issues need to be created.
- **Risks:**
  - The maintainer's platform choice (ADR-0002 Q1) delays S1.
  - The scope of the MVP is large for one person. M6 can ship behind a toggle, as SPEC already says.

## Validation plan
Each spike's findings document ends with a go/no-go line and updates the relevant ADR status. A milestone is closed only when its issue's acceptance criteria and docs updates are merged into `dev`.

## Revisit if
- S1 or S3 is a no-go. Then re-plan around X11-only or GNOME-first.
- The maintainer picks GNOME-first. Then S6 moves into M1 and M3 starts with `GnomeShellOverlay`.

## Sources
- Existing issues #2, #3, #4, #5, #8, #9 (read via `gh issue view`, 2026-11-20)
- ADR-0002 through ADR-0021 in this directory
