#!/usr/bin/env python3
"""Check that Do/Don't guidance bullet lists follow the ordering convention.

The convention across Morrison-Lab documentation and memory files is that
in any contiguous block of guidance bullets, all `- **Do:**` bullets appear
before any `- **Don't:**` bullets. Interleaving a Do bullet after a Don't bullet
breaks visual scanning and convention consistency (ai-config#3751).

## What is a block

A block is a contiguous run of top-level `- **Do:**` and `- **Don't:**` bullets.
Indented lines (starting with at least two spaces or a tab) continue the current
bullet. A blank line, an unindented line that is not a Do/Don't bullet,
a heading, a thematic break (`---`), or entering a code fence ends the block.
Lines inside code fences (``` or ~~~) are ignored.

## Denominator reporting

Reports files examined, blocks examined, bad blocks found, and misplaced Do
bullets found so a zero from a clean run is distinguishable from a detector
that never ran.

## Modes

- Whole-corpus scan: scans all tracked Markdown (`*.md`) and Quarto (`*.qmd`) files.
- Path-scoped: scans specified files or directories passed on the command line.
- Diff-scoped (`--base-ref <ref>`): inspects files changed since `<ref>`,
  reporting only blocks that contain added or modified lines.
- Advisory by default: exits 0 so that pre-existing historical violations do not
  break CI before a separate sweep PR fixes them.
- Strict mode (`--strict`): exits 1 if any ordering violations are found.

Usage:
    python3 scripts/check-do-dont-order.py
    python3 scripts/check-do-dont-order.py --strict
    python3 scripts/check-do-dont-order.py --json
    python3 scripts/check-do-dont-order.py path/to/file.md
    python3 scripts/check-do-dont-order.py --base-ref origin/main
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import NamedTuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from lib.fences import find_fence_spans
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from lib.fences import find_fence_spans

DO_DONT_BULLET_RE = re.compile(r"^- \*\*(Do|Don't):\*\*")

IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".quarto",
    "_site",
    "site",
    "dist",
    "build",
    ".gemini",
    ".cursor",
    "worktrees",
    ".worktrees",
}


class Bullet(NamedTuple):
    line_number: int
    kind: str  # "Do" or "Don't"
    text: str


class Block(NamedTuple):
    start_line: int
    end_line: int
    bullets: list[Bullet]


class Violation(NamedTuple):
    file_path: str
    line_number: int
    first_dont_line: int
    bullet_text: str

    def to_dict(self) -> dict:
        return {
            "file": self.file_path,
            "line": self.line_number,
            "first_dont_line": self.first_dont_line,
            "text": self.bullet_text,
        }


def extract_blocks_from_text(content: str) -> list[Block]:
    """Extract contiguous Do/Don't guidance bullet blocks from markdown text.

    Ignores lines inside code fences. Indented lines continue the current bullet.
    """
    fenced_lines, _, _ = find_fence_spans(content, swallow_unclosed=True)
    blocks: list[Block] = []
    cur_bullets: list[Bullet] = []
    block_start = 0

    lines = content.splitlines()
    for idx, line in enumerate(lines, 1):
        # 1-based line idx corresponds to 0-based index idx - 1
        if (idx - 1) in fenced_lines:
            if cur_bullets:
                blocks.append(Block(block_start, idx - 1, cur_bullets))
                cur_bullets = []
            continue

        m_bullet = DO_DONT_BULLET_RE.match(line)
        if m_bullet:
            kind = m_bullet.group(1)
            if not cur_bullets:
                block_start = idx
            cur_bullets.append(Bullet(idx, kind, line))
        elif (line.startswith("  ") or line.startswith("\t")) and cur_bullets:
            # Continuation line of current bullet
            continue
        else:
            if cur_bullets:
                blocks.append(Block(block_start, idx - 1, cur_bullets))
                cur_bullets = []

    if cur_bullets:
        blocks.append(Block(block_start, len(lines), cur_bullets))

    return blocks


def check_block(file_rel_path: str, block: Block) -> list[Violation]:
    """Check a single block for Do bullets appearing after a Don't bullet."""
    violations: list[Violation] = []
    seen_dont = False
    first_dont_line: int | None = None

    for bullet in block.bullets:
        if bullet.kind == "Don't":
            seen_dont = True
            if first_dont_line is None:
                first_dont_line = bullet.line_number
        elif seen_dont and first_dont_line is not None:
            violations.append(
                Violation(
                    file_path=file_rel_path,
                    line_number=bullet.line_number,
                    first_dont_line=first_dont_line,
                    bullet_text=bullet.text,
                )
            )

    return violations


def get_diff_changed_lines(root: Path, base_ref: str) -> dict[str, set[int]] | None:
    """Return a mapping of file_path -> set of added/modified line numbers since base_ref.

    Returns None if git diff failed (e.g. unresolvable ref or shallow clone).
    """
    cmd = ["git", "diff", "--unified=0", base_ref, "HEAD", "--", "*.md", "*.qmd"]
    try:
        proc = subprocess.run(
            cmd, cwd=root, capture_output=True, text=True, check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as err:
        print(
            f"check-do-dont-order: warning: git diff against {base_ref} failed ({err}); falling back to full scan",
            file=sys.stderr,
        )
        return None

    changed_lines: dict[str, set[int]] = {}
    cur_file: str | None = None
    hunk_re = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

    for line in proc.stdout.splitlines():
        if line.startswith("+++ b/"):
            cur_file = line[6:].strip()
            if cur_file not in changed_lines:
                changed_lines[cur_file] = set()
        elif line.startswith("@@ ") and cur_file:
            m = hunk_re.match(line)
            if m:
                start = int(m.group(1))
                count = int(m.group(2)) if m.group(2) is not None else 1
                for lnum in range(start, start + count):
                    changed_lines[cur_file].add(lnum)

    return changed_lines


def is_ignored_path(p: Path, root: Path) -> bool:
    """Check if path falls under an ignored or worktree directory."""
    try:
        rel = p.relative_to(root)
    except ValueError:
        return False
    for part in rel.parts[:-1]:
        if part in IGNORED_DIRS:
            return True
    return False


def discover_files(root: Path, paths: list[str]) -> list[Path]:
    """Discover markdown and Quarto files to inspect."""
    if paths:
        collected: list[Path] = []
        for p_str in paths:
            p = Path(p_str)
            if not p.is_absolute():
                p = root / p
            if p.is_file():
                if p.suffix in (".md", ".qmd") and not is_ignored_path(p, root):
                    collected.append(p)
            elif p.is_dir():
                for ext in ("*.md", "*.qmd"):
                    for child in p.rglob(ext):
                        if not is_ignored_path(child, root):
                            collected.append(child)
        return sorted(set(collected))

    # Whole repo discovery, skipping internal git, build, and worktree directories
    collected = []
    for ext in ("*.md", "*.qmd"):
        for p in root.rglob(ext):
            if not is_ignored_path(p, root):
                collected.append(p)

    return sorted(collected)


def run_check(
    root: Path,
    paths: list[str],
    base_ref: str | None = None,
) -> dict:
    """Run Do/Don't ordering check over requested files.

    Returns a report dictionary containing statistics and violations.
    """
    target_files = discover_files(root, paths)
    diff_lines = get_diff_changed_lines(root, base_ref) if base_ref else None

    files_examined = 0
    files_with_blocks = 0
    total_blocks = 0
    bad_blocks_count = 0
    violations: list[Violation] = []

    for file_path in target_files:
        try:
            rel_str = file_path.relative_to(root).as_posix()
        except ValueError:
            rel_str = file_path.as_posix()

        # If base_ref was requested and file was not touched in diff, skip
        if diff_lines is not None and rel_str not in diff_lines:
            continue

        files_examined += 1

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"check-do-dont-order: cannot read {rel_str}: {exc}", file=sys.stderr)
            continue

        blocks = extract_blocks_from_text(content)
        if not blocks:
            continue

        file_has_blocks = False
        for block in blocks:
            # If diff-scoped, only check blocks that overlap with changed lines
            if diff_lines is not None:
                changed = diff_lines[rel_str]
                block_lines = range(block.start_line, block.end_line + 1)
                if not any(ln in changed for ln in block_lines):
                    continue

            file_has_blocks = True
            total_blocks += 1
            block_violations = check_block(rel_str, block)
            if block_violations:
                bad_blocks_count += 1
                violations.extend(block_violations)

        if file_has_blocks:
            files_with_blocks += 1

    return {
        "files_examined": files_examined,
        "files_with_blocks": files_with_blocks,
        "blocks_examined": total_blocks,
        "bad_blocks_count": bad_blocks_count,
        "misplaced_do_count": len(violations),
        "violations": [v.to_dict() for v in violations],
    }


def format_text_report(report: dict, limit: int = 50) -> str:
    """Format check report as human-readable text."""
    lines: list[str] = []
    files_n = report["files_examined"]
    blocks_n = report["blocks_examined"]
    bad_n = report["bad_blocks_count"]
    misplaced_n = report["misplaced_do_count"]

    lines.append(
        f"Checked {files_n} file(s), {blocks_n} Do/Don't block(s)."
    )

    if bad_n == 0:
        lines.append("No Do/Don't ordering violations found.")
        return "\n".join(lines)

    lines.append(
        f"Found {bad_n} block(s) with Do after Don't ({misplaced_n} misplaced Do bullet(s)):\n"
    )

    violations = report["violations"]
    for v in violations[:limit]:
        f = v["file"]
        ln = v["line"]
        first_dont = v["first_dont_line"]
        txt = v["text"].strip()
        if len(txt) > 80:
            txt = txt[:77] + "..."
        lines.append(f"  {f}:{ln}: {txt}")
        lines.append(f"    (Do bullet follows Don't at line {first_dont})")

    if len(violations) > limit:
        lines.append(f"\n  ... and {len(violations) - limit} more violation(s).")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check that Do/Don't guidance lists place all Do bullets before Don't bullets."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional files or directories to check (default: all tracked markdown files)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repository root directory (default: auto-detected)",
    )
    parser.add_argument(
        "--base-ref",
        metavar="REF",
        help="Diff-scoped check: only report blocks touched in git diff against REF",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 if ordering violations are found (default: exit 0 advisory)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON report",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum violations to print in text output (default: 50)",
    )

    args = parser.parse_args(argv)
    root = args.root.resolve()

    report = run_check(root, args.paths, base_ref=args.base_ref)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_text_report(report, limit=args.limit))

    if args.strict and report["bad_blocks_count"] > 0:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
