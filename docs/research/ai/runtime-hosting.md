# Runtime and hosting: how to run small AI models at zero cost, without a GPU

Author: research agent RUNTIME-HOSTING. All web pages read on 2026-11-25 (access date for every URL below). Labels: M = measured by me on 2026-11-25 on a Windows 11 developer PC (8 logical cores, CPU model not recorded, Python 3.11.9, onnxruntime 1.32.0, tokenizers 0.23.3, one thread); P = primary vendor or library page; HF-API = Hugging Face model JSON API (file sizes); EST = my estimate, not measured; UNVERIFIED = seen only in a snippet, an aggregator or a vendor claim. No phone and no Render instance was available, so every phone and Render latency is an EST until the test plan in section 11 runs.

## 0. Bottom line

1. **Run models in the student's browser, never on the Render free box.** The free box has 512 MB and 0.1 CPU (P: render.com/docs/compute-plans); docs/DEPLOY_FREE.md says the app already uses about 150 MB (not measured by me). A multilingual 118 MB int8 encoder needed 448 MB of resident memory in my test (M), of which 264 MB was the tokenizer alone. An English 23 MB encoder needed 43 MB on top of Python (M). Only the second fits, and it still needs a separate process (section 3).
2. **A free Hugging Face CPU Space is not available any more for our use.** HF docs (P, read today): "Static Spaces are free for everyone. Gradio and Docker Spaces run on compute and require a paid plan to create." Free CPU Basic (2 vCPU, 16 GB) exists only for paid accounts. A Space would also be a third party for personal text (HF terms give no no-training promise for inference inputs). Static Spaces and Hub repos can still host model files, but GitHub Pages is better for us (section 2.4).
3. **Model bytes cost more than model compute.** Render Hobby includes 5 GB of outbound bandwidth a month, then suspends services without a card (P: render.com/docs/outbound-bandwidth). Five GB is only 37 first downloads of a 135 MB model. GitHub Pages allows 100 GB a month (soft, P) from a Chennai edge (observed: `x-github-edge-region: centralindia`, `Access-Control-Allow-Origin: *` on our audio site). So models go on a GitHub Pages repo, the default tier is under 25 MB, and bigger tiers are opt-in on Wi-Fi.
4. **The default tier that is worth building is small:** all-MiniLM-L6-v2 int8, 23.0 MB (HF-API), about 38 s on a 5 Mbps link (computed), 6.7 ms per short sentence on one desktop thread (M), for matching a student's words to the exercise and tip library with embeddings that were precomputed at build time. Anything bigger waits for measured need.
5. **The rule-based floor must work with zero models loaded and zero JavaScript model files fetched.** Every layer below it is optional, time-boxed and can only raise concern.
6. **Does this really improve anything?** Hosting choice does not improve outcomes; it only decides whether a feature is affordable. No evidence in this report shows that any of these models improves student wellbeing (see `evidence-safety-eval.md`). The verdicts below are about feasibility and cost.

## 1. Placement matrix (use case by placement)

Verdict key: BUILD NOW, BUILD LATER, RESEARCH, NO. "Floor" = deterministic crisis path in `ai/severity.py`, unchanged in every row.

| Use case | A. Student browser (WASM, WebGPU) | B. Render free server | C. HF Space free | D. Other free tiers | E. Paid box later |
|---|---|---|---|---|---|
| Crisis floor (keywords, regex) | BUILD NOW as a JS mirror for offline instant fixed reply; server copy stays authoritative | Already there, no model | NO (third party) | NO | Same code |
| Match free text to exercises, tips, FAQ (embeddings, precomputed library) | BUILD NOW: 23 MB English int8 first; multilingual after Hinglish test | NO for multilingual (448 MB, M); possible for 23 MB model in a subprocess but pointless when the browser can do it | NO | Cloudflare Workers AI only for non-personal text | Fine at 2 GB |
| Raise-only concern signal on journal or chat text | BUILD LATER, shadow mode first; text never leaves the phone except by the existing POST | RESEARCH: only the 23 MB class fits; 0.1 CPU makes it a slow offline job | NO | NO (personal text) | BUILD LATER if browser tier fails the tests |
| Speech to text for voice journal | BUILD LATER: whisper-tiny int8 about 43 MB (HF-API); stock tiny is poor in Hindi (section 5.2) | NO | NO | NO | RESEARCH (audio would stay on our box, still heavy) |
| Text to speech for fixed guides | BUILD NOW with pre-rendered audio files on Pages (no model at runtime); `speechSynthesis` for the rest | NO | NO | Offline render in Colab or Kaggle, public text only | Not needed |
| Open-ended companion LLM | RESEARCH: opt-in WebGPU only; 135M to 360M models are 118 to 273 MB to download (HF-API) and WebLLM lists 360 to 376 MB GPU memory for them (P); quality and safety are the blocker, not hosting | NO: 1 to 3 tokens a second at best (EST) | NO | Cloudflare Workers AI is hosted inference: personal text needs the owner's written approval | RESEARCH at 2 GB with a 360M model (EST 3 to 8 tokens a second) |
| Counsellor-side note summary | RESEARCH: on the counsellor's laptop WebGPU, data already visible to that counsellor | NO | NO | NO | RESEARCH |
| Batch topic statistics for counsellors (no text shown) | NO | RESEARCH: job via `utils/jobs.py` writing only labels, never text | NO | GitHub Actions on synthetic data only | Fine |
| Training and fine-tuning (public licensed data only) | NO | NO | NO | Colab or Kaggle, offline, never student data | Not needed |

## 2. Placement A: the student's browser

### 2.1 Runtimes compared

| Runtime | What it is | Licence | Version seen (npm, 2026-11-25) | Fits us? |
|---|---|---|---|---|
| transformers.js | JS port of the transformers pipeline over ONNX Runtime Web; `device: 'webgpu'` opt-in, default WASM CPU, `dtype` q8 default on WASM (P: huggingface.co/docs/transformers.js) | Apache-2.0 | 4.3.2, depends on `onnxruntime-web 1.31.0-dev.20260914` (a dev build; pin the pair) | Yes: encoders, whisper, small LLMs, one API |
| ONNX Runtime Web | Engine under transformers.js: providers wasm, webgpu, webnn, webgl (P) | MIT | 1.31.1 | Yes, direct use if we want fewer dependencies |
| WebLLM (mlc-ai) | WebGPU LLM engine, Cache API, IndexedDB or OPFS cache, web worker, service worker support, an integrity-verification option (P: github.com/mlc-ai/web-llm) | Apache-2.0 | 0.2.89 | LLM only; WebGPU required (README names no fallback) |
| wllama | WASM llama.cpp, GGUF, OPFS cache, WebGPU auto-enabled in v4, multithread needs COOP and COEP, single-thread build otherwise (P: github.com/ngxson/wllama) | MIT | 4.0.0 | LLM fallback when WebGPU is missing |
| MediaPipe LLM Inference (web) | Google's web LLM task, WebGPU (P: developers.google.com/edge/mediapipe) | Apache-2.0 (code); model terms separate | 0.10.30 | Google now steers new work to LiteRT-LM; skip |
| LiteRT.js | Google's web runtime, `.tflite`, CPU (XNNPACK), WebGPU, WebNN experimental; LLMs not included, separate LiteRT-LM.js (P: developers.googleblog.com, post dated 2026-07-09) | Apache-2.0 | 2.6.0 | Research only; too new, converters are Google-centric |
| whisper-web and similar demos | Demos built on transformers.js | per demo | n/a | Use the library, not the demo |

Choice: **transformers.js with a pinned onnxruntime-web, everything self-hosted.** One dependency family covers encoders, Whisper and small LLMs. wllama is the only fallback for GGUF.

### 2.2 Real browser support in 2026

| Fact | Source |
|---|---|
| WebGPU shipped in Chrome 144, Edge 144, Firefox 141 (Windows), Safari 26 on macOS, iOS 26, iPadOS 26. Chrome for Android since 121 "for devices running at least Android 12, and with Qualcomm/ARM GPUs". | P: web.dev/blog/webgpu-supported-major-browsers (2025-11-25) |
| Global WebGPU support about 85 percent in March 2026. | P: huggingface.co/docs/transformers.js/guides/webgpu |
| India Android versions, mobile, August 2026: Android 16 24.1 percent, 15 23.3, 13 13.9, 14 12.1, 12 9.4 (sum of 12 and up is about 83 percent of Android web traffic; the rest is Android 11 and older, plus phones with no Qualcomm or ARM GPU are not counted). Traffic share over-represents newer phones. | UNVERIFIED (search snippet of gs.statcounter.com, pages need JavaScript) |
| Safari does not fail `memory.grow()`; it kills and reloads the tab. iOS has no fixed cap; a 2024 WebKit bug is titled "Only ~300 MB of RAM is reliably available to WebAssembly pages". On Chrome Android a 2021 comment estimated 500 to 700 MB in practice; a 2024 tester got 4 GB on a 5 GB phone. Low-end phones are worse than the best data point. | P (bug tracker pages): bugs.webkit.org/show_bug.cgi?id=269777 |
| Safari deletes script-written storage (Cache API, IndexedDB, service worker registrations) after seven days without a tap or click, when tracking prevention is on. Home Screen web apps are exempt. Chrome and Safari 17 or later: per-origin quota up to about 60 percent of total disk. `navigator.storage.persist()` is auto-decided without a prompt in Chrome and Safari. | P: developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria |

Consequences: (1) design for 250 MB peak per tab on the default tier; (2) a Safari student who does not open the site for a week re-downloads, so the default tier must be small; (3) call `navigator.storage.persist()` after the first successful load and show an honest "stored on this phone, remove" control.

### 2.3 Model sizes and first load (HF-API sizes, files read on 2026-11-25; download time = size x 8 / speed, computed)

| Model (file) | Licence | Download | 2 Mbps | 5 Mbps | 10 Mbps | 20 Mbps |
|---|---|---|---|---|---|---|
| onnxruntime-web CPU wasm (`ort-wasm-simd-threaded.wasm`, npm 1.31.1, uncompressed) | MIT | 14.8 MB | 59 s | 24 s | 12 s | 6 s |
| same, WebGPU build (`...jsep.wasm`) | MIT | 29.5 MB | 118 s | 47 s | 24 s | 12 s |
| all-MiniLM-L6-v2 `model_int8.onnx` + tokenizer (Xenova/all-MiniLM-L6-v2) | Apache-2.0 | 23.7 MB | 95 s | 38 s | 19 s | 9 s |
| whisper-tiny int8 encoder 10.1 + merged decoder 30.7 + tokenizer 2.5 (onnx-community/whisper-tiny) | Apache-2.0 (the card of Xenova/whisper-tiny says so; onnx-community card showed none in the API) | 43.3 MB | 173 s | 69 s | 35 s | 17 s |
| whisper-base int8 encoder 23.2 + decoder 53.7 + tokenizer | Apache-2.0 | about 79 MB | 316 s | 126 s | 63 s | 32 s |
| SmolLM2-135M-Instruct `model_q4f16.onnx` | Apache-2.0 | 117.7 MB | 8 min | 3.2 min | 97 s | 48 s |
| multilingual-e5-small / paraphrase-multilingual-MiniLM-L12 int8 + tokenizer | card tag not in API | 135 MB | 9 min | 3.6 min | 108 s | 54 s |
| SmolLM2-360M-Instruct `model_q4f16.onnx` | Apache-2.0 | 272.7 MB | 18 min | 7.3 min | 3.6 min | 109 s |
| Gemma 3 270M IT `model_q4f16` (+ data file) + tokenizer | Gemma terms (not OSI; legal review needed) | about 293 MB | 20 min | 7.8 min | 3.9 min | 117 s |
| Qwen2.5-0.5B-Instruct `model_q4f16.onnx` | tag not in API (Qwen repo says Apache-2.0, not re-checked) | 483 MB | 32 min | 13 min | 6.4 min | 193 s |

India's median mobile download speed was reported at 131.77 Mbps in August 2025 (UNVERIFIED: telecomtalk.info quoting Ookla), which is a 5G-heavy city median. Campus, hostel and low-end 4G reality is far lower, so the 2 to 10 Mbps columns are the planning range (EST). Quantisation notes from the same listings: dynamic int8 turned the 470 MB fp32 multilingual MiniLM into 118 MB; **q4 is not always smaller than int8** (the same model's q4 file is 398 MB because the 250k-word embedding table is not shrunk), while for Qwen2.5-0.5B q4f16 (483 MB) beats int8 (512 MB) and q4 (786 MB).

### 2.4 Hosting model files: GitHub Pages, Render or HF

| Host | Limits (P unless noted) | Verdict |
|---|---|---|
| Render `static/` (same origin) | Free instance counts against 5 GB a month on Hobby; at the limit services spin down without a card; no edge cache on free; `COMPRESS_TYPES` in `extensions.py` does not list `application/wasm` | Only the small JS glue and, at most, the 15 MB wasm. No models. |
| GitHub Pages (new repo `mindfull-models`, next to `mindfull-audio`) | Site at most 1 GB; 100 GB a month soft; 10 builds an hour soft (not for Actions deploys); a regular git push blocks files over 100 MiB (warns at 50 MiB); Pages is "not intended or allowed" as free hosting for a commercial SaaS or online business. Observed headers on our audio site: `Access-Control-Allow-Origin: *`, `Cache-Control: max-age=600`, `Accept-Ranges: bytes`, no COOP, COEP or CORP headers. | **Default.** Keep each file under 50 MB (shard bigger ones with fixed-size chunks and reassemble in JS, then hash the whole). Risk: a college pilot app is arguably not "commercial SaaS", but ask the owner (section 13). |
| GitHub Releases assets | No limit on total size or bandwidth per the large-files page; asset download CORS behaviour not checked | UNVERIFIED for browser fetch; test before relying on it |
| HF Hub model repo or Static Space | Static Spaces free (P). Public storage "best-effort" for free accounts. Files served through a CDN. Needs `huggingface.co` and its CDN hosts in `connect-src`; the student's IP reaches HF | Acceptable mirror for builders, not for runtime |
| Git LFS on Pages | The GitHub docs page does not say how they interact | Do not use |

### 2.5 Caching, battery, weak-device fallback

- transformers.js uses the Cache API by default (`env.useBrowserCache`, P), key `transformers-cache`, and can pre-cache the wasm and its `.mjs` factory (`env.useWasmCache`, default true). A custom cache and a custom `fetch` can be injected (`env.customCache`, `env.fetch`, P). Prefer the page-owned Cache API over a service worker: a service worker needs `/sw.js` served at the site root (the Flask static folder would limit its scope to `/static/`), and browsers may kill it at any time (WebLLM README, P).
- Integrity: the `Request.integrity` property exists, "Baseline: Widely available" since March 2017 (P: MDN). Pass `integrity: 'sha256-...'` from our manifest to every model fetch through `env.fetch`; a corrupted or swapped file then fails closed. WebLLM has its own integrity option (P).
- Battery: no measured number exists in what I found. EST: a 25 to 60 ms encoder call per message is negligible; Whisper on a 30 s clip and any LLM are visible battery draw. Run heavy work only on a tap, never in the background.
- Capability gate, in this order, all feature-detected, no user-agent sniffing: `Worker`, `WebAssembly`, `navigator.storage.estimate()` free space at least 3 times the download, `navigator.gpu` (adapter request succeeds) for the WebGPU tier, `navigator.deviceMemory` and `navigator.connection` where present (Chromium only, EST that Safari lacks them). Any failure leaves the student on the floor and the fixed replies, with no error shown beyond "this feature is not available on this phone".
- Consent and cost: never download a model without a visible tap, show the size and "uses your mobile data", offer "Wi-Fi only" as the default, and a "remove from this phone" button.

### 2.6 Content-Security-Policy and headers (our policy is in `utils/security_headers.py`)

Today: `script-src 'self' 'nonce-X'`, `connect-src 'self' wss://host`, `default-src 'self'`, COOP `same-origin`, no COEP, `Permissions-Policy` camera and microphone for self.

| Need | Directive or header | Why (source) |
|---|---|---|
| Compile and run WebAssembly | `script-src ... 'wasm-unsafe-eval'` | Without it "WebAssembly is blocked from loading and executing on the page"; narrower than `'unsafe-eval'` (P: MDN script-src). Send it only on responses of pages that host the AI worker, so the other pages keep today's policy. |
| Workers | `worker-src 'self'` (explicit) | Falls back to `child-src`, then `script-src`, so same-origin worker files already work; stating `worker-src 'self'` makes `blob:` workers fail, which is what we want. Note: ORT `env.wasm.proxy` creates its worker "from a Blob" and "does not work in CSP-restricted environments" (P: onnxruntime.ai); leave proxy off and write our own worker file in `static/js/ai/`. |
| Fetch model files and wasm from Pages | `connect-src 'self' https://ayushjaiswal21.github.io wss://host` | Model and wasm are fetched with `fetch`, so `connect-src` applies. Add only the one origin, only on AI pages. |
| ORT `.mjs` loader | Serve `ort-wasm-simd-threaded.mjs` (25 KB) from `/static/vendor/ort/` | A cross-origin `.mjs` would need that origin in `script-src`. `env.wasm.wasmPaths` accepts "an object mapping binary filenames to URLs", so the `.mjs` is same-origin and the `.wasm` comes from Pages (P). |
| **Test first** | `env.useWasmCache = false` | The docs say transformers.js pre-loads the factory `.mjs` into the Cache API; if it then imports it from a `blob:` URL, `script-src` would block it. I did not read the source. Spike item S3 in section 10. |
| `crossOriginIsolated` for threads | `Cross-Origin-Opener-Policy: same-origin` (already sent) plus `Cross-Origin-Embedder-Policy: require-corp` or `credentialless` | P: web.dev/articles/coop-coep. Under `require-corp`, cross-origin subresources without CORP or CORS headers are blocked (scripts, styles, images, iframes). Our YouTube embed (`frame-src`), `i.ytimg.com` images and the Pages audio would break; `credentialless` is "Chrome 96 and Edge" only per that article (older page, re-check). **Do not set COEP.** Run single-thread WASM and WebGPU; WebGPU needs no isolation. iOS 16.4 also threw "Out Of memory" for `shared: true` memory (P: WebKit bug 255103). |

Header summary for AI pages: add `'wasm-unsafe-eval'`, `worker-src 'self'`, one `connect-src` origin; for every other page nothing changes. Never `'unsafe-eval'` (it overrides `wasm-unsafe-eval` and permits JS `eval`, P).

## 3. Placement B: our own Render free web service

Facts: free plan = 512 MB RAM and 0.1 CPU (P: render.com/docs/compute-plans); spins down after 15 minutes without inbound traffic, spin-up "about one minute"; ephemeral filesystem; 750 instance hours; restart "at any time"; no outbound ports 25, 465, 587 (P: render.com/docs/free). The Dockerfile runs **one gunicorn eventlet worker** with `--timeout 60` and the job worker as a thread in the same process (`JOBS_INPROCESS=1`, `utils/jobs.py`).

| Candidate | On disk | Resident memory (M, one thread, Windows) | Latency p50 / p95 per short sentence (M) | Fits beside Flask (about 150 MB, docs, not measured by me)? |
|---|---|---|---|---|
| all-MiniLM-L6-v2 int8 + tokenizers | 23 + 0.7 MB | 92 MB total process, 43 MB over the Python and numpy base of 49 MB; load 0.12 s | 6.7 / 10.8 ms | Yes, in a subprocess: about 150 + 92 = 242 MB |
| multilingual-e5-small int8 + tokenizers | 118 + 17 MB | **448 MB** total, 399 MB over base; the tokenizer alone costs 264 MB (250k-word vocabulary); load 0.98 s | 13.2 / 24.4 ms | **No.** With a lean tokenizer EST about 185 MB, still tight |
| SmolLM2-135M q4 GGUF via llama.cpp | about 100 MB (EST; not measured) | EST 150 to 250 MB | EST 1 to 3 tokens a second at 0.1 CPU | No for interactive chat |
| whisper-tiny int8 | 43 MB | EST 250 MB | EST minutes per clip at 0.1 CPU | No; and audio would reach our server |

On Render the 0.1 CPU is a share; I could not measure it. EST: latencies are 5 to 10 times the desktop numbers (35 to 70 ms for MiniLM), plus a cold sleep of about 60 s (P) and a model load of 1 to 3 s. onnxruntime wheel (PyPI, P): 27.8 MB manylinux x86_64, 55 MB unpacked on Windows (M); `llama-cpp-python` has only a source tarball on PyPI (needs gcc at build; the Dockerfile already installs gcc).

**Two real engineering traps, from reading the repo:**
1. **Eventlet blocks.** `app.py` runs under the eventlet worker; a C call in onnxruntime holds the single event loop thread, so every request, the Socket.IO heartbeat and the crisis escalation timers stall for the length of the call, and gunicorn kills the worker after 60 s. Inference must run in a **separate process** (stdin and stdout JSON lines through `eventlet.green.subprocess`, not a thread, not `ProcessPoolExecutor`) with `RLIMIT_AS` of 200 MB and an idle exit after 60 s so the memory returns.
2. **Render OOM-kills the whole container.** The crisis path lives in the same container. A memory guard (psutil: refuse to load when free memory is under 150 MB) and the subprocess limit keep a model bug from taking the floor down.

Job queue design if ever used: kind `ml.embed_entry`, payload **ids only** (entry id and kind), the handler loads the text, calls the subprocess, stores a label or score, and never writes text to `jobs.payload`, `last_error` or logs (matches the module's own rule in `utils/jobs.py`). Retries are safe because handlers are idempotent. Lazy-load: the subprocess starts on first job and exits when idle. The first message after a cold start gets the floor only (as in `evidence-safety-eval.md` section 3.2).

**Verdict B: do not build as a default.** Allowed only: a 23 MB-class model in a subprocess for an offline job, after the browser tier has failed its tests. The 100 to 280 million parameter multilingual encoders proposed in `datasets-finetuning.md` section 4.1 are about 135 MB on disk and 448 MB in memory with the stock tokenizer (M), so they belong in the browser or on a paid 2 GB box.

## 4. Placement C: Hugging Face Spaces

| Question | Answer (P: huggingface.co/docs/hub/spaces-overview, spaces-sdks-static, storage-limits, terms-of-service) |
|---|---|
| Free CPU Space? | CPU Basic: 2 vCPU, 16 GB, 50 GB non-persistent disk, FREE hourly price, but "creating a Space that runs on compute (Gradio or Docker) requires a paid plan"; free accounts can host up to 2 Gradio Spaces on ZeroGPU only. |
| Sleep | Free hardware "will go to sleep and stop executing after a period of time if unused" (period not stated on that page). |
| Private Space access | Private: running app reachable only by the owner and collaborators, so a browser on our site cannot call it without our token; a token in client JavaScript would be public. Protected visibility (public app, private code) is PRO or Team. |
| Request size | Not stated on the pages read. UNVERIFIED. |
| Terms for health use | The Terms read do not address medical or mental-health use. Liability is capped at "$50 for free services"; HF "may also aggregate, anonymize, or learn from usage data"; inference inputs are not mentioned; private repos get "reasonable and appropriate measures" but HF may access or share under its Privacy Policy. |
| Third party for the privacy rule? | **Yes.** A Space is HF infrastructure, not our server, and the terms do not forbid training on what is sent. Personal text cannot go there under `AI_SEND_PERSONAL_TEXT=0`. |
| Static Space | Free, no compute, can serve files. Allowed as a model mirror for builders. |

Verdict C: **NO as an inference host** (needs a paid plan, which breaks constraint 1, and is a third party). Not needed as a file host.

## 5. Placement D and E: other free tiers and a later paid box

### 5.1 Table

| Option | Quota and terms found | Data use | Suitable for |
|---|---|---|---|
| Cloudflare Workers AI | 10,000 neurons a day free, resets 00:00 UTC; Workers Free has no overage, calls fail past the limit (P: developers.cloudflare.com/workers-ai/platform/pricing). | "Cloudflare does not use Customer Content processed by Workers AI to train AI models"; standard inference inputs and outputs are not retained (P: .../platform/data-usage). | Non-personal jobs only. Personal text is still third-party hosted inference; allowed only with the owner's written approval and a data-processing review (DPDP). Not recommended. |
| Google Colab free | "not guaranteed and not unlimited", about 12 h runtime, idle timeout, expensive GPUs restricted; file hosting and remote proxies prohibited (P: research.google.com/colaboratory/faq.html). | Prompts to Colab AI features can be read by human reviewers; keep personal data out. | Offline training and quantisation on public data. Never student data. |
| Kaggle notebooks | Weekly GPU quota and session length from memory (about 30 h and 12 h): UNVERIFIED, the docs page did not load for me. `datasets-finetuning.md` also could not open Kaggle docs. | n/a | Offline training, same rule. |
| Oracle Always Free | Ampere A1: 1,500 OCPU hours and 9,000 GB hours a month = 2 OCPUs and 12 GB (P: docs.oracle.com Always Free page); 2 AMD micro VMs, 1/8 OCPU, 1 GB. **Idle reclaim:** instance is idle if in 7 days CPU 95th percentile under 20 percent and network under 20 percent (and memory under 20 percent on A1). An allowance cut is visible: the older figure of 4 OCPU and 24 GB is from my memory, UNVERIFIED; today's page says 2 and 12. Card requirement not stated on that page; sign-up normally needs one (UNVERIFIED). | Our own VM | The only free always-on box with real RAM, but a quiet campus app would match the idle rule and be reclaimed, and a card likely breaks constraint 1. Owner decision. |
| Koyeb | Free web service 512 MB, 0.1 vCPU, 2 GB SSD, one per org, Frankfurt or Washington only; **card required** with a 29 dollar pre-authorisation hold (P: koyeb.com/docs/faqs/pricing, updated 2026-05-27). | Own VM | Same size as Render, so no gain; card breaks constraint 1. |
| Fly.io | Aggregators say new accounts get only a short trial (about 2 VM hours or 7 days). UNVERIFIED. | n/a | No. |
| Railway | Aggregators disagree: 5 dollar trial credit then 1 dollar a month, or 5 dollars a month. UNVERIFIED. | n/a | No. |
| GitHub Codespaces | Free personal: 120 compute hours and 15 GB-month storage a month (P: docs.github.com billing page); the page does not allow or forbid hosting. | n/a | Development only. |
| GitHub Actions | Free for public repos (docs/DEPLOY_FREE.md) | Our own runner, ephemeral | Shadow-mode evaluation and CI model checks on synthetic data (also proposed in `evidence-safety-eval.md`). |

### 5.2 Paid ladder, only verified prices (US dollars as listed by the vendor, no conversion)

| Step | Spec | Price | Source | Use |
|---|---|---|---|---|
| Render free | 0.1 CPU, 512 MB | 0 | P | Today |
| Render "less than 1 CPU" | 0.5 CPU, 512 MB, always on | 7 a month | P: render.com/pricing.md | Fixes sleep and escalation timers, **does not add RAM**, no help for models |
| Render 1 CPU | 1 CPU, 2 GB | 25 a month | P | First tier where a 135 MB encoder (448 MB in my test) fits comfortably |
| Render 2 CPU | 2 CPU, 4 GB | 85 a month | P | A 360M LLM plus Flask |
| Hetzner Cloud shared | specs not on the page I read | from 5.49 euro a month excluding VAT; Singapore is its only Asian location | P: hetzner.com/cloud | Cheapest always-on option with more RAM; card needed; confirm the plan specs before deciding |

Render bandwidth (5 GB a month on Hobby, 25 GB on Pro, 0.15 dollar a GB over; P) also matters if a paid box serves models.

## 6. Model optimisation, and what it means here

| Technique | Verdict for us | Evidence |
|---|---|---|
| ONNX export (Optimum, one command) | Do it for our own fine-tunes; for stock models use the `onnx-community` or `Xenova` exports | P: transformers.js custom-usage page |
| Dynamic int8 | Default for encoders: 470 to 118 MB on multilingual MiniLM (HF-API). Re-run the full evaluation on the quantised file, since quantisation can move recall (`datasets-finetuning.md` 4.3) | HF-API |
| int4 / q4f16 | For LLMs on WebGPU; for encoders it can be larger than int8 (398 vs 118 MB) | HF-API |
| GGUF | Only through wllama (MIT) as the non-WebGPU LLM fallback; files above 100 MiB must be sharded for Pages | P |
| Vocabulary pruning | The one big win for multilingual encoders: embedding table and tokenizer dominate (264 MB of 448 MB RSS). Keep only tokens seen in English, Hindi, Devanagari and Hinglish text. EST: 118 MB to under 50 MB. Needs a re-evaluation. | M plus EST |
| Distillation, pruning, LoRA | Research on a Colab or Kaggle GPU with public data; not a runtime concern | n/a |
| Dynamic batching | Not needed: pilot traffic is single digit requests a second, and a browser serves one student | EST |
| Embedding and answer caching | **Highest value:** precompute embeddings for exercises, tips and FAQ at build time (a few thousand 384-dimension float16 vectors is about 1 to 4 MB, EST), embed only the student's query in the browser, nearest neighbour in JS. Answers are the fixed texts in `utils/chat_templates.py`, no generation | EST |
| Streaming and token budgets | For any LLM: stream tokens from the worker by `postMessage`, `max_new_tokens` about 120, hard 10 s wall clock, then fall back to a fixed reply | EST |
| Cold-start mitigation | Browser: load model after first paint, on idle, only after consent; Render: do not warm models (the box sleeps); keep the existing `/health` keep-alive, which loads nothing | P: DEPLOY_FREE |

## 7. Failure, fallback, observability, versioning, supply chain

**Layers (lower never depends on higher):** L0 rule floor and fixed replies (server `ai/severity.py` plus JS mirror) then L1 local embedding retrieval (23 MB) then L2 raise-only classifier (shadow first) then L3 opt-in bigger local model. Each higher layer has a timeout (2 s for L1 and L2, 10 s for L3), a capability gate, and a kill switch. On any error, an out-of-memory tab reload, a device lost event or a timeout the page behaves exactly as if the layer were off. `evidence-safety-eval.md` section 3.7 proposes `AI_KILL_ALL` and `AI_L1_*` flags; a Render env change needs a restart, so also serve the active model id from a DB feature flag (`utils/feature_flags.py` exists) through the manifest route.

**Observability without text:** latency histograms with fixed buckets (under 50, 100, 250, 500, 1000, 2000 ms, above), counters by `model_id`, `device` (wasm or webgpu), `outcome` (ok, timeout, oom, unsupported, declined), download time bucket, cache hit. The browser posts bucket counts to one rate-limited endpoint that accepts only those enums and integers (no free text field exists to log). No user id, no text, no text length, no user-agent string. Server side: the same counters in memory, read by the existing admin pages. Matches the rule "never log patient text".

**Versioning and rollback:** manifest entries `{id, revision (40-hex commit), url, sha256, size_bytes, licence_spdx, licence_file, format, active, previous}`. The Cache API key includes `id@sha8`. Rollback = set `active` to `previous` in the manifest (no new download for students who still have it) and flip the DB flag. Old files stay on Pages for 30 days.

**Supply chain (all become CI checks, section 9):** `safetensors`, `onnx` or `gguf` only, never `.pkl`, `.pt`, `.bin`, `.ckpt` (pickle runs code at load; the Hub scanner is "not 100% foolproof", P: huggingface.co/docs/hub/security-pickle); pin an exact Hub commit, not `main`; hash every file; ship the licence text and a NOTICE next to each model; convert and quantise ourselves from a pinned revision where practical; pin `@huggingface/transformers` and its `onnxruntime-web` dev build as a pair and vendor the files (no CDN at runtime; `connect-src` forbids it anyway); Dependabot or a monthly manual check for the pair.

## 8. Recommended default architecture: browser first, personal text never goes to a third party, floor always on

(The existing `/chat` and journal POSTs already carry text to our own server for the authoritative floor and storage; this design adds no new place for personal text to go. See owner question 3.)

```
STUDENT PHONE (Chrome Android 12+, Safari iOS 26, others)
+-----------------------------------------------------------------------+
| Page (nonce scripts, strict CSP; AI pages add wasm-unsafe-eval)       |
|   L0  JS floor mirror (crisis_phrases) ---> fixed reply, instant      |
|   capability gate -> consent tap -> download from Pages (sha256 check)|
|        Cache API  "transformers-cache"@id+sha8  + storage.persist()   |
|   Web Worker (static/js/ai/worker.js, self, no blob)                  |
|     ORT-Web wasm (single thread) or webgpu                            |
|     L1 embed query (23 MB) -> nearest neighbour in precomputed vectors|
|     L2 raise-only signal (later, shadow) -> an integer 0..3           |
|     L3 optional small LLM (WebGPU, opt-in)                            |
|   timeouts + kill switch; failure => behave as if layer off           |
+-----------------+-----------------------------------+-----------------+
                  | existing POST /chat, /journal      | counts only
                  v (text, as today)                    v (buckets, enums)
RENDER FREE (Flask, 512 MB, sleeps)                /api/ai-metrics
  server floor ai/severity.py = authoritative; model signal can only raise
  no model loaded; no ONNX import; fixed templates; Gemini only for non-personal
                  |
                  v
NEON Postgres (labels, scores, alerts; never model text output)

GITHUB PAGES (mindfull-models, Chennai edge): wasm, models, manifest.json, licences
GITHUB ACTIONS: weekly hash + size + licence check; shadow evaluation on synthetic sets
COLAB / KAGGLE (offline, public data only): training, quantisation, evaluation
```

Server rules: no `onnxruntime` or `tokenizers` in `requirements.txt` for the default design (keeps the image and memory as today; `tests/test_perf.py` already asserts heavy imports stay out of `import app`, extend its list). Routes for the manifest and metrics go in a new blueprint `routes/ai_assets.py`, not in `app.py` (project rule). Static JS under `static/js/ai/` as small modules under 300 lines, no Jinja tags, no inline handlers.

## 9. CI checks to add

| # | Check | Where | Fails when |
|---|---|---|---|
| 1 | `tests/test_ai_manifest.py`: schema; `revision` is 40 hex; `sha256` present; `licence_spdx` in allowlist (Apache-2.0, MIT, BSD-3-Clause, CC-BY-4.0); Gemma, Llama and other custom terms need an explicit `reviewed_by` field; licence file present; `format` in onnx, safetensors, gguf | pytest (PR) | any entry malformed |
| 2 | Size budget `tests/test_ai_budget.py`: default tier total at most 30 MB including wasm if self-served by us; each file at most 50 MB; any tier at most its declared cap; `static/vendor/ort` total at most 20 MB; repo `static/` growth at most a set budget | pytest (PR) | over budget |
| 3 | Checksum job `models-verify` (scheduled weekly and on manifest change): download from Pages, compare sha256 and size with the manifest, check `Access-Control-Allow-Origin`, and that no file extension or magic bytes look like pickle (`\x80\x02` to `\x80\x05`, a zip holding `data.pkl`) | GitHub Actions, not blocking PRs | drift or tampering |
| 4 | CSP test (extend `tests/test_csp.py`): `wasm-unsafe-eval` only on AI pages; never `unsafe-eval`; `worker-src 'self'`; `connect-src` has at most the one Pages origin; no `blob:` in `script-src` | pytest | policy widened |
| 5 | Floor-only test: with every AI flag off, chat, journal and crisis tests pass and `import app` does not load `onnxruntime` or `tokenizers` | pytest | a hard dependency on a model |
| 6 | Raise-only property test: for the golden crisis set, final severity is never below `classify()` output when any model signal is injected, including a model that errors or returns garbage | pytest | a model can lower the floor |
| 7 | JS lint: no Jinja tags, no `Worker(` with a blob URL, no `eval`/`new Function`, no inline handlers, each file at most 300 lines | existing frontend job | violation |
| 8 | Memory smoke (scheduled): run the app and the subprocess under `docker run -m 512m`, load the model, assert peak RSS under 350 MB and p95 latency recorded | Actions | memory regression |

## 10. Engineering plan in phases

| Phase | Weeks | Work | Exit gate |
|---|---|---|---|
| 0 Spike | 1 | Hidden `/ai-lab` page behind a flag: ORT-Web wasm self-hosted, 23 MB model from a Pages test repo, own worker, CSP as in 2.6. Items: S1 worker and wasm under the new CSP; S2 Cache API plus `persist()` on Android Chrome and iOS Safari; S3 `useWasmCache` and blob import; S4 `integrity` through `env.fetch`; S5 peak memory and latency on 3 real phones (one under 4 GB RAM, one iPhone, one mid-range Android). | Numbers recorded in this file's table; if S3 or S5 fail, stay at L0 |
| 1 Plumbing | 2 to 3 | Models repo, manifest route, consent and capability gate, fallback ladder, metrics endpoint, CI checks 1 to 8, kill switch, floor JS mirror with test parity against `docs/review/generated/crisis_phrases.csv`. No student-facing model feature yet | All CI green, floor-only mode tested |
| 2 First feature | 4 to 6 | Precomputed library embeddings plus in-browser query embedding for exercise and tip matching; Hinglish evaluation set; compare with keyword baseline | Beats baseline by the bar set in `evidence-safety-eval.md`, else stop |
| 3 Shadow signal | 7 to 9 | Raise-only classifier in shadow mode (logs bucket counts only), evaluated by the datasets and safety plans | Pre-registered pass bars met; clinician sign-off |
| 4 Optional tiers | 10 to 12 | WebGPU small LLM or Whisper, opt-in, on Wi-Fi, only if the quality and safety work says yes | Measured on target phones |
| Later | when needed | Paid 2 GB box (Render 25 dollars a month) if the browser tier fails on too many phones | Owner approval |

## 11. What would convince me (smallest experiments)

| Claim | Experiment | Metric and pass bar (PROPOSED) |
|---|---|---|
| 23 MB model loads and runs on weak phones | S5 on 3 phones, 10 loads each | Load under 30 s on 5 Mbps Wi-Fi; peak tab memory under 250 MB; zero tab crashes in 30 runs; p95 under 300 ms |
| CSP works with strict policy | Spike S1 to S3 in Chrome Android, Safari iOS | Zero CSP reports for the AI page; model runs |
| Render cannot host the multilingual encoder | `docker run -m 512m` with the app plus subprocess, repeat my benchmark on Linux | Confirm peak RSS above 400 MB (my Windows figure was 448 MB) |
| Weak-device fallback is safe | Force-fail each gate on an emulator and real phone | Floor reply always shown in under 1 s |
| Pages bandwidth is enough | Count downloads for a pilot of 100 students | Under 20 GB a month at 24 MB each |

## 12. Cross-notes (files read on 2026-11-25: `voice-product.md`, `datasets-finetuning.md`, `evidence-safety-eval.md`; `speech.md`, `llm-agents.md`, `encoders-nlp.md` were not present yet)

- **Agreement with `datasets-finetuning.md` 4.3:** HF free Gradio and Docker Spaces need a paid plan; confirmed from the primary page. Their proposed 100 to 280 million parameter int8 encoder for concern detection does not fit Render free: 118 MB int8 file but 448 MB resident with the stock tokenizer (M). It goes to the browser, with vocabulary pruning, or to a 2 GB box.
- **Correction to `voice-product.md` F3 Plan B:** their "about 40 to 80 MB, ESTIMATE" for whisper-tiny is now measured from file listings: 43.3 MB at int8 (encoder 10.1, merged decoder 30.7, tokenizer 2.5) and about 79 MB for whisper-base. Untuned Whisper-tiny on Hindi FLEURS was reported at 172.60 percent WER in the Collabora blog (collabora.com, with a label conflict between blog and model card, so UNVERIFIED), so Plan B needs a Hindi-tuned tiny model. Their Q to me ("would a HF Space count as our own server?"): no, it is a third party and not free.
- **Agreement with `voice-product.md`:** server-side STT is out; browser speech with a Web Worker is the route; pre-rendered breathing audio is cheapest. I add that pre-rendered audio lives on Pages with a hash in the manifest.
- **Agreement with `evidence-safety-eval.md` 3.2 and 3.7:** lazy load after the first reply, kill flags, shadow mode in GitHub Actions. Conflict: they list L1 "second opinion" after `classify()` on the server; with the eventlet single worker and 512 MB it must be browser-side or a subprocess. Env flag changes restart Render, so the DB flag through the manifest is faster.
- **Would change my answer:** `encoders-nlp.md` choosing a multilingual encoder above 100 MB (then vocabulary pruning becomes mandatory, plan phase 2 slips two weeks); `speech.md` showing native on-device Hindi recognition on Android (then no Whisper download at all); `llm-agents.md` approving a generative companion (then the WebGPU L3 tier moves from research to build and download size 118 to 273 MB becomes the main cost).

## 13. Questions for the owner

1. **GitHub Pages for model files:** the Pages page bars "free hosting for an online business ... or commercial SaaS". Is the app a college pilot (non-commercial) so that a second Pages repo `mindfull-models` is acceptable, or should model files wait for a paid host?
2. **Card for Oracle, Koyeb or Hetzner:** all need one. Keep the "no card at all" rule for the free design and treat the 25 dollar Render 2 GB tier as the first paid step?
3. **Chat text path:** today `POST /chat` sends the student's message to our server (floor, stored replies). Keep that (server remains authoritative), or move toward local-only chat where only a fixed signal reaches the server? The second needs the JS floor mirror plus clinician review of its parity.
4. **Data cost to students:** accept a visible, opt-in 24 to 43 MB download on mobile data, with Wi-Fi-only as the default?
5. **Gemma or Llama licence terms** (custom, not OSI) are acceptable for L3, or limit to Apache-2.0 and MIT models only?

## Sources (accessed 2026-11-25)

Render: https://render.com/docs/free ; https://render.com/docs/compute-plans ; https://render.com/docs/outbound-bandwidth ; https://render.com/pricing.md
Hugging Face: https://huggingface.co/docs/hub/spaces-overview ; https://huggingface.co/docs/hub/spaces-sdks-static ; https://huggingface.co/docs/hub/storage-limits ; https://huggingface.co/terms-of-service ; https://huggingface.co/docs/hub/security-pickle ; https://huggingface.co/docs/transformers.js/guides/webgpu ; https://huggingface.co/docs/transformers.js/en/guides/dtypes ; https://huggingface.co/docs/transformers.js/en/custom_usage ; https://huggingface.co/docs/transformers.js/en/api/env ; model sizes through https://huggingface.co/api/models/<id>?blobs=true (ids listed in section 2.3)
Browsers and web platform: https://web.dev/blog/webgpu-supported-major-browsers ; https://web.dev/articles/coop-coep ; https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/script-src ; https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria ; https://developer.mozilla.org/en-US/docs/Web/API/Request/integrity ; https://bugs.webkit.org/show_bug.cgi?id=269777 ; https://bugs.webkit.org/show_bug.cgi?id=255103
Runtimes: https://onnxruntime.ai/docs/tutorials/web/env-flags-and-session-options.html ; https://onnxruntime.ai/docs/tutorials/web/ ; https://github.com/mlc-ai/web-llm ; https://webllm.mlc.ai/models/ ; https://github.com/ngxson/wllama ; https://developers.google.com/edge/mediapipe/solutions/genai/llm_inference/web_js ; https://developers.googleblog.com/en/litertjs-googles-high-performance-web-ai-inference/ ; npm registry and jsDelivr file listing for versions and wasm sizes ; PyPI JSON for onnxruntime wheel sizes
Other tiers: https://developers.cloudflare.com/workers-ai/platform/pricing/ ; https://developers.cloudflare.com/workers-ai/platform/data-usage/ ; https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm ; https://www.koyeb.com/docs/faqs/pricing ; https://research.google.com/colaboratory/faq.html ; https://docs.github.com/en/billing/concepts/product-billing/github-codespaces ; https://www.hetzner.com/cloud/
GitHub: https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits ; https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github ; response headers of https://ayushjaiswal21.github.io/mindfull-audio/data.json (curl -I)
UNVERIFIED snippets: gs.statcounter.com India Android versions; telecomtalk.info Ookla India speed; Fly.io and Railway comparison sites; Collabora Hindi Whisper blog
Repo files read: `utils/security_headers.py`, `utils/jobs.py`, `render.yaml`, `Dockerfile`, `extensions.py`, `app.py` cache policy, `routes/chat.py`, `utils/ai_policy.py`, `docs/DEPLOY_FREE.md`
My measurements: scratchpad scripts `bench.py` and `bench2.py` (onnxruntime 1.32.0, `CPUExecutionProvider`, 1 intra-op thread, arena off, 30 runs, input "main kal raat se bahut udaas hoon aur padhai mein mann nahi lag raha", max 128 tokens). SHA-256 of the files I benchmarked: MiniLM int8 `afdb6f1a0e45b715d0bb9b11772f032c399babd23bfc31fed1c170afc848bdb1`, e5-small int8 `4d24e2bc01a447951524466ef533e52944bf48509e6552810bcee1a2711cb02c`.
