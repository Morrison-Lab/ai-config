#!/usr/bin/env python3
r"""PreToolUse guard: a test that reads its own package's source from disk.

A test which derives something by READING a source file -- rather than by
inspecting the loaded module, package or namespace -- passes in a source
checkout and fails wherever the code is consumed as an installed artifact.
An installed R package has no `R/*.R`; a Python wheel need not ship `src/`.
The local suite is green, so nothing signals it until a packaging check runs.

THE MEASUREMENT (2026-09-04, ucdavis/hac.sap#43)
------------------------------------------------
A test derived its coverage list this way:

    src <- readLines(test_path("..", "..", "R", "format_sap_table.R"))

`testthat::test_local()` reported 25 tests / 0 failures. `R CMD check` on a
clean tree reported `Error in file(con, "r"): cannot open the connection`.

The line was written inside the PR fixing ucdavis/hac.sap#27, whose entire
content is *a test that cannot run where CI runs it* -- by an author who had
read that issue minutes earlier. That is the argument for an instrument over
a rule: the rule is consulted at read time and broken at composition time
(`shared/principles/deterministic-tools.md`).

The fix is to read the LOADED artifact. In R, `deparse(body(f))` over
`asNamespace(pkg)` works in a checkout and an installed package alike; in
Python, `inspect.getsource` on an imported object does.

WHAT IT MATCHES
---------------
An `Edit`/`Write`/`NotebookEdit` whose target is a CODE file under a test
directory, and whose new content calls one of a short, explicit list of read
functions on a path escaping that directory:

  * `test_path("..", "..", ...)` / `file.path("..", "..", ...)` -- two up
  * a literal `../../` inside the call
  * a quoted path BEGINNING `R/`, `src/` or `inst/`

HOW IT AVOIDS THE FALSE POSITIVES THAT GET A GUARD SWITCHED OFF
---------------------------------------------------------------
An earlier revision of this file was reviewed and fired on committed, correct
code in this repo. Each narrowing below answers a measured false positive:

  * The read-call list is explicit and LEFT-ANCHORED (`(?<![\w.$])`), because
    a bare `path|file|read|open` alternation matched every identifier ending
    in one -- `normalizePath(`, `monitor_path(`, `fs::path(`, `relpath(`,
    `sourcePath(`. `file.path` and namespaced `pkg::read_x` are listed
    explicitly rather than reached by loosening the anchor.
  * `R/` is matched CASE-SENSITIVELY, via an inline `(?-i:...)`, because
    under `re.I` a lowercase `r/` segment made ordinary URLs match --
    `https://reddit.com/r/python/x`, `https://github.com/o/r/pull/1`.
  * The directory arm requires the path to BEGIN with `R/`/`src/`/`inst/`,
    not merely contain it, so `"build/src/app.js"` does not match.
  * Only code extensions are in scope. Markdown and reStructuredText under
    `tests/` are prose that quotes paths constantly.
  * Comment detection covers `#`, `//`, `--`, `*` continuations and lines
    inside a triple-quoted docstring, not just `#`. (Spelled out rather than
    shown: a literal triple quote here would end this very docstring -- which
    it did, on the first attempt.)
  * Write-shaped calls (`tempfile`, `write_*`, `local_file`, `save_*`) are
    never in the read list.

Warns; never blocks. Reading source is occasionally right (a linter's own
fixtures, a codegen check), and the author judges that better than a regex.
Fails OPEN on every malformed input.
"""
import json
import os
import re
import sys

WRITE_TOOL_NAMES = {
    "Write", "Edit", "MultiEdit", "NotebookEdit",
    "create_file", "edit_file", "replace_string_in_file", "write_file",
}

# Code files only. Prose under tests/ quotes paths constantly.
CODE_EXT = r"(?:R|r|py|jl|rb|js|ts|tsx|jsx|go|rs|java|kt|scala|sh)"
# A test DIRECTORY component is required, not merely a test-shaped filename.
# `hooks/test-*.py` in this repo are guard tests whose fixtures legitimately
# CONTAIN such code as payload data -- three of them, including this hook's
# own suite, fired under a filename-only rule. A package's real tests live
# under a test directory, so requiring one costs nothing and removes the
# whole fixture-bearing class.
RX_TEST_PATH = re.compile(
    r"(?:^|/)(?:tests?|spec|testthat)/(?:[^/]+/)*[^/]*\." + CODE_EXT + r"$",
)

# An explicit, short list. Dotted and namespaced forms are spelled out rather
# than reached by relaxing the anchor, which is what produced the false
# positives an earlier revision was reviewed for.
_BARE_READS = (
    r"readLines|readRDS|readr|scan|source|open|"
    r"read_text|read_bytes|getsource|parse_file|"
    r"read\.csv|read\.table|read\.delim|file\.path|test_path"
)
_DOTTED_READS = (
    r"readr::read_[a-z_]+|xml2::read_[a-z]+|yaml::read_yaml|jsonlite::fromJSON|"
    r"inspect\.getsource|pathlib\.Path|importlib\.resources\.files"
)
# `(?<![\w.$])` keeps `normalizePath(` and `monitor_path(` out while letting
# `file.path(` and `test_path(` in -- they are listed above in full.
READ_CALL = r"(?:(?<![\w.$])(?:" + _BARE_READS + r")|(?:" + _DOTTED_READS + r"))\s*\("

RX_ESCAPE_TWO_UP = re.compile(
    READ_CALL + r"[^)\n]*"
    r"(?:"
    r"""["']\.\.["']\s*,\s*["']\.\.["']"""
    r"|\.\./\.\./"
    r")",
    re.I,
)

# Case-SENSITIVE `R/` via (?-i:), and anchored to the start of the quoted
# path so "build/src/app.js" does not match.
RX_PACKAGE_SRC = re.compile(
    READ_CALL + r"[^)\n]*"
    r"""["'](?:(?-i:R)|src|inst)/[^"'\n]*["']""",
    re.I,
)

# Built by concatenation: a triple-single-quote inside a raw string
# terminates it.
_TQ = '"' * 3
_SQ = "'" * 3
RX_COMMENT = re.compile(r"^\s*(?:#|//|--|\*|/\*|" + _TQ + "|" + _SQ + ")")
RX_DOCSTRING_DELIM = re.compile(_TQ + "|" + _SQ)

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

SYSTEM_MESSAGE = (
    "Packaging reminder: this test reads a source file from disk, which "
    "passes locally and fails under an installed-package check. Read the "
    "loaded artifact instead."
)


def _extract(tool_input):
    """(target_path, new_content) for an edit-shaped tool call."""
    if not isinstance(tool_input, dict):
        return "", ""
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
            (e.get("new_string") or e.get("replacement") or "")
            for e in tool_input["edits"] if isinstance(e, dict)
        )
    if not isinstance(target, str):
        target = ""
    if not isinstance(content, str):
        content = ""
    return target, content


def offending_line(target, content):
    """The first line of `content` that reads outside the tests tree, or None."""
    if not isinstance(target, str) or not isinstance(content, str):
        return None
    if not target or not RX_TEST_PATH.search(target):
        return None
    if not content.strip():
        return None
    in_docstring = False
    for line in content.splitlines():
        stripped = line.strip()
        delims = len(RX_DOCSTRING_DELIM.findall(line))
        if in_docstring:
            if delims % 2 == 1:
                in_docstring = False
            continue
        if RX_COMMENT.match(line):
            if delims % 2 == 1:
                in_docstring = True
            continue
        if delims % 2 == 1:
            in_docstring = True
        if RX_ESCAPE_TWO_UP.search(line) or RX_PACKAGE_SRC.search(line):
            return stripped
    return None


def _read_payload():
    """(payload, is_dry_run). Mirrors flag-unmeasured-timestamp.py's contract."""
    is_dry_run = any(a in ("--dry-run", "--simulate") for a in sys.argv[1:])
    try:
        raw = sys.stdin.read() if not sys.stdin.isatty() else ""
        if not raw.strip():
            return {}, is_dry_run
        payload = json.loads(raw)
        return (payload if isinstance(payload, dict) else {}), is_dry_run
    except Exception:
        return {}, is_dry_run


def main() -> int:
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0
    try:
        if payload.get("tool_name") not in WRITE_TOOL_NAMES:
            if is_dry_run:
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
            return 0
        target, content = _extract(payload.get("tool_input"))
        hit = offending_line(target, content)
        if not hit:
            if is_dry_run:
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
            return 0
        snippet = hit if len(hit) <= 160 else hit[:157] + "..."
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": NOTE.format(snippet=snippet),
            },
        }
        if not os.environ.get("ANTIGRAVITY_AGENT"):
            out["systemMessage"] = SYSTEM_MESSAGE
        print(json.dumps(out))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
