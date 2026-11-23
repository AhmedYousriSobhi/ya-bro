# ADR-0027: Pack format v1 and loader

- Status: Accepted
- Date: 2026-11-23
- Issue: #8
- Refines: ADR-0012

## Decision
ADR-0012 designed packs; this records what v1 actually is.

- **TOML only, no YAML.** Tasks are `tasks/*.toml` in the existing plan format (`plans.py`), so one parser serves scripted plans and pack tasks, and core gains no YAML dependency. ADR-0012 said `tasks/*.yaml`.
- **`pack.toml`** has `[pack]` (`id`, `name`, `version` as `x.y.z`, optional `format = 1`, `trust` = `data-only` or `hooks`, `locales`), `[match]` and `[sources]`. `id` must equal the directory name.
- **Matchers are exact:** `desktop_ids`, `window_classes` (case-insensitive), `argv0`, and `urls` (fnmatch patterns). A pack needs at least one; an unknown matcher is an error, so a typo never silently matches everything or nothing.
- **`sources` are pointers** (strings or lists of strings, e.g. `mcp = ["benchctl", "serve", "mcp"]`). v1 stores them; nothing fetches or runs them yet.
- **`knowledge.md`** is capped at 16,000 characters (about 4k tokens, ADR-0012 §4).
- **Search order:** shipped `packs/`, then `$XDG_DATA_HOME/ya-bro/packs/`; a user pack replaces a shipped one with the same id.
- **A broken pack is skipped and reported**, never half-loaded (same rule as targets). Tasks are validated at load time. A task symlink leaving the pack is refused.
- **`fixits.toml`** (added with the workbench pack, #22): `[[fixit]]` rows of `code` (like `WB-REFUSED-MEMORY`), `meaning`, and either `suggest` or `hint`. `suggest` must start with one of the pack's own `argv0` commands (checked at load) and is only ever offered to the user, never run (R2, ADR-0009); anything else is a `hint` in plain words.
- **`[[element]]` in `pack.toml`** (added with #20): `role`, optional `name` (empty means any), `risk` 1 to 3 and/or `secret = true`. `LocalPolicy` takes the highest of the planner's tier, the pack's and the heuristics, so a pack can raise an element's risk or mark it secret and can never lower either (ADR-0012 §9). A secret element is treated like a password field: Show-me points at it as the user's own click, Do-it never acts on it. A pack applies only to its own app.
- **`signals.toml`** (added with #9): `[weights] signal = 0..3` and `[counts.signal] count, window` tune the struggle detector for that app, bounded at load; the detector re-checks the bounds. A pack tunes, it cannot force an offer (the threshold, caps and back-off stay in core).
- **`license`** (added with #26): an optional SPDX identifier or expression in `[pack]`; shipped packs must say `MIT`, checked by `scripts/check_licences.py`. A third-party pack declares its own.
- **Data only:** core reads packs and never imports or executes anything in one. `trust = "hooks"` parses but no hook is read yet.

## Not in v1
`selectors.toml`, `hooks.toml`, `docs/` retrieval, toolkit packs and the auto-pack fallback, overrides directory, `broctl pack new|test|doctor`, app version ranges. Each lands with the feature that needs it.

## Consequences
The Brain can later list a pack's tasks and knowledge for an app without app-specific core code. The workbench pack (#22) is the first real consumer; `packs/gnome-calculator` is the reference example.
