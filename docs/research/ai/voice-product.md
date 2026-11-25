# Voice AI and conversational agents: product design for MindFull Horizon

Agent: VOICE-PRODUCT. Date and access date for every URL: 2026-11-25. Tags: **P** = page opened and read this session; **S** = search snippet or secondary report, treat as UNVERIFIED until the primary page is opened. Vendor claims are marked "claim". Estimates are mine and are labelled ESTIMATE. No emoji, no em dashes.

## 0. Summary and verdicts

Voice is worth adding only where it removes a real barrier and costs no privacy. The free, on-device, no-GPU constraints cut most of what the market calls "voice AI".

| Candidate | Verdict | One-line reason |
|---|---|---|
| F1 Spoken breathing and grounding (cues in the student's ears, eyes closed) | **Build now** | Real need (you cannot watch a circle with eyes closed), no microphone, no model, offline, hooks into `MFHBreath.onPhase`. |
| F2 "Listen" button on static text (starter answers, safety plan, psychoeducation) | **Build now** (same module as F1) | Dyslexia, low vision, low literacy in a second language; our own text, device TTS, nothing leaves the phone. |
| F3 Voice journaling by dictation (transcribe on device, student edits, saves TEXT) | **Build now if on-device Hindi works, else keyboard-mic guidance only** | Typing Hindi or Hinglish on a phone is slow; but Chrome's default recogniser sends audio to a third party, so only on-device is allowed. |
| F4 Hands-free voice chat (STT, chat pipeline, TTS) | **Do not build** (half-duplex dictate-then-listen only, via F2+F3) | No local LLM, so Anya is a rule-based bot plus saved answers; on-device STT latency is not conversational; hostel setting. |
| F5 Spoken safety-plan walkthrough | **Build later** (after F2; it is F2 plus a step player) | Useful at the worst moment, but must be silent by default and reviewed by a clinician. |
| F6 Voice check-in for mood (spoken 1 to 10) | **Do not build** | A tap is faster and more accurate than speaking a digit in two languages. |
| F7 Voice navigation | **Do not build** | Android Voice Access, iOS Voice Control, TalkBack and VoiceOver already do it; our job is to be compatible. |
| Existing voice log "tone" guess (pitch, energy) | **Retire** (owner question 2) | No validity evidence; points attached; audio upload no longer needed if F3 ships. |

Does it really improve anything? **No outcome evidence exists that voice improves wellbeing in Indian college students** (section 1.6). The defensible gains are accessibility, lower effort, and eyes-closed practice. Do not market voice as clinically better.

---

## 1. Findings: what students would use, what would annoy them

### 1.1 Table of evidence

| Finding | Number or quote | Source | Tag | What it means for us |
|---|---|---|---|---|
| Indian adolescents prefer text to voice for a mental-health chatbot | 69% text, 23% both, 7% voice (survey n=278, mean age 19, 12% under 18, 74% female, urban, English questionnaire; 12 interviews). "texting anywhere is fine even in public ... but voice chat only in my room" | https://arxiv.org/html/2503.08562v1 | P | Text is the default; voice is optional and private-place only. Sample skews urban, female, English. |
| Privacy and stigma dominate | 67% cite privacy; 60% want anonymity; social stigma 41.7% vs self-stigma 11.2%; 61% rarely or never discuss mental health with family; "I don't want it on record" | same | P | Store nothing; show what is saved; no registration friction beyond what exists. |
| Same paper's design advice | text default, multimodal option, India-specific helplines, memory only with consent, concise replies | same | P | Matches our direction. |
| Indians like voice notes | 48% of Indian respondents preferred or equally liked voice notes (YouGov 2024, adults); FRND app survey (n=12,666, app users, not a general sample): 66% say hearing a voice connects them most, 70% among Hindi users | https://theprint.in/feature/indian-social-media-users-voice-messaging-frnd-survey/3011813/ | S | Voice notes to friends are normal; that is not evidence students want to speak to software about distress. |
| WhatsApp added voice-message transcripts in India (Feb 2025) | title only | https://business-standard.com/amp/technology/tech-news/whatsapp-starts-rolling-out-voice-message-transcripts-in-india-how-to-use-125022600312_1.html | S | Students already read transcripts of voice; "speak then read the text" is a familiar pattern. |
| Hindi voice search exists since 2014; no share figure found | n/a | https://thinkwithgoogle.com/intl/en-apac/country/india/ok-google-how-is-voice-making-technology-more-accessible-in-india (redirected, not read) | S | No usable Hindi-voice usage number. I found none specific to college students. |
| Smart speakers in dorms raise stigma and privacy worries | opinion and a 2019 report: a student told a campus speaker "I feel depressed" and was pointed to federal financial aid | https://www.technologyreview.com/2019/12/27/131139/colleges-smart-speakers-in-dorms-privacy/ | S | Wrong answers to distress are worse by voice than by text because they are heard by others. |
| Code-switched speech hurts recognition | relative WER up 30 to 50% vs monolingual (HiACC paper); Hindi code-mixed spoken queries 44% WER baseline (a code-learner study, Indic ASR) | https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12329218/ ; https://arxiv.org/html/2601.15339v1 | S ; P | Hinglish dictation will be wrong often. The student must see and edit the text. |
| Data cost | average 25.51 GB per wireless user per month (March 2026); entry plans about Rs 299 for 28 days at 1 to 1.5 GB a day; about Rs 7 per GB (my arithmetic) | https://trai.gov.in/sites/default/files/2026-04/PR_No.46of2026.pdf | S | A 60 MB model is about 4% of one day on a 1.5 GB plan (ESTIMATE). Cost is tolerable; patience on weak networks is the issue, so opt-in, cached, never automatic. |

### 1.2 Where students speak: hostels and shared rooms (state it plainly)

Speaking aloud about mental health in a shared hostel room is a barrier. Roommates, wall-thin partitions, corridor noise and family-on-the-phone all mean the student may be overheard, and the stigma finding above (41.7% worry about others' reactions) is exactly about being overheard or found out. Design consequences, all in the specs below:

1. **Text first, always.** Every voice feature has a text equivalent on the same screen. Nothing is voice-only.
2. **Quiet mode** (device-level setting, persists on the device): hides every microphone control and blocks all spoken output. First visit asks one question: "Are you on headphones or somewhere private?" with "Text only" as the preselected answer.
3. **No audio output by itself, ever.** No autoplay, including the crisis reply. A crisis reply read aloud in a shared room can out the student; show the text and offer a "Listen" button.
4. **Headphone nudge** before the first spoken cue: "Use headphones if others are nearby." Browsers cannot reliably tell if headphones are in, so we ask; we do not guess.
5. **Whisper-friendly dictation**: no "speak louder" prompts; a visible live transcript so a quiet speaker can see it works.
6. **No wake word, no always-listening.** The mic opens only on a tap and closes on a tap or after 5 seconds of silence or 2 minutes (existing `MAX_SECONDS = 120`).

### 1.3 Accessibility

| Need | What voice gives | What we must do |
|---|---|---|
| Low vision, blind (TalkBack, VoiceOver users) | Screen readers already speak the page | Do not build our own reader. Keep controls labelled; speech output must not fight the screen reader (offer "Listen" only when no screen reader is detected is unreliable, so make Listen a button the user chooses, and let it stop instantly). |
| Dyslexia, reading in a second language | Hear the answer | F2 Listen button; keep the text visible and highlight nothing that moves. |
| Motor difficulty, RSI, one hand | Dictate instead of type | F3; large tap targets; OS Voice Control compatibility (visible label equals accessible name, WCAG 2.5.3, known criterion, not re-fetched). |
| Deaf or hard of hearing | None | Every audio cue has an on-screen cue (the breathing page already draws phases). |
| Cognitive load, anxiety | Short, calm steps | One instruction at a time; user-controlled pace; Pause and Stop always visible. |

Law: RPwD Act 2016 s.46 is cited for digital accessibility; whether WCAG 2.1 AA binds private sites is contested across the sources I found (W3C WAI lists the Act as covering public and private sectors; Deque says IS 17802 aligned to WCAG 2.1 is the benchmark; another source says WCAG is voluntary). GIGW 3.0 is government-facing. https://www.w3.org/WAI/policies/india ; https://www.deque.com/accessibility-compliance/apac/india/ (S). Treat WCAG 2.2 AA as our target regardless; confirm the legal point with counsel.

### 1.4 Language

- 94% of the 278 surveyed adolescents preferred English (P), but that survey was English-only, so it is biased. No Hindi, Hinglish or regional preference figure exists in what I found.
- Product rule: accept Hindi (Devanagari), Hinglish and English; reply in the language the student used last; offer a visible language switch (English, Hindi). Other Indian languages: not in MVP.
- Dictation output is mostly Devanagari for Hindi speech with English words in Latin script; Hinglish typed by students is Roman. The crisis floor covers Roman Hinglish with about 14 pattern lines and Devanagari with 4 (`ai/severity.py`). **Devanagari recall must be raised and clinician-reviewed before any STT ships** (existing open item O-20).
- Do not speak romanised Hindi with TTS: an English or Hindi voice reads Roman Hindi with the wrong phonetics (engineering judgement, UNVERIFIED). Speak Devanagari or English only.
- Hindi grammar marks the speaker's gender ("thak gaya" vs "thak gayi"). Use gender-neutral constructions in all Anya text, so neither Anya nor the student is assigned a gender.

### 1.5 Competitors in 2026: what exists, what is claimed, evidence, failures

| Product | Voice status | Evidence | Source | Tag |
|---|---|---|---|---|
| Headspace Ebb | Voice mode launched Dec 2025. English only, paid or trial members, US, UK, Canada, Australia, 18+. Claims a "multi-layered safety system" that flags high-risk language and shows crisis resources. Promised efficacy and safety studies in 2026; I found none published. Not available in India. | claim only | https://www.businesswire.com/news/home/20251208896917/en/Headspace-Rolls-out-Voice-Feature-for-Empathetic-AI-Companion-Ebb (fetch 403; from snippets) ; https://help.headspace.com/hc/en-us/articles/44080195624859-What-is-Ebb-Voice (403) | S |
| Wysa | Hindi chat launched 2024 (text, CBT exercises; WhatsApp plan). I found no voice input feature. | company-reported only | https://yourstory.com/socialstory/2024/04/wysa-launches-hindi-version-of-ai-therapy-app | S |
| Calm | No voice AI found. Audio is pre-recorded narration (sleep stories, meditations), not conversational. | n/a | search found nothing | S |
| Youper | Discontinued 30 Sep 2026 (already verified in `competitive-2026.md`). | n/a | docs/research/competitive-2026.md | P |
| Replika | Voice calls reported behind Pro (about USD 19.99 a month, affiliate sites); users report voice mode lacks shared memory with text (anecdote). Italian regulator fined Replika's operator EUR 5m over age gating and privacy (secondary report). | none | https://iapp.org/news/a/italy-s-dpa-reaffirms-ban-on-replika-over-ai-and-children-s-privacy-concerns | S |
| Pi | Free voice, per review sites; claim of tone detection unverified. | none | aicompanionpick.com (affiliate) | S |
| ChatGPT voice | Hindi voices exist per help text (Leher, Neer); a Hindi-tuned voice model reported as planned, not confirmed shipped. | MIT and OpenAI 4-week RCT (below) | https://yourstory.com/ai-story/hindi-tuned-ai-voice-model-openai-india-chatgpt | S |
| Gemini Live | Hindi since Oct 2024, eight more Indian languages announced. | none on wellbeing | https://business-standard.com/technology/tech-news/google-for-india-gemini-live-available-in-hindi-more-languages-to-follow-124100300478_1.html | S |
| Alexa+ India | Launched 16 Sep 2026, Hindi and Hinglish, early access free then Rs 2,000 a month for non-Prime; Amazon says it may mispronounce local nuances. | none | https://techcrunch.com/2026/09/16/amazon-launches-alexa-in-india-with-hindi-support/ | S |
| Sarvam (Saaras STT, Bulbul TTS, Indus app) | Indian-language STT and TTS APIs. Pricing pages conflict (Rs 30 per hour on AWS listing vs Rs 1.25 to 1.5 per minute on its own pages). Its pages say API inputs are not used for training; a third-party catalogue says its terms allow training. | none | https://www.sarvam.ai/speech-to-text | S |
| Bhashini (government) | Free-to-register ASR and TTS for Indian languages via ULCA keys; the terms I found cover the website, not API audio handling. | none | https://bhashini.gov.in/bhashadaan/en/terms-and-conditions | S |
| Google Assistant, Siri | Hindi supported for years; I did not verify current status. | n/a | not checked | n/a |

**What failed or warns.** Smart-speaker counselling pilots in dorms drew privacy and stigma objections (S above). Woebot and Youper closed (business and regulatory causes, not voice). Character.AI banned open-ended chat for under-18s by 25 Nov 2025 and Replika was fined over age checks (S). California SB 243 (effective 1 Jan 2026) requires companion-chatbot disclosure, a suicide-response protocol and, for known minors, break reminders (S: https://techcrunch.com/2025/10/13/california-becomes-first-state-to-regulate-ai-companion-chatbots). None of this is Indian law, but it shows where regulators look.

**Third-party hosted Indian STT and TTS (Sarvam, Bhashini, Gemini Live, ChatGPT voice) are blocked for student audio** under hard constraint 2 unless the owner approves in writing after reading each vendor's current terms. The default design uses none of them.

### 1.6 Evidence on voice and wellbeing

| Study | Finding | Tag |
|---|---|---|
| MIT Media Lab and OpenAI RCT, 981 people, 4 weeks, text vs neutral voice vs engaging voice (preprint, not peer reviewed) | Voice initially looked better than text for loneliness and dependence, but the advantage faded at high usage, especially with the neutral voice; personal conversations went with worse outcomes; authors call it a trend. https://arxiv.org/html/2503.17473v2 | S |
| Review of voice-based conversational agents for chronic and mental health (2021) | Studies report speech-recognition performance; modality comparison explicitly out of scope. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8042539/ | S |
| Spoken vs written emotional disclosure (Murray and Segal 1994 and later trials, via reviews) | About equally effective, modest effects; writing studied far more; one RCT in rheumatoid arthritis gave conflicting summaries of which mode helped. https://pmc.ncbi.nlm.nih.gov/articles/PMC3065513/ (S, summaries conflict, read the paper before citing) | S |
| Conversational-agent RCT meta-analyses | Small short-term effects (g about 0.3), mostly not lasting; no India college RCT (from `docs/research/product-market.md` section 3.1) | P (repo doc) |

Reading: voice is an input and output convenience, not a treatment. The one RCT signal is a caution: voice that feels like a person, used heavily, on personal topics, can backfire. This is why section 4 bans personas and caps use.

---

## 2. What decides the design: browser speech facts

| Fact | Source | Tag |
|---|---|---|
| In Chrome, `SpeechRecognition` normally uses a server engine: audio is sent to a web service. `processLocally = true` forces on-device; default false lets the browser choose. | https://developer.mozilla.org/docs/Web/API/SpeechRecognition/processLocally | P |
| Chrome's on-device Web Speech shipped in Chrome 135 "on desktop" (Windows, Mac, Linux; ChromeOS to follow). Android is not mentioned. Language packs download on request; a forum reply says about 60 MB each. Sites can require on-device with an "ondevice-only" mode and get an error if unavailable. | https://groups.google.com/a/chromium.org/g/blink-dev/c/VNOok2dbmHM | P ; pack size S |
| Safari (iOS 14.5+) exposes `webkitSpeechRecognition` and prompts before sending audio to Apple. Firefox desktop disabled by default (older versions), Firefox Android not supported in one table. | https://caniuse.com/speech-recognition | S |
| `speechSynthesis`: on Chrome Android the voice list may be unfiltered; if the language's voice pack is missing Chrome falls back to an English voice; prefer voices with `localService === true` for offline use. | https://readium.org/speech/docs/WebSpeech.html | S |
| In-browser Whisper: a developer reported tiny at about 2.7 s for a 24 s clip on a Mac M3 with WASM (real-time factor about 0.11), English, not a phone. A different engine (Shruti) reported 60 s of audio in 9.5 s on a Galaxy F62 with 2 threads. No Hindi in-browser phone measurement exists in what I found. | https://dev.to/fzsheik/how-i-built-a-private-audio-transcription-tool-in-browser-using-transformersjs-1fl0 ; https://huggingface.co/udgamlabs/Shruti | S |
| A Hindi fine-tune of Whisper tiny reports 14.21% WER on FLEURS Hindi (whisper normalisation); stock tiny far worse. Licence not checked. | https://huggingface.co/collabora/whisper-tiny-hindi | S |

**Consequences.**

1. The easy path (`webkitSpeechRecognition` with defaults) sends student speech to Google or Apple. It is **banned** here. Any recogniser we ship must be `processLocally`/on-device only, or a WASM model inside the page.
2. On the main target (a mid-range Android phone) browser on-device Hindi recognition is **unproven**. Plan A is detect-and-use if present (`SpeechRecognition.available` with `processLocally`; MDN page lists the static methods, I did not verify Android behaviour). Plan B is a WASM Whisper-tiny Hindi in a Web Worker, opt-in download, cached. Plan C costs nothing: tell the student to use the **keyboard's own microphone key** (Gboard or iOS dictation), which works in our text boxes with no code. Caveat for the consent text: that key is run by the phone maker and its audio handling is theirs, not ours.
3. Server-side STT is out: Render free (512 MB RAM, about 0.1 CPU) cannot run it, and audio would leave the student's device. `utils/voice_features.py` already needs optional librosa and numpy.

### 2.1 Latency budget (stated target, achievable)

| Path | Target | Achievable on a mid-range phone, free hosting | Basis |
|---|---|---|---|
| F1/F2 first spoken word after tap | under 0.5 s | about 0.2 to 0.8 s if a local voice is installed | ESTIMATE, measure |
| F3 partial text appears while speaking | under 1 s | only with browser on-device streaming; Whisper WASM is not streaming (result after stop) | MDN/blink-dev P; Whisper behaviour known |
| F3 final transcript after stop, 15 s utterance | under 3 s | 2 to 10 s with Whisper-tiny WASM (RTF 0.15 to 0.7) | ESTIMATE from two non-comparable data points above |
| F4 end of speech to first spoken reply | under 2.5 s | 4 to 12 s: end-of-speech 0.7 s + STT 2 to 10 s + server floor and template 0.3 to 1.5 s + TTS 0.3 s; a sleeping Render instance adds a cold start (DEPLOY_FREE; seconds to tens of seconds, not measured here) | ESTIMATE |

F3 fits (journaling is not turn-taking). F4 does not.

---

## 3. Feature specs

Common rules for every spec: microphone only on tap; no audio bytes sent to or stored on the server; the transcript is shown and editable before anything is saved or sent; **never auto-send**; Pause and Stop visible at all times; the text is always on screen; Quiet mode honoured; crisis floor runs on the final text exactly as on typed text (`ai.severity.classify` through `/api/chat` and the journal save). Files: no source file over 300 lines, so each feature is its own small module.

### F1. Spoken guided breathing and grounding (BUILD NOW)

- **User value:** eyes-closed practice; no need to watch the animation; helps low vision.
- **Flow:** On the breathing page the student picks a pattern and minutes (today's flow). New toggle "Spoken cues" (off by default; first use shows the headphone prompt). Press Start: a calm cue per phase ("Breathe in, 4"), spoken once at each phase change, then silence or a soft tick option. Pause stops speech at once; Stop ends the session; the existing "finished" state remains. Grounding: each step is read when shown; Next and Back work as now; Listen replays the current step.
- **Runs where:** browser only. `MFHBreath.create({onPhase})` already fires at every phase change; a new `static/js/speech-output.js` listens. No server change.
- **Content:** device TTS (`speechSynthesis`, `hi-IN` or `en-IN` voice with `localService`). Better: 15 to 25 short recorded clips by a counsellor volunteer, Opus mono 16 kbps = about 2 KB a second, so a 3-minute script is about 360 KB (my arithmetic), cached for offline. Pre-recorded avoids the missing-Hindi-voice problem. Needs a recording-consent and licence note.
- **Privacy text:** "Spoken cues play on your phone. Nothing is recorded or sent."
- **Failure modes:** no Hindi voice installed (Chrome silently speaks English): detect with `getVoices()`, show "No Hindi voice on this phone. Showing text cues" and offer English; screen locks and the animation frame loop stops (the engine uses `requestAnimationFrame`, which pauses in background tabs): request Screen Wake Lock and test on real phones; cues overlap on Pause-Resume: cancel the speech queue on every state change.
- **Safety:** no cue says anything clinical; stop-able within one frame; breathing holds longer than 4 s offered with a note for people with asthma or panic (clinician to approve wording).
- **Latency:** cue starts under 0.5 s after the phase edge (ESTIMATE). Cue length must fit the phase (4 s inhale: "Breathe in" only).
- **Effort:** 0.5 to 1 week. **Extends:** `static/js/breathing-guide.js`, `static/js/grounding.js`, `templates/breathing.html`.

### F2. Listen button on static text (BUILD NOW)

- **User value:** hear the six starter answers, a psychoeducation snippet or a tip; dyslexia, fatigue, second-language reading.
- **Flow:** each answer card has "Listen" (not autoplay). Press: button becomes "Stop"; a rate control (slow, normal); the text never changes. Language follows the text.
- **Runs where:** browser `speechSynthesis`; text comes from `utils/chat_templates.py` answers that already render. No server change.
- **Privacy text:** "Plays on your phone using the phone's voice."
- **Failure modes:** same as F1; long answers cut off by some Android engines (split by sentence); romanised Hindi mispronounced (do not offer Listen on Roman Hindi text).
- **Safety:** the saved crisis reply gets Listen only on tap; never spoken unprompted.
- **Latency:** under 0.5 s. **Effort:** 3 to 4 days including the shared `speech-output.js` (queue, cancel, voice pick, Quiet mode). **Extends:** `utils/chat_templates.py`, `static/js/inline_extracted/chat_inline_1.js` (287 lines: do not grow it; add a separate module).

### F3. Voice journaling by dictation (BUILD NOW if on-device works; otherwise guidance only)

- **User value:** speak a messy paragraph in Hindi or Hinglish instead of typing it; the saved result is ordinary journal text.
- **Flow:** Journal page, new button "Speak". First tap: one screen explains "Your voice is turned into text on this phone. The recording is not kept or sent. If your browser cannot do this on the phone, the button is hidden." The student picks Hindi or English, taps Start (timer, 2-minute cap, Stop). A live or final transcript appears in the journal text box with a notice "This is what the phone heard. Please check it." Words the recogniser was unsure of are underlined where the engine reports confidence. The student edits freely, then presses the usual Save. Discard clears it. The entry carries no "voice" flag.
- **Runs where:** browser only. Plan A: `SpeechRecognition` with `processLocally = true` and an "ondevice-only" requirement; Plan B: Whisper-tiny Hindi in a Web Worker, opt-in download (about 40 to 80 MB, ESTIMATE from 39M parameters, licence and exact size to confirm in `speech.md`); Plan C: keyboard mic key guidance. Server receives text only, through the existing journal POST, so the existing crisis scan on journal save runs unchanged.
- **Crisis rule:** the floor sees the text at Save (same as typed). The student has seen exactly what was heard because it sits in the box. If the engine returns a different transcript from what is shown (e.g. editing), the saved text is the shown text. If the student discards before saving, nothing is sent, as with typing.
- **Privacy and consent text (draft):** "Speak turns your voice into text on your phone. Your recording is not saved and does not leave your phone. Only the text you choose to save is sent to MindFull Horizon. Phone keyboard dictation, if you use it instead, is handled by your phone maker." Consent record: a line in the existing consent flow, stored as a boolean `voice_input_notice_seen` (needs an Alembic migration, or reuse the existing consent table).
- **Failure modes:** noisy hostel (engine returns empty or junk): show "Could not hear clearly. Try again or type." and keep the audio nowhere; accents and code-mixing (WER 30 to 50% worse): edit step is mandatory, no "save as is" shortcut on first use; mis-transcribed crisis phrase: the floor's Devanagari list is thinner than Roman (section 1.4), so run the transcript test in section 8.3 before release; negation dropped ("do not want to die" heard as "want to die"): the floor already turns a negated hit into a soft check-in and does not drop it, and the student sees the text; permission denied: reuse the existing permission copy in `patient_voice_logs_inline_1.js`; Safari/iOS: prompts before sending to Apple, so hide Speak there unless on-device is confirmed.
- **Safety:** the recording is never uploaded; a visible "Recording" state with a Stop button; the mic stream is released on Stop (existing `releaseStream`); no points or streaks (the existing voice log awards 20 points, see section 6).
- **Latency:** partial text under 1 s only with the browser engine; Whisper WASM gives the final text 2 to 10 s after Stop (ESTIMATE). Acceptable for journaling with a visible "Turning your speech into text" status.
- **Effort:** 2 weeks for Plan A + C with the transcript test; +2 to 3 weeks for Plan B. **Extends:** `static/js/inline_extracted/patient_voice_logs_inline_1.js` (recorder, permission copy, 120 s cap and stream release are reusable; split it, since it is 200 lines and a new module must not inflate it), `templates/patient_voice_logs.html`, journal template; `utils/voice_features.py` is not used by F3.

### F4. Hands-free voice chat in Hindi or Hinglish (DO NOT BUILD; ship dictate-then-listen)

- **User value claimed:** talk to Anya without typing. **Reality:** today `/api/chat` returns the deterministic floor, a few fixed replies and saved starter answers (`AI_SEND_PERSONAL_TEXT=0`, no local LLM). A voice front-end on that is a talking menu. STT latency (section 2.1) breaks the turn-taking that makes voice feel natural, and the hostel problem is greatest here (back-and-forth speech is the most audible).
- **What to ship instead (free from F2 and F3):** a Speak button in the chat input fills the text box (never sends); the student presses Send; the reply shows as text with a Listen button. This is half-duplex, student-paced, fully visible. Barge-in is trivial: any tap stops speech.
- **Revisit when:** a local small model that can add safe replies exists on the free tier (see `llm-agents.md`, `runtime-hosting.md`) and measured on-device STT on target phones is under 3 s for 10 s of speech.
- **Failure modes and safety (if revisited):** crisis text spoken aloud must never be auto-played; the floor must see the transcript before any reply; a "Talk to a person" control must always be reachable; session cap 10 minutes.
- **Effort:** 3 to 4 days for the half-duplex version (button plus wiring to the existing `post('/api/chat', ...)` in `chat_inline_1.js`); full hands-free: not estimated, not recommended.

### F5. Spoken safety-plan walkthrough (BUILD LATER)

- **User value:** at high distress reading is hard; hearing one's own plan step by step (warning signs, coping steps, people to call, safe place) helps.
- **Flow:** On the safety plan page "Walk me through it" (never autoplay). One step at a time, Next and Back, each step read aloud on request, the student's own words shown big. Last step: "Call Tele-MANAS 14416" and "Call 112" as `tel:` links. Plain "Stop" always.
- **Runs where:** browser TTS on text from the student's own saved plan (the page already has it); no new network call.
- **Consent and privacy:** "Your plan is read by your phone's voice. Nothing is sent." Other people may hear it: headphone prompt each time (not remembered).
- **Failure modes:** plan text in romanised Hindi is mispronounced; empty steps; TTS missing voice. If the walkthrough is open when the floor trips elsewhere, show the crisis block (fixed text) first.
- **Safety:** clinician review of the fixed framing lines ("This is your plan. You wrote it when you were calmer.") before release; no AI-generated content in it.
- **Latency:** under 0.5 s. **Effort:** 3 to 4 days after F2. **Extends:** the safety-plan template and `speech-output.js`.

### F6. Voice check-in for mood, spoken 1 to 10 (DO NOT BUILD)

- Reason: speaking "saat", "seven", "सात" or "so-so" to a recogniser that is 30 to 50% worse on mixed speech, then confirming, is slower than one tap on a 1 to 10 control, and it announces a mood score aloud in a shared room. It also tempts engagement mechanics on mood scores, which the project forbids. If a student cannot tap, OS Voice Control already says "tap 7". Spec withheld; no engineering weeks.

### F7. Voice navigation for accessibility (DO NOT BUILD)

- Reason: Android Voice Access, iOS Voice Control, TalkBack and VoiceOver exist and are better than anything we can build. Our job: visible labels equal accessible names, no gesture-only controls, 24 px minimum targets (WCAG 2.2), `aria-live` for status ("Recording", "Stopped", "Heard: ..."), no focus traps. Add these checks to `tools/e2e/`. Effort: part of normal QA, about 2 days.

### F8. Audio psychoeducation (BUILD LATER, folded into F2)

- Two or three short clips (under 2 minutes) of existing starter answers, recorded by a counsellor volunteer, Opus 16 kbps (about 240 KB for 2 minutes, my arithmetic). Same Listen button; played from our static files, cached. Only after the counsellor recording and licence question (owner question 3). Effort: 2 days plus recording time.

---

## 4. Conversational agent UX principles (text and voice)

Grounded in `ai_prompts/psychologist_system.txt`, `utils/chat_templates.py` and `ai/service.py`. Persona name is Anya; keep it as a label, not a character.

1. **Say what it is, every session.** First line: "I am an automated assistant, not a person and not a counsellor. I cannot diagnose or give medical advice." Spoken output repeats it once per session. (`ai_policy.assistant_kind()` already switches "an AI assistant" or "an automated assistant" to match reality; keep that honesty.)
2. **No persona fiction.** No backstory, no "I missed you", no "I feel", no claims to understand or remember beyond what is stored. No gender, no human voice mimicry. Voice: one plain synthetic voice, not "engaging" (the MIT and OpenAI RCT linked heavy, personal, engaging-voice use to worse outcomes).
3. **Turn length.** Text: 4 to 6 short sentences (matches the starter answers). Spoken: at most about 50 words, roughly 20 seconds at 150 words a minute (my arithmetic). One idea, one question.
4. **Silence.** Never fill silence. In dictation, stop after 5 s of quiet and show what was heard. No "are you still there". A student who stops talking is allowed to stop.
5. **Distress.** Distress words get the fixed floor reply from `ai/service.py`: acknowledge, ask if safe, helplines, someone they trust nearby. In voice, the reply is text with tap-to-call numbers, not an automatic speech. After a crisis flag stop cheerful prompts and points (already in `docs/SAFETY_RESEARCH.md`).
6. **Repair.** When the transcript looks wrong or the reply misses: "I may have heard that wrong. Is this what you meant?" with the text shown and one-tap Edit. Never silently correct.
7. **Scope.** If asked for diagnosis, medicines or therapy: say it cannot and point to the counsellor or a doctor (Telemedicine Practice Guidelines 2020 clause 5.4, verified in `competitive-2026.md`).
8. **Cultural fit.** Exams, placements, family pressure, "log kya kahenge", hostel life, loneliness far from home are common topics; do not moralise, do not default to "talk to your parents" (family can be the stressor): say "someone you trust". Avoid Western therapy jargon. Hindi in gender-neutral forms; no forced Devanagari or forced English.
9. **Code-mixing.** Reply in the last language used; keep English technical words as the student writes them ("stress", "exam"); offer a language switch; never ask the student to rephrase "in proper Hindi".
10. **Dependence.** Daily cap on chat and voice minutes (the chat budget exists in `llm_guard.BUDGET`); after a long session say "This might be a good time to take a break or talk to someone"; surface a counsellor option when distress repeats across days (the multi-turn aggregation gap that a 2026 preprint on chatbot failure modes also names: https://arxiv.org/pdf/2602.22775, S).
11. **Warm handoff.** A persistent "Talk to a person" control: book a counsellor (the existing `/api/chat/book-appointment` route and `schedule` page), Tele-MANAS 14416, KIRAN 1800-599-0019, 112 from the one helplines config. State plainly what a counsellor will and will not see ("an alert without your words" is already in `CRISIS_REPLY`).
12. **Nudges.** No voice nudges, no push for voice features. At most one optional daily reminder the student sets themselves, with an off switch in two taps. No streaks, no points on mood or assessment scores, no guilt copy.
13. **Honesty about errors.** Say when the saved answer is a "Saved answer" (the chat page already labels this) and when AI is unavailable.
14. **Never claim what is false:** no "encrypted" or "private" unless true (project rule); say "not saved" only where the code proves it (test in section 8.3).

---

## 5. Voice-specific risks

| Risk | Where it bites | Decision |
|---|---|---|
| Voice recordings as sensitive personal data | The words reveal mental-health state. DPDP Act 2023 has no sensitive-data tier (weight of sources; a Chambers comparison disagrees); until 13 May 2027 the SPDI Rules treat mental-health information as sensitive (Taxmann, S: https://www.taxmann.com/post/blog/spdi-rules-vs-dpdp-act). Voice recordings are not classified in any source I found; assume ordinary personal data containing health content. | Store no audio anywhere; transcript is the student's own saved text; document in `docs/PRIVACY_AND_CONSENT.md` the exact paths. |
| Voiceprints as biometrics | A speaker embedding can identify a person. | Never compute or store speaker embeddings, diarisation or voice identity. Existing `mean_pitch`, `mean_spectral_centroid`, `mean_zcr` per log are speaker-characterising; stop collecting them (retire the voice log analysis). |
| Emotion from voice | `classify_emotion` uses fixed cut-offs (pitch 150 and 200 Hz, energy, ZCR). Typical pitch differs by sex, so a fixed threshold labels voice type, not mood (my inference; no validation in the repo; the page already says "can be wrong"). | Retire. Under project rule "no fake claims" it should not be shown as a "tone" at all. |
| Accidental recording | A mic left open in a hostel; background talk of third parties. | Tap to start, tap or silence to stop, 2-minute cap, visible Recording state, stream released on stop (existing), no background capture, no wake word. Third-party audio is never kept because no audio is kept. |
| Third-party audio | Roommates' voices in the clip. | On-device only; no upload; say so in the consent text. |
| Minors | Product is 18+; `consent.html` has a self-declared 18+ checkbox; no date of birth is stored (grep found none). DPDP Rules need verifiable parental consent for under-18s (Livelaw, S: https://www.livelaw.in/amp/top-stories/digital-personal-data-protection-rules-2025-notified-309928). Replika and Character.AI show regulator and litigation pressure on weak age checks. | Keep voice off for anyone who has not confirmed 18+; do not add features that attract teens; the 18+ gate stays text. |
| Recording consent | A new purpose (microphone) needs an itemised, plain-language notice and withdrawal. DPDP main obligations are phased about 18 months from Nov 2025 (Bar and Bench, S: https://www.barandbench.com/amp/story/law-firms/view-point/meity-notifies-final-digital-personal-data-protection-rules-2025). | Consent line per feature (F3), withdrawal = Quiet mode plus data deletion already built. |
| Retention | "Store nothing" for audio. Transcript is a journal entry with the journal's retention (operator task: retention periods, `PRIVACY_AND_CONSENT.md`). | Test asserts no audio file or blob persists (section 8.3). |
| Deepfake, spoofing | Not relevant: no voice authentication. | Do not add voice login. |
| Accessibility law | See 1.3. | WCAG 2.2 AA target; confirm legal scope with counsel. |
| Hosted-vendor leakage | Chrome and Safari defaults, Gboard dictation, Sarvam or Bhashini APIs all move audio off-device. | Only on-device recognition in our code; disclose that keyboard dictation is the phone maker's. |

Existing-code observations (not run, flagged for the owner):

1. `static/js/inline_extracted/patient_voice_logs_inline_1.js` builds the upload with `new Blob(chunks, { type: 'audio/wav' })` and a `voice_log.wav` name, but `MediaRecorder` produces WebM/Opus (Chrome) or MP4 (Safari) unless configured. `extract_features` then calls librosa on a `.wav`-suffixed temp file; on failure it returns `{}` and `'neutral'` silently (`utils/voice_features.py` catches everything). UNVERIFIED: I did not run it, but many logs may be stored as "neutral" with empty features.
2. `app.py` awards 20 points (`award_points(user_id, 20, 'voice_log', ...)`) for a voice log that carries an emotion label. The project rule is "never attach points or streaks to assessment or mood scores"; a tone label is close to a mood score. Owner call.
3. The voice log page tells the truth about what is kept; F3 would let us delete the audio upload route, `utils/voice_features.py` and `requirements/voice.txt` entirely, which is less code and less risk.

---

## 6. Recommended 4-week MVP and later roadmap

Team: 1 to 2 people. Rules: each file under 300 lines; no new routes in `app.py`; JS without inline handlers or Jinja tags; run `tools/e2e/` for every UI change.

| Week | Build | Done when |
|---|---|---|
| 1 | `static/js/speech-output.js` (voice pick, `localService`, missing-Hindi-voice detection, queue cancel, rate, Quiet mode, headphone prompt) and F2 Listen on the six starter answers and one tip | Works on 3 phones (one low-end Android, one iOS, one desktop); Quiet mode blocks all audio and hides all mic controls; e2e test covers it |
| 2 | F1 spoken breathing via `MFHBreath.onPhase`; grounding steps spoken; Wake Lock test; decision on counsellor-recorded clips | 3-minute box-breathing session runs with the screen on and with Pause, Resume, Stop behaving; text cues if no voice |
| 3 | F3 dictation Plan A plus Plan C: feature-detect on-device Hindi and English; Speak button in journal and chat input (fills, never sends); consent text; Devanagari crisis-phrase additions with clinician and native-speaker review | Transcript test (8.3) passes; no audio persisted; Speak hidden where on-device is not confirmed |
| 4 | Usability test with 5 to 8 students (section 8), fix list, docs (`PRIVACY_AND_CONSENT.md`, `ARCHITECTURE.md`), retire voice-log analysis (if the owner agrees) | Test pass bars met or the feature is cut |

**Roadmap after week 4 (each gated by a measured result):**

1. Plan B in-browser Whisper-tiny Hindi, only after `speech.md` confirms licence, size and phone speed; opt-in download on Wi-Fi; Web Worker; progress shown; cache and remove-from-device button. 2 to 3 weeks.
2. F5 spoken safety-plan walkthrough. 3 to 4 days.
3. F8 counsellor-recorded psychoeducation clips. 2 days plus recording.
4. F4 full hands-free chat: only if a local model and phone STT under 3 s per 10 s speech both exist. Otherwise never.
5. Cut list (never): voice mood scores, voice navigation, voice login, emotion-from-voice, personas, proactive voice nudges, streaks for voice use.

### 6.1 Success metrics (all targets are PROPOSALS)

| Metric | Target | How measured |
|---|---|---|
| Dictation completion: sessions that reach Save among sessions that press Start | at least 60% | aggregate counter without user ids, or observed in usability test |
| Edit rate: share of dictated entries where the student changed more than 10% of characters | report only; above 30% means the recogniser is not good enough | counted in the browser, only a count is sent |
| Crisis-floor recall on dictated transcripts vs the same phrases typed | at least 90% of typed recall, and no tested phrase with zero hits | transcript test (8.3), a pre-release gate |
| Zero audio stored | 0 audio rows or files | automated test and code review |
| Quiet mode found and used | 5 of 6 find it within 30 s | usability test |
| Accessibility | no critical issue with TalkBack and VoiceOver on the three flows | manual test |
| Safety incidents | 0 auto-played crisis replies, 0 auto-sends | e2e test |
| Perceived helpfulness | usability scale at least 70; "would use in my own room" at least 4 of 6 for F1 | test questionnaire |
| Do not measure | points, streaks, minutes spoken as a goal | project rule |

---

## 7. Fit for MindFull Horizon: what each adds over the rule-based floor

| Candidate | Plugs into | Adds over today | Gemini calls and saved answers | Cost |
|---|---|---|---|---|
| F1, F2 | `breathing-guide.js`, `grounding.js`, `chat_templates.py`, new `speech-output.js` | Audio access to existing content | None; saved answers read aloud | 1 to 1.5 weeks, no RAM on server, device TTS; risk: missing Hindi voices |
| F3 | journal page, `patient_voice_logs_inline_1.js` recorder parts, chat input | Lower effort to write; transcript runs through the same floor | None | 2 weeks (+2 to 3 for WASM); download 40 to 80 MB ESTIMATE; risk: accuracy, Devanagari floor gaps |
| F5 | safety-plan page | Plan read aloud | None | 3 to 4 days |
| Floor interaction | `ai/severity.py` | Voice never lowers the floor; transcripts only add text to scan. A model may later add signals, never remove (constraint 3) | None | Devanagari patterns need review before F3 |

---

## 8. Test plan

### 8.1 Usability test: 5 to 8 students, 30 to 40 minutes each, in person or video, on their own phones

**Recruit:** 5 to 8 adult (18+) students: at least 3 hostel residents, 2 day scholars, 1 who uses TalkBack or VoiceOver or reports low vision, 1 who reports dyslexia, at least 1 on a low-end Android on mobile data, mixed Hindi-first and English-first. Use a test account with fictional scenario text; **never ask for real distress and never record their screen audio**; give a standard distress-support sheet and a counsellor on call. Ethics sign-off (owner question 4).

**Tasks (observe, do not help for the first minute):**

1. Open breathing, choose box breathing for 2 minutes, turn on Spoken cues. Observe: do they find the toggle; do they notice the headphone prompt; do they pause and resume; do they close their eyes.
2. Find a way to make the app silent. Observe: time to find Quiet mode; whether they trust it.
3. Open a starter answer ("Stress before exams") and listen to it, then stop it midway.
4. Journal: read the scenario aloud ("exam kal hai, bahut tension ho raha hai") using Speak, check the text, fix one error, save. Observe: do they read the transcript; do they fix errors; do they press Save without reading; reaction to a wrong word.
5. Repeat the same sentence with noise (tap, a friend talking). Observe: reaction to "Could not hear clearly".
6. In chat, dictate a message, then choose Send. Observe: do they expect auto-send; do they understand it did not send.
7. Type the fixed crisis scenario sentence (not spoken) and read the reply; then press "Talk to a person". Observe: do they find the helpline and counsellor option; do they understand what the counsellor sees.
8. Open the privacy notice for Speak. Ask them to say in their own words what is saved.

**Questions after:** Where would you use this: hostel room, library, home, never? What would you not say out loud? Who might overhear you? Did you think Anya was a person at any point? What did the voice get wrong? Would you rather type, speak or listen, for what? What data do you think we keep? What made you hesitate? Would this make you more or less likely to talk to a counsellor?

**Observe:** hesitation before pressing the microphone; whispering; glances around; use of headphones; unprompted switch to typing; time to complete; errors tapped past; screen reader focus order; confusion about language switch; whether anyone calls Anya "she" or "he".

**Pass bars (proposals):** at least 5 of 6 complete dictate, edit, save unaided; every participant sees the "what was heard" text before saving; no participant believes Anya is a person; at least 5 of 6 find Quiet mode in 30 s; zero crisis-reply auto-plays; the accessibility participant completes tasks 1, 3, 4 with TalkBack or VoiceOver; usability score at least 70. If dictation fails, ship F1 and F2 only (they stand alone).

### 8.2 Smallest experiment for F3 (does dictation help?)

Within-subject, 8 students, 2 sessions: write a 100-word journal entry about a fictional prompt by typing in one session and by dictating in the other (order randomised). Measure completion time and edit rate (not wellbeing). Pass: dictation at least 30% faster including the edit step, and edit rate under 30%. This measures effort, not outcomes: no outcome claim is made.

### 8.3 Crisis-floor transcript test (a release gate for F3)

1. Take the constructed phrases from `docs/review/generated/crisis_phrases.csv` (about 1,400 rows; constructed fixtures, not real student data) and pick 40 across Roman Hinglish, Devanagari and English, plus 20 near misses (idioms, negations, third-person).
2. Have 5 adult volunteer speakers with consent read each phrase on 3 phone models, with and without noise; run the on-device recogniser; log (not store audio) only the transcript.
3. Run `ai.severity.classify` on the typed phrase and on the transcript. Metrics: recall on transcripts vs typed, false positives on near misses, list of phrases that lose their hit.
4. Pass: transcript recall at least 90% of typed recall and no tested true-crisis phrase with zero transcript hits; failures lead to floor pattern additions reviewed by a clinician and a native speaker (O-20), then re-run.
5. Never train or tune on real student speech or text.

### 8.4 What would convince me voice is worth continuing

- On-device Hindi dictation edit rate under 30% on target phones in the usability test, **and** the transcript test passes.
- At least 4 of 6 students say they would use spoken breathing in their own room.
- No safety incident in the test. If any fails, cut the feature that failed, not the safeguard.

---

## 9. Cross-notes

When I finished, `docs/research/ai/` held one other report: `evidence-safety-eval.md` (read the voice-related rows). Agreements and differences:

- **Agree:** remove the voice emotion label (their 2.1 and priority 3); TTS read-aloud of fixed guides is "build now if cheap" (their priority 5, my F1 and F2); voice biometrics, speaker identity and voice-based risk scoring are "do not build" (their priority 13); same floor on the transcript, student edits, no audio kept; multi-turn OpenAI and MIT RCT cited the same way.
- **Differs (small):** they rank STT for journal or chat as "build later" (priority 8, weeks 2 to 3, gated by WER on Hinglish). I put F3 in week 3 of the MVP, but only as a gated release: it ships only if the transcript test (8.3) passes, otherwise the student gets keyboard-dictation guidance. If the owner wants one rule, follow theirs: STT after the held-out set exists.
- **Numbers to reconcile:** their pass bar is WER at most 20% and crisis-term miss rate no worse than typed baseline; mine is edit rate under 30% and transcript recall at least 90% of typed recall. Use theirs for the WER bar and mine for the crisis-term paired test. Their held-out set A (300 items, at least 50 in Hinglish or Devanagari, authored by people who have not seen the regexes) should replace my 40 plus 20 phrases in 8.3 once it exists. They count only 16 Devanagari cases in `crisis_test_cases.csv`, which fits my finding that the Devanagari floor is thin.
- **Code pointer correction (theirs):** `routes/audio.py` holds music and audio routes only; the voice upload handler is still in `app.py:509` (`/api/upload-voice`), which breaks the "no new routes in app.py" rule's spirit and should move to a blueprint when touched.
- **Add from them:** per-feature env flags (`AI_STT`, `AI_TTS`, a kill switch) and a separate consent line per feature; both fit F1 to F3 and I adopt them.

Reports not yet present at that time, and the answers that would change mine:

| File | Question for it | If the answer differs |
|---|---|---|
| `speech.md` | Does `SpeechRecognition` with `processLocally` work for hi-IN on Chrome for Android? What is the licence, size and phone speed of Whisper-tiny Hindi (and Hinglish) in a browser worker? | If Android on-device Hindi works natively, Plan B is dropped and F3 becomes 1 week. If the model is non-commercial or over 100 MB, F3 stays Plan C. |
| `encoders-nlp.md` | A small classifier that adds crisis signals on Devanagari and Hinglish text (never lowers the floor); robustness to ASR noise | Could raise transcript recall; I assumed only regex. |
| `llm-agents.md` | Is there a local model that fits free hosting for reply generation? | If yes, F4 could be revisited; today I assume none. |
| `runtime-hosting.md` | Would a Hugging Face Space count as "our own server"? | I assumed audio never leaves the phone; a Space would still be a third-party host. |
| `datasets-finetuning.md` | Licensed Hinglish and Hindi speech sets for evaluation only | Would enlarge the transcript test beyond volunteers. |
| `evidence-safety-eval.md` | Eval design for crisis recall | Replace my 8.3 with theirs if stronger. |

I have no conflicts to report yet. Numbers in my report that are estimates and should be replaced by measurements: the phone RTF range, the model download size, TTS start latency, and the end-to-end F4 budget.

---

## 10. Questions for the owner

1. **On-device only, even if that means no Hindi dictation on some Android phones in the MVP.** OK to ban the browser default recogniser (audio goes to Google or Apple) and fall back to "use your keyboard's microphone key", accepting that this key is the phone maker's? (Recommended: yes.)
2. **Retire the voice-log "tone" guess and its 20 points?** No validity evidence, speaker-characterising numbers stored, and points on a mood-like label sit badly with the project rule. Retiring it lets us delete the audio upload and librosa. (Recommended: yes, after F3 ships.)
3. **Who records the human voice clips** for breathing and grounding (a college counsellor volunteer, with written consent and licence), or is synthetic device voice acceptable?
4. **Usability test ethics:** who signs off at the college (counsellor, ethics committee), and is an incentive allowed? Needed before week 4.
5. **Default for first-time users:** confirm "text only until the student opts into audio" (recommended), rather than a tour that turns sound on.
6. **Third-party hosted Indian STT or TTS (Sarvam, Bhashini):** do you want me to read their current terms for a possible written approval later, or keep them out for good? Default here: out.

---

## Sources (all accessed 2026-11-25)

P (read): https://arxiv.org/html/2503.08562v1 ; https://arxiv.org/html/2601.15339v1 ; https://developer.mozilla.org/docs/Web/API/SpeechRecognition/processLocally ; https://groups.google.com/a/chromium.org/g/blink-dev/c/VNOok2dbmHM ; repo docs `docs/research/competitive-2026.md`, `docs/research/product-market.md`, `docs/SAFETY_RESEARCH.md`, `docs/PRIVACY_AND_CONSENT.md`, and code files named in the text.
S (snippets, UNVERIFIED): https://theprint.in/feature/indian-social-media-users-voice-messaging-frnd-survey/3011813/ ; https://business-standard.com/amp/technology/tech-news/whatsapp-starts-rolling-out-voice-message-transcripts-in-india-how-to-use-125022600312_1.html ; https://www.businesswire.com/news/home/20251208896917/en/Headspace-Rolls-out-Voice-Feature-for-Empathetic-AI-Companion-Ebb ; https://help.headspace.com/hc/en-us/articles/44080195624859-What-is-Ebb-Voice ; https://yourstory.com/socialstory/2024/04/wysa-launches-hindi-version-of-ai-therapy-app ; https://business-standard.com/technology/tech-news/google-for-india-gemini-live-available-in-hindi-more-languages-to-follow-124100300478_1.html ; https://yourstory.com/ai-story/hindi-tuned-ai-voice-model-openai-india-chatgpt ; https://techcrunch.com/2026/09/16/amazon-launches-alexa-in-india-with-hindi-support/ ; https://www.sarvam.ai/speech-to-text ; https://bhashini.gov.in/bhashadaan/en/terms-and-conditions ; https://arxiv.org/html/2503.17473v2 ; https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8042539/ ; https://pmc.ncbi.nlm.nih.gov/articles/PMC3065513/ ; https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12329218/ ; https://readium.org/speech/docs/WebSpeech.html ; https://caniuse.com/speech-recognition ; https://huggingface.co/collabora/whisper-tiny-hindi ; https://huggingface.co/udgamlabs/Shruti ; https://dev.to/fzsheik/how-i-built-a-private-audio-transcription-tool-in-browser-using-transformersjs-1fl0 ; https://trai.gov.in/sites/default/files/2026-04/PR_No.46of2026.pdf ; https://www.barandbench.com/amp/story/law-firms/view-point/meity-notifies-final-digital-personal-data-protection-rules-2025 ; https://www.livelaw.in/amp/top-stories/digital-personal-data-protection-rules-2025-notified-309928 ; https://www.taxmann.com/post/blog/spdi-rules-vs-dpdp-act ; https://www.w3.org/WAI/policies/india ; https://www.deque.com/accessibility-compliance/apac/india/ ; https://techcrunch.com/2025/10/13/california-becomes-first-state-to-regulate-ai-companion-chatbots ; https://fortune.com/2025/10/29/character-ai-ban-children-teens-chatbots-regulatory-pressure-age-verification-online-harms ; https://iapp.org/news/a/italy-s-dpa-reaffirms-ban-on-replika-over-ai-and-children-s-privacy-concerns ; https://www.technologyreview.com/2019/12/27/131139/colleges-smart-speakers-in-dorms-privacy/ ; https://arxiv.org/pdf/2602.22775.
