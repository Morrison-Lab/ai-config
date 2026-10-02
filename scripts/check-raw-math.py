#!/usr/bin/env python3
"""Lint: flag raw LaTeX math notation where a shared semantic macro exists.

Usage:
    python3 scripts/check-raw-math.py [--macros PATH] FILE_OR_DIR [...]

Scans `.qmd`, `.Rmd`, `.tex`, `.md`, `.R`, `.Rd`, `.Rnw` and `.ipynb` files
(directories recursively) for hand-spelled operators such as
`\\mathbb{E}`, `\\operatorname{Var}` or `\\text{logit}`, and names the macro
from the shared macros library (`d-morrison/macros`) to use instead.
In Markdown-like files, fenced code blocks and inline code spans are
skipped, so prose can quote a raw form.

`--macros` points at the library's `macros.qmd`, whose zero-argument
`\\operatorname` macros then extend the built-in rules. Without it, the lint
looks for exactly one `macros/macros.qmd` under the current directory and
uses it; when it finds several, it stops and asks for `--macros`.

Exit status: 0 when nothing is found, 1 when raw notation is found, 2 on a
usage or read error. The rule is in `skills/use-math-macros/SKILL.md`
(ai-config#4221).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from raw_math import (  # noqa: E402
    MATH_SUFFIXES, find_raw, is_library, is_markdown, load_rules)

SKIP_DIRS = {".git", "_site", "_freeze", ".quarto", "node_modules", "renv"}


def _skipped(path: Path, root: Path) -> bool:
    return bool(SKIP_DIRS.intersection(path.relative_to(root).parts))


def iter_files(paths):
    for p in paths:
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if (f.is_file() and f.suffix.lower() in MATH_SUFFIXES
                        and not _skipped(f, p)):
                    yield f
        elif p.is_file():
            yield p
        else:
            raise FileNotFoundError(p)


class AmbiguousMacros(Exception):
    pass


def default_macros(root: Path) -> Path | None:
    found = [f for f in root.rglob("macros/macros.qmd") if not _skipped(f, root)]
    distinct = sorted({f.resolve() for f in found})
    if len(distinct) > 1:
        raise AmbiguousMacros(", ".join(str(f) for f in distinct))
    return distinct[0] if distinct else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="+", type=Path)
    ap.add_argument("--macros", type=Path, default=None,
                    help="the macros library's macros.qmd")
    args = ap.parse_args(argv)

    if args.macros is not None and not args.macros.is_file():
        print(f"check-raw-math: --macros {args.macros} is not a file", file=sys.stderr)
        return 2
    try:
        macros = args.macros or default_macros(Path.cwd())
        rules = load_rules(macros)
        files = list(iter_files(args.paths))
    except AmbiguousMacros as exc:
        print(f"check-raw-math: several macros libraries found ({exc}); "
              "pass --macros", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"check-raw-math: {exc}", file=sys.stderr)
        return 2

    hits = 0
    for f in files:
        if is_library(f):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"check-raw-math: cannot read {f}: {exc}", file=sys.stderr)
            return 2
        for lineno, raw, macro in find_raw(text, rules, markdown=is_markdown(f)):
            print(f"{f}:{lineno}: {raw} -> use {macro}")
            hits += 1
    print(f"check-raw-math: {len(files)} file(s) scanned, {hits} raw notation hit(s)"
          + (f" (rules extended from {macros})" if macros else ""))
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
