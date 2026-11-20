# ADR-0009: Actuation (Do-it mode)

- Status: Proposed
- Date: 2026-11-20
- Issue: #13
- Depends on: ADR-0002, ADR-0003, ADR-0007, ADR-0014
- Target release: v0.15 (SPEC), after Show-me mode is proven

## Context
In Do-it mode the bro performs one step while the user watches. Every action must be paced, narrated, visible and interruptible. Available mechanisms ([linux-platform.md V5, §1](../research/linux-platform.md); [non-ai-tools.md §4](../research/non-ai-tools.md)):

| Mechanism | Sessions | Notes |
|---|---|---|
| **AT-SPI `Action.do_action`, `EditableText.set_text_contents/insert_text`, `Selection`, `Value`** | Any session where the app exposes AT-SPI | Semantic. No pointer injection, no portal consent. Does not move the real cursor. |
| **XTest** | X11 | Works silently. Under XWayland it reaches only X11 clients. |
| **RemoteDesktop portal + `ConnectToEIS` (libei, MIT)** | GNOME (x-d-p-gnome ≥ 45), KDE (x-d-p-kde ≥ 6.1) | Consent dialog. Absolute motion needs a combined ScreenCast session (`mapping_id`). Restore tokens are single-use and flaky on KDE (bug 490988). Whether the visible cursor moves is unverified. |
| **`org_kde_kwin_fake_input`** | KWin | Open to unsandboxed clients from Plasma 6.8 (MR 6057). Restricted via `.desktop` `X-KDE-Wayland-Interfaces` on ≤ 6.7, which includes the maintainer's Ubuntu 6.6. |
| **wlr virtual-pointer / virtual-keyboard** | Sway, Hyprland | No consent needed |
| **uinput (ydotool AGPL / dotool)** | Anywhere | Root or a udev group. Bypasses compositor policy. Drops characters missing from the active keyboard layout, which matters for Arabic. |

**Lessons from computer-use agents and agentic browsers** ([ai-tools.md §2.2, §2.6](../research/ai-tools.md)):
- Long autonomous runs are unreliable. OSWorld 2.0 full-completion is about 44%, unverified.
- Prompt injection through screen content is real: 23.6% → 11.2% → 1.4% attack success across Anthropic's Claude for Chrome evaluations.
- Confirmations for publish, purchase and share are table stakes.

## Decision drivers
- Safety and user trust above speed.
- Visibility: the user must *see* what the bro does ("watch me").
- Stop within 500 ms.
- Minimal consent friction.
- Arabic text entry must work.

## Options considered
| Option | For | Against |
|---|---|---|
| **Pointer/keyboard injection only (computer-use style)** | Universal | Needs consent or root on Wayland. Fragile coordinates. Arabic layout problems. |
| **AT-SPI actions first, injection fallback, with a visual "ghost cursor" (recommended)** | Exact target, no consent, layout-independent text. A ghost cursor animation keeps the action visible even though the real cursor doesn't move. | Not every widget has actions (canvas, drag gestures). Some apps ignore `set_text_contents` events. |
| **App-native APIs only (MCP, D-Bus, UNO)** | Most reliable | Needs per-app packs; not "on the live UI" |

## Decision
1. **Backend order per action.** Each backend is an `Actuator` implementation chosen at runtime:
   1. **pack-native action**, if the pack declares one for this intent and the user enabled it. Examples: a workbench MCP tool, a D-Bus method.
   2. **AT-SPI semantic action**: `do_action("click"|"press"|"activate")`, `EditableText` insertion, `Selection.select_child`, `Value.set_current_value`.
   3. **Session injection**:

      | Session | Injector |
      |---|---|
      | X11 | XTest via python-xlib |
      | KWin ≥ 6.8 (unsandboxed) | fake-input |
      | KWin ≤ 6.7 / GNOME | RemoteDesktop portal + libei |
      | wlroots | virtual pointer/keyboard |

   4. **uinput is not shipped.** It is documented as an external, opt-in power-user path only.
2. **Visibility ("watch me").**
   - Every action is preceded by narration, then the overlay's pointer flying to the target (ADR-0006), then a 300 ms "press" animation, then the action.
   - With semantic actions the ghost cursor *is* the visible cursor.
   - With injection the real pointer moves too. If portal absolute motion turns out not to move the visible cursor (open question, spike S7), the ghost cursor still shows it.
3. **Pacing.**
   - Default 800–1500 ms per action, stretched by narration length.
   - The user can choose "slow / normal / brisk".
   - Typing is shown at a readable speed, or as a paste with a visible preview.
4. **Text entry.**
   - Prefer `EditableText` or the clipboard (with an explicit, visible "pasting…") over key synthesis, especially for Arabic and other non-layout characters.
   - Never type into fields with role `password text` or with a pack-declared secret flag.
5. **Risk tiers and confirmation.** The local `Policy` engine applies these; the LLM only proposes ([ADR-0014](0014-privacy-security-trust-model.md)).

   | Tier | Examples | Policy |
   |---|---|---|
   | R0 | focus, scroll, open a menu, hover | Act |
   | R1 | toggles, typing into a non-sensitive field, opening dialogs | Act, with narration |
   | R2 | save or overwrite, apply settings, run a shell command | Confirm in this step: "I'll click Apply, ok?" |
   | R3 | send, publish, buy, delete, payment, credential entry, `sudo`, `rm` | Show-me only. The bro points and the user clicks. Even an explicit "do it" switches to Show-me for that step. |

   The tier is the max of: planner-proposed tier, a pack-declared tier for that element, and local heuristics. Heuristics are role and name matches against a bilingual deny-list (`delete|remove|send|publish|buy|pay|حذف|إرسال|نشر|شراء|دفع…`) and terminal commands matching a destructive pattern list.
6. **Abort and undo.**
   - Stop cancels the current action before the next injected event; each event checks a cancellation token.
   - Generic undo is not promised. Where the app offers Undo (AT-SPI menu item or pack hint), the bro offers "want me to undo that?".
   - Because there is no universal undo, irreversible actions are R3.
7. **Consent lifecycle.**
   - The portal session is requested only on the first Do-it step, with an explanation in the bubble first.
   - The restore token is stored in the Secret Service (ADR-0014) and refreshed after every Start.
   - If restore fails, the bro falls back to Show-me mode and does not prompt again in the same session.
8. **Verification after acting.** Same predicates as Show-me (ADR-0005). After two failed attempts the bro stops acting, says so, and switches to Show-me.

## Consequences
- **Positive:**
  - Do-it mode works on Wayland without any consent for most AT-SPI-exposed widgets.
  - Arabic text entry is safe.
  - Risky actions are always the user's own click.
- **Negative:**
  - Drag gestures and canvas painting need injection, so they need consent.
  - The ghost cursor differs from the real cursor position. This is explained in onboarding.
- **Risks:**
  - Apps that ignore AT-SPI actions (they claim to handle them but don't).
  - Portal persistence bugs.
  - KWin 6.6 vs 6.8 differences.

## Validation plan
Spike **S7** (v0.15):
- 30 actions across GIMP, LibreOffice, KDE Settings and Firefox, run via AT-SPI actions, recording success and visible effect.
- Portal + libei session on KWin 6.6 and GNOME 50:
  - consent friction (number of dialogs per session);
  - whether absolute motion moves the visible cursor;
  - stop latency (target ≤ 200 ms p95 to last event).
- **Go:** ≥ 85% of R0–R1 actions succeed via AT-SPI or injection, and zero R3 actions were ever injected (asserted by policy unit tests and the eval).

## Revisit if
- Wayland gains a standard, consent-free "assistive input" protocol.
- AT-SPI action coverage proves too low.
- Users want unattended macros. That is a SPEC non-goal, so the SPEC would change first.

## Sources
- [docs/research/linux-platform.md](../research/linux-platform.md): V5, §1 matrix
- [docs/research/non-ai-tools.md](../research/non-ai-tools.md): §4 input tools, §13 takeaway 6
- [docs/research/ai-tools.md](../research/ai-tools.md): §2.2 doers, §2.6 Claude for Chrome / Comet
- RemoteDesktop portal: https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html
- libei: https://gitlab.freedesktop.org/libinput/libei
- KWin MR 6057: https://invent.kde.org/plasma/kwin/-/merge_requests/6057
- AT-SPI Action interface: https://docs.gtk.org/atspi2/iface.Action.html
