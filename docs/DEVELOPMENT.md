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
