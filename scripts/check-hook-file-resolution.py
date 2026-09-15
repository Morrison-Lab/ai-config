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
own path and reports `<checkout>/.claude/hooks`, which holds only
`session-start.sh` and none of the Python hooks a sibling import looks for. Every
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
18 non-test hooks (plus the `__file__` and subject resolution of 34 test
suites: 16 carried one on `__file__`, 26 on their subject, 8 on both,
re-derived at `e388e906` after this instrument gained its `sys.argv` binding
arm -- the figure before that arm was 31/16/23/8, undercounted by exactly the
three suites the arm surfaced) in
`hooks/` under ai-config#2981, because the first fix was not swept. That is the
recurrence bar in `shared/principles/deterministic-tools.md`, and this file is
the instrument it asks for.

Hard-gating rather than advisory: the condition is lexically decidable and
the remedy is one word. A hard gate has no suppression path, though, so a
false positive would cost its author a red required check whose message tells
them to do what their code already does -- which is why `_mentions` refuses to
descend through a `realpath()`/`resolve()` call rather than matching the
outer spelling alone.

Scope is `hooks/*.py` and `plugins/ai-config/*.py`, test suites included,
and two argument shapes:

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
`os.path.abspath`, `os.path.normpath` and `os.path.relpath`.
`relpath` was the one missed longest, because it reads as being about
*relativeness* rather than about normalization --- but `posixpath.relpath`
calls `abspath()` on both operands, and `os.path.relpath("a/b/../c/d.py")`
returns `a/c/d.py`, collapsed as text with no such directory on disk. It is
live in the scanned tree (`flag-add-a-outside-pathspec.py` calls it), and
`dirname(relpath(<registration path>))` lands on the same wrong
`<checkout>/.claude/hooks` that `abspath` does, measured. `normpath` alone accounts for 25
call sites across 7 files in `hooks/`, 12 of them in 5 non-test hooks, counted
at `e388e906` on 2026-09-14 -- a moving population, so the ref and the date
are attached rather than only the criterion. That figure is `normpath`'s
alone, not the set's: `abspath` and `normpath` together are 91 calls across 56
files at the same ref. It is quoted to show `normpath` is a live idiom here rather than a
hypothetical.

`Path(...).absolute()` is deliberately NOT among them, and an earlier revision
had it there on a belief nobody measured. CPython documents it as performing
"no normalization or symlink resolution", and measured against this corpus's
own registration path it PRESERVES the `..` for the OS to walk, landing on a
path that exists -- grouping it with `realpath`, not with `abspath`. Matching
it made a hard gate with no suppression path reject
`ROOT = Path(__file__).absolute().parent`, correct code that cannot cause
ai-config#2981, under a message telling its author to do what they had already
done. It is not a resolver either, so a lexical call wrapped around it is still
caught.

`Path(...).resolve()` is realpath-equivalent and deliberately clean, as is
`os.path.realpath`.

One hop of name binding is followed, because both live escapes are that shape
and both are deliberate: `flag-config-deletion-without-ref-check.py` writes
`_SELF = globals().get("__file__") or sys.argv[0]`, and
`plugins/ai-config/claude-hook-adapter.py` writes
`target_file = start_file or __file__`, each so the file still works when
exec'd into a namespace with no `__file__`. Before `_self_bound_names`
existed, swapping either site's `realpath` to `abspath` yielded zero
offenders -- a one-word reintroduction of ai-config#2981 passing the gate in
silence, at the very file where the corpus first fixed it.

One hop covers four binding forms -- an ordinary assignment, an annotated
one, a walrus, and a tuple target -- and applies to BOTH argument shapes: a
name bound from `__file__`, and, inside a suite, a name bound from
`sys.argv`. The second arm was missing at first, and the gate read clean over
three live suites that resolve a name-bound subject lexically.

What remains unseen, enumerated rather than gestured at, because a boundary
stated loosely is one nobody can check:

  - TWO hops (`A = __file__; B = A; os.path.abspath(B)`).
  - Four further ONE-hop forms that are not assignments -- a `for` target, a
    `with ... as` target, a comprehension target, and an `AugAssign`.
  - A function parameter (`def f(p): os.path.abspath(p)` called with
    `__file__`), and a container built by a method call
    (`paths.append(__file__)`).
  - A call named `resolve` or `realpath` that is NOT a path resolver.
    `_RESOLVERS` matches by function name and ignores the receiver, so
    `os.path.abspath(corpus.resolve(__file__))` is skipped. The collision is
    live in the scanned tree -- `no-misattributed-quote.py` calls
    `corpus.resolve(cited)` -- though no site combines it with a lexical call
    today. Narrowing it needs type information, which a syntax match does not
    have.

A container built by a LITERAL or a store is NOT unseen, and is listed here
because the natural reading of "a container" covers both: `d = {"f":
__file__}`, `d = [__file__]`, `d["f"] = __file__` and `c.f = __file__` are all
flagged, because the target walk binds the container's own name. The same
holds for a `sys.argv` subject in a suite, since both arms share one
collector -- an earlier revision had the `__file__` arm only, and every
binding row above was asymmetric as a result. That is the
same over-reach the tuple arm has, with the same remedy.

Each unseen shape above was measured at zero offenders against this checker,
and each was then swept for in `hooks/` and `plugins/ai-config/`: none occurs.
Closing them needs real dataflow, so the instrument enforces the common
members of the class stated in `memories/hooks.md` rather than the whole
class -- and says which members those are.

Measuring rather than reasoning is the point of that paragraph: an earlier
revision asserted the container case was unseen, and four of its five shapes
turned out to be caught.

Run: python3 scripts/check-hook-file-resolution.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = ROOT / "hooks"
# `plugins/ai-config/` is in scope for the same reason `hooks/` is, and for a
# sharper one: `claude-hook-adapter.py` is the file where this corpus FIRST
# fixed this bug, under ai-config#2681, and it is reached through a symlinked
# plugin root by construction. It kept a lexical `abspath` in its second
# layout branch while its first used `realpath`, so the fix had not been
# carried across two branches of one function -- which is the same
# fix-where-the-symptom-appeared failure at its smallest possible scale.
PLUGIN_DIR = ROOT / "plugins" / "ai-config"
SCANNED_DIRS = (HOOKS_DIR, PLUGIN_DIR)

SUCCESS_EXIT = 0
FAILURE_EXIT = 1


# Every spelling that collapses `..` without consulting the filesystem.
# `realpath` and `Path.resolve()` are the symlink-resolving counterparts and
# are deliberately absent.
_LEXICAL = frozenset({"abspath", "normpath", "relpath"})


def _is_lexical_call(node: ast.AST) -> bool:
    """True for a call to a path function that collapses `..` as text."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    # `os.path.abspath(x)`, `path.normpath(x)`, `os.path.relpath(x)`; a bare
    # `abspath(x)` from
    # `from os.path import abspath` counts too, since the hazard is the
    # function rather than the spelling used to reach it. `Path(x).absolute()`
    # is deliberately NOT here -- see the module docstring; it preserves `..`
    # and so behaves like `realpath`.
    if isinstance(func, ast.Attribute) and func.attr in _LEXICAL:
        return True
    return isinstance(func, ast.Name) and func.id in _LEXICAL


# The symlink-resolving calls. A `__file__` that reaches a lexical call
# THROUGH one of these has already been resolved, so there is no `..` left for
# the lexical call to collapse against a symlink -- `normpath(join(
# dirname(realpath(__file__)), ".."))` is correct code, and flagging it would
# hand its author a red required check whose remedy message tells them to do
# what they already did. Walking past such a subtree is a one-node check, not
# dataflow: it only skips a resolver that is syntactically in the path from
# the lexical call down to `__file__`.
_RESOLVERS = frozenset({"realpath", "resolve"})


def _resolved_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
    return name in _RESOLVERS


def _mentions(node: ast.AST, subject_path: bool,
              bound: frozenset[str] = frozenset()) -> bool:
    """True when NODE reads an UNRESOLVED `__file__`, subject, or alias.

    `subject_path` widens this to `sys.argv[...]`, which is meaningful only in
    a test suite: there the argv is the hook under test, and resolving it
    lexically breaks the registration-path invocation.

    A reference sitting underneath a `realpath()`/`resolve()` call does not
    count: the collapse it would cause has already been prevented.
    """
    for n in _walk_unresolved(node):
        if isinstance(n, ast.Name) and (n.id == "__file__" or n.id in bound):
            return True
        # The STRING spelling, which `_self_bound_names` already matched and
        # this walk did not -- so `globals()["__file__"]` passed straight into
        # a lexical call was missed while the same value bound to a name first
        # was caught. The direct form being weaker than the indirect one
        # inverts the usual relationship, which is why it went unnoticed.
        if isinstance(n, ast.Constant) and n.value == "__file__":
            return True
        if not subject_path:
            continue
        # `sys.argv[1]` and a bare `argv[1]` from `from sys import argv`.
        if isinstance(n, ast.Attribute) and n.attr == "argv":
            return True
        if isinstance(n, ast.Name) and n.id == "argv":
            return True
    return False


def _walk_unresolved(node: ast.AST):
    """`ast.walk`, but not descending into a `realpath()`/`resolve()` call.

    The ROOT is skipped too, which is the whole node rather than a child and
    is easy to miss: `HERE = os.path.realpath(__file__)` binds a value whose
    root IS the resolver, so yielding the root unconditionally walked straight
    into it and tainted `HERE`. The wrapped spelling
    (`dirname(realpath(__file__))`) hid that, because there the resolver is a
    child and the skip applied -- so the common idiom passed while the plainer
    one did not.
    """
    if _resolved_call(node):
        return
    queue = [node]
    while queue:
        current = queue.pop()
        yield current
        for child in ast.iter_child_nodes(current):
            if _resolved_call(child):
                continue
            queue.append(child)


def _self_bound_names(tree: ast.AST, subject_path: bool = False) -> frozenset[str]:
    """Names assigned directly from an UNRESOLVED `__file__` expression.

    Both known escapes from the syntactic match are this one hop, and both are
    written deliberately rather than by accident:

        _SELF = globals().get("__file__") or sys.argv[0]   # a hook
        target_file = start_file or __file__               # the adapter

    Each exists so the file still works when exec'd into a namespace with no
    `__file__`, so neither is going away. Resolving one hop covers them without
    reaching for dataflow: a binding whose value already passes through
    `realpath()`/`resolve()` is NOT collected, because the collapse it would
    cause has already been prevented -- which is what keeps the ordinary
    `HERE = os.path.dirname(os.path.realpath(__file__))` from tainting `HERE`.

    Two hops (`A = __file__; B = A; abspath(B)`) are still invisible. No such
    shape exists in the scanned tree, and saying so is cheaper than the
    dataflow that would close it.
    """
    bound = set()
    for node in ast.walk(tree):
        # `ast.Assign` alone misses an annotated binding (`p: str = __file__`)
        # and a walrus (`f := __file__`), both of which bind exactly as an
        # ordinary assignment does. Neither occurs in the scanned tree today;
        # they are covered because the docstring's job is to state the real
        # boundary, and a boundary drawn at the shape that happens to be in
        # front of you is not one.
        if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
            continue
        # `__file__` reaches a binding two ways, and only the first is a Name.
        # `globals().get("__file__")` -- the spelling the hook uses, precisely
        # because a bare reference would raise there -- carries it as a STRING
        # constant, so matching Name alone misses the site this check exists
        # for. Measured: it did.
        if node.value is None:
            continue  # a bare annotation (`p: str`) binds nothing
        if not any(
                (isinstance(n, ast.Name) and n.id == "__file__")
                or (isinstance(n, ast.Constant) and n.value == "__file__")
                # The SUBJECT half needs the same one hop, and an earlier
                # revision gave it only the direct form. `HOOK = sys.argv[1]`
                # followed by `os.path.abspath(HOOK)` is the identical shape
                # the `__file__` arm already special-cases, and THREE live
                # suites carried it while the gate read clean:
                # test-flag-positional-figure-in-commit-message.py,
                # test-remind-deserialize-before-binary-claim.py, and
                # test-warn-stale-review-diff-base.py. An external review
                # found the first two; fixing the arm surfaced the third,
                # which is why an exhaustive-looking list of two was worse
                # than no list at all. The asymmetry also silently
                # undercounted the census this instrument was used to derive,
                # by exactly those three.
                or (subject_path and (
                    (isinstance(n, ast.Attribute) and n.attr == "argv")
                    or (isinstance(n, ast.Name) and n.id == "argv")))
                for n in _walk_unresolved(node.value)):
            continue
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target])
        for target in targets:
            # A tuple/list target (`a, b = __file__, 1`) binds every name in
            # it. Which element carries `__file__` is not decidable here, so
            # all of them are taken -- over-inclusive by design, and only
            # within an assignment already known to mention an unresolved
            # `__file__`.
            for name in ast.walk(target):
                if isinstance(name, ast.Name):
                    bound.add(name.id)
    return frozenset(bound)


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
    bound = _self_bound_names(tree, subject_path)
    found = []
    for node in ast.walk(tree):
        if _is_lexical_call(node) and _mentions(node, subject_path, bound):
            found.append((node.lineno, lines[node.lineno - 1].strip()))
    return sorted(set(found))


def main() -> int:
    paths = []
    for directory in SCANNED_DIRS:
        if not directory.is_dir():
            print(f"error: no directory at {directory}", file=sys.stderr)
            return FAILURE_EXIT
        found = sorted(directory.glob("*.py"))
        if not found:
            # Per directory, not over the union. Checking the union instead
            # would let a populated sibling mask an empty one, which is the
            # same vacuous-zero the emptiness check exists to refuse -- just
            # harder to see.
            print(f"error: no python files under {directory}", file=sys.stderr)
            return FAILURE_EXIT
        paths.extend(found)
    failures = []
    for path in paths:
        for lineno, text in offenders(path):
            failures.append(f"{path.relative_to(ROOT)}:{lineno}: {text}")

    if failures:
        print("Hooks resolving a path lexically "
              "(use os.path.realpath / Path.resolve):\n", file=sys.stderr)
        for line in failures:
            print(f"  {line}", file=sys.stderr)
        print("\nabspath, normpath and relpath collapse `..` as text, so a hook "
              "reached "
              "through the .claude/skills symlink resolves its own directory "
              "to <checkout>/.claude/hooks, which holds none of the hooks a "
              "sibling import looks for. "
              "If the flagged value is NOT a self-path, the binding was "
              "over-matched: a tuple target binds every name in it, and a "
              "container literal or store binds the container, so a name "
              "beside `__file__` is reported too. Split that assignment "
              "rather than changing the call. "
              "See memories/hooks.md and ai-config#2981.", file=sys.stderr)
        return FAILURE_EXIT

    print(f"checked {len(paths)} hook and adapter files; "
          f"none resolves its own path or its subject lexically")
    return SUCCESS_EXIT


if __name__ == "__main__":
    sys.exit(main())
