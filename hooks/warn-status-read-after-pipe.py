#!/usr/bin/env python3
"""PreToolUse reminder: `$?` after a pipeline is the pipe's status.

Without `pipefail`, a pipeline's exit status is its RIGHTMOST command's, so
`cmd | head -20; echo "exit=$?"` reports whether `head` succeeded. `head`
succeeds on any input, including none. The status of the thing you actually ran
is discarded one character earlier, and nothing in the output says so.

WHY A GUARD RATHER THAN ANOTHER PROSE SITE
------------------------------------------
Not because the corpus lacked the rule. It had it, exactly, with `head` named:
`shared/coding/errexit-is-not-uniform.md:430` reads "**Don't:** pipe a
verification check into `tail` or `head` for readability while its exit status
is still gating what runs next", and its case record two lines later is a
near-identical 2026-08-03 incident (markdownlint piped to `tail`, `tail` exited
0, the chain reported every check passing).

So the honest account is that a correct, specific rule was not consulted, and
a fourth prose site would not have been either. That is what makes this
decidable-from-one-artifact condition worth a guard instead: the failure
happens at COMPOSITION time, when the pipe is added as a formatting decision
about output length and the exit status is not in view at all.

WHY IT WARNS RATHER THAN BLOCKS
-------------------------------
Reading a pipeline's status is legitimate under `pipefail`, and legitimate
whenever the author wants the rightmost command's status --- `grep -c ... |
tail -1` is a real thing to want. The shape is suggestive, never decisive, so
this only ever ADDS context. There is no code path that denies, escalates, or
auto-approves; it never emits `permissionDecision`, whose absence defers to the
normal permission flow.

WHAT IT ANCHORS ON
------------------
Structure, not vocabulary. This corpus quotes shell snippets constantly ---
including inside the fragments describing this bug --- so a substring matcher
for `$?` would fire on documentation. Two structural rules keep it off prose:

  * A `$?` inside SINGLE quotes is literal to the shell, so it is never a
    status read. That covers every `bash -c '... | tail; echo "rc=$?"'` this
    corpus writes to demonstrate the bug, and it is a deliberate
    under-approximation: someone genuinely running `bash -c` with a pipe
    inside gets no warning. Warn-not-block makes that the cheap direction.
  * A heredoc BODY is content being written, not a value consumed, so bodies
    are stripped regardless of delimiter quoting.

A `$?` in DOUBLE quotes does expand, and is exactly the observed bug
(`echo "exit=$?"`), so those are scanned. `${?}` is the same read spelled
differently and is scanned too.

WHAT IS NOT A PIPE
------------------
Several constructs put a `|` in a command string without creating a pipeline
whose status `$?` reports, and each was measured against bash rather than
reasoned about:

  * `<(...)` and `>(...)` process substitution --- a separate process, so
    `diff <(a|cat) <(b|cat); echo $?` reports `diff`'s status.
  * `$(...)` used as an ARGUMENT, where the outer command's status wins:
    `echo "$(a|b)"; echo $?` is `echo`'s.
  * `[[ ... ]]`, where `|` is regex alternation: `[[ $x =~ ^(a|b)$ ]]`.
  * `$(( ... ))` arithmetic.
  * `>|`, the noclobber-override redirect.
  * `||`, which is a separator.
  * A comment, `# ...`, which is prose and the third such surface after single
    quotes and heredoc bodies. A comment correctly explaining this bug
    otherwise trips the guard enforcing it.

Two neighbours of those are NOT excluded, because bash reads them as the
pipeline's own status, which makes them instances of the bug rather than
exceptions to it:

  * `$(...)` on the right of an ASSIGNMENT. Measured,
    `out=$(grep -q zzz /dev/null | cat); echo $?` gives 0 while the real
    command exited 1, and `set -o pipefail` flips it to 1 --- and `pipefail`
    changing the answer is exactly what proves the status is the pipeline's.
  * A bare subshell, `( cmd | head ); echo $?`.

Paren contexts are tracked on a STACK rather than a counter, since a bare
group nested inside a substitution otherwise decrements the wrong thing and
leaves an unbalanced `)` in the reported pipeline. Separators inside any paren
group belong to that group's own command list and do not end the outer
segment.

And `&` is a segment separator ONLY when it is not part of a redirect. `2>&1`,
`1>&2`, `>&2`, `&>out` and `|&` all contain `&` and none of them ends a
command. Getting this wrong garbled the diagnostic on the very command this
guard was built for, which reported a phantom pipeline of `1 | head -20` --- the
`1` being the tail of `2>&1`.

A line ending in a trailing `|` continues its pipeline onto the next line, so
that newline does not split a segment. Piping across lines is ordinary
formatting for a long command.

THE NEGATIVE CONTROL, AND WHAT IT IS WORTH
------------------------------------------
A matcher that fires on nothing and a matcher that never ran leave the same
evidence, so the rate was measured. An earlier figure quoted here did not
reproduce for a reviewer, so the METHOD is stated rather than the trees:

  * files --- `git ls-files 'shared/*.md' 'memories/*.md' 'skills/*.md'
    CLAUDE.md AGENTS.md README.md` (tracked files only)
  * blocks --- the regions between lines whose first three characters are
    three backticks at column 0; the fence lines are not part of a block
  * run 2026-08-24 at this branch's HEAD

        files examined                      : 356
        fenced blocks                       : 645
          discriminating ($? AND | present) :   8
          fired                             :   2

Report the middle number, not the first. Only 8 of the 645 could fire under ANY
implementation, so a matcher firing on every block containing both would still
score "645 examined, 8 fired" --- the other 637 are padding, and quoting them
as specificity is the zero-matrix problem
`shared/workflow/batch-merge-and-resolve.md` names.

Both hits are genuine: the `|| rc=$?` capture idiom at
`shared/coding/errexit-is-not-uniform.md`, which that fragment's own detector
list says to flag, and the incident command quoted in
`shared/workflow/algorithmatize-checks.md`.

**An earlier run of this control scored 3, and the third was a FALSE
POSITIVE** --- `shared/principles/fail-fast.md`'s
`echo "hits: $(wc -l < out.txt) (rc=$?)"`, whose `$?` is `wc`'s and whose own
inline comment says so. It was reported as a true positive here for a full
review round, because the docstring quoted the block's first line rather than
the line holding the read. That is this file's own subject arriving one level
up: a measurement published without re-deriving what it counted. The
double-quote branch now tracks substitutions, which is what fixed it.

The control's real limitation is the artifact class. This guard runs on Bash
TOOL COMMANDS and the control measured MARKDOWN BLOCKS, and the two differ
systematically along the axis the scanner excludes by design, since prose is
dense in single-quoted `bash -c '...'` demonstrations. So it bounds the
documentation-noise risk and says little about the live false-positive rate.

THE POSITIONAL RULE
-------------------
`$?` holds the status of the last command that finished, so the guard fires
only when the segment IMMEDIATELY BEFORE the one holding the `$?` is a
pipeline. That keeps `cmd | head; other_command; echo $?` quiet, where `$?` is
`other_command`'s and reading it is correct.

WHAT IT CANNOT SEE, IN BOTH DIRECTIONS
--------------------------------------
The scanner is lexical by design, so anything needing a real shell parse is out
of reach. The limits are enumerated as `KNOWN_LIMITS` in the test suite, where
each one is EXERCISED against bash rather than merely described --- and the
suite fails if a listed limit is no longer real, so the list cannot rot.

Misses (a real bug, no warning):

  * a pipeline inside a compound statement --- `for`, `if`, `case`, `{ ... }`
    --- whose terminator becomes the immediate predecessor;
  * a read inside the group that holds the pipe, `( cmd | head; echo $? )`;
  * a read nested in a substitution, `echo $(echo $?)`;
  * a top-level backgrounded `set -o pipefail &`, the mirror of the in-paren
    case the guard does handle;
  * an assignment substitution containing a nested `$(` or `$((`, or preceded
    by a second assignment, or followed by an `&>` redirect.

False positives (a warning where the read is correct):

  * `pipefail` set in a BRACE group, which is not scope-tracked the way a
    paren group is;
  * `pipefail` set inside a compound statement within a paren group.

Misses are the cheap direction for a warn-only guard, which is why the fixes
have consistently tightened toward them. The two false positives are recorded
rather than fixed because both need the same shell parse the scanner avoids.

WHY THE LIMITS ARE MEASURED RATHER THAN ARGUED
----------------------------------------------
Three review rounds running, the fix for one round's finding produced the next
round's finding, every time inside the `pipefail`-scope machinery. That
recurrence is what `shared/principles/deterministic-tools.md` says to answer
with an instrument instead of more care, so the suite carries a DIFFERENTIAL
ORACLE: for each shape it runs bash twice, once plainly and once under
`set -o pipefail`, and treats a change in the printed status as proof that
`$?` was reading a pipeline. The guard's verdict is compared against that.
It reports how many shapes it examined alongside how many agreed, so a run
that examined nothing is distinguishable from a run that found nothing.

THE INCIDENT
------------
2026-08-24, driving `UCD-SERG/ucd-serg.github.io#111`:

    python3 scripts/check-pr-fully-clean.py 111 -R UCD-SERG/ucd-serg.github.io 2>&1 | head -20; echo "exit=$?"

reported `exit=0`. The checker's real exit was 1, and a PR's cleanliness was
reasoned from the wrong number. Tracked as ai-config#2149.
"""

import json
import re
import sys

# `<<WORD`, `<<'WORD'`, `<<-"WORD"`; then the rest of the opener line, which may
# carry a redirect or a pipe on either side of the opener; then the body up to a
# terminator that `<<-` allows to be tab-indented.
#
# Borrowed from hooks/warn-dupe-check-chained-to-create.py, where the same
# pattern carries its own review history. Group 2 is the opener line's tail,
# which is still live shell and is kept; the body is dropped.
RX_HEREDOC = re.compile(
    r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?([^\n]*)\n"
    r".*?\n[ \t]*\1\b",
    re.DOTALL,
)

# `set -o pipefail`, `set -euo pipefail`, `set -eo pipefail`. Anchored to a
# COMMAND POSITION -- start of segment, or just after a separator or an
# opening paren -- so only a real `set` command counts. Merely naming the
# option must not disarm the guard, and this corpus names it constantly:
# `grep -rn pipefail hooks/ | head -20; echo $?` carries no `set` token at a
# command position and stays armed.
#
# The paren alternative is load-bearing rather than tidiness. Separators inside
# a paren group do not cut a segment, so `( set -o pipefail; cmd | head )`
# keeps its `set` inside the PIPELINE's own segment rather than an earlier one.
# Measured, that subshell gives rc=1, so `pipefail` is genuinely in force and a
# warning there would be false.
RX_SET_PIPEFAIL = re.compile(
    r"^\s*set\b[^;&|\n]*\bpipefail\b" + r"(?!\s*&(?![&>]))"
)

# `set -o pipefail` at a command position inside a paren group. A segment-wide
# search cannot do this job: `(set -o pipefail; make) | tail -20; echo $?`
# carries the option in the segment while the pipe sits OUTSIDE the subshell,
# and that is a real misread (measured 0 without an outer `pipefail`, 1 with
# one). So the search is bounded to the group, by `_paren_sets_pipefail`.
#
# It must NOT be restricted to the group's first command, which an earlier
# version did: `( true; set -o pipefail; cmd | head )` measures rc=1, so the
# option really is in force and warning there was false.
# The trailing lookahead matters: `set -o pipefail &` backgrounds the `set`
# into a subshell, so the option never reaches the caller. Measured,
# `( set -o pipefail & grep -q zzz /dev/null | cat ); echo $?` gives 0.
#
# It must distinguish a lone `&` from `&&` and `&>`, which do NOT background:
# `( cd /tmp && set -o pipefail && cmd | cat )` and
# `( set -o pipefail &>/dev/null; cmd | cat )` both measure rc=1, so the
# option is in force and warning there is false. A bare `(?!\s*&)` refused
# both.
RX_TRAILING_BACKGROUND = r"(?!\s*&(?![&>]))"
RX_PAREN_PIPEFAIL = re.compile(
    r"(?:^|[;&\n]\s*)\s*set\b[^;&|\n]*\bpipefail\b" + RX_TRAILING_BACKGROUND
)


def _paren_sets_pipefail(text, open_index):
    """True when the group opening at `open_index` sets `pipefail` ITSELF.

    Walks the group's OWN command level: quoted spans and nested `( ... )`
    groups are skipped whole, and the walk stops at this group's own `)`.

    Skipping a nested group rather than searching it is what keeps a child's
    option from protecting the parent --- measured,
    `( ( set -o pipefail ); cmd | head )` gives rc=0 while
    `( set -o pipefail; cmd | head )` gives rc=1.

    An earlier version stopped the scan at the first `(` OR `)` of any kind,
    which truncated before the group's own `set` whenever anything
    paren-bearing preceded it. That produced a false positive on an idiomatic
    line: `( cd "$(dirname /tmp/x)"; set -o pipefail; make | tail -20 )`
    measures rc=1, so the read is correct, and the guard warned anyway.
    """
    limit = len(text)
    index = open_index + 1
    own = []
    quote = ""
    while index < limit:
        char = text[index]
        if quote:
            if char == "\\" and quote == '"':
                index += 2
                continue
            if char == quote:
                quote = ""
            index += 1
            continue
        if char == "\\":
            index += 2
            continue
        # The main scanner skips comments; this walker must too. A group's
        # internal comment carrying an odd number of quotes otherwise put the
        # walker into quote mode and swallowed the rest of the group, and one
        # carrying an unbalanced paren truncated it --- either way losing a
        # real `set -o pipefail` and warning on a protected pipe.
        if char == "#" and (index == 0 or text[index - 1] in " \t\n;&|("):
            newline = text.find("\n", index)
            index = limit if newline == -1 else newline
            continue
        if char in ("'", '"'):
            quote = char
            own.append(" ")
            index += 1
            continue
        if char == "(":
            end = _matching_paren(text, index)
            if end >= limit:
                return False
            own.append(" ")
            index = end + 1
            continue
        if char == ")":
            break
        own.append(char)
        index += 1
    # Searched over a rebuilt string rather than via pos/endpos: in
    # `pattern.search(s, pos)` the `^` anchor still matches only at the real
    # start of `s`, so the start-of-group alternative would never fire.
    return RX_PAREN_PIPEFAIL.search("".join(own)) is not None

# A real `${PIPESTATUS[0]}` / `$PIPESTATUS` expansion, not the bare word. The
# author reading a specific stage by index is taking control of the pipeline's
# status; `echo PIPESTATUS` is not.
RX_PIPESTATUS = re.compile(r"\$\{?PIPESTATUS\b")

# Quoted spans, stripped before testing for a `set` command so that a QUOTED
# mention -- `grep -rn "set -o pipefail" hooks/` -- cannot pass for one.
RX_QUOTED = re.compile(r"'[^']*'|\"(?:\\[\s\S]|[^\"\\])*\"")

MAXLEN = 90

NOTE = """\
A `$?` read directly follows a pipeline, and no `pipefail` is in force.

    pipeline:  {pipeline}
    reads $?:  {read}

Without `set -o pipefail`, a pipeline's exit status is its RIGHTMOST command's.
A trailing `head`, `tail` or `jq` added purely to shorten output usually
succeeds whatever the real command did, so `$?` here reports the formatter's
status while the one you wanted is already gone. The number that prints is
indistinguishable from a correct reading.

Prefer taking the status BEFORE the pipe:

    cmd >/tmp/out.txt 2>&1; rc=$?; head -20 /tmp/out.txt   # status, then trim
    cmd | head -20; rc=${{PIPESTATUS[0]}}                   # the stage you meant

`set -o pipefail;` also fixes the read, but do not reach for it first here.
`shared/coding/errexit-is-not-uniform.md` warns that a producer piped to `head`
gets SIGPIPEd once `head` has read enough, which `pipefail` turns into a false
FAILURE --- measured, `set -o pipefail; seq 1 200000 | head -20` gives rc=141.
It is the right remedy for a script whose every stage must succeed, and the
wrong one for a long output deliberately truncated.

If you genuinely want the last stage's status --- `grep -c ... | tail -1` ---
carry on. This is a reminder, not a refusal.
"""


def strip_heredoc_bodies(command):
    """Drop heredoc bodies, keeping each opener line's tail.

    Only removes text, and never inserts a separator, so it cannot manufacture
    a segment boundary that was not already there.
    """
    return RX_HEREDOC.sub(lambda m: m.group(2), command)


def _last_significant(text, upto):
    """The last non-whitespace character before `upto`, or ''."""
    index = upto - 1
    while index >= 0 and text[index] in " \t":
        index -= 1
    return text[index] if index >= 0 else ""


# A plain assignment immediately before a `$(`. An assignment takes the
# substitution's OWN status, so `out=$(cmd | head -1); echo $?` reads the
# pipeline and is a genuine instance of this bug. Measured:
#   out=$(grep -q zzz /dev/null | cat); echo $?               -> 0  (cat's)
#   set -o pipefail; out=$(... | cat); echo $?                -> 1
# `pipefail` flipping the answer is what proves it is the pipeline's status.
#
# `local`, `export`, `declare` and `readonly` are deliberately NOT here. They
# are COMMANDS, so `$?` is the builtin's status and `pipefail` does not flip
# it --- measured, `export OUT=$(... | cat); echo $?` gives 0 with and without
# `pipefail`. An earlier version admitted them, which made the guard fire
# while asserting a mechanism that was not operating and offering two remedies
# that measurably do not work.
RX_ASSIGN_PREFIX = re.compile(
    r"^\s*[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]*\])?\+?=$"
)

# The assignment must be the WHOLE segment. Used as a command PREFIX ---
# `V=$(echo x | grep -q zzz) true; echo $?` --- the following command's status
# wins instead, measured at 0 for `true`. Trailing redirects are allowed,
# since they do not change whose status `$?` reports.
#
# The `.*` is greedy and `re.DOTALL`, so it happily spans a SECOND assignment:
# `out=$(cmd | head -1) other=$(true)` matched, and there the last
# substitution owns the status while the pipeline does not. The caller
# therefore also requires the segment to contain exactly one `$(`.
RX_WHOLE_ASSIGN = re.compile(
    r"^\s*[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]*\])?\+?=\$\(.*\)"
    r"(?:\s*\d?[<>]{1,2}\s*\S+)*\s*$",
    re.DOTALL,
)


def _matching_paren(text, open_index):
    """Index of the `)` closing the `(` at `open_index`, or len(text).

    Tracks nesting and quoting well enough to skip a substitution whole. Used
    so a command substitution the guard does not need to look inside is
    stepped over in one move rather than scanned.
    """
    depth = 0
    quote = ""
    index = open_index
    limit = len(text)
    while index < limit:
        char = text[index]
        if quote:
            if char == "\\" and quote == '"':
                index += 2
                continue
            if char == quote:
                quote = ""
            index += 1
            continue
        # An escaped character outside quotes is literal. Missing this let
        # `$(printf %s \')` open a phantom single-quoted span that ran to the
        # end of the command, and since the caller jumped past the returned
        # index, the ENTIRE rest of the command went unscanned.
        if char == "\\":
            index += 2
            continue
        # A `#` comment inside the substitution can hold an unbalanced paren
        # either way, so skip it rather than counting its characters.
        if char == "#" and (index == 0 or text[index - 1] in " \t\n;&|("):
            newline = text.find("\n", index)
            index = limit if newline == -1 else newline
            continue
        if char in ("'", '"'):
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return limit


def scan(command):
    """Split into segments and locate expandable `$?` reads.

    Returns (segments, reads):
      segments -- list of {"text": str, "has_pipe": bool}, empties dropped
      reads    -- list of {"seg": int}, one per `$?` or `${?}` the shell would
                  expand, mapped onto the surviving segment list

    Reads are collected by absolute offset and mapped to segments afterwards,
    so dropping empty segments cannot shift a read onto the wrong one.
    """
    text = command
    bounds = []          # (start, end, plain_pipe, assign_pipe) per raw segment
    offsets = []         # absolute offset of each expandable `$?`
    comments = []        # (start, end) of each comment span, blanked later
    closes = []          # offset at which each command substitution CLOSED
    start = 0
    pipe_plain = False   # a pipe at top level of this segment
    pipe_assign = False  # a pipe inside an assignment's `$( ... )`
    quote = ""
    # A STACK rather than a counter, so a bare `( ... )` nested inside a
    # `$( ... )` cannot decrement the wrong thing. Entries are "hide" for a
    # context whose `|` is not a readable pipeline status (`<(`, `>(`, and a
    # `$(` used as an argument) and "show" for one whose status IS read (a
    # bare subshell, and a `$(` on the right of an assignment). Counting these
    # together desynchronized on the first nested group and produced a
    # false positive naming an unbalanced `)`.
    parens = []
    # Parallel to `parens`: whether that group opened with `set -o pipefail`,
    # so a pipe inside it is genuinely protected.
    paren_pf = []
    # Nesting of `[[ ... ]]`, where `|` is regex alternation.
    condition = 0
    i = 0
    n = len(text)

    def hidden():
        return "hide" in parens

    def cut(end, skip):
        nonlocal start, pipe_plain, pipe_assign, i, condition
        bounds.append((start, end, pipe_plain, pipe_assign))
        pipe_plain = False
        pipe_assign = False
        # A command separator ends any unterminated `[[`, so a stray one
        # cannot disable pipe detection for the rest of the string.
        condition = 0
        i = end + skip
        start = i

    while i < n:
        char = text[i]

        if quote == "'":
            # Inside single quotes only the closing quote is special; a
            # backslash is literal, matching the shell.
            if char == "'":
                quote = ""
            i += 1
            continue

        if quote == '"':
            if char == "\\" and i + 1 < n:
                i += 2  # `\$` is a literal dollar
                continue
            if char == '"':
                quote = ""
                i += 1
                continue
            if char == "$" and text[i + 1:i + 2] == "?":
                offsets.append(i)
                i += 2
                continue
            if char == "$" and text[i + 1:i + 3] == "{?" and text[i + 3:i + 4] == "}":
                offsets.append(i)
                i += 4
                continue
            # A command substitution INSIDE double quotes. Skipping it whole
            # matters for what follows it: in
            # `cmd | head -20; echo "n=$(wc -l < f) rc=$?"` the `$?` is
            # `wc`'s, not the pipeline's --- measured,
            # `true | cat; echo "x $(exit 7) (rc=$?)"` prints rc=7.
            # Not tracking this produced the guard's one measured false
            # positive, on `shared/principles/fail-fast.md`'s own example.
            if char == "$" and text[i + 1:i + 2] == "(":
                # `$(( ))` is ARITHMETIC and does not set `$?`, so it must not
                # shadow a following read. Measured:
                #   true | false; echo "n=$((1+1)) rc=$?"   -> rc=1 (pipeline)
                #   true | false; echo "x=$(exit 7) rc=$?"  -> rc=7 (subst)
                # Omitting this carve-out here, while having it in the
                # unquoted branch, silenced a genuine misread for one round.
                if text[i + 2:i + 3] == "(":
                    i += 3
                    continue
                end = _matching_paren(text, i + 1)
                if end >= n:
                    i += 2   # unbalanced: keep scanning rather than give up
                    continue
                closes.append(end)
                i = end + 1
                continue
            i += 1
            continue

        # --- unquoted -------------------------------------------------------
        if char == "\\" and i + 1 < n:
            i += 2  # covers backslash-newline line continuation
            continue
        if char in ("'", '"'):
            quote = char
            i += 1
            continue

        if char == "$" and text[i + 1:i + 2] == "?":
            offsets.append(i)
            i += 2
            continue
        if char == "$" and text[i + 1:i + 4] == "{?}":
            offsets.append(i)
            i += 4
            continue
        # A `#` at a word boundary starts a comment, which runs to end of line.
        # Comments are the third prose surface (after single quotes and heredoc
        # bodies), and the one that bites hardest: a comment CORRECTLY
        # explaining this bug otherwise trips the guard describing it.
        if char == "#" and (i == 0 or text[i - 1] in " \t\n;&|("):
            newline = text.find("\n", i)
            end = n if newline == -1 else newline
            # Recorded so the span can be blanked from the segment body. A
            # comment is not a command and does not set `$?`, so a
            # comment-only segment must not become the "immediate
            # predecessor" and hide a real pipeline behind it.
            comments.append((i, end))
            i = end
            continue

        if char == "$" and text[i + 1:i + 2] == "(":
            # `$((` is arithmetic, not a substitution, and carries no pipe.
            if text[i + 2:i + 3] == "(":
                parens.append("hide")
                parens.append("hide")
                paren_pf.append(False)
                paren_pf.append(False)
                i += 3
                continue
            assigned = RX_ASSIGN_PREFIX.search(text[start:i]) is not None
            if not assigned:
                # Nothing inside is read as this segment's status, and a `$?`
                # AFTER it belongs to the substitution rather than to any
                # earlier pipeline, so step over it whole and record where it
                # closed.
                end = _matching_paren(text, i + 1)
                if end >= len(text):
                    i += 2   # unbalanced: keep scanning rather than give up
                    continue
                closes.append(end)
                i = end + 1
                continue
            parens.append("assign")
            # An assignment's substitution reads the pipeline's status, so a
            # `pipefail` set inside it protects that pipe exactly as it does
            # in a bare subshell. Measured,
            # `x=$(set -o pipefail; grep -q zzz /dev/null | cat); echo $?`
            # gives rc=1. Hard-coding False here warned on it.
            paren_pf.append(_paren_sets_pipefail(text, i + 1))
            i += 2
            continue
        if char in ("<", ">") and text[i + 1:i + 2] == "(":
            parens.append("hide")
            paren_pf.append(False)
            i += 2
            continue
        if text[i:i + 2] == "((":
            # Bare `(( ... ))` arithmetic, where `|` is bitwise OR.
            parens.append("hide")
            parens.append("hide")
            paren_pf.append(False)
            paren_pf.append(False)
            i += 2
            continue
        if char == "(":
            # Extglob -- `@(a|b)`, `!(keep|also)`, `?(x|y)`, `*(...)`,
            # `+(...)` -- where `|` is pattern alternation rather than a pipe.
            if _last_significant(text, i) in ("@", "!", "?", "*", "+"):
                parens.append("hide")
                paren_pf.append(False)
                i += 1
                continue
            # A bare subshell's status IS its last command's, so a pipeline
            # inside one is read exactly as a top-level pipeline would be.
            parens.append("show")
            # `pipefail` set anywhere at this group's own command level covers
            # pipes inside the group, and only those.
            paren_pf.append(_paren_sets_pipefail(text, i))
            i += 1
            continue
        if char == ")" and parens:
            # `parens` and `paren_pf` are pushed and popped together at every
            # site, so their lengths are equal by construction. Popping both
            # unconditionally keeps a violated invariant loud rather than
            # silently absorbed, per shared/principles/fail-fast.md.
            parens.pop()
            paren_pf.pop()
            i += 1
            continue
        if text[i:i + 2] == "[[":
            condition += 1
            i += 2
            continue
        if text[i:i + 2] == "]]" and condition:
            condition -= 1
            i += 2
            continue

        two = text[i:i + 2]

        # Inside any paren group a separator belongs to that group's internal
        # command list, not to the outer one. Splitting there let a `;` inside
        # `<( ... )` end the outer segment and expose the group's tail --- and
        # an unbalanced `)` with it --- at top level.
        if parens:
            if two in ("&&", "||"):
                i += 2
                continue
            if char in ("&", ";", "\n"):
                i += 1
                continue

        if two in ("&&", "||"):
            cut(i, 2)
            continue

        if char == "&":
            previous = _last_significant(text, i)
            # `2>&1`, `>&2`, `1>&2` -- fd duplication, not a separator.
            if previous in ("<", ">"):
                i += 1
                continue
            # `&>file`, `&>>file` -- redirect of both streams.
            if text[i + 1:i + 2] == ">":
                i += 1
                continue
            # `|&` -- pipe including stderr. The `|` already marked the pipe.
            if previous == "|":
                i += 1
                continue
            # A lone `&` BACKGROUNDS what precedes it, so the `$?` that follows
            # is the async launch's status (0) rather than the pipeline's.
            # Measured: `cmd | head -20 & echo $?` prints 0 whatever `cmd` did.
            # Clearing the flags keeps the guard from asserting something
            # false. Both must be cleared -- an earlier version cleared a
            # single `has_pipe` that a later refactor split in two, which
            # silently reinstated this false positive until a test caught it.
            pipe_plain = False
            pipe_assign = False
            cut(i, 1)
            continue

        if char == ";":
            cut(i, 1)
            continue

        if char == "\n":
            # A trailing `|`, `&&` or `||` continues onto the next line.
            previous = _last_significant(text, i)
            if previous in ("|", "&"):
                i += 1
                continue
            cut(i, 1)
            continue

        if char == "|":
            # `>|` is the noclobber-override redirect, not a pipe.
            if _last_significant(text, i) == ">":
                i += 1
                continue
            if not hidden() and not condition and not any(paren_pf):
                if "assign" in parens:
                    pipe_assign = True
                else:
                    pipe_plain = True
            i += 1
            continue

        i += 1

    bounds.append((start, n, pipe_plain, pipe_assign))

    # Blank comment spans so a comment-only segment reads as empty and gets
    # dropped, rather than standing between a pipeline and the read of it.
    body_text = list(text)
    for begin, end in comments:
        for position in range(begin, end):
            body_text[position] = " "
    body_text = "".join(body_text)

    segments = []
    spans = []
    for begin, end, plain, assigned in bounds:
        body = body_text[begin:end].strip()
        if not body:
            continue  # an empty or comment-only segment is not a command
        # An assignment's substitution only owns the status when the
        # assignment IS the segment; used as a command prefix, the following
        # command's status wins.
        piped = plain or (assigned
                          and body.count("$(") == 1
                          and RX_WHOLE_ASSIGN.match(body) is not None)
        segments.append({"text": body, "has_pipe": piped})
        spans.append((begin, end))

    reads = []
    for offset in offsets:
        for index, (begin, end) in enumerate(spans):
            if begin <= offset < end:
                # A command substitution that CLOSED earlier in this segment
                # owns the status, so a `$?` after it is not reading any
                # pipeline. Measured: `true | cat; echo "x $(exit 7) (rc=$?)"`
                # prints rc=7.
                shadowed = any(begin <= close < offset for close in closes)
                if not shadowed:
                    reads.append({"seg": index})
                break
    return segments, reads


def truncate(text):
    text = " ".join(text.split())
    return text if len(text) <= MAXLEN else text[:MAXLEN - 3] + "..."


def find_misread(command):
    """Return (pipeline_text, read_text) for the earliest offending pair.

    Fires when an expandable `$?` sits in a segment whose IMMEDIATE predecessor
    is a pipeline, `set ... pipefail` appears in no segment before that
    pipeline, and `PIPESTATUS` appears neither before it nor in the reading
    segment. Returns None otherwise.
    """
    segments, reads = scan(strip_heredoc_bodies(command))

    for read in reads:
        index = read["seg"]
        if index == 0 or index >= len(segments):
            continue
        previous = segments[index - 1]
        if not previous["has_pipe"]:
            continue

        # `set` must OPEN the segment. That anchor is what does the work here,
        # measured: without it, `( set -o pipefail; true ); cmd | head; echo $?`
        # goes quiet, and that is a real misread (0 without an outer
        # `pipefail`, 1 with one) because the option is scoped to a subshell
        # the pipe is not in.
        #
        # The slice stops one short of the pipeline for the same reason, and
        # is belt-and-braces rather than load-bearing: no input is known that
        # `segments[:index]` would decide differently, since a `set` sharing a
        # segment with the pipeline is necessarily inside parens, and that
        # case is decided by the per-group `paren_pf` scope in scan() instead.
        preceding = segments[:index - 1]
        if any(RX_SET_PIPEFAIL.search(RX_QUOTED.sub(" ", s["text"]))
               for s in preceding):
            continue
        # `PIPESTATUS` is checked ONLY in the reading segment. An earlier
        # segment reading it refers to some earlier pipeline and says nothing
        # about this one, so scanning the prefix let `rc=${PIPESTATUS[0]};
        # cmd | head -20; echo $?` disarm itself.
        if RX_PIPESTATUS.search(segments[index]["text"]):
            continue

        return truncate(previous["text"]), truncate(segments[index]["text"])
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:  # fail open, but say so
        print(f"warn-status-read-after-pipe: unreadable hook input ({exc})",
              file=sys.stderr)
        return 0

    if not isinstance(payload, dict):
        print("warn-status-read-after-pipe: hook input was not an object",
              file=sys.stderr)
        return 0

    if payload.get("tool_name") not in ("Bash", "bash", "run_command"):
        return 0

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    command = (tool_input.get("command")
               or tool_input.get("cmd")
               or tool_input.get("CommandLine")
               or "")
    if not isinstance(command, str) or not command.strip():
        return 0

    try:
        hit = find_misread(command)
    except Exception as exc:  # fail open on any parse trouble
        print(f"warn-status-read-after-pipe: could not evaluate ({exc})",
              file=sys.stderr)
        return 0

    if hit is None:
        return 0

    pipeline, read = hit

    # No `permissionDecision` key at all: an absent decision defers to the
    # normal permission flow. Naming "allow" would suppress a prompt the user
    # would otherwise have seen.
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": NOTE.format(pipeline=pipeline, read=read),
        },
        "systemMessage": (
            f"`{read}` reads the status of `{pipeline}`'s LAST stage, not the "
            "command's. Take the status before the pipe, or read "
            "${PIPESTATUS[0]}."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
