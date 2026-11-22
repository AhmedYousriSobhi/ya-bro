# ADR-0005: Perception strategy: sources, fusion order, element identity, step verification

- Status: Proposed
- Date: 2026-11-20
- Issue: #13
- Depends on: ADR-0003, ADR-0004
- Related: ADR-0007 (grounding), ADR-0012 (packs), ADR-0021 (terminal and browser)

## Context
Perception answers three questions:
1. **What is on screen?** This is the context the planner uses.
2. **Where is element X?** This drives pointing.
3. **Did the expected change happen?** This drives step verification.

Surveyed tools split into two camps:

- **Vision-first: Clicky, Copilot Vision, the Claude/OpenAI computer-use agents.** They are weakest on dense UIs:
  - on ScreenSpot-Pro, GPT-4o scores 0.8 and the early-2025 "Claude (Computer Use)" entry scores 17.1;
  - specialist grounders score 61.6 (UI-TARS-1.5) to 85.1 (cascades);
  - icon targets score 20–40 points below text targets.
- **Accessibility-tree-first: Navisual, ChatGPT "Work with Apps", Raycast.**
  - Navisual resolves a target with app adapters first, then UIA (under 5 ms), then OCR (10–50 ms), then icon templates.
  - ChatGPT reads other macOS apps through the Accessibility API.
  - Source: [ai-tools.md §2.1, §2.5, §3.1](../research/ai-tools.md).

On Linux the equivalent of UIA is AT-SPI. Its coverage, from [linux-platform.md §3.7](../research/linux-platform.md):

| Toolkit or app | AT-SPI coverage |
|---|---|
| GTK3 / GTK4 | Good |
| Qt5 / Qt6 | Good, given `QT_LINUX_ACCESSIBILITY_ALWAYS_ON` or the a11y bus enabled |
| Chromium / Electron | Needs `--force-renderer-accessibility`, or auto-enables when an assistive technology is detected |
| Firefox | Good, and exposes ARIA |
| Canvas UIs and games | Nothing |

Two caveats for Ya-Bro specifically:
- **The a11y bus is off on the maintainer's machine.** Local check: `toolkit-accessibility=false`, `org.a11y.Status.IsEnabled=false`.
- **Flatpak apps** expose their own tree through a filtered proxy. Ya-Bro, as an unsandboxed client, can read them ([factsheet.md D.1](../research/factsheet.md)).

## Decision drivers
- Accuracy, especially on icon-only controls.
- Latency: the step-to-next-highlight budget is under 3 s.
- Token and money cost.
- Privacy: send as little as possible, prefer text over pixels.
- Works without per-app code. Packs only *improve* it.
- Element identity must stay stable across app versions and languages (Arabic and English UI).

## Options considered
| Option | For | Against |
|---|---|---|
| **Vision-only (screenshot → LLM)** | Universal; no a11y enablement needed | Slow (2–6 s), costly (~1–1.8k tokens per screenshot), weakest on icons, needs capture consent on Wayland, screenshots leak more |
| **AT-SPI-only** | Exact names, roles, states, bounds; zero tokens; events double as verification and struggle signals | Blind on canvas and custom-drawn UIs. Electron needs flags. Popovers are fiddly. |
| **Layered resolver: pack adapters → AT-SPI → OCR on crop → vision grounding (recommended)** | Cheapest exact method first (Navisual, Agent S, OmniParser, browser-use pattern). Each layer reports a confidence. Vision only on a crop. | More code paths to test; fusion logic to tune |

## Decision
**1. Sources, in resolution order.** Each layer is a `Resolver` with `resolve(target_spec) -> [Candidate(rect, confidence, source)]`.

| # | Source | Used for | Notes |
|---|---|---|---|
| 0 | **Pack adapters / app-side hooks** (ADR-0012) | Apps that report their own state or element rectangles. Examples: the workbench web UI posting state, the LibreOffice UNO bridge. | Optional and opt-in. Highest trust for *state*. Rectangles are still converted through ADR-0004. |
| 1 | **AT-SPI** via `gi.repository.Atspi` (not the deprecated pyatspi wrapper) | Tree snapshots of the *focused window only*, element lookup, events | Lookup is by fingerprint (below). Never walk the whole desktop. |
| 2 | **Terminal / browser structured sources** (ADR-0021) | Shell hook events, VTE/Ptyxis AT-SPI text (Konsole D-Bus on KWin, v0.2), browser accessibility (Firefox/Chromium AT-SPI with ARIA), later a WebExtension | Keeps terminal and web out of vision |
| 3 | **OCR on a window crop**: Tesseract (Apache-2.0, has Arabic traineddata) or RapidOCR (Apache-2.0) | Text labels missing from AT-SPI | Arabic OCR quality is unverified, so measure it in S2 |
| 4 | **Vision grounding** on the window crop | Icons and canvas | Default is Claude with a set-of-marks prompt (ADR-0007). Optional local grounder (UI-TARS-1.5-7B, Apache-2.0) if hardware allows. |

**2. Context for the planner (question 1).**
- Send a compact numbered list of interactive elements from AT-SPI, filtered by role and `SHOWING|VISIBLE|ENABLED`.
- Cap it at about 150 nodes.
- Each entry has role, name (in both locales if known), state, and a short ancestor path.
- Send a screenshot only when AT-SPI yields fewer than N useful nodes or the step is visual, and only after capture consent (ADR-0014).

**3. Element identity: a fingerprint, not a path.** This is borrowed from DAP "smart selectors" (Whatfix reliability scores, WalkMe's "multiple alternative representations"; [non-ai-tools.md §7](../research/non-ai-tools.md)). Fields in priority order:
1. stable id: AT-SPI `accessible-id` / Qt `objectName` / DOM `id` / `data-testid` exposed via attributes;
2. role + name, keeping the EN and AR names (and the app's translation msgid when known);
3. ancestor chain of roles and names;
4. sibling index and relative geometry inside the window;
5. OCR text anchor, or an optional image patch.

The matcher scores all candidates and accepts the best one above a threshold. The ambiguity margin to the runner-up becomes part of the confidence. When the user confirms a correction ("no bro, it's this one"), the corrected fingerprint goes to a **local pack override** (auto-heal) and is never auto-uploaded.

**4. Step verification (question 3).** Each step carries an `expect` predicate (ADR-0008). Verification checks:
1. **AT-SPI events and state predicates** first, e.g.:
   - `window:create role=dialog name~"Export"`;
   - `state-changed:checked` on the fingerprint target;
   - focus moving to the target.
2. **Structured sources**: shell-hook exit code 0, browser URL or state change, pack hook state.
3. **Tree diff** of the focused window: added or removed nodes matching the expectation.
4. **Pixel diff or vision check** on the crop, only if 1–3 are inconclusive and consent exists.

Verification has three outcomes:
- **passed** → advance;
- **unexpected** → re-perceive and re-plan out loud (SPEC "Recover");
- **unknown after timeout** → ask "did that work?" rather than guessing.

**5. Enabling accessibility.**
- On first run, `broctl doctor` checks `org.a11y.Status.IsEnabled` and offers to set it, together with `toolkit-accessibility` on GNOME. This needs explicit user consent, because it is a persistent setting.
- *Amended for GNOME-first (2026-11-20):* Ubuntu 26.04 ships at-spi2-core **2.60.4**, older than the 2.61.0 change where registering a listener flips `IsEnabled`. So on the reference platform, setup must set `org.gnome.desktop.interface toolkit-accessibility true` (persistent, currently `false` on the maintainer's machine) after consent, on the same screen as the extension consent (ADR-0023 §9). `IsEnabled` alone resets at logout. Qt apps also need `QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1` or the a11y flag; Chromium/Electron need `--force-renderer-accessibility`. Never set `ScreenReaderEnabled`, so Orca's behaviour is untouched.
- It also explains per-app flags: the Chromium/Electron `--force-renderer-accessibility` flag and the VS Code `editor.accessibilitySupport` setting.
- Ya-Bro never edits other apps' launchers silently.

**6. Performance rules (borrowed from Orca).**
- One listener per event type.
- Register only the event types the current mode needs.
- A priority queue with coalescing that drops obsolete events.
- Cache invalidation on `children-changed` and periodic flushes.
- Per-call deadlines (ADR-0003).
- Pin at-spi2-core ≥ 2.60.5 where possible, for the listener-deregistration fix.

## Consequences
- **Positive:**
  - Most steps resolve in tens of milliseconds with zero tokens and no pixels leaving the machine.
  - Verification comes almost for free from events.
  - Vision is a targeted fallback.
- **Negative:**
  - Canvas-heavy apps (Blender viewport, GIMP canvas, the workbench SVG diagram) need vision or pack help.
  - Several resolvers to maintain.
- **Risks:**
  - AT-SPI coverage gaps per app (issue #2 measures them).
  - Arabic OCR quality.
  - Event floods from Electron and LibreOffice.

## Validation plan
- **Spike S2** (= issue #2, extended).
  - Apps: GIMP 3, Inkscape 1.x, LibreOffice Writer, GNOME Settings (GTK4/libadwaita), VS Code (with the flag), Firefox (Snap) on the workbench UI, Ptyxis, plus one Qt6 app. KDE System Settings is added with the KWin port (v0.2).
  - Task: locate 20 named controls per app by role and name.
  - Record found/unique/bounds-correct (through ADR-0004) and lookup latency.
  - **Go** for AT-SPI-first: ≥ 80% found and unique in ≥ 4 of 6 apps, with p95 lookup ≤ 50 ms.
  - Also record which controls need OCR or vision; this sizes the vision fallback.
- **Verification eval.** 50 scripted steps across the fixture apps. Event-based verification decides correctly in ≥ 90% of cases within 2 s.

## Revisit if
- Spike S2 shows AT-SPI-first below 60% in key apps. Then promote vision and budget for a local grounder.
- Newton replaces AT-SPI on GNOME.
- Hardware makes a local grounder fast enough to run speculatively.

## Sources
- [docs/research/ai-tools.md](../research/ai-tools.md): §2.1 Navisual, ChatGPT Work with Apps; §2.5 ScreenSpot-Pro; §3.1
- [docs/research/non-ai-tools.md](../research/non-ai-tools.md): §2 Orca, §7 DAP selectors, §13 takeaways 1–2
- [docs/research/linux-platform.md](../research/linux-platform.md): §3.7 coverage, V4 event table
- ScreenSpot-Pro leaderboard: https://github.com/GUI-Agent/grounding-leaderboard
- Navisual: https://github.com/NavisualGuide/navisual
- ChatGPT Work with Apps: https://help.openai.com/en/articles/10119604-work-with-apps-on-macos
- Whatfix element reliability: https://support.whatfix.com/docs/improve-element-selection-using-element-reliability-indicators-for-steps
