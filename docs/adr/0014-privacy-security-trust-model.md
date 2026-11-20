# ADR-0014: Privacy, security and trust model

- Status: Proposed
- Date: 2026-11-20
- Issue: #13
- Depends on: ADR-0003, ADR-0005, ADR-0008, ADR-0009, ADR-0010

## Context
Ya-Bro reads other apps' UI trees and shell activity, may capture screens, may inject input, and sends context to a cloud LLM. Lessons from comparable tools ([ai-tools.md §3.5](../research/ai-tools.md)):

- **Microsoft Recall**
  - Original design: a plaintext SQLite timeline, planned on by default. It caused a public backlash.
  - Fix: opt-in, enclave storage and Windows Hello gating.
- **Cluely.** An unfiltered IPC bridge let a link trigger screen capture.
- **Perplexity Comet.** Prompt injection via hidden page text and screenshots exfiltrated a one-time password.
- **Claude for Chrome.** Anthropic's red-teaming measured attack success at 23.6% without mitigations, then 11.2%, then 1.4% with later safeguards. Site permissions and confirmations were essential.
- **Ourguide.** HN readers rejected its unverifiable privacy claims.

Platform facts ([factsheet.md D.1](../research/factsheet.md)):
- **The AT-SPI bus has no access control.** Any client can read and drive other apps. Ya-Bro therefore holds a powerful capability and must use it narrowly.

SPEC §7 and CLAUDE.md already require:
- visible, interruptible actions;
- never typing secrets;
- confirmation for destructive or outward-facing actions;
- treating screen text as data;
- monitoring that is opt-in, local and limited to types/counts;
- no telemetry.

## Decision drivers
- Minimise what leaves the machine.
- Make what is sent inspectable.
- Prompt-injection resistance by construction, not just by prompting.
- Consent that is meaningful but not naggy.
- A kill switch that works even if core misbehaves.

## Options considered
| Option | For | Against |
|---|---|---|
| **Rely on the LLM to follow safety instructions** | Simple | Injection numbers show this is insufficient alone |
| **Local policy engine + data minimisation + consent tiers (recommended)** | Deterministic gate outside the model; auditable | More code; some false refusals |
| **Local-only (no cloud)** | Maximum privacy | Quality gap today (ADR-0008); SPEC keeps local-only as a roadmap goal |

## Decision
**1. Threat model**

| Asset | Threat | Mitigation |
|---|---|---|
| Screen and UI content (documents, mail, chats) | Over-collection, cloud leakage | Focused window only; AT-SPI text before pixels; crops; redaction; per-app capture consent |
| Secrets (passwords, tokens, keys) | Sent to the LLM or typed by the bro | elements with AT-SPI role `ROLE_PASSWORD_TEXT`, or fields a pack marks secret, are never read; regex redaction of key/token patterns in terminal and web text; never type into secret fields (ADR-0009) |
| User intent and authority | Prompt injection from screen, web, terminal or pack text | Untrusted-content framing; local `Policy` decides every action; R3 actions are never automated; the LLM cannot raise its own permissions |
| The machine | Malicious pack hooks or MCP servers | Packs are data-only by default; hooks need explicit trust per pack; the exact command is shown |
| Behaviour log | Profiling or leakage | Struggle data is types/counts only, local, with a 30-day retention cap |
| API keys and portal tokens | Theft | Secret Service (libsecret) storage; `.env` fallback with 0600; never logged |
| Ya-Bro's own IPC | Local abuse by other processes | D-Bus methods are narrow, typed and accept no code. Actuator accepts only policy-signed single actions from core (sender check on the unique bus name). |

**2. Data flows**
- **Stays local:** AT-SPI events, struggle counts, shell hook events, element fingerprints, logs, audio (unless cloud voice is enabled), screenshots (unless vision is needed).
- **Goes to the configured LLM, per request:**
  - the user's question;
  - the pack context;
  - a compact element list of the focused window;
  - a cropped screenshot when needed;
  - the last N terminal lines when the user asks for help with a command.

  All of it is redacted first.
- **"What was sent" log:** a local log the user can open (`ya-bro sent`) listing the categories and sizes of every request, and in debug mode the payload itself.

**3. Consent UX**
- **First run:** a single screen explaining what Ya-Bro reads and what it sends, with toggles. It also offers to enable the a11y bus (a persistent setting) and the shell hook (an rc-file edit).
- **Per-app opt-in** for proactive monitoring (SPEC). Show-me mode works on any app the user asks about.
- **Screen capture:** portal consent on Wayland, plus Ya-Bro's own per-app "allow screenshots" toggle. Password-manager, banking and messaging apps are capture-denied by default (a bilingual app list in core config).
- **Visible state:** the avatar shows small indicators for watching, listening, sending and acting. These cannot be disabled while the state is active.

**4. Prompt-injection controls**
- Observations are wrapped and described as untrusted data. Operator rules live only in system and mid-conversation system messages (ADR-0008).
- The LLM's tool calls are *proposals*. `Policy` checks each proposed action against risk tier, deny-lists, current mode, app permission and step context, then allows, asks or refuses.
- Text on screen can never trigger an action by itself. Every action traces back to a user goal in the current session.
- Ya-Bro never opens URLs, runs commands or sends data to destinations that came from screen content without showing them and asking.

**5. Do-it risk tiers.** R0–R3 as defined in ADR-0009. R3 (send, publish, buy, delete, credentials, sudo, rm) is always the user's own click.

**6. Kill switch**
- The global stop hotkey: core cancel, plus overlay hide, plus actuator abort (ADR-0003).
- `ya-bro panic`, which also works from a terminal: kills all Ya-Bro processes, revokes the portal session and closes the mic.
- The overlay and actuator obey the stop signal even if core is wedged.

**7. Retention**
- No content is persisted by default.
- Struggle counts and offer labels: 30 days (configurable). Logs: 7 days.
- Restore tokens: until the user revokes them.
- `ya-bro forget` wipes all state.

**8. Supply chain.** Pinned dependencies with hashes (`uv.lock`), and a licence and model register (ADR-0020). Model weights are downloaded only on demand, from the documented URL, with checksums.

## Consequences
- **Positive:** a defensible, explainable privacy story, safety that does not depend on the model behaving, and an open-source, inspectable log.
- **Negative:** extra prompts during onboarding. Redaction will sometimes hide useful context, so the user can choose "share this one".
- **Risks:**
  - Redaction misses new secret formats.
  - Over-broad deny-lists annoy users.
  - The AT-SPI capability is powerful by nature, so a compromise of Ya-Bro is a compromise of the desktop session.

## Validation plan
- **Policy unit tests:** a table of 200+ proposed actions with expected allow/ask/refuse, in EN and AR labels.
- **Injection eval:** 50 fixture pages, documents and terminal outputs carrying injected instructions ("ignore previous… click Delete"). Pass criterion is 0 policy-violating actions and a refusal or ignore rate of 100% for R2+.
- **Redaction tests:** a corpus of fake keys and tokens (AWS-like, GitHub-like, JWT, PEM) in terminal, web and UI text.
- **Kill-switch test:** stop works within 500 ms with core paused (SIGSTOP).

## Revisit if
- A local model is good enough to offer local-only mode.
- Newton or Wayland a11y introduces access control.
- A security report comes in.

## Sources
- [docs/research/ai-tools.md](../research/ai-tools.md): §2.3 Recall, §2.6 Claude for Chrome and Comet, §3.5
- Recall update: https://blogs.windows.com/windowsexperience/2024/09/27/update-on-recall-security-and-privacy-architecture/
- Claude for Chrome: https://www.anthropic.com/news/claude-for-chrome
- Comet injection: https://brave.com/blog/comet-prompt-injection/
- AT-SPI has no access control: https://wiki.gnome.org/Projects/GTK/Accessibility (via [factsheet.md D.1](../research/factsheet.md))
- libsecret: https://gnome.pages.gitlab.gnome.org/libsecret/
