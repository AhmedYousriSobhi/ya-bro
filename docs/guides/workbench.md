# Running Bro on workbench

workbench is a tool with two faces: the `benchctl` command and a web page (`python -m webui`, port 8088). You allow it as one **target** (ADR-0025), not as "the whole browser" or "every shell". This guide says what works today, with the exact commands, and what does not yet.

Do [Getting started](getting-started.md) first (extension loaded, `broctl doctor` happy). Commands below assume you are in the `ya-bro` folder; drop `uv run` if `broctl` is on your PATH.

## What works today

| You want | Works | How |
|---|---|---|
| Bro walks you through a workbench task (start the cluster, run a scenario, clear faults, export a report) | yes | section 1 |
| Bro explains a failing `benchctl` command and offers help when you are stuck | partly | section 2 |
| Bro shows the workbench web page only while that tab is active | yes | section 3 |
| Bro points at buttons on the workbench web page | no | needs the page to report its own state (workbench #31) or Chromium's accessibility tree |
| Bro types or runs `benchctl` for you | no | Do-it on terminals is not built; the bro never runs a command without you |

## 1. Walk through a task (no extension, no app to allow)

```bash
uv run broctl ask "start the cluster" --pack workbench
```

A small Bro window opens with one step at a time ("(1/3) In the workbench folder, run: ./scripts/benchctl plan"). **You** run the command in your terminal, then press **Next** in the Bro window. **Why?** explains the step, **Stop** (or Esc) ends it. Nothing is read from your screen and nothing is sent anywhere: the steps come from the pack.

Tasks in the pack: `start-cluster`, `run-scenario`, `clear-faults`, `export-test-report` (`broctl pack list`). Say it in plain words ("run a scenario", "clear the faults"); the best keyword match wins. With no goal (`broctl ask --pack workbench`) a window asks you to type it. Words the pack has no task for fail with the list of tasks; Claude is not used in this mode.

## 2. Failing `benchctl` commands (shell hook)

The hook tells Bro only the command **name**, exit code and duration of `benchctl`, never arguments or output, and nothing at all while Bro is not running.

```bash
uv run broctl targets allow workbench --command benchctl
uv run broctl hook install          # asks before editing ~/.bashrc; open a new terminal after
uv run broctl struggle enable workbench
uv run broctl struggle on
uv run broctl struggle watch        # leave running; needs the extension loaded
```

Now when `benchctl` fails three times in a row, a bubble asks "you stuck, bro?" (Yes, No, Not for this app). `broctl shell watch` prints the commands Bro would see, which is the quickest way to check the hook works. The pack's error-code explanations (`WB-...`) live in `packs/workbench/fixits.toml`; today **Yes** only greets, it does not yet read the terminal and explain the code (reading a VTE terminal exists in `ya_bro.terminal` but is not wired to the offer). Bash only; zsh and fish are not built.

## 3. The web page, scoped to its tab

Bro must see the workbench tab and no other tab. It cannot read a URL, so the page proves which tab it is with a secret token in its title (ADR-0025):

1. **Allow the origin**, and make sure the whole browser is not allowed (that would show every tab):
   ```bash
   uv run broctl targets allow workbench --origin http://127.0.0.1:8088 --command benchctl
   uv run broctl apps list             # if your browser is listed:
   uv run broctl apps revoke <browser id>
   ```
2. **Start the page with the helper on**, in the workbench repo:
   ```bash
   WORKBENCH_DESKTOP_HELPER=1 python -m webui      # or ./scripts/benchctl start with the same variable set
   ```
   and sign in with `./scripts/benchctl open`. Once, in the page's browser console: `localStorage.setItem('workbench-desktop-helper', '1')`, then reload.
3. **Run a Bro command that stays up** while you use the page, for example `uv run broctl point` (it runs the small loopback server on 127.0.0.1:47800 that hands the token only to the page's own origin; the token exists only while it runs).
4. The ring and bubble appear on the workbench tab and leave when you switch tabs. Use Chromium or Chrome; Firefox is not verified.

Revoke at any time: `uv run broctl targets revoke workbench`. `uv run broctl panic` stops everything.

## Gaps, in the order they hurt
1. Bro cannot point at elements on the web page yet (#31 `/api/state`, and web selectors in the pack format).
2. **Yes** on the stuck bubble does not start a conversation or read the terminal.
3. No Do-it for terminals or the page (#27 covers AT-SPI controls only).
4. The pack's tasks assume you are in the workbench folder and use `./scripts/benchctl`; if `benchctl` is on your PATH the steps still say `./scripts/benchctl`.
