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

Successive review rounds on ai-config#3199 each found another recipe with that
gap, after the previous round had fixed the ones it was shown. The property is
mechanical, so this checks it instead: a `Push as a separate Bash call` block
must carry its own `cd` whenever the block above it has one, and must set every
variable it reads.

Reports how many pairs it examined, so a zero is distinguishable from a sweep
that never ran.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

MARKER = "Push as a separate Bash call"
PUSH_BLOCK = re.compile(
    MARKER + r"[^\n]*\n\n[ \t]*```bash\n(?P<body>.*?)```", re.S)
ANY_BLOCK = re.compile(r"```bash\n(.*?)```", re.S)
CD = re.compile(r"^[ \t]*cd\s+\S", re.M)
GIT_CALL = re.compile(r"^[ \t]*git\s+([^\n]*)", re.M)
USES = re.compile(r"[$]{?([A-Za-z_][A-Za-z0-9_]*)")
ASSIGNS = re.compile(r"^[ \t]*([A-Za-z_][A-Za-z0-9_]*)=", re.M)
FOR_VAR = re.compile(r"\bfor\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\b")

# Names the shell or the harness supplies, so a block need not set them.
AMBIENT = {"CLAUDE_PLUGIN_ROOT", "HOME", "PATH", "PWD", "USER", "SHELL"}


def names_its_directory(body):
    """True when `body` says which directory it acts on.

    Either spelling counts, and `git -C` is the better one: it does not
    depend on where the call started, so it survives a session that keeps
    the previous directory and one that resets it alike.
    """
    if CD.search(body):
        return True
    gits = GIT_CALL.findall(body)
    return bool(gits) and all("-C" in call for call in gits)


def problems_in(text):
    """Every way a split push block in `text` depends on a call that ended."""
    found = []
    for match in PUSH_BLOCK.finditer(text):
        body = match.group("body")
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
