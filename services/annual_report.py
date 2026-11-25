"""Annual report for one institution (design 5.4). Aggregates only; every count drawn from fewer than K distinct people
(patients) is replaced by None with `suppressed: True`. Staff counts are not about students and are shown as they are.

Not a prevalence estimate: counts from this service only.
"""
from datetime import date
from statistics import median

from sqlalchemy import func, or_, union

from ai.scoring import band_for, canonical_type
from core.extensions import db
from models import (Appointment, Assessment, BreathingExerciseLog, CrisisEvent, DigitalDetoxLog, InventoryBatch,
                    InventoryTransaction, MedicationLog, MoodLog, MusicTherapyLog, PrescriberProfile, Prescription,
                    User, YogaLog)
from services import config
from services.db_util import inst_match
from services.http import iso
from utils.aggregates import patient_ids_query
from services.inventory_csv import to_csv
from utils.timeutil import ist_day_bounds, to_ist_date, utcnow

CSV_COLUMNS = ['section', 'metric', 'value', 'note']
BANDS = {'PHQ-9': ('None', 'Minimal', 'Mild', 'Moderate', 'Moderately Severe', 'Severe'),
         'GAD-7': ('Minimal', 'Mild', 'Moderate', 'Severe')}
NOTE = 'Counts from this service only; not a prevalence estimate.'


def _metric(name, value, people, k, note=''):
    """value is hidden when fewer than K distinct people stand behind it."""
    hidden = people < k
    return {'name': name, 'value': None if hidden else value, 'suppressed': hidden, 'note': note}


def _plain(name, value, note=''):
    return {'name': name, 'value': value, 'suppressed': False, 'note': note}


def _year_bounds(year):
    return ist_day_bounds(date(year, 1, 1))[0], ist_day_bounds(date(year + 1, 1, 1))[0]


def _distinct(col, *conds):
    return db.session.query(func.count(func.distinct(col))).filter(*conds).scalar() or 0


def _people(pids, start, end, k):
    registered = db.session.query(func.count(User.id)).filter(User.id.in_(pids), User.created_at < end).scalar() or 0
    new = db.session.query(func.count(User.id)).filter(User.id.in_(pids), User.created_at >= start,
                                                       User.created_at < end).scalar() or 0
    stamps = ((Assessment.user_id, Assessment.created_at), (MoodLog.user_id, MoodLog.created_at),
              (MedicationLog.user_id, MedicationLog.taken_at), (BreathingExerciseLog.user_id, BreathingExerciseLog.created_at),
              (YogaLog.user_id, YogaLog.created_at), (MusicTherapyLog.user_id, MusicTherapyLog.created_at))
    parts = [db.select(c).where(c.in_(pids), t >= start, t < end) for c, t in stamps]
    parts.append(db.select(DigitalDetoxLog.user_id).where(
        DigitalDetoxLog.user_id.in_(pids), DigitalDetoxLog.date >= to_ist_date(start), DigitalDetoxLog.date < to_ist_date(end)))
    active = db.session.scalar(db.select(func.count()).select_from(union(*parts).subquery())) or 0
    return [_metric('Students registered by the end of the year', registered, registered, k),
            _metric('New students in the year', new, new, k),
            _metric('Active students (any logged activity)', active, active, k)]


def _screenings(pids, start, end, k):
    out = []
    rows = db.session.query(Assessment.assessment_type, Assessment.score, Assessment.user_id).filter(
        Assessment.user_id.in_(pids), Assessment.created_at >= start, Assessment.created_at < end).all()
    for kind in ('PHQ-9', 'GAD-7'):
        mine = [(s, u) for t, s, u in rows if canonical_type(t) == kind]
        people = len({u for _, u in mine})
        out.append(_metric(f'{kind} screenings completed', len(mine), people, k))
        for band in BANDS[kind]:
            cell = [u for s, u in mine if band_for(kind, s) == band]
            out.append(_metric(f'{kind} band: {band}', len(cell), len(set(cell)), k))
    return out


def _appointments(pids, start, end, k):
    day0, day1 = to_ist_date(start), to_ist_date(end)
    out = []
    for label, statuses in (('requested', None), ('completed', ('completed',)), ('cancelled', ('cancelled',))):
        q = [Appointment.user_id.in_(pids), Appointment.date >= day0, Appointment.date < day1]
        if statuses:
            q.append(Appointment.status.in_(statuses))
        n = db.session.query(func.count(Appointment.id)).filter(*q).scalar() or 0
        out.append(_metric(f'Appointments {label}', n, _distinct(Appointment.user_id, *q), k))
    return out


def _crisis(pids, start, end, k):
    rows = db.session.query(CrisisEvent.user_id, CrisisEvent.created_at, CrisisEvent.acknowledged_at).filter(
        CrisisEvent.user_id.in_(pids), CrisisEvent.created_at >= start, CrisisEvent.created_at < end).all()
    people, window = len({r[0] for r in rows}), config.crisis_escalate_minutes() * 60
    mins = [(a - c).total_seconds() for _, c, a in rows if a]
    within = sum(1 for s in mins if s <= window)
    share = round(within / len(rows) * 100, 1) if rows else None
    med = round(median(mins) / 60, 1) if mins else None
    return [_metric('Crisis alerts raised', len(rows), people, k),
            _metric('Alerts acknowledged within the escalation time (%)', share, people, k),
            _metric('Median minutes to acknowledge', med, people, k)]


def _staff(key):
    base = User.query.filter(User.role == 'provider', User.deactivated_at.is_(None), inst_match(User.institution, key))
    counsellors = base.filter(or_(User.provider_type == 'counsellor', User.provider_type.is_(None))).count()
    verified = (base.join(PrescriberProfile, PrescriberProfile.user_id == User.id)
                .filter(User.provider_type == 'doctor', PrescriberProfile.status == 'verified',
                        PrescriberProfile.review_due_at > utcnow()).count())
    return [_plain('Counsellors', counsellors), _plain('Verified doctors', verified)]


def _clinical(key, start, end, k):
    q = [Prescription.institution_key == key, Prescription.issue_date >= start, Prescription.issue_date < end,
         Prescription.status != 'draft']
    issued = db.session.query(func.count(Prescription.id)).filter(*q).scalar() or 0
    people = _distinct(Prescription.patient_id, *q)
    done = db.session.query(func.count(Prescription.id)).filter(*q, Prescription.status == 'dispensed').scalar() or 0
    units = db.session.query(func.coalesce(func.sum(-InventoryTransaction.delta), 0)).join(
        InventoryBatch, InventoryBatch.id == InventoryTransaction.batch_id).filter(
        InventoryBatch.institution_key == key, InventoryTransaction.kind.in_(('dispense', 'return')),
        InventoryTransaction.created_at >= start, InventoryTransaction.created_at < end).scalar() or 0
    return [_metric('Prescriptions issued', issued, people, k),
            _metric('Prescriptions fully dispensed', done, people, k),
            _metric('Medicine units dispensed (total)', int(units), people, k)]


def build(institution_key, year, k=None):
    """{'year', 'institution', 'generated_at', 'sections': [{'title', 'metrics': [...]}]} (design 5.6 `report`)."""
    k = k or config.min_group()
    start, end = _year_bounds(year)
    pids = patient_ids_query(institution_key)
    sections = [('Students', _people(pids, start, end, k)), ('Screenings', _screenings(pids, start, end, k)),
                ('Appointments', _appointments(pids, start, end, k)), ('Crisis alerts', _crisis(pids, start, end, k)),
                ('Staff', _staff(institution_key)), ('Prescriptions and medicines', _clinical(institution_key, start, end, k))]
    return {'year': year, 'institution': institution_key, 'generated_at': iso(utcnow()), 'k': k, 'note': NOTE,
            'sections': [{'title': t, 'metrics': m} for t, m in sections]}


def to_csv_text(report):
    rows = []
    for sec in report['sections']:
        for m in sec['metrics']:
            hidden = m['value'] is None
            note = f"suppressed (fewer than {report['k']} people)" if hidden else m['note']
            rows.append({'section': sec['title'], 'metric': m['name'], 'value': '' if hidden else m['value'], 'note': note})
    head = [{'section': 'Report', 'metric': 'Year', 'value': report['year'], 'note': NOTE},
            {'section': 'Report', 'metric': 'Institution', 'value': report['institution'], 'note': ''},
            {'section': 'Report', 'metric': 'Generated at (UTC)', 'value': report['generated_at'], 'note': ''}]
    return to_csv(CSV_COLUMNS, head + rows)
