# Spike S1: GNOME Shell extension, bridge + overlay

Issue: #15 · ADRs: [0023](../../adr/0023-gnome-shell-extension-bridge.md), [0004](../../adr/0004-window-geometry-and-coordinate-pipeline.md), [0022](../../adr/0022-mvp-build-plan.md)
Date: 2026-11-22 · Environment: Ubuntu 26.04, GNOME Shell 50.1, Wayland. All measurements ran in an **isolated headless gnome-shell** (software rendering, virtual monitor), never in the live session.
Raw numbers: [scale 1](S1-measurements-scale-1.json), [scale 1.5](S1-measurements-scale-1.5.json). Reproduce: `uv run pytest -m gnome_measure -s` (about 5 minutes).

## Verdict (provisional)
**Overlay approach: go. Stop key: go (with the stage fallback; confirmed with a real keyboard in the nested shell). Coordinates: go for GTK on Wayland, open for everything else.**
Not decided: the S1 go/no-go as a whole, because XWayland, Qt6 and Firefox are unresolved and the extension has not been loaded in the live session (lock screen and fullscreen scanout unchecked). #15 stays open.

## What was built
`extension/` (`Bridge1`, `Overlay1`, caller check, per-peer signals, rate limits, dead-man switch, stop key, Bézier pointer flight, `disable_unredirect` while visible) and the test tooling: `scripts/dev/headless-shell.sh`, `tests/fixtures/shell_contract.py` (fast contract test, `pytest -m gnome`), `tests/fixtures/measure.py` + `shellkit.py` + `apps/toolkit_fixture.py` (measurements, `pytest -m gnome_measure`).

## Method
- **Input and frames:** Mutter's own `RemoteDesktop` + `ScreenCast` D-Bus APIs, called from test code. The extension has no capture or injection method. **This is not the portal + libei path**, so S1 does not settle S7's libei-binding question.
- **Ground truth for coordinates:** the fixture app reports where each injected click lands in its own window coordinates, and its widgets' bounds from the toolkit. Origin = global click position minus the reported window-local position. Button activation is the hit test. Frames are grabbed from the screen-cast stream and ring pixels are located by colour.
- Click coordinates are scaled by the monitor scale (stream space is physical pixels); this was a harness bug at 150% until fixed.

## Coordinates (ADR-0004 origin table, measured)
Median error in px of "origin from the bridge + AT-SPI `WINDOW` extents" against truth. 20 widgets per toolkit; "hit" is clicking the predicted centre.

| Toolkit (client) | Origin to use | 100% | 150% | Hit test |
|---|---|---|---|---|
| GTK4 (Wayland) | **frame** | 0.0 (buffer: 18.4) | 0.13 (buffer: 18.5) | 20/20 |
| libadwaita (Wayland) | **frame** | 0.0 (buffer: 18.4) | 0.13 (buffer: 18.5) | 20/20 |
| GTK3 (Wayland) | **buffer** | 0.0 (frame: 34.7) | 0.56 (frame: 34.3) | 20/20 |
| GTK3 (XWayland) | frame + (0, 37) | frame: 37.0 | not measurable (see below) | 0/20 |
| Qt6, Firefox | not covered | | | |

- **The ADR's starting hypothesis was backwards for GTK4:** GTK4 and libadwaita use the **frame** origin; GTK3 uses the **buffer** origin. The table must be per toolkit, as ADR-0004 said.
- AT-SPI `WINDOW` extents matched each toolkit's own widget bounds exactly (0 px). AT-SPI `SCREEN` extents are `(0,0)` for GTK4 on Wayland, as ADR-0004 states. GTK3 returned non-zero values; unexplained.
- XWayland: the true client origin was exactly `(frame.x, frame.y + 37)`, which is consistent with a server-side title bar inside `frame`. Proposed fix, **untested**: add the client-area rect to `Bridge1`. At 150% the XWayland samples were unusable (7 clicks, errors above 300 px), so X11 under fractional scale is unresolved.
- Popups: a GTK4 popover appears in `ListWindows` as its own window (type 9, `DROPDOWN_MENU`) with a frame rect. Item-level accuracy inside popups was **not** measured.

## Overlay
| Criterion | 100% | 150% |
|---|---|---|
| Ring edge position error | 1.5 px median, 2.0 max | 1.5 / 2.0 |
| Clicks through ring and bubble background (1000 sent) | 1000 reached the app, 0 blocked | 1000 / 0 |
| Focus events during clicks / app still focused | 0 / yes | 0 / yes |
| Avatar click: `UserEvent`, leaked to app | 1, 0 | 1, 0 |
| Bubble button click: `UserEvent button:next`, leaked | yes, 0 | yes, 0 |
| Ring visible above popover, maximized, fullscreen | yes (all four edges) | yes |
| Ring hidden in overview, back after | yes | yes |
| Pointer flight lands at target | yes | yes |
| `disable_unredirect` active while visible | yes (state reported) | yes |

Plus, from the contract test: non-peer callers get `AccessDenied`; draw rate limit works (60/s); dead-man hides at 6.4 s; core name loss hides in 0.8 s; 20 disable/enable cycles keep serving with no extension errors.

## Open problems
1. **Stop key: Mutter drops the shell-added binding in about half of fresh sessions; fixed with a stage fallback.** With only the `Main.wm.addKeybinding` binding, `Super+Shift+Escape` worked in about 40 to 50% of fresh sessions, in the headless shell and in a nested `--devkit` shell on the real display (2 of 5). Registration was identical in good and bad sessions (valid action id, correct value). Key-event logging showed the difference: in good sessions the Escape key-down never reached the stage (the binding consumed it); in bad ones it reached the stage with the correct modifiers (`state=0x41`, Super+Shift) and keycode, so Mutter simply did not match it. GNOME's own `Super+A` worked in every session, settle delays and a different combo did not help. Fix: `extension.js` also matches the combo from the stage's `captured-event` (if the binding fires the stage never sees the key, so there is no double trigger). After the fix: **10/10 headless sessions and 5/5 nested real-display sessions**, latency median 7 ms, p95 8.2 ms. Limits: the fallback matches the default combo only (a user-customised key uses the binding alone), and the root cause inside Mutter is unknown. `ADR-0011` still lists the GlobalShortcuts portal as an alternative.
2. **GTK4 `EventControllerMotion` coordinates disagreed with click coordinates** by a constant (17, 5) px in an early probe. They were not used as ground truth; the click path agreed with toolkit bounds exactly. Unexplained.
3. **`layout_mode` is `unknown`.** The extension cannot read Mutter's layout mode; Mutter reports `layout-mode: 1` (logical) in `org.gnome.Mutter.DisplayConfig.GetCurrentState` at 150%. Core should read it there. Stage coordinates were logical at 150% (rings aligned at 1.5 px).
4. **`BecomeMonitor` sees unicast signals.** A non-peer match rule received 0 Ya-Bro signals, but a same-user process that calls `BecomeMonitor` saw 6 to 7 (window ids, pids, app ids). This is the residual same-user risk ADR-0023 §11 already accepts; it is now measured.

## Nested real-display run (mutter-devkit, GNOME 50.1)
A nested shell in a `mutter-devkit` window on the real desktop (`YB_DEVKIT=1`; private bus, runtime dir and display; only the nested shell sees the host socket). It ran the same extension on the real GPU.
- Extension loads, `GetInfo`, frame grabs and injected input work. Stop key: see problem 1 (5/5 after the fix).
- **Frame rate:** screen-cast frame interval during a 1 s pointer flight: **median 8.4 ms, max 12.8 ms (about 119 fps)** nested, against a median 33 ms (about 30 fps) in the software-rendered headless shell. The 60 fps target is met. This is the shell's repaint cadence as seen through the stream, not a display measurement, and per-frame handler cost (under 1 ms target) was not measured.
- **Real keyboard confirmed:** in a 90 s run the maintainer pressed `Super+Shift+Escape` on their own keyboard in the nested window and the nested shell received **8 stop-key events** (an earlier 75 s run recorded 0 because the window was not in use). The host GNOME does not swallow the combo. The test cannot tell whether the binding or the stage fallback fired, only that the stop path works. No mouse clicks were recorded in that run (not required for this check). Camera device watcher: 0 opens.

## Not measured
- Qt6 (no bindings installed) and Firefox.
- Still outstanding on the real desktop: GPU scanout (`disable_unredirect` effect on a fullscreen video), lock screen, and multi-monitor. These need the extension installed in the live session (logout/login) or a manual nested run.
- Actor and signal leak counts after disable (only "still serving, no errors").
- Popup item-level accuracy; ring across monitors.
- The portal + libei path (S7).

## Incidents during the spike (disclosed)
- The GitHub token was printed once in the session output through a failed redaction. It should be rotated.
- An early XWayland test inherited the real `DISPLAY=:0`, so a fixture window probably flashed on the real desktop. The harness now unsets `DISPLAY`, finds its own Xwayland from the shell's child process, and removes its own socket and lock files on exit.
- A harness run started WirePlumber, whose V4L2 monitor probably lit the webcam LED. WirePlumber now runs with video, audio and Bluetooth features off, inside a `bwrap` namespace that replaces `/dev/video*` and `/dev/media*` with `/dev/null`, and the harness aborts if it holds a video descriptor. Across the final runs a watcher polling those device nodes every 0.2 s saw 0 opens.

## Corrections to ADR-0023
- `GetMonitors` signature is `a(iiiiidb)`.
- `wrapJSObject` methods named `FooAsync` receive `(args, invocation)`; `a{sv}` values arrive as `GLib.Variant`.
- The stop key needs a stage `captured-event` fallback next to `addKeybinding` (see problem 1).
- `Overlay1.Visible` is replaced by a gated `GetState()` method (`visible`, `overview`, `unredirect_disabled`), readable by Core and Perceiver only.
- A headless shell works without `mutter-dev-bin` or sudo, if it gets a private `XDG_RUNTIME_DIR`, PipeWire plus a camera-masked WirePlumber (needed to link screen-cast streams), and its own Xwayland.
