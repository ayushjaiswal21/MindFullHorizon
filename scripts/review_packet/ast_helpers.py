"""Static-value extraction from Python source via AST: strings, numbers, and system prompts."""
import ast

from .core import tree_of


def static_str(node, env):
    """Best-effort static value of a string expression; unknown parts appear as {expr}."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return env.get(node.id, '{' + node.id + '}')
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return static_str(node.left, env) + static_str(node.right, env)
    if isinstance(node, ast.JoinedStr):
        return ''.join(v.value if isinstance(v, ast.Constant) else '{' + ast.unparse(v.value) + '}' for v in node.values)
    return None


def module_strings(rel):
    """{NAME: value} for module-level assignments that are static strings."""
    env = {}
    for node in tree_of(rel).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            v = static_str(node.value, env)
            if v is not None and '{' not in v[:1]:
                env[node.targets[0].id] = v
    return env


def _num(node):
    """Value of a numeric literal or simple arithmetic on literals (15 * 60.0), else None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.BinOp):
        l, r = _num(node.left), _num(node.right)
        ops = {ast.Add: lambda x, y: x + y, ast.Sub: lambda x, y: x - y, ast.Mult: lambda x, y: x * y,
               ast.Div: lambda x, y: x / y}
        if l is not None and r is not None and type(node.op) in ops:
            return ops[type(node.op)](l, r)
    return None


def module_ints(rel):
    out = {}
    for node in tree_of(rel).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            v = _num(node.value)
            if v is not None:
                out[node.targets[0].id] = v
    return out


def function_strings(rel, funcs, minlen=30):
    """(function, line, text) for string literals (f-strings with {expr} placeholders) of at least `minlen` chars
    inside the named functions. Docstrings are skipped."""
    out = []
    for fn in ast.walk(tree_of(rel)):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and fn.name in funcs:
            doc = ast.get_docstring(fn, clean=False)
            inner = {id(v) for n in ast.walk(fn) if isinstance(n, ast.JoinedStr) for v in ast.walk(n) if v is not n}
            for n in ast.walk(fn):
                if id(n) in inner:
                    continue
                text = None
                if isinstance(n, ast.Constant) and isinstance(n.value, str):
                    text = n.value
                elif isinstance(n, ast.JoinedStr):
                    text = static_str(n, {})
                if text and len(text) >= minlen and text != doc:
                    out.append((fn.name, n.lineno, text))
    return sorted(set(out), key=lambda t: (t[1], t[0]))


def system_prompts(rel):
    """(function, line, text) for every `system_prompt = <static string>` assignment."""
    env = module_strings(rel)
    out = []
    for fn in ast.walk(tree_of(rel)):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for n in ast.walk(fn):
                if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'system_prompt' for t in n.targets):
                    v = static_str(n.value, env)
                    if v is not None:
                        out.append((fn.name, n.lineno, v))
    return sorted(set(out), key=lambda t: t[1])
