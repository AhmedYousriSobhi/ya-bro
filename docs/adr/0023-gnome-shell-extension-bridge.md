# ADR-0023: GNOME Shell extension as compositor bridge and overlay

- Status: Proposed
- Date: 2026-11-20
- Issue: #13. Implementation is split three ways: the new issue "Spike S1: GNOME Shell extension bridge + overlay" (throwaway measurements); the new issue "GNOME Shell extension: skeleton, Bridge1, setup and CI" (§1–4, 7–10, including S3 and the dev loop); and **#3** (`Overlay1` renderer, ask window, docked fallback; §5–6).
- Depends on: ADR-0002 (GNOME-first), ADR-0003, ADR-0004, ADR-0006, ADR-0014
- Implementation status (S1, #15): prototype in `extension/`; contract, security and lifecycle checks pass in a headless shell. Coordinates, click-through, stacking, fps and stop-key latency are not yet measured. See [S1 findings](../research/spikes/S1-gnome-extension.md). Still Proposed.
- Refines: ADR-0004 §3 (GNOME row), ADR-0006 (`GnomeShellOverlay`)

## Context
ADR-0002 makes GNOME 50 Wayland the reference platform. On Mutter a normal client can neither stay on top nor learn its own screen position, and the shell's own window list is closed to us. All three were checked on the maintainer's machine (Ubuntu 26.04.1, GNOME Shell 50.1, 2026-11-20):

| Probe | Result |
|---|---|
| `org.gnome.Shell.Introspect.GetWindows` | `AccessDenied: GetWindows is not allowed` |
| `org.gnome.Shell.Eval "1+1"` | `(false, '')` (unsafe mode off) |
| Layer-shell / client always-on-top | Absent in Mutter; wayland-protocols MR 369 closed ([linux-platform.md §3.8](../research/linux-platform.md)) |
| `org.gnome.Mutter.IdleMonitor.GetIdletime` | Works for any session client |
| `org.gnome.Shell.Extensions` | `ListExtensions`, `GetExtensionInfo`, `GetExtensionErrors`, `EnableExtension`, `ExtensionStateChanged`; `UserExtensionsEnabled = true` |
| Display layout | `layout-mode = 1` (logical); `experimental-features = ['scale-monitor-framebuffer', 'xwayland-native-scaling']` (Ubuntu default override) |

So on GNOME both the ring (overlay) and the window origin (ADR-0004) need code inside `gnome-shell`. That is a GNOME Shell extension. It is written in GJS as an ES module (required since GNOME 45) and runs in the compositor process.

Source facts that shape the design, read from `js/ui/layout.js` on the `gnome-50` branch:
- `addChrome()` puts an actor in `Main.layoutManager.uiGroup` **below** `global.top_window_group`. `addTopChrome()` puts it "above all windows, including popups".
- `trackFullscreen` defaults to `false`. Only actors added with `trackFullscreen: true` (the top panel) hide when a fullscreen window is on their monitor.
- GNOME 50's `layout.js` no longer computes a stage input region (`set_stage_input_region` is gone). Input goes to the actor that Clutter picks, so an actor with `reactive: false` should let clicks reach the window below. This is read from the source, **not tested**; spike S1 confirms it.
- The screen shield is added with `addChrome`, so an `addTopChrome` actor could draw above the lock screen. Extensions in the default `user` session mode are disabled on lock, which avoids this (gjs.guide anatomy).

## Decision drivers
- Correct rings: the S1 error bounds from ADR-0004.
- Never block a click and never take focus.
- Crash safety. An exception or hang in the extension takes the whole Wayland session with it.
- A small, hand-reviewable surface: GNOME release churn and extensions.gnome.org (EGO) review.
- No new bypass of GNOME's consent model. The extension must not become a screenshot or input-injection backdoor, and must not re-expose the window list that `Introspect.GetWindows` denies.
- Content-free by default (SPEC §7).

## Options considered
| Option | For | Against |
|---|---|---|
| **One extension: bridge + overlay, a dumb renderer driven by core over D-Bus (recommended)** | One install. Geometry and drawing share one coordinate space, the stage, so no conversion error. All logic stays in testable Python. | GJS code inside the compositor. Has to be ported every GNOME release. |
| Extension as bridge only; overlay as an XWayland GTK window with `_NET_WM_STATE_ABOVE` | Overlay stays in Python | Fails when maximized, sits below fullscreen, blurry under `xwayland-native-scaling` coordinate mapping, and GTK's X11 backend has been deprecated since 4.18. Still needs the extension for geometry. |
| Smart extension (step logic, AT-SPI in GJS) | Fewer IPC hops | More compositor-resident code. Harder review. Duplicates core. |
| No extension: docked mode only | Zero shell code | No live pointing, which is the product's whole point |

## Decision

### 1. Identity and packaging
- **UUID** `ya-bro@ahmedyousrisobhi.github.io` (proposal, follows README Q5). **Bus name** `io.github.ahmedyousrisobhi.YaBro.Shell`. **Object** `/io/github/ahmedyousrisobhi/YaBro/Shell`.
- Lives in-tree at `extension/` (`metadata.json`, `extension.js`, `bridge.js`, `overlay.js`, `stylesheet.css`, `schemas/`). Plain JS with no build step and no bundled binaries or libraries.
- `metadata.json`: `"session-modes": ["user"]` and `"shell-version"` listing **only versions tested in CI** (start with `["50"]`, add 48/49/51 when their CI job is green).

### 2. Responsibilities (everything else stays in Python)
| In the extension | Not in the extension |
|---|---|
| Window list and geometry, focus, stacking order, monitors, scale, pointer position | AT-SPI, planning, LLM, persona, policy |
| Drawing avatar, ring, pointer, bubble and state indicators as St/Clutter actors | Screen capture (stays on the portal, ADR-0005) |
| Hit-testing on avatar and bubble buttons → events to core | Input injection (stays on AT-SPI actions / portal + libei, ADR-0009) |
| Stop key binding (works even if core hangs) | The text "ask" box. It is a normal, focusable GTK window in `ya-bro-overlay`, because typing into St would need a modal grab. |
| Dead-man switch: hide everything if core disappears | Settings UI (no `prefs.js` in v0.1) |

### 3. D-Bus API (session bus, versioned interfaces)
Core is the client. The extension owns the name. All rects are `(iiii)` x, y, w, h in **stage coordinates**, which are global logical pixels when `layout-mode` is logical (the maintainer's setup). `GetInfo` reports the layout mode so core never guesses.

**`io.github.ahmedyousrisobhi.YaBro.Shell.Bridge1`**

| Member | Signature | Notes |
|---|---|---|
| `GetInfo()` | `→ a{sv}` | `api` (u), `shell_version`, `extension_version`, `layout_mode` (logical/physical), `capabilities` (as) |
| `ListWindows()` | `→ aa{sv}` | Per window: `id` (t, `get_id`), `seq` (`get_stable_sequence`), `pid` (`get_pid`), `app_id` (`get_gtk_application_id` / `get_sandboxed_app_id` / `get_wm_class`), `type` (`get_window_type`), `client` (wayland/x11), `frame` and `buffer` rects, `monitor`, `fullscreen`, `focused`, `transient_for`, `stack` index. **No titles.** |
| `GetWindowTitle(t id, u step_serial)` | `→ s` | Only for the focused window, or the window of the active guided step identified by `step_serial` from `ShowStep`. Used for AT-SPI frame matching (ADR-0004 §4). |
| `GetMonitors()` | `→ a(iiiiidb)` | index, x, y, w, h, scale, primary (signature corrected in S1) |
| `GetPointer()` | `→ (ii)` | `global.get_pointer()`. Rate-limited to 30/s. |
| `WindowsChanged` | signal `(at added, at removed)` | All signals are **unicast** to allowed peers (§11) |
| `GeometryChanged` | signal `(t id, (iiii) frame, (iiii) buffer)` | From `position-changed` / `size-changed`, coalesced to at most one per window per frame |
| `FocusChanged` | signal `(t id)` | From `global.display` `notify::focus-window` |
| `MonitorsChanged`, `OverviewChanged(b)`, `FullscreenChanged(i monitor, b)` | signals | |

**`io.github.ahmedyousrisobhi.YaBro.Shell.Overlay1`**

| Member | Signature | Notes |
|---|---|---|
| `ShowStep(a{sv})` | `→ u serial` | `target` rect or none; `ring` = `confident` / `dashed` / `none` (ADR-0007 tiers); `text` (s, ≤ 280 chars, already localized); `dir` = `ltr` / `rtl` (ADR-0019); `buttons` (as) from a **fixed enum** (`next`, `repeat`, `why`, `do_it`, `stop`, `yes`, `no`, `not_for_app`); `follow_window` (t) |
| `FlyPointer((ii) to, u ms)` | `→ u serial` | Quadratic Bezier with ease-out, 400–700 ms (ADR-0006 §3) |
| `SetAvatar(a{sv})` | | position, state (`idle`, `watching`, `thinking`, `talking`, `acting`) |
| `SetIndicators(as)` | | `watching`, `capturing`, `acting` badges (ADR-0014 visible state) |
| `Hide()` | | Idempotent. Also triggered locally by the stop key and the dead-man switch. |
| `Ping(u)` | `→ u` | Heartbeat from core every 2 s |
| `UserEvent` | signal `(s kind, s id, u serial)` | `avatar_click`, `button:<enum>`, `stop_key` |

There is no method that takes code, file paths, shell strings, images or arbitrary markup. Text is set with `St.Label.text` (Pango plain text), never markup.

### 4. Geometry
- `frame` (`get_frame_rect`) is the visible window edge. `buffer` (`get_buffer_rect`) includes client-side shadows. Core computes `screen_rect = origin + extents(WINDOW)` (ADR-0004). **Which origin is correct differs per toolkit:** GTK4 CSD with shadows versus GTK3 versus Qt versus Firefox versus XWayland. It is a per-toolkit table measured in S1, not a constant. Starting hypothesis: GTK4 WINDOW extents are relative to the surface, so they use `buffer` (gtk#8242 shadow offset).
- **XWayland clients** under `xwayland-native-scaling` work in physical pixels. The extension converts with `Meta.Window.protocol_to_stage_rect` where needed and flags `client = x11` so core can apply the toolkit table (behaviour unverified, covered in S1).
- **Popups and menus.** GTK4 popovers and Qt menus are `xdg_popup` surfaces. Whether Mutter lists them as `Meta.Window` of type `DROPDOWN_MENU` / `POPUP_MENU` with usable rects is **unverified**. S1 measures it. Fallback per ADR-0004 §6.
- **Occlusion.** `global.display.sort_windows_by_stacking()` gives the order. Core hides the ring when the target window is covered at the ring centre.

### 5. Overlay actors and input
- For each monitor: one full-monitor `St.Widget` container with `reactive: false`, added with `Main.layoutManager.addTopChrome(actor, {affectsStruts: false, trackFullscreen: false})`, positioned at the monitor's stage origin. Containers are rebuilt on `monitors-changed`.
- Ring, pointer, dashed region and bubble background are non-reactive children. **Only the avatar and the bubble buttons are `reactive: true`.** Nothing is `can_focus`, and the extension never calls `Main.pushModal`, so keyboard focus never moves.
- A target that spans monitors is drawn in each monitor's container, each with its own origin subtracted.
- **Scale.** Stage units are logical. St handles device scale. Line widths use `St.ThemeContext` `scale_factor`.
- **Overview.** All containers hide while `Main.overview` is showing, then re-show and re-layout.
- **Fullscreen.** With `trackFullscreen: false` the containers stay visible over fullscreen windows. Mutter may scan out a fullscreen window directly and skip painting the stage (unredirect). While a ring is visible on a monitor with a fullscreen window, the extension calls `global.compositor.disable_unredirect()` and calls `enable_unredirect()` on hide (API location per the GNOME 48 port guide; whether it is needed on 50 is **unverified**, an S1 check).
- **Self-exclusion from capture.** Core asks for `Hide()` for one frame before a portal screenshot, or masks known rects (ADR-0006 §7).

### 6. Pointer, ring, bubble rendering
- Ring: rounded rectangle with a soft glow, drawn with CSS `border` + `box-shadow` in `stylesheet.css`. `dashed` style for Medium confidence. No ring for Low.
- Pointer: an `St.Icon` that animates with `actor.ease()` along core-computed Bezier keyframes. 60 fps is the target (S1 criterion).
- Bubble: `St.BoxLayout` with an `St.Label` (wrapping, max width 360 logical px) plus buttons. Core does placement (Floating-UI-style flip/shift, ADR-0006 §3) and sends the final position, so the extension stays dumb. RTL: core sends `dir`. The label uses Pango auto-direction with `Clutter.TextDirection` set from `dir` (unverified detail, ADR-0019).

### 7. Lifecycle and failure modes
- `enable()` owns the bus name, exports both interfaces, builds actors and connects signals. `disable()` (synchronous: GNOME 51 throws on an async `disable`) undoes every one of them. The constructor does nothing (EGO rule).
- **Dead-man switch.** If the core's well-known name loses its owner, or no `Ping` arrives for 6 s, the extension hides everything. A stale "click here" ring must never outlive core.
- **Core restarts** resync with `GetInfo` + `ListWindows`. The extension holds no step state apart from what is drawn.
- **No synchronous D-Bus calls and no subprocesses** from the extension. All work is signal handlers plus O(windows) loops. Every handler is wrapped in `try/catch` and logs through `console.error`, so an exception cannot escape into the shell.
- **Lock screen.** `user` session mode only, so the extension is disabled on lock and re-enabled on unlock. Core treats `NameOwnerChanged` as "overlay gone" and redraws the current step after unlock.
- **Errors.** `ya-bro doctor` reads `org.gnome.Shell.Extensions.GetExtensionInfo(uuid)` (state) and `GetExtensionErrors(uuid)`.

| Failure | Behaviour |
|---|---|
| Extension not installed, disabled, or in error state | `DockedOverlay` + no ring (ADR-0006). Doctor says why. |
| Shell version not in `shell-version` | Shell refuses to load it (`disable-extension-version-validation` is false by default). Docked mode, plus "update Ya-Bro". |
| API mismatch (`api` lower than core needs) | Core uses the common subset or goes docked |
| Extension exception at runtime | Shell marks it ERROR. Core sees the name vanish and goes docked. |

### 8. Version compatibility (GNOME 48 → 51+)
- **Reference: 50** (Ubuntu 26.04 LTS stays on 50 for its lifetime, per Ubuntu LTS practice; unverified for point releases).
- One codebase. Use no API that any of 48–51 removed or deprecated: `Clutter.ClickAction` (gone in 49), `Meta.Rectangle` (gone in 49), St `vertical` (removed in 51), direct `key-press-event` signals (deprecated in 51), `pointerWatcher.js` (removed in 51), async `disable()`. Calls to `Gio.DBus.makeProxyWrapper()` result classes use `new` (51). The extension does not need a proxy at all; it exports with `Gio.DBusExportedObject.wrapJSObject`.
- Feature-detect instead of version-sniffing (`global.compositor.disable_unredirect ?? global.display.disable_unredirect`).
- **CI matrix** of headless shells per supported version (ADR-0016). A version is added to `shell-version` only when its job is green.
- Track gjs.guide port guides each March and September. Budget about 1 day per GNOME release.

### 9. Install, enable and first-run consent
1. `ya-bro setup` explains in plain words what the extension can see (window positions, app ids, pointer) and what it cannot (screen pixels, typing, window contents), then asks.
2. **Files.** From a source or `uv tool` install: copy `extension/` to `~/.local/share/gnome-shell/extensions/<uuid>/` and compile `schemas/` with `glib-compile-schemas`. From the .deb: shipped in `/usr/share/gnome-shell/extensions/<uuid>/` (ADR-0015).
3. **Enable.** Append the UUID to `org.gnome.shell enabled-extensions`. On Wayland a running shell does not discover a newly installed extension directory, and GNOME Shell cannot restart while the user is logged in (gjs.guide debugging page), so **one logout/login is required** the first time. `gnome-extensions enable` / `EnableExtension` works without logout only once the shell already knows the UUID (unverified in detail; checked in S1).
4. After login, doctor confirms state ENABLED and an `api` match. Updates to the extension code also need a re-login.
5. **Accessibility bus.** On the same consent screen (ADR-0005), because at-spi2-core on 26.04 is 2.60.4, older than the 2.61 listener-based enablement.
6. **EGO publication** is *not* part of v0.1. EGO rejects AI-generated submissions ("unnecessary code, inconsistent code style, imaginary API usage, comments serving as LLM prompts"). Local install from the repo or .deb is unaffected. Before any EGO submission the maintainer hand-writes or line-by-line reviews the code (README Q4).

### 10. Development and testing
- **Dev loop.** `sudo apt install mutter-dev-bin` (universe, 50.1; the Mutter Development Kit that GNOME ≥ 49 uses instead of `--nested`), then `dbus-run-session gnome-shell --devkit --wayland` with `G_MESSAGES_DEBUG=all SHELL_DEBUG=all`. Install and enable the extension inside that session's terminal. Restart the nested shell to load changes, so the main session never needs re-login during development. The nested instance is "not fully isolated" (gjs.guide), so don't use it with important data open. Exact devkit behaviour on Ubuntu is unverified until S1.
- **Unit tests.** Pure geometry and placement helpers live in separate ES modules, run with `gjs -m` in CI.
- **Contract tests.** Python tests run against the D-Bus XML (a fake bridge in core tests), plus the real extension in a headless shell: `dbus-run-session gnome-shell --headless --wayland --virtual-monitor 1920x1080` (flags present in local `gnome-shell --help`; full invocation in CI unverified) inside an Ubuntu 26.04 container. Schneegans' gnome-shell-pod is Xvfb/X11-based and stops at GNOME 47, so it cannot be used for 49+.
- **Ground truth for S1** on the real desktop: Screenshot portal capture (one-time permission) + known widget colours. In CI, the harness may use Mutter's ScreenCast D-Bus inside the headless session (access rules unverified). It is never exposed by the extension.

### 11. Security
The session bus has no per-object access control, and any same-user process can call the extension or add a match rule for its signals. Same-uid processes can already do a lot (ptrace, `LD_PRELOAD`), so these rules limit **new** harm and spoofing:
1. **Allowed peers.** The extension serves only the current unique-name owners of `io.github.ahmedyousrisobhi.YaBro.Core` (every method), `…YaBro.Perceiver` (`Bridge1` reads, for AT-SPI↔window matching) and `…YaBro.Actuator` (receives `stop_key` only). Ownership is re-checked on `NameOwnerChanged`. Other callers get `AccessDenied`.
2. **Unicast signals.** `wrapJSObject`'s signal emission broadcasts, so any client with a match rule would receive window ids, pids, app ids and focus changes. That would re-open what `Introspect.GetWindows` denies. All signals are therefore emitted with `Gio.DBusConnection.emit_signal(destination = <peer unique name>, …)` once per allowed peer, never broadcast.
3. **Residual risk: name squatting.** While Ya-Bro is not running, any same-uid process can own the core name and pass the check. Exposure is then bounded to window geometry, pid, app id, focus and drawing a Ya-Bro-branded bubble, and never includes pixels, input or window contents. This is accepted and documented. Core logs a warning if it finds its name already owned at start.
4. **No capture, no injection, no eval.** The extension could do all three in-process (`Shell.Screenshot`, Clutter virtual input devices). Exporting them would re-open what GNOME closed in 41 (Shell screenshot API) and what Mutter gates for Orca (KeyboardMonitor). They are permanently out of scope.
5. **Content-free.** No titles in lists. Titles only per §3. No text content of any kind.
6. **UI-spoofing limits.** Bubble text is capped at 280 chars and rendered as plain text. Buttons come from the fixed enum, and their labels come from the extension's own translations, not from the caller. A persistent "Ya-Bro" avatar is always attached to the bubble, so a bubble can never pose as a system dialog. The overlay never shows a password or credential field.
7. **Rate limits.** At most 60 draw calls/s and 30 `GetPointer`/s. Excess calls are dropped.
8. **Lock screen.** Disabled on lock (§7).
9. **Logs** carry method names and counts, never text arguments.

## Consequences
- **Positive:** pixel-exact global coordinates from the compositor itself. An overlay that sits above all windows and popups without stealing input. A stop key that works when core is hung. The same draw protocol as the layer-shell backend, so KWin becomes a port, not a redesign.
- **Negative:**
  - A second language (GJS) in the compositor process.
  - A re-login is needed on first install and on every extension update.
  - Work is needed every GNOME release.
  - EGO distribution needs human-written code.
- **Risks:**
  - A crash or hang in the extension kills the session. Mitigation: a dumb renderer, no sync calls, try/catch everywhere, a nested dev loop.
  - Popup geometry is unknown.
  - Direct scanout may hide the ring over fullscreen windows.
  - The caller check depends on core owning its name before calling.

## Validation plan
Part of **spike S1** (ADR-0022), on GNOME 50 Wayland at 100% and 150% scale:
- **Coordinates:** median ≤ 4 px, p95 ≤ 12 px for in-window widgets in GTK3, GTK4/libadwaita, Qt6, Firefox and one XWayland app. ≥ 70% of popup/menu items within 12 px.
- **Click-through:** 0 blocked out of 1,000 synthetic clicks on the window under the ring and bubble background. Clicks are generated by a test script through the RemoteDesktop portal + libei (one consent dialog), which pulls part of S7's plumbing into week 1. A Python libei binding (e.g. snegg) on Ubuntu 26.04 is unverified; the fallback is the `libei` C API via ctypes. The avatar and buttons receive clicks. Keyboard focus never changes (checked with AT-SPI focus events).
- **Stacking:** ring visible above a normal window, a GTK4 popover, a maximized window and a fullscreen video. Hidden in the overview and on lock.
- **Performance:** 60 fps pointer flight. Extension handlers add < 1 ms per frame (`SHELL_DEBUG` / Sysprof).
- **Lifecycle:** kill core → overlay hidden within 6 s. Disable and enable the extension 50 times → no leaked actors or signal connections.
- **Security:** a non-allowed caller gets `AccessDenied` on every method, and a `dbus-monitor` match rule from a non-peer receives no Ya-Bro signals.

## Revisit if
- Mutter gains layer-shell or an always-on-top protocol for clients. Then the overlay moves back to GTK, and the extension shrinks to the bridge.
- A standard Wayland or AT-SPI API gives assistive technology correct global coordinates (Newton or similar). Then the bridge becomes optional.
- GNOME restricts what extensions can do, or EGO policy changes.
- The extension causes session crashes in dogfooding. Then split it to bridge-only and fall back to docked mode.

## Sources
- GNOME Shell `js/ui/layout.js`, `gnome-50` branch (`addChrome`, `addTopChrome`, `trackFullscreen`, `_updateRegions`): https://gitlab.gnome.org/GNOME/gnome-shell/-/blob/gnome-50/js/ui/layout.js (read 2026-11-20)
- Mutter `Meta.Window` API (`get_frame_rect`, `get_buffer_rect`, `get_pid`, `get_sandboxed_app_id`, `protocol_to_stage_rect`, `position-changed`, `size-changed`): https://gnome.pages.gitlab.gnome.org/mutter/meta/class.Window.html
- Extension anatomy (session modes, `shell-version`, ESM): https://gjs.guide/extensions/overview/anatomy.html
- Creating and enabling an extension: https://gjs.guide/extensions/development/creating.html
- Debugging and nested `--devkit` session, Wayland restart rule: https://gjs.guide/extensions/development/debugging.html
- Port guides: https://gjs.guide/extensions/upgrading/gnome-shell-48.html, https://gjs.guide/extensions/upgrading/gnome-shell-49.html, https://gjs.guide/extensions/upgrading/gnome-shell-50.html, https://gjs.guide/extensions/upgrading/gnome-shell-51.html
- EGO review guidelines (AI-generated rule, `disable()` cleanup, no binaries, no telemetry): https://gjs.guide/extensions/review-guidelines/review-guidelines.html
- `mutter-dev-bin` (Mutter Development Kit) in Ubuntu resolute: https://packages.ubuntu.com/resolute/mutter-dev-bin
- gnome-shell-pod (X11/Xvfb, up to GNOME 47): https://github.com/Schneegans/gnome-shell-pod
- GTK CSD shadow offset: https://gitlab.gnome.org/GNOME/gtk/-/issues/8242
- Local probes on the maintainer's machine (`gdbus introspect` / `gdbus call` on `org.gnome.Shell.Introspect`, `org.gnome.Shell`, `org.gnome.Shell.Extensions`, `org.gnome.Mutter.IdleMonitor`, `org.gnome.Mutter.DisplayConfig`; `gnome-shell --help`; `gsettings`), 2026-11-20
