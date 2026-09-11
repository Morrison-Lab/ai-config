#!/usr/bin/env python3
"""Every split-out push block must run alone.

`check-chained-commit-push-in-fences.py` finds a `git commit` chained into a
`git push` inside one fenced block, and the fix is to split the block in two.
Splitting has a cost the split itself does not pay: shell state does not cross
a Bash call boundary, so a `cd` or a variable the first block established is
gone by the time the second runs. The push then targets the caller's directory,
or an empty `-C` path, which git resolves to the current directory rather than
refusing.

Four review rounds on ai-config#3199 each found another recipe with that gap,
after the previous round had fixed the ones it was shown. The property is
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
USES = re.compile(r"[$]{?([A-Za-z_][A-Za-z0-9_]*)")
ASSIGNS = re.compile(r"^[ \t]*([A-Za-z_][A-Za-z0-9_]*)=", re.M)
FOR_VAR = re.compile(r"\bfor\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\b")

# Names the shell or the harness supplies, so a block need not set them.
AMBIENT = {"CLAUDE_PLUGIN_ROOT", "HOME", "PATH", "PWD", "USER", "SHELL"}


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
        if any(CD.search(block) for block in earlier) and not CD.search(body):
            found.append(
                "an earlier block in this recipe changes directory and it "
                "does not, so it would push from wherever the caller was")
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
