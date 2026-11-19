#!/usr/bin/env python3
"""Flag a cross-document step reference that names no step in its target.

Morrison-Lab/ai-config#1865. Skills and shared fragments cite each other's
procedure steps in prose -- "run `clean-worktrees` steps 1 through 3",
"[`post-merge`](../post-merge/SKILL.md)'s step 3.75" -- and nothing checked
them. A renumbering breaks the *citing* file while touching only the *cited*
one, so the PR that causes it shows a clean diff on the file that is now
wrong, and a wrong step number still reads as an instruction.

This is the decidable first part of the issue: does every cited step exist,
and is every cited range in order. The issue's later parts (a command quoted
from a step that no longer matches it, a range described as read-only that
mutates) are not checked here.

What counts as a reference
--------------------------

A step reference names its target explicitly, immediately before the word
"step" or "steps", or right after the ids as "step 3 of <target>":

- a backticked skill name, `` `ardi` step 2 `` or `` `ardi`'s step 2 ``,
  which resolves to ``skills/<name>/SKILL.md``;
- a Markdown link, ``[`ums`](../ums/SKILL.md) step 3``, which resolves to the
  linked ``.md`` file.

An optional "own" may sit between the name and "step". A backticked name that
is not a skill, and a link to anything but an existing ``.md`` file, are
skipped: the reference names no document this checker can read. A bare
"step 4" with no named target is a same-document reference and out of scope,
since a document may run several numbered procedures.

The numbers after "step"/"steps" are a list joined by ``,``, ``and``, ``or``,
``to``, ``through`` or a dash; a dash or ``to``/``through`` makes a range.

What counts as a step
---------------------

A target defines a step id by either form, outside fenced code:

- a heading whose text starts with the id, optionally after "Step":
  ``### 4b. Reply ...``, ``### 1.25. Check ...``, ``## Step 0 -- Extend``;
- a numbered list item at column 0, ``3. **Merge ...**``.

The defined set is the union over the whole target. That is lenient on
purpose: a target with two numbered procedures defines both sets of numbers,
and a reference into either passes. A reference to ``8`` also passes when only
``8a`` is defined, since ``8`` then names the group.

Exit status is 1 when any reference fails, 0 otherwise.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.fences import find_fence_spans  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

STEP_ID = r"\d+(?:\.\d+)?[a-z]?"
SEP = r"\s*(?:,\s*(?:and|or)?|and|or|to|through|--|\u2013|\u2014|-)\s*"

TARGET = (
    r"(?:\[`?(?P<lname>[A-Za-z0-9_.-]+)`?\]\((?P<lpath>[^)\s]+)\)"
    r"|`(?P<bname>[a-z0-9][a-z0-9-]*)`)"
)
IDS = rf"(?P<ids>{STEP_ID}(?:{SEP}{STEP_ID})*)(?![\w.]\d)"
REF_RES = (
    # `ardi`'s step 2, [`ums`](../ums/SKILL.md) steps 2 through 4
    re.compile(TARGET + r"(?:'s)?\s+(?:own\s+)?steps?\s+" + IDS),
    # step 3 of [`delegate-to-opencode`](../delegate-to-opencode/SKILL.md)
    re.compile(r"\b[Ss]teps?\s+" + IDS + r"\s+(?:of|in)\s+(?:the\s+)?" + TARGET),
)
SPLIT_RE = re.compile(rf"({STEP_ID})|({SEP})")
RANGE_WORDS = {"to", "through", "--", "\u2013", "\u2014", "-"}

HEADING_RE = re.compile(
    rf"^#{{1,6}}\s+(?:\*\*)?(?:Step\s+)?(?P<id>{STEP_ID})(?:\*\*)?(?:[.:)]|\s+[\u2014\u2013-]|\s*$)"
)
LIST_RE = re.compile(rf"^(?P<id>\d+)\.\s")


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    text: str
    reason: str


def blank_fences(text: str) -> str:
    """Return text with fenced lines replaced by spaces, keeping offsets."""
    fenced, _, orphans = find_fence_spans(text)
    lines = text.split("\n")
    for idx in fenced | orphans:
        lines[idx] = " " * len(lines[idx])
    return "\n".join(lines)


def defined_steps(path: Path) -> set[str]:
    """Collect the step ids a document defines."""
    text = blank_fences(path.read_text(encoding="utf-8"))
    ids: set[str] = set()
    for line in text.split("\n"):
        for pattern in (HEADING_RE, LIST_RE):
            m = pattern.match(line)
            if m:
                ids.add(m.group("id"))
    return ids


def step_exists(step: str, defined: set[str]) -> bool:
    """Say whether a cited id is defined, or names a group of sub-steps."""
    if step in defined:
        return True
    group = re.compile(rf"{re.escape(step)}[a-z.]")
    return any(group.match(d) for d in defined)


def sort_key(step: str) -> tuple[float, str]:
    m = re.match(r"(\d+(?:\.\d+)?)([a-z]?)", step)
    return float(m.group(1)), m.group(2)


def parse_ids(ids: str) -> tuple[list[str], list[tuple[str, str]]]:
    """Split a reference's id list into single ids and (start, end) ranges."""
    tokens = [
        (m.group(1), (m.group(2) or "").strip().strip(","))
        for m in SPLIT_RE.finditer(ids)
    ]
    steps: list[str] = []
    ranges: list[tuple[str, str]] = []
    pending_range = False
    for step, sep in tokens:
        if step:
            if pending_range and steps:
                ranges.append((steps[-1], step))
            steps.append(step)
            pending_range = False
        elif sep.strip() in RANGE_WORDS:
            pending_range = True
    return steps, ranges


def resolve(match: re.Match[str], source: Path, root: Path) -> Path | None:
    """Return the document a reference names, or None when it names none."""
    if match.group("bname"):
        target = root / "skills" / match.group("bname") / "SKILL.md"
        return target if target.is_file() else None
    link = match.group("lpath").split("#", 1)[0]
    if not link.endswith(".md") or "://" in link:
        return None
    target = (source.parent / link).resolve()
    return target if target.is_file() else None


def check_file(
    path: Path, root: Path, cache: dict[Path, set[str]]
) -> tuple[list[Finding], int]:
    """Check one document; return its findings and how many references it resolved."""
    raw = path.read_text(encoding="utf-8")
    text = blank_fences(raw)
    flat = text.replace("\n", " ")
    findings: list[Finding] = []
    resolved = 0
    matches = [m for pattern in REF_RES for m in pattern.finditer(flat)]
    for m in sorted(matches, key=lambda m: m.start()):
        target = resolve(m, path, root)
        if target is None:
            continue
        resolved += 1
        if target not in cache:
            cache[target] = defined_steps(target)
        defined = cache[target]
        line = text.count("\n", 0, m.start()) + 1
        try:
            shown_target = target.relative_to(root)
        except ValueError:
            shown_target = target
        steps, ranges = parse_ids(m.group("ids"))
        for step in steps:
            if not step_exists(step, defined):
                findings.append(
                    Finding(path, line, m.group(0), f"{shown_target} defines no step {step}")
                )
        for start, end in ranges:
            if sort_key(start) >= sort_key(end):
                findings.append(
                    Finding(path, line, m.group(0), f"range {start} to {end} is not ascending")
                )
    return findings, resolved


def iter_documents(root: Path) -> list[Path]:
    docs = sorted((root / "skills").rglob("*.md")) + sorted((root / "shared").rglob("*.md"))
    docs += [p for p in (root / "AGENTS.md", root / "CLAUDE.md") if p.is_file()]
    return docs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("paths", nargs="*", type=Path, help="files to check (default: corpus)")
    parser.add_argument("--root", type=Path, default=REPO, help="repository root")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    paths = [p.resolve() for p in args.paths] or iter_documents(root)
    cache: dict[Path, set[str]] = {}
    findings: list[Finding] = []
    checked = 0
    references = 0
    for path in paths:
        checked += 1
        file_findings, file_refs = check_file(path, root, cache)
        findings.extend(file_findings)
        references += file_refs
    for f in findings:
        try:
            shown = f.path.relative_to(root)
        except ValueError:
            shown = f.path
        print(f"{shown}:{f.line}: {f.reason}: {f.text!r}")
    print(
        f"check-step-references: {len(findings)} finding(s) in {references} reference(s) "
        f"across {checked} file(s), {len(cache)} target(s) read",
        file=sys.stderr,
    )
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
