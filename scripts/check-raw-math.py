#!/usr/bin/env python3
"""Lint: flag raw LaTeX math notation where a shared semantic macro exists.

Usage:
    python3 scripts/check-raw-math.py [--macros PATH] FILE_OR_DIR [...]

Scans `.qmd`, `.Rmd`, `.tex`, `.md`, `.R`, `.Rd`, `.Rnw` and `.ipynb` files
(directories recursively) for hand-spelled operators such as
`\\mathbb{E}`, `\\operatorname{Var}` or `\\text{logit}`, and names the macro
from the shared macros library (`d-morrison/macros`) to use instead.
`--macros` points at the library's `macros.qmd`; without it, the first
`macros/macros.qmd` under the current directory is used when one exists,
and its zero-argument `\\operatorname` macros extend the built-in rules.

Exit status: 0 when nothing is found, 1 when raw notation is found, 2 on a
usage error. The rule is in `skills/use-math-macros/SKILL.md`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from raw_math import MATH_SUFFIXES, find_raw, load_rules  # noqa: E402

SKIP_DIRS = {".git", "_site", "_freeze", ".quarto", "node_modules", "renv"}


def iter_files(paths):
    for p in paths:
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if (f.is_file() and f.suffix.lower() in MATH_SUFFIXES
                        and not SKIP_DIRS.intersection(f.parts)):
                    yield f
        elif p.is_file():
            yield p
        else:
            raise FileNotFoundError(p)


def default_macros() -> Path | None:
    return next(iter(sorted(Path.cwd().rglob("macros/macros.qmd"))), None)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="+", type=Path)
    ap.add_argument("--macros", type=Path, default=None,
                    help="the macros library's macros.qmd")
    args = ap.parse_args(argv)

    macros = args.macros or default_macros()
    if args.macros and not args.macros.is_file():
        print(f"check-raw-math: --macros {args.macros} is not a file", file=sys.stderr)
        return 2
    rules = load_rules(macros)

    hits = 0
    try:
        files = list(iter_files(args.paths))
    except FileNotFoundError as exc:
        print(f"check-raw-math: no such file or directory: {exc}", file=sys.stderr)
        return 2
    for f in files:
        if macros and f.resolve() == macros.resolve():
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        for lineno, raw, macro in find_raw(text, rules):
            print(f"{f}:{lineno}: {raw} -> use {macro}")
            hits += 1
    print(f"check-raw-math: {len(files)} file(s) scanned, {hits} raw notation hit(s)"
          + (f" (rules extended from {macros})" if macros else ""))
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
