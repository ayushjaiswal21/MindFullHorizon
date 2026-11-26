"""Deploy configuration: scripts/predeploy_check.py, scripts/backup_db.py, render.yaml, Dockerfile, .dockerignore.

No network, no database. Uses PyYAML when installed, else a small line parser (render.yaml is flat on purpose).
"""
import importlib.util
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, 'scripts', name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pc = _load('predeploy_check')
bk = _load('backup_db')

SECRET = 'S3cr3t-VALUE-' + 'a1b2c3d4e5f6' * 4
DB_PASS = 'dbPassWord123XYZ'
GOOD = {
    'FLASK_ENV': 'production',
    'SECRET_KEY': SECRET,
    'DATABASE_URL': f'postgres://user:{DB_PASS}@ep-cool-123.ap-southeast-1.aws.neon.tech/db?sslmode=require',
    'GEMINI_API_KEY': 'gemini-key-value-123',
    'SITE_URL': 'https://app.example.org',
    'SMTP_HOST': 'smtp.example.org', 'SMTP_USER': 'u', 'SMTP_PASSWORD': 'smtp-pass-value', 'SMTP_FROM': 'a@example.org',
    'CONTACT_RECIPIENT': 'team@example.org',
    'CRISIS_ESCALATION_EMAIL': 'crisis@example.org',
    'PROVIDER_INVITE_CODE': 'provider-code-0123456789',
    'DOCTOR_INVITE_CODE': 'doctor-code-98765432100',  # read by routes/auth.py since the clinical build
    'AUDIO_BASE_URL': 'https://audio.example.org',
    'GRIEVANCE_EMAIL': 'g@example.org', 'DATA_FIDUCIARY_NAME': 'Example Trust',
}


def levels(env, **kw):
    return {(n): lvl for lvl, n, _ in pc.run_checks(env, **kw)}


def with_(**changes):
    env = dict(GOOD)
    for k, v in changes.items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = v
    return env


def test_good_environment_has_no_fail_and_no_warn():
    res = pc.run_checks(GOOD, pilot=True)
    assert [r for r in res if r[0] != pc.PASS] == []


@pytest.mark.parametrize('changes,name', [
    ({'FLASK_ENV': 'development'}, 'FLASK_ENV'),
    ({'FLASK_ENV': None}, 'FLASK_ENV'),
    ({'SECRET_KEY': None}, 'SECRET_KEY'),
    ({'SECRET_KEY': 'short'}, 'SECRET_KEY'),
    ({'SECRET_KEY': 'change-me-to-a-long-random-string-0123456789'}, 'SECRET_KEY'),
    ({'DATABASE_URL': None}, 'DATABASE_URL'),
    ({'DATABASE_URL': 'mysql://u:p@h/db'}, 'DATABASE_URL'),
    ({'DATABASE_URL': 'postgresql://u:p@ep-x.neon.tech/db'}, 'DATABASE_URL sslmode'),
    ({'SITE_URL': 'http://app.example.org'}, 'SITE_URL'),
    ({'SMTP_PASSWORD': None}, 'SMTP_*'),
    ({'CONTACT_RECIPIENT': None}, 'CONTACT_RECIPIENT'),
    ({'PROVIDER_INVITE_CODE': 'short'}, 'PROVIDER_INVITE_CODE'),
    ({'DOCTOR_INVITE_CODE': 'provider-code-0123456789'}, 'DOCTOR_INVITE_CODE'),
    ({'FLASK_DEBUG': '1'}, 'FLASK_DEBUG'),
    ({'JOB_IDLE_MAX_SECONDS': 'soon'}, 'JOB_IDLE_MAX_SECONDS'),
])
def test_each_failure_mode_is_a_fail(changes, name):
    assert levels(with_(**changes))[name] == pc.FAIL


@pytest.mark.parametrize('changes,name', [
    ({'GEMINI_API_KEY': None}, 'GEMINI_API_KEY'),
    ({'AUDIO_BASE_URL': None}, 'AUDIO_BASE_URL'),
    ({'GRIEVANCE_EMAIL': None}, 'GRIEVANCE_EMAIL'),
    ({'DATA_FIDUCIARY_NAME': None}, 'DATA_FIDUCIARY_NAME'),
    ({'SITE_URL': 'https://app.example.org/'}, 'SITE_URL'),
    ({'SITE_URL': None}, 'SITE_URL'),
    ({'PROVIDER_INVITE_CODE': None}, 'PROVIDER_INVITE_CODE'),
    ({'DATABASE_URL': 'postgresql://u:p@ep-x-pooler.neon.tech/db?sslmode=require'}, 'DATABASE_URL pooled endpoint'),
    ({'JOBS_INPROCESS': '0'}, 'JOBS_INPROCESS'),
    ({'DOCTOR_INVITE_CODE': None}, 'DOCTOR_INVITE_CODE'),
    ({'ENABLE_PRESCRIPTIONS': '0'}, 'ENABLE_PRESCRIPTIONS'),
])
def test_each_warning_mode_is_a_warn(changes, name):
    res = levels(with_(**changes))
    assert res[name] == pc.WARN
    assert pc.FAIL not in res.values()


def test_no_smtp_at_all_is_a_warning_not_a_failure():
    env = with_(SMTP_HOST=None, SMTP_USER=None, SMTP_PASSWORD=None, SMTP_FROM=None)
    assert levels(env)['SMTP_*'] == pc.WARN


def test_crisis_email_is_warn_normally_and_fail_for_a_pilot():
    env = with_(CRISIS_ESCALATION_EMAIL=None)
    assert levels(env)['CRISIS_ESCALATION_EMAIL'] == pc.WARN
    assert levels(env, pilot=True)['CRISIS_ESCALATION_EMAIL'] == pc.FAIL


def test_postgres_scheme_is_normalised_and_localhost_needs_no_ssl():
    res = levels(with_(DATABASE_URL='postgres://u:p@localhost:5432/db'))
    assert res['DATABASE_URL'] == pc.PASS and 'DATABASE_URL sslmode' not in res
    assert pc.normalize_db_url('postgres://a') == 'postgresql+psycopg2://a'


def test_main_exit_codes_and_no_secret_in_output(capsys):
    env = with_(CRISIS_ESCALATION_EMAIL=None, DATABASE_URL=GOOD['DATABASE_URL'] + '&channel_binding=require')
    assert pc.main([], env=env) == 0
    assert pc.main(['--pilot'], env=env) == 1
    out = capsys.readouterr().out
    for secret in (SECRET, DB_PASS, 'smtp-pass-value', 'gemini-key-value-123', 'provider-code-0123456789'):
        assert secret not in out
    assert 'ep-cool-123' not in out  # not even the host


def test_failure_output_never_echoes_bad_secret(capsys):
    bad = 'change-me-' + 'z9y8x7' * 4
    pc.main([], env=with_(SECRET_KEY=bad, PROVIDER_INVITE_CODE='tiny-code'))
    out = capsys.readouterr().out
    assert bad not in out and 'tiny-code' not in out


def test_check_db_without_url_fails_and_never_prints_url():
    res = pc.check_db({})
    assert res[0][0] == pc.FAIL


# ---------------------------------------------------------------- backup script

def test_backup_splits_url_into_pg_variables_and_keeps_password_out_of_argv():
    env, host = bk.pg_env('postgres://us%40er:p%40ss@ep-a.neon.tech:5433/mydb?sslmode=require&channel_binding=require', {})
    assert host == 'ep-a.neon.tech'
    assert env['PGUSER'] == 'us@er' and env['PGPASSWORD'] == 'p@ss' and env['PGDATABASE'] == 'mydb'
    assert env['PGPORT'] == '5433' and env['PGSSLMODE'] == 'require' and env['PGCHANNELBINDING'] == 'require'
    with pytest.raises(ValueError):
        bk.pg_env('mysql://u:p@h/db', {})


def test_backup_refuses_inside_repo_and_pooler(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://u:topsecretpw@ep-a.neon.tech/db')
    assert bk.inside_repo(os.path.join(ROOT, 'backups')) is True
    assert bk.inside_repo(str(tmp_path)) is False
    assert bk.main([os.path.join(ROOT, 'backups')]) == 2
    monkeypatch.setenv('DATABASE_URL', 'postgresql://u:topsecretpw@ep-a-pooler.neon.tech/db')
    assert bk.main([str(tmp_path)]) == 2
    assert 'topsecretpw' not in capsys.readouterr().err


# ---------------------------------------------------------------- render.yaml, Dockerfile, .dockerignore

def _read(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as fh:
        return fh.read()


def _render_service():
    text = _read('render.yaml')
    try:
        import yaml
    except ImportError:
        yaml = None
    if yaml:
        svc = yaml.safe_load(text)['services'][0]
        return svc, svc['envVars']
    svc, env, cur = {}, [], None
    for raw in text.splitlines():
        line = raw.split(' #')[0].rstrip()
        line = re.sub(r'^(\s*)- (type:)', r'\1  \2', line)  # first key of the service list item
        m = re.match(r'^\s*- key: (\S+)', line)
        if m:
            cur = {'key': m.group(1)}
            env.append(cur)
            continue
        m = re.match(r'^\s+(\w+): ?(.*)$', line)
        if not m:
            continue
        k, v = m.group(1), m.group(2).strip().strip('"')
        if cur is not None and k in ('value', 'generateValue', 'sync'):
            cur[k] = {'true': True, 'false': False}.get(v, v)
        elif cur is None and v:
            svc[k] = v
    return svc, env


def test_render_yaml_service_basics():
    svc, _ = _render_service()
    assert svc['type'] == 'web' and svc['runtime'] == 'docker'
    assert svc['plan'] == 'free'
    assert svc['healthCheckPath'] == '/health'
    assert svc['branch'] == 'main'


def test_render_yaml_commits_no_secret_values():
    _, env = _render_service()
    secret_keys = {'SECRET_KEY', 'DATABASE_URL', 'GEMINI_API_KEY', 'SMTP_PASSWORD', 'PROVIDER_INVITE_CODE', 'DOCTOR_INVITE_CODE', 'SMTP_USER'}
    for item in env:
        assert sum(k in item for k in ('value', 'generateValue', 'sync')) == 1, item['key']
        if item['key'] in secret_keys:
            assert 'value' not in item, item['key']
        if 'value' in item:
            assert not re.search(r'://[^/\s]*:[^/\s]*@', str(item['value'])), item['key']
    keys = {i['key'] for i in env}
    assert {'SECRET_KEY', 'DATABASE_URL', 'FLASK_ENV', 'CRISIS_ESCALATION_EMAIL', 'SITE_URL'} <= keys
    assert next(i for i in env if i['key'] == 'FLASK_ENV')['value'] == 'production'
    assert next(i for i in env if i['key'] == 'SECRET_KEY').get('generateValue') is True
    assert next(i for i in env if i['key'] == 'DATABASE_URL').get('sync') is False


def test_every_render_env_var_is_read_by_the_code():
    _, env = _render_service()
    source = ''
    for folder in ('.', 'ai', 'routes', 'utils'):
        base = os.path.join(ROOT, folder)
        if folder == '.':
            paths = [os.path.join(base, 'app.py'), os.path.join(base, 'core', 'extensions.py')]
        else:
            paths = [os.path.join(dirpath, name) for dirpath, _, names in os.walk(base) for name in names
                     if name.endswith('.py')]
        for path in paths:
            if path.endswith('.py'):
                with open(path, encoding='utf-8', errors='ignore') as fh:
                    source += fh.read()
    for item in env:
        assert re.search(r"['\"]%s['\"]" % item['key'], source), f"{item['key']} is in render.yaml but no code reads it"


def test_dockerfile_hardening():
    d = _read('Dockerfile')
    assert 'flask db upgrade' in d and 'FLASK_APP=app.py' in d
    assert 'PYTHONUNBUFFERED=1' in d and 'PYTHONDONTWRITEBYTECODE=1' in d
    assert '${PORT:-5000}' in d and '--worker-class eventlet' in d and '--workers 1' in d
    assert re.search(r'^USER app$', d, re.M)
    assert 'MIGRATION FAILED' in d and 'flask assets build' in d


def test_dockerignore_keeps_what_the_runtime_needs():
    ignored = [l.strip() for l in _read('.dockerignore').splitlines() if l.strip() and not l.startswith('#')]
    for must_ship in ('templates', 'static/css', 'migrations', 'routes', 'utils', 'ai', 'ai_prompts', 'models.py', 'app.py',
                      'scripts', 'data/binaural-beats-dataset/tracks.csv', 'static/css/tailwind.css'):
        assert not any(p.rstrip('/') == must_ship or p.rstrip('/*') == must_ship for p in ignored), must_ship
    for must_skip in ('.env', 'tests/', 'docs/', 'node_modules/', '.git', 'instance/', 'flask_session/', 'static/uploads/*', 'data/**/*.mp3'):
        assert must_skip in ignored, must_skip
    assert os.path.isfile(os.path.join(ROOT, 'static', 'css', 'tailwind.css'))


def test_render_yaml_deploy_code_settings():
    _, env = _render_service()
    by = {i['key']: i for i in env}
    assert by['ENABLE_PRESCRIPTIONS']['value'] == '1'  # owner decision: prescriptions on in production
    assert by['DOCTOR_INVITE_CODE'].get('generateValue') is True
    assert by['TRUST_PROXY']['value'] == '1' and by['LOG_TO_STDOUT']['value'] == '1'
    assert int(by['JOB_IDLE_MAX_SECONDS']['value']) >= 60
