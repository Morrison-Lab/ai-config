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

  * a read whose argument goes two levels up, directly or through a path
    constructor: `readLines(test_path("..", "..", ...))`,
    `readLines(file.path("..", "..", ...))`, a literal `../../`
  * a read on a quoted path BEGINNING `R/`, `src/` or `inst/`, including the
    `here::here("R", "x.R")` spelling
  * a PATH-THEN-READ chain, which is how Python spells it:
    `Path(...).joinpath("src", "m.py").read_text()`

`test_path`, `file.path`, `here::here` and `pathlib.Path` are path
CONSTRUCTORS rather than reads. They are passthroughs here -- a read must
appear as well -- because listing them fired on `dir.create`, `writeLines`,
`unlink`, `file.exists` and `.mkdir()`.

Lines are continuation-joined before scanning, since the motivating call
wraps at 80 columns under `styler`, and split on `;` afterwards, since a
statement boundary separates an unrelated write from an unrelated read.

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

SIGNAL TO NOISE, MEASURED ON REAL CODE
--------------------------------------
Swept over 1695 test-scoped files across 137 local repositories: ONE fires,
`ucd-serg.github.io/tests/spelling.R`:

    wordlist <- if (file.exists("inst/WORDLIST")) {
      readLines("inst/WORDLIST")
    } else {
      character()
    }

(`tests/spelling.R:10-14`, quoted rather than paraphrased -- an earlier
revision compressed it to one line in the very section whose subject is
measurement fidelity. The hook reports only the `readLines` line, since it
never sees the guard the argument below rests on.)

It is a true positive. An installed package relocates `inst/` contents to
the package root, so `inst/WORDLIST` is absent under `R CMD check` -- and
because the read is guarded by `file.exists()`, the spell check silently falls
back to an empty wordlist and keeps passing while checking nothing.

That measurement replaces an earlier one. The first version of this docstring
claimed a sweep of this repository "fires on ZERO", which was 0 out of 0:
requiring a test DIRECTORY leaves ai-config with no in-scope files at all, so
reverting every other narrowing still yields zero. A detector given no input
reports the same number as a clean one.

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
# R and Python only, matching the read list below. An earlier revision
# admitted fifteen extensions while listing read functions for two, so it
# was inert on JS, Go, Rust and Ruby while implying coverage -- measured:
# `fs.readFileSync("../../src/index.js")` was silent. Extending the gate
# without extending the list is the wrong half to widen.
CODE_EXT = r"(?:R|r|py)"
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
    # `readr` alone is not a function; its real spellings are dotted.
    r"readLines|readRDS|scan|source|open|"
    r"getsource|parse_file|"
    r"read\.csv|read\.table|read\.delim"
)
_DOTTED_READS = (
    r"readr::read_[a-z_]+|xml2::read_[a-z]+|yaml::read_yaml|jsonlite::fromJSON|"
    # `pathlib.Path` and `importlib.resources.files` are CONSTRUCTORS, not
    # reads -- the Python twins of `file.path`. Listing them fired on
    # `.mkdir()`, `.write_text()`, `.rmdir()` and `.exists()`. The
    # path-then-read arm covers their read forms.
    r"inspect\.getsource|"
    # Method forms. These need the dot, so they cannot live in the
    # left-anchored bare list -- an earlier revision put them there and
    # made them unreachable, missing the canonical Python spelling.
    r"\.read_text|\.read_bytes|\.readlines"
)
# `(?<![\w.$])` keeps `normalizePath(` and `monitor_path(` out while letting
# `file.path(` and `test_path(` in -- they are listed above in full.
READ_CALL = r"(?:(?<![\w.$])(?:" + _BARE_READS + r")|(?:" + _DOTTED_READS + r"))\s*\("

# `[^)\n]*` already spans a path CONSTRUCTOR between the read and the path --
# `readLines(file.path("..", "..", x))` -- without treating the constructor
# itself as a read. An earlier revision added an explicit optional group for
# that and it was dead code: deleting it changed nothing.
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
    r"""(?:"""
    r"""["'](?:(?-i:R)|src|inst)/[^"'\n]*["']"""      # "R/x.R"
    r"""|["'](?:(?-i:R)|src|inst)["']\s*,"""           # here::here("R", "x.R")
    r""")""",
    re.I,
)

# Built by concatenation: a triple-single-quote inside a raw string
# terminates it.
_TQ = '"' * 3
_SQ = "'" * 3
# Python method chains put the READ LAST: `Path(...).joinpath("src", "m.py")
# .read_text()`. The arms above all assume read-then-path, so the canonical
# Python spelling needs its own path-then-read arm.
# No bare `.read(`: it matched sockets, HTTP responses, subprocess
# pipes and zipfile members. Only the pathlib spellings, which name a
# filesystem read.
_READ_METHOD = r"\.(?:read_text|read_bytes|readlines)\s*\("
RX_PATH_THEN_READ = re.compile(
    r"(?:"
    r"""\.\./\.\./"""
    r"""|["']\.\.["']\s*,\s*["']\.\.["']"""
    r"""|["'](?:(?-i:R)|src|inst)/"""
    r"""|["'](?:(?-i:R)|src|inst)["']\s*[,)]"""
    # Bounded by DISTANCE, not by parens. A method chain crosses a closing
    # paren by construction -- `joinpath("src", "m.py").read_text()` -- so a
    # paren bound blocks the very shape this arm exists for. An unbounded
    # `[^\n]*` paired an unrelated path with an unrelated read elsewhere on
    # the line; 40 characters admits the chain and not the coincidence.
    r")[^\n]{0,40}?" + _READ_METHOD,
    re.I,
)

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
    # Continuation-joined before scanning. The motivating call is 68 columns
    # plus indentation, so `styler`/`lintr`'s 80-column default wraps it as
    # soon as the file name grows -- and a line-oriented scan is then blind to
    # the exact case this guard exists for. Measured: all three wrapped
    # spellings were silent.
    #
    # A line ending in `(` or `,` is continued, which is how every formatter
    # in scope breaks a call. The joined text keeps the ORIGINAL first line
    # for reporting, so the quoted snippet still points at something the
    # author can find.
    raw = content.splitlines()
    joined, origin = [], []
    buf, first = "", None
    for ln in raw:
        stripped_end = ln.rstrip()
        if first is None:
            first = ln
        buf += (" " if buf else "") + ln.strip()
        if stripped_end.endswith("(") or stripped_end.endswith(","):
            continue
        joined.append(buf)
        origin.append(first)
        buf, first = "", None
    if buf:
        joined.append(buf)
        origin.append(first if first is not None else buf)

    in_docstring = False
    for idx, line in enumerate(joined):
        stripped = line.strip()
        delims = len(RX_DOCSTRING_DELIM.findall(line))
        if in_docstring:
            if delims % 2 == 1:
                in_docstring = False
            continue
        # A read inside a TRAILING comment is still a mention, not a read.
        # Only the leading-marker case was handled, so
        # `x <- 1  # never readLines("R/f.R")` fired.
        line = re.sub(r"(?<![:\w])#.*$|//.*$", "", line)
        if RX_COMMENT.match(line):
            if delims % 2 == 1:
                in_docstring = True
            continue
        if delims % 2 == 1:
            in_docstring = True
        # Split on `;` first: it is a statement boundary in both languages,
        # and the distance-bounded path-then-read arm otherwise pairs a write
        # in one statement with a read in the next --
        # `tmpfile.write_text("src/a"); assert tmpfile.read_text()`.
        if any(RX_ESCAPE_TWO_UP.search(part) or RX_PACKAGE_SRC.search(part)
               or RX_PATH_THEN_READ.search(part)
               for part in line.split(";")):
            # Report the source line the author wrote, not the joined form.
            return (origin[idx] or line).strip()
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
