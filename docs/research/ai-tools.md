# AI Tools Landscape: How They Work Inside, and What Ya-Bro Takes From Them

**Scope.** This document surveys AI products, open-source agents, research systems and grounding models that overlap with Ya-Bro: an on-screen "bro" that *guides* the user one step at a time on the live app, can later *do* steps itself, and *proactively* notices struggle. For each tool it records how it works internally (perception, overlay/output, input/actuation, knowledge source) and what went wrong, then what Ya-Bro should borrow or avoid. Research date: **2026-11-20**. Fast-moving facts (benchmark numbers, product availability, versions) carry their source date; anything not confirmed from a primary source is marked **(unverified)**. Where source code was read (GitHub, via `gh api`), the file is named.

> Reading guide: section 1 is the summary table, section 2 the per-tool notes grouped by category, section 3 the cross-cutting patterns, section 4 the sources.

---

## 1. Summary table

| Tool | Category | Platform | Perception | Overlay/output | Input/actuation | Knowledge source | Open source? | Key lesson for Ya-Bro |
|---|---|---|---|---|---|---|---|---|
| Clicky / HeyClicky | guider | macOS (HeyClicky also Windows) | Screenshots of all displays (ScreenCaptureKit, max 1280 px) | Full-screen click-through NSPanel, blue cursor flies on Bezier arc; TTS | None (points only); push-to-talk | Claude general knowledge | Yes (MIT, frozen Apr 2026) | Great overlay UX; LLM-guessed pixels are the weak link |
| Skilly | guider | macOS app + web widget | Screenshots (desktop), DOM digest (web) | Same cursor overlay; realtime voice | None | `SKILL.md` per app: vocabulary, common mistakes, curriculum | Yes (Apache-2.0) | Pack format prior art; use structure (DOM/a11y) when available |
| Navisual | guider | Windows | Active-window capture + UIA tree + OCR + icon templates + app adapters | Transparent overlay pointer + caption + TTS | None ("observe, never act") | LLM + app adapters + icon packs | Source-available (FSL-1.1-ALv2) | **"Select, don't ground"**: LLM names target, local a11y resolves it |
| Ourguide | guider | macOS (Electron) | Screenshots on request; earlier custom UI detector + VLM | Highlights next element | None | LLM + live web search | No | Detector+VLM accurate but slow; privacy must be verifiable |
| Copilot Vision Highlights | guider | Windows | User-shared window(s) | Highlights click target in shared app; voice | None | Copilot (cloud) | No | Explicit per-window share + Stop; "show me how" mode |
| Agent S2/S3/S4 | doer | Linux, macOS, Windows | Screenshots; separate grounding model; Tesseract for text | None (agent) | pyautogui code; app APIs (UNO) | General LLM + reflection | Yes (Apache-2.0) | Planner/grounder split with NL element descriptions |
| UI-TARS / Desktop | doer, grounding | Desktop, browser, mobile | Screenshots only (native VLM) | Agent UI | pyautogui via parser | Model weights | Yes (archived repos) | UI-TARS-1.5-7B: viable local vision fallback |
| Claude computer use | doer | Any (dev-provided env) | Screenshots, zoom | None | Dev executes actions (ref. demo: xdotool in Docker X11) | Claude | Ref. impl. open | Follow scaling recipe; screen text = injection surface |
| OpenAI CUA / ChatGPT agent | doer | Cloud VM / browser | Screenshots (+ text browser, terminal) | Watch/take-over UI | Remote VM actions | GPT + connectors | No | Sandboxed doers; confirmations before consequential acts |
| ChatGPT desktop "Work with Apps" | guider (context) | macOS | macOS Accessibility API text; terminal last 200 lines | Chat | None | GPT | No | A11y text context validates AT-SPI-first |
| Open Interpreter OS mode | doer | Desktop (historical) | Screenshots + OCR click-by-text | None | Code against `computer` API | LLM | Yes (pivoted to coding agent) | OCR click-by-text is a cheap grounding pass |
| Self-Operating Computer | doer | Desktop | Screenshots (+ OCR mode) | None | Mouse/keyboard | Various VLMs | Yes (MIT) | Give model labelled candidates, not raw pixels |
| Bytebot | doer | Own Linux container | Screenshots | Web UI to watch | Mouse/keyboard in container | LLM | Yes (archived) | Safe doers use their own desktop; Ya-Bro works on the real one |
| cua (trycua) | doer infra | macOS/Linux/Windows sandboxes | n/a | n/a | Drivers + VMs | n/a | Yes (MIT) | Eval/sandbox infra if Do-it is benchmarked |
| OpenAdapt | doer (recorded) | Web, desktop | Recorded demonstrations | n/a | Compiled deterministic programs | User/agent demonstration | Yes (MIT) | Verify outcomes by read-back, not "looks done" |
| browser-use | doer | Chrome | DOM via CDP, indexed elements | n/a | Python REPL + CDP | LLM | Yes (MIT) | Indexed element list for selection |
| Skyvern | doer | Browser | Screenshots + DOM | n/a | Browser automation | LLM | Yes (AGPL-3.0) | Vision + structure hybrid |
| Project Mariner | doer | Chrome extension | Screenshots/DOM (unverified mix) | Side panel plan | Browser actions | Gemini | No | Show plan; confirm sensitive actions |
| Gemini Live / Astra | guider, proactive | Android/iOS/web | Camera or screen-share video stream | Voice | None | Gemini | No | "Proactive audio": model may stay silent |
| Magic Cue | proactive | Pixel 10 | On-device personal data + optional screen activity | Inline suggestions | None | Gemini Nano | No | Separate toggle for screen-activity use |
| Microsoft Recall | recorder | Copilot+ Windows | Periodic snapshots + OCR | Timeline search | None | Local index | No | Plaintext DB backlash; opt-in + enclave fix |
| Click to Do | guider (on demand) | Copilot+ Windows | Local OCR + Phi Silica + Florence | Overlay actions on selection | None | Local SLM (+ cloud) | No | User-invoked, local perception |
| screenpipe | recorder | macOS/Windows/Linux | A11y text first, OCR fallback, audio | API/apps | None | Local SQLite | Source available (license unclear) | Event-driven capture, a11y-first |
| Rewind / Limitless | recorder | macOS | Continuous screen + audio | Search | None | Local + cloud | No | Capture shut off after Meta acquisition (Dec 2025) |
| Cluely | guider (covert) | macOS/Windows (Electron) | Screen + audio, OCR | Hidden overlay | None | LLM | No | Privilege separation; never hide from user |
| Highlight AI | guider (context) | Desktop | Screen capture (details unverified) | Floating button chat | None | LLMs | No | Thin public technical info |
| Clippy / Lumière | proactive | Office 97 to 2003 | UI event stream; Bayesian (Lumière) vs rules (shipped) | Animated character + balloon | None | Help topics | No | Thresholds, back-off, no repeats; rules-based triggers failed |
| GitHub Copilot inline | proactive | IDEs | Editor context + telemetry | Ghost text | Tab to accept | Code LLM | No | Cheap filter (15% threshold) before LLM call |
| Cursor Tab | proactive | Cursor IDE | Editor context | Ghost text / jumps | Tab | RL-tuned model | No | Show only when P(accept) is at least ~25% |
| JetBrains trigger/filter | proactive | JetBrains IDEs | ~120 telemetry features | Completions | Tab | CatBoost + Mellum | No | Trigger model skips ~20% of calls |
| ProactiveBench / Proactive Agent | proactive (research) | Simulated | Event streams | Offers | n/a | Fine-tuned LLM + reward model | Yes (code/data) | "Offer or not" is learnable; base rates low |
| OmniParser | grounding | Any (screenshots) | Icon detector + caption model | Labelled boxes | n/a | Models | Yes (CC-BY-4.0 repo) | Set-of-marks lifts general LLMs (GPT-4o 0.8 to 39.6 SS-Pro) |
| UI-TARS-1.5, GTA1, Holo2, MAI-UI, UGround, OS-Atlas, ShowUI, SeeClick, Aria-UI, GUI-Actor, Qwen-VL | grounding | Any | Screenshot to coordinates | n/a | n/a | Models | Mostly open weights | SS-Pro: best cascades ~85, UI-TARS-1.5 61.6, general VLMs much lower; icons hardest |
| Claude for Chrome / Comet / Manus / Apple onscreen awareness | doer / guider | Browser / cloud VM / iOS-macOS | Mixed | Mixed | Mixed | Mixed | No | Prompt injection is real; app-declared intents beat pixel driving |

---

## 2. Per-tool notes

### 2.1 Guiders (point, do not click)

#### Clicky (farzaa/clicky, now "HeyClicky")

Sources: https://github.com/farzaa/clicky (README, AGENTS.md, `leanring-buddy/OverlayWindow.swift`, `CompanionManager.swift`, `ElementLocationDetector.swift`, `CompanionScreenCaptureUtility.swift`, read 2026-11-20). Repo created 2026-04-07, MIT, ~8k stars. On 2026-04-27 the author froze the open repo and moved new work to the closed HeyClicky app for Mac and Windows (README).

**How it works**
- macOS menu-bar app (`LSUIElement=true`), Swift/SwiftUI with AppKit bridging.
- **Input:** push-to-talk on `ctrl+option` via a listen-only `CGEvent` tap (`GlobalPushToTalkShortcutMonitor.swift`). Audio streams over a websocket to AssemblyAI; OpenAI and Apple Speech are fallbacks.
- **Perception:** pure vision. On each turn, ScreenCaptureKit grabs every display, downsizes to max 1280 px, JPEG quality 0.8, labelled per screen and marked with which screen holds the cursor (`CompanionScreenCaptureUtility.swift`). No accessibility tree is used.
- **Reasoning/grounding:** transcript + screenshots go to Claude (Sonnet 4.6 default, Opus 4.6 optional) over streaming SSE. The system prompt tells the model to end its reply with a tag `[POINT:x,y:label:screenN]` (or `[POINT:none]`) in screenshot-pixel coordinates (`CompanionManager.swift`). A regex parses the tag off the end, the rest is spoken via ElevenLabs TTS.
- **Coordinate mapping:** clamp to screenshot size, scale screenshot pixels to display points, flip to AppKit bottom-left origin, add the display frame offset (`CompanionManager.swift`).
- **Overlay:** one borderless full-screen `NSPanel` per screen with `level = .screenSaver`, `ignoresMouseEvents = true` (click-through), `collectionBehavior = [.canJoinAllSpaces, .stationary, .fullScreenAuxiliary]`, transparent background, `hidesOnDeactivate = false` (`OverlayWindow.swift`). A blue cursor "buddy" follows the mouse and flies to the target along a quadratic Bezier arc animated frame-by-frame by a timer, rotating to the curve's tangent.
- **Unused alternative:** `ElementLocationDetector.swift` grounds via Claude's Computer Use tool (`computer_20251124`, beta header `computer-use-2025-11-24`), resizing to the Anthropic-recommended size closest to the display aspect ratio (1024x768, 1280x800, 1366x768) on the claim that the computer-use tool engages better "pixel-counting". A code search shows it is not referenced by `CompanionManager.swift`; the shipped path is the inline `[POINT]` tag.
- **Keys:** a Cloudflare Worker proxies Anthropic, ElevenLabs and AssemblyAI so no key ships in the binary (`worker/src/index.ts`).

**Strengths:** tiny surface area; one model call yields both speech and the pointing target; the flying-cursor animation is the viral part of the demo; click-through overlay never steals focus.

**Limits/failures:** pointing accuracy depends entirely on the VLM guessing pixels from a downscaled screenshot; no verification that the point landed on a real control; one point per answer, no multi-step plan; no state tracking between turns other than chat history; macOS-only; analytics via PostHog.

**What Ya-Bro borrows or avoids**
- Borrow: the click-through, always-on-top, all-workspaces overlay pattern (on Linux this likely needs an undecorated, transparent window with an empty input region plus X11-specific "above"/sticky hints, since GTK4 removed some window-management APIs; on Wayland, layer-shell. Implementation to verify in an ADR), Bezier flight animation, push-to-talk, the "speech + one target per turn" response contract, and the key-holding proxy idea.
- Avoid: asking the LLM for raw pixel coordinates as the primary grounding. Ask for a semantic target and resolve it locally against AT-SPI (see Navisual below), keeping VLM pixels as the fallback.

#### Skilly (tryskilly/skilly)

Sources: https://github.com/tryskilly/skilly (README, `leanring-buddy/skills/blender-fundamentals/SKILL.md`, read 2026-11-20). Apache-2.0; created 2026-04-08, last push 2026-11-14. A fork-descendant of Clicky (same `leanring-buddy` project name).

**How it works**
- Same macOS menu-bar + blue Bezier cursor overlay as Clicky, but voice, vision and TTS all go through **OpenAI's Realtime API (`gpt-realtime`)** over one WebSocket (v2.0, 2026-05-30). A "Live Tutor" mode uses server-side VAD so no hotkey is needed.
- A second surface, `@skilly/web`, is a ~24 KB Shadow-DOM widget that sees a page through a **DOM digest, not screenshots**, talks over WebRTC, and points at elements by `data-skilly` attribute, CSS selector or text.
- **Knowledge:** `SKILL.md` files with YAML front-matter (`target_app`, `bundle_id`, `pointing_mode`, `difficulty`, `recommended_model`...) and body sections: Teaching Instructions, Expertise (exact UI vocabulary), Teaching Approach, Common Beginner Mistakes to Watch For, What NOT to Do, and a staged Curriculum with goals and completion signals. The README says a skill is composed into a "5-layer system prompt". Bundled skills: Blender, After Effects, Premiere Pro, DaVinci Resolve, Figma.
- Pricing: BYO OpenAI key (README estimates about $0.06 to $0.10 per voice minute) or $19/month hosted.

**Strengths:** the skill format is the clearest public example of an app "pack" for a tutor: vocabulary, known pitfalls, and progressive curriculum. Realtime speech-to-speech keeps latency low.

**Limits/failures:** still VLM-pixel pointing on desktop; realtime audio cost per minute; locked to one vendor's realtime stack.

**What Ya-Bro borrows or avoids:** borrow the SKILL.md shape almost directly for Ya-Bro packs (front-matter keyed by app id / WM_CLASS / desktop file, plus "common mistakes" which double as **struggle-detection hints**). Note the web widget's lesson: when a structured tree exists (DOM), use it instead of pixels; on Linux the AT-SPI tree is the analogue.

#### Navisual (NavisualGuide/navisual)

Sources: https://github.com/NavisualGuide/navisual (README and ARCHITECTURE.md, read 2026-11-20). Windows-only, Rust + Tauri + Svelte 5; FSL-1.1-ALv2 (source-available, converts to Apache-2.0 after two years). Small project (single-digit stars) but the most relevant architecture found.

**How it works**
- **Observe, never act**: never moves the mouse, clicks or types.
- **Perception:** BitBlt capture of the *active window only* (the union of all visible same-process top-level windows, so floating dialogs are not cropped); its own panel and overlay are blanked out of the capture. Change detection via an 8x8 average hash, on demand.
- **Model contract:** via `tool_use`, the model returns 1 to 4 steps, each with `instruction`, `target_text`, `target_role`, `target_bbox`, `overlay_type`, `clipboard`, `checkpoint`, `state_summary`.
- **Local element locator ("select, don't ground")**: the AI's text description is resolved on the machine: (1) app object-model adapters (Excel cells, Office COM, a Blender add-on that reports tool positions over 127.0.0.1); (2) AI picks an element id from a verified list of on-screen elements; (3) Windows UI Automation name matching with anchored regex then substring, rejecting containers, off-screen nodes and length outliers, under 5 ms; (4) Windows OCR with exact, word-boundary and fuzzy (LCS 0.85/0.75/0.70) passes, 10 to 50 ms; (5) icon template matching ("Nav-Packs", e.g. a 66-icon Blender pack). The model's own predicted bbox is only a proximity prior.
- **Debuggability:** a drawer records which pass resolved the target and why every other candidate was rejected.
- **Advancing:** user presses a "next" hotkey, or Autopilot advances when the screen changes; a "Wrong" hotkey re-analyses.
- **Privacy:** active-window crop (about 80% fewer image tokens than full desktop, per ARCHITECTURE.md), screenshots in memory only, no heuristic redaction (the authors call it unreliable) but a pause hotkey and local Ollama option; last-clicked control is reported by name and role only, passwords as "(password field)".
- Cost controls: prompt caching on the system prompt, daily/monthly token caps.

**Strengths:** grounding accuracy comes from the OS accessibility data, so a cheap model is enough; failures are visible before anything happens; multi-step responses with checkpoints cut API calls 2 to 4x (their claim).

**Limits/failures:** Windows-only today (macOS/Linux on roadmap "v1.x"); UIA misses icon-only and custom-drawn UI, needing OCR and per-app icon packs; free tier routes screenshots to free providers that may train on them (disclosed in README).

**What Ya-Bro borrows or avoids:** this is the template for Ya-Bro's perception stack. Swap UIA for AT-SPI (`pyatspi`/`Atspi` GI), Windows OCR for Tesseract or a local OCR model, keep the cascade order and the debug trace of which pass won. Adopt the step schema (`instruction`, `target_name`, `target_role`, `bbox_hint`, `checkpoint`) and the "active window plus its dialogs only" capture rule. Adopt the "pack can include icon templates and an in-app add-on" idea for apps with custom-drawn UI (Blender, GIMP canvases, games).

#### Ourguide

Sources: Show HN thread https://hn.svelte.dev/item/46769422 (Jan 2026), Product Hunt https://www.producthunt.com/products/ourguide/launches (launch 2026-01-20).

**How it works:** Electron app, macOS (live), OS-wide. "Guide mode" overlays the screen and highlights the next element; "Ask mode" is a vision chat with screen context. Per the author on HN: an earlier version trained a computer-vision model on ~2,300 screenshots to detect/segment UI elements and then had a VLM pick one; it beat UI-TARS on accuracy but was too slow, so the shipped version is simpler and responds in under 1 s (internals of the current version: unverified). Screenshots taken only when the user asks for the next step; a PII filter runs first and inference runs in TEEs via Tinfoil (author's claims, unverified). Live web search for current app docs.

**Limits/failures:** HN commenters pushed back hard on sending screenshots to an indie service without verifiable guarantees, and questioned testimonial authenticity. A "why not fix the UI" critique also came up.

**What Ya-Bro borrows or avoids:** "computer use without the use" framing (author's phrase) matches Ya-Bro's guide-first stance. Detector+VLM-pick is accurate but slow, so latency must be budgeted. Privacy must be verifiable (open source, local-first, show exactly what is sent), not just claimed.

#### Microsoft Copilot Vision on Windows, with Highlights

Sources: https://blogs.windows.com/windows-insider/2025/05/12/copilot-on-windows-windows-insiders-can-now-use-vision-with-2-apps-and-new-highlights-feature-with-1-app/ ; https://blogs.windows.com/windowsexperience/2025/06/12/copilot-vision-on-windows-with-highlights-now-available-in-us/ (2025-06-12).

**How it works:** In the Copilot app the user clicks the glasses icon and explicitly picks a window (or two) to share. Copilot then talks about what it sees, and in **Highlights** mode ("show me how to...") it marks where to click inside the shared app. It is opt-in per session, with a Stop button; launched US-only, labelled Copilot Labs. Internals (whether it uses UI Automation or pure vision for the highlight) are not documented publicly (unverified).

**Strengths:** proves the "guide, don't drive" pattern is mainstream; explicit, visible share-a-window consent.

**Limits/failures:** Highlights worked on one app at a time at launch; cloud-only; regional limits.

**What Ya-Bro borrows or avoids:** per-session, per-window sharing consent with a clear on/off indicator; "show me how" as a named mode.

### 2.2 Doers (computer-use agents that click and type)

#### Agent S / S2 / S2.5 / S3 / S4 (simular-ai) and Simular "Sai"

Sources: https://github.com/simular-ai/Agent-S (README; `gui_agents/s3/README.md`; `gui_agents/s3/agents/grounding.py`, read 2026-11-20); papers https://arxiv.org/abs/2410.08164 (S1, ICLR 2025), https://arxiv.org/abs/2504.00906 (S2, COLM 2025), https://arxiv.org/abs/2510.02250 (S3, TMLR 2026). Apache-2.0, ~13k stars, Python package `gui-agents`, runs on Linux, macOS, Windows.

**How it works**
- **Two-model split (S2 onward):** a strong general "worker" model (README recommends `gpt-5-2025-08-07`) plans and emits actions as Python calls on an Agent-Computer Interface (`OSWorldACI`) with *natural-language element descriptions*, e.g. `click(element_description=...)`. A separate **grounding model** (recommended UI-TARS-1.5-7B) turns each description into coordinates.
- From `grounding.py`: `generate_coords()` sends the screenshot plus `Query:<description>\nOutput only the coordinate of one point` to the grounding model and regex-parses the first two integers; `resize_coordinates()` rescales from the grounding model's output space (1920x1080 for UI-TARS-1.5-7B, 1000x1000 for UI-TARS-72B) to the screen. Text-span targets use **Tesseract OCR** word boxes, with an LLM picking the word id. Actions compile to `pyautogui` code strings. A LibreOffice-specific action talks UNO directly to set spreadsheet cells, i.e. app APIs beat pixels when available.
- Extras: reflection agent, trajectory capped at 8 images by default, optional local code-execution agent (`call_code_agent`) running Python/Bash (README warns it runs arbitrary code with user permissions, 30 s Bash timeout).
- **S3 "Behavior Best-of-N" (bBoN):** run several full rollouts and have a judge pick the best by comparing "behavior narratives".
- **S4 (2026-10-20, arXiv 2610.28601):** an agent that evolves its own tool interfaces from experience (README summary).

**Numbers (as reported by Simular):** S3 alone 66% on OSWorld (100 steps), 72.6% with bBoN, described as above the ~72% human baseline (README, 2025-10/12); WindowsAgentArena 50.2% to 56.6% and AndroidWorld 68.1% to 71.6% with 3 rollouts. Production agent "Sai" reported at 73% on "OSWorld 2.0" (2026-08-28). S4 reported 21.3% on the stricter OSWorld V2 with a 27B open model, above the frontier closed models it compares against (README, 2026-10-20; model names as listed in README).

**Limits/failures:** single-monitor assumption; bBoN multiplies cost and time by N and needs a resettable environment, so it does not apply to a user's live desktop; pixel grounding via a separate hosted model adds a round trip per action.

**What Ya-Bro borrows or avoids:** borrow the **planner/grounder split with natural-language element descriptions as the interface**: it lets Ya-Bro swap the grounder (AT-SPI resolver first, OCR second, VLM grounding model third) without touching the planner. Borrow "use the app's own API when it exists" (UNO for LibreOffice, D-Bus for KDE apps). Avoid best-of-N on a live user machine.

#### UI-TARS, UI-TARS-1.5, UI-TARS-2 and UI-TARS Desktop / Agent TARS (ByteDance)

Sources: https://github.com/bytedance/UI-TARS (README), https://github.com/bytedance/UI-TARS-desktop (README), paper https://arxiv.org/abs/2501.12326, UI-TARS-2 report https://arxiv.org/abs/2509.02544. Both repos are **archived** on GitHub as of 2026-11-20 (UI-TARS last push 2026-01, UI-TARS-desktop 2026-10).

**How it works:** a "native agent" model: one VLM (built on Qwen2.5-VL) reads a screenshot and emits `Thought: ... Action: click(start_box='(x,y)')`. Coordinates are absolute in the resized-image space (Qwen2.5-VL convention); the `ui-tars` pip package parses actions and converts to `pyautogui` code with a `factor=1000` and the original image size (README, `README_coordinates.md`). Prompt templates: `COMPUTER_USE`, `MOBILE_USE`, `GROUNDING` (action only, no thought). UI-TARS Desktop is an Electron app offering local and remote "computer operator" and "browser operator"; Agent TARS is the broader CLI/Web-UI agent with MCP tools (v0.3.0, 2025-11-05).

**Numbers (UI-TARS README, 2025-04):** UI-TARS-1.5: OSWorld 42.5 (100 steps) vs OpenAI CUA 36.4 and Claude 3.7 28; WindowsAgentArena 42.1; ScreenSpot-V2 94.2; **ScreenSpot-Pro 61.6** vs CUA 23.4 and Claude 3.7 27.7. UI-TARS-1.5-7B is open weights on Hugging Face.

**Limits/failures:** pure-vision, so it must re-see the screen every step; repos are archived, so long-term maintenance is uncertain.

**What Ya-Bro borrows or avoids:** UI-TARS-1.5-7B is the de-facto open grounding model (Agent S recommends it) and can run locally on a GPU; good candidate for Ya-Bro's vision fallback when AT-SPI fails. Mind the coordinate convention (absolute vs 0-1000 normalized) per model.

#### Anthropic Claude computer use (API tool + reference implementation)

Sources: https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool (read 2026-11-20); reference implementation https://github.com/anthropics/claude-quickstarts/tree/main/computer-use-demo.

**How it works:** a client-side tool: Claude asks for `screenshot`, then emits actions with pixel coordinates; the developer's code executes them. The reference demo (`computer-use-demo/README.md` and `computer_use_demo/tools/computer.py`, read 2026-11-20) runs a Linux desktop in Docker with X11 + VNC, executes input with `xdotool` (`mousemove --sync`, `click`, `key`), and scales both screenshots and coordinates to the closest of `MAX_SCALING_TARGETS` = XGA 1024x768, WXGA 1280x800, FWXGA 1366x768 rather than relying on API-side resizing (README: API resizing lowers accuracy and speed). Smaller screens are padded to 1024x768. A separate "Computer Use Best Practices" quickstart runs natively on macOS with image pruning, prompt caching and trajectory recording. Tool versions documented on 2026-11-20:
- `computer_toolset_20260801` (current, no beta header; Claude 5.x family): 17 member tools incl. `screenshot`, `zoom(region)`, click variants, `left_click_drag`, `left_mouse_down/up`, `scroll`, `type`, `key`, `hold_key`, `wait`, `cursor_position`.
- `computer_20251124` (beta `computer-use-2025-11-24`; Opus 4.5 to 4.7, Sonnet 4.6), `enable_zoom` off by default.
- `computer_20250124` (beta `computer-use-2025-01-24`).
**Coordinate scaling:** recommended screen sizes 1024x768 or 1280x720 (desktop), 1280x800 or 1366x768 (web); avoid above 1920x1080. Image limits: 2,576 px long edge and ~3.75 MP for Opus 4.7 and later (toolset rejects oversized images rather than downscaling); 1,568 px and ~1.15 MP for earlier models. Developer downscales by `scale = min(1, 1568/long_edge, sqrt(1.15e6/(w*h)))` and divides Claude's coordinates by `scale`; Retina needs a 2x correction. Each screenshot costs roughly 1,000 to 1,800 input tokens; docs suggest at most ~20 images per request and batching actions.
**Safety:** classifiers scan screenshots/tool results for prompt injection; docs recommend VMs, domain allowlists and human confirmation for consequential actions.

**What Ya-Bro borrows or avoids:** Ya-Bro already uses Claude. For the vision fallback, follow the scaling recipe exactly (Clicky's author claims, in an unused file, that aspect-ratio-matched sizes reduce X-axis error; the reference implementation uses the same three targets). For Do-it mode, mirror the action vocabulary but execute via AT-SPI actions (`doAction`, `setText`) before synthetic input, and keep a human confirmation gate for irreversible steps. Treat on-screen text as untrusted (prompt-injection surface).

#### OpenAI Operator / CUA / ChatGPT agent, and the ChatGPT desktop app

Sources: CUA launch (2025-01-23) https://openai.com/index/computer-using-agent/ (403 to automated fetch; numbers cross-checked via UI-TARS README); ChatGPT agent https://openai.com/index/introducing-chatgpt-agent/ (2025-07-17), system card https://deploymentsafety.openai.com/chatgpt-agent; Work with Apps https://help.openai.com/en/articles/10119604-work-with-apps-on-macos and https://techcrunch.com/2024/11/14/chatgpt-can-now-read-some-of-your-macs-desktop-apps/.

**How it works**
- **CUA/Operator (Jan 2025):** GPT-4o-based vision model trained with RL to act on raw screenshots in a cloud browser; user can take over; confirmations before sensitive actions. OSWorld: the UI-TARS README lists CUA at 36.4 (100 steps) and a "previous SOTA" of 38.1 (200 steps) without naming it; attributing 38.1% to CUA at launch is from memory of OpenAI's post (unverified, page returned 403). WebVoyager 87 (UI-TARS README table).
- **ChatGPT agent (Jul 2025):** merges Operator and deep research: its own virtual computer with a visual browser, a text browser, a terminal and API connectors; asks permission before consequential actions. OpenAI's launch post now carries an "outdated" banner. OSWorld figure for ChatGPT agent: (unverified).
- **ChatGPT desktop "Work with Apps" (Nov 2024, macOS):** reads other apps' text through the **macOS Accessibility API**, not screenshots; terminals contribute the last 200 lines of open panes; selected text is prioritized; VS Code needs an extension; a banner shows which apps are connected; content is attached only when the user sends a message.

**Strengths:** accessibility-text context is cheap, exact and private-ish compared with screenshots; explicit connected-apps banner.

**Limits/failures:** A11y text cannot convey visual layout or images (TechCrunch); CUA-style agents run in a remote sandbox, not on the user's live apps.

**What Ya-Bro borrows or avoids:** the Work-with-Apps design is strong validation for **AT-SPI-first context gathering**: read focused-window text, selected text, terminal scrollback (Konsole exposes text via AT-SPI and D-Bus) and attach it only on the user's turn or on an accepted proactive offer, with a visible "what I can see" indicator.

#### Open Interpreter (OS mode)

Sources: https://docs.openinterpreter.com/guides/os-mode ; https://docs.openinterpreter.com/code-execution/computer-api ; repo https://github.com/openinterpreter/open-interpreter (README read 2026-11-20).

**How it works (historical):** the Python CLI's experimental `--os` mode let an LLM write code against a `computer` API: `computer.display.view()` screenshots, `computer.mouse.click("on-screen text")` locates text via OCR (pytesseract) and clicks, `computer.mouse.move(icon="description")` locates an icon by description. Single display only; needs screen-recording permission.

**Status:** as of 2026-11 the repo README describes Open Interpreter as a coding agent (a Codex fork with "harness emulation" for low-cost models); OS mode no longer features (whether it still exists in the new codebase: unverified).

**What Ya-Bro borrows or avoids:** "click by visible text" through OCR is a cheap, model-free grounding pass worth keeping in the cascade. The project's pivot is a reminder that general OS-control agents are hard to make reliable.

#### Self-Operating Computer (OthersideAI)

Source: https://github.com/OthersideAI/self-operating-computer (README). MIT, released Nov 2023.

**How it works:** screenshot in, mouse/keyboard out; supports GPT-4o/4.1, o1, Gemini, Claude 3, Qwen-VL, LLaVA; modes like `-with-ocr` add OCR text boxes the model can reference instead of raw coordinates. Early proof that pure-pixel coordinates from general VLMs were unreliable, which drove the OCR and set-of-mark variants.

**What Ya-Bro borrows or avoids:** historical lesson only: give the model labelled candidates (OCR boxes, a11y ids) rather than asking for raw pixels.

#### Bytebot

Source: https://github.com/bytebot-ai/bytebot (README). Apache-2.0, archived (last push 2025-09).

**How it works:** the agent gets **its own containerized Linux desktop** (Docker Compose or Railway), sees it via screenshots, controls it with mouse/keyboard, has its own filesystem and password-manager integration; the user watches/takes over through a web UI.

**What Ya-Bro borrows or avoids:** sandboxed "agent's own desktop" is the safe pattern for doers but is the opposite of Ya-Bro's premise (work on the user's real session). For Do-it mode on the live desktop, compensate with step-by-step narration, confirmation for destructive actions, and an always-visible "stop" control.

#### cua (trycua)

Source: https://github.com/trycua/cua (repo metadata read 2026-11-20; MIT, ~33k stars). Describes itself as open-source drivers, cross-OS sandboxes (macOS/Linux/Windows VMs) and benchmarks for computer-use agents. Detailed internals not reviewed for this document (unverified beyond the repo description). Relevance: a source of sandboxes and an evaluation harness if Ya-Bro ever benchmarks Do-it mode.

#### OpenAdapt

Sources: https://github.com/OpenAdaptAI/OpenAdapt (README, read 2026-11-20). MIT.

**How it works (2026 positioning):** a person or agent does a task once ("Explore"), OpenAdapt records it and **compiles it into a deterministic program** that replays with no model calls ("Run"), checks the target record before each save, **reads the save back from the system of record**, and stops on mismatch ("Repair" asks an agent and a human). Earlier versions (2023 to 2024) were a demonstration-recording + process-mining project.
**Notable measurement (README):** in a fault-injection test, the app's on-screen "Saved" message reported 54 of 72 bad saves as successful; a computer-use agent claimed success on all 30 bad saves in another test.

**What Ya-Bro borrows or avoids:** for Do-it mode, never trust "it looks done" on screen; verify state through AT-SPI properties, files, or app APIs after each step. Recording a user's successful path and replaying it as a pack "recipe" is a possible later feature.

#### browser-use

Source: https://github.com/browser-use/browser-use (README read 2026-11-20; MIT, ~122k stars). Drives a real Chrome over the Chrome DevTools Protocol. Earlier versions (2024 to 2025) serialized the page into an indexed list of interactive DOM elements (plus optional screenshot) and the LLM picked actions by index (from prior knowledge, unverified against current code). The current README describes "V4" as the model writing Python cells into one persistent REPL that calls helper functions and raw CDP, e.g. `bu.click(41)` (still element-index based). The README also contains instructions addressed to AI agents asking them to send feedback to the vendor; these were ignored for this research.

**What Ya-Bro borrows or avoids:** the "numbered interactive elements" observation format is exactly what Ya-Bro should build from the AT-SPI tree for the LLM (id, role, name, state, bbox), so the model selects instead of grounds.

#### Skyvern

Source: https://github.com/Skyvern-AI/skyvern (AGPL-3.0, ~23k stars). Browser workflow automation combining LLM + computer vision over screenshots and DOM, targeted at form-heavy workflows. Internals not re-read for this document (unverified detail). Relevance to Ya-Bro is low beyond "vision + DOM hybrid beats either alone".

### 2.3 Recorders (continuous capture) and the privacy lessons

#### Microsoft Recall (and the 2024 backlash)

Sources: https://www.windowscentral.com/software-apps/windows-11/microsoft-should-recall-windows-recall-security-researcher-finds-microsofts-new-ai-tool-woefully-insecure ; https://www.techspot.com/news/103258-researcher-microsoft-windows-recall-has-security-gaps-you.html (June 2024); redesign: https://blogs.windows.com/windowsexperience/2024/09/27/update-on-recall-security-and-privacy-architecture/ ; https://www.pcworld.com/article/2470708/microsoft-now-confirms-you-can-opt-out-of-and-remove-windows-recall.html.

**How it works:** Copilot+ PCs take periodic snapshots of the screen, OCR them, and index them locally so the user can search their past activity.

**Failure:** before launch (May/June 2024), researcher Kevin Beaumont showed the OCR text sat in an **unencrypted SQLite database in the user's profile**, readable without admin rights, so any infostealer could take a person's entire history. Recall was also going to be on by default. Microsoft pulled it from the launch.

**Redesign (2024-09-27 blog):** opt-in (off unless chosen), storage services moved into a **VBS enclave** with the UI treated as untrusted, keys protected by the TPM and tied to Windows Hello Enhanced Sign-in Security, re-authentication with time-outs, and the feature removable. Automatic filtering of passwords/credit cards/IDs is reported by Windows Central (secondary source).

**What Ya-Bro borrows or avoids:** Ya-Bro must not keep a screenshot/OCR timeline by default. Short-lived, in-memory context only; anything persisted (e.g., opt-in "remember what I did") goes encrypted, with retention visible and one-click wipe. Default-on capture is the single fastest way to lose trust.

#### Windows Click to Do

Sources: https://support.microsoft.com/windows/click-to-do-do-more-with-what-s-on-your-screen-6848b7d5-7fb0-4c43-b08a-443d6d3f5955 ; https://learn.microsoft.com/en-us/windows/apps/develop/windows-integration/click-to-do.

**How it works:** user-invoked (Win+Q or Win+click) overlay that analyses the current screen with **local OCR, the Phi Silica small language model on the NPU, and a Florence vision encoder**, then offers actions on the selected text or image (summarize, rewrite, etc.). Some text actions also call Microsoft's cloud for safety checks. Works without Recall snapshots. Requires Copilot+ hardware (40 TOPS NPU).

**What Ya-Bro borrows or avoids:** user-invoked "act on what's on screen" with local perception is a privacy-friendly entry point. Ya-Bro's equivalent: a hotkey that snapshots the focused window's AT-SPI subtree and offers contextual help.

#### screenpipe (mediar-ai)

Sources: https://github.com/mediar-ai/screenpipe (repo metadata 2026-11-20; license "NOASSERTION" on GitHub); https://docs.screenpi.pe/architecture ; https://mintlify.com/screenpipe/screenpipe/architecture.

**How it works:** Rust app that records screen and audio continuously and locally: text comes **from the accessibility tree first, OCR only when accessibility returns nothing** (Apple Vision / Windows OCR / Tesseract), audio via local Whisper (Deepgram optional), stored in local SQLite with FTS5 search, exposed on a localhost REST API (port 3030) and to agents. Capture is described as **event-driven** (app switch, click, typing pause, scroll) in one doc, while another lists a per-monitor FPS setting (default 1.0, 0.5 on macOS); which is default today is unclear. By 2026 it positions itself as finding workflows "worth automating" (YC S26 per repo description).

**What Ya-Bro borrows or avoids:** borrow **event-driven capture** (only look when something changes) and **a11y-first, OCR-fallback** text extraction. Avoid continuous recording; Ya-Bro needs a rolling window of interaction *events* (not pixels) for struggle detection.

#### Rewind / Limitless

Sources: https://9to5mac.com/2025/12/05/rewind-limitless-meta-acquisition/ ; https://www.techcrunch.com/2025/12/05/meta-acquires-ai-device-startup-limitless/.

**How it worked:** macOS app that recorded the screen and audio continuously and made it searchable (local compression and OCR by the company's description, unverified detail); later pivoted to the Limitless pendant (meeting recorder).
**Outcome:** Meta acquired Limitless (announced 2025-12-05); the Rewind app's screen and audio capture was disabled from **2025-12-19**.

**What Ya-Bro borrows or avoids:** a user's lifetime capture can vanish or change owner with an acquisition. Local-first, open-source storage the user controls is the only durable promise.

#### Highlight AI

Sources: https://highlightai.com/product ; https://techcrunch.com/?p=2902919 (2024). Floating desktop button that attaches screen, voice note or document context to LLM queries and can auto-detect "actionable information" on screen. Whether it uses accessibility APIs, and where screen processing happens, is not documented publicly (unverified); privacy claims are vendor statements. Low technical signal for Ya-Bro beyond "screen-context chat with a floating affordance".

#### Cluely

Sources: https://www.hacktron.ai/blog/hacking-cluely (published 2026-02-14, issue found July 2025); breach reports e.g. https://www.fast.io/resources/cluely-ai-review-2026.md.

**How it works:** Electron + React overlay that captures screen and microphone (Deepgram transcription) and feeds an LLM; marketed as "undetectable" (hidden from screen sharing, Mission Control and the taskbar; exact mechanism not confirmed by the primary source).
**Failures:** Hacktron found that a link in an AI answer could navigate the main window to an attacker page (no `will-navigate` guard), which could then call the unfiltered IPC bridge (`send`/`invoke`/`on` exposed in preload) to take screenshots and record audio with no prompt; the renderer was not sandboxed. A 2025 breach exposing ~83k users' screen and audio data is reported by secondary sources (unverified).

**What Ya-Bro borrows or avoids:** a screen-reading assistant is a high-value target. **Never render LLM output in a context that holds capture or input privileges**; separate the privileged daemon (AT-SPI, capture, input) from the UI, whitelist IPC methods, and never auto-follow links. Ya-Bro's overlay must be visible and honest, never hidden from the user.

### 2.4 Proactive assistance and "when to speak"

#### Microsoft Office Assistant ("Clippy") and the Lumière project

Sources: Horvitz et al., "The Lumière Project: Bayesian User Modeling for Inferring the Goals and Needs of Software Users", UAI 1998, https://arxiv.org/abs/1301.7385 (full text read); Horvitz's notes https://www.erichorvitz.com/lum.htm ; Horvitz, "Principles of Mixed-Initiative User Interfaces", CHI 1999, https://erichorvitz.com/chi99horvitz.pdf ; history https://en.wikipedia.org/wiki/Office_Assistant ; https://www.theregister.com/2023/06/12/clippy_designer_embarrassed.

**How Lumière worked (paper):**
- Built **Bayesian networks** over a user's time-varying goals from a stream of UI events, each evidence variable defined over a time horizon with decay ("action x happened less than t seconds ago").
- **Evidence classes** (paper, section 4), almost a spec for Ya-Bro's struggle detector:
  - *Search*: repetitive scanning, e.g. exploring multiple menus without acting.
  - *Focus of attention*: dwelling on an object or a document region.
  - *Introspection*: a sudden pause after activity, or a marked slowdown.
  - *Undesired effects*: trying to return to a prior state, e.g. undo, or closing a dialog right after opening it.
  - *Inefficient command sequences*: doing something the long way when a shortcut exists.
  - Plus domain-specific state (e.g., what is selected) and the user's typed query words.
- **Wizard-of-Oz study** (experts watching Excel users from another room): experts *could* infer goals but were often uncertain; **poor advice was costly because users took it seriously and started experimenting with the suggested feature, which looked like confirmation to the expert** and pushed both down the wrong path. Experts learned to be conservative and to phrase advice conditionally.
- **Intervention policy:** autonomous help appears only when P(user wants help) exceeds a **user-adjustable threshold ("volume control")**; if the user ignores it, the window **times out with a brief apology**; the same help is **not offered again until the most likely topic changes**. They also experimented with cost-benefit thresholds.

**What shipped and why it failed:** Office 97's assistant was "based in spirit" on Lumière; the Bayesian *query* analysis shipped, but proactive tips were driven by **a relatively simple rule-based system** the Office team added, which Horvitz worried would be distracting (lum.htm). Clippy interrupted on shallow triggers (the famous "It looks like you're writing a letter"), did not learn from dismissals, used a persistent anthropomorphic character that occupied screen space, and was widely disliked. Microsoft turned it **off by default in Office XP (2001)** and **removed it in Office 2007**. Horvitz's 1999 mixed-initiative principles name the failure modes directly: poor guessing of goals, ignoring costs/benefits of action, poor timing, and too little user control.

**What Ya-Bro borrows or avoids**
- Borrow the evidence classes verbatim as detector features: menu open/close loops = *search*; idle after activity = *introspection*; undo bursts, cancel/close dialog, failing command re-runs = *undesired effects*; long paths when a shortcut exists = *inefficient sequences*.
- Borrow the policy: probability threshold with a user-visible "volume" slider; **one offer, then time out with an apology**; **no repeat until the inferred topic changes**; conditional phrasing ("if you're trying to X, ...").
- Avoid: rule-based triggers on single events; persistent character that blocks content; not learning from dismissals; no global off switch. Ya-Bro's humor must never be the interruption itself, only the tone of an offer that already passed the threshold.

#### GitHub Copilot inline suggestions (when to show)

Sources: reverse engineering of Copilot v1.57.7193 (June 2022), https://thakkarparth007.github.io/copilot-explorer/posts/copilot-internals ; GitHub blog https://github.blog/2023-05-17-how-github-copilot-is-getting-better-at-understanding-your-code/ ; https://arxiv.org/abs/2405.14753 (JonBERTa, 2024).

**How it works:**
- Inline "ghost text" asks for 1 to 3 suggestions, **debounces** while the user types fast, caches aggressively (debounce delay in ms: not published, unverified).
- **Hard rules first**: no request if the prompt is under 10 characters, or if the cursor is mid-line unless what follows is whitespace or a closing character.
- **Contextual filter**: a logistic regression over 11 features (previous filter decision, time since last decision, whitespace after cursor, last-line length, document length, cursor offset, language, last character...) gives a score; **below a default 15% threshold, no request is made**. The explicitly-invoked panel has no filter.
- "Still in code" telemetry checks acceptance at 15 s, 30 s, 2 min, 5 min and 10 min.
- In-flight cancellation behaviour: not documented in these sources (unverified).

**Research follow-ups:** JonBERTa (a small transformer filter on code + telemetry) in a 34-developer online study: no filter showed 97.8% of completions with 1.42% acceptance; logistic regression showed 70.5% with 0.62%; JonBERTa-head 65.6% with 1.44%. Median filter latency ~21 ms vs 0.2 ms for logistic regression.

#### JetBrains trigger and filter models (2026)

Source: "Control Models for In-IDE Code Completion", arXiv 2601.20223 (Jan 2026), https://www.alphaxiv.org/abs/2601.20223.md.

A **trigger model** decides whether to run inference at all; a **filter model** hides generated suggestions likely to be rejected. Production uses CatBoost gradient boosting on ~120 telemetry features (typing speed etc.) because transformer latency could not be guaranteed on user hardware. Online A/B: trigger avoided ~20% of inference requests; filter raised accept rate 33 to 48% and cut cancel rate 15 to 37%. Only ~31% of inferences became shown completions; the authors estimate two-thirds no longer match the code by the time they are generated.

#### Cursor Tab (online RL)

Source: https://cursor.com/blog/tab-rl (2025-09-12).

Instead of a separate filter, the Tab model itself is trained with policy gradients on live user feedback: reward for accepted suggestions, penalty for shown-and-rejected ones, so the policy only suggests when its estimated acceptance probability is at least ~25% (per the post). Result reported by Cursor: **21% fewer suggestions with a 28% higher accept rate**. New checkpoints roll out every 1.5 to 2 hours.

**What Ya-Bro borrows from Copilot/JetBrains/Cursor**
- Two-stage gating: a **cheap, local trigger model** on interaction telemetry (milliseconds, no LLM) decides whether to even consider helping; only then call Claude to compose an offer; then a final "is this worth showing" check.
- Measure **accept rate of proactive offers** and tune for fewer, better offers. Treat "dismissed" and "ignored" as negative labels; adapt per user.
- Cancel stale work: if the user's state changes before the offer is ready, drop it (JetBrains: most late generations no longer fit).

#### Proactive agent research

- **Proactive Agent / ProactiveBench** (Lu et al., arXiv 2410.12361, ICLR 2025, https://arxiv.org/abs/2410.12361; code https://github.com/thunlp/ProactiveAgent): agents predict a task from environment events (coding, writing, daily life) and offer help; 6,790 training and 233 test events; a reward model judges whether an offer would be accepted. LLaMA-3.1-8B-Instruct reached 55.06% F1 before fine-tuning (v2/v3); fine-tuning on the data improves it. Lesson: "should I offer now?" is a learnable classification, and the base rate of good offers is low.
- **"Need Help? Designing Proactive AI Assistants for Programming"** (Chen et al., CHI 2025, https://arxiv.org/abs/2410.04596): proactive assistants raised task completion by roughly 12 to 18%, but **only half of participants preferred the higher-frequency variant**; untimely or irrelevant messages hurt the experience.
- **"Assistance or Disruption?"** (Pu et al., CHI 2025, doi 10.1145/3706598.3713357): interruption-management view; participants were ambivalent about highly proactive agents; proactivity should adapt to the work phase.
- **Stuck detection from IDE logs** (Carter and Dewan, ICSE CHASE 2009 and CSCW 2010 "Are You Having Difficulty?", e.g. https://www.springerprofessional.de/doi/10.1145/1880071.1880109): predicted "stuck" status purely from the programmer's own interaction log (edit/debug/navigation/focus event mix over sliding windows; exact features and classifier unverified because the PDFs returned 404). A later GROUP 2010 paper reported the predictor agreed with programmers' self-perception better than human observers did (per search summary).

#### Microsoft "proactive Copilot"

Sources: https://www.windowscentral.com/microsoft/windows-11/microsoft-quietly-scraps-plans-to-bring-copilot-to-notifications-and-settings-on-windows-11-as-it-moves-to-reduce-ai-bloat-across-the-os (2026-03); https://thejournal.com/articles/2026/03/30/microsoft-scales-back-copilot-integrations-in-windows-11.aspx ; https://venturebeat.com/ai/microsoft-copilot-gets-12-big-updates-for-fall-including-new-ai-assistant.

Microsoft 365 Copilot has a "Proactive Actions" preview (next-step suggestions from recent activity). On Windows, Microsoft **shelved planned Copilot suggestions in notifications and Settings in March 2026** amid "AI bloat" criticism. An October 2026 Insider rollout of more agentic Copilot actions on Copilot+ PCs is reported by secondary sources (details unverified). Lesson: OS-wide unsolicited suggestions met user fatigue even at Microsoft scale.

#### Google: Gemini Live / Project Astra, Magic Cue

Sources: https://deepmind.google/models/project-astra/ ; https://techcrunch.com/2025/05/20/project-astra-comes-to-google-search-gemini-and-developers ; Live API docs https://docs.cloud.google.com/vertex-ai/generative-ai/docs/live-api ; Magic Cue https://blog.google/products/pixel/google-pixel-magic-cue-ai-feature/ , https://support.google.com/pixelphone/answer/16508057.

- **Gemini Live** streams camera or screen-share video plus voice to Gemini for low-latency spoken help (Astra research powers it). The **Live API** exposes "proactive audio" (the model decides whether a given input warrants a response, so it can stay silent on irrelevant speech) and "affective dialog" (adapts tone to the user's expression); availability varies by model.
- **Magic Cue** (Pixel 10, Aug 2025): on-device Gemini Nano surfaces info from Gmail/Calendar/Messages/screenshots inside other apps only "when available and useful"; a separate toggle controls use of recent screen activity; new data is processed while charging. Ranking/threshold logic is not published.
- **Project Mariner** (Gemini 2.0 research prototype, Dec 2024): Chrome-extension agent showing its plan in a side panel, asks before sensitive actions; reported 83.5% on WebVoyager (widely cited, self-reported; WebVoyager is not standardized and stricter Online-Mind2Web evaluation finds large gaps, https://arxiv.org/abs/2504.01382).

**What Ya-Bro borrows or avoids:** "proactive audio" is the right primitive for a voice bro: the model may choose silence. Keep a separate, explicit toggle for "use my recent screen activity for suggestions" as Magic Cue does.

### 2.5 Grounding models and benchmarks

**What "grounding" means here:** given a screenshot and an element description ("the Export button"), output its location. It is the step that fails most for pure-vision agents and the step Ya-Bro mostly avoids by asking AT-SPI.

#### Grounding numbers on ScreenSpot-Pro (high-resolution professional apps)

Source: official leaderboard data, https://github.com/GUI-Agent/grounding-leaderboard `results/screenspot_pro.json` (repo last commit 2026-11-10; page https://gui-agent.github.io/grounding-leaderboard/). Benchmark paper: https://arxiv.org/abs/2504.07981. Accuracy = click lands inside the target box; micro-average, greedy decoding.

| Model / system | Overall | Text | Icon | Note |
|---|---|---|---|---|
| GroundCascade (Indeed-UI-32B + Indeed-UI-8B; name as listed in the leaderboard JSON on 2026-11-20) | 85.1 | 92.1 | 73.8 | #1 of 99 entries; cascade, ~2.6 model calls per query, zoom |
| Indeed-UI-32B (zoom-in) | 82.7 | 90.4 | 70.4 | |
| Holo2-235B-A22B (agentic) | 78.5 | 78.8 | 78.0 | best icon score |
| MAI-UI-8B (zoom-in) | 71.9 | 82.1 | 55.5 | small open model |
| GTA1-32B | 63.6 | 78.9 | 38.9 | |
| UI-TARS-1.5 | 61.6 | 76.3 | 37.9 | (UI-TARS-1.5-7B is the open checkpoint Agent S recommends) |
| Qwen2.5-VL-72B-Instruct | 53.3 | 69.4 | 27.3 | general VLM |
| GUI-Actor-2.5VL-7B | 44.6 | 60.0 | 19.7 | |
| UI-TARS-72B (v1) | 38.1 | 50.9 | 17.5 | |
| UGround-v1-72B / -7B | 34.5 / 31.1 | | | |
| Qwen2.5-VL-7B-Instruct | 26.8 | 38.9 | 7.1 | |
| OS-Atlas-7B | 18.9 | 28.1 | 4.0 | |
| "Claude (Computer Use)" | 17.1 | 23.4 | 7.1 | unversioned, almost certainly the early-2025 Claude 3.x entry from the benchmark paper; **not** current frontier capability |
| GPT-5 (minimal / high, "resized") | 18.5 / 6.0 | | | resized-image runs; not representative of native use |
| Aria-UI (MoE, 3.9B active) | 11.3 | 17.1 | 2.0 | |
| ShowUI-2B | 7.7 | 10.8 | 2.6 | |
| SeeClick-7B | 1.1 | 1.8 | 0.0 | |
| GPT-4o | 0.8 | 1.3 | 0.0 | |

Other reported figures: OmniParser V2 + GPT-4o 39.6 on ScreenSpot-Pro (Microsoft blog, 2025-02-12, https://www.microsoft.com/en-us/research/articles/omniparser-v2-turning-any-llm-into-a-computer-use-agent/; OmniParser also cut latency 60% vs V1, no absolute figure given). UI-TARS-1.5 on ScreenSpot-V2: 94.2 vs OpenAI CUA 87.9 and Claude 3.7 87.6 (UI-TARS README, 2025-04). Qwen3-VL technical report (arXiv 2511.21631, Dec 2025) gives ScreenSpot-Pro values around 57 to 62 depending on variant (column mapping unverified). Aggregators list frontier closed models (e.g., Gemini 3 Pro at 72.7) but those were not checked against the official board (unverified).

**Takeaways for Ya-Bro:**
- Icon targets are far harder than text targets for every model (often 20 to 40 points lower). Icon-only toolbars are where AT-SPI names (or pack-supplied icon templates, as in Navisual) matter most.
- Specialist grounders beat general VLMs by a wide margin on dense pro apps; general models asked for raw pixels (Clicky's approach) are the weakest option.
- The best systems now use **zoom/crop-then-ground cascades**; Ya-Bro can do the same cheaply by cropping to the AT-SPI bounding box of the focused window or pane before any vision call.

#### Grounding model one-liners

- **OmniParser (Microsoft, 2024 to 2026)** https://github.com/microsoft/OmniParser: parses a screenshot into interactable regions with an icon detector (YOLO-family; a YOLOv9-E detector added 2026-07) plus an icon-caption model, so any LLM can *select* an element instead of guessing pixels. CC-BY-4.0 repo (model licenses vary). Good model for Ya-Bro's vision fallback "set-of-marks" mode.
- **SeeClick** (2024): early grounding-pretrained VLM; introduced ScreenSpot. Now obsolete numerically.
- **UGround** (OSU, 2024): universal visual grounding trained on large synthetic web data; 31 to 35 on ScreenSpot-Pro.
- **OS-Atlas** (2024): cross-platform grounding foundation model; 4B/7B.
- **ShowUI** (2024): 2B lightweight; token-selection for efficiency; weak on pro apps.
- **Aria-UI** (2024/25): MoE grounding model.
- **GUI-Actor** (Microsoft, 2025): coordinate-free grounding via an attention "action head" over patches instead of emitting numbers.
- **Qwen2.5-VL / Qwen3-VL**: general VLMs with native absolute-coordinate grounding (Qwen2.5-VL uses absolute pixel coordinates of the resized image, per UI-TARS README); base for many GUI specialists (UI-TARS, GTA1, MAI-UI, KV-Ground).

#### Agent-level benchmarks (OSWorld)

- **OSWorld** (xlang): 369 real Ubuntu/Windows tasks; **human baseline 72.36%** (official site, https://os-world.github.io/ redirecting to http://osworld-v1.xlang.ai/). OSWorld-Verified (2025-07-28) re-checked tasks; **OSWorld 2.0** announced 2026-06-26.
- Reported scores over time: Claude 3.7 28 (100 steps), OpenAI CUA 36.4 (100 steps), UI-TARS-1.5 42.5 (UI-TARS README, 2025-04); Agent S3 69.9% (2025-10) then 72.6% with best-of-N (2025-12) (Simular).
- Secondary aggregators (not checked against the official board, which renders client-side) list OSWorld-Verified top entries around 86 to 90% in Oct/Nov 2026 (e.g., https://presenc.ai/research/osworld-computer-use-leaderboard-2026 citing an agentic framework at 90.19% and Claude 5-family models around 84 to 86%) and best OSWorld 2.0 full completion around 44% (unverified).
- Takeaway: frontier agents now meet or exceed the human baseline on OSWorld-Verified in sandboxes, but the harder OSWorld 2.0/V2 numbers (Agent S4 cites 21.3% for its open-model result under strict pass/fail) show long tasks remain unreliable. For Ya-Bro this argues for *guide-first, step-at-a-time Do-it with verification*, not long autonomous runs on the user's machine.

### 2.6 Other notable tools (short)

- **Anthropic Claude for Chrome** (pilot announced Aug 2025, https://www.anthropic.com/news/claude-for-chrome): browser-extension agent. Anthropic's red-teaming (123 cases, 29 scenarios) found 23.6% prompt-injection attack success without mitigations and 11.2% with them; site-level permissions (financial/adult/piracy sites blocked by default) and confirmations for publishing/purchasing/sharing data. A later Anthropic post (Nov 2025, https://www.anthropic.com/research/prompt-injection-defenses) reports 1.4% for Opus 4.5 with improved safeguards on a different evaluation. Lesson: on-screen content is adversarial input; per-site/per-app permission scopes plus confirmations are table stakes for Do-it mode.
- **Perplexity Comet** (agentic browser): Brave showed indirect prompt injection via hidden text in a Reddit comment led the assistant to exfiltrate a one-time password (2025-08-20, https://brave.com/blog/comet-prompt-injection/), and later injections hidden in screenshots (2025-10-21, https://brave.com/blog/unseeable-prompt-injections/); LayerX's "CometJacking" used a crafted URL to make it pull data from connected services and POST it out (Oct 2025, https://www.akamai.com/blog/security/2025/oct/cometjacking-how-one-click-can-turn-perplexitys-comet-ai-browser-against-you). Lesson: separate "user's instruction" from "content on screen" in prompts; never let screen text trigger tool calls on its own.
- **Manus** (general agent; acquired by Meta, announced 2025-12-30, https://www.theregister.com/2025/12/30/meta_acquires_manus/): each task gets an isolated cloud VM (E2B Firecracker microVMs, https://e2b.dev/blog/how-manus-uses-e2b-to-provide-agents-with-virtual-computers) with browser, shell and file system; multi-agent planning. Not a desktop companion; relevant only as the "agent's own computer" extreme.
- **Apple Intelligence onscreen awareness**: Siri acting on what's on screen via developer-declared **App Intents** (apps expose actions and entities to the assistant rather than being driven by pixels). Delayed in March 2025 to 2026 over quality concerns (https://www.macrumors.com/2025/03/07/apple-intelligence-siri-features-delayed/, https://appleinsider.com/articles/26/02/16/apples-upgraded-siri-is-late-but-not-lost----the-real-story-is-timing); shipping status as of 2026-11: unverified. Lesson: app-declared semantic actions (Ya-Bro analogue: D-Bus interfaces, KDE's KXMLGUI action collections, MCP servers in packs) are more reliable than UI driving, but depend on app cooperation.
- **Raycast Screen Awareness** (https://manual.raycast.com/ai/screen-awareness.md): needs Screen Recording for window screenshots and Accessibility to read the focused app's content, an example of the combined a11y + pixel approach.
- **OpenAI Codex "Chronicle"** (reported 2026-04, https://thenextweb.com/news/openai-codex-chronicle-screen-context-mac): periodically captures the screen, summarizes it into local text memory files, but sends screenshots to OpenAI for processing (per TNW; unverified detail). Another recorder-style design with the same privacy trade-off as Recall.

---

## 3. Patterns and lessons

### 3.1 Perception approaches compared

| Approach | Who uses it | Accuracy | Latency / cost | Fails on | Ya-Bro role |
|---|---|---|---|---|---|
| OS accessibility tree (UIA / AX / AT-SPI) | Navisual (primary), ChatGPT Work with Apps, screenpipe (text), Raycast | Exact element names, roles, states and boxes when the app exposes them | Navisual: UIA lookup under 5 ms; zero tokens | Custom-drawn UIs (Blender, games, canvas), some Electron/Chromium apps without a11y enabled, icon-only buttons with no name | **Primary**: build a numbered list of on-screen interactive elements for the LLM to *select* from |
| App object model / plugin | Navisual (Excel/Office COM, Blender add-on), Agent S (LibreOffice UNO), Apple App Intents | Exact, semantic | Fast | Needs per-app work and cooperation | **Pack-provided** adapters (D-Bus, UNO, Blender Python add-on, MCP servers) |
| OCR on a crop | Navisual (fallback, 10 to 50 ms), Agent S (Tesseract text spans), Open Interpreter (click by text), screenpipe (fallback) | Good for text labels; fuzzy matching needed | Tens of ms locally | Icons, low contrast, RTL/Arabic shaping (Tesseract Arabic quality needs testing) | **Second** pass, model-free |
| Icon detection / set-of-marks | OmniParser, Ourguide (custom detector), Navisual icon templates | Medium; boosts general LLMs (GPT-4o 0.8 to 39.6 on ScreenSpot-Pro with OmniParser V2) | GPU model; ~sub-second (Ourguide's earlier detector+VLM path was "too slow" per author) | New icon styles | **Optional** local fallback; pack icon templates for known apps |
| Specialist grounding VLM | Agent S (UI-TARS-1.5-7B), UI-TARS | 61.6 (UI-TARS-1.5) to 85 (best cascades) on ScreenSpot-Pro | Extra model round trip per action; local GPU or hosted endpoint | Icon-dense pro apps (icon scores 20 to 40 pts below text) | **Third** pass when a11y and OCR miss |
| General VLM pixels | Clicky (`[POINT:x,y]`), Skilly, Copilot Vision (likely), Claude/OpenAI CUA | Weakest on dense high-res UIs unless the model has computer-use training; sensitive to resize/aspect ratio | ~1,000 to 1,800 input tokens per Claude screenshot | Small targets, multi-monitor, HiDPI scaling bugs | **Last resort**, using Claude computer-use scaling recipe and crop-to-window |

**Rule distilled from Navisual, Agent S, OmniParser and browser-use:** let the LLM *describe or select* the target; resolve coordinates locally with the cheapest exact method first. Record which pass resolved each target (Navisual's debug trace) so failures are diagnosable.

### 3.2 Overlay patterns

- **Full-screen transparent click-through layer, always on top, on every workspace**: Clicky (`NSPanel`, `.screenSaver` level, `ignoresMouseEvents`, `.canJoinAllSpaces`), Navisual (Tauri transparent always-on-top canvas), Ourguide (Electron). Never steals focus.
- **Exclude own windows from capture** (Navisual blanks panel/overlay rects before sending), otherwise the model sees and reasons about its own pointer.
- **Pointer + caption + voice**: Navisual shows a caption strip plus TTS; Clicky a cursor buddy with a text bubble; Copilot Highlights marks the click target inside the shared window. One target per step.
- **Animated travel** to the target (Clicky/Skilly quadratic Bezier arc) makes the pointer easy to follow and is the most memorable part of those demos.
- **Advance model**: explicit "next" hotkey, "wrong" hotkey, or auto-advance on screen change (Navisual Autopilot via 8x8 aHash; Ya-Bro can use AT-SPI focus/state-changed events instead of image hashing).
- **Visible, honest presence**: Cluely's "invisible" overlay is the anti-pattern; Copilot Vision's explicit share-a-window with a Stop button is the pattern.
- Linux specifics (X11 keep-above/sticky hints, input-shape regions, Wayland layer-shell, per-monitor scaling) are not solved by any surveyed tool; none of the guiders ships on Linux today (Navisual lists Linux as "v1.x").

### 3.3 Latency figures collected

| Item | Figure | Source |
|---|---|---|
| UIA element lookup | under 5 ms | Navisual ARCHITECTURE.md |
| Windows OCR fallback | ~10 to 50 ms | Navisual ARCHITECTURE.md |
| Screen-change detection (events + aHash) | under 500 ms | Navisual ARCHITECTURE.md |
| Ourguide next step (simplified pipeline) | under 1 s | author on HN (unverified) |
| Copilot logistic-regression filter | ~0.2 ms; transformer filter ~21 ms median | arXiv 2405.14753 |
| JetBrains trigger model | avoids ~20% of inference calls | arXiv 2601.20223 |
| Claude screenshot cost | ~1,000 to 1,800 input tokens each; keep under ~20 images/request | Claude computer-use docs |
| Image-token reduction from active-window crop | ~80% vs full desktop | Navisual ARCHITECTURE.md |
| Realtime voice cost (Skilly BYOK) | ~$0.06 to 0.10 per minute | Skilly README |
| Agent S3 grounding | one extra grounding-model call per click/type/scroll | `grounding.py` |
| Cursor Tab RL checkpoint cadence | 1.5 to 2 h | Cursor blog |

### 3.4 Proactive / interruption lessons

1. **Struggle signals are old and well-defined.** Lumière (1998) already listed menu search loops, pause-after-activity, undo/close-dialog "undesired effects" and inefficient sequences. Ya-Bro's planned signals map one-to-one; add failing shell commands as a modern "undesired effect".
2. **Gate in stages with a cheap local model first.** Copilot (logistic regression, 15% threshold), JetBrains (CatBoost trigger, ~20% calls avoided) and Cursor (show only at an estimated acceptance of 25% or more) all decide *whether to speak* before or without the big model. Ya-Bro: local scorer on AT-SPI/event telemetry, then Claude for wording.
3. **Fewer, better offers win.** Cursor: 21% fewer suggestions, 28% higher accept rate. "Need Help?": only half of users preferred the high-frequency assistant. Microsoft shelved OS-wide Copilot suggestions in 2026.
4. **Wrong help is worse than no help**, because users follow it and it looks like success (Lumière Wizard-of-Oz). Phrase offers conditionally and make "no" cheap.
5. **Back off visibly.** Lumière: time out with an apology, never re-offer until the topic changes; user-set threshold ("volume"). Clippy ignored this and became the cautionary tale. Ya-Bro's humor goes in the *offer*, never in an extra interruption.
6. **Allow silence.** Gemini Live's "proactive audio" lets the model decide not to respond; Ya-Bro's voice loop should too.
7. **Learn per user.** Treat dismiss/ignore as negative labels (Copilot telemetry, Cursor RL, ProactiveBench reward model). Even a simple per-user threshold adaptation beats fixed rules.

### 3.5 Privacy and security lessons

1. **No default timeline.** Recall's plaintext SQLite and default-on plan caused a recall of Recall; the fix was opt-in, enclave storage and Windows Hello gating. Ya-Bro keeps context in memory, per request.
2. **Send less.** Active-window crop (Navisual), a11y text instead of pixels (ChatGPT Work with Apps), terminal last-N lines, password fields reported as "(password field)", explicit consent for full-screen capture.
3. **Show what is shared.** Connected-apps banner (ChatGPT), share-a-window with Stop (Copilot Vision), pause hotkey (Navisual).
4. **Local option.** Navisual supports Ollama/OpenAI-compatible local servers; Click to Do runs Phi Silica on device. Ya-Bro should keep a local-model path for perception and triage even if Claude does the talking.
5. **Treat screen content as hostile input.** Comet and Claude for Chrome numbers show prompt injection through page text and screenshots is real (23.6% to 11.2% to 1.4% attack success across Anthropic's evaluations). Never let on-screen text authorize actions; confirm destructive steps.
6. **Privilege separation.** Cluely's unfiltered IPC bridge plus navigable renderer let a link take screenshots and record audio. Ya-Bro: privileged perception/input daemon with a narrow, whitelisted API; UI process never renders untrusted links with privileges.
7. **Verifiable claims.** HN readers rejected Ourguide's unverifiable privacy claims; open source plus a "what was sent" log is Ya-Bro's advantage.
8. **Durability.** Rewind's capture was switched off after the Meta acquisition; user data under user control is the only stable promise.

### 3.6 Knowledge-source patterns

- **Per-app skill files** (Skilly `SKILL.md`: front-matter with app id, plus expertise, common mistakes, curriculum stages) are the closest prior art to Ya-Bro packs. Adding Ya-Bro-specific fields (AT-SPI role/name aliases, icon templates, D-Bus/MCP actions, struggle hints) is a natural extension.
- **Live web search** for current versions (Ourguide) and **official-manual-sourced** content (Skilly's Blender skill cites the Blender 5.1 manual) counter UI drift between app versions.
- **Recorded demonstrations compiled to programs** (OpenAdapt) are a path for packs to include verified "recipes".

---

## 4. Sources

Primary repositories and source files (read 2026-11-20 via `gh api`):
- https://github.com/farzaa/clicky (README.md, AGENTS.md, leanring-buddy/OverlayWindow.swift, CompanionManager.swift, ElementLocationDetector.swift, CompanionScreenCaptureUtility.swift)
- https://github.com/tryskilly/skilly (README.md, leanring-buddy/skills/blender-fundamentals/SKILL.md)
- https://github.com/NavisualGuide/navisual (README.md, ARCHITECTURE.md)
- https://github.com/simular-ai/Agent-S (README.md, gui_agents/s3/README.md, gui_agents/s3/agents/grounding.py)
- https://github.com/bytedance/UI-TARS and https://github.com/bytedance/UI-TARS-desktop (READMEs)
- https://github.com/anthropics/claude-quickstarts/tree/main/computer-use-demo (README.md, computer_use_demo/tools/computer.py)
- https://github.com/OpenAdaptAI/OpenAdapt ; https://github.com/OthersideAI/self-operating-computer ; https://github.com/bytebot-ai/bytebot ; https://github.com/trycua/cua ; https://github.com/browser-use/browser-use ; https://github.com/Skyvern-AI/skyvern ; https://github.com/openinterpreter/open-interpreter ; https://github.com/mediar-ai/screenpipe ; https://github.com/microsoft/OmniParser
- https://github.com/GUI-Agent/grounding-leaderboard (results/screenspot_pro.json, last commit 2026-11-10)

Docs, papers and posts:
- Claude computer use tool docs: https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool
- Agent S papers: https://arxiv.org/abs/2410.08164 , https://arxiv.org/abs/2504.00906 , https://arxiv.org/abs/2510.02250 , https://arxiv.org/abs/2610.28601
- UI-TARS: https://arxiv.org/abs/2501.12326 ; UI-TARS-2: https://arxiv.org/abs/2509.02544
- ScreenSpot-Pro: https://arxiv.org/abs/2504.07981 ; leaderboard https://gui-agent.github.io/grounding-leaderboard/
- OmniParser V2 blog: https://www.microsoft.com/en-us/research/articles/omniparser-v2-turning-any-llm-into-a-computer-use-agent/
- Qwen3-VL report: https://arxiv.org/abs/2511.21631
- OSWorld: https://os-world.github.io/ (redirects to http://osworld-v1.xlang.ai/) ; aggregator https://presenc.ai/research/osworld-computer-use-leaderboard-2026
- Online-Mind2Web "Illusion of Progress": https://arxiv.org/abs/2504.01382
- OpenAI: https://openai.com/index/computer-using-agent/ ; https://openai.com/index/introducing-chatgpt-agent/ ; https://deploymentsafety.openai.com/chatgpt-agent ; https://help.openai.com/en/articles/10119604-work-with-apps-on-macos ; https://techcrunch.com/2024/11/14/chatgpt-can-now-read-some-of-your-macs-desktop-apps/
- Copilot Vision: https://blogs.windows.com/windows-insider/2025/05/12/copilot-on-windows-windows-insiders-can-now-use-vision-with-2-apps-and-new-highlights-feature-with-1-app/ ; https://blogs.windows.com/windowsexperience/2025/06/12/copilot-vision-on-windows-with-highlights-now-available-in-us/
- Ourguide: https://hn.svelte.dev/item/46769422 ; https://www.producthunt.com/products/ourguide/launches
- Open Interpreter OS mode: https://docs.openinterpreter.com/guides/os-mode ; https://docs.openinterpreter.com/code-execution/computer-api
- Recall: https://www.windowscentral.com/software-apps/windows-11/microsoft-should-recall-windows-recall-security-researcher-finds-microsofts-new-ai-tool-woefully-insecure ; https://www.techspot.com/news/103258-researcher-microsoft-windows-recall-has-security-gaps-you.html ; https://blogs.windows.com/windowsexperience/2024/09/27/update-on-recall-security-and-privacy-architecture/ ; https://www.pcworld.com/article/2470708/microsoft-now-confirms-you-can-opt-out-of-and-remove-windows-recall.html
- Click to Do: https://support.microsoft.com/windows/click-to-do-do-more-with-what-s-on-your-screen-6848b7d5-7fb0-4c43-b08a-443d6d3f5955 ; https://learn.microsoft.com/en-us/windows/apps/develop/windows-integration/click-to-do
- screenpipe: https://docs.screenpi.pe/architecture ; https://mintlify.com/screenpipe/screenpipe/architecture
- Rewind/Limitless: https://9to5mac.com/2025/12/05/rewind-limitless-meta-acquisition/ ; https://www.techcrunch.com/2025/12/05/meta-acquires-ai-device-startup-limitless/
- Highlight AI: https://highlightai.com/product ; https://techcrunch.com/?p=2902919
- Cluely: https://www.hacktron.ai/blog/hacking-cluely ; https://www.fast.io/resources/cluely-ai-review-2026.md
- Lumière / Clippy: https://arxiv.org/abs/1301.7385 ; https://www.erichorvitz.com/lum.htm ; https://erichorvitz.com/chi99horvitz.pdf ; https://en.wikipedia.org/wiki/Office_Assistant ; https://www.theregister.com/2023/06/12/clippy_designer_embarrassed
- Copilot internals: https://thakkarparth007.github.io/copilot-explorer/posts/copilot-internals ; https://github.blog/2023-05-17-how-github-copilot-is-getting-better-at-understanding-your-code/ ; https://arxiv.org/abs/2405.14753
- JetBrains control models: https://www.alphaxiv.org/abs/2601.20223.md
- Cursor Tab RL: https://cursor.com/blog/tab-rl
- Proactive Agent: https://arxiv.org/abs/2410.12361 ; https://github.com/thunlp/ProactiveAgent
- Need Help?: https://arxiv.org/abs/2410.04596 ; Assistance or Disruption?: doi 10.1145/3706598.3713357
- Carter and Dewan: https://www.springerprofessional.de/doi/10.1145/1880071.1880109
- Microsoft proactive Copilot: https://www.windowscentral.com/microsoft/windows-11/microsoft-quietly-scraps-plans-to-bring-copilot-to-notifications-and-settings-on-windows-11-as-it-moves-to-reduce-ai-bloat-across-the-os ; https://thejournal.com/articles/2026/03/30/microsoft-scales-back-copilot-integrations-in-windows-11.aspx ; https://venturebeat.com/ai/microsoft-copilot-gets-12-big-updates-for-fall-including-new-ai-assistant
- Google: https://deepmind.google/models/project-astra/ ; https://techcrunch.com/2025/05/20/project-astra-comes-to-google-search-gemini-and-developers ; https://docs.cloud.google.com/vertex-ai/generative-ai/docs/live-api ; https://blog.google/products/pixel/google-pixel-magic-cue-ai-feature/ ; https://support.google.com/pixelphone/answer/16508057
- Claude for Chrome: https://www.anthropic.com/news/claude-for-chrome ; https://www.anthropic.com/research/prompt-injection-defenses
- Comet: https://brave.com/blog/comet-prompt-injection/ ; https://brave.com/blog/unseeable-prompt-injections/ ; https://www.akamai.com/blog/security/2025/oct/cometjacking-how-one-click-can-turn-perplexitys-comet-ai-browser-against-you
- Manus: https://www.theregister.com/2025/12/30/meta_acquires_manus/ ; https://e2b.dev/blog/how-manus-uses-e2b-to-provide-agents-with-virtual-computers
- Apple: https://www.macrumors.com/2025/03/07/apple-intelligence-siri-features-delayed/ ; https://appleinsider.com/articles/26/02/16/apples-upgraded-siri-is-late-but-not-lost----the-real-story-is-timing
- Raycast: https://manual.raycast.com/ai/screen-awareness.md ; Codex Chronicle: https://thenextweb.com/news/openai-codex-chronicle-screen-context-mac

### Claims not verified from a primary source
- Copilot Vision Highlights internals (a11y vs vision); Ourguide's current pipeline, TEE/PII-filter claims and <1 s latency; Highlight AI's capture mechanism.
- OpenAI CUA's launch OSWorld 38.1%; ChatGPT agent's OSWorld score.
- Whether Open Interpreter's OS mode survives in the 2026 codebase; browser-use's current observation format beyond the README; Skyvern and cua internals.
- Copilot debounce interval and in-flight cancellation behaviour; Carter and Dewan feature set and accuracy.
- Cluely's 83k-user breach and its overlay-hiding mechanism; Recall's automatic sensitive-content filtering scope.
- Secondary-aggregator OSWorld-Verified/2.0 top scores (90.19%, ~86%, ~44%) and frontier ScreenSpot-Pro claims (e.g., Gemini 3 Pro 72.7); Qwen3-VL column mapping.
- Apple onscreen-awareness shipping status as of 2026-11; Microsoft's October 2026 Copilot+ agent rollout details.
