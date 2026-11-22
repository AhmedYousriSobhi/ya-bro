# ADR-0004: Window geometry and the screen-coordinate pipeline (CompositorBridge)

- Status: Proposed
- Date: 2026-11-20
- Issue: #13
- S1 measurement (2026-11-22, headless GNOME 50, see [S1 findings](../research/spikes/S1-gnome-extension.md)): the window origin for AT-SPI `WINDOW` extents is the **frame** rect for GTK4 and libadwaita and the **buffer** rect for GTK3, both within 0.6 px at 100% and 150%. XWayland GTK3 needed frame + (0, 37). Qt6 and Firefox are not yet measured.
- Depends on: ADR-0002, ADR-0003, ADR-0023

> **Amended for GNOME-first (2026-11-20).**
> - The first `CompositorBridge` is the **GNOME Shell extension** ([ADR-0023](0023-gnome-shell-extension-bridge.md)). The KWin script is second (v0.2). EWMH is CI-only.
> - On GNOME, `org.gnome.Shell.Introspect.GetWindows` returns AccessDenied (checked locally), so the extension is the only route to window origins.
> - The extension reports `frame` and `buffer` rects in stage coordinates. These are logical pixels when Mutter `layout-mode` is logical (as on the maintainer's machine). Whether a toolkit's WINDOW extents are relative to `frame` or `buffer` is measured per toolkit in S1.
> - S1 now runs on GNOME 50 first.

## Context
Show-me mode has to draw a ring around a real widget. AT-SPI's `Component.get_extents(SCREEN)` was assumed to give that rectangle, but it does not:

| Toolkit | Platform | What SCREEN returns |
|---|---|---|
| GTK4 | every backend, X11 included | `(0,0)`. Confirmed in `gtkatspiutils.c` on main. |
| Qt | Wayland | Collapses to roughly window-relative values (unverified empirically) |
| GTK3 | Wayland | Window-relative |
| Firefox | Wayland | No screen coordinates; bug 1790717 closed as a known limitation |
| GTK3 | X11 | Unscaled under HiDPI (gtk#1505) |

The compositor-side `org.freedesktop.a11y.PointerLocator` gives only a surface-relative pointer, and it has open bugs:
- client-side-decoration shadow offsets of about 15 px (gtk#8242, at-spi2-core#232);
- it ignores scaling (mutter#4833).

Details: [linux-platform.md V1](../research/linux-platform.md).

WINDOW coordinates are consistent within each toolkit. So a correct screen rectangle needs three things: the window's origin from whoever manages windows, the client-side-decoration (CSD) offset, and the output scale.

## Decision drivers
- Pointing correctness. The SPEC target is 80% of steps correctly pointed, and a wrong ring is worse than none.
- It has to work on GNOME Wayland first, then KWin Wayland and wlroots, without root.
- Low latency. The ring must follow window moves within one or two frames of the user noticing.
- Map an AT-SPI application to a compositor window reliably.

## Options considered
| Option | For | Against |
|---|---|---|
| **Trust AT-SPI SCREEN** | Zero work | Wrong for GTK4 everywhere and for all toolkits on Wayland (verified). Unacceptable. |
| **Vision-only localisation (screenshot + grounding model)** | Toolkit-agnostic | 1–6 s latency, cost, error-prone on icons (ScreenSpot-Pro icon accuracy 20–40 points below text). Needs capture consent on Wayland. |
| **CompositorBridge for window origin + AT-SPI WINDOW extents (recommended)** | Exact, cheap (D-Bus), event-driven on window move. Accerciser MR 33 does the same for GTK4. Each compositor has a supported way to do it: KWin scripting, Shell extension, sway/hyprland IPC, EWMH. | One implementation per compositor. Window↔app matching is ambiguous for multi-window apps. Popups and menus are separate surfaces positioned by the compositor. |
| **PointerLocator-based calibration** | Standard API | Gated (Mutter allow-lists Orca) or buggy. Gives a pointer position, not a window origin. |

## Decision
1. **Formula.** `screen_rect = window_origin(bridge) + csd_offset + extents(WINDOW)`, then convert logical to physical units per output (`scale` from the bridge). Work in **logical (layout) pixels** end-to-end, and let the overlay backend handle device scale.
2. **`CompositorBridge` interface.** It is a new peer of the five SPEC interfaces:
   - `windows()` lists windows with `id, pid, app_id/resource_class, title, frame_rect, buffer_rect, client_rect, output, scale, is_active`;
   - change signals: `window_added`, `window_removed`, `geometry_changed`, `activated`;
   - `pointer_position()` (optional).
3. **Implementations:**

   | Order | Session | Implementation | Notes |
   |---|---|---|---|
   | 1 (MVP) | GNOME 48–51 Wayland | Ya-Bro **Shell extension** `Bridge1` API exporting `Meta.Window.get_frame_rect()`, `get_buffer_rect()`, `get_pid()`, app id, type, monitor, scale, stacking, focus ([ADR-0023](0023-gnome-shell-extension-bridge.md) §3) | Shared with the overlay (ADR-0006). Needs install + one re-login. |
   | 2 (v0.2) | KWin Wayland | **KWin script** loaded at runtime via `org.kde.KWin /Scripting loadScript`, using `workspace.windowList()` / `windowAdded`, `window.frameGeometry` / `clientGeometry` / `bufferGeometry` / `pid` | Pushed to core with `callDBus`. No install step and no review. |
   | best-effort | Sway | `swaymsg -t get_tree` plus the `subscribe` window event | |
   | best-effort | Hyprland | `hyprctl clients -j` plus socket2 events | |
   | CI only | X11 (Xvfb) | EWMH `_NET_CLIENT_LIST`, `XTranslateCoordinates`, minus `_GTK_FRAME_EXTENTS` | Test fixture, not a product target |
4. **Matching an AT-SPI app to a window:**
   - match by **PID** first (AT-SPI `Application.get_process_id()` against the bridge's pid);
   - then by title equality with the AT-SPI frame `name`;
   - then by size: the extents of the AT-SPI frame should equal the window client size within ±2 px.

   If the match is still ambiguous, ask the bridge for the active window and assume that one, because guidance targets the focused window.
5. **CSD offset.** Use `buffer_rect` versus `frame_rect` from the bridge, or `_GTK_FRAME_EXTENTS` on X11. Cache it per window.
6. **Popups and menus.** GTK4 popovers and Qt menus are separate surfaces.
   - Their AT-SPI WINDOW extents are relative to their own surface, so the bridge must report popup surfaces too. On GNOME, whether Mutter lists `xdg_popup` surfaces as `Meta.Window` (type `DROPDOWN_MENU`/`POPUP_MENU`) with usable rects is unverified (S1). KWin lists popups as windows (`window.popupWindow`) (unverified for all toolkits).
   - When that fails, perception (ADR-0005) falls back to an OCR or vision crop near the parent widget, and the step says "in the menu that just opened" with no ring if confidence stays low (ADR-0007).
7. **Self-check calibration.** In debug mode, or on low confidence, perceiver captures the window (where consent exists) and checks that the widget's text or edges appear inside the computed rectangle. The measured offset is stored per app and toolkit, and the overlay applies it as a correction.

## Consequences
- **Positive:**
  - A single, testable pipeline for all sessions.
  - The X11/Wayland difference shrinks to "which bridge".
  - It is cheap, since it is event-driven rather than polled.
- **Negative:**
  - GNOME requires the extension even for Show-me mode, not only for the overlay, and the extension must be ported each GNOME release (ADR-0023 §8).
  - KWin scripting API changes between Plasma versions (5 → 6 renamed `clientList` to `windowList`), so the bridge must support versions.
- **Risks:**
  - Fractional scaling mismatches between toolkits (GTK3 reports unscaled extents).
  - Unverified Chromium/Electron behaviour on Wayland.

  Both are covered by S1 measurements.

## Validation plan
Spike **S1**, the highest-risk spike (ADR-0022):
- Setup: a fixture GTK3/GTK4/Qt6 app with 20 known widgets, plus Firefox showing the workbench page.
- Sessions: GNOME 50 Wayland (MVP gate), then KWin Wayland 6.6 (v0.2).
- Targets also include one XWayland app, because `xwayland-native-scaling` is on.
- Scales: 100%, 125%, 150% and 200%.
- Ground truth: screenshot plus the widget's known pixel colour.
- **Go:** median ≤ 4 px and p95 ≤ 12 px for in-window widgets, and ≥ 70% of popup/menu items located within 12 px.
- **No-go** on popups alone means those steps are presented without a ring. That is acceptable. No-go on in-window widgets blocks Show-me mode on that session.

## Revisit if
- Upstream makes AT-SPI SCREEN correct on Wayland (Newton or similar).
- A standard Wayland protocol for "window geometry for assistive technologies" appears.
- KWin or GNOME restrict scripting or extensions in a way that breaks the bridge.

## Sources
- [docs/research/linux-platform.md](../research/linux-platform.md): V1, §3.1, §1 matrix
- GTK source: https://gitlab.gnome.org/GNOME/gtk/-/raw/main/gtk/a11y/gtkatspiutils.c
- GTK issues: https://gitlab.gnome.org/GNOME/gtk/-/issues/6343 ; https://gitlab.gnome.org/GNOME/gtk/-/issues/1505
- Firefox: https://bugzilla.mozilla.org/show_bug.cgi?id=1790717
- KWin scripting API: https://develop.kde.org/docs/plasma/kwin/api/ (Plasma 6 window API)
- Mutter `Meta.Window`: https://gnome.pages.gitlab.gnome.org/mutter/meta/class.Window.html
- Accerciser MR 33 (GTK4 screen coords workaround), cited in linux-platform.md
