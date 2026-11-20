# ADR-0002: Platform targets and session strategy (KWin Wayland as reference, X11 demoted)

- Status: Proposed
- Date: 2026-11-20
- Issue: #13
- Refines: SPEC.md §5 "KDE Plasma and X11 first", PRIOR_ART "Recommended wedge"
- Depends on: none. Everything about the overlay, actuation, pointing, struggle signals and test infrastructure (ADR-0004, 0006, 0007, 0009, 0010, 0016, 0022) builds on this one.

## Context
SPEC.md says the MVP targets "KDE Plasma and X11 first" and puts Do-it mode on "X11 XTest first". The brief says not to reopen that unless there is strong evidence. There are now three independent pieces of primary-source evidence, all checked during this research:

1. **X11 sessions are end-of-life on both major desktops.**
   - KDE Plasma 6.8 (KWin v6.8.0, tagged 2026-10-08) has no X11 session. 6.7 is the last series with one. KDE announced it on 2025-11-26 and D. Edmundson confirmed it on 2026-06-02.
   - Mutter dropped its X11 session code in GNOME 50.
   - Sources: [linux-platform.md §V16](../research/linux-platform.md), https://blogs.kde.org/2025/11/26/going-all-in-on-a-wayland-future/
2. **On GTK4, X11 does not give us correct pointing coordinates either.**
   - GTK4 returns `(0,0)` for `ATSPI_COORD_TYPE_SCREEN` on every backend, X11 included. This was checked in `gtk/a11y/gtkatspiutils.c` on main: the SCREEN branch assigns `*xo = 0; *yo = 0`.
   - On Wayland, no toolkit gives correct global coordinates.
   - Either way we need a window origin from the window manager or compositor (ADR-0004). Easy pointing was most of X11's advantage, and for GTK4 apps it is gone.
3. **The maintainer's own machine cannot run an X11 desktop session today.**
   - Local check: Ubuntu 26.04.1 LTS, GNOME Shell 50.1, `XDG_SESSION_TYPE=wayland`.
   - The Ubuntu archive does offer Plasma 6.6.7 (`kwin-wayland`, `plasma-workspace`) and `kwin-x11` 6.6.4 / `plasma-session-x11`. Installing a Plasma session would therefore give the maintainer **both** KWin Wayland and KWin X11 on the same machine.

X11 is still easier in three places:
- global input observation (XRecord/XInput2);
- input injection (XTest, no consent dialog);
- screen capture (XGetImage).

LTS distros still ship X11 Plasma: Plasma 6.7 gets bugfixes into early 2027, and AlmaLinux 9 is supported to 2032.

## Decision drivers
- The maintainer must dogfood daily on the target. Proactive mode needs real use.
- Pointing must be correct, since a wrong highlight destroys trust (PRIOR_ART risk 5).
- The cost of each overlay path (ADR-0006).
- Where Linux desktops are heading over the next 2–3 years.
- Keep OS- and compositor-specific code behind interfaces (CLAUDE.md).

## Options considered
| Option | For | Against |
|---|---|---|
| **A. KDE X11 first (status quo)** | Cheapest injection (XTest), observation (XRecord) and capture; GTK4 overlay works with Xlib hints plus an empty XShape input region | The session no longer exists in Plasma ≥ 6.8 or GNOME ≥ 50. GTK4 apps still need WM origin math. The maintainer must log into a legacy session to dogfood. Builds the habit of relying on global input hooks that will not survive. |
| **B. KWin Wayland as reference, X11 as secondary/dev/LTS (recommended)** | `gtk4-layer-shell` OVERLAY sits above fullscreen windows (KWin source `layershellv1window.cpp`). A KWin script can be loaded at runtime over D-Bus to supply window geometry, with no install or review. Plasma 6.8 opens `org_kde_kwin_fake_input` and `ScreenShot2` to unsandboxed clients (KWin MR 6057). The RemoteDesktop portal with `ConnectToEIS` exists since x-d-p-kde 6.1. Matches where KDE is going. | Ubuntu 26.04 ships Plasma **6.6**, where fake-input and ScreenShot2 are still restricted behind `.desktop` permissions. No global input observation (KeyboardMonitor is Orca-only). Screen capture needs portal consent on ≤ 6.7. |
| **C. GNOME Wayland first** | It is the maintainer's current desktop, the largest user base, and the Ubuntu default | No layer-shell and no client "above" request: wayland-protocols MR 369 closed Dec 2024. Needs a **GNOME Shell extension for both overlay and window geometry**, in JS, versioned per Shell release. extensions.gnome.org review rejects AI-generated code (verified on gjs.guide). Every capability needs consent. Highest cost and risk for a first spike. |
| **D. wlroots (Sway/Hyprland) first** | Layer-shell, virtual pointer/keyboard and screencopy all exist with no consent | Small audience, not the maintainer's desktop, no RemoteDesktop portal, Hyprland click-through quirk (discussion #14136) |

## Decision
1. **Reference platform: KDE Plasma on Wayland (KWin), Plasma ≥ 6.6.** All MVP acceptance criteria (SPEC §8) are measured here first.
2. **X11 is a supported secondary backend, not the lead.** Use it for:
   - CI (Xvfb is the cheapest headless display, ADR-0016);
   - LTS users on Plasma 6.6/6.7 X11 sessions;
   - development convenience.

   No feature may depend on an X11-only capability unless it also has a Wayland plan in the same ADR.
3. **GNOME Wayland is the second desktop, via a hand-written GNOME Shell extension** (ADR-0006, ADR-0004) in v0.2, as SPEC already says. The extension is the only GNOME path to correct coordinates, so it is a perception dependency, not just an overlay nicety.
4. **wlroots and Hyprland are best-effort.** They get the layer-shell overlay and a `swaymsg`/`hyprctl` geometry bridge, with no acceptance gate.
5. **Detect the session at runtime and pick backends by capability.** Probe Wayland globals (`zwlr_layer_shell_v1`) and D-Bus names (`org.kde.KWin`, `org.gnome.Shell`) rather than trusting `XDG_CURRENT_DESKTOP` alone. `ya-bro doctor` prints the chosen backends (ADR-0017).
6. **The maintainer has to choose how to dogfood. This is open question Q1 in the README.**
   - (a) Install a Plasma 6.6 session on Ubuntu 26.04 and log into it (gives KWin Wayland and X11).
   - (b) Develop inside a nested or virtual `kwin_wayland` window on GNOME. The exact flags are unverified; to be checked in spike S1.
   - (c) Reverse the order and go GNOME-first, paying the Shell-extension cost now.

   This ADR recommends (a) for development, keeping GNOME as the daily desktop until proactive mode needs dogfooding. It does not decide (c) on the maintainer's behalf.

## Consequences
- **Positive:**
  - We design against the APIs that will exist in 2027+.
  - Pointing uses one pipeline (origin + WINDOW extents) on every session.
  - Struggle detection is designed around AT-SPI object events from day one (ADR-0010) instead of X11 key hooks.
- **Negative:**
  - Do-it mode on Wayland needs a consent dialog (portal), or Plasma 6.8 for silent fake-input.
  - Screen capture needs a portal consent on Plasma ≤ 6.7.
  - Some convenience is lost early on.
- **Risks:**
  - Ubuntu 26.04's Plasma 6.6 differs from upstream 6.8 in privileged-protocol policy, so test both.
  - If the maintainer stays on GNOME, the KDE-first order delays dogfooding of proactive mode. Mitigation: the GNOME extension spike moves earlier (ADR-0022, S6).

## Validation plan
- **Spike S1 (ADR-0022), coordinate pipeline.**
  - Setup: on KWin Wayland 6.6 and on KWin X11, run a KWin script to get the window origin, then AT-SPI WINDOW extents for GTK3, GTK4, Qt6 and Firefox targets.
  - Measure the pointing error in physical pixels at 100% and 150% scale.
  - Go: median error ≤ 4 px and p95 ≤ 12 px for top-level-window widgets.
- **Spike S6, GNOME.** A ~150-line Shell extension that exports `get_frame_rect()` over D-Bus and draws one ring. Go: the same error bounds on GNOME 50.

## Revisit if
- The maintainer picks option (c).
- A cross-desktop "always on top / overlay" Wayland protocol lands (e.g. ext-layer-shell adopted by Mutter).
- KDE re-opens an X11 session (very unlikely).
- An upstream fix makes AT-SPI SCREEN coordinates correct on Wayland (Newton or similar).

## Sources
- [docs/research/linux-platform.md](../research/linux-platform.md): §0 TL;DR, §1 matrix, V1, V3, V5, V16
- KDE: https://blogs.kde.org/2025/11/26/going-all-in-on-a-wayland-future/
- KDE: https://planet.kde.org/david-edmundson-2026-06-02-ex-11-prepping-for-plasmas-last-x11-supported-release/
- GTK4 SCREEN coords: https://gitlab.gnome.org/GNOME/gtk/-/raw/main/gtk/a11y/gtkatspiutils.c (lines ~522–527 on main, 2026-11-20)
- GTK4 SCREEN coords: https://gitlab.gnome.org/GNOME/gtk/-/issues/6343
- KWin MR 6057: https://invent.kde.org/plasma/kwin/-/merge_requests/6057
- gtk4-layer-shell: https://github.com/wmww/gtk4-layer-shell
- GNOME extension review rules ("Extensions must not be AI-generated"): https://gjs.guide/extensions/review-guidelines/review-guidelines.html
- Local machine facts: `apt-cache policy`, `gnome-shell --version`, `$XDG_SESSION_TYPE` (run 2026-11-20)
