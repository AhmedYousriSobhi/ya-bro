# Spike S1: GNOME Shell extension, bridge + overlay

Issue: #15 · ADRs: [0023](../../adr/0023-gnome-shell-extension-bridge.md), [0004](../../adr/0004-window-geometry-and-coordinate-pipeline.md), [0022](../../adr/0022-mvp-build-plan.md)
Date: 2026-11-22 · Environment: Ubuntu 26.04, GNOME Shell 50.1, Wayland, no `mutter-dev-bin`.

**Status: partial. Go/no-go is not decided.** The extension loads and its D-Bus contract, security and lifecycle behave as designed in an isolated headless shell. The criteria that need pixels, real input or a real desktop are not measured yet.

## What was built
`extension/`: `metadata.json`, `extension.js`, `peers.js`, `bridge.js` (`Bridge1`), `overlay.js` (`Overlay1`), `stylesheet.css`, GSettings schema (stop key). Dev loop: `scripts/dev/headless-shell.sh` runs `gnome-shell --headless --wayland` on a private bus, config, data and runtime dir, so the live session is never touched. Contract checks: `tests/fixtures/shell_contract.py` (run by `pytest -m gnome`).

## Measured (headless shell, 1280x800, 100% scale)
| Criterion (ADR-0023 validation plan) | Result |
|---|---|
| Extension loads in GNOME 50.1, no errors | pass |
| Non-peer callers get `AccessDenied` on `Bridge1` and `Overlay1` | pass |
| Window list: frame, buffer, pid, app_id, no title | pass (GTK4 fixture) |
| `GetMonitors` | pass, after fixing the signature (see below) |
| Overlay state: shown by `ShowStep`, hidden by `Hide`, `Hide` idempotent | pass |
| Draw rate limit 60/s | pass (21 of 80 rapid calls refused) |
| Dead-man: no `Ping` hides the overlay | pass, 6.4 s (limit 6 s plus a 1 s poll) |
| `Ping` keeps overlay visible | pass (10 s) |
| Core name lost: overlay hidden | pass, 0.8 s |
| 20 disable/enable cycles keep serving, no extension errors | pass |

Data point for ADR-0004: a GTK4 window had `frame=(460,361,361,111)` and `buffer=(446,349,389,140)`, so the client-side shadow adds 14 px left and 12 px top. Whether AT-SPI WINDOW extents use frame or buffer is still unmeasured.

## Not measured (open, required before go/no-go)
- Coordinate error (median/p95) across GTK3, GTK4, Qt6, Firefox, XWayland at 100% and 150%; popup geometry.
- Click-through (0/1,000 clicks blocked), avatar and button clicks, keyboard focus never moving: needs input injection (RemoteDesktop portal + libei).
- Ring visibility above maximized, popover and fullscreen windows; hidden in overview and on lock; `disable_unredirect`.
- 60 fps pointer flight, handler cost per frame.
- Stop-key latency (key binding is implemented, not exercised).
- Signal unicast: no non-peer `dbus-monitor` check yet. Signals are emitted per peer by design.
- Actor and signal leaks after disable: only "still works, no errors" is checked, not actor counts.
- `layout_mode` reported `physical` in the headless shell; the detection (`Meta.is_stage_views_scaled`) is unverified on a real desktop at 150%.
- The extension was never loaded in the live session, by design.

## Corrections to ADR-0023
- `GetMonitors` signature is `a(iiiiidb)` (index, x, y, w, h, scale, primary). The ADR's `a(iiiidb)` has one field too few.
- With `Gio.DBusExportedObject.wrapJSObject`, a method named `FooAsync` receives `(args, invocation)`; `a{sv}` values arrive as `GLib.Variant` and must be unpacked.
- A headless shell in `dbus-run-session` works without `mutter-dev-bin` and without sudo. Use a private `XDG_RUNTIME_DIR`: a shell started in the real one leaves `gnome-shell-disable-extensions` behind if killed, which would disable extensions on the next real login.
