"""Builders for crisis_phrases.csv and crisis_test_cases.csv."""
import inspect
import re

from .core import CSV_CLINICIAN, check, note, script, src, write_csv
from .phrase_expand import category_of, expand_pattern
from .test_cases import extract_test_cases


def build_phrases(out, sev):
    header = ['id', 'list', 'phrase_normalised_form', 'language_script', 'category_auto', 'detector_class_alone',
              'detector_severity_alone', 'pattern_id', 'pattern_regex', 'expansion_note', 'lookaround_conditions',
              'negation_rule', 'third_party_rule', 'idiom_rule', 'n_test_sentences_hitting_pattern', 'code_location'] + CSV_CLINICIAN
    if sev is None:
        write_csv(out, 'crisis_phrases.csv', header, [['', 'MODULE MISSING', 'ai/severity.py could not be loaded'] + [''] * 16])
        return 0
    cases = extract_test_cases()
    norm_cases = [sev.normalize(t) for t in cases]
    src_sev = inspect.getsource(sev.classify)
    neg_w = re.search(r'_NEGATORS & set\(before\[-(\d+):\]\)', src_sev)
    third_w = re.search(r'_THIRD & set\(before\[-(\d+):\]\)', src_sev)
    idiom_w = re.search(r'_IDIOM_BEFORE & set\(before\[-(\d+):\]\)', src_sev)
    check('classify() negation window is read from code', neg_w is not None)
    check('classify() third-party window is read from code', third_w is not None)
    neg_rule = (f"Downgraded to soft check-in (never dropped) if a negator word (rows list=negator_word) is in the previous "
                f"{neg_w.group(1) if neg_w else '?'} tokens of the same clause.")
    third_rule = (f"Class friend if no first-person word (rows list=first_person_word) is just before the hit and a third-party "
                  f"word (rows list=third_party_word) is in the previous {third_w.group(1) if third_w else '?'} tokens.")
    idiom_rule = (f"Skipped if an idiom word (rows list=idiom_exclusion_word) is in the previous "
                  f"{idiom_w.group(1) if idiom_w else '?'} tokens, or a negator in the previous 4.")
    rows = []
    n = [0]

    def add(list_name, idx, rx, rule_cols, class_alone=True):
        pid = f'{list_name[:2].upper()}{idx:03d}'
        phrases, trunc = expand_pattern(rx.pattern)
        lookaround = ' ; '.join(re.findall(r'\(\?[!=<][^)]*\)', rx.pattern))
        hits = sum(1 for nt in norm_cases if rx.search(nt))
        for ph in phrases:
            n[0] += 1
            alone = ('', '')
            if class_alone and '<' not in ph:
                try:
                    alone = (sev.classify(ph), sev.heuristic_severity(ph))
                except Exception:  # noqa: BLE001
                    alone = ('error', '')
            rows.append([f'P{n[0]:04d}', list_name, ph, script(ph), category_of(ph), alone[0], alone[1], pid, rx.pattern,
                         'expansion truncated' if trunc else 'complete', lookaround, *rule_cols, hits,
                         f'ai/severity.py::{ATTR_OF[list_name]}'] + [''] * 3)

    ATTR_OF = {'crisis_pattern': '_CRISIS', 'cautious_pattern': '_CRISIS_CAUTIOUS', 'friend_pattern': '_OTHER_RISK',
               'soft_pattern': '_SOFT', 'mild_pattern': '_MILD'}
    for i, rx in enumerate(getattr(sev, '_CRISIS', []), 1):
        add('crisis_pattern', i, rx, [neg_rule, third_rule, ''])
    for i, rx in enumerate(getattr(sev, '_CRISIS_CAUTIOUS', []), 1):
        add('cautious_pattern', i, rx, [neg_rule, third_rule, idiom_rule])
    if hasattr(sev, '_OTHER_RISK'):
        add('friend_pattern', 1, sev._OTHER_RISK, ['', 'Already about another person: friend path.', ''])
    if hasattr(sev, '_SOFT'):
        add('soft_pattern', 1, sev._SOFT, ['', '', ''])
    if hasattr(sev, '_MILD'):
        add('mild_pattern', 1, sev._MILD, ['', '', ''], class_alone=False)
    words = [('negator_word', sorted(sev._NEGATORS)), ('third_party_word', sorted(sev._THIRD)),
             ('first_person_word', sorted(sev._FIRST)), ('idiom_exclusion_word', sorted(sev._IDIOM_BEFORE))]
    for lname, ws in words:
        for w in ws:
            n[0] += 1
            rows.append([f'P{n[0]:04d}', lname, w, script(w), 'rule word', '', '', '', '', '', '', '', '', '', '',
                         'ai/severity.py'] + [''] * 3)
    for pat, rep in getattr(sev, '_CONTRACTIONS', []):
        n[0] += 1
        rows.append([f'P{n[0]:04d}', 'normalisation_rule', f'{pat}  ->  {rep}', 'Hinglish' if 'nahi' in rep or rep in ('hu', 'jana') else 'English',
                     'spelling normalisation', '', '', '', pat, '', '', '', '', '', '', 'ai/severity.py::_CONTRACTIONS'] + [''] * 3)
    write_csv(out, 'crisis_phrases.csv', header, rows)
    return len(rows)


def crisis_reply_mode():
    """'model' if the model-written reply wins during a crisis, 'fixed' if the fixed text always does, else 'unknown'."""
    svc = src('ai/service.py')
    if re.search(r'if crisis:\s*\n\s*reply = (CRISIS_REPLY|None)', svc) or 'reply = CRISIS_REPLY if crisis' in svc:
        return 'fixed'
    if re.search(r'reply = reply or \(CRISIS_REPLY', svc):
        return 'model'
    return 'unknown'


def outcome_text(level):
    mode = crisis_reply_mode()
    reply = {'model': 'the model reply if it returned one, else the fixed crisis reply', 'fixed': 'the fixed crisis reply',
             'unknown': 'reply text UNKNOWN to the exporter'}[mode]
    return {'crisis': (f'Crisis card with 3 helplines; reply text is {reply}; alert created',
                       'Entry saved, warning message with helplines, alert created'),
            'friend': ('Helping-a-friend reply with helplines; no alert', 'No special handling (not flagged)'),
            'soft': ('Gentle check-in reply with helplines; no alert', 'No special handling (not flagged)'),
            'none': ('Normal reply; no helplines unless the model is blocked', 'No special handling')}.get(level, ('', ''))


def build_cases(out, sev):
    header = ['case_id', 'text', 'language_script', 'test_type', 'test_expects', 'test_sources', 'detector_class',
              'detector_severity', 'detector_matches_test', 'matched_crisis_pattern_ids', 'normalised_form',
              'chat_outcome', 'journal_outcome', 'clinician_verdict', 'clinician_expected_class', 'clinician_comment']
    if sev is None:
        write_csv(out, 'crisis_test_cases.csv', header, [['', 'MODULE MISSING: ai/severity.py'] + [''] * 14])
        return 0
    check('chat helpline rule matches the outcome text', 'show_helplines = crisis or level in (' in src('ai/service.py'))
    cases = extract_test_cases()
    rows = []
    kind = {'crisis': 'positive (must trigger crisis)', 'none': 'negative (must not trigger)',
            'soft': 'ambiguous or negated (soft check-in)', 'friend': 'third party (friend path)'}
    for i, text in enumerate(sorted(cases, key=lambda t: (sorted(cases[t]['expects']), t)), 1):
        c = cases[text]
        level, score = sev.classify(text), sev.heuristic_severity(text)
        ids = [f'CR{j:03d}' for j, rx in enumerate(sev._CRISIS, 1) if rx.search(sev.normalize(text))]
        exp = sorted(c['expects'])
        chat, journal = outcome_text(level)
        rows.append([f'T{i:04d}', text, script(text), ' / '.join(kind.get(e, e) for e in exp), ' / '.join(exp),
                     ' ; '.join(sorted(c['sources'])), level, score, 'yes' if level in exp else 'NO', ' '.join(ids),
                     sev.normalize(text), chat, journal, '', '', ''])
    write_csv(out, 'crisis_test_cases.csv', header, rows)
    bad = [r for r in rows if r[8] == 'NO']
    if bad:
        note(f'{len(bad)} test sentence(s) currently disagree with their test expectation (column detector_matches_test)')
    return len(rows)
