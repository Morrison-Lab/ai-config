#!/usr/bin/env python3
"""PreToolUse guard: a content move committed with no inbound-link sweep.

When prose moves from one file to another, the files that cited the **source**
for that content are left pointing at a file which no longer contains it.

Nothing else in this repo sees that. The link still resolves, to a file that
still exists, so `check-links.py` is green. A phrase search over the moved
content finds only the citing sites that quote it verbatim, and misses every
one that paraphrases, or that cites the file for a claim it states in its own
words. And `shared/writing/reorganize-prose.md`'s older sweep bullet covers the
moved block and the survivor left behind -- both searches over *text that
moved*, so both are structurally blind to this direction.

The reader who follows such a link lands somewhere real and finds no trace of
what was cited, with no pointer onward. That is worse than a broken link, which
at least announces itself.

## Why this is a hook rather than another sentence

The rule exists. It is in `reorganize-prose.md`, and on the move that prompted
this guard it was *written into that file in the same commit where it was not
run*. A rule is consulted at read time and broken at composition time, and
re-reading it does not reach the moment it breaks. Six stale sites across two
PRs in one day, every one found by a reviewer and none by an instrument
(ai-config#3501).

## Why it warns rather than denies

The failure being fixed is invisibility, and a warning at the moment of the
commit fixes that completely.

It also cannot tell a swept move from one swept in a shape this guard does not
recognize -- a sweep run in an editor, in a previous session, or through a
script whose command line does not name the basename. Denying on that would
block correct work with no way to say so. So this only ever ADDS context: there
is no path in it that denies, escalates, or auto-approves, and in particular it
never emits `permissionDecision: "allow"`, which would bypass the normal
permission prompt for the command it is inspecting.

## What it deliberately does not do

It does not judge whether the sweep was any *good*. Enumerating the inbound
links is one grep; deciding, per link, whether the claim still describes
something in the source file is a reading task with no mechanical form. The
guard's job is to make the moment arrive.

It also skips pure renames. A rename takes the whole file with it, so every
inbound link breaks loudly and `check-links.py` already reports them.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys

# A move has to be substantial before it is worth a warning. Measured against
# the two moves that prompted this guard: 496 lines (ai-config#3480) and 137
# (#3499). A threshold this low also catches a moved paragraph, which has the
# same failure mode at smaller scale, while staying clear of the incidental
# overlap two files get from shared boilerplate -- a Do/Don't label, a blank
# line, a fence marker. Those are excluded separately by TRIVIAL below.
MIN_MOVED_LINES = 12

# Lines too common to count as evidence of a move. A file full of `- **Do:**`
# openers would otherwise register as moved into any other file with the same
# convention.
TRIVIAL = re.compile(r"""
    \A \s* (?:
        [-*+]? \s* (?: \*\* )? (?: Do | Don't | Note | Fix | Example ) \b .{0,4} \Z
      | [`~]{3,}  .* \Z
      | \#{1,6} \s* \Z
      | [-|:\s]+ \Z
    )
""", re.VERBOSE)

# `git` options that sit BEFORE the subcommand. The ones listed here take a
# separate value, so the value has to be skipped too or it reads as the
# subcommand -- `git -C /repo commit` would otherwise look like `git /repo`.
GIT_OPTS_WITH_VALUE = {
    "-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path",
    "--config-env",
}

# A repo-wide search naming the source file. `grep -r`, `git grep`, `rg` and
# `ag` all qualify; a plain `grep pattern file` does not, since reading one
# file is not an enumeration of who links to it.
SWEEP_RE = re.compile(r"""
    (?:
        \bgrep\b (?=[^|;&]*\s-[A-Za-z]*[rR])
      | \bgit\s+grep\b
      | \brg\b
      | \bag\b
    )
""", re.VERBOSE)

NOTE = """\
This `git commit` stages a CONTENT MOVE, and no inbound-link sweep for the \
source file appears in this session:

    {n} line(s) moved out of  {src}
    into                      {dst}

Other files that cite `{base}` for the moved content are now pointing at a file \
that no longer contains it. Nothing reports that: the link still resolves, to a \
file that still exists, so `check-links.py` stays green, and a phrase search \
over the moved content only ever finds the citing sites that QUOTE it -- never \
the ones that paraphrase, or that cite the file for a claim stated in their own \
words. The reader who follows one lands somewhere real and finds no trace of \
what was cited.

Enumerate the inbound links, then check each claim against what remains in the \
source file:

    grep -rn '{base}' --include='*.md' .

That list is long in a corpus this size, so narrow it mechanically rather than \
by eye: keep only the citing lines whose surrounding lines share a distinctive \
term with the moved block, then read the survivors. The narrowing is a \
heuristic in both directions -- on the move this guard was written for it \
surfaced two real stale sites and two false positives keyed on wording as \
generic as "default branch" -- so treat its output as a shortlist to read, not \
as the answer.

See `shared/writing/reorganize-prose.md`, "Inbound links to the SOURCE file go \
stale too". This is a reminder, not a refusal.\
"""


def significant(line: str) -> bool:
    """Is this line distinctive enough to count as evidence of a move?"""
    body = line[1:]
    if not body.strip():
        return False
    return not TRIVIAL.match(body)


def staged_diff(cwd: str) -> str:
    """The staged diff, with renames detected so they can be skipped."""
    try:
        out = subprocess.run(
            ["git", "diff", "--cached", "-M", "--no-color"],
            cwd=cwd or None, capture_output=True, text=True, timeout=10)
    except Exception:
        return ""
    return out.stdout if out.returncode == 0 else ""


def moves(diff: str):
    """Yield (src, dst, n) for each cross-file content move in `diff`.

    A move is lines removed from one file that reappear as added lines in
    another. Compared as multisets of whole lines, which is what makes this
    cheap and what keeps it honest: a line reformatted on the way across is not
    counted, so the guard under-reports rather than inventing moves.
    """
    removed: dict[str, set] = {}
    added: dict[str, set] = {}
    path = None
    renamed = set()

    for line in diff.split("\n"):
        if line.startswith("diff --git "):
            path = None
            continue
        if line.startswith("rename from "):
            # Only the SOURCE side is collected. A rename's destination is a
            # new path whose content reads as added, and the pair is skipped
            # by the source check below -- so collecting both sides would add
            # a second condition that no input can distinguish from the first,
            # which is a branch no test could pin.
            renamed.add(line[len("rename from "):].strip())
            continue
        if line.startswith("+++ b/"):
            path = line[6:].strip()
            continue
        if path is None or line.startswith(("+++", "---", "@@")):
            continue
        if line.startswith("-") and significant(line):
            removed.setdefault(path, set()).add(line[1:])
        elif line.startswith("+") and significant(line):
            added.setdefault(path, set()).add(line[1:])

    for src, gone in removed.items():
        if src in renamed:
            continue
        for dst, arrived in added.items():
            if dst == src:
                continue
            n = len(gone & arrived)
            if n >= MIN_MOVED_LINES:
                yield src, dst, n


def swept(transcript: str, basename: str) -> bool:
    """Did a repo-wide search naming `basename` run in this session?"""
    if not transcript or not os.path.isfile(transcript):
        # Unknown, so assume it did. A guard that fires when it cannot see the
        # transcript would fire on every session that hides one.
        return True
    try:
        with open(transcript, errors="ignore") as fh:
            for line in fh:
                if basename not in line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                for cmd in commands(rec):
                    if basename in cmd and SWEEP_RE.search(cmd):
                        return True
    except Exception:
        return True
    return False


def commands(rec) -> list:
    """Every Bash command string in one transcript record."""
    out = []
    msg = rec.get("message") or {}
    content = msg.get("content")
    if not isinstance(content, list):
        return out
    for block in content:
        if not isinstance(block, dict) or block.get("name") != "Bash":
            continue
        args = block.get("input") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                continue
        cmd = (args or {}).get("command")
        if isinstance(cmd, str):
            out.append(cmd)
    return out


def is_commit(command: str) -> bool:
    """Does this command run `git commit`?

    Split on the shell's own statement separators first, so a `git commit`
    buried in a chain is still seen. Then require `git` to be the PROGRAM of
    that statement rather than merely a word in it -- otherwise
    `echo 'run git commit later'` matches, since shlex strips the quotes and
    leaves the words looking exactly like the real thing.
    """
    for part in re.split(r"(?:&&|\|\||[;|\n])", command or ""):
        try:
            words = shlex.split(part, comments=False)
        except ValueError:
            words = part.split()
        if not words:
            continue
        # Step over a leading `env FOO=bar` or an inline assignment.
        i = 0
        while i < len(words) and ("=" in words[i] and not words[i].startswith("-")):
            i += 1
        if i < len(words) and os.path.basename(words[i]) == "env":
            i += 1
            while i < len(words) and "=" in words[i]:
                i += 1
        if i >= len(words) or os.path.basename(words[i]) != "git":
            continue
        i += 1
        # Skip git's own pre-subcommand options, taking their values with them.
        while i < len(words) and words[i].startswith("-"):
            takes_value = words[i] in GIT_OPTS_WITH_VALUE
            i += 1
            if takes_value and i < len(words):
                i += 1
        if i < len(words) and words[i] == "commit":
            return True
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not is_commit(command):
        return 0

    cwd = payload.get("cwd") or os.getcwd()
    diff = staged_diff(cwd)
    if not diff:
        return 0

    transcript = payload.get("transcript_path") or ""
    for src, dst, n in moves(diff):
        base = os.path.basename(src)
        if swept(transcript, base):
            continue
        note = NOTE.format(n=n, src=src, dst=dst, base=base)
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": note,
            },
        }
        if not os.environ.get("ANTIGRAVITY_AGENT"):
            out["systemMessage"] = (
                f"Content move out of {base} with no inbound-link sweep. "
                f"Run: grep -rn '{base}' --include='*.md' ."
            )
        print(json.dumps(out))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
