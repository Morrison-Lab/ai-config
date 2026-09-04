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

    \\b\\d+\\s+(?:lines?|characters?|chars?|words?)\\s+(?:above|below|earlier|later)\\b
    |\\b\\d+-to-\\d+\\s+range\\b

matched **14 of 2412 commits** (15 occurrences). Every one is the target
shape -- a decorative figure locating a passage -- and there is not a single
legitimate code-move description among them, which is what makes the pattern
safe to warn on. Samples: `4e1dea144` ("the section 13 lines above it"),
`593d25ccf` ("its own sibling 39 lines below"), `fcb4ee10d` ("says, 77 lines
earlier at L186"), `f2f706fa1` ("a section defined ~130 lines later"),
`60edf4c1e` ("already sat ~2000 lines below"), `0709c1a28` ("the 60-to-80
range is human guidance").

Two properties of the corpus the regex has to respect:

  * `38a0738cc` wraps as "instruction 30\\n  lines above", so the gap between
    the number and the unit must be `\\s+` rather than a literal space. Twelve
    of the fourteen match a space-only pattern; the newline tolerance is what
    reaches the other two.
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
  * A bare dimensional count with no positional word: "143 characters",
    "9000 chars". Measured against the same 2412 commits, `\\b\\d+\\s+
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
`--message=...`, `-F <file>` / `--file=<file>` read off disk, leading
environment assignments (`FOO=1 git commit ...`), and global git flags
(`-C dir`, `-c k=v`) between `git` and the subcommand -- the `_ENV` and
`_GIT_FLAGS` idioms from `no-unshipped-commit.py`, imported rather than
re-derived.

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

# The measured pattern. `\s+` (not a literal space) for the wrapped case;
# `~` tolerated before the number because the corpus writes "~2000 lines
# below"; case-insensitive for "140 lines LATER".
RX_POSITIONAL = re.compile(
    r"~?\b\d+\s+(?:lines?|characters?|chars?|words?)\s+"
    r"(?:above|below|earlier|later)\b"
    r"|\b\d+-to-\d+\s+range\b",
    re.IGNORECASE,
)

BASH_TOOL_NAMES = ("Bash", "bash", "run_command", "execute_command", "terminal", "shell")

NOTE = (
    "[flag-positional-figure-in-commit-message] This commit message states "
    "\"{figure}\" -- a positional figure about text. A commit message is "
    "permanent history: the count is true at the instant it is typed, false "
    "as soon as anything above it changes, and re-derived by nobody. "
    "Measured on this repository's own history (2026-09-03): 14 of 2412 "
    "commits carry this shape and every one is decoration rather than a "
    "code-move description. THE REMEDY IS USUALLY TO DELETE THE NUMBER, NOT "
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
        if tok in ("-m", "--message", "-F", "--file"):
            if i + 1 >= len(tokens):
                return None
            value = tokens[i + 1]
            if tok in ("-m", "--message"):
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
        elif tok.startswith("--file="):
            text = _read_file(tok[len("--file="):], cwd)
            if text is None:
                return None
            parts.append(text)
        elif tok.startswith("-m") and len(tok) > 2 and not tok.startswith("--"):
            parts.append(tok[2:])
        elif tok.startswith("-F") and len(tok) > 2 and not tok.startswith("--"):
            text = _read_file(tok[2:], cwd)
            if text is None:
                return None
            parts.append(text)
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
    cwd = payload.get("cwd") or os.getcwd()
    tpath = payload.get("transcript_path") or ""

    try:
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
