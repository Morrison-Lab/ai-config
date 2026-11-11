#!/usr/bin/env python3
"""Fail when a memory file has no row in `memories/MEMORY.md` (ai-config#4987).

`MEMORY.md` is how a session finds a memory file without listing the
directory, and it tells a writer to register every new file. Nothing checked
that, so a review on ai-config#4985 caught an unregistered file by reading.
Whether each file is linked from the index is decidable, so it is an
instrument rather than a review item (`shared/workflow/algorithmatize-checks.md`).

A file counts as registered when a table row of `MEMORY.md` links to it from
its first cell, `| [...](name.md) |`; a link in prose or in another row's
cell does not count. Exit 0 when every `memories/*.md` other than `MEMORY.md` is
registered, 1 when one is not, 2 when the index is missing.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

INDEX = "MEMORY.md"
ROW = re.compile(r"^\|\s*\[[^\]]*\]\(\.?/?([^)#\s/|]+\.md)(?:#[^)]*)?\)\s*\|")


def unregistered(memories: Path) -> list[str]:
    """Names of memory files the index does not link to, sorted."""
    text = (memories / INDEX).read_text(encoding="utf-8")
    linked = {m.group(1) for line in text.splitlines() if (m := ROW.match(line))}
    names = sorted(p.name for p in memories.glob("*.md") if p.name != INDEX)
    return [name for name in names if name not in linked]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--memories",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "memories",
        help="the memories directory (default: this repo's)",
    )
    args = parser.parse_args(argv)
    if not (args.memories / INDEX).is_file():
        print(f"error: no {INDEX} in {args.memories}", file=sys.stderr)
        return 2
    missing = unregistered(args.memories)
    for name in missing:
        print(f"{args.memories / name}: no row in {INDEX}; add one to its table")
    count = len(list(args.memories.glob("*.md"))) - 1
    print(f"checked {count} memory files: {len(missing)} unregistered")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
