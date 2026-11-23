# Licences

Ya-Bro is **MIT** ([LICENSE](../LICENSE)); every pack in this repository is MIT too (`license = "MIT"` in `pack.toml`; a third-party pack declares its own).

## What the gate checks
`scripts/check_licences.py` runs in `scripts/check.sh` and in the CI draft (`docs/ci/ci.yml`). It fails when:
1. the project is not MIT, `LICENSE` is not the MIT text, or a shipped pack does not say MIT;
2. a package in the dependency closure (read from `uv.lock`, so transitive dependencies, extras and dev tools too) is not listed in [licences.toml](licences.toml), or its licence is not one the gate recognises;
3. anything that ships (runtime or an extra) is strong copyleft (GPL, AGPL), or is on the forbidden list by name, or a `tests-only` package is reachable at runtime;
4. an installed package's own metadata says something stronger than `licences.toml` does (a surprise licence change);
5. a file under `src/` imports a forbidden module (`piper`, `espeakng`, `ydotool`, `dogtail`).

**Isolation rule (ADR-0020 §2):** GPL and AGPL programs (Piper, espeak-ng, ydotool, dogtail) are never imported or linked into Ya-Bro. They may run only as separate processes the user installs, talking over pipes or sockets; dogtail may be used in tests only. LGPL libraries (GTK, PyGObject, pycairo) are used dynamically and unmodified.

## Adding a dependency
Read its licence, add a `[packages.<name>]` entry to `licences.toml` with its SPDX expression and scope, and run `scripts/check_licences.py`. The gate fails closed: an unlisted package is a failure, not a warning.

## Current closure
Generated with `scripts/check_licences.py --markdown` (a test fails if this table drifts).

| Package | Reached from | Licence | Class |
|---|---|---|---|
| colorama | dev | BSD-3-Clause | permissive |
| iniconfig | dev | MIT | permissive |
| packaging | dev | Apache-2.0 OR BSD-2-Clause | permissive |
| pluggy | dev | MIT | permissive |
| pycairo | optional | LGPL-2.1-only OR MPL-1.1 | weak |
| pygments | dev | BSD-2-Clause | permissive |
| pygobject | optional | LGPL-2.1-or-later | weak |
| pytest | dev | MIT | permissive |
| pytest-asyncio | dev | Apache-2.0 | permissive |
| ruff | dev | MIT | permissive |
| typing-extensions | dev | PSF-2.0 | permissive |

## Not covered yet
- A model register (`docs/THIRD_PARTY_MODELS.md`, ADR-0020 §3) is created with the first model integration; there are none.
- System packages (GNOME, GTK, AT-SPI, libvte) are the user's, not bundled.
- A licence audit and SPDX headers on source files are release-checklist items, not gated.
