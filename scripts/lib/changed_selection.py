"""Decide whether a test suite needs to run, given the files a change touched.

ai-config#5087: a pre-push run in a cloud container spent over 500 s on the
hook suites whatever the diff touched. A suite has to run when a changed file
is one of its inputs, and no suite declares its inputs (#3533), so they are
derived from the code:

1. the seeds (a test and its subject) and every file whose name they mention,
   as a whole token: a file name such as `check-links.py` or `hooks.json`, or a
   Python module's bare stem such as `agent_notice`;
2. then every Python module those files import, followed transitively.

Mentions are followed one level only. Followed further, comments that name
other scripts pulled most of the tree into every suite (measured 2026-11-11:
a median of 1127 of 1647 files, so a one-hook change selected 155 of 193
suites); imports carry the real code dependencies and are followed all the
way.

What the derivation cannot see is a file reached by a computed path (a glob,
a string built at run time). A change under ALWAYS_RUN selects every suite,
and CI runs every suite regardless, so a selection made here only orders the
local work; it never replaces the CI gate.
"""
from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

# A change under one of these selects every suite: shared code reached by
# path arithmetic, the hook registry, and the runners themselves.
ALWAYS_RUN = (
    "scripts/lib/",
    "hooks/hooks.json",
    "scripts/test_hooks.py",
    "scripts/run-local-validation.py",
    ".github/workflows/validate.yml",
)
_TOKEN = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*")
_MODULE_FILE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\.py")
_TEXT_SUFFIXES = {".py", ".sh"}


def tree_files(root: Path) -> List[str]:
    """Tracked files plus untracked, non-ignored ones: what a commit of the tree would hold."""
    out = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--cached", "--others",
                          "--exclude-standard"], capture_output=True, text=True, check=True).stdout
    return sorted({name for name in out.split("\0") if name})


class Selector:
    """Name and import index over a tree, built once per run."""

    def __init__(self, root: Path, files: Optional[Iterable[str]] = None):
        self.root = root
        self.files = list(files) if files is not None else tree_files(root)
        self.by_token: Dict[str, Set[str]] = {}
        self.by_module: Dict[str, Set[str]] = {}
        for path in self.files:
            name = path.rsplit("/", 1)[-1]
            self.by_token.setdefault(name, set()).add(path)
            if _MODULE_FILE.fullmatch(name):
                self.by_token.setdefault(name[:-3], set()).add(path)
                self.by_module.setdefault(name[:-3], set()).add(path)
        self._text: Dict[str, str] = {}
        self._imports: Dict[str, Set[str]] = {}

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
            except SyntaxError:
                tree = None
            for node in ast.walk(tree) if tree is not None else ():
                names: List[str] = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""] + [alias.name for alias in node.names]
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
                named |= self.by_token.get(token, set())
        seen = set(named)
        queue = [p for p in named if p.endswith(".py")]
        while queue:
            for hit in self._imported(queue.pop()):
                if hit not in seen:
                    seen.add(hit)
                    queue.append(hit)
        return seen

    def needed(self, seeds: Iterable[str], changed: Iterable[str]) -> bool:
        changed = list(changed)
        if any(c.startswith(ALWAYS_RUN) for c in changed):
            return True
        inputs = self.inputs(seeds)
        return any(c in inputs for c in changed)


def read_changed_list(path: str) -> List[str]:
    return [ln.strip() for ln in Path(path).read_text(encoding="utf-8").splitlines() if ln.strip()]
