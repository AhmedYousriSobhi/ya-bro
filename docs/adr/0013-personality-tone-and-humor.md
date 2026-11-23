# ADR-0013: Personality, tone and humour system

- Status: Proposed (persona module, lines, filter and controls implemented in #23; see "Implemented")
- Date: 2026-11-20
- Issue: #13
- Depends on: ADR-0008, ADR-0010, ADR-0019

## Context
The product is a "bro". It offers help "with humour", and when told "no" it says "I don't think so, but I'm here". Personality is part of the brand, but research shows it is also a liability.

- **Clippy.** Users reacted to the Office Assistant socially. Labels, appearance and behaviour shaped whether it was perceived as helpful or annoying (Swartz 2003, via secondary summaries). Being impolite (Whitworth 2005) got it disabled.
- **Whitworth's polite-computing rules:** respect user choice, disclose identity, offer useful choices, remember past choices.
- **Wrong help gets followed** (Lumière). Humour must never obscure what the bro is unsure about.
- **Gemini Live's "proactive audio"** lets the model stay silent, which is a reminder that saying nothing is a valid output.

Sources: [factsheet.md B.1](../research/factsheet.md), [ai-tools.md §3.4](../research/ai-tools.md).

The maintainer is Arabic-speaking. The persona should sound natural in Egyptian Arabic ("يا برو", "إنت متلخبط ولا إيه؟") and in English, and switch with the user.

## Decision drivers
- Consistency: same character across LLM calls, languages and offline templates.
- Safety: humour never in errors, security or destructive steps, and never at the user's expense on sensitive topics.
- Controllability: the user sets how much humour they want.
- Cost and latency: frequent short lines shouldn't need an LLM call.
- Testability.

## Options considered
| Option | For | Against |
|---|---|---|
| **Free-form LLM persona via system prompt only** | Natural, contextual | Drift, uneven humour, costs a call per line, hard to test |
| **Template library only** | Deterministic, offline, cheap | Repetitive and stale fast; no context |
| **Persona spec + template library for frequent moments + LLM for contextual lines under a style contract (recommended)** | Consistent and cheap where frequent, fresh where it matters, testable with a rubric | Two mechanisms to keep aligned |

## Decision
1. **A `persona` module in core** (not in packs). It owns:
   - `persona.toml`: name, voice, register per locale, a humour intensity scale of 0–3, and banned topics;
   - `lines/<locale>.toml`: templated lines per **moment** (`offer_stuck`, `offer_declined`, `back_off_long`, `step_done`, `task_done`, `unsure`, `error_recovered`, `greeting`), with 10–30 variants each, carrying weights and humour levels;
   - `style.md`: a tone guide that is included in the Brain's frozen system prompt (ADR-0008).
2. **Tone guide (summary).**
   - Warm, brief, teammate energy.
   - One sentence per bubble.
   - Address the user as "bro" or "يا برو" at most once per task.
   - Confident when the target is High confidence. Explicitly hedged when Medium or Low (ADR-0007). Humour never replaces the hedge.
   - Self-deprecating rather than user-deprecating ("my bad, wrong button" rather than "you clicked wrong").
3. **Where humour is allowed:**

   | Moment | Humour allowed? |
   |---|---|
   | Proactive offers and back-off acknowledgements | Yes, up to the user's intensity |
   | Step done / task done | Light (level ≤ 2) |
   | Narration of a step | No jokes; clarity first |
   | Errors, uncertainty, recovery | Only gentle reassurance, no jokes |
   | R2/R3 risk confirmations, privacy or security prompts, anything about credentials or money | **Never** |
   | User frustration detected (repeated failures plus "no") | Humour drops one level automatically |

4. **How a line is produced.**
   - Frequent moments use a **template** chosen by locale, intensity and recency (no repeat within the last 10 lines).
   - Contextual lines, such as an offer naming the actual menu or a "why?" answer, are produced by the LLM under the style contract and limited to ≤ 140 characters.
   - Templates are the offline fallback.
5. **Language.**
   - Follow the user's last language.
   - Egyptian Arabic is the default Arabic register. MSA is used for TTS fallback when the offline voice is MSA-trained (ADR-0011).
   - Code-switching mirrors the user.
   - UI element names are quoted in the UI's own language, isolated for bidi (ADR-0019).
6. **User controls.**
   - Humour slider: 0 = plain, 3 = full bro.
   - "Less chatty" toggle.
   - Persona name and avatar choice (later).
7. **Safety filter.**
   - Every LLM-generated persona line passes a deterministic check before display: length, banned-topic keyword list in EN and AR, and no imperative to perform an R2+ action unless it came from the policy-approved step.
   - A line that fails falls back to a template.

## Implemented (#23, 2026-11-23)
- **`ya_bro.persona`** (data in the package): `persona.toml` (14 moments with a humour ceiling each, `optional` and `sensitive` flags, banned topics in English and Arabic), `lines/en.toml` and `lines/ar.toml` (79 lines each, tagged with the lowest humour setting that may use them, with `bro`, `requires` and `forbids` fields), `style.md` (the tone guide for the Brain's prompt, `broctl persona style`).
- **Rules enforced in code:** humour never in `cant_find`, `unsure`, `error_recovered` or the sensitive `risk_confirm` (a ceiling of 0, and a risky step silences everything); the setting is a ceiling per moment; it drops one level when the user seems frustrated (three wrong actions in a row, cleared by progress); "less chatty" mutes optional moments and all humour; "bro" at most once per task; a line does not repeat while an unused one exists; lines are chosen deterministically in file order, so a run is reproducible.
- **Languages:** English and Egyptian Arabic; the bro follows the user's language (`detect_locale`, a third of the letters Arabic), UI names are bidi-isolated in Arabic lines, the overlay is told `dir = rtl` for Arabic. `language` in `config.toml` is `auto` (English until the user writes Arabic), `en` or `ar`; `less_chatty` is a config key too.
- **Safety filter for generated lines:** `Persona.vet` (one line, at most 140 characters, no banned topic in either language including with the Arabic article, no link or backtick command, no risky instruction unless the approved step is risky) and `generated_or` (falls back to the template, never replaces a sensitive moment). Nothing generates lines yet; this is the gate for the Claude brain.
- **In the step loop:** a step the user must take themselves (R3) gets a plain "this one is yours to press" line and no teasing even after a wrong action at full humour; the teasing face needs humour of at least 1 and no frustration; the struggle offer's lines (`offer_stuck`, `offer_declined`, `back_off_long`) exist and are previewable (`broctl persona say|list|lint|style`) but the offer bubble is not built.
- **Measured:** 46 unit tests (every moment and level in both languages, the ceilings, frustration, less-chatty, bro-once, rotation, language switching, the filter with 17 good and bad lines, the loop on a risky step, config, the command, and a lint that catches broken data) and a real-frame check in the isolated shell that an Arabic line renders as real text and that the right-to-left bubble mirrors its buttons.
- **Changed from the old behaviour:** "can't find" and the hedge are no longer playful (ADR-0013's table); the first mismatch line is unchanged.
- **Not done:** the rubric eval (100 generated lines per locale graded by an LLM judge, 90% target) and the dogfood rule (more than 40% lowering the slider), because no line is generated yet; 10 to 30 variants per moment (there are 2 to 9); native review of every Arabic line (they are drafts, marked as such in the file); the humour slider UI and the "less chatty" toggle UI (only `config.toml`); code-switching inside one line; MSA for TTS fallback; persona name and avatar choice; reading the user's language from their requests (no request input exists yet); the offer bubble itself; the Arabic first/last-line wrap of RTL paragraphs inside the bubble was only looked at, not measured.

## Consequences
- **Positive:**
  - A recognisable character that stays out of the way when it matters.
  - Cheap and offline for frequent lines.
  - Tests are possible: rubric evals and template linting.
- **Negative:**
  - Template authoring in two languages.
  - Egyptian Arabic needs native review. The maintainer does it.
- **Risks:**
  - Humour misfires culturally.
  - LLM lines drift from the style. Mitigation: a rubric eval in ADR-0016.

## Validation plan
- **Rubric eval.** 100 generated offers and acknowledgements per locale, graded by an LLM judge plus spot-checked by the maintainer on: brevity, correct hedging, humour level matching the setting, no banned content, and natural Egyptian phrasing. Target ≥ 90% pass.
- **Dogfood.** Track how often users lower the humour slider in the first week. If more than 40% of users lower it, reduce the default.

## Revisit if
- Users consistently set humour to 0. Then lower the default and reconsider the brand.
- Voice TTS cannot carry the intended tone in Arabic. Then simplify Arabic lines.

## Sources
- Whitworth 2005, Polite computing: https://digitalcommons.njit.edu/fac_pubs/19576
- Swartz, "Why People Hate the Paperclip" (summary): https://jerz.setonhill.edu/?p=1399
- Horvitz 1999 (social appropriateness, graceful degradation): https://www.erichorvitz.com/chi99horvitz.pdf
- [docs/research/ai-tools.md](../research/ai-tools.md): §2.4, §3.4
- [docs/research/factsheet.md](../research/factsheet.md): Part B
