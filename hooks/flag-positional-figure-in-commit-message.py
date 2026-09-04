#!/usr/bin/env python3
"""PreToolUse guard: a positional figure about text, typed into a commit message, is asserted forever and re-derived by nobody.

"The bullet restated an identical instruction 30 lines above", "a section
defined ~130 lines later", "an entry already sat ~2000 lines below" -- each
locates a passage by counting to it. The count is true at the instant it is
typed and false as soon as anything above it changes, which in a prose corpus
is the next commit. Nothing recomputes it: a commit message is immutable
history, so the figure is never re-derived, never diffed, never linted, and
never contradicted by a failing check. It simply becomes wrong quietly.

`shared/writing/timestamp-volatile-claims.md` names the class -- a claim that
is *true* yet decays into a confident falsehood because it was stated as
timeless fact. `shared/principles/deterministic-tools.md` names why prose
about it does not reach the moment it breaks: the rule is consulted at read
time and broken at composition time. This is the instrument for the
commit-message surface.

THE REMEDY IS USUALLY DELETION, NOT CORRECTION
----------------------------------------------
The reflex on being told a number is stale is to recount and update it. That
is the wrong move here, and saying so is the whole point of the warning. The
figure is decoration: it locates a passage the sentence could simply *name*.
"restated an identical instruction 30 lines above" becomes "restated an
identical instruction in the keep-dispatching-rounds bullet" -- shorter,
unambiguous, and correct for as long as the bullet exists. Naming the target
beats counting to it, and a corrected count is merely a fresher instance of
the same defect.

THE MEASUREMENT (this repository's own history, re-derived 2026-09-03)
----------------------------------------------------------------------
    git log --format='%H%x00%B%x00---END---'

piped to a scan for

    ~?\\b\\d+\\s+(?:lines?|characters?|chars?|words?)\\s+(?:above|below|earlier|later)\\b

matched **14 occurrences across 13 commit messages**, out of roughly 2400
scanned (2412 on `origin/main` as of 2026-09-03; the denominator moves with
every commit, so read it as dated rather than fixed). Every one is the target
shape -- a decorative figure locating a passage -- and there is not a single
legitimate code-move description among them, which is what makes the pattern
safe to warn on. Samples: `4e1dea144` ("the section 13 lines above it"),
`593d25ccf` ("its own sibling 39 lines below"), `fcb4ee10d` ("says, 77 lines
earlier at L186"), `f2f706fa1` ("a section defined ~130 lines later"),
`60edf4c1e` ("already sat ~2000 lines below").

Two properties of the corpus the regex has to respect:

  * The corpus wraps its commit messages, and it wraps at BOTH gaps.
    `38a0738cc` breaks between the number and the unit ("instruction 30\\n
    lines above"); `6f5b9dde3` breaks between the unit and the positional
    word ("this file's own remedy 25 lines\\n   above"). So both gaps are
    `\\s+` rather than a literal space, and that tolerance is what reaches
    exactly 2 of the 13 -- a space-only variant of the same pattern matches
    11.
  * `1385f7b48` writes "~140 lines LATER". No commit in this history is
    reached *only* by `re.IGNORECASE` (that commit carries a second, lowercase
    occurrence), but that occurrence itself is, so the flag stays on: the
    shape is the target whatever its case.

WHAT IT DELIBERATELY DOES NOT MATCH
-----------------------------------
A warn hook nobody trusts gets switched off, so the pattern is narrow on
purpose:

  * A bare count of changed lines or files -- "3 files changed",
    "2 insertions". That is a fact about the diff, derived by git itself.
  * A `\\d+-to-\\d+ range`. An earlier draft carried that arm; it matched
    exactly one commit in the whole history, `0709c1a28`'s "The 60-to-80
    range is human guidance", and that match is a misfire rather than a hit
    -- the sentence states what a style guide asks for, locates no passage,
    and would be destroyed rather than improved by deleting its numbers.
    One measured false positive and zero measured true positives is a losing
    trade for a hook whose only capital is that a fire means something.
  * A bare dimensional count with no positional word: "143 characters",
    "9000 chars". Measured against the same ~2400 commits, `\\b\\d+\\s+
    (?:characters?|chars?|words?)\\b` alone matches **53** commits, and they
    are overwhelmingly legitimate measured facts -- a context budget
    (`b0f279f8e`, `78ab9ed4f`), GitHub's 65536-character comment cap
    (`5dfcb6e74`), a measured line length against a style guide
    (`a2faa9afa`). Warning on those is exactly the noise that costs a hook
    its credibility, so a dimensional figure only matches when it carries a
    positional word.
  * Version numbers, issue and PR numbers (#123), SHAs, dates, times.

MESSAGE EXTRACTION
------------------
Handles `-m "..."` / `-m '...'` (repeated `-m` concatenated as git does),
the attached form `-m"..."`, `--message=...`, `-F <file>` / `--file=<file>`
read off disk, CLUSTERED short flags (`-am`, `-sm`, `-asm`, and `-ams` read
as `-a -m s` exactly as git reads it), leading environment assignments
(`FOO=1 git commit ...`), and global git flags (`-C dir`, `-c k=v`) between
`git` and the subcommand.

The cluster case is not a nicety: `git commit -am "..."` is among the
commonest commit invocations there is, and a token-equality test against
`-m` sees none of it -- so the first draft of this guard was silently blind
on a large fraction of real traffic while every test passed.

The `_ENV` and `_GIT_FLAGS` patterns are COPIED from
`no-unshipped-commit.py`, byte-identical to the definitions there, not
imported from it. The consequence is worth stating rather than leaving to be
discovered: this is a DRY violation, so a fix to either copy does not reach
the other, and a change to how a `git commit` invocation is recognised has
to be made in both places. Copying rather than importing is the local
convention for these two one-line patterns; the sibling hooks that import
(`flag-unmeasured-timestamp.py`'s `_sibling()`) do so for whole functions.

The command word is guarded with `(?![\\w-])`, not `\\b`, for the reason that
file documents at length: a word boundary sits happily between `commit` and
`-`, so `git\\s+commit\\b` matches `git commit-tree` and `git commit-graph
write`, neither of which writes a commit message at all. Both are silent
here.

FAILS SILENT, ALWAYS
--------------------
Every parse failure -- unbalanced quotes, an unreadable `-F` file, a
`-F -` reading stdin, a payload shape this does not recognise -- returns
without output. A commit is the single worst thing for a hook to break, and
the cost of a missed warning is one stale figure in one commit message.

WARNS, never blocks. Emits `hookSpecificOutput.additionalContext` plus a
single-line `systemMessage`; never a `permissionDecision`. Fires once per
distinct (transcript, message, figure) via a `/tmp` sentinel, so a retried
identical commit does not nag twice.

See `hooks/test-flag-positional-figure-in-commit-message.py` for the fixtures.
"""
import hashlib
import json
import os
import re
import shlex
import sys
import tempfile

# `no-unshipped-commit.py`'s own idioms, so the two guards agree on what a
# `git commit` invocation looks like.
_ENV = r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
_GIT_FLAGS = r"(?:-(?:C\s*\S+|c\s*\S+|[a-zA-Z0-9_-]+(?:=\S*)?)\s+|--[a-zA-Z0-9_-]+(?:=\S*)?\s+)*"
COMMIT = re.compile(
    r"(?:^|[;&|\n])\s*" + _ENV + r"git\s+" + _GIT_FLAGS + r"commit(?![\w-])",
    re.MULTILINE,
)

# The measured pattern. BOTH gaps are `\s+` rather than a literal space,
# because the corpus wraps in both places: `38a0738cc` breaks between the
# number and the unit ("instruction 30\n  lines above") and `6f5b9dde3`
# breaks between the unit and the positional word ("remedy 25 lines\n
# above"). `~` is tolerated before the number for "~2000 lines below", and
# the match is case-insensitive for "140 lines LATER".
#
# There is no `\d+-to-\d+ range` arm. It was written for `0709c1a28`'s
# "The 60-to-80 range is human guidance", and that is the arm's ONLY match
# in the whole history -- and it is a misfire, not a hit: the sentence
# states what a style guide asks for, locates no passage, decays on no
# insertion, and deleting the number would destroy it. Zero measured true
# positives against one measured false positive is a losing trade for a
# warn-only hook, whose whole capital is that a fire means something.
RX_POSITIONAL = re.compile(
    r"~?\b\d+ (?:lines?|characters?|chars?|words?)\s+"
    r"(?:above|below|earlier|later)\b",
    re.IGNORECASE,
)

BASH_TOOL_NAMES = ("Bash", "bash", "run_command", "execute_command", "terminal", "shell")

NOTE = (
    "[flag-positional-figure-in-commit-message] This commit message states "
    "\"{figure}\" -- a positional figure about text. A commit message is "
    "permanent history: the count is true at the instant it is typed, false "
    "as soon as anything above it changes, and re-derived by nobody. "
    "Measured on this repository's own history (2026-09-03): 14 occurrences "
    "across 13 of roughly 2400 commit messages carry this shape, and every "
    "one is decoration rather than a code-move description. "
    "THE REMEDY IS USUALLY TO DELETE THE NUMBER, NOT "
    "TO CORRECT IT -- name the target instead of counting to it (\"in the "
    "keep-dispatching-rounds bullet\", not \"30 lines above\"). A recounted "
    "figure is a fresher instance of the same defect. See "
    "shared/writing/timestamp-volatile-claims.md."
)

MESSAGE = (
    "Positional-figure reminder: this commit message says \"{figure}\". "
    "Prefer naming the passage over counting to it -- delete the number "
    "rather than recounting it."
)


def _blank_quotes(text):
    """Replace the inside of quoted strings with spaces, keeping offsets."""
    return re.sub(
        r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'',
        lambda m: m.group(0)[0] + " " * (len(m.group(0)) - 2) + m.group(0)[-1],
        text,
    )


def split_segments(command):
    """Split on shell separators OUTSIDE quotes, preserving each segment's text.

    Quote-aware because a commit message routinely contains `;`, `|`, and
    newlines, and a naive split would cut a message in half and judge the
    fragments.
    """
    blanked = _blank_quotes(command)
    cuts, pos = [], 0
    for m in re.finditer(r"\|\||&&|[;&|\n]", blanked):
        cuts.append(command[pos:m.start()])
        pos = m.end()
    cuts.append(command[pos:])
    return [seg for seg in cuts if seg.strip()]


def _read_file(path, cwd):
    """File contents, or None when unreadable. Never raises."""
    if not path or path == "-":
        return None
    full = path if os.path.isabs(path) else os.path.join(cwd, path)
    try:
        with open(full, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


RX_SHORT_CLUSTER = re.compile(r"-[A-Za-z]+$")


def short_flag_value(tok):
    """(letter, attached_value_or_None) for a short flag carrying a message.

    Covers the plain `-m`, the attached `-m"..."`, and CLUSTERED short flags
    -- `-am`, `-sm`, `-asm` -- which a token-equality test against `-m` misses
    entirely. `git commit -am "..."` is one of the commonest commit
    invocations there is, so that miss is a large silent blind spot rather
    than an edge case.

    The scan walks the cluster and stops at the first value-taking letter
    (`m` or `F`), which is how git itself reads it: anything after that
    letter in the same token is the attached value, so `-ams` is `-a -m s`
    and `-ma` is `-m a` -- neither takes the NEXT token. A value-taking
    letter in final position takes the next token instead.

    Returns None for a token that is not a short-flag cluster (`--message`,
    a path, a `--` terminator) or carries no value-taking letter (`-v`).
    """
    if not tok or tok.startswith("--"):
        return None
    # The ATTACHED form first, because after `shlex` splits it the token is
    # `-mthe note 13 lines above` -- one token carrying spaces, which the
    # cluster pattern below rightly refuses. Checking the cluster first
    # silently lost `-m"..."` entirely.
    if tok[:2] in ("-m", "-F") and len(tok) > 2:
        return tok[1], tok[2:]
    if not RX_SHORT_CLUSTER.match(tok):
        return None
    for i, ch in enumerate(tok[1:], start=1):
        if ch in ("m", "F"):
            return ch, (tok[i + 1:] or None)
    return None


def extract_message(segment, cwd):
    """The commit message text this segment would commit, or None.

    Returns None on any parse failure, per the fail-silent contract.
    """
    try:
        tokens = shlex.split(segment, comments=False, posix=True)
    except ValueError:
        return None
    parts, i = [], 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("--message", "--file"):
            if i + 1 >= len(tokens):
                return None
            value = tokens[i + 1]
            if tok == "--message":
                parts.append(value)
            else:
                text = _read_file(value, cwd)
                if text is None:
                    return None
                parts.append(text)
            i += 2
            continue
        if tok.startswith("--message="):
            parts.append(tok[len("--message="):])
            i += 1
            continue
        if tok.startswith("--file="):
            text = _read_file(tok[len("--file="):], cwd)
            if text is None:
                return None
            parts.append(text)
            i += 1
            continue
        short = short_flag_value(tok)
        if short:
            letter, attached = short
            if attached is not None:
                value, step = attached, 1
            else:
                if i + 1 >= len(tokens):
                    return None
                value, step = tokens[i + 1], 2
            if letter == "m":
                parts.append(value)
            else:
                text = _read_file(value, cwd)
                if text is None:
                    return None
                parts.append(text)
            i += step
            continue
        i += 1
    return "\n\n".join(parts) if parts else None


def positional_figure(command, cwd):
    """The first positional figure in a `git commit` message here, or None."""
    for segment in split_segments(command):
        # A segment begins where a separator ended, so prepend one to satisfy
        # COMMIT's `(?:^|[;&|\n])` anchor without weakening it to a bare `\b`.
        if not COMMIT.search("\n" + segment):
            continue
        message = extract_message(segment, cwd)
        if not message:
            continue
        hit = RX_POSITIONAL.search(message)
        if hit:
            return " ".join(hit.group(0).split())
    return None


def _read_payload():
    """Parse payload from sys.argv (--dry-run / --simulate) or sys.stdin."""
    args = sys.argv[1:]
    is_dry_run = "--dry-run" in args or "--simulate" in args
    if is_dry_run:
        positional = [a for a in args if not a.startswith("-")]
        if positional:
            raw = positional[0].strip()
            if raw.startswith("{") and raw.endswith("}"):
                try:
                    return json.loads(raw), True
                except Exception:
                    pass
            return {"tool_name": "Bash", "tool_input": {"command": raw}}, True
    try:
        payload = json.load(sys.stdin)
        return (payload if isinstance(payload, dict) else {}), is_dry_run
    except Exception:
        return {}, is_dry_run


def main() -> int:
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    if payload.get("tool_name") not in BASH_TOOL_NAMES:
        return 0
    tpath = payload.get("transcript_path") or ""

    try:
        # Inside the try: `os.getcwd()` raises FileNotFoundError when the
        # process's working directory has been deleted -- a traceback and a
        # non-zero exit, which is exactly what "FAILS SILENT, ALWAYS" above
        # promises never to do.
        cwd = payload.get("cwd") or os.getcwd()
        command = (tool_input.get("command") or tool_input.get("CommandLine")
                   or tool_input.get("cmd") or tool_input.get("script"))
        if not isinstance(command, str) or not command.strip():
            return 0
        figure = positional_figure(command, cwd)
        if not figure:
            if is_dry_run:
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
            return 0

        if not is_dry_run:
            key = hashlib.sha256(
                (tpath + "|" + command + "|" + figure).encode()).hexdigest()[:16]
            sentinel = os.path.join(
                tempfile.gettempdir(), f".claude-positional-figure-{key}")
            if os.path.exists(sentinel):
                return 0
            try:
                open(sentinel, "w").close()
            except Exception:
                pass

        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": NOTE.format(figure=figure),
            },
        }
        if not os.environ.get("ANTIGRAVITY_AGENT"):
            out["systemMessage"] = MESSAGE.format(figure=figure)
        print(json.dumps(out))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
