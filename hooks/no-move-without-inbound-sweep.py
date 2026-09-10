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

Three misses are accepted by construction, and are worth naming so nobody reads
a silent commit as an all-clear:

  - A move whose lines are REFLOWED in transit. Lines are compared whole, so a
    rewrapped paragraph does not match itself. The guard under-reports rather
    than inventing moves.
  - A move SPLIT ACROSS TWO COMMITS -- deleted from the source in one, added to
    the destination in another. Each commit's staged diff is all this guard
    sees, and neither half is a move on its own.
  - A commit issued through a nested shell (`sh -c "git commit ..."`) or
    `xargs`. `is_commit` parses the statement it is given and does not descend
    into a quoted command line, which is a lot of machinery for a shape that
    is rare in practice.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys

# A move has to be substantial before it is worth a warning. Calibrated by
# running `moves()` against the two diffs that prompted this guard, rather than
# from their diffstats -- the two disagree, and the figure that matters is this
# function's own: 409 for ai-config#3480, against that merged commit's diffstat
# of 494 for the moved file (1 insertion, 493 deletions), and 134 for #3499. `moves()` counts DISTINCT significant lines present on both sides,
# so it is always the smaller number, and quoting a diffstat here would describe
# a population this threshold is not measured against.
#
# A threshold this low also catches a moved paragraph, which has the same
# failure mode at smaller scale, while staying clear of the incidental overlap
# two files get from shared boilerplate -- a Do/Don't label, a blank line, a
# fence marker. Those are excluded separately by TRIVIAL below.
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

# Detection is scoped to prose, because the whole rationale is prose citation:
# a memory file or fragment is cited BY NAME from other prose, which is what
# makes a stale citation invisible. Code has no equivalent -- a moved function
# is referenced by import or by symbol, and a mover who breaks one gets an
# ImportError rather than a link that still resolves. Firing on a `.py`-to-`.py`
# refactor would hand the author a warning about "citing sites" and a
# markdown-only remediation command, neither of which fits what moved.
PROSE_SUFFIXES = (".md", ".markdown", ".qmd", ".rmd", ".txt", ".rst")

# `git` options that sit BEFORE the subcommand. The ones listed here take a
# separate value, so the value has to be skipped too or it reads as the
# subcommand -- `git -C /repo commit` would otherwise look like `git /repo`.
GIT_OPTS_WITH_VALUE = {
    "-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path",
    "--config-env",
}

# Programs that search a tree by default, so no recursion flag is needed.
RECURSIVE_BY_DEFAULT = {"rg", "ag", "ack"}

# `grep`'s recursion flags, long form and short. The short forms cluster, so
# `-rn` and `-nr` both count, and a token that merely CONTAINS an r does not:
# `-report.md` is a filename, not a flag cluster.
GREP_RECURSIVE_LONG = {"--recursive", "--dereference-recursive"}


def skip_git_options(words: list, i: int) -> int:
    """Index of the subcommand, stepping over git's pre-subcommand options.

    The options in `GIT_OPTS_WITH_VALUE` take a separate value, so the value
    has to be skipped too -- otherwise `git -C /repo commit` reads as
    `git /repo`.
    """
    while i < len(words) and words[i].startswith("-"):
        takes_value = words[i] in GIT_OPTS_WITH_VALUE
        i += 1
        if takes_value and i < len(words):
            i += 1
    return i


def is_sweep(command: str, basename: str) -> bool:
    """Is this command a repo-wide search naming `basename`?

    Word-parsed rather than pattern-matched. A regex over the raw string gets
    this wrong in both directions, measured: it misses `grep --recursive`
    (the long flag has a second dash where the pattern wants letters) and it
    accepts `grep -n x -report.md` (a dash-prefixed FILENAME read as a
    recursion flag). Both were found by adversarial review of this guard.
    """
    for part in re.split(r"(?:&&|\|\||[;|\n])", command or ""):
        try:
            words = shlex.split(part, comments=False)
        except ValueError:
            words = part.split()
        if not words:
            continue

        if os.path.basename(words[0]) == "git":
            # `git -C <path> grep` is an ordinary shape when working across a
            # worktree, and it is the same pre-subcommand option handling
            # `is_commit` needs, so both call one helper.
            j = skip_git_options(words, 1)
            if j < len(words) and words[j] == "grep":
                program, i = "git grep", j + 1
            else:
                continue
        else:
            program, i = os.path.basename(words[0]), 1

        if program in RECURSIVE_BY_DEFAULT or program == "git grep":
            recursive = True
        elif program == "grep":
            recursive = False
            for w in words[i:]:
                if w == "--":
                    break
                if w in GREP_RECURSIVE_LONG:
                    recursive = True
                    break
                # A short-option cluster: one dash, then letters only. That
                # excludes `--recursive` (handled above) and `-report.md`.
                if (len(w) > 1 and w[0] == "-" and w[1] != "-"
                        and w[1:].isalpha() and ("r" in w[1:] or "R" in w[1:])):
                    recursive = True
                    break
        else:
            continue

        if not recursive:
            continue
        if any(names_file(w, basename) for w in words[i:]):
            return True
    return False


def names_file(word: str, basename: str) -> bool:
    """Does `word` name `basename`, as a whole filename rather than a suffix?

    `"a.md" in "data.md"` is true as a substring and false as a claim about
    which file is being searched for, so a sweep for `data.md` must not clear
    a move out of `a.md`. Anchoring on a path separator or a non-name character
    is what draws that line.
    """
    if basename not in word:
        return False
    return re.search(r"(?:\A|[^\w.-])" + re.escape(basename) + r"(?:\Z|[^\w.-])",
                     word + " ") is not None


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


def as_str(value) -> str:
    """`value` when it is a string, otherwise the empty string.

    Every field in a hook payload is attacker- or harness-shaped: `json.load`
    guarantees the SYNTAX and nothing about the types inside. Four crash sites
    in this module came from assuming otherwise, so each boundary reads through
    here rather than through `or ""`, which passes a truthy non-string straight
    to whatever consumes it.
    """
    return value if isinstance(value, str) else ""


def as_dict(value) -> dict:
    """`value` when it is a dict, otherwise an empty one.

    The `or {}` idiom this replaces is the specific bug: it substitutes for a
    FALSY value and passes a truthy non-dict through, so `(x or {}).get(...)`
    raises `AttributeError` on exactly the input the guard was meant to absorb.
    """
    return value if isinstance(value, dict) else {}


def significant(line: str) -> bool:
    """Is this line distinctive enough to count as evidence of a move?"""
    body = line[1:]
    if not body.strip():
        return False
    return not TRIVIAL.match(body)


def staged_diff(cwd: str) -> str:
    """The staged diff, with renames detected so they can be skipped.

    The catch is narrowed to what running a subprocess can actually raise --- a
    missing or unreadable directory, a missing `git`, a timeout. It used to be
    a blanket `except Exception`, and review established that the blanket was
    doing undocumented work: `main()` passed an untyped `cwd` straight through,
    so a non-string one raised `TypeError` inside `subprocess.run` and was
    absorbed here rather than at the boundary where it belonged. `main()` now
    coerces `cwd` through `as_str`, which is what makes narrowing this safe --
    the order matters, and narrowing first would have converted that silent
    no-op into a crash.
    """
    try:
        out = subprocess.run(
            ["git", "diff", "--cached", "-M", "--no-color"],
            cwd=cwd or None, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
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
    old_path = None
    new_path = None
    renamed = set()

    for line in diff.split("\n"):
        if line.startswith("diff --git "):
            old_path = new_path = None
            continue
        if line.startswith("rename from "):
            # Only the SOURCE side is collected. A rename's destination is a
            # new path whose content reads as added, and the pair is skipped
            # by the source check below -- so collecting both sides would add
            # a second condition that no input can distinguish from the first,
            # which is a branch no test could pin.
            renamed.add(line[len("rename from "):].strip())
            continue
        # The two sides are tracked separately because they can DIFFER. A
        # rename carrying edits prints `--- a/OLD` against `+++ b/NEW`, so
        # crediting removals to the `+++` path would report content as having
        # left a file that did not exist before the commit -- and would name
        # that path in the remediation grep, where nobody has ever linked to
        # it, while the real stale links against OLD went unreported.
        if line.startswith("--- a/"):
            old_path = line[6:].strip()
            continue
        if line.startswith("--- /dev/null"):
            old_path = None
            continue
        if line.startswith("+++ b/"):
            new_path = line[6:].strip()
            continue
        if line.startswith(("+++", "---", "@@")):
            continue
        if line.startswith("-") and old_path and significant(line):
            removed.setdefault(old_path, set()).add(line[1:])
        elif line.startswith("+") and new_path and significant(line):
            added.setdefault(new_path, set()).add(line[1:])

    for src, gone in removed.items():
        if src in renamed:
            continue
        if not src.lower().endswith(PROSE_SUFFIXES):
            continue
        for dst, arrived in added.items():
            if dst == src:
                continue
            n = len(gone & arrived)
            if n >= MIN_MOVED_LINES:
                yield src, dst, n


def swept(transcript: str, basename: str) -> bool:
    """Did a repo-wide search naming `basename` run in this session?

    The two failure modes are not symmetric, and an earlier draft treated them
    as one. Not being able to OPEN the transcript is a statement about the
    whole session: a guard that fired whenever it could not see one would fire
    on every session that hides it, so that case returns True. A malformed
    RECORD says nothing about the other records, so it is skipped rather than
    clearing the file.

    Collapsing the two is a fail-open, and it was one here: `commands()` raised
    `AttributeError` on a record whose `message` was a truthy non-dict, an outer
    `except Exception` caught it, and the guard reported the whole transcript
    swept when nothing had been searched at all. Silent, and in the permissive
    direction --- the shape `shared/principles/fail-fast.md` names.
    """
    if not transcript or not os.path.isfile(transcript):
        return True

    try:
        fh = open(transcript, errors="ignore")
    except OSError:
        return True
    with fh:
        for line in fh:
            if basename not in line:
                continue
            try:
                rec = json.loads(line)
            except (ValueError, RecursionError):
                continue
            for cmd in commands(rec):
                if is_sweep(cmd, basename):
                    return True
    return False


def commands(rec) -> list:
    """Every Bash command string in one transcript record."""
    out = []
    content = as_dict(as_dict(rec).get("message")).get("content")
    if not isinstance(content, list):
        return out
    for block in content:
        if not isinstance(block, dict) or block.get("name") != "Bash":
            continue
        args = block.get("input")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except (ValueError, RecursionError):
                continue
        cmd = as_dict(args).get("command")
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
        i = skip_git_options(words, i + 1)
        if i < len(words) and words[i] == "commit":
            return True
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, RecursionError):
        # `RecursionError` is a `RuntimeError`, not a `ValueError`, so deeply
        # nested JSON slips past a catch written for malformed input. Named at
        # all three parse sites.
        #
        # The depth required is NOT the Python recursion limit. `json` uses the
        # C-accelerated scanner by default, which recurses on the C stack, so
        # `sys.setrecursionlimit` does not move it: measured at roughly 116,000
        # levels on this machine against a limit of 1000. That makes it a
        # property of the platform's stack rather than a constant, which is why
        # the tests search for a depth that genuinely raises instead of
        # asserting one. An earlier draft assumed ~1000 and its fixtures parsed
        # cleanly, pinning nothing.
        return 0
    if not isinstance(payload, dict):
        # Valid JSON that is not an object: a bare list, string, or number.
        return 0

    if payload.get("tool_name") != "Bash":
        return 0
    command = as_str(as_dict(payload.get("tool_input")).get("command"))
    if not is_commit(command):
        return 0

    cwd = as_str(payload.get("cwd")) or os.getcwd()
    diff = staged_diff(cwd)
    if not diff:
        return 0

    transcript = as_str(payload.get("transcript_path"))
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
