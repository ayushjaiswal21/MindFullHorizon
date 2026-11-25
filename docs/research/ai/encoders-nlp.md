# Encoders, classical NLP and lexical analysis for MindFull Horizon

Date: 2026-11-25. Agent: ENCODERS-NLP. Scope: small encoder models, classical algorithms and lexicons for Hindi, English and Hinglish, on a free CPU server or in the browser. All web sources were accessed 2026-11-25. UNVERIFIED means seen only in a search snippet, a vendor claim, or background knowledge. Four small experiments were run on this repo's own data and are marked MEASURED; scripts live in the session scratchpad (not in the repo), the method is described so they can be rerun.

## 0. Bottom line

1. **No encoder beats the current rules plus clinician review on the safety path today, and none should touch it yet.** MEASURED: a nearest-neighbour second opinion with multilingual-e5-small against the 1,243 crisis phrases (leave-pattern-out) reached AUC 0.76 on the 169 test cases. At 5 percent false alarms it recalled 6 percent of crisis cases; at 10 percent, 28 percent. It cannot read negation or third person ("mujhe marna nahi hai" scored 0.98 against "mujhe marna hai"). Verdict: research only, offline shadow mode, never paging.
2. **The cheapest real gain on the safety path is spelling-variant robustness, not a neural net.** MEASURED: when one word of a Hinglish crisis sentence is respelled in common ways (marna to mrna, chahta to chahtha), the floor still fires on only 39 percent of 326 variants. A 30-line edit-distance-1 snap onto the crisis vocabulary lifts that to 58 percent with 0 extra false positives on the 57 non-crisis cases. This is a bounded, auditable, raise-only change. It needs clinician and native-speaker review of the vocabulary, as the floor already does.
3. **Multilingual encoders are only good at Devanagari and English; romanised Hinglish is the weak spot.** MEASURED (n=16 queries, author-written, so a smoke test): cross-lingual FAQ retrieval top-1 was 0.88 to 0.94 for Devanagari queries but 0.50 to 0.62 for romanised Hinglish (0.56 to 0.62 with SMS-style spelling). Char n-gram TF-IDF over docs that carry a Hinglish alias line got 0.88 to 0.94, but the aliases and queries share an author, so treat that as an upper bound. For retrieval and search, build the lexical version first.
4. **The 512 MB Render free server cannot host a multilingual encoder comfortably.** MEASURED: multilingual-e5-small int8 (118 MB file) used 446 MB RSS in a bare Python process with the Hugging Face `tokenizers` library, about 210 MB with `sentencepiece` (31 + 41 + 136 MB, still before Flask). 81 percent of its parameters are the 250k-word embedding table. Browser inference (transformers.js, Apache-2.0) is the privacy-correct place, at a 118 MB one-time download that weak networks will feel.
5. **Where ML adds nothing:** PHQ-9 and GAD-7 trajectories, mood and sleep change detection and counsellor aggregates. Reliable-change thresholds, EWMA/CUSUM or PELT, and counts over fixed categories with K of at least 5 do the job, with no training data and a clear audit story.
6. **Licence blockers found:** MentalBERT is `cc-by-nc-4.0` and gated (blocked). NRC Emotion Lexicon and NRC VAD are free for non-commercial research only, "Do not redistribute" (blocked unless the owner obtains a licence). LIWC is proprietary with commercial licences via Receptiviti (blocked). Perspective API shuts down on 2026-12-31 (do not depend on it). Hugging Face Docker and Gradio Spaces need a paid plan; only Static Spaces are free, so HF Spaces is not a zero-rupee inference host.

## 1. How the crisis floor works today (what any proposal must plug into)

Read: `ai/severity.py`, `utils/llm_guard.py`, `docs/review/generated/crisis_phrases.csv`, `crisis_test_cases.csv`, `tests/test_safety.py` (423 lines, 40+ tests).

| Stage | What it does | File |
|---|---|---|
| Sanitise | NFKC, drop zero-width/bidi/control/tag characters, cap 20,000 chars keeping head and tail so padding cannot hide a phrase | `utils/llm_guard.py::bound, sanitize` |
| Normalise | lowercase, Cyrillic/Greek lookalike fold, leetspeak only inside letter+digit tokens, de-spacing of "k i l l", collapse 3+ repeats, spelling contractions (nahin/nhi to nahi, hoon/hun to hu, chahta variants, theek to thik) | `ai/severity.py::normalize` |
| Match | about 40 regexes (English, Hinglish, Devanagari); 1,243 phrase forms in the CSV; negation in previous 4 tokens downgrades to soft; third-person word and no first-person marker gives "friend"; idiom words skip "mar jaunga" | `ai/severity.py::classify` |
| Output | `crisis`, `friend`, `soft`, `none` and severity 0 to 10 (crisis 9); crisis never waits on the model and cannot be lowered by an injection verdict | `ai/severity.py`, `ai/service.py` |
| Review state | clinician columns in the CSV are empty (1,416 of 1,416 rows have `clinician_verdict` blank); the wordlist is a fixture needing clinician and native review (O-20) | CSV, `severity.py` header |

Test assets: 169 cases (112 must trigger crisis: 73 English, 27 Hinglish, 12 Devanagari; 57 others: 11 benign, 40 negated or soft, 6 friend). The detector matches all 169 (`detector_matches_test = yes` for every row), because the cases were written next to the regexes. This is a regression suite, not an accuracy estimate (same conclusion as `evidence-safety-eval.md` 4.1). The English cases dominate (about 70 percent of positives); Devanagari has 12.

Plug-in rule for everything below: a new signal is computed on `normalize(text)` clauses, runs after `classify()`, takes `max(floor, signal)`, writes a distinct reason code (never text) and never reduces a level.

## 2. Encoder candidates

Sizes for the first two are measured from the Hugging Face file tree (`Xenova/*` ONNX exports). Latency is MEASURED with onnxruntime 1.31.1 on an Intel Core i7-8650U (4 cores, 1.9 GHz base, 2017 laptop), Windows 11, Python 3.11, sequences up to 128 tokens.

| Model | Params | Disk fp32 / int8 | Licence | Hindi and Hinglish evidence | Browser | Verdict |
|---|---|---|---|---|---|---|
| multilingual-e5-small (intfloat) https://huggingface.co/intfloat/multilingual-e5-small | about 118M (12 layers, hidden 384, vocab 250,037; config read) | 470 MB / 118 MB (`model_int8.onnx` 118,054,593 B) | MIT (repo page) | MIRACL Hindi nDCG@10 55.1 (small) vs 58.3 (base), second-hand from the IBM Granite table, UNVERIFIED against the mE5 appendix | Yes, `Xenova/multilingual-e5-small`, q8 default on WASM | Build later (retrieval only) |
| paraphrase-multilingual-MiniLM-L12-v2 (sentence-transformers) | about 118M, dim 384, max 128 tokens | 470 MB / 118 MB (118,054,609 B) | Apache-2.0 | 50+ languages; MEASURED Devanagari FAQ 0.94, Hinglish 0.62 | Yes, `Xenova/...` | Build later (alternative to e5) |
| multilingual-e5-base, bge-m3 | bge-m3: 568M, dim 1024, 8192 tokens | bge-m3 int8 569 MB (`model_int8.onnx` 568,456,694 B) | bge-m3 MIT | strong retrieval, too big for free tiers | No (569 MB) | Do not build here |
| LaBSE (Google/sentence-transformers) | 470,927,360 | 1.88 GB / 471 MB | Apache-2.0 | made for translation-pair mining; sbert docs say weaker for non-translation similarity | No | Do not build |
| bge-small-en-v1.5 (BAAI) | about 33M (UNVERIFIED) | small | MIT | English only; no Hindi | n/a | Not applicable |
| potion-multilingual-128M (model2vec, MinishLab) | 128M, dim 256, static lookup | ONNX 512 MB fp32 | MIT | distilled from bge-m3; MTEB mean 47.31 vs LaBSE 52.07 (own card); CPU speed not found | Heavy | Research only |
| MuRIL base (Google) https://huggingface.co/google/muril-base-cased | about 237M (UNVERIFIED) | 4.4 GB repo (many formats) | Apache-2.0, not gated | 17 Indian languages and trained on transliterated segment pairs; best candidate for romanised text among BERT-class, but not a sentence encoder; needs fine-tuning | Too big | Research only |
| IndicBERT v2 MLM-only (AI4Bharat) | 278M | n/a | MIT | 23 Indic languages, IndicCorp v2; romanised text not mentioned on the card | Too big | Research only |
| XLM-R base | 278,885,778 | about 1.1 GB | MIT | GLUECoS Hinglish sentiment F1 61.57 (Roman script) | Too big | Do not build |
| distilbert-base-multilingual-cased | 135,445,755 | n/a | Apache-2.0 | weak on Hinglish; no better than MiniLM above | Large vocab | Do not build |
| HingBERT / HingMBERT / HingRoBERTa (L3Cube) | 0.1B to 0.28B | n/a | CC-BY-4.0 on the HingMBERT and HingRoBERTa cards; HingBERT card not confirmed | trained on 52.9M scraped Roman-script Hinglish tweets; GLUECoS sentiment F1 HingRoBERTa 66.43, HingBERT 63.72 vs mBERT 58.42 (paper) | Too big | Research only (tweet scraping has consent issues) |
| IndicSBERT `l3cube-pune/indic-sentence-bert-nli` | MuRIL-sized | n/a | CC-BY-4.0 | Indic sentence similarity | Too big | Research only |
| MentalBERT / MentalRoBERTa (`mental/...`) | BERT-base | 876 MB | **cc-by-nc-4.0, gated auto** | trained on Reddit mental-health posts | n/a | **BLOCKED** (non-commercial; also consent problem) |
| SamLowe/roberta-base-go_emotions-onnx | about 125M | 499 MB / 125 MB | MIT | English only; F1 0.450 (author, fixed 0.5 threshold) | Possible, 125 MB | Do not build for Hindi |

Other facts used:
- The 118 MB is vocabulary, not depth: 250,037 words x 384 dims = 96.0M of about 118M parameters. A vocabulary pruned to about 30,000 Hindi, Hinglish and English pieces would leave about 34M parameters, roughly 34 MB at int8 (my arithmetic, not an existing release; it needs a re-export with a matching tokenizer and a re-test).
- Licence note: the third-party ONNX copy `metarank/multilingual-e5-small` is tagged Apache-2.0 while the source is MIT; take weights from `intfloat` or an exporter you control and keep the original licence file. The `Xenova/*` cards did not state a licence on the page I could read.
- Romanisation hurts encoders. A 2021 paper (https://arxiv.org/abs/2108.13620) shows transliterated Hindi sits in separate clusters from Devanagari; teacher-student training recovered about 3 F1 points on average (mBERT 58.86 to 62.17, XLM-R 58.62 to 61.37; its headline "+5.6/+4.7" does not match its own table). A 2026 paper (https://arxiv.org/abs/2603.19771) reports code-mixed text is "loosely connected" to both English and Hindi in multilingual encoders. A 2026 LoResLM paper reports all tokenisers degrade under romanisation; Indic models (MuRIL, IndicBERT) hold up better than mBERT and XLM-R on clean text (UNVERIFIED snippet).
- Benchmarks: IndicXTREME (https://arxiv.org/abs/2212.05409) compares IndicBERT v2 with XLM-R and MuRIL across nine tasks; the Hindi table is in the appendix and was not read. SemEval-2020 Task 9 Hinglish: best F1 75.0 over 61 teams (https://arxiv.org/abs/2008.04277); a character n-gram SVM scored 0.678, rank 21 of 62, and mBERT was "comparable" on dev (https://aclanthology.org/2020.semeval-1.121); NB-SVM beat RoBERTa by 6.2 percent relative F1 on the same data (https://arxiv.org/abs/2008.09820). LinCE has no Hinglish sentiment task (Hinglish there is LID, POS, NER). Conclusion: for short noisy Hinglish, big transformers are not clearly better than character n-gram linear models.
- Hinglish suicide text: Agarwal and Dhingra (ICON 2021, https://aclanthology.org/2021.icon-main.14) report IndicBERT 98.54 percent accuracy on 6,533 samples; `datasets-finetuning.md` finds the data is machine-converted Reddit. A near-perfect score on a weakly labelled, machine-made set is an in-corpus figure; I discount it (also noted by `evidence-safety-eval.md`).

### 2.1 MEASURED cost on this laptop (multilingual-e5-small int8, same architecture as paraphrase-multilingual-MiniLM)

| Case | 1 thread | 4 threads |
|---|---|---|
| 1 short sentence (about 10 tokens) | 15.8 ms median, 19 ms p95 | 9.2 ms |
| 1 text of about 60 tokens | 34.6 ms median | 25.5 ms |
| batch of 16 short | 178 ms (11 ms each) | 102 ms |
| model load | 0.75 s | 0.5 s |

RAM (RSS, bare process): Python 18 MB; + numpy, onnxruntime, tokenizers 13 MB; + `tokenizers` tokenizer.json 231 MB (!); + int8 session 136 MB; total 446 MB. With `sentencepiece` (5 MB model file) the tokenizer costs 41 MB, so about 210 MB all in, before Flask, SQLAlchemy and SocketIO (not measured here).
Render free gives about 0.1 CPU. Scaling by the share of a core is only an estimate (UNVERIFIED): expect 10x or worse, so 150 ms or more for one short sentence and 20 seconds or more for a batch of 16. First-request cold start (sleep wake plus 0.75 s model load plus import) is added to Render's own wake time.

Browser: transformers.js runs ONNX Runtime Web, WASM on CPU by default with `q8`, WebGPU optional and "experimental in many browsers" (https://github.com/huggingface/transformers.js). The ORT WASM runtime is about 4.7 MB and cached separately; models go in Cache Storage. For models under 100M parameters WASM often beats WebGPU because of buffer-transfer overhead (sitepoint benchmark commentary, UNVERIFIED). I did not measure browser latency; expect 2 to 5 times native (UNVERIFIED). The real cost is the 118 MB first download on a weak phone connection; an opt-in "download once" step is needed, and a pruned 34 MB model would change the answer.

## 3. MEASURED experiments on this repo

Scripts are in the session scratchpad (`enc_scripts/`: `bench.py`, `knn2.py`, `faq.py`, `faq3.py`, `fuzzy2.py`) and use the repo's own `ai/severity.py::normalize` loaded without its package imports.

### 3.1 Second-opinion kNN against the phrase set (use case 2a)
Method: index = embeddings of the 1,243 `crisis_pattern` phrase forms; query = each test case, normalised by the floor and split at "|" into clauses, max cosine over clauses; for positives, phrases from the case's own matched pattern ids are removed (leave-pattern-out, a hard setting because the nearest paraphrase sibling is gone). Model: multilingual-e5-small int8, "query: " prefix.

| Quantity | Result |
|---|---|
| Cases | 112 must-trigger, 57 others (11 benign, 40 negated or soft, 6 friend) |
| AUC, positives vs others | 0.756 on normalised clauses (0.695 on raw text) |
| Median max-cosine by class | Hinglish positives 0.933, Devanagari 0.927, English 0.913; benign 0.869; soft 0.93; friend 0.906 |
| Threshold 0.85 | recall 112/112, 50 of 57 others flagged |
| Threshold 0.88 | recall 107/112 (0.96), 34/57 flagged |
| Threshold 0.90 | recall 90/112 (0.80), 18/57 flagged |
| Threshold 0.92 | recall 60/112 (0.54), 13/57 flagged |
| At 3 false alarms of 57 (5 percent) | threshold 0.954, recall 7/112 (6 percent) |
| At 6 false alarms of 57 (10.5 percent) | threshold 0.938, recall 31/112 (28 percent) |

Highest-scoring non-crisis items: "mujhe marna nahi hai" 0.983, "kaam khatam kar lena" (finish the work) 0.979, "marne ka man nahi hai" 0.967, "i don't want to die" 0.954, "tired of the rain" 0.936, "mera dost marna chahta hai" (my friend wants to die) 0.933. Lowest positives: "main suicide karunga" 0.862, "i'm a burden and should disappear" 0.869.

Reading: cosine values from e5 are compressed into 0.85 to 0.98 (a known property of its contrastive training, UNVERIFIED here), so any threshold needs calibration; embeddings treat negation, third person and idiom as near-identical to the crisis phrase, which is exactly what the floor's explicit rules handle. Caveats: only 57 non-crisis cases (a 5 percent false-alarm estimate has a 95 percent interval of about 1 to 15 percent); no learned classifier head was tried; the cases share authorship with the phrase list. What this does show: a raw similarity score is not a usable second opinion, and the floor's rules carry real information that embeddings lack. A supervised head on embeddings (logistic regression) might do better but needs the clinician-labelled set (section 9); it was not tried because 169 cases is too few and not independent.

### 3.2 Spelling-variant robustness of the floor and a cheap fuzzy layer (use cases 2a, 4)
Method: for each of the 27 Hinglish must-trigger cases, respell one word at a time (only words of 4+ letters that change) with six habits: drop an interior vowel, double an "a", "i" to "ee", add "h" after t/d/k/g, drop the final vowel, swap two letters. 326 variants. Fuzzy layer: after `normalize`, a token not in the known vocabulary and at least 5 letters is snapped to a crisis-vocabulary token within Levenshtein distance 1 (rapidfuzz); the result is `classify`-ed and the answer is the OR of both. Crisis vocabulary is the tokens (5+ letters) of the Hinglish phrase forms.

| Respelling | Variants | Floor fires | Floor + fuzzy ED<=1 |
|---|---|---|---|
| drop interior vowel (marna to mrna) | 89 | 0.40 | 0.62 |
| double a (marna to maarna) | 71 | 0.45 | 0.69 |
| i to ee (jina to jeena) | 27 | 0.56 | 0.56 |
| add h (chahta to chahtha) | 35 | 0.54 | 0.83 |
| drop final vowel (marna to marn) | 61 | 0.20 | 0.43 |
| swap letters (khatam to khtaam) | 43 | 0.33 | 0.33 |
| **All** | **326** | **0.39** | **0.58** |

False positives: 0 of 57 non-crisis cases flagged with or without the fuzzy layer; 5 of 342 perturbed non-crisis variants flagged by both (no increase). Caveats: my respellings are systematic, not the real distribution of student spellings; the vocabulary and the "known words" list come from the same fixtures (partly circular); 57 negatives is small. Also, changing all words at once drops the floor to 0.28 and fuzzy to 0.38, which is deliberately harsh. What it shows: the floor is brittle to romanisation variants, and a cheap bounded fix helps most for h-insertion and vowel doubling but not for dropped vowels or swaps. A phonetic key (see 6) is the next step and was not tested.

### 3.3 Retrieval of vetted answers by Hinglish query (use cases 2c, 2d)
Method: 16 invented FAQ titles (exam stress, sleep, panic, talking to a counsellor, helping a friend, breathing, homesickness, comparison, PHQ-9 and GAD-7, journal privacy, booking, loneliness, procrastination, phone use, anger, family pressure); 16 queries each in Hinglish, noisy SMS-style Hinglish and Devanagari, written by me (not native-validated, same author as the aliases).

| Method | Hinglish top-1 / top-3 | Noisy Hinglish | Devanagari |
|---|---|---|---|
| multilingual-e5-small, English docs | 0.50 / 0.69 | 0.56 / 0.69 | 0.88 / 0.94 |
| paraphrase-multilingual-MiniLM-L12, English docs | 0.62 / 0.75 | 0.62 / 0.69 | 0.94 / 0.94 |
| e5-small, docs plus a Hinglish alias line each | 0.69 / 0.81 | 0.69 / 0.75 | n/a |
| MiniLM, docs plus alias line | 0.50 / 0.62 | 0.50 / 0.75 | n/a |
| TF-IDF char_wb 2-4 grams, alias line plus English title | 0.94 / 1.00 | 0.88 / 0.94 | n/a |

Each query is 6 points, so differences under about 12 points are noise (the alias line helped e5 and hurt MiniLM). The lexical result is inflated by shared authorship (queries reuse words like "counsellor", "exam", "appointment"). The robust points: (a) embeddings are clearly worse on romanised Hinglish than on Devanagari; (b) the current substring search cannot match any of these (it needs every term as a substring of the English text); (c) a char n-gram index over curated aliases is cheap and a strong baseline. The answer to `llm-agents.md`'s question (does a 100 MB multilingual encoder route Hinglish intents at 85 percent or more?): not in this test; the encoders scored 50 to 69 percent top-1 on Hinglish and are 118 MB. Keep a selector design (or a lexical router) in play.

## 4. Use cases, algorithms, fit and verdicts

Plug-in points refer to this repo as read on 2026-11-25. "Floor" means `ai/severity.py::classify`.

| # | Use case | Algorithm | Plugs in at | Size / RAM / latency | Licence | Verdict |
|---|---|---|---|---|---|---|
| A | Second-opinion crisis signal | (1) fuzzy and phonetic extension of the floor; (2) e5 nearest neighbour; (3) supervised head on frozen embeddings or fine-tuned encoder | after `classify()` in `ai/service.py::ask_with_severity` and the journal path; queue in `routes/provider.py` | (1) 0 MB, microseconds; (2),(3) 118 MB, 15 to 35 ms native per message | rapidfuzz MIT; e5 MIT | (1) **build now**; (2) **do not build** (measured); (3) **build later**, gated on the labelled set |
| B | Emotion and sentiment tags for journals | GoEmotions-style classifier on device, or lexicon | replaces TextBlob in `routes/patient.py` (lines 26 to 45, 869) | roberta GoEmotions int8 125 MB, English only | MIT | **do not build** for Hindi/Hinglish; replace TextBlob with student-picked tags |
| C | Semantic retrieval over vetted content, search | char n-gram TF-IDF plus aliases first; embeddings later, precomputed at build time | `routes/seo.py` (`_search_pages`, `_search_posts`), saved answers in `utils/chat_templates.py` | lexical: under 1 MB, no model; embeddings: 118 MB in browser | none / MIT | lexical **build now**; embeddings **build later** |
| D | Chat intent routing | char n-gram TF-IDF over example utterances per intent; embedding as tie-break | `routes/chat.py::chat_template` and the AI-off path | lexical 0 MB; e5 118 MB | none / MIT | lexical **build now**; encoder **research only** |
| E | Near-duplicate detection | exact hash after normalisation, then shingle Jaccard | blog dedupe, repeated-message budget in `utils/llm_guard.py::UserBudget` | pure Python | stdlib | **build later** if needed |
| F | Topic modelling for counsellor aggregates | counts over fixed categories with K suppression, not free-text clusters | `utils/aggregates.py` (already K=5 via `MIN_AGGREGATE_GROUP`) | trivial | n/a | structured counts **build later**; free-text topic model **do not build** |
| G | Mood and sleep change points | CUSUM, EWMA or PELT, min segment 5 days | patient progress and provider charts (`routes/patient_progress.py`, `static/js/provider-charts.js`) | pure Python or JS, `ruptures` BSD-2 optional | BSD-2 / own code | **build later** (statistical) |
| H | PHQ-9 and GAD-7 trajectory | reliable change index, slope, item-9 rule | `ai/scoring.py`, provider dashboard | trivial | n/a | statistical **build later**; ML **do not build** |

### 4.1 A: second-opinion crisis signal (the safety-critical question)

Options and honest assessment:
1. **Fuzzy and phonetic floor extension (build now).** Snap tokens to the crisis vocabulary at edit distance 1, and add a phonetic key (collapse aa/a, ee/i/ii, oo/u, th/t, dh/d, v/w, drop h after a consonant, remove doubled letters) so "chahtha", "chahta", "chaahta" share a key. Libraries: `rapidfuzz` (already installed here, MIT), or `SymSpell` (MIT since v6.1; the author's claim of ED<=2 lookup in about 0.03 ms per word is on a 2012 laptop, https://github.com/wolfgarbe/SymSpell). Levenshtein automata (Lucene style) give the same result with more code; for a vocabulary of a few hundred tokens a plain loop is fine. Guards: only snap tokens of 5+ letters, never snap a token that is a known benign word (needs a Hinglish common-word list from the clinician review, a gap), tag hits with code `fuzzy` so counsellors can see why, and run it as `OR` with the floor. Risk: the false-positive rate on real traffic is unknown; a 57-case negative set cannot show it. Expected benefit: MEASURED +19 points on single-word respellings; unknown on real traffic. Cost: about 1 to 2 weeks including the clinician review of the vocabulary and tests; keep the module under 300 lines (project rule).
2. **Embedding nearest neighbour (do not build).** MEASURED above: AUC 0.76, 6 percent recall at 5 percent false alarms.
3. **Trained head on embeddings, or a fine-tuned encoder (build later).** Needs a clinician-labelled, independently written Hinglish set (section 9) and, for training, more than the 112-sample fixtures. No licensed Hindi or Hinglish mental-health dataset exists (`datasets-finetuning.md`), MentalBERT is non-commercial, and Reddit and Twitter corpora raise consent and re-identification problems (people in them did not agree to this use; models can memorise and leak). Calibration plan: choose the threshold on a dev split for recall at a fixed false-alert rate (for example 1 or 2 percent on the hard-negative set), freeze it, report the interval, apply Platt or isotonic scaling on dev only, re-check per script slice. Because it may only raise concern, wire it as a non-paging review-queue flag, not an automatic alert (matches `evidence-safety-eval.md` 4.4 gates). At realistic prevalence the positive predictive value will be low (the evidence report cites PPV 0.1 to 17 percent for text and risk models at real prevalence), so alert burden, not recall, is the limiting metric.
4. **Where it runs.** In the browser for chat (the text never leaves the device, the crisis card is shown locally and the existing server floor still runs on submission). Server-side only after `runtime-hosting.md` finds the RAM. The crisis path must never wait on a model download: if the model is not loaded the floor alone runs.

Does it beat rules plus clinician review? No evidence says so for Hinglish. The rule list is currently unreviewed by a clinician; the first and cheapest safety gain is that review plus the held-out set. A model can add value only for novel phrasing the regexes miss, and nobody has yet measured how often that happens.

### 4.2 B: emotion and sentiment tags for journal entries
Current: `utils/sentiment.py` wraps TextBlob (English lexicon polarity; its import "pulls in nltk, about 0.8 s and 40 MB", from the file's docstring), used in `routes/patient.py` for the journal "sentiment" fed to insights. On Hindi, Devanagari and Hinglish it returns neutral for nearly everything (it has no such lexicon; inference, not measured).
Candidates: SamLowe `roberta-base-go_emotions` int8 125 MB, F1 0.450 on GoEmotions, English only; GoEmotions is 58k English Reddit comments, 27 emotions plus neutral, Apache-2.0, but Reddit-sourced (https://research.google/blog/goemotions-a-dataset-for-fine-grained-emotion-classification/). No licensed Hinglish emotion model was found. Showing a student an inferred label on private writing at F1 near 0.45 is likely to be wrong often and can feel intrusive. Verdict: do not build. Offer student-chosen tags (a fixed list) and use those for the aggregates in F. If a lexicon is wanted for English only, VADER (MIT) is the cheapest option.

### 4.3 C and D: retrieval, search, saved answers, intent routing
- Current search (`routes/seo.py`): up to 5 terms; every term must appear as a substring in the title+description of public pages or in the title or content of published blog posts (ILIKE); shortcuts for logged-in roles. It never searches private data (good). Hinglish and typo queries return nothing.
- Build now: a char_wb 2 to 4-gram TF-IDF index over public page titles, blog titles and a curated `aliases` field (Hinglish and Devanagari alias per page, written or reviewed by a native speaker). Pure Python (hash n-grams into sparse dicts, cosine) fits in well under 300 lines and a few MB; sklearn is a heavy import for 512 MB, so avoid it in production. Add a simple synonym table (neend/nind/नींद to sleep).
- Build later: precompute document embeddings at build time in GitHub Actions (about 100 docs x 384 floats, under 200 KB as JSON) and embed only the query in the browser behind an opt-in "smarter search" download (118 MB, or about 34 MB pruned). A hybrid (lexical score plus cosine) is the usual best choice; I did not test fusion.
- Saved answers: keep exact-key caching of the allowlisted starter ids (`utils/chat_templates.py`). A semantic cache for free text is dangerous: two near neighbours in embedding space ("I don't want to die" vs "I want to die") are opposite in meaning (measured above). Never serve a cached or semantically matched answer for any message that the floor classified non-`none`.
- Intent routing (`llm-agents.md` section on intent routing): route only among fixed, reviewed intents and answers; crisis is decided by the floor before routing. Lexical router first (about 15 intents x 20 to 30 example utterances in 3 scripts, char n-gram TF-IDF), embeddings only if the evaluation shows a gain. Pass bar: Hinglish top-1 at least 85 percent on an independently authored routing set.
- Search queries are health-related text; `GET /search?q=` puts them in URLs and server access logs. If kept server-side, mask `q` in logs (project rule: never log patient text).

### 4.4 E, F: duplicates and aggregates
- Near duplicates: exact match on the floor-normalised string covers copy-paste spam; for fuzzy use 5-word shingles and Jaccard at 0.8 (stdlib). No encoder needed.
- Counsellor aggregates: `utils/aggregates.py` already suppresses cells under K (default 5). A free-text topic model (LDA or BERTopic) over journals is not safe at college scale: topic models leak membership of documents (Harvard study, https://arxiv.org/abs/2403.04451), k-anonymity does not transfer from tables to text, and anonymising changes BERTopic output (https://arxiv.org/abs/2505.08439). Alternative: count student-chosen or rule-derived categories (exam stress, sleep, family) per institution per week, with K of at least 5 per cell, no per-cluster text, and a minimum number of weeks. I did not confirm BERTopic's licence (UNVERIFIED).

### 4.5 G, H: trends and PHQ-9 and GAD-7 trajectories (ML adds nothing here)
- Data volume: a student has 14 to 60 mood or sleep points and a PHQ-9 every few weeks (3 to 6 points). Per-student ML cannot be trained on that. Population ML needs outcome labels this product does not have.
- Methods that work with no training data: Reliable Change Index. For PHQ-9 the literature gives 5 points (Lowe et al. 2004, 2 standard errors of measurement, https://pubmed.ncbi.nlm.nih.gov/15550799/), 5.72 (MDC95, individual patient meta-analysis) and 6 (used by UK NHS Talking Therapies, UNVERIFIED analysis). Use "change of 6 or more" as the label for a change worth noting and keep item 9 as a separate always-on rule (`docs/SAFETY_RESEARCH.md`). For GAD-7 I found no RCI; a population mean MCID of 3.3 (Bauer-Staeb 2021) is not an RCI, so do not show a GAD-7 "reliable change" until a source is read.
- Mood and sleep change detection: EWMA or CUSUM over the last 14 days against the student's own prior 28 days; or PELT with `ruptures` (BSD-2, numpy and scipy only, https://pypi.org/project/ruptures) with a minimum segment of 5 days. Latent class growth models of PHQ-9 trajectories exist (4 or 5 classes in cohorts of hundreds) but I found no study showing they add predictive value beyond a simple change score, and our data cannot support them.
- Rules for display: never attach points, streaks or scores to these outputs (project rule); words like "your sleep changed this week" not diagnoses; show it only to the student, and to the assigned provider on consent.

## 5. Lexical analysis

| Resource | Licence and terms (read) | Hindi/Hinglish | Verdict |
|---|---|---|---|
| LIWC-22 | proprietary; academic licence only for university research; commercial licences from Receptiviti (https://liwc.app/help/faq) | other languages on request, Hindi not confirmed | **Blocked**, no open dictionary |
| NRC Emotion Lexicon | free for non-commercial research and education; "Do not redistribute"; commercial licence for a fee from the author (https://saifmohammad.com/WebPages/NRC-Emotion-Lexicon.htm) | Hindi via Google Translate (Aug 2022), "some translations may still be incorrect" | **Blocked** until the owner gets written permission; bundling it in the repo is redistribution |
| NRC VAD v2.1 | same non-commercial terms, item 8 commercial contact (https://saifmohammad.com/WebPages/nrc-vad.html) | Hindi (machine translated) | **Blocked** likewise |
| VADER | MIT (https://github.com/cjhutto/vaderSentiment) | English only; no translation built in | Usable for English; low value here |
| Empath | MIT (https://github.com/Ejhfast/empath-client), about 194 categories counted from the README | English | Usable; low value |
| SentiWordNet 3.0 | CC BY-SA 4.0 (https://github.com/aesuli/SentiWordNet); share-alike clause | English only | Usable with attribution; ShareAlike may bind derived lexicons |
| Hindi SentiWordNet (IIT Bombay) | no licence found; Hindi WordNet is an LDC user licence | Hindi | **Blocked** until read |
| Hinglish emotion or distress lexicon | none found with a clear licence | n/a | Build our own (clinician plus native speakers), same review as the crisis list |
| Perspective API | shutting down; stays up to 2026-12-31, no new requests, no migration help (https://perspectiveapi.com/) | n/a | Do not use |

Lexicon vs transformers on mental-health text (honest summary; no study with effect sizes for Hinglish exists):
- Lexicon-only models are modest. A 2026 preprint cites a lexicon-feature classifier with a non-significant AUC of 0.63 on social media text (secondary, UNVERIFIED).
- Adding lexicons to BERT is task and data dependent. Milintsevich et al. (https://arxiv.org/abs/2404.19359) on DAIC-WOZ (189 clinical interviews, PHQ-8 MAE): BERT 4.38 baseline, +NRC 4.31 (slightly better), +AFINN 4.56 (worse); MeBERT 4.71 baseline, +all lexicons 3.59 (best). On PRIMATE (2,003 Reddit posts) gains were small and inconsistent. Conclusion of the authors: helpful only when the lexicon content matches the task.
- Hybrid lexicon plus contextual embeddings gave the best F1 in one MDPI paper (73.35 on one set, 63.81 on another), and psycholinguistic features plus transformers stayed within 3 F1 points of state of the art while staying explainable (SMM4H 2022); both secondary snippets, UNVERIFIED.
- About 75 percent of social-media depression datasets rely on weak supervision, which inflates scores (meta-analysis cited in the same results, UNVERIFIED).
Verdict: for this product the lexicon route is worth it only as explainable, clinician-owned cue lists (that is what `crisis_phrases.csv` already is), not as LIWC-style psychological scoring. No open Hinglish LIWC equivalent exists; building one is a large linguistic task with no evidence it would help.

## 6. Normalisation for Hinglish and phrase-floor extension

Already handled in `severity.py` and `llm_guard.py`: NFKC, invisible characters, Cyrillic and Greek lookalikes, leetspeak inside mixed tokens, letter spacing, repeated letters, about 12 Hinglish spelling contractions. Not handled: systematic romanisation variants (measured above), Devanagari and Roman mixed in one word, Hindi written with English keyboard shortcuts, and transcripts from speech-to-text (the `speech.md` and `voice-product.md` agents both depend on the floor catching ASR output; ASR errors resemble the dropped-vowel and swapped-letter variants, so the fuzzy layer matters there too).

| Technique | Role | Cost | Licence | Notes |
|---|---|---|---|---|
| Edit-distance-1 snap onto crisis vocabulary (rapidfuzz or SymSpell) | raise-only variant catch | microseconds | MIT | measured +19 points; keep `fuzzy` reason code |
| Phonetic key for Roman Hindi (collapse vowels, aspirates, v/w) | spelling-variant folding | microseconds | own code | untested; `dhvani` (PyPI) does IPA-bridge normalisation and claims +1.2 macro F1 on a Hindi tweet set (own figure, UNVERIFIED), and its licence was not checked |
| Character n-gram match against phrase forms | fuzzy phrase match | milliseconds | own code | catches merged or split words ("marjana", "mar jana"); more false-positive risk; run only on clauses already near a crisis word |
| Transliteration to Devanagari with IndicXlit | one canonical script | about 11M parameters, MIT code and models, word level (sentences must be split) (https://ai4bharat.iitm.ac.in/areas/xlit) | MIT | Hindi accuracy 60.56 on Dakshina vs 50.00 for the baseline (so about 40 percent of words are wrong); romanisation is inconsistent (pani, paani, paanee) so transliteration "can degrade performance" (2026 ACL Findings, UNVERIFIED); do not put it in front of the floor; maybe in front of a retrieval index |
| Aksharamukha | script conversion (ITRANS, Harvard-Kyoto, IAST) | pure Python | licence not checked | for scheme-based, lossless conversion, not for free-form chat romanisation. I found no library called "Aksharamantra" (UNVERIFIED that it exists) |
| Datasets for transliteration or normalisation | Aksharantar: 26M word pairs, Hindi 1.3M train; manual data CC-BY, mined data CC0 (https://huggingface.co/datasets/ai4bharat/Aksharantar). Dakshina: CC BY-SA 4.0, Hindi lexicon of 25,000 word types, 10,000 manually romanised sentences (https://github.com/google-research-datasets/dakshina) | | | usable for building a variant table; word level, so not conversational Hinglish |

Spelling-variant tables should be generated from these (Hindi word to attested romanisations with counts in Dakshina) for the crisis vocabulary and reviewed by a native speaker. That is the safest way to extend the floor: enumerate, review and add, rather than guess at runtime. For speech output, test the fuzzy layer on a few hundred ASR transcripts of the same phrases (needs `speech.md` output).

Rules for any normalisation change: it may only add detections; it must be a pure function with unit tests in `tests/test_safety.py` style; it must keep the 169 cases passing; it must have its own false-positive test set; and it must not log text.

## 7. Efficiency and deployment

| Topic | Finding |
|---|---|
| Quantisation | int8 ONNX is 4x smaller (470 to 118 MB) at about the same accuracy (GoEmotions F1 0.450 fp32 vs 0.447 int8, author's card). Variants available: fp16 235 MB, q4f16 205 MB, q4 399 MB (q4 is larger here because the embedding table stays high precision) |
| Biggest lever | prune the vocabulary (81 percent of weights are embeddings) to about 30k pieces |
| Tokenizer | `tokenizers` 231 MB RSS for the 250k vocab vs `sentencepiece` 41 MB (measured); use sentencepiece, or the browser tokenizer in transformers.js |
| Batching | batch 16 short texts took 178 ms vs 16 x 16 ms: batching does not help much for single messages; use it only for offline index builds |
| Caching | cache document embeddings (precompute at build time, ship as JSON); cache query embeddings by exact normalised string only for non-personal queries (search), never for chat |
| Server budget (512 MB, 0.1 CPU) | encoder 210 MB + Flask/SocketIO unmeasured (guess 120 to 180 MB) leaves under 100 MB headroom; ORT arenas grow with batch size. Not recommended as default; a paid always-on instance would change this |
| Free Hugging Face Space | Docker and Gradio Spaces "require a paid plan to create"; only Static Spaces are free, with a ZeroGPU Gradio exception for personal accounts; CPU Basic is 2 vCPU, 16 GB but not free to create (https://huggingface.co/docs/hub/spaces-overview). Also personal text on a third-party host conflicts with the owner's privacy rule unless terms forbid training and the owner approves. Static Spaces can host model files and a JS page only |
| Browser | transformers.js Apache-2.0, ORT Web WASM q8 default; first download 118 MB (or about 34 MB pruned, not built); cache in Cache Storage; works offline after load; no text leaves the device. Needs a clear opt-in and progress UI, and must degrade to the lexical path when not loaded |
| Offline CI | GitHub Actions can run encoder evaluation and index builds free; use it for shadow evaluation on the clinician set (no student data) |
| Privacy | on-device inference is the only option for student text that the owner's rule allows without a legal review; do not log embeddings (they leak content) |

## 8. Does any of this really improve anything? Honest judgement

| Question | Answer |
|---|---|
| Does an encoder beat the rules for crisis detection? | No evidence for Hinglish students. MEASURED: a similarity score is a poor classifier (AUC 0.76). A trained head might help, but it needs data we do not have and cannot ethically scrape. Published Hinglish figures (98.54 percent) are in-corpus. |
| Does anything improve the safety path now? | Yes, two non-ML things: clinician review of the 1,416-row list plus an independent held-out set; and a bounded fuzzy and phonetic layer (+19 points on respellings, 0 extra false positives on 57 negatives). |
| Where do encoders clearly help? | Semantic retrieval over vetted content for Devanagari and English (top-1 0.88 to 0.94 in a 16-query smoke test) and for cross-lingual search. For romanised Hinglish they help less than a char n-gram index with aliases. |
| Where do they not help? | Emotion tags (English only, F1 0.45, intrusive), topic models on private text, PHQ-9 and GAD-7 trajectories, change detection, near duplicates. |
| Expected user-visible benefit | Better "search and starter questions" in Hindi and Hinglish; fewer missed crisis messages from spelling variants. Both modest and unproven on real traffic. |
| Does it save Gemini calls? | Under the current policy (`AI_SEND_PERSONAL_TEXT=0`, canned answers for starters) the saving is small: lexical routing to vetted answers avoids model calls for common questions, which is where the real saving lies. |

## 9. Minimal evaluation protocol

This follows `evidence-safety-eval.md` 4.1 to 4.4 and `datasets-finetuning.md` 3.2; where they differ, notes are given.

**Step 0, baseline.** Run the floor, unchanged, on the existing 169 cases (regression only) and report per-script counts. All 169 match by construction, so these cases show no accuracy.

**Step 1, clinician-labelled Hinglish set (held out).** Size 600 minimum (matches `datasets-finetuning.md`); suggested mix for the encoder question:

| Stratum | Items | Notes |
|---|---|---|
| Must trigger crisis | 200 | English 50, Roman Hinglish 100 (30 with noisy spellings), Devanagari 50 |
| Passive ideation, negated, "soft" | 100 | includes "mujhe marna nahi hai" style negations |
| Third party (friend path) | 60 | |
| Hard negatives | 160 | idioms ("sharam se mar gaya"), exam stress, jokes, quotes, news, lyrics, academic talk about suicide |
| Obfuscated and injection-wrapped crisis | 80 | leet, spacing, Cyrillic, "ignore the rules" |

Statistics: with zero misses among n positives the 95 percent upper bound on the miss rate is about 3/n, so 200 positives bound it near 1.5 percent and 60 near 5 percent. A recall near 0.90 measured on 150 positives has an interval of roughly plus or minus 5 points (`datasets-finetuning.md`); 200 negatives bound a false-alert rate estimate of 2 percent to within about plus or minus 2 points.

**Authorship and ethics.** Items are fictional, written by 2 to 3 clinicians and 2 to 4 native Hinglish writers who have not seen the regexes (independence is the point), told to write characters, never their own experiences; no method detail, no names, places, institutions or numbers. No real student text, no scraped posts. Raters are paid, can skip any item, get content warnings and a named counsellor on call; the college ethics committee reviews before the first batch (from `datasets-finetuning.md` 3.2). Keep the held-out portion sealed from developers and from any model training or threshold tuning; a separate 200-item dev set is used for tuning.

**Labels and agreement.** 3 independent raters per item (at least one clinician): none, concern, check-in needed, crisis. Report Cohen's kappa for each pair of raters and Krippendorff's alpha overall and per script; target kappa 0.70 or more for crisis versus not (conventional "substantial" band, from memory, UNVERIFIED) and treat anything lower as a guideline problem to fix before using the labels. Annotation of suicide risk is hard: `evidence-safety-eval.md` cites kappa 0.34 in one study, so expect disagreement and keep contested items flagged. Double-label 100 percent of the crisis stratum. Adjudicate splits with the senior clinician; report results with and without contested items.

**Metrics.** Recall by script with Wilson 95 percent intervals; false-alert rate on hard negatives; recall of each candidate at a false-alert rate fixed in advance on the dev set (for example 1 percent and 2 percent); incremental recall over the floor (what the candidate catches that the floor misses) and incremental positive predictive value on those items; per-slice results; calibration curve and Brier score for any model score; latency and RSS.

**Pass bars (proposals, for clinician and owner sign-off, in line with `evidence-safety-eval.md` 4.4):**
- Floor baseline measured first.
- Fuzzy layer: no loss on any existing case; incremental recall on the noisy-spelling stratum of at least 15 points; false-alert rate on hard negatives up by at most 0.5 points; owner and clinician sign off on the vocabulary.
- Encoder head (shadow): incremental recall of at least 15 percentage points of the floor's misses with at most 1 percent of benign items flagged; no script slice worse than the floor; passes RAM and licence checks.
- Retrieval or routing: top-3 hit rate of at least 85 percent on an independently authored Hinglish set, no unreviewed content served.

## 10. What would convince me (smallest experiments)

1. **Clinician review plus held-out set (2 to 3 weeks, mostly clinician time).** Metric: floor recall and false-alert rate with intervals per script. Pass: lower recall bound at least 0.85, each script at least 0.80. Without this nothing else can be judged.
2. **Fuzzy layer in shadow on the new set (1 week engineering).** Metric: incremental recall and false alerts on the noisy-spelling and hard-negative strata. Pass: as above.
3. **Lexical search with aliases against the current search (1 week).** Metric: top-3 hit rate on 100 Hinglish and Devanagari queries from native writers. Pass: 85 percent versus the current near-zero baseline.
4. **Encoder head on frozen e5 embeddings (3 days, offline in Actions).** Train logistic regression on clinician-written dev items, evaluate once on the sealed set. Pass: the shadow bar above. If it fails, stop; the evidence then says encoders add nothing for this task at this data size.
5. **Vocabulary-pruned e5 (3 days).** Metric: size, RSS, retrieval top-1 on the same queries versus unpruned. Pass: under 40 MB, top-1 within 3 points. If it holds, browser or server hosting becomes realistic.

## 11. Fit summary

| Candidate | Where | Adds over today | Cost (size / RAM / latency / effort) | Risk | Verdict |
|---|---|---|---|---|---|
| Fuzzy and phonetic floor layer | `ai/severity.py` (new small module) | MEASURED +19 pts on respellings, 0 extra false positives on 57 | 0 MB / negligible / microseconds / 1 to 2 weeks | untested false-positive rate on real text; vocabulary needs review | Build now |
| e5 kNN second opinion | after `classify()` | AUC 0.76; no usable operating point | 118 MB / 210 to 446 MB / 15 to 35 ms native | alert noise; negation blind | Do not build |
| Trained head or fine-tuned encoder | same | unknown; needs labelled set | 118 MB, weeks | PPV low at real prevalence; data ethics | Build later |
| Lexical search with aliases | `routes/seo.py` | Hinglish and typo queries work | under 1 MB / small / ms / 1 week | none beyond alias review | Build now |
| e5 or MiniLM retrieval in browser | search, saved answers | cross-lingual, Devanagari strong | 118 MB download | weak networks; Hinglish weak | Build later |
| Vocabulary pruning of e5 | build script | 118 to about 34 MB (my arithmetic) | days | accuracy loss unknown | Research only |
| Intent router | `routes/chat.py` | picks a vetted answer without a model call | 0 MB lexical | mis-route; never for crisis | Lexical now, encoder research only |
| GoEmotions-style emotion tags | journal | English only, F1 0.45 | 125 MB | intrusive, wrong labels | Do not build |
| Topic model on journals | aggregates | none over fixed counts | n/a | membership leakage, re-identification | Do not build |
| EWMA/CUSUM/PELT, RCI | progress views | clear, auditable trends | negligible | over-interpretation by users | Build later |
| MentalBERT, NRC, LIWC | n/a | n/a | n/a | licence | Blocked |

## 12. Cross-notes (read 2026-11-25: `datasets-finetuning.md`, `evidence-safety-eval.md`, `llm-agents.md`, `speech.md`, `voice-product.md`; `runtime-hosting.md` not yet present)

Agreements:
- `evidence-safety-eval.md`: same conclusion that the 169 cases are a regression suite (169 of 169 match). Its sample-size table (lower bound 0.95 at n=59 with zero misses) agrees with my 3/n rule. Its L1 gate (at least 15 points incremental recall, at most 1 percent benign flagged) is adopted as my encoder bar.
- `datasets-finetuning.md`: the 600-item protocol, paid raters, ethics review and the finding that no clean licensed Hinglish crisis data exists. Its lexicon table (NRC non-commercial, VADER and Empath MIT, Hindi-SentiWordNet licence unknown) matches mine. Its "build later, only after the evaluation set shows the floor misses real phrasing" matches my verdict.
- `llm-agents.md` and `evidence-safety-eval.md` both put routing and retrieval below the floor and keep answers curated; consistent.

Conflicts and corrections:
- `llm-agents.md` states "Encoder 20 to 90 MB server-side". For multilingual encoders that is wrong as shipped: multilingual-e5-small and paraphrase-multilingual-MiniLM are 118 MB at int8 and 446 MB RSS with the default tokenizer (about 210 MB with sentencepiece). Only an English-only MiniLM or a vocabulary-pruned model reaches 20 to 90 MB. Its question "does a multilingual encoder of 100 MB or less route Hinglish intents at 85 percent or more?" is answered no in my smoke test (50 to 69 percent on 16 queries), so its selector design should stay alive; a char n-gram router scored 88 to 94 percent but is optimistic.
- `datasets-finetuning.md` lists the e5 and MiniLM pair at "about 118M"; confirmed (118 MB int8 files). It lists MuRIL as about 237M (UNVERIFIED); I could not confirm either. It treats XLM-R base's licence as UNVERIFIED; the HF API shows MIT and 278,885,778 parameters. MentalBERT is cc-by-nc-4.0 and gated; add it to its blocked list if absent.
- `speech.md` and `voice-product.md` ask whether a text classifier can raise signals on ASR transcripts and Devanagari: only the fuzzy layer is ready; a trained head is not. Transcripts should go through the same floor and the fuzzy layer; test on real ASR output.
- Hugging Face Spaces: `speech.md` asks whether a Space is acceptable for a heavy model. Today's docs say Docker and Gradio Spaces need a paid plan, so a free HF Space is not a zero-rupee host (Static Spaces only). `runtime-hosting.md` should confirm.
- `runtime-hosting.md` is absent: my 446 MB and 210 MB RSS figures are bare-process measurements; its Flask baseline would decide the final answer.

## 13. Questions for the owner

1. Will the owner arrange a clinician and two native Hinglish writers for the held-out set (section 9)? Without it, no model can be judged and the floor stays unmeasured. What time and payment can be budgeted?
2. Is a 118 MB one-time, opt-in, in-browser download acceptable for students on weak networks for "smarter search"? If not, approve a 3-day vocabulary-pruning experiment (target about 34 MB) or keep search lexical.
3. Should the fuzzy and phonetic floor layer be built now, with the understanding that it adds `fuzzy`-coded flags the counsellor will see, and that the vocabulary needs a native-speaker review?
4. NRC lexicons and LIWC are blocked by licence. Does the owner want to ask the NRC author for a written licence, or drop lexicon features and rely on our own reviewed cue lists?
5. Student-chosen emotion tags instead of inferred emotion labels: agreed?

## Sources (accessed 2026-11-25)

Hugging Face: https://huggingface.co/intfloat/multilingual-e5-small ; https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 ; https://huggingface.co/api/models/Xenova/multilingual-e5-small/tree/main/onnx ; https://huggingface.co/api/models/Xenova/paraphrase-multilingual-MiniLM-L12-v2/tree/main/onnx ; https://huggingface.co/api/models/Xenova/LaBSE/tree/main/onnx ; https://huggingface.co/api/models/Xenova/bge-m3/tree/main/onnx ; https://huggingface.co/BAAI/bge-m3 ; https://huggingface.co/google/muril-base-cased ; https://huggingface.co/ai4bharat/IndicBERTv2-MLM-only ; https://huggingface.co/api/models/FacebookAI/xlm-roberta-base ; https://huggingface.co/api/models/sentence-transformers/LaBSE ; https://huggingface.co/api/models/distilbert/distilbert-base-multilingual-cased ; https://huggingface.co/api/models/mental/mental-bert-base-uncased ; https://huggingface.co/api/models/l3cube-pune/indic-sentence-bert-nli ; https://huggingface.co/SamLowe/roberta-base-go_emotions-onnx ; https://huggingface.co/minishlab/potion-multilingual-128m ; https://huggingface.co/docs/hub/spaces-overview ; https://huggingface.co/datasets/ai4bharat/Aksharantar ; https://huggingface.co/l3cube-pune/hing-roberta.
Papers: https://arxiv.org/abs/2402.05672 (multilingual E5) ; https://arxiv.org/abs/2212.05409 (IndicXTREME) ; https://arxiv.org/abs/2204.08398 (HingBERT, GLUECoS numbers via the ar5iv copy) ; https://arxiv.org/abs/2108.13620 ; https://arxiv.org/abs/2603.19771 ; https://arxiv.org/abs/2008.04277 ; https://aclanthology.org/2020.semeval-1.121 ; https://arxiv.org/abs/2008.09820 ; https://aclanthology.org/2021.icon-main.14 ; https://arxiv.org/abs/2404.19359 ; https://arxiv.org/abs/2403.04451 ; https://arxiv.org/abs/2505.08439 ; https://arxiv.org/abs/2005.00547 (GoEmotions) ; https://pubmed.ncbi.nlm.nih.gov/15550799/ (PHQ-9 monitoring).
Tools and lexicons: https://github.com/huggingface/transformers.js ; https://github.com/wolfgarbe/SymSpell ; https://pypi.org/project/ruptures ; https://ai4bharat.iitm.ac.in/areas/xlit ; https://github.com/google-research-datasets/dakshina ; https://pypi.org/project/aksharamukha ; https://pypi.org/project/dhvani ; https://saifmohammad.com/WebPages/NRC-Emotion-Lexicon.htm ; https://saifmohammad.com/WebPages/nrc-vad.html ; https://github.com/cjhutto/vaderSentiment ; https://github.com/Ejhfast/empath-client ; https://github.com/aesuli/SentiWordNet ; https://liwc.app/help/faq ; https://perspectiveapi.com/.

Not verified: mE5 Hindi MIRACL row in the original appendix, IndicXTREME Hindi table, MuRIL and bge-small parameter counts, browser latency, Render CPU scaling, Flask baseline RSS, Hindi SentiWordNet licence, BERTopic licence, GAD-7 reliable change, Cohen's kappa band wording, the licence text of the `Xenova/*` ONNX exports.
