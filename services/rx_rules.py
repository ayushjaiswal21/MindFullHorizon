"""Pure prescribing rules (design 3.4, 3.5). No database access: functions take plain values or model rows."""
from services import config
from services.errors import MESSAGES

PRESCRIBABLE_SCHEDULES = ('none', 'H')

# Fixed warning texts (design 3.5). The permanent "not an interaction check" line is in utils/rx_text.SAFETY_LINES.
WARNING_TEXT = {
    'dup_active_rx': 'The patient already has an active prescription with the same medicine.',
    'dup_class': 'Two medicines in the same therapeutic class are involved.',
    'dup_self_logged': 'The patient lists this medicine in their own medicine log.',
    'allergy_text_match': 'The allergy text mentions this medicine.',
    'current_meds_text_match': 'The current medicines text mentions this medicine.',
}


def allowed_lists(tpg_context):
    """TPG lists a medicine may come from: first consult O and A; follow-up and in-person also B. C is never allowed."""
    return {'O', 'A'} if tpg_context in (None, 'first') else {'O', 'A', 'B'}


def default_env():
    return {'production': config.in_production(), 'allow_demo': config.allow_demo_data(),
            'four_eyes': config.four_eyes()}


def medicine_block_code(med, allowed, env=None):
    """None when `med` may be prescribed in this context, else the reason code (texts in services.errors.MESSAGES)."""
    env = env or default_env()
    if not med.active:
        return 'medicine_inactive'
    if med.is_demo and env['production'] and not env['allow_demo']:
        return 'medicine_demo_blocked'
    if med.is_controlled or med.schedule not in PRESCRIBABLE_SCHEDULES:
        return 'medicine_controlled'
    if med.list_verified_at is None or (env['four_eyes'] and med.list_verified_by is not None
                                        and med.list_verified_by == med.updated_by):
        return 'medicine_unverified'
    if med.tpg_list == 'C' or med.tpg_list not in ('O', 'A', 'B'):
        return 'medicine_blocked_c'
    if med.tpg_list not in allowed:
        return 'medicine_needs_followup'
    return None


def limits_cfg():
    return {'max_items': config.rx_max_items(), 'max_days_first': config.rx_max_days_first(),
            'max_days_followup': config.rx_max_days_followup()}


def max_days(tpg_context, cfg=None):
    cfg = cfg or limits_cfg()
    return cfg['max_days_first'] if tpg_context in (None, 'first') else cfg['max_days_followup']


def check_limits(items, tpg_context, cfg=None):
    """Item count and duration caps. `items` are dicts or rows with line_no and duration_days. Returns error dicts."""
    cfg = cfg or limits_cfg()
    cap, errors = max_days(tpg_context, cfg), []
    if len(items) > cfg['max_items']:
        errors.append(error('too_many_items'))
    for it in items:
        days = it['duration_days'] if isinstance(it, dict) else it.duration_days
        line = it['line_no'] if isinstance(it, dict) else it.line_no
        if days > cap:
            errors.append(error('duration_too_long', item=line, field='duration_days'))
    return errors


def error(code, item=None, field=None):
    """One entry of ValidateResult.errors (design 5.5)."""
    return {'code': code, 'item': item, 'field': field, 'message': MESSAGES.get(code, MESSAGES['bad_request'])}
