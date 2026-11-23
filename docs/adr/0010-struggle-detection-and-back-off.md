# ADR-0010: Struggle detection ("you stuck, bro?") and back-off policy

- Status: Proposed (core detector, shell, idle and AT-SPI sources implemented in #9; see "Implemented")
- Date: 2026-11-20
- Issue: #13 (designs #9)
- Depends on: ADR-0002, ADR-0003, ADR-0005, ADR-0014, ADR-0021
- Related: ADR-0013 (tone of the offer), ADR-0017 (local state)

> **Amended for GNOME-first (2026-11-20).**
> - The **GNOME Wayland column is now the reference**, and S5b runs on GNOME 50 first.
> - Idle comes from `org.gnome.Mutter.IdleMonitor`, verified working on the maintainer's machine.
> - Focus and fullscreen come from the extension's `FocusChanged` / `FullscreenChanged` signals ([ADR-0023](0023-gnome-shell-extension-bridge.md)).
> - The terminal signals assume Ptyxis, the Ubuntu 26.04 default (ADR-0021).
> - KWin Wayland is verified in v0.2. X11-only signals (rage/dead click, XRecord undo) are out of scope, because X11 is CI-only.

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

## Implemented (#9, 2026-11-23)
- **Core:** `ya_bro.struggle`: content-free `Observation`s (kind, short token, number; anything else raises `ContentError`), the nine signals with their counts and windows (defaults from the table above), a score that halves every 90 s, the context gate (typing, fullscreen, do not disturb), breakpoints (a dialog closed, an alert, a command finished, or 5 s of idle) and every back-off rule: one pending offer, 2 min cooldown, 3 an hour and 10 a day, "no" or ignored suppresses that signal for that app until the context changes (or the failing command finally succeeds), two in a row silence the app for 30 min, three in a week halve that weight (reversible), "not for this app", "yes" clears the score. Opt-in per app and a global switch; sensitivity 1 to 4 maps to the threshold (2.5, 1.4, 1.0, 0.6). State (opt-ins, "never", the 7-day "no" log, halved weights, answer counts) is a private JSON file with no observations in it.
- **Pack tuning:** `signals.toml` in a pack (`[weights]`, `[counts.signal]`), bounded at load (weight 0 to 3, count 2 to 50, window 1 s to 1 h); the workbench pack ships one.
- **Sources built:** failing commands from the shell hook (ADR-0021; only allowed commands reach it) and idle from Mutter's IdleMonitor (`platform/gnome_idle.py`, through `gdbus`). `StruggleHost` joins them to the detector; `broctl struggle status|on|off|enable|disable|sensitivity|watch`.
- **Measured for real:** a real interactive bash with the hook, the real spool and the real host: three failures of an allowed command give one offer with the reason "In workbench I saw 3 failed commands of the same name."; a success in between, or a command nobody allowed, gives none; a "no" keeps the same loop quiet. Real Mutter idle in the isolated shell: about 0.5 s right after a key, 4.5 s after 4 s of nothing, back to 0.5 s on the next key; a real pause after a failure is the idle-in-context signal, once, with an offer. That run found a re-arm bug (a shortened idle threshold below the 5 s breakpoint fired every second); fixed with a regression test.
- **Replay eval (#24):** `broctl eval struggle [-v] [--sensitivity N] [--sweep]` replays `evals/struggle/` through the detector on a fake clock (second by second, an unanswered bubble fades after 8 s and counts as ignored). 62 scenarios: 54 scripted (we wrote them, with seeded jitter, and chose the labels) and 8 **recorded** from a real bash with the hook. At the default sensitivity: precision 97%, recall 74%, median time to offer 20 s (p90 57 s), 0.31 false offers per hour of calm, 7 of 7 back-off scenarios as expected: it passes the ADR's gates (P at least 0.6, R at least 0.5, median at most 45 s) and one offer per hour. Sweep: sensitivity 1 recall 6%; 2 precision 97%, recall 74%; 3 and 4 precision 95%, recall 91%, at 0.62 false offers per hour. The misses are all weak signals that cannot reach the threshold alone (dialog bounce, menu thrash, focus ping-pong, undo, an idle pause), and the one false offer is three quick failures that then succeed. Breaking the back-off (no cooldown, no hourly cap, no 30-minute quiet) or making the detector jumpy or deaf fails the eval (tests).
- **Not built:** AT-SPI sources for help and focus-based signals (see "AT-SPI sources" below for what was built), focus ping-pong from the bridge's focus signal, fullscreen and do-not-disturb inputs, the offer bubble with [Yes] [No] [Not for this app] and its 8 s fade (needs the overlay and the persona, #23), "why did you offer?" in the UI, the learned gate, and persistence of the in-session quiet timers and the hour and day caps (a restart forgets them).

## AT-SPI sources, measured (#9, 2026-11-23, GNOME 50, GTK4 and GTK3 in the isolated shell)
`ya_bro.ui_events` (pure, no `gi`) turns raw accessibility events into the detector's kinds; `platform/gnome_atspi_events.py` is the thin listener (interface `UiEventSource`); `broctl struggle watch` runs it with the shell and idle sources. It reads only apps that are allowed in the extension **and** enabled with `broctl struggle enable`: the AT-SPI registry sends every app's events to a listener, so each callback first maps the process to an app through the bridge's window list and drops the event unread otherwise. Keys are random-salted hashes made on the spot (a dialog gets the same key all run; nothing is stored or logged). The text of a text event is never read, only its length. What GNOME's AT-SPI really sends differs from the table above:
- **Menu thrash (GTK4):** no `showing` on the menu. The MenuButton (role button, state `expandable` while open, no HAS_POPUP) sends `expanded` 1 then 0. A click on an item makes the item send `expanded` 0 about 14 ms after the button's, so a close is held 150 ms. **That item event arrives only the first time each item is used**; later clicks look like a dismissal, so a menu used repeatedly can look like thrash (weight 1.0 is below every threshold on its own). Menu items have no accessible name. Context menus (right-click) and keyboard-opened menus send nothing we use. GTK3 and Qt menus are not measured.
- **Dialog bounce:** no `window:create` or `destroy`. A dialog is a `children-changed` add on the application node (role frame and modal, or dialog or alert); closing is a remove whose child is already gone. **Cancel and OK look the same**, so a dialog closed within 3 s counts as bounced. The extension does not list modal dialogs as windows.
- **Error dialogs:** a GTK3 error `MessageDialog` has role `alert`. GTK4's `AlertDialog` and libadwaita's are role `dialog` (or only part of the window), so an error shown that way is a plain dialog, and **modern GTK4 and Adwaita error dialogs are not recognised as errors**.
- **Undo:** there is no event; Ctrl+Z is a `text-changed` delete, as backspace is. Only a delete of two or more characters in one event counts, so backspacing is not undo, but cut and select-and-delete count too. Typing is reported at most once a second.
- **Not built:** help-seeking (menu items have no names, and matching a "Help" menu would read text) and focus ping-pong (needs the bridge's focus signal).
- **Harness:** libatspi dispatches on GLib's default main context while asyncio's GLib loop runs its own, so the source pumps the default context itself; its first call (connecting to the accessibility bus) must run in a worker thread or the process aborts.
- **Real test:** `tests/test_struggle_atspi.py` drives a GTK4 fixture with real pointer and key input (and accessibility actions for dialog buttons), a GTK3 app that raises error dialogs, and two copies that must stay unseen (one not enabled, one not allowed); a second run breaks the translator on purpose and must fail. Six of the 14 replay scenarios in `evals/struggle/` (`recorded-atspi-*`) are what that run's source emitted; their labels are what each script meant. With them the replay eval is 68 scenarios: precision 97%, recall 70% (the new weak-signal struggle scenarios, a menu thrash or a dialog bounce alone, cannot reach the threshold), median 20 s, 0.31 false offers per hour, 7 of 7 back-off.
- **Offer bubble (#9, 2026-11-23):** built in `ya_bro.offers` and `platform/gnome_offers.py`; the "Not built" line below no longer lists it. Yes, No and Not for this app call `Detector.answer` (so the back-off runs as specified), a bubble left alone for 20 s counts as "ignored", the stop key as "no", and an offer is withdrawn unshown (`Detector.withdraw`, no answer counted) if a step loop got there first. The watcher takes the Core bus name only while a bubble is up. Yes only greets and fires an `accepted` event; it does not yet start the ask flow.

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
  - Idle source availability on KWin 6.6 (v0.2; GNOME's IdleMonitor is verified).

## Validation plan
- **Spike S5b (signal observability).** Script each signal in fixture apps on GNOME 50 Wayland (then KWin in v0.2), and record whether the event arrives and its latency. **Go:** at least 5 of the 8 Wayland-observable signals are reliable (≥ 95% detection in scripted runs).
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
