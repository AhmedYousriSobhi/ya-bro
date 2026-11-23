# ADR-0024: `broctl`, the control CLI

- Status: Accepted
- Date: 2026-11-22
- Issue: #45
- Depends on: ADR-0003, ADR-0014, ADR-0017

## Context
Management commands started as `ya-bro doctor` and `ya-bro setup`. The same name would also have to be the agent (daemon), and a growing set of management verbs (config, stats, forget, packs, per-app access) needs a predictable shape.

## Decision
1. **`broctl` controls the agent**, as `kubectl` controls a cluster. `ya-bro` stays the product name and the name of the agent process (a later issue); it carries no management subcommands.
2. **Grammar: `broctl <noun> <verb> [args]`**, with `--help` at every level and exit code 0 for success, 1 for a failed check or error.
3. **Commands today:** `version`, `doctor`, `setup`, `load`, `apps list|available|allow|revoke <app-id>`, `targets list|allow|revoke <id>` (ADR-0025), `point`, `scope watch`, `show <plan.toml>` (ADR-0026), `key set|status|clear` (the API key in the keyring, ADR-0014; `set` reads it from a hidden prompt, never from an argument).
4. **Planned (same grammar):** `config get|set|edit` and `stats`, `sent`, `forget` (ADR-0017, ADR-0014), `pack list|doctor` (ADR-0012).
5. **Safety:** commands that change persistent state ask first (`setup`) or are explicit about their effect (`apps allow|revoke`). There is no `--yes` flag for `setup`. `broctl` never prints secrets.
6. **Per-app scope:** `broctl apps` manages the default-deny allowlist (#43). An empty list means Ya-Bro sees no app.

## Consequences
- Positive: one discoverable entry point; the agent binary can stay minimal.
- Negative: docs and ADRs that said `ya-bro doctor` etc. were updated to `broctl`; any external notes are stale.
- Risk: `broctl` is a short name that may collide with another tool on some systems; revisit if it does.
