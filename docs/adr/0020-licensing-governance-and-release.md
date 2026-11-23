# ADR-0020: Licensing, governance and release engineering

- Status: Proposed. **Licence decided: MIT only** (maintainer, 2026-11-22), see the update below; the rest is unchanged
- Date: 2026-11-20
- Issue: #13
- Resolves: SPEC.md §9 open question 5 (licence)

## Update 2026-11-22: MIT only
The maintainer chose **MIT** for the repository, instead of the dual MIT OR Apache-2.0 recommended below. A single `LICENSE` file (MIT) is in the repository root, `pyproject.toml` says `license = "MIT"`, and SPDX headers, when added, read `SPDX-License-Identifier: MIT`. What MIT gives up compared with the recommendation: no express patent grant. The dependency analysis below is unaffected (every core dependency allows an MIT outbound licence). Issue #26 (licence files and compliance gate) still covers the CI check.

## Implemented (#26, 2026-11-23)
- `LICENSE` (MIT) and `pyproject.toml` were already in place (#80). New: `scripts/check_licences.py`, run by `scripts/check.sh` and in the CI draft, with the hand-written policy `docs/licences.toml` and the human-readable `docs/LICENCES.md`. It fails closed on anything not listed, on strong copyleft in what ships, on the forbidden names (Piper, espeak-ng, ydotool, dogtail, OmniParser), on installed metadata that disagrees with the policy, and on a copyleft import under `src/`. It reads the closure from `uv.lock`, so transitive dependencies (pycairo under PyGObject) and dev tools are covered.
- The pack format gained `license` (ADR-0027); every shipped pack says MIT and the gate checks it. `broctl pack list` shows it.
- A first version of the metadata reader missed licences written out in words ("GNU General Public License v3"); a test caught it and it is fixed.
- **Not done:** the model register (no model yet), SPDX headers on source files, DCO sign-off enforcement, CODE_OF_CONDUCT.md, SECURITY.md, CONTRIBUTING.md, `pip-licenses` on the built wheel (the gate reads the lock file, not the wheel), a check of system packages, and the CI job has never run (CI is not active, #16).

## Context
SPEC proposes "MIT or Apache-2.0" as the licence. The sibling project workbench is dual-licensed MIT OR Apache-2.0: it ships `LICENSE-MIT` and `LICENSE-APACHE`. CLAUDE.md fixes the delivery flow:

1. issue
2. branch from `dev`
3. pull request into `dev`, with docs updated first
4. release pull request `dev` → `main`
5. tag `vX.Y.Z` and GitHub release
6. Keep a Changelog
7. Conventional Commits

**Dependency licences** ([factsheet.md Part A](../research/factsheet.md)).

Every core dependency permits a permissive outbound licence:

| Licence | Components |
|---|---|
| LGPL, used dynamically and unmodified | GTK4, PyGObject, pycairo, libatspi, pyatspi2, python-xlib, dasbus |
| Apache-2.0 | `anthropic` SDK |
| MIT or Apache-2.0 | whisper.cpp, faster-whisper, CTranslate2, Silero VAD, openWakeWord *code*, libei, gtk4-layer-shell, xdotool (BSD) |

These are copyleft or restrictive:

| Licence | Components |
|---|---|
| GPL-3.0 | piper1-gpl / `piper-tts`, espeak-ng |
| AGPL-3.0 | ydotool, OmniParser v2 `icon_detect`, Vosk linto Arabic model |
| GPL-2.0 | dogtail |

**Model-weight traps:**

| Licence | Weights |
|---|---|
| CC BY-NC-SA | openWakeWord pretrained models |
| CC-BY-NC | MMS-TTS |
| CPML (non-commercial) | XTTS-v2 |
| Research licence | Qwen2.5-VL-3B |
| Unlicensed dataset plus lessac lineage | Piper `ar_JO-kareem` |

## Decision drivers
- Maximum reuse and adoption, by app authors writing packs and by companies.
- A patent grant, since speech and ML is a patent-dense area.
- Consistency with the maintainer's other projects.
- No accidental copyleft contamination.
- A simple process for a single maintainer.

## Options considered
| Option | For | Against |
|---|---|---|
| **MIT OR Apache-2.0 dual (recommended)** | Matches workbench. Users can choose the Apache patent grant, or MIT for GPL-2.0 compatibility. Rust-ecosystem norm. | Two licence files; a contributor sign-off must cover both |
| **Apache-2.0 only** | Patent grant and NOTICE | Incompatible with GPL-2.0-only code (dogtail), which only matters if it were linked |
| **MIT only** | Simplest | No express patent grant |
| **GPL-3.0-or-later** | Could import Piper and espeak-ng in-process; protects against proprietary forks | Deters pack and app authors and companies. The benefit is small, because out-of-process TTS is the better architecture anyway (ADR-0003). |
| **MPL-2.0** | File-level copyleft | Unusual in Python desktop projects; adds friction for no specific gain |

## Decision
1. **Licence:** `MIT OR Apache-2.0` (recommended here; the maintainer chose `MIT` only, see the update above).
   - Files: `LICENSE-MIT`, `LICENSE-APACHE` (as built: a single `LICENSE`, MIT).
   - SPDX headers on source files: `SPDX-License-Identifier: MIT` (see the update above).
   - Packs in this repo use the same licence. Third-party packs declare their own in `pack.toml`.
2. **Copyleft isolation rule.**
   - GPL and AGPL components are **never imported or linked in-process**. They run only as separate optional processes over pipes or sockets: Piper and espeak-ng as Wyoming services, ydotool as an external binary if the user opts in.
   - dogtail may be used in **tests only**, never shipped.
   - Under the FSF GPL FAQ, communication between separate programs over pipes or sockets is normally mere aggregation.
3. **Model register.**
   - `docs/THIRD_PARTY_MODELS.md` (created with the first model integration) lists every model and voice with its licence, source URL and checksum, and whether it is redistributable.
   - Non-commercial or unlicensed weights are **never bundled or downloaded by default**. They are opt-in, user-initiated downloads that show the licence text.
   - The default stack must be fully redistributable.
4. **Contributions.** Use the Developer Certificate of Origin (`Signed-off-by:`), not a CLA. Lightweight governance: the maintainer is benevolent dictator for now, with a CODE_OF_CONDUCT (Contributor Covenant) and a SECURITY.md with a private report channel before the first public release.
5. **Versioning.**
   - SemVer `0.MINOR.PATCH` until v1.0. MINOR maps to SPEC milestones (0.1 MVP, 0.15 Do-it, 0.2 GNOME and voice, …).
   - The IPC interface versions (`…Overlay1`) and the pack format version (`pack.toml format = 1`) are versioned separately. A pack format change bumps MINOR and ships a migration note.
6. **Release flow** (unchanged from CLAUDE.md, made concrete):
   - Feature pull requests into `dev` run CI: ruff, pytest, headless integration and replay evals (ADR-0016).
   - A release pull request `dev` → `main` requires:
     1. a passing nightly live eval within 48 h;
     2. the manual dogfood checklist on the reference platform;
     3. CHANGELOG "Unreleased" moved under the version;
     4. docs (SPEC, README, ADRs) consistent.
   - Tag `vX.Y.Z`, then a GitHub release with notes. Publish to PyPI (`ya-bro`) via trusted publishing from the tag workflow, starting with v0.1.
7. **Licence compliance in CI.** A job lists dependency licences (e.g. `pip-licenses`) and fails on GPL or AGPL in the runtime dependency closure.

## Consequences
- **Positive:** permissive and patent-safe, consistent with workbench, and the copyleft risk is managed structurally.
- **Negative:**
  - Two licence files.
  - The Arabic offline TTS default cannot be the best-sounding option, because of licences (ADR-0011).
- **Risks:** a contributor adds an in-process GPL import. The CI licence gate guards against this.

## Validation plan
- The CI licence gate passes on the first `pyproject.toml`.
- The model register is reviewed at each release.
- The first release checklist includes a licence audit.

## Revisit if
- A key dependency changes licence (Piper already did once, MIT to GPL).
- The project needs to absorb GPL code in-process.
- An organisation adopting Ya-Bro requests a different licence.

## Sources
- [docs/research/factsheet.md](../research/factsheet.md): Part A (licence table and analysis)
- [docs/research/non-ai-tools.md](../research/non-ai-tools.md): §11 licences, Shepherd/Intro.js AGPL note (§6)
- FSF GPL FAQ, mere aggregation: https://www.gnu.org/licenses/gpl-faq.en.html#MereAggregation
- Apache-2.0 and GPL compatibility: https://www.apache.org/licenses/GPL-compatibility.html
- Developer Certificate of Origin: https://developercertificate.org/
- workbench licence files: https://github.com/AhmedYousriSobhi/workbench
