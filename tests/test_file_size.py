"""The 300-line rule (scripts/check_file_sizes.py). Oversize files are grandfathered in scripts/oversize_baseline.json."""
import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location('check_file_sizes', os.path.join(ROOT, 'scripts', 'check_file_sizes.py'))
cfs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cfs)


def test_no_source_file_over_300_lines_and_baseline_only_shrinks():
    sizes, baseline = cfs.scan(), cfs.load_baseline()
    print('\n' + cfs.table(sizes, baseline))
    found = cfs.problems(sizes, baseline)
    assert not found, '\n' + '\n'.join(found)


def test_checker_logic():
    sizes = {'a.py': 301, 'b.py': 250, 'c.py': 400, 'd.py': 310}
    base = {'b.py': 320, 'c.py': 390, 'd.py': 310, 'gone.py': 305}
    msgs = ' | '.join(cfs.problems(sizes, base))
    assert 'a.py: 301 lines, limit 300' in msgs          # new oversize file
    assert 'c.py: grew from 390 to 400' in msgs          # grandfathered file grew
    assert 'b.py: now 250 lines' in msgs                 # shrank under the limit, entry must go
    assert 'gone.py' in msgs and 'no longer exists' in msgs
    assert 'd.py' not in msgs                            # unchanged grandfathered file is fine


def test_scan_skips_generated_and_vendor_paths():
    sizes = cfs.scan()
    assert not any(p.startswith(('migrations/', 'static/gen/', 'docs/', 'data/', 'instance/')) for p in sizes)
    assert 'static/css/tailwind.css' not in sizes
    assert not any('node_modules' in p for p in sizes)
    assert 'app.py' in sizes and 'tests/test_file_size.py' in sizes
