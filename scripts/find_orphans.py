"""List templates and static files that nothing references (read-only; deletes nothing).

    python scripts/find_orphans.py            # print orphan templates and static files
    python scripts/find_orphans.py --json     # machine readable

A template counts as used when Python calls render_template/render_error_page with its name, or another template
extends, includes or imports it, or a Python file names it in a string. A static file counts as used when any
template, Python, JS or CSS file mentions its relative path or its file name. Dynamic names (f-strings) can hide a
reference, so treat the output as a candidate list and check each file before deleting.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {'.git', 'node_modules', 'venv', '__pycache__', 'instance', 'logs', 'flask_session', '.archive', 'gen',
             '.webassets-cache', 'migrations', 'data', 'docs', 'tools'}


def walk(base, exts=None):
    for dirpath, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('venv')]
        for name in files:
            if exts is None or name.endswith(exts):
                yield os.path.join(dirpath, name)


def read(path):
    try:
        with open(path, encoding='utf-8', errors='ignore') as fh:
            return fh.read()
    except OSError:
        return ''


def rel(path, base):
    return os.path.relpath(path, base).replace(os.sep, '/')


def main():
    as_json = '--json' in sys.argv
    tpl_dir = os.path.join(ROOT, 'templates')
    templates = {rel(p, tpl_dir): p for p in walk(tpl_dir, ('.html', '.txt', '.xml'))}
    code = {p: read(p) for p in walk(ROOT, ('.py',))}
    tpl_text = {p: read(p) for p in templates.values()}
    js_css = {p: read(p) for p in walk(os.path.join(ROOT, 'static'), ('.js', '.css', '.json', '.webmanifest'))}

    used_tpl = set()
    ref_re = re.compile(r'''['"]([\w./-]+\.(?:html|txt|xml))['"]''')
    for text in list(code.values()) + list(tpl_text.values()):
        used_tpl.update(ref_re.findall(text))
    orphan_tpl = sorted(t for t in templates if t not in used_tpl)

    corpus = '\n'.join([*code.values(), *tpl_text.values(), *js_css.values()])
    static_dir = os.path.join(ROOT, 'static')
    orphan_static = []
    for p in walk(static_dir):
        r = rel(p, static_dir)
        if r.startswith(('gen/', '.webassets-cache/')) or os.path.basename(p) in {'.gitkeep'}:
            continue
        if r not in corpus and os.path.basename(p) not in corpus:
            orphan_static.append(r)
    orphan_static.sort()

    if as_json:
        print(json.dumps({'templates': orphan_tpl, 'static': orphan_static}, indent=2))
        return
    print(f'Templates with no reference ({len(orphan_tpl)}):')
    for t in orphan_tpl:
        print('  templates/' + t)
    print(f'\nStatic files with no reference ({len(orphan_static)}):')
    for s in orphan_static:
        print('  static/' + s)


if __name__ == '__main__':
    main()
