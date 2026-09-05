#!/usr/bin/env python3
r"""PreToolUse guard: a test that reads its own package's source from disk.

A test which derives something by READING a source file -- rather than by
inspecting the loaded module, package or namespace -- passes in a source
checkout and fails wherever the code is consumed as an installed artifact.
An installed R package has no `R/*.R`; a Python wheel need not ship `src/`.
The local suite is green, so nothing signals it until a packaging check runs,
and where no packaging check runs it is never signalled at all.

THE MEASUREMENT (2026-09-04, ucdavis/hac.sap#43)
------------------------------------------------
A test derived its coverage list this way:

    src <- readLines(test_path("..", "..", "R", "format_sap_table.R"))

`testthat::test_local()` reported 25 tests / 0 failures. `R CMD check` on a
clean tree reported:

    Error in `file(con, "r")`: cannot open the connection

The line was written inside the PR fixing ucdavis/hac.sap#27, whose entire
content is *a test that cannot run where CI runs it* -- by an author who had
read that issue minutes earlier. That is the argument for an instrument over
a rule: the rule is consulted at read time and broken at composition time
(`shared/principles/deterministic-tools.md`).

The fix is to read the LOADED artifact instead. In R, `deparse(body(f))` over
`asNamespace(pkg)` works in a checkout and an installed package alike; in
Python, `inspect.getsource` on an imported object does.

WHAT IT CHECKS
--------------
An `Edit`/`Write`/`NotebookEdit` whose target is under a test directory, and
whose new content reads a path that ESCAPES that directory:

  * `test_path("..", "..", ...)`      -- two or more levels up
  * `file.path("..", "..", ...)`      -- likewise
  * a literal path string containing `../../`
  * a read call naming a package source directory: `R/`, `src/`, `inst/`

WHAT IT DELIBERATELY DOES NOT CHECK
-----------------------------------
One level up is the legitimate fixture idiom -- `test_path("..", "testdata")`
resolves inside the tests tree -- so it is not matched. Nor is a bare mention
of a path in a comment: the match requires a READ call around it, because
this corpus's tests quote paths in prose constantly and a guard that fires on
those gets switched off, taking the real cases with it.

Warns; never blocks. A test reading a source file is occasionally right (a
linter's own fixtures, a codegen check), and the author is better placed to
judge that than a regex. Fails OPEN.
"""
import json
import os
import re
import sys

WRITE_TOOL_NAMES = {
    "Write", "Edit", "MultiEdit", "NotebookEdit",
    "create_file", "edit_file", "replace_string_in_file", "write_file",
}

# The edit's target must live under a test directory.
RX_TEST_PATH = re.compile(
    r"(^|/)(tests?|spec|testthat)(/|$)"
    r"|(^|/)test[_-][^/]*\.(R|r|py|jl|rb|js|ts)$"
    r"|(^|/)[^/]*[_-]test\.(R|r|py|jl|rb|js|ts)$",
    re.I,
)

# A read call. Kept explicit rather than "any function": the whole point is
# that the content is being READ, not that a path is mentioned.
READ_CALLS = (
    r"readLines|readRDS|read\.csv|read\.table|source|file|scan|"
    r"readr::read_[a-z_]+|xml2::read_[a-z]+|yaml::[a-z_]*read[a-z_]*|"
    r"open|read_text|read_bytes|Path|parse_file|getsource|read"
)

# Two or more levels up, inside a read call. `[^)\n]*` keeps the match on one
# call rather than running across a whole file.
RX_ESCAPE_TWO_UP = re.compile(
    r"(?:" + READ_CALLS + r")\s*\([^)\n]*"
    r"(?:"
    r"""["']\.\.["']\s*,\s*["']\.\.["']"""   # "..", ".."
    r"|\.\./\.\./"                            # ../../
    r")",
    re.I,
)

# A read call naming a package source directory by name.
RX_PACKAGE_SRC = re.compile(
    r"(?:" + READ_CALLS + r")\s*\([^)\n]*"
    r"""["'][^"'\n]*(?<![A-Za-z0-9_])(?:R|src|inst)/[^"'\n]*["']""",
    re.I,
)

NOTE = """A test appears to READ its own package's source from disk:

    {snippet}

That passes in a source checkout and fails wherever the code is consumed as an
installed artifact -- an installed R package has no `R/*.R`, and a Python wheel
need not ship `src/`. The local suite stays green, so only a packaging check
(`R CMD check`, a wheel build, an installed-package test run) reveals it.

Measured 2026-09-04 on ucdavis/hac.sap#43: `readLines(test_path("..", "..",
"R", "format_sap_table.R"))` gave 25 tests / 0 failures locally and
`Error in file(con, "r"): cannot open the connection` under `R CMD check`.

Read the LOADED artifact instead, which works in both:

  * R      -- `deparse(body(f))` over `asNamespace("<pkg>")`
  * Python -- `inspect.getsource` on an imported object

If reading the source really is the point (a linter's fixtures, a codegen
check), carry on -- this is a reminder, not a refusal. Then make sure the test
is reachable where it runs: a `skip_if_not(file.exists(...))` that is
unconditional in CI occupies the slot while protecting nothing."""


def _extract(tool_input):
    """(target_path, new_content) for an edit-shaped tool call."""
    target = (
        tool_input.get("file_path")
        or tool_input.get("path")
        or tool_input.get("filePath")
        or tool_input.get("notebook_path")
        or ""
    )
    content = (
        tool_input.get("content")
        or tool_input.get("text")
        or tool_input.get("new_string")
        or tool_input.get("new_source")
        or tool_input.get("replacement")
        or ""
    )
    if not content and isinstance(tool_input.get("edits"), list):
        content = "\n".join(
            e.get("new_string") or e.get("replacement") or ""
            for e in tool_input["edits"] if isinstance(e, dict)
        )
    return target, content


def offending_line(target, content):
    """The first line of `content` that reads outside the tests tree, or None."""
    if not target or not RX_TEST_PATH.search(target):
        return None
    if not isinstance(content, str) or not content.strip():
        return None
    for line in content.splitlines():
        stripped = line.strip()
        # A comment mentioning a path is not a read.
        if stripped.startswith("#") or stripped.startswith("//"):
            continue
        if RX_ESCAPE_TWO_UP.search(line) or RX_PACKAGE_SRC.search(line):
            return stripped
    return None


def main() -> int:
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    if not raw.strip():
        return 0
    try:
        payload = json.loads(raw)
    except Exception:
        return 0
    if payload.get("tool_name") not in WRITE_TOOL_NAMES:
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0

    try:
        target, content = _extract(tool_input)
        hit = offending_line(target, content)
        if not hit:
            return 0
        snippet = hit if len(hit) <= 160 else hit[:157] + "..."
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": NOTE.format(snippet=snippet),
            },
        }
        if not os.environ.get("ANTIGRAVITY_AGENT"):
            out["systemMessage"] = (
                "Packaging reminder: this test reads a source file from disk, "
                "which passes locally and fails under an installed-package "
                "check. Read the loaded artifact instead."
            )
        print(json.dumps(out))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
