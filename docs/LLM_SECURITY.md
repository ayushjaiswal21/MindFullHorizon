# LLM security and resilience (as built)

Scope: every Gemini call (`ai/service.py`, `ai/gemini_impl.py`), the crisis floor (`ai/severity.py`), the guards (`utils/llm_guard.py`) and the breaker (`utils/circuit_breaker.py`). Research and threat model: [research/llm-security.md](research/llm-security.md). Clinical rules: [SAFETY_RESEARCH.md](SAFETY_RESEARCH.md). Tests: `tests/test_llm_injection.py`, `tests/test_llm_resilience.py`, `tests/test_safety.py`.

Principle: the model proposes, deterministic code disposes. No guard here is a proof against injection; each limits the damage if the model is fooled.

## Pipeline for a chat turn (`ask_with_severity`)

| Step | What | Where |
|------|------|-------|
| 1 | **Crisis floor** on the head and tail of the raw text (up to 20,000 chars). Runs first, alone, before sanitising, detection, budget or any model call. Normalisation strips zero-width/bidi/control characters, folds full-width and Cyrillic/Greek lookalikes, handles leetspeak (`k1ll`) and spaced letters. | `ai/severity.py` |
| 2 | Sanitise for the model: NFKC, drop invisible characters, collapse whitespace and repeat floods, cap (chat 1000, journal 4000, voice 2000, stored data 6000, clinical transcript 8000). | `llm_guard.sanitize` |
| 3 | Detect injection markers (English, Hinglish, Devanagari, role tags, markup, URLs, base64/hex blobs, indirect "note to AI"). Detection never blocks. A `moderate` verdict appends an alert to the system prompt. Only category codes, lengths and a boolean level are logged, never text. | `llm_guard.detect`, `log_event` |
| 4 | Per-user budget (id from the session only). Over budget: no model call, floor still answers. | `llm_guard.UserBudget` |
| 5 | Model call. Rules in `system_instruction`; user text only in `<user_message>` (angle brackets escaped so no delimiter survives); history in `<chat_history>` with roles forced to user/assistant, last 10 turns, each re-sanitised. | `ai/service.py` |
| 6 | Parse (first JSON object, tolerant), severity can only be raised by the model (`max(floor, model)`), action allow-listed, then output guard. | `ai/service.py` |
| 7 | Output guard (below). Unsafe or leaking replies are replaced: on a risk path by the fixed templates, otherwise by `SAFE_FALLBACK`. | `llm_guard.guard_output` |

Stored content echoed into prompts (journal entries, voice transcripts, clinical transcripts, assessment answers, progress/detox/goal/medication data) goes through `llm_guard.data_block` (sanitise, escape, wrap as `<journal_entry>`, `<voice_transcript>`, `<transcript>` or `<data>`) and `service._call`, which hardens the prompt on a `moderate` verdict.

## Output guard (`guard_output`, `clean_text`)

Strips HTML and script/style, fenced code, markdown images and links (link text kept), bare URLs, e-mail addresses, phone-like numbers that are not a helpline in `utils/helplines.py`, emoji; replaces em and en dashes with commas or hyphens. Blocks (replaces the whole reply): prompt leakage (canary, 8-word shingles of the system prompt, internal field names), dosage instructions, diagnoses stated as fact, self-harm method details, promises of confidentiality or cure. Non-string or empty output returns `''` so the caller uses its rule-based fallback. Length is capped at `AI_MAX_REPLY_CHARS` on a sentence or word boundary. Model-written JSON (assessment, progress, detox, goals, adherence) has every string passed through `clean_text` and a shape check; adherence score is clamped 0-100; assessment `resources` are always our helplines. Clinician notes use only the structural filters (`content_checks=False`) because medicines may legitimately appear there; they are drafts for review.

## Configuration

| Env var | Default | Meaning |
|---------|---------|---------|
| `GEMINI_API_KEY` | none | Blank means every AI feature uses the rule-based fallbacks |
| `AI_SEND_PERSONAL_TEXT` | `0` (off) | Truthy only for 1/true/yes/on. Off: no personal content is sent to any model (see "Personal-text policy") |
| `AI_PERSONAL_TEXT_APPROVED_BY` | none | Free-text record of the college's written approval; nowhere in the UI; the predeploy check warns when the flag is on without it |
| `GEMINI_MODEL_NAME` | `gemini-flash-lite-latest` | Pin a dated model id in production (model drift) |
| `GEMINI_TIMEOUT` | 20 | Seconds per request |
| `AI_MAX_RETRIES` | 2 (ceiling 2) | Retries on transient errors only (timeouts, 408, 429, 5xx, connection errors), full jitter, max 4 s sleep |
| `AI_BREAKER_FAILURES` | 2 | Consecutive failed requests that open the circuit |
| `AI_BREAKER_RESET_SECONDS` | 60 | Cool-down before one half-open trial call |
| `AI_DAILY_LIMIT` | 200 | AI messages per user per UTC day |
| `AI_BURST_LIMIT` | 8 | AI messages per user per 60 s |
| `AI_MAX_REPLY_CHARS` | 600 | The one value used in the prompt ("at most N chars") and the code clamp (closes O-19) |
| `AI_CANARY` | random per process | Leak tripwire written into the system prompt |

## Interactive latency (chat, ask, starter questions)

`ask_gemini_system_user(..., interactive=True)` shares one deadline of at most 10 s (`INTERACTIVE_TIMEOUT`, regardless of `GEMINI_TIMEOUT`) across all attempts, enforced by waiting on a worker thread so a stuck SDK call cannot hold the request. At most one retry, transient errors only, jitter up to 0.5 s, and no retry once the deadline has passed. No key configured: `RuntimeError` at once (no sleep, no retry, breaker untouched). The breaker opens after 2 consecutive failed requests for 60 s, so a dead provider costs one wait, then instant fallbacks. A text the crisis floor classifies as `crisis` never calls the model. Other generators keep `GEMINI_TIMEOUT` and up to 2 retries. Starter questions (`utils/chat_templates.py`, route `POST /api/chat/template`) use a fixed allowlist, a 24 h cache keyed by template id and AI config, the output guard before caching, and a static answer when the AI is off or down.

## Degradation and budgets

- Safety blocks (`GeminiBlocked`) are never retried and do not count as an outage. Client errors (4xx other than 408/429) neither retry nor open the circuit.
- Breaker open or a failed call: the rule-based replies answer (`DEFAULT_REPLY`, `SOFT_REPLY`, `FRIEND_REPLY`, `CRISIS_REPLY`). The chat payload keeps its keys and adds `ai_unavailable` (bool), `notice` (text or null), `rate_limited` (bool), `retry_after` (seconds). `/api/chat` also returns `ai_unavailable` and `notice` in its JSON when set. Exception text is never returned; logs carry the exception class only.
- Over budget: `/api/chat` and `/api/ask` return 429 JSON with `error`, `reply` (same text), `rate_limited`, `retry_after` and `helplines`, and say that messages about harming yourself are still answered. A crisis, friend or soft-risk text is never rate limited: the floor answers with the fixed template (HTTP 200) and no model call.
- `check_api_status()` reports key configured (bool), model name and breaker state; it never includes the key.

## SDK, model and what was not verified

`google.generativeai` is end-of-life (PyPI notice, 2025-08-31) and prints a FutureWarning at import. It is kept: no new dependency was added. The SDK call lives only in `GeminiProvider` (`ai/gemini_impl.py`), which implements `AIProvider`. Migration to `google-genai`:

1. Add `google-genai` to `requirements.txt`, remove `google-generativeai`.
2. Write `GenaiProvider(AIProvider)` with `ask(prompt, system_prompt, max_tokens, temperature, timeout)` and `configured()`: `client.models.generate_content(model=..., contents=prompt, config=GenerateContentConfig(system_instruction=..., max_output_tokens=..., temperature=...))`; map a blocked or empty candidate to `GeminiBlocked`, and make the exceptions expose `.code` or `.status_code` so `is_transient` classifies them.
3. Call `set_provider(GenaiProvider())` at startup (or switch the default `PROVIDER`). Breaker, retries, guards and callers do not change.
4. Consider `response_mime_type="application/json"` with an enum schema for `recommended_action`; the code validates anyway.
5. Re-run the tests, then a live smoke run (below).

**Verified live (2026-11-24, owner's rotated key):** `python scripts/check_gemini.py` passed the direct call and the full companion pipeline with `gemini-flash-lite-latest` (about 1.5 s). The `gemini-flash-latest` alias returned ResourceExhausted (free-tier quota) and `gemini-2.0-flash` and `gemini-2.5-flash-lite` return 404 for new keys, so the default is the lite alias. Re-run the script after any key, model or SDK change. Tests still use fakes.

## Known limits

- Budgets and the breaker are per process and in memory (bounded, LRU of 20,000 users). There is no chat message table, so counting rows in the database was not possible without a schema change. With several workers the effective limit is per worker. A shared store or a `llm_usage` table is the upgrade.
- The socket chat in `app.py` calls `generate_chat_response(msg)` without a user id, so it has the floor and guards but no budget until `app.py` passes `user_id=session['user_id']`.
- Journal, voice, detox and other generators have output and input guards but no per-user budget (their routes do not pass an id).
- Injection detection is regex based and easy to evade by paraphrase; it only hardens the prompt. Wrapping and escaping stop literal delimiter break-out, not persuasion. The deterministic floor, the max-only severity rule, the output guard and fixed templates are the real controls.
- Output guard patterns are English-only; a Hinglish dosage or method sentence can pass. Native-speaker review is needed.
- Crisis wordlists (English, Hinglish, Devanagari) are constructed fixtures and need clinician and native-speaker review (O-20). Known gaps: bare "khatam kar lena" is not matched (too many benign uses), "kms" gives only a soft check-in, fiction framings ("in a story...") rely on the model and the output guard.
- Provider-facing AI text should still show the code-computed crisis flag beside it (target in `docs/DESIGN.md`); this module does not change provider views.

## Personal-text policy (zero-cost deployment, decision 2026-11-24)

**Why.** The owner deploys at zero cost. Google's Gemini API free tier (unpaid services) may use submitted content to improve Google products; the paid tier does not (ai.google.dev/gemini-api/terms, data logging page). Billing is not acceptable, so: AI only for non-personal work. Student-authored or health-related text must never reach an external model in this mode.

**How.** `utils/ai_policy.py`: `personal_text_allowed()` reads `AI_SEND_PERSONAL_TEXT` on every call (default off). The one choke point is `ask_gemini_system_user(..., *, personal)`: `personal` is a required keyword, so an unclassified call raises `TypeError`, and `personal=True` with the flag off raises `PersonalTextBlocked` (a `RuntimeError`) before the key check, breaker or provider, so the existing deterministic fallbacks answer. `tests/test_ai_policy.py` also scans the source for any call to `ask_gemini_system_user`, `ask` or `_personal_call` that does not state `personal=`. The chat entry points (`ask_with_severity`, `_simple_chat`) also check the flag up front: no model call, no per-user budget used, no "AI unavailable" notice, a fixed reply (`ai/replies.py`) instead.

| Call site | `personal` | Off-mode result |
|-----------|-----------|-----------------|
| Chat `/api/chat` (`ask_with_severity`), `/api/ask` and socket chat (`_simple_chat`) | True | crisis, friend and soft fixed replies as before; otherwise `off_reply()` |
| Journal suggestions (`generate_journal_insights`) | True | crisis helplines text, else the existing thank-you text |
| Voice analysis (`analyze_voice_emotion`) | True | acoustic guess from `utils/voice_features.py` |
| Assessment insights (`generate_assessment_insights`) | True | fixed text and helplines |
| Progress recommendations (`generate_progress_recommendations`) | True | route answers "unavailable" with an honest message |
| Digital detox (`generate_digital_detox_insights`) | True | N/A score, no suggestion |
| Goal suggestions (`generate_goal_suggestions`) | True | empty list (no route calls it today) |
| Medication adherence (`analyze_medication_adherence`) | True | fixed fallback (no route calls it today) |
| Counsellor session note draft (`generate_clinical_note`, `routes/provider.py`) | True | "write the note yourself" |
| Starter-question answers (`utils/chat_templates.py`) | False | unchanged: fixed allowlisted question, cached 24 h |
| Tip of the day (`utils/daily_tip.py`) | False | n/a |

The crisis floor, the canned template answers, `CRISIS_REPLY` and the helplines never touch a model and are unchanged by the flag.

## Caveat policy for LLM-generated scores (decision 2026-11-25)

`analyze_medication_adherence` (adherence score 0-100) and `generate_digital_detox_insights`
(digital-detox score) each invent a number from a handful of logged entries, with no clinical
validation. Per `docs/research/ai/SYNTHESIS.md` section 3(c) item c2, both are kept (not removed)
but must always carry the exact caveat text in `utils/ai_caveats.py` (`ADHERENCE_CAVEAT`,
`DETOX_CAVEAT`) directly beside the score, plus the raw logged-entries count next to it, on every
screen where the score appears (`templates/digital_detox.html`, `templates/profile.html`,
`templates/wellness_report.html`). The score must never appear bare to a counsellor, and must
never be fed into an aggregate, chart, ranking or alert: the institution-wide "average wellness
score" chart that used to average `DigitalDetoxLog.ai_score` across patients (`routes/provider.py`
`_analytics_core`, `templates/analytics.html`) was removed for this reason. `generate_goal_suggestions`
returns titles/descriptions with no numeric score, so this policy does not apply to it.
`generate_progress_recommendations` is also free-text (insights/actions), already labelled "written
by an AI assistant ... general information, not clinical advice" in `templates/progress.html`.

**Tip of the day.** One short general tip, generated at most once per IST day per process from a fixed prompt plus a topic from a fixed list (no user data), started by `GET /api/tip` (never by a page render) in a background thread, passed through `guard_output`, held in process memory (no database). A page shows one of 30 vetted static tips (`utils/tip_data.py`) until the model's tip lands, and whenever the model is off, down, blocked or no key is set. The dashboard card is labelled "General tip, not advice for you".

**Turning personal-text AI on.** Only with the college's written approval. Set `AI_SEND_PERSONAL_TEXT=1` and record who approved and when in `AI_PERSONAL_TEXT_APPROVED_BY`; the on-page copy (chat, `/ai`, privacy, terms, FAQ, landing) then describes what is sent and that Google's free-tier terms may allow it to use submitted content. A paid Gemini tier would remove that concern, but is not part of this deployment.

**Not verified.** The behaviour on a multi-process host: the daily tip is per process, so each worker may make one call a day.
