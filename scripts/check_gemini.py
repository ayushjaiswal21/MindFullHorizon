"""Live smoke check of the Gemini integration (opt-in, sends two harmless prompts, prints no secrets).

    python scripts/check_gemini.py

Reads GEMINI_API_KEY (and optionally GEMINI_MODEL_NAME) from the environment or `.env`. Checks that the key works,
that the model id and the SDK call form are accepted, that the interactive path answers within its deadline, and
that the full companion pipeline (crisis floor, prompt guard, model, output guard) returns a usable reply.
Exit code 0 on success, 1 on any failure. Needs network access; never run it in CI.
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    from dotenv import load_dotenv
    load_dotenv()
    if not os.environ.get('GEMINI_API_KEY'):
        print('FAIL: GEMINI_API_KEY is not set (checked the environment and .env)')
        return 1
    os.environ['AI_SEND_PERSONAL_TEXT'] = '1'  # this process only: the pipeline step sends one fixed harmless sentence, no student text
    from ai import gemini_impl
    from ai.service import ask_with_severity
    print(f"model id: {gemini_impl.GEMINI_MODEL_NAME} (fallback {gemini_impl.FALLBACK_MODEL}); key length {len(os.environ['GEMINI_API_KEY'])}")
    failures = 0
    t0 = time.perf_counter()
    try:
        out = gemini_impl.ask_gemini_system_user('You are a test. Reply with the single word OK.', 'ping', max_tokens=16, personal=False)
        print(f"PASS direct call: {out.strip()[:40]!r} in {time.perf_counter() - t0:.1f}s")
    except Exception as exc:  # class name only: never print messages that could echo a key
        failures += 1
        print(f"FAIL direct call: {type(exc).__name__} after {time.perf_counter() - t0:.1f}s")
    t0 = time.perf_counter()
    try:
        res = asyncio.run(ask_with_severity('I feel a bit stressed about my exams this week.', user_id=None))
        ok = bool(res.get('reply')) and not res.get('ai_unavailable')
        print(f"{'PASS' if ok else 'FAIL'} companion pipeline: severity={res.get('severity')} unavailable={res.get('ai_unavailable')} "
              f"reply_chars={len(res.get('reply') or '')} in {time.perf_counter() - t0:.1f}s")
        failures += 0 if ok else 1
    except Exception as exc:
        failures += 1
        print(f"FAIL companion pipeline: {type(exc).__name__}")
    print('RESULT:', 'all checks passed' if not failures else f'{failures} check(s) failed')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
