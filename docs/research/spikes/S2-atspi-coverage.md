# Spike S2: AT-SPI coverage on real apps (#2), first measurement

**Status: partial.** One of the five named apps was measured (plus the GTK apps in the pointing eval, #19). No go/no-go on the vision fallback yet. #2 stays open.

Reproduce: `YB_ALLOWED='[...]' scripts/dev/headless-shell.sh /usr/bin/python3 tests/fixtures/shell_atspi_coverage.py` (isolated shell, private profiles, observation only; `YB_APPS` picks apps). It walks the whole tree (30,000-node budget) and counts, per role Bro acts on, elements found, elements with a name, and elements whose rectangle is non-empty and inside the window.

## Measured: LibreOffice Writer (GNOME 50.1, Wayland, 700 x 460 window, fresh profile)
2,347 nodes, depth 17, not truncated. Window app id is `soffice`.

| Role | found | named | rect inside window |
|---|---|---|---|
| menu item | 781 | 781 | 0 |
| check menu item | 513 | 513 | 0 |
| radio menu item | 86 | 86 | 0 |
| list item | 120 | 120 | 0 |
| toggle button | 44 | 34 | 7 |
| combo box | 27 | 8 | 6 |
| text | 15 | 0 | 3 |
| page tab | 3 | 3 | 3 |
| check box / radio button | 5 / 11 | all | 0 |

**Reading it:** names are essentially complete on menus, lists and tabs, so lookup by role and name works for what exists. Most nodes are not on screen (closed menus and sidebar panels report an empty rectangle), so the last column mostly counts hidden elements, not wrong ones. Of the 44 toolbar-style toggle buttons only 7 have an on-screen rectangle at this window size (the rest are likely collapsed toolbar items), and 10 of 44 are unnamed. Text areas carry no name.

## Not measured, and why
- **VS Code:** launched, but no window appeared under any app id I allowed (`code`, `Code`, `code-url-handler`, `code-oss`, `visual-studio-code`); the Electron app idles on a network error in the sandbox. The window's real app id is unknown.
- **Firefox:** the system Firefox is a snap and refuses to start outside its cgroup (`not a snap cgroup`), so a private-profile run is not possible here.
- **GIMP, Inkscape, KDE Settings:** not installed.
- **Position accuracy:** this run checks that a rectangle exists and fits the window, not that it matches the drawn control (no pixel check; see S9 for the Calculator's constant offset).
- Only one window state, one profile, one scale (1.0).

## What it does not decide
Whether vision fallback is needed for LibreOffice: the evidence says names are good, but whether the visible controls are the ones a user needs is a per-task question (the eval for pointing, #19, is the tool). Next: find VS Code's app id (log windows without an allow-list in a throwaway shell), run Firefox from a non-snap build, install the others in a test machine, then add a position check against pixels.
