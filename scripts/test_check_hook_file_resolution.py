#!/usr/bin/env python3
"""Tests for scripts/check-hook-file-resolution.py.

The negative control matters more than the positive one here: a checker that
reports "none found" over a directory it never read is indistinguishable from
one that works, which is the failure `shared/workflow/` warns about for any
sweep. So every case that expects a clean result is paired with one that
plants an offender and asserts it is caught.

Run: python3 scripts/test_check_hook_file_resolution.py
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "scripts" / "check-hook-file-resolution.py"


def _load():
    spec = importlib.util.spec_from_file_location("chfr", CHECKER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _offenders_of(mod, source: str, name: str = "sample.py") -> list[tuple[int, str]]:
    d = Path(tempfile.mkdtemp(prefix="chfr-"))
    try:
        p = d / name
        p.write_text(source, encoding="utf-8")
        return mod.offenders(p)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _run_main(mod, hooks_contents: dict | None,
              plugin_files: list | None = None) -> int:
    """Run main() against a temp tree and return its exit code.

    `hooks_contents` of None means no hooks directory at all. An empty dict
    means the directory exists and is empty -- the case whose whole point is
    that a sweep of zero files must not read as a clean sweep.
    """
    d = Path(tempfile.mkdtemp(prefix="chfr-main-"))
    saved = (mod.ROOT, mod.HOOKS_DIR, mod.PLUGIN_DIR, mod.SCANNED_DIRS)
    try:
        mod.ROOT = d
        mod.HOOKS_DIR = d / "hooks"
        # The plugin directory is held constant and always present, so each
        # case varies exactly one directory -- otherwise a "missing directory"
        # case could pass for the wrong reason.
        plugin_dir = d / "plugins" / "ai-config"
        plugin_dir.mkdir(parents=True)
        for name in (["adapter.py"] if plugin_files is None else plugin_files):
            (plugin_dir / name).write_text("X = 1\n", encoding="utf-8")
        mod.PLUGIN_DIR = plugin_dir
        mod.SCANNED_DIRS = (mod.HOOKS_DIR, plugin_dir)
        if hooks_contents is not None:
            mod.HOOKS_DIR.mkdir()
            for fname, text in hooks_contents.items():
                target = mod.HOOKS_DIR / fname
                if isinstance(text, bytes):
                    target.write_bytes(text)
                else:
                    target.write_text(text, encoding="utf-8")
        try:
            return mod.main()
        except SystemExit as exc:
            # offenders() raises SystemExit on an unreadable or unparseable
            # file; a string payload is a failure, not a clean exit.
            return 1 if exc.code else 0
    finally:
        mod.ROOT, mod.HOOKS_DIR, mod.PLUGIN_DIR, mod.SCANNED_DIRS = saved
        shutil.rmtree(d, ignore_errors=True)


MAIN_CASES = [
    # (label, hooks dir contents or None, expected exit code)
    ("a clean hooks directory exits 0",
     {"h.py": "import os\nHERE = os.path.dirname(os.path.realpath(__file__))\n"}, 0),
    ("one offender exits nonzero",
     {"h.py": "import os\nHERE = os.path.dirname(os.path.abspath(__file__))\n"}, 1),
    # The three fail-closed branches. Each is the shape where a checker that
    # examined nothing would otherwise print a reassuring result.
    ("a missing hooks directory exits nonzero rather than reporting clean", None, 1),
    # This is also the masking case: `_run_main` always populates the plugin
    # directory, so an empty hooks/ only fails if the emptiness check runs per
    # directory rather than over the union of the scanned ones. A separately
    # labelled masking case was added and then removed -- same input, same
    # helper, same expectation, so it could not fail independently of this one.
    ("an empty hooks directory exits nonzero rather than reporting clean", {}, 1),
    ("an unparseable hook exits nonzero rather than being skipped",
     {"h.py": "def broken(:\n"}, 1),
    # The unreadable branch, pinned separately from the unparseable one: they
    # are different `except` arms, and mutating this one's `raise SystemExit`
    # to `return []` left the suite green before this case existed. A file of
    # invalid UTF-8 exercises it without depending on file permissions, which
    # a root-running CI container would not honour.
    ("an undecodable hook exits nonzero rather than being skipped",
     {"h.py": b"\xff\xfe not utf-8"}, 1),
]

# The loop in `main()` runs over both scanned directories, and every case
# above varies only `hooks/`. A loop narrowed to `hooks/` alone would leave
# all of them green, so the plugin arm needs its own case -- otherwise the
# per-directory guarantee is proven for one of the two directories and
# asserted for the other.
PLUGIN_DIR_CASES = [
    ("an empty plugin directory exits nonzero rather than reporting clean", [], 1),
    ("a populated plugin directory is fine", ["adapter.py"], 0),
]


CASES = [
    # (label, source, expected number of offenders)
    ("the exact idiom the sweep removed",
     "import os\nHERE = os.path.dirname(os.path.abspath(__file__))\n", 1),
    ("a bare re-exec of the script's own path",
     "import os\nrun([exe, os.path.abspath(__file__)])\n", 1),
    ("the `from os.path import abspath` spelling",
     "from os.path import abspath\nHERE = abspath(__file__)\n", 1),
    ("a module aliased as `path`",
     "import os.path as path\nHERE = path.abspath(__file__)\n", 1),
    ("two offenders in one file are both reported",
     "import os\nA = os.path.abspath(__file__)\nB = os.path.abspath(__file__)\n", 2),
    # Clean cases. Each is a shape a naive substring matcher would misjudge.
    ("the corrected idiom",
     "import os\nHERE = os.path.dirname(os.path.realpath(__file__))\n", 0),
    ("abspath applied to something that is NOT __file__",
     "import os\nHERE = os.path.abspath(sys.argv[1])\n", 0),
    ("__file__ used without abspath",
     "import os\nHERE = os.path.dirname(__file__)\n", 0),
    ("Path(__file__).resolve(), which is realpath-equivalent",
     "from pathlib import Path\nROOT = Path(__file__).resolve().parent\n", 0),
    ("the word abspath inside a string or comment only",
     "# do not use os.path.abspath(__file__) here\nX = 'os.path.abspath(__file__)'\n", 0),
    # normpath collapses `..` exactly as abspath does, and is already used at
    # 25 call sites across 7 files in hooks/ (12 of them in 5 non-test hooks),
    # so it is a live reintroduction route rather than a hypothetical one.
    ("normpath joining __file__ with a parent segment",
     "import os\nROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))\n", 1),
    ("Path(__file__).absolute(), pathlib's non-resolving form",
     "from pathlib import Path\nROOT = Path(__file__).absolute().parent\n", 1),
    ("normpath on a path that is not __file__",
     "import os\nX = os.path.normpath(os.path.join(a, b))\n", 0),
    # Already-resolved prefixes. These were false positives before `_mentions`
    # stopped descending through a resolver, and a hard gate has no
    # suppression path -- so flagging them would have handed their author a
    # red required check whose remedy says to do what the code already does.
    # Joining ".." onto a realpath-rooted directory is the ordinary way to
    # reach the repo root, so this is a common shape rather than a contrived
    # one.
    ("normpath over an already-realpath'd prefix",
     "import os\nROOT = os.path.normpath(os.path.join("
     "os.path.dirname(os.path.realpath(__file__)), '..'))\n", 0),
    ("absolute() over an already-resolved prefix",
     "from pathlib import Path\nR = Path(__file__).resolve().parent.absolute()\n", 0),
    # The exemption must not swallow the real cases: the same two spellings
    # over an UNresolved __file__ are still offenders.
    ("normpath over an unresolved __file__ is still caught",
     "import os\nR = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))\n", 1),
    ("Path(__file__).absolute() with no resolve is still caught",
     "from pathlib import Path\nR = Path(__file__).absolute().parent\n", 1),
    # One hop of name binding. Both live escapes are this shape, and both are
    # written deliberately so the file survives being exec'd into a namespace
    # with no `__file__` -- so neither is going away and the checker has to
    # follow them. The second spelling carries `__file__` as a STRING, which a
    # Name-only match misses; it did, until measured.
    ("a name bound from __file__ and then resolved lexically",
     "import os\ntarget = start or __file__\nD = os.path.dirname(os.path.abspath(target))\n", 1),
    ("a name bound via globals().get(\"__file__\") and resolved lexically",
     "import os, sys\n_SELF = globals().get(\"__file__\") or sys.argv[0]\n"
     "D = os.path.dirname(os.path.abspath(_SELF))\n", 1),
    ("the same binding resolved with realpath is clean",
     "import os\ntarget = start or __file__\nD = os.path.dirname(os.path.realpath(target))\n", 0),
    # A binding whose value is ALREADY resolved must not taint the name, or
    # the commonest correct idiom in the tree becomes a false positive.
    ("a name bound from an already-resolved __file__ does not taint it",
     "import os\nHERE = os.path.dirname(os.path.realpath(__file__))\n"
     "ROOT = os.path.abspath(HERE)\n", 0),
    # The UNWRAPPED spellings, where the resolver is the value's ROOT rather
    # than a child. The wrapped case above passed while these failed, because
    # the walk applied its resolver skip to children and yielded the root
    # unconditionally -- so the common idiom was clean and the plainer one was
    # a false positive on a gate with no suppression path.
    ("an unwrapped realpath binding does not taint it",
     "import os\nHERE = os.path.realpath(__file__)\n"
     "ROOT = os.path.abspath(os.path.join(HERE, '..'))\n", 0),
    ("an unwrapped Path.resolve() binding does not taint it",
     "import os\nfrom pathlib import Path\nHERE = Path(__file__).resolve()\n"
     "R = os.path.normpath(str(HERE) + '/..')\n", 0),
    # The exemption must not reach an inner collapse: here the outer call is a
    # resolver, but abspath has already flattened the path underneath it.
    ("realpath wrapping an abspath is still caught",
     "import os\nH = os.path.realpath(os.path.abspath(__file__))\n", 1),
    # The other one-hop binding forms. None occurs in the scanned tree; they
    # are covered because a boundary drawn at the shapes that happen to be
    # present is not a boundary, and the docstring claims this one.
    ("an annotated binding from __file__",
     "import os\np: str = __file__\nD = os.path.abspath(p)\n", 1),
    # The walrus case must separate the BINDING from the USE. Written as
    # `abspath((p := __file__))` the reference sits lexically inside the call,
    # so `_mentions` finds it by direct walk and never consults the collector
    # -- the case passed identically with NamedExpr removed, which is a case
    # named for a feature it could not test.
    ("a walrus binding used on a later line",
     "import os\nif (p := __file__):\n    D = os.path.abspath(p)\n", 1),
    ("a tuple-target binding from __file__",
     "import os\na, b = __file__, 1\nD = os.path.abspath(a)\n", 1),
    ("a bare annotation binds nothing",
     "import os\np: str\nD = os.path.abspath(p)\n", 0),
    # Container shapes. The docstring asserted these were unseen; four of the
    # five turned out to be caught, because the target walk binds the
    # container's own name. Pinned in whichever direction they measured, so
    # the corrected claim cannot drift back.
    ("a dict literal holding __file__ binds the container",
     "import os\nd = {'f': __file__}\nD = os.path.abspath(d['f'])\n", 1),
    ("a subscript store of __file__ binds the container",
     "import os\nd = {}\nd['f'] = __file__\nD = os.path.abspath(d['f'])\n", 1),
    # An ATTRIBUTE store and a LIST literal, pinned separately. The dict-literal
    # case above cannot discriminate the target walk: its target is a plain
    # Name, so it survives a Name-only mutation. These two do not -- measured,
    # a mutant skipping ast.Attribute targets leaves every other case green
    # while the docstring's `c.f = __file__` claim goes false.
    ("an attribute store of __file__ binds the base name",
     "import os\nc.f = __file__\nD = os.path.abspath(c.f)\n", 1),
    ("a list literal holding __file__ binds the container",
     "import os\nd = [__file__]\nD = os.path.abspath(d[0])\n", 1),
    ("a container built by a method call is genuinely unseen",
     "import os\nd = []\nd.append(__file__)\nD = os.path.abspath(d[0])\n", 0),
    ("a function parameter is genuinely unseen",
     "import os\ndef f(p):\n    return os.path.abspath(p)\nf(__file__)\n", 0),
]

# The subject-path half, which applies only inside a `hooks/test-*.py` suite:
# there `sys.argv[1]` is the hook under test, and resolving it lexically makes
# the suite unrunnable against the real registration path. The same line in a
# non-test file is out of scope, so each case is asserted BOTH ways -- a
# matcher ignoring the filename would fail the second column.
SUBJECT_CASES = [
    ("a suite resolving its subject lexically",
     "import os, sys\nHOOK = os.path.abspath(sys.argv[1])\n", 1, 0),
    ("a suite resolving its subject with realpath",
     "import os, sys\nHOOK = os.path.realpath(sys.argv[1])\n", 0, 0),
    ("the `from sys import argv` spelling",
     "from sys import argv\nfrom os.path import abspath\nHOOK = abspath(argv[1])\n", 1, 0),
]


def main() -> int:
    mod = _load()
    failures = 0
    for label, source, expected in CASES:
        got = len(_offenders_of(mod, source))
        if got != expected:
            print(f"FAIL (got {got}, wanted {expected}): {label}")
            failures += 1
        else:
            print(f"PASS: {label}")

    for label, source, in_suite, in_hook in SUBJECT_CASES:
        got_suite = len(_offenders_of(mod, source, "test-sample.py"))
        got_hook = len(_offenders_of(mod, source, "sample.py"))
        if (got_suite, got_hook) != (in_suite, in_hook):
            print(f"FAIL (suite={got_suite}/{in_suite}, "
                  f"hook={got_hook}/{in_hook}): {label}")
            failures += 1
        else:
            print(f"PASS: {label}")

    for label, contents, expected in MAIN_CASES:
        code = _run_main(mod, contents)
        if bool(code) != bool(expected):
            print(f"FAIL (exit {code}, wanted {'nonzero' if expected else '0'}): {label}")
            failures += 1
        else:
            print(f"PASS: {label}")

    clean_hook = {"h.py": "import os\nH = os.path.dirname(os.path.realpath(__file__))\n"}
    for label, plugin_files, expected in PLUGIN_DIR_CASES:
        code = _run_main(mod, clean_hook, plugin_files=plugin_files)
        if bool(code) != bool(expected):
            print(f"FAIL (exit {code}, wanted {'nonzero' if expected else '0'}): {label}")
            failures += 1
        else:
            print(f"PASS: {label}")

    # The checker must also be green on the repo it ships in -- and that
    # assertion is only worth anything because the planted cases above prove
    # the detector fires.
    scanned = [p for d in (ROOT / "hooks", ROOT / "plugins" / "ai-config")
               for p in sorted(d.glob("*.py"))]
    repo_offenders = sum(len(mod.offenders(p)) for p in scanned)
    if repo_offenders:
        print(f"FAIL (repo has {repo_offenders} offenders): "
              f"hooks/ and plugins/ai-config/ are clean")
        failures += 1
    else:
        print(f"PASS: hooks/ and plugins/ai-config/ are clean "
              f"({len(scanned)} files)")

    total = (len(CASES) + len(SUBJECT_CASES) + len(MAIN_CASES)
             + len(PLUGIN_DIR_CASES) + 1)
    print(f"\n{total - failures}/{total} cases passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
