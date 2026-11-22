# ADR-0017: Configuration, state storage and observability

- Status: Accepted (config loader and log API implemented in #36; CLI, SQLite state, debug-content and retention pending)
- Date: 2026-11-20
- Issue: #13
- Depends on: ADR-0003, ADR-0010, ADR-0014

## Context
Ya-Bro needs four kinds of persistence:

1. **User configuration:** global and per-app settings, model routes, voice choices, humour level.
2. **Learned state:** struggle labels, per-app thresholds, pack overrides from corrections, portal restore tokens.
3. **Caches:** `--help` and `man` output, model weights, OCR data.
4. **Logs:** for debugging.

SPEC requires no telemetry by default. Logs must not capture content: "never typed text or screen content". The process model spans several processes (ADR-0003), so cross-process tracing matters.

## Decision drivers
- Users can read and edit their settings.
- XDG compliance.
- Logs are content-free by default but still useful for diagnosis.
- Debugging can be done locally without extra infrastructure.
- Simple: no database server.

## Options considered
| Option | For | Against |
|---|---|---|
| **TOML config + SQLite state + JSONL logs (recommended)** | `tomllib` is in the stdlib. SQLite is robust, single-file and in the stdlib. JSONL is greppable. | TOML writing needs `tomli-w` or a small writer |
| **GSettings / dconf** | Native on GNOME, live change notifications | Opaque to users, schema compilation step, less portable to macOS/Windows |
| **YAML config** | Familiar | Needs a dependency and has parsing pitfalls. Packs use YAML for task graphs because readability matters there; config does not need it. |
| **OpenTelemetry export** | Rich tracing | Needs a backend. Telemetry optics conflict with "local only". Optional at most. |

## Decision
1. **Locations (XDG):**

   | Kind | Path |
   |---|---|
   | Config | `$XDG_CONFIG_HOME/ya-bro/config.toml` |
   | Per-app config | `$XDG_CONFIG_HOME/ya-bro/apps/<pack-or-app-id>.toml` |
   | State | `$XDG_STATE_HOME/ya-bro/state.sqlite` (struggle events aggregated, offer labels, per-app thresholds, last-used language) |
   | Logs | `$XDG_STATE_HOME/ya-bro/logs/*.jsonl` |
   | Data | `$XDG_DATA_HOME/ya-bro/pack-overrides/`, user packs in `$XDG_DATA_HOME/ya-bro/packs/` |
   | Cache | `$XDG_CACHE_HOME/ya-bro/` (help text, model weights, OCR data) |
   | Runtime | `$XDG_RUNTIME_DIR/ya-bro/` (sockets, shell-hook spool, screenshot handles; mode 0700) |
   | Secrets | Secret Service via libsecret (API keys, portal restore tokens); `.env` fallback (ADR-0014) |

2. **Config schema.**
   - Typed with Pydantic (or `msgspec`), validated at load time.
   - Unknown keys produce a warning, not a crash.
   - `broctl config get/set/edit` CLI.
   - The settings UI (later) writes the same file.
   - Live reload is driven by a file-monitor signal from core.
   - Per-app files override global keys: `proactive.enabled`, `proactive.sensitivity`, `capture.allowed`, `do_it.allowed`, `humour`.
3. **Logs are content-free by construction.**
   - The log API accepts only typed records: event type, ids, durations, counts, confidence tiers, error classes and hashes.
   - Free-text fields are allowed only for Ya-Bro's own messages.
   - A unit test scans log records for disallowed field types.
   - Every record carries `session_id`, `task_id`, `step_id` and a `corr_id` that propagates across D-Bus calls, so a step can be traced through core, perceiver, overlay and actuator.
4. **Debug mode.**
   - `ya-bro --debug` raises the log level.
   - `--debug-content` additionally records prompts, element lists and screenshots to `$XDG_STATE_HOME/ya-bro/debug/<timestamp>/`.
   - Content logging needs an explicit flag each run. It auto-expires after 24 h, shows a visible avatar badge while on, and is never on by default.
   - `broctl sent` shows the "what was sent" log (ADR-0014).
5. **Local metrics.** These are computed from the logs. Nothing is exported.
   - Step latency percentiles.
   - Pointing outcomes per tier, including corrections.
   - Offers, acceptances and per-signal stats.
   - Token use and estimated cost per day.
   - `broctl stats` prints them. They also feed the dogfood metrics in ADR-0010 and ADR-0008.
6. **`broctl doctor`** reports:
   - session and backend selection (ADR-0002);
   - a11y bus status;
   - GNOME extension state, errors and API version (via `org.gnome.Shell.Extensions`), then layer-shell and KWin script availability (v0.2);
   - portal capabilities;
   - PipeWire AEC;
   - library versions (PyGObject, GTK, at-spi2-core);
   - API key presence (never its value).

   Its output is safe to paste into a bug report.
7. **Retention.** Logs are kept 7 days. Struggle state is kept 30 days. `broctl forget` deletes everything except config.
8. **Telemetry.** None. If ever added, it would need its own ADR, be opt-in, and be aggregate-only.

## Consequences
- **Positive:** transparent, portable (TOML and SQLite work on macOS and Windows), debuggable without leaking content, and consistent with the privacy ADR.
- **Negative:** no GNOME-native settings integration, and the content-free logs sometimes make bugs harder to diagnose. Use `--debug-content` for those cases.
- **Risks:** a developer adding a content field to logs. The log-scanning test guards against this.

## Validation plan
- A unit test asserts that log records contain no strings longer than N characters from untrusted sources.
- A `doctor` snapshot test runs on CI fakes.
- After one week of dogfooding, the maintainer can answer "why did the bro offer at 14:03?" from `broctl stats` and the logs alone.

## Revisit if
- Users want sync across machines (it would need an explicit design).
- GNOME integration is requested (a GSettings mirror).
- OpenTelemetry is wanted for development, as an opt-in exporter to a local collector only.

## Sources
- XDG Base Directory spec: https://specifications.freedesktop.org/basedir-spec/latest/
- Python `tomllib`: https://docs.python.org/3/library/tomllib.html
- libsecret: https://gnome.pages.gitlab.gnome.org/libsecret/
- SPEC.md §7; CLAUDE.md "Architecture rules"
