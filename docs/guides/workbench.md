# Running Bro on workbench

workbench is a tool with two faces: the `benchctl` command and a web page (`python -m webui`, port 8088). You allow it as one **target** (ADR-0025), not as "the whole browser" or "every shell". This guide says what works today, with the exact commands, and what does not yet.

Do [Getting started](getting-started.md) first (extension loaded, `broctl doctor` happy). Commands below assume you are in the `ya-bro` folder; drop `uv run` if `broctl` is on your PATH.

## What works today

| You want | Works | How |
|---|---|---|
| Bro beside your terminal with the command to type: Copy, or Write it at your prompt | yes (bash, VTE terminals) | section 1 |
| Bro explains a failing `benchctl` command and offers help when you are stuck | partly | section 2 |
| Bro shows the workbench web page only while that tab is active | yes | section 3 |
| Bro points at buttons on the workbench web page | no | needs the page to report its own state (workbench #31) or Chromium's accessibility tree |
| Bro runs `benchctl` for you | no, by design | Write it only fills your prompt; you press Enter |

## 1. Bro beside your terminal (the main way)

One-time setup. Install `broctl` once (`uv tool install --editable .` in the Bro checkout) and pick workbench as a **tool** in `broctl setup` (it asks for the web page address and the folder where workbench's commands run; do not allow Firefox or Chrome as an app, that exposes every window of the browser). Needs the extension loaded, see getting started; **the extension changed: run `broctl setup` to copy the new files, then log out and in (GNOME on Wayland keeps the code it loaded at login; `broctl load` only loads an extension that is not loaded yet, and `broctl doctor` shows "extension code" when yours is old)**):

```bash
broctl hook install          # asks before editing ~/.bashrc; open a new terminal after
```

Then, in that terminal:

```bash
broctl ask "start the cluster" --pack workbench
```

Bro starts with a step that takes you to workbench's folder (`cd '<folder>'`, with Copy, Write it and Next if you are already there), because `./scripts/benchctl` only works from there. Tell it the folder once, in `broctl setup` or later:

```bash
broctl targets allow workbench --command benchctl --dir ~/path/to/workbench
```

Use a terminal whose window title follows the shell (Ptyxis, GNOME Terminal and other VTE terminals). Terminals inside another app (VS Code's, or the Claude desktop app's) do not change their window title, so Bro cannot tell which window is the terminal: the bubble is then a plain window with Copy only, and `~/.local/state/ya-bro/companion.log` says why. For such a terminal allow the whole app with `broctl apps allow <id>` (it then sees that app's window position, not its content).

The prompt comes back at once and Bro's bubble appears at the terminal's top-right with one step at a time: a sentence, and the command in a code box. Buttons:

| Button | What it does |
|---|---|
| **Copy** | puts exactly that command on the clipboard; paste with Ctrl+Shift+V |
| **Write it** | types the command at your prompt for you. It never presses Enter: check it, press Enter yourself |
| **Next** / **Why?** / **Stop** | skip the step / explain it / end (Esc-style stop key also works) |

When you run the command, Bro sees it finish (name and exit code only) and moves to the next step by itself; if it fails it says so and waits for you to run it again. **Write it** only appears when your terminal is at an empty idle prompt with the hook installed; it refuses (and says why) when text is already at your prompt, when something is running, or for a destructive command (those are yours to type; Copy still works). Without the allowed terminal Bro shows the same bubble in its own small window.

Tasks: `start-cluster`, `run-scenario`, `clear-faults`, `export-test-report` (`broctl pack list`). Say it in plain words; the best keyword match wins. Without a goal a window asks you. `--wait` keeps Bro in the foreground; `broctl panic` stops it.

## 2. Failing `benchctl` commands (shell hook)

The hook tells Bro only the command **name**, exit code and duration of `benchctl`, never arguments or output, and nothing at all while Bro is not running.

```bash
broctl targets allow workbench --command benchctl
broctl hook install          # asks before editing ~/.bashrc; open a new terminal after
broctl struggle enable workbench
broctl struggle on
broctl struggle watch        # leave running; needs the extension loaded
```

Now when `benchctl` fails three times in a row, a bubble asks "you stuck, bro?" (Yes, No, Not for this app). `broctl shell watch` prints the commands Bro would see, which is the quickest way to check the hook works. The pack's error-code explanations (`WB-...`) live in `packs/workbench/fixits.toml`; today **Yes** only greets, it does not yet read the terminal and explain the code (reading a VTE terminal exists in `ya_bro.terminal` but is not wired to the offer). Bash only; zsh and fish are not built.

## 3. The web page, scoped to its tab

Bro must see the workbench tab and no other tab. It cannot read a URL, so the page proves which tab it is with a secret token in its title (ADR-0025):

1. **Allow the origin**, and make sure the whole browser is not allowed (that would show every tab):
   ```bash
   broctl targets allow workbench --origin http://127.0.0.1:8088 --command benchctl
   broctl apps list             # if your browser is listed:
   broctl apps revoke <browser id>
   ```
2. **Start the page with the helper on**, in the workbench repo:
   ```bash
   WORKBENCH_DESKTOP_HELPER=1 python -m webui      # or ./scripts/benchctl start with the same variable set
   ```
   and sign in with `./scripts/benchctl open`. Once, in the page's browser console: `localStorage.setItem('workbench-desktop-helper', '1')`, then reload.
3. **Run a Bro command that stays up** while you use the page, for example `broctl point` (it runs the small loopback server on 127.0.0.1:47800 that hands the token only to the page's own origin; the token exists only while it runs).
4. The ring and bubble appear on the workbench tab and leave when you switch tabs. Use Chromium or Chrome; Firefox is not verified.

Revoke at any time: `broctl targets revoke workbench`. `broctl panic` stops everything.

## Gaps, in the order they hurt
1. Bro cannot point at elements on the web page yet (#31 `/api/state`, and web selectors in the pack format).
2. **Yes** on the stuck bubble does not start a conversation or read the terminal.
3. No Do-it for terminals or the page (#27 covers AT-SPI controls only).
4. If `benchctl` is on your PATH the steps still say `./scripts/benchctl` (the folder step is skipped only when there is no folder set).
