"""AST extraction of detector test sentences (and their expected outcome) from tests/*.py."""
import ast
import os

from .core import note, path_of, src

DETECTORS = {'classify', 'text_is_crisis', 'heuristic_severity'}


def _eval_strs(node, env):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        out = []
        for e in node.elts:
            out += _eval_strs(e, env)
        return out
    if isinstance(node, ast.Name):
        return list(env.get(node.id, []))
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _eval_strs(node.left, env) + _eval_strs(node.right, env)
    return []


def _const_set(node):
    if isinstance(node, ast.Constant):
        return [node.value]
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return [e.value for e in node.elts if isinstance(e, ast.Constant)]
    return []


def extract_test_cases():
    """{text: {'expects': set, 'sources': set}} for every sentence a test feeds to the detector with a stated outcome."""
    cases = {}
    tests_dir = path_of('tests')
    if not os.path.isdir(tests_dir):
        note('tests/ folder not found: crisis_test_cases.csv is empty')
        return cases
    for fname in sorted(os.listdir(tests_dir)):
        if not (fname.startswith('test_') and fname.endswith('.py')):
            continue
        rel = f'tests/{fname}'
        try:
            tree = ast.parse(src(rel))
        except SyntaxError:
            note(f'could not parse {rel}')
            continue
        env = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                vals = _eval_strs(node.value, env)
                if vals:
                    env[node.targets[0].id] = vals
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            argvals = {}
            for dec in fn.decorator_list:
                if (isinstance(dec, ast.Call) and getattr(dec.func, 'attr', '') == 'parametrize'
                        and len(dec.args) >= 2 and isinstance(dec.args[0], ast.Constant)):
                    names = [n.strip() for n in str(dec.args[0].value).split(',')]
                    if len(names) == 1:
                        argvals[names[0]] = _eval_strs(dec.args[1], env)
            loopvals = {}
            for n in ast.walk(fn):
                if isinstance(n, ast.For) and isinstance(n.target, ast.Name):
                    loopvals[n.target.id] = _eval_strs(n.iter, env)
            for n in ast.walk(fn):
                if not (isinstance(n, ast.Compare) and isinstance(n.left, ast.Call)
                        and getattr(n.left.func, 'id', '') in DETECTORS and n.left.args):
                    continue
                if getattr(n.left.func, 'id', '') != 'classify':
                    continue  # only class outcomes are labelled; severity-only asserts carry no expected class
                arg = n.left.args[0]
                texts = ([arg.value] if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                         else argvals.get(getattr(arg, 'id', ''), []) or loopvals.get(getattr(arg, 'id', ''), []))
                exp = [str(e) for e in _const_set(n.comparators[0])] if isinstance(n.ops[0], (ast.Eq, ast.In)) else []
                if not exp:
                    continue
                for t in texts:
                    c = cases.setdefault(t, {'expects': set(), 'sources': set()})
                    c['expects'].update(exp)
                    c['sources'].add(f'{rel}::{fn.name}')
    return cases
