#!/usr/bin/env python3
"""Check a history-free export of a repository before it becomes public.

Usage: python3 scripts/check_public_export.py SOURCE_CHECKOUT EXPORT_DIR [--deny-file FILE]

Two checks, both of which must pass before any visibility change:

1. Dropped files. Every file tracked in SOURCE_CHECKOUT (git ls-files) must be in
   EXPORT_DIR, and no file may appear only in EXPORT_DIR. A `git archive` plus the
   source .gitignore dropped 16 tracked files from a 97-file repository on
   2026-10-22; nobody compared the counts.
2. Internal names, not only hosts and tokens. Every file in EXPORT_DIR is searched
   case-insensitively for the built-in patterns below plus any extra regular
   expressions, one per line, in --deny-file (blank lines and lines starting with
   `#` are skipped). A match prints `path:line: text` and fails the check.

Exit 0 means both checks passed. It does not replace the separate-agent review of
the exported tree (shared/workflow/going-public.md).
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

BUILTIN = [
    r"ucdavis/", r"ucdmc", r"\bUCDH\b", r"UC Davis Health", r"\bVPN\b", r"\bBAA\b",
    r"hc2-gitlab", r"databricks\.com", r"\bdbc-",r"hac\.it", r"health-analytics-core",
    r"private (?:github )?mirror", r"runbook", r"project id\W{0,3}[0-9]{3,}",
    r"glpat-", r"glptt-", r"ghp_", r"gho_", r"AKIA[0-9A-Z]{16}",
    r"BEGIN [A-Z ]*PRIVATE KEY", r"\b[0-9]{3}-[0-9]{2}-[0-9]{4}\b",
]


def tracked(root: Path) -> set[str]:
    out = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                         capture_output=True, check=True).stdout.decode()
    return {p for p in out.split("\0") if p}


def exported(root: Path) -> set[str]:
    return {str(p.relative_to(root)) for p in root.rglob("*")
            if p.is_file() and ".git" not in p.relative_to(root).parts}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("export")
    ap.add_argument("--deny-file")
    args = ap.parse_args()
    src, exp = Path(args.source), Path(args.export)
    failed = False

    a, b = tracked(src), exported(exp)
    for label, paths in (("dropped from export", sorted(a - b)),
                         ("only in export", sorted(b - a))):
        if paths:
            failed = True
            print(f"FAIL {len(paths)} file(s) {label}:")
            for p in paths:
                print(f"  {p}")
    print(f"files: source {len(a)}, export {len(b)}")

    patterns = list(BUILTIN)
    if args.deny_file:
        for line in Path(args.deny_file).read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.lstrip().startswith("#"):
                patterns.append(line.strip())
    rx = re.compile("|".join(f"(?:{p})" for p in patterns), re.I)
    hits = 0
    for rel in sorted(b):
        try:
            text = (exp / rel).read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                hits += 1
                print(f"{rel}:{n}: {line.strip()[:140]}")
    if hits:
        failed = True
        print(f"FAIL {hits} line(s) match an internal-name or secret pattern; "
              "each must be removed or justified in the review.")
    print("FAIL" if failed else "ok")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
