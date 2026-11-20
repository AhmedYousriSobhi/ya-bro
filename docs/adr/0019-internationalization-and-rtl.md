# ADR-0019: Internationalisation and right-to-left (Arabic) support

- Status: Proposed
- Date: 2026-11-20
- Issue: #13
- Depends on: ADR-0006, ADR-0011, ADR-0013, ADR-0023

> **Amended for GNOME-first (2026-11-20).** On GNOME the bubble is an `St.Label` drawn by the Shell extension (ADR-0023 §6), still rendered by Pango. Core sends already-localized, already-isolated text plus an explicit `dir` (`ltr`/`rtl`). The extension sets the label's text direction from `dir` instead of auto-detecting, and mirrors button order. The golden rendering tests run against both the St bubble (headless GNOME shell) and the GTK bubble (KWin/docked).

## Context
The maintainer is an Arabic speaker. Ya-Bro's own text appears in several places: the bubble, the ask box, settings, doctor output and persona lines. It must work in Arabic, right to left, and in English, and it often mixes the two. A typical Arabic line still quotes English UI names, for example "دوس على **Export** فوق على اليمين".

Arabic in the guided apps raises its own problems:
- the apps' own UI may be in Arabic, so their AT-SPI names are in Arabic;
- Arabic OCR quality is unverified (ADR-0005);
- typing Arabic through injection is unsafe (ADR-0009);
- TTS needs diacritization (ADR-0011).

What the toolkits already handle:
- GTK4 and Pango do Arabic shaping and the Unicode Bidirectional Algorithm.
- `Pango.Layout` auto-detects the base direction per paragraph by default.
- GTK mirrors layouts when the widget direction is RTL.
- Noto fonts cover Arabic script.

## Decision drivers
- Correct shaping and bidi in mixed-script sentences.
- Natural Egyptian Arabic phrasing.
- Element names stay recognisable, in the language shown on screen.
- Low effort: use the platform's bidi support rather than reimplementing it.

## Options considered
| Option | For | Against |
|---|---|---|
| **gettext for UI strings + Pango bidi + explicit isolates for embedded names (recommended)** | Standard Linux i18n; Pango handles shaping; isolates fix the classic "punctuation jumps" bugs | Translators needed (the maintainer covers Arabic) |
| **Custom string tables (TOML) for everything** | Simple for persona lines | Reinvents gettext plurals and context for UI strings |
| **English-only UI, Arabic only in voice** | Least work | Fails the primary user |

## Decision
1. **UI strings** use gettext (`ya-bro.pot`, `po/ar.po`, `po/en.po`) with context markers. **Persona lines** use the per-locale TOML libraries from ADR-0013, because they are variants rather than one-to-one translations.
2. **Language selection.** The UI language follows the system locale, with an override in settings. The *conversation* language follows the user's last utterance or message, detected per message. The two can differ: for example, Arabic conversation with an English desktop.
3. **Bidi in the bubble.**
   - Render with Pango, with the base direction set from the *message* language. Do not rely on first-strong auto-detection, which fails when an Arabic sentence starts with an English UI name.
   - Wrap every embedded UI element name, path, command or number in Unicode isolates. Use FSI…PDI by default, or LRI/RLI when the script is known.
   - Render commands and file paths in a monospace LTR span.
4. **Bubble layout mirroring.** For RTL messages the bubble mirrors three things: button order (primary on the left in RTL), the tail side, and the preferred placement relative to the target. The ring and pointer geometry do not mirror, because they follow the real widget.
5. **Fonts.**
   - Default stack: system UI font, then **Noto Sans Arabic** / **Noto Naskh Arabic** (OFL-1.1), then Noto Sans.
   - Never force a Latin-only font.
   - Minimum size 11 pt for Arabic, because Arabic glyphs need more x-height.
   - `doctor` checks that an Arabic-capable font is installed.
6. **Element names in two languages.**
   - Fingerprints store names per locale (ADR-0005), plus the translation msgid when the app uses gettext and it can be discovered (unverified feasibility).
   - Narration quotes the name *as shown on screen*. When the UI language differs from the conversation language, the bro adds a gloss: "**Export** (تصدير)".
7. **Numerals and punctuation.** Use Western digits by default in technical contexts (versions, coordinates, commands), with an optional Arabic-Indic digits setting for prose. Use the Arabic comma and question mark (، ؟) in Arabic persona lines.
8. **Voice.** STT language routing and script-split TTS are specified in ADR-0011. The LLM produces a separate TTS-friendly variant (diacritics for offline voices).
9. **Packs.** Pack text fields allow `{en, ar}` maps. Missing Arabic falls back to English with an LLM translation at runtime, marked as machine-translated in debug.

## Consequences
- **Positive:** correct mixed-script rendering by using Pango properly, Arabic as a first-class language, and standard tooling.
- **Negative:** translation upkeep, and isolate markers in strings need care in tests.
- **Risks:**
  - Arabic OCR quality.
  - Apps with Arabic UIs exposing untranslated or garbled AT-SPI names.
  - Persona tone in Arabic reading as unnatural (ADR-0013 eval).

## Validation plan
- **Golden rendering tests.** 30 mixed-script bubble strings (Arabic with English names, commands, numbers and punctuation at the ends) rendered via Pango in a headless test and compared to reviewed screenshots.
- **Arabic UI run.** Run the pointing eval (ADR-0007) with GIMP and LibreOffice in an `ar_EG.UTF-8` locale, and measure name-match accuracy against the English UI.
- The maintainer reviews all Arabic strings before the first release.

## Revisit if
- GTK or Pango bidi behaviour changes.
- Users of other RTL languages (Persian, Hebrew) appear: the design generalises, but the persona libraries do not.

## Sources
- Pango layout direction and auto-dir: https://docs.gtk.org/Pango/method.Layout.set_auto_dir.html
- Unicode Bidirectional Algorithm (UAX #9, isolates): https://www.unicode.org/reports/tr9/
- Noto Arabic fonts: https://fonts.google.com/noto/specimen/Noto+Sans+Arabic
- GNU gettext: https://www.gnu.org/software/gettext/
- [docs/research/non-ai-tools.md](../research/non-ai-tools.md): §11 (Arabic STT/TTS, tashkeel)
