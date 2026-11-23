# ADR-0007: Grounding and pointing accuracy

- Status: Proposed
- Date: 2026-11-20
- Issue: #13
- Depends on: ADR-0004, ADR-0005, ADR-0008

## Context
"Grounding" means turning a step's intent into one on-screen rectangle. For example, "click the Export button" becomes a rectangle. A wrong highlight in teaching mode is worse than none. Lumière's Wizard-of-Oz study found that users follow wrong advice, which makes it look like success ([ai-tools.md §3.4](../research/ai-tools.md)).

Evidence on grounding methods:

| Method | Accuracy | Source |
|---|---|---|
| General VLM asked for raw pixels (Clicky's `[POINT:x,y]` approach) | Weakest. GPT-4o scores 0.8 on ScreenSpot-Pro. | ScreenSpot-Pro leaderboard, 2026-11-10 |
| Specialist grounders | 61.6 (UI-TARS-1.5) to 85.1 (zoom cascades) | Same |
| Set-of-marks: the LLM picks a numbered candidate | Lifts weak models a lot (GPT-4o goes from 0.8 to 39.6 with OmniParser V2) | OmniParser V2 |
| Icon targets, any model | 20–40 points lower than text targets | Same |

Navisual and Agent S use the same split: **the LLM describes or selects, and local code resolves**.

On the Claude side:
- Opus 4.7+ and Sonnet 5+ accept images up to 2576 px on the long edge.
- Their coordinates map 1:1 to image pixels.
- The current computer-use surface is `computer_toolset_20260801`.
- Source: Claude API skill reference, cached 2026-10-06.

## Decision drivers
- The SPEC target is ≥ 80% of steps correctly pointed. Within that, the share of *confidently wrong* rings must be tiny.
- Latency.
- Cost.
- No raw screen leaves the machine unless it has to.

## Options considered
| Option | For | Against |
|---|---|---|
| **LLM emits pixel coordinates from a screenshot** | Simple (Clicky) | Weakest accuracy, HiDPI/scale bugs, needs a screenshot every step |
| **LLM selects from an AT-SPI candidate list (set-of-marks over the a11y tree) (recommended primary)** | Exact rects, no pixels, cheap; the LLM does what it is good at (semantic choice) | Only works where AT-SPI exposes the element |
| **Local specialist grounder (UI-TARS-1.5-7B, Apache-2.0)** | Good on pro apps, offline | 7B on a 4 GB RTX 3050 laptop GPU likely needs heavy quantisation (unverified feasibility). Icon accuracy is still about 38. |
| **Claude vision on a cropped window with an OmniParser-style or OCR set-of-marks (recommended fallback)** | No local GPU needed; marks turn pointing into selection; the crop cuts tokens about 80% (Navisual) | Cloud round trip of 1–3 s; needs capture consent |

## Decision
1. **Target spec from the planner.** Each step names its target as a structured `TargetSpec`:
   - `{role?, name?, name_alts[], text?, near?, within?, fingerprint_id?}`;
   - or `candidate_id` when choosing from the list it was given.

   The planner never emits pixels when candidates exist.
2. **Resolution cascade** (ADR-0005 layers). Stop at the first layer that clears its confidence threshold:
   1. pack fingerprint or app hook: exact;
   2. AT-SPI fingerprint match;
   3. AT-SPI candidate-list selection by the LLM;
   4. OCR text match on the window crop (fuzzy, both locales);
   5. vision set-of-marks on the crop, where OCR boxes and icon-detector boxes are numbered and Claude picks one;
   6. raw vision coordinates, as a last resort. This tier is always "low".

   Use the MIT-licensed OmniParser `icon_detect_v3` + `icon_caption` only if it is installed. Do not use the AGPL v2 `icon_detect`.
3. **Confidence tiers drive presentation:**

   | Tier | Criteria (initial; tune in eval) | What the user sees |
   |---|---|---|
   | **High** | Unique fingerprint/id match, or AT-SPI role+name unique with margin ≥ 0.3, and the rect passes the ADR-0004 sanity checks | Solid ring + pointer flight + "click **Export**" |
   | **Medium** | Best candidate margin < 0.3, or the OCR/vision tier agrees with one other signal | Dashed ring + hedged text ("I think it's this one, the **Export** button") + quick "wrong one?" button |
   | **Low** | Vision-only, or disagreement between tiers | No ring. The region is described ("top-right toolbar, looks like a floppy-disk icon"). Offer "show me where you're looking" or ask the user to hover it so AT-SPI focus/hover can confirm. |
   | **None** | Nothing found | Re-plan (the element may be in a closed menu or another tab). The bro says so honestly. |

4. **Do-it gating.** The bro only *acts* on a High-confidence target (ADR-0009). Medium targets need the user to confirm "yes that one" first.
5. **Learning from corrections.** "Wrong one" plus the user's click, observed through the AT-SPI focus/activate event on the real element, gives the correct fingerprint. It is stored as a local override (ADR-0005 auto-heal) and logged without content as a pointing miss for the eval.
6. **Zoom/crop cascade.** Every vision call works on the focused window crop or a sub-pane (from AT-SPI pane bounds), never the full multi-monitor desktop. This follows the best ScreenSpot-Pro systems, which crop and zoom.

## Consequences
- **Positive:**
  - Most steps need no pixels at all.
  - Confidence is visible to the user, so a mistake costs "wrong one?" rather than lost trust.
  - The design degrades gracefully, in line with Horvitz principle 8: "doing less but doing it correctly".
- **Negative:**
  - Medium and Low tiers make some steps less magical.
  - The margin thresholds need data.
- **Risks:**
  - AT-SPI names that are poor or untranslated ("button", "", icon file names).
  - OCR quality on Arabic UI text.

## Validation plan
**Pointing eval harness (ADR-0016)**
- About 300 labelled targets: fixture apps plus recorded snapshots (AT-SPI tree JSON + screenshot + ground-truth rect) from GIMP, Inkscape, LibreOffice, GNOME Settings, Firefox/workbench and Ptyxis, in EN and AR UI locales (amended for GNOME-first 2026-11-20; KDE System Settings and Konsole join with the KWin port).
- Metrics:
  - **pointed-correct rate**: target ≥ 80% overall, SPEC §8;
  - **confidently-wrong rate**: High tier but wrong, target ≤ 2%;
  - Medium-tier precision;
  - latency per tier;
  - tokens per step.
- Runs per commit on recorded fixtures, with no LLM calls for tiers 1–4 and LLM responses cached for 5–6. Live LLM runs nightly.

**Implemented (#19):** `ya_bro.grounding` (AT-SPI tiers only) and `broctl eval pointing` over `evals/pointing/`. The shipped corpus is synthetic (300 cases, 6 made-up apps, EN and AR); recorded snapshots from the real apps above are still to come, and until they exist the gate does not measure real accuracy.

**Go/no-go for MVP:** a confidently-wrong rate above 5% blocks release, whatever the overall accuracy.

## Revisit if
- A small local grounder (≤ 4 GB VRAM) reaches ≥ 60 on ScreenSpot-Pro. Then make it the default tier 5 for privacy.
- Claude's native computer-use grounding on crops reaches parity with AT-SPI on our eval.

## Sources
- ScreenSpot-Pro leaderboard: https://github.com/GUI-Agent/grounding-leaderboard ; paper https://arxiv.org/abs/2504.07981
- OmniParser V2: https://www.microsoft.com/en-us/research/articles/omniparser-v2-turning-any-llm-into-a-computer-use-agent/
- OmniParser v2 weights licences: https://huggingface.co/microsoft/OmniParser-v2.0
- Agent S grounding (`grounding.py`): https://github.com/simular-ai/Agent-S
- Horvitz 1999, Principles of mixed-initiative UIs: https://www.erichorvitz.com/chi99horvitz.pdf
- [docs/research/ai-tools.md](../research/ai-tools.md): §2.5, §3.1, §3.4
- Claude vision and computer-use facts: Anthropic API reference (`computer_toolset_20260801`; 2576 px high-res tier), https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool.md
