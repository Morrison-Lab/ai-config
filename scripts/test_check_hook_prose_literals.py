#!/usr/bin/env python3
"""Tests for check-hook-prose-literals.py, over throwaway trees."""
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "check-hook-prose-literals.py"
LONG = 'MSG = """\\\n' + "".join(f"line {i}\n" for i in range(9)) + '"""\n'
LONG_F = 'q = 1\nMSG = (f"a {q}"\n' + "".join(f'       "b{i}"\n' for i in range(8)) + ")\n"
DOC = '"""' + "".join(f"doc {i}\n" for i in range(12)) + '"""\n'
FUNC_DOC = 'def f():\n    """' + "".join(f"doc {i}\n" for i in range(12)) + '    """\n'
SHORT = 'MSG = ("one "\n       "two")\n'

failures = 0


def run(files: dict, known: str = None, *flags):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "hooks").mkdir()
        (root / "scripts").mkdir()
        for name, text in files.items():
            (root / "hooks" / name).write_text(text, encoding="utf-8")
        if known is not None:
            (root / "scripts" / "hook-prose-literals-known.txt").write_text(known, encoding="utf-8")
        proc = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), *flags],
                              capture_output=True, text=True)
        return proc.returncode, proc.stdout


def case(name, files, expect, known=None):
    global failures
    code, out = run(files, known)
    if code != expect:
        failures += 1
        print(f"FAIL {name}: exit {code}, expected {expect}\n{out}")
    else:
        print(f"ok   {name}")


case("long literal in an unlisted hook fails", {"a.py": LONG}, 1)
case("long f-string fails", {"a.py": LONG_F}, 1)
case("module docstring passes", {"a.py": DOC}, 0)
case("function docstring passes", {"a.py": FUNC_DOC}, 0)
case("short literal passes", {"a.py": SHORT}, 0)
case("test suites are out of scope", {"test-a.py": LONG, "b.py": SHORT}, 0)
case("listed count passes", {"a.py": LONG}, 0, known="a.py 1\n")
case("count above the listed one fails", {"a.py": LONG + LONG.replace("MSG", "M2")}, 1,
     known="a.py 1\n")
case("count below the listed one fails until lowered", {"a.py": SHORT}, 1, known="a.py 1\n")
case("no hooks is an error, not a pass", {}, 2)
case("unparsable hook is an error", {"a.py": "def (:\n"}, 2)

if failures:
    print(f"{failures} case(s) failed")
    sys.exit(1)
print("all cases passed")
