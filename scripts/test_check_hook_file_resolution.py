#!/usr/bin/env python3
"""Tests for scripts/check-hook-file-resolution.py.

The negative control matters more than the positive one here: a checker that
reports "none found" over a directory it never read is indistinguishable from
one that works, which is the failure `shared/workflow/` warns about for any
sweep. So every case that expects a clean result is paired with one that
plants an offender and asserts it is caught.

Run: python3 scripts/test_check_hook_file_resolution.py
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "scripts" / "check-hook-file-resolution.py"


def _load():
    spec = importlib.util.spec_from_file_location("chfr", CHECKER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _offenders_of(mod, source: str) -> list[tuple[int, str]]:
    d = Path(tempfile.mkdtemp(prefix="chfr-"))
    try:
        p = d / "sample.py"
        p.write_text(source, encoding="utf-8")
        return mod.offenders(p)
    finally:
        shutil.rmtree(d, ignore_errors=True)


CASES = [
    # (label, source, expected number of offenders)
    ("the exact idiom the sweep removed",
     "import os\nHERE = os.path.dirname(os.path.abspath(__file__))\n", 1),
    ("a bare re-exec of the script's own path",
     "import os\nrun([exe, os.path.abspath(__file__)])\n", 1),
    ("the `from os.path import abspath` spelling",
     "from os.path import abspath\nHERE = abspath(__file__)\n", 1),
    ("a module aliased as `path`",
     "import os.path as path\nHERE = path.abspath(__file__)\n", 1),
    ("two offenders in one file are both reported",
     "import os\nA = os.path.abspath(__file__)\nB = os.path.abspath(__file__)\n", 2),
    # Clean cases. Each is a shape a naive substring matcher would misjudge.
    ("the corrected idiom",
     "import os\nHERE = os.path.dirname(os.path.realpath(__file__))\n", 0),
    ("abspath applied to something that is NOT __file__",
     "import os\nHERE = os.path.abspath(sys.argv[1])\n", 0),
    ("__file__ used without abspath",
     "import os\nHERE = os.path.dirname(__file__)\n", 0),
    ("Path(__file__).resolve(), which is realpath-equivalent",
     "from pathlib import Path\nROOT = Path(__file__).resolve().parent\n", 0),
    ("the word abspath inside a string or comment only",
     "# do not use os.path.abspath(__file__) here\nX = 'os.path.abspath(__file__)'\n", 0),
]


def main() -> int:
    mod = _load()
    failures = 0
    for label, source, expected in CASES:
        got = len(_offenders_of(mod, source))
        if got != expected:
            print(f"FAIL (got {got}, wanted {expected}): {label}")
            failures += 1
        else:
            print(f"PASS: {label}")

    # The checker must also be green on the repo it ships in -- and that
    # assertion is only worth anything because the planted cases above prove
    # the detector fires.
    repo_offenders = sum(len(mod.offenders(p))
                         for p in sorted((ROOT / "hooks").glob("*.py")))
    if repo_offenders:
        print(f"FAIL (repo has {repo_offenders} offenders): hooks/ is clean")
        failures += 1
    else:
        print("PASS: hooks/ is clean")

    total = len(CASES) + 1
    print(f"\n{total - failures}/{total} cases passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
