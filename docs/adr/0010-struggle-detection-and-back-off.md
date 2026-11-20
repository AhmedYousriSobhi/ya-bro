# ADR-0010: Struggle detection ("you stuck, bro?") and back-off policy

- Status: Proposed
- Date: 2026-11-20
- Issue: #13 (designs #9)
- Depends on: ADR-0002, ADR-0003, ADR-0005, ADR-0014, ADR-0021
- Related: ADR-0013 (tone of the offer), ADR-0017 (local state)

## Context
Proactive mode is the headline feature. The closest ancestor is Microsoft's Office Assistant, and the HCI record on it is specific ([factsheet.md Part B](../research/factsheet.md); [ai-tools.md §2.4, §3.4](../research/ai-tools.md)).

**Lumière (Horvitz et al., UAI 1998)**
- Already used Ya-Bro's planned signals:
  - repetitive menu "search";
  - a pause after activity;
  - "undesired effects" (undo; closing a dialog right after opening it);
  - inefficient command sequences.
- It offered help only above a **user-adjustable threshold** (a "volume control").
- An ignored offer **timed out** and was **not re-offered until the inferred topic changed**.
- The shipped Office '97 Assistant did *not* use these autonomous offers. Office XP turned the Assistant off by default.

**Horvitz, "Principles of Mixed-Initiative User Interfaces" (CHI 1999)**
- Act only when expected utility beats the cost of interrupting.
- Two thresholds: ignore → ask, and ask → act.
- Scope precision to uncertainty. Make dismissal cheap. Keep learning.

**Interruption timing research**
- Adamczyk & Bailey (CHI 2004): interrupting at task breakpoints cut annoyance by **56%**, with no gain on objective measures.
- Iqbal & Bailey: deferring to breakpoints reduces frustration.

**"Need Help?" (CHI 2025, n=65)**
- Offers came after **5 s idle**, or immediately on a run error, with a **20 s cooldown**.
- Result: **+18% productivity** and 90% preference.
- A persistent, high-frequency variant dropped preference to **47%**.

**Other evidence**
- ProactiveBench: the best "should I help now?" F1 is about **66%**. Expect to be wrong often, and make being wrong cheap.
- Coding tools (Copilot logistic filter, Cursor, JetBrains) gate with cheap local models. Cursor's Tab model made 21% fewer suggestions with a 28% higher accept rate.
- No public desktop dataset with struggle labels exists. ProAgentBench (2026 preprint) has real-session timing labels.

**The platform constrains what can be observed** ([linux-platform.md V4](../research/linux-platform.md)):
- On Wayland there is **no global key or click observation** for a non-screen-reader. The KeyboardMonitor D-Bus API is allow-listed to Orca in both Mutter and KWin 6.8.
- So the analytics-style desktop translations in [non-ai-tools.md §7](../research/non-ai-tools.md) work only on X11. Those are rage click (PostHog: 3 clicks, < 30 px, < 1 s), dead click (no change in 2.5 s) and the Ctrl+Z loop.

SPEC §7 also requires that monitoring be opt-in per app, local, and limited to **event types and counts, never typed text or screen content**.

## Decision drivers
- Low false-positive rate: every false alarm spends trust.
- Respect: offer, never impose. Back off visibly. The user stays in control (Whitworth's politeness rules).
- Works on Wayland.
- Content-free observation.
- Per-app tuning without app code in core.
- Measurable.

## Options considered
| Option | For | Against |
|---|---|---|
| **Hand-tuned heuristics with a decaying score (recommended v1)** | Explainable, works with zero data, easy to tune per app (pack `signals.toml`), cheap | Fixed weights misfire across users; manual tuning |
| **Learned classifier (logistic regression / GBDT on event features)** | Copilot, JetBrains and Cursor show cheap learned gates beat rules | No labelled data yet; risk of opaque behaviour |
| **LLM decides from an event summary** | Flexible | Cost and latency on every tick; ProactiveBench shows LLMs ~66% F1; sends a behaviour log to the cloud |
| **Bayesian user model (Lumière-style)** | Principled; handles uncertainty | Hard to author; Lumière needed expert-built networks per domain |

## Decision
**1. Signals and observability matrix.** Each signal is a *count or type*, never content.

| Signal | X11 | KWin Wayland | GNOME Wayland | Source |
|---|---|---|---|---|
| Menu thrash: same menu shown→hidden ≥ 3× in 20 s without an item activation | ✓ | ✓ (Qt reliable; GTK4 popovers caveat) | ✓ (same) | AT-SPI `state-changed:showing` on `ROLE_MENU`/`POPUP_MENU` |
| Dialog bounce: dialog opened and cancelled within 3 s, ≥ 2× | ✓ | ✓ | ✓ | AT-SPI `window:create`/`destroy` + role `dialog`; button role only, not text |
| Error loop: error/alert dialog of the same app ≥ 2× in 5 min | ✓ | ✓ | ✓ | AT-SPI `ROLE_ALERT`, or a dialog with an error icon/state; identity = hash of the title, not stored text |
| Failing command loop: same `argv0` with non-zero exit ≥ 3× in 5 min | ✓ | ✓ | ✓ | Shell hook (ADR-0021) |
| App-reported error kinds: the same error *code* reported ≥ 2× (e.g. workbench `WB-REFUSED-MEMORY`) | ✓ | ✓ | ✓ | **Only through an app-side state hook** (ADR-0012), which reports the last error code. The shell hook cannot see stderr, and Ya-Bro never sets `BENCHCTL_AGENT=1` in the user's shell. Without a hook, this falls back to the failing-command loop (exit codes). |
| Idle-in-context: no input ≥ T s while the app is focused *and* a dialog/flow is open or the last command failed | ✓ (XScreenSaver idle) | ✓ `ext-idle-notify-v1` (unverified on KWin 6.6) or the KWin bridge | ✓ `org.gnome.Mutter.IdleMonitor` (verified present on the maintainer's GNOME 50) | Idle source via `CompositorBridge`/`IdleSource` |
| Focus ping-pong between the same 2 windows ≥ 6× in 60 s | ✓ | ✓ | ✓ | Bridge `activated` / AT-SPI `window:activate` |
| Undo loop: ≥ 4 undo activations in 30 s | ✓ (XRecord key category, opt-in) | proxy: Undo menu-item activations, or text-changed delete bursts | proxy (same) | Weak on Wayland; low weight |
| Rage click / dead click | ✓ (opt-in X11 XInput2, categories only) | ✗ dropped | ✗ dropped | Not observable on Wayland |
| Help-seeking: app's Help menu or F1 opened, or a browser tab to docs for this app | ✓ | ✓ | ✓ | AT-SPI menu activation; browser via ADR-0021 |

Global input hooks (XRecord) are **off by default, even on X11**, so behaviour stays the same across sessions.

**2. Scoring.**
- Each signal adds a weight to a per-app **struggle score** that decays exponentially (half-life about 90 s).
- Defaults are in core. Packs may override weights and thresholds in `signals.toml` and add app-specific signals, expressed as declarative AT-SPI/hook predicates, not code.
- Combine with a **context gate**: no offer while the user is typing (any `text-changed` in the last 3 s), during a screen share or fullscreen video (bridge says fullscreen plus a media role), or in a "do not disturb" state.

**3. Decision rule** (Horvitz two-threshold, simplified):
- `score ≥ θ_offer(app, user)` *and* at a breakpoint → **offer**.
- Breakpoints: right after a dialog closes, after an error appears, after a command finishes, or after ≥ 5 s idle.
- Ya-Bro **never auto-acts** from proactive mode. The second threshold ("act") does not exist. Acceptance leads to ask-and-guide.

**4. The offer.**
- One small bubble by the avatar, with one line written by the persona (ADR-0013), plus [Yes, help] [No] [Not for this app].
- No sound by default. Voice only if the user enabled voice offers.
- Fades out after 8 s if ignored. Ignoring counts as a soft "no".

**5. Back-off policy.** This is a core requirement, not polish.

| Event | Effect |
|---|---|
| Any offer | Global cooldown ≥ 2 min (stricter than Need-Help's 20 s, because desktop offers are more intrusive than an IDE side panel) |
| "No" / ignored | Suppress the *same signal type for the same app* until the context changes (new window/dialog/task), as in Lumière. Optional humour line once: "I don't think so, but I'm here." |
| 2 consecutive "no" in a session | Quiet for that app for 30 min |
| 3 "no" for the same signal type within 7 days | That signal's weight for that app is halved, so it learns false alarms. Reversible from settings. |
| "Not for this app" | Proactive mode off for that app until re-enabled |
| "Yes" | Positive label. The struggle score resets after the help ends. |

Hard caps: **≤ 3 offers per hour** and **≤ 10 per day** by default.

**6. User controls.**
- Global on/off.
- Per-app on/off (opt-in per app, SPEC §7).
- A **sensitivity slider** with 4 steps (Lumière's "volume"; Need-Help guideline 6).
- "Why did you offer?" shows the signal names and counts in plain words.
- The tray/avatar shows a small "watching" indicator while monitoring is on.

**7. Learning (v1.x).**
- Every offer outcome becomes a local label: features are the signal counts and timings, the label is yes/no/ignored.
- Stored in local state (ADR-0017).
- Once there are ≥ 200 labels, fit a per-user logistic-regression gate (Copilot-style) that replaces θ_offer. Ship it only if it beats the heuristic offline on held-out labels.
- Nothing leaves the machine.

**8. Content rule.**
- Detection uses types and counts only.
- Text (dialog message, failing command line, stderr) is read **only after the user says yes**, as perception input to the Brain (ADR-0014).

## Consequences
- **Positive:**
  - Works on Wayland.
  - Explainable ("I saw that menu open 4 times").
  - Respects the HCI evidence.
  - Packs can tune it without core code.
- **Negative:**
  - Lacks the click and key signals analytics tools rely on, so recall on Wayland is lower.
  - Defaults will be wrong for some users until learning kicks in.
- **Risks:**
  - The Clippy effect, if cooldowns are too short or offers are badly timed.
  - GTK4 popover menus may not emit reliable showing/hidden events (spike S5b).
  - Idle source availability on KWin 6.6.

## Validation plan
- **Spike S5b (signal observability).** Script each signal in fixture apps on KWin Wayland and GNOME, and record whether the event arrives and its latency. **Go:** at least 5 of the 8 Wayland-observable signals are reliable (≥ 95% detection in scripted runs).
- **Replay eval set.**
  - Record the maintainer's opt-in, content-free event streams (JSONL) while doing scripted "stuck" and "not stuck" scenarios: 40 scenarios, 2 people if possible.
  - Label them, then replay through the detector in CI (ADR-0016).
  - Metrics: precision of offers ≥ 0.6, recall ≥ 0.5, and median time-to-offer after struggle onset ≤ 45 s.
- **Dogfood metrics** (local): offer acceptance rate (target ≥ 40%), offers per active hour (≤ 1 median), and "Not for this app" rate (alarm if > 20%).
- **Usability check.** A short interview after 1 week of dogfooding: "did the bro ever annoy you?"

## Revisit if
- The acceptance rate stays below 25% after tuning.
- A Wayland API for assistive-technology input observation becomes available to non-screen-readers.
- Enough local labels exist to justify the learned gate.

## Sources
- Horvitz et al. 1998, Lumière: https://arxiv.org/abs/1301.7385
- Horvitz 1999: https://www.erichorvitz.com/chi99horvitz.pdf
- Adamczyk & Bailey 2004: https://hci.rwth-aachen.de/materials/conferences/CHI2004/1p271.pdf
- Iqbal & Bailey OASIS: https://www.interruptions.net/literature/Iqbal-TOCHI10.pdf
- Chen et al., "Need Help?", CHI 2025: https://arxiv.org/html/2410.04596v2
- ProactiveBench: https://arxiv.org/html/2410.12361v3 · ProAgentBench: https://arxiv.org/abs/2602.04482
- Whitworth 2005, Polite computing: https://digitalcommons.njit.edu/fac_pubs/19576
- Cursor Tab RL: https://cursor.com/blog/tab-rl · Copilot filter (arXiv 2405.14753), cited in ai-tools.md
- PostHog rage/dead click source: https://github.com/PostHog/posthog-js
- [docs/research/linux-platform.md](../research/linux-platform.md): V4 (KeyboardMonitor gating, AT-SPI event table)
- [docs/research/non-ai-tools.md](../research/non-ai-tools.md): §7 frustration signals
