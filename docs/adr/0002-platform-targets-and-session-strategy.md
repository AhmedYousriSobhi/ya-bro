# ADR-0002: Platform targets and session strategy (GNOME Wayland as reference, KWin second, X11 CI-only)

- Status: Proposed (maintainer-decided 2026-11-20; becomes Accepted when spike S1 passes)
- Date: 2026-11-20
- Issue: #13
- Refines: SPEC.md §5, PRIOR_ART "Recommended wedge"
- Depends on: none. ADR-0004, 0006, 0007, 0009, 0010, 0016, 0022 and 0023 build on this one.

## History
The first version of this ADR (same day, PR #14) chose **KWin Wayland (Plasma ≥ 6.6) as reference**. It left the maintainer's dogfooding desktop open (README Q1: (a) install Plasma, (b) nested KWin, (c) GNOME-first). Its reasoning was that KWin is the cheapest Wayland target: layer-shell overlay, runtime KWin scripts with no install or review, and fake-input/ScreenShot2 opening up in 6.8.

**What changed:** the maintainer chose option (c). GNOME on Wayland is the desktop they use every day, and it is Ubuntu's default, so it is where proactive mode actually gets dogfooded. The KWin facts below are still true. They now describe the **second** target.

## Context
1. **X11 sessions are end-of-life on both major desktops.**
   - Mutter dropped its X11 session code in GNOME 50.
   - Plasma 6.8 (KWin v6.8.0, 2026-10-08) has no X11 session.
   - Sources: [linux-platform.md §V16](../research/linux-platform.md), https://blogs.kde.org/2025/11/26/going-all-in-on-a-wayland-future/
2. **X11 does not give GTK4 apps correct pointing coordinates either.** GTK4 returns `(0,0)` for `ATSPI_COORD_TYPE_SCREEN` on every backend (`gtkatspiutils.c`). Every session needs a window origin from the compositor (ADR-0004).
3. **The maintainer's machine** (checked 2026-11-20):
   - Ubuntu 26.04.1 LTS, GNOME Shell 50.1, Wayland session via gdm3, `layout-mode` logical, fractional scaling on.
   - a11y bus `IsEnabled = false`, at-spi2-core 2.60.4.
   - Default terminal Ptyxis 50.1. Firefox 160 and Chromium as Snaps.
   - xdg-desktop-portal 1.21.1, x-d-p-gnome 50.0, libei 1.5.0.
4. **What GNOME 50 allows a normal client** (details in [ADR-0023](0023-gnome-shell-extension-bridge.md) and [linux-platform.md §3.17](../research/linux-platform.md)):
   - no layer-shell and no always-on-top request;
   - `org.gnome.Shell.Introspect.GetWindows` returns AccessDenied, and `Shell.Eval` is off;
   - Shell screenshot D-Bus is portal-only;
   - KeyboardMonitor is Orca-only.
   - It does allow: `org.gnome.Mutter.IdleMonitor`, the RemoteDesktop/ScreenCast/Screenshot/GlobalShortcuts portals (consent), and AT-SPI.
   - A **GNOME Shell extension** can see every window's geometry and draw above all windows, from inside the compositor.

## Decision drivers
- The maintainer must dogfood daily on the target. Proactive mode needs real use.
- Pointing must be correct, since a wrong highlight destroys trust.
- Where the users are: GNOME is the Ubuntu and Fedora default.
- The cost and risk of each overlay/bridge path (ADR-0006, ADR-0023).
- Keep compositor-specific code behind interfaces, so a second desktop is a port.

## Options considered
| Option | For | Against |
|---|---|---|
| **A. KDE X11 first (original SPEC)** | XTest, XRecord and XGetImage are cheap | The session is gone in Plasma ≥ 6.8 and GNOME ≥ 50. GTK4 still needs WM origin math. Not the maintainer's desktop. |
| **B. KWin Wayland first (previous decision)** | `gtk4-layer-shell` overlay above fullscreen. KWin script geometry with no install or review. fake-input/ScreenShot2 open in 6.8. | Not the maintainer's desktop. Ubuntu 26.04 ships Plasma 6.6, where the privileged protocols are still restricted. Dogfooding of proactive mode slips. |
| **C. GNOME Wayland first (chosen)** | The maintainer's daily desktop. Ubuntu/Fedora default and the largest audience. One extension supplies both geometry and overlay in the same coordinate space. Portals are mature (x-d-p-gnome ≥ 48 has GlobalShortcuts, ≥ 45 has `ConnectToEIS`). | A Shell extension is required (GJS, in-compositor, ported every release). First install needs a re-login. EGO rejects AI-generated code (local install unaffected). Every capture/injection needs portal consent. |
| **D. wlroots (Sway/Hyprland) first** | No-consent layer-shell, virtual input and screencopy | Small audience, not the maintainer's desktop |

## Decision
1. **Reference platform: GNOME 50 on Wayland** (Ubuntu 26.04 LTS). All MVP acceptance criteria (SPEC §8) are measured here.
2. **The GNOME Shell extension is the CompositorBridge *and* the overlay on GNOME** ([ADR-0023](0023-gnome-shell-extension-bridge.md)). Without it, Ya-Bro runs in docked mode with no live ring (ADR-0006).
3. **Second target: KWin Wayland (Plasma ≥ 6.6), in v0.2.** It uses the KWin script bridge (ADR-0004) and the `gtk4-layer-shell` overlay (ADR-0006), driven by the same draw protocol. wlroots/Hyprland are best-effort on the same layer-shell backend.
4. **X11 is CI-only.** Xvfb stays as the cheapest headless display for AT-SPI and core tests (ADR-0016). There is no X11 product target and no X11 acceptance gate. No feature may depend on an X11-only capability.
5. **GNOME support window.** Reference 50. Support 48–51 where CI is green (ADR-0023 §8). Older than 48 is out of scope.
6. **Detect at runtime, pick by capability.** Probe D-Bus names (`org.gnome.Shell`, our extension's name, `org.kde.KWin`) and Wayland globals (`zwlr_layer_shell_v1`) rather than trusting `XDG_CURRENT_DESKTOP` alone (it reads `ubuntu:GNOME` here). `broctl doctor` prints the chosen backends (ADR-0017).
7. **Development loop:** a nested `gnome-shell --devkit` session for extension work (ADR-0023 §10). Dogfood in the real session.

## Consequences
- **Positive:**
  - The maintainer dogfoods the product, proactive mode included, from week 1.
  - Pointing uses the compositor's own geometry, and the ring and the geometry share one coordinate space.
  - The stop key lives in the compositor and works even if core hangs.
- **Negative:**
  - The riskiest code (GJS in `gnome-shell`) comes first.
  - The first install and every extension update need a logout.
  - Do-it injection and screen capture always need portal consent on GNOME. No silent fast path exists, unlike KWin 6.8.
- **Risks:**
  - Extension API churn every six months (49 and 51 both broke APIs we could use).
  - An extension crash takes down the Wayland session.
  - KWin support arrives later, so KWin-specific bugs surface later.

## Validation plan
- **Spike S1 (ADR-0022): GNOME extension bridge + overlay** on GNOME 50 Wayland at 100% and 150% scale, against GTK3, GTK4/libadwaita, Qt6, Firefox and XWayland targets.
  - **Coordinates go:** median ≤ 4 px, p95 ≤ 12 px for in-window widgets.
  - **Overlay go:** 0/1,000 clicks blocked, and the ring is visible above maximized and fullscreen windows.
  - Full criteria in ADR-0023.
- **KWin port (v0.2):** the same thresholds on KWin Wayland 6.6.

## Revisit if
- S1 is a no-go on GNOME. Then re-plan around docked mode plus vision, or around KWin-first.
- Mutter adopts layer-shell or an always-on-top protocol for clients. Then the overlay moves to GTK, and the extension shrinks to the bridge.
- GNOME restricts extensions in a way that breaks the bridge.
- An upstream fix makes AT-SPI SCREEN coordinates correct on Wayland (Newton or similar).

## Sources
- [docs/research/linux-platform.md](../research/linux-platform.md): §0, §1 matrix, V1, V3, V5, V16, §3.8, §3.17
- [ADR-0023](0023-gnome-shell-extension-bridge.md) and its sources
- GNOME X11 session removal: https://blogs.gnome.org/alatiera/2025/06/08/the-x11-session-removal/
- KDE: https://blogs.kde.org/2025/11/26/going-all-in-on-a-wayland-future/
- GTK4 SCREEN coords: https://gitlab.gnome.org/GNOME/gtk/-/raw/main/gtk/a11y/gtkatspiutils.c ; https://gitlab.gnome.org/GNOME/gtk/-/issues/6343
- KWin MR 6057: https://invent.kde.org/plasma/kwin/-/merge_requests/6057
- gtk4-layer-shell: https://github.com/wmww/gtk4-layer-shell
- EGO review guidelines: https://gjs.guide/extensions/review-guidelines/review-guidelines.html
- Local machine facts: `gnome-shell --version`, `gsettings`, `gdbus`, `dpkg -l`, `snap list`, xdg-terminal-exec lists (run 2026-11-20)
