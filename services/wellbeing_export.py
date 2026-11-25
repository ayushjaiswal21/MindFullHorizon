"""Account-export rows of the private wellbeing tools (same tuple shape as routes/auth.py `_EXPORT`)."""
from models import ReminderPref, SafetyPlan, SleepLog

WELLBEING_EXPORT = [
    ('safety_plans', SafetyPlan, 'user_id', ('client_request_id',)),
    ('sleep_logs', SleepLog, 'user_id', ('client_request_id',)),
    ('reminder_prefs', ReminderPref, 'user_id', ('nonce',)),  # the nonce is a link secret, not the student's data
]
