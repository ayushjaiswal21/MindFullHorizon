"""Builder for helplines.csv."""
from .core import src, write_csv


def build_helplines(out, helplines):
    header = ['name', 'number', 'tel_link', 'hours', 'note', 'last_verified_in_code', 'in_app', 'verification_status_in_docs',
              'code_location', 'clinician_verdict', 'comment']
    doc_rows = []
    for ln in src('docs/SAFETY_RESEARCH.md').splitlines():
        cells = [c.strip() for c in ln.strip().strip('|').split('|')]
        if ln.startswith('|') and len(cells) == 3 and cells[0] not in ('Service', '---') and not set(cells[0]) <= set('-'):
            doc_rows.append(cells)
    rows, used = [], set()
    if helplines is None:
        rows.append(['MODULE MISSING', 'utils/helplines.py could not be loaded'] + [''] * 9)
    else:
        for h in helplines.HELPLINES:
            status = ''
            for i, (nm, num, st) in enumerate(doc_rows):
                if h['number'].split(' ')[0] in num or num.split(' ')[0] in h['number']:
                    status, _ = st, used.add(i)
                    break
            rows.append([h['name'], h['number'], h.get('tel', ''), h.get('hours', ''), h.get('note', ''),
                         h.get('last_verified', getattr(helplines, 'LAST_VERIFIED', '')), 'yes', status,
                         'utils/helplines.py', '', ''])
    for i, (nm, num, st) in enumerate(doc_rows):
        if i not in used:
            rows.append([nm, num, '', '', '', '', 'no (listed in docs only)', st, 'docs/SAFETY_RESEARCH.md', '', ''])
    write_csv(out, 'helplines.csv', header, rows)
    return len(rows)
