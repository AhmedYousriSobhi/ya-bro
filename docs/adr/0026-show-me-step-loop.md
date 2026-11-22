# ADR-0026: Show-me step loop (plans, verification, scope, tone)

- Status: Accepted for the scripted loop as built (#66, #72, #74, #76); the Claude brain (#5) is still open
- Date: 2026-11-22
- Issues: #66, #68, #69, #72, #74, #76. Refs #5.
- Depends on: ADR-0003, ADR-0004, ADR-0005, ADR-0014, ADR-0023, ADR-0025

## Context
The first working end-to-end loop: point at one real element, wait for the user, check the screen, move on. It was built and tried live on GNOME Calculator before any LLM exists, so the plan comes from a file. The live trials found four problems that shaped the design: a crash on the first button press, a constant offset in one app's AT-SPI rectangles, Next skipping a step the user never did, and a wrong key going unnoticed.

## Decisions
1. **Core is written against the interfaces only.** `StepLoop` (`src/ya_bro/steps.py`) takes `Perception`, `Overlay`, `CompositorBridge` and `Policy`; GNOME code is under `platform/` (`gnome_adapters.py`, `gnome_show.py`) and runs under the system python3, which has PyGObject. `broctl show` starts it with `PYTHONPATH=src`, so `broctl` itself stays dependency-free. asyncio runs on the GLib loop (`gi.events`).
2. **Plans are data.** A TOML file of steps (narration, target role and name, `expect`, `why`, `risk`) served by `ScriptedBrain` (`plans.py`). No app code in core; the pack format (#8) will extend this, not replace it. Narration and `why` come from the plan, never from text read off the screen.
3. **Pointing uses ADR-0004.** Rectangle = window origin from `Bridge1` (frame for GTK4, buffer for GTK3, measured in S1) plus AT-SPI window extents. Per-plan `extents_offset` corrects an app whose extents are a constant off (GNOME Calculator, 12 px, S9). It is a stopgap; a general check of the rectangle is open.
4. **The perceiver enforces scope itself.** AT-SPI is system-wide, so the perceiver only walks applications that own a window `Bridge1.ListWindows` returns, and the extension returns only allowed windows (ADR-0023, ADR-0025). A reference to an element whose window left scope is never answered. Tested with a second, not-allowed app that has the same role and name.
5. **Verification reads the screen.** `expect = {role, name?, text?, appears}`; text is matched by "contains" through AT-SPI's Text interface (`Perception.find(..., text)` and `read_text`). A step with an `expect` advances by itself. Edge-triggered: a step that already looks done when shown does not advance (the screen may show an old result); it waits for Next.
6. **Next never skips silently.** On a step with an `expect` that is not satisfied, the first Next asks ("I don't see that yet"), the second skips. After a wrong action or on a step that already looks done, Next goes on at once. A step with no `expect` advances on Next only.
7. **A wrong action is named.** When the watched text changes to something other than the expectation and holds for 0.6 s, the bubble says what was expected. Mid-way states do not trigger it (the hold time), clearing an old result does not (the baseline is re-read), and **Why?** then explains the mistake (what the screen shows versus what was needed) instead of only restating the step. Only text expectations can see a wrong action; button-only steps cannot.
8. **Tone is its own module.** `tone.py` holds the lines: plain at `humour = 0`, playful from 1 (config key from ADR-0017), three mismatch lines that rotate. Screen text echoed back is cut to 24 characters and never logged.
9. **The bubble stays on screen.** Below the target, above it when there is no room, clamped inside the monitor with the avatar's gap; `Overlay1.GetState` reports the placed rectangle (ADR-0023 §6).
10. **Logging is a side channel.** The loop wraps every log call so a sink can never end a step (the first live crash was a log field named `event`).
11. **Stop always wins.** Stop (bubble button or Super+Shift+Esc) ends the loop and hides the overlay; a cancelled loop hides it too; the loop pauses and hides when no allowed window is focused.

## Tested
Unit tests with fakes (`tests/test_steps.py`, `test_plans.py`); headless shell end to end with a GTK4 fixture (`tests/fixtures/shell_steps.py`: scope, click at the ring's centre advances, Next before the step, label-text verification, Stop button) and with the real Calculator (`shell_calc.py`: wrong key, undo, right key); bubble placement at four corners (`shell_bubble.py`); a live trial by the maintainer on the real desktop.

## Not done / consequences
- Claude brain (#5), Do-it (#27), voice, struggle detection. A real core process and pack format (#8).
- Text matching is "contains" only: typing 5 then 7 shows `57`, which contains `7`. No equals, numbers or regex.
- Browsers and web text are unmeasured; workbench needs its page to report state (#31).
- Only English lines; humour 2 and 3 equal 1.
- Multi-window apps use the focused window; popups and menus are not handled.
- The extents offset cause is unknown and only Calculator is corrected.

## Revisit when
The Claude brain writes plans (it must emit `expect`s the loop can check), a second app shows a different extents offset, or a wrong action must be caught on button-only steps.
