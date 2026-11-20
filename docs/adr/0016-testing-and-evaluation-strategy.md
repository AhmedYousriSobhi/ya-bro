# ADR-0016: Testing and evaluation strategy

- Status: Proposed
- Date: 2026-11-20
- Issue: #13
- Depends on: ADR-0003 and every component ADR

> **Amended for GNOME-first (2026-11-20).**
> - The headless **GNOME** row becomes the primary compositor integration test.
> - Sway headless and KWin `--virtual` move to the v0.2 KWin/layer-shell work.
> - X11/Xvfb stays for cheap AT-SPI and core tests only.
> - GitHub's ubuntu-24.04 runners ship GNOME 46, so GNOME 50 jobs run in an `ubuntu:26.04` container (Fedora images for 48/49/51 in the version matrix, ADR-0023 §8).
> - Schneegans' gnome-shell-pod is X11/Xvfb-based and stops at GNOME 47, so it cannot be used.

## Context
Ya-Bro is hard to test in four ways:
- it depends on live desktops (compositors, AT-SPI, portals);
- it depends on third-party apps that change;
- it depends on a non-deterministic LLM;
- its key qualities are statistical: pointing accuracy, offer precision and latency.

CLAUDE.md requires tests with every feature, with `pytest` and `ruff` before each PR. The success criteria in SPEC §8 are quantitative: ≥ 80% of steps pointed correctly, < 3 s per step, and < 500 ms to stop.

## Decision drivers
- Fast, deterministic unit and integration tests on every PR.
- Realistic end-to-end coverage without flakes blocking merges.
- Statistical evaluation sets for pointing, struggle detection, plans and tone.
- Cheap LLM usage in CI.

## Options considered
| Option | For | Against |
|---|---|---|
| **Only manual testing on the maintainer's desktop** | Zero infrastructure | Regressions go unnoticed; claims can't be measured |
| **Full end-to-end on real desktops in CI for everything** | Realistic | Slow and flaky; portals need consent dialogs; GPU and licensing issues |
| **Layered: fakes + recorded fixtures + headless sessions + nightly live evals (recommended)** | Fast PR loop; realism where it matters | Fixtures need upkeep |

## Decision
1. **Unit tests** (pytest, no display):
   - Every interface (`Perception`, `Overlay`, `Actuator`, `Voice`, `Brain`, `CompositorBridge`, `Hotkeys`, `ShellHook`, `Policy`) has an in-memory **fake** in `tests/fakes/`.
   - Pure logic is tested against those fakes: step loop, plan validation, fingerprint scoring, struggle scoring and back-off, policy tiers, redaction, persona selection, pack parsing.
   - Property tests (Hypothesis) cover scorer monotonicity and the back-off invariants, for example "never more than N offers per hour".
2. **Integration tests on headless sessions** (CI, Linux runners):

   | Session | How it runs |
   |---|---|
   | AT-SPI | `dbus-run-session` + `at-spi-bus-launcher` + **fixture apps**: tiny GTK3, GTK4 and Qt6 apps with known widgets, menus and dialogs, kept in `tests/fixtures/apps/` |
   | **GNOME (reference)** | `dbus-run-session gnome-shell --headless --wayland --virtual-monitor 1920x1080` in an `ubuntu:26.04` container with the extension installed and enabled before shell start. D-Bus contract tests from Python. Synthetic clicks via the RemoteDesktop/EIS path or Mutter's virtual input for click-through. Flags present in `gnome-shell --help` 50.1; the full CI invocation is unverified until S1. Pure-JS helpers run under `gjs -m`. |
   | GNOME dev loop | `dbus-run-session gnome-shell --devkit --wayland` (needs `mutter-dev-bin`) on the maintainer's desktop (ADR-0023 §10) |
   | X11 (CI only) | **Xvfb** for AT-SPI fixture tests and EWMH bridge fakes. No product overlay tests. |
   | Wayland layer-shell (v0.2) | **Sway headless** (`WLR_BACKENDS=headless`). KWin `--virtual` for KWin-specific bridge tests; flags to be checked in the KWin port. |

   - Overlay assertions use screenshots of the headless output, and synthetic clicks through the virtual backends to prove click-through.
3. **Record and replay.**
   - **AT-SPI event streams** and **shell hook events** are recorded as JSONL (types and counts only, ADR-0010).
   - Struggle scenarios are replayed through the detector deterministically.
   - **Perception snapshots** (focused-window AT-SPI tree JSON, optional screenshot, ground-truth rects) feed the pointing harness.
   - **LLM responses** are recorded per prompt hash (VCR-style) so PR runs make zero API calls.
   - A stale-cassette check flags when a prompt template changes.
4. **Evaluation sets** live in `evals/` with versioned data and a runner:

   | Eval | Size (initial) | Metrics | Gate |
   |---|---|---|---|
   | Pointing (ADR-0007) | ~300 targets, 6 apps, EN and AR locales | pointed-correct, confidently-wrong, latency/tier | ≥ 80% correct; ≤ 2% confidently wrong (≤ 5% blocks release) |
   | Coordinate pipeline (ADR-0004) | 20 widgets × 4 scales × sessions | px error | median ≤ 4 px, p95 ≤ 12 px |
   | Struggle detector (ADR-0010) | 40+ labelled replays | precision, recall, time-to-offer | P ≥ 0.6, R ≥ 0.5 |
   | Plans (ADR-0008) | 30 tasks × 3 apps | task success in replay, steps, tokens, cost | no regression > 5% |
   | Pack task match (ADR-0012) | 30 phrasings × packs, EN/AR | accuracy | ≥ 85% |
   | Persona/tone (ADR-0013) | 100 lines/locale | rubric pass (LLM judge + spot check) | ≥ 90% |
   | Injection and policy (ADR-0014) | 50 adversarial fixtures + 200 policy cases | violations | 0 |
   | Voice (ADR-0011) | 60 utterances (local only, never committed) | WER, RTF, barge-in latency | per S8 |

5. **Cadence.**
   - On PR: unit tests, headless integration, and replay evals using cassettes.
   - Nightly: live LLM evals on a small budget with a cost cap, posting a trend summary as a CI artefact.
   - Before release: manual dogfood checklist on GNOME 50 Wayland (Ubuntu 26.04) at 100% and 150% scale with two monitors. KWin Wayland 6.6/6.8 is added from v0.2.
6. **Flake policy.**
   - Retry integration tests at most once.
   - A test that flakes twice in 7 days moves to a quarantine marker with an issue.
   - Quarantined tests never gate merges but stay visible.
   - Statistical evals use fixed seeds and report confidence intervals; they gate on thresholds, not exact values.
7. **Privacy in tests.** No real user content in committed fixtures. Recorded trees from real apps are scrubbed: names are kept and document text is removed. Voice recordings stay local.

## Consequences
- **Positive:** PRs stay fast and deterministic, the product claims become measurable, and regressions in accuracy are visible.
- **Negative:** fixture apps and cassettes need maintenance, and the headless compositor setup is fiddly.
- **Risks:**
  - Headless sessions behave differently from real desktops (scale, portals). Mitigated by the pre-release manual matrix.

## Validation plan
- The first CI milestone (with issue #4): a GTK4 fixture app plus AT-SPI lookup test passing in GitHub Actions under `dbus-run-session`.
- The second milestone: the extension's D-Bus contract and click-through test in a headless GNOME 50 shell.
- Track the CI duration budget: PR pipeline ≤ 10 min.

## Revisit if
- Headless Wayland proves unworkable in CI. Then move overlay tests to a self-hosted runner.
- Eval costs exceed budget.

## Sources
- gjs.guide debugging (devkit/nested): https://gjs.guide/extensions/development/debugging.html
- gnome-shell-pod (X11, ≤ 47): https://github.com/Schneegans/gnome-shell-pod
- Sway headless backend (wlroots `WLR_BACKENDS`): https://gitlab.freedesktop.org/wlroots/wlroots/-/blob/master/docs/env_vars.md
- at-spi2-core (bus launcher): https://gitlab.gnome.org/GNOME/at-spi2-core
- dogtail (GPL, test-only use per ADR-0020): https://gitlab.com/dogtail/dogtail
- [docs/research/linux-platform.md](../research/linux-platform.md): verification checklist section
