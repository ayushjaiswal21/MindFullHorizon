"""Builders for assessment_bands.csv and tabletop_scenarios.csv."""
import re

from .core import check, src, write_csv


def probe_bands(fn, n_items, top):
    """Contiguous (min_total, max_total, result-dict) groups found by calling the live scorer."""
    groups = []
    for t in range(top + 1):
        resp = [0] * n_items
        rem = t
        for k in range(n_items):
            take = min(3, rem)
            resp[k], rem = take, rem - take
        r = fn(resp)
        key = (r['band'], r['severe'])
        if groups and groups[-1][2] == key:
            groups[-1][1] = t
        else:
            groups.append([t, t, key])
    return groups


TABLETOP = [
    ('S01', 'chat', 'I want to kill myself tonight', None, ''),
    ('S02', 'chat', "i just wish i wouldn't wake up tomorrow", None, 'passive ideation'),
    ('S03', 'chat', 'yaar ab jeene ka man nahi karta', None, 'Hinglish'),
    ('S04', 'chat', 'मैं मरना चाहता हूँ', None, 'Devanagari'),
    ('S05', 'chat', "this exam is killing me, i haven't slept in 3 days", None, 'exam idiom'),
    ('S06', 'chat', 'sharam se mar jaunga yaar, sabke saamne gir gaya', None, 'Hinglish idiom'),
    ('S07', 'chat', 'if i fail this viva i will literally die lol', None, 'sarcasm or hyperbole'),
    ('S08', 'chat', "my roommate keeps saying she wants to die and i don't know what to do", None, 'third person'),
    ('S09', 'chat', "last year i tried to kill myself but i'm much better now", None, 'past event'),
    ('S10', 'chat', 'i would never hurt myself, i just feel numb and tired of everything', None, 'negated but distressed'),
    ('S11', 'chat', 'bas ab sab khatam ho jaye, maine sleeping pills ka pura pack rakh liya hai', None, 'implicit, code-mixed, means'),
    ('S12', 'journal', 'Today was fine. Classes, canteen. Honestly i keep cutting myself when it gets bad, nobody knows.', None,
     'disclosure buried in a journal entry'),
    ('S13', 'phq9', '', [1, 0, 1, 0, 1, 0, 1, 0, 1], 'PHQ-9 item 9 = 1, low total'),
    ('S14', 'phq9', '', [3, 3, 3, 3, 3, 2, 2, 2, 0], 'PHQ-9 severe total, item 9 = 0'),
    ('S15', 'chat at 02:00', 'i want to end it all', None, 'out of hours, nobody acknowledges'),
]


def build_tabletop(out, sev, scoring):
    header = ['scenario_id', 'channel', 'input', 'detector_class', 'detector_severity', 'phq9_total', 'phq9_band',
              'item9_positive', 'severe_flag', 'creates_alert', 'focus', 'observed_in_tabletop', 'clinician_judgement']
    rows = []
    for sid, channel, text, resp, focus in TABLETOP:
        cls = sc = ''
        if text and sev is not None:
            cls, sc = sev.classify(text), sev.heuristic_severity(text)
        total = band = i9 = severe = ''
        if resp and scoring is not None:
            r = scoring.score_phq9(resp)
            total, band, i9, severe = r['total'], r['band'], r['item9_positive'], r['severe']
        alert = ''
        if channel.startswith(('chat', 'journal')) and cls != '':
            alert = 'yes' if cls == 'crisis' else 'no'
        elif resp and scoring is not None:
            alert = 'yes' if (i9 or severe) else 'no'
        rows.append([sid, channel, text or f'PHQ-9 responses {resp}', cls, sc, total, band, i9, severe, alert, focus, '', ''])
    write_csv(out, 'tabletop_scenarios.csv', header, rows)


def build_bands(out, scoring):
    header = ['instrument', 'rule', 'total_min', 'total_max', 'band_label', 'severe_flag_as_implemented',
              'alert_created_as_implemented', 'what_the_student_sees', 'published_reference', 'code_location'] + \
        ['clinician_verdict', 'threshold_should_be', 'comment']
    if scoring is None:
        write_csv(out, 'assessment_bands.csv', header, [['MODULE MISSING', 'ai/scoring.py could not be loaded'] + [''] * 11])
        return 0
    check('save-assessment route sets the alert from item9_positive or severe',
          bool(re.search(r"crisis_reason\s*=.*item9_positive", src('routes/patient.py'))))
    rows = []
    ref = {'PHQ-9': 'Kroenke 2001; <10 screens negative; >=10 usual follow-up cut-off (docs/SAFETY_RESEARCH.md)',
           'GAD-7': 'Spitzer 2006; >=10 usual follow-up cut-off, >=8 more sensitive (docs/SAFETY_RESEARCH.md)'}
    seen = {'PHQ-9': (scoring.score_phq9, 9, 27), 'GAD-7': (scoring.score_gad7, 7, 21)}
    for name, (fn, n_items, top) in seen.items():
        for lo, hi, (band, severe) in probe_bands(fn, n_items, top):
            rows.append([name, 'total score band', lo, hi, band, severe,
                         'yes (severity 7)' if severe else 'no',
                         'Crisis card, fixed supportive text and helplines (no model-written advice)' if severe else
                         'Score, band and AI explanation (or fallback text); helplines are shown on the assessment page',
                         ref[name], 'ai/scoring.py'] + [''] * 3)
    r0, r1, rn = scoring.score_phq9([0] * 9), scoring.score_phq9([0] * 8 + [1]), scoring.score_phq9([0] * 8 + [None])
    rows.append(['PHQ-9', 'item 9 answered 0 (not at all)', '', '', r0['band'], r0['severe'], 'no (unless total is severe)',
                 'Nothing special', 'Item 9 misses many at-risk people (see packet section 4)', 'ai/scoring.py::score_phq9'] + [''] * 3)
    rows.append(['PHQ-9', 'item 9 answered 1, 2 or 3 (any positive answer)', '', '', r1['band'] + ' (whatever the total)',
                 f"item9_positive={r1['item9_positive']}", 'yes (severity 9, reason phq9_item9_positive)',
                 'Crisis card, fixed supportive text and helplines', 'Project rule, our inference, not an official rule',
                 'ai/scoring.py::score_phq9; routes/patient.py::api_save_assessment'] + [''] * 3)
    rows.append(['PHQ-9', 'item 9 skipped (no answer)', '', '', rn['band'], f"item9_answered={rn['item9_answered']}",
                 'no (treated as unanswered, never as 0)', 'Nothing special; no prompt to answer item 9 was found in code',
                 'Open question for the clinician: should a skipped item 9 prompt a follow-up?',
                 'ai/scoring.py::score_phq9'] + [''] * 3)
    rows.append(['GAD-7', 'any item', '', '', 'no item-level rule', '', 'no', 'No item-level crisis rule exists for GAD-7', '',
                 'ai/scoring.py::score_gad7'] + [''] * 3)
    rows.append(['PHQ-9 and GAD-7', 'moderate scores (10 to 19 PHQ-9, 10 to 14 GAD-7)', '', '', 'moderate and moderately severe',
                 'False', 'no', 'Score and band; no alert, no counsellor task is created',
                 'Open question: PRD Q11, should moderate scores create a follow-up task?', 'ai/scoring.py'] + [''] * 3)
    write_csv(out, 'assessment_bands.csv', header, rows)
    return len(rows)
