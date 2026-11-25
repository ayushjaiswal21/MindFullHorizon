"""Score a filled independent crisis-evaluation CSV against the live crisis floor (ai/severity.py + ai/fuzzy_crisis.py).

This is the companion to docs/review/eval_set_template.csv (see docs/review/EVAL_SET_HOWTO.md for how to fill it).
It never trains anything: it only measures today's deterministic detector against a held-out set the detector's
own author never saw, which is the first real accuracy number the floor has ever had (see SYNTHESIS.md section 2).

    python scripts/score_eval_set.py docs/review/eval_set_filled.csv

Reads `item_id, stratum, language_script, text, your_label_none_concern_checkin_crisis` (extra columns ignored).
Rows with an empty `text` or label are skipped (still-blank template rows). Maps the 4-point clinician label
(none/concern/checkin/crisis) onto the detector's 4 levels (none/soft/friend/crisis) as: none->none,
concern->soft-or-none (either counts as a correct low-level read), checkin->soft, crisis->crisis. `friend`
(third-party) rows are matched by stratum name containing "third_party", not by the label scale.
Prints per-stratum and overall recall with a Wilson 95% confidence interval, and the false-alert rate on
hard-negative rows, against the pass bar in SYNTHESIS.md section 2: overall recall >= 0.90 (CI lower bound >=
0.85), each language slice >= 0.80, false-alert rate on hard negatives <= 2%.
"""
import csv
import math
import sys

sys.path.insert(0, '.')


def wilson(successes, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (p, max(0.0, (centre - half) / denom), min(1.0, (centre + half) / denom))


def expected_is_crisis(stratum, label):
    label = (label or '').strip().lower()
    if 'must_trigger' in stratum:
        return True
    if label == 'crisis':
        return True
    return False


def is_hard_negative(stratum):
    return stratum in ('hard_negative', 'negated_passive_soft', 'third_party')


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    from ai.fuzzy_crisis import classify_and_score

    rows = []
    with open(sys.argv[1], newline='', encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            text = (r.get('text') or '').strip()
            label = (r.get('your_label_none_concern_checkin_crisis') or '').strip()
            if not text or not label:
                continue
            rows.append(r)

    if not rows:
        print('No filled rows found (text and label both required). Nothing to score.')
        return 1

    by_stratum = {}
    by_lang = {}
    false_alerts, hard_neg_n = 0, 0
    for r in rows:
        stratum, lang, text = r['stratum'], r['language_script'], r['text']
        level, score, matched_via = classify_and_score(text)
        fired = level == 'crisis'
        expected = expected_is_crisis(stratum, r.get('your_label_none_concern_checkin_crisis'))
        hit = fired == expected
        by_stratum.setdefault(stratum, [0, 0])
        by_stratum[stratum][0] += 1 if hit else 0
        by_stratum[stratum][1] += 1
        by_lang.setdefault(lang, [0, 0])
        by_lang[lang][0] += 1 if hit else 0
        by_lang[lang][1] += 1
        if is_hard_negative(stratum):
            hard_neg_n += 1
            if fired and not expected:
                false_alerts += 1

    print(f'{len(rows)} filled rows scored.\n')
    print('Recall by stratum (correct / total, 95% CI lower-upper):')
    overall_ok, overall_n = 0, 0
    for stratum, (ok, n) in sorted(by_stratum.items()):
        p, lo, hi = wilson(ok, n)
        print(f'  {stratum:32s} {ok:4d}/{n:<4d}  {p:.2f}  [{lo:.2f}, {hi:.2f}]')
        overall_ok += ok
        overall_n += n
    p, lo, hi = wilson(overall_ok, overall_n)
    print(f'\nOverall: {overall_ok}/{overall_n} = {p:.3f}  95% CI [{lo:.3f}, {hi:.3f}]')

    print('\nRecall by language:')
    for lang, (ok, n) in sorted(by_lang.items()):
        p2, lo2, hi2 = wilson(ok, n)
        print(f'  {lang:20s} {ok:4d}/{n:<4d}  {p2:.2f}  [{lo2:.2f}, {hi2:.2f}]')

    false_rate = false_alerts / hard_neg_n if hard_neg_n else 0.0
    print(f'\nFalse-alert rate on hard-negative strata: {false_alerts}/{hard_neg_n} = {false_rate:.3f}')

    print('\nPass bar (SYNTHESIS.md section 2):')
    print(f'  overall recall >= 0.90, CI lower >= 0.85:  {"PASS" if p >= 0.90 and lo >= 0.85 else "NOT MET"}')
    print(f'  every language slice >= 0.80:              '
          f'{"PASS" if all(wilson(ok, n)[0] >= 0.80 for ok, n in by_lang.values()) else "NOT MET"}')
    print(f'  false-alert rate <= 0.02:                  {"PASS" if false_rate <= 0.02 else "NOT MET"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
