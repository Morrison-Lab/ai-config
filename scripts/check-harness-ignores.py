#!/usr/bin/env python3
"""Fail if harness ignore files omit local-residue paths that .gitignore lists.

`.gitignore` stops git from proposing Aider history and repo-root worktrees as
commit candidates. Cursor Glob/Grep and Gemini CLI file tools can still walk
those paths unless `.cursorignore` / `.geminiignore` name them too
(ai-config#1641). This check keeps the three files from drifting apart.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Exact gitignore lines for local residue. Adding a new residue path means
# adding it here and to each IGNORE_FILE, not only to .gitignore.
REQUIRED_PATTERNS = (
    ".claude/worktrees/",
    ".worktrees/",
    ".aider.chat.history.md",
    ".aider.input.history",
    ".aider.tags.cache.v4/",
)

IGNORE_FILES = (
    ".gitignore",
    ".cursorignore",
    ".geminiignore",
)


def uncommented_lines(path: Path) -> set[str]:
    lines = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if stripped and not stripped.startswith("#"):
            lines.add(stripped)
    return lines


def audit(repo_root: Path) -> list[str]:
    defects: list[str] = []
    for rel in IGNORE_FILES:
        path = repo_root / rel
        if not path.is_file():
            defects.append(f"missing file: {rel}")
            continue
        have = uncommented_lines(path)
        for pattern in REQUIRED_PATTERNS:
            if pattern not in have:
                defects.append(f"{rel}: missing {pattern}")
    return defects


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", default=str(ROOT))
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    defects = audit(repo_root)
    if defects:
        print("harness ignore files are missing local-residue patterns:")
        for defect in defects:
            print(f"  {defect}")
        return 1
    print(
        f"checked {len(IGNORE_FILES)} ignore files for "
        f"{len(REQUIRED_PATTERNS)} residue patterns: ok"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
