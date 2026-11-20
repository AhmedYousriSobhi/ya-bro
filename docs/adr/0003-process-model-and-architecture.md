# ADR-0003: Overall architecture and process model

- Status: Proposed
- Date: 2026-11-20
- Issue: #13
- Depends on: ADR-0001 (Python + GTK4), ADR-0002 (platform targets)

> **Amended for GNOME-first (2026-11-20).**
> - On the reference platform (GNOME 50) the compositor bridge **and** the always-on-top drawing are one GNOME Shell extension ([ADR-0023](0023-gnome-shell-extension-bridge.md)).
> - `ya-bro-overlay` (GTK4) still runs on GNOME. It hosts the focusable "ask" window, docked mode and settings. The layer-shell preload applies only to the KWin/wlroots backend (v0.2).
> - The stop key is also bound inside the extension, so the overlay hides even if core hangs.
> - The KWin script becomes the second bridge.

## Context
SPEC §6 names five components behind interfaces: Perception, Overlay, Actuator, Voice and Brain. Research turned up more things that need a home:
- a compositor bridge for window geometry, needed because AT-SPI cannot give global coordinates (ADR-0004);
- a struggle detector;
- a pack loader;
- a policy/safety engine;
- terminal and browser adapters.

Several technical facts shape how these split into processes:
- **AT-SPI calls are synchronous D-Bus round trips into other apps.** A hung or flooding app can stall the caller. Orca needs a priority queue, event coalescing and periodic cache clearing just to stay responsive ([non-ai-tools.md §2](../research/non-ai-tools.md)). at-spi2-core 2.60.1 started hiding "unresponsive applications" for the same reason.
- **`gtk4-layer-shell` must be loaded with `CDLL` before `import gi`** because it shims libwayland symbols ([linux-platform.md V3](../research/linux-platform.md)). That constrains whichever process hosts the overlay.
- **GTK must own its main loop on one thread.** PyGObject ≥ 3.50 ships native asyncio integration (`gi.events.GLibEventLoopPolicy`), marked experimental (https://pygobject.gnome.org/guide/asynchronous.html).
- **TTS engines are GPL.** Piper (piper1-gpl) and espeak-ng are GPL-3.0, so they must stay out of process if Ya-Bro is permissively licensed (ADR-0020).
- **"Stop" must halt within 500 ms** (SPEC §8), even while the LLM is mid-request or an app is hung.
- **Privilege separation lesson.** Cluely's unfiltered IPC bridge let a crafted link take screenshots ([ai-tools.md §3.5](../research/ai-tools.md)), which argues for narrow, whitelisted IPC between privileged parts.

## Decision drivers
- Overlay smoothness (60 fps pointer flight) must not depend on LLM or AT-SPI latency.
- Crash and hang isolation from third-party apps and from native ML engines.
- Simplicity for a single maintainer: few processes, one IPC style.
- Instant stop.
- License isolation.
- Testability with fakes (ADR-0016).

## Options considered
| Option | For | Against |
|---|---|---|
| **Single process (GTK main loop + asyncio + threads)** | Simplest to build and debug; no IPC | A hung AT-SPI call or native STT crash takes down the overlay and the stop button. Layer-shell's preload constraint leaks into everything. GPL TTS can't be loaded in-process. |
| **Core daemon + overlay process + workers (recommended)** | Overlay stays responsive. Perception hangs are isolated and restartable. Voice engines run as separate (Wyoming) services. Matches the Navisual and Clicky separation of UI shell from brain. | IPC schema to maintain; more moving parts; startup orchestration |
| **Microservices per component (each its own process)** | Maximum isolation | Overkill: about 7 processes, harder debugging, latency added at each hop |
| **Rust core + Python UI** | Performance, single binary | Contradicts ADR-0001. Latency is dominated by LLM round trips, not CPU. |

## Decision
**Four kinds of process plus in-compositor helpers.** All of them run in the user session, unsandboxed (ADR-0015).

```
        ┌──────────────── ya-bro-core (asyncio on GLib loop) ────────────────┐
        │  Brain (planner, step loop)   StruggleDetector   PackRegistry        │
        │  Policy/Safety engine         Persona            Config/State        │
        │  Session/Capability probe     TerminalHub        BrowserHub          │
        └───▲──────────────▲───────────────▲───────────────▲───────────────▲───┘
            │ D-Bus        │ D-Bus          │ D-Bus          │ Wyoming/TCP   │ D-Bus
   ┌────────┴──────┐ ┌─────┴────────┐ ┌─────┴────────┐ ┌─────┴──────┐ ┌──────┴─────────┐
   │ ya-bro-overlay│ │ ya-bro-      │ │ ya-bro-      │ │ voice svc  │ │ compositor     │
   │ GTK4: ask box,│ │ perceiver    │ │ actuator     │ │ (STT, TTS, │ │ bridge: GNOME  │
   │ docked; draws │ │ AT-SPI, OCR, │ │ AT-SPI Action│ │ VAD, wake) │ │ Shell ext (+   │
   │ only on layer-│ │ capture      │ │ portal+libei │ │ separate   │ │ overlay); KWin │
   │ shell (v0.2)  │ │              │ │ (on demand)  │ │ processes  │ │ script (v0.2)  │
   └───────────────┘ └──────────────┘ └──────────────┘ └────────────┘ └────────────────┘
```

1. **`ya-bro-core`**
   - Runs on a single asyncio loop on top of GLib, via `GLibEventLoopPolicy`, so Gio D-Bus calls are awaitable.
   - Owns all state and decisions.
   - Has no GTK widgets. It uses GLib/Gio only, so it can also run headless in tests.
   - LLM calls are async HTTP using the Anthropic SDK's async client.
2. **`ya-bro-overlay`**
   - A GTK4 process that only draws. It accepts declarative draw commands, such as `show_step(target_rect, bubble_text, style)`, `fly_pointer(to)`, `hide()` and `set_interactive_regions(...)`.
   - It emits user events back to core: click on avatar or bubble buttons, text input.
   - On GNOME (reference) the always-on-top drawing is done by the Shell extension. This process keeps the focusable "ask" window, docked mode and settings (ADR-0006, ADR-0023).
   - On KWin/wlroots (v0.2) it draws everything itself and preloads layer-shell.
3. **`ya-bro-perceiver`**
   - Hosts the AT-SPI event listener and queries, plus OCR and screen capture.
   - Publishes coalesced, typed events (content-free for struggle detection, ADR-0010) and answers element queries.
   - Every query has a deadline (default 300 ms). On timeout core gets a "target app unresponsive" result instead of hanging.
   - Core restarts it on crash.
4. **`ya-bro-actuator`**
   - Started only when Do-it mode is enabled (ADR-0009).
   - Holds the portal/EIS session (XTest only in X11 CI tests).
   - Receives single, policy-approved actions with a cancellation token. It never accepts free-form commands.
5. **Voice services**
   - STT, TTS, VAD and wake word run as separate processes speaking the **Wyoming protocol** (MIT) over a local socket (ADR-0011).
   - This isolates GPL engines and native crashes, and lets users point Ya-Bro at existing Wyoming servers.
6. **Compositor bridge** (ADR-0004)
   - In-compositor code: first the GNOME Shell extension (MVP, ADR-0023), then a KWin script loaded at runtime through `org.kde.KWin /Scripting` (v0.2).
   - Reports window geometry and focus to core over D-Bus. On GNOME the same extension also renders the overlay and owns a stop key binding.

**IPC.**
- **Control plane:** the D-Bus session bus, one well-known name per process under the `io.github.ahmedyousrisobhi.YaBro.*` prefix (the reverse-DNS form is a proposal). Reasons:
  - the compositor bridges (KWin `callDBus`, GJS `Gio.DBus`) can only talk D-Bus easily;
  - it is introspectable;
  - it is already in the GLib loop.

  Use Gio directly, or `dasbus` (LGPL, GLib-native) as a thin helper.
- **Bulk data** (screenshots, crops) moves as memfd or files in `$XDG_RUNTIME_DIR/ya-bro/` (tmpfs, 0700) and is referenced by handle. It is never base64 on the bus.
- **Schema:** method signatures are versioned (`...YaBro.Overlay1`) and listed in `src/ya_bro/ipc/`. No method takes code or a shell string.

**Threading rule.** No blocking calls on any GLib main loop. CPU-bound or blocking native work (OCR, image diff) goes to `asyncio.to_thread` inside perceiver, never in overlay or core.

**Stop path (within 500 ms).** The global stop hotkey is registered by core (ADR-0011 hotkeys). On GNOME it is an extension key binding that hides the overlay locally and emits `UserEvent(stop_key)` to core. Pressing it:
1. cancels the current asyncio task tree (LLM stream, step loop);
2. sends `Actuator.Abort` and `Overlay.Hide` as fire-and-forget D-Bus signals;
3. stops TTS playback.

The actuator checks its cancellation token before every injected event. The overlay also listens to the same signal directly, so a stuck core cannot keep drawing.

**Mapping to SPEC interfaces.** `Perception` → perceiver plus `CompositorBridge`; `Overlay` → overlay process or Shell extension; `Actuator` → actuator; `Voice` → voice services; `Brain` → core. The new interfaces are `CompositorBridge`, `Capture`, `IdleSource`, `Hotkeys`, `ShellHook`, `SecretStore` and `Policy`, listed in ADR-0018.

**Lifecycle.**
- `ya-bro` starts core, and core spawns and supervises the children with restart and backoff.
- Optional systemd `--user` units come later (ADR-0015).
- A single-instance lock is the D-Bus name ownership.

## Consequences
- **Positive:**
  - The overlay stays smooth.
  - Hung apps cannot freeze the bro.
  - GPL engines are isolated.
  - Every boundary can be faked in tests.
  - The GNOME extension slots in as just another overlay/bridge implementation.
- **Negative:**
  - IPC schema upkeep.
  - Debugging spans processes. Mitigation: a shared correlation id in structured logs (ADR-0017).
- **Risks:**
  - PyGObject asyncio integration is marked experimental. Fallback: run asyncio in a dedicated thread and bridge with `GLib.idle_add`. That fallback is the classic pattern, more code but stable.
  - D-Bus latency per call is about 0.1–1 ms, which is negligible against the budget.

## Validation plan
- **Spike within S1 (GNOME extension bridge + overlay; the Python side is the ask window and core).**
  - Overlay process at 60 fps pointer flight while perceiver is blocked by a deliberately hung test app; no dropped frames over 50 ms.
  - Stop → overlay hidden in under 150 ms (p95) measured with timestamps.
- **Chaos test in CI.** Kill perceiver and voice processes during a scripted step loop. Core must recover within 2 s and say so ("lost sight of the app for a second, bro").

## Revisit if
- IPC overhead shows up in step latency (> 100 ms of the 3 s budget).
- Single-maintainer complexity proves too high. Then merge perceiver into core with a watchdog thread.
- A port to macOS/Windows needs a different bus. Then the IPC adapter changes, not the process split (ADR-0018).

## Sources
- PyGObject asyncio guide: https://pygobject.gnome.org/guide/asynchronous.html
- gbulb README (superseded by PyGObject 3.50): https://pypi.org/project/gbulb/
- gtk4-layer-shell linking caveat: https://github.com/wmww/gtk4-layer-shell (`linking.md`)
- Wyoming protocol: https://github.com/rhasspy/wyoming
- [docs/research/non-ai-tools.md](../research/non-ai-tools.md): §2 Orca event handling
- [docs/research/ai-tools.md](../research/ai-tools.md): §3.5 Cluely IPC lesson, §2.1 Navisual architecture
- [docs/research/linux-platform.md](../research/linux-platform.md): V3, V4 (at-spi2-core unresponsive-app handling)
