#!/usr/bin/env python3
"""Tests for scripts/check-mutation-anchors.py (ai-config#5738)."""
import os
import subprocess
import sys
import tempfile

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "check-mutation-anchors.py")
HOOK = "def run(x):\n    if alpha(x):\n        return 1\n    pad()\n    pad()\n"
LIB = "def walk(words):\n    if beta(words):\n        return 2\n"
DICT_LOOP = ("for clause, (statement, edits, flips) in MUTATIONS.items():\n"
             "    for find, replace in edits:\n"
             "        assert SOURCE.count(find) == 1\n")


def table(*clauses, prefix=""):
    rows = "".join(f"    {name!r}: ('s', [{edits}], set()),\n" for name, edits in clauses)
    return prefix + "MUTATIONS = {\n" + rows + "}\n" + DICT_LOOP


LIST_LENIENT = ("MUTATIONS = [('m1', ('pad()', 'pass'), {'c'}),\n"
                "             ('m2', ('if gamma(x):', 'x'), {'c'})]\n"
                "for mid, (old, new), expect_flip in MUTATIONS:\n"
                "    if old not in src:\n        raise SystemExit(1)\n")
LIST_ANCHOR_FIRST = ("MUTATIONS = [('if alpha(x):', 'x', [], True, 'first'),\n"
                     "             ('if gamma(x):', 'x', [], True, 'second')]\n"
                     "for anchor, replacement, events, want_fire, label in MUTATIONS:\n"
                     "    assert source.count(anchor) == 1\n")
NO_ANCHOR = "MUTATIONS = [('n', 'c', False)]\nfor name, content, want in MUTATIONS:\n    pass\n"
WITH_LIB = "LIB = 'shellcmd'\n"

# (name, test-file body, hook present, exit code, BAD lines, text the output must carry)
CASES = [
    ("present once", table(("ok", "('if alpha(x):', 'if 0:')")), True, 0, 0, []),
    ("missing", table(("gone", "('if gamma(x):', 'x')")), True, 1, 1, ["clause gone", "has 0, need exactly 1"]),
    ("duplicate under .count()", table(("twice", "('pad()', 'x')")), True, 1, 1, ["has 2"]),
    ("every bad anchor", table(("g1", "('if gamma(x):', 'x')"), ("ok", "('if alpha(x):', 'x')"),
                               ("g2", "('if delta(x):', 'x')")), True, 1, 2, ["clause g1", "clause g2"]),
    ("3-tuple in lib", table(("lib", "(LIB, 'if beta(words):', 'x')"), prefix=WITH_LIB), True, 0, 0, []),
    ("3-tuple only in hook", table(("lib", "(LIB, 'if alpha(x):', 'x')"), prefix=WITH_LIB), True, 1, 1,
     ["scripts/lib/shellcmd.py has 0"]),
    ("unknown 3-tuple target", table(("lib", "('nosuch', 'if beta(words):', 'x')")), True, 0, 0, ["SKIP", "nosuch"]),
    ("edits apply in order", table(("seq", "('if alpha(x):', 'if omega(x):'), ('if omega(x):', 'x')")), True, 0, 0, []),
    ("chr() and +", table(("b", "('if alpha' + chr(40) + 'x):', 'x')")), True, 0, 0, []),
    ("not-in harness is lenient", LIST_LENIENT, True, 1, 1, ["clause m2", "need 1 or more"]),
    ("anchor-first list shape", LIST_ANCHOR_FIRST, True, 1, 1, ["clause second"]),
    ("no anchor field: skip, exit 2", NO_ANCHOR, True, 2, 0, ["loop binds no anchor field", "skipped 1 file"]),
    ("unparseable: skip", "MUTATIONS = {\nfor\n", True, 2, 0, ["does not parse"]),
    ("no subject hook: skip", table(("ok", "('x', 'y')")), False, 2, 0, ["no subject hooks/probe.py"]),
]

failures = 0
for name, body, has_hook, want_code, want_bad, want_text in CASES:
    with tempfile.TemporaryDirectory() as root:
        os.makedirs(os.path.join(root, "scripts", "lib"))
        os.makedirs(os.path.join(root, "hooks"))
        files = {"hooks/test-probe.py": body, "scripts/lib/shellcmd.py": LIB}
        files.update({"hooks/probe.py": HOOK} if has_hook else {})
        for rel, text in files.items():
            with open(os.path.join(root, rel), "w", encoding="utf-8") as handle:
                handle.write(text)
        proc = subprocess.run([sys.executable, SCRIPT, root], capture_output=True, text=True)
    out = proc.stdout + proc.stderr
    ok = proc.returncode == want_code and out.count("BAD  ") == want_bad and all(t in out for t in want_text)
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {name}" + ("" if ok else f": exit {proc.returncode}\n{out}"))

sys.exit(f"{failures} case(s) FAILED" if failures else 0)
