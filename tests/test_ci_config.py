"""CI/CD configuration: .github/workflows, .github/dependabot.yml, render.yaml deploy trigger. No network.

Needs PyYAML (in requirements/dev.txt); the module is skipped where it is not installed.
"""
import glob
import os
import re

import pytest

yaml = pytest.importorskip('yaml')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOWS = sorted(glob.glob(os.path.join(ROOT, '.github', 'workflows', '*.yml')))
# A repo path inside a shell command: starts at a known top-level folder or file, not preceded by / or $ (so /app/static is ignored).
PATH_RE = re.compile(r'(?<![\w/.$-])((?:scripts|tools|static|tests|requirements|docs|migrations)/[\w./*-]+|requirements\.txt|app\.py)')


def _load(path):
    with open(path, encoding='utf-8') as fh:
        return yaml.safe_load(fh)


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _wf(name):
    return _load(os.path.join(ROOT, '.github', 'workflows', name))


def _triggers(wf):
    return wf.get('on', wf.get(True))  # PyYAML reads the bare key `on` as boolean True


def _steps(wf):
    for job in wf['jobs'].values():
        yield from job.get('steps', [])


def test_workflows_exist_and_parse():
    names = {os.path.basename(p) for p in WORKFLOWS}
    assert {'ci.yml', 'post-deploy.yml'} <= names
    for p in WORKFLOWS:
        wf = _load(p)
        assert wf['jobs'], p
        assert wf['permissions'] == {'contents': 'read'}, f'{p}: least-privilege permissions'
        assert len(_read(p).splitlines()) <= 300, f'{p} is over the 300-line rule'


def test_ci_triggers_and_concurrency():
    wf = _wf('ci.yml')
    trig = _triggers(wf)
    assert trig['push']['branches'] == ['main'] and 'pull_request' in trig
    assert wf['concurrency']['cancel-in-progress'] is True


def test_ci_jobs_and_ci_ok_gate():
    wf = _wf('ci.yml')
    assert {'test', 'frontend', 'docker', 'e2e', 'audit', 'ci-ok'} <= set(wf['jobs'])
    gate = wf['jobs']['ci-ok']
    assert set(gate['needs']) == {'test', 'frontend', 'docker'}
    assert 'always()' in str(gate['if']), 'without always() a failed need would SKIP ci-ok, and skipped passes branch protection'
    script = ' '.join(s.get('run', '') for s in gate['steps'])
    for job in ('test', 'frontend', 'docker'):
        assert f'needs.{job}.result' in script
    # advisory jobs must not gate
    assert wf['jobs']['e2e']['continue-on-error'] is True and wf['jobs']['audit']['continue-on-error'] is True
    assert not wf['jobs']['test'].get('continue-on-error')


def test_ci_runs_the_agreed_commands():
    text = _read(os.path.join(ROOT, '.github', 'workflows', 'ci.yml'))
    for needle in ('scripts/scan_imports.py', 'compileall -q', 'pytest tests -q -p no:cacheprovider -W ignore', 'npm run build:css',
                   'git diff --exit-code', 'static/css/tailwind.css', 'node --check', 'docker build', 'FLASK_ENV=production',
                   'DATABASE_URL=sqlite:////tmp/ci.db', '/health', '/ready', 'pip-audit -r requirements.txt', 'npm audit --omit=dev',
                   'EDGE: /usr/bin/google-chrome', 'scripts/local_demo.py --port 5000'):
        assert needle in text, needle


def test_every_repo_path_in_run_commands_exists():
    checked = 0
    for p in WORKFLOWS:
        wf = _load(p)
        for job in wf['jobs'].values():
            for step in job.get('steps', []):
                targets = PATH_RE.findall(step.get('run', ''))
                if step.get('working-directory'):
                    targets.append(step['working-directory'])
                for t in targets:
                    t = t.rstrip('.,;')
                    assert glob.glob(os.path.join(ROOT, t)), f'{os.path.basename(p)}: {t!r} does not exist'
                    checked += 1
    assert checked >= 10


def test_e2e_specs_and_lockfiles_exist():
    text = _read(os.path.join(ROOT, '.github', 'workflows', 'ci.yml'))
    specs = re.search(r'for spec in ([\w ]+); do', text).group(1).split()
    assert len(specs) >= 4
    for s in specs:
        assert os.path.isfile(os.path.join(ROOT, 'tools', 'e2e', 'specs', s + '.mjs')), s
    for lock in ('tools/frontend/package-lock.json', 'tools/e2e/package-lock.json'):
        assert os.path.isfile(os.path.join(ROOT, lock)), f'npm ci needs {lock}'


def test_no_hard_coded_secrets_in_workflows():
    for p in WORKFLOWS + [os.path.join(ROOT, '.github', 'dependabot.yml')]:
        text = _read(p)
        assert not re.search(r'\$\{\{\s*secrets\.', text), f'{p}: no repository secrets are needed; keep it that way unless docs/CICD.md says otherwise'
        assert not re.search(r'(AIza[0-9A-Za-z_-]{20,}|ghp_\w{20,}|github_pat_\w+|sk-[A-Za-z0-9]{20,}|postgres(ql)?://\S+:\S+@)', text), p
        assert not re.search(r'(?i)^\s*(SECRET_KEY|GEMINI_API_KEY|SMTP_PASSWORD)\s*:\s*\S+', text, re.M), p


def test_actions_are_pinned_to_versions():
    uses = [s['uses'] for p in WORKFLOWS for s in _steps(_load(p)) if 'uses' in s]
    assert uses
    for u in uses:
        ref = u.split('@', 1)[1] if '@' in u else ''
        assert re.fullmatch(r'v\d+(\.\d+){0,2}|[0-9a-f]{40}', ref), f'{u}: pin to a version tag or commit sha, never a branch'


def test_post_deploy_workflow():
    wf = _wf('post-deploy.yml')
    trig = _triggers(wf)
    assert trig['workflow_run']['workflows'] == ['CI'] and trig['workflow_run']['types'] == ['completed']
    assert trig['workflow_run']['branches'] == ['main'] and 'workflow_dispatch' in trig
    text = _read(os.path.join(ROOT, '.github', 'workflows', 'post-deploy.yml'))
    assert 'vars.SITE_URL' in text and 'conclusion == \'success\'' in text
    for path in ('/health', '/ready', '/robots.txt', '/sitemap.xml'):
        assert path in text


def test_render_yaml_deploys_only_after_checks_pass():
    svc = _load(os.path.join(ROOT, 'render.yaml'))['services'][0]
    # Allowed values per https://render.com/docs/blueprint-spec (read 2026-11-24): commit, checksPass, off.
    assert svc['autoDeployTrigger'] == 'checksPass'
    assert svc['branch'] == 'main'


def test_dependabot_config():
    cfg = _load(os.path.join(ROOT, '.github', 'dependabot.yml'))
    assert cfg['version'] == 2
    valid = {'pip', 'npm', 'github-actions', 'docker'}
    seen = {u['package-ecosystem'] for u in cfg['updates']}
    assert seen == valid
    for u in cfg['updates']:
        assert u['schedule']['interval'] == 'weekly'
        assert u['open-pull-requests-limit'] >= 1 and u['labels']
        assert u['groups'], 'minor and patch updates are grouped'
        for d in u.get('directories') or [u['directory']]:
            assert os.path.isdir(os.path.join(ROOT, d.lstrip('/'))), d
    pip = next(u for u in cfg['updates'] if u['package-ecosystem'] == 'pip')
    assert set(pip['directories']) == {'/', '/requirements'}
    npm = next(u for u in cfg['updates'] if u['package-ecosystem'] == 'npm')
    assert set(npm['directories']) == {'/tools/frontend', '/tools/e2e'}


def test_pull_request_template_has_the_checklist():
    text = _read(os.path.join(ROOT, '.github', 'pull_request_template.md')).lower()
    for word in ('tests', 'e2e', 'migration', 'docs', '300 lines', 'secrets', 'rollback'):
        assert word in text, word
