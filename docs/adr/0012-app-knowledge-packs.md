# ADR-0012: App knowledge packs: format, sources, retrieval, versioning, hooks

- Status: Proposed (v1 subset implemented: ADR-0027)
- Date: 2026-11-20
- Issue: #13 (designs #8)
- Depends on: ADR-0005, ADR-0008, ADR-0014
- Related: ADR-0010 (signal tuning), ADR-0021 (terminal and browser)

## Context
SPEC sets two constraints:
- **The core contains no app-specific code.** App knowledge lives in `packs/<app>/`.
- **The first pack is [workbench](https://github.com/AhmedYousriSobhi/workbench).**

### What workbench already exposes
Inspected through `gh api` on 2026-11-20:
- `AGENTS.md`, with ten verbs, endpoints and rules (for example, "never print a credential", and "destructive verbs need `--yes` when `BENCHCTL_AGENT=1`").
- `llms.txt`.
- An **MCP server** (`benchctl serve mcp`, stdio) whose tools are the verbs and whose resources are AGENTS.md, recipes and schemas.
- **JSON contract v2.5**, with schemas in `docs/agents/schemas/`.
- Recipes in `docs/agents/recipes/`.
- A user manual (`docs/manual/`).
- With `BENCHCTL_AGENT=1`, **one-line errors `CODE: message | fix: COMMAND`**, with stable codes such as `WB-REFUSED-MEMORY` listed in `docs/agents/ERROR-CODES.md`. This is a ready-made next-step source. It is **not directly observable** by Ya-Bro:
  - the shell hook sees exit codes, not stderr (ADR-0021);
  - the documented error codes do not map to distinct exit codes;
  - Ya-Bro must not set `BENCHCTL_AGENT=1` in the user's shell, because it changes `--yes` semantics and log behaviour.

  So code-level detail needs an app-side hook (below), or is read from the terminal *after* the user accepts help.
- AGENTS.md's own rule is to "never fit it to one app". Any hook we ask workbench for must therefore be generic and contract-versioned, not Ya-Bro-specific.
- The web UI `index.html` has **216 `id`s and 71 `aria-label`s**, so stable selectors exist for Firefox/Chromium AT-SPI and a future WebExtension. Its diagram is SVG/canvas-heavy, which AT-SPI sees poorly.
- `benchctl/pagefeed.py` already shows an app-side hook pattern: the CLI posts step results to the page on `127.0.0.1` with a token header.

### Prior art ([ai-tools.md §3.6](../research/ai-tools.md), [non-ai-tools.md §2, §8](../research/non-ai-tools.md))
- **Skilly's `SKILL.md`** is the closest existing model: front-matter with an app id, the app's vocabulary, common mistakes, and a staged curriculum.
- **Orca's per-app scripts** resolve in a fixed order: app, then toolkit, then default.
- **Mallard topic pages** are help pages that declare their own links, and `help:` URIs deep-link into them.
- **DAP flows**: Whatfix and WalkMe use smart selectors, reliability scores, visibility rules and auto-heal.
- **OpenAdapt** compiles recorded demonstrations into programs.
- **Apple App Intents** are app-declared semantic actions.

## Decision drivers
- Authoring cost for one maintainer, with packs eventually written by app authors.
- Retrieval quality versus latency and tokens.
- Robustness when the app's UI changes between versions.
- Safety: pack content is semi-trusted, and executable hooks are dangerous.
- A generic fallback for apps without a pack.

## Options considered
| Option | For | Against |
|---|---|---|
| **Pure docs + RAG (vector DB)** | Ingest anything | Adds an embedding dependency and index upkeep. Retrieval misses for UI-step questions. Little reason when packs are small. |
| **Long context only (dump all pack docs into the prompt)** | Simplest; caching makes it cheap after the first call | Breaks down beyond roughly 100k tokens, adds first-call latency, spends tokens on noise |
| **Structured task graphs only (WalkMe-style flows)** | Deterministic, fast, verifiable, no LLM per step | Expensive to author; only covers anticipated tasks |
| **Hybrid: structured tasks + small curated knowledge + lexical retrieval over docs + live sources (recommended)** | Common tasks are fast and exact. The long tail is LLM-planned and grounded in docs. Live sources (MCP, `--help`) stay current. | Two content kinds to maintain |

## Decision
**1. On-disk format.** One directory per app, data-first:

```
packs/<pack-id>/
  pack.toml          # id, name, version, app matchers, app version range, locales, trust, sources
  knowledge.md       # Skilly-style: vocabulary/aliases (EN+AR), mental model, common mistakes, gotchas
  tasks/*.yaml       # task graphs: goal, preconditions, steps[] (TargetSpec fingerprints, expect predicates, risk)
  docs/*.md          # Mallard-like topic pages with front-matter: topics, guides, app_version, source URL
  selectors.toml     # named element fingerprints (stable ids, role+name EN/AR, ancestors) + reliability score
  signals.toml       # struggle tuning: weight/threshold overrides + declarative app signals (ADR-0010)
  fixits.toml        # terminal rules: match(argv0, exit code [, error code from hook or post-consent text]) -> suggestion (ADR-0021)
  hooks.toml         # declared app-side hooks (state endpoints, MCP server, D-Bus), all opt-in
  tests/             # recorded fixtures for this pack's tasks (ADR-0016)
```

**2. `pack.toml` essentials:**
- `match`: any of `desktop_id` (e.g. `org.inkscape.Inkscape`), AT-SPI application name, process `argv0`, window class, browser URL pattern, or terminal `argv0`.
- `app_version`: a semver range, plus how to read the version (`--version`, AT-SPI `toolkit_version`, or a hook).
- `sources`: pointers rather than copies. Examples: `agents_md = "https://…/AGENTS.md"`, `llms_txt = …`, `mcp = { command = ["benchctl", "serve", "mcp"], cwd = "…" }`, `man = ["benchctl"]`, `help_uri = "help:inkscape"`.
- `trust`: `data-only` (default) or `hooks`, which needs the user to enable it per pack.

**3. Resolution order** (the Orca pattern): exact app pack, then toolkit pack (e.g. `gtk4-common`, `libreoffice-common`, `firefox`), then the core generic behaviour. Several packs may match, for example `firefox` plus `workbench-web`.

**4. Retrieval.**
- **Task match first.** Map the user's goal to `tasks/*.yaml` using the LLM, with task titles and descriptions in the cached prefix. A match gives deterministic steps (ADR-0008 fast path).
- **Knowledge always in context.** `knowledge.md` stays small (≤ 4k tokens) and sits in the cached prefix.
- **Docs.**
  - Packs under about 60k tokens: include them whole in the cached prefix.
  - Larger packs: **BM25 lexical retrieval** (pure Python, no vector DB) over doc chunks, retrieving the top 6.
  - Embeddings are revisited only if evals show BM25 misses.
- **Live sources at session start, all opt-in:**
  - MCP `list_tools` / `list_resources`;
  - `--help` and `man` output for terminal apps (cached per version);
  - the `llms.txt` index.

**5. Generic fallback for apps without a pack.** Build an ephemeral "auto-pack" at runtime:
- the app name and version;
- the AT-SPI menu bar structure (menu paths are great step targets);
- `--help`/`man` for CLIs;
- an `llms.txt` or `AGENTS.md` discovered in the app's repo or website (if the user approves a fetch);
- the Yelp/KHelpCenter `help:` index.

Accuracy is lower, and the bro says so once ("I don't know this app well yet, bro, bear with me").

**6. Versioning and drift.**
- Packs carry `app_version` ranges, and tasks can carry per-version overrides.
- Fingerprints tolerate drift through scoring (ADR-0005).
- User corrections land in `~/.local/share/ya-bro/pack-overrides/<pack-id>/`, never in the shipped pack.
- `broctl pack doctor <id>` replays `tests/` fixtures to flag selectors that broke in a new app version.

**7. App-side hooks.** These are an "app cooperates" path for apps we own:
- `hooks.toml` declares endpoints like `state = { kind = "http-local", url = "http://127.0.0.1:<port>/api/state", auth = "token-file:<path>" }`, or `mcp`, or `dbus`.
- Hooks are **read-only state reporters by default**. Actions over MCP count as Do-it actions under ADR-0009 risk policy, and need `trust = "hooks"` plus per-action confirmation at R2 and above.
- Token files are read, never printed or sent to the LLM (workbench rule).

**8. Authoring workflow.**
1. `broctl pack new <id>` scaffolds a pack.
2. `broctl pack record` (later) watches the maintainer perform a task, capturing AT-SPI fingerprints and predicates, and writes `tasks/<task>.yaml` (the OpenAdapt idea, without pixels).
3. The maintainer edits the YAML.
4. `broctl pack test` replays fixtures.

An Accerciser-like inspector mode in the overlay ("what's this element?") shows the fingerprint to copy.

**9. Security.**
- Pack text is **untrusted** for authority purposes. It can inform plans, but cannot grant risk-tier downgrades below the core deny-list (ADR-0014).
- Third-party packs install disabled-hooks by default.
- No pack ever contains Python code that core imports. If a future plugin API needs code, it is a separate trust level (ADR-0018).

### Workbench pack sketch
- `match`:
  - terminal `argv0 ∈ {benchctl, ./scripts/benchctl}`;
  - browser URL `http://127.0.0.1:*/` with page title "workbench" (exact matcher TBD);
  - desktop process name for the web UI server.
- `sources`: `AGENTS.md`, `llms.txt`, and `mcp = benchctl serve mcp` (read verbs only by default: `describe`, `get faults`, `get endpoints`, `get scenario-status`).
- `knowledge.md`: the vocabulary (governor, REFUSED, scenario, fault, lab), with mistakes taken from AGENTS.md rules ("REFUSED is a decision, not a bug; don't retry in a loop").
- `tasks/`:
  - `start-cluster.yaml`: `plan` → `start` → `wait ready` → open link;
  - `run-scenario.yaml`;
  - `clear-faults.yaml`;
  - `export-test-report.yaml`;
  - web-UI tasks using `selectors.toml` entries keyed on `aria-label`/`id`.
- `fixits.toml`: map `WB-*` codes from ERROR-CODES.md to explanations in EN and AR. Codes arrive from the state hook, or from the terminal text read after the user accepts help. The `| fix: COMMAND` part, or the table's Fix column, becomes a *suggested* command for the user to confirm (R2).
- `signals.toml`:
  - **without a hook:** three or more non-zero `benchctl` exits within 5 min form a failing-command loop (exit codes only);
  - **with the state hook:** the same `WB-` code twice within 5 min is an error loop, and a `WB-REFUSED-*` followed by a retry is a strong struggle signal (AGENTS.md: "do not retry in a loop").
- `hooks.toml`:
  - proposed cross-repo issue: workbench exposes a **generic, contract-versioned** `GET /api/state` on localhost, under the existing page token, with a JSON schema in `docs/agents/schemas/`.
    - It reports the current view, selected node, scenario status, and the **last CLI error code with its timestamp**.
    - It is useful to any client, which keeps to workbench's rule of not fitting itself to one app.
    - It mirrors the `pagefeed.py` pattern;
  - also `postMessage` for a future WebExtension.

## Consequences
- **Positive:**
  - The core stays app-agnostic.
  - Common tasks are deterministic and cheap.
  - Packs are reviewable data.
  - The workbench pack exercises the terminal, the browser and MCP at once.
- **Negative:**
  - Two content kinds (tasks plus docs) to maintain.
  - The recorder is extra work.
- **Risks:**
  - Pack rot as apps change. `pack doctor` and fixtures mitigate it.
  - MCP servers are code execution. They are opt-in, the user is shown the exact command, and they run under the user's own account.

## Validation plan
- **Spike within issue #8.** Write the workbench pack and a GIMP pack (5 tasks each).
  - Measure task-match accuracy over 30 phrasings (EN and AR): target ≥ 85% correct task or "no task".
  - Measure step success on the fast path.
  - Measure the token size of the cached prefix.
- **Generic fallback eval.** 10 tasks in an app with no pack (e.g. Kate). Record success, comparing auto-pack against no-pack.

## Revisit if
- Packs grow beyond about 60k tokens and BM25 retrieval misses (then add embeddings).
- MCP becomes a standard desktop API, which would mean preferring MCP actions over UI driving.
- App authors ask for a code plugin API.

## Sources
- workbench `AGENTS.md`, `llms.txt`, `benchctl/pagefeed.py`, `webui/static/index.html`: https://github.com/AhmedYousriSobhi/workbench (read 2026-11-20)
- Skilly SKILL.md: https://github.com/tryskilly/skilly
- Orca scripts and Mallard, Whatfix and WalkMe selectors: [docs/research/non-ai-tools.md](../research/non-ai-tools.md) §2, §7, §8
- OpenAdapt, Apple App Intents: [docs/research/ai-tools.md](../research/ai-tools.md) §2.2, §2.6
- llms.txt proposal: https://llmstxt.org/
- MCP specification: https://modelcontextprotocol.io/
