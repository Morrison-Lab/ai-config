#!/usr/bin/env python3
"""Assert no hook resolves its own path with lexical `os.path.abspath(__file__)`.

`os.path.abspath()` collapses `..` as TEXT, without consulting the filesystem.
`os.path.realpath()` resolves symlinks first. The two agree wherever no symlink
sits in the path, so the difference is invisible in a checkout and decisive in
an install.

This corpus puts a symlink there by construction. An ai-config checkout carries
`.claude/skills` as a symlink to its own `skills/`, and the hooks-only
skills-directory plugin registers every hook as
`${CLAUDE_PLUGIN_ROOT}/../../hooks/<name>.py`. The interpreter walks that
`../../` THROUGH the symlink and opens the real file, so the hook runs and
nothing looks wrong; `abspath` collapses the same `..` against the symlink's
own path and reports `<checkout>/.claude/hooks`, which holds no hooks. Every
sibling import and data file resolved from there is then missing.

The two failure directions are both bad and only one is visible:

  - A fail-closed guard (`no-push-without-self-review.py`) loses its detector
    and denies every push-shaped command, including a heredoc that merely
    QUOTES a push line -- a session-wide lockout (ai-config#2981).
  - A fail-open hook (`no-empty-promise.py`, whose `_sibling()` catches a bare
    `Exception`) silently runs without its sibling's helpers, and says nothing
    at all.

The corpus has paid for this twice: once in `plugins/ai-config/
claude-hook-adapter.py` under ai-config#2681, and again across 19 sites in
`hooks/` under ai-config#2981, because the first fix was not swept. That is the
recurrence bar in `shared/principles/deterministic-tools.md`, and this file is
the instrument it asks for.

Hard-gating rather than advisory: the condition is lexically decidable, the
remedy is one word, and a false positive costs nothing.

Scope is `hooks/*.py`, test suites included. A test suite resolving its subject
lexically cannot be run through the registration path at all, which is the
natural way to reproduce ai-config#2981 by hand.

Run: python3 scripts/check-hook-file-resolution.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = ROOT / "hooks"

SUCCESS_EXIT = 0
FAILURE_EXIT = 1


def _is_abspath_call(node: ast.AST) -> bool:
    """True for `os.path.abspath(...)`, however `os.path` was spelled."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    # `os.path.abspath(x)` and `path.abspath(x)`; a bare `abspath(x)` from
    # `from os.path import abspath` counts too, since the hazard is the
    # function rather than the spelling used to reach it.
    if isinstance(func, ast.Attribute) and func.attr == "abspath":
        return True
    return isinstance(func, ast.Name) and func.id == "abspath"


def _mentions_dunder_file(node: ast.AST) -> bool:
    return any(isinstance(n, ast.Name) and n.id == "__file__"
               for n in ast.walk(node))


def offenders(path: Path) -> list[tuple[int, str]]:
    """(lineno, source line) for every `abspath(...__file__...)` in PATH."""
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        # Not swallowed into a pass: an unreadable hook is reported as a
        # failure, because this check cannot say anything about it.
        raise SystemExit(f"{path}: cannot read ({exc})")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise SystemExit(f"{path}: cannot parse ({exc})")

    lines = source.splitlines()
    found = []
    for node in ast.walk(tree):
        if _is_abspath_call(node) and _mentions_dunder_file(node):
            found.append((node.lineno, lines[node.lineno - 1].strip()))
    return sorted(set(found))


def main() -> int:
    if not HOOKS_DIR.is_dir():
        print(f"error: no hooks directory at {HOOKS_DIR}", file=sys.stderr)
        return FAILURE_EXIT

    paths = sorted(HOOKS_DIR.glob("*.py"))
    if not paths:
        # A glob that matches nothing would otherwise report a clean sweep of
        # zero files, which is the shape `shared/workflow/` warns about: a
        # detector that never ran is indistinguishable from one that found
        # nothing.
        print(f"error: no hooks found under {HOOKS_DIR}", file=sys.stderr)
        return FAILURE_EXIT

    failures = []
    for path in paths:
        for lineno, text in offenders(path):
            failures.append(f"{path.relative_to(ROOT)}:{lineno}: {text}")

    if failures:
        print("Hooks resolving their own path lexically "
              "(use os.path.realpath, not os.path.abspath):\n", file=sys.stderr)
        for line in failures:
            print(f"  {line}", file=sys.stderr)
        print("\nos.path.abspath() collapses `..` as text, so a hook reached "
              "through the .claude/skills symlink resolves its own directory "
              "to <checkout>/.claude/hooks, where no hook lives. "
              "See memories/hooks.md and ai-config#2981.", file=sys.stderr)
        return FAILURE_EXIT

    print(f"checked {len(paths)} hook files; "
          f"none resolves its own path with lexical abspath")
    return SUCCESS_EXIT


if __name__ == "__main__":
    sys.exit(main())
