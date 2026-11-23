# Spike S2: AT-SPI coverage on real apps (#2), first measurement

**Status: partial.** Two of the five named apps were measured (LibreOffice Writer, VS Code) (plus the GTK apps in the pointing eval, #19). No go/no-go on the vision fallback yet. #2 stays open.

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

## Measured: VS Code (`--force-renderer-accessibility`, `--ozone-platform=wayland`, fresh profile)
Electron exposes its tree to AT-SPI under the application name `code` (406 nodes, depth 34): 7 menu items, 7 page tabs, 4 toggle buttons, 5 links, 1 entry and 1 check box, all named; 11 list items, none named. **Caveat:** the Shell never reported a window for it under any app id tried (`code`, `Code`, `code-url-handler`, `code-oss`, `visual-studio-code`), so Bro's scoped lookup (which starts from windows the extension reports) could not have found it, and the "rect" column is meaningless here (no window frame). The tree is the welcome screen only. So: the accessibility data is there once the flag is on; the window id and a mapped window are the open problem.

## Not measured, and why
- **Firefox:** the system Firefox is a snap and refuses to start outside its cgroup (`not a snap cgroup`), so a private-profile run is not possible here.
- **GIMP, Inkscape, KDE Settings:** not installed.
- **Position accuracy:** this run checks that a rectangle exists and fits the window, not that it matches the drawn control (no pixel check; see S9 for the Calculator's constant offset).
- Only one window state, one profile, one scale (1.0).

## What it does not decide
Whether vision fallback is needed for LibreOffice: the evidence says names are good, but whether the visible controls are the ones a user needs is a per-task question (the eval for pointing, #19, is the tool). Next: find why VS Code's window is not reported (log windows without an allow-list in a throwaway shell), run Firefox from a non-snap build, install the others in a test machine, then add a position check against pixels.
