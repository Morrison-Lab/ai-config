#!/usr/bin/env python3
"""Report fenced shell blocks that `hooks/no-commit-chained-to-push.py` refuses.

A fenced ```bash block in this corpus is a recipe a reader --- human or model
--- pastes.  Pasted whole, the block is ONE Bash call, and a block whose lines
include a `git commit` followed by a `git push` is exactly the shape
`hooks/no-commit-chained-to-push.py` denies.  So the corpus can prescribe, in
its own skills, a call its own guard refuses.

That is the defect ai-config#3199 records.  It also records why a hand-run
sweep is the wrong remedy: ai-config#3002 ran one, concluded its single
`tool-mappings.yml` finding was "the only residual prescriptive denial in the
repository", and was wrong by fourteen sites.  The likeliest cause was fence
extraction anchored at column 0, which cannot see a block indented inside a
list item.  A result reached by hand expires the moment anyone writes another
fence, so the deliverable is this instrument rather than a number in an issue.

## What it does

Extract every fenced block from every tracked Markdown file, tolerating leading
indentation, and feed each block's text --- unchanged, as one string --- to the
hook's own `evaluate()`.  The predicate is IMPORTED rather than reimplemented:
a second implementation of "what counts as a chained commit and push" would
drift from the guard, and a sweep that disagrees with the guard it is auditing
reports nothing anyone can act on.

## What it does not decide

Whether a given block is a *defect* is a judgment about intent, not a property
of the text.  `shared/workflow/check-before-pushing.md` carries the chained
form deliberately, as the anti-example the fragment exists to warn about;
rewriting it would delete the lesson.  So a small allow-list of
`(path, reason)` pairs is subtracted, and every allowed hit is REPORTED in its
own bucket rather than silently dropped --- an exemption nobody can see is
indistinguishable from a detector that missed the file
(`shared/principles/fail-fast.md`).

## Reporting the denominator

A zero from a detector that never ran and a zero from a clean corpus are the
same zero, which is `shared/workflow/batch-merge-and-resolve.md`'s negative
control argument.  So the summary states how many files and how many blocks
were examined alongside how many were denied, and an empty search space is
itself a failure.

Gating: exits 1 on any denial outside the allow-list, 0 otherwise.  The check
is safe to gate because compliance costs nothing --- splitting a fence in two,
or putting a prose line between the commit and the push, preserves the recipe
exactly and only makes the call boundary explicit.

Usage:

    python3 scripts/check-chained-commit-push-in-fences.py
    python3 scripts/check-chained-commit-push-in-fences.py --json
    python3 scripts/check-chained-commit-push-in-fences.py --root /path/to/checkout
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

# Info-string languages whose blocks are shell recipes.  A block with no info
# string is included too: an undecorated fence carrying git commands is still
# something a reader pastes, and excluding it would let a defect hide by
# dropping one word.
SHELL_LANGUAGES = {
    "", "sh", "bash", "shell", "zsh", "console", "shell-session", "sh-session",
}

# A fence opener, tolerating leading indentation.  ai-config#3002's sweep is
# believed to have anchored at column 0, which misses every block nested in a
# list item --- `skills/st/SKILL.md`'s is indented two spaces, several others
# three.  The indentation is captured so the closing fence can be matched at
# the same or shallower depth, and stripped from the block body before the
# block is handed to the predicate.
FENCE_RE = re.compile(r"^(?P<indent>[ \t]*)(?P<ticks>```+|~~~+)(?P<info>.*)$")

# Blocks that carry the chained form ON PURPOSE.  Each entry names the reason,
# and each match is reported rather than hidden.  Only Markdown is scanned, so
# a path here is a Markdown path: the guard's own docstring quotes the shape it
# refuses, and needs no entry because a `.py` file is never examined.
ALLOWED = {
    "shared/workflow/check-before-pushing.md":
        "the deliberate anti-example the fragment is about (ai-config#3199)",
}


def load_predicate(root: Path):
    """Import `evaluate` from the hook, so the sweep cannot drift from it."""
    hook = root / "hooks" / "no-commit-chained-to-push.py"
    if not hook.is_file():
        raise SystemExit(f"cannot find {hook}; not evaluating")
    spec = importlib.util.spec_from_file_location("_nccp", hook)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.evaluate


def tracked_files(root: Path, suffixes):
    """Every tracked file under `root` with one of `suffixes`."""
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True, text=True, check=True,
    ).stdout
    names = [n for n in out.split("\0") if n]
    return [n for n in names if Path(n).suffix in suffixes]


def fenced_blocks(text: str):
    """Yield `(start_line, info, body)` for each fenced block in `text`.

    `start_line` is 1-based and names the opening fence.  `body` has the
    opener's indentation removed from each line, so an indented block is fed
    to the predicate as the reader would paste it.
    """
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        opener = FENCE_RE.match(lines[i])
        if opener is None:
            i += 1
            continue
        indent = opener.group("indent")
        ticks = opener.group("ticks")
        info = opener.group("info").strip()
        marker = ticks[0]
        start = i
        i += 1
        body = []
        while i < len(lines):
            closer = FENCE_RE.match(lines[i])
            if (closer is not None
                    and closer.group("ticks")[0] == marker
                    and len(closer.group("ticks")) >= len(ticks)
                    and closer.group("info").strip() == ""):
                i += 1
                break
            line = lines[i]
            if indent and line.startswith(indent):
                line = line[len(indent):]
            body.append(line)
            i += 1
        yield start + 1, info, "\n".join(body)


def language_of(info: str) -> str:
    """The info string's language word, lowercased."""
    return info.split()[0].lower() if info.split() else ""


def scan(root: Path):
    evaluate = load_predicate(root)
    files = tracked_files(root, {".md", ".qmd"})
    findings = []
    allowed_hits = []
    blocks_examined = 0

    for name in files:
        try:
            text = (root / name).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_no, info, body in fenced_blocks(text):
            if language_of(info) not in SHELL_LANGUAGES:
                continue
            blocks_examined += 1
            if not body.strip():
                continue
            try:
                reason = evaluate(body)
            except Exception:
                # The guard itself fails open on an unparseable command, and a
                # sweep that failed loudly where the guard stays silent would
                # report a denial the guard would never issue.
                continue
            if reason is None:
                continue
            hit = {"path": name, "line": line_no, "language": language_of(info)}
            if name in ALLOWED:
                hit["reason"] = ALLOWED[name]
                allowed_hits.append(hit)
            else:
                findings.append(hit)

    return {
        "files_scanned": len(files),
        "blocks_examined": blocks_examined,
        "findings": findings,
        "allowed": allowed_hits,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=None,
                        help="repository root (default: this script's repo)")
    parser.add_argument("--json", action="store_true",
                        help="emit the full result as JSON")
    args = parser.parse_args(argv)

    root = (Path(args.root).resolve() if args.root
            else Path(__file__).resolve().parent.parent)
    result = scan(root)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"files scanned:    {result['files_scanned']}")
        print(f"blocks examined:  {result['blocks_examined']}")
        print(f"denied:           "
              f"{len(result['findings']) + len(result['allowed'])}")
        print(f"  findings:       {len(result['findings'])}")
        print(f"  allowed:        {len(result['allowed'])}")
        for hit in result["allowed"]:
            print(f"    allowed  {hit['path']}:{hit['line']}  {hit['reason']}")
        for hit in result["findings"]:
            print(f"    FINDING  {hit['path']}:{hit['line']}  "
                  f"fenced `{hit['language'] or 'no-info-string'}` block "
                  f"chains a commit into a later push")
        if result["findings"]:
            print()
            print("Split each block so the commit and the push are separate "
                  "calls: two fenced blocks, or a prose line between them. "
                  "Nothing about either command needs to change.")

    if result["blocks_examined"] == 0:
        print("no fenced shell blocks examined; the sweep found nothing to "
              "check, which is a defect in the sweep rather than a clean "
              "corpus", file=sys.stderr)
        return 1
    return 1 if result["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
