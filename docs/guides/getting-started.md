# Getting started

About 10 minutes, no guessing. At the end you will watch Ya-Bro walk you through multiplying 7 by 6 in GNOME Calculator, pointing at each key.

> **Pre-alpha.** Ya-Bro works today with hand-written plans on GNOME Wayland. It has no voice, no LLM brain and no "do it for me" mode yet. See the [status table](../../README.md#status).

## 1. What you need

| Need | Check | Install |
|---|---|---|
| Ubuntu 26.04 (or any GNOME 50 desktop) on **Wayland** | `echo $XDG_SESSION_TYPE` prints `wayland`; `gnome-shell --version` prints 50.x | Log in with the "Ubuntu" session, not "Ubuntu on Xorg" |
| Python 3.12+ with PyGObject and AT-SPI bindings | `python3 -c "import gi"` prints nothing | `sudo apt install python3-gi gir1.2-atspi-2.0` |
| GNOME Shell tools and GLib | `which gnome-extensions glib-compile-schemas` | `sudo apt install gnome-shell libglib2.0-bin` |
| `uv` (runs the project) | `uv --version` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| `wl-clipboard` (optional) | `which wl-copy` | `sudo apt install wl-clipboard` (lets `broctl load` copy a line for you) |
| GNOME Calculator (for the demo) | `which gnome-calculator` | `sudo apt install gnome-calculator` |

KDE Plasma and X11 desktops are not supported yet.

## 2. Install

```bash
git clone https://github.com/AhmedYousriSobhi/ya-bro.git
cd ya-bro
uv sync
uv run broctl --version        # prints: broctl 0.1.0
```

Optional: `uv tool install --editable .` puts `broctl` on your PATH so you can drop the `uv run` below.

## 3. Check your machine

```bash
uv run broctl doctor
```

Every line starts with `[ok  ]` or `[WARN]` and tells you how to fix a warning. On a fresh machine you will see warnings for the extension and for allowed apps: that is what the next step fixes. A warning about `api key` is fine for now (there is no LLM brain yet). The output is safe to paste in a bug report.

## 4. Set up (one app, your choice)

```bash
uv run broctl setup
```

Ya-Bro starts blind. It sees nothing until you name **one app**, and it asks before every change to your system:

1. **Pick the app.** Type a word (`calculator`), press Enter, then type the number from the list. (Know the id already? Type it, e.g. `org.gnome.Calculator`.)
2. **Accessibility** (`Do this? [y/N]`): lets apps expose their buttons to Ya-Bro. This is a GNOME setting for the whole desktop. Answer `y`.
3. **Shell extension** (`Do this? [y/N]`): copies the small Ya-Bro extension into `~/.local/share/gnome-shell/extensions/` and enables it. It draws the ring and reports window positions, but only for the app you named. Answer `y`.
4. Setup prints `Ya-Bro may now see: <your app>`.

Anything other than `y` skips that step, so you can stop at any point and run it again.

## 5. Load the extension (no logout)

GNOME only notices a new extension at login. To avoid logging out:

```bash
uv run broctl load
```

and follow the three steps it prints: press **Alt+F2**, type `lg`, press Enter (Looking Glass opens), paste the line (it is already in your clipboard when `wl-copy` is installed), press Enter, then **Esc**. The command waits and prints `loaded`. It lasts until your next login, then GNOME loads it normally. If you prefer, just log out and back in instead.

Check: `uv run broctl doctor` shows `extension: ENABLED`.

## 6. Run the demo

```bash
gnome-calculator &
uv run broctl apps allow org.gnome.Calculator     # skip if setup already allowed it
uv run broctl show examples/plans/calculator.toml
```

1. Press **C** in the Calculator so the display is empty.
2. **Click the Calculator window.** The ring only appears on the window you are using.
3. An amber ring lands on **7** with a bubble: "(1/4) Press 7." Press 7. The bro sees the display change and moves to **×**, then **6**, then **=**. At 42 the ring leaves.

What you can do while it runs:

| Control | What it does |
|---|---|
| Press the key it points at | It reads the screen and moves on by itself |
| **Next** | Skip ahead. If you have not done the step it asks first; press Next again to skip anyway |
| **Why?** | Explains the step. After a wrong key it explains your mistake: what the screen shows versus what it needed |
| **Repeat** | Shows the step again |
| **Stop**, or **Super+Shift+Esc** | Ends the walkthrough and hides everything at once |

Try pressing a wrong key on purpose: the bro teases you and waits for you to undo it. Put `humour = 0` in `~/.config/ya-bro/config.toml` for plain lines.

## 7. Write your own plan

A plan is a short TOML file. Copy `examples/plans/calculator.toml` and change the steps:

```toml
[plan]
goal = "do the thing"
app = "org.example.App"

[[step]]
narration = "Click Save."
target = {role = "button", name = "Save"}
expect = {role = "button", name = "Saved"}      # what the screen shows when it worked
why = "Save keeps your work."
```

`broctl apps available` lists installed app ids. Full format: [DEVELOPMENT.md](../DEVELOPMENT.md#show-me-plans-broctl-show). The app must expose an accessibility tree (GTK apps do). If the ring sits a few pixels off in some app, add `extents_offset = [dx, dy]` to `[plan]` ([finding S9](../research/spikes/S9-extents-offset.md)).

## 8. If something goes wrong

| What you see | Fix |
|---|---|
| `cannot reach the Ya-Bro extension` or `ServiceUnknown` | The extension is not loaded in this session. Run `uv run broctl load` (or log out and in), then `uv run broctl doctor` |
| `no allowed window is open` | Open the app you allowed and check `uv run broctl apps list` |
| Nothing appears, and the run says `step_paused` | Click the allowed app's window: the ring only shows on the focused window |
| `another core already runs; stop it first` | A previous `broctl show` or `point` is still running: `pkill -f gnome_show` (or `gnome_demo`) |
| `needs the system python3 with PyGObject` | `sudo apt install python3-gi gir1.2-atspi-2.0` |
| `extension: not known to the shell` in doctor | Run `uv run broctl setup` and answer `y` to the extension, then `uv run broctl load` (doctor says "re-login"; `load` saves you the logout) |
| The ring is slightly off the button | See [extents offset](../research/spikes/S9-extents-offset.md); the Calculator example already corrects it |
| It looks stuck | Press **Stop** in the bubble or **Super+Shift+Esc**, then run the command again |
| Anything else | `uv run broctl doctor` and paste the output into an issue |

## 9. Privacy: what Ya-Bro can see

- **Only the app you allow.** Default-deny: with no app named, the extension reports nothing. Revoke with `uv run broctl apps revoke <app-id>`.
- Everything it draws is visible, and Stop always works.
- It never types for you or clicks for you (Show-me mode only points).
- Logs are written to `~/.local/state/ya-bro/logs/` and contain event types and counts, never typed text or screen content.
- Honest limit: the GNOME accessibility setting is desktop-wide and the extension runs inside the shell, so the one-app rule is enforced by Ya-Bro's own code, not by the operating system ([ADR-0023](../adr/0023-gnome-shell-extension-bridge.md)).

## 10. Undo everything

```bash
uv run broctl apps revoke org.gnome.Calculator            # stop seeing any app
gnome-extensions disable ya-bro@ahmedyousrisobhi.github.io
rm -rf ~/.local/share/gnome-shell/extensions/ya-bro@ahmedyousrisobhi.github.io
rm -rf ~/.config/ya-bro ~/.local/state/ya-bro             # optional: settings and logs
```

The accessibility setting is left on because other tools may rely on it; to turn it off: `gsettings set org.gnome.desktop.interface toolkit-accessibility false`.

## Advanced: a web tool instead of a whole browser

To let Ya-Bro see one web page without exposing your other tabs, allow it as a **target**:

```bash
uv run broctl targets allow mytool --origin http://127.0.0.1:8080
```

The page proves it is that origin by putting a token in its title; see [ADR-0025](../adr/0025-pack-scoped-targets.md) and [DEVELOPMENT.md](../DEVELOPMENT.md#trying-a-tab-scoped-target). Browser pages expose little to the accessibility tree, so walkthroughs on web pages are not ready yet.
