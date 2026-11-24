"""Pre-deploy configuration check. Reads the environment, prints PASS / WARN / FAIL lines, exits 1 on any FAIL.

    python scripts/predeploy_check.py                  # check the current environment
    python scripts/predeploy_check.py --pilot          # real students: a missing CRISIS_ESCALATION_EMAIL is a FAIL
    python scripts/predeploy_check.py --check-db       # also connect (10 s timeout), SELECT 1, read alembic_version

Stdlib only (psycopg2 is imported lazily for --check-db). No network except --check-db. Secret values are never
printed: only presence and length. See docs/DEPLOY.md.
"""
import argparse
import os
import sys
from urllib.parse import parse_qs, urlsplit

PASS, WARN, FAIL = 'PASS', 'WARN', 'FAIL'
PLACEHOLDERS = ('change-me', 'changeme', 'change_me', 'your-secret', 'your_secret', 'test-secret', 'secret-key',
                'replace-me', 'example', 'dev-secret', 'insert', 'xxxx', 'placeholder')
LOCAL_HOSTS = ('localhost', '127.0.0.1', '::1', '')
SMTP_GROUP = ('SMTP_HOST', 'SMTP_USER', 'SMTP_PASSWORD', 'SMTP_FROM')


def _get(env, name):
    return (env.get(name) or '').strip()


def normalize_db_url(url):
    return 'postgresql://' + url[len('postgres://'):] if url.startswith('postgres://') else url


def check_flask_env(env):
    v = _get(env, 'FLASK_ENV')
    if v == 'production':
        return [(PASS, 'FLASK_ENV', 'production')]
    return [(FAIL, 'FLASK_ENV', f"must be 'production' (is {'unset' if not v else repr(v)}); production turns on secure cookies, HSTS and the SECRET_KEY check")]


def check_secret_key(env):
    v = _get(env, 'SECRET_KEY')
    if not v:
        return [(FAIL, 'SECRET_KEY', 'not set: the app refuses to start in production')]
    if len(v) < 32:
        return [(FAIL, 'SECRET_KEY', f'too short ({len(v)} chars, need 32 or more)')]
    low = v.lower()
    if any(p in low for p in PLACEHOLDERS):
        return [(FAIL, 'SECRET_KEY', 'looks like a placeholder; generate a random value')]
    return [(PASS, 'SECRET_KEY', f'set, {len(v)} chars')]


def check_database_url(env):
    raw = _get(env, 'DATABASE_URL')
    if not raw:
        return [(FAIL, 'DATABASE_URL', 'not set: the app would fall back to a local SQLite file that is lost on every deploy')]
    out = []
    try:
        parts = urlsplit(normalize_db_url(raw))
        host = (parts.hostname or '').lower()
        query = parse_qs(parts.query)
    except ValueError:
        return [(FAIL, 'DATABASE_URL', 'cannot be parsed as a URL (special characters in the password must be percent-encoded)')]
    if parts.scheme.split('+')[0] != 'postgresql':
        return [(FAIL, 'DATABASE_URL', f"scheme must be postgresql (is {parts.scheme!r})")]
    out.append((PASS, 'DATABASE_URL', 'set, scheme postgresql' + (' (normalised from postgres://)' if raw.startswith('postgres://') else '')))
    if host in LOCAL_HOSTS:
        out.append((WARN, 'DATABASE_URL host', 'localhost: fine for a local rehearsal, not for a hosted deploy'))
    elif (query.get('sslmode') or [''])[0] not in ('require', 'verify-ca', 'verify-full'):
        out.append((FAIL, 'DATABASE_URL sslmode', 'add ?sslmode=require (Neon refuses unencrypted connections)'))
    else:
        out.append((PASS, 'DATABASE_URL sslmode', query['sslmode'][0]))
    if '-pooler' in host:
        out.append((WARN, 'DATABASE_URL pooled endpoint',
                    'host contains -pooler. Run migrations (flask db upgrade, create-admin, backups) against the DIRECT host. '
                    'The app skips the statement_timeout startup option for -pooler hosts (the pooler rejects it), so there is no '
                    'statement timeout unless you run ALTER ROLE ... SET statement_timeout; the direct host is simpler'))
    elif host not in LOCAL_HOSTS:
        out.append((PASS, 'DATABASE_URL endpoint', 'direct host (no -pooler)'))
    return out


def check_gemini(env):
    if _get(env, 'GEMINI_API_KEY'):
        return [(PASS, 'GEMINI_API_KEY', f"set, {len(_get(env, 'GEMINI_API_KEY'))} chars")]
    return [(WARN, 'GEMINI_API_KEY', 'not set: the AI companion falls back to canned text')]


def check_site_url(env):
    v = _get(env, 'SITE_URL')
    if not v:
        return [(WARN, 'SITE_URL', 'not set: canonical, Open Graph and sitemap URLs come from the request (ProxyFix is on in production, but set SITE_URL anyway)')]
    if not v.startswith('https://'):
        return [(FAIL, 'SITE_URL', 'must start with https://')]
    if v.endswith('/'):
        return [(WARN, 'SITE_URL', 'has a trailing slash (the code strips it, but keep the value clean)')]
    return [(PASS, 'SITE_URL', 'https, no trailing slash')]


def check_smtp(env):
    present = [n for n in SMTP_GROUP if _get(env, n)]
    out = []
    if not present:
        out.append((WARN, 'SMTP_*', 'not configured: contact messages are saved but not emailed, and crisis escalation emails are not sent'))
    elif len(present) < len(SMTP_GROUP):
        missing = ', '.join(n for n in SMTP_GROUP if n not in present)
        out.append((FAIL, 'SMTP_*', f'partly set; also set: {missing}'))
    else:
        out.append((PASS, 'SMTP_*', 'host, user, password and from are set'))
    port = _get(env, 'SMTP_PORT')
    if port and not port.isdigit():
        out.append((FAIL, 'SMTP_PORT', 'must be a number (587 STARTTLS or 465 SSL)'))
    if _get(env, 'SMTP_HOST') and not _get(env, 'CONTACT_RECIPIENT'):
        out.append((FAIL, 'CONTACT_RECIPIENT', 'SMTP_HOST is set but CONTACT_RECIPIENT is not: contact emails would be skipped'))
    elif _get(env, 'CONTACT_RECIPIENT'):
        out.append((PASS, 'CONTACT_RECIPIENT', 'set'))
    else:
        out.append((WARN, 'CONTACT_RECIPIENT', 'not set: contact messages stay in the database only'))
    return out


def check_crisis_email(env, pilot=False):
    if _get(env, 'CRISIS_ESCALATION_EMAIL'):
        return [(PASS, 'CRISIS_ESCALATION_EMAIL', 'set')]
    level = FAIL if pilot else WARN
    return [(level, 'CRISIS_ESCALATION_EMAIL',
             'not set: an institution with no counsellor accounts notifies nobody when a student is in crisis, '
             'and unacknowledged alerts are only logged. Required for a pilot with real students')]


def check_invite_codes(env):
    provider, doctor = _get(env, 'PROVIDER_INVITE_CODE'), _get(env, 'DOCTOR_INVITE_CODE')
    out = []
    if not provider:
        out.append((WARN, 'PROVIDER_INVITE_CODE', 'not set: counsellor self-signup is disabled (safe, but you need another way to create providers)'))
    elif len(provider) < 12:
        out.append((FAIL, 'PROVIDER_INVITE_CODE', f'too short ({len(provider)} chars, need 12 or more)'))
    else:
        out.append((PASS, 'PROVIDER_INVITE_CODE', f'set, {len(provider)} chars'))
    if not doctor:
        out.append((WARN, 'DOCTOR_INVITE_CODE', 'not set: doctor self-signup is disabled (doctors cannot join without it)'))
    elif provider and doctor == provider:
        out.append((FAIL, 'DOCTOR_INVITE_CODE', 'equals PROVIDER_INVITE_CODE'))
    elif len(doctor) < 12:
        out.append((FAIL, 'DOCTOR_INVITE_CODE', f'too short ({len(doctor)} chars, need 12 or more)'))
    else:
        out.append((PASS, 'DOCTOR_INVITE_CODE', f'set, {len(doctor)} chars'))
    return out


def check_audio(env):
    if _get(env, 'AUDIO_BASE_URL'):
        return [(PASS, 'AUDIO_BASE_URL', 'set')]
    return [(WARN, 'AUDIO_BASE_URL', 'not set: the mp3 files are not in the Docker image, so binaural audio will 404')]


def check_legal(env):
    out = []
    for name in ('GRIEVANCE_EMAIL', 'DATA_FIDUCIARY_NAME'):
        if _get(env, name):
            out.append((PASS, name, 'set'))
        else:
            out.append((WARN, name, 'not set: the privacy page shows a placeholder'))
    return out


def check_flags(env):
    out = []
    if _get(env, 'FLASK_DEBUG') in ('1', 'true', 'True'):
        out.append((FAIL, 'FLASK_DEBUG', 'debug must be off in production'))
    else:
        out.append((PASS, 'FLASK_DEBUG', 'off'))
    if _get(env, 'JOBS_INPROCESS').lower() in ('0', 'false', 'no', 'off'):
        out.append((WARN, 'JOBS_INPROCESS', 'off: make sure a separate `flask jobs-worker` runs, or emails and crisis escalation never happen'))
    if _get(env, 'ENABLE_PRESCRIPTIONS').lower() in ('0', 'false', 'no', 'off'):
        out.append((WARN, 'ENABLE_PRESCRIPTIONS', 'off: the owner decision is prescriptions ON in production (verified doctors only)'))
    idle = _get(env, 'JOB_IDLE_MAX_SECONDS')
    if idle:
        ok = idle.replace('.', '', 1).isdigit() and float(idle) >= 5
        out.append((PASS if ok else FAIL, 'JOB_IDLE_MAX_SECONDS', f'{idle} s' if ok else 'must be a number of seconds, 5 or more'))
    return out


def run_checks(env, pilot=False):
    results = []
    for fn in (check_flask_env, check_secret_key, check_database_url, check_gemini, check_site_url, check_smtp,
               check_invite_codes, check_audio, check_legal, check_flags):
        results += fn(env)
    results += check_crisis_email(env, pilot)
    return results


def check_db(env, timeout=10):
    """Connect, SELECT 1, read alembic_version. Reports exception class names only (messages can echo the URL)."""
    url = normalize_db_url(_get(env, 'DATABASE_URL'))
    if not url:
        return [(FAIL, 'db connect', 'DATABASE_URL not set')]
    try:
        import psycopg2
    except ImportError:
        return [(WARN, 'db connect', 'psycopg2 is not installed here (pip install -r requirements.txt); skipped')]
    out = []
    try:
        conn = psycopg2.connect(url.replace('postgresql+psycopg2://', 'postgresql://'), connect_timeout=timeout)
    except Exception as exc:
        return [(FAIL, 'db connect', f'{type(exc).__name__}: could not connect within {timeout}s '
                                     '(a sleeping Neon database can need one retry; wrong password or host also lands here)')]
    try:
        cur = conn.cursor()
        cur.execute('SELECT 1')
        out.append((PASS, 'db connect', 'SELECT 1 ok'))
        try:
            cur.execute('SELECT version_num FROM alembic_version')
            row = cur.fetchone()
            out.append((PASS, 'db migrations', f'alembic_version = {row[0]}' if row else 'alembic_version is empty'))
            if not row:
                out[-1] = (WARN, 'db migrations', 'alembic_version is empty: run flask db upgrade')
        except Exception as exc:
            conn.rollback()
            out.append((WARN, 'db migrations', f'no alembic_version table ({type(exc).__name__}): run flask db upgrade'))
    except Exception as exc:
        out.append((FAIL, 'db query', type(exc).__name__))
    finally:
        conn.close()
    return out


def format_results(results):
    return '\n'.join(f'{level:<5} {name}: {msg}' for level, name, msg in results)


def main(argv=None, env=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--pilot', action='store_true', help='real students: stricter rules (CRISIS_ESCALATION_EMAIL is a FAIL)')
    ap.add_argument('--check-db', action='store_true', help='connect to DATABASE_URL (10 s timeout) and read alembic_version')
    args = ap.parse_args(argv)
    env = os.environ if env is None else env
    results = run_checks(env, pilot=args.pilot)
    if args.check_db:
        results += check_db(env)
    print(format_results(results))
    counts = {k: sum(1 for r in results if r[0] == k) for k in (PASS, WARN, FAIL)}
    print(f"\n{counts[PASS]} passed, {counts[WARN]} warnings, {counts[FAIL]} failures")
    return 1 if counts[FAIL] else 0


if __name__ == '__main__':
    sys.exit(main())
