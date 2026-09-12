#!/usr/bin/env python3
"""Every split-out push block must run alone.

`check-chained-commit-push-in-fences.py` finds a `git commit` chained into a
`git push` inside one fenced block, and the fix is to split the block in two.
Splitting has a cost the split itself does not pay. A variable the first block
set is gone by the second, always. The working directory is the unsettled half:
`memories/preferences.md` and `memories/claude-code.md` both state that Bash's
cwd PERSISTS across calls, and `memories/git-worktrees.md` records a main
session that reset it after every call, naming `claude-code.md` as the account
its measurement contradicts. A recipe cannot assume either.

`git -C <path>` is right under both, which is why `memories/preferences.md`
recommends it over `cd` even while asserting persistence: there, a stray `cd`
silently carries into later calls. Under the reset behaviour the directory is
simply gone. Naming the directory answers both.

A RELATIVE `cd` re-issued in the second block assumes the reset, and fails
under persistence: `cd ../sibling` run from inside that sibling does not
resolve. So this check accepts either spelling rather than demanding a `cd`,
which would demand the worse one.

Successive review rounds on [#3199](https://github.com/Morrison-Lab/ai-config/issues/3199) each found another recipe with that
gap, after the previous round had fixed the ones it was shown. The property is
mechanical, so this checks it instead: a `Push as a separate Bash call` block
must carry its own `cd` whenever the block above it has one, and must set every
variable it reads.

Reports how many pairs it examined, so a zero is distinguishable from a sweep
that never ran.

What this check does NOT see, and which way each error runs.

Three review rounds on this file each produced another shell spelling the
previous round's grammar had missed, and each fix read as closing the class.
It does not close: a hand-written grammar can always be shown one more
spelling, and the cost of chasing them is a check nobody can read. So the
approximation is stated here instead, and the shapes below are left open.

Quoting is not modelled. A `&&`, `|` or `;` inside a quoted argument -- a PR
body quoting a command, say -- splits the line as though it were an operator.
That direction is a false FAILURE, which a reader sees and can rewrite around.

A relative path spelled with backslashes, or one whose first segment starts
with a character outside `[A-Za-z0-9_-]`, reads as not-relative. A subshell
opened with a bare `(` hides the call inside it, since the opener is only
recognized after `$`. A `cd` reached through a chain or a conditional is not
matched at all. In an earlier block that is a false PASS, since the push
block is then never asked the question. In the push block itself it is a
false FAILURE, since the block falls through to the git calls and the
unanchored push fails: a reader sees that one and can rewrite it.

The false passes are the ones to weigh, and they are bounded by what this
check is for: it decides a property of RECIPES IN THIS CORPUS, which a person
writes and a reader follows. It is not a shell sandbox and nothing is
executed on its verdict. A recipe written in one of the accepted shapes is
checked; one written in a shape below is not, and the remedy is to rewrite it
into an accepted shape rather than to teach this file more bash.

Fix the general shape rather than the reported command when another spelling
turns up here (Morrison-Lab/ai-config#3565).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

MARKER = "Push as a separate Bash call"
PUSH_BLOCK = re.compile(
    MARKER + r"[^\n]*\n\n[ \t]*```bash\n(?P<body>.*?)```", re.S)
ANY_BLOCK = re.compile(r"^[ \t]*```bash\n(.*?)^\s*```", re.S | re.M)
CD = re.compile(r"^[ \t]*cd[ \t]+(?P<target>\S+)", re.M)
COMMENT = re.compile(r"#[^\n]*")
# Every operator that ends one command and may begin another, so a segment
# between two of them is at most one command. Splitting on these is what lets
# a `git` call inside a substitution be seen as the call it is.
SEGMENT = re.compile(r"[$][(]|[)]|`|&&|\|\||\||;")
# A target this file can tell is relative by reading it. A leading `.`, or a
# bare first segment, resolves against wherever the call began. A derived
# path is accepted: the recipes that use one anchor it on an absolute root
# and the value is not in the block to inspect.
RELATIVE = re.compile(r"\A(?:[.]|[A-Za-z0-9_-]+(?:/|\Z))")


def push_runs_alone(body: str) -> tuple[bool, str]:
    """True when git push is not chained with other commands and runs alone."""
    text = COMMENT.sub("", body)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    push_line_idx = -1
    for idx, line in enumerate(lines):
        segments = SEGMENT.split(line)
        for seg_idx, segment in enumerate(segments):
            tokens = segment.split()
            if len(tokens) >= 2 and tokens[0] == "git" and "push" in tokens[1:]:
                if seg_idx < len(segments) - 1 and any(s.strip() for s in segments[seg_idx + 1:]):
                    return False, "it chains other commands with `git push`"
                if idx < len(lines) - 1:
                    return False, "it contains subsequent commands after `git push`; the push must run alone"
                push_line_idx = idx
                break
    if push_line_idx == -1:
        return False, "no `git push` command found in push block"
    return True, ""
USES = re.compile(r"[$]{?([A-Za-z_][A-Za-z0-9_]*)")
ASSIGNS = re.compile(r"^[ \t]*([A-Za-z_][A-Za-z0-9_]*)=", re.M)
FOR_VAR = re.compile(r"\bfor\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\b")

# Names the shell or the harness supplies, so a block need not set them.
AMBIENT = {"CLAUDE_PLUGIN_ROOT", "HOME", "PATH", "PWD", "USER", "SHELL"}


def is_not_relative(token):
    """Does `token` name a directory independent of where a call began?

    The question is deliberately the negative one. A path built from a
    variable or a substitution cannot be resolved by reading the block, and
    the recipes that build one anchor it on an absolute root, so refusing
    every derived path would reject correct work. What a reader can always
    tell is that a leading `.` or a bare first segment is relative.
    """
    text = token.strip(chr(34) + chr(39))
    if not text:
        return False
    return not RELATIVE.match(text)


def git_calls(body):
    """Every `git` invocation in `body`, as its own list of tokens.

    Comments go first, so a command named in prose is not read as a call.
    The rest is split on the shell operators that separate commands, which
    puts a call inside a substitution and a call chained after another on
    the same footing as one at the start of a line.
    """
    text = COMMENT.sub("", body)
    calls = []
    for line in text.split(chr(10)):
        for segment in SEGMENT.split(line):
            tokens = segment.split()
            if tokens and tokens[0] == "git":
                calls.append(tokens)
    return calls


def is_anchored(tokens):
    """Does this call pass `-C` a directory that is not relative?"""
    for index, token in enumerate(tokens[:-1]):
        if token == "-C":
            return is_not_relative(tokens[index + 1])
    return False


def names_its_directory(body):
    """True when `body` says which directory it acts on.

    Either spelling counts and neither may be relative, since a relative one
    assumes the reset behaviour: `cd ../sibling` run from inside that sibling
    does not resolve.

    A `cd` is the right form wherever the block also runs `gh` or `glab`,
    since neither takes `-C` and both act on the directory the call began in.
    `git -C` is the right form where only git runs, and it is checked per
    call, so a second unanchored call cannot ride along behind an anchored
    one.
    """
    cd = CD.search(body)
    if cd:
        above = git_calls(body[:cd.start()])
        if not all(is_anchored(call) for call in above):
            return False
        return is_not_relative(cd.group("target"))
    calls = git_calls(body)
    return bool(calls) and all(is_anchored(call) for call in calls)


def problems_in(text):
    """Every way a split push block in `text` depends on a call that ended."""
    found = []
    for match in PUSH_BLOCK.finditer(text):
        body = match.group("body")
        alone_ok, alone_err = push_runs_alone(body)
        if not alone_ok:
            found.append(alone_err)
        # EVERY preceding block, not just the one immediately above. The
        # directory a recipe works in is often established several steps
        # earlier -- `gi` cds in step 6b and pushes in step 8 -- and checking
        # only the adjacent block missed exactly that case.
        earlier = ANY_BLOCK.findall(text[:match.start()])
        directory_matters = any(CD.search(block) for block in earlier)
        if directory_matters and not names_its_directory(body):
            found.append(
                "an earlier block in this recipe changes directory and this "
                "one neither cds nor passes `git -C`, so it would act on "
                "wherever the caller happened to be")
        reads = set(USES.findall(body))
        writes = set(ASSIGNS.findall(body)) | set(FOR_VAR.findall(body))
        missing = sorted(reads - writes - AMBIENT)
        if missing:
            found.append(
                "it reads " + ", ".join("$" + name for name in missing)
                + ", which a separate Bash call does not inherit")
    return found


def main(argv):
    root = Path(argv[1]) if len(argv) > 1 else REPO
    pairs = 0
    failures = []
    for path in sorted(root.glob("skills/*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        pairs += len(PUSH_BLOCK.findall(text))
        for problem in problems_in(text):
            failures.append((path.relative_to(root), problem))
    print("split push blocks examined: " + str(pairs))
    if not pairs:
        print("no split push blocks found; the marker may have changed, which "
              "is a defect in this check rather than a clean corpus",
              file=sys.stderr)
        return 1
    for where, problem in failures:
        print("FAIL " + str(where) + ": " + problem, file=sys.stderr)
    print("not self-contained: " + str(len(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
