# ADR-0006: Overlay rendering per display server and compositor

- Status: Proposed
- Date: 2026-11-20
- Issue: #13 (implements #3)
- Depends on: ADR-0002, ADR-0003, ADR-0004

## Context
The overlay draws four things:
- an **avatar** (the bro);
- a **speech bubble** with step text and buttons;
- a **highlight ring** or cut-out around the target;
- an **animated pointer** that flies to the target.

The whole screen must stay click-through except the avatar and bubble. It has to sit above normal and, ideally, fullscreen windows, on every monitor, at any scale.

Platform facts ([linux-platform.md §1, V2, V3, V8](../research/linux-platform.md)):

**KWin Wayland, Sway, Hyprland, COSMIC**
- `gtk4-layer-shell` OVERLAY layer works; on KWin it sits above fullscreen windows.
- An empty `wl_surface` input region gives click-through.
- Keyboard mode must be `NONE`; with `EXCLUSIVE`, Hyprland still grabs the pointer.
- One layer surface per output.

**X11 (GTK4)**
- No keep-above or override-redirect API.
- Set `_NET_WM_STATE_ABOVE|STICKY|SKIP_TASKBAR` plus a NOTIFICATION or DOCK type via Xlib on the GdkX11 XID.
- `set_input_region(cairo.Region())` maps to an XShape input region of 0 rectangles.
- Trap: GtkWindow overwrites the input region when it is client-side-decorated with a shadow, so call `set_decorated(False)` and re-apply after map and resize.
- Needs a compositor for alpha.
- GTK's X11 backend has been deprecated since 4.18.
- Keep-above stays below the active fullscreen window on KWin.

**GNOME/Mutter Wayland**
- Native clients cannot stay on top.
- XWayland windows with `_NET_WM_STATE_ABOVE` do stay on top, unless maximized.
- A Shell extension can draw in-shell with St/Clutter, `reactive: false`.

**Prior art**
- Clicky: a full-screen transparent `NSPanel` at screen-saver level, ignoring mouse events, on all Spaces, with Bezier pointer flight.
- Navisual: a Tauri transparent always-on-top canvas that blanks its own regions in screenshots.
- Both from [ai-tools.md §3.2](../research/ai-tools.md).
- Tour libraries: driver.js and Shepherd give the bubble UX — even-odd cut-out, Floating UI flip/shift placement, scroll-into-view, handling of missing targets ([non-ai-tools.md §6](../research/non-ai-tools.md)).

## Decision drivers
- Never steal focus or clicks.
- Smooth 60 fps animation.
- Correct placement at fractional scale and across multiple monitors.
- Readable bidi text (ADR-0019).
- An honest, visible presence (the opposite of Cluely's "invisible" overlay).
- Minimal per-compositor code.

## Options considered
| Option | For | Against |
|---|---|---|
| **One GTK4 process with per-session backends (recommended)** | One rendering codebase (GtkSnapshot or Cairo). layer-shell and Xlib hints are small backend shims. Python per ADR-0001. | GNOME needs separate in-shell drawing anyway |
| **KWin effect / script drawing (compositor-side)** | Pixel-perfect, always on top | KWin-only, C++ effects or limited QML. Effect API churn. |
| **Qt/PySide6 overlay** | `WindowTransparentForInput` is trivial | Two toolkits; no first-class layer-shell binding (ADR-0001 rejected it) |
| **GNOME: Shell extension draws everything** | The only native top-most path on Mutter Wayland; same extension supplies geometry (ADR-0004) | JS, re-test every GNOME release, extensions.gnome.org forbids AI-generated code |
| **GNOME: XWayland keep-above window** | Reuses the X11 backend | Coordinates of an XWayland surface versus Wayland windows under fractional scale are unverified. Fails if maximized. Deprecated path. |
| **Docked fallback (no pointing)** | Works anywhere: a normal window showing the step text plus a cropped screenshot with the target circled | Not "on the live app". Needs capture consent. |

## Decision
1. **`Overlay` backends:**

   | Session | Backend |
   |---|---|
   | KWin Wayland, wlroots, Hyprland, COSMIC | **`LayerShellOverlay`** |
   | X11 | **`X11Overlay`** |
   | GNOME Wayland | **`GnomeShellOverlay`**: the Shell extension draws and core sends it the same draw commands over D-Bus |
   | GNOME without the extension, or any unknown compositor | **`DockedOverlay`** |

   The XWayland keep-above path is only an experiment in spike S6, not a supported backend.
2. **Surface layout.**
   - One full-output transparent surface per monitor, re-created on hotplug.
   - The avatar and bubble get a non-empty input region; everything else stays click-through.
   - The input region is recomputed whenever the bubble moves.
   - Bridge and perception rects are in global logical coordinates. Each per-output surface subtracts its monitor's global origin (`Gdk.Monitor.get_geometry()`) before drawing, and a target that spans two outputs is drawn on both. This is a classic multi-monitor bug, so it gets a dedicated test.
   - The keyboard is never grabbed. Text input goes through a small, normal, focusable "ask" popup window that opens on avatar click or the hotkey, so typing is never routed to a full-screen surface.
3. **Drawing.**
   - GTK4 `GtkSnapshot`, or Cairo inside a `GtkDrawingArea`.
   - The ring is a rounded rectangle with a soft glow, plus an optional dimmed even-odd cut-out (driver.js style). The dimming is off by default so the user still sees context.
   - The pointer flies along a quadratic Bezier over 400–700 ms with ease-out (Clicky).
   - The bubble is placed with Floating-UI-style logic: preferred side, flip, shift to stay on the output, keep away from the target rect, mirrored for RTL (ADR-0019).
   - The bubble shows at most one short sentence plus controls: Next, Repeat, Why?, Do it, Stop.
4. **Missing or uncertain target.** If there is no rect, or confidence is low (ADR-0007):
   - show the bubble near the avatar with "it should be in the Export menu…";
   - add a dashed ring on the region if one is known;
   - never draw a confident ring on a guess.
5. **Following the target.**
   - Subscribe to bridge `geometry_changed` and AT-SPI `bounds-changed` and re-layout within one frame.
   - Hide the ring while the window is being moved or is occluded. Occlusion comes from the bridge stacking order where available.
6. **Fullscreen.** Layer-shell OVERLAY shows above fullscreen windows on KWin. On X11 a keep-above window shows below the active fullscreen window. That is accepted, and the bubble then appears as a notification-style dock.
7. **Self-exclusion from perception.** Before any capture the overlay is either hidden for one frame, or its rects are masked out of the image (Navisual pattern), so vision never sees the bro's own pointer.
8. **Accessibility of the overlay itself.** The bubble is an AT-SPI-exposed label with a live-region-like announcement, so Orca users hear steps. The overlay process is also excluded from Ya-Bro's own perception by PID.
9. **HiDPI.** Logical pixels end-to-end. GTK handles device scale and `wp_fractional_scale_v1` on Wayland. For each monitor, read `Gdk.Monitor.get_scale()` (fractional, GTK ≥ 4.14, unverified version) and the bridge's output scale, and log any mismatch.

## Consequences
- **Positive:**
  - A single Python overlay serves KDE, wlroots and X11.
  - GNOME reuses the same command protocol.
  - The bubble UX follows proven tour-library patterns.
- **Negative:**
  - The GNOME extension is a second codebase in GJS. It must be hand-reviewed by the maintainer for extensions.gnome.org, or distributed from the repo.
  - X11 cannot overlay fullscreen apps.
- **Risks:**
  - Hyprland and KWin layer-shell click-through quirks.
  - The GTK4 X11 deprecation.
  - Fractional-scale rounding giving 1–2 px ring offsets.

## Validation plan
Spike **S3** (= issue #3), on KWin Wayland 6.6 and KWin X11:
- **Click-through:** 1,000 synthetic clicks land on the app beneath, at 0 failures.
- **Avatar:** clickable.
- **Frame rate:** 60 fps pointer flight on the maintainer's laptop (i7-11800H, Intel + RTX 3050).
- **Placement:** correct on 2 monitors with mixed 100%/150% scale.
- **Fullscreen:** the overlay stays above a fullscreen window on KWin Wayland.

**Go/no-go:** failing click-through on either session blocks that backend.

## Revisit if
- Mutter adopts layer-shell or an always-on-top protocol. Then drop the extension overlay.
- GTK removes the X11 backend before X11 users are gone. Then X11 moves to a small Xlib/cairo or Qt backend.
- KWin makes layer-shell privileged.

## Sources
- [docs/research/linux-platform.md](../research/linux-platform.md): §1 matrix, V2, V3, §3 GNOME overlay options
- [docs/research/ai-tools.md](../research/ai-tools.md): §3.2 overlay patterns (Clicky, Navisual)
- [docs/research/non-ai-tools.md](../research/non-ai-tools.md): §6 tour libraries, §9 annotators (Gromit-MPX), §10 desktop pets / koverlay
- gtk4-layer-shell: https://github.com/wmww/gtk4-layer-shell
- GDK input region: https://docs.gtk.org/gdk4/method.Surface.set_input_region.html
- Hyprland discussion #14136 (cited in linux-platform.md)
- GNOME extension review guidelines: https://gjs.guide/extensions/review-guidelines/review-guidelines.html
