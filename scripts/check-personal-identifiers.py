#!/usr/bin/env python3
"""Fail when a shared file gains a hardcoded machine name, home path or account.

ai-config started as one maintainer's configuration, so machine names, home
directories and login names are written into rules, skills and hooks that other
people now install.  A fork cannot tell which of them are examples and which
are values its own machines would need.  This check stops the set growing
while the existing ones are moved into per-user configuration
(`ai-config.local.example.json`, step (b) of making the repo usable by others).

Scope: the files other people load, which are the shared rules, skills, hooks,
scripts, plugins, commands and top-level instruction files.  Out of scope: `memories/`, which are
the maintainer's own notes and are expected to name their machines, `docs/`,
`examples/`, case records (`*.cases.md`) and test files, which pin behaviour
with a fixed login and gain nothing from being forced onto a placeholder.

What counts: a lab machine name (`cf463-NN`, `DEM-MBP-NN`), a home or
checkout path that names the maintainer (`/home/morri313`,
`/Users/ezramorrison`, `D:\\GitHub`) and a login or email of the maintainer's
own accounts (`morri313`, `dougmor`, `dem-extra1`).  The organisation
`Morrison-Lab` and the login `d-morrison` are not counted here: both are the
repo's own address and have their own handling.

The existing occurrences are recorded per file in
`scripts/personal-identifiers-baseline.json`.  A file fails when its count
differs from its baseline (a file absent from the baseline has zero): above it
is a new occurrence, and below it means the baseline is stale, so the count
can only fall and each fall is recorded.  Run with `--update-baseline` after
removing one.

Exit status: 1 when any file exceeds its baseline, else 0.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "scripts" / "personal-identifiers-baseline.json"

PATTERN = re.compile(
    r"cf463-\d+|DEM-MBP-\d+|/home/morri313|ezramorrison|[Dd]:[/\\]GitHub|/d/GitHub"
    r"|morri313|dougmor|dem-extra1"
)

SCOPE_DIRS = ("shared/", "skills/", "hooks/", "scripts/", "plugins/", "commands/")
SCOPE_FILES = ("AGENTS.md", "CLAUDE.md", "GEMINI.md", "README.md")
SKIP_PARTS = (".cases.md", "__pycache__")
TEST_DIRS = ("hooks/", "scripts/")
SKIP_FILES = ("scripts/personal-identifiers-baseline.json",
              "scripts/check-personal-identifiers.py",
              "scripts/test_check_personal_identifiers.py")
TEXT_SUFFIXES = (".md", ".py", ".sh", ".json", ".yml", ".yaml", ".toml", ".txt")


def in_scope(path: str) -> bool:
    """Whether a tracked path is a shared file this check covers."""
    if path in SKIP_FILES or any(part in path for part in SKIP_PARTS):
        return False
    name = path.rsplit("/", 1)[-1]
    if path.startswith(TEST_DIRS) and name.startswith(("test-", "test_")):
        return False
    if not path.endswith(TEXT_SUFFIXES):
        return False
    return path in SCOPE_FILES or path.startswith(SCOPE_DIRS)


def count_hits(text: str) -> int:
    """Number of identifier occurrences in a file's text."""
    return len(PATTERN.findall(text))


def hit_lines(text: str) -> list[int]:
    """1-based numbers of the lines holding an identifier."""
    return [n for n, line in enumerate(text.splitlines(), start=1) if PATTERN.search(line)]


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True)
    return out.stdout.splitlines()


def scan(paths: list[str]) -> dict[str, int]:
    """Occurrences per in-scope file, only for files that have any."""
    counts: dict[str, int] = {}
    for path in paths:
        if not in_scope(path):
            continue
        if not (ROOT / path).is_file():
            continue
        text = (ROOT / path).read_text(encoding="utf-8", errors="replace")
        hits = count_hits(text)
        if hits:
            counts[path] = hits
    return counts


def compare(counts: dict[str, int], baseline: dict[str, int]) -> list[tuple[str, str]]:
    """(path, message) findings for files whose count differs from the baseline.

    A count above the baseline is a new occurrence; a count below it means the
    baseline is stale, and leaving it would let the file regrow unnoticed.
    """
    findings = []
    for path in sorted(set(counts) | set(baseline)):
        n, base = counts.get(path, 0), baseline.get(path, 0)
        if n > base:
            findings.append((path, f"{n} occurrence(s), baseline {base}"))
        elif n < base:
            findings.append((path, f"{n} occurrence(s), baseline {base}: the baseline "
                                   "is stale, run --update-baseline"))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--update-baseline", action="store_true",
                        help="rewrite the baseline from the current tree")
    args = parser.parse_args()
    paths = tracked_files()
    counts = scan(paths)
    if args.update_baseline:
        BASELINE.write_text(json.dumps(counts, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
        print(f"baseline written: {len(counts)} file(s), {sum(counts.values())} occurrence(s)")
        return 0
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    examined = sum(1 for p in paths if in_scope(p))
    findings = compare(counts, baseline)
    print(f"examined {examined} shared file(s); {sum(counts.values())} occurrence(s) "
          f"in {len(counts)} file(s) against a baseline of {sum(baseline.values())}")
    for path, message in findings:
        lines = hit_lines((ROOT / path).read_text(encoding="utf-8", errors="replace")) \
            if (ROOT / path).is_file() else []
        where = f" (lines {', '.join(map(str, lines[:8]))})" if lines else ""
        print(f"::error file={path}::{message}{where}")
    if findings:
        print("Move the value into per-user configuration instead of writing it into "
              "a shared file (see ai-config.local.example.json), or, for a value that "
              "must stay, run with --update-baseline and say why in the PR.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
