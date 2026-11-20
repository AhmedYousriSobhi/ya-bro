# Linux platform facts for Ya-Bro

> **Scope:** the hard platform facts behind Ya-Bro (Python 3.12 + GTK4/PyGObject), including what is known to be broken or flaky:
> - the overlay;
> - perception through AT-SPI, screenshots, the browser and the terminal;
> - struggle observation;
> - input injection;
> - global hotkeys;
> - voice.
>
> **Research date:** 2026-11-20.
>
> **Sources:** primary wherever possible: protocol XMLs, portal XMLs from the `xdg-desktop-portal` repo (HEAD 2026-11-19), and compositor and toolkit source code. The source read was KWin `master` (2026-11-20) plus tags v6.0.0–v6.8.0, GTK `main` (4.25.2), Mutter `main` and Qt `qtbase` `dev`, with GitLab/GitHub issues alongside.
>
> **Unverified claims** are marked "(unverified)". "Source-verified" means I read the code, not that I ran it.

**Current releases as of today** (read from tags and announcements):
- **KDE Plasma:** 6.8.3 (KWin tag 2026-11-10). 6.8.0 was tagged 2026-10-08 and is the first Wayland-only Plasma. 6.7.x is the last series with an X11 session.
- **GNOME:** 49 (Sept 2025) and 50 (March 2026) are released. 51 was due on the usual six-month cadence (Sept 2026), and gjs.guide has a GNOME Shell 51 port guide, so it is out. The exact 51 release date is unverified. Ubuntu 26.04 LTS ships GNOME 50.1.
- **GTK:** 4.25.x on main. The X11 backend has been deprecated since 4.18.
- **xdg-desktop-portal:** 1.22.0 (2026-06-08). The next release is numbered "23.0".

---

## 0. TL;DR for architecture

1. **X11-first is now a legacy target.** Plasma 6.8 (Oct 2026) removed the Plasma X11 session. Mutter dropped its X11 session code in GNOME 50. *(Updated 2026-11-20: the maintainer chose **GNOME 50 Wayland as the primary target**, with KWin Wayland second and X11 for CI only. See ADR-0002 and the GNOME-specific facts in §3.17. This doc originally recommended KWin first.)*
2. **There are no correct global AT-SPI screen coordinates on Wayland, from any toolkit.** GTK4 returns `(0,0)` for `ATSPI_COORD_TYPE_SCREEN` on **every backend, X11 included**. Always query `ATSPI_COORD_TYPE_WINDOW`, then add the window origin from the compositor. Get that origin from a KWin script, a GNOME Shell extension, `swaymsg`/`hyprctl`, or EWMH plus `_GTK_FRAME_EXTENTS` on X11.
3. **Overlay mechanism per desktop:**
   - **KWin Wayland:** layer-shell OVERLAY. It sits above fullscreen windows.
   - **Sway, Hyprland:** layer-shell OVERLAY.
   - **GNOME:** a GNOME Shell extension (chosen, ADR-0023). An XWayland window with `_NET_WM_STATE_ABOVE` that is never maximized is possible but rejected (§3.17).
   - **X11:** a GTK4 window plus Xlib EWMH hints and an empty XShape input region.
4. **Input injection:**
   - **GNOME and KDE:** RemoteDesktop portal with `ConnectToEIS`, behind a consent dialog. Since Plasma 6.8, KWin's `org_kde_kwin_fake_input` is also open to unsandboxed clients.
   - **Sway, Hyprland:** wlr virtual-pointer and virtual-keyboard.
   - **X11:** XTest.
5. **Global input observation on Wayland is effectively unavailable to non-screen-readers.** The new `org.freedesktop.a11y.KeyboardMonitor` D-Bus API in Mutter and KWin 6.8 is gated to the owner of `org.gnome.Orca.KeyboardMonitor`. Rely on AT-SPI *object* events and the shell or terminal hooks instead.
6. **Flatpak hurts on KDE.** KWin 6.8 keeps restricted Wayland interfaces only for **sandboxed** clients: Flatpak or Snap, detected by systemd unit name. That covers fake-input, window management and screencast. A deb, pipx or AppImage build gets more.

---

## 1. Summary matrix

Legend:
- **works:** works out of the box for an unsandboxed app.
- **consent:** works after a per-session or one-time user dialog.
- **restricted:** exists, but is gated to privileged clients.
- **broken:** not possible.
- **unknown:** not verified.

| Capability | X11 (any EWMH WM) | KWin Wayland (Plasma 6.x) | Mutter Wayland (GNOME 46–51) | wlroots (Sway 1.11) | Hyprland (0.5x) |
|---|---|---|---|---|---|
| **Overlay always-on-top** | **works:** `_NET_WM_STATE_ABOVE` or a `_NET_WM_WINDOW_TYPE_NOTIFICATION`/`DOCK` hint via Xlib on the GdkX11 XID. Override-redirect is above everything, but GTK4 has no API for it, so it needs Xlib before map (unverified). | **works:** `zwlr_layer_shell_v1` OVERLAY layer (v5), mapped to KWin `OverlayLayer`, above fullscreen. A KWin script `keepAbove` puts a window *below* the active fullscreen window. | **broken** for native Wayland clients: no layer-shell and no client-side above request. **works** for an XWayland window with `_NET_WM_STATE_ABOVE` (TOP layer, *unless maximized*). **works** for a GNOME Shell extension drawing in-shell. | **works:** layer-shell OVERLAY (v4) | **works:** layer-shell OVERLAY (v5) |
| **Click-through** | **works:** `gdk_surface_set_input_region(empty)` becomes an XShape `ShapeInput` with 0 rects. Needs a compositor for alpha. | **works:** empty `wl_surface.set_input_region` on the layer surface | **works** for an XWayland XShape input region or in-shell (`reactive: false`) | **works** | **flaky:** an empty input region still captures the pointer when keyboard mode is `EXCLUSIVE` (discussion #14136). Use `NONE`. |
| **Global input observation** | **works:** XInput2 raw events / XRecord. AT-SPI keystroke listeners work. | **restricted:** `org.freedesktop.a11y.KeyboardMonitor` (KWin 6.8+) is Orca-only. XWayland apps see keys only if the user enables "Legacy X11 App Support". | **restricted:** KeyboardMonitor is Orca-only (allow-listed bus name) | **broken** (no protocol). `/dev/input` needs the `input` group, which is a security hole. | **broken** (same as Sway) |
| **Input injection** | **works:** XTest | **consent:** RemoteDesktop portal plus `ConnectToEIS` (Plasma 6.1+). **works** (6.8+, unsandboxed): `org_kde_kwin_fake_input`. uinput needs root/udev. | **consent:** RemoteDesktop portal plus `ConnectToEIS` (x-d-p-gnome 45+) | **works:** `zwlr_virtual_pointer_v1` plus `zwp_virtual_keyboard_v1`. No RemoteDesktop portal. | **works:** virtual pointer/keyboard. No RemoteDesktop portal. |
| **Screen capture** | **works:** XGetImage / XShm / XComposite | **consent:** ScreenCast/Screenshot portal. **works** (6.8+, unsandboxed): `org.kde.KWin.ScreenShot2` D-Bus without a `.desktop` permission. Through 6.7 it needs `X-KDE-DBUS-Restricted-Interfaces`. | **consent:** Screenshot portal (one-time permission) or ScreenCast + PipeWire. Shell D-Bus is portal-only since GNOME 41. | **works:** `zwlr_screencopy` / `ext-image-copy-capture`, or portal-wlr | **works:** screencopy, or portal-hyprland |
| **AT-SPI global coords** | **works** for GTK3 and Qt. **broken** for GTK4: SCREEN is always `(0,0)`, so use WINDOW plus the WM frame. HiDPI: GTK3 reports unscaled (logical) units. | **broken** (any toolkit). Workaround: WINDOW coords plus KWin script `clientGeometry`/`bufferGeometry`. | **broken.** Workaround: WINDOW coords plus a Shell extension `get_frame_rect()`/`get_buffer_rect()`. | **broken.** Workaround: WINDOW coords plus `swaymsg -t get_tree` rects. | **broken.** Workaround: WINDOW coords plus `hyprctl clients -j`. |
| **Global hotkey** | **works:** XGrabKey | **consent:** GlobalShortcuts portal (Plasma 5.27+). **works:** kglobalaccel D-Bus. | **consent:** GlobalShortcuts portal (GNOME 48+) | **unknown/partial:** no portal-wlr GlobalShortcuts. Use the sway `bindsym` config plus IPC. | **consent:** GlobalShortcuts via x-d-p-hyprland, or `hyprctl`/config binds |

---

## 2. Verdicts on decision-critical questions

### V1: AT-SPI coordinates on Wayland (item 1)

**Verdict: no toolkit returns correct global screen coordinates on Wayland. GTK4 returns `(0,0)` for SCREEN on every backend, including X11.**

**Per toolkit:**
- **GTK4.** `gtk/a11y/gtkatspiutils.c` (`gtk_at_spi_translate_coordinates_from_accessible`, GTK main 4.25.2) returns `*xo = 0; *yo = 0` for `ATSPI_COORD_TYPE_SCREEN` unconditionally. WINDOW and PARENT work.
  - The behaviour dates from the 4.10/4.11 era: gtk#5896 (closed 2023-06) reported garbage values. gtk#6343 (closed 2025-01) said "returns (0,0) in ATSPI for every widget".
  - Accerciser MR 33 ("Calculate screen coords for gtk4 apps") works around it by adding a window-manager-supplied origin to WINDOW coords.
- **Qt5/Qt6.** `atspiadaptor.cpp` computes SCREEN from `QAccessibleInterface::rect()`, which is `mapToGlobal`-based.
  - On X11 this is correct.
  - On Wayland, Qt cannot know the window position. SCREEN therefore collapses to roughly window-relative values (unverified empirically; consistent with QTBUG-86780).
  - WINDOW is computed by subtracting the top-level accessible's rect.
- **GTK3 on Wayland.** Coordinates are window-relative; popovers are at `(0,0)` (gtk#5149, open). On X11 they are correct.
- **Firefox.** Mozilla bug 1790717 was resolved as a known limitation: "no screen-relative coordinates on Wayland".
- **Chromium/Electron.** Wayland behaviour unverified. Assume window-relative.

**The compositor-side pointer API is not a fix either.** GNOME's `org.freedesktop.a11y.PointerLocator` (Mutter) returns only the toplevel under the pointer plus *surface-relative* pointer coordinates. It does not return a window origin. KWin 6.8 implements it as well. Known bugs:
- the offset includes client-side shadows of about 15px (gtk#8242, at-spi2-core#232, both opened 2026-06);
- it ignores scaling (mutter#4833, 2026-05).

**Separately, HiDPI:** GTK3 extents are not multiplied by the scale factor (gtk#1505, open since 2018).

**Workaround Ya-Bro must implement:** `global = window_origin(compositor) + content_offset(CSD/shadow) + AtspiComponent.get_extents(WINDOW)`, then convert logical to physical units per output.

| Session | Window origin source |
|---|---|
| X11 | `_NET_WM` / `XTranslateCoordinates` on the client window, minus `_GTK_FRAME_EXTENTS` for CSD apps |
| KWin Wayland | A KWin script: `workspace.stackingOrder` or `windowAdded`, then `window.clientGeometry` / `bufferGeometry` / `frameGeometry`, `pid`, `internalId`, pushed to Ya-Bro via `callDBus`. Load it at runtime with `org.kde.KWin /Scripting loadScript`. Match the AT-SPI app to the window by **PID** plus title. |
| GNOME | A Shell extension exporting `Meta.Window.get_frame_rect()` / `get_buffer_rect()` / `get_pid()` over D-Bus |
| Sway | `swaymsg -t get_tree` (`rect`, `window_rect`, `pid`) |
| Hyprland | `hyprctl clients -j` (`at`, `size`, `pid`) |

Ambiguity remains for multiple windows per PID, and for popups and menus, which are separate surfaces whose position is compositor-controlled. Calibrate with a screenshot plus vision when confidence is low.

### V2: GTK4 on X11 for an overlay (item 2)

**Verdict: feasible, with Xlib or ctypes for the stacking hints. Click-through is reliable if you stop GtkWindow from resetting the input region. GTK's X11 backend has been deprecated since GTK 4.18 (removal planned for GTK 5), and all 13 `GdkX11Surface` methods are marked deprecated in 4.18 docs, though they still work.**

**Stacking:**
- GTK4 removed `gtk_window_set_keep_above`, type hints and public override-redirect. Remaining tools:
  - `GdkX11.X11Surface.get_xid()`, `set_skip_taskbar_hint()`, `set_skip_pager_hint()`;
  - raw Xlib (python-xlib) on that XID: `_NET_WM_STATE` = `_NET_WM_STATE_ABOVE` + `_NET_WM_STATE_STICKY` + `_NET_WM_STATE_SKIP_TASKBAR`, and `_NET_WM_WINDOW_TYPE_NOTIFICATION` or `_NET_WM_WINDOW_TYPE_DOCK`.
- Set them on the realized but unmapped window, or send a `_NET_WM_STATE` ClientMessage after mapping.
- Override-redirect via `XChangeWindowAttributes` before map is possible in principle but unverified with GTK4.
- In KWin (all sessions), override-redirect windows are "unmanaged", which puts them in `OverlayLayer`. Dock and keep-above go to `AboveLayer`; notification type goes to `NotificationLayer`. All of these sit below the active fullscreen window (`ActiveLayer`) except unmanaged and OSD windows. Source: KWin `src/window.cpp` `belongsToLayer`.

**Click-through:**
- `gdk_surface_set_input_region(surface, cairo.Region())`, with an **empty** region, not `None`:
  - on X11 it becomes `XShapeCombineRectangles(..., ShapeInput, 0 rects)`;
  - on Wayland it becomes `wl_surface_set_input_region` (applied at the next commit);
  - `None` means "whole surface reactive".
- **Known trap (source-verified):** `GtkWindow`'s `update_realized_window_properties()` calls `gdk_surface_set_input_region()` itself whenever the window is client-decorated with a client shadow, overwriting yours. Fixes:
  - use `window.set_decorated(False)`, which avoids CSD and shadow;
  - re-apply the region after `map` and after each size allocation.
- This matches user reports that setting the region in `size_allocate` vs `realize` behaves differently under XWayland (GNOME Discourse, 2024-03).
- **Transparency:** RGBA needs a compositing manager (KWin, Mutter, picom). Without one, the window is opaque black.

### V3: gtk4-layer-shell (item 3)

**Verdict: use it for KWin Wayland, Sway, Hyprland, COSMIC and Mir. It is impossible on GNOME/Mutter and on any X11 session.**

**Support** (README, v1.3.0, 2025-10-29):
- supported: wlroots compositors, Smithay compositors (COSMIC), Mir, KDE Plasma Wayland;
- not supported: GNOME-on-Wayland and X11.

Protocol versions seen (wayland-explorer dumps): KWin 6.7 v5, Hyprland 0.57 v5, Sway 1.11 v4, niri v5, Mutter none. The first KWin version to support layer-shell is unverified (circa Plasma 5.20).

**Python:**
- Run `from ctypes import CDLL; CDLL('libgtk4-layer-shell.so')` **before** `import gi`. The alternative is `LD_PRELOAD=.../libgtk4-layer-shell.so`.
- The reason: the library shims libwayland symbols, so it must load before `libwayland-client` (see `linking.md`).
- Typelib: `Gtk4LayerShell 1.0`.

**API and protocol notes:**
- `init_for_window`, `set_layer(OVERLAY)`, `set_anchor` (all four edges for a fullscreen overlay), `set_exclusive_zone(-1 or 0)` (no space reservation), `set_keyboard_mode(NONE)`, `set_monitor(Gdk.Monitor)`.
- Keyboard interactivity `on_demand` arrived in protocol v4.
- Use **one layer surface per output**, since `get_layer_surface` binds to a `wl_output` or null (compositor's choice). Re-create surfaces on monitor hotplug.

**Click-through:** combine it with an empty input region; this works on Sway, niri and KWin (unverified on KWin by test). On Hyprland, `EXCLUSIVE` keyboard mode plus an empty region still steals the pointer (discussion #14136, 2026). Keep `NONE`.

**KWin stacking:** layer-shell OVERLAY maps to `OverlayLayer`, the topmost layer, so it sits **above fullscreen windows** (source-verified, `layershellv1window.cpp`). On Plasma ≤ 6.7, layer-shell was not in KWin's restricted list, so no `.desktop` permission was needed.

**Flatpak:** works as long as the compositor exposes layer-shell to sandboxed clients. KWin 6.8 restricts only the listed privileged globals, and layer-shell is not one of them.

### V4: Input observation on Wayland (item 4)

**Verdict: there is no global key or mouse observation for a normal app on any Wayland compositor. Design struggle detection around AT-SPI object events, not input hooks.**

**Legacy AT-SPI keystroke listeners** (`Atspi.register_keystroke_listener`, the `DeviceEventController`):
- On X11 these are fed by XInput2 in the registry daemon, so they work for all apps.
- On Wayland the X11 device backend is absent. Since at-spi2-core 2.55.90 / 2.56 (GNOME 48), `AtspiDevice` can use the compositor's `org.freedesktop.a11y.KeyboardMonitor`. 2.59.90 added `key-pressed`/`key-released` and a `pointer-moved` signal via `PointerLocator`.

**The KeyboardMonitor is allow-listed:**
- **Mutter:** `meta-a11y-manager.c` uses `meta_dbus_access_checker_allow_sender(..., "org.gnome.Orca.KeyboardMonitor")` on both the KeyboardMonitor and PointerLocator skeletons. Unsafe mode is the only bypass.
- **KWin:** `src/a11ymanager.cpp`, present in v6.8.0, absent in v6.7.0. Key methods check that the caller owns `org.gnome.Orca.KeyboardMonitor` ("Only screen readers are allowed to use this interface"). `QueryPointer` is *not* gated in KWin; it returns the PID plus a buffer-relative pointer position.
- **Name-squatting:** claiming that bus name would technically pass, but it breaks Orca and is clearly against intent. **Do not.**

**Other routes:**
- **GTK4 apps:** whether they still emit legacy per-app keystroke events to listeners on Wayland is unverified. Do not rely on it.
- **X11:** XRecord or XInput2 raw events give global keys and pointer. Both work but are deprecated paths.
- **evdev/libinput:** reading `/dev/input/event*` needs the `input` group. That is equivalent to a system-wide keylogger, so reject it.
- **KWin XWayland bridge:** the "Legacy X11 App Support" setting (Plasma 5.27+; "always allow input emulation" option from 6.4) lets an XWayland client receive keys typed into Wayland windows. Options are all keys, modifiers only, or none, and the user must opt in. A fallback, not a plan.

**AT-SPI events usable as struggle signals** (all work on Wayland because they are object events, not input):

| Event | Use as a signal | Caveats |
|---|---|---|
| `window:activate` / `window:deactivate` | app switching, ping-pong between windows | Reliable for GTK and Qt. GTK4 maps it via its `GtkAtSpiRoot`. |
| `object:state-changed:showing` / `:visible` on `ROLE_MENU`, `ROLE_POPUP_MENU` | menu open/close loops | GTK4 popovers are separate surfaces. Qt menus are reliable. |
| `object:state-changed:focused` / `focus:` | focus thrash | High volume |
| `object:children-changed:add` with `ROLE_DIALOG` or `ROLE_ALERT`; `window:create` | error dialogs appearing | Read the dialog text through the `Text` interface |
| `object:text-changed:insert` / `:delete` | typing then deleting (rough undo proxy) | Very high volume. Throttle. |
| `object:property-change:accessible-name` | title changes (e.g. "*unsaved") | |

Repeated undo can only be inferred, from text-changed deletes or from menu item activation via `object:state-changed:selected` (unverified for shortcuts). There is no key event.

**Reliability caveats:**
- event floods from Chromium/Electron and LibreOffice;
- at-spi2-core 2.60.1 started hiding "unresponsive applications";
- 2.60.5 fixed listeners being wrongly deregistered.

Pin at-spi2-core ≥ 2.60.5 where possible.

### V5: Input injection (item 5)

**Verdict: use the RemoteDesktop portal plus libei on GNOME and KDE (consent dialog, restore token), wlr virtual-pointer/keyboard on Sway and Hyprland, and XTest on X11. Use KWin fake-input only as a Plasma 6.8+ unsandboxed fast path.**

**RemoteDesktop portal** (interface version 2):
- `ConnectToEIS` and `persist_mode` / `restore_token` were added in v2. The frontend supports restore from 1.17.0 (2023-08).
- Backends:
  - `xdg-desktop-portal-gnome` has `connect_to_eis` from **45.0** (absent in 44.0);
  - `xdg-desktop-portal-kde` from **v6.1.0** (absent in v6.0.0).
- Once EIS is connected, the `Notify*` D-Bus methods return errors.
- `NotifyPointerMotionAbsolute` and EIS absolute devices take coordinates relative to a **ScreenCast stream**. So absolute motion needs a combined RemoteDesktop+ScreenCast session; map with the `mapping_id` stream property (1.17.2+).
- Whether absolute EIS motion visibly moves the real cursor is unverified. It is expected to, because the compositor injects it as pointer motion.

**Persistence:**
- `persist_mode=2` gives a token that is **single-use**. Store the new token from every Start response.
- Known KDE flakiness: "Persistence in the remote desktop portal fails sporadically" (KDE bug 490988). Early 6.1.x lacked the "allow restoring" checkbox (Gentoo bug 945888).

**KWin `org_kde_kwin_fake_input`:**
- Through Plasma 6.7 it is restricted: the client must list it in `X-KDE-Wayland-Interfaces` in a `.desktop` file matching its executable path. `KWIN_WAYLAND_NO_PERMISSION_CHECKS=1` disables the check.
- From Plasma 6.8 (MR 6057, merged 2026-06-18, milestone 6.8) restricted globals are hidden **only from sandboxed clients**: Flatpak or Snap, detected via systemd `app-flatpak-*` / `snap.*` units.
- So a deb or pipx Ya-Bro can bind fake-input with no prompt. It is a KDE-private protocol.

**wlroots and Hyprland:**
- `zwlr_virtual_pointer_manager_v1` v2 (absolute motion supported) and `zwp_virtual_keyboard_manager_v1` v1 are present on Sway 1.11, Hyprland 0.57 and niri.
- Neither x-d-p-wlr nor x-d-p-hyprland implements RemoteDesktop. Their `.portal` files list only Screenshot, ScreenCast, GlobalShortcuts and InputCapture (Hyprland), or Screenshot and ScreenCast (wlr).

**X11 and XWayland:**
- XTest works on X11.
- Under XWayland, XTest only reaches X11 clients, unless Xwayland is started with portal/EI support. Mutter enables it when not nested; it then prompts a RemoteDesktop dialog *per X client*. The flag name (`-enable-ei-portal` vs `-enable-portal`) is unverified.
- KWin offers an "always allow input emulation" setting for XWayland apps (6.4+).

**uinput / ydotool:**
- Needs write access to `/dev/uinput`: root, or a udev rule plus a group.
- It creates a system-wide virtual device that bypasses every compositor policy, and absolute positioning is awkward.
- Avoid it except as an opt-in power-user mode.

### V16: Session landscape (item 16)

**Verdict: X11 is end-of-life on both major desktops. Target KWin Wayland first, and treat X11 as a dev and LTS target.**

**KDE:**
- The KDE blog (2025-11-26) said Plasma 6.8 would be Wayland-exclusive, with X11-session support "into early 2027" via 6.7 bugfix releases.
- KWin was split into `kwin_x11` / `kwin_wayland` in 6.4.
- D. Edmundson (2026-06-02): 6.7 is the last release with an X11 session.
- KWin v6.8.0 was tagged 2026-10-08.

**GNOME:**
- GNOME 49 disabled the X11 session by default. GDM's ability to launch X11 sessions was reverted for 49, but GNOME Shell on X11 stayed disabled.
- Mutter's X11 code was disabled in 49 and dropped in GNOME 50. XWayland remains (GNOME blog, 2025-06; Fedora "WaylandOnlyGNOME").

**Detection:**
- `XDG_SESSION_TYPE` is `x11`, `wayland` or `tty`. `WAYLAND_DISPLAY` is set on Wayland, and `DISPLAY` is also set when XWayland is available.
- `XDG_CURRENT_DESKTOP` is `KDE`, `GNOME`, `sway`, `Hyprland`, `COSMIC` or similar, possibly colon-separated, e.g. `ubuntu:GNOME`.
- `KDE_SESSION_VERSION=6` on Plasma 6.
- Wayland protocol detection is more reliable: enumerate `wl_registry` globals such as `zwlr_layer_shell_v1`.
- Fall back to D-Bus names: `org.kde.KWin`, `org.gnome.Shell`.

---

## 3. Per-topic sections

### 3.1 AT-SPI coordinates (item 1)

**How it works**
- `AtspiComponent.get_extents(coord_type)` makes a D-Bus `GetExtents(u)` call into the app's toolkit bridge.
- `coord_type` is SCREEN=0, WINDOW=1 or PARENT=2. at-spi2-core#72 (2022) notes that the meaning of WINDOW was historically underspecified.

**Strengths**
- WINDOW and PARENT are consistent within GTK4.
- On X11, SCREEN is correct for GTK3, Qt and Firefox. Chromium on X11 is unverified.

**Limits (known broken or flaky)**
- **GTK4 SCREEN is `(0,0)` on all backends.** See V1.
- **On Wayland, nobody can provide SCREEN.** The "window" origin may include CSD shadows, and GTK's accessible root excludes them, so expect a ~15 px error (gtk#8242).
- **Popovers and menus** are separate surfaces:
  - GTK3 on Wayland reports them at `(0,0)` (gtk#5149, open);
  - GTK4 popover extents ignored the popover position (gtk#5148).
- **`GetAccessibleAtPoint`** with WINDOW coords was broken in GTK4 (gtk#6448, closed 2024-02).
- **Scaling:**
  - GTK3 reports logical px (gtk#1505, open);
  - Mutter's pointer locator ignores scale (mutter#4833).
- **`object:bounds-changed`** events report WINDOW-space values (at-spi2-core#72), so you cannot detect window moves from them. Poll the compositor for window geometry instead.

**What Ya-Bro should do**
- Always query WINDOW coords.
- Keep a per-desktop "window geometry provider" (KWin script, Shell extension, sway/hypr IPC, X11 EWMH).
- Add per-toolkit content offsets:
  - GTK CSD: `bufferGeometry` vs `clientGeometry` difference, or `_GTK_FRAME_EXTENTS` on X11;
  - Qt with server-side decorations: `clientGeometry`.
- Verify with a cheap screenshot diff when the target is small.
- Track confidence and show a softer highlight (bigger ring) when uncertain.

### 3.2 GTK4 overlay window on X11 (item 2)

**How it works**
- A `Gtk.Window` with `set_decorated(False)`, a transparent CSS background and a Cairo or GtkSnapshot drawing area. On realize:
  - take `GdkX11.X11Surface.get_xid()`;
  - set EWMH atoms via python-xlib;
  - call `set_skip_taskbar_hint(True)` and `set_skip_pager_hint(True)`;
  - call `surface.set_input_region(cairo.Region())`.
- Size it to the full virtual screen, or use one window per monitor, which is more robust with mixed DPI.
- Do **not** maximize or fullscreen it. Mutter drops `wm_state_above` from TOP when the window is maximized (`meta_window_get_default_layer`). KWin puts fullscreen in ActiveLayer.

**Strengths**
- Works with any EWMH WM and, through XWayland, on GNOME Wayland as a fallback.
- XShape input regions are honoured by Xorg and Xwayland.

**Limits (known broken or flaky)**
- All `GdkX11Surface` methods are deprecated (4.18). The X11 backend gets no new features and is slated for removal in GTK 5.
- GtkWindow overwrites your input region when CSD shadows are active (source-verified).
- XWayland input-shape timing quirks have been reported (Discourse 2024-03).
- Without a compositor there is no alpha.
- **XWayland on fractional scaling:**
  - KWin offers "apply scaling themselves" vs "scaled by the system" (blurry);
  - Mutter's `xwayland-native-scaling` is unverified.
- **Stacking under KWin:** a keep-above or notification window still goes *under* an active fullscreen window. Only unmanaged (override-redirect) or OSD-type windows go above it.

**What Ya-Bro should do**
- X11 path:
  - `_NET_WM_WINDOW_TYPE_NOTIFICATION` + `_NET_WM_STATE_ABOVE|STICKY|SKIP_TASKBAR|SKIP_PAGER`;
  - an empty input region re-applied after map;
  - one window per monitor.
- Prototype override-redirect via Xlib for fullscreen apps on X11 (unverified).

### 3.3 gtk4-layer-shell (item 3)

**How it works**
- A shim library intercepts GTK's xdg-shell calls and speaks `zwlr_layer_shell_v1` (protocol v5: layers background/bottom/top/overlay; keyboard_interactivity none/exclusive/on_demand(v4); `set_exclusive_edge` v5).

**Strengths**
- True overlay above fullscreen on KWin.
- No WM hints needed.
- Per-output anchoring.

**Limits (known broken or flaky)**
- No GNOME support and no X11 support.
- Load-order requirement: `CDLL` before `gi`, or `LD_PRELOAD`.
- The library's own AI policy rejects AI-written production patches. That matters only if we contribute upstream.
- Hyprland pointer-capture quirk with `EXCLUSIVE` keyboard mode.
- A surface per output must be managed on hotplug.

**What Ya-Bro should do**
- Use it as the primary overlay on KWin Wayland, Sway, Hyprland and COSMIC:
  - `Layer.OVERLAY`, all edges anchored, `exclusive_zone = -1`, `KeyboardMode.NONE`, empty input region;
  - when the speech bubble needs clicks, temporarily set the input region to the bubble rect, and switch keyboard mode to `ON_DEMAND` only if text entry is needed.
- Check support at runtime with `Gtk4LayerShell.is_supported()` (C: `gtk_layer_is_supported()`). The default keyboard mode is `NONE`.

### 3.4 Input observation (item 4)

See V4.

**How it works**
- X11: XInput2/XRecord or AT-SPI DEC.
- Wayland: compositor a11y D-Bus (Orca-only), or nothing.

**Strengths**
- AT-SPI object events work everywhere AT-SPI works.

**Limits (known broken or flaky)**
- Keystroke-level data is unavailable on Wayland.
- `/dev/input` access is a security problem.
- KDE's XWayland key forwarding is opt-in, and mouse forwarding is limited (KDE bugs 488837, 513604).

**What Ya-Bro should do**
- Signals:
  - AT-SPI object events;
  - idle via `ext_idle_notify_v1` (KWin, Sway, Hyprland), `org.gnome.Mutter.IdleMonitor` (GNOME), or XScreenSaver/XSync on X11;
  - shell hooks for failing commands;
  - screenshot diffs at low frequency.
- Never ship an evdev reader.

### 3.5 Input injection (item 5)

See V5.

**What Ya-Bro should do**
- Show the cursor animation in the overlay ("ghost cursor") *before* injecting. Then inject one absolute move plus click.
- Store the RemoteDesktop restore token and refresh it on every start.
- On KDE 6.8+ unsandboxed, prefer fake-input (no dialog).
- On Sway and Hyprland use virtual-pointer: bind to the target output and use `motion_absolute` with an extent equal to the output size.

### 3.6 Screen capture (item 6)

**How it works**

| Session | Mechanism | Consent and access |
|---|---|---|
| X11 | `XGetImage`/XShm on the root window (python-xlib, or `mss`) | None needed |
| Wayland, portal | **Screenshot portal:** `interactive` hint since v2; `target` (screen/window/area/active-window) since v3, added in x-d-p 1.21.2 (2026-05) | Frontend 1.15+ asks permission once and stores it (`permission_store_checked`). **GNOME** backend honours the stored permission. **KDE** backend does a full-screen grab with no dialog when non-interactive (source: `screenshot.cpp`). |
| Wayland, portal | **ScreenCast portal** (v6) + PipeWire | `persist_mode` / `restore_token` (single-use tokens) |
| KWin | `org.kde.KWin.ScreenShot2` D-Bus (v5) | Through **6.7** requires the caller's `.desktop` to list `X-KDE-DBUS-Restricted-Interfaces=org.kde.KWin.ScreenShot2`, else `NoAuthorized`. **6.8.0** removed `checkPermissions`. |
| GNOME Shell | `org.gnome.Shell.Screenshot` | Restricted to the portal (and unsafe mode) since GNOME 41. gnome-screenshot itself was dropped from the allow-list in GNOME 49 (secondary sources). |
| wlroots | `zwlr_screencopy_manager_v1` v3 / `ext_image_copy_capture` | Direct, no prompt |

`org.kde.KWin.ScreenShot3` on master adds `hide-caller-windows` (default true), which is ideal for excluding our overlay. Whether it is in 6.8.x or only in 6.9 is unverified; 6.8.0 has no ScreenShot3 file.

**Strengths**
- Portals are uniform across desktops.
- ScreenCast gives a continuous stream, which is cheap per frame once running.

**Limits (known broken or flaky)**
- Single Screenshot portal calls go through D-Bus plus a PNG file written to disk: roughly 100–500 ms (unverified estimate).
- ScreenCast needs a PipeWire consumer (GStreamer `pipewiresrc` works from Python) and a dialog on first use.
- Our own overlay appears in captures unless hidden: KWin ScreenShot3 `hide-caller-windows`, or an un-draw before capture.

**What Ya-Bro should do**
- **KDE:** ScreenShot2 (6.8+), falling back to the portal.
- **GNOME:** keep a ScreenCast session alive with persist, or use Screenshot portal calls.
- **wlroots:** screencopy.
- **X11:** XShm.
- Hide or blank the overlay during capture, or capture per window.

### 3.7 AT-SPI coverage and enablement (item 7)

**How it works**
- The a11y bus is started by `at-spi-bus-launcher` (`org.a11y.Bus.GetAddress`). Toolkits decide whether to expose a tree based on `org.a11y.Status`:
  - `IsEnabled` (general);
  - `ScreenReaderEnabled` (screen reader).
- at-spi2-core 2.61.0 changed `IsEnabled` handling: the launcher now treats a11y as enabled when ATs register event listeners, instead of relying on the gsettings key `org.gnome.desktop.interface toolkit-accessibility`.

**Per toolkit:**

| Toolkit or app | Enablement and notes |
|---|---|
| GTK3 | atk-bridge; always on when the bus exists |
| GTK4 | Native AT-SPI over D-Bus (no ATK) since 4.0; exposes when the bus exists. AccessKit backend since 4.18 for Windows/macOS. |
| Qt5/Qt6 | Exposes when `IsEnabled` **or** `ScreenReaderEnabled` is true, or `QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1`. `QT_ACCESSIBILITY=1` is obsolete. Upstream discourages always-on for performance. |
| Chromium/Electron | Reads `ACCESSIBILITY_ENABLED=1/0`, then `org.a11y.Status.IsEnabled`, then the GNOME gsettings key. `--force-renderer-accessibility` forces it on; `--disable-renderer-accessibility` disables auto-detection. Chromium calls desktop-Linux a11y "not really supported". |
| Firefox | ATK; enabled by the a11y bus. `accessibility.force_disabled` pref (1 = off). `GNOME_ACCESSIBILITY=1` forcing (unverified for current versions). |
| VS Code | `editor.accessibilitySupport: "on"` exposes the editor text |
| Java | java-atk-wrapper (distro package) |
| LibreOffice | VCL gtk3 plugin exposes ATK. Trees are deep and events heavy. |
| GIMP 3.0 / Inkscape 1.x | GTK3. GIMP 2.10 is GTK2: poor coverage (unverified detail). |
| Flatpak apps | Flatpak gives sandboxed apps a filtered a11y bus via xdg-dbus-proxy by default (unverified detail). A Flatpak'd **AT** (Ya-Bro) needs full a11y bus access: `--talk-name=org.a11y.Bus` plus `--no-a11y-bus`, the combination reported working in KDE bug 452132. |
| Snap | The `desktop-legacy` interface grants AT-SPI access (snapcraft forum) |

**Strengths**
- One API across GTK, Qt, Chromium, Firefox and LibreOffice.
- Python binding: `gi.repository.Atspi` 2.0. at-spi2-core also ships Python overrides; 2.57+ added more.

**Limits (known broken or flaky)**
- Deep trees and slow synchronous D-Bus queries. A full walk of LibreOffice or Chromium can take seconds.
- Cache: `org.a11y.atspi.Cache` gained a `Ready` signal in 2.61.90. `ATSPI_NO_CACHE` disables GetItems.
- Stale objects: unresponsive apps are hidden since 2.60.1.
- `pyatspi` is legacy. Use `gi.repository.Atspi` directly.
- Re-entrancy: 2.61.0 added `atspi_set_g_main_loop_reentrancy`.
- Electron apps often expose nothing unless forced.
- Enabling a11y slows Qt and Chromium apps.

**What Ya-Bro should do**
- Register at least one event listener, which itself flips `IsEnabled` on new at-spi2-core.
- Set `org.a11y.Status.IsEnabled=true` on older versions.
- Never set `ScreenReaderEnabled`: it changes app behaviour and Orca-like heuristics.
- Use the Collection interface (`GetMatches`) instead of tree walks.
- Run AT-SPI in a worker thread or process with timeouts.
- Document per-app enablement: Electron flag, VS Code setting.

### 3.8 GNOME overlay options (item 8)

**How it works**
- Native Wayland clients on Mutter cannot request always-on-top:
  - Mutter has no layer-shell;
  - wayland-protocols MR 369 ("make a toplevel surface always on top") was **closed** 2024-12-19;
  - xdg-pip MR 132 is still open (updated 2026-10).
- Users can set "Always on Top" via the window menu, but apps cannot.
- **Options:**
  - **(a) GNOME Shell extension.** Draws the pointer, ring, bubble and avatar as St/Clutter actors in the shell's top layer (`Main.layoutManager.addTopChrome` or `uiGroup`, with `reactive: false`). It exposes a session D-Bus API that Ya-Bro calls with screen rects. It can also export window geometry (`Meta.Window.get_frame_rect`, `get_buffer_rect`) and call `make_above()` on any window.
  - **(b) An XWayland GTK4 window** (`GDK_BACKEND=x11`) with `_NET_WM_STATE_ABOVE`. Mutter maps above-state X11 windows to `META_LAYER_TOP` unless maximized (source: `meta_window_get_default_layer`). XShape input works.

**Strengths**
- (a) gives pixel-perfect global coordinates, since the shell knows everything, and stays above fullscreen if added to the top chrome (unverified for fullscreen).
- (b) needs no extension.

**Limits (known broken or flaky)**
- **Extensions:**
  - must be updated for every GNOME major release (JS API churn);
  - review rules:
    - no GTK in the shell;
    - no binaries;
    - processes "MUST be spawned carefully";
    - no telemetry;
    - "Extensions must not be AI-generated";
    - clean `enable()`/`disable()`.
  - Users must install and enable it (extensions.gnome.org or a distro package).
- **XWayland window:**
  - scaling blur on fractional scaling;
  - no layer above fullscreen;
  - will go away whenever GTK drops X11 (GTK 5).

**What Ya-Bro should do**
- Ship a minimal, human-written GNOME Shell extension as "Ya-Bro Shell Helper" (overlay drawing plus window geometry plus pointer position, over D-Bus).
- ~~Fall back to the XWayland overlay when the extension is absent.~~ *Superseded 2026-11-20:* fall back to docked mode. The XWayland overlay is rejected (§3.17, ADR-0006).
- Keep the extension tiny and hand-written to pass review.

### 3.9 KWin options (item 9)

**How it works**

*KWin scripts (JS, Plasma 6):*
- **Window properties:**
  - `frameGeometry` (read-write), `clientGeometry`, `bufferGeometry` (including shadows), `pos`;
  - `keepAbove` (read-write);
  - `pid`, `resourceClass`, `internalId` (UUID), `caption`, `output`.
- **Workspace:** signals `windowAdded`, `windowRemoved`, `windowActivated`, plus `stackingOrder`.
- **Global functions:** `callDBus(...)` and `registerShortcut(...)`.
- **Loading:**
  - install with `kpackagetool6 --type=KWin/Script`;
  - or at runtime via D-Bus: `org.kde.KWin /Scripting` with `loadScript(filePath, pluginName)`, `loadDeclarativeScript`, `isScriptLoaded`, `unloadScript`, then `start()` (source: `src/scripting/scripting.h`).
- **Debug output** goes to the journal (`QT_CATEGORY=js`).

*Other KWin mechanisms:*
- **Window rules** (`kwinrulesrc`) can force keep-above, no-focus or skip-taskbar by window class or app-id.
- **`xdg_toplevel_tag_v1`** is implemented in KWin, Mutter and Hyprland. It lets rules match a stable tag. GTK4's support for setting it is unverified.
- **KWin effects** (C++ or QML) can draw over everything, but are heavyweight.
- **Other D-Bus:**
  - `org.kde.KWin.ScreenShot2`;
  - `org.freedesktop.a11y.Manager` (6.8+; keyboard methods Orca-only, `QueryPointer` open);
  - kglobalaccel.

**Strengths**
- The KWin script plus D-Bus gives exact window geometry and live move and resize events, without an extension store.
- Layer-shell OVERLAY sits above fullscreen (`OverlayLayer`).
- From 6.8, unsandboxed clients can bind privileged protocols: fake-input, `org_kde_plasma_window_management`, `zkde_screencast_unstable_v1`.

**Limits (known broken or flaky)**
- **`keepAbove`** windows sit below the active fullscreen window, in `AboveLayer` vs `ActiveLayer`.
- **Scripting API churn:** Plasma 5 used `workspace.clientList()` and `client`; Plasma 6 uses `windowList`/`stackingOrder` and `window`.
- **Plasma ≤ 6.7 needs `.desktop` permissions:**
  - `X-KDE-Wayland-Interfaces` for restricted protocols;
  - `X-KDE-DBUS-Restricted-Interfaces` for ScreenShot2.
  - The `.desktop` must match the executable path, which is fragile for pipx or venv installs.
- **Flatpak 6.8+:** restricted globals are hidden from Flatpak and Snap clients (MR 6057).

**What Ya-Bro should do**
- Ship a small KWin script ("ya-bro-geometry") that pushes window geometry, PID, active window and stacking changes to Ya-Bro's D-Bus service.
- Use layer-shell for the overlay.
- On 6.0–6.7, install a `.desktop` with both restricted-interface keys pointing at the real executable.

### 3.10 Multi-monitor, HiDPI and fractional scaling (item 10)

**How it works**
- **Wayland:**
  - clients get an integer `wl_output.scale`, or a fractional scale via `wp_fractional_scale_v1` (KWin, Mutter, Sway, Hyprland and niri all support it, per the wayland-explorer dumps);
  - GTK4 renders fractionally through viewporter (GTK ≥ 4.12/4.14, unverified exact version);
  - all Wayland surface coordinates are **logical**.
- **KWin script and compositor geometry** is in logical (global compositor) coordinates.
- **X11:**
  - one big physical-pixel root;
  - "scale" is per-toolkit: `Xft.dpi`, `GDK_SCALE` (integer), `GDK_DPI_SCALE`, `QT_SCALE_FACTOR`, `QT_SCREEN_SCALE_FACTORS`, `QT_AUTO_SCREEN_SCALE_FACTOR`.

**Strengths**
- On Wayland, the overlay (layer surface per output) and compositor geometry share logical coordinates. Only screenshots are physical.

**Limits (known broken or flaky)**
- **AT-SPI units differ per toolkit:**
  - GTK3 reports unscaled logical units even when `GDK_SCALE=2` on X11 (gtk#1505);
  - Qt reports device-independent pixels (unverified);
  - Chromium varies (unverified).
- **Mutter pointer-locator coordinates** ignore scale (mutter#4833).
- **XWayland apps under fractional scaling:** either blurry (scaled by the compositor) or "apply scaling themselves" (KWin setting). Their coordinates then disagree with native windows.
- **Mixed-DPI multi-monitor on X11** has no correct answer for GTK (single scale).

**What Ya-Bro should do**
- Normalize everything to compositor logical coordinates.
- Keep a per-output scale table (Wayland: `Gdk.Monitor.get_scale()`; X11: Xrandr plus `Xft.dpi`).
- Convert screenshot pixels to logical coordinates using the output scale.
- Run a calibration test per toolkit at startup: highlight a known widget and compare against a screenshot.

### 3.11 Browser integration (item 11)

**How it works**
- **Chrome DevTools Protocol (CDP):** `--remote-debugging-port`.
  - **Since Chrome 136** the switch is ignored for the *default* user-data-dir. It needs `--user-data-dir=<non-default>`, which means a separate profile without the user's logins (Chrome blog, 2025-03).
  - Any local process can connect to the port, so it is a security exposure.
- **Firefox:**
  - experimental CDP was disabled by default in 129 and **removed in 141**;
  - use **WebDriver BiDi** (`--remote-debugging-port`) or Marionette;
  - both require starting Firefox with remote flags, and the browser shows a "remote control" indicator.
- **WebExtension plus native messaging** (Firefox and Chromium): the extension reads the DOM (`getBoundingClientRect`, `window.screenX/Y`, `devicePixelRatio`, `outerHeight - innerHeight`) and talks to a host binary registered via a JSON manifest:
  - Chromium: `~/.config/google-chrome/NativeMessagingHosts/`;
  - Firefox: `~/.mozilla/native-messaging-hosts/`;
  - Flatpak browsers need extra sandbox holes (unverified detail).

**Strengths**
- The extension works in the user's real profile.
- The DOM gives semantic targets.

**Limits (known broken or flaky)**
- **On Wayland, `window.screenX/Y` is 0 or meaningless**, since clients don't know their position. Combine viewport-relative rects with compositor window geometry plus the browser chrome offset.
- The chrome offset (`outerHeight - innerHeight`) varies with toolbars, CSD and fullscreen.
- Coordinates come in CSS px × `devicePixelRatio` (includes page zoom) and must be converted to logical compositor px.
- Iframes need offsets accumulated across frames.
- The Chrome 136 restriction rules out attaching to the user's main profile via CDP.

**What Ya-Bro should do**
- Ship a WebExtension (MV3 for Chromium, MV3/MV2 for Firefox) plus a native-messaging host.
- Send viewport-relative rects and the page zoom.
- Ya-Bro adds the window geometry (compositor) plus the content-area offset. Learn the offset from AT-SPI: the browser's document frame accessible `ROLE_DOCUMENT_WEB` WINDOW extents give the viewport origin.
- Use CDP or BiDi only for a dedicated "Ya-Bro browser profile" in Do-it mode.

### 3.12 Terminal integration (item 12)

**How it works**
- **VTE** (GNOME Terminal, Ptyxis, Tilix) and **Konsole** expose the terminal as an AT-SPI `ROLE_TERMINAL` with a `Text` interface. You can read the visible buffer and get `text-changed` events. Reliability on large scrollback is unverified.
- **Semantic prompts (OSC 133 A/B/C/D)** mark prompt, command and output plus the exit status:
  - Konsole documents "semantic shell integration";
  - kitty, WezTerm and foot support it;
  - VTE once just ignored OSC 133 (GNOME bug 783710). Current VTE support is unverified.
- **Shell hooks** work with any terminal:
  - bash `PROMPT_COMMAND` / `trap DEBUG`;
  - zsh `precmd`/`preexec`;
  - fish `fish_postexec`.
- **Terminal APIs:** kitty remote control (`kitten @`), `wezterm cli`, `tmux` control mode / `capture-pane`. A separate document covers these in depth.

**Strengths**
- Shell hooks give exact command, exit code and duration, with no screen scraping.

**Limits (known broken or flaky)**
- AT-SPI terminal text is noisy and has no semantic structure.
- OSC 133 support is uneven.
- Hooks require a user opt-in snippet in the rc files.

**What Ya-Bro should do**
- Provide an opt-in shell snippet (bash, zsh, fish) that reports `cmd`, `exit`, `cwd` and `duration` over a Unix socket.
- Use AT-SPI terminal text as a fallback context source.

### 3.13 Sandboxing: Flatpak and Snap (item 13)

**How it works and limits** (what changes inside Flatpak):

| Need | Flatpak status |
|---|---|
| Read other apps' AT-SPI | Needs `--talk-name=org.a11y.Bus` and an unfiltered a11y bus (`--no-a11y-bus` + host bus); unverified defaults. Flathub reviewers may push back. |
| Overlay, KWin | Layer-shell works (not restricted) |
| Overlay, GNOME | The extension must be installed on the host separately. XWayland needs `--socket=x11`/`fallback-x11`. |
| Privileged KWin protocols (fake-input, window management, screencast) | **Blocked** for Flatpak on Plasma 6.8+ (`isSandboxed()` by systemd unit name). Before 6.8 they needed `X-KDE-Wayland-Interfaces` via the security-context app-id. |
| KWin ScreenShot2 D-Bus | Needs `--talk-name=org.kde.KWin`. Authorization through 6.7 relied on the `.desktop`; in 6.8, D-Bus checks are gone, but Flatpak's D-Bus proxy still needs the talk-name. |
| Portals | Native and designed for this. The new "entitlements" system (x-d-p 23.x docs) gates portals for sandboxed apps; host apps get all. |
| Global hotkeys | GlobalShortcuts portal (KDE 5.27+, GNOME 48+, Hyprland). kglobalaccel needs `--talk-name=org.kde.kglobalaccel`. |
| `/dev/uinput`, `/dev/input` | Needs `--device=all`. Do not use it. |
| X11 socket | `--socket=x11` for the X11 overlay path |
| KWin scripting D-Bus | `--talk-name=org.kde.KWin` |
| GNOME Shell extension D-Bus | `--talk-name=` our extension's bus name |

**Snap:**
- the `desktop-legacy` interface grants AT-SPI;
- KWin 6.8 treats Snap like Flatpak (`snap.*` units are sandboxed);
- classic confinement avoids this, but needs store approval (unverified).

**What Ya-Bro should do**
- The primary distribution should be **unsandboxed**: deb/rpm, pipx, or AppImage (AppImage is unsandboxed, so it counts as a host app).
- Offer Flatpak as a "reduced capability" build: portals only, a11y bus hole, no KWin privileged protocols.

### 3.14 Audio stack (item 14)

**How it works**
- PipeWire is the default sound server on current Fedora, Ubuntu, Debian and Arch desktops (unverified per distro). `pipewire-pulse` provides the PulseAudio protocol and `pipewire-alsa` the ALSA plugin.
- **Python capture and playback options:**
  - `sounddevice` (PortAudio → ALSA → pipewire-alsa, or PortAudio's PulseAudio backend in newer versions, unverified);
  - GStreamer (`pipewiresrc`/`pipewiresink` or `pulsesrc`/`pulsesink`; also handles Opus and resampling);
  - `pw-cat`;
  - `python-pipewire` bindings (immature, unverified).
- **Echo cancellation:** `libpipewire-module-echo-cancel` with the default `aec/libspa-aec-webrtc` library:
  - creates "Echo Cancellation Source/Sink" nodes;
  - `monitor.mode` captures the default sink's monitor instead of creating a sink;
  - `aec.args` passes WebRTC options (`webrtc.*`, documented only in `aec-webrtc.cpp`);
  - `node.latency` is tunable (example `1024/48000` ≈ 21 ms);
  - also loadable as the Pulse module `module-echo-cancel` via pipewire-pulse.

**Strengths**
- System-level AEC that works for any app, with no need to embed WebRTC.

**Limits (known broken or flaky)**
- AEC quality issues reported when mic and speakers are on different devices (pipewire#2165, 2023).
- Some users report no audio with the webrtc module loaded (pipewire#3766).
- Loading a module means editing user PipeWire config (`~/.config/pipewire/pipewire.conf.d/`). That is a persistent-config change needing user consent.
- In Flatpak, audio goes through the Pulse socket (`--socket=pulseaudio`). Fine.

**What Ya-Bro should do**
- Use GStreamer (or sounddevice) against the default devices.
- Offer to install an echo-cancel drop-in config, with explicit user consent, and select "Echo Cancellation Source" as the mic.
- Also implement in-app half-duplex fallback: mute the mic while TTS plays.

### 3.15 Global hotkey (item 15)

**How it works**
- **X11:** `XGrabKey` on the root window. It conflicts if another client already grabbed the key.
- **GlobalShortcuts portal** (interface v2; frontend since 1.16.0, 2022-12):
  - **KDE** backend since Plasma **5.27** (file present in x-d-p-kde v5.27.0, absent in v5.26.0);
  - **GNOME** since **48** (`globalshortcuts.c` present in x-d-p-gnome 48.0, absent in 47.0);
  - **Hyprland** (x-d-p-hyprland);
  - **not** x-d-p-wlr.
  - The user confirms or edits bindings in a dialog.
- **KDE kglobalaccel D-Bus:** `org.kde.kglobalaccel`, register a component plus action, then the `globalShortcutPressed` signal. Works without a dialog for unsandboxed apps (unverified detail).
- **KWin script:** `registerShortcut()`.
- **Sway/Hyprland:** config `bindsym`/`bind` that runs `ya-bro --toggle` (IPC).

**Strengths**
- The portal is a uniform API on KDE, GNOME and Hyprland.

**Limits (known broken or flaky)**
- A GNOME 48 setup dialog issue was reported (Discourse "Issue with Global Shortcuts Setup Popup in Gnome 48").
- The portal requires an app-id; host apps need the host app registry (x-d-p 1.19.4+) or a matching `.desktop` file.
- Sway has no portal.

**What Ya-Bro should do**
- Portal first.
- kglobalaccel fallback on KDE.
- `XGrabKey` on X11.
- Document compositor-config binds for Sway, Hyprland and niri.
- Register via `org.freedesktop.host.portal.Registry` with our app-id.

### 3.16 Session detection (item 16)

See V16.

**Detection order:**
1. `XDG_SESSION_TYPE`, `WAYLAND_DISPLAY`, `DISPLAY`.
2. `XDG_CURRENT_DESKTOP` (split on `:`), plus `DESKTOP_SESSION` and `KDE_SESSION_VERSION`.
3. Probe Wayland globals (`zwlr_layer_shell_v1`, `org_kde_kwin_fake_input`, `zwlr_virtual_pointer_manager_v1`).
4. Probe D-Bus names (`org.kde.KWin`, `org.gnome.Shell`, `org.freedesktop.portal.Desktop` + interface `version` properties).
5. Check sandboxing: `/.flatpak-info` exists, or the `SNAP` env var.

**Pick capability backends from probed features, not from desktop names.** Desktop names lie, e.g. `XDG_CURRENT_DESKTOP=ubuntu:GNOME`, or KDE under a custom session.


### 3.17 GNOME 50 specifics for a GNOME-first build (added 2026-11-20)

Added after the maintainer chose GNOME first. "Local" means probed on the maintainer's machine: Ubuntu 26.04.1, GNOME Shell 50.1, Wayland, 2026-11-20.

**What a normal (non-extension) client can and cannot do on GNOME 50**

| Capability | Status | Evidence |
|---|---|---|
| Window list / geometry via `org.gnome.Shell.Introspect.GetWindows` | **denied**: `AccessDenied: GetWindows is not allowed` | local `gdbus call` |
| `org.gnome.Shell.Eval` | **off**: returns `(false, '')` without unsafe mode | local |
| Shell screenshot D-Bus | portal-only since GNOME 41 | §3.6 |
| Idle time `org.gnome.Mutter.IdleMonitor` (`/org/gnome/Mutter/IdleMonitor/Core`, `GetIdletime`, watches) | **works** | local (`(uint64 53,)`) |
| Extensions control `org.gnome.Shell.Extensions` | `ListExtensions`, `GetExtensionInfo`, `GetExtensionErrors`, `EnableExtension`, `DisableExtension`, `ReloadExtension`, `ExtensionStateChanged`; `UserExtensionsEnabled = true` | local `gdbus introspect` |
| Mutter services on the bus | `RemoteDesktop`, `ScreenCast`, `InputCapture`, `DisplayConfig`, `IdleMonitor` | local `busctl --user list`. Direct use of Mutter RemoteDesktop/ScreenCast without the portal: access rules unverified. Use the portals. |
| Display layout | `layout-mode = 1` (logical); `org.gnome.mutter experimental-features = ['scale-monitor-framebuffer', 'xwayland-native-scaling']` | local `DisplayConfig.GetCurrentState`, `gsettings` |

**GNOME Shell extension as bridge + overlay** (design in ADR-0023)
- **Format.** ES modules since GNOME 45. `metadata.json` `shell-version` lists major versions only (`"50"`), and the shell refuses unlisted versions unless `disable-extension-version-validation` is set (default false). `session-modes` defaults to `user`: the extension is disabled on lock and re-enabled on unlock. https://gjs.guide/extensions/overview/anatomy.html
- **Stacking (source-read, `js/ui/layout.js` on `gnome-50`).**
  - `addChrome()` inserts below `global.top_window_group`.
  - `addTopChrome()` adds "above all windows, including popups".
  - `trackFullscreen` defaults to `false`. Only `trackFullscreen: true` actors (the panel) hide over fullscreen.
  - The screen shield uses `addChrome`, so top chrome could cover the lock screen. This is one more reason for `user`-only session mode.
- **Input.** The GNOME 50 `layout.js` no longer computes a stage input region. Input follows Clutter picking, so `reactive: false` actors should be click-through (source-read, unverified by test).
- **Fullscreen direct scanout** may skip painting chrome. `global.compositor.disable_unredirect()` exists (moved from `Meta` in GNOME 48). Whether it is needed on 50 is unverified.
- **Geometry.** `Meta.Window.get_frame_rect()` (visible edge) and `get_buffer_rect()` (includes client-side shadows), plus `get_pid`, `get_gtk_application_id`, `get_sandboxed_app_id` (Flatpak/Snap), `get_wm_class`, `get_window_type`, `is_fullscreen`, `get_transient_for`, `get_stable_sequence`, and the signals `position-changed`, `size-changed` and `unmanaged`. `protocol_to_stage_rect` converts XWayland protocol coordinates. Monitors come from `Main.layoutManager.monitors`, the pointer from `global.get_pointer()`. https://gnome.pages.gitlab.gnome.org/mutter/meta/class.Window.html
- **Popups.** Whether `xdg_popup` menus (GTK4 popovers, Qt menus) appear as `Meta.Window` with usable rects is unverified.
- **D-Bus export** from GJS: `Gio.DBusExportedObject.wrapJSObject(xml, obj).export(Gio.DBus.session, path)` plus `Gio.bus_own_name`. Standard GJS; the exact review stance on extensions owning bus names is unverified (the guidelines do not mention D-Bus).
- **API churn per release** (gjs.guide port guides):
  - 48: `Clutter.Image` → `St.ImageContent`; `disable_unredirect` etc. → `global.compositor`; `CursorTracker` via `global.backend`; St `vertical` deprecated.
  - 49: `Meta.Rectangle` → `Mtk.Rectangle`; `ClickAction`/`TapAction` → `ClickGesture`/`LongPressGesture`; `get_maximized()` removed; X11 off, so `--nested` is gone in favour of `--devkit`.
  - 50: X11 bits removed (`restart` signals, `RunDialog._restart`), `holdKeyboard`/`releaseKeyboard` removed.
  - 51: async `disable()` throws; St `vertical` removed; direct `key-press-event` signals deprecated; `pointerWatcher.js` removed; `makeProxyWrapper()` results need `new`.
- **EGO review** (https://gjs.guide/extensions/review-guidelines/review-guidelines.html):
  - "Extensions must not be AI-generated". This covers unnecessary code, inconsistent style, imaginary APIs and "comments serving as LLM prompts".
  - No binaries or libraries. Processes "MUST be spawned carefully". No telemetry.
  - Everything created in `enable()` is destroyed in `disable()`, and nothing is created in the constructor.
  - These rules apply to EGO distribution only, not to local installs.
- **Install and reload.**
  - A local extension lives in `~/.local/share/gnome-shell/extensions/<uuid>/`, where the directory name must equal the UUID, and is enabled with `gnome-extensions enable <uuid>`.
  - On Wayland, JS cannot be unloaded and the shell cannot be restarted while logged in. New or changed extension code needs a logout/login, or a nested shell. https://gjs.guide/extensions/development/debugging.html
  - Ubuntu 26.04 also ships system extensions in `/usr/share/gnome-shell/extensions/` (ubuntu-dock, ding, tiling-assistant, appindicators: local).
- **Nested dev session.** `dbus-run-session gnome-shell --devkit --wayland` on GNOME ≥ 49 (`--nested` on ≤ 48). The devkit viewer comes from `mutter-dev-bin` ("Mutter Development Kit", Ubuntu universe 50.1, not installed locally). `gnome-shell --help` 50.1 lists `--devkit`, `--headless`, `--virtual-monitor WxH[@R]`, `--wayland`, `--no-x11` and `--debug-control`.
- **CI.** Schneegans' gnome-shell-pod runs the shell under Xvfb/X11, with images up to GNOME 47, so it does not work for 49+. GitHub's ubuntu-24.04 image has GNOME 46. Plan for `gnome-shell --headless --wayland --virtual-monitor` inside an `ubuntu:26.04` container (invocation unverified). https://github.com/Schneegans/gnome-shell-pod

**Actuation on GNOME 50**
- Installed locally: xdg-desktop-portal 1.21.1, xdg-desktop-portal-gnome 50.0, libei/libeis 1.5.0.
- RemoteDesktop portal + `ConnectToEIS`: consent dialog. Persist with `persist_mode` / `restore_token` on `RemoteDesktop.SelectDevices` (not `ScreenCast.SelectSources`). Tokens are single-use; store the new one after `Start`. https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html ; field report https://github.com/agent-sh/computer-use-linux/pull/188
- Absolute motion needs a linked ScreenCast stream. Virtual-source streams were reported to reject absolute positions with "Invalid position" (https://github.com/flatpak/xdg-desktop-portal/issues/2077).
- Whether injected absolute motion visibly moves the cursor on GNOME 50 is unverified.
- AT-SPI actions need no consent and stay the primary path.
- An extension could inject in-process through a Clutter virtual input device. Ya-Bro does not do this, because it bypasses consent (ADR-0023 §11).

**Screen capture on GNOME 50**
- Screenshot portal: permission is stored once by the x-d-p frontend (§3.6). The `target` option (window/area) arrived in x-d-p 1.21.2, and Ubuntu 26.04 has **1.21.1**, so we capture full screen and crop locally.
- ScreenCast portal + PipeWire for continuous capture.
- The extension never exports capture.

**AT-SPI on GNOME 50 / Ubuntu 26.04**
- at-spi2-core is **2.60.4**, older than the 2.61.0 change that treats registered listeners as enabling a11y. `org.a11y.Status.IsEnabled` is `false` and `org.gnome.desktop.interface toolkit-accessibility` is `false` (local).
- First run must set `toolkit-accessibility` (persistent) after consent. `IsEnabled` alone does not survive logout.
- Never set `ScreenReaderEnabled`, which would change Orca and app behaviour. Orca 50.3 is installed but not running.
- **Ptyxis 50.1** is the default terminal (`/usr/share/xdg-terminal-exec/ubuntu-xdg-terminals.list` → `org.gnome.Ptyxis.desktop`). It is GTK4 with `libvte-2.91-gtk4`.
  - Its key `org.gnome.Ptyxis enable-a11y` defaults to `false` upstream ("Currently experimental feature to send accessibility information to screen readers").
  - Ubuntu sets it to `true` in `10_ptyxis.gschema.override` (local).
  - GNOME Terminal 3.58 (GTK3 VTE) is also installed.
- **Firefox 160 and Chromium 158 are Snaps.** Firefox's `desktop-legacy` plug (AT-SPI access) is connected (local `snap connections`). Chromium still needs `--force-renderer-accessibility` (§3.7).
- GTK4/libadwaita apps expose AT-SPI natively once the bus is up. Qt needs `QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1` or `IsEnabled` (§3.7).

**Idle, focus, shortcuts**
- Idle: `org.gnome.Mutter.IdleMonitor` (works, above).
- Focus: the extension's `global.display` `notify::focus-window`, or AT-SPI `window:activate`.
- Global shortcuts:
  - GlobalShortcuts portal (x-d-p-gnome ≥ 48) with `Activated`/`Deactivated`. Whether `Deactivated` fires on key release on GNOME, as hold-to-talk needs, is unverified.
  - Extension key bindings (`Main.wm.addKeybinding` with a GSettings schema shipped in the extension) fire on press, with no dialog. Use them for the stop key.

**Docked fallback (extension missing, disabled or erroring)**
- A normal GTK4 window shows the step text plus a cropped Screenshot-portal capture with the target circled. There is no live ring and no window geometry (Introspect is denied).
- The XWayland keep-above overlay is not used. It fails when the window is maximized, sits below fullscreen, the scaling mapping under `xwayland-native-scaling` is unverified, and GTK's X11 backend is deprecated.

---

## 4. Open questions to test empirically (prototype checklist)

1. **GTK4 on X11:**
   - Does the empty input region survive resize and remap with `set_decorated(False)`?
   - Does an override-redirect set via Xlib before map work?
2. **KWin 6.8:**
   - Is the layer-shell OVERLAY plus empty input region click-through over a fullscreen video?
   - Can a pipx-installed Python process bind `org_kde_kwin_fake_input` without a `.desktop` file?
3. **Per-toolkit WINDOW-coordinate offset** vs KWin `clientGeometry`/`bufferGeometry`: GTK3 CSD, GTK4 CSD, Qt6 with SSD, Chromium, Firefox. Run at 100%, 125% and 200% scale.
4. **RemoteDesktop with EIS on GNOME 50 (first) and Plasma 6.8:**
   - Does absolute motion move the visible cursor?
   - How reliable is restore-token reuse across reboot?
5. **GTK4 apps on Wayland:** does any legacy AT-SPI keystroke event reach a non-Orca listener?
6. **Screenshot latency:**
   - portal vs ScreenShot2 vs a kept-alive ScreenCast;
   - an XShm baseline on X11.
7. **GNOME 50 extension (S1):**
   - Are `reactive: false` top-chrome actors click-through for Wayland and XWayland clients?
   - Does the ring stay visible over a fullscreen video, or is `disable_unredirect()` needed?
   - Are `xdg_popup` menus listed as `Meta.Window`, and with which rect?
   - Per toolkit: is WINDOW extents relative to `frame` or `buffer`?
   - Does `gnome-extensions enable` work without re-login for a UUID installed during the session?

---

## 5. Sources

**Protocols and portal specs**
- xdg-desktop-portal repo (HEAD 2026-11-19): `data/org.freedesktop.portal.{RemoteDesktop,ScreenCast,Screenshot,GlobalShortcuts,InputCapture}.xml`, `NEWS.md`, `doc/entitlements.rst`, `data/org.freedesktop.host.portal.Registry.xml`. Repo: https://github.com/flatpak/xdg-desktop-portal. Docs: https://flatpak.github.io/xdg-desktop-portal/
- wlr-layer-shell XML: https://gitlab.freedesktop.org/wlroots/wlr-protocols/-/raw/master/unstable/wlr-layer-shell-unstable-v1.xml
- wayland-protocols MR 369 (always-on-top, closed): https://gitlab.freedesktop.org/wayland/wayland-protocols/-/merge_requests/369
- wayland-protocols MR 132 (xdg-pip, open): https://gitlab.freedesktop.org/wayland/wayland-protocols/-/merge_requests/132
- wayland-protocols MR 238 (toplevel tag, merged): https://gitlab.freedesktop.org/wayland/wayland-protocols/-/merge_requests/238
- Compositor protocol dumps (wayland-explorer data): https://github.com/vially/wayland-explorer/tree/main/src/data/compositors

**KDE / KWin**
- KWin source (master 2026-11-20; tags v6.0.0, v6.4.0, v6.6.0, v6.7.0, v6.8.0): https://invent.kde.org/plasma/kwin. Files read:
  - `src/wayland_server.cpp`
  - `src/wayland/clientconnection.cpp`
  - `src/a11ymanager.cpp`
  - `src/plugins/screenshot/screenshotdbusinterface2.cpp` and `screenshotdbusinterface3.cpp`
  - `src/window.cpp`
  - `src/effect/globals.h`
  - `src/layershellv1window.cpp`
  - `src/wayland/layershell_v1.cpp`
  - `src/scripting/scripting.h`
- KWin MR 6057 "Skip announcing restricted interfaces only to sandboxed clients" (merged 2026-06-18, milestone 6.8): https://invent.kde.org/plasma/kwin/-/merge_requests/6057
- xdg-desktop-portal-kde (`remotedesktop.cpp` at v6.0.0/v6.1.0; `globalshortcuts.cpp` at v5.26/v5.27; `screenshot.cpp`): https://invent.kde.org/plasma/xdg-desktop-portal-kde
- KWin scripting API: https://develop.kde.org/docs/plasma/kwin/api/ and https://develop.kde.org/docs/plasma/kwin/
- "Going all in on a Wayland future" (2025-11-26): https://blogs.kde.org/2025/11/26/going-all-in-on-a-wayland-future/
- D. Edmundson, last X11 release (2026-06-02): https://planet.kde.org/david-edmundson-2026-06-02-ex-11-prepping-for-plasmas-last-x11-supported-release/
- KDE bug 490988 (RemoteDesktop persistence flaky): https://bugs.kde.org/show_bug.cgi?id=490988
- Gentoo bug 945888 (no restore checkbox): https://bugs.gentoo.org/945888
- KDE bug 452132 (Flatpak a11y bus flags): https://bugs.kde.org/show_bug.cgi?id=452132
- Legacy X11 App Support discussions: https://discuss.kde.org/t/remote-control-requested-still-an-issue/24733/16, https://bugs.kde.org/show_bug.cgi?id=488837, https://bugs.kde.org/show_bug.cgi?id=513604
- Konsole semantic shell integration: https://docs.kde.org/trunk_kf6/en/konsole/konsole/semantic-shell-integration.html

**GNOME / GTK / Mutter / AT-SPI**
- GTK source (main, 4.25.2): https://gitlab.gnome.org/GNOME/gtk. Files read:
  - `gtk/a11y/gtkatspiutils.c`
  - `gtk/a11y/gtkatspicomponent.c`
  - `gtk/gtkwindow.c` (`update_realized_window_properties`)
  - `gdk/x11/gdksurface-x11.c`
  - `gdk/wayland/gdksurface-wayland.c`
- GTK issues:
  - https://gitlab.gnome.org/GNOME/gtk/-/issues/5896
  - https://gitlab.gnome.org/GNOME/gtk/-/issues/6343
  - https://gitlab.gnome.org/GNOME/gtk/-/issues/5148
  - https://gitlab.gnome.org/GNOME/gtk/-/issues/5149
  - https://gitlab.gnome.org/GNOME/gtk/-/issues/6448
  - https://gitlab.gnome.org/GNOME/gtk/issues/1505
  - https://gitlab.gnome.org/GNOME/gtk/-/issues/8242
- GTK docs:
  - https://docs.gtk.org/gdk4/method.Surface.set_input_region.html
  - https://docs.gtk.org/gdk4-x11/class.X11Surface.html
- GTK X11 deprecation: https://blog.gtk.org/2025/02/01/whats-new-in-gtk-winter-2025-edition/
- GTK4 input-region thread: https://discourse.gnome.org/t/gtk4-non-rectangular-window-with-gtk4-under-linux/19817
- Accerciser MR 33 (GTK4 screen coords): https://gitlab.gnome.org/GNOME/accerciser/-/merge_requests/33
- Mutter source (main): https://gitlab.gnome.org/GNOME/mutter. Files read:
  - `data/dbus-interfaces/org.freedesktop.a11y.xml`
  - `src/backends/meta-a11y-manager.c`
  - `src/backends/meta-dbus-access-checker.c`
  - `src/core/window.c` (`meta_window_get_default_layer`)
- Mutter issues:
  - https://gitlab.gnome.org/GNOME/mutter/-/issues/2074
  - https://gitlab.gnome.org/GNOME/mutter/-/issues/3280
  - https://gitlab.gnome.org/GNOME/mutter/-/issues/4833
- at-spi2-core NEWS (2.55.90 → 2.62.0): https://gitlab.gnome.org/GNOME/at-spi2-core/-/blob/main/NEWS
- at-spi2-core issues:
  - https://gitlab.gnome.org/GNOME/at-spi2-core/-/issues/72
  - https://gitlab.gnome.org/GNOME/at-spi2-core/-/issues/158
  - https://gitlab.gnome.org/GNOME/at-spi2-core/-/issues/232
- Orca Mouse Review on GNOME 50 thread (2026): https://discourse.gnome.org/t/mouse-review-is-hit-and-miss/34949
- Newton update (2024-06): https://blogs.gnome.org/a11y/
- xdg-desktop-portal-gnome (`remotedesktop.c` at 44.0/45.0; `globalshortcuts.c` at 47.0/48.0; `screenshot.c`): https://gitlab.gnome.org/GNOME/xdg-desktop-portal-gnome
- GNOME 48 developer notes (global shortcuts): https://release.gnome.org/48/developers/
- GNOME X11 session removal: https://blogs.gnome.org/alatiera/2025/06/08/the-x11-session-removal/, https://fedoraproject.org/wiki/Changes/WaylandOnlyGNOME
- GNOME Shell screenshot API restriction: https://gitlab.gnome.org/GNOME/gimp/-/issues/7591, https://gitlab.gnome.org/GNOME/gtk/-/issues/4283
- GNOME extension review guidelines: https://gjs.guide/extensions/review-guidelines/review-guidelines.html
- GNOME Shell `js/ui/layout.js` (gnome-50): https://gitlab.gnome.org/GNOME/gnome-shell/-/blob/gnome-50/js/ui/layout.js
- Mutter `Meta.Window` API: https://gnome.pages.gitlab.gnome.org/mutter/meta/class.Window.html
- gjs.guide anatomy, creating, debugging: https://gjs.guide/extensions/overview/anatomy.html, https://gjs.guide/extensions/development/creating.html, https://gjs.guide/extensions/development/debugging.html
- gjs.guide port guides 48–51: https://gjs.guide/extensions/upgrading/gnome-shell-48.html (…-49, -50, -51)
- `mutter-dev-bin` (Ubuntu resolute): https://packages.ubuntu.com/resolute/mutter-dev-bin
- gnome-shell-pod: https://github.com/Schneegans/gnome-shell-pod
- Portal absolute-motion issue: https://github.com/flatpak/xdg-desktop-portal/issues/2077

**Layer shell, wlroots, Hyprland**
- gtk4-layer-shell README, `linking.md`, `examples/simple-example.py`, `include/gtk4-layer-shell.h` (v1.3.0): https://github.com/wmww/gtk4-layer-shell
- Hyprland discussion #14136 (empty input region still captures the pointer): https://github.com/hyprwm/Hyprland/discussions/14136
- x-d-p-hyprland `hyprland.portal`: https://github.com/hyprwm/xdg-desktop-portal-hyprland
- x-d-p-wlr `wlr.portal`: https://github.com/emersion/xdg-desktop-portal-wlr

**Qt, browsers, other toolkits**
- Qt `atspiadaptor.cpp`: https://code.qt.io/cgit/qt/qtbase.git/plain/src/gui/accessible/linux/atspiadaptor.cpp
- Qt env vars and accessibility: https://doc.qt.io/qt-6/qaccessible.html, https://bugs.gentoo.org/853820
- QTBUG-86780 (no global positioning on Wayland): https://bugreports.qt.io/browse/QTBUG-86780
- Chromium Linux a11y detection (`atk_util_auralinux.cc`): https://sources.debian.org/src/chromium/139.0.7258.127-2/ui/accessibility/platform/atk_util_auralinux.cc and https://www.chromium.org/developers/accessibility/linux-accessibility
- Chrome 136 remote debugging change: https://developer.chrome.com/blog/remote-debugging-port
- Firefox CDP removal: https://fxdx.dev/cdp-retirement-in-firefox/, https://fxdx.dev/firefox-webdriver-newsletter-141/
- Mozilla bug 1790717 (no screen coordinates on Wayland): https://bugzilla.mozilla.org/show_bug.cgi?id=1790717
- Xwayland EI/portal option MR: https://gitlab.freedesktop.org/xorg/xserver/-/merge_requests/1170
- Snap AT-SPI (`desktop-legacy`): https://forum.snapcraft.io/t/accessibility-support-failing-for-desktop-snaps-on-recent-distro-releases/27274
- VTE OSC 133 history: https://bugzilla.gnome.org/show_bug.cgi?id=783710

**Audio**
- PipeWire echo-cancel module: https://docs.pipewire.org/page_module_echo_cancel.html
- PipeWire issues: https://gitlab.freedesktop.org/pipewire/pipewire/-/issues/2165, https://gitlab.freedesktop.org/pipewire/pipewire/-/issues/3766
