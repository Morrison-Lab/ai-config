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
# A test DIRECTORY is required. `hooks/test-*.py` here are guard tests whose
# fixtures CONTAIN such code as payload data; three of them, including this
# suite, fired under a filename-only rule.
check(
    "a test-named file outside a test directory does not fire",
    fires("test_packaging.py", '    open("../../src/mod.py")'),
    False,
)
check(
    "this repo's own hook tests do not fire",
    fires("hooks/test-remind-x.py", '  "readRDS(\\"inst/extdata/x.rds\\")"'),
    False,
)
check(
    "a nested package test dir still fires",
    fires("pkg/tests/testthat/test-x.R", '  source("R/helpers.R")'),
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

# --- the false positives a review measured against committed code ---------
# Each of these fired in an earlier revision. A guard that fires on correct
# code gets switched off, taking the real cases with it.
for label, path, line in [
    ("monitor_path", "tests/test_x.py",
     'assert monitor_path("https://github.com/o/r/pull/1") == 1'),
    ("normalizePath", "tests/testthat/test-x.R", '  p <- normalizePath("../../inst")'),
    ("fs.path build/src", "tests/test_x.py", '    out = fs.path("build", "src/app.js")'),
    ("sourcePath", "tests/test_x.ts", "  expect(map.sourcePath('../../src/a.ts')).toBe(1)"),
    ("relpath", "tests/test_x.py", '    assert relpath("pkg/src/mod.py") == "m"'),
    ("a reddit r/ URL", "tests/test_x.py", '    u = urlpath("https://reddit.com/r/python/x")'),
    ("local_file is a write", "tests/testthat/test-x.R", '  withr::local_file("src/tmp.txt")'),
    ("markdown prose", "tests/README.md", '  Use `readLines("../../R/x.R")` here.'),
    ("a docstring body", "tests/test_x.py", '    """Do not open("../../src/m.py")."""'),
    ("a block-comment star", "tests/testthat/test-x.R", "   * open('../../src/x.py')"),
]:
    check(f"false positive stays silent: {label}", fires(path, line), False)

# The left-anchor lookbehind specifically. Without it, any identifier ENDING
# in a listed read name matches -- these are the cases that make it
# load-bearing rather than decorative.
for label, line in [
    ("mysource", '  mysource("../../src/x.R")'),
    ("reopen", '    reopen("../../src/mod.py")'),
    ("do_scan", '  do_scan("../../R/x.R")'),
]:
    check(f"the left anchor holds: {label}",
          fires("tests/testthat/test-x.R", line), False)


# --- the narrowings themselves, each pinned ------------------------------
# The six false-positive assertions above were regression guards against an
# OLD unanchored alternation. Measured: they pass identically with the
# case-sensitive `R/` and the begin-anchoring reverted, so they pin neither.
# These inputs do.
check("a lowercase r/ path is not R/", 
      fires("tests/testthat/test-x.R", '  readLines("r/notes.txt")'), False)
check("the directory must BEGIN the path",
      fires("tests/testthat/test-x.R", '  readLines("build/src/app.js")'), False)
check("...and vendor/inst likewise",
      fires("tests/testthat/test-x.R", '  readLines("vendor/inst/x.txt")'), False)

# Path CONSTRUCTORS are not reads. An earlier revision listed `file.path` and
# `test_path` as reads and fired on writes and existence checks.
for label, line in [
    ("dir.create", '  dir.create(file.path("..", "..", "tmpout"))'),
    ("writeLines", '  writeLines(txt, file.path("..", "..", "out.txt"))'),
    ("unlink", '  unlink(file.path("..", "..", "scratch"), recursive = TRUE)'),
    ("file.exists", '  expect_true(file.exists(file.path("..", "..", "DESCRIPTION")))'),
    ("local_dir", '  withr::local_dir(test_path("..", ".."))'),
]:
    check(f"a path constructor is not a read: {label}",
          fires("tests/testthat/test-x.R", line), False)

# ...but a real read THROUGH a constructor still fires.
check("a read through file.path still fires",
      fires("tests/testthat/test-x.R",
            '  readLines(file.path("..", "..", "DESCRIPTION"))'), True)
check("here::here, the standard R root idiom, fires",
      fires("tests/testthat/test-x.R", '  src <- readLines(here::here("R", "x.R"))'), True)
check("system.file, the installed-SAFE idiom, does not",
      fires("tests/testthat/test-x.R",
            '  p <- system.file("R", "x.R", package = "p")'), False)

# The Python method spelling, which sat unreachable behind the left anchor.
check("Path(...).read_text() fires",
      fires("tests/test_x.py",
            '    src = Path(__file__).parent.parent.joinpath("src", "m.py").read_text()'),
      True)

# Scope: the extension gate must match the read list, not overclaim.
check("a JS test is out of scope, not silently inert",
      mod.RX_TEST_PATH.search("tests/api.test.js") is None, True)

# The real-world true positive the repo sweep found.
check("the measured real-world instance fires",
      fires("tests/spelling.R", '  wordlist <- readLines("inst/WORDLIST")'), True)

# Each remaining directory name.
for d in ("tests", "test", "spec", "testthat"):
    check(f"the {d}/ directory is in scope",
          mod.RX_TEST_PATH.search(f"{d}/x.R") is not None, True)


# --- the arms a third round found unasserted or wrongly pinned ------------
# `styler` wraps the motivating call at 80 columns, and a line-oriented scan
# was blind to it -- the exact case this guard exists for.
check("the motivating call still fires once styler wraps it",
      fires("tests/testthat/test-format_sap_table.R",
            '  src <- readLines(\n    test_path("..", "..", "R", "format_sap_table.R")\n  )'),
      True)

# Python's path constructors are the twins of `file.path` and fired on
# writes, deletions and existence checks.
for label, line in [
    ("mkdir", '  pathlib.Path("../../scratch").mkdir(parents=True)'),
    ("write_text", '  pathlib.Path("../../out.txt").write_text("hi")'),
    ("rmdir", '  pathlib.Path("src/generated").rmdir()'),
    ("exists", '  assert pathlib.Path("../../LICENSE").exists()'),
]:
    check(f"a python path constructor is not a read: {label}",
          fires("tests/test_x.py", line), False)

# A bare `.read(` matched sockets, pipes and zipfile members; the distance
# bound and the statement split stop unrelated pairings.
for label, line in [
    ("subprocess pipe", 'out = subprocess.run(["ls","../../"], capture_output=True).stdout.read()'),
    ("zipfile member", 'zf.writestr("src/mod.py", code); assert zf.read("src/mod.py")'),
    ("unrelated fh.read", 'assert loader.paths == ["src/main.py"] and fh.read() == "x"'),
    ("write then read", 'tmpfile.write_text("src/a"); assert tmpfile.read_text() == "src/a"'),
    ("argparse then log", 'args = parser.parse_args(["--out","../../build"]); log.read()'),
]:
    check(f"an unrelated read is not paired: {label}", fires("tests/test_x.py", line), False)

# The distance bound specifically: one STATEMENT carrying an unrelated path
# and an unrelated read, too far apart to be the same expression. The
# statement split does not reach this; only the 40-character bound does.
for label, line in [
    ("wide assert", 'assert cfg["src/main.py"] == expected_value_for_this_case and handle.read_text() == ok'),
    ("wide call", 'result = compare(manifest["src/a.py"], other, tolerance=0.01, verbose=True, fh.read_text())'),
]:
    check(f"a distant read is not paired: {label}", fires("tests/test_x.py", line), False)

# ...while the chain it exists to admit stays within the bound.
check("a real method chain is still within the bound",
      fires("tests/test_x.py",
            '    src = Path(__file__).parent.joinpath("src", "m.py").read_text()'),
      True)

# Trailing comments, which the line-start-anchored detector missed.
for line in ['  x <- 1  # never readLines("R/f.R") here',
             '  expect_equal(f(), 1)  # cf. source("R/helpers.R")',
             '    assert f() == 1  # open("../../src/m.py") is wrong']:
    check("a trailing comment is a mention, not a read",
          fires("tests/testthat/test-x.R", line), False)

# Dotted reads, which were entirely unasserted.
for label, line in [
    ("inspect.getsource", '    src = inspect.getsource(open("../../src/m.py"))'),
    ("xml2::read_xml", '  d <- xml2::read_xml("inst/x.xml")'),
    ("jsonlite::fromJSON", '  j <- jsonlite::fromJSON("inst/x.json")'),
]:
    check(f"a dotted read fires: {label}", fires("tests/testthat/test-x.R", line), True)

# The multi-line docstring state machine, whose only test was self-closing.
check("a read inside a MULTI-line docstring is suppressed",
      fires("tests/test_x.py",
            '    """\n    Do not open("../../src/m.py") in a test.\n    """'),
      False)

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

# --- the output SHAPE, which exit 0 does not pin --------------------------
# A `permissionDecision: "deny"` blocks on exit 0, so "rc == 0" is not what
# makes a PreToolUse hook non-blocking. A mutation adding one survived the
# first version of this suite.
hit = {"tool_name": "Edit", "tool_input": {
    "file_path": "tests/testthat/test-x.R",
    "new_string": '  readLines(test_path("..", "..", "R", "x.R"))'}}
rc, out = run_hook(hit)
parsed = json.loads(out)
check("no permissionDecision anywhere in the output", "permissionDecision" in out, False)
# The quoted snippet IS the diagnostic. Truncating it to a few characters
# left the first version of this suite green while making the message
# useless.
check("the full offending line is quoted back",
      'readLines(test_path("..", "..", "R", "x.R"))'
      in parsed["hookSpecificOutput"]["additionalContext"], True)
check("hookEventName is present", parsed["hookSpecificOutput"]["hookEventName"], "PreToolUse")
check("systemMessage is emitted outside Antigravity", "systemMessage" in parsed, True)

env = dict(os.environ, ANTIGRAVITY_AGENT="1")
p = subprocess.run([sys.executable, HOOK], input=json.dumps(hit),
                   capture_output=True, text=True, env=env)
check("systemMessage suppressed under ANTIGRAVITY_AGENT",
      "systemMessage" in json.loads(p.stdout), False)

# --- every bound tool name and payload shape ------------------------------
for tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
    rc, out = run_hook({"tool_name": tool, "tool_input": {
        "file_path": "tests/testthat/test-x.R",
        "new_string": '  readLines(test_path("..", "..", "R", "x.R"))'}})
    check(f"fires for tool {tool}", "additionalContext" in out, True)

rc, out = run_hook({"tool_name": "Write", "tool_input": {
    "file_path": "tests/testthat/test-x.R",
    "content": '  readLines(test_path("..", "..", "R", "x.R"))'}})
check("reads the Write `content` key", "additionalContext" in out, True)

rc, out = run_hook({"tool_name": "MultiEdit", "tool_input": {
    "file_path": "tests/testthat/test-x.R",
    "edits": [{"new_string": "ok <- 1"},
              {"new_string": '  readLines(file.path("..", "..", "R", "x.R"))'}]}})
check("reads the MultiEdit edits[] array", "additionalContext" in out, True)

rc, out = run_hook({"tool_name": "NotebookEdit", "tool_input": {
    "notebook_path": "tests/test_nb.py",
    "new_source": '    open("../../src/mod.py")'}})
check("reads notebook_path and new_source", "additionalContext" in out, True)

# --- fails OPEN on valid JSON that is not an object -----------------------
for payload in ("[1,2,3]", '"hello"', "null", "42", "not json at all", ""):
    p = subprocess.run([sys.executable, HOOK], input=payload,
                       capture_output=True, text=True)
    check(f"fails open on {payload[:14]!r}", (p.returncode, p.stderr.strip()), (0, ""))

# --- the dry-run contract the sibling hooks implement ---------------------
p = subprocess.run([sys.executable, HOOK, "--dry-run"],
                   input=json.dumps({"tool_name": "Edit", "tool_input": {
                       "file_path": "R/x.R", "new_string": "ok <- 1"}}),
                   capture_output=True, text=True)
check("--dry-run emits an envelope even with no hit",
      json.loads(p.stdout)["hookSpecificOutput"]["hookEventName"], "PreToolUse")

if failures:
    print("FAILED:")
    for line in failures:
        print("  " + line)
    sys.exit(1)
print("all tests passed")
