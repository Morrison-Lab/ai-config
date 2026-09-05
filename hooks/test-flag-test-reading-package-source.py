#!/usr/bin/env python3
"""Tests for `flag-test-reading-package-source.py`.

The motivating case is first, verbatim from ucdavis/hac.sap#43. The rest are
the boundaries: the legitimate one-level fixture idiom must NOT fire, and a
non-test file must not either, or the guard becomes noise and gets removed.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
HOOK = os.path.join(HERE, "flag-test-reading-package-source.py")

spec = importlib.util.spec_from_file_location("ftrps", HOOK)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

failures = []


def check(label, got, want):
    if got != want:
        failures.append(f"{label}: got {got!r}, want {want!r}")


def fires(path, content):
    return mod.offending_line(path, content) is not None


# --- the motivating case, verbatim ---------------------------------------
check(
    "the hac.sap#43 line fires",
    fires(
        "tests/testthat/test-format_sap_table.R",
        '  src <- readLines(test_path("..", "..", "R", "format_sap_table.R"))',
    ),
    True,
)
check(
    "the fix that replaced it does NOT fire",
    fires(
        "tests/testthat/test-format_sap_table.R",
        '  ns <- asNamespace("hac.sap")\n'
        "  lines <- deparse(body(f))",
    ),
    False,
)

# --- the legitimate idiom must stay silent -------------------------------
# One level up resolves INSIDE the tests tree; this is how fixtures are
# reached, and firing on it is how the guard gets switched off.
check(
    "one level up is a fixture, not an escape",
    fires(
        "tests/testthat/test-thing.R",
        '  readLines(test_path("..", "testdata", "fixture.txt"))',
    ),
    False,
)
check(
    "a plain relative fixture read is silent",
    fires("tests/testthat/test-thing.R", '  readLines("fixture.txt")'),
    False,
)

# --- the other escape shapes ---------------------------------------------
check(
    "a literal ../../ path fires",
    fires("tests/test_thing.py", '    open("../../src/pkg/mod.py").read()'),
    True,
)
check(
    "file.path two levels up fires",
    fires("tests/testthat/test-x.R", '  readLines(file.path("..", "..", "DESCRIPTION"))'),
    True,
)
check(
    "a read naming R/ fires",
    fires("tests/testthat/test-x.R", '  source("R/helpers.R")'),
    True,
)
check(
    "a read naming inst/ fires",
    fires("tests/testthat/test-x.R", '  readLines("inst/docx/ref.docx")'),
    True,
)

# --- scope: only test files ----------------------------------------------
check(
    "the same line in R/ does not fire",
    fires("R/format_sap_table.R", '  readLines(test_path("..", "..", "R", "x.R"))'),
    False,
)
check(
    "the same line in a script does not fire",
    fires("scripts/check-thing.R", '  readLines(file.path("..", "..", "R", "x.R"))'),
    False,
)
check(
    "a test-named file outside tests/ still fires",
    fires("test_packaging.py", '    open("../../src/mod.py")'),
    True,
)

# --- a mention is not a read ---------------------------------------------
# This corpus quotes paths in prose constantly; matching those is how a
# guard earns its removal.
check(
    "a comment mentioning the path does not fire",
    fires(
        "tests/testthat/test-x.R",
        '  # do not readLines(test_path("..", "..", "R", "x.R")) here',
    ),
    False,
)
check(
    "a python comment mentioning it does not fire",
    fires("tests/test_x.py", '    # open("../../src/mod.py") would break the wheel'),
    False,
)
check(
    "a bare path with no read call does not fire",
    fires("tests/testthat/test-x.R", '  expected_path <- "../../R/x.R"'),
    False,
)

# --- empty and malformed input -------------------------------------------
check("empty content is silent", fires("tests/testthat/test-x.R", ""), False)
check("empty path is silent", fires("", 'readLines("../../R/x.R")'), False)
check("non-string content is silent", mod.offending_line("tests/t.R", None), None)

# --- the returned snippet is the offending line --------------------------
check(
    "the offending line comes back stripped",
    mod.offending_line(
        "tests/testthat/test-x.R",
        'ok <- 1\n  readLines(file.path("..", "..", "R", "x.R"))\nmore <- 2',
    ),
    'readLines(file.path("..", "..", "R", "x.R"))',
)

# --- end to end, through the hook's own stdin contract -------------------
def run_hook(payload):
    p = subprocess.run(
        [sys.executable, HOOK], input=json.dumps(payload),
        capture_output=True, text=True,
    )
    return p.returncode, p.stdout


rc, out = run_hook({
    "tool_name": "Edit",
    "tool_input": {
        "file_path": "tests/testthat/test-format_sap_table.R",
        "new_string": '  src <- readLines(test_path("..", "..", "R", "x.R"))',
    },
})
check("end to end: exits 0 (warns, never blocks)", rc, 0)
check("end to end: emits additionalContext", "additionalContext" in out, True)
check("end to end: names the measured case", "hac.sap#43" in out, True)

rc, out = run_hook({
    "tool_name": "Edit",
    "tool_input": {
        "file_path": "tests/testthat/test-x.R",
        "new_string": '  readLines(test_path("..", "testdata", "f.txt"))',
    },
})
check("end to end: silent on the fixture idiom", out.strip(), "")

rc, out = run_hook({
    "tool_name": "Bash",
    "tool_input": {"command": 'readLines(test_path("..", "..", "R", "x.R"))'},
})
check("end to end: ignores a non-edit tool", out.strip(), "")

rc, out = run_hook({"tool_name": "Edit", "tool_input": "not a dict"})
check("end to end: survives a malformed payload", rc, 0)

if failures:
    print("FAILED:")
    for line in failures:
        print("  " + line)
    sys.exit(1)
print("all tests passed")
