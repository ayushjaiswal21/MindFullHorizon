import ast
import os
import re
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
os.chdir(ROOT)
SKIP = {"venv", "node_modules", "data", "static", "__pycache__", ".git", "instance"}
mods = {}
for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in SKIP]
    for f in files:
        if not f.endswith(".py"):
            continue
        p = os.path.join(root, f).replace(os.sep, "/")
        try:
            tree = ast.parse(open(p, encoding="utf8").read())
        except Exception as e:
            print("PARSE FAIL", p, e)
            continue
        for n in ast.walk(tree):
            names = []
            if isinstance(n, ast.Import):
                names = [a.name.split(".")[0] for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                names = [n.module.split(".")[0]]
            for m in names:
                mods.setdefault(m, set()).add(p)

# Only first-party code counts as local: tracked package dirs + root modules.
# (Runtime dirs such as flask_session/ must NOT be treated as local; they shadow a real package name.)
local = {"ai", "routes", "utils", "scripts", "tests", "migrations"} | {f[:-3] for f in os.listdir(".") if f.endswith(".py")}
std = set(sys.stdlib_module_names)
print("== third-party imports (module, #files, in tests only?, first files)")
for m in sorted(m for m in mods if m not in std and m not in local):
    where = sorted(mods[m])
    only_tests = all(w.startswith("./tests/") or w.startswith("tests/") for w in where)
    print(f"{m:26} {len(where):2} {'TESTS-ONLY' if only_tests else '':10} {', '.join(where[:3])}")

print("\n== requirements.txt entries")
reqs = []
for line in open("requirements.txt", encoding="utf8"):
    line = line.strip()
    if line and not line.startswith("#"):
        reqs.append(re.split(r"[<>=!~\[ ;#]", line)[0])
print(len(reqs), "entries")
print(", ".join(reqs))
