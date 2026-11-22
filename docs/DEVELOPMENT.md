# Development guide

## Setup
```bash
uv sync                # Python 3.12 venv with pytest and ruff
```
PyGObject is **not** installed in the venv (it needs system dev headers). Code under `src/ya_bro/platform/**` may import `gi`; everything else may not (enforced by ruff `TID251`). The AT-SPI integration test runs the fixture app and probe with the system `/usr/bin/python3`, which needs `python3-gi`, `gir1.2-gtk-4.0`, `gir1.2-atspi-2.0`, `at-spi2-core`, `dbus`, and a display (`xvfb-run` on a headless box).

## Validate after every change
```bash
scripts/check.sh          # ruff check, ruff format --check, unit tests, AT-SPI integration
scripts/check.sh --fast   # skip the integration test
```

## GNOME extension
`scripts/dev/headless-shell.sh <cmd>` runs `<cmd>` inside an isolated headless `gnome-shell` with the extension enabled: private bus, config, data and runtime dirs, its own PipeWire, WirePlumber and (with `YB_X11=1`) Xwayland. It never uses your `DISPLAY`. WirePlumber runs with video, audio and Bluetooth off inside a `bwrap` namespace that masks `/dev/video*` and `/dev/media*`, so the harness cannot touch the camera; it refuses to start without `bwrap`. `YB_DEVKIT=1` runs a nested shell in a `mutter-devkit` window on your real desktop instead (needs `sudo apt install mutter-dev-bin`; a window opens, nothing else on the real desktop is touched). Env: `YB_X11`, `YB_SCALE`, `YB_MONITOR`, `YB_GDK`, `YB_DEBUG`. `pytest -m gnome` runs the fast contract test; `pytest -m gnome_measure` runs the S1 measurements (about 5 minutes, writes `docs/research/spikes/S1-measurements-scale-*.json`; not part of `scripts/check.sh`). Do not reload the extension in your live session; the ADR-0023 nested `--devkit` loop (needs `mutter-dev-bin`) is for visual checks.

## CI
The workflow draft is `docs/ci/ci.yml` and triggers on pushes to `main` only (so PRs into `dev` are validated locally with `scripts/check.sh`); it is not active until copied to `.github/workflows/` (needs a token with `workflow` scope). See docs/PROGRESS.md.

## Layout
| Path | Purpose |
|---|---|
| `src/ya_bro/interfaces/` | Component Protocols (provisional) |
| `src/ya_bro/types.py` | Shared value types |
| `src/ya_bro/ipc/` | Versioned D-Bus names and the adapter Protocol |
| `src/ya_bro/platform/` | The only place for OS and toolkit imports |
| `tests/fakes/` | In-memory fake per interface |
| `tests/fixtures/` | AT-SPI fixture app(s) and probe |
| `scripts/check.sh` | Full validation |

## Adding an interface or fake
Add the Protocol to `interfaces/__init__.py`, a fake in `tests/fakes/__init__.py`, and a row in `tests/test_interfaces.py`.

## Trying a tab-scoped target
A page on an allowed origin proves itself by putting a token in its title:
```js
fetch('http://127.0.0.1:47800/token', {headers: {'X-Scope-Token': '1'}})
  .then(r => r.ok ? r.text() : '').then(t => { if (t) document.title += ' ' + t; });
```
Demo without workbench: `scripts/dev/token_page.py`, then `broctl targets allow demo --origin http://127.0.0.1:8099`, `broctl apps revoke <your browser id>` (otherwise the whole browser is already allowed), `broctl point`, and open the page. The ring shows on that tab only. `broctl point` must be running: the token exists only while it runs.

## Show-me plans (`broctl show`)
A plan is a TOML file; the loop shows one step at a time on the real window (tests/fixtures/steps_plan.toml is a working example):
```toml
[plan]
goal = "create the thing"
keywords = ["create"]            # ScriptedBrain picks the plan by these
app = "org.example.App"          # optional; --app overrides, default: the focused allowed window

[[step]]
narration = "Click Create."      # what the bubble says (never text read off the screen)
target = {role = "button", name = "Create"}      # omit for a bubble-only step
expect = {role = "button", name = "Confirm"}     # screen proof the user did it; appears = false means gone
# expect can also read text: expect = {role = "text", text = "42"}  (the element's text contains it)
why = "Create opens the confirmation."           # shown by the Why button
risk = 0                                         # 3 = the user's own click, always only shown
```
Run `broctl show plan.toml` with the target app allowed (`broctl apps allow`), `broctl load` done and the app open. The app must expose an accessibility tree (GTK apps do; Firefox and Chrome need the page to report its own state, #31). Buttons: Next, Repeat, Why, Stop; Super+Shift+Esc also stops. A step with an `expect` advances by itself once the screen shows it. If you press Next first, the bro says it doesn't see it yet and skips only on a second Next. If the watched text changes to something else (Why? then names what the screen shows versus what was needed; `humour = 0` in config.toml makes every line plain) and stays that way for a moment, the bro says what it expected (“That's not what I asked for”) and Next then goes on at once. A step that already looks done when it appears waits for Next instead of racing ahead (the screen may show an old result). Steps without an `expect` advance on Next only. If the element is not on screen yet, you get a bubble that says so and the ring appears as soon as it does.

A working example is `examples/plans/calculator.toml` (multiply 7 by 6). If an app's AT-SPI rectangles are a constant off (GNOME Calculator reports keys 12 px right and down), add `extents_offset = [dx, dy]` to `[plan]` ([S9](research/spikes/S9-extents-offset.md)). The reference GIF in the README is regenerated with:
```bash
YB_MONITOR=1280x1000 YB_ALLOWED='["org.gnome.Calculator"]' \
  scripts/dev/headless-shell.sh /usr/bin/python3 scripts/dev/record_demo.py docs/assets/show-me-calculator.gif
```
