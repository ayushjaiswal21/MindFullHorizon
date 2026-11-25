"""Builder for MANIFEST.md."""
from .core import NOTES, fingerprints, md_header, write_text


def build_manifest(out, stamp, commit, dirty, files):
    p = [md_header('Generated review data: manifest', stamp, commit, dirty), '', '## Files', '',
         '| File | Rows or lines | Purpose |', '|---|---|---|']
    purposes = {'crisis_phrases.csv': 'Every phrase and pattern the detector uses; clinician columns blank',
                'crisis_test_cases.csv': 'Every test sentence with the detector output; clinician columns blank',
                'safety_flow.md': 'Step list: detection, replies, events, jobs, notifications, timeline',
                'assessment_bands.csv': 'PHQ-9 and GAD-7 cut-offs and the item 9 rule as implemented',
                'ai_prompt_snapshot.md': 'System prompt and refusal rules as implemented (canary redacted)',
                'helplines.csv': 'Helpline numbers in the app and their verification status',
                'tabletop_scenarios.csv': 'The 15 tabletop scenarios with live detector output'}
    for name in sorted(files):
        p.append(f'| {name} | {files[name]} | {purposes.get(name, "")} |')
    p += ['', '## Code fingerprint (sha256, first 16 hex, line endings normalised)', '', '| File | Fingerprint |', '|---|---|']
    p += [f'| {rel} | {h} |' for rel, h in fingerprints()]
    p += ['', 'A reviewer signing a page must copy the git commit above. If the working tree is not clean, also copy the '
          'fingerprints: the commit alone does not identify what was reviewed.', '', '## Notes from this run', '']
    p += [f'- {n}' for n in NOTES] or ['- none: every module and file was found']
    write_text(out, 'MANIFEST.md', '\n'.join(p))
