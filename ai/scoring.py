"""Pure PHQ-9 / GAD-7 scoring (screening tools, not diagnosis). See docs/SAFETY_RESEARCH.md."""


class ScoreError(ValueError):
    pass


PHQ9_BANDS = [(4, 'minimal'), (9, 'mild'), (14, 'moderate'), (19, 'moderately severe'), (27, 'severe')]
GAD7_BANDS = [(4, 'minimal'), (9, 'mild'), (14, 'moderate'), (21, 'severe')]


def _band(total, bands):
    return next(name for top, name in bands if total <= top)


def band_for(assessment_type, total):
    """Band label for 'PHQ-9' / 'GAD-7' totals, or None for other types."""
    bands = {'PHQ-9': PHQ9_BANDS, 'GAD-7': GAD7_BANDS}.get(assessment_type)
    return _band(total, bands) if bands and total is not None else None


def canonical_type(raw):
    """'GAD-7 Anxiety Screening' -> 'GAD-7'; unknown -> None."""
    s = str(raw or '').lower().replace('-', '').replace(' ', '')
    return 'PHQ-9' if s.startswith('phq9') else 'GAD-7' if s.startswith('gad7') else None


def _items(responses, n, optional_last=False):
    if not isinstance(responses, (list, tuple)) or len(responses) != n:
        raise ScoreError(f'expected {n} responses')
    for i, v in enumerate(responses):
        if v is None and optional_last and i == n - 1:
            continue
        if type(v) is not int or not 0 <= v <= 3:  # bool and float are rejected on purpose
            raise ScoreError('each response must be an integer 0-3')
    return list(responses)


def score_phq9(responses):
    r = _items(responses, 9, optional_last=True)
    total = sum(v for v in r if v is not None)
    # project rule: item 9 >= 1 is positive whatever the total; a skipped item 9 is "unanswered", never 0
    return {'total': total, 'band': _band(total, PHQ9_BANDS), 'severe': total >= 20,
            'item9_answered': r[8] is not None, 'item9_positive': bool(r[8])}


def score_gad7(responses):
    total = sum(_items(responses, 7))
    return {'total': total, 'band': _band(total, GAD7_BANDS), 'severe': total >= 15}


def score_assessment(assessment_type, responses):
    fn = {'PHQ-9': score_phq9, 'GAD-7': score_gad7}.get(assessment_type)
    if not fn:
        raise ScoreError('unsupported assessment type')
    return fn(responses)
