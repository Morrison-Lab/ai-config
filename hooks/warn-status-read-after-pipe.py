#!/usr/bin/env python3
"""PreToolUse reminder: `$?` after a pipeline is the pipe's status.

Without `pipefail`, a pipeline's exit status is its RIGHTMOST command's, so
`cmd | head -20; echo "exit=$?"` reports whether `head` succeeded. `head`
almost always succeeds. The status of the thing you actually ran is discarded
one character earlier, and nothing in the output says so.

WHY THIS IS A HOOK RATHER THAN ANOTHER PROSE SITE
-------------------------------------------------
The mechanism is already written down three times over:
`shared/coding/errexit-is-not-uniform.md` measures it in two shapes,
`shared/principles/fail-fast.rationale.md` states that a whole-call status
belongs to the last command in a `;`-sequence or a `pipefail`-less pipeline,
and `shared/workflow/algorithmatize-checks.md` names truncating pipes as
interpretations of an instrument's answer.

All three were loaded and none fired, because the failure happens at
COMPOSITION time. The pipe is added as a formatting decision about output
length, at which moment the exit status is not in view at all.

`algorithmatize-checks.md` states the tell as "a sentence about an instrument
that names no exit status". That tell cannot catch this case, and the gap is
the whole reason for the guard: the offending sentence NAMED an exit status.
It named the wrong command's. A reader sees `exit=0` and has no way to tell it
apart from a real reading.

WHY THIS WARNS RATHER THAN BLOCKS
---------------------------------
Reading a pipeline's status is legitimate under `pipefail`, and legitimate
whenever the author genuinely wants the rightmost command's status --- `grep -c
... | tail -1` is a real thing to want. The shape is suggestive, never
decisive, so this only ever ADDS context. There is no code path that denies,
escalates, or auto-approves; in particular it never emits `permissionDecision`,
whose absence defers to the normal permission flow.

WHAT IT ANCHORS ON
------------------
Structure, not vocabulary. This corpus quotes shell snippets constantly ---
including inside the very fragments that describe this bug --- so a substring
matcher for `$?` would fire on documentation. Two structural rules keep it off
prose:

  * A `$?` inside SINGLE quotes is literal to the shell, so it is never a
    status read. That covers every `bash -c '... | tail; echo "rc=$?"'` this
    corpus writes to demonstrate the bug, and it is a deliberate
    under-approximation: someone genuinely running `bash -c` with a pipe
    inside gets no warning. Warn-not-block makes that the cheap direction.
  * A heredoc BODY is content being written, not a value being consumed, so
    its bodies are stripped before scanning regardless of whether the
    delimiter was quoted. Writing `$?` into a file is not reasoning from a
    misread status.

A `$?` in DOUBLE quotes does expand, and is exactly the observed bug
(`echo "exit=$?"`), so those are scanned.

THE NEGATIVE CONTROL
--------------------
A matcher that fires on nothing and a matcher that never ran leave the same
evidence, so the rate was measured rather than asserted. Running `find_misread`
over every fenced shell block in `shared/`, `memories/`, `skills/`, `CLAUDE.md`
and `AGENTS.md` on 2026-08-24: **705 blocks examined, 1 fired.**

That one is `shared/coding/errexit-is-not-uniform.md`'s
`git diff --cached --name-only | grep -qE '...' || rc=$?`, and it is a true
positive by that fragment's own standard --- its detector list says to "flag
`|| fallback` attached to a pipeline in a script without `pipefail`". The
capture idiom is correct there only because `grep`'s status is the one wanted;
the guard cannot know that, and saying so is the point of a warning.

THE POSITIONAL RULE
-------------------
`$?` holds the status of the last command that finished. So the guard fires
only when the segment IMMEDIATELY BEFORE the one holding the `$?` is a
pipeline. That ordering is what keeps `cmd | head; other_command; echo $?`
quiet: there `$?` is `other_command`'s, and reading it is correct.

Segments are split on unquoted `;`, newline, `&`, `&&` and `||`. A single
unquoted `|` does not split a segment --- it marks it as a pipeline, which is
the property being tested.

THE INCIDENT
------------
2026-08-24, driving `UCD-SERG/ucd-serg.github.io#111`:

    python3 scripts/check-pr-fully-clean.py 111 -R UCD-SERG/ucd-serg.github.io 2>&1 | head -20; echo "exit=$?"

reported `exit=0`. The checker's real exit was 1, and a PR's cleanliness was
reasoned from the wrong number. Tracked as ai-config#2149.

Remedies, in the order `errexit-is-not-uniform.md` prefers them: open the line
with `set -o pipefail;`, or drop the pipe and redirect to a file
(`cmd >/tmp/out.txt 2>&1; rc=$?`), or read `${PIPESTATUS[0]}`.
"""

import json
import re
import sys

# `<<WORD`, `<<'WORD'`, `<<-"WORD"`; then the rest of the opener line, which may
# carry a redirect or a pipe on either side of the opener; then the body up to a
# terminator that `<<-` allows to be tab-indented.
#
# Borrowed verbatim from hooks/warn-dupe-check-chained-to-create.py, where the
# same pattern carries its own review history. Group 2 is the opener line's
# tail, which is still live shell and is kept; the body is dropped.
RX_HEREDOC = re.compile(
    r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?([^\n]*)\n"
    r".*?\n[ \t]*\1\b",
    re.DOTALL,
)

# Separators that END a command segment, longest first so `&&` is not read as
# `&` and `||` is not read as a pipe.
SPLITTERS = ("&&", "||", ";", "\n", "&")

MAXLEN = 90

NOTE = """\
A `$?` read directly follows a pipeline, and no `pipefail` is in force.

    pipeline:  {pipeline}
    reads $?:  {read}

Without `set -o pipefail`, a pipeline's exit status is its RIGHTMOST command's.
A trailing `head`, `tail`, `grep` or `jq` almost always succeeds, so `$?` here
reports the formatter's status and the real command's is already discarded.
The number that gets printed is indistinguishable from a correct reading.

`shared/coding/errexit-is-not-uniform.md` measures this; its preferred remedies
in order:

    set -o pipefail; <pipeline>; echo "rc=$?"     # one word, fixes the line
    cmd >/tmp/out.txt 2>&1; rc=$?; head -20 /tmp/out.txt   # status before trim
    cmd | head -20; rc=${{PIPESTATUS[0]}}          # the stage you meant

If you genuinely want the last stage's status --- `grep -c ... | tail -1` ---
carry on. This is a reminder, not a refusal.
"""


def strip_heredoc_bodies(command):
    """Drop heredoc bodies, keeping each opener line's tail.

    Only removes text, and never inserts a separator, so it cannot manufacture
    a segment boundary that was not already there.
    """
    return RX_HEREDOC.sub(lambda m: m.group(2), command)


def scan(command):
    """Split into segments and locate expandable `$?` reads.

    Returns (segments, reads):
      segments -- list of {"text": str, "has_pipe": bool}
      reads    -- list of {"seg": int} for each `$?` the shell would expand

    Single-quoted spans are traversed without recording reads or pipes, since
    the shell treats both characters as literal inside them.
    """
    segments = []
    reads = []
    start = 0
    has_pipe = False
    quote = ""
    i = 0
    n = len(command)

    while i < n:
        char = command[i]

        if quote == "'":
            # Inside single quotes nothing is special except the closing quote.
            # A backslash is literal here, matching the shell.
            if char == "'":
                quote = ""
            i += 1
            continue

        if quote == '"':
            if char == "\\" and i + 1 < n:
                i += 2  # `\$` is a literal dollar, so skip the pair
                continue
            if char == '"':
                quote = ""
                i += 1
                continue
            if char == "$" and command[i + 1:i + 2] == "?":
                reads.append({"seg": len(segments)})
                i += 2
                continue
            i += 1
            continue

        # Unquoted.
        if char == "\\" and i + 1 < n:
            i += 2
            continue
        if char in ("'", '"'):
            quote = char
            i += 1
            continue
        if char == "$" and command[i + 1:i + 2] == "?":
            reads.append({"seg": len(segments)})
            i += 2
            continue

        two = command[i:i + 2]
        if two in ("&&", "||"):
            segments.append({"text": command[start:i].strip(),
                             "has_pipe": has_pipe})
            has_pipe = False
            i += 2
            start = i
            continue
        if char in (";", "\n", "&"):
            segments.append({"text": command[start:i].strip(),
                             "has_pipe": has_pipe})
            has_pipe = False
            i += 1
            start = i
            continue
        if char == "|":
            # A lone `|` is a pipe; `||` was consumed above.
            has_pipe = True
            i += 1
            continue

        i += 1

    segments.append({"text": command[start:n].strip(), "has_pipe": has_pipe})
    return segments, reads


def truncate(text):
    text = " ".join(text.split())
    return text if len(text) <= MAXLEN else text[:MAXLEN - 3] + "..."


def find_misread(command):
    """Return (pipeline_text, read_text) for the earliest offending pair.

    Fires when an expandable `$?` sits in a segment whose IMMEDIATE predecessor
    is a pipeline, and no `pipefail` or `PIPESTATUS` appears in any earlier
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
        # The author has already taken control of pipeline status: either the
        # option is set, or a specific stage is being read by index.
        earlier = segments[:index]
        if any("pipefail" in s["text"] or "PIPESTATUS" in s["text"]
               for s in earlier):
            continue
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
        return 0  # fail open: the harness always sends an object

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
            "command's. Add `set -o pipefail;`, redirect to a file, or read "
            "${PIPESTATUS[0]}."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
