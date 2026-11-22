# ADR-0025: Pack-scoped targets (tools with a web UI and a CLI)

- Status: Proposed
- Date: 2026-11-22
- Issue: #47
- Depends on: ADR-0012, ADR-0021, ADR-0023, #43 (per-app allowlist)

## Context
The per-app allowlist (#43) gives Ya-Bro one or more whole apps. Tools such as workbench (CLI `benchctl` plus a web page) have no app of their own: the web page lives in a browser tab and the CLI in whatever terminal the user opens. Allowing "Chromium" or "Terminal" would expose every tab and every shell, which breaks default-deny in spirit.

## Decision (proposed)
1. **A target is the unit of consent.** `target = id + optional web origins + optional CLI command names`, declared by a pack (ADR-0012) or by a user file `$XDG_CONFIG_HOME/ya-bro/targets/<id>.toml`:
   ```toml
   [target]
   id = "workbench"
   [web]
   origins = ["http://127.0.0.1:8080"]
   [cli]
   commands = ["benchctl"]
   ```
2. **Default-deny stays.** Nothing is reported for a browser or terminal until a target is allowed, and then only what matches the target.
3. **Web.** A browser window is reportable only while its active tab's origin matches. The web UI can also report its own state to core (workbench `/api/state`, #31), which avoids reading the browser's accessibility tree for that page.
4. **CLI.** The shell hook (ADR-0021) forwards only events whose command name is in `commands`: name, exit code and counts, never arguments or output.
5. **Commands.** `broctl targets list|allow|revoke <id>` (follow-up). `broctl apps available` already lists installed app ids.

## Open questions (must be answered before Accepted)
- **How the extension learns the active tab's origin.** It cannot read a URL, so it does not try. Spike S8 tested a **secret title token**: core gives a random per-run token only to a request with the allowed `Origin`; the page puts it in `document.title`; core pushes live tokens to the extension (`Bridge1.SetScopeTokens`, core only, memory only); a window is in scope only while its title contains one, and leaves scope on the next title change. In the headless shell the window entered and left scope in about 25 ms and the removal was emitted ([findings](../research/spikes/S8-active-tab-scope.md)). **Not yet verified:** a real browser (the installed ones are snaps and cannot run under the harness), and the `Origin`-gated issuance.
- **Why a title token is not the weak "match on title" idea.** Matching on page-controlled text is unsafe because any page can write it. A secret that only the allowed origin can obtain cannot be copied by another tab. The accepted leak: anything that reads window titles can see the token while that tab is active.
- Other candidates (not tested): reading the URL bar over AT-SPI, a browser extension.
- Browsers expose little content to AT-SPI unless started with accessibility flags (ADR-0021).

## Consequences
- Positive: Ya-Bro can help with CLI and UI tools without seeing other tabs or shells.
- Negative: more moving parts; depends on packs (#8), the shell hook (#21) and the open question above.
- Until this is Accepted and built, the only scope available is a whole app.
