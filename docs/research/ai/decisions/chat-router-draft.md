# Decision: lexical chat router (clinician-reviewed 2026-11-25, now ships ON)

**Update 2026-11-25:** the owner, a licensed psychiatrist/psychologist, read all 16 KB snippets in full in a chat
review and approved them as clinically appropriate (plain, factual pointers to the app's own features; no
invented coping techniques, no diagnosis, no medication advice). Each file's `review_status` is now
`clinician_reviewed` (`reviewed_at: 2026-11-25`). Record: `docs/review/signoff/2026-11-25-clinician-approvals.md`.
`CHAT_ROUTER_ENABLED` now defaults to `1` in `render.yaml` and `.env.example`. The owner explicitly accepted the
remaining limitation below (1 snippet per intent, not the 80-150 `SYNTHESIS.md` suggests for natural variety) as a
known trade-off for an earlier launch, not a safety gap — the content itself is reviewed, only its variety is thin.

The description below is otherwise unchanged from the original build.

Built per SYNTHESIS.md section 3(b) item b3: a local char n-gram TF-IDF router (`ai/router.py`) matches a
student's free-typed chat text against ~16 fixed intents (aliases: English, Hinglish, common misspellings).
A confident match returns a knowledge-base snippet (`ai/kb.py`, `ai/kb_data/*.json`); a low-confidence match
returns a short clarifying menu (2-4 likely intents); no match falls back to the existing `off_reply()`
exactly as before. Wired into `ai/service.py::ask_with_severity` at the exact point `off_reply()` was called,
only for a message the crisis floor (`ai/severity.py`) already classified `'none'`. Crisis/friend/soft are
decided before this code runs and are never reconsidered by it.

No model call, no network: matching is 100% local lexical text comparison inside the Flask process. The
student's message is read in memory to compute n-gram overlap and is not sent anywhere, logged, or stored.

## Ships OFF by default

New flag `CHAT_ROUTER_ENABLED`, default `0` in `.env.example` and `render.yaml`. With it unset or `0`,
`ask_with_severity` behaves exactly as before (`tests/test_chat_router.py::test_flag_off_preserves_off_reply`).

**To turn it on for testing or a demo:** set `CHAT_ROUTER_ENABLED=1` in the environment (or Render dashboard)
and restart the process. There is no other switch.

## Why it is off: nothing here has been clinically reviewed

Every file in `ai/kb_data/` is tagged `"review_status": "draft_unreviewed"`. Each snippet is either adapted
from existing fixed text in this repo (the FAQ in `routes/pages.py`, `ai/replies.py`/`ai/service.py`'s fixed
replies, `utils/chat_templates.py`) or is plain psychoeducation pointing only at the app's own existing
features (breathing guide, journal, etc.) - no invented coping technique or clinical script. `flask
list-kb-drafts` lists every entry with its source for review.

## What a clinician must review before production

1. **The KB content** (`ai/kb_data/*.json`, 16 files): wording, accuracy, and whether pointing at a tool is
   the right answer for that intent. Each file's `source` field says what it was adapted from.
2. **The intent-confidence threshold** (`ai/router.py::CONFIDENCE_THRESHOLD = 0.20`): tuned only against the
   author's own `tests/test_chat_router.py` smoke set, same caveat as `encoders-nlp.md` section 3.3 (shared
   authorship inflates the score). Needs an independently authored Hinglish set per SYNTHESIS.md's pass bar
   (85% top-1) before raising confidence in it.
3. **The clarifying-menu wording** (`ai/service.py::routed_reply`, the "I'm not sure what you mean yet..."
   line) and the intent labels shown in it (`ai/router.py::Intent.label`).

Until items 1-3 are signed off, this stays OFF in production per `SYNTHESIS.md` section 2.6.
