# Prior art (survey: Nov 2026)

Produced by an Opus research agent via web search. Some claims are from memory or self-reported by vendors; **re-verify before citing publicly**.

## Verdict
The core concept (AI sees your screen and points at the next click) **already exists on macOS and Windows**. We found nothing that is **Linux-native**, **open source**, and does a **paced teach-or-do hybrid**. The opening is platform and execution, not a new concept.

Products split in two camps: *guiders* point but never act; *doers* act but never teach.

## Comparison
| Product | Teaches on live app | Acts for you, paced | Voice+text | Linux | Open source |
|---|---|---|---|---|---|
| Microsoft Copilot Vision "Highlights" | Yes | No | Yes | No (Windows) | No |
| Clicky (farzaa/clicky) | Yes | No | Voice | No (macOS) | Yes |
| Skilly (Clicky fork) | Yes ("Live Tutor") | No | Voice | No (macOS) | Yes |
| Ourguide | Yes, whole-OS overlay | No (by design) | Unclear | No (macOS) | No (planned) |
| Navisual | Yes | No | Unclear | No (Windows) | Source-available |
| Whatfix Desktop / WalkMe | Yes, pre-authored flows | Limited | Text | No | No |
| Pendo / Appcues / Userflow | Own web app only | No | No | Web | No |
| Gemini Live screen share | Talks, doesn't point | No | Yes | Browser | No |
| Agent S (Simular) | No | Yes, autonomous | Text | Yes | Yes |
| UI-TARS Desktop | No | Autonomous | Text | Unclear | Yes |
| Claude computer use | No | Autonomous | Text | Reference impl. in Linux container | API only |
| Open Interpreter OS mode, OpenAdapt | No | Autonomous / replay | Some | Partial | Yes |

## Where Ya-Bro differs
1. **Linux-native**: every guider found is Mac/Windows only.
2. **Per-step teach-or-do with verification**: show a step, optionally do it, then check the user (or bro) did it before moving on.
3. **Accessibility tree first (AT-SPI), vision second**: exact bounds and names, cheap, fast; most competitors are vision-only.
4. **Open source, local-model friendly.**
5. Docs/MCP/skills as extra knowledge: weak differentiator (others will add it).

## Top technical risks (Linux)
1. **Overlay on Wayland**: GNOME/Mutter has no `wlr-layer-shell` and no always-on-top API. KDE, Sway, Hyprland do. GNOME needs a Shell extension or a fallback. X11 is easy.
2. **Input injection on Wayland**: RemoteDesktop portal + libei (GNOME 46+, Plasma 6). Per-session consent prompt; `persist_mode` issues on GNOME 46–50; absolute pointer moves may not visibly move the cursor on GNOME 50 (hurts "watch me").
3. **Screen capture**: Portal ScreenCast + PipeWire, needs consent; capture on demand only.
4. **AT-SPI coverage**: GTK good, Qt decent, Electron/Chromium needs `--force-renderer-accessibility` (or `ACCESSIBILITY_ENABLED=1`), Flatpak adds friction, canvas/games expose nothing → vision fallback required.
5. **Grounding accuracy and latency**: wrong highlight destroys trust in teaching mode; vision round-trips are 2–6 s.
6. **Voice**: offline whisper.cpp/faster-whisper + Piper is workable; cloud realtime feels better but costs money and has privacy tradeoffs.

## Recommended wedge (adopted in SPEC.md)
- **KDE Plasma and X11 first**; GNOME via Shell extension later.
- **Show-me mode with automatic step verification first**; Do-it mode (portal + libei) next.
- Text first, push-to-talk whisper.cpp after.
- Prove on 3–5 accessible apps (GIMP, Inkscape, LibreOffice, system settings, VS Code with accessibility flag). Not Electron/general vision first.

## Sources
- Copilot Highlights: https://blogs.windows.com/windowsexperience/2025/06/12/copilot-vision-on-windows-with-highlights-now-available-in-us/
- Clicky: https://github.com/farzaa/clicky · Skilly: https://github.com/tryskilly/skilly
- Ourguide: https://hn.svelte.dev/item/46769422
- Navisual: https://awesome.ecosyste.ms/projects/github.com%2Fnavisualguide%2Fnavisual
- Whatfix Desktop: https://whatfix.com/products/desktop/
- Agent S: https://github.com/simular-ai/Agent-S · UI-TARS: https://github.com/bytedance/UI-TARS-desktop
- GNOME overlay limits: https://discourse.gnome.org/t/any-way-to-set-window-always-on-top-programmatically/31579 · koverlay: https://github.com/erik96/koverlay
- libei/portal injection: https://github.com/cushycush/wdotool
- Chromium AT-SPI: https://github.com/microsoft/vscode/issues/84833
