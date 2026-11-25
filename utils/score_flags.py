"""Screening score-change flags for the counsellor caseload (docs/FOLLOWUPS.md).

A flag says that the latest PHQ-9 or GAD-7 result rose by 5 or more points since the previous result of the same
type, or entered a higher severity band. It describes a screening result, not a diagnosis, and triggers no action.
`compute_flag` is a pure function; `flags_for_provider` reads every assigned patient with ONE query.
"""
from sqlalchemy import func, select

from ai.scoring import GAD7_BANDS, PHQ9_BANDS, canonical_type
from extensions import db
from models import Assessment, ProviderPatient

RISE_POINTS = 5
MAX = {'PHQ-9': 27, 'GAD-7': 21}
_BANDS = {'PHQ-9': PHQ9_BANDS, 'GAD-7': GAD7_BANDS}


def band_index(kind, score):
    """0-based severity band of a total (PHQ-9: minimal..severe, GAD-7: minimal..severe)."""
    return next(i for i, (top, _) in enumerate(_BANDS[kind]) if score <= top)


def band_name(kind, score):
    return _BANDS[kind][band_index(kind, score)][1]


def compute_flag(kind, previous, latest):
    """None, or {'kind','previous','latest','delta','reason','text'} when `latest` rose >= 5 points or entered a higher band."""
    if kind not in _BANDS or previous is None or latest is None:
        return None
    delta = latest - previous
    rose, higher = delta >= RISE_POINTS, band_index(kind, latest) > band_index(kind, previous)
    if not (rose or higher):
        return None
    text = (f'Score up {delta} since last screening ({kind})' if rose
            else f'Moved to a higher band since last screening ({kind})')
    return {'kind': kind, 'previous': previous, 'latest': latest, 'delta': delta,
            'reason': 'both' if rose and higher else 'rise' if rose else 'band', 'text': text}


def flags_from_series(series):
    """series {kind: [scores oldest to newest]} -> list of flags (PHQ-9 first), judged on the last two scores of each kind."""
    out = [compute_flag(k, v[-2], v[-1]) for k, v in sorted(series.items(), reverse=True) if len(v) >= 2]
    return [f for f in out if f]


def _by_kind(rows):
    """rows of (assessment_type, score) newest first -> {kind: [scores oldest first]} for PHQ-9 and GAD-7 only."""
    series = {}
    for raw, score in reversed(list(rows)):
        kind = canonical_type(raw)
        if kind and score is not None:
            series.setdefault(kind, []).append(score)
    return series


def flags_for_provider(provider_id):
    """{patient_id: [flag, ...]} for the provider's assigned patients; patients without a flag are absent. One query."""
    mine = select(ProviderPatient.patient_id).where(ProviderPatient.provider_id == provider_id)
    rn = func.row_number().over(partition_by=[Assessment.user_id, Assessment.assessment_type],
                                order_by=[Assessment.created_at.desc(), Assessment.id.desc()]).label('rn')
    ranked = (select(Assessment.user_id, Assessment.assessment_type, Assessment.score, Assessment.created_at,
                     Assessment.id, rn)
              .where(Assessment.user_id.in_(mine), func.lower(Assessment.assessment_type).like('phq%')
                     | func.lower(Assessment.assessment_type).like('gad%')).subquery())
    rows = db.session.execute(select(ranked).where(ranked.c.rn <= 2)).all()
    per_user = {}
    for r in sorted(rows, key=lambda r: (r.created_at, r.id), reverse=True):  # newest first across stored type strings
        per_user.setdefault(r.user_id, []).append((r.assessment_type, r.score))
    flags = {uid: flags_from_series(_by_kind(v)) for uid, v in per_user.items()}
    return {uid: f for uid, f in flags.items() if f}


def history_for_patient(patient_id, limit=40):
    """{kind: [(date, score), ...] oldest first} of the patient's last screenings per kind (for the report sparkline)."""
    rows = db.session.execute(select(Assessment.assessment_type, Assessment.score, Assessment.created_at)
                              .where(Assessment.user_id == patient_id).order_by(Assessment.created_at.desc(), Assessment.id.desc())
                              .limit(limit)).all()
    out = {}
    for raw, score, at in reversed(rows):
        kind = canonical_type(raw)
        if kind:
            out.setdefault(kind, []).append((at.strftime('%Y-%m-%d'), score))
    return {k: v[-8:] for k, v in out.items()}


def sparkline_xy(scores, kind, width=160, height=48, pad=4):
    """[(x, y)] SVG coordinates of scores on the fixed 0..max scale of the instrument (a 1-point series sits mid-width)."""
    top, n = MAX[kind], len(scores)
    return [(pad + (width - 2 * pad) * (i / (n - 1) if n > 1 else 0.5),
             height - pad - (height - 2 * pad) * min(max(s, 0), top) / top) for i, s in enumerate(scores)]


def sparkline_points(scores, kind, **size):
    return ' '.join(f'{x:.1f},{y:.1f}' for x, y in sparkline_xy(scores, kind, **size))
