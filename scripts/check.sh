#!/usr/bin/env bash
# One-shot validation: lint, format, unit tests, then integration tests (AT-SPI).
# Run after every edit. Usage: scripts/check.sh [--fast]   (--fast skips integration)
set -euo pipefail
cd "$(dirname "$0")/.."

step() { printf '\n== %s\n' "$*"; }

step "ruff check";          uv run ruff check .
step "ruff format --check"; uv run ruff format --check .
step "unit tests";          uv run pytest -m "not atspi and not gnome and not gnome_measure" -q
if [[ "${1:-}" != "--fast" ]]; then
  step "integration (AT-SPI)"; uv run pytest -m atspi -q -rs
  step "integration (GNOME extension, headless shell)"; uv run pytest -m gnome -q -rs
fi
step "OK"
