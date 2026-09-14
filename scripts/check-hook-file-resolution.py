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

Scope is `hooks/*.py`, test suites included, and two argument shapes:

  - `__file__`, which is how a hook finds its own directory.
  - `sys.argv[...]` inside a `hooks/test-*.py` suite, which is how a suite
    finds the SUBJECT it was handed. That half matters for the same reason:
    running a suite against the hook's real registration path is the natural
    way to reproduce ai-config#2981 by hand, and under the lexical spelling
    the suite cannot run at all. Measured on `test-guard-slide-major-tag.py`
    before the sweep: `FileNotFoundError` on
    `<checkout>/.claude/hooks/guard-slide-major-tag.py`, a path that opens
    fine when it is not collapsed lexically.

Three collapsing spellings are matched, because `abspath` is not the only one:
`os.path.abspath`, `os.path.normpath` (25 call sites across 7 files in
`hooks/`, 12 of them in 5 non-test hooks, so a live idiom here rather than a
hypothetical), and `Path(...).absolute()`,
pathlib's non-symlink-resolving form. `Path(...).resolve()` is
realpath-equivalent and deliberately clean.

What this cannot see, stated rather than implied: the argument has to mention
`__file__` or `sys.argv` syntactically inside the call. Binding it to a name
first escapes the walk, and that shape IS live here --
`flag-config-deletion-without-ref-check.py` writes
`_SELF = globals().get("__file__") or sys.argv[0]` and resolves `_SELF`,
deliberately, so the file works when exec'd into a namespace with no
`__file__`. It uses `realpath` today, but swapping that one word to `abspath`
yields zero offenders: measured, a one-word reintroduction of ai-config#2981
at an existing site passes this gate silently.

Closing it needs dataflow rather than a syntax match. Until then the
instrument enforces the common members of the class stated in
`memories/hooks.md`, not the whole class, and that one site is the known
hole rather than a hypothetical one.

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


# Every spelling that collapses `..` without consulting the filesystem.
# `realpath` and `Path.resolve()` are the symlink-resolving counterparts and
# are deliberately absent.
_LEXICAL = frozenset({"abspath", "normpath", "absolute"})


def _is_lexical_call(node: ast.AST) -> bool:
    """True for a call to a path function that collapses `..` as text."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    # `os.path.abspath(x)`, `path.normpath(x)`, `Path(x).absolute()`; a bare
    # `abspath(x)` from `from os.path import abspath` counts too, since the
    # hazard is the function rather than the spelling used to reach it.
    if isinstance(func, ast.Attribute) and func.attr in _LEXICAL:
        return True
    return isinstance(func, ast.Name) and func.id in _LEXICAL


def _mentions(node: ast.AST, subject_path: bool) -> bool:
    """True when NODE syntactically reads `__file__`, or an argv subject.

    `subject_path` widens this to `sys.argv[...]`, which is meaningful only in
    a test suite: there the argv is the hook under test, and resolving it
    lexically breaks the registration-path invocation.
    """
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and n.id == "__file__":
            return True
        if not subject_path:
            continue
        # `sys.argv[1]` and a bare `argv[1]` from `from sys import argv`.
        if isinstance(n, ast.Attribute) and n.attr == "argv":
            return True
        if isinstance(n, ast.Name) and n.id == "argv":
            return True
    return False


def offenders(path: Path) -> list[tuple[int, str]]:
    """(lineno, source line) for every lexical self-path resolution in PATH."""
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
    subject_path = path.name.startswith("test-")
    found = []
    for node in ast.walk(tree):
        if _is_lexical_call(node) and _mentions(node, subject_path):
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
        print("Hooks resolving a path lexically "
              "(use os.path.realpath / Path.resolve):\n", file=sys.stderr)
        for line in failures:
            print(f"  {line}", file=sys.stderr)
        print("\nabspath/normpath/Path.absolute collapse `..` as text, so a hook reached "
              "through the .claude/skills symlink resolves its own directory "
              "to <checkout>/.claude/hooks, where no hook lives. "
              "See memories/hooks.md and ai-config#2981.", file=sys.stderr)
        return FAILURE_EXIT

    print(f"checked {len(paths)} hook files; "
          f"none resolves its own path or its subject lexically")
    return SUCCESS_EXIT


if __name__ == "__main__":
    sys.exit(main())
