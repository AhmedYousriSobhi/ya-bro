# Non-AI prior art: how existing tools solve Ya-Bro's sub-problems

> **Scope.** This survey covers non-LLM tools and libraries that already solve parts of what Ya-Bro needs: accessibility-tree perception, overlays, input injection and observation, step-by-step tours, struggle detection, help systems, the voice pipeline (wake word, VAD, STT, TTS, AEC) and terminal integration. For each tool it records what Ya-Bro should borrow and what it should avoid.
> **Date:** 2026-11-20. Repository status ("last push") comes from the GitHub API on that date unless stated otherwise. Licenses come from the repo's LICENSE file or the model card. **"(unverified)"** marks claims that rest on recall or secondary sources and that were not confirmed in a primary source.
> **Note on licensing.** Ya-Bro does not have a LICENSE file in the repo yet, and SPEC.md (open question 5) proposes **MIT or Apache-2.0**. Several of the best components are GPL-3.0, AGPL or non-commercial. Because the proposed license is permissive, running GPL components (Piper, espeak-ng, dotool) **out of process**, as separate executables or services, matters for the component choices below (general practice, not legal advice).

## 1. Summary table

| Tool | Area | How it works (1 line) | Status / license | Borrow / avoid for Ya-Bro |
|---|---|---|---|---|
| Orca | Screen reader | Atspi GI event listener feeding a priority queue, with per-app and per-toolkit Python "scripts" | Active (51.1, Oct 2026); LGPL-2.1+ (unverified) | **Borrow**: event filtering and coalescing, cache invalidation, app/toolkit script lookup as the pack model |
| Accerciser | A11y inspector | GTK AT-SPI tree browser with an IPython console | GNOME project (status unverified) | **Borrow** as the pack-authoring and debugging tool |
| dogtail | GUI testing | pyatspi-based search by role and name, then actions | Last push Oct 2026; GPL-2.0 | Borrow its predicate-search idea; avoid as a dependency (GPL-2.0, test-oriented) |
| LDTP2 | GUI testing | AT-SPI automation with a Windows-style API | Dead (last push 2021); LGPL-2.1 | Avoid |
| pyatspi2 vs Atspi GI | A11y bindings | pyatspi is a Python wrapper over the libatspi GObject-introspection API | Both ship with at-spi2 | **Use Atspi GI directly**, as current Orca does |
| Odilia | Screen reader (Rust) | Async atspi crate plus speech-dispatcher | Beta, "not production ready"; MIT | Watch it; the Rust `atspi` crate is a possible future perf path |
| Newton | Wayland a11y proposal | Pushes a11y trees through the compositor | Prototype (unverified) | Track it; AT-SPI on Wayland lacks global coordinates |
| SikuliX | Visual automation | OpenCV template matching plus Tesseract OCR | Archived (repo moved to oculix-org, archived); MIT | Borrow the "image as fallback selector" idea; avoid the Java stack |
| PyAutoGUI | Visual automation | Screenshot plus locateOnScreen, and X11 input via Xlib | Last push Aug 2024; BSD-3 | Avoid (X11-only input, slow matching) |
| pywinauto | Windows UIA automation | UIA/Win32 backends with spec-based element lookup | Active; BSD-3 | Borrow the "window spec / best-match" selector idea |
| xdotool | Input (X11) | XTEST injection plus window search | Active (Sep 2026); BSD-3 | **Use on X11** (first target) |
| ydotool | Input | Daemon writes to /dev/uinput | Last push Dec 2025; AGPL-3.0 | Avoid by default (root/udev, bypasses compositor, AGPL) |
| dotool | Input | Reads commands on stdin and writes to uinput, keymap-aware via xkbcommon | Active; GPL-3.0-only | Fallback only, run out of process |
| wtype | Input (Wayland) | virtual-keyboard-unstable-v1 | Active; MIT | Not on KWin (protocol not supported by KWin, unverified) |
| wdotool | Input (Wayland) | libei via RemoteDesktop portal, wlr protocols, KWin scripts, GNOME extension | Early; MIT OR Apache-2.0 (README) | **Borrow its backend matrix**; the KDE path is not yet smoke-tested |
| libei / libeis | Input (Wayland) | Emulated-input protocol granted by the portal | Freedesktop; MIT (unverified) | **Target for Wayland injection** |
| kdotool | Window control (KDE) | Generates a KWin script and loads it over D-Bus | Active (Sep 2026); Apache-2.0 | **Borrow** for KWin window queries |
| input-remapper / keyd | Input remapping | evdev grab and uinput re-emit | Active; GPL-3.0 / MIT | Avoid (grabbing devices is too invasive for a helper) |
| AutoKey | Automation (X11) | Python scripts with X11 key hooks | Active; GPL-3.0 | Borrow the "phrase + script" UX idea only |
| Hammerspoon | macOS automation | Lua with eventtap (CGEventTap) and canvas (overlay drawing) | Active; MIT | **Borrow the API shape** of eventtap and canvas for our overlay layer |
| AutoHotkey | Windows automation | Low-level keyboard/mouse hooks with a hotkey DSL | Active; GPL-2.0 | Borrow hotstring/context-sensitive hotkey ideas |
| Espanso | Text expander | X11: XRecord. Wayland: reads /dev/input evdev with xkbcommon | Active (v2.4.1, Sep 2026); GPL-3.0 | **Borrow** its observation design; note the input-group requirement on Wayland |
| Shepherd.js | Web tour | SVG overlay with rounded-rect cutouts, in-house flip/shift positioning | Active (v16); **AGPL-3.0 or commercial** | Borrow patterns only (no code) |
| driver.js | Web tour | SVG evenodd path cutout, live region, dummy element when the target is missing | Active (1.14.0, Nov 2026); MIT | **Borrow** patterns and code ideas |
| Intro.js | Web tour | Absolutely positioned helper layer plus a tooltip; ships an RTL stylesheet | Active (8.7.0); **AGPL-3.0 or commercial** | Borrow the RTL idea only |
| React Joyride | Web tour | @floating-ui/react-dom with scrollparent-based scrolling | Active (3.2.0); MIT | Borrow its step-status state machine |
| WalkMe / Whatfix / Pendo / Appcues / Userlane | DAP | Captured-element selectors plus a runtime matcher, flow recorder, analytics | Commercial SaaS | **Borrow**: multi-attribute selectors, reliability score, auto-reselect/heal, visibility rules |
| FullStory / Clarity / Hotjar / PostHog | Frustration analytics | Client-side heuristics over clicks, DOM mutations and errors | SaaS; PostHog JS is open source | **Borrow PostHog's published thresholds** |
| Yelp / Mallard | Help system | Topic-oriented XML pages with `ghelp:`/`help:` URIs | Active GNOME; GPL-2.0+ (unverified) | Borrow "help:" deep-link idea and topic-oriented pack docs |
| KHelpCenter, Welcome Center, GNOME Tour, "What's This?" | Help/onboarding | Docs browser; first-run carousel; per-widget help pointer mode | Active KDE/GNOME | Borrow "What's This?" as a user-invoked "explain this" mode |
| Gromit-MPX | Screen annotation | Full-screen transparent GTK window with toggled input grab; Wayland via XWayland | Active (Sep 2026); GPL-2.0 | Borrow the hotkey toggle between "draw" and "pass-through" |
| ksnip / Flameshot | Annotation | Screenshot, then annotate a static image | Active; GPL-3.0 | Not applicable to a live overlay |
| KWin Mouse Mark / Track Mouse | Compositor effects | Draws inside the compositor | KDE | Ideal rendering location, but would require a KWin effect or script |
| screenkey / key-mon | Key display | Screenkey: X11 key events in an overlay window | screenkey on GitLab (status unverified); key-mon dead (2015) | Borrow the click-through, always-on-top OSD pattern |
| Shimeji-ee, eSheep (desktopPet), xpenguins, oneko | Desktop pets | Shaped or transparent top-level windows that walk along window edges | desktopPet active (MIT) | **Borrow** "avatar lives on window edges" behaviour |
| koverlay | Wayland overlay | Qt6 + LayerShellQt, overlay layer, click-through | Small (last push Oct 2025); MIT | **Borrow** the layer-shell recipe (gtk4-layer-shell on Plasma Wayland) |
| MangoHud | In-game overlay | Vulkan layer / OpenGL preload drawing inside the app | Active; MIT | Avoid (in-process injection) |
| Talon Voice | Voice control | Proprietary engine, `.talon` context-scoped command files, noise triggers, eye tracking | Free, closed source (unverified); community scripts MIT | **Borrow** context-scoped grammars (app/title) as pack voice commands |
| Numen | Voice control (Linux) | Vosk + dotool, phrase files | AGPL-3.0-only | Borrow the phrase-file idea; avoid code (AGPL) |
| Wyoming | Voice protocol | JSONL header plus PCM over TCP | Active; MIT | **Adopt** as the internal voice service protocol (on localhost) |
| Rhasspy 3 | Voice toolkit | Pipeline of Wyoming programs | Archived (Dec 2023); MIT | Superseded by Wyoming plus HA |
| OVOS / Mycroft | Voice assistant | Message bus, listener, intent and skills plugins | OVOS active (Apache-2.0); mycroft-core archived | Borrow the plugin interfaces; avoid the whole stack |
| HA Assist pipeline | Voice pipeline | wake → STT → intent → TTS as staged events | Active; Apache-2.0 | **Borrow** the stage/event model |
| openWakeWord | Wake word | Frozen melspec + embedding backbone, small per-word classifier | Code Apache-2.0; **pretrained models CC BY-NC-SA 4.0**, English only | **Borrow**; train our own word, check licenses of backbone files |
| Porcupine | Wake word | Proprietary engine with Console-trained keywords | Repo Apache-2.0 but **needs AccessKey**; no Arabic | Avoid |
| microWakeWord | Wake word | TFLite-Micro streaming MixConv model | Early release; Apache-2.0 | Option for later; training is "very difficult" by its own README |
| Snowboy / Precise | Wake word | DNN hotword / GRU | Dead (2021 / 2023) | Avoid |
| Silero VAD | VAD | Small ONNX/PyTorch model, 30 ms+ chunks | Active (v6.2.3); MIT | **Use** |
| WebRTC VAD | VAD | GMM-based frame classifier | py-webrtcvad last push 2024; MIT wrapper | Use only as a cheap pre-gate |
| TEN VAD | VAD | Low-latency frame-level model | Active; **Apache-2.0 plus Agora non-compete conditions** | Avoid as a default (not OSI-open) |
| pyannote | Diarization/VAD | PyTorch segmentation pipelines | Active; MIT (some models gated) | Not needed (single user) |
| whisper.cpp / faster-whisper | STT | Whisper on ggml / CTranslate2 | Active; MIT | **Use** for Arabic+English (large-v3 or turbo) |
| distil-whisper | STT | Distilled Whisper | English-only checkpoints | Avoid for Arabic |
| Vosk | STT | Kaldi-based streaming | Active; Apache-2.0 (Arabic models Apache or AGPL) | Use only for small command grammars |
| Parakeet / Canary (NVIDIA) | STT | FastConformer | CC-BY-4.0; **no Arabic** in v3/v2 cards | Avoid for Arabic |
| NVIDIA Arabic FastConformer | STT | Hybrid TDT/CTC with diacritics and punctuation | CC-BY-4.0; non-streaming | **Evaluate** for Arabic-only |
| Moonshine | STT/TTS | Small streaming models | Code MIT; **legacy Arabic STT models non-commercial** | Evaluate (verify Arabic license per model) |
| sherpa-onnx | Runtime | ONNX runtime for many STT/TTS/KWS/VAD models | Active; Apache-2.0 | **Use** as a single runtime |
| Piper | TTS | VITS via ONNX, espeak-ng phonemes, built-in Arabic tashkeel | Moved to OHF-Voice/piper1-gpl; **GPL-3.0** (old rhasspy/piper MIT, archived) | **Use** out of process; ar_JO-kareem only Arabic voice |
| Coqui TTS / XTTS-v2 | TTS | GPT-style voice cloning | Coqui closed; idiap fork MPL-2.0; **XTTS weights CPML** | Avoid weights |
| espeak-ng | TTS/phonemizer | Formant synth and rules | Active; GPL-3.0 | Use only via Piper |
| Kokoro / MeloTTS | TTS | Small neural TTS | Apache-2.0 / MIT; **no Arabic** | English voice candidates |
| F5-TTS | TTS | Flow matching | Code MIT; **weights CC-BY-NC-4.0** | Avoid weights |
| Chatterbox | TTS | 0.5B multilingual incl. Arabic | MIT; **retired Aug 2026** | Avoid (unmaintained) |
| Fish-speech / OpenAudio | TTS | LLM-style TTS | Fish Audio Community License (revenue threshold) | Avoid |
| MMS-TTS (ara) | TTS | VITS per language | CC-BY-NC-4.0 | Avoid |
| Azure / Google / ElevenLabs / OpenAI TTS | Cloud TTS | Hosted neural voices | Commercial | Azure has **ar-EG** Salma/Shakir; Google has only ar-XA (MSA) |
| Mishkal / CATT / Shakkala | Tashkeel | Rules / transformer / RNN | GPL-3.0 / Apache-2.0 / unclear | CATT if Piper's built-in is weak |
| PipeWire echo-cancel | AEC | WebRTC AEC as a virtual source and sink | Active | **Use** for barge-in |
| bash-preexec, zsh/fish hooks | Shell hooks | preexec/precmd callbacks | Active; MIT | **Use** |
| atuin | Shell history | Hooks call `atuin history start/end`; SQLite `history` table | Active; MIT | **Borrow** its schema and hook design |
| OSC 133 / OSC 7 | Terminal protocol | Prompt/command/output/exit marks; cwd | Supported by kitty, WezTerm, foot, Konsole 22.08+, Ghostty, iTerm2; VTE unclear | **Use** as the main terminal signal |
| kitty rc / WezTerm CLI / tmux control mode / Konsole D-Bus | Terminal APIs | Read scrollback, send text | Active | Per-terminal adapters |
| thefuck | Command correction | Rule modules match a failed command and its output | Last push Jul 2024; MIT | **Borrow** the rule shape for the terminal pack |
| command-not-found | Shell handler | Shell hook looks up the missing command in a package DB | Distro packages | Borrow as an offline knowledge source |

## 2. Screen readers and AT-SPI tooling

### Orca (GNOME screen reader)
- **How it works.** Orca registers one `Atspi.EventListener` whose callback pushes each event into a `queue.PriorityQueue`. The queue is keyed by an `EventPriority` enum (IMMEDIATE … LOW). A GLib idle handler drains the queue. Before an event is processed it passes a set of filters, all visible in `src/orca/event_manager.py`:
  - `_ignore_by_role`, `_ignore_by_focus_state` and `_ignore_by_spam_filter`.
  - Filters for children-changed, property-change and state-changed subtypes, and for text events.
  - `_is_obsoleted_by`, which drops an event when a newer event for the same source is already queued.

  `ax_cache_manager.py` provides "centralized storage and invalidation" for accessibility caches, with a `DEFAULT_CLEAR_INTERVAL_SECONDS = 60` periodic clear and per-cache clear policies. `script_manager.py` maps the focused application to a **script**:
  - It looks for an app-specific module under `scripts/apps/` (Thunderbird, evolution, gnome-shell, kwin, soffice, …).
  - Otherwise it uses a toolkit module under `scripts/toolkits/` (Chromium, Gecko, Qt, WebKitGTK, gtk, Servo).
  - Otherwise it uses `default.py`.
  - There are also dedicated `terminal/` and `web/` scripts.

  Orca 51.x has a D-Bus remote controller (`dbus_service.py`).
- **Strengths.** It is the most battle-tested AT-SPI consumer on Linux. It shows exactly how to survive event floods, for example from Chromium and terminals, through coalescing, obsolescence and role filters. The app → toolkit → default script resolution is the same layering Ya-Bro wants for packs.
- **Limits.** The code is speech- and braille-centric and contains no geometry/overlay logic. Behaviour depends on app a11y quality (Electron and Qt quirks get their own toolkit scripts). Upstream Wayland coordinate support is still limited.
- **Ya-Bro borrows.**
  - (a) A single listener, a priority queue and drop-obsolete coalescing.
  - (b) Explicit cache invalidation on `children-changed` and `property-change` events, plus a periodic clear.
  - (c) Pack resolution order: **app pack → toolkit pack (Qt/GTK/Chromium/Gecko/VTE) → global core pack**. That matches Orca's apps/toolkits/default layering and SPEC's "global core + app packs".
  - (d) Orca's `terminal` script is a reference for reading VTE and Konsole text via AT-SPI.
- Sources: https://gitlab.gnome.org/GNOME/orca (tree `src/orca`, `event_manager.py`, `script_manager.py`, `ax_cache_manager.py`)

### Accerciser
- **How it works.** A GTK app that browses the AT-SPI tree. It shows interfaces (Component, Text, Action, …), lets you watch events and includes an IPython console (unverified on current version details).
- **Strengths.** It shows exactly what Orca sees, including live events. **Limits.** It is a developer tool and can be slow or hang on huge trees such as browsers (unverified).
- **Ya-Bro borrows.** Pack authors should use it, or a Ya-Bro "inspect" mode modelled on it, to find role, name and path for selectors. Ya-Bro should ship a CLI `ya-bro inspect` that dumps the same data in the pack's selector format.
- Source: https://gitlab.gnome.org/GNOME/accerciser

### dogtail and LDTP
- **How they work.** dogtail (GPL-2.0, last push Oct 2026) wraps pyatspi with `findChild(predicate)` searches by role, name and description, plus `click()`/`typeText()`. LDTP2 (LGPL-2.1) provided a Windows-like "window name / object name" API and has been **dead since 2021**.
- **Strengths.** Readable role/name searches and proven use in distro QA (dogtail is used for GNOME/RHEL testing, unverified). **Limits.** Both are test-oriented and synchronous. LDTP is unmaintained.
- **Ya-Bro borrows.** dogtail's predicate objects map well to pack selectors (`role=push button, name~="Save"`). Ya-Bro should not take a dependency on either.
- Sources: https://github.com/vhumpa/dogtail , https://github.com/ldtp/ldtp2

### pyatspi2 vs Atspi GI
- pyatspi2 is a Python compatibility layer on top of the `Atspi` GObject-introspection library. Current Orca imports `gi.repository.Atspi` directly (`Atspi.EventListener.new(...)` in `event_manager.py`). **Ya-Bro should use `gi.repository.Atspi` directly**, which matches our PyGObject stack and avoids an extra layer.

### Odilia (Rust screen reader)
- **How it works.** A Rust screen reader on the async `atspi` crates, speaking through speech-dispatcher. Its README says Beta and "absolutely not production ready". MIT, active (Nov 2026).
- **Strengths.** Async and memory-safe, with a modern zbus-based atspi stack. **Limits.** Beta, with few users and limited app coverage.
- **Ya-Bro borrows.** Nothing directly. If the Python AT-SPI layer turns out too slow, a Rust side-process using the `atspi`/`zbus` crates is a proven path.
- Source: https://github.com/odilia-app/odilia

### Newton (Wayland accessibility proposal)
- **How it works (unverified details).** Matt Campbell's GNOME-funded prototype (2024) proposes that apps push accessibility trees through the Wayland compositor, using AccessKit-style tree updates, instead of the AT-SPI D-Bus pull model. A key motivation is that on Wayland, AT-SPI cannot give reliable global screen coordinates.
- **Ya-Bro implication.** AT-SPI `Component.get_extents(SCREEN)` is reliable on X11, which supports X11-first. On Wayland we will need window-relative extents plus the window's position from KWin scripting (kdotool-style), or vision fallback, until Newton or a successor lands.

## 3. Visual automation

### SikuliX
- **How it works.** OpenCV template matching (`Region.find(image)` with a similarity threshold) plus Tesseract OCR for text. Scripts are Jython/Python. The GitHub repo `RaiMan/SikuliX1` now redirects to `oculix-org/SikuliX1`, which is **archived** (MIT).
- **Strengths.** Works on anything visible, with no a11y needed. **Limits.** Template matching breaks with themes, DPI scaling and dark mode. It runs on Java and the project is archived.
- **Ya-Bro borrows.** For an element with no a11y, a pack may store a small reference image **and** an OCR text anchor as fallbacks, matched multi-scale. This is used only after AT-SPI fails.

### PyAutoGUI
- **How it works.** `locateOnScreen` (Pillow/OpenCV) and X11 input through Xlib, with a failsafe that aborts when the mouse is in a screen corner. BSD-3, last push Aug 2024.
- **Strengths.** Simple API, cross-platform. **Limits.** X11-only input on Linux, slow full-screen matching, no Wayland.
- **Ya-Bro borrows.** The failsafe idea: an emergency stop gesture/hotkey that cancels any self-driving step. Avoid the library itself (no Wayland, slow).

### pywinauto (Windows)
- **How it works.** UIA and Win32 backends. "Window specifications" are resolved lazily with fuzzy best-match on title, control type and automation id. BSD-3, active.
- **Strengths.** Robust lookup despite title or order changes. **Limits.** Windows-only.
- **Ya-Bro borrows.**
  - Lazy, re-resolved element specs, so selectors are re-evaluated at each step rather than holding stale references.
  - Fuzzy name matching with a score.

## 4. Input injection tools

| Tool | Mechanism | Needs | Wayland/KDE | Notes |
|---|---|---|---|---|
| xdotool | XTEST + EWMH | X11 | No (XWayland apps only) | BSD-3, active. Best X11 option. |
| ydotool | daemon `ydotoold` writing `/dev/uinput` | root or udev rule | Works everywhere, compositor-blind | AGPL-3.0. wdotool's README notes it bypasses the compositor's security boundary. |
| dotool | stdin commands → uinput, xkbcommon for layouts | `input` group via udev rule | Works everywhere | GPL-3.0-only. Written for Numen. |
| wtype | `virtual-keyboard-unstable-v1` | wlroots-style compositor | Not on KWin (unverified) | MIT |
| wdotool | libei via XDG RemoteDesktop portal; wlr virtual-keyboard/pointer; KWin scripting over D-Bus; GNOME Shell extension; uinput fallback | Portal consent | KDE/GNOME backends "experimental", not smoke-tested on real hardware | MIT OR Apache-2.0; early. Unicode typing via libei is "partial", and characters missing from the active layout are skipped. |
| libei/libeis | Emulated-input protocol; compositor is the EIS server; access via RemoteDesktop portal | User consent dialog | Plasma 6 and GNOME support it (unverified versions) | The sanctioned Wayland path |
| kdotool | Generates a KWin JS script, loads it over KWin D-Bus, runs it, deletes it | Plasma 6 | Window control only (search, activate, geometry) | Apache-2.0, active |
| input-remapper / keyd | Grab evdev devices, re-emit via uinput | root daemon | Everywhere | Remappers, not automation. Too invasive. |

- **Strengths.** xdotool and kdotool are mature and scriptable. wdotool and libei respect compositor security. **Limits.** Every Wayland path loses one of three things: focus awareness (uinput), keymap fidelity (libei and uinput skip characters not in the layout), or universality (wlr protocols are absent on KWin and GNOME).
- **Ya-Bro borrows.**
  - (1) An `InputBackend` interface with backends `xtest` (X11), `libei-portal` (Wayland) and `uinput` (opt-in fallback, out of process). This copies wdotool's backend matrix.
  - (2) Window queries on KDE via generated KWin scripts, as kdotool does.
  - (3) **Text entry through the clipboard or AT-SPI `EditableText.set_text_contents`/`insert_text`** where possible, instead of synthesized keystrokes, to avoid Arabic keymap problems: libei and uinput cannot type characters missing from the active layout.
  - (4) Always "show, then ask, then act". Injection runs only after explicit consent.
- Sources: https://github.com/jordansissel/xdotool , https://github.com/ReimuNotMoe/ydotool , https://git.sr.ht/~geb/dotool , https://github.com/atx/wtype , https://github.com/cushycush/wdotool , https://gitlab.freedesktop.org/libinput/libei , https://github.com/jinliu/kdotool , https://github.com/sezanzeb/input-remapper , https://github.com/rvaiya/keyd

## 5. Automation and hotkey frameworks (input observation)

### Espanso
- **How it works (from source, `espanso-detect/src`).**
  - X11 backend: uses the **XRecord** extension (`XRecordCreateContext` with `XRecordAllClients`, `XRecordEnableContextAsync`) to observe all key events without grabbing them, and `XGrabKey` for hotkeys.
  - Wayland backend (`evdev/`): enumerates `/dev/input/*`, keeps devices that look like keyboards or mice, and decodes keycodes with xkbcommon. The code says it is modelled on libxkbcommon's `interactive-evdev.c`. This requires the user to be in the `input` group or similar, because Wayland deliberately has no global key-snooping API.

  GPL-3.0, v2.4.1 (Sep 2026).
- **Strengths.** Proven, cross-platform and passive on X11 (no grab). **Limits.** On Wayland it needs raw device access, which sees everything including passwords, needs group membership and misses virtual keyboards/IMEs (unverified).
- **Ya-Bro borrows.** For struggle detection (undo loops, repeated Escape, menu open/close), on X11 use **XRecord** (or XInput2 raw events) passively. On Wayland, prefer **AT-SPI events** (focus, menu `state-changed:showing`, window activation) over raw evdev, because reading `/dev/input` captures passwords too. If evdev is ever used, keep it opt-in and never log key values, only event categories.

### AutoKey (Linux, X11)
- Python scripts and phrases triggered by abbreviations or hotkeys, with window-title filters. GPL-3.0, active. Strength: scriptable in Python. Limit: X11-centric (Wayland support limited, unverified). **Borrow:** per-window-filter triggers (the pack activation rule). Avoid code.

### Hammerspoon (macOS)
- **How it works.** Lua bindings over macOS APIs. `hs.eventtap` wraps CGEventTap to observe and modify input events. `hs.canvas` draws arbitrary shapes, text and images in borderless, level-controlled, optionally click-through windows. `hs.axuielement` exposes the macOS AX tree (unverified module details). MIT, active.
- **Strengths.** Small composable primitives. **Limits.** macOS-only, so it is an API model, not a dependency.
- **Ya-Bro borrows.** Its API shape for our overlay module: `canvas` elements (rect, circle, text, image) with frame, level and `clickActivating`-style toggles. This is a clean model for "highlight ring + bubble + avatar" primitives.

### AutoHotkey (Windows)
- Low-level hooks (`WH_KEYBOARD_LL`, unverified naming in docs), hotstrings and `#HotIf` context-sensitive hotkeys. GPL-2.0, active. Strength: a huge user base and a mature DSL. Limit: Windows-only. **Borrow:** context-sensitive activation (`#HotIf WinActive(...)`) maps to pack-scoped hotkeys and voice commands.

## 6. In-app tour libraries (UX blueprint for the step bubble)

### driver.js (MIT, 1.14.0, Nov 2026; repo now `nilbuild/driver.js`)
- **Cutout.** `overlay/stage.ts` builds a full-viewport `<svg>` with one `<path>` using `fill-rule: evenodd`. The path is the viewport rectangle plus an inner rounded rectangle around the target, so the hole is a real hole: clicks through it can be allowed. `overlay.ts` animates the stage between elements with `transitionStage` and supports extra "allowed cutouts".
- **Positioning.** `popover/position.ts` has its own side/align logic, with "over" for centered steps, side classes such as `driver-popover-side-left` and a fixed arrow size of 10 px.
- **Missing elements.** `tour/highlight.ts` has `mountDummyElement()`: if the step's element is absent, it highlights an invisible centred dummy, so the step still shows as a centred popover instead of crashing.
- **Advance.** `tour/advance.ts` advances on user events along `composedPath()`, debouncing multi-clicks (`MULTI_CLICK_MS = 500`, `SAME_SPOT_PX = 8`).
- **Resilience.** It observes target size (`observeSize`) and re-renders on change.
- **Strengths/limits.** MIT, small and well factored, with good a11y. Like all tour libraries it assumes the DOM is queryable and stable, which is exactly what desktop apps do not guarantee.
- **Accessibility.** `popover/live-region.ts` mounts an `aria-live="polite"` visually hidden region and `announce()`s each step. `highlight.ts` sets and restores ARIA on the popover.

### Shepherd.js (v16; **AGPL-3.0 or commercial**)
- Strengths: multi-opening cutouts, rich step hooks. Limits: AGPL/commercial license, web-only.
- `utils/overlay-path.ts` `makeOverlayPath()` generates SVG path data for one or more rounded-rect "openings", with per-corner radii, inside a `position: fixed` modal overlay. It compensates for pinch zoom (issue #2495).
- `utils/position.ts` now implements Floating-UI-style `computePosition`, `flip()` and `shift()` middleware in-house.
- Step options: `attachTo {element, on}` (omit it for a centred step), `advanceOn {selector, event}`, `beforeShowPromise` (e.g. open a panel first), `canClickTarget`, and `scrollTo` taking `ScrollIntoViewOptions` or a `scrollToHandler`.

### Intro.js (8.7.0; **AGPL-3.0 or commercial**)
- Strengths: simple, RTL-aware. Limits: AGPL/commercial license; a box-style highlight layer rather than a true cutout.
- An absolutely positioned `.introjs-helperLayer` draws the highlight, and its CSS comment says it "must never take clicks" from the target. A tooltip layer sits on top. It ships `introjs-rtl.scss`, which is relevant for Arabic.

### React Joyride (MIT, 3.2.0)
- Strengths: MIT, controlled-mode state machine. Limits: React-only.
- Depends on `@floating-ui/react-dom`, `scroll` and `scrollparent` (from package.json). It finds the scroll parent, scrolls the target into view, then positions with Floating UI. It exposes per-step lifecycle states through callbacks; the state names were not verified in source.

### Floating UI (MIT)
- `computePosition(reference, floating, {placement, middleware:[offset, flip, shift, arrow, hide]})`. `autoUpdate` re-runs it on scroll, resize and layout shift. `hide()` detects when the reference is clipped.

**Patterns Ya-Bro copies, re-implemented in GTK/Cairo:**
1. **Even-odd cutout.** The overlay is one surface with a rounded-rect hole per highlighted element. Let clicks pass through the hole only (input region = hole) when the user should act, and block nowhere else. In "show only" mode the input region is empty.
2. **Placement with flip/shift/hide.** The bubble prefers a side, flips if it would overflow the monitor, shifts along the edge, and hides or re-anchors when the target is occluded or off-screen. The arrow points at the target centre.
3. **Scroll-into-view first.** Before highlighting, ask the app to scroll the target into view, via AT-SPI `Component.scroll_to` where supported (AT-SPI ≥ 2.28, unverified) or by pack-defined steps.
4. **Missing-target fallback.** Use driver.js's dummy-element trick: show a centred bubble that says "I can't see X yet. Open the File menu first?" and offer a `beforeShow` pre-step, as with Shepherd's `beforeShowPromise`.
5. **Advance on the real event.** Advance on an observed AT-SPI event (focus moved to the expected widget, dialog appeared, terminal command exited 0) rather than a "Next" click. Debounce it.
6. **Re-measure continuously.** Re-measure on window move or resize and on AT-SPI `bounds-changed` (driver.js `observeSize`).
7. **Accessibility.** Announce each step through a live-region equivalent. Expose the bubble itself as an AT-SPI `notification` or `tooltip` role so Orca users get the guidance too. Provide keyboard navigation (next, back, dismiss).
8. **RTL.** Mirror the bubble layout and arrow side for Arabic text (Intro.js RTL stylesheet). Pango handles bidi for mixed Arabic/English text.

Sources: https://github.com/nilbuild/driver.js (packages/driver/src/overlay, popover, tour) · https://github.com/shipshapecode/shepherd (shepherd.js/src/utils/overlay-path.ts, position.ts, step.ts, LICENSE.md) · https://github.com/usablica/intro.js · https://github.com/gilbarbara/react-joyride · https://floating-ui.com/docs/computePosition

## 7. Digital adoption platforms (DAPs) and frustration analytics

### WalkMe, Whatfix, Pendo, Appcues, Userlane: element targeting
- **Whatfix (documented).**
  - Element capture generates CSS selectors automatically. The docs recommend a "Using CSS selector" rule followed by a "Using Element Text" rule when there is no unique id.
  - An **Element Reliability indicator** in Studio scores strength by the "uniqueness and specificity" of identifiers.
  - **Auto reselect** has a Standard mode (selector matching) and an AI mode (vision).
  - **Auto-heal** repairs detection failures at runtime.
  - **Visibility rules** gate content on page or element conditions.
  - **Whatfix Desktop** overlays Windows desktop apps (Teams, SAP GUI, Java apps). It requires enabling SAP GUI accessibility, which suggests it relies on OS accessibility APIs. The exact hooks (UIA, Java Access Bridge) are not documented publicly (unverified).
- **WalkMe (documented).** Its help center says default element selection adapts to page changes. jQuery selectors are reserved for "edge cases" where it can't find the element consistently. It holds a patent on GUI element acquisition using **multiple alternative representations** of an element (USPTO US 12,405,809 B2). Desktop/UIA internals: unverified.
- **Pendo / Appcues / Userlane.** Feature tagging by CSS selector rules with text/attribute conditions (Pendo), and flow builders with in-browser recorders (unverified; docs not fetched).
- **Patent background.** US11461090B2 ("Element detection") describes searching for "strong attributes", collecting multiple candidates, then running a finder algorithm to pick the best. Assignee and relation to any vendor are not verified here.

**Strengths/limits of DAPs.** They are mature at authoring, with recorders, reliability scores and self-heal. They are mostly web-first, their desktop internals are undocumented, and they are expensive SaaS that relies on admins to maintain flows.

**Ya-Bro selector design (borrowed):** a pack step targets an element through a **fingerprint**, not a single path. Fields, in priority order:
1. Stable ids: AT-SPI `accessible-id` (GTK4 and Qt `objectName`, unverified exposure), or a DOM `id`/`data-testid` via the browser's AT-SPI attributes.
2. Role plus accessible name (localized: keep both EN and AR names).
3. Ancestor chain of roles and names (window title pattern → panel → button).
4. Relative position among siblings and geometry ratio inside the window.
5. Visible text / OCR anchor and an optional image patch (SikuliX-style fallback).

At runtime, score all candidates and accept the best above a threshold. Store a **reliability score** per selector at authoring time (Whatfix). On failure, attempt **auto-reselect**: relax fields, then try vision, and ask the user to confirm ("Is this the Save button?"). Write the corrected fingerprint back to a local pack override (auto-heal). Use **visibility rules** (app, window, URL or terminal state) to decide when a step or tip applies.

### Frustration signals: published definitions
| Signal | Vendor | Published definition | Numeric threshold |
|---|---|---|---|
| Rage click | FullStory | Clicks "multiple times, rapidly, in the same area" | Not published (secondary source says proprietary) |
| Rage click | Microsoft Clarity | Multiple clicks "in a clustered area in rapid succession" | Not published |
| Rage click | Hotjar | Repeated clicks on an area or element in a short period | Not published (third parties cite 3–5 clicks within ~1 s, unverified) |
| **Rage click** | **PostHog (open source)** | `posthog-js` `rageclick.ts`: clicks whose Manhattan distance from the previous click is < `threshold_px` and that come < `timeout_ms` after it; fires when the count reaches `click_count` | **30 px, 1000 ms, 3 clicks** (configurable) |
| Dead click | FullStory | Nothing on the page changes within "a few seconds" | Not published |
| Dead click | Clarity | No feedback "in a reasonable amount of time", no visual change, no navigation | Not published |
| **Dead click** | **PostHog** | `dead-clicks-autocapture.ts`: dead if no "liveness" signal (DOM mutation, scroll, selection change, focus/visibility change) occurs in time | **mutation 2500 ms, scroll 100 ms, selection 100 ms**, absolute backstop 2750 ms (mutation × 1.1) |
| Error click | FullStory / Clarity | Click just before or after a JS/console error | — |
| Thrashed cursor | FullStory | Mouse moving erratically or in circles (desktop only) | Not published |
| Excessive scrolling | Clarity | More vertical scrolling than the expected average | Adaptive |
| Quick back | Clarity | Navigate away, then return faster than the page's dwell-time threshold | Adaptive |
| U-turn | Hotjar | Listed as a frustration signal filter | Definition not found (unverified) |
| Pendo frustration metrics | Pendo | Rage/dead/error clicks and U-turns exist in Pendo Analytics (unverified) | Not checked |

**Desktop translation for Ya-Bro's proactive mode** (initial defaults, to tune):
- *Rage click*: ≥ 3 clicks within 1 s each and < 30 px apart (PostHog defaults) on a widget that produced no AT-SPI state change.
- *Dead click*: a click on a non-disabled widget followed by no AT-SPI event (focus, state, children, window) within 2.5 s.
- *Menu thrash (desktop analogue of the U-turn)*: the same menu opened and closed ≥ 3 times within ~20 s without activating an item (Ya-Bro-specific; no published source).
- *Error loop*: the same error dialog or the same failing shell command (same argv0 and non-zero exit) ≥ 2–3 times within a few minutes.
- *Undo loop*: ≥ N Ctrl+Z within a short window (observed via the X11 XRecord category; on Wayland only via app signals).
- *Idle-with-context*: no input for T seconds while a dialog or an incomplete flow step is showing.

Each signal raises a score that decays over time. Offer help once the score crosses a threshold, then **back off** (cool-down and a per-app "don't offer again" setting). Analytics vendors only record these signals; they never interrupt the user, so Ya-Bro's offer-then-back-off policy is new territory.

Sources: https://help.fullstory.com/hc/en-us/articles/360020624154 · https://learn.microsoft.com/en-us/clarity/insights/semantic-metrics · https://www.hotjar.com/blog/rage-clicks/ · https://github.com/PostHog/posthog-js (packages/browser-common/src/rageclick.ts, packages/browser/src/entrypoints/dead-clicks-autocapture.ts) · https://support.whatfix.com/docs/improve-element-selection-using-element-reliability-indicators-for-steps · https://support.whatfix.com/docs/element-reselection-automation · https://support.whatfix.com/docs/screensense-auto-heal · https://support.whatfix.com/desktop/docs/what-is-whatfix-desktop · https://support.whatfix.com/desktop/docs/configure-sap-applications-for-whatfix-desktop · https://support.walkme.com/knowledge-base/find-element-basic-troubleshooting-tips · https://patents.google.com/patent/US11461090

## 8. Help systems

- **GNOME Yelp + Mallard.** Mallard is a topic-oriented XML help format. Pages declare their own links into guide pages ("informational links" from topic to guide), so help is assembled bottom-up rather than as a book. Apps open help through `help:appname/page` URIs, which Yelp renders. **Borrow:**
  - Pack docs are small topic pages that declare which "guides" they belong to (Mallard's model).
  - Ya-Bro can deep-link to existing `help:` pages as the "read more" target of a step, reusing upstream docs instead of rewriting them.
  - Source: http://projectmallard.org/ , https://gitlab.gnome.org/GNOME/yelp
- **KHelpCenter.** A KDE documentation browser over DocBook handbooks (`help:/konsole`). Same borrowing: link to handbook anchors from pack steps. Source: https://apps.kde.org/khelpcenter/
- **KDE Welcome Center / GNOME Tour.** First-run carousels with static pages and a few actionable buttons (e.g. "Open System Settings"). They are not live guidance. **Borrow:** a short first-run Ya-Bro introduction, skippable and never repeated. (unverified current feature set) Sources: https://apps.kde.org/plasma-welcome/ , https://gitlab.gnome.org/GNOME/gnome-tour
- **Strengths/limits (help systems).** Rich, maintained, localized documentation (including Arabic translations for many KDE/GNOME apps, unverified), but it is passive, separated from the live UI, and often lags behind the app.
- **KDE "What's This?" (Shift+F1).** Switches the pointer into a help mode. Clicking a widget shows its `whatsThis` text (Qt `QWhatsThis`). **Borrow** directly as a Ya-Bro mode: the user presses a hotkey or says "what's this?", clicks any element, and Ya-Bro reads that element's AT-SPI role, name and description plus pack knowledge, then explains it. Qt's `whatsThis` text may itself be exposed as the AT-SPI description or help text (unverified).

## 9. Screen annotators and pointer/key display tools

- **Gromit-MPX** (GPL-2.0, active, Sep 2026).
  - Uses a full-screen transparent window and the XCOMPOSITE extension "where available". It toggles **painting** (input grab on/off) with F9 and **visibility** with Ctrl-F9, or `gromit-mpx --toggle`.
  - On Wayland it runs **through XWayland** (README: "with a Wayland session using XWayland"), so it does not use layer-shell.
  - Multi-pointer support comes from XInput2 MPX.
  - **Borrow:** the explicit two-state model (pass-through vs. interactive) bound to a hotkey, and the visible indicator of which state is active.
  - Strength: works on every desktop. Limit: no native Wayland surface, and while painting it grabs all input.
  - Source: https://github.com/bk138/gromit-mpx
- **ksnip / Flameshot** (GPL-3.0). Annotate a captured screenshot, not the live screen. **Borrow:** the annotation vocabulary (arrow, numbered marker, blur, rectangle) for "show me" snapshots in chat history. Not for live guidance.
- **KWin "Mouse Mark" and "Track Mouse" effects.** These draw inside the compositor, so they have no window, no input-region issues and are correct on both X11 and Wayland. **Implication:** the most robust Plasma-Wayland highlight is a **KWin script or effect** that Ya-Bro drives over D-Bus. Keep it as the Plasma-Wayland option if layer-shell proves insufficient. (Effect internals not verified.)
- **screenkey / key-mon / "Show Me The Key".** On-screen display of pressed keys, using an always-on-top, click-through, semi-transparent window. key-mon has been dead since 2015. screenkey lives on GitLab (status unverified). **Borrow:** the OSD style for showing a shortcut Ya-Bro wants the user to press ("Press Ctrl+Shift+T").

## 10. Desktop pets and overlays (always-on-top, click-through, transparency)

- **xeyes / oneko / xpenguins (X11).** These use the **X Shape extension** to make non-rectangular windows. xpenguins draws on the root window and walks along window edges, which it learns from window geometry (unverified details).
- **Shimeji-ee** (Java; Linux ports exist, status unverified) and **eSheep** (the `Adrianotiger/desktopPet` repo, MIT, active Nov 2026). Transparent top-level sprites that climb and sit on window title bars.
- **koverlay** (MIT, small, last push Oct 2025).
  - Qt 6 + QML + **LayerShellQt**.
  - "Always on top" comes from layer-shell (overlay layer).
  - Click-through means it "passes all mouse/keyboard through" (empty input region) and never takes focus.
  - Tested on Fedora KDE Plasma Wayland.
  - Strength: the exact native Plasma Wayland recipe. Limit: tiny project (16 stars), and layer-shell is not available on GNOME.
  - Source: https://github.com/erik96/koverlay
- **MangoHud** (MIT). A Vulkan layer / OpenGL `LD_PRELOAD` that draws inside the target process. **Avoid** for a desktop helper (process injection, per-app).
- **KDE Plasma widgets (plasmoids).** Live in the panel or desktop layer, not above windows. Plasma widget overlay behaviour not verified.

**Recipe for Ya-Bro (GTK4).**
- **X11 (KDE first).** Use an ARGB visual with an RGBA-transparent surface. Set the window type to `_NET_WM_WINDOW_TYPE_NOTIFICATION`/`DOCK` or set `_NET_WM_STATE_ABOVE`, and skip the taskbar and pager. For click-through, set an **XShape input region** that is empty (`XShapeCombineRectangles` with `ShapeInput`), or covers only the bubble when it is interactive. GTK4 removed `gtk_widget_input_shape_combine_region`. In GTK4, `gdk_surface_set_input_region()` exists on GdkSurface (unverified whether it applies the X11 input shape on the GTK4 X11 backend).
- **Wayland, Plasma or wlroots.** Use **gtk4-layer-shell** with the overlay layer, keyboard interactivity `none`, and an empty (or bubble-only) `wl_surface` input region. This is the same recipe as koverlay.
- **GNOME Wayland.** No layer-shell, so it needs a GNOME Shell extension (wdotool also ships one for its GNOME backend).
- **Avatar behaviour.** Shimeji/xpenguins-style: the avatar perches on the target window's edge near the highlighted element, and moves aside when the pointer approaches. Never cover the target.

## 11. Voice tools

### Voice control and assistant frameworks
- **Talon Voice.**
  - The core is free (Patreon funds betas). The core is closed source (unverified); the `talonhub/community` command set is MIT and active.
  - Commands live in `.talon` files whose header is a **context matcher** (app name, window title, OS, mode), followed by `phrase: action` rules backed by Python actions.
  - It also has noise recognizers ("pop", "hiss") and eye-tracker mouse control (details unverified; see talon.wiki).
  - **Borrow:** context-scoped grammars are exactly the "pack-scoped voice commands" Ya-Bro needs. Pack voice intents should be activated by the same matcher as the pack (app id, window title, URL). Avoid any closed engine.
  - Strengths: very fast, mature hands-free control. Limits: proprietary core; English-centric.
  - Sources: https://talonvoice.com , https://talon.wiki , https://github.com/talonhub/community
- **Numen.** Linux voice control that runs **Vosk** locally (about a 40 MB English model) and types through **dotool**/uinput. It uses phrase files and syllable-based spelling. AGPL-3.0-only. Strength: fully local, works on Wayland via uinput. Limit: English-only model by default; AGPL. **Borrow:** a tiny grammar-constrained recognizer for commands ("next", "back", "stop", "اللي بعده") can run alongside the big STT. Source: https://git.sr.ht/~geb/numen
- **Wyoming protocol** (OHF, MIT).
  - JSONL header lines (`type`, `data`, `data_length`, `payload_length`) followed by an optional PCM payload, over TCP.
  - It has **no authentication or encryption by design**, for trusted networks only.
  - There are existing servers for openWakeWord, porcupine1, snowboy, faster-whisper, Piper and others.
  - Strengths: dead simple, language-agnostic, with an existing server ecosystem. Limits: no auth/encryption, and no built-in service discovery outside HA (unverified).
  - **Adopt** it for Ya-Bro's speech services, bound to a Unix socket or 127.0.0.1 only. That gives drop-in reuse of `wyoming-faster-whisper` and `wyoming-piper` and process isolation for GPL engines.
  - Source: https://github.com/OHF-Voice/wyoming
- **Rhasspy 3.** Archived (Dec 2023); its ideas moved into Wyoming and Home Assistant. https://github.com/rhasspy/rhasspy3
- **OVOS / Mycroft.**
  - mycroft-core is **archived** (Apache-2.0).
  - OVOS (ovos-core, ovos-dinkum-listener; Apache-2.0, active) keeps a message-bus architecture: the listener runs VAD, wake word and STT plugins and emits utterances on the bus, an intent service (Adapt/Padatious-style) routes to skills, and TTS plugins speak. Plugin details unverified.
  - Strengths: a mature plugin ecosystem. Limits: a heavy stack designed for a standalone assistant, not an embedded helper.
  - **Borrow:** plugin interfaces per stage (WakeWord, VAD, STT, TTS) and the "bus message" decoupling. Avoid the whole stack.
- **Home Assistant Assist pipeline.** Stages are wake word → STT → intent → TTS. Each run emits typed events (run-start, wake_word-end, stt-end, intent-end, tts-end, run-end, error), with Wyoming used for remote engines. **Borrow:** model Ya-Bro's voice turn as the same staged event stream, which makes UI feedback (listening, thinking, speaking) and barge-in straightforward. (Event names from memory of HA developer docs, unverified.) https://developers.home-assistant.io/docs/voice/pipelines/

### Wake word engines
| Engine | How | License | Arabic | Status |
|---|---|---|---|---|
| openWakeWord | Melspectrogram → frozen Google speech-embedding backbone (Apache-2.0 TFHub model, re-implemented) → small per-word classifier. Trains in under an hour on **100% synthetic TTS clips**. Default threshold 0.5. Targets < 0.5 false accepts/hour and < 5% false rejects. Optional per-speaker "verifier" model. | **Code Apache-2.0. Included pretrained models CC BY-NC-SA 4.0** (README) | Pretrained models English-only | Active (last push Dec 2025) |
| Porcupine | Proprietary engine; custom words trained in Picovoice Console | Repo Apache-2.0, but runtime needs an **AccessKey** | Languages: EN, ZH, FR, DE, IT, JA, KO, PT, ES; others "for commercial customers" | Active |
| microWakeWord | 40 spectrogram features every 10 ms → streaming MixConv TFLite-Micro model, inference every 30 ms | Apache-2.0 | No pretrained Arabic | "Early release"; training "still very difficult" (README) |
| Snowboy | DNN hotword | Apache-2.0 (models own licenses) | — | **Dead** (last push 2021; Kitt.ai shut down) |
| Mycroft Precise | GRU on MFCC | Apache-2.0 | — | **Dead** (last push 2023) |

- **Custom Arabic wake word feasibility.** openWakeWord's training uses synthetic TTS clips of the phrase plus negative data. It is language-agnostic in principle, because the backbone learns general speech embeddings. The constraint is **voice diversity**: Piper has a single Arabic voice (ar_JO-kareem, one speaker). Options:
  - (a) Use a short, phonetically distinctive name that works in both languages ("Ya Bro"/"يا برو"), generated with Piper's English voices plus kareem plus cloud voices (Azure ar-EG Salma/Shakir) for training-only augmentation. Check each cloud provider's ToS on using synthetic audio for training (unverified).
  - (b) Record about 50–200 real samples from the maintainer and friends and add the speaker verifier.
  - (c) **Avoid shipping the openWakeWord pretrained models** because of NC-SA.
  - **Open question:** whether the bundled `melspectrogram.onnx`/`embedding_model.onnx` fall under the README's "included pre-trained models" NC clause. The backbone is described as Google's Apache-2.0 model, re-implemented. The README wording is ambiguous, so confirm with the author or re-export from the TFHub original. (unverified)
- **Strengths/limits summary.** openWakeWord is easy to train and permissive in code, but its models are NC and English-only. Porcupine is the most accurate and smallest, but proprietary, keyed and has no Arabic. microWakeWord is tiny, but hard to train. False accepts in a desktop setting (videos, calls) are the main UX risk for any engine.
- **Alternative that avoids wake words.** A push-to-talk hotkey plus "listen while the bubble is open". This is probably the right v1 default for a desktop app, with the wake word opt-in.
- Sources: https://github.com/dscripka/openWakeWord , https://github.com/Picovoice/porcupine , https://github.com/kahrendt/microWakeWord , https://github.com/Kitt-AI/snowboy , https://github.com/MycroftAI/mycroft-precise

### VAD
| VAD | Notes | License |
|---|---|---|
| Silero VAD | 30 ms+ chunks in < 1 ms on one CPU thread (README). Trained on corpora covering 6000+ languages. 8/16 kHz. ONNX or PyTorch. v6.2.3 (Sep 2026). | **MIT**, "no telemetry, no keys" |
| WebRTC VAD (py-webrtcvad) | GMM classifier on 10/20/30 ms frames; very cheap; more false positives on noise | MIT wrapper; the bundled WebRTC code is BSD (unverified) |
| TEN VAD | Claims better precision than Silero and WebRTC on its own released test set, and faster speech→silence transitions (Silero "delay of several hundred milliseconds", vendor claim) | **Apache-2.0 plus extra conditions**: may not be deployed to compete with Agora, and only for your own application's end users. **Not OSI open source.** |
| pyannote.audio | Segmentation/diarization pipelines, heavier | MIT code; pretrained pipelines are gated on HF (unverified) |

Strengths/limits: Silero is accurate and permissive, but has endpoint lag (per TEN's claim) that needs a tuned `min_silence_duration`. WebRTC is the cheapest option and the weakest on noise. TEN is fastest at transitions, but its license is restrictive.

**Choice:** Silero VAD (MIT) as the endpointing VAD, optionally with WebRTC VAD as a near-free pre-gate. Avoid TEN VAD unless its license is acceptable.

### STT
**Arabic evidence (primary): Open Universal Arabic ASR Leaderboard** (Wang, Alhmoud, Alqurishi; arXiv 2412.13788 v1, Dec 2024). Test sets: SADA, Common Voice 18, MASC clean/noisy, MGB-2. "Egyptian" below is the **SADA Egyptian subset**, not a dedicated corpus.

| Model | Avg WER | Avg CER | SADA-Egyptian WER |
|---|---|---|---|
| nvidia conformer-ctc-large-ar (+4-gram LM) | 25.71% | 10.02% | 40.97% |
| nvidia conformer-ctc-large-ar (greedy) | 27.46% | 9.94% | 41.97% |
| whisper-large-v3 | 29.87% | 13.65% | 59.28% |
| seamless-m4t-v2-large | 32.55% | 14.47% | 72.98% |
| whisper-large-v3-turbo | 33.30% | 15.68% | 63.01% |
| whisper-large-v2 | 34.04% | 16.26% | 48.44% |
| whisper-medium | 39.60% | 19.10% | 55.79% |
| facebook/mms-1b-all | 47.86% | 17.66% | 81.94% |
| whisper-small | 52.18% | 25.15% | 69.61% |

- Takeaways: dialectal Arabic is hard for everyone (Egyptian WER of 40–60%+). Whisper-large-v2 does better than v3 on Egyptian in this table. Smaller Whisper models degrade sharply.
- **Newer, not in that paper: NVIDIA `stt_ar_fastconformer_hybrid_large_pcd_v1.0`** (CC-BY-4.0, model card).
  - Outputs Arabic with **diacritics and punctuation**.
  - It is **non-streaming**.
  - Greedy WER (TDT head): MASC 16.67, Common Voice 25.60, FLEURS 12.94, EveryAyah 6.55.
  - It is mostly MSA/Quranic-leaning, it is not built for English code-switching, and its card warns against word-for-word use.
- **Code-switching (Egyptian Arabic–English).** The ArzEn corpus (about 12 h of spontaneous Egyptian–English speech, LREC 2020) reported a best WER of about 30.6% for hybrid/E2E systems in 2021. That figure comes from a search snippet, so it is a secondary source (unverified). ArzEn-LLM (arXiv 2406.18120) fine-tunes Whisper for code-switched Egyptian; its WER figures were not verified. Code-switched output also breaks standard WER, because the same word can be written in either script (EMNLP Findings 2024 PolyWER paper).
- **Engines.**
  - **whisper.cpp** (MIT, active) and **faster-whisper** (MIT, CTranslate2, active) are the practical local runners. Both are batch/chunked by design. "Streaming" is done with VAD-segmented utterances or a sliding window with local agreement (the whisper_streaming approach, unverified repo status).
  - **distil-whisper**: English-only checkpoints, so avoid it for Arabic.
  - **Vosk** (Apache-2.0 API, active) has Arabic models:
    - `vosk-model-ar-mgb2-0.4` (318 MB, WER 16.40 on MGB-2 dev, Apache-2.0).
    - `vosk-model-ar-0.22-linto-1.1.0` (1.3 GB, WER 52.87 on CV and 28.50 on MGB-2, **AGPL**).
    - Tunisian models (Apache-2.0).
    - There is no Egyptian model. Vosk is true streaming with grammar restriction, so it is good for command words.
  - **NVIDIA Parakeet-tdt-0.6b-v3 / Canary-1b-v2**: CC-BY-4.0, but **Arabic is not in their language lists**.
  - **Moonshine** (code MIT) advertises Arabic STT and TTS. Its LICENSE lists the **legacy non-streaming Arabic Base/Tiny STT models as non-commercial** (Moonshine Community License) and says every other STT model, including all streaming models, is MIT. Whether a streaming Arabic model exists was not verified.
  - **sherpa-onnx** (Apache-2.0, very active): one C++/Python runtime for streaming Zipformer/Paraformer, Whisper, NeMo CTC/TDT, VAD (Silero), keyword spotting and TTS (Piper/VITS/Kokoro) on CPU. It is a strong candidate to host most models in one process. Arabic-specific streaming models in sherpa-onnx: unverified.
  - **ArTST** (MBZUAI) checkpoints are CC-BY-NC-4.0. **MMS** (`mms-1b-all`) is CC-BY-NC-4.0 (unverified for the ASR checkpoint). **SeamlessM4T v2** is CC-BY-NC-4.0. Avoid the non-commercial weights for a product default.
- **Strengths/limits summary.** Whisper handles multilingual and code-switched speech but is batch-oriented and hallucinates on silence (needs VAD gating). NVIDIA Arabic models are accurate but non-streaming and Arabic-only. Vosk streams and is small but inaccurate on open dictation.
- **Recommendation.** Use whisper-large-v3 (or v2 for Egyptian, worth A/B testing), or v3-turbo for speed, through faster-whisper or whisper.cpp, with Silero endpointing. Do not force the language: Whisper's language ID handles AR/EN, but code-switched utterances often get translated or transliterated, so test with the maintainer's real speech. Add a tiny Vosk/sherpa grammar recognizer for barge-in commands. Offer cloud STT (Azure has `ar-EG` real-time STT) as opt-in.

### TTS
| Engine | Arabic | License | Notes |
|---|---|---|---|
| **Piper** | **ar_JO-kareem** (low, medium). The medium model card says it was fine-tuned from the US English "lessac" medium voice, with the dataset from AliMokhammad/arabictts. One speaker, 22.05 kHz. | **Repo moved: `rhasspy/piper` (MIT) is archived (Aug 2025). The active repo `OHF-Voice/piper1-gpl` is GPL-3.0** (v1.8.0, Sep 2026). Each voice has its own license. | Embeds espeak-ng for phonemes. **Has built-in Arabic diacritization**: `voice.py` runs `TashkeelDiacritizer` (from mush42/libtashkeel) when `espeak_voice == "ar"`, `use_tashkeel=True`, `taskeen_threshold=0.8`. OHF is "looking for maintainers". Kareem's quality is a Jordanian/MSA-ish single voice; no Egyptian voice (subjective quality unverified). |
| Coqui TTS / XTTS-v2 | XTTS-v2 supports Arabic (unverified list) | Coqui (company) shut down in early 2024 (unverified date). `coqui-ai/TTS` last push Aug 2024. The **idiap/coqui-ai-TTS** fork is MPL-2.0 and active. **XTTS-v2 weights: Coqui Public Model License (non-commercial)** | Avoid the weights for a product default |
| espeak-ng | Arabic voice exists; needs diacritized input to pronounce vowels correctly | GPL-3.0, active | Robotic. Use only as Piper's phonemizer. |
| Kokoro-82M | No Arabic (model card language tag: en) | Apache-2.0 | English voice candidate |
| MeloTTS | No Arabic (unverified list) | MIT, last push Dec 2024 | English voice candidate |
| F5-TTS | Base EN/ZH; community Arabic fine-tunes (unverified) | Code MIT; **weights CC-BY-NC-4.0** | Avoid weights |
| Chatterbox Multilingual | **Arabic listed** among 23 languages | MIT, but **"retired research … no longer maintained" since Aug 2026** | Usable only as a frozen snapshot; 0.5B is heavy |
| Fish-speech / OpenAudio | Multilingual (Arabic unverified) | Fish Audio Community License: free for research/non-commercial, limited commercial use under a revenue threshold | Avoid |
| MMS-TTS (`facebook/mms-tts-ara`) | Arabic | **CC-BY-NC-4.0** | Avoid |
| Moonshine TTS | Arabic listed | Per-model third-party licenses (LICENSE says not MIT by default) | Evaluate |
| Azure Speech | **ar-EG-SalmaNeural (F), ar-EG-ShakirNeural (M)** plus 15 more Arabic locales | Commercial cloud | Only verified Egyptian-dialect voices found |
| Google Cloud TTS | **ar-XA only (MSA)**: Chirp3-HD, WaveNet, Standard | Commercial | No Egyptian locale |
| ElevenLabs / OpenAI TTS | Arabic supported via multilingual models; Egyptian accent quality unverified | Commercial | Optional |

- **Diacritization (tashkeel).** Arabic script omits short vowels, so TTS needs diacritics to pronounce correctly.
  - Piper already bundles libtashkeel (ONNX).
  - Alternatives: **Mishkal** (rule-based, GPL-3.0, last push Sep 2025), **CATT** (transformer, Apache-2.0, last push Jul 2025) and **Shakkala** (Keras RNN, no SPDX license detected, last push 2023).
  - All of them target MSA. Egyptian colloquial words often have no "correct" MSA diacritization, so expect mispronunciations; this is an argument for cloud ar-EG voices when the user wants Egyptian speech.
- **Strengths/limits summary.** Piper is fast on CPU and local, with built-in tashkeel, but has one Arabic voice and is now GPL. Cloud voices have Egyptian variants but need a network connection and raise privacy questions. Most expressive open models carry non-commercial weights.
- **Recommendation.** Use Piper out of process (GPL-3.0) through Wyoming: an English voice plus ar_JO-kareem, with the built-in tashkeel. Script-switch per segment for code-switched text, sending Arabic runs to kareem and Latin runs to an English voice. Offer Azure ar-EG as an opt-in cloud voice for an Egyptian accent. Re-evaluate Moonshine TTS and Chatterbox snapshots later.

### Echo cancellation and barge-in
- **PipeWire `libpipewire-module-echo-cancel`.** Creates linked capture/source/sink/playback nodes. The only backend is `aec/libspa-aec-webrtc` (the WebRTC audio processing library). Configure it in `~/.config/pipewire/pipewire.conf.d/`. Options include `library.name`, `aec.args`, per-stream props and `monitor.mode` (cancel against the default sink's monitor instead of a dedicated sink). Source: https://docs.pipewire.org/page_module_echo_cancel.html
- **speexdsp.** Older AEC and preprocessing (BSD-style, unverified). Lower quality than WebRTC AEC.
- **Barge-in pattern (HA/OVOS-style).** While TTS plays, keep the mic open on the AEC source and run VAD plus the small command recognizer. On detected speech, duck or stop TTS, cancel the pending pipeline stage, and start STT. Ya-Bro should play its TTS **into the echo-cancel sink** (or use `monitor.mode`) so its own voice is removed from the mic.

## 12. Terminal tools (first pack: CLI + web UI)

### Shell hooks
- **bash.** Bash has no native preexec. **bash-preexec** (MIT, active Aug 2026) emulates `preexec` (before a command runs, receiving the command string) and `precmd` (before the prompt, where `$?` holds the exit status) using a DEBUG trap plus `PROMPT_COMMAND`. Bash 5.x also has `PS0`, which expands after a command is read and before it runs (unverified as an alternative).
- **zsh.** Native `preexec_functions` / `precmd_functions` (`add-zsh-hook`).
- **fish.** Event functions `--on-event fish_preexec` / `fish_postexec` (`$status`, `$CMD_DURATION`). fish emits OSC 133 itself (fish docs, terminal compatibility page).
- Source: https://github.com/rcaloras/bash-preexec

### atuin (MIT, very active)
- **How it records.**
  - The bash hook (`crates/atuin/src/shell/atuin.bash`) runs `atuin history start --hook -- "$1"` in **preexec**, which returns an id, and records `EPOCHREALTIME`.
  - In **precmd** it captures `EXIT=$?` and the end time, then calls `atuin history end` with the exit code and duration.
  - It supports both bash-preexec and ble.sh backends.
- **Schema.** The original migration `crates/atuin-client/migrations/20210422143411_create_history.sql` creates `history(id text pk, timestamp int, duration int, exit int, command text, cwd text, session text, hostname text, unique(timestamp,cwd,command))`, indexed on timestamp and command. Later migrations add `deleted_at`, author/kind and more indexes.
- **Strengths.** Accurate exit codes and durations for every terminal; a robust bash path via bash-preexec or ble.sh. **Limits.** Requires shell rc changes, and bash-preexec has edge cases with existing DEBUG traps and `PROMPT_COMMAND` (hence atuin's failure workarounds).
- **Ya-Bro borrows.** The same two-phase start/end hook and the same columns: id, ts, duration_ns, exit, command, cwd, session, host, plus Ya-Bro's own fields `pack_step_id` and `stderr_excerpt?`. The data feeds the **failing-command loop detector** and the terminal pack. Interoperate: if atuin is installed, read its SQLite DB read-only instead of installing a second hook (opt-in, privacy).

### OSC 133 (semantic prompts) and OSC 7 (cwd)
- **Protocol.** It originated in FinalTerm and was popularised by iTerm2. The marks are:
  - `OSC 133;A` prompt start
  - `;B` command input start
  - `;C` command output start
  - `;D;<exit>` command finished with exit status

  `OSC 7;file://host/path` reports the cwd. kitty adds a `cmdline_url` extension to mark C (per fish docs).

| Terminal | OSC 133 | Source quality |
|---|---|---|
| kitty | Yes. Its shell integration emits OSC 133, including `133;D;<status>`. Jump to prompt; open last command output. | Primary (kitty docs) |
| WezTerm | Yes. Input/Output/Prompt semantic zones, `ScrollToPrompt`, Lua `pane:get_semantic_zones()`; also OSC 7 | Primary (wezterm docs) |
| foot | Yes. Jump to prompt (needs `133;A`); pipe last output (needs `133;C`/`D`); also OSC 7 | Primary (foot README) |
| **Konsole** | **Yes since KDE Gear 22.08** (Ctrl+Alt+] pastes bash setup); 22.12 parses OSC 133 parameters and adds visual hints | Primary (Konsole changelog, KDE docs) |
| Ghostty | Yes | Secondary (terminfo tracker) |
| iTerm2 | Yes (originator of the iTerm2 variant) | Secondary |
| VTE / GNOME Terminal / Ptyxis | **Unclear.** In 2017 VTE only swallowed OSC 133. Later VTE/Ptyxis work landed per Christian Hergert's blog; whether it is enabled by default in GNOME Terminal is unverified. | Secondary |
| Alacritty, xterm.js | No (per tracker) | Secondary |

- **Ya-Bro approach.** Ya-Bro installs its own small shell snippet (bash via bash-preexec, zsh/fish natively) that:
  - (a) emits OSC 133/OSC 7, so supporting terminals benefit;
  - (b) **sends a structured event to Ya-Bro over a Unix socket**: start (command, cwd, tty, ts) and end (exit, duration).

  Do not try to parse OSC 133 out of the terminal itself. Terminal-side marks matter only for highlighting the right scrollback region; the hook gives exit codes for every terminal.

### Terminal control APIs (per-terminal adapters)
- **Konsole D-Bus** (from `src/session/Session.h`, `Q_SCRIPTABLE`):
  - `sendText`, `runCommand` and `sendMouseEvent`.
  - `getDisplayedText` / `getAllDisplayedText` (screen and scrollback).
  - `foregroundProcessId` and `processId`.
  - `setMonitorPrompt` / `setMonitorActivity` / `setMonitorSilence(Seconds)`.
  - `title`, `profile` and `shellSessionId`.

  The service is `org.kde.konsole-<pid>` and the path is `/Sessions/N` (unverified naming). **This is the primary KDE adapter**: read the screen to explain an error, and type a suggested command for the user to confirm.
- **kitty remote control.** Needs `allow_remote_control` (or a socket via `--listen-on`). `kitten @ get-text --extent last_cmd_output` / `last_non_empty_output` uses the OSC 133 marks; `send-text` is also available.
- **WezTerm CLI.** `wezterm cli get-text` (with start/end line options and an escapes flag) and `wezterm cli send-text`. Lua `pane:get_text_from_semantic_zone()`.
- **tmux.** Control mode (`tmux -CC`) streams `%output` notifications as a line protocol. Hooks such as `after-new-window` and `pane-exited` can be set (unverified hook list). `capture-pane -p` reads text.
- **Strengths/limits.** Rich, scriptable control, but every API is terminal-specific and some need opt-in (kitty `allow_remote_control`). This is why the shell hook is the universal layer and adapters are extras.
- **VTE via AT-SPI.** VTE exposes the terminal as an AT-SPI `terminal` role with the `Text` interface (Orca's `scripts/terminal` consumes it). This is a terminal-agnostic fallback for reading the visible screen in GNOME Terminal and Ptyxis. The Konsole a11y exposure level is unverified.

### thefuck (MIT, last push Jul 2024, effectively unmaintained)
- **How it works.** It re-runs or inspects the last command and its output. Each rule module has `match(command)` and `get_new_command(command)`, with `priority` and `requires_output`. Rules cover git, apt, sudo, typos (difflib) and more.
- **Strengths.** A huge rule corpus, deterministic. **Limits.** Stale; re-running commands can have side effects (Ya-Bro must only inspect, never re-run without consent).
- **Borrow.** The terminal pack's "fix-it" rules use this exact shape (match on argv plus stderr pattern → suggestion plus explanation in AR/EN). Rules are cheap, offline and testable, and come before any LLM call. Avoid importing the package (stale).
- Source: https://github.com/nvbn/thefuck

### command-not-found handlers
- bash's `command_not_found_handle` and zsh's `command_not_found_handler` functions are called with the missing command. Distros map it to a package (Ubuntu `command-not-found`, Fedora `PackageKit-command-not-found`, Arch `pkgfile`; details unverified). **Borrow:** hook the same functions (chaining to the distro handler) to raise a "missing tool" event, so Ya-Bro can offer "install it with … ?" with a confirm step.

## 13. Key takeaways for Ya-Bro architecture

1. **Perception core = Orca's design.** Use `gi.repository.Atspi` directly with one listener, a priority queue, drop-obsolete coalescing, role/state filters and explicit cache invalidation (Orca's cache manager also clears every 60 s). Resolve packs in Orca's order: **app pack → toolkit pack → global core**. Use Accerciser-style inspection as the pack authoring tool.
2. **Selectors = DAP-style fingerprints**, not paths: stable id > role+name (AR and EN) > ancestor chain > sibling index/geometry > OCR/image fallback. Compute a reliability score at authoring time. Auto-reselect with user confirmation and local auto-heal overrides. Use visibility rules for step applicability (Whatfix/WalkMe).
3. **Overlay.**
   - X11: ARGB top-level with an empty XShape **input** region (click-through) and `_NET_WM_STATE_ABOVE`.
   - Plasma Wayland: **gtk4-layer-shell** overlay layer with no keyboard interactivity and an empty input region (koverlay recipe).
   - A KWin effect/script is the fallback for perfect compositor-side drawing. GNOME Wayland needs a Shell extension.
   - Keep a Gromit-style explicit pass-through/interactive toggle.
4. **Step bubble UX = driver.js + Shepherd + Floating UI patterns.**
   - Even-odd cutout that lets clicks through only at the target.
   - Flip/shift/hide placement and scroll-into-view first.
   - Missing-target → centred bubble plus a pre-step (`beforeShowPromise`).
   - Advance on observed events, not "Next".
   - Re-measure on bounds change.
   - Live-region-style announcements and AT-SPI exposure of the bubble.
   - RTL mirroring.

   Copy patterns, not code: Shepherd and Intro.js are AGPL/commercial; driver.js and Joyride are MIT.
5. **Struggle detection thresholds (initial).** Use PostHog's published rage click (3 clicks, < 30 px, < 1 s apart) and dead click (no DOM/state change within 2.5 s) defaults, translated to AT-SPI events. Add desktop-specific menu-thrash, undo-loop, error-loop (same failing command ≥ 2–3×) and idle-in-flow signals. Use a decaying score, one offer, then cool-down. FullStory, Clarity and Hotjar publish no numbers.
6. **Input injection.**
   - X11: XTEST (xdotool-equivalent via python-xlib/XTest).
   - Wayland: **libei via the RemoteDesktop portal** (user consent); KWin scripting for window queries (kdotool approach).
   - uinput (ydotool/dotool) only as an opt-in out-of-process fallback.
   - Prefer AT-SPI `Action.do_action` / `EditableText` and clipboard paste over synthesized keys, especially for Arabic, because libei and uinput drop characters missing from the active layout.
7. **Input observation.** X11: XRecord or XInput2 raw events, as Espanso does. Wayland: rely on AT-SPI events (no global key snooping without `/dev/input` access). Never log key values, only categories.
8. **Voice pipeline.** Model it as HA Assist-style stages (wake/PTT → VAD → STT → intent → TTS) with events. Run engines as **Wyoming services on localhost/Unix sockets**, which isolates GPL engines (Piper/espeak-ng) and reuses existing servers. Consider sherpa-onnx as one runtime for VAD, KWS, STT and TTS.
9. **Wake word.** The default is **push-to-talk / hotkey**; a wake word is opt-in. Use **openWakeWord code (Apache-2.0)** with a **self-trained "Ya Bro / يا برو" model** from synthetic clips (Piper EN voices, Piper ar_JO-kareem, optionally Azure ar-EG for training) plus real recordings and a speaker verifier. **Do not ship openWakeWord's pretrained models (CC BY-NC-SA 4.0)**, and confirm the license status of its feature-extractor ONNX files. Avoid Porcupine (AccessKey, no Arabic), Snowboy and Precise (dead). microWakeWord is a later option.
10. **VAD.** Use **Silero VAD (MIT)**. Avoid TEN VAD (Agora non-compete conditions) as a default.
11. **STT (Arabic + English).** Use **Whisper large-v3 / v3-turbo via faster-whisper or whisper.cpp (MIT)** as the primary engine; it has the best open trade-off for mixed AR/EN.
    - Evidence: OUAAL avg WER 29.87% (v3) / 33.30% (turbo). Egyptian (SADA subset) is 59–63% for v3/turbo, 48.44% for v2 and 40.97% for NVIDIA Conformer-CTC + LM.
    - Benchmark v2 vs v3 on the maintainer's Egyptian/code-switched speech before deciding.
    - Arabic-only option: NVIDIA `stt_ar_fastconformer_hybrid_large_pcd_v1.0` (CC-BY-4.0, diacritized output, non-streaming).
    - Use Vosk or a sherpa-onnx grammar model for low-latency command words.
    - Avoid non-commercial weights (ArTST, SeamlessM4T v2, MMS, Moonshine legacy Arabic) and models without Arabic (distil-whisper is English-only; Parakeet v3 and Canary v2 cover 25 European languages but not Arabic).
12. **TTS (Arabic + English).**
    - **Piper (now GPL-3.0 at OHF-Voice/piper1-gpl), out of process**, with an English voice plus **ar_JO-kareem** (the only Arabic Piper voice, one speaker, Jordanian).
    - Piper **already includes Arabic tashkeel** (libtashkeel, `use_tashkeel=True`). Add CATT (Apache-2.0) only if quality demands it.
    - Split code-switched text by script per segment.
    - For an Egyptian accent the only verified option is cloud: **Azure ar-EG-SalmaNeural / ar-EG-ShakirNeural** (opt-in). Google offers only ar-XA (MSA).
    - Avoid XTTS-v2 weights (CPML), F5 weights (CC-BY-NC), MMS-TTS (NC), Fish (community license) and Chatterbox (retired Aug 2026).
13. **Barge-in.** Load PipeWire `module-echo-cancel` (WebRTC AEC). Play TTS into the echo-cancel sink and read the mic from the echo-cancel source. Keep VAD and the command KWS running during TTS, and stop or duck TTS on speech.
14. **Terminal integration.**
    - Ship Ya-Bro shell snippets (bash via bash-preexec, zsh/fish native) that send start/end events (cmd, cwd, exit, duration) over a Unix socket. Use an atuin-like schema, and optionally read atuin's DB.
    - Also emit OSC 133/OSC 7 for terminal-side marks; supported by kitty, WezTerm, foot, **Konsole ≥ 22.08**, Ghostty and iTerm2, with VTE unclear.
    - Per-terminal adapters: **Konsole D-Bus** (`getDisplayedText`, `sendText`, `foregroundProcessId`) first on KDE, then kitty `@ get-text --extent last_cmd_output` and `wezterm cli get-text`, with AT-SPI Text on VTE as the generic fallback.
    - Implement thefuck-style `match`/`get_new_command` rules plus a chained `command_not_found_handle` for offline fixes.
15. **Help content.** Write pack docs as Mallard-like topic pages. Deep-link to existing `help:` (Yelp/KHelpCenter) pages. Add a KDE "What's This?"-style "explain this element" mode.

## 14. Sources

**Screen readers / AT-SPI**
- Orca source: https://gitlab.gnome.org/GNOME/orca (src/orca/event_manager.py, script_manager.py, ax_cache_manager.py, scripts/apps, scripts/toolkits, scripts/terminal); tags 51.1 (2026-10-14)
- Accerciser: https://gitlab.gnome.org/GNOME/accerciser
- dogtail: https://github.com/vhumpa/dogtail · LDTP2: https://github.com/ldtp/ldtp2
- Odilia: https://github.com/odilia-app/odilia

**Visual automation**
- SikuliX: https://github.com/RaiMan/SikuliX1 (redirects to archived oculix-org/SikuliX1)
- PyAutoGUI: https://github.com/asweigart/pyautogui · pywinauto: https://github.com/pywinauto/pywinauto

**Input**
- xdotool: https://github.com/jordansissel/xdotool · ydotool: https://github.com/ReimuNotMoe/ydotool · dotool: https://git.sr.ht/~geb/dotool · wtype: https://github.com/atx/wtype
- wdotool: https://github.com/cushycush/wdotool · kdotool: https://github.com/jinliu/kdotool · libei: https://gitlab.freedesktop.org/libinput/libei
- input-remapper: https://github.com/sezanzeb/input-remapper · keyd: https://github.com/rvaiya/keyd

**Automation frameworks**
- Espanso: https://github.com/espanso/espanso (espanso-detect/src/x11/native.cpp, espanso-detect/src/evdev/)
- AutoKey: https://github.com/autokey/autokey · Hammerspoon: https://github.com/Hammerspoon/hammerspoon , https://www.hammerspoon.org/docs/ · AutoHotkey: https://github.com/AutoHotkey/AutoHotkey

**Tours**
- driver.js: https://github.com/nilbuild/driver.js · Shepherd: https://github.com/shipshapecode/shepherd · Intro.js: https://github.com/usablica/intro.js · React Joyride: https://github.com/gilbarbara/react-joyride · Floating UI: https://github.com/floating-ui/floating-ui

**DAPs / analytics**
- Whatfix: https://support.whatfix.com/docs/improve-element-selection-using-element-reliability-indicators-for-steps , https://support.whatfix.com/docs/element-reselection-automation , https://support.whatfix.com/docs/screensense-auto-heal , https://support.whatfix.com/docs/visibility-rules-for-content , https://support.whatfix.com/desktop/docs/what-is-whatfix-desktop , https://support.whatfix.com/desktop/docs/configure-sap-applications-for-whatfix-desktop
- WalkMe: https://support.walkme.com/knowledge-base/find-element-basic-troubleshooting-tips , https://patentsgazette.uspto.gov/week35/OG/html/1538-1/US12405809-20250902.html
- Element detection patent: https://patents.google.com/patent/US11461090
- FullStory: https://help.fullstory.com/hc/en-us/articles/360020624154 · Clarity: https://learn.microsoft.com/en-us/clarity/insights/semantic-metrics · Hotjar: https://www.hotjar.com/blog/rage-clicks/ · PostHog: https://github.com/PostHog/posthog-js

**Help systems**
- Mallard: http://projectmallard.org/ · Yelp: https://gitlab.gnome.org/GNOME/yelp · KHelpCenter: https://apps.kde.org/khelpcenter/ · Plasma Welcome: https://apps.kde.org/plasma-welcome/ · GNOME Tour: https://gitlab.gnome.org/GNOME/gnome-tour

**Annotators / overlays / pets**
- Gromit-MPX: https://github.com/bk138/gromit-mpx · ksnip: https://github.com/ksnip/ksnip · Flameshot: https://github.com/flameshot-org/flameshot · key-mon: https://github.com/critiqjo/key-mon
- koverlay: https://github.com/erik96/koverlay · desktopPet (eSheep): https://github.com/Adrianotiger/desktopPet · MangoHud: https://github.com/flightlessmango/MangoHud

**Voice frameworks**
- Talon: https://talonvoice.com , https://talon.wiki , https://github.com/talonhub/community · Numen: https://git.sr.ht/~geb/numen
- Wyoming: https://github.com/OHF-Voice/wyoming · Rhasspy3: https://github.com/rhasspy/rhasspy3 · OVOS: https://github.com/OpenVoiceOS/ovos-core · Mycroft: https://github.com/MycroftAI/mycroft-core · HA pipelines: https://developers.home-assistant.io/docs/voice/pipelines/

**Wake word / VAD**
- openWakeWord: https://github.com/dscripka/openWakeWord · Porcupine: https://github.com/Picovoice/porcupine · microWakeWord: https://github.com/kahrendt/microWakeWord · Snowboy: https://github.com/Kitt-AI/snowboy · Precise: https://github.com/MycroftAI/mycroft-precise
- Silero VAD: https://github.com/snakers4/silero-vad · py-webrtcvad: https://github.com/wiseman/py-webrtcvad · TEN VAD: https://github.com/TEN-framework/ten-vad (LICENSE) · pyannote: https://github.com/pyannote/pyannote-audio

**STT**
- Open Universal Arabic ASR Leaderboard: https://arxiv.org/abs/2412.13788 (HTML v1), https://huggingface.co/spaces/elmresearchcenter/open_universal_arabic_asr_leaderboard
- whisper.cpp: https://github.com/ggml-org/whisper.cpp · faster-whisper: https://github.com/SYSTRAN/faster-whisper · distil-whisper: https://huggingface.co/distil-whisper/distil-large-v3.5 · whisper-large-v3-turbo: https://huggingface.co/openai/whisper-large-v3-turbo
- Vosk models: https://alphacephei.com/vosk/models · NVIDIA Arabic FastConformer: https://huggingface.co/nvidia/stt_ar_fastconformer_hybrid_large_pcd_v1.0 · Parakeet v3: https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3 · Canary v2: https://huggingface.co/nvidia/canary-1b-v2
- Moonshine: https://github.com/moonshine-ai/moonshine (LICENSE) · sherpa-onnx: https://github.com/k2-fsa/sherpa-onnx · ArTST: https://huggingface.co/MBZUAI/artst_asr_v3 · SeamlessM4T v2: https://huggingface.co/facebook/seamless-m4t-v2-large
- ArzEn: https://aclanthology.org/2020.lrec-1.523 · ArzEn-LLM: https://arxiv.org/abs/2406.18120 · PolyWER: https://aclanthology.org/2024.findings-emnlp.356.pdf

**TTS / tashkeel / AEC**
- Piper: https://github.com/OHF-Voice/piper1-gpl (README, docs/VOICES.md, src/piper/voice.py, src/piper/tashkeel/SOURCE), archived https://github.com/rhasspy/piper , voice card https://huggingface.co/rhasspy/piper-voices/tree/main/ar/ar_JO/kareem/medium
- libtashkeel: https://github.com/mush42/libtashkeel · Mishkal: https://github.com/linuxscout/mishkal · CATT: https://github.com/abjadai/catt · Shakkala: https://github.com/Barqawiz/Shakkala
- Coqui TTS: https://github.com/coqui-ai/TTS · idiap fork: https://github.com/idiap/coqui-ai-TTS · XTTS-v2: https://huggingface.co/coqui/XTTS-v2 · espeak-ng: https://github.com/espeak-ng/espeak-ng
- Kokoro: https://huggingface.co/hexgrad/Kokoro-82M · MeloTTS: https://github.com/myshell-ai/MeloTTS · F5-TTS: https://github.com/SWivid/F5-TTS , https://huggingface.co/SWivid/F5-TTS · Chatterbox: https://github.com/resemble-ai/chatterbox · Fish-speech: https://github.com/fishaudio/fish-speech · MMS-TTS: https://huggingface.co/facebook/mms-tts-ara
- Azure voices: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts · Google voices: https://docs.cloud.google.com/text-to-speech/docs/list-voices-and-types
- PipeWire echo-cancel: https://docs.pipewire.org/page_module_echo_cancel.html

**Terminal**
- bash-preexec: https://github.com/rcaloras/bash-preexec · atuin: https://github.com/atuinsh/atuin (crates/atuin/src/shell/atuin.bash, crates/atuin-client/migrations/)
- kitty shell integration: https://sw.kovidgoyal.net/kitty/shell-integration/ · kitty remote control: https://sw.kovidgoyal.net/kitty/remote-control/
- WezTerm shell integration: https://wezterm.org/shell-integration.html · `wezterm cli get-text`: https://wezterm.org/cli/cli/get-text.html
- foot: https://codeberg.org/dnkl/foot · Konsole semantic shell integration: https://docs.kde.org/trunk_kf6/en/konsole/konsole/semantic-shell-integration.html , https://konsole.kde.org/changelogs/22.08.html · Konsole D-Bus: https://invent.kde.org/utilities/konsole (src/session/Session.h)
- OSC 133 tracker (secondary): https://terminfo-dev.pages.dev/extensions/osc-133-semantic-prompts · fish terminal compatibility: https://fishshell.com/docs/4.7/terminal-compatibility.html · VTE OSC 133 history: https://lists.gnome.org/archives/commits-list/2017-June/msg02677.html · Ptyxis: https://blogs.gnome.org/chergert/?p=12687
- thefuck: https://github.com/nvbn/thefuck
