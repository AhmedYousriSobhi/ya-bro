> Companion to the three landscape docs. Decision-oriented fact sheet compiled 2026-11-20 by a research agent for the ADR set (issue #13): dependency licences, HCI research on proactive help, Arabic/English voice facts, and packaging facts. Every fact carries a source URL; anything not confirmed from a primary source is marked (unverified). Not legal advice.

# Ya-Bro ADR Factsheet (research date 2026-11-20)

Method: licenses read from the GitHub license API (`gh api repos/OWNER/REPO`), PyPI JSON metadata (`https://pypi.org/pypi/<pkg>/json`), Hugging Face model API tags (`https://huggingface.co/api/models/<id>`), and raw LICENSE/COPYING files. Anything not confirmed from a primary source is marked **(unverified)**. Not legal advice.

---

## PART A — Dependency licenses

### A.1 Table

| Component | SPDX license | Source | Compatibility notes (distributing Ya-Bro under MIT / Apache-2.0 / GPL-3.0 / LGPL) |
|---|---|---|---|
| PyGObject | LGPL-2.1-or-later | https://github.com/GNOME/pygobject (API: LGPL-2.1); PyPI classifier "LGPLv2+" https://pypi.org/project/PyGObject/ | Imported Python module, used unmodified -> fine for any outbound license. LGPL obligations only bite if we ship a modified PyGObject or a bundled binary (then allow relinking/replacement). |
| pycairo | LGPL-2.1-only OR MPL-1.1 | https://raw.githubusercontent.com/pygobject/pycairo/main/COPYING ; PyPI `license_expression` https://pypi.org/project/pycairo/ | Same as above. |
| GTK4 | LGPL-2.0-or-later (COPYING = GNU Library GPL v2) | https://gitlab.gnome.org/GNOME/gtk/-/raw/main/COPYING | System library, dynamic linking via GI -> compatible with all four. |
| gtk4-layer-shell | MIT | https://github.com/wmww/gtk4-layer-shell | No constraint. |
| at-spi2-core / libatspi | LGPL-2.1-or-later | https://github.com/GNOME/at-spi2-core (API: LGPL-2.1) | System library via GI/D-Bus -> fine. |
| pyatspi2 | LGPL-2.0 (COPYING = GNU Library GPL v2) | https://gitlab.gnome.org/GNOME/pyatspi2/-/raw/master/COPYING | Fine (unmodified import). Not on PyPI (`pyatspi` 404 on PyPI) -> distro package / system-site-packages only. |
| python-xlib | LGPL-2.1-or-later | https://github.com/python-xlib/python-xlib ; https://pypi.org/project/python-xlib/ | Fine. Note: repo last pushed 2023-04-01 (low maintenance). |
| dbus-python | MIT AND (GPL-2.0-or-later OR AFL-2.1) | https://pypi.org/project/dbus-python/ (license_expression) | Choose AFL-2.1 branch -> permissive. Needs libdbus C build. |
| dasbus | LGPL-2.1-or-later | https://github.com/rhinstaller/dasbus ; https://pypi.org/project/dasbus/ | Fine; built on GLib GDBus (PyGObject) so no extra native dep. |
| jeepney | MIT | https://pypi.org/project/jeepney/ | Pure Python, no native deps. |
| dbus-fast | MIT | https://github.com/Bluetooth-Devices/dbus-fast ; https://pypi.org/project/dbus-fast/ | asyncio, Cython-accelerated. |
| Anthropic Python SDK (`anthropic`) | Apache-2.0 | https://github.com/anthropics/anthropic-sdk-python ; PyPI v2.12.0 https://pypi.org/project/anthropic/ | Apache-2.0 is compatible with MIT/Apache/GPL-3.0 outbound (not GPL-2.0-only). |
| whisper.cpp | MIT | https://github.com/ggml-org/whisper.cpp | No constraint. |
| pywhispercpp | MIT | https://github.com/absadiki/pywhispercpp | No constraint. |
| faster-whisper | MIT | https://github.com/SYSTRAN/faster-whisper ; PyPI v1.2.1 | No constraint. |
| CTranslate2 | MIT | https://github.com/OpenNMT/CTranslate2 | No constraint. |
| Whisper code | MIT | https://github.com/openai/whisper | — |
| Whisper weights | large-v3: Apache-2.0 (HF tag); large-v3-turbo: MIT (HF tag) | https://huggingface.co/openai/whisper-large-v3 ; https://huggingface.co/openai/whisper-large-v3-turbo | Both permissive; downloadable at runtime or redistributable with notice. |
| Vosk (vosk-api) | Apache-2.0 | https://github.com/alphacep/vosk-api | Code permissive. |
| Vosk models | Per model: Apache-2.0, AGPL, GPL-3.0, LGPL-3.0, MIT, CC-BY-NC-SA-4.0 | https://alphacephei.com/vosk/models | Arabic: `vosk-model-ar-mgb2-0.4` (318 MB, Apache-2.0, WER 16.40 MGB-2 dev); `vosk-model-ar-0.22-linto-1.1.0` (1.3 GB, **AGPL**, WER 52.87 CV test / 28.50 MGB-2 dev). Check per model. |
| Piper (rhasspy/piper) | MIT, **archived** (archived=true, last push 2025-08-26); README: "Development has moved: https://github.com/OHF-Voice/piper1-gpl " | https://github.com/rhasspy/piper | Old MIT code still linked espeak-ng (GPL-3.0) via piper-phonemize -> the MIT label was arguably misleading for binaries. |
| piper1-gpl (OHF-Voice) / `piper-tts` on PyPI | GPL-3.0-or-later (PyPI v1.8.0 `license_expression`) | https://github.com/OHF-Voice/piper1-gpl ; https://pypi.org/project/piper-tts/ | README: "embeds espeak-ng for phonemization". Importing `piper` in-process from Ya-Bro makes the combined Python program a GPL-3.0 work (FSF view). Keep it out-of-process (subprocess / Wyoming protocol) if Ya-Bro stays permissive. |
| Piper voices (rhasspy/piper-voices) | HF repo tag MIT, but Piper docs: "The Piper project makes **no license grant of its own over voice models**"; rights come from the training-data chain | https://huggingface.co/rhasspy/piper-voices ; https://raw.githubusercontent.com/OHF-Voice/piper1-gpl/main/docs/LICENSING.md | Lessac base voice: Blizzard 2013 corpus limits use to "research and exploration of speech technologies" (non-commercial). Replacement bases: `nl_BE-rdh-medium` (CC0), `en_US-hifi_tts_92-medium` (CC BY 4.0). Docs require shipping each voice's `MODEL_CARD` when redistributing. |
| Piper `ar_JO-kareem` (low, medium) — only Arabic Piper voices in voices.json | Dataset https://github.com/AliMokhammad/arabicttstrain — GitHub license: **none** (null); MODEL_CARD: "License: See URL"; "Finetuned from U.S English lessac voice (medium quality)" | https://huggingface.co/rhasspy/piper-voices/raw/main/ar/ar_JO/kareem/medium/MODEL_CARD ; https://huggingface.co/rhasspy/piper-voices/raw/main/voices.json | **Double problem**: unlicensed dataset + lessac (non-commercial) ancestry. Not on the Piper commercial-use list (grep of COMMERCIAL_USE.md found no `ar_` entries: https://raw.githubusercontent.com/OHF-Voice/piper1-gpl/main/docs/COMMERCIAL_USE.md). Do not bundle; at most optional user download with clear notice. |
| espeak-ng | GPL-3.0 (GitHub API; upstream states GPL-3.0-or-later (unverified exact "or-later" wording)) | https://github.com/espeak-ng/espeak-ng | Linking (incl. Piper's embedded copy) -> GPL-3.0 for the combined work. Invoking the `espeak-ng` binary as a separate process (pipes/args) is generally treated as "mere aggregation" per FSF GPL FAQ (https://www.gnu.org/licenses/gpl-faq.en.html#MereAggregation). |
| Kokoro (code `kokoro`) | Apache-2.0 | https://github.com/hexgrad/kokoro ; PyPI v0.9.4 | Note: default G2P `misaki` falls back to espeak-ng for some languages (unverified). |
| Kokoro-82M weights | Apache-2.0 | https://huggingface.co/hexgrad/Kokoro-82M | **No Arabic**: VOICES.md lists 9 languages (en-US, en-GB, ja, zh, es, fr, hi, it, pt-BR) https://huggingface.co/hexgrad/Kokoro-82M/raw/main/VOICES.md |
| openWakeWord code | Apache-2.0 | https://github.com/dscripka/openWakeWord | Code permissive. |
| openWakeWord pretrained models | **CC BY-NC-SA 4.0** (README: "All of the included pre-trained models are licensed under ... CC BY-NC-SA 4.0"); HF tag cc-by-nc-sa-4.0 | https://raw.githubusercontent.com/dscripka/openWakeWord/main/README.md ; https://huggingface.co/davidscripka/openwakeword | Shared embedding backbone is from Google speech_embedding (Apache-2.0) per same README. A custom "Ya bro" model we train ourselves on licensed/synthetic data is ours to license; don't ship the NC pretrained "hey jarvis"-type models in a commercial-friendly bundle. |
| Porcupine (Picovoice) | SDK repo Apache-2.0, but engine requires an AccessKey from Picovoice Console; proprietary service terms | https://github.com/Picovoice/porcupine ; README "AccessKey obtained from Picovoice Console" | **Free tier ending**: HA forum thread (June 2026) reports Picovoice email: free-tier AccessKeys disabled 2026-06-30, "The SDK does not run without a valid key", "There is no non-commercial tier planned" — https://community.home-assistant.io/t/porcupine-free-tier-shutdown-alternatives-for-home-assistant-voice-users/1012382 (secondary source; Picovoice primary page not retrievable -> **(unverified on picovoice.ai)**). Unfit for an open-source default. |
| microWakeWord | Apache-2.0 | https://github.com/kahrendt/microWakeWord ; `pymicro-wakeword` PyPI Apache-2.0 | Model licenses per model (unverified). |
| Silero VAD | MIT (code + model, PyPI `silero-vad` v6.2.3 MIT) | https://github.com/snakers4/silero-vad ; https://pypi.org/project/silero-vad/ | No constraint. |
| webrtcvad (py-webrtcvad) | MIT (wrapper; bundles WebRTC VAD C code under BSD-3-Clause (unverified)) | https://raw.githubusercontent.com/wiseman/py-webrtcvad/master/LICENSE ; https://pypi.org/project/webrtcvad/ | Upstream last push 2024; `webrtcvad-wheels` fork (MIT) has wheels. |
| python-sounddevice | MIT | https://github.com/spatialaudio/python-sounddevice | — |
| PortAudio | MIT-style (permissive, "PortAudio License"; GitHub NOASSERTION) | https://raw.githubusercontent.com/PortAudio/portaudio/master/LICENSE.txt | Permissive. |
| Tesseract | Apache-2.0 | https://github.com/tesseract-ocr/tesseract | Arabic traineddata in tessdata repo (Apache-2.0, unverified). |
| RapidOCR | Apache-2.0 | https://github.com/RapidAI/RapidOCR ; PyPI `rapidocr` 3.10.0 | ONNX models from PaddleOCR. |
| PaddleOCR | Apache-2.0 | https://github.com/PaddlePaddle/PaddleOCR | — |
| OmniParser code | CC-BY-4.0 (GitHub API) | https://github.com/microsoft/OmniParser | CC-BY on code: attribution required; unusual but permissive. |
| OmniParser v2 weights | Per folder: `icon_detect` (YOLOv8/Ultralytics) **AGPL-3.0**; `icon_caption` (Florence-2) MIT; new `icon_detect_v3` (YOLOv9-E via MultimediaTechLab/YOLO) **MIT** | https://huggingface.co/microsoft/OmniParser-v2.0/raw/main/README.md | "Pairing icon_detect_v3 with icon_caption gives a fully MIT licensed OmniParser pipeline." Use v3 detector only. |
| UGround | code MIT; UGround-V1-7B weights Apache-2.0 | https://github.com/OSU-NLP-Group/UGround ; https://huggingface.co/osunlp/UGround-V1-7B | Permissive (base Qwen2-VL licence inherited — check per size, unverified). |
| OS-Atlas | code Apache-2.0; OS-Atlas-Base-7B weights Apache-2.0 | https://github.com/OS-Copilot/OS-Atlas ; https://huggingface.co/OS-Copilot/OS-Atlas-Base-7B | Permissive. |
| UI-TARS | code Apache-2.0 (repo archived); UI-TARS-1.5-7B weights Apache-2.0 | https://github.com/bytedance/UI-TARS ; https://huggingface.co/ByteDance-Seed/UI-TARS-1.5-7B | Permissive. |
| Qwen2.5-VL | code Apache-2.0; weights: **7B Apache-2.0**, **3B "qwen-research"** (non-commercial research licence), **72B "qwen" licence** (custom) | https://github.com/QwenLM/Qwen2.5-VL ; https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct ; https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct/blob/main/LICENSE ; https://huggingface.co/Qwen/Qwen2.5-VL-72B-Instruct/blob/main/LICENSE | Size-dependent — only 7B is plainly permissive. |
| sherpa-onnx | Apache-2.0 | https://github.com/k2-fsa/sherpa-onnx | Models licensed separately. |
| libei | MIT | https://gitlab.freedesktop.org/libinput/libei/-/raw/main/COPYING | — |
| ydotool | **AGPL-3.0** | https://github.com/ReimuNotMoe/ydotool | Invoke as external process only; never vendor/link. Requires root/uinput daemon. |
| xdotool | BSD-3-Clause | https://github.com/jordansissel/xdotool | — |
| dogtail | GPL-2.0 (COPYING = GPL v2) | https://gitlab.com/dogtail/dogtail/-/raw/master/COPYING | Importing GPL-2.0(-only?) code in-process is **incompatible with Apache-2.0** and forces GPL; use only in tests/dev, or reimplement over pyatspi. "Only vs or-later" unverified. |

### A.2 Sibling project
- `AhmedYousriSobhi/workbench` ships **both `LICENSE-APACHE` and `LICENSE-MIT`** (dual MIT OR Apache-2.0); GitHub's detector shows only Apache-2.0. Source: `gh api repos/AhmedYousriSobhi/workbench/contents`.
- Ya-Bro SPEC.md open question 5: "License (proposal: MIT or Apache-2.0)" (SPEC.md §9).

### A.3 Analysis: which outbound license
- Every *core* dependency (GTK4/PyGObject/pycairo/libatspi/pyatspi2/python-xlib/dasbus: LGPL; anthropic SDK: Apache-2.0; whisper.cpp/faster-whisper/CTranslate2/Silero/openWakeWord code/sounddevice/PortAudio/jeepney/dbus-fast: MIT/Apache) permits a permissive outbound license. LGPL libraries used dynamically and unmodified impose no copyleft on Ya-Bro's own code.
- The only copyleft hazards are **espeak-ng (GPL-3.0)**, **piper1-gpl / piper-tts (GPL-3.0-or-later)**, **dogtail (GPL-2.0)**, **ydotool (AGPL-3.0)**, OmniParser `icon_detect` (AGPL-3.0), Vosk linto Arabic model (AGPL). All are avoidable or can be isolated:
  - Run TTS engines (Piper, espeak-ng) as **separate processes** talking over stdin/stdout, a socket, or the Wyoming protocol (https://github.com/rhasspy/wyoming, MIT). FSF GPL FAQ: communication via pipes/sockets/command-line args between separate programs is normally aggregation, unless the semantics are so intimate they form one program (https://www.gnu.org/licenses/gpl-faq.en.html#MereAggregation). Do **not** `import piper` inside the Ya-Bro process if staying permissive.
  - Ship GPL engines as optional plugins/packages (e.g. `ya-bro-tts-piper`) carrying their own GPL license; the core declares no hard dependency.
- **Apache-2.0 vs MIT**: Apache-2.0 adds an express patent licence + patent-retaliation clause and NOTICE handling (Apache-2.0 §3, §4: https://www.apache.org/licenses/LICENSE-2.0). Relevant for a voice/ML project in a patent-dense space. Apache-2.0 is one-way compatible with GPL-3.0 but **not GPL-2.0-only** (https://www.apache.org/licenses/GPL-compatibility.html) — irrelevant unless dogtail is linked.
- **Dual MIT OR Apache-2.0** (Rust-ecosystem convention, matches workbench) gives users the patent grant if they want it and maximal GPL-2.0 compatibility via MIT.
- **GPL-3.0-or-later** would let Ya-Bro import piper-tts/espeak-ng in-process freely and protects against proprietary forks, but blocks permissive reuse of the core and is a deterrent to app-pack authors; the user-facing benefit (in-process Piper) is small since out-of-process TTS is the better architecture anyway (crash isolation, latency streaming).
- **MPL-2.0**: file-level copyleft, compatible with GPL via secondary-licence clause; a middle ground, but less common in Python desktop land and adds friction for no specific gain here.
- Verdict (recommendation for ADR): **MIT OR Apache-2.0 dual licence**, with an ADR rule "GPL/AGPL components only out-of-process and optional; model weights checked individually (NC models never bundled)".

### A.4 Implications for Ya-Bro
1. Default stack can be fully permissive: faster-whisper or whisper.cpp + Whisper large-v3(-turbo) weights + Silero VAD + custom-trained openWakeWord model + dasbus/jeepney + PyGObject.
2. Piper: out-of-process only; and **no permissively-licensed Arabic Piper voice exists** (only `ar_JO-kareem`, unlicensed dataset + lessac lineage). Arabic TTS must come from elsewhere (cloud or another engine) or a newly trained voice from a licensed corpus fine-tuned from `nl_BE-rdh` (CC0).
3. Don't bundle openWakeWord's pretrained models (CC BY-NC-SA); train "Ya bro" ourselves.
4. Porcupine is not viable (AccessKey, free tier reportedly ended 2026-06-30).
5. Grounding models: OmniParser v2 only with `icon_detect_v3`; Qwen2.5-VL only at 7B for permissive use; UI-TARS-1.5-7B / OS-Atlas / UGround are Apache-2.0.
6. Input injection: prefer libei (MIT)/xdotool (BSD); call ydotool (AGPL) only as an external binary; dogtail only in tests.
7. D-Bus: dasbus (LGPL, GLib-native, fits GTK main loop) or jeepney/dbus-fast (MIT, pure Python/asyncio); dbus-python needs libdbus build.

---
## PART B — HCI research on proactive help and interruption

### B.1 Lumière (Horvitz, Breese, Heckerman, Hovel, Rommelse, UAI 1998, pp. 256–265)
Source: https://arxiv.org/abs/1301.7385 (full text read via PDF); https://erichorvitz.com/lumiere.htm
- Bayesian networks over user goals; inferred P(user needs assistance) and P(goal) from actions + free-text query; persistent competency profiles.
- **Evidence classes** (quoted categories from the paper):
  - *Search*: "Repetitive, scanning patterns" — exploring multiple menus, scrolling through text, "mousing over and clicking on multiple non-active regions".
  - *Focus of attention*: selecting/dwelling on objects or document regions.
  - *Introspection*: "A sudden pause after a period of activity or a significant slowing of the rate of interaction."
  - *Undesired effects*: undo, or "closing a dialog box shortly after it is opened without invocating an operation".
  - *Inefficient command sequences*: doing something the long way when a shortcut exists.
  - *Domain-specific syntactic/semantic content*.
  - Events were turned into time-windowed variables, e.g. "performed action x less than y seconds ago" / "dwelled for at least t seconds".
- **Autonomous offer mechanics**: when P(need help) exceeds a **user-specified threshold**, a small window shows the inferred help; it has a **"volume control"** to change that threshold; if the user ignores it, it **times out "after a brief apology"**, and "will not be offered again until there is a change in the most likely topics". They also tried cost-benefit thresholds based on how much the user wants alerts. Example trigger: user searched several menus, selected the whole spreadsheet, and paused (Fig. 9).
- **How the shipped Office '97 Assistant differed** (same paper, section on Office Assistant): broader but shallower models; **no persistent user profile, no competency reasoning; no rich combinations of events over time** — only "a small set of relatively atomic user actions" and a small queue of recent events; words and events analysed separately; and "the automated facility of providing assistance based on the likelihood that a user may need assistance or on the expected utility of such autonomous action **was not employed**" — inference results were used only when the user asked explicitly. (The famous unsolicited pop-ups such as "It looks like you're writing a letter" were therefore not Lumière's decision-theoretic offers; they appear to be simpler rule-based triggers — **(unverified; no primary Microsoft source found)**.)
- Aftermath: Office XP (2001) **turned the Assistant off by default**, and marketed that change; removed entirely in Office 2007 — https://en.wikipedia.org/wiki/Office_Assistant (secondary); Microsoft archive on defaults https://learn.microsoft.com/en-us/archive/msdn-magazine/2011/august/don-t-get-me-started-the-power-of-the-default .
- **Swartz, "Why People Hate the Paperclip: Labels, Appearance, Behavior, and Social Responses to User Interface Agents"** (Stanford Symbolic Systems honors thesis, 2003 — year unverified). Findings (via secondary summaries): labels attached to an agent shape how users perceive it; appearance and behaviour (character embodiment, social etiquette) matter especially combined with labels; beginners were unclear what the Assistant was for, and even experienced users credited it with things the software did (e.g. auto-formatting). https://jerz.setonhill.edu/?p=1399 ; full text reportedly at xenon.stanford.edu/~lswartz/paperclip (unverified).
- **Whitworth, "Polite computing", Behaviour & Information Technology 24(5):353–363, 2005, DOI 10.1080/01449290512331333700**: politeness = "offering the locus of control of a social interaction to another party"; four requirements: **respect user choice, disclose identity, offer useful choices, remember past choices**; "Mr. Clippy" cited as impolite software users disable. https://digitalcommons.njit.edu/fac_pubs/19576 (abstract).

### B.2 Horvitz, "Principles of Mixed-Initiative User Interfaces", CHI 1999, pp. 159–166
Source: https://www.erichorvitz.com/chi99horvitz.pdf (full text read); https://www.microsoft.com/en-us/research/publication/principles-mixed-initiative-user-interfaces/
- 12 critical factors (paraphrased from the paper): (1) significant value-added automation; (2) consider uncertainty about goals; (3) consider the user's attention in timing (defer when less distracting); (4) infer ideal action from costs, benefits, uncertainty (expected utility); (5) use dialog to resolve key uncertainties, weighing the cost of bothering; (6) efficient direct invocation **and termination**; (7) minimise cost of poor guesses — "appropriate timing out and natural gestures for rejecting"; (8) scope precision to uncertainty — "doing less but doing it correctly" (graceful degradation); (9) efficient collaboration to refine results; (10) socially appropriate behaviour / courtesies; (11) working memory of recent interactions; (12) keep learning by observing.
- Decision theory: a threshold probability **p\*** above which acting has higher expected utility than not acting; adding a dialog option yields two thresholds, **p\*¬A,D** (no action vs ask) and **p\*D,A** (ask vs act). Thresholds can be set directly by designers/users, and shift as the context changes costs.
- LookOut timing data: preferred dwell before an automated scheduling offer is a **sigmoid of message length** — roughly 2–8 s across 0–2,500 bytes for a sample user (Fig. 7); the system can learn a per-user timing model (piecewise linear regression) or use a fixed user-set delay.

### B.3 Interruption cost
- **Adamczyk & Bailey, CHI 2004 "If Not Now, When?"** (pp. 271–278): interrupting at the best moment gave a **56% reduction in annoyance** vs the worst moment; best points also gave less frustration and time pressure, lower mental effort, felt "more respectful"; **no improvement in objective measures**. Best moments lie **between coarse breakpoints** of the task model. https://hci.rwth-aachen.de/materials/conferences/CHI2004/1p271.pdf
- **Iqbal & Bailey (CHI 2008; OASIS, TOCHI 2010)**: scheduling notifications at detected breakpoints **reduces frustration and reaction time** versus immediate delivery; OASIS detects three breakpoint granularities with reasonable accuracy. https://www.interruptions.net/literature/Iqbal-TOCHI10.pdf ; https://www.microsoft.com/en-us/research/?p=161181 (exact numbers not extracted — unverified).
- **Mark, Gudith & Klocke, CHI 2008 "The Cost of Interrupted Work: More Speed and Stress"**: interrupted people completed tasks **faster** but with **more stress, frustration, time pressure and effort**. https://www.ics.uci.edu/~gmark/chi08-mark.pdf
- "23 min 15 s to resume interrupted work; 81.9% resumed same day" — reported from Mark's UCI KM Forum 2008 slides via a search snippet; the PDF URL (isr.uci.edu/events/KM-Forum-2008/...) now 404s and the 2005 "No task left behind" paper was not checked — **(unverified)**.

### B.4 Struggle / frustration signals
- **Rage clicks**: Microsoft Clarity: "clicks multiple times in a clustered area in rapid succession" — **no numeric threshold published**: https://learn.microsoft.com/en-us/clarity/insights/semantic-metrics . FullStory states its exact definition is proprietary: https://help.fullstory.com/hc/en-us/articles/360020624154 . Practitioner heuristic (not vendor): ~3 clicks within 500–1000 ms on the same element: https://www.parallelhq.com/blog/what-rage-click . Hotjar threshold: not found **(unverified)**. Related signals in the same vendor docs: dead clicks, error clicks, thrashed cursor, excessive scrolling, quick backs.
- **Mouse kinematics and emotion**: Hibbeln et al., MIS Quarterly 41(1) 2017: negative emotion **increases cursor distance and lowers speed**; inference accuracy **81.7%** in a shopping-site study (n=126). Authors linked to Neuro-ID (commercial). https://experts.arizona.edu/en/publications/how-is-your-user-feeling-inferring-emotion-through-human-computer/
- **Programming struggle metrics**: Jadud's Error Quotient (2006; repeated consecutive compile errors); Watwin (Watson, Li, Godwin; adds time-to-fix, penalties 1/15/25 relative to population); Repeated Error Density (Becker, ITiCSE 2016; less context-dependent, works on short sessions). 2024 comparison: EQ explained CS1 grade variance best; EQ/Watwin weak on first-week data. https://arxiv.org/abs/2404.05988 ; https://dx.doi.org/10.1145/2899415.2899463 . Analogue for Ya-Bro: "same error dialog / same failed action repeated N times" density.
- **CHI 2026 "Sensing What Surveys Miss"** (Liu et al., arXiv 2602.00880): EDA + mouse movement personalised classifiers with rule-based threshold adaptation trigger LLM help; n=32; correctly-timed help **+21% response accuracy**, false-negative rate **50.9% -> 22.9%**. https://arxiv.org/abs/2602.00880

### B.5 Help-seeking in software learning (Autodesk Research)
- **ToolClips** (Grossman & Fitzmaurice, CHI 2010): video-augmented tooltips; users completed **7x as many unfamiliar tasks** vs a commercial online help system, and were faster a week later. https://research.autodesk.com/app/uploads/2023/03/toolclips-an-investigation-of.pdf_recbnW20cbxDanglq.pdf
- **Ambient Help** (Matejka, Grossman, Fitzmaurice, CHI 2011): automatic context-sensitive learning resources shown while the user works (peripheral display, (unverified detail)); found more helpful information **without hurting productivity**. https://research.autodesk.com/app/uploads/2023/03/ambient-help.pdf_recdxgDIEWhYal4JV.pdf
- **CommunityCommands** (Matejka, Li, Grossman, Fitzmaurice, UIST 2009, pp. 193–202): collaborative-filtering command recommendations; extended in Li et al. TOCHI 2011 (6-week deployment). https://research.autodesk.com/app/uploads/2023/03/communitycommands-command-recommendations-for.pdf_recZiyrKCEIuGQLZh.pdf
- **Patina** (Matejka et al., CHI 2013 (year unverified)): app-independent usage heatmaps without instrumenting the app. https://research.autodesk.com/app/uploads/2023/03/patina-smart-heatmaps-for.pdf_recCytk45J1290FTT.pdf

### B.6 Proactive LLM assistants (2024–2026)
- **"Need Help? Designing Proactive AI Assistants for Programming"** (Chen, Zhu, Zhao, Mozannar, Sontag, Talwalkar; CHI 2025, DOI 10.1145/3706598.3714002) — **verified**. https://arxiv.org/html/2410.04596v2
  - Triggers: no suggestions while user types/chats; suggestion after **5 s idle**; immediate debugging suggestion **on run/submit with error**; cooldown **one suggestion per 20 s**. (Values from a 4-person pilot.)
  - n=65. Productivity vs baseline chat: Suggest **+18%** (p=0.002), Suggest+Preview +12.1%, Persistent Suggest (5 s cooldown, 5 suggestions) +11.6%.
  - Preference over baseline: **90%** (Suggest), 80% (Suggest+Preview), **47%** (Persistent) — more frequent = "distracting and annoying" despite productivity gains.
  - Guidelines: easy evaluate/accept/dismiss; contextual relevance; learn from feedback; time to context; **let users decide when proactivity is on**; adjust amount of information.
- **Proactive Agent / ProactiveBench** (Lu et al., ICLR 2025, arXiv 2410.12361): 6,790 train / 233 test events (synthetic, LLM-generated environment); fine-tuned Qwen2-7B reaches **66.47% F1** at deciding whether to offer help; reward model 91.8% agreement with humans. Shows "when to help" is hard even for frontier LLMs. https://arxiv.org/html/2410.12361v3
- **ProAgentBench** (Tang et al., arXiv 2602.04482, Feb 2026, preprint): **28,000+ events from 500+ hours of real user sessions**; splits proactive help into **timing prediction** and content generation; real data beats synthetic; long-term memory helps. Dataset released (anonymous repo; licence not stated). https://arxiv.org/abs/2602.04482
- Microsoft research on proactive Copilot timing: not located this session **(unverified)**.

### B.7 Evaluation datasets
- No public desktop dataset with struggle/confusion labels on real GUI interaction logs was found. Nearest:
  - Confusion detection dataset of mouse + eye movements, UMAP 2020 (60 participants; availability unclear): https://unpaywall.org/10.1145%2F3386392.3399289
  - DUX keyboard/mouse emotion dataset (2023, i-com): https://dx.doi.org/10.1515/icom-2023-0014 (labels include frustration? unverified)
  - ProAgentBench (real sessions, timing labels): above.
  - Rico (Deka et al., UIST 2017) Android UI + interaction traces, no struggle labels: http://interactionmining.org/rico (unverified, not fetched).
- Implication: Ya-Bro needs its own opt-in, local, labelled logging ("did you want help here?" responses become labels).

### B.8 Implications for Ya-Bro (struggle-detector ADR)
1. **Signals** (Lumière-validated classes, all observable via AT-SPI/X11/libei): repetitive menu/dialog search without activation; pause after activity; undo / dialog opened-then-cancelled; repeated identical failing action or error (RED analogue); rage clicks (start ~3 clicks < 1 s within a small radius, tune); cursor thrash / longer slower paths (Hibbeln).
2. **Decision**: expected-utility with two thresholds (p\*ignore→offer, p\*offer→act); Ya-Bro should mostly stop at "offer" (dialog), never auto-act — matches Horvitz (5)(8).
3. **Timing**: offer at breakpoints (after a dialog closes, after an error, after idle ~5 s), never mid-typing (Adamczyk & Bailey 56% less annoyance; Need-Help 5 s idle rule).
4. **Rate limit and back-off**: minimum cooldown (Need-Help used 20 s; shortening to 5 s halved preference to 47%); after a dismissal, don't re-offer for the same inferred topic until it changes (Lumière rule); escalate cooldown on repeated dismissals (design inference, no published constant found).
5. **Graceful exit**: unobtrusive offer that times out on its own with an apology-free/neutral fade (Lumière timed out with an apology); one-key dismiss; "volume control" sensitivity slider and a global off switch (Need-Help guideline 6; Clippy's lesson: off-by-default came only after backlash).
6. **Learning**: record accept/dismiss as labels to adapt per-user thresholds (Horvitz factor 12; CHI 2026 personalised thresholds cut false negatives 50.9%→22.9%).
7. **Expect modest accuracy**: best ProactiveBench F1 ~66%; design for being wrong cheaply.

---
## PART C — Voice for Arabic + English

### C.1 Speech-to-text
- **Open Universal Arabic ASR Leaderboard** (Wang, Alhmoud, Alqurishi, arXiv 2412.13788, Dec 2024; live at https://huggingface.co/spaces/elmresearchcenter/open_universal_arabic_asr_leaderboard ; code https://github.com/Natural-Language-Processing-Elm/open_universal_arabic_asr_leaderboard). Test sets: SADA (10 dialects, Saudi), Common Voice 18 (25), MASC clean/noisy, MGB-2 (broadcast, mostly MSA), Casablanca (8 dialects, added 2025-01). Paper Table 1 (WER, 5 sets, before Casablanca) https://arxiv.org/html/2412.13788v1 :

  | Model | Avg | SADA | CV18 | MASC clean | MASC noisy | MGB-2 |
  |---|---|---|---|---|---|---|
  | whisper-large-v3 | 29.87 | 55.96 | 17.83 | 24.66 | 34.63 | 16.26 |
  | whisper-large-v3-turbo | 33.30 | 60.36 | 25.73 | 25.51 | 37.16 | 17.75 |
  | whisper-large-v2 | 34.04 | 57.46 | 21.77 | 27.25 | 38.55 | 25.17 |
  | whisper-medium | 39.60 | 67.71 | 28.07 | 29.99 | 42.91 | 29.32 |
  | whisper-small | 52.18 | 87.34 | 41.79 | 37.82 | 53.28 | 40.66 |
  | nvidia conformer-ctc-large-ar (+LM), #1 then | 25.71 | 44.52 | 8.80 | 23.74 | 34.29 | 17.20 |

  - Takeaway: turbo costs ~3.4 WER points avg vs large-v3 on Arabic (and +8 on CV); medium/small degrade sharply.
- **Leaderboard snapshot 2026-06-23** (with Casablanca), via Cohere's post: Cohere Transcribe Arabic 25.87 avg (Casablanca 49.71); OmniASR-LLM-7B 28.32; Whisper large-v3 **36.86** (Casablanca **71.81**). Cohere Transcribe Arabic: **2B params, Apache-2.0**. **Egyptian dialect** (Cohere internal eval, not leaderboard): Cohere Transcribe Arabic 16.24, OmniASR-LLM-7B 16.47, **Whisper large-v3 30.60**. https://huggingface.co/blog/CohereLabs/cohere-transcribe-arabic-07-2026-release (vendor source).
- Other 2026 models added to the leaderboard: Qwen3-ASR-0.6B/1.7B, VibeVoice-ASR-7B, Gemma-4-E2B/E4B, Meta omnilingual-asr, Voxtral (repo README updates list).
- Whisper large-v3 on FLEURS Arabic 9.6% WER, CV15 15.1% (as cited in arXiv 2406.04512 — secondary): https://arxiv.org/html/2406.04512v1
- **Code-switching (Egyptian Arabic–English)**: ArzEn corpus — 12 h spontaneous interviews, 38 speakers (Hamed et al., LREC 2020) https://aclanthology.org/2020.lrec-1.523 ; best hybrid+E2E system **30.6% WER** (Hamed et al. 2021) https://arxiv.org/abs/2108.12881 ; ArzEn-LLM (2024) uses Whisper for CS ASR https://arxiv.org/abs/2406.18120 ; SAGE (2025) reports fine-tuned Whisper-base ~68% WER on ArzEn test (table hard to parse — unverified) https://arxiv.org/pdf/2506.22143 . Code-switched technical speech ("open the Settings, ya3ni...") is a known weak spot; expect high WER on English terms embedded in Arabic.
- **NVIDIA**: Canary-1B-v2 / Parakeet-TDT-0.6B-v3 support 25 **European** languages — no Arabic (https://arxiv.org/html/2509.14128v2). Arabic options: NeMo `stt_ar_fastconformer_hybrid_large_pcd_v1.0` (with diacritics) https://docs.nvidia.com/nemo/speech/nightly/asr/asr_checkpoints.html ; older Riva Canary-1B lists ar-AR (NGC) https://catalog.ngc.nvidia.com/orgs/nvidia/riva/models/canary-riva-1b/- ; Parakeet-CTC-1.1B "Universal" is on the Arabic leaderboard.
- **Vosk Arabic**: `vosk-model-ar-mgb2-0.4` 318 MB Apache-2.0, WER 16.40 MGB-2 dev (https://alphacephei.com/vosk/models) — MSA broadcast; useful as tiny offline fallback / command grammar, not dialect chat.
- **CPU speed (faster-whisper README, 13 min audio, i7-12700K, 8 threads, beam 5)**: *small* model — faster-whisper int8 **1m42s** (RTF ≈ 0.13), batched int8 51 s; whisper.cpp fp32 2m05s; openai/whisper 6m58s. Large-v2 on RTX 3070 Ti: faster-whisper int8 59 s, batched 16 s. No official CPU large-v3 number (unverified; expect several times slower than small — large-v3 on laptop CPU will not be real-time for interactive turns). https://raw.githubusercontent.com/SYSTRAN/faster-whisper/master/README.md
- **whisper.cpp streaming**: repo ships a `stream` example (sliding window, sample mic every ~0.5 s) (unverified detail; https://github.com/ggml-org/whisper.cpp/tree/master/examples/stream). Whisper is not natively streaming — chunk with VAD.
- **Cloud STT Arabic dialects**:
  - Deepgram Nova-3: Arabic `ar` + 16 dialect codes incl. **ar-EG** (changelog 2026-01-27) https://developers.deepgram.com/changelog/2026/1/27 ; https://deepgram.com/learn/nova-3-arabic-speech-to-text-production-grade-stt
  - Azure Speech: 18 Arabic STT locales incl. **ar-EG**, real-time + batch; ar-EG also supports multilingual refinement and "Azure LLM Speech" https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=stt
  - ElevenLabs Scribe: vendor pages give Arabic FLEURS WER 11.1% (other locale page says 3.1%) — inconsistent, vendor-reported https://elevenlabs.io/speech-to-text/arabic
  - Google Chirp 3, OpenAI gpt-4o-transcribe Arabic dialect numbers: **not found (unverified)**.

### C.2 Text-to-speech (Arabic)
- **Piper**: only `ar_JO-kareem` (low, medium); Jordanian, single male speaker; dataset unlicensed + lessac lineage (see Part A). https://huggingface.co/rhasspy/piper-voices/raw/main/voices.json
- **MMS-TTS ara** (Meta): **CC-BY-NC-4.0** — non-commercial https://huggingface.co/facebook/mms-tts-ara
- **XTTS-v2**: supports Arabic (17 languages) but **Coqui Public Model License**: "This license allows only non-commercial use of a machine learning model and its outputs." (https://huggingface.co/coqui/XTTS-v2/blob/main/LICENSE.txt). coqui.ai/cpml now returns 404; Coqui the company shut down (unverified). https://huggingface.co/coqui/XTTS-v2
- **Chatterbox Multilingual** (Resemble AI): 23 languages **incl. Arabic**, **MIT**, but README now says it is "retired research and is no longer maintained"; all output carries Resemble's Perth **neural watermark**. Nano variant "3x faster than realtime on 8 CPU cores". https://github.com/resemble-ai/chatterbox ; HF tag MIT https://huggingface.co/ResembleAI/chatterbox
- **Kokoro-82M**: **no Arabic** (9 languages). https://huggingface.co/hexgrad/Kokoro-82M/raw/main/VOICES.md
- **Azure**: 16 Arabic locales × 2 voices, incl. **ar-EG-SalmaNeural (F) / ar-EG-ShakirNeural (M)** — Egyptian dialect voices https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts
- **Google Cloud TTS**: Arabic only as generic **ar-XA** (Chirp 3 HD voices e.g. ar-XA-Chirp3-HD-Aoede/Charon); no Egyptian locale found. https://docs.cloud.google.com/text-to-speech/docs/chirp3-hd
- **ElevenLabs**: Eleven v3 lists Arabic among 74 languages; Egyptian-dialect voice availability not confirmed. https://elevenlabs.io/docs/help-center/other/what-languages-do-you-support
- **OpenAI TTS**: per a search snippet of OpenAI's TTS guide (page not fetched — treat as **unverified**): tts-1, tts-1-hd, gpt-4o-mini-tts deprecated, shutting down 2027-01-06, migrate to `gpt-realtime-2.1-mini` via the Realtime API. Arabic support list not extracted (unverified). https://developers.openai.com/api/docs/guides/text-to-speech
- **Diacritization**: Arabic script omits short vowels; deployed TTS commonly runs automatic diacritization before synthesis (arXiv 2311.10771). Tools: **libtashkeel** (Rust + Python, MSA-trained; Piper once loaded a libtashkeel ONNX model before phonemization — current status unverified) https://github.com/mush42/libtashkeel ; Tashkeel-v3 reports 2.85% DER on SadeedDiac-25 https://huggingface.co/gyoom-sa/Tashkeel-v3 . QCRI 2026 ("More Data, Fewer Diacritics") finds more data partly compensates for missing diacritics https://arxiv.org/html/2603.01622v1 . Egyptian colloquial text has no standard diacritization — cloud neural voices handle undiacritized input internally. Practical: have the LLM emit MSA-ish or lightly diacritized text for offline engines.

### C.3 Wake word "Ya bro"
- **openWakeWord**: "Currently, openWakeWord only supports English", because training data is synthesised with English TTS; trained 100% on synthetic speech; recommends "several thousand" positives and used ~30,000 h of negative data; Colab trains a basic model in <1 h. Target performance: **<0.5 false accepts/hour and <5% false rejects**, measured on the ~5.5 h DiPCo far-field corpus. Optional Silero VAD gate and Speex noise suppression reduce false accepts; per-speaker "custom verifier" second stage available. https://raw.githubusercontent.com/dscripka/openWakeWord/main/README.md
  - "Ya bro" is phonetically close to English syllables (/jɑː broʊ/), so English-TTS synthetic training is plausible; Arabic-accented realisations should be added (record real samples, or use Arabic-capable TTS such as Azure ar-EG voices for synthetic positives — check those services' ToS for training use (unverified)).
  - Short two-syllable phrases have higher false-accept risk than 3–4 syllable phrases (general wake-word guidance; unverified primary source).
- **microWakeWord** (Apache-2.0, ESPHome, TFLite micro) — alternative trainer (https://github.com/kahrendt/microWakeWord).
- **Porcupine**: custom wake words were trainable in Arabic on Picovoice Console (Porcupine v2.2.0 release notes, Apr 2023: "Added language support for Arabic, ..." — https://github.com/Picovoice/porcupine), **but** free tier reportedly discontinued 2026-06-30 and engine needs a valid online-checked AccessKey (HA forum, secondary). Not suitable.
- **HA community suggestion**: "local-wake" for non-English keywords (from same forum thread; unverified).

### C.4 Barge-in, echo cancellation, latency
- **PipeWire `libpipewire-module-echo-cancel`**: creates capture/source/sink/playback nodes; default and only listed backend `aec/libspa-aec-webrtc` (WebRTC AEC); configured via `~/.config/pipewire/pipewire.conf.d/*.conf`; `aec.args` passes backend args; `monitor.mode` can use the default sink's monitor instead of a dedicated sink; `node.latency` e.g. 1024/48000. https://docs.pipewire.org/page_module_echo_cancel.html
  - For barge-in, Ya-Bro's TTS must play into the echo-cancel **sink** (or use monitor.mode) and its STT/VAD must read the echo-cancel **source**; otherwise the assistant hears itself. The module is a user-level config change (persistent config -> needs user consent per safety rules); alternative is in-app AEC (e.g. WebRTC APM via `webrtc-audio-processing` bindings) (unverified option).
- **Latency targets**:
  - Human turn gaps: cross-language mean ~200 ms; languages differ within ±250 ms (Stivers et al., PNAS 2009) https://pubmed.ncbi.nlm.nih.gov/19553212/ ; https://pmc.ncbi.nlm.nih.gov/articles/PMC2705608
  - Speech production latency ~600 ms+ for a new word, so humans pre-plan (review) https://pmc.ncbi.nlm.nih.gov/articles/PMC4464110
  - Engineering target: **~800 ms voice-to-voice** called "a good target" by Daily's Pipecat voice-AI primer https://daily-co.github.io/voice-ai-primer-web ; AWS "800ms rule" budget article https://builder.aws.com/content/3JDFAfXBiuwPP5MPzgf4RUWSAIp/the-800ms-rule-budgeting-latency-for-a-real-time-voice-agent-on-aws . Typical budget split (blog-level estimates): end-of-utterance detection 200–300 ms, final STT 100–200 ms, LLM TTFT 300–600 ms, TTS first audio 90–250 ms, network 50–150 ms. LLM TTFT dominates; stream LLM→TTS sentence by sentence.

### C.5 Implications for Ya-Bro
1. **Offline Arabic STT default**: Whisper large-v3 (not turbo) is the best Whisper for Arabic but is *likely* too slow for interactive laptop-CPU use (inferred: no CPU large-v3 benchmark found; the only CPU number is the small model at RTF≈0.13 on a desktop i7-12700K); small/medium Whisper are poor on Arabic (52%/40% avg WER). Realistic: cloud STT for Arabic (Azure ar-EG or Deepgram nova-3 ar-EG), local Whisper for English and as private fallback; evaluate Cohere Transcribe Arabic (2B, Apache-2.0) and Qwen3-ASR as local Arabic candidates (benchmarks on Egyptian are vendor-reported).
2. **Arabic TTS**: no good permissive offline Egyptian voice exists. Cloud: Azure ar-EG Salma/Shakir is the only verified Egyptian-dialect neural pair. Offline fallback: Chatterbox multilingual (MIT, Arabic, but unmaintained + watermark) or Piper ar_JO-kareem as an opt-in user download.
3. **Diacritize** before any offline Arabic TTS (libtashkeel) or prompt Claude to produce diacritized MSA for TTS.
4. **Wake word**: train our own openWakeWord "ya bro" model (synthetic + recorded Arabic-accented positives), gate with Silero VAD; accept target ≤0.5 FA/h; push-to-talk hotkey as the primary trigger.
5. **Barge-in**: depend on PipeWire echo-cancel (documented opt-in setup) and stop TTS on VAD speech onset from the AEC source.
6. **Latency budget**: target ≤800 ms to first audio for English; Arabic via cloud likely slower — show "listening/thinking" state in overlay.

---
## PART D — Packaging

### D.1 Flatpak and AT-SPI
- `flatpak run` man page: "--a11y-bus: Allow access to the accessibility bus. **This is the default, except when run with --sandbox**." Also `--a11y-own-name=NAME` to own names on the a11y bus. https://docs.flatpak.org/en/latest/flatpak-command-reference.html
- **But the default a11y access is a filtered proxy**, not the raw bus. Flatpak source (`common/flatpak-run-dbus.c`, https://raw.githubusercontent.com/flatpak/flatpak/main/common/flatpak-run-dbus.c) runs xdg-dbus-proxy with `--filter --sloppy-names` and only allows: Registry `EventListenerRegistered/Deregistered` broadcasts, `Socket.Embed/Unembed` on the root, `GetRegisteredEvents`, and DeviceEventController `GetKeystrokeListeners/GetDeviceEventListeners/NotifyListenersSync/Async`. This is what an *accessible application* needs to expose its own tree; it does **not** let a sandboxed client walk other applications' trees (what Ya-Bro, like a screen reader, needs). (Analysis from source.)
- Workaround seen in the wild: `--no-a11y-bus` + `--talk-name=org.a11y.Bus` (get real bus address from the session bus) made an app work with Orca — KDE bug https://bugs.kde.org/show_bug.cgi?id=452132 ; GNOME Builder issue suggests the same permission https://gitlab.gnome.org/GNOME/gnome-builder/-/issues/1346 . Reaching the real socket may also need filesystem access to `$XDG_RUNTIME_DIR/at-spi/` (unverified).
- Security context: GNOME notes the a11y bus has **no access control** — any client can see/drive others — so it can't simply be granted to sandboxed apps; "Newton" (Wayland-native a11y) is meant to let sandboxed apps be accessible without the AT-SPI exception. https://wiki.gnome.org/Projects/GTK/Accessibility ; https://blogs.gnome.org/a11y/
- Default session-bus policy: app may own only `$FLATPAK_ID` names and talk to `org.freedesktop.DBus` and `org.freedesktop.portal.*`; "It is recommended to use the minimum required talk-name permissions"; Flathub "places requirements on which permissions can be used". https://docs.flatpak.org/en/latest/sandbox-permissions.html
- **Flatpak + X11/XTest**: with `--socket=x11` (or `fallback-x11` when no Wayland) the app is an ordinary X client, so XTest injection and global screen capture work as for any X client (X11 has no client isolation — general X11 knowledge; Flatpak docs don't call it out). `--socket=wayland --socket-if=x11:!has-wayland` pattern in docs. https://docs.flatpak.org/en/latest/flatpak-command-reference.html
- **Flatpak + layer-shell**: no documentation found on whether Flatpak filters `zwlr_layer_shell_v1` **(unverified)**; Flatpak currently exposes the Wayland socket wholesale (unverified), so the limit is compositor support. gtk4-layer-shell works only on compositors supporting the protocol (wlroots e.g. Sway, Smithay e.g. COSMIC; KDE KWin supports it (unverified)); **not GNOME Wayland, not X11**. https://github.com/wmww/gtk4-layer-shell ; Debian copy of README https://sources.debian.org/src/gtk4-layer-shell/1.3.0-1/README.md
- Portals relevant to Ya-Bro (not verified in detail this session): `org.freedesktop.portal.Background` (autostart request for sandboxed apps), `ScreenCast`/`Screenshot`, `RemoteDesktop` (input injection with user consent), `InputCapture`, `GlobalShortcuts` — see https://flatpak.github.io/xdg-desktop-portal/docs/ (unverified).

### D.2 Snap
- Snapcraft forum: plug **`desktop-legacy`** "to allow your app to talk to at-spi" https://forum.snapcraft.io/t/how-do-i-enable-access-to-at-spi-in-my-snap/11115 ; but an a11y-tool developer reports desktop-legacy etc. "do not allow enough access to the AT-SPI accessibility framework" for an app that works with other applications under strict confinement — they requested classic confinement https://forum.snapcraft.io/t/classic-confinement-request-snippetpixie/11186 . Proposal to split a `desktop-accessibility` interface (status unverified) https://forum.snapcraft.io/t/desktop-interfaces-moving-forward/1652 ; AppArmor bug: "org.a11y.atspi is not designed for application isolation" https://bugs.launchpad.net/apparmor/+bug/1727887/comments/1 ; at-spi socket moved from abstract namespace to a path socket, breaking desktop snaps' a11y (2021) https://forum.snapcraft.io/t/accessibility-support-failing-for-desktop-snaps-on-recent-distro-releases/27274 . No dedicated "accessibility" interface verified.

### D.3 PyGObject in pip/pipx/uv venvs
- PyPI PyGObject 3.58.1 ships **only an sdist** (`pygobject-3.58.1.tar.gz`); pycairo 1.29.2 ships Windows wheels + sdist only — **no Linux wheels** (checked via PyPI JSON https://pypi.org/pypi/PyGObject/3.58.1/json , https://pypi.org/pypi/pycairo/1.29.2/json). Building needs a C toolchain and dev headers: `sudo apt install libgirepository-2.0-dev gcc libcairo2-dev pkg-config python3-dev gir1.2-gtk-4.0` https://pygobject.gnome.org/getting_started.html . Since 3.52, girepository-2.0 => **GLib >= 2.80** https://download.gnome.org/sources/pygobject/3.52/pygobject-3.52.1.news ; manylinux wheels blocked by old GLib in manylinux images https://gitlab.gnome.org/GNOME/pygobject/-/issues/590 .
- Typelibs (`gir1.2-gtk-4.0`, `gir1.2-atspi-2.0`, gtk4-layer-shell's typelib) always come from the system regardless of venv.
- Alternatives: use distro `python3-gi python3-gi-cairo` and create the venv with **`--system-site-packages`** (`python -m venv`, `uv venv --system-site-packages` — flag confirmed in local `uv venv --help`; `pipx install --system-site-packages` (per pipx docs, unverified locally)). pyatspi is not on PyPI at all -> system package `python3-pyatspi` is mandatory, which pushes towards system-site-packages.

### D.4 AppImage + GTK4
- AppImages run only on the glibc version they were built on **or newer** (Rocky Linux forum example) https://forums.rockylinux.org/t/appimage-errs-on-launch/20757 ; GTK4/Qt6 are "specially problematic" because old build distros lack them https://pkgforge-dev.github.io/Anylinux-AppImages/HOW-TO-MAKE-THESE.html ; AppImage excludelist warns about bundling GLib causing symbol errors in libpango etc. https://raw.githubusercontent.com/probonopd/AppImages/master/excludelist ; appimage-builder issue "Bundling gtk in AppImage causes errors in some distros". Also bundling AT-SPI/GI typelibs + Python makes AppImage heavy. Verdict: poor fit for GTK4+PyGObject.

### D.5 Debian packaging (dh-python / pybuild)
- Build-Depends `dh-sequence-python3` (saves `--with python3`); `debian/rules`: `export PYBUILD_NAME=foo` + `dh $@ --buildsystem=pybuild`; `dh_python3` fills `${python3:Depends}`; build-deps must be listed by hand; for programs install to a private dir: `PYBUILD_INSTALL_ARGS=--install-lib=/usr/share/packagename/ --install-scripts=/usr/share/packagename/`. https://wiki.debian.org/Python/Pybuild . pyproject.toml builds use `pybuild-plugin-pyproject` (per pybuild manpage, unverified this session).
- Native packages get `python3-gi`, `gir1.2-gtk-4.0`, `python3-pyatspi`, `gir1.2-gtk4layershell-1.0` as plain Depends — the cleanest dependency story.

### D.6 XDG autostart
- Files in `$XDG_CONFIG_DIRS/autostart` (default `/etc/xdg/autostart/`) and `$XDG_CONFIG_HOME/autostart` (default `~/.config/autostart/`); same filename -> most important dir wins (user overrides system); `Hidden=true` disables (create same-named user file with `Hidden=true` to disable a system entry); `OnlyShowIn`/`NotShowIn` (only one allowed); `TryExec` not found -> don't start. https://specifications.freedesktop.org/autostart/latest/
- Sandboxed apps should request autostart via the Background portal instead of writing the file (unverified detail).

### D.7 Implications for Ya-Bro
1. **Flatpak is a poor primary channel**: default a11y proxy only lets an app be *accessible*, not *read others*; Ya-Bro would need `--talk-name=org.a11y.Bus` (+ maybe `--no-a11y-bus` and runtime-dir access) plus X11 socket for XTest — effectively unsandboxed and likely to face Flathub review friction (Flathub policy specifics unverified).
2. **Snap**: strict confinement insufficient for cross-app AT-SPI; classic confinement needed.
3. **Primary distribution**: native packages (deb/rpm/AUR) + `pipx`/`uv tool` install with `--system-site-packages` on top of distro `python3-gi`, `python3-pyatspi`, typelibs. Document the system packages per distro.
4. Avoid AppImage.
5. Autostart: write `~/.config/autostart/ya-bro.desktop` only on explicit user opt-in; honour `Hidden=true`.
6. Layer-shell overlay only on wlroots/KDE/COSMIC; GNOME Wayland needs a different overlay strategy (and X11 uses normal override-redirect windows).

---
