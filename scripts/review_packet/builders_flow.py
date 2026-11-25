"""Builder for safety_flow.md."""
import re

from .ast_helpers import function_strings, module_ints, module_strings
from .builders_assessment import probe_bands
from .builders_crisis import crisis_reply_mode, outcome_text
from .core import CHECKS, check, excerpt, first_match, load, md_header, src, write_text


def build_flow(out, stamp, commit, dirty, sev, scoring, guard=None):
    crisis = 'utils/crisis.py'
    mins = first_match(crisis, r"CRISIS_ESCALATE_MINUTES'\)\s*or\s*([\d.]+)")
    max_level = module_ints(crisis).get('MAX_LEVEL')
    attempts = first_match(crisis, r"enqueue\('crisis_alert'[^\n]*max_attempts=(\d+)")
    jints = module_ints('utils/jobs.py')
    poll = first_match('utils/jobs.py', r'def run_worker\([^)]*poll_interval=([\d.]+)')
    lock = first_match('utils/jobs.py', r"_cfg\('JOB_LOCK_TIMEOUT',\s*(\d+)")
    jobs_default = 'on' if re.search(r"default = '1' if os\.getenv\('FLASK_ENV'\) == 'production'", src('utils/jobs.py')) else 'unknown'
    check('escalation interval default read from utils/crisis.py', mins is not None)
    check('MAX_LEVEL read from utils/crisis.py', max_level is not None)
    n = float(mins) if mins else None
    mins_s = f'{mins}' if mins else 'UNKNOWN (not found in code)'

    def at(k):
        return f'{n * k:g} min' if n is not None else 'unknown'

    chat_len = first_match('routes/chat.py', r'text\[:(\d+)\]')
    g_raw = getattr(guard, 'MAX_RAW_CHARS', None)
    g_chat = getattr(guard, 'FIELD_LIMITS', {}).get('chat') if guard is not None else None
    g_budget = getattr(guard, 'BUDGET', None)
    ai_page = src('templates/how_ai_works.html')
    model_first, fixed_first = crisis_reply_mode() == 'model', crisis_reply_mode() == 'fixed'
    crisis_cond = excerpt('ai/service.py', r'^\s*crisis = ', limit=1)
    helpline_cond = excerpt('ai/service.py', r'show_helplines = ', limit=1)
    friend_cap = excerpt('ai/service.py', r"score = min\(score, 6\)", limit=1)
    calls = []
    for rel in ('routes/chat.py', 'routes/patient.py', 'app.py', 'utils/crisis.py'):
        for ln in excerpt(rel, r'(?<!def )(?:try_)?record_crisis\('):
            if 'def ' not in ln:
                calls.append(ln)
    providers_q = excerpt(crisis, r"User\.role == 'provider'", limit=1)
    send_cond = excerpt(crisis, r'level >= 2 and target', limit=1)
    mail_subject = [t for _, _, t in function_strings(crisis, {'crisis_escalate'}, 20) if 'Unacknowledged' in t]
    notif = [t for _, _, t in function_strings(crisis, {'crisis_alert', 'crisis_escalate'}, 25)
             if 'student' in t.lower() and 'Unacknowledged' not in t and 'Event id' not in t]
    cm = re.search(r'class CrisisEvent\(db\.Model\):(.*?)\n\n\n', src('models.py'), re.S)
    cols = re.findall(r'^\s{4}(\w+) = db\.Column', cm.group(1), re.M) if cm else []
    has_followup = any(c for c in cols if re.search(r'follow|closed|status|resolved|contacted', c))
    no_hours = not re.search(r'hour|weekday|business|timezone|working', src(crisis), re.I)
    no_sms = not re.search(r'twilio|sms|whatsapp|fcm|push_notification|webpush', src(crisis) + src('utils/mailer.py'), re.I)
    sev_probe = {}
    if sev is not None:
        for lvl, probe in (('crisis', 'i want to die'), ('friend', 'my friend wants to die'),
                           ('soft', "i don't want to die"), ('none', 'hello how are you')):
            sev_probe[lvl] = (sev.classify(probe), sev.heuristic_severity(probe), probe)
    helplines = load('helplines_flow', 'utils/helplines.py')
    hl = [f"{h['name']}: {h['number']} ({h['hours']})" for h in helplines.HELPLINES] if helplines else ['UNKNOWN']
    sev_thresholds = ''
    if scoring is not None:
        pg = probe_bands(scoring.score_phq9, 9, 27)
        gg = probe_bands(scoring.score_gad7, 7, 21)
        ps = min((lo for lo, hi, (b, s) in pg if s), default=None)
        gs = min((lo for lo, hi, (b, s) in gg if s), default=None)
        sev_thresholds = f'PHQ-9 total >= {ps} or GAD-7 total >= {gs}'

    p = [md_header('Safety flow: what happens when someone may be at risk', stamp, commit, dirty), '']
    p += ['This is the step list for a clinician or lawyer to check. Each fact is read from the code at export time; where '
          'the code could not be read the text says UNKNOWN. Paths are relative to the project root.', '']
    p += ['## 0. Constants read from code and environment defaults', '',
          '| Constant | Value | Source |', '|---|---|---|',
          f'| Escalation interval (env `CRISIS_ESCALATE_MINUTES`) | {mins_s} min | utils/crisis.py `_minutes()` |',
          f'| Escalation levels | 1 to {max_level} (level 0 is the first notification) | utils/crisis.py `MAX_LEVEL` |',
          f'| Alert job retry ceiling | {attempts or "UNKNOWN"} attempts | utils/crisis.py `record_crisis` |',
          f'| Job retry backoff | full jitter, base {jints.get("BACKOFF_BASE", "?")} s, cap {jints.get("BACKOFF_CAP", "?")} s | utils/jobs.py |',
          f'| Worker poll interval | {poll or "?"} s | utils/jobs.py `run_worker` |',
          f'| Job lock timeout (env `JOB_LOCK_TIMEOUT`) | {lock or "?"} s | utils/jobs.py |',
          f'| In-process worker (env `JOBS_INPROCESS`) default | {jobs_default} only when FLASK_ENV=production | utils/jobs.py `init_jobs` |',
          '| Escalation email recipient | env `CRISIS_ESCALATION_EMAIL` (one address, unset by default) | utils/crisis.py |',
          '| SMTP | env `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` (unset by default) | utils/mailer.py |',
          f'| Detector severity values | ' + '; '.join(f'{k}: {v[1]}' for k, v in sev_probe.items()) + ' (probe sentences) | ai/severity.py `heuristic_severity` |',
          f'| Chat text checked by the rule-based floor | up to {g_raw} characters | utils/llm_guard.py `MAX_RAW_CHARS` |'
          if guard is not None else f'| Chat text cut before checking | {chat_len or "unknown"} characters | routes/chat.py |',
          f'| Chat text sent to the model (after clean-up) | up to {g_chat} characters | utils/llm_guard.py `FIELD_LIMITS` |'
          if guard is not None else '| Chat text sent to the model | not read (utils/llm_guard.py missing) | |',
          f'| Per-user model budget (env `AI_DAILY_LIMIT`, `AI_BURST_LIMIT`) | {getattr(g_budget, "daily", "?")} per day, '
          f'{getattr(g_budget, "burst", "?")} per minute | utils/llm_guard.py `UserBudget` |'
          if guard is not None else '| Per-user model budget | none (utils/llm_guard.py missing) | |',
          f'| Assessment alert thresholds | PHQ-9 item 9 >= 1, or {sev_thresholds} | ai/scoring.py |', '',
          'The exporter ignores the environment of the machine it runs on. Production may set different values: read the real '
          'production configuration before relying on the timeline.', '']
    p += ['## 1. The rule-based floor (runs first, never calls a model)', '',
          '`ai/severity.py::classify(text)` returns one of four classes:', '',
          '| Class | Meaning | Detector severity | Chat | Journal |', '|---|---|---|---|---|']
    for lvl, label in (('crisis', 'first-person self-harm language'), ('friend', 'someone else is at risk'),
                       ('soft', 'negated or ambiguous distress'), ('none', 'nothing found')):
        v = sev_probe.get(lvl, ('', '?', ''))
        c, j = outcome_text(lvl)
        p.append(f'| {lvl} | {label} | {v[1]} | {c} | {j} |')
    p += ['', 'The full phrase list is in `crisis_phrases.csv`; sentences and the detector output are in `crisis_test_cases.csv`.', '']
    p += ['## 2. Flow A: chat message (web chat, `POST /api/chat`)', '',
          '1. The student must be logged in; the user id comes from the session, never from the request.',
          ('2. The message is bounded (limit in section 0) and passed to `ai/service.py::ask_with_severity`.' if guard is None else
           '2. The message is bounded to the first limit in section 0 and passed to `ai/service.py::ask_with_severity`; the model only ever '
           'sees the cleaned, shorter text.'),
          '3. The rule-based class and severity are computed first, on the full bounded text, before anything else. ' +
          ('Injection markers are detected but this only hardens the prompt, it never changes the floor. A per-user budget decides whether '
           'the model is called at all; over budget, a crisis message is still answered by the floor. ' if guard is not None else '') +
          'Then the model (Gemini) is asked for a reply and its own severity. If the model fails, times out or is blocked, the rule-based '
          'result still stands.',
          f'4. Final severity is the higher of the rule-based and model severities. Decision line in code: `{(crisis_cond or ["NOT FOUND"])[0]}`.',
          f'   Friend class caps severity: `{(friend_cap or ["NOT FOUND"])[0]}`.',
          f'5. Helplines are attached when: `{(helpline_cond or ["NOT FOUND"])[0]}`.',
          '6. Which reply text is shown during a crisis:']
    if model_first:
        guard_txt = (' If the output guard blocks the model reply on a risk path (dosage, diagnosis stated as fact, method details, '
                     'promises, leaks), the fixed text is used instead.' if guard is not None else '')
        p += ['   - AS IMPLEMENTED: the model-written reply is shown during a crisis if the model returned a usable one; the fixed '
              '`CRISIS_REPLY` is used when the model gave nothing usable.' + guard_txt + ' Clinician note: the crisis wording is therefore '
              'not always the fixed text. ' + ('The public page `/ai` (templates/how_ai_works.html) says a fixed reply is shown "whatever the model wrote"; '
              'that sentence and the code disagree and the owner must resolve it before any claim is made.' if 'whatever the model wrote' in ai_page else
              'Check that the public page `/ai` (templates/how_ai_works.html) describes this accurately.')]
    elif fixed_first:
        p += ['   - AS IMPLEMENTED: the fixed `CRISIS_REPLY` is shown whenever the class is crisis.']
    else:
        p += ['   - UNKNOWN: the reply-selection code could not be matched by the exporter. Read ai/service.py.']
    p += [f'7. If the final decision is crisis, `routes/chat.py` writes a `CrisisEvent` (source `chat`, reason code `chat_self_harm`) '
          'and queues a `crisis_alert` job in one commit. If that write fails, the student still receives the reply and helplines '
          'and the response carries `alert_recorded: false`; an ERROR log line holds ids only.',
          '8. A crisis can also be raised by the model alone (model severity at or above the threshold with no rule hit). '
          'It then creates an alert with the same reason code.',
          '9. Soft and friend classes show helplines but create NO alert and NO counsellor notification.',
          '10. Legacy socket chat (`app.py` event `chat_message`): crisis text gets the fixed `CRISIS_REPLY` and '
          'an event with severity 9; the helplines appear inside that reply text.', '',
          'Calls that create events (verbatim):', ''] + ['    ' + c for c in calls] + ['']
    p += ['## 3. Flow B: journal entry', '',
          '1. Title and content are joined and checked with `utils/crisis.py::text_is_crisis`, which is true only for class crisis. '
          'Friend and soft classes are NOT flagged in journals.',
          '2. If crisis: the entry is saved and a `CrisisEvent` (source `journal`, severity 9, reason `journal_self_harm`) plus a '
          '`crisis_alert` job are written in the same transaction as the entry. If the write fails the student sees an error message '
          'and still sees the helplines.',
          '3. The student sees a warning message with the helplines (strings below). No points are awarded for that entry.',
          '4. The AI suggestion for a crisis entry is a fixed text with helplines; no model is called for it.', '']
    p += ['## 4. Flow C: PHQ-9 and GAD-7 (`POST /api/save-assessment`)', '',
          '1. The score is always recomputed on the server from the item answers; a client-sent score is ignored.',
          f'2. An alert is raised when PHQ-9 item 9 is answered 1, 2 or 3 (reason `phq9_item9_positive`, severity 9), or when the total is severe '
          f'({sev_thresholds}; reason `phq9_severe` or `gad7_severe`, severity 7). A skipped item 9 is unanswered and raises nothing.',
          '3. For an alert, the explanation text is fixed (no model call) and the response carries `crisis: true` plus the helplines; '
          'the assessment and the `CrisisEvent` commit together (all or nothing). If saving fails the student still gets the fixed text and helplines.',
          '4. Event source is `phq9` for GAD-7 events as well (the database allows only chat, phq9, journal).',
          '5. No points, badges or streaks are attached to any score.',
          '6. Moderate scores (PHQ-9 10 to 19, GAD-7 10 to 14) raise no alert and create no counsellor task. See `assessment_bands.csv`.', '']
    p += ['## 5. Alert pipeline and escalation timeline (after any event above)', '',
          '| Time | What happens | Who is told | How |', '|---|---|---|---|',
          '| T0 | Event row and `crisis_alert` job committed | nobody yet | database |',
          f'| T0 + a few seconds (worker poll {poll or "?"} s) | `crisis_alert` job runs | every provider account whose institution text equals the student\'s | in-app notification only |',
          f'| T0 + {at(1)} | Level 1, only if nobody acknowledged | same providers | in-app notification again |',
          f'| T0 + {at(2)} | Level 2 | same providers, plus one configured address | in-app notification; email only if `CRISIS_ESCALATION_EMAIL` and SMTP are set |',
          f'| T0 + {at(3)} | Level 3 (last) | same as level 2 | in-app notification and email as above; then an ERROR log line; no further steps |', '',
          'Acknowledging the event on the provider dashboard stops the chain at the next step.', '',
          f'Provider selection in code: `{(providers_q or ["NOT FOUND"])[0]}` (exact match on the free-text institution field; a typo or '
          'a different spelling means nobody is notified).',
          f'Email condition: `{(send_cond or ["NOT FOUND"])[0]}`.', '']
    if notif:
        p += ['Notification text counsellors see:', ''] + [f'> {t}' for t in notif] + ['']
    if mail_subject:
        p += ['Escalation email subject: ' + '; '.join(f'`{m}`' for m in mail_subject), '',
              'Email body holds the institution name, event id and time only. It never holds the student message.', '']
    p += ['Providers of the institution can also see all unacknowledged events on their dashboard without any assignment, and every '
          'acknowledgement is written to the audit log (`routes/provider/` package).', '']
    p += ['## 6. What the code does NOT do (read from the code, verify with the owner)', '']
    p += [f'- No out-of-hours logic: {"no hour, weekday or timezone handling was found in utils/crisis.py" if no_hours else "UNKNOWN, time-related words exist in utils/crisis.py; read it"}. '
          'An alert at 02:00 follows the same timeline as one at 14:00 and waits for a counsellor to log in.',
          f'- No SMS, WhatsApp, phone call or push notification: {"none found in the alert code" if no_sms else "UNKNOWN, matching words found; read the code"}.',
          '- Level 0 and level 1 reach counsellors only as in-app notifications. The only outbound message is the level 2 and 3 email to one configured address.',
          '- No notification to a guardian, hostel warden, college management or police.',
          f'- No follow-up workflow: the CrisisEvent columns are {", ".join(cols) or "UNKNOWN"}. '
          f'{"A column that looks like follow-up state exists; check it." if has_followup else "There is no contacted, closed or follow-up field, so the three-session follow-up from the UGC draft is not tracked."}',
          '- No merging of repeat alerts: each flagged message or entry creates its own event and notifications.',
          '- No 24x7 human behind the alerts is built into the product. Nobody is paged.',
          '- A model failure never removes the helplines, but a database failure can lose the alert (the student is still shown help).', '']
    p += ['## 7. Text the student sees (quoted from the code)', '']
    env = module_strings('ai/service.py')
    for nm in sorted(k for k in env if k.endswith('_REPLY')):
        p += [f'`ai/service.py::{nm}`', '', f'> {env[nm]}', '']
    for rel, funcs, label in (('ai/service.py', {'generate_journal_insights'}, 'Journal suggestion text for a crisis entry'),
                              ('routes/patient.py', {'patient_journal'}, 'Journal page messages'),
                              ('routes/patient.py', {'api_save_assessment'}, 'Assessment result text when an alert is raised'),
                              ('routes/chat.py', {'chat_handler'}, 'Chat API messages')):
        found = [(f, ln, t) for f, ln, t in function_strings(rel, funcs, 40)
                 if re.search(r'alone|painful|danger|screening result|Reach out|trusted|helpline|Free support|Something went wrong', t)]
        if found:
            p += [f'{label} (`{rel}`):', '']
            for f, ln, t in found:
                p += [f'> `{rel}:{ln}` {t}', '']
    js = src('static/js/inline_extracted/chat_inline_1.js')
    m = re.search(r'function showCrisisBanner\(.*?\n  }\n', js, re.S)
    if m:
        lines = re.findall(r"el\('p', null, '([^']+)'\)", m.group(0)) + re.findall(r"placeholder = '([^']+)'", m.group(0))
        p += ['Chat crisis banner (`static/js/inline_extracted/chat_inline_1.js`, function `showCrisisBanner`):', ''] + \
             [f'> {t}' for t in lines] + ['']
    p += ['Helplines shown (`utils/helplines.py`, one config for the whole app):', ''] + [f'- {h}' for h in hl] + \
         ['', 'Last verified in code: ' + (getattr(helplines, 'LAST_VERIFIED', 'UNKNOWN') if helplines else 'UNKNOWN') +
          '. See `helplines.csv` for the verification status of each number.', '']
    p += ['## 8. Drift checks (facts this file relies on, checked at export time)', '', '| Check | Result |', '|---|---|']
    for d, ok in CHECKS:
        p.append(f"| {d} | {'ok' if ok else 'FAILED: re-read the code before using this file'} |")
    write_text(out, 'safety_flow.md', '\n'.join(p))
