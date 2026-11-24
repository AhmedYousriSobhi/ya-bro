# Getting started

Ten minutes, no guessing. Bro is a small sidekick that shows you the steps **on your real screen**, one at a time, instead of you reading a guide. You ask, it points at the button (or shows the command), and it notices when you did it.

> **Pre-alpha.** It works today on GNOME Wayland with the tasks in its knowledge packs, hand-written plans, or Claude (with your API key). No voice and no "Bro does everything" mode yet; see the [status table](../../README.md#status).

## The short version

```bash
git clone https://github.com/AhmedYousriSobhi/ya-bro.git && cd ya-bro
sudo apt install python3-gi gir1.2-atspi-2.0 wl-clipboard
uv sync && uv tool install --editable .     # puts `broctl` on your PATH
broctl setup        # answer Enter (yes) to the two required steps, pick your tool or app
# log out and in once (GNOME only loads a new extension at login)
broctl doctor       # every line should say [ok  ]
broctl ask "what you want to do"
```

Stuck at any point? Run `broctl doctor`: it checks everything and says how to fix what is wrong. Details and fixes are below, in the order you will hit them.

## 1. What you need

| Need | Check | Install |
|---|---|---|
| Ubuntu 26.04 (or any GNOME 50 desktop) on **Wayland** | `echo $XDG_SESSION_TYPE` prints `wayland` | Log in with the "Ubuntu" session, not "Ubuntu on Xorg" |
| PyGObject and AT-SPI | `python3 -c "import gi"` prints nothing | `sudo apt install python3-gi gir1.2-atspi-2.0` |
| GNOME Shell tools | `which gnome-extensions glib-compile-schemas` | `sudo apt install gnome-shell libglib2.0-bin` |
| `uv` | `uv --version` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| `wl-clipboard` (optional) | `which wl-copy` | `sudo apt install wl-clipboard` |

KDE Plasma and X11 are not supported yet. Check with `broctl doctor` once Bro is installed.

## 2. Install

```bash
git clone https://github.com/AhmedYousriSobhi/ya-bro.git
cd ya-bro
uv sync
uv tool install --editable .      # `broctl` now works from any folder
broctl --version
```

Keep the checkout: the install points at it. Update later with `git pull` and `broctl setup` again.

## 3. Set up

```bash
broctl setup
```

Bro starts blind: it sees nothing until you name something, and it asks before every change to your system. Press **Enter** to accept the default shown in capitals (`[Y/n]` means yes). `broctl setup --yes` skips the questions.

1. **Pick what Bro may see.** You get a numbered list. Pick a **tool** (a command and/or a web page, for example workbench) or one **app** (for example Calculator). Type a word to filter the list, a number to choose, `q` to stop.
2. **For a tool:** its web page address (Enter to skip) and **the folder its commands run from**. Bro uses the folder to start the walk-through with a `cd` step, so you are never in the wrong place.
3. **Accessibility** (required): lets apps tell Bro where their buttons are. Enter for yes.
4. **Shell extension** (required): copies the small Bro extension into your GNOME and turns it on. It draws the ring and the bubble and reports window positions, only for what you allowed. Enter for yes.
5. The first time, it shows what it reads and asks whether you allow sending your question to Claude. The default is no, and nothing is sent unless you say yes. `broctl consent revoke` changes your mind later.

Then **log out and back in once.** GNOME on Wayland loads an extension only at login. This is normal for every GNOME extension; it is not a reboot. `broctl doctor` says when you need to do it again (after an update that changes the extension).

Check: `broctl doctor` shows `[ok  ]` lines. A warning about the API key is fine until you want Claude to write plans.

## 4. Use it

### In a terminal (for tools like workbench)

```bash
broctl hook install        # asks before editing ~/.bashrc; then open a NEW terminal
broctl ask "start the cluster" --pack workbench
```

Bro's bubble, with its face, appears at the top-right of your terminal, one step at a time: a sentence and the command in a box.

| Button | What it does |
|---|---|
| **Copy** | puts the command on your clipboard; paste with Ctrl+Shift+V |
| **Write it** | types the command at your prompt. It never presses Enter: you check it and press Enter |
| **Next** | skip the step (asks first if you have not done it) |
| **Why?** | explains the step, or what went wrong |
| **Stop** | ends everything (also **Super+Shift+Esc**) |

When you run the command, Bro sees it finish and moves on by itself. Use a terminal that shows its title (Ptyxis, GNOME Terminal, Console). Terminals inside other apps, like VS Code's, are not supported; see the [workbench guide](workbench.md).

### On a desktop app (Calculator demo)

```bash
gnome-calculator &         # press C so the display is empty, then click its window
broctl apps allow org.gnome.Calculator     # skip if setup already allowed it
broctl show examples/plans/calculator.toml
```

An amber ring lands on **7** with a bubble: "(1/4) Press 7." Press 7. Bro sees the display change and moves to **×**, **6**, then **=**. The same buttons as above apply (**Repeat** shows the step again).

### Ask in your own words

```bash
broctl ask "multiply 7 by 6"
broctl ask                      # no sentence: a small window asks you
broctl ask "..." --dry          # only print the plan
```

Bro first looks for a matching task in the knowledge pack (nothing leaves your machine). If none fits, and you allowed sending, it asks Claude. That needs an API key: `broctl key set` (hidden prompt, stored in your system keyring). Each request carries only your question and the names of the controls in the allowed window, never a screenshot; `broctl sent` lists every request.

### Let Bro press the buttons itself (Do-it)

Off by default, and only for apps you enable: put this in `~/.config/ya-bro/config.toml`'s app section (see [DEVELOPMENT.md](../DEVELOPMENT.md)):

```toml
[do_it]
allowed = true
```

Then `broctl show plan.toml --do-it`. Bro says what it will do, flies the pointer to the control, waits a second, then presses. It asks first before anything that changes things, hands anything risky (buying, deleting, sending, passwords) back to you, and **Stop** halts it at once.

## 5. Make it yours

Put these in `~/.config/ya-bro/config.toml`:

| Setting | Effect |
|---|---|
| `humour = 0` | plain lines, no jokes |
| `language = "ar"` | Egyptian Arabic (drafts) |
| `less_chatty = true` | fewer extras |

`broctl persona list` shows everything Bro can say. Your own tools: `broctl targets list`, `allow`, `revoke`; apps: `broctl apps list`, `allow`, `revoke`.

## 6. If something goes wrong

Run `broctl doctor` first; paste its output into an issue if you are stuck (it is safe to share).

| What you see | Fix |
|---|---|
| `cannot reach the Bro extension` | Not loaded in this session: log out and in, then `broctl doctor` |
| doctor says **extension code** is old | You updated Bro: run `broctl setup`, then log out and in |
| The bubble is a plain box with no face, not beside the terminal | The terminal's title did not reach Bro. Check you ran `broctl hook install` and opened a **new** terminal; read `~/.local/state/ya-bro/companion.log` |
| `./scripts/...: No such file or directory` | You were in the wrong folder: run `broctl targets allow <tool> --command <cmd> --dir <folder>` so the walk-through starts with `cd` |
| `no allowed window is open` | Open the allowed app; `broctl apps list` shows what is allowed |
| Nothing appears and the run says `step_paused` | Click the allowed app's window: the ring shows only on the focused window |
| `another core already runs` | Run `broctl panic`, then try again |
| `needs the system python3 with PyGObject` | `sudo apt install python3-gi gir1.2-atspi-2.0` |
| The ring is a few pixels off | See [extents offset](../research/spikes/S9-extents-offset.md) |
| It looks stuck | **Stop** in the bubble, or **Super+Shift+Esc**, then run the command again |

## 7. Privacy: what Bro can see

- **Only what you allow.** With nothing named, the extension reports nothing. `broctl apps revoke <id>` and `broctl targets revoke <id>` take it back.
- Everything Bro draws is visible and **Stop always works**. Small dots under the bro show what it is doing: blue reading your app, green listening, red sending, orange acting.
- `broctl sent` lists every request that left your machine (kind and size, never content).
- `broctl panic` stops every Bro process at once. `broctl forget` deletes logs; `--everything` also removes allowed apps and tools, the stored key, the shell hook lines and your consent.
- It never types a password or clicks a purchase, delete or send control for you.
- Logs (`~/.local/state/ya-bro/logs/`) hold event types and counts, never typed text or screen content.
- Honest limit: the GNOME accessibility setting is desktop-wide and the extension runs inside the shell, so the "only what you allow" rule is enforced by Bro's own code, not by the operating system ([ADR-0023](../adr/0023-gnome-shell-extension-bridge.md)).

## 8. Undo everything

```bash
broctl forget --everything          # logs, allowed apps and tools, key, hook lines, consent
gnome-extensions disable ya-bro@ahmedyousrisobhi.github.io
rm -rf ~/.local/share/gnome-shell/extensions/ya-bro@ahmedyousrisobhi.github.io
uv tool uninstall ya-bro            # removes `broctl`
```

The accessibility setting stays on because other tools may use it; to turn it off: `gsettings set org.gnome.desktop.interface toolkit-accessibility false`.

## Next

- Running Bro on a tool with a terminal and a web page: [workbench guide](workbench.md).
- Writing your own plan or knowledge pack: [DEVELOPMENT.md](../DEVELOPMENT.md#show-me-plans-broctl-show).
- Letting Bro see just one web page instead of a whole browser: [ADR-0025](../adr/0025-pack-scoped-targets.md).
