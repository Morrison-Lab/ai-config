"""Decide whether a test suite needs to run, given the files a change touched (ai-config#5087).

A suite's inputs are derived from the code, since no suite declares them (#3533):
the seeds (a test and its subject), every file whose name or module stem they
mention as a whole token, and every Python module those import or load by a
literal `x.py` path, transitively. Other mentions are followed one level only:
followed further, comments naming other scripts pulled a median of 1127 of 1647
files into every suite (2026-11-11). A file reached only by a computed path or
a directory scan is not selected, so shared code reached that way must live
under ALWAYS_RUN; a deleted path selects every suite, and CI runs all of them.
The changed list must name both sides of a rename (`git diff --no-renames`).
"""
from __future__ import annotations

import ast
import os
import posixpath
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Set

# A change under one of these selects every suite: shared code reached by
# path arithmetic, the hook registry, and the runners themselves.
ALWAYS_RUN = ("scripts/lib/", "hooks/hooks.json", "scripts/test_hooks.py",
              "scripts/run-local-validation.py", ".github/workflows/validate.yml")
_TOKEN = re.compile(r"[A-Za-z0-9_.][A-Za-z0-9_.-]*")
_MODULE_FILE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\.py")
_MODULE_PATH = re.compile(r"[A-Za-z0-9_./-]*[A-Za-z0-9_-]\.py")
_TEXT_SUFFIXES = {".py", ".sh"}


def tree_files(root: Path) -> List[str]:
    """Tracked files plus untracked, non-ignored ones: what a commit of the tree would hold."""
    out = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--cached", "--others",
                          "--exclude-standard"], capture_output=True, text=True, check=True).stdout
    return sorted({name for name in out.split("\0") if name})


class Selector:
    """Name and import index over a tree, built once per run."""

    def __init__(self, root: Path):
        self.root = root
        self.files = tree_files(root)
        self.by_token: Dict[str, Set[str]] = {}
        self.by_module: Dict[str, Set[str]] = {}
        for path in self.files:
            name = path.rsplit("/", 1)[-1]
            self.by_token.setdefault(name, set()).add(path)
            if _MODULE_FILE.fullmatch(name):
                # A package's __init__.py is the module named by its directory.
                module = path.rsplit("/", 2)[-2] if name == "__init__.py" and "/" in path else name[:-3]
                self.by_token.setdefault(module, set()).add(path)
                self.by_module.setdefault(module, set()).add(path)
        self._text: Dict[str, str] = {}
        self._imports: Dict[str, Set[str]] = {}
        self.unparsed: Set[str] = set()

    def _read(self, path: str) -> str:
        if path not in self._text:
            full = self.root / path
            text = ""
            if Path(path).suffix in _TEXT_SUFFIXES and full.is_file():
                text = full.read_text(encoding="utf-8", errors="replace")
            self._text[path] = text
        return self._text[path]

    def _imported(self, path: str) -> Set[str]:
        if path not in self._imports:
            found: Set[str] = set()
            try:
                tree = ast.parse(self._read(path))
            except SyntaxError:  # its imports are unknown, so any suite reaching it runs
                print(f"warning: cannot parse {path}; selecting what reads it", file=sys.stderr)
                self.unparsed.add(path)
                tree = None
            for node in ast.walk(tree) if tree is not None else ():
                names: List[str] = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""] + [alias.name for alias in node.names]
                if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                        and _MODULE_PATH.fullmatch(node.value):  # a sibling loaded by path
                    found |= self.by_token.get(node.value.rsplit("/", 1)[-1], set())
                for dotted in names:
                    for part in dotted.split("."):
                        found |= self.by_module.get(part, set())
            self._imports[path] = found
        return self._imports[path]

    def inputs(self, seeds: Iterable[str]) -> Set[str]:
        """The seeds, the files they name, and every module those import, transitively."""
        named = set(seeds)
        for path in list(named):
            for token in set(_TOKEN.findall(self._read(path))):
                named |= self.by_token.get(token.rstrip(".-"), set())
        seen = set(named)
        queue = [p for p in named if p.endswith(".py")]
        while queue:
            for hit in self._imported(queue.pop()):
                if hit not in seen:
                    seen.add(hit)
                    queue.append(hit)
        return seen

    def needed(self, seeds: Iterable[str], changed: Iterable[str]) -> bool:
        """Whether a suite seeded by `seeds` reads a path in `changed` (repo-relative)."""
        changed = [posixpath.normpath(c) for c in changed]  # ./x and a/../x match too
        bad = [c for c in changed if posixpath.isabs(c) or c.split("/")[0] in ("..", ".")]
        if bad or not changed:  # an empty list would select nothing and pass vacuously
            raise ValueError(f"changed paths must be a non-empty list of repo-relative files: {bad}")
        # A path gone from the working tree (deleted, or the old side of a rename)
        # cannot be matched against what reads it, so it runs everything.
        if any(c.startswith(ALWAYS_RUN) or not os.path.lexists(self.root / c) for c in changed):
            return True
        inputs = self.inputs(seeds)
        return bool(inputs & self.unparsed) or any(c in inputs for c in changed)
