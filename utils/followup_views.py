"""Read side of the follow-up tracker: the dashboard panel and the per-patient timeline (docs/FOLLOWUPS.md).

Visible to the plan owner and to providers assigned to the patient; only assigned providers get `can_act`.
A plan is never listed for anyone else. Two queries for the panel, two for a timeline.
"""
from datetime import timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import aliased, selectinload

from core.extensions import db
from models import Appointment, FollowUpPlan, FollowUpStep, ProviderPatient, User
from utils.followups import OUTCOMES
from utils.timeutil import ist_today

WINDOW_DAYS = 7


def _when(due, today):
    late = (today - due).days
    return ('due today' if late == 0 else f'due {due:%d %b}' if late < 0
            else f'was due {due:%d %b}, {late} day{"" if late == 1 else "s"} ago')


def panel(provider_id):
    """{'overdue': [...], 'today': [...], 'soon': [...]} of pending steps (due within 7 days or overdue), oldest first."""
    today = ist_today()
    prev, every = aliased(FollowUpStep), aliased(FollowUpStep)
    total = select(func.count()).select_from(every).where(every.plan_id == FollowUpPlan.id).scalar_subquery()
    before = (select(func.max(prev.completed_at)).where(prev.plan_id == FollowUpStep.plan_id, prev.seq < FollowUpStep.seq)
              .scalar_subquery())
    rows = db.session.execute(
        select(FollowUpStep, FollowUpPlan, User.name, ProviderPatient.id, total, before)
        .join(FollowUpPlan, FollowUpPlan.id == FollowUpStep.plan_id)
        .join(User, User.id == FollowUpPlan.patient_id)
        .outerjoin(ProviderPatient, and_(ProviderPatient.patient_id == FollowUpPlan.patient_id,
                                         ProviderPatient.provider_id == provider_id))
        .where(FollowUpPlan.status == 'open', FollowUpStep.status == 'pending',
               FollowUpStep.due_date <= today + timedelta(days=WINDOW_DAYS),
               or_(FollowUpPlan.owner_provider_id == provider_id, ProviderPatient.id.isnot(None)))
        .order_by(FollowUpStep.due_date, FollowUpStep.id)).all()
    done_with = {}
    if rows:
        done_with = dict(db.session.execute(
            select(Appointment.user_id, func.max(Appointment.updated_at))
            .where(Appointment.provider_id == provider_id, Appointment.status == 'completed',
                   Appointment.user_id.in_({r[1].patient_id for r in rows})).group_by(Appointment.user_id)).all())
    out, first = {'overdue': [], 'today': [], 'soon': []}, {}
    for step, plan, name, assigned, n, prior in rows:
        first.setdefault(plan.id, step.seq)  # rows are due-date ordered, so the first one per plan is its next step
        met = done_with.get(plan.patient_id)
        offer = bool(assigned and first[plan.id] == step.seq and met and met > (prior or plan.created_at))
        item = {'step_id': step.id, 'plan_id': plan.id, 'patient_id': plan.patient_id, 'name': name, 'seq': step.seq,
                'of': n, 'due': step.due_date.strftime('%d %b'), 'when': _when(step.due_date, today), 'can_act': bool(assigned), 'offer': offer}
        out['overdue' if step.due_date < today else 'today' if step.due_date == today else 'soon'].append(item)
    return out


def timeline(patient_id):
    """Up to 5 newest plans of the patient with their steps, for the wellness report (the caller has scoped the patient)."""
    plans = db.session.scalars(select(FollowUpPlan).where(FollowUpPlan.patient_id == patient_id)
                               .options(selectinload(FollowUpPlan.steps)).order_by(FollowUpPlan.created_at.desc())
                               .limit(5)).all()
    today = ist_today()
    return [{'id': p.id, 'status': p.status, 'created': p.created_at.strftime('%d %b %Y'),
             'steps': [{'id': s.id, 'seq': s.seq, 'due': s.due_date.strftime('%d %b %Y'), 'status': s.status,
                        'overdue': s.status == 'pending' and s.due_date < today,
                        'outcome': OUTCOMES.get(s.outcome), 'done': s.completed_at.strftime('%d %b') if s.completed_at else None}
                       for s in p.steps]} for p in plans]
