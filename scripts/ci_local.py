"""Run the CI checks locally (same commands as .github/workflows/ci.yml, minus Docker and the browser).

    python scripts/ci_local.py            # everything
    python scripts/ci_local.py --fast     # skip pytest (quick pre-commit pass)

Prints PASS, FAIL or SKIP per step and the total time; exits 1 if any step failed. Works on Windows and Linux.
Docker and e2e are not run here: see docs/CICD.md for those.
"""
import glob
import hashlib
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
CSS = os.path.join(ROOT, 'static', 'css', 'tailwind.css')


def run(cmd, tail=15):
    """Run a command in the repo root; return (ok, last lines of output)."""
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
    out = (p.stdout + p.stderr).strip().splitlines()
    return p.returncode == 0, '\n'.join(out[-tail:])


def step_pytest():
    return run([PY, '-m', 'pytest', 'tests', '-q', '-p', 'no:cacheprovider', '-W', 'ignore'], tail=25)


def step_imports():
    return run([PY, 'scripts/scan_imports.py'], tail=3)


def step_compile():
    files = [os.path.basename(f) for f in glob.glob(os.path.join(ROOT, '*.py'))]
    dirs = [d for d in ('ai', 'routes', 'services', 'utils', 'scripts', 'tests', 'migrations') if os.path.isdir(os.path.join(ROOT, d))]
    return run([PY, '-m', 'compileall', '-q', *files, *dirs])


def step_file_sizes():
    return run([PY, 'scripts/check_file_sizes.py'], tail=40)


def step_yaml():
    try:
        import yaml
    except ImportError:
        return None, 'PyYAML is not installed (pip install -r requirements/dev.txt)'
    files = sorted(glob.glob(os.path.join(ROOT, '.github', '**', '*.yml'), recursive=True)) + [os.path.join(ROOT, 'render.yaml')]
    bad = []
    for f in files:
        try:
            with open(f, encoding='utf-8') as fh:
                yaml.safe_load(fh)
        except Exception as exc:  # noqa: BLE001 - report any parse problem
            bad.append(f'{os.path.relpath(f, ROOT)}: {exc}')
    return not bad, '\n'.join(bad) or f'{len(files)} YAML files parse'


def _digest():
    with open(CSS, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def step_css():
    node = shutil.which('node')
    if not node or not os.path.isdir(os.path.join(ROOT, 'tools', 'frontend', 'node_modules')):
        return None, 'node or tools/frontend/node_modules missing (cd tools/frontend && npm ci)'
    before = _digest()
    ok, out = run([node, os.path.join('tools', 'frontend', 'build_css.mjs')], tail=5)
    if not ok:
        return False, out
    if _digest() != before:
        return False, 'static/css/tailwind.css was out of date and has been rebuilt: review and commit it'
    return True, 'static/css/tailwind.css matches the templates'


def step_js():
    node = shutil.which('node')
    if not node:
        return None, 'node not found'
    files = sorted(glob.glob(os.path.join(ROOT, 'static', 'js', '**', '*.js'), recursive=True))
    for f in files:
        ok, out = run([node, '--check', f])
        if not ok:
            return False, f'{os.path.relpath(f, ROOT)}\n{out}'
    return True, f'{len(files)} JS files parse'


STEPS = [('pytest', step_pytest), ('scan_imports', step_imports), ('compileall', step_compile),
         ('file sizes (300-line rule)', step_file_sizes), ('YAML validity', step_yaml),
         ('css build matches committed', step_css), ('node --check static/js', step_js)]


def main(argv):
    t0, failed = time.time(), 0
    for name, fn in STEPS:
        if name == 'pytest' and '--fast' in argv:
            print(f'SKIP  {name} (--fast)')
            continue
        t = time.time()
        ok, out = fn()
        label = 'SKIP' if ok is None else 'PASS' if ok else 'FAIL'
        print(f'{label:5} {name} ({time.time() - t:.1f}s)')
        if ok is False:
            failed += 1
            print('      ' + out.replace('\n', '\n      '))
        elif ok is None:
            print('      ' + out)
    print(f'\n{"FAIL" if failed else "PASS"}: {failed} failed step(s), total {time.time() - t0:.1f}s')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
