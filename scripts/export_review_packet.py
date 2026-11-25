#!/usr/bin/env python
"""Export the review packet data for clinicians, counsel and the pilot site.

    python scripts/export_review_packet.py [--out docs/review/generated] [--timestamp ISO8601]

Reads the LIVE code (detector, scoring, helplines, prompts, routes) and writes plain files that a human reviewer can
open without running the app: crisis_phrases.csv, crisis_test_cases.csv, safety_flow.md, assessment_bands.csv,
ai_prompt_snapshot.md, helplines.csv, tabletop_scenarios.csv and MANIFEST.md.

Rules of this script
- stdlib only, no network, no Gemini, no database. It never prints or writes secrets (a redaction pass runs on every
  output). Pure modules (ai/severity.py, ai/scoring.py, utils/helplines.py, utils/llm_guard.py) are loaded by file
  path so that `ai/__init__.py` (which imports the Gemini SDK and python-dotenv) is never executed.
- Everything else (routes, service, crisis jobs) is read as text or AST, so a missing dependency cannot break it.
- A missing or changed module prints a NOTE, produces a placeholder, and the run continues (exit code 0).
- Deterministic: same code and same --timestamp give byte-identical files. The commit hash and a code fingerprint
  (sha256 of the safety-relevant files) are recorded so a signed review can be tied to an exact version.

NOTHING in the output is clinically validated or legally reviewed. It is the current behaviour of the code.

Implementation lives in scripts/review_packet/ (split by concern: core state/helpers, AST helpers, regex phrase
expansion, test-case extraction, and one "builder" module per output file). This file is only the CLI entry point.
"""
import argparse
import datetime
import os
import sys

from review_packet.builders_assessment import build_bands, build_tabletop
from review_packet.builders_crisis import build_cases, build_phrases
from review_packet.builders_flow import build_flow
from review_packet.builders_helplines import build_helplines
from review_packet.builders_manifest import build_manifest
from review_packet.builders_prompt import build_prompt_snapshot
from review_packet.core import NOTES, ROOT, git_info, load, note, write_text


def count_lines(path):
    with open(path, encoding='utf-8-sig') as f:
        return sum(1 for _ in f)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', default=os.path.join(ROOT, 'docs', 'review', 'generated'))
    ap.add_argument('--timestamp', default=None, help='fixed UTC timestamp for reproducible output')
    args = ap.parse_args(argv)
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    stamp = args.timestamp or datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    commit, dirty = git_info()

    sev = load('severity', 'ai/severity.py')
    scoring = load('scoring', 'ai/scoring.py')
    helplines = load('helplines', 'utils/helplines.py')
    added = False
    if helplines is not None and 'utils.helplines' not in sys.modules:
        sys.modules['utils.helplines'], added = helplines, True  # llm_guard imports it by package name
    guard = load('llm_guard', 'utils/llm_guard.py')
    if added:
        sys.modules.pop('utils.helplines', None)

    steps = [
        ('crisis_phrases.csv', lambda: build_phrases(out, sev)),
        ('crisis_test_cases.csv', lambda: build_cases(out, sev)),
        ('assessment_bands.csv', lambda: build_bands(out, scoring)),
        ('helplines.csv', lambda: build_helplines(out, helplines)),
        ('tabletop_scenarios.csv', lambda: build_tabletop(out, sev, scoring)),
        ('ai_prompt_snapshot.md', lambda: build_prompt_snapshot(out, stamp, commit, dirty, guard)),
        ('safety_flow.md', lambda: build_flow(out, stamp, commit, dirty, sev, scoring, guard)),
    ]
    for name, fn in steps:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - one broken section must not stop the others
            note(f'{name} could not be built ({type(exc).__name__}: {str(exc)[:120]}); a placeholder was written')
            target = os.path.join(out, name)
            if not os.path.exists(target) or os.path.getsize(target) == 0:
                write_text(out, name, f'NOT EXPORTED: {name} failed with {type(exc).__name__}. See MANIFEST.md.')
    files = {n: count_lines(os.path.join(out, n)) for n, _ in steps if os.path.exists(os.path.join(out, n))}
    build_manifest(out, stamp, commit, dirty, files)
    print(f'Wrote {len(files) + 1} files to {out}')
    print(f'Git commit: {commit}')
    print(f'Notes: {len(NOTES)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
