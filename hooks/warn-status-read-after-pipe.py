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
Four constructs put a `|` in a command string without creating a pipeline whose
status `$?` would report, and each was measured against bash before being
excluded:

  * `<(...)` and `>(...)` process substitution, and `$(...)` command
    substitution --- these run in a separate process, so `diff <(a|cat)
    <(b|cat); echo $?` reports `diff`'s status.
  * `[[ ... ]]`, where `|` is regex alternation: `[[ $x =~ ^(a|b)$ ]]`.
  * `>|`, the noclobber-override redirect.
  * `||`, which is a separator.

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
evidence, so the rate was measured. Method: `find_misread` over every fenced
block in `shared/`, `memories/`, `skills/`, `CLAUDE.md`, `AGENTS.md` and
`README.md`, matching ```` ``` ```` fences of any language tag, on 2026-08-24
at this branch's HEAD.

    all fenced blocks examined          : 774
      discriminating ($? AND | present) :   8
      fired                             :   2

Report the middle number, not the first. Only 8 of the 774 could fire under ANY
implementation, so a matcher firing on every block containing both would still
score "774 examined, 8 fired" --- the other 766 are padding, and quoting them
as specificity is the zero-matrix problem
`shared/workflow/batch-merge-and-resolve.md` names.

Both hits are genuine instances rather than false positives: the `|| rc=$?`
capture idiom at `shared/coding/errexit-is-not-uniform.md`, which that
fragment's own detector list says to flag, and the incident command quoted in
`shared/workflow/algorithmatize-checks.md`.

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

WHAT IT CANNOT SEE
------------------
A pipeline inside a compound statement --- `for`, `if`, `case`, `{ ... }` ---
whose terminator (`done`, `fi`, `esac`, `}`) becomes the immediate predecessor.
Those are real instances of the bug and this guard misses them. The scanner is
lexical by design, and parsing shell compound statements to catch them would
cost more than the miss.

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

# `set -o pipefail`, `set -euo pipefail`, `set -eo pipefail`. Anchored on a
# `set` command rather than on the bare word, so that grepping the corpus FOR
# the word --- `grep -rn pipefail hooks/ | head -20; echo $?` --- does not
# silently disarm the guard on a genuine misread.
RX_SET_PIPEFAIL = re.compile(r"\bset\b[^;&|\n]*\bpipefail\b")

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
    bounds = []          # (start, end, has_pipe) for every raw segment
    offsets = []         # absolute offset of each expandable `$?`
    start = 0
    has_pipe = False
    quote = ""
    # Depth of contexts in which a `|` is not a pipeline: `$(`, `<(`, `>(`.
    subshell = 0
    # Nesting of `[[ ... ]]`, where `|` is regex alternation.
    condition = 0
    i = 0
    n = len(text)

    def cut(end, skip):
        nonlocal start, has_pipe, i
        bounds.append((start, end, has_pipe))
        has_pipe = False
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
        if char == "$" and text[i + 1:i + 2] == "(":
            subshell += 1
            i += 2
            continue
        if char in ("<", ">") and text[i + 1:i + 2] == "(":
            subshell += 1
            i += 2
            continue
        if char == ")" and subshell:
            subshell -= 1
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
            # Clearing the flag keeps the guard from asserting something false.
            has_pipe = False
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
            if not subshell and not condition:
                has_pipe = True
            i += 1
            continue

        i += 1

    bounds.append((start, n, has_pipe))

    segments = []
    spans = []
    for begin, end, piped in bounds:
        body = text[begin:end].strip()
        if not body:
            continue  # an empty segment is punctuation, not a command
        segments.append({"text": body, "has_pipe": piped})
        spans.append((begin, end))

    reads = []
    for offset in offsets:
        for index, (begin, end) in enumerate(spans):
            if begin <= offset < end:
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

        # Segments strictly BEFORE the pipeline. The pipeline itself is
        # excluded on purpose: `grep -rn pipefail hooks/ | head -20; echo $?`
        # merely mentions the word and is a genuine misread.
        preceding = segments[:index - 1]
        if any(RX_SET_PIPEFAIL.search(s["text"]) for s in preceding):
            continue
        if any("PIPESTATUS" in s["text"] for s in preceding):
            continue
        # The author is reading a specific stage by index in the same breath.
        if "PIPESTATUS" in segments[index]["text"]:
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
