# Speech to text and text to speech for Hindi, Indian English and Hinglish: low load, no GPU

Agent: SPEECH. Access date for every URL: 2026-11-25. Tags: **P** = page or file opened and read this session; **S** = search snippet only (UNVERIFIED); **claim** = vendor or model-author claim, not independently measured; **EST** = my arithmetic or estimate, with the assumption stated. No emoji, no em dashes.

## 0. Summary

| Question | Short answer |
|---|---|
| Can a free-tier server (Render free, 512 MB, about 0.1 CPU) do STT? | No. Even Whisper tiny needs about 273 MB RAM (whisper.cpp table, P) and on 0.1 CPU would run many times slower than real time (EST in 2.4). Audio would also have to leave the phone. |
| Can the student's phone do STT in the browser? | Yes in principle: Whisper tiny or base as ONNX int8 (about 73 MiB for base, P) in a Web Worker. Stock Whisper tiny/base is useless on Hindi (FLEURS WER 102.3 and 101.1, P). A Hindi fine-tune is required (Collabora whisper-tiny-hindi, CC BY 4.0, 10.1 WER on FLEURS read speech, P). Phone speed is NOT measured anywhere I could find. |
| Is the browser's own `SpeechRecognition` acceptable? | Not by default. It may send audio to a server (MDN, P). On-device mode exists only on desktop Chrome (Android and ChromeOS: "currently do not support", blink-dev May 2026, P). Hindi pack availability: not confirmed. |
| Best TTS for Hindi that is legally usable? | None of the Piper Hindi voices passes a licence check (2 are CC BY-NC-SA, 1 is fine-tuned from lessac and uses the IndicTTS database). Kokoro (Apache 2.0, grade C Hindi voices) and Indic Parler-TTS (Apache 2.0, 0.9B) are usable only to PRE-RENDER static audio offline. Best answer: a human narrator for breathing and grounding scripts, plus the phone's own `speechSynthesis` as an opt-in extra. |
| Is acoustic "emotion" from pitch and energy a real wellbeing signal? | No. It is not valid as built (section 6). Retire it. No diagnosis claim may be made on any speech marker. |
| Does any of this improve outcomes? | No outcome evidence exists for voice input or output in Indian college students. The defensible gains are accessibility, lower typing effort, eyes-closed practice. |

Verdicts:

| Candidate | Verdict |
|---|---|
| Browser dictation with an on-device Hindi Whisper fine-tune, text only saved after the student edits it | **Build later**, after a phone speed test (week 1 of the test plan decides) |
| Keyboard mic key guidance (Gboard, iOS dictation) | **Build now** (zero code, disclose that it is the phone maker's service) |
| `SpeechRecognition` with `processLocally = true`, desktop Chrome only, only if `available()` says "available" | **Build later**, progressive enhancement, tiny |
| Pre-recorded human narration for breathing and grounding | **Build now** |
| `speechSynthesis` "Listen" button, only voices with `localService === true` | **Build now** (cheap, but test on devices) |
| Server STT of any size on the free tier | **Do not build** |
| Hosted STT/TTS (Gemini, Google, Azure, Sarvam, Bhashini) for student audio or text | **Blocked** by constraint 2 |
| MMS (ASR and TTS) | **Blocked**: CC BY-NC 4.0 |
| XTTS v2 | **Blocked**: Coqui Public Model License, non-commercial |
| Piper Hindi voices pratham, priyamvada | **Blocked**: dataset CC BY-NC-SA 4.0 |
| IndicConformer 600M, IndicWhisper | **Research only / later paid server**: best Hindi accuracy, too big for the free tier or a phone |
| Parakeet, Canary | **Do not build**: no Hindi |
| Moonshine | **Do not build**: no Hindi STT |
| Acoustic emotion label (`classify_emotion`) and stored pitch/energy | **Retire** |

---

## 1. What the product does with voice today (code read, P)

| Piece | What it does |
|---|---|
| `static/js/inline_extracted/patient_voice_logs_inline_1.js` | Records with `MediaRecorder` up to 120 s, shows a preview, uploads `new Blob(chunks, {type: 'audio/wav'})` named `voice_log.wav` (line 101). MediaRecorder normally yields WebM/Opus (Chrome) or MP4 (Safari); the label is not a conversion. |
| `app.py:509` `POST /api/upload-voice` | `@login_required`, role patient, 5 per hour. Calls `utils/voice_features.extract_features`, then `get_ai_voice_emotion_analysis`, stores a `VoiceLog` (`filename='not-stored'`, `emotion`, `audio_features` JSON, `ai_analysis`), awards 20 points. Audio is deleted from a temp file. `VoiceLog.transcript` exists and is never filled. |
| `utils/voice_features.py` | librosa `piptrack` mean over all positive pitch bins, RMS mean, ZCR mean, spectral centroid; `classify_emotion`: pitch above 200 Hz and energy above 0.1 = "happy", pitch below 150 and energy below 0.05 = "sad", ZCR above 0.1 = "stressed", 150 to 200 Hz = "calm". |
| `requirements/voice.txt` | librosa is optional and heavy; `render.yaml` and `requirements.txt` do not reference it (grep). If it is not installed, `extract_features` returns `({}, 'neutral')` and every log is "Neutral: Estimated from the sound of your recording only." UNVERIFIED for the live deploy; check the deployed image. |
| Gemini path | `analyze_voice_emotion` goes through `_personal_call`, which is blocked unless `AI_SEND_PERSONAL_TEXT` is on (`ai/service.py:67`, P). Good. |
| `Permissions-Policy` | `microphone=(self)` already set (`utils/security_headers.py:68`). CSP is `script-src 'self' nonce`, `connect-src 'self'`, `media-src 'self' blob:`: in-browser WASM needs `'wasm-unsafe-eval'`, a `worker-src` and the model files served from our own origin (or an added origin). |

Safety gap worth stating: the words a student says in a voice log are never read by anything. No transcript, so the deterministic crisis floor (`ai/severity.py`, `docs/review/generated/crisis_phrases.csv`) sees nothing. A student who says something alarming in a two-minute voice log gets a "tone" label. Browser STT whose text goes through the same floor (after the student sees and edits it) would be strictly safer than today.

---

## 2. STT findings

### 2.1 Table (Hindi, Indian English, Hinglish)

| Candidate | Licence | Size / RAM | Languages | Accuracy (test set; tag) | Runs where | Verdict |
|---|---|---|---|---|---|---|
| OpenAI Whisper tiny, zero-shot | MIT (whisper.cpp repo MIT, P; OpenAI repo licence not re-fetched) | whisper.cpp: 75 MiB disk, about 273 MB RAM (P) | 99 languages | **Hindi FLEURS WER 102.3** (Whisper paper Table 13, P) | CPU, WASM | Unusable for Hindi as is |
| Whisper base, zero-shot | MIT | 142 MiB disk, about 388 MB RAM (P). ONNX int8: encoder 22.1 MiB + decoder 51.2 MiB = **73.3 MiB** (onnx-community/whisper-base, P; model Apache-2.0 per its card) | same | **Hindi FLEURS 101.1** (paper, P) | CPU, WASM | Unusable for Hindi as is |
| Whisper small, zero-shot | MIT | 466 MiB disk, about 852 MB RAM (P). ONNX int8: 88.1 + 149.5 = **237.5 MiB** (P) | same | Hindi FLEURS **38.4** (paper, P). Medium 26.8, large 26.9, large-v2 21.5 | CPU; too big for a phone download or 512 MB | Not for us |
| Collabora whisper-{tiny..large-v2}-hindi (fine-tunes) | tiny card: **CC BY 4.0** (P); other sizes' licences not stated on the blog (P) | tiny 37.8M params (F32 safetensors, so about 150 MB; int8 ONNX not published that I found, EST 40 to 60 MB) | Hindi, Devanagari output | FLEURS Hindi test, WER whisper-norm / Indic-norm: tiny 10.01 / 18.94, base 8.95 / 17.42, small 7.17 / 15.10, medium 6.10 / 13.36, large-v2 5.33 / 13.06 (Collabora blog, P, authors' own eval, beam 5, repetition penalty 1.15, utterances with digits removed) | CPU, WASM after ONNX conversion (we would convert; CC BY 4.0 needs attribution) | **Best candidate for in-browser Hindi.** Read speech only. |
| Oriserve Whisper-Hindi2Hinglish-Swift (base, 72.6M) | Apache-2.0 (P) | about 290 MB F32 (EST from 72.6M x 4 bytes) | Hindi speech to **Roman** Hinglish | claim: FLEURS 35.1, Common Voice 38.7, IndicVoices 65.2 vs stock base 104 to 111, scored against Roman references the authors produced (P). Not comparable with other rows. Trained on about 550 h of proprietary noisy audio, provenance undisclosed | CPU, WASM after conversion | **Research only**: only Roman-output option found; verify on our test set |
| faster-whisper (CTranslate2) int8 | MIT | small int8: about 1,477 MB RAM, 7.6x real time on an i7-12700K with 8 threads (README, S) | as Whisper | n/a (engine) | Server CPU | Not for the free tier |
| whisper.cpp | MIT (P) | see Whisper rows; WASM demos exist (P); 2 to 3x real time for tiny/base on "a modern CPU and browser" (README, S) | as Whisper | n/a | CPU, WASM | Engine option for the browser |
| distil-whisper | MIT | distil-small.en 166M | **English only** | within 4% WER of large-v3 on English (claim, S) | CPU | Indian-accent English not measured; not Hindi |
| Moonshine | MIT for English and all streaming models; legacy non-English (Arabic, Japanese, Korean, Mandarin, Spanish, Ukrainian, Vietnamese) under the non-commercial Community License (P) | tiny/base, small | **No Hindi STT** | n/a | CPU, WASM (sherpa-onnx demo, P) | Do not build for Hindi |
| Vosk small-hi-0.22 | Apache 2.0 (P) | 42 MB | Hindi | WER 20.89 IITM Challenge, 24.72 MUCS (alphacephei, P, authors' numbers) | CPU, streaming, Kaldi | Possible server or WASM fallback; worse than Whisper fine-tunes; no code-mix |
| Vosk hi-0.22 | Apache 2.0 | 1.5 GB | Hindi | 14.85 CV, 14.83 IITM, 13.11 MUCS (P) | server | Too big |
| Vosk small-en-in-0.4 / en-in-0.5 | Apache 2.0 | 36 MB / 1 GB | Indian English | WER **49.05** / 36.12 on NPTEL (P) | CPU | Poor. Do not build |
| NVIDIA Parakeet-TDT-0.6b-v3, Canary-1b-v2 | CC BY 4.0 (v3 card, P) | 0.6B; "at least 2 GB RAM to load", GPU-oriented (P) | 25 European languages, **Hindi not listed** (P) | n/a | GPU | Do not build |
| AI4Bharat IndicConformer 600M multilingual | MIT (card, P); **gated** (accept terms to download) | 600M; Hindi monolingual .nemo 523 MB (S) | 22 Indian languages incl. Hindi | Hindi WER 13.2 on Vaani Benchmark V1.0 (card, P). Paper: 20.0 / 16.8 / 13.1 by scoring approach 1/2/3 vs **Whisper-large-v3 32.8 / 30.0 / 26.4** (Vaani paper Table 1, P) | needs onnxruntime or NeMo; too big for 512 MB and for a phone download | **Research only** (later: paid always-on instance) |
| AI4Bharat IndicWhisper | Vistaar repo says MIT, wording ambiguous for the weights (S) | Whisper-medium class (third-party claim, S) | 12 Indian languages | Hindi average WER 13.6 on Vistaar (S) | CPU/GPU | Too big; Collabora covers the same need smaller |
| Meta MMS (`mms-1b-all`) | **CC BY-NC 4.0** (P) | 1B | 1,100+ languages | n/a | | **Blocked** (non-commercial) |
| SpeechBrain, wav2vec2 Hindi fine-tunes | not checked | | | | | Not evaluated; no licence or Hindi checkpoint verified here |
| Silero VAD | **MIT**, "Copyright (c) 2020-present Silero Team" (LICENSE, P) | about 0.6 to 2.3 MB depending on file (S, sources differ) | language-agnostic | no noise-robustness number found | CPU, ONNX Runtime Web (upstream lists browser examples, S) | Use for silence trimming |
| sherpa-onnx | Apache-2.0 (P) | n/a | runs Whisper tiny.en, Moonshine tiny, Silero VAD, Piper English/German in WASM; Android builds (P) | no Hindi model listed (P) | WASM, Android | Useful runtime if we avoid transformers.js; no Hindi model shipped |
| Web Speech `SpeechRecognition` | n/a (browser) | none | browser-defined | none published | see 2.3 | Conditional |

### 2.2 Accuracy on Hindi and code-mixed speech: what the numbers really say

| Fact | Source |
|---|---|
| Zero-shot Whisper WER on FLEURS Hindi: tiny 102.3, base 101.1, small 38.4, medium 26.8, large 26.9, large-v2 21.5 | Whisper paper (arXiv 2212.04356), Table 13, extracted from the PDF, P |
| Collabora's baselines (tiny 172.6, base 149.2) differ from the paper's because they used beam search, a repetition penalty, number filtering and their own normalisation | Collabora blog, P. Treat all stock-Whisper tiny/base Hindi numbers as "unusable" either way |
| Fine-tuning on about 3,000 h of Hindi (Shrutilipi, IITM SpringLab, Common Voice, IndicSUPERB, snow-mountain, yodas, IndicVoices-R, Lahaja, FLEURS) takes tiny to 10.0 WER (whisper norm) or 18.9 (Indic norm, keeps diacritics) on FLEURS Hindi | Collabora, P |
| FLEURS is read, clean, Wikipedia-style sentences. It is not conversation and not Hinglish. Its train split is in Collabora's training data (the test split is held out). Expect conversational WER to be much higher | my reading of the two pages |
| Vaani Benchmark V1.0 (Hindi, 102 districts, spontaneous image-prompted speech, CC BY 4.0 per PDF metadata, three transcripts per clip, three scoring approaches): Gemini-3.1-Pro 19.0/15.6/12.3, IndicConformer-600M 20.0/16.8/13.1, Google Chirp 3 22.5/19.2/15.6, Whisper-large-v3 32.8/30.0/26.4 | arXiv 2606.21408 Table 1, P |
| Same paper: noise from above 25 dB to below 5 dB SNR costs IndicConformer only 3.7 points; code-switched English tokens: Chirp 3 goes 10.2% to 12.8% substitution, Shrutam-HindiASR 12.8% to 28.3% | arXiv 2606.21408, P |
| Open model quality ranking on conversational Hindi: IndicConformer beats Whisper-large-v3 by about 7 to 13 WER points. A tiny model will be worse than large-v3 | derived |
| Whisper without an explicit language may translate code-switched audio into English instead of transcribing (tested on Spanish, French, German pairs with synthetic TTS audio, not Hinglish) | ServiceNow blog, 9 Jun 2026, P |
| Hinglish literature figures: HiACC says monolingual models are about 42% worse on code-switched speech; CS-FLEURS says distinct-script pairs (Hindi-English is one) have about 3x the character error rate of same-script pairs; Deepgram quotes 26.97% to 69.53% Hinglish WER across systems (vendor, source unverified) | S, UNVERIFIED |
| Vividh-ASR (May 2026): fine-tuned Whisper-medium 15.73 WER, small 18.73, on a 36.96 h Hindi test set with four recording tiers; IndicWhisper 25.01 and Vaani Large-v3 21.05 on the same set (authors' own numbers; licence not stated) | HF blog, P |

No public, licensed, conversational Hinglish test set with published WER for small models was verified. That is why section 8 specifies our own.

### 2.3 Browser engines

**In-browser inference (transformers.js / ONNX Runtime Web, whisper-web style).**
- Sizes (P, from the onnx-community repos): whisper-base int8 encoder 22.1 MiB plus int8 merged decoder 51.2 MiB = 73.3 MiB; whisper-small int8 88.1 + 149.5 = 237.5 MiB. fp16 base: 39.4 + 99.9 = 139 MiB. Tiny was not listed (a community tiny fine-tune lists about 10 MB encoder plus 30 to 50 MB decoder, S).
- At 4 Mbps, 73.3 MiB takes about 2.5 minutes (EST: 73.3 x 8.39 Mbit / 4). Fine as a one-time opt-in on Wi-Fi, bad as an automatic download. Cache with the Cache API; offer "remove downloaded model".
- WebGPU vs WASM: transformers.js v3 added WebGPU; a table quoting 10 to 15x real time for tiny on WebGPU is unsourced (S). Many mid-range Android phones lack stable WebGPU; plan on WASM (with SIMD, threads need cross-origin isolation headers, which our CSP/hosting would have to allow: check) and treat WebGPU as a bonus.
- **Phone speed is not measured in any source I found.** Two non-comparable data points exist: tiny at about 0.11 real-time factor (RTF) on an M3 Mac with WASM, English (S, from the voice-product report), and a different engine (Shruti) at 9.5 s for 60 s on a Galaxy F62 with 2 threads, RTF about 0.16 (S). Neither is Hindi, neither is Whisper-tiny on a phone. The test plan measures it.
- Whisper is batch, not streaming: text appears after Stop, in 30-second windows. With Silero VAD cutting at pauses, a 60 s clip becomes 2 to 4 windows.
- Memory: whisper.cpp tiny about 273 MB, base about 388 MB. On a 3 to 4 GB phone this is fine; on a 2 GB phone with a full browser, a risk (tab kill). Detect `navigator.deviceMemory` and hide the feature below 3.

**Web Speech `SpeechRecognition` (the browser's own).**
- MDN (P): "Depending on the browser, your audio might be sent to a server-based recognition service, in which case recognition won't work offline." `processLocally = true` forces on-device and then "neither the audio nor the transcribed speech is sent to a third-party service". Default is false. If the language pack is missing, start fails with `service-not-allowed`. `available()` and `install()` exist.
- Chrome on-device shipped on desktop: Chrome 139 release notes (S, search result) versus "Chrome 135" in the intent to ship (voice-product report, P there): sources differ on the milestone, both say desktop. A blink-dev message of 6 May 2026 (P): "Android & ChromeOS currently do not support on-device Web Speech". So on a student's Android phone, which is the main target, Chrome uses the server engine. Whether hi-IN has an on-device pack on desktop: not confirmed.
- Privacy verdict: the default Chrome path sends audio to Google. A Chromium developer says so for desktop (S), Google publishes no clear current retention or training statement that I could find (S). **Verdict: never use the default.** Use only with `processLocally = true` and `available()` resolving to "available", else hide the button.
- Brave has a bug where `available()` says "downloading" and `install()` never resolves (S): feature-detect with a timeout.
- Offline: only with an installed on-device pack.

**Keyboard dictation (Gboard, iOS).** Works in any text box with no code. Audio handling belongs to the phone maker. Mention it in the consent text; do not claim it is private.

### 2.4 Server-side on the free tier

Render free: 512 MB RAM, about 0.1 CPU, sleeps. faster-whisper small int8 needs about 1.5 GB (S) and runs 7.6x real time on 8 threads of an i7-12700K (S). EST: 0.1 CPU is roughly 1/80 of that throughput if scaling were linear, so about 10x slower than real time, a 60 s clip taking around 10 minutes, assuming one 8-thread desktop is about 8 cores. Tiny would fit in RAM (about 273 MB) but stock tiny is useless for Hindi and a Hindi fine-tune would need conversion to ggml/CTranslate2. A Hugging Face Space (free CPU tier, I recall 2 vCPU and 16 GB, UNVERIFIED) is a third-party host: audio would leave the phone, so it does not meet constraint 2 unless the owner decides a Space we control counts as our own server. Verdict: **do not build** server STT on the free tier. If a paid always-on instance comes later, IndicConformer 600M or a Whisper Hindi small fine-tune becomes possible (research only).

### 2.5 Noise robustness on phones

Hostel conditions (fans, corridor, roommates) and cheap phone mics are the real test. Evidence: Vaani paper (above) shows large degradation for Whisper-large-v3 on background speech and for most systems on code-switched tokens, with IndicConformer the most robust (P). Whisper-family models are also widely reported to hallucinate text on silence or noise (general knowledge, not measured here), which is why the student must see and edit the text and why a VAD gate and an empty-result path are required. Silero VAD number on noisy phone audio: none found.

---

## 3. TTS findings

| Candidate | Licence | Size / speed | Languages | Browser? | Verdict |
|---|---|---|---|---|---|
| Piper engine | New repo `OHF-Voice/piper1-gpl` is **GPL-3.0** (P); the older MIT `rhasspy/piper` repo not re-checked (UNVERIFIED). Voices: "Piper grants no license over voice models" (COMMERCIAL_USE.md, P) | VITS, ONNX, 22.05 kHz medium voices; size and RTF not measured here | Voices on `rhasspy/piper-voices`: hi_IN pratham, priyamvada, rohan; en_GB and en_US only (no en_IN) (P) | sherpa-onnx WASM demos list Piper English and German only (P) | See Hindi voice rows below |
| Piper hi_IN **pratham** (medium) | dataset **CC BY-NC-SA 4.0**, trained by PravalX on "AI4Bharat IndicNLP corpus" (P) | | Hindi | | **Blocked** (non-commercial) |
| Piper hi_IN **priyamvada** (medium) | same, CC BY-NC-SA 4.0 (P) | | Hindi | | **Blocked** |
| Piper hi_IN **rohan** (medium) | IndicTTS "Hindi Mono Male" database, licence only a PDF link; fine-tuned from the US "lessac" voice (P). Piper's commercial-use page excludes voices derived from lessac and lists no hi_IN voice (P) | | Hindi | | **Do not use** without a lawyer reading the IndicTTS terms |
| Kokoro-82M | **Apache-2.0** weights; trained on permissive/non-copyrighted audio per card (P) | 82M params. ONNX: about 325 MB fp32, 92 MB int8, 86 MB q8f16 (third-party guide, S). One independent CPU benchmark: RTF 0.64 (1.6x real time), fp32 ONNX, desktop-class CPU (S) | 8 languages. **Hindi voices hf_alpha, hf_beta, hm_omega, hm_psi, all graded C**; 10 to 100 minutes of training audio per voice, 1 to 10 h Hindi total (VOICES.md, P). Hindi uses espeak-ng G2P (P); espeak-ng licence not checked | kokoro-js runs `wasm` or `webgpu` (README, S); WASM speed claim 0.5 to 1x real time unverified | **Build later, offline pre-render only**; needs native-speaker listening test |
| MeloTTS | **MIT**, commercial use allowed (P) | "fast enough for CPU real-time" (claim, no numbers, P) | English (incl. Indian), Spanish, French, Chinese, Japanese, Korean. **No Hindi** (P) | not verified | Indian English voice only; research only |
| Indic Parler-TTS (AI4Bharat) | **Apache 2.0**, gated download (P) | about 0.9B params, F32 (about 3.6 GB, EST); no CPU speed published (P) | Hindi (voices Rohit, Divya, Aman, Rani), Indian English among 69 speakers (P). The card itself recommends the newer "Indic-Speak" (P) | no | **Offline pre-render on a dev machine only**; too heavy for any free runtime |
| AI4Bharat Indic-TTS (FastPitch + HiFi-GAN) | repo MIT (P); IIT Madras IndicTTS training database terms **not found** | sizes not stated; GPU-oriented setup (P) | 13 languages incl. Hindi | no | UNVERIFIED licence chain; do not use until the database terms are read |
| MMS-TTS hin | **CC BY-NC 4.0** (P) | VITS 36.3M params | Hindi | | **Blocked** |
| XTTS v2 (Coqui) | Coqui Public Model License: non-commercial only; revenue-generating use, including grant-funded projects, is not non-commercial (mirrors of the licence, S; official coqui.ai/cpml returned 404) | | | | **Blocked** |
| Bhashini TTS/ASR APIs | API terms not found (the terms page I found covers BhashaDaan, not the API) (S) | hosted | Indian languages | n/a | Third-party hosted: **blocked** for personal text or audio. Possible only for static non-personal scripts, after reading the terms |
| Google Cloud, Azure, Edge neural voices as services | paid or billing account needed; unofficial Edge read-aloud endpoints are against the vendor's terms (my understanding, UNVERIFIED) | | | | Blocked (zero rupees, constraint 2) |
| Browser `speechSynthesis` | n/a | none | depends on OS voices | yes | Conditional, below |

**Browser `speechSynthesis` facts (Readium review, S):**
- Chrome Android returns "an unfiltered list of languages/regions", and if a language's voice pack is not installed Chrome "falls back to an English voice" (so `getVoices()` cannot prove a Hindi voice is present; the page cannot detect the fallback).
- Vanilla Android has high-quality voices (67 as of April 2024) but they are downloaded in system settings.
- iOS: all browsers use WebKit; downloadable voices do not appear in the list; Siri voices are unavailable; `speak()` must start inside a user gesture (S, other source).
- Chrome desktop voices "require online access with no offline fallback" and Edge natural voices are ML-based and online: **spoken text can leave the device**. Use only voices with `localService === true`.
- Chrome desktop cuts off an utterance longer than about 14 seconds (S): split by sentence.
- Verdict: fine for fixed, non-personal text (breathing cues, starter answers). Do not speak text that quotes the student (an AI reply that echoes their words) through a non-local voice.

---

## 4. Where each option fits

| Use case | Best option now | Why | Cost (EST) |
|---|---|---|---|
| Voice journaling transcription in the browser before saving only the approved text | Hindi Whisper fine-tune (tiny or base) in a Web Worker, opt-in download; fallback keyboard dictation | Meets constraint 2; transcript passes the same crisis floor as typed text | 2 to 3 weeks after a go decision, 1 week test set and phone benchmark |
| Reading breathing and grounding scripts aloud | Pre-recorded human audio (Opus, about 16 kbps = 2 KB per second, so a 3-minute script is about 360 KB, EST) served from `static/`; `speechSynthesis` as an extra | Best quality, no licence problem if volunteers consent, works offline, zero runtime cost | 3 to 5 days plus recording |
| Spoken companion reply | `speechSynthesis` Listen button on fixed saved answers only | No personal text; student-triggered; a crisis reply is never auto-spoken | 2 to 4 days, shared with the above |
| Low-vision accessibility | Do not build a reader; keep labels and live regions correct for TalkBack and VoiceOver | Screen readers already do this better | part of QA |
| Counsellor-facing voice | Nothing | No validated signal (section 6) | 0 |

Privacy: with the above, audio never reaches our server, a third party, or storage. Saved data is text the student approved, same as a typed journal entry.

---

## 5. Does it really improve anything?

- STT for typing convenience: plausible accessibility and effort benefit (typing Hindi or Hinglish on a phone is slow). **No outcome evidence exists** that it improves wellbeing or help-seeking in Indian students. Claim only "easier to write", never "better care". Measurable: completion rate and time vs typing (section 8).
- TTS of breathing and grounding: plausible benefit (eyes closed). No outcome evidence found. Cheap enough to build on plausibility, with the feature measured for use not for effect.
- Acoustic emotion: negative (section 6).

---

## 6. Acoustic features (pitch, energy) as a wellbeing signal: evidence-based judgement

**What the research says (quality graded).**

| Source | Finding | Quality |
|---|---|---|
| Mao, Wu, Chen, npj Mental Health Research 2023 (PRISMA review, 264 studies, 140 acoustic, median 189 participants) (P) | Many studies report lower F0 and narrower F0 range, lower loudness, longer pauses and slower speech in depression, jitter and shimmer rising with severity. Authors list small, unrepresentative datasets, often non-clinical and recorded in noise-free rooms, only some studies with held-out tests, self-report scales instead of clinical diagnosis, confounders (age, sex, language, medication) | Review of mostly small lab studies: **low to moderate** |
| Maran et al., JMIR Mental Health 2025;12:e67802, three-level meta-analysis, searched Jan 2013 to 1 Apr 2025, PROSPERO CRD42023444431 (S, via the preprint page; the paper itself did not load) | Pooled accuracy between 0.65 and 0.81, sensitivity 0.63 to 0.84, specificity 0.58 to 0.83 depending on algorithm, features and validation | Pooled estimates over heterogeneous, mostly in-corpus studies: **moderate-low**, UNVERIFIED numbers |
| Liu et al. 2024 (S) | Deep-learning speech models, 8 of 25 studies pooled; handcrafted acoustic features outperformed end-to-end models | snippet only |
| Reports in `evidence-safety-eval.md` | Accuracy drops across corpora, languages and recording setups; Kintsugi, the best-funded voice-biomarker company, closed in Feb 2026; EU AI Act recital 44 bans emotion inference in workplaces and education | S there |

**Reading.** Group-level differences in prosody exist in depression research. They are small effects, measured with controlled protocols and clinical samples, fall apart across corpora, languages and devices, and describe people, not a single recording. None of this supports labelling one 30-second phone clip "sad" or "stressed". Even the best pooled numbers are below any threshold for a screening claim in a general student population, where prevalence is low and false positives dominate (the PPV point in `evidence-safety-eval.md`). **No diagnosis may be claimed from any speech marker**, and the product must not imply one.

**What MindFull Horizon does today and why it fails.**

1. `piptrack` returns many spurious pitch bins per frame; the mean of all positive bins is not fundamental frequency (F0). The code treats it as F0.
2. The thresholds (150 and 200 Hz) are fixed. Typical F0 differs strongly by sex (adult male roughly 100 to 130 Hz, female roughly 190 to 230 Hz, general phonetics knowledge, not fetched here), so the rule mostly labels voice type: low voice plus quiet = "sad", high voice plus loud = "happy". My inference; no validation exists in the repo.
3. RMS energy depends on mic gain, distance and phone model, uncalibrated. ZCR above 0.1 mostly measures noise or fricatives.
4. No within-person baseline, which is what the research relies on (change over time), and no control for language, accent or setting.
5. The label ("Tone guessed from the sound: Stressed") is shown to the student next to a number, stored in `voice_logs.emotion`, and sits in data exports. A wrong "sad" label is a fake claim under the project rules and could reach a counsellor as fact.
6. Speaker-characterising numbers (`mean_pitch`, `mean_spectral_centroid`, `mean_zcr`) are stored per log, which are voice-identity-adjacent features, for no benefit.
7. The 20 points awarded for a log carrying a mood-like label sit badly with "no points on mood or assessment scores" (owner call).

**Judgement: marketing, not measurement.** Retire `classify_emotion`, stop storing pitch/centroid/ZCR, drop the "tone" line from the page and the export, and with it `utils/voice_features.py`, `requirements/voice.txt`, the Gemini voice prompt and the audio upload route once browser dictation or a simple text note replaces it. If the clinic ever wants speech markers, run a clinician-owned study with consent and a validated protocol (within-person trend of speech rate and pause time), not a product feature. This agrees with `evidence-safety-eval.md` and `voice-product.md`.

---

## 7. Recommended minimal design: "Speak your journal", on-device, text only

**Where audio stays.** In memory in the student's browser only. Never uploaded, never written to IndexedDB, Cache or disk, never a Blob URL kept after Stop. Float32 buffer at 16 kHz mono for 120 s is about 7.7 MB (EST: 120 x 16000 x 4). Zeroed on Save, Discard, `pagehide`, or error.

**What is stored.** Nothing from the audio. After the student reads and edits the text and presses the normal Save, the text is posted to the existing journal route as ordinary text, with no "voice" flag and no acoustic features. The server sees text only, so the existing crisis scan on journal save applies (verify that the journal save path runs the floor, as `voice-product.md` also assumes). If the student discards, nothing is sent.

**Flow.**
1. Journal page: "Speak" button, shown only if feature checks pass: WebAssembly, `navigator.deviceMemory >= 3` where available, not `Save-Data`, microphone permission not blocked. Otherwise hide it and show a one-line tip about the keyboard mic key.
2. First use: consent text (below) and a model download prompt with the size and "Wi-Fi recommended".
3. Student picks the language: Hindi, English, or Hinglish (if the Roman-output model passes the test). **Always set the language explicitly; never auto-detect** (Whisper may translate code-switched speech to English, 2.2).
4. Record with an obvious Recording state, Stop, 120 s cap. Silero VAD trims silence and splits at pauses to windows of 30 s or less.
5. Web Worker runs the model. Show "Turning your speech into text". Empty or very short result: "I could not hear that clearly. Try again or type."
6. Transcript lands in the editable journal box. Mandatory read-and-edit step (no one-tap save on first use). Words below a confidence threshold are not marked unless the engine gives probabilities; do not invent confidence.
7. Save or Discard.

**Static assets and CSP.** Model files and WASM served from our own origin (`/static/models/...` or GitHub Pages added to `connect-src`), `script-src` gains `'wasm-unsafe-eval'`, add `worker-src 'self'`, no CDN at runtime. Each new JS file under 300 lines; no inline handlers. Attribution file for CC BY 4.0 models. These are engineering notes; the owner decides after the benchmark.

**Consent text (draft, matches what the code would do).**
"Speak turns your voice into text on this phone or computer. The recording is not sent to MindFull Horizon or to anyone else, and it is deleted from memory when you save or discard. Only the text you choose to save is stored, like any journal entry. Speech to text makes mistakes, especially when Hindi and English are mixed, so please read and fix the text before you save. The first time, this page downloads a language file of about [size] MB to your device; you can remove it later. If you use your phone keyboard's microphone instead, that is handled by your phone maker, not by us."

**Failure modes.**

| Failure | Handling |
|---|---|
| Model download fails or stalls | Resume or cancel; fall back to typing and the keyboard mic tip; no retry loop on metered data |
| Phone runs out of memory, tab reloads | Detect with a pre-flight memory check; recording stays in memory only, so on reload it is gone: say so; never persist partial audio |
| Hallucinated text on silence or noise | VAD gate; empty-result path; mandatory edit step; never auto-save |
| Mixed Hindi-English mis-transcribed | Edit step; language picker; show "this may be wrong" copy; track edit rate (count only) |
| Misheard crisis phrase or a dropped negation ("do not want to die" heard as "want to die") | The floor sees only the saved text; negation handling already softens, never drops; run the transcript recall test (8.3 and `voice-product.md` 8.3) before release; the model never lowers the floor |
| Devanagari vs Roman spelling variants of the same crisis phrase | Floor recall on STT output must be measured; `voice-product.md` says Devanagari coverage is thin (see Cross-notes for a number conflict) |
| Student in a shared hostel room | Text-first, Quiet mode (see `voice-product.md`), no autoplay, headphone prompt for any audio output |
| Permission denied or no mic | Existing permission copy in the voice-log JS |
| Unsupported browser | Hide the button; typing unaffected |

---

## 8. Test plan

### 8.1 Phone benchmark and accuracy (the experiment that decides build or not)

1. Convert `collabora/whisper-tiny-hindi` and `whisper-base-hindi` to ONNX int8 (tiny and base). Record sizes. Run with transformers.js in a Web Worker, WASM only, on: one low-end Android (3 GB RAM), one mid-range Android (4 to 6 GB, Snapdragon 6 class), one iPhone, one laptop. Measure: download size, first-load time on a throttled 4 Mbps connection, RTF for a 30 s clip (processing seconds divided by audio seconds), peak memory, whether the tab survives three consecutive clips.
2. Same audio through the same model with Oriserve Swift (Roman) for the Hinglish bucket.
3. Score on our own test set below. Add sanity checks on public sets: FLEURS Hindi (CC BY 4.0), Svarah (9.6 h Indian English, 117 speakers, CC BY 4.0, gated, P), Lahaja (12.5 h Hindi accents, 132 speakers; CC BY 4.0 badge, UNVERIFIED), Vaani Benchmark V1.0 test split (CC BY 4.0 per PDF metadata; dataset licence to verify).

### 8.2 Our small Hinglish test set (specification)

Never use real student data. Scripts written by the team; read aloud by adult volunteers who sign a consent and a licence release; recordings kept only on the project's private storage, deleted after the evaluation.

| Bucket | Utterances | Style | Reference format |
|---|---|---|---|
| A. Hindi read | 20, 8 to 15 words | Everyday wellbeing and campus sentences in Devanagari, e.g. "मुझे आज रात ठीक से नींद नहीं आई" | Devanagari |
| B. Hinglish conversational | 20, 10 to 25 words | Mixed Hindi-English, spoken casually, e.g. "exam kal hai aur bahut tension ho raha hai, kuch samajh nahi aa raha"; "hostel mein sab so gaye par mujhe neend nahi aa rahi"; "I feel thoda low today, assignment submit nahi kar paya" | Roman Hinglish, plus an agreed Devanagari alternative for Hindi words, with English words kept in Latin (multiple valid references, as in the Vaani paper's approach 3) |
| C. Indian English | 20, 10 to 20 words | Same topics in English with Indian accents | English |
| D. Safety subset (inside A to C, 12 phrases) | 12 | Paraphrases of crisis and near-miss phrases written by the team (never copied from real data), including 4 negated ones and 2 third-person ones, taken from the constructed fixtures in `docs/review/generated/crisis_phrases.csv` | same as bucket |

Speakers: at least 8 volunteers (mix of sex, Hindi-first and English-first, at least 3 regional accents). Devices: 2 phones (one low-end), 1 laptop. Conditions: quiet room and a noisy room (fan plus background speech). That is 60 utterances x 8 speakers x 2 conditions about 960 clips, or about 2.5 to 3 hours of audio (EST at 10 s average). For a first pass use 4 speakers and quiet plus noisy.

Normalisation before scoring: lowercase, strip punctuation, collapse a fixed variant list for common Roman spellings (hoon/hun/hu, nahi/nahin, etc.); report WER and CER separately; also report "edits to fix" (character edits needed, the cost the student pays).

### 8.3 Metrics and proposed pass bars (all PROPOSALS)

| Metric | Pass bar | Note |
|---|---|---|
| WER, Hindi read (A), tiny or base fine-tune, phone mic, quiet | at most 20% (Indic norm) | FLEURS reference is 18.9 tiny |
| WER, Hinglish conversational (B), quiet | at most 30% for a "typing aid with editing"; `evidence-safety-eval.md` proposes 20% (owner to set) | Best open large models are 13 to 26 on Hindi conversational (Vaani); a tiny model reaching 20% on B is unlikely, so expect to ship as an edit-first aid |
| Crisis-term miss rate (D), transcript vs the same phrase typed | transcript recall at least 90% of typed recall and no true-crisis phrase with zero hits; failures lead to floor additions reviewed by a clinician and a native speaker | same gate as `voice-product.md` 8.3 and `evidence-safety-eval.md`; the model only adds signals |
| Noisy minus quiet WER gap | report; above 15 points means hide the feature in noise | |
| RTF on a mid-range Android (30 s clip, WASM) | at most 1.0 | otherwise the wait is longer than the speech |
| First-load download | at most 75 MiB, one-time opt-in; ideally tiny at about 40 MiB | 4 Mbps gives 2.5 minutes for 73 MiB (EST) |
| Peak memory, no tab crash in 3 clips | pass on the 3 GB phone | |
| Student edit time for a 60 s dictated entry vs typing it | at least 30% faster including editing | usability test (`voice-product.md` 8.2) |
| Zero audio persisted | automated test: no audio blob, file, or request body with audio; Network panel shows no upload | |

If the bars fail, ship keyboard mic guidance and pre-recorded audio only, and say so plainly.

---

## 9. Cross-notes

Files found in `docs/research/ai/` when I checked: `voice-product.md`, `evidence-safety-eval.md`. (`llm-agents.md`, `encoders-nlp.md`, `datasets-finetuning.md`, `runtime-hosting.md` were absent.)

**Agreements.** Both reports and mine agree: no audio stored or sent; browser default `SpeechRecognition` is banned; text-first with mandatory edit step; transcript goes through the same floor and a model can only add signals; retire `classify_emotion`, pitch/energy storage and the 20 points; pre-recorded or device TTS for fixed content; no hands-free voice chat; no outcome evidence for voice in Indian students. `evidence-safety-eval.md` row 8 ("STT, build later") and `voice-product.md` F3 ("build now if on-device Hindi works") are consistent with my "build later after the phone benchmark".

**Conflicts and corrections to their numbers.**

| Item | Their number | What I found | Which to trust |
|---|---|---|---|
| Collabora whisper-tiny-hindi FLEURS WER | `voice-product.md`: 14.21% (snippet) | The model card (P): 10.10 (whisper norm), 18.94 (Indic norm); the blog: 10.01 and 18.94. Licence: **CC BY 4.0** (P). 37.8M params | Mine (page opened). This also answers their open licence question |
| Chrome on-device Web Speech milestone | "Chrome 135 desktop" (P there) | A search result for Chrome 139 release notes lists on-device Web Speech (S). Android is unsupported either way (blink-dev 6 May 2026, P by me) | Unresolved; irrelevant to the decision because Android is the target |
| Devanagari crisis coverage | `voice-product.md`: "about 14 pattern lines Roman and 4 Devanagari" (`ai/severity.py`) | `crisis_phrases.csv` has 109 of 1,416 lines containing Devanagari characters (all list types, so not a pattern count) | Not comparable; re-count patterns before concluding. Either way the transcript recall test decides |
| WER bar | `evidence-safety-eval.md`: at most 20% on "our accent set (owner to set)" | Hinglish conversational for a tiny model probably above 20% | Keep 20% for Hindi read, treat Hinglish as an edit-first aid; do not claim STT as a safety input |
| In-browser phone speed | `voice-product.md`: RTF 0.15 to 0.7, EST from two non-comparable points | Same two points; still no Hindi Whisper phone measurement | Replace with 8.1 results |
| Model download size | `voice-product.md`: about 40 to 80 MB, EST | base int8 ONNX is 73.3 MiB (P); tiny not measured | Consistent |

Questions for the unwritten reports that would change my answer: `runtime-hosting.md` (is a Hugging Face Space or a paid always-on instance acceptable for IndicConformer?), `datasets-finetuning.md` (a licensed conversational Hinglish set for evaluation), `encoders-nlp.md` (a small classifier robust to ASR noise on Devanagari/Roman crisis text), `llm-agents.md` (none needed for STT or TTS).

---

## 10. Questions for the owner

1. **Retire the voice-log "tone" label, the stored pitch/energy/centroid, the 20 points and eventually `utils/voice_features.py` and the audio upload?** My recommendation: yes (section 6).
2. **Approve a one-time, opt-in model download of up to about 75 MiB** (Wi-Fi recommended) if the phone benchmark passes?
3. **Narration for breathing and grounding:** will a counsellor or volunteer record Hindi and English audio with written consent and a licence (best quality, zero licence risk), or should we accept the phone's own voice only?
4. **Test set:** may the team recruit 8 adult volunteers under a consent and licence release, and who signs off on ethics?
5. **Hosted Indian speech APIs (Bhashini, Sarvam):** keep out for good (default), or do you want me to read their current terms for a possible written approval?

---

## Sources (all accessed 2026-11-25; P = opened, S = snippet)

STT: Whisper paper PDF https://arxiv.org/pdf/2212.04356 (P, Table 13); whisper.cpp https://github.com/ggml-org/whisper.cpp (P); onnx-community sizes https://huggingface.co/api/models/onnx-community/whisper-base/tree/main/onnx and `.../whisper-small/tree/main/onnx` (P); https://huggingface.co/onnx-community/whisper-base (P); Collabora https://collabora.com/news-and-blog/news-and-events/breaking-language-barriers-20-moving-closer-production-ready-hindi-asr.html and https://huggingface.co/collabora/whisper-tiny-hindi (P); Oriserve https://huggingface.co/Oriserve/Whisper-Hindi2Hinglish-Swift (P); Vosk https://alphacephei.com/vosk/models (P); Moonshine licence https://moonshine-voice.readthedocs.io/en/latest/license/ (P); Parakeet https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3 (P); IndicConformer https://huggingface.co/ai4bharat/indic-conformer-600m-multilingual and https://github.com/AI4Bharat/IndicConformerASR (P); Vaani Benchmark https://arxiv.org/pdf/2606.21408 (P, text extracted from PDF); Vividh-ASR https://huggingface.co/blog/adalat-ai/vividh-benchmark (P); ServiceNow https://huggingface.co/blog/ServiceNow-AI/code-switching (P); MMS https://huggingface.co/facebook/mms-1b-all (P); Silero https://raw.githubusercontent.com/snakers4/silero-vad/master/LICENSE (P); sherpa-onnx https://github.com/k2-fsa/sherpa-onnx (P); Svarah https://huggingface.co/datasets/ai4bharat/Svarah (S); Lahaja https://huggingface.co/datasets/ai4bharat/Lahaja (S); Vistaar https://github.com/AI4Bharat/vistaar and https://arxiv.org/pdf/2305.15386 (S); HiACC https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12329218/ (S); faster-whisper numbers via https://deepwiki.com/SYSTRAN/faster-whisper (S); distil-whisper https://huggingface.co/distil-whisper/distil-small.en (S).

Browser: https://developer.mozilla.org/docs/Web/API/SpeechRecognition/processLocally (P); https://developer.mozilla.org/docs/Web/API/Web_Speech_API/Using_the_Web_Speech_API (P); https://groups.google.com/a/chromium.org/g/blink-dev/c/P8P-x7AnC6I (P, 6 May 2026); https://groups.google.com/a/chromium.org/g/chromium-html5/c/EJl8kE52MyI (S); https://developer.chrome.com/blog/new-in-chrome-139 (S); https://github.com/brave/brave-browser/issues/55414 (S); https://readium.org/speech/docs/WebSpeech.html (P).

TTS: Piper https://github.com/OHF-Voice/piper1-gpl and `.../docs/COMMERCIAL_USE.md` (P); voice cards https://huggingface.co/rhasspy/piper-voices/blob/main/hi/hi_IN/pratham/medium/MODEL_CARD, `.../priyamvada/medium/MODEL_CARD`, `.../rohan/medium/MODEL_CARD` (P); Kokoro https://huggingface.co/hexgrad/Kokoro-82M and `.../blob/main/VOICES.md` (P); Kokoro sizes and RTF https://localaimaster.com/blog/best-tts-without-gpu and https://raw.githubusercontent.com/gauravvij/kokoro-tts-vs-supertonic-3-tts/main/results/benchmark_report.md (S); MeloTTS https://github.com/myshell-ai/MeloTTS (P); Indic Parler-TTS https://huggingface.co/ai4bharat/indic-parler-tts (P); Indic-TTS https://github.com/AI4Bharat/Indic-TTS (P); MMS-TTS https://huggingface.co/facebook/mms-tts-hin (P); XTTS licence mirrors https://huggingface.co/coqui/XTTS-v2/commits/v2.0.3/LICENSE.txt (S); Bhashini https://bhashini.gov.in/bhashadaan/en/terms-and-conditions and https://bhashini.gitbook.io/bhashini-apis/ (S).

Evidence: https://pmc.ncbi.nlm.nih.gov/articles/PMC10955993 (P, first 100k characters); https://mental.jmir.org/2025/1/e67802 and https://pmc.ncbi.nlm.nih.gov/articles/PMC12590051/ (did not load; figures from the search snippet, S); https://pmc.ncbi.nlm.nih.gov/articles/PMC11413444 (S).

Repo files read: `utils/voice_features.py`, `app.py` (509 to 549, 486 to 506), `templates/patient_voice_logs.html`, `static/js/inline_extracted/patient_voice_logs_inline_1.js`, `models.py` VoiceLog, `ai/service.py` (67, 384), `utils/security_headers.py`, `requirements/voice.txt`, `docs/review/generated/crisis_phrases.csv`, `docs/research/ai/voice-product.md`, `docs/research/ai/evidence-safety-eval.md`.
