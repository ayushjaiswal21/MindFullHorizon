# Datasets, lexicons and fine-tuning for MindFull Horizon

Agent: DATASETS. Date of all lookups: 2026-11-25. Scope: licensed, ethically sourced data and a fine-tuning plan that fits a laptop CPU or a free GPU session. Not legal advice. Items marked UNVERIFIED were seen only in a search snippet, a secondary article, a model-card tag or my own background knowledge.

Method note: dataset cards and licence tags were read through the Hugging Face (HF) web pages and the HF JSON API (`huggingface.co/api/datasets/<id>`), licence files through GitHub raw URLs. An HF licence tag is what the uploader typed, not a legal opinion; re-uploads of scraped data are often mislabelled (see rows 9, 19, 20, 21). Several sites refused automated reads (Reddit policies, MeitY and India Code PDFs, Kaggle docs, HF gated repos); those items are listed in section 7.

## 0. Bottom line (read this first)

1. Almost every dataset built from real mental-health text (Reddit, Twitter, counselling recordings) is either non-commercial, under a data use agreement (DUA), or has no licence at all, and it was collected without the authors' consent. These are blocked for the product and also conflict with the owner's ethics rule. The few permissive ones (GoEmotions Apache-2.0, Counsel Chat MIT tag, Reddit C-SSRS CC BY 4.0) still inherit Reddit or website terms, and none is Hindi or Hinglish.
2. For Hindi, Hinglish and Devanagari there is no clean, licensed mental-health or crisis dataset. The only Hinglish suicide-ideation work I found (ICON 2021) is Reddit text machine-converted to code-mixed form, and I could not confirm a release.
3. So the realistic path is: (a) write our own data (clinician seed phrases, counsellor-reviewed paraphrases, synthetic expansion with a permissively licensed generator), (b) use public licensed data only for general language competence (Indic encoders, CC BY or CC0 speech) and never for the clinical signal, and (c) spend the first effort on an evaluation set, because it measures the existing rule-based floor too.
4. A fine-tuned model is optional. Evidence that it improves safety for Hinglish students: none found in this research. Build the evaluation set first; train only if the floor measurably misses things.

## 1. Candidate table (datasets, lexicons, models)

Column key. Comm = commercial use allowed. Deriv = derivative models allowed. Redist = redistribution allowed. Y = yes, N = no, ? = not confirmed. "Seen" says what I actually opened.

### 1.1 Emotion, empathy and counselling text

| # | Name (owner) and URL | Task, language, size | Access | Licence (key text) | Comm / Deriv / Redist | Ethics and privacy | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | GoEmotions (Google Research) huggingface.co/datasets/google-research-datasets/go_emotions | 27 emotions + neutral, English, 54.3k simplified rows (211k raw) | Public | Apache-2.0 (card). Seen. | Y / Y / Y | Reddit comments; original usernames are in the data and card says identities may be discoverable; annotators were 3 raters in India per row; Reddit terms still apply (see row 18) | Usable for English emotion experiments only; low value (not Hindi, not crisis). Strip usernames |
| 2 | EmpatheticDialogues (Meta) huggingface.co/datasets/facebook/empathetic_dialogues | Empathetic chat, English, 76,673 train / 12,030 val / 10,943 test | Public | CC BY-NC 4.0 (card tag and text). Seen. | N / ? / ? | Card has "More Information Needed" for source, PII and bias | Blocked (non-commercial) |
| 3 | ESConv (Tsinghua CoAI) github.com/thu-coai/Emotional-Support-Conversation | Emotional-support dialogues, English, 1,300 convs | Public | LICENSE file: "Attribution-NonCommercial 4.0 International", grant "for NonCommercial purposes only"; README: "Data and codes are for academic research use only." Seen. | N / N / N | Crowdsourced role play; no PII statement seen | Blocked |
| 4 | Counsel Chat (N. Bertagnolli) huggingface.co/datasets/nbertagnolli/counsel-chat | Counsellor answers to public questions, English, about 2,775 rows | Public | MIT (card). Seen. Card does not say whether the counsellors' answers carry separate rights. | Y? / Y? / Y? | Scraped from counselchat.com on 2022-04-01; card: "not anonymized, so individuals' names can be found"; answers are often promotional, US-centric | Needs agreement: the MIT tag does not cure the copyright of the 3rd-party answers. Do not train on it |
| 5 | mental_health_counseling_conversations (Amod, HF) | Counselling Q and A, English | Gated, manual approval | Tag "other" (cannot read the text). Not opened. | ? | Widely re-used compilation of Counsel Chat-type sources, provenance unverified | Blocked until the licence is read |
| 6 | psychology-10k (samhog, HF) | Psychologist-style replies, English, 9,846 rows | Public | No licence, "No dataset card yet". Seen. | ? | Unknown provenance; near-duplicate rows | Blocked (no licence) |
| 7 | Psych8k (EmoCareAI, HF) | Counselling turns from about 260 real sessions, English, 1K to 10K rows | Gated, manual | CC BY-NC-SA 4.0; notice "please do not disseminate data at will". Seen. | N / N / N | Real counselling recordings; no consent or de-identification described | Blocked |
| 8 | MentalChat16K (ShenLab) huggingface.co/datasets/ShenLab/MentalChat16K | Counselling dialogues, English, 16,084 rows (9,775 synthetic via GPT-3.5 Turbo; 6,338 Q and A from 378 real clinical-trial interviews, paraphrased by Mistral-7B) | Public | MIT (card). Seen. Card text calls the set "entirely synthetic", which contradicts its own interview component. | ? / ? / ? | Interview part is from real caregivers in palliative care; consent not stated. GPT-3.5 output also falls under OpenAI terms (restriction on using output to build competing models: background knowledge, UNVERIFIED) | Blocked for training (consent unclear, mixed provenance). Usable as reading material only |
| 9 | empathetic_dialogues_llm (Estwld, HF) | Re-formatted EmpatheticDialogues | Public | Tag Apache-2.0 | N (upstream is CC BY-NC) | Licence laundering: an NC dataset relabelled Apache | Blocked |
| 10 | Hindi GoEmotions translation (utkarsharora100, HF) | Machine-translated GoEmotions, Hindi | Public | Tag "unknown". Seen via API. | ? | Derived from Reddit text; machine translation quality unknown | Research only |
| 11 | MindBridge Hindi PHQ-9/GAD-7 seeds, dialogues, evaluation (Huzayfah-Patel, HF) | Hand-written Hindi screening seeds (144 rows), about 2,883 synthetic dialogues, 224 held-out rows incl. suicidality slice | Public | CC BY 4.0 (card). Seen only the seeds card. | Y / Y / Y | Card says no real patient data, authors named, one psychiatrist; expansion used Gemma-family outputs (Gemma terms flow down) | Usable for evaluation only, after our own clinician reads it; single-author, unreviewed. Useful as a style reference for our own seeds |

### 1.2 Mental-health social-media and clinical-interview corpora

| # | Name (owner) and URL | Task, language, size | Access | Licence (key text) | Comm / Deriv / Redist | Ethics and privacy | Verdict |
|---|---|---|---|---|---|---|---|
| 12 | Dreaddit (Turcan and McKeown, Columbia) aclanthology.org/D19-6213 | Stress, English; 190K posts, 3.5K labelled segments from 3K posts | Zip on author page; HF mirrors | No licence found in any page I could read; Columbia repository page blocked me (bot wall). | ? | Reddit posts, authors never consented; usernames removed? unconfirmed | Blocked (no licence, Reddit terms) |
| 13 | SDCNL (A. Zhaque et al.) github.com/ayaanzhaque/SDCNL | Suicide vs depression, English, 1,895 posts | Public | No LICENSE file visible on repo page. Seen. | ? | Scraped from r/SuicideWatch and r/depression via Reddit API | Blocked |
| 14 | SMHD (Georgetown IR Lab) ir.cs.georgetown.edu/resources/smhd.html | Self-reported diagnoses, 9 conditions, English, large | DUA (page says details are on the resources page; not read) | Unknown DUA text | N? / ? / N | Reddit users with self-reported diagnoses; high re-identification risk | Blocked (DUA, not read) |
| 15 | CLPsych 2015 and UMD Reddit Suicidality (Univ. of Maryland, AAS) umiacs.umd.edu/~resnik/umd_reddit_suicidality_dataset.html | Suicide risk, English | IRB letter plus DUA; governance committee of 5 reviews applications; CLPsych 2015 distribution ended June 2026 (search snippet) | DUA text not read | N? / ? / N | Built on a secure-enclave model because of risk to users | Blocked |
| 16 | DAIC-WOZ / Extended DAIC (USC ICT) dcapswoz.ict.usc.edu | Interviews with audio, video, text, depression and PTSD, English | Signed EULA, academic and non-profit only | Site: "due to consent constraints we are only allowed to distribute the data to academics and other non-profit researchers" (academic email required). Seen. | N / N / N | Interviews with identifiable faces and voices | Blocked |
| 17 | Reddit C-SSRS Suicide Dataset (Gaur et al., Zenodo 2667859) | 500 users labelled by 4 psychiatrists, English, 3.7 MB | Open | CC BY 4.0 (record). Seen. | Y? / Y? / Y? | Reddit-derived posts; page has no ethics statement; Reddit terms and user deletion rights are not removed by a CC licence on a re-upload | Usable for evaluation only at most, and I recommend not using it (re-identifiable text) |
| 18 | Reddit "Data API Terms" and Pushshift | Source terms for every Reddit-derived set | n/a | Secondhand: terms bar using Reddit data "to train large language, artificial intelligence, or other algorithmic models" without approval (The Register, 2023). Reddit's page refused my fetch. UNVERIFIED wording. Pushshift API access was cut off May 2023 and returned for moderators only (search snippets). | N (needs Reddit approval) | Users cannot be assumed to consent; deletions are not propagated into static dumps | Blocks all Reddit-derived sets for commercial training |
| 19 | suicide_prediction_dataset_phr (vibhorag101, HF) | Binary suicide text, English, 232K rows | Public | Tag MIT; card says sourced from Reddit via Kaggle "suicide-watch". Seen. | N? | Re-upload of scraped r/SuicideWatch posts, lowercased and lemmatised | Blocked (licence laundering plus ethics) |
| 20 | reddit-depression-cleaned (hugginglearners, HF) | Depression text, English | Public | Tag CC0 1.0; card: "collected through web scrapping Subreddits" | N? | Same as above | Blocked |
| 21 | mental_health_chatbot_dataset (heliosbrahma, HF) | Q and A, English, 172 rows | Public | Tag MIT; card: "curated from popular healthcare blogs like WebMD, Mayo Clinic and HeatlhLine". Seen. | N? (third-party copyright) | Scraped publisher content | Blocked |
| 22 | Between Help and Harm crisis benchmark (arnaiztech, JMIR Mental Health) | LLM crisis-handling conversations, English, expert and machine labelled | Public | CC BY-NC 4.0. Seen. | N | Synthetic conversations | Blocked for product; read its labelling protocol as a design reference |
| 23 | Hindi-English suicidal-ideation corpus (Agarwal and Dhingra, ICON 2021) aclanthology.org/2021.icon-main.14 | Suicide vs not, Hinglish, size not confirmed | Release not confirmed | Not found | ? | Positives are r/SuicideWatch text converted to code-mixed form by a generator, so not real Hinglish; best model IndicBERT, 98.54% accuracy (paper claim, UNVERIFIED, and likely inflated because positives and negatives come from different subreddits) | Research only; do not use the accuracy as a target |
| 24 | MentaLLaMA / IMHI (SteveKGYang; HF Tianlin668/IMHI) github.com/SteveKGYang/MentaLLaMA | 105K instruction samples, 19K test samples, English | HF repo returned 401 (not opened) | Code: MIT. README: repository is "for non-clinical research only", and "you agree to indemnify, defend, and hold harmless the authors". Seen. No separate data licence stated. | N? / ? / ? | Raw data "from public social media platforms such as Reddit and Twitter"; also built on Dreaddit, SAD (SMS), T-SID (Twitter) | Blocked. Models sit on Llama 2 / Vicuna / BART / T5 bases (Llama licence applies) |
| 25 | MentalBERT, MentalRoBERTa (mental/, HF) | Encoders further pre-trained on Reddit mental-health posts | Gated, auto | CC BY-NC 4.0 (HF API). | N | Trained on Reddit posts | Blocked |

### 1.3 Assessment instruments

| # | Name and URL | What | Access | Licence (key text) | Comm | Notes | Verdict |
|---|---|---|---|---|---|---|---|
| 26 | PHQ-9 and GAD-7 item wording (Spitzer, Williams, Kroenke; Pfizer grant) | Item text, scoring | Public | Copyright line on public forms: "No permission required to reproduce, translate, display or distribute" (North Dakota HHS copy of the forms, a Montana DPHHS copy, and Apple Health support page, all via search snippets, not the Pfizer original; phqscreeners.com returned 403) | Y (per notice) | Apple notes the tools are clinically validated only in certain languages | Usable, with the notice kept |
| 27 | Hindi PHQ-9 and GAD-7 translations | Validated Hindi versions | Papers | Hindi PHQ-9 validated in 228 cancer patients (J Palliative Care), 125 older rural adults (PMC), and Hindi GAD-7 and PHQ-9 in 443 women in Kangra, Himachal (BMJ Open 2026, per search snippet). I did not open the papers and did not find translation usage terms. MAPI Trust involvement not confirmed. | ? | The app's own Hindi wording must match a published validated version | Needs agreement: confirm the exact Hindi text source and its permission before shipping |
| 28 | C-SSRS (Columbia Lighthouse Project) cssrs.columbia.edu | Suicide severity screener | Public | Page text: "You do not need special permission from us to take the Columbia Protocol tools and use them in your setting"; footer "© 2026 The Columbia Lighthouse Project / All Rights Reserved"; licence required for clinical trials (search snippet). Commercial software use is not addressed. Seen. | ? | Do not present as C-SSRS-validated if reworded | Needs agreement: email the project before embedding wording; do not copy item text now |

### 1.4 Indian-language text resources

| # | Name (owner) and URL | Task, language, size | Access | Licence (key text) | Comm / Deriv / Redist | Ethics and privacy | Verdict |
|---|---|---|---|---|---|---|---|
| 29 | IndicSentiment (AI4Bharat) HF ai4bharat/IndicSentiment | Product-review sentiment, 10 Indic languages incl. Hindi, 18.2 MB | Public, loading script | No licence stated on card (API licence None). Seen. | ? | Translated reviews; no personal data expected | Needs agreement (licence missing); irrelevant to crisis text |
| 30 | IndicGLUE (AI4Bharat) | NLU suite, 11 languages | Public | Tag "other"; card lists nothing more. Seen. | ? | Mixed sources | Evaluation only after reading per-task licences |
| 31 | IndicXNLI (D. Aggarwal) | Machine-translated XNLI, 11 Indic languages, 1M to 10M rows | Public | CC0 1.0 (card, mirror Divyanshu/indicxnli). Seen. | Y? | Machine translation of XNLI, whose English source licence I did not check; CC0 on a derivative may not be valid | Usable with caution for NLI evaluation; not for the product signal |
| 32 | Bhasha-Abhijnaanam (AI4Bharat) | Language ID, 22 Indic languages, native and romanised | Public | CC0 1.0 (HF API) | Y / Y / Y | Seen via API only | Usable: language ID incl. romanised Hindi. Candidate to route Hinglish vs English |
| 33 | L3Cube-HingCorpus (L3Cube Pune) github.com/l3cube-pune/code-mixed-nlp | Romanised Hindi-English corpus, 52.93M sentences, 1.04B tokens | Public | CC BY-NC-SA 4.0 per repo table. Seen. | N / ? / ? | "Scraped from Twitter": Twitter terms and user rights apply | Blocked (NC) |
| 34 | HingBERT, HingRoBERTa, HingmBERT (L3Cube) HF l3cube-pune/hing-bert | Encoders for romanised Hinglish, about 0.1B params (card) | Public | CC BY 4.0 (card). Seen. | Y? / Y? / Y? | Pre-trained on HingCorpus, which is CC BY-NC-SA and Twitter-scraped: model licence and training-data licence disagree, so risk is unresolved | Needs agreement: ask L3Cube in writing; until then use only for evaluation |
| 35 | SentiMix / SemEval-2020 Task 9 (Patwa et al., Zenodo 3974927) | Hinglish tweet sentiment, 20k instances (14k/3k/3k) | Open download | CC BY 4.0 on the Zenodo record. Seen. | Y? | Tweets: Twitter/X terms and users' rights are separate from the Zenodo licence | Usable for evaluation only (sentiment is not crisis) |
| 36 | LinCE (Aguilar et al.) ritual-ai.github.io/lince | Code-switch benchmark incl. Hindi-English | Registration (from memory) | Page returned 404. Not opened. | ? | Twitter-derived tasks | Unconfirmed |
| 37 | Hinglish community sets on HF (HinglishBench CC BY-SA 4.0; MUCS-Hinglish CC BY 4.0; hinglish-youtube-sentiments CC BY 4.0; Hinglish-Everyday-Conversations-1M MIT; hinglish-instruct-10k Apache-2.0; CMU DoG Hinglish CC BY-SA 3.0 + GFDL) | Assorted | Public | Tags from HF API, not opened | ? | YouTube comments and LLM-made sets have unknown provenance and terms | Do not use as clinical signal; treat tags as unverified |

### 1.5 Speech and TTS (see also the speech agent's report)

| # | Name (owner) | Task, language, size | Access | Licence | Comm | Ethics | Verdict |
|---|---|---|---|---|---|---|---|
| 38 | Mozilla Common Voice Hindi | ASR, Hindi | Since Oct 2025 only via Mozilla Data Collective (HF card redirect, seen) | CC0 (site, seen via fetch summary) | Y | Volunteers donate voices; no personal data expected | Usable (hours not confirmed) |
| 39 | Shrutilipi, Kathbath, IndicVoices, IndicVoices-R, Rasa (AI4Bharat) | ASR and TTS, Indic | HF gated, auto-approve | CC BY 4.0 (HF API) | Y / Y / Y with attribution | Recorded with consent per AI4Bharat (not read) | Usable after accepting gate; check consent text |
| 40 | Vistaar (AI4Bharat) | 59 ASR benchmarks, 12 languages, 10,700+ h training data | GitHub | "Vistaar is MIT-licensed. The license applies to all the fine-tuned language models." Underlying datasets keep their own licences. | Y for models | Seen | Usable for models; check each dataset |
| 41 | FLEURS (Google) | ASR, 102 languages incl. Hindi | Public | CC BY 4.0 (HF API) | Y | Read speech | Usable (evaluation) |
| 42 | Svarah (AI4Bharat) | Indian-accented English, 9.6 h, 117 speakers | Gated, accept conditions | CC BY 4.0 (card). Seen. | Y | Seen | Usable (evaluation) |
| 43 | Indic TTS database (IIT Madras) | Studio TTS, Hindi 31.87 h across voices | Email request; licence PDF | "perpetual, non-exclusive, worldwide, transferable, sub-licensable, royalty-free"; copyright notice must stay (search snippet of licence PDF, not read in full). Start-ups may need an MoU (third-party case study). | ? | Voice actors | Needs agreement |
| 44 | Facebook MMS | Multilingual ASR/TTS | Public | CC BY-NC 4.0 (HF API) | N | n/a | Blocked |

### 1.6 Lexicons

| # | Name (owner) | Content | Licence | Comm | Verdict |
|---|---|---|---|---|---|
| 45 | NRC Emotion Lexicon and VAD (Saif Mohammad, NRC Canada) | 14k English words with emotions; Hindi version machine-translated with Google Translate in Aug 2022 and "some translations may be incorrect" | Download labelled "Non-Commercial Use Only"; item 8: "If interested in commercial use of the lexicon, contact the author"; item 5: no sub-licensing; "commercially licensed to companies for a small fee". Seen. VAD page terms not read. | N without a written licence | Blocked unless the owner buys a licence |
| 46 | VADER (C. Hutto) | About 7,500 rated English tokens, emoticons, slang | MIT. Seen. | Y | Usable but English only and built for social media sentiment, not distress |
| 47 | Empath (E. Fast) | Seed-expanded English categories | MIT repository. Seen (lexicon data terms not separately read). | Y? | Usable for English cue lists, low value |
| 48 | Hindi-SentiWordNet (IIT Bombay and others) | Hindi polarity, derived from English SentiWordNet via WordNet linking | Licence not found. English SentiWordNet is CC BY-SA 4.0 (search snippet); Hindi WordNet is distributed through LDC under IIT Bombay copyright | ? | Blocked until read |
| 49 | Hinglish emotion or distress lexicon | None found with a clear licence | n/a | n/a | Build our own (section 3) |

### 1.7 Safety and refusal-behaviour sets

| # | Name | Content | Licence (HF API tags) | Comm | Verdict |
|---|---|---|---|---|---|
| 50 | Aegis 2.0 (NVIDIA) | Content-safety labels, English | CC BY 4.0, public | Y | Usable for refusal-style evaluation; English; check upstream components UNVERIFIED |
| 51 | XSTest (Walled AI mirror) | Exaggerated-refusal probes | CC BY 4.0, auto gate | Y | Usable for evaluation |
| 52 | WildGuardMix (AI2) | Safety classification and refusals | ODC-By, auto gate | Y with attribution (AI2 may add a separate impact licence: UNVERIFIED) | Needs agreement check |
| 53 | Anthropic HH-RLHF | Preference data | MIT tag | Y? | Evaluation only; contains offensive text and crowdworker chats |
| 54 | BeaverTails, PKU-SafeRLHF | Safety preference data | CC BY-NC 4.0 | N | Blocked |
| 55 | HarmBench (MIT, gated), SORRY-Bench ("other", gated) | Red-team prompts | MIT / other | ? | Evaluation only |
| 56 | Tulu 3 SFT mixture (AI2) | General instruction tuning, includes safety slices | ODC-By | Y with attribution; mixed upstream licences | General competence only |

### 1.7a Pretrained models (all re-checked via the HF API on 2026-11-25; sizes are approximate and not measured here)

| # | Model | Role | Licence | Notes |
|---|---|---|---|---|
| 57 | MuRIL base (Google) | Encoder, 17 Indian languages and transliterated text | Apache-2.0 | About 237M params (background knowledge, UNVERIFIED) |
| 58 | IndicBERT v2 (AI4Bharat) | Encoder, 23 Indian languages | MIT | About 278M (UNVERIFIED); trained on IndicCorp v2 |
| 59 | mDeBERTa-v3-base | Multilingual encoder | MIT | About 278M (UNVERIFIED) |
| 60 | XLM-RoBERTa base | Multilingual encoder | MIT (background knowledge; API call failed, UNVERIFIED) | About 278M |
| 61 | HingBERT | Hinglish encoder | CC BY 4.0, see row 34 | 0.1B (card) |
| 62 | multilingual-e5-small, paraphrase-multilingual-MiniLM-L12 | Sentence embeddings | MIT, Apache-2.0 | About 118M; for retrieval and few-shot probes |
| 63 | distilbert-base-multilingual-cased | Small encoder | Apache-2.0 | About 135M (UNVERIFIED); weak on Hinglish |
| 64 | Qwen3-0.6B, Qwen2.5-0.5B-Instruct | Small decoders | Apache-2.0 | 0.6B params (card) |
| 65 | SmolLM2-360M-Instruct | Small decoder | Apache-2.0 | English-centred |
| 66 | Gemma 3 270M and 1B | Small decoders | "Gemma" terms, manual gate | See 2.3 |
| 67 | Gemma 4 E2B and E4B | Small decoders | Apache-2.0 (HF API) | Newer; terms text not read |
| 68 | Llama 3.2 1B Instruct | Small decoder | Llama 3.2 Community Licence, manual gate | See 2.3 |
| 69 | Phi-4-mini-instruct | Small decoder | MIT | About 3.8B (UNVERIFIED), too big for the free server |
| 70 | Whisper small | ASR | Apache-2.0 | Covered by the speech agent |

## 2. What is usable under the owner's constraints

### 2.1 Licences that block commercial use (seen in this research)
CC BY-NC 4.0: EmpatheticDialogues, ESConv (also "academic research use only"), Psych8k (NC-SA), MentalBERT, MentalRoBERTa, MMS, BeaverTails, PKU-SafeRLHF, the arnaiztech crisis benchmark. CC BY-NC-SA 4.0: L3Cube HingCorpus and HingLID. NRC lexicon: "Non-Commercial Use Only" unless the author grants a licence. Academic-only agreements: DAIC-WOZ. DUAs: SMHD, CLPsych, UMD Reddit Suicidality. Research-only statement: MentaLLaMA and IMHI. Reddit and Twitter terms (rows 18, 33, 35) restrict model training on their content.

### 2.2 What is actually usable
- Permissive and relevant: Bhasha-Abhijnaanam (CC0, language ID), Common Voice Hindi (CC0), FLEURS, Svarah, Shrutilipi, Kathbath, IndicVoices (CC BY 4.0), PHQ-9 and GAD-7 wording (notice says no permission needed), MuRIL, IndicBERT v2, mDeBERTa, multilingual-e5 (Apache or MIT), VADER (MIT, English).
- Permissive but irrelevant or ethically weak for the crisis signal: GoEmotions (English Reddit), Counsel Chat (scraped, unanonymised), Reddit C-SSRS (re-identifiable Reddit text).
- There is no licensed, ethically collected Hindi, Hinglish or Devanagari mental-health or crisis text corpus that I could find. Every Hinglish candidate was Twitter or Reddit derived.
- Consequence: the clinical signal has to be trained and evaluated on our own written data (section 3).

### 2.3 Generator terms for synthetic data (checked today)
| Generator | What the terms say | Effect on a model trained on its outputs |
|---|---|---|
| Gemini API (free tier) aistudio.google.com/docs/terms (seen) | "You may not use the Services to develop models that compete with the Services." Unpaid services: Google uses submitted content and outputs to "provide, improve, and develop" products, "human reviewers may read, annotate, and process your API input and output", and "Do not submit sensitive, confidential, or personal information to the Unpaid Services." Google "won't claim ownership" of outputs. | A small crisis classifier is arguably not a competing general model, but this is a legal judgement for the owner. Prompts must contain no real data. Training data would also pass through a vendor that may read it: acceptable only for fictional text. |
| Gemma 1 to 3 terms (read at gemma.ai/resources/terms, which ai.google.dev redirects to) | "Model Derivatives" includes "methods based on the generation of synthetic data Outputs by Gemma for training that model", while "Outputs are not deemed Model Derivatives". Recipients must get the Terms and the Prohibited Use Policy flows down. Google "claims no rights in Outputs". | A classifier trained on Gemma synthetic data is a Model Derivative: it carries the Gemma terms and use policy to anyone we give it to. Manageable if the model stays private to our server; awkward if we publish it. |
| Gemma 4 E2B/E4B | HF API shows Apache-2.0; the Gemma terms page says Gemma 4 has its own licence. I did not read it. | If Apache-2.0 holds, no flow-down. Verify before use. |
| Llama 3.2 (licence read on GitHub) | "If you use the Llama Materials or any outputs or results of the Llama Materials to create, train, fine tune, or otherwise improve an AI model, which is distributed or made available, you shall also include 'Llama' at the beginning of any such AI model name"; "Built with Llama" notice; Acceptable Use Policy; 700 million MAU clause. | Usable, with naming and notice duties if the model is distributed. |
| Qwen3 and Qwen2.5-0.5B (Apache-2.0 on the cards) | Apache-2.0; cards say nothing about output use. | Least friction. Qwen larger sizes (3B, 72B) have other licences: not checked. |
| OpenAI (used for MentalChat16K) | Not read; background knowledge says output may not be used to build competing models. UNVERIFIED | Do not use. |

Recommendation: generate with Qwen3 or Gemma 4 (if Apache-2.0 is confirmed) run locally or on a Kaggle GPU; use Gemini free tier only for fictional, non-sensitive drafts, and then only after the owner accepts the clause above.

## 3. Data plan without any real student data

### 3.1 Sources, in order
1. Clinician-written seeds. A psychologist or psychiatrist writes about 40 seed utterances per risk class in English, Hindi (Devanagari) and Hinglish (Roman), covering: passive ideation, active ideation, plan or means, past attempt, self-harm, hopelessness, burnout and exam stress (not crisis), idioms that look like crisis ("mar jaunga hasi se"), third-person worry about a friend, negation, song or film quotes. The repo already has 1,243 crisis patterns (594 English, 566 Hinglish, 83 Devanagari) in `docs/review/generated/crisis_phrases.csv`, with `clinician_verdict` empty on all 1,416 rows. Reviewing that file is the cheapest first deliverable and tells us what the floor already covers.
2. Counsellor-reviewed paraphrases. A model proposes 5 to 10 paraphrases per seed (dialect, spelling noise, code-mixing, SMS style, missing vowels, mixed scripts). A counsellor accepts, edits or rejects each, and marks fluency and register. Keep rejected items as hard negatives.
3. Synthetic expansion only from the training seeds, never from the evaluation seeds, using the generators in 2.3. Tag every row with generator name, version, prompt id and date.
4. Public CC0 or CC BY material only for neutral language competence (Bhasha-Abhijnaanam for script and language ID; neutral Hinglish chat for non-crisis negatives, after checking its licence).
5. Do not paste any real post, chat, journal entry or news story into a prompt. Do not copy sentences from Reddit or Twitter sets even to "inspire" seeds: that brings back the consent and re-identification problem.

### 3.2 Evaluation set for Hinglish crisis phrases (ethical protocol)
- Size: 600 items minimum; at least 300 positive across the classes in 3.1 (at least 100 per top two risk classes) and 300 negatives of which at least 100 are hard negatives (idioms, third person, negation, exam stress, lyrics). A recall of 0.90 measured on 150 positives has a 95% interval of roughly plus or minus 5 points; on 300, plus or minus 3.4 (my calculation, normal approximation). Fewer than 100 positives per class is too noisy to judge a change.
- Authors: 2 to 3 clinicians plus 2 to 4 native Hinglish writers (not students of the deploying college, to avoid power imbalance and recognition). Writers get a brief to write fictional characters, never their own experience. Items with first names, institutions, places or phone numbers are rejected.
- Labelling: 3 independent raters per item (at least 1 clinician), labels from a short fixed scheme (none, concern, check-in needed, crisis), plus a free-text note when unsure. Agreement metric: Krippendorff's alpha (ordinal) overall and per class; target 0.67 as a floor and 0.80 as a goal (conventional thresholds, UNVERIFIED for this domain). Items where raters split are adjudicated by the senior clinician and stay in the set marked "contested"; report results with and without them.
- Evaluation items are frozen, stored encrypted outside the training repo, and never used for training, prompt examples, threshold tuning or generator few-shots. Keep a separate dev set of 200 for tuning.
- Payment: pay all raters and writers for time, in cash, at a rate the owner sets above the local minimum wage for skilled work and with clinicians at professional rates; not per item (that rewards speed); no payment contingent on labels. No academic credit as a substitute for pay. The owner must set figures (see questions).
- Safeguarding: written consent that explains the content; content warning on every batch; sessions of at most 45 to 60 minutes, at most 2 per day; mix neutral items into every batch; right to skip any item and quit without reason or loss of pay; a named counsellor available during and after sessions; helplines (Tele-MANAS 14416, KIRAN 1800-599-0019, 112) on the tool's first screen; no free-text from raters about their own lives is stored; raters are told the data is fictional and used only for testing and training this app; rotation and weekly check-in; raters can withdraw their contributions up to a stated date.
- Approval: ask the college ethics committee or an independent IRB for a short review before the first batch, even though no student data is used. Reason: raters are people reading distressing text, and the outputs will influence a safety feature.

## 4. Fine-tuning plan

### 4.1 What to fine-tune (and what not)
| Job | Model | Verdict |
|---|---|---|
| "Additional concern" signal for chat and journal text in English, Hindi, Hinglish | Encoder classifier, 100M to 280M params, int8 ONNX | Build later, only after the evaluation set shows the floor misses real phrasing |
| Language and script ID (route Hinglish, Devanagari, English) | Bhasha-Abhijnaanam-trained small model or simple rules | Research only; rules likely enough |
| Anya's replies | Small decoder (0.5B to 1B) tuned on counselling style | Do not build. No licensed Hinglish counselling data exists, the CPU cost is high, and counselling is out of scope (Telemedicine Guidelines 5.4). Keep fixed replies and templates |
| Paraphraser and data generator | Qwen3-0.6B to Gemma 4 E2B with LoRA on a free GPU | Build now as an offline tool if the seed plan needs it; never on the production server |

### 4.2 Base model candidates
MuRIL base (Apache-2.0) and IndicBERT v2 (MIT) both cover romanised Indian text and Devanagari; mDeBERTa-v3-base (MIT) is a strong generic multilingual encoder; HingBERT (CC BY 4.0, 0.1B) is the smallest Hinglish-specific one but has the licence mismatch in row 34. Plan: train two or three (MuRIL, IndicBERT v2, mDeBERTa) on the same data, compare on the dev set, ship the smallest that passes. Encoder size on disk (my estimates, not measured): about 0.95 GB fp32 and 0.25 to 0.3 GB int8 for a 278M model; about 0.45 GB fp32 and 0.12 GB int8 for a 110M model. On Render free (512 MB RAM, about 0.1 CPU) a 278M int8 model plus Flask and workers is tight; a 110M int8 model or an in-browser ONNX build (WASM) is more realistic. The runtime-hosting agent should confirm.

### 4.3 Method and cost (estimates, to be measured, UNVERIFIED)
- Full fine-tune of a 100M to 280M encoder, sequence length 64, 4 labels, 5k to 15k training rows (seeds plus counsellor-accepted paraphrases plus synthetic), 3 to 5 epochs. LoRA gives a small memory saving but little speed-up at this size and can lose accuracy on rare classes; use it only if memory is short.
- Free GPU: on a Kaggle T4 or P100 I expect 5 to 20 minutes per run; on a laptop CPU with 8 cores expect 1 to 4 hours per run for a 110M model and longer for 278M. Use mixed precision on GPU, gradient checkpointing if memory is short.
- Decoder LoRA (Qwen3-0.6B) for paraphrase generation: 1 to 2 hours on a T4 for a few thousand pairs; not needed if prompting is enough.
- Export: ONNX, then int8 dynamic quantisation, then re-run the full evaluation on the quantised file (quantisation can move recall).
- Free session facts. Colab: official FAQ says resources are "not guaranteed and not unlimited", limits are not published, free notebooks "can run for at most 12 hours", GPUs are "heavily restricted", terminations can happen "without warning", and users must avoid "sensitive (e.g., confidential) or personal information" in AI prompts (Colab FAQ, seen). Kaggle: about 30 GPU hours a week with a P100 or two T4s and 12-hour sessions (secondary articles; Kaggle's page would not load, UNVERIFIED). Neither service's terms for sensitive data were read in full; since our training data is fictional and clinician-written, no real student data ever touches them, which is the safe position. Never upload real journal or chat text to Colab, Kaggle or HF.
- HF Spaces change: current HF docs state "Static Spaces are free for everyone. Gradio and Docker Spaces run on compute and require a paid plan to create" (page seen today). Do not assume a free CPU Space for the model API. Flagged for the runtime-hosting agent.

### 4.4 Evaluation protocol
1. Freeze the 600-item set (section 3.2). Report, with Wilson 95% intervals, per class: recall, precision, false-alert rate on negatives, and results by script (English, Roman Hinglish, Devanagari).
2. Run three systems: floor alone (current `ai/severity.py` rules), model alone, and combined `max(floor, model)`. Report how many positives only the model catches, and how many extra alerts it creates.
3. Invariant test: on every item and on a large random sample of neutral text, assert final severity is at least the floor severity. Any violation fails the build.
4. Robustness: typo, vowel-dropping, mixed-script, emoji and long-text variants; adversarial paraphrases written by a second clinician group.
5. Calibration: pick the threshold on the dev set to cap the extra alert rate; never tune on the frozen set.
6. Bias checks: results by gender words, regional dialect markers, and Hindi versus Hinglish; document gaps.

### 4.5 Keeping the safety floor authoritative
- Code shape: `final = max(rule_severity, min(model_severity, MODEL_CAP))`. The model can raise a soft check-in or a counsellor-review flag; whether it may trigger the full crisis reply on its own is an owner and clinician decision (question 3). The crisis reply stays a fixed, clinician-reviewed template; the model never writes it and the crisis path never waits on the model (CLAUDE.md rule).
- If the model file is missing, slow, fails to load or times out, the floor result is used and nothing else changes. No error shown to the student.
- Run in shadow mode first for several weeks: store only the score and a hash, never the text (CLAUDE.md: never log patient text), and compare with counsellor outcomes.
- Because the app sends no personal text off the server (`AI_SEND_PERSONAL_TEXT=0`), a model on our own server or in the student's browser is consistent with the privacy rule.

### 4.6 Model card, versioning, rollback
- Model card in the repo: intended use (raise-only secondary signal), out of scope (diagnosis, severity grading for treatment, any decision about a student), data provenance table (every row source, licence, generator and version), language coverage, evaluation numbers with intervals and the contested-item rate, known failure modes, ethics review reference, retraining date, owner.
- Versioning: model file named by semantic version and SHA-256; stored in a GitHub Release or a private HF model repo; the app reads `CRISIS_MODEL_VERSION` and refuses a file whose hash differs. Training data and evaluation set are versioned separately; every evaluation report names both.
- Rollback: set `CRISIS_MODEL_VERSION=off` (floor only) or the previous version; no deploy needed. Keep the last two versions available. A failed invariant test blocks promotion.

### 4.7 Claims allowed
Allowed: "Anya looks for additional signs of distress to help counsellors notice students sooner; the safety checks do not depend on it; it is not a diagnosis and has been tested only on written examples." Not allowed: "detects depression or suicide risk", any accuracy figure presented as clinical performance, "clinically validated", "AI therapist". Reason: offline accuracy on fictional text is not clinical validity; that needs a prospective study with ethics approval and real outcomes. If the feature were framed as diagnostic, Indian medical-device rules might apply (UNVERIFIED, ask counsel).

## 5. Legal notes for India (all UNVERIFIED: primary text could not be fetched)
- Primary sources failed: MeitY and India Code returned 403. Everything below is from secondary commentary (law-school review, FPF, KPMG, India Briefing; search snippets).
- DPDP Act 2023 and Rules 2025: Rules were notified in November 2025 with phased commencement; one source says the remaining obligations, including the exemptions, apply from 13 May 2027, consent-manager rules about November 2026. Section 3(c)(ii) excludes personal data the principal made publicly available; commentators warn this does not clearly cover aggregation or profiling by AI developers and does not override other laws or contracts. Section 17(2)(b) exempts research, archiving and statistical use under conditions (no decision specific to the individual; prescribed standards). A student-wellbeing app run by a company is not "research" merely because it trains models. We avoid the question by using no real personal data in training.
- Children: the product serves adults (18+); the Act's child provisions (under 18) should not apply but age checks matter.
- Copyright and text and data mining: India has no general TDM exception that I could confirm; fair-dealing for research is narrow (background knowledge, UNVERIFIED). The DPIIT working paper (Part 1, 8 December 2025) proposes a "hybrid model" with a mandatory blanket licence for AI training and royalties on commercialisation, a majority view with a dissent from Nasscom; it is a proposal, not law (secondary sources). Contract terms (Reddit, Twitter, dataset licences) bind regardless.
- Dataset copyright: a CC or MIT tag on a re-upload cannot grant rights the uploader did not hold (rows 9, 19, 20, 21). India has no separate database right (background knowledge, UNVERIFIED).
- Practical rule: the product trains only on data we wrote or generated under a licence that permits it; keep a provenance table per row; send the table to counsel before launch.

## 6. Fit for MindFull Horizon and verdicts

| Candidate | Where it plugs in | Adds over today | Cost | Verdict |
|---|---|---|---|---|
| Clinician review of `crisis_phrases.csv` plus 600-item Hinglish evaluation set | New `tests/` fixtures and an offline script; measures `ai/severity.py` | First measured recall and false-alert numbers for the floor; today `clinician_verdict` is empty on all rows | 3 to 6 weeks, mostly clinician and rater time, small engineering | Build now |
| Encoder "additional concern" classifier | New module beside `ai/severity.py`, called from `routes/chat.py` and journal save, raise-only | Catches paraphrases and spelling variants the regexes miss; no Gemini call, no personal text off server | 1 to 2 engineering weeks after data; model 100 to 300 MB; CPU latency unmeasured (my guess: tens of ms for 64 tokens on a laptop, much slower on 0.1 vCPU) | Build later, gated by the evaluation result |
| Language and script ID | Chat input routing | Choose Hinglish vs Devanagari handling | Days | Research only; rules first |
| Decoder fine-tune for Anya | `ai/replies.py`, chat | Nothing safe: counselling out of scope, no licensed data | Heavy | Do not build |
| Synthetic generation with Qwen3 or Gemma 4 | Offline tool, Kaggle | Cheap scale of counsellor-approved seeds | 1 week | Build now (offline, if needed) |
| NRC lexicon in app | `utils/daily_tip.py` or analytics | Emotion words | Needs paid licence; Hindi version is machine translated | Do not build |
| Own clinician-curated Hinglish distress lexicon | `ai/severity.py` word lists | Transparent, auditable, owned | 1 to 2 weeks clinician time | Build now (it is the same work as seeds) |
| GoEmotions fine-tune | Mood-note tagging | English only, Reddit-derived | Small | Research only |

Does it really improve anything? Honest answer: for the free, privacy-bound deployment, the likely benefit of a fine-tuned model is small and unproven. No study I found tests Hinglish crisis detection on licensed, consented data. The only Hinglish paper (ICON 2021) reports 98.54% accuracy on Reddit text artificially made code-mixed, which is not evidence for real student writing. The solid improvement is the evaluation set and clinician review, which improve the floor regardless of any model.

### Test plan ("what would convince me")
- Smallest experiment: freeze the 600-item set, score the current floor, then add a MuRIL-base classifier trained on counsellor-approved synthetic data.
- Metrics: recall on floor-missed positives (the gain), extra alert rate on negatives, per-script recall, invariant violations.
- Pass bar (proposed, owner and clinician to confirm): the model recovers at least 30 percent of floor-missed positives in the two top risk classes with 95% interval lower bound above 15 percent; adds at most 3 percentage points of alerts on negatives; zero invariant violations; inter-rater alpha at least 0.67; p95 latency in the target environment under 300 ms. If it fails, keep floor-only and spend the effort on clinician-curated patterns.

## 7. What I could not open or confirm
- Not opened (blocked, 401, 403, 404 or bot wall): HF IMHI and Amod counselling datasets (gated); Reddit Data API and Developer Terms; phqscreeners.com; India Code and MeitY DPDP PDFs; Kaggle docs; HF Spaces free-tier details beyond the overview page; LinCE page; Columbia repository page for Dreaddit; MAPI Trust terms; Hindi-SentiWordNet licence; DAIC-WOZ EULA text; SMHD and CLPsych DUA text; NRC VAD page terms; Indic TTS full licence; Svarah, Shrutilipi, Kathbath, IndicVoices consent statements; Gemma 4 licence text; Qwen licences for larger sizes.
- Licence tags I took from the HF API without reading the card: rows 10, 22, 32, 37, 41, 44, 50 to 56, 57 to 70.
- Numbers marked "my estimate": model sizes, CPU latencies, training times, interval widths. None were measured.
- Common Voice Hindi hours: not found.

## 8. Cross-notes
No other agent reports existed in `docs/research/ai/` when I finished (directory was empty on 2026-11-25). Questions from other agents that would change my answers:
- encoders-nlp: which encoder they pick decides the licence analysis (HingBERT row 34 has the unresolved NC-corpus problem); whether they measured int8 size and latency on Render free.
- runtime-hosting: HF free Spaces now appear to require a paid plan for Gradio and Docker; static Spaces only. That affects any plan to host a model API there. Whether a 100 to 300 MB int8 encoder fits Render free at 512 MB with Flask.
- evidence-safety-eval: any published Hinglish crisis benchmark they find would replace my "none found"; their pass bars for recall should override my proposed ones.
- llm-agents: if they propose a decoder, section 2.3 applies (Gemma and Llama flow-down) and the no-personal-text rule decides where it can run.
- speech and voice-product: licences in 1.5 are only a first pass; consent statements not read.

## 9. Questions for the owner
1. Pay and ethics: who sets payment rates for clinicians and Hinglish writers, and may we ask the college ethics committee for a short review of the annotation protocol?
2. Which clinicians (names or roles) will write seeds and adjudicate? Without at least one, the evaluation set cannot be built.
3. May a model-only signal ever trigger the full crisis reply, or only a soft check-in and a counsellor flag? I recommend the latter until the shadow period ends.
4. Is the Gemini free tier acceptable for generating fictional drafts given its terms (competing-model clause, human review), or should generation be limited to local Apache-2.0 models?
5. Will you accept paying for an NRC lexicon licence later, or should we build our own lexicon only?
6. Are you willing to email L3Cube (HingBERT), the Columbia Lighthouse Project (C-SSRS wording) and the source of the Hindi PHQ-9 and GAD-7 text for written permission, and to have a lawyer check the DPDP position before launch?
