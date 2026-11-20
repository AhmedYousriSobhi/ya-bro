# ADR-0011: Voice pipeline (push-to-talk, wake word, VAD, STT, TTS, barge-in; Arabic and English)

- Status: Proposed. The Arabic STT and TTS engine choice is **not decidable yet**; spike S8 decides it.
- Date: 2026-11-20
- Issue: #13
- Depends on: ADR-0003, ADR-0014, ADR-0019, ADR-0020
- Target release: v0.2 (SPEC), text-only before that

## Context
The maintainer speaks Arabic, likely Egyptian dialect, and will code-switch with English technical terms ("eh, open el Settings…").

### Speech-to-text ([factsheet.md C.1](../research/factsheet.md); [non-ai-tools.md §11](../research/non-ai-tools.md))

Open Universal Arabic ASR Leaderboard, average WER over 5 test sets (paper, Dec 2024):

| Model | Avg WER |
|---|---|
| Whisper large-v3 | 29.87 |
| Whisper large-v3-turbo | 33.30 |
| Whisper small | 52.18 |
| NVIDIA Conformer-CTC + LM | 25.71 |

Egyptian-dialect figures, from two sources that should not be merged:
- **Leaderboard, SADA Egyptian subset:** Whisper large-v3 59.28, large-v3-turbo 63.01, large-v2 48.44, NVIDIA Conformer-CTC 40.97.
- **Cohere's own vendor-reported Egyptian set:** Whisper large-v3 30.60, Cohere Transcribe Arabic (2B, Apache-2.0) 16.24.

Other STT facts:
- Arabic–English code-switching: about **30.6% WER** best on ArzEn (2021).
- Cloud with Egyptian support: **Deepgram Nova-3 `ar-EG`** and **Azure `ar-EG`**.
- Vosk `ar-mgb2` (Apache-2.0, WER 16.4 on broadcast MSA) is useful only for command words.
- distil-whisper, Parakeet v3 and Canary v2 have **no Arabic**.

### Text-to-speech
- Piper moved to `OHF-Voice/piper1-gpl`, which is **GPL-3.0** and embeds espeak-ng.
- Its only Arabic voice, `ar_JO-kareem`, has an **unlicensed dataset and lessac (non-commercial) ancestry**. It must never be bundled.
- Non-commercial weights: XTTS-v2 (CPML), MMS-TTS (CC-BY-NC), F5.
- Chatterbox (MIT, has Arabic) is **retired** and watermarks its output.
- Kokoro has no Arabic.
- **The only verified Egyptian voices are Azure `ar-EG-SalmaNeural` / `ar-EG-ShakirNeural` (cloud).** Google offers only `ar-XA` (MSA).
- Offline Arabic TTS needs diacritization: libtashkeel is built into Piper.

### Wake word
- openWakeWord code is Apache-2.0, but its pretrained models are **CC BY-NC-SA** and English-only.
- A self-trained "ya bro" model is feasible; its target is under 0.5 false accepts per hour.
- Porcupine requires an AccessKey; the free tier reportedly ended 2026-06-30 (secondary source).

### VAD
- Silero (MIT).

### Echo cancellation
- PipeWire `module-echo-cancel` (WebRTC AEC), configured per user.

### Latency target
- About **800 ms voice-to-voice** is the industry target. The LLM's time to first token dominates.

### Hardware
- The maintainer's laptop has an i7-11800H (16 threads), 14 GiB RAM, and an RTX 3050 Mobile (4 GB VRAM).
- No CPU benchmark of large-v3 was found. The small model runs at about 0.13× real time on a desktop i7 (faster-whisper README).

## Decision drivers
- Arabic (Egyptian) accuracy and code-switching.
- Turn latency.
- Privacy, with a local-first preference.
- Licence cleanliness (ADR-0020).
- Barge-in ("stop" while the bro talks).
- Optional: text stays the primary channel.

## Options considered
| Area | Option | For | Against |
|---|---|---|---|
| Trigger | **Push-to-talk hotkey (default)** | Zero false accepts; simple; private | Needs a hand on the keyboard |
| | Wake word "Ya bro / يا برو" (opt-in) | Hands-free, on-brand | Always-on mic; custom training; false accepts on a 2-syllable phrase |
| STT | Local Whisper (faster-whisper / whisper.cpp) | Private, MIT, good English | Arabic dialect WER is high; large-v3 speed on a laptop is unknown |
| | Local Arabic-specialist (Cohere Transcribe Arabic 2B, NVIDIA FastConformer ar) | Best open dialect numbers | Vendor-reported; English and code-switching unknown; size and speed unknown |
| | Cloud (Deepgram / Azure `ar-EG`) | Dialect support, streaming, fast | Audio leaves the machine; cost; account needed |
| TTS | Piper out-of-process (English) | Fast, offline, quality OK | GPL (fine out-of-process); no clean Arabic voice |
| | Azure `ar-EG` neural (Arabic) | The only verified Egyptian voices | Cloud, account, cost |

## Decision
1. **Pipeline as a Home-Assistant-Assist-style chain:** trigger → VAD → STT → (Brain) → TTS.
   - Every engine is a separate **Wyoming** service over a Unix or localhost socket.
   - This keeps GPL engines out of process, isolates native crashes, and lets users reuse existing Wyoming servers.
2. **Trigger.**
   - **Push-to-talk is the default.** The hotkey goes through the `Hotkeys` interface. *Amended for GNOME-first (2026-11-20):* on GNOME (reference) push-to-talk uses the GlobalShortcuts portal (x-d-p-gnome ≥ 48), which has `Activated`/`Deactivated` signals for hold-to-talk; whether x-d-p-gnome emits `Deactivated` on key release is unverified (check in M0). Shell key bindings fire on press only, so they are not used for push-to-talk. KDE (v0.2): `kglobalaccel` D-Bus or the portal. X11 `XGrabKey` only in CI.
   - The global **stop** key goes through the same interface. On GNOME it is bound inside the Shell extension (`Main.wm.addKeybinding`), so it works with no portal dialog and even when core is hung (ADR-0023).
   - The wake word is **opt-in, v0.3**. Use openWakeWord code with a **self-trained "ya bro" model**, trained on synthetic positives plus recorded Arabic-accented samples, gated by Silero VAD.
   - The pretrained NC models are never shipped.
3. **VAD.** Silero VAD for end-of-utterance, with a 500–700 ms silence default, tuned per language.
4. **STT: not decided, spike S8 decides.** Interim plan:
   - **English:** local faster-whisper (CUDA when available, int8). Choose small or large-v3-turbo by measured real-time factor.
   - **Arabic / code-switched:** run the S8 bake-off on the maintainer's own recordings.
   - **Language routing:** by user setting (AR / EN / auto). Auto uses Whisper language ID on the first 2 s, with a bias to the last-used language.
5. **TTS.**
   - **English:** Piper (piper1-gpl) as an out-of-process Wyoming service, with a voice whose licence allows redistribution. Do not use the lessac-derived voices for bundling (factsheet A).
   - **Arabic:** Azure `ar-EG` neural voices as an **opt-in cloud** backend. Offline fallback is a user-downloaded Piper `ar_JO-kareem` with a clear licence notice, or text-only.
   - **Code-switched sentences** are split by script, with English segments spoken by the English voice or kept inline when the cloud voice handles them.
   - **Persona text for TTS:** the Brain emits a TTS-specific variant. It uses short sentences, and either light diacritics (offline) or plain text (cloud).
6. **Barge-in.**
   - `ya-bro doctor` offers to install a PipeWire echo-cancel config snippet. This is consent-gated because it is persistent configuration.
   - TTS plays into the AEC sink; VAD reads the AEC source.
   - Detected speech during TTS ducks, then stops playback.
   - "Stop"/"خلاص"/"بس" is recognised by a tiny local command spotter (Vosk grammar or the KWS model) **without waiting for full STT**, to meet the 500 ms stop target.
7. **Latency budget, English, local STT plus cloud LLM:**

   | Stage | Budget |
   |---|---|
   | End of speech → STT final | 300 ms |
   | LLM first sentence | ≤ 600 ms (streamed) |
   | TTS first audio | ≤ 200 ms |
   | **Target voice-to-voice** | **≤ 1.2 s** at MVP (≤ 0.8 s stretch) |

   The overlay shows "listening / thinking" states within 100 ms.
8. **Privacy.**
   - The mic is open only during push-to-talk or with the wake word enabled (a visible indicator in both cases).
   - Audio is never stored.
   - Cloud STT/TTS is off until the user configures a key, with a one-line disclosure of what is sent.

## Consequences
- **Positive:**
  - A licence-clean default (MIT/Apache STT and VAD, GPL TTS isolated).
  - Honest about Arabic quality.
  - The modular engines let a better Arabic model drop in.
- **Negative:**
  - A good Egyptian Arabic voice requires a cloud account at present.
  - The wake word needs a training effort.
- **Risks:**
  - Arabic STT may be unusable locally on this laptop, forcing cloud for Arabic voice.
  - AEC setup friction.
  - Retirement of vendor APIs.

## Validation plan
Spike **S8 (Arabic voice bake-off)**, before any v0.2 voice work:
- **Data:** 60 utterances from the maintainer, recorded with consent and kept local: 20 English, 20 Egyptian Arabic, 20 code-switched. All are typical Ya-Bro commands and questions.
- **Engines:**
  - faster-whisper large-v3 and large-v3-turbo (GPU and CPU);
  - whisper.cpp;
  - Cohere Transcribe Arabic;
  - NVIDIA FastConformer ar;
  - Deepgram Nova-3 `ar-EG`;
  - Azure `ar-EG`.
- **Metrics:** WER/CER per set, real-time factor on the laptop, and memory.
- **Go for local Arabic:**
  - WER ≤ 25% on Egyptian;
  - WER ≤ 30% on code-switched;
  - real-time factor ≤ 0.3 on the RTX 3050 or ≤ 0.5 on the CPU.

  Otherwise Arabic voice is cloud-only (opt-in) and the README says so.
- **TTS:** an MOS-style listening check by the maintainer (1–5) on 20 persona lines in each candidate voice.
- **Barge-in test:** say "stop" during TTS; it must halt within 500 ms in ≥ 95% of trials with AEC enabled.

## Revisit if
- An open-licence Egyptian TTS voice appears.
- A local Arabic STT passes S8.
- Wyoming proves too limiting for streaming partial results; then consider sherpa-onnx in-process for permissive engines.

## Sources
- [factsheet.md Part C](../research/factsheet.md): Open Universal Arabic ASR Leaderboard https://arxiv.org/abs/2412.13788
- Cohere Transcribe Arabic (vendor): https://huggingface.co/blog/CohereLabs/cohere-transcribe-arabic-07-2026-release
- ArzEn code-switching: https://arxiv.org/abs/2108.12881
- Piper (GPL): https://github.com/OHF-Voice/piper1-gpl · `ar_JO-kareem` model card: https://huggingface.co/rhasspy/piper-voices/raw/main/ar/ar_JO/kareem/medium/MODEL_CARD
- openWakeWord README (licences, English-only, FA targets): https://github.com/dscripka/openWakeWord
- Porcupine free tier report (secondary): https://community.home-assistant.io/t/porcupine-free-tier-shutdown-alternatives-for-home-assistant-voice-users/1012382
- Azure Speech language support (ar-EG STT/TTS): https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support
- Deepgram Nova-3 Arabic dialects: https://developers.deepgram.com/changelog/2026/1/27
- Silero VAD: https://github.com/snakers4/silero-vad
- PipeWire echo-cancel: https://docs.pipewire.org/page_module_echo_cancel.html
- Wyoming: https://github.com/rhasspy/wyoming
- faster-whisper benchmarks: https://github.com/SYSTRAN/faster-whisper
- Voice latency target: https://daily-co.github.io/voice-ai-primer-web
