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

## NOT verified
- **A real browser.** Chromium and Firefox on this machine are snaps. A snap launcher runs `snap-confine` against the real user runtime dir and session, which the harness rules (CLAUDE.md) forbid for tests, so no browser was started. The whole claim "a tab switch changes the window title and the window drops out of scope" is therefore **untested on a browser**. Chromium shows `<title> - Chromium`; Firefox `<title> - Mozilla Firefox`; both are expected to work but unconfirmed. A non-snap browser build (or a distro package) in the private session would settle it.
- Step 1 (token issue by `Origin`) and the workbench page change (it must write the token into its title; tracked with #31). The spike used a stand-in, not workbench.
- Pages that never set a title, or pages whose title another script overwrites.
- Multiple windows of the same browser, private windows, and tab-title truncation in long titles.

## Accepted leak
The token sits in the window title, so anything that reads titles can see it while that tab is active: the window switcher, screen sharing, and other accessibility clients. It is per run and can be rotated by core, but it is not secret from the user's own session. It grants only "this window is in scope", never data.

## Alternatives not tested
- Reading the URL bar over AT-SPI: needs the browser's whole accessibility tree, which is the exposure we are avoiding.
- A browser extension: one more thing to install and trust.

## Verdict
Mechanism works in the compositor (listed and dropped in about 25 ms, revocation emitted, tokens memory-only). ADR-0025 stays **Proposed** until a real browser passes and the `Origin`-gated token issuance is built.
