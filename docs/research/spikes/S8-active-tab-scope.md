# Spike S8: scoping the browser to one web UI (issue #47, ADR-0025)

Question: how can Ya-Bro see only the one web page the user allowed (for example workbench) and not the other tabs, given that the Shell extension cannot read a tab's URL?

## Approach tested: secret title token
1. Core hands a random per-run token only to a request whose `Origin` header is the allowed origin (browsers set `Origin`; a page on another origin cannot forge it or read the response without CORS). **Not built or tested here.**
2. The allowed page writes the token into `document.title`.
3. Core pushes live tokens to the extension with the new core-only `Bridge1.SetScopeTokens(as)`. Tokens stay in memory, are ignored below 16 characters (max 8), and count only while core owns its bus name, so they die with core.
4. The extension treats a window as in scope while its title contains a live token, re-evaluated on `notify::title`. A browser shows the active tab's title in the window title, so switching tabs should drop the window by itself.
5. On leaving scope the extension emits `WindowsChanged` (removed), stops geometry for it, and hides the overlay if it was following that window.

Separately, the `allowed-apps` change from #43 now also re-evaluates windows (`changed::allowed-apps`); before, a window kept a stale state until its next event.

## Measured (isolated headless shell, GTK4 stand-in window, 3 runs)
Stand-in: `tests/fixtures/apps/title_fixture.py`, an app whose id is not allowed and whose title is set from stdin.

| Check | Result |
|---|---|
| Unlisted without a token | pass |
| Non-core caller of `SetScopeTokens` | denied (`AccessDenied`) |
| Listed after the title carries the token | 0.026 to 0.027 s (3/3) |
| Dropped after the title changes | 0.022 to 0.024 s (3/3) |
| `WindowsChanged` removal reaches core | 0.022 to 0.025 s (3/3) |
| Clearing tokens drops the window | pass |
| Token shorter than 16 chars is ignored | pass |

Timings are bounded by the 10 ms polling loop and a D-Bus round trip, so read them as "under about 30 ms", not precise latencies.

## Real browser (Chrome for Testing 159, not a snap)
The system Chromium and Firefox are snaps, which run against the real user session and are not used (CLAUDE.md harness rules). Instead the test uses Playwright's Chrome for Testing from `~/.cache/ms-playwright` with a throwaway profile, `--ozone-platform=wayland --disable-gpu --no-sandbox` (the sandbox is off only because it fails under user-namespace limits; the browser loads only pages the test serves on loopback), in the isolated headless shell (`tests/fixtures/shell_browser.py`, `pytest -m gnome_measure`).

| Check | Result |
|---|---|
| Page A fetches the token (same origin, `X-YaBro: 1` header) | issued |
| Tab A (token in title) in scope after core pushes it | 0.024 to 0.025 s |
| Switch to tab B (other origin): window out of scope | 0.021 s |
| Tab B's attempt to read the token | blocked (CORS preflight refused, title "other site (blocked)") |
| Switch back to tab A: in scope again | 0.022 s |
| Tokens cleared: out of scope | pass |

Observations: the browser's first page load took about 25 s in this software-rendered session (cause not investigated), so the test waits for it. The window's `app_id` came back as `com.anthropic.Claude` for this Chrome build, unexplained, which is one more reason not to key on app ids for browsers. The first check ("invisible without a token") passes with zero windows listed and does not by itself prove the browser window was mapped at that point; the later in-scope check does.

## NOT verified
- Firefox and the snap Chromium (title format `<title> - Mozilla Firefox` / `- Chromium` is expected to work, unconfirmed).
- Core-side token issuance is only simulated by the test server (the real `Origin`/CORS behaviour was exercised in Chrome, but core does not exist yet). The workbench page change (it must write the token into its title; tracked with #31). The spike used a stand-in, not workbench.
- Pages that never set a title, or pages whose title another script overwrites.
- Multiple windows of the same browser, private windows, and tab-title truncation in long titles.

## Accepted leak
The token sits in the window title, so anything that reads titles can see it while that tab is active: the window switcher, screen sharing, and other accessibility clients. It is per run and can be rotated by core, but it is not secret from the user's own session. It grants only "this window is in scope", never data.

## Alternatives not tested
- Reading the URL bar over AT-SPI: needs the browser's whole accessibility tree, which is the exposure we are avoiding.
- A browser extension: one more thing to install and trust.

## Verdict
Works with a real browser: in scope when the active tab carries the token, out of scope about 20 ms after a tab switch, and another origin cannot obtain the token. ADR-0025 can move to Accepted once core issues tokens for real and workbench writes one into its title (#31); until then it stays **Proposed**.
