# Small language models and a safe conversational agent for MindFull Horizon

Agent: LLM-AGENTS. Date of research and access date for every URL below: 2026-11-25. Read first: `AI_VISION.md` constraints (zero rupees, no personal text to external AI, deterministic crisis floor authoritative, India languages, licences, ethics).

Marks used: **VERIFIED** = read on the page this session. **SNIPPET** = seen only in a search result. **VENDOR** = the model maker's own claim. **UNVERIFIED** = from memory or a low-quality source; do not rely on it. **ESTIMATE** = my arithmetic, not measured.

## 0. Bottom line (read this if nothing else)

1. **A small LLM is not what the chat is missing today.** With `AI_SEND_PERSONAL_TEXT=0` (the default), any non-crisis message gets `off_reply()` ("no AI model reads what you write here, so I cannot talk it through", `ai/replies.py`). The gap is a useful, vetted, instant answer, not fluent generation. Intent routing plus retrieval over clinician-written snippets (Design A) closes most of that gap with zero model risk, zero GPU and no new dependency of note.
2. **No published evidence shows that a 4B-or-smaller model gives mental-health benefit.** The best pooled evidence for any chatbot is small (g about 0.3 on depression and anxiety, short follow-up) and the difference between LLM and rule-based bots is "not practically significant" (section 1.6). Small models hallucinate more, are easier to jailbreak, and are weak in Hinglish (sections 1.2 to 1.4).
3. **Under the owner's privacy rule only two places can run a model on student text: the student's own device (browser) or a server we run.** Render free (512 MB, 0.1 CPU) cannot hold even a 0.5B model. Every free hosted API fails or needs written approval (section 1.5). Cloudflare Workers AI is the only one whose official docs clearly say no training on customer content.
4. **Verdict:** build Design A now (about 3 to 4 weeks plus clinician time). Design B (on-device model used only as a selector among vetted snippets, opt-in) later, only if the section 5 experiment passes. Design C (free-form generative small LLM) do not build.

## 1. Findings

### 1.1 Small open-weight models (as of 2026-11-25)

Sizes are Q4_K_M GGUF file sizes read from bartowski or unsloth repos (VERIFIED page reads, but quantiser repos, not the vendor). "Hindi" is what the vendor says, not a measurement.

| Model | Params | Q4_K_M | Licence | Hindi / Indic claim | Notes |
|---|---|---|---|---|---|
| Qwen3.5-0.8B (Mar 2026) | 0.8B | 533 MB | Apache 2.0 (HF card, VERIFIED for 2B/0.8B) | "201 languages and dialects", Hindi not named (VENDOR) | Includes a vision encoder; non-thinking by default |
| Qwen3.5-2B | 2B | 1.28 GB | Apache 2.0 (VERIFIED) | same; MMMLU 63.1 thinking, 56.9 non-thinking, MMLU-ProX 52.3 (29 langs), INCLUDE 55.4 (VENDOR) | Card warns of thinking loops in thinking mode |
| Qwen3.5-4B | 4B | 2.74 GB | Apache 2.0 (SNIPPET) | same | Artificial Analysis: 80% hallucination rate on AA-Omniscience, 12.8% accuracy (VERIFIED article) |
| Qwen3 0.6B / 1.7B / 4B (2025) | 0.6 to 4B | 0.46 / 1.28 / 2.5 GB | Apache 2.0 for all six dense sizes (Qwen blog, VERIFIED) | 119 languages; Hindi listed among Indo-Aryan (VENDOR) | Older than Qwen3.5 |
| Qwen2.5-3B | 3B | about 2 GB | **qwen-research, non-commercial: BLOCKED** (SNIPPET of licence label) | n/a | Other Qwen2.5 sizes not checked |
| Gemma 4 E2B / E4B (Apr 2026; sources say 2 April, one URL says March) | 2.3B / 4.5B effective (5.1B / 8B with embeddings) | E2B **3.46 GB**; LiteRT-LM file 2.58 GB | **Apache 2.0** (Google blog, HF card VERIFIED) | pre-trained on 140+ languages, "35+ out of the box", Hindi not named; MMMLU E2B 67.4, E4B 76.6 (VENDOR) | Big download because of per-layer embeddings |
| Gemma 3 1B / 4B, Gemma 3n | 1B / 4B | 0.81 / 2.49 GB | **Gemma Terms of Use + Prohibited Use Policy**: flow-down of use restrictions to every recipient of derivatives (SNIPPET) | n/a | Policy bars "unlicensed practice of ... medical/health" (3.6) and "automated decisions ... affecting well-being" (3.4) (read on a mirror reached by Google's redirect). Avoid; Gemma 4 replaces it |
| Llama 3.2 1B / 3B | 1.23B / 3.21B | 0.81 / 2.02 GB | Llama 3.2 Community Licence; 700M MAU clause irrelevant for us (SNIPPET); AUP bars "unauthorized or unlicensed practice of any profession" (1d) and self-harm, suicide, eating disorders as harm activities (2e) (VERIFIED on dev.meta.ai) | **Hindi is one of 8 official languages (VERIFIED model card)**; multilingual MMLU Hindi **33.5 (1B), 43.3 (3B)**, vs Llama 3.1 8B 50.9 (VENDOR table, 5-shot; chance is 25) | Attribution and naming terms exist (UNVERIFIED, read the licence). Gated download |
| Phi-4-mini-instruct | 3.8B | 2.49 GB | MIT (SNIPPET) | 23 listed languages, **Hindi not listed** | Too big for browser use |
| Granite 4.0 nano (Oct 2025) | 350M, 1B | 223 MB (350M-H) | Apache 2.0 (SNIPPET) | Hindi **not in the listed languages**; IBM says Indic data were in training and quality is "limited and often noisy" (SNIPPET) | Hybrid SSM variants; plain-transformer variants exist for llama.cpp |
| SmolLM2 1.7B / 360M / 135M | 1.7B etc | 1.06 GB (1.7B) | Apache 2.0 (SNIPPET; mirrors disagree for 135M) | English only | Hinglish bench: 9% normalised match (below) |
| SmolLM3 3B | 3B | 1.92 GB | Apache 2.0 (VERIFIED card via search) | 6 languages, **no Hindi** | |
| TinyLlama 1.1B | 1.1B | about 0.7 GB | Apache 2.0 (UNVERIFIED, memory) | English-centric | 2023 model; no reason to use it |
| Sarvam-1 | 2B | n/a | **Sarvam non-commercial licence: BLOCKED** (VERIFIED) | 10 Indic languages + English; base model only, not chat-tuned | MMLU (translated) 44.4 |
| Sarvam-30B / 105B (Mar 2026) | 30B MoE (2.4B active) / 105B | 30B has a Q4_K_M GGUF | Apache 2.0 (SNIPPET) | strong Indic focus (VENDOR) | **Total 30B weights: far beyond any phone or free server.** A Nov 2026 "Sarvam-105B-1711" exists (SNIPPET, page 403) |
| Airavata, OpenHathi, Gajendra | 7B | about 4 GB | Llama 2 licence (Airavata conflicting: CC BY vs Llama 2) (SNIPPET) | Hindi-first | 7B, 2023-24 vintage; too big, superseded |
| BharatGPT 3B (CoRover), Krutrim | 3B / n/a | n/a | licence not found | n/a | No usable evidence. Do not consider |

Newer releases after August 2026: a search found only 26B+ models (Inkling 2 Mini, Qwen3.8-27B) and a 7B-total MoE (Olala mini). I did not exhaustively search; treat the table as the current small-model field, not as proof nothing newer exists.

### 1.2 Speed and RAM: what really runs where

Decode speed is limited by memory bandwidth, so model file size is the best predictor. Real numbers I could find:

| Target | Evidence | Reading |
|---|---|---|
| Flagship Android (Snapdragon 8 Elite class) | Google LiteRT-LM: Gemma 4 E2B 52 tok/s decode on GPU (OpenCL), Samsung S26 Ultra, peak memory 676 MB GPU path, 1733 MB CPU path, model file 2.58 GB (VENDOR, SNIPPET) | Fine, but not our students' phone |
| Mid-range Android, llama.cpp CPU, Q4_K_M | Ertas blog table, "measured" but no method (UNVERIFIED): 1B model SD 7 Gen 3 18 to 25 tok/s, Dimensity 8300 20 to 28, SD 6 Gen 3 12 to 18. 3B model SD 7 Gen 3 7 to 11, SD 6 Gen 3 4 to 7. RAM: 1B about 0.8 GB, 3B about 2.2 GB. Thermal loss 15 to 40% after 3 to 7 minutes | Plausible but unreviewed |
| Mid-range, independent | arXiv 2410.03613 (peer-style paper, VERIFIED): Cortex-A76/A77 CPUs reach about 2 to 4 tok/s decode on a 7B Q4 model; Kirin devices had up to 20 s cold-start from mmap; MLC GPU path crashed on two mid-tier devices | 7B is out; sub-2B plausible |
| Gemma 4 E2B on mid-range | A DEV Community post estimates 2 to 5 tok/s on CPU (individual report, UNVERIFIED) | Too slow and too big |
| Laptop CPU | Not measured by me. Bandwidth arithmetic: a 1.3 GB model on dual-channel DDR5 gives at most 40 to 60 tok/s, real 15 to 35 (ESTIMATE). One test reports Gemma 3 1B at 18.6 tok/s on an unspecified CPU (SNIPPET) | Fine for dev and CI |
| 2 shared vCPU server | llama-bench README example: 7B Q4_0, 2 threads, 7.8 tok/s decode, 12 tok/s prefill (SNIPPET, hardware unnamed). Scaling by file size: 0.5 to 1.3 GB models give about 10 to 25 tok/s decode and **30 to 100 tok/s prefill** (ESTIMATE) | A 400-token prompt costs 4 to 13 s before the first token. Prompt must be tiny or the prefix KV cache reused |
| Render free (512 MB, 0.1 CPU; Render docs SNIPPET) | Qwen3.5-0.8B Q4_K_M is 533 MB: does not fit. 0.1 CPU would be unusable anyway | **Cannot host any generative model** |

### 1.3 Can it run in the browser?

| Runtime | Status (Nov 2026) | Verdict for a mid-range Android phone |
|---|---|---|
| WebLLM (WebGPU, MLC) | Needs WebGPU. Chrome enabled it on Android 12+ with Qualcomm and ARM GPUs from Chrome 121 (SNIPPET). Mali GPUs are slow at prefill (arXiv 2410.03613). An arXiv 2605.20706 WebGPU study found the "low cluster" of phone GPUs (Adreno, Mali, PowerVR, iPhone) reaches 4 to 17 tok/s and fits only the four smallest models; iOS Safari tab memory is under 500 MB (VERIFIED) | Works for 0.5B to 0.8B on recent Chrome with 6 GB+ RAM; tab kills and driver bugs are the risk. Not for 2B+ |
| transformers.js v4 (ONNX, WebGPU) | Demos exist for Qwen3.5 0.8B/2B/4B and Gemma 4 E2B (SNIPPET); no phone speed figures published | Same limits. Easiest to ship (CDN script, ONNX files) |
| wllama (llama.cpp WASM, CPU) | No GPU needed; 2 GB per-file limit, split into 512 MB chunks; multithreading needs SharedArrayBuffer, which needs COOP/COEP headers (SNIPPET) | Works everywhere but CPU-WASM on a phone is slow (single digit tok/s ESTIMATE). Our CSP and headers would need care |
| MediaPipe LLM Inference (web) | Maintenance mode; Google points to LiteRT-LM JS. Gemma 3 1B runs there; optimised for Pixel 8 / S23 or newer (SNIPPET) | Do not start a new build on it |
| Chrome Prompt API (Gemini Nano) | Desktop only, Android not supported yet; languages en, ja, es, de, fr, Hindi not listed (SNIPPET of docs updated 2026-05-19) | **No** |
| Native (llama.cpp, LiteRT-LM in an APK) | Fastest, but we ship a Flask web app, not an APK | Out of scope unless a native app is planned |

**What works on a mid-range Android phone in 2026:** a 0.5B to 1.7B model, 4-bit, in a recent Chrome with WebGPU, after a 0.5 to 1.3 GB one-time download, at roughly 5 to 20 tok/s, with thermal slowdown and a real chance the tab is killed. **What does not:** 3B and larger, Gemma 4 E2B (3.5 GB), anything on iOS Safari beyond tiny models, anything for a student on a weak network who cannot afford a 1 GB download, anything needing a quick first reply from a cold start.

### 1.4 Hindi and Hinglish quality

- Hindi (Devanagari): the only vendor table I found with a Hindi number is Llama 3.2, 33.5 and 43.3 multilingual MMLU for 1B and 3B (VENDOR). That is barely above chance for 1B. Qwen3.5 and Gemma 4 publish language-averaged scores only; no Hindi split.
- Hinglish (romanised Hindi mixed with English): **no credible benchmark exists for models of 4B or smaller.** The one I found (kartikkparik/Hinglish-LLM-Bench on GitHub, single author, 150 items, T4 GPU, VERIFIED) gives Qwen2.5-1.5B-Instruct 22% and SmolLM2-1.7B-Instruct 9% normalised-match accuracy on reasoning and instruction tasks. Indi-RomCoM (arXiv 2606.30790, abstract VERIFIED) says all tested models do worse on romanised code-mixed text than on native-script or monolingual text, and worse again as mixing rises; no headline numbers were readable. Treat small-model Hinglish as poor until we measure it on our own test set (section 5).
- Consequence: the existing crisis floor already has Hinglish and Devanagari wordlists (`ai/severity.py`, owner flags O-20 for clinician review). A small model must never be the thing that understands a Hinglish crisis.

### 1.5 Free hosted options and data terms (verdict under the owner's rule)

Rule: personal text may go to a third party only if its terms clearly forbid training on it and the owner approves in writing.

| Provider | May it train on or review free-tier data? | Source | Verdict |
|---|---|---|---|
| Gemini API free tier | **Yes.** "Google uses the content you submit ... and any generated responses to provide, improve, and develop" products; human reviewers may read it; "Do not submit sensitive, confidential, or personal information to the Unpaid Services". EEA/UK/CH exempt, India is not. Terms effective 2026-03-23 (VERIFIED, aistudio.google.com/docs/terms) | | **Blocked** for student text. Fine for non-personal text (tip of the day) |
| Groq | Default: no retention of inference data, abuse logs up to 30 days, ZDR self-serve (VERIFIED Your Data page). The page is silent on training; community and third-party pages say no training (SNIPPET). Free tier not distinguished | console.groq.com/docs/your-data | **Not approved.** Possible only after Groq confirms in writing via its ToS/DPA; I did not read those |
| OpenRouter `:free` models | Provider-dependent. OpenRouter "works with providers to ensure prompts will not be trained on, but there are exceptions"; separate settings for paid and free (VERIFIED). A third-party review (Oct 2026) says 9 of 19 free models sit on providers that may train (UNVERIFIED snapshot) | openrouter.ai/docs/guides/privacy/logging | **No.** Cannot guarantee per request |
| Cloudflare Workers AI | **No training:** "Cloudflare does not use Customer Content processed by Workers AI to train AI models"; inputs and outputs not retained after processing unless you use storage, AI Gateway logging etc. (VERIFIED). Daily free allowance not stated on that page (I recall 10,000 neurons per day, UNVERIFIED). Model catalogue and Hindi quality not checked | developers.cloudflare.com/workers-ai/platform/data-usage/ | **Only hosted candidate that passes the terms test.** Still a third party outside India: needs owner written approval; do not use for crisis text (the floor handles that) |
| Hugging Face Inference Providers | HF "does not store request body or response", logs 30 days; but each routed provider's own policy applies (SNIPPET). Free credit about $0.10 a month | huggingface.co/docs/inference-providers | **No.** Provider-dependent and the credit is negligible |
| Hugging Face Spaces, CPU Basic, private Space | Our own container: 2 vCPU, 16 GB RAM, 50 GB ephemeral disk, sleeps after 48 h; **free availability disputed since about July 2026** (community reports of "cpu-basic quota" errors on new accounts, one staff reply says PRO needed) (SNIPPET). HF terms for private-Space data not read | huggingface.co/docs/hub/en/spaces-overview | Technically the right size for a 1 to 2B GGUF. Whether a HF-hosted container counts as "our own server" is an owner decision. Not the default |
| Together AI | Docs: data sharing for training is opt-in and off by default (SNIPPET). No verified standing free tier | docs.together.ai/docs/privacy-and-security | Not free as far as I could verify. **Out** |
| Mistral La Plateforme, Experiment (free) plan | Mistral says Experiment-plan API requests may be used to train; an opt-out toggle exists in the Admin Console (help centre, SNIPPET). Retention and review terms separate | help.mistral.ai | **No** by default. Opt-out on plus written approval is the minimum, and Mistral's open small models are not the hosted ones |

Net: the constraint is met by on-device (browser) inference or a server we operate. Everything else is an exception requiring a written owner decision.

### 1.6 Evidence on LLM chatbots for mental health

Effect sizes (pooled, mostly short follow-up; abstracts and snippets, the papers were mostly paywalled or blocked, so **SNIPPET** unless stated):

| Source | Finding |
|---|---|
| Sohn et al., npj Digital Medicine 2026, 39 studies | Depression g = 0.31 (95% CI 0.17 to 0.46), anxiety g = 0.28 (0.05 to 0.51) versus controls. **Generative-AI subgroup not significant** |
| JMIR 2026, 29 RCTs of CBT-oriented chatbots | Depression g = -0.32 (-0.55 to -0.09); anxiety smaller |
| Commercial AI chatbots as adjuncts (Karger, 2026): 18 RCTs, N = 3,170 | Depression g = -0.35 (-0.56 to -0.13); anxiety g = -0.37 (-0.87 to 0.12), uncertain. Product-market.md notes about 1.6 PHQ-9 points, below the usual 5-point clinical threshold |
| Du et al., JMIR 2025;27:e78186 | Rule-based depression g = 0.266 (p = 0.039); LLM-based g = 0.407 (CI -0.73 to 1.55, **not significant**); anxiety LLM g = 0.711 (CI -0.33 to 1.76, not significant). Separate 2025 review (Zhang et al., e78238) says GenAI beats rule-based on depression. The evidence conflicts; none of it is about models under 4B |
| Therabot RCT, Heinz et al., NEJM AI 2025;2(4) | n = 210 (press sources differ on arm sizes), 8 weeks, versus a no-access control: 51% fall in depression symptoms, 31% in anxiety (press figures; Cohen's d not confirmed). A purpose-built, studied system, not a general small model; no India or Hinglish data |

Harms and warnings:
- Stanford (FAccT 2025): five therapy bots responded appropriately under 60% of the time versus 93% for licensed therapists; several answered a "bridge" prompt after a job-loss disclosure with bridge details (SNIPPET).
- Brown (Oct 2025): 15 ethical risk types in simulated counselling chats, including poor crisis handling (SNIPPET).
- RAND (Aug 2025): large chatbots consistent at very high and very low suicide risk, inconsistent at intermediate risk (cited in product-market.md, not reopened).
- IGAP India report (May 2026, 500+ prompted interactions over a seven-day escalating-distress persona): safety got worse as distress rose; failure types were harm facilitation, ineffective crisis resources, not disclosing it is non-human, fostering dependency; cultural and language understanding did not reliably help (VERIFIED via ThePrint; chatbots not named, Hindi testing not stated).
- OpenAI (Oct 2025): about 0.15% of weekly users show explicit suicidal planning indicators; OpenAI admitted safeguards were weaker in long conversations (SNIPPET). Design consequence: cap conversation length.
- Small models: a 13-model study (Tsinghua, arXiv 2502.19883) found most SLMs "quite susceptible" to jailbreaks; GUARD-SLM (arXiv 2603.28817) says the same (SNIPPET).

Regulators and law:
- FDA Digital Health Advisory Committee met 2025-11-06 on generative-AI mental-health devices; FDA noted none is authorised yet (SNIPPET).
- APA health advisory (Nov 2025): do not rely on generative-AI chatbots for psychotherapy, evidence insufficient (cited in product-market.md; page not opened this session).
- US states: Illinois and Nevada restrict AI therapy, Utah requires disclosure, California SB 243 (effective Jan 2026) requires suicide and self-harm protocols for companion chatbots (SNIPPET, law-firm sources).
- Lawsuits: Character.AI and Google settled teen-harm suits in Jan 2026 without admission (CNN, SNIPPET); OpenAI faces suits (Raine); a Florida AG suit about June 2026 (low-quality source).
- India: I found no rule specific to mental-health chatbots; DPDP full enforcement reportedly 2027 (SNIPPET). The brief's Telemedicine Practice Guidelines 2020 clause 5.4 stays the operative limit: AI supports humans, does not counsel.
- Woebot (scripted, not generative) closed its app in June 2025, citing regulatory cost (product-market.md).

### 1.7 Judgement: would a small on-device LLM improve the product?

**No evidence says yes, and some says it adds risk.** Specifically:
- No trial of any sub-4B model for mental health exists that I could find. The best LLM trial (Therabot) used a bespoke system, not a general small model.
- LLM versus rule-based: no practically significant difference in the one head-to-head meta-analysis (Du et al.), with wide intervals.
- What the student gets today in default mode is a dead-end reply. Replacing it with the right vetted snippet gives most of the benefit a model could, with none of the open-ended-generation risk.
- Where a small model might add value (rephrasing a snippet in the student's wording, reflecting a journal entry back privately) the gain is cosmetic and unmeasured; the cost is a 0.5 to 1.3 GB download, battery and a larger attack surface.
- I would reverse this only if the section 5 experiment shows the model-as-selector beats the encoder router by a clear margin on our own Hinglish set with zero safety failures.

## 2. Architecture of a safe wellbeing companion (applies to every design)

Pipeline per message, each layer able to stop the turn:

| # | Layer | What it does | Latency budget | Exists today |
|---|---|---|---|---|
| 0 | Crisis floor | Regex on head and tail, Hinglish, Devanagari, negation, friend vs self (`ai/severity.py`). Fixed `CRISIS_REPLY`, helplines, `record_crisis`. No model waits | under 50 ms server | Yes |
| 1 | Sanitise and injection detect | `llm_guard.sanitize`, `detect` | under 10 ms | Yes |
| 2 | Intent routing | Small multilingual encoder or keyword router picks one of about 15 intents: greet, exam stress, sleep, loneliness, panic, low mood, relationship, family pressure, procrastination, breathing, safety plan, helplines, book counsellor, out of scope, unknown | 20 to 100 ms (see `encoders-nlp.md`) | No |
| 3 | Scope rules | Out-of-scope intents (diagnosis, medicines and doses, homework, legal, roleplay as a person, romance, "are you real") get a fixed refusal in en/hi/Hinglish that points to the counsellor | 0 ms | Partly (system prompt only) |
| 4 | Retrieval | Top-1 or top-3 snippet from a **curated knowledge base**, by intent tag first, embedding similarity second. Below a similarity threshold: ask one fixed clarifying question or show the menu. Never fall back to open generation | 30 to 100 ms | No (templates exist: `utils/chat_templates.py`, 6 answers) |
| 5 | Response assembly | Template with slots: `{snippet}`, `{help}` (from `utils/helplines.py`), `{next_step}`. No free text from a model in Designs A and B | 0 ms | Partly |
| 6 | Tools | A fixed set, executed by app code, no model-supplied arguments: open breathing guide, open safety plan, show helplines, suggest booking (`/api/chat/book-appointment`, idempotent, exists) | 0 ms | `recommended_action` banners exist |
| 7 | Output guard | `llm_guard.guard_output` on anything a model wrote (Design C only) | under 20 ms | Yes |

**Knowledge base rules.** 80 to 150 snippets, each 2 to 5 sentences, written or approved by a named clinician: id, intent tags, language (en, Devanagari, Hinglish), reviewer, review date, version, "do not use when" flags (for example no breathing-hold exercise for panic with asthma, none that name medicines). Stored as JSON in the repo (reviewable in a PR), never fetched from the web, no user text ever added. The 30 static tips (`utils/tip_data.py`) and the 6 starter answers are the seed.

**Constrained generation (Designs B and C only).** Use a grammar so the model can only output an enum. With llama.cpp GBNF or transformers.js constrained decoding: `{"intent": enum, "snippet_id": enum, "tool": enum[none, breathing, safety_plan, helplines, booking]}`. The model picks among ids we supply; it writes no sentence. A small model is far more reliable at choosing from 3 options than at writing safe prose. Free-text fields (Design C) get at most 25 tokens, no digits, no names, no URLs, then `guard_output`, and the fixed template wins on any failure.

**Memory: what must not be remembered.**
- Nothing about what a student wrote persists past the session in any model context. History in the prompt: last 3 turns at most, held in browser memory only.
- Never store or replay: crisis disclosures, methods, third-party names, medicines, diagnoses, assessment scores, journal text, voice transcripts.
- No "relationship" memory ("last time you told me ..."): it fosters dependency (IGAP failure type) and is a privacy liability.
- Allowed: UI language, last tool opened, whether the student dismissed a suggestion.
- The server still stores only what it stores today (crisis event without words, appointments).

**Conversation caps.** Safety degraded in long chats (OpenAI, IGAP). Soft cap at 8 turns: offer the counsellor and the breathing guide. After 3 consecutive messages classified low mood or worse: offer booking. Hard cap 20 turns, then "start a new chat" with the menu. A cap is a number the app enforces, not a prompt request.

**Escalation to humans.** Crisis: existing path unchanged. Model or router can only add a signal ("elevated concern" banner, booking suggestion), never lower the floor or silence an alert (`max(floor, model)` already in `ask_with_severity`). Counsellor alerts keep coming from the floor or an explicit student action.

**Prompt-injection posture for small models.** Do not rely on a system prompt (small models follow injected text more readily). Reduce what an obeyed injection can do: enum-only output, no tool arguments, no free text in Designs A and B, no retrieval of user-supplied or web content, short history. The existing 83-case `ATTACKS` corpus plus `CRISIS_COMBOS` in `tests/test_llm_injection.py` is the regression suite; add 40 more Hinglish and Devanagari attacks (the existing corpus is mostly English and the output guard patterns are English-only, per `docs/LLM_SECURITY.md`).

**Hallucination control.** Extractive-first: every sentence shown to the student comes from a vetted snippet or a template. If a model ever writes text, check that each sentence is in the allow-list of vetted sentences or passes the output guard and a 25-token cap; otherwise use the template. Artificial Analysis puts even Qwen3.5-4B at 80% hallucination on factual recall, so small-model "knowledge" must never be the source of a claim.

**Latency budget (student on a mid-range phone, weak network).** Floor and routing together under 300 ms. Template or snippet reply visible in under 1 s with no model. Optional on-device model: first token under 3 s warm, full reply under 8 s, then show the template instead (the existing server rule is a 10 s deadline for Gemini). Cold-load of a downloaded model (mmap, WebGPU shader compile) can take 10 to 20 s, so the model is never on the critical path.

**Hybrid pattern we already have, extended.** Deterministic floor first, saved answers, optional model. Today: floor, `off_reply`, 6 starter answers, optional Gemini behind `AI_SEND_PERSONAL_TEXT`. Extension: insert steps 2 to 6 between the floor and `off_reply`. Gemini stays for non-personal jobs only.

**Where the crisis floor runs if the model is on the device.** Keep sending the text to our own server for the floor and alerting (`POST /api/chat`, status quo), but do not send it to any model server-side. A fully on-device chat would never reach `record_crisis`, which breaks counsellor alerts; if a pure on-device mode is ever wanted, the floor must be ported to JS from the same generated data (`docs/review/generated/crisis_phrases.csv`) and tested for parity.

## 3. Fit for MindFull Horizon: three designs, ranked

All three keep the floor authoritative and ship dark behind `utils/feature_flags.py`. File-size rule: `ai/service.py` is 410 lines and `chat_inline_1.js` 287; do not grow them, put new code in new small modules and change only call sites.

### Design A: router + vetted retrieval + templates, no LLM (RECOMMENDED, build now)

| Item | Detail |
|---|---|
| What the student sees | Types a free message; gets an instant, relevant, clinician-written reply in their language, plus buttons (breathing, safety plan, helplines, book). "I don't understand" falls back to the menu, not a dead end |
| Adds over today | Replaces `off_reply()` for non-crisis text. Today default mode answers every non-crisis message identically |
| Cost | Encoder 20 to 90 MB server-side or a keyword router (0 MB); no GPU; fits Render free if the encoder is small (see `runtime-hosting.md`/`encoders-nlp.md`). KB JSON under 200 KB |
| Engineering | 3 to 4 weeks: router and retriever 1.5 weeks, KB schema and loader 0.5, route and JS 1, tests and Hinglish eval 1. Plus clinician time: 80 to 150 snippets and Hindi/Hinglish review (the real critical path, 3 to 6 weeks elapsed) |
| Files | New `ai/router.py`, `ai/kb.py`, `ai/kb_data/*.json` (split by language to stay under 300 lines), `ai/chat_reply.py` (assembles the reply; called from `ai/service.py` where `off_reply()` is today); edit `ai/replies.py`; `routes/chat.py` (return `actions` list from a fixed allow-list; it is 117 lines); new `static/js/chat-actions.js` (button rendering, no inline handlers); `utils/chat_templates.py` (read the same KB for starter questions); `tests/test_chat_router.py`, extend `tests/test_llm_injection.py` corpus |
| Risk | Low. Wrong-intent reply is the main failure: mitigated by a confidence threshold, clarifying menu, and a counsellor-reviewed 200-message set |
| Verdict | **Build now** |

### Design B: A plus an opt-in on-device model that only selects (build later, gated)

| Item | Detail |
|---|---|
| What changes | A "smarter replies" toggle downloads a 0.5 to 1.3 GB model once (Qwen3.5-0.8B 533 MB, or 2B 1.28 GB) to the browser cache. The model runs in a Web Worker with a grammar and returns `{intent, snippet_id, tool}`; it never writes text. If the model is absent, slow, crashes or disagrees with the floor, Design A answers |
| Adds over A | Better handling of messy Hinglish, multi-intent messages and paraphrase, if (and only if) it beats the encoder. Unproven; see section 5 |
| Cost | 0.5 to 1.3 GB storage, 0.8 to 2 GB RAM, 5 to 20 tok/s on mid-range Android (section 1.3); selector output is about 20 tokens, so 2 to 4 s plus prefill of a 200-token prompt. No server cost |
| Engineering | 6 to 8 weeks after A: worker and runtime wrapper 2, constrained decoding 1, download and consent UI 1, server floor endpoint 0.5, service-worker caching and COOP/COEP review 1, phone testing on 3 devices 1.5, red-team 1 |
| Files | New `static/js/chat-llm-worker.js`, `static/js/chat-llm.js`, `static/js/chat-llm-grammar.js`; `templates/chat.html` (opt-in block, size and data-stays-on-device copy, only if true); `routes/chat.py` or a new `routes/chat_screen.py` with `POST /api/chat/screen` (floor result only, no model); `utils/security_headers.py` and `static/` cache headers; `docs/PRIVACY_AND_CONSENT.md`; `tests/e2e` browser checks (CLAUDE.md requires e2e for UI) |
| Risk | Medium. Tab crashes, battery, a 1 GB download on mobile data, model licence drift. Safety risk is bounded because the model only picks among vetted ids |
| Licence | Qwen3.5 Apache 2.0, ship the licence and attribution; weights are redistributed from our static host or fetched from Hugging Face by the browser (the latter shows the student's IP to HF; say so) |
| Verdict | **Build later**, only if the section 5 pass bars are met |

### Design C: free-form generative small LLM in the browser or on a self-run server (do not build)

| Item | Detail |
|---|---|
| What it is | The model writes replies in 2 to 3 sentences from retrieved snippets (RAG), on device or in a private HF Space |
| Why not | Hallucination (80% on recall for a 4B model), Hinglish weak, injection-susceptible, long-chat drift, no evidence of benefit over A, regulators and courts focused exactly on free-form emotional chat, and under India's guideline AI must not counsel. Output guard patterns are English-only. Needs a clinician-reviewed transcript audit that the team cannot staff |
| Cost if built anyway | 8 to 12 weeks beyond B; server variant needs a host we do not have free (Render cannot; HF Space availability disputed, section 1.5) |
| Files | `ai/service.py` (already over 300 lines), `ai/gemini_impl.py` replaced by a local provider behind `AIProvider`, `utils/llm_guard.py` (391 lines, already over the limit), chat JS |
| Verdict | **Do not build.** Revisit only with evidence from a pilot of A and B and a clinical sign-off |

Variant D (not ranked): Cloudflare Workers AI for non-crisis text. It is the only hosted option whose docs say no training, but it moves student text to a US vendor and needs written owner approval. Not recommended; A and B give the benefit without it.

## 4. Per-candidate verdicts

| Candidate | Verdict | Reason |
|---|---|---|
| Qwen3.5-0.8B / 2B (Apache 2.0) | Research only, then B if passed | Best size-to-licence fit; Hindi and Hinglish unmeasured; non-thinking mode only |
| Qwen3 0.6B / 1.7B (Apache 2.0) | Research only | Older but mature in llama.cpp, wllama and transformers.js; fallback if Qwen3.5 tooling lags (Qwen3.5 in wllama UNVERIFIED) |
| Gemma 4 E2B / E4B (Apache 2.0) | Do not build | 2.6 to 3.5 GB download; mid-range speed 2 to 5 tok/s (UNVERIFIED) |
| Gemma 3 / 3n | Do not build | Restrictive terms with health-practice clauses and flow-down; superseded |
| Llama 3.2 1B / 3B | Research only | Only one with a published Hindi number (weak); AUP and naming terms; gated; 3B too big for browser |
| Phi-4-mini, SmolLM3, SmolLM2, TinyLlama, Granite nano | Do not build | No Hindi support listed or English only; Phi and SmolLM3 too big for browser |
| Sarvam-1, Airavata, OpenHathi, Gajendra, BharatGPT, Krutrim | Do not build | Non-commercial or Llama-2 licence, 7B size, base-only, or no evidence |
| Sarvam-30B/105B | Do not build | Apache but 30B+ total weights |
| Gemini free tier for student text | Blocked | Free tier trains and humans review (VERIFIED) |
| Groq, OpenRouter free, HF Inference, Together, Mistral free | Do not use for student text | Section 1.5 |
| Cloudflare Workers AI | Owner decision | Passes the terms test, still third-party |
| HF Space private CPU | Owner decision, research only | Right size, availability disputed, "own server" ambiguity |
| Router + retrieval + templates (Design A) | **Build now** | Closes the actual gap safely |

## 5. What would convince me: smallest experiments

**Experiment 1 (gates Design A, 1 week).**
- Data: 200 test messages in English, Devanagari and Hinglish written by the team and a counsellor (no real student text, no social-media scrapes: consent and re-identification problems). Cover 15 intents plus 30 out-of-scope, 20 ambiguous and 20 injection-flavoured messages.
- Compare: today (`off_reply`) versus Design A prototype, blind-rated by one or two counsellors for "helpful" and "safe".
- Pass bar: intent accuracy 85% or more on in-scope; zero replies a counsellor marks unsafe; A preferred over `off_reply` in 70% or more of pairs; floor parity 100% on the `crisis_phrases.csv` fixtures; 0 of 83 plus 40 new injection cases change the reply category.

**Experiment 2 (gates Design B, 2 weeks, needs Experiment 1 done).**
- Run Qwen3.5-0.8B and 2B, and Qwen3 1.7B, as grammar-constrained selectors in llama.cpp on a GitHub Actions runner (free for public repos), on the same 200 messages.
- Then on two real mid-range Android phones (Snapdragon 6/7 class, 6 GB RAM) in Chrome with WebGPU: p50 and p95 time to first selector output, battery per 20 messages, crash count over 20 sessions.
- Pass bar: selector accuracy at least 5 points above the Design A router on Hinglish messages; injection attack success 0 of 123; p50 under 3 s warm, p95 under 8 s; 0 tab kills in 20 sessions on both phones; download under 1.3 GB.
- Fail on any one: stop, keep Design A.

**Experiment 3 (evidence of benefit, only after a pilot).** With the college's counsellor and consent: A/B of Design A versus a static FAQ among volunteer students, outcome counsellor-booking appropriateness and a short helpfulness item; no claims about clinical outcome. No published bar exists for chatbots in Indian students; I will not invent one.

## 6. Cross-notes

Read on 2026-11-25: `evidence-safety-eval.md`, `datasets-finetuning.md`, `voice-product.md`. Not yet written when I checked: `encoders-nlp.md`, `runtime-hosting.md`, `speech.md`.

**Agreements**
- `evidence-safety-eval.md` reaches the same stance ("AI-assisted, not AI-centric", at most a few small models, each only able to raise concern, shadow mode first) and the same pooled numbers (Sohn g about 0.31 and 0.28; Therabot n=210 with humans watching). It adds a real-world Wysa RCT with a null depression result and Spittal 2025 on text risk detection (PPV 0.1 to 17 percent at realistic prevalence). That supports my rule that a model never replaces the floor and never ranks students.
- `evidence-safety-eval.md` finds no outcome evidence for "retrieval of vetted content" or AI psychoeducation, and notes static vetted text has the same plausible benefit without model risk. That is Design A; the gain there is access and relevance, and I claim no clinical effect.
- `voice-product.md` also says Anya is rule-based plus saved answers, text first (69% of surveyed Indian adolescents prefer text), no autoplay of the crisis reply, and verdict "do not build" for hands-free voice chat. Same conclusion as my Design C. If F2 ("Listen" on static text) ships, Design A's snippets should be the text it reads, so the KB is spoken text too: write snippets in short sentences.
- `datasets-finetuning.md` finds no licensed Hinglish crisis or mental-health dataset and blocks almost every social-media set on licence or ethics grounds. I agree: Design A needs hand-written data, and I recommend no fine-tuning.

**Conflicts and corrections to my own numbers**
- Commercial-chatbot review: I quoted 18 RCTs, N = 3,170, depression g = -0.35 from a PubMed snippet (PMID 42113705). `evidence-safety-eval.md` cites a Karger review with 52 studies, 22 RCTs, 13 commercial bots. They may be the same paper or two reviews; neither of us read the full text. Treat both as SNIPPET and quote only "small, low certainty".
- Cohen's d for Therabot: that report gives d 0.845 to 0.903 (depression) and 0.794 to 0.840 (anxiety), marked UNVERIFIED and computed from log-odds. I did not confirm any d, so I left it out. Use the percent reductions only.
- `evidence-safety-eval.md` asks to retire the LLM adherence score. `ai/service.py` `analyze_medication_adherence` is one of the generators I did not touch; it has no route calling it today, so retiring it costs nothing. Agree.
- `datasets-finetuning.md` row 11 (MindBridge Hindi PHQ-9/GAD-7 seeds, CC BY 4.0, 144 hand-written rows) could seed Hindi test phrases for Experiment 1. It says expansion used Gemma-family outputs, so check the Gemma 3 terms flow-down (my section 1.1) before reuse beyond evaluation.

**Questions that would still change my answer**
- `encoders-nlp.md`: if a multilingual encoder of 100 MB or less routes Hinglish intents at 85% or more, Design B's selector has no job and B can be dropped. Which encoder fits Render free under 512 MB.
- `runtime-hosting.md`: is HF Spaces CPU Basic really free today (my sources conflict), and measured llama.cpp numbers on 2 vCPU (mine are ESTIMATES).
- `speech.md`: on-device Hindi STT quality; voice input adds latency in front of layer 0 and the floor must also run on transcripts.

## 7. Questions for the owner

1. **Clinician time.** Can a named counsellor or psychologist write and approve 80 to 150 snippets and review Hindi and Hinglish, with a review date, before launch? Design A's schedule depends on this, not on code.
2. **Third-party hosting exception.** Do you accept, in writing, Cloudflare Workers AI (official no-training statement) for non-crisis chat, or is the answer strictly "device or our own server only"? My recommendation is to keep it strict.
3. **Hugging Face Space as "our own server".** If a model is ever needed server-side, is a private HF Space acceptable, given Hugging Face hosts the container?
4. **On-device download.** For Design B, is an opt-in 0.5 to 1.3 GB browser download acceptable for students on mobile data, and may the weights be fetched from Hugging Face (shows the student's IP to HF) or must we host them?
5. **Memory policy.** Confirm that no chat content is remembered across sessions (my recommendation) and that the server floor keeps seeing the text for crisis alerts even when a model runs on the device.

## 8. Sources (accessed 2026-11-25)

Models and licences: Qwen3 blog https://qwenlm.github.io/blog/qwen3/ ; Qwen3.5-2B card https://huggingface.co/Qwen/Qwen3.5-2B ; Artificial Analysis Qwen3.5 small https://artificialanalysis.ai/articles/qwen3-5-small-models ; Gemma 4 card https://huggingface.co/google/gemma-4-E4B-it ; Google open-source blog https://opensource.googleblog.com/2026/03/gemma-4-expanding-the-gemmaverse-with-apache-20.html ; Gemma terms https://ai.google.dev/gemma/terms ; Gemma prohibited use (mirror via redirect) https://gemma.ai/resources/prohibited-use/ ; Llama 3.2 model card https://github.com/meta-llama/llama-models/blob/main/models/llama3_2/MODEL_CARD.md ; Llama 3.2 use policy https://dev.meta.ai/llama/llama3_2/use-policy ; Llama licence https://developer.meta.com/ai/llama3_2/license/ ; Phi-4-mini https://huggingface.co/microsoft/Phi-4-mini-instruct ; Granite 4 nano https://huggingface.co/blog/ibm-granite/granite-4-nano ; SmolLM3 https://huggingface.co/HuggingFaceTB/SmolLM3-3B ; Sarvam-1 https://huggingface.co/sarvamai/sarvam-1 ; Sarvam-30B https://huggingface.co/sarvamai/sarvam-30b ; GGUF sizes from https://huggingface.co/bartowski and https://huggingface.co/unsloth repos named in the table.

Speed and browser: https://www.ertas.ai/blog/llm-android-benchmarks-snapdragon-tensor ; https://arxiv.org/html/2410.03613v5 ; https://arxiv.org/html/2605.20706 ; https://developers.google.com/edge/litert-lm/models/gemma-4 ; https://developers.google.com/edge/mediapipe/solutions/genai/llm_inference ; https://developer.chrome.com/docs/ai/prompt-api ; https://github.com/ngxson/wllama ; https://developer.chrome.com/blog/new-in-webgpu-146 ; https://render.com/docs/compute-plans ; https://huggingface.co/docs/hub/en/spaces-overview.

Hindi and Hinglish: https://github.com/kartikkparik/Hinglish-LLM-Bench ; https://arxiv.org/abs/2606.30790 .

Hosted terms: https://aistudio.google.com/docs/terms ; https://console.groq.com/docs/your-data ; https://openrouter.ai/docs/guides/privacy/logging ; https://developers.cloudflare.com/workers-ai/platform/data-usage/ ; https://huggingface.co/docs/inference-providers/security ; https://docs.together.ai/docs/privacy-and-security ; https://help.mistral.ai/en/articles/347614-can-i-opt-out-of-my-input-or-output-data-being-used-for-training .

Evidence: https://www.nature.com/articles/s41746-026-02566-w ; https://doi.org/10.2196/82677 ; https://www.jmir.org/2025/1/e78186 ; https://pubmed.ncbi.nlm.nih.gov/42113705/ ; https://tto.dartmouth.edu/news/2025/03/first-therapy-chatbot-trial-yields-mental-health-benefits ; https://hai.stanford.edu/news/exploring-the-dangers-of-ai-in-mental-health-care ; https://www.brown.edu/news/2025-10-21/ai-mental-health-ethics ; https://theprint.in/health/ai-chatbots-cant-handle-vulnerability-igap-report-flags-safety-gaps-amid-indias-mental-health-crisis/2934446/ ; https://techcrunch.com/2025/10/27/openai-says-over-a-million-people-talk-to-chatgpt-about-suicide-weekly ; https://www.cnn.com/2026/01/07/business/character-ai-google-settle-teen-suicide-lawsuit ; https://www.fda.gov/medical-devices/digital-health-center-excellence/fda-digital-health-advisory-committee ; https://arxiv.org/html/2502.19883v3 ; https://arxiv.org/html/2603.28817v1.
