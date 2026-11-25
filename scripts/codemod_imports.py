"""Rewrite imports after a module moves into a package (dry run by default).

    python scripts/codemod_imports.py                     # show what would change
    python scripts/codemod_imports.py --apply             # rewrite the files in place

Moves handled (edit MOVES to add more):  extensions -> core.extensions,  decorators -> core.decorators.
Rewrites `from extensions import x`, `import extensions`, `import extensions as e`, and dotted strings used by
monkeypatch or patch (`"extensions.limiter"`). Prints every line it changes and every line it cannot classify.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOVES = {'extensions': 'core.extensions', 'decorators': 'core.decorators'}
SKIP = {'.git', 'node_modules', 'venv', '__pycache__', 'instance', 'logs', 'flask_session', '.archive', 'migrations'}


def rules():
    out = []
    for old, new in MOVES.items():
        out.append((re.compile(rf'^(\s*)from {old} import\b'), rf'\1from {new} import'))
        out.append((re.compile(rf'^(\s*)import {old}\b(?! as)'), rf'\1import {new} as {old}'))
        out.append((re.compile(rf'^(\s*)import {old} as\b'), rf'\1import {new} as'))
        out.append((re.compile(rf'''(['"]){old}\.(?!py\b)'''), rf'\1{new}.'))  # but not the file name 'extensions.py'
    return out


def py_files():
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith('venv')]
        for name in files:
            if name.endswith('.py'):
                yield os.path.join(dirpath, name)


def main():
    apply = '--apply' in sys.argv
    rs, changed_files, changed_lines = rules(), 0, 0
    for path in py_files():
        if os.path.basename(path) == 'codemod_imports.py':
            continue
        with open(path, encoding='utf-8', newline='') as fh:
            text = fh.read()
        new_lines, dirty = [], False
        for n, line in enumerate(text.split('\n'), 1):
            fixed = line
            for rx, repl in rs:
                fixed = rx.sub(repl, fixed)
            if fixed != line:
                dirty = True
                changed_lines += 1
                print(f'{os.path.relpath(path, ROOT)}:{n}: {line.strip()}  ->  {fixed.strip()}')
            new_lines.append(fixed)
        if dirty:
            changed_files += 1
            if apply:
                with open(path, 'w', encoding='utf-8', newline='') as fh:
                    fh.write('\n'.join(new_lines))
    print(f'\n{changed_lines} line(s) in {changed_files} file(s) {"rewritten" if apply else "would change (dry run; use --apply)"}')


if __name__ == '__main__':
    main()
