#!/usr/bin/env python3
"""Flag a hook that builds a long prose message inline instead of reading a file.

Ezra, 2026-11-24, on ai-config#6095: "why aren't we using semantic line
breaks in python files?" and "why are we constructing large prose blocks
inline instead of reading them from text files or markdown files?".
The reminder he flagged was a backslash-continued string wrapped at a fixed
column: no semantic line breaks, and no checker reads prose inside a `.py`
file, so nothing caught it.
The rule is `shared/coding/prose-in-files.md`: a message of more than a few
lines lives in `hooks/messages/<hook>.md`, written with semantic line breaks,
and the hook reads it.

A long literal is a string constant or f-string spanning at least MIN_LINES
source lines that is not a docstring (the first statement of a module, class
or function).
Every hook already carrying such literals is listed with its count in
`scripts/hook-prose-literals-known.txt`, a ratchet: a count may fall, never
rise, and a hook not listed may carry none.
Converting the existing hooks is not swept (AGENTS.md "No sweeps for new
rules by default"); a hook moves its prose out when someone edits it.

Usage: check-hook-prose-literals.py [--root DIR] [--write-known]
Exit 0 clean, 1 on a finding, 2 on a usage or parse error.
"""
import argparse
import ast
import sys
from pathlib import Path

MIN_LINES = 8
KNOWN = "scripts/hook-prose-literals-known.txt"


def docstring_nodes(tree: ast.AST) -> set:
    """The constant nodes that are docstrings, which are prose by design."""
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                    and isinstance(first.value.value, str):
                found.add(id(first.value))
    return found


def long_literals(source: str) -> list:
    """Line numbers of the non-docstring string literals of MIN_LINES lines or more."""
    tree = ast.parse(source)
    docs = docstring_nodes(tree)
    lines = []
    inner = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            inner.update(id(part) for part in node.values)
    for node in ast.walk(tree):
        text = isinstance(node, ast.JoinedStr) or (
            isinstance(node, ast.Constant) and isinstance(node.value, str)
            and id(node) not in inner)
        if text and id(node) not in docs \
                and node.end_lineno - node.lineno + 1 >= MIN_LINES:
            lines.append(node.lineno)
    return sorted(lines)


def hook_files(root: Path) -> list:
    return sorted(p for p in (root / "hooks").glob("*.py")
                  if not p.name.startswith("test-"))


def read_known(path: Path) -> dict:
    known = {}
    if not path.is_file():
        return known
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name, _, count = line.partition(" ")
        known[name] = int(count)
    return known


def write_known(path: Path, counts: dict) -> None:
    header = ("# Hooks that build long prose literals inline, with their counts.\n"
              "# A ratchet for scripts/check-hook-prose-literals.py: counts may only fall.\n")
    body = "".join(f"{name} {n}\n" for name, n in sorted(counts.items()) if n)
    path.write_text(header + body, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".", help="ai-config checkout")
    parser.add_argument("--write-known", action="store_true",
                        help="rewrite the ratchet from the current tree")
    args = parser.parse_args()
    root = Path(args.root)
    files = hook_files(root)
    if not files:
        print(f"::error::no hooks found under {root / 'hooks'}")
        return 2
    counts = {}
    sites = {}
    for path in files:
        try:
            found = long_literals(path.read_text(encoding="utf-8"))
        except SyntaxError as err:
            print(f"::error file={path}::cannot parse: {err}")
            return 2
        counts[path.name] = len(found)
        sites[path.name] = found
    known_path = root / KNOWN
    if args.write_known:
        write_known(known_path, counts)
        print(f"wrote {known_path}")
        return 0
    known = read_known(known_path)
    failures = 0
    for name, n in counts.items():
        allowed = known.get(name, 0)
        if n > allowed:
            failures += 1
            where = ", ".join(str(x) for x in sites[name])
            print(f"::error file=hooks/{name},line={sites[name][-1]}::"
                  f"{n} prose literal(s) of {MIN_LINES}+ lines (lines {where}); "
                  f"{allowed} allowed. Move the message to hooks/messages/ as "
                  f"Markdown with semantic line breaks and read it "
                  f"(shared/coding/prose-in-files.md).")
    stale = [name for name, n in known.items() if counts.get(name, 0) < n]
    for name in stale:
        print(f"::error file={KNOWN}::{name} now carries {counts.get(name, 0)}, "
              f"below the listed {known[name]}: lower the count (the ratchet only falls).")
    examined = sum(counts.values())
    print(f"Examined {len(files)} hook(s); {examined} long prose literal(s), "
          f"{len(known)} hook(s) on the ratchet.")
    return 1 if failures or stale else 0


if __name__ == "__main__":
    sys.exit(main())
