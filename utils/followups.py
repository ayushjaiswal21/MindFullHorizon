"""Post-crisis follow-up plans: configuration, creation and the step state machine (docs/FOLLOWUPS.md).

A plan is created when a provider acknowledges a CrisisEvent: N steps (config FOLLOWUP_SESSIONS, default 3) due
FOLLOWUP_DAYS (default 2,7,14) days after the acknowledgement, as IST calendar dates. The three-session figure comes from
a UGC DRAFT that is not verified as final, so it is configuration, not a rule in code.

pending -> done | missed | skipped (terminal). Each change is one compare-and-set UPDATE, audited with ids and codes only.
A plan completes when no step is pending, or closes early with a reason code. The caller commits. No free text here:
an optional note is saved by the route as a ClinicalNote.
"""
import os
from datetime import timedelta

from sqlalchemy import func, update

from core.extensions import db
from models import FollowUpPlan, FollowUpStep
from utils.audit import audit
from utils.jobs import enqueue
from utils.timeutil import ist_day_bounds, to_ist_date, utcnow

OUTCOMES = {
    'contacted_in_person': 'Met in person',
    'contacted_by_phone': 'Spoke by phone',
    'no_answer': 'No answer',
    'patient_declined': 'Student declined contact',
    'referred': 'Referred to another service',
    'other': 'Other',
}
CLOSE_REASONS = {
    'patient_declined': 'Student declined further contact',
    'referred': 'Referred to another service',
    'transferred': 'Care moved to another provider',
    'no_longer_needed': 'No longer needed',
    'other': 'Other',
}
RULES = {('pending', 'done'), ('pending', 'missed'), ('pending', 'skipped')}
CONFLICT_MESSAGE = 'This follow-up cannot be changed that way any more.'
REMIND_HOUR_IST = 9


class FollowUpError(Exception):
    """Illegal move or bad code."""


class FollowUpConflict(FollowUpError):
    """The step or plan is no longer in a state that allows this change (another request got there first)."""


def config():
    """(sessions, days): FOLLOWUP_SESSIONS (1 to 10, default 3) and FOLLOWUP_DAYS (default '2,7,14'), always N long and ascending."""
    try:
        n = min(10, max(1, int(os.getenv('FOLLOWUP_SESSIONS') or 3)))
    except ValueError:
        n = 3
    try:
        days = sorted({int(d) for d in (os.getenv('FOLLOWUP_DAYS') or '2,7,14').split(',') if int(d) > 0})
    except ValueError:
        days = []
    days = days or [2, 7, 14]
    while len(days) < n:  # more sessions than listed intervals: keep a weekly rhythm after the last one
        days.append(days[-1] + 7)
    return n, days[:n]


def create_plan(event, owner_id):
    """Plan plus N pending steps and their reminder jobs for an acknowledged `event`. Idempotent (unique crisis_event_id)."""
    existing = FollowUpPlan.query.filter_by(crisis_event_id=event.id).first()
    if existing:
        return existing
    n, days = config()
    base = to_ist_date(event.acknowledged_at or utcnow())
    plan = FollowUpPlan(crisis_event_id=event.id, patient_id=event.user_id, owner_provider_id=owner_id)
    plan.steps = [FollowUpStep(seq=i + 1, due_date=base + timedelta(days=d)) for i, d in enumerate(days)]
    db.session.add(plan)
    db.session.flush()
    for step in plan.steps:
        enqueue('followup_due', {'step_id': step.id}, idempotency_key=f'followup-due:{step.id}:{step.due_date.isoformat()}',
                run_at=ist_day_bounds(step.due_date)[0] + timedelta(hours=REMIND_HOUR_IST))
    audit(owner_id, 'followup_plan_create', 'followup_plan', plan.id, crisis_event_id=event.id, steps=n)
    return plan


def on_acknowledged(event, actor_id):
    """Called by the acknowledge route for the winning acknowledger: audit the acknowledgement and open the plan."""
    audit(actor_id, 'ack_crisis', 'crisis_event', event.id)
    create_plan(event, actor_id)


def _finish_if_resolved(plan_id, actor_id):
    if db.session.scalar(db.select(func.count()).select_from(FollowUpStep).where(
            FollowUpStep.plan_id == plan_id, FollowUpStep.status == 'pending')):
        return False
    won = db.session.execute(update(FollowUpPlan).where(FollowUpPlan.id == plan_id, FollowUpPlan.status == 'open')
                             .values(status='completed', closed_at=utcnow())).rowcount
    if won:
        audit(actor_id, 'followup_plan_complete', 'followup_plan', plan_id)
    return bool(won)


def set_step(step, new_status, actor_id, outcome=None):
    """pending -> done (needs an outcome code) | missed | skipped. A replay of the same change is a quiet no-op.
    Returns True when something changed. Raises FollowUpError on an illegal move."""
    if ('pending', new_status) not in RULES or (new_status == 'done') != (outcome is not None):
        raise FollowUpError('bad move')
    if outcome is not None and outcome not in OUTCOMES:
        raise FollowUpError('bad outcome')
    if step.status == new_status and step.outcome == outcome:
        return False
    plan_open = db.session.scalar(db.select(FollowUpPlan.status).where(FollowUpPlan.id == step.plan_id)) == 'open'
    changed = plan_open and db.session.execute(
        update(FollowUpStep).where(FollowUpStep.id == step.id, FollowUpStep.status == 'pending')
        .values(status=new_status, outcome=outcome, completed_at=utcnow() if new_status == 'done' else None)).rowcount
    if changed != 1:
        db.session.expire(step)
        raise FollowUpConflict('step changed concurrently')
    db.session.expire(step)
    audit(actor_id, f'followup_step_{new_status}', 'followup_step', step.id, plan_id=step.plan_id, seq=step.seq, outcome=outcome)
    _finish_if_resolved(step.plan_id, actor_id)
    return True


def close_plan(plan, reason, actor_id):
    """open -> closed_early with a reason code; pending steps become skipped. False for a replay."""
    if reason not in CLOSE_REASONS:
        raise FollowUpError('bad reason')
    if plan.status == 'closed_early' and plan.closed_reason == reason:
        return False
    won = db.session.execute(update(FollowUpPlan).where(FollowUpPlan.id == plan.id, FollowUpPlan.status == 'open')
                             .values(status='closed_early', closed_at=utcnow(), closed_reason=reason)).rowcount
    if won != 1:
        db.session.expire(plan)
        raise FollowUpConflict('plan changed concurrently')
    db.session.execute(update(FollowUpStep).where(FollowUpStep.plan_id == plan.id, FollowUpStep.status == 'pending')
                       .values(status='skipped'))
    db.session.expire(plan)
    audit(actor_id, 'followup_plan_close', 'followup_plan', plan.id, reason=reason)
    return True
