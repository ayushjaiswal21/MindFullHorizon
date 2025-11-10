#!/usr/bin/env python
import os
import re
import io

templates_dir = 'templates'
out_dir = os.path.join('static', 'js', 'inline_extracted')
if not os.path.exists(out_dir):
    os.makedirs(out_dir)

script_re = re.compile(r'(<script(?P<attrs>[^>]*)>)(?P<body>.*?)(</script>)', re.S|re.I)

for root, _, files in os.walk(templates_dir):
    for filename in files:
        if not filename.endswith('.html'):
            continue
        
        tpl_path = os.path.join(root, filename)
        
        with io.open(tpl_path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        state = {'counter': 0, 'modified': False}
        tpl_stem = os.path.splitext(filename)[0]

        def repl(m):
            attrs = m.group('attrs') or ''
            body = m.group('body') or ''
            if 'src=' in attrs.lower():
                # keep as is but inject nonce if not present
                if 'nonce=' not in attrs:
                    state['modified'] = True
                    return u"<script nonce=\"{{ g.csp_nonce }}\"{}>{}</script>".format(attrs, body)
                return m.group(0)
            # inline script - extract
            state['counter'] += 1
            fname = "{}_inline_{}.js".format(tpl_stem, state['counter'])
            out_path = os.path.join(out_dir, fname)
            with io.open(out_path, 'w', encoding='utf-8') as f:
                f.write(body)
            state['modified'] = True
            return u'<script nonce="{{{{ g.csp_nonce }}}}" src="{{{{ url_for(\'static\', filename=\'js/inline_extracted/{}\') }}}}"></script>'.format(fname)

        new_text = script_re.sub(repl, text)
        if state['modified']:
            with io.open(tpl_path, 'w', encoding='utf-8') as f:
                f.write(new_text)
            print("Updated {} (extracted {} inline scripts)".format(tpl_path, state['counter']))

print("Done extracting inline scripts.")