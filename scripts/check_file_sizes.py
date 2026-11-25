"""The 300-line rule: no Python, JS, CSS or HTML source file may be longer than 300 lines.

    python scripts/check_file_sizes.py                  # print the table, exit 1 on a problem
    python scripts/check_file_sizes.py --write-baseline # regenerate scripts/oversize_baseline.json from today's sizes

Files that were already over the limit are grandfathered in scripts/oversize_baseline.json ({path: line count}).
Problems: (a) a file not in the baseline is over 300 lines, (b) a baseline file grew, (c) a baseline file is now at or
under 300 lines but is still listed (delete its entry; delete the whole file when the list is empty).
Stdlib only. Walks the folder (not `git ls-files`) so a new, uncommitted file is checked too.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIMIT = 300
EXTENSIONS = ('.py', '.js', '.css', '.html')
BASELINE = os.path.join(ROOT, 'scripts', 'oversize_baseline.json')
# Directory names skipped at any depth (dot folders and venv* are skipped too).
SKIP_DIRS = {'migrations', 'node_modules', 'docs', 'data', 'instance', 'logs', '__pycache__', 'build', 'dist',
             'graphify-out', 'flask_session'}
SKIP_PATHS = {'static/gen', 'static/uploads'}  # generated bundles and user files
SKIP_FILES = {'static/css/tailwind.css'}  # built by tools/frontend, committed, minified


def _skip_dir(rel, name):
    return name in SKIP_DIRS or name.startswith(('.', 'venv')) or rel in SKIP_PATHS


def scan(root=ROOT):
    """{posix relative path: line count} for every checked source file."""
    sizes = {}
    for folder, dirs, files in os.walk(root):
        rel_folder = os.path.relpath(folder, root).replace(os.sep, '/')
        rel_folder = '' if rel_folder == '.' else rel_folder
        dirs[:] = [d for d in dirs if not _skip_dir((rel_folder + '/' + d).lstrip('/'), d)]
        for name in files:
            rel = (rel_folder + '/' + name).lstrip('/')
            if not name.endswith(EXTENSIONS) or '.min.' in name or rel in SKIP_FILES:
                continue
            with open(os.path.join(folder, name), 'rb') as fh:
                sizes[rel] = len(fh.read().decode('utf-8', 'replace').splitlines())
    return sizes


def load_baseline(path=BASELINE):
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def problems(sizes, baseline):
    out = []
    for path, n in sorted(sizes.items()):
        if path not in baseline and n > LIMIT:
            out.append(f'{path}: {n} lines, limit {LIMIT}. Split it into smaller modules (do not add it to the baseline).')
        elif path in baseline and n > baseline[path]:
            out.append(f'{path}: grew from {baseline[path]} to {n} lines. A grandfathered file may not grow; put new code in a new module.')
    for path, n in sorted(baseline.items()):
        if path not in sizes:
            out.append(f'{path}: listed in scripts/oversize_baseline.json but the file no longer exists. Delete the entry.')
        elif sizes[path] <= LIMIT:
            out.append(f'{path}: now {sizes[path]} lines (limit {LIMIT}) but still listed. Delete its entry from scripts/oversize_baseline.json.')
    return out


def table(sizes, baseline):
    rows = sorted(((n, p) for p, n in sizes.items() if n > LIMIT or p in baseline), reverse=True)
    lines = [f'{"lines":>6} {"baseline":>8}  file']
    for n, p in rows:
        lines.append(f'{n:>6} {baseline.get(p, "-"):>8}  {p}')
    lines.append(f'{len(rows)} file(s) over {LIMIT} lines or grandfathered; {len(sizes)} source files checked.')
    return '\n'.join(lines)


def main(argv):
    sizes = scan()
    if '--write-baseline' in argv:
        data = {p: n for p, n in sorted(sizes.items()) if n > LIMIT}
        with open(BASELINE, 'w', encoding='utf-8', newline='\n') as fh:
            json.dump(data, fh, indent=1)
            fh.write('\n')
        print(f'wrote {len(data)} entries to {os.path.relpath(BASELINE, ROOT)}')
        return 0
    baseline = load_baseline()
    print(table(sizes, baseline))
    found = problems(sizes, baseline)
    for p in found:
        print('PROBLEM', p)
    return 1 if found else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
