#!/usr/bin/env python3
"""Tests for scripts/lib/sibling.py (ai-config#2018).

The first section pins `load_sibling` itself. The second loads each hook
that uses it in a fresh process and checks that the sibling it names really
loads, so a migration that broke the path would show here rather than as a
hook that quietly runs without its sibling. The third copies each hook that
guards its import of the loader, with its siblings, to a tree whose
scripts/lib lacks the loader, and checks that the hook still imports and
says why on stderr.

Run:  python3 scripts/test_sibling.py
"""
import contextlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))

from sibling import load_sibling  # noqa: E402

failures = []


def check(label, got, want):
    if got == want:
        print(f"  ok    {label}")
    else:
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")
        failures.append(label)


tmp = tempfile.mkdtemp()
try:
    real = os.path.join(tmp, "real")
    os.mkdir(real)
    hook = os.path.join(real, "my-hook.py")
    with open(hook, "w", encoding="utf-8") as fh:
        fh.write("")
    with open(os.path.join(real, "good-sibling.py"), "w", encoding="utf-8") as fh:
        fh.write("VALUE = 7\n")
    with open(os.path.join(real, "bad-sibling.py"), "w", encoding="utf-8") as fh:
        fh.write("raise RuntimeError('boom')\n")

    mod = load_sibling(hook, "good-sibling.py")
    check("loads a hyphenated sibling", getattr(mod, "VALUE", None), 7)
    check("derives an identifier key", mod.__name__, "_sibling_good_sibling")
    check("uses a given key", load_sibling(hook, "good-sibling.py", "k").__name__, "k")
    for name, why in (("nope.py", "No such file"), ("bad-sibling.py", "boom")):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            got = load_sibling(hook, name)
        check(f"{name} is None, and stderr says why",
              (got, f"my-hook.py: cannot load sibling {name}" in err.getvalue(),
               why in err.getvalue()), (None, True, True))
    # A name without .py gets no spec from importlib: ImportError, not
    # an AttributeError on the missing spec.
    for name, exc in (("nope.py", FileNotFoundError), ("bad-sibling.py", RuntimeError),
                      ("notes.txt", ImportError)):
        try:
            load_sibling(hook, name, required=True)
            got = None
        except Exception as e:  # noqa: BLE001 -- the type is what is checked
            got = type(e)
        check(f"required=True raises for {name}", got, exc)

    # A hook symlinked into another directory still finds its real siblings.
    # Windows without Developer Mode or elevation cannot make symlinks: skip
    # there, so the hook probes below still run. Anywhere else, fail.
    linked = os.path.join(tmp, "linked")
    os.mkdir(linked)
    try:
        os.symlink(hook, os.path.join(linked, "my-hook.py"))
    except OSError as e:
        if os.name != "nt":
            raise
        print(f"  skip  symlinked hook: cannot make a symlink here ({e})")
    else:
        mod = load_sibling(os.path.join(linked, "my-hook.py"), "good-sibling.py")
        check("resolves a symlinked hook to its real directory",
              getattr(mod, "VALUE", None), 7)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# Each migrated hook and the attribute it binds to each sibling, which the
# probe reads, in a fresh `python3 -I` process: the hook must find the
# loader through its own sys.path setup, not through this test's.
HOOKS = os.path.join(os.path.dirname(HERE), "hooks")
USERS = (
    ("no-empty-promise.py", {"_ums": "remind-ums-after-error.py"}),
    ("no-mistake-without-a-hook.py", {"_ums": "remind-ums-after-error.py"}),
    ("remind-learn-from-review.py", {"_ums": "remind-ums-after-error.py"}),
    ("no-user-correction-without-mechanism.py", {
        "_corr": "remind-encode-user-correction.py", "_mist": "no-mistake-without-a-hook.py"}),
    ("remind-ums-on-scrutiny.py", {"_ums": "remind-ums-after-error.py"}),
    ("no-unread-issue-claim.py", {"_claim": "warn-claim-without-comments-read.py"}),
    ("flag-idea-without-issue.py", {"_unfiled": "no-unfiled-finding.py"}),
    ("flag-unfiled-issue.py", {"_unfiled": "no-unfiled-finding.py"}),
    ("flag-cop-out-offer.py", {
        "_idea": "flag-idea-without-issue.py", "_unfiled": "no-unfiled-finding.py"}),
    ("flag-blocker-without-retry.py", {
        "_copout": "flag-cop-out-offer.py", "_retry": "remind-retry-before-declaring-blocked.py"}),
    ("warn-title-only-issue-edit.py", {
        "_stale": "warn-stale-issue-edit.py", "_disclosure": "require-agent-disclosure.py"}),
)
PROBE = ("import importlib.util as u, sys; "
         "s = u.spec_from_file_location('h', sys.argv[1]); "
         "m = u.module_from_spec(s); s.loader.exec_module(m); "
         "print(m.load_sibling is None, "
         "*(getattr(m, a) is None for a in sys.argv[2:]))")


def probe(hook_path, attrs):
    return subprocess.run([sys.executable, "-I", "-c", PROBE, hook_path, *attrs],
                          capture_output=True, text=True, timeout=30)


for hook_name, sibs in USERS:
    proc = probe(os.path.join(HOOKS, hook_name), sibs)
    want = " ".join(["False"] * (1 + len(sibs)))
    check(f"{hook_name} loads {', '.join(sibs.values())}",
          (proc.returncode, proc.stdout.strip(), proc.stderr), (0, want, ""))


def probe_copy(hook_name, sibs, with_lib, with_sibs):
    """Probe a copy of the hook in a fresh tree, with or without scripts/lib
    and the hook's siblings."""
    bare = tempfile.mkdtemp()
    try:
        hooks_dir = os.path.join(bare, "hooks")
        lib_dir = os.path.join(bare, "scripts", "lib")
        os.makedirs(hooks_dir)
        if with_lib:
            shutil.copytree(os.path.join(HERE, "lib"), lib_dir)
        else:
            os.makedirs(lib_dir)
        for name in (hook_name, *(sibs.values() if with_sibs else ())):
            shutil.copy(os.path.join(HOOKS, name), hooks_dir)
        return probe(os.path.join(hooks_dir, hook_name), sibs)
    finally:
        shutil.rmtree(bare, ignore_errors=True)


# The hooks that must import the loader in a try and survive a broken
# install. Declared here, not read from the hooks, so deleting a guard fails;
# GUARD_RE only cross-checks that each hook's source matches the declaration.
GUARDED = {
    "no-empty-promise.py", "no-mistake-without-a-hook.py", "remind-learn-from-review.py",
    "no-user-correction-without-mechanism.py", "remind-ums-on-scrutiny.py",
    "no-unread-issue-claim.py",
}
check("every GUARDED hook is in USERS", sorted(GUARDED - {h for h, _ in USERS}), [])
GUARD_RE = re.compile(r"^try:\n    from sibling import load_sibling\n", re.M)
for hook_name, sibs in USERS:
    # Siblings missing, loader present: each sibling attribute is None, and
    # the loader names each missing sibling on stderr.
    proc = probe_copy(hook_name, sibs, with_lib=True, with_sibs=False)
    want = " ".join(["False"] + ["True"] * len(sibs))
    check(f"missing siblings: {hook_name} imports and binds None",
          (proc.returncode, proc.stdout.strip()), (0, want))
    check(f"missing siblings: {hook_name} names each one on stderr",
          [f"cannot load sibling {s}" in proc.stderr for s in sibs.values()],
          [True] * len(sibs))

    # A broken install whose scripts/lib is empty, siblings present. A hook
    # that imports the loader in a try still imports, loads no sibling, and
    # names the missing loader. A hook that imports it bare (with the other
    # scripts/lib modules it already needs) fails to import.
    guarded = hook_name in GUARDED
    with open(os.path.join(HOOKS, hook_name), encoding="utf-8") as fh:
        check(f"{hook_name} source {'guards' if guarded else 'does not guard'} the import",
              bool(GUARD_RE.search(fh.read())), guarded)
    proc = probe_copy(hook_name, sibs, with_lib=False, with_sibs=True)
    if guarded:
        want = " ".join(["True"] * (1 + len(sibs)))
        check(f"broken install: {hook_name} imports, with no loader and no sibling",
              (proc.returncode, proc.stdout.strip()), (0, want))
        check(f"broken install: {hook_name} names the missing loader on stderr",
              "scripts/lib/sibling.py" in proc.stderr, True)
    else:
        check(f"broken install: unguarded {hook_name} fails to import",
              (proc.returncode != 0, "ModuleNotFoundError" in proc.stderr), (True, True))

if failures:
    print(f"\n{len(failures)} failure(s)")
    sys.exit(1)
print("\nall tests passed")
