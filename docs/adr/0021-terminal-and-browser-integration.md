# ADR-0021: Terminal and browser integration

- Status: Proposed
- Date: 2026-11-20
- Issue: #13
- Depends on: ADR-0005, ADR-0010, ADR-0012, ADR-0014
- Why a separate ADR: the first pack (workbench) is a CLI plus a web UI, so the first demo runs in a terminal and a browser, not in GTK apps (SPEC §6). AT-SPI is weak inside both.

## Context

### Terminal ([non-ai-tools.md §12](../research/non-ai-tools.md))
- **Shell hooks.** Hooks capture exit codes reliably in every terminal:
  - bash via bash-preexec (DEBUG trap plus `PROMPT_COMMAND`);
  - zsh `preexec`/`precmd`;
  - fish `fish_preexec`/`fish_postexec`.
- **atuin** uses exactly this two-phase start/end hook and keeps a SQLite schema of id, timestamp, duration, exit, command, cwd and session.
- **OSC 133 semantic prompt marks** are supported by kitty, WezTerm, foot and **Konsole ≥ 22.08**. Support in VTE / GNOME Terminal is unclear.
- **Konsole's D-Bus interface** offers `getDisplayedText`, `sendText` and `foregroundProcessId`.
- **kitty** has `@ get-text --extent last_cmd_output`, and **WezTerm** has `cli get-text`.
- **VTE** exposes the terminal through AT-SPI (`terminal` role, Text interface).
- **thefuck-style rules**: `match` → `get_new_command` gives cheap offline fixes.
- **workbench** emits `CODE: msg | fix: COMMAND` lines (e.g. `WB-REFUSED-MEMORY`) only when `BENCHCTL_AGENT=1`, which Ya-Bro must not set in the user's shell. Its error codes do not map to distinct exit codes (ERROR-CODES.md).

### Browser ([linux-platform.md §3.11](../research/linux-platform.md))
- **AT-SPI.** Firefox and Chromium expose web content via AT-SPI, including ARIA labels and roles. Chromium may need a flag or an AT-detection trigger. The workbench page has 216 `id`s and 71 `aria-label`s.
- **CDP** needs `--remote-debugging-port`. Since Chrome 136, a non-default user-data-dir is required for remote debugging. It exposes powerful control to any local process.
- **Firefox** removed CDP in favour of WebDriver BiDi / Marionette.
- **WebExtensions plus native messaging** work in both Firefox and Chromium. They give the DOM, element rects and URL with user-installed consent.
- **Page-to-screen mapping** is pitfall-prone: window position, browser chrome offsets and `devicePixelRatio`.

## Decision drivers
- Exit codes and errors as struggle signals, without logging typed text (SPEC §7).
- Explaining the actual error once the user asks.
- Low setup friction.
- Security: no always-open debugging ports.
- Reuse of the coordinate pipeline (ADR-0004).

## Options considered
| Area | Option | For | Against |
|---|---|---|---|
| Terminal | Parse terminal output via AT-SPI or screenshots only | No setup | Misses exit codes; VTE-only; content-heavy |
| | **Ya-Bro shell snippet (bash-preexec / zsh / fish) → local spool + optional terminal adapters (recommended)** | Works in every terminal; exact exit codes; content-free by default | rc-file edit (opt-in) |
| | Read the atuin DB | Zero new hook if atuin is installed | Optional dependency; includes full command text |
| Browser | **AT-SPI first (recommended for MVP)** | Already built (ADR-0005); ARIA exposed; no extension | Coordinates via ADR-0004 only; Chromium flags |
| | WebExtension + native messaging (v0.3) | Exact DOM, rects, URL, page state; user-installed consent | Two browser stores; review |
| | CDP / BiDi automation | Powerful | Open debugging port is a local attack surface; Chrome 136 restrictions; feels like automation, not guidance |

## Decision
**Terminal**

1. **Shell hook (opt-in from first run or `ya-bro hook install`).**
   - Ya-Bro ships `ya-bro.bash` (via bash-preexec), `ya-bro.zsh` and `ya-bro.fish`.
   - On **preexec** the hook records `{ts, tty, cwd_hash, argv0, cmd_hash}`. On **precmd** it records `{exit, duration_ms}`.
   - Each record is one JSON line appended to `$XDG_RUNTIME_DIR/ya-bro/shell.spool`. That file lives on tmpfs, has mode 0600, and is truncated by core.
   - The hook writes **only if `$XDG_RUNTIME_DIR/ya-bro/` exists**. Core creates that directory on start and removes it on exit, so the spool cannot grow when Ya-Bro isn't running.
   - The write is non-blocking: no daemon dependency, no extra processes, and nothing happens if Ya-Bro isn't running. Core tails the file with inotify.
   - The hook also emits OSC 133 A/B/C/D and OSC 7, so capable terminals mark prompts.
2. **Content rule.**
   - The spool holds only `argv0`, hashes, exit codes and durations.
   - Once the user accepts help, the full last command and its output are read *then*, from shell history (`fc -ln -1`) and a terminal adapter.
   - The output is redacted (ADR-0014).
3. **Terminal adapters**, used to read the last command output or to type a suggested command:
   - **Konsole D-Bus** (KDE reference platform, first);
   - kitty (`allow_remote_control` required);
   - WezTerm CLI;
   - **VTE via AT-SPI Text** as the generic fallback.

   Typing a command into the terminal is **R2** (it needs confirmation) and **never presses Enter** for commands matching the destructive list (R3: the user runs it).
4. **Fix-it rules.**
   - Packs ship `fixits.toml` rules that match on `argv0` and the exit code for detection.
   - Optionally they also match an error code from an app state hook (ADR-0012), or from terminal text that is read only after the user accepts help.
   - The shell hook never captures stderr.
   - Each rule yields a suggestion plus an explanation in EN/AR.
   - Core ships generic rules: command not found (chained `command_not_found_handle`), permission denied, typo in a git subcommand.
   - Rules run before any LLM call.
5. **Struggle signals:** a failing-command loop and pack-declared error-code repetition (ADR-0010).

**Browser**

6. **MVP: AT-SPI only.**
   - Find web elements by ARIA role and name, or `id` where the browser exposes it.
   - Convert rects through ADR-0004 using the browser window's origin.
   - `doctor` checks that Chromium-based browsers expose web content and explains the flag if not.
7. **v0.3: optional WebExtension** (`ya-bro-bridge`) for Firefox and Chromium, using native messaging to core.
   - **Reads:** URL, title, element rects in CSS pixels plus `devicePixelRatio` and viewport offset, and the page-state hooks a site opts into (the workbench `postMessage` proposal in ADR-0012).
   - **Writes:** highlight scroll-into-view only. No form filling and no clicking via the extension; Do-it uses ADR-0009 like every other app.
8. **No CDP or WebDriver** in the product. They may be used in tests only.

## Consequences
- **Positive:**
  - Exact, content-free terminal signals work in every terminal.
  - Workbench errors become struggle signals and fix suggestions.
  - The web UI works on day one through AT-SPI.
  - No debugging ports are left open.
- **Negative:**
  - Requires an rc-file edit, which is opt-in.
  - The precision of web pointing depends on the browser's AT-SPI until the extension exists.
- **Risks:**
  - bash-preexec conflicts with existing DEBUG traps. Detect them and fall back to `PROMPT_COMMAND`-only (exit codes, no start time).
  - Chromium a11y tree performance on heavy pages.

## Validation plan
- Hook tests in bash, zsh and fish inside CI containers: the spool records the correct exit code and duration for 100 commands, adds no measurable prompt latency (< 5 ms), and produces no output when Ya-Bro is absent.
- Run the workbench pack end-to-end in spike S9: "start the cluster and run the node-down scenario". This covers terminal steps verified by exit codes, a fix-it on a forced `WB-` error, and web UI steps pointed via AT-SPI in Firefox. Go: ≥ 80% of steps pointed and verified.

## Revisit if
- VTE gains OSC 133 plus an API.
- Browsers expose better a11y on Wayland (screen coordinates).
- The WebExtension proves necessary earlier, for example if the workbench SVG views need DOM-level rects.

## Sources
- [docs/research/non-ai-tools.md](../research/non-ai-tools.md): §12 (shell hooks, atuin, OSC 133 table, Konsole/kitty/WezTerm APIs, thefuck)
- [docs/research/linux-platform.md](../research/linux-platform.md): §3.11 browser integration, §3.12 terminal
- bash-preexec: https://github.com/rcaloras/bash-preexec
- atuin: https://github.com/atuinsh/atuin
- Native messaging (MDN): https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Native_messaging
- Chrome remote debugging change: https://developer.chrome.com/blog/remote-debugging-port
- workbench AGENTS.md (error line format): https://github.com/AhmedYousriSobhi/workbench/blob/main/AGENTS.md
