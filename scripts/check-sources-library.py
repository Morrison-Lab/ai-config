#!/usr/bin/env python3
"""Audit a repository's `sources/` library: orphans, bibliography drift, naming.

This is the audit half of ai-config#885, run against a consuming repository.
The scaffold and conversion halves are not built.

The contract: `sources/references.bib` maps each cite key to a source filed
as `sources/md/<key>.md`, so a citation resolves to a document that has
been read and filed. Layout:

  sources/og/            original PDFs (gitignored, so often absent in a clone)
  sources/md/            Markdown conversions (tracked)
  sources/unprocessed/   incoming documents not yet filed
  sources/references.bib cite keys

Findings (exit 1 if any, exit 2 if `sources/` or the bibliography is missing):

  naming        a file stem in og/ or md/ that is not author-year-slug
  unfiled-key   a bibliography key with no md/<key>.md
  orphan-md     an md/<stem>.md with no bibliography entry
  unconverted   an og/<stem>.pdf with no md/<stem>.md

Files in `unprocessed/` are counted and reported, but are not findings.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*-\d{4}[a-z]?-[a-z0-9]+(-[a-z0-9]+)*$")
BIB_KEY_RE = re.compile(r"^\s*@\w+\s*\{\s*([^,\s]+)\s*,", re.MULTILINE)


def stems(directory: Path, suffix: str) -> set[str]:
    """File stems with `suffix` directly under `directory`, empty if absent."""
    if not directory.is_dir():
        return set()
    return {p.stem for p in directory.iterdir() if p.suffix == suffix}


def audit(root: Path) -> list[tuple[str, str]]:
    """(kind, detail) findings for the library under `root`/sources."""
    sources = root / "sources"
    bib_keys = set(BIB_KEY_RE.findall((sources / "references.bib").read_text(encoding="utf-8")))
    md = stems(sources / "md", ".md")
    og = stems(sources / "og", ".pdf")
    findings = [("naming", f"{s}") for s in sorted(md | og) if not NAME_RE.match(s)]
    findings += [("unfiled-key", k) for k in sorted(bib_keys - md)]
    findings += [("orphan-md", s) for s in sorted(md - bib_keys)]
    findings += [("unconverted", s) for s in sorted(og - md)]
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("root", nargs="?", default=".", help="repository root (default: .)")
    args = parser.parse_args(argv)
    root = Path(args.root)
    if not (root / "sources" / "references.bib").is_file():
        print(f"no sources/references.bib under {root}", file=sys.stderr)
        return 2
    findings = audit(root)
    for kind, detail in findings:
        print(f"{kind}: {detail}")
    pending = len(list((root / "sources" / "unprocessed").glob("*"))) if (root / "sources" / "unprocessed").is_dir() else 0
    print(f"{len(findings)} finding(s); {pending} file(s) in unprocessed/")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
