#!/usr/bin/env python3
"""Regression tests for check-hook-delivery.py.

Every case builds a scratch HOME -- a plugin cache with pins, and an
`installed_plugins.json` naming some of them -- and runs the real script as a
subprocess against it, so the control enters where a caller's does.

The case that matters most is `unreadable records still fail`. Labelling pins
by install record was added to make the tool answer ai-config#2439 directly,
and it shipped a regression in the same commit: an unreadable records file
yields zero records, every pin then looks orphaned, and an orphan's gap does
not set the exit status -- so a completely broken install exited 0 where the
previous version exited 1. Nothing about that run looks wrong. It prints the
missing hooks and then reports success.

The rest of the negative cases cover the other ways this script could pass
while having examined nothing: a `--repo` with no `hooks/` directory, and the
overlapping-record arithmetic that used to hide a genuinely different
project's install.

Two cases are deliberately awkward, and both are awkward for the same reason
-- a fixture that is easy to write does not distinguish the behaviour it is
named after. The pin-count case needs TWO pins, because with one pin an
unconditional counter and a conditional one print the same number. The
`ValueError` case substitutes the module's `Path`, because a real NUL raises
on POSIX and returns quietly on Windows, so a plain fixture asserts nothing
on half the machines that run it -- including the half the bug was wrongly
generalised from.

Run: python3 scripts/test_check_hook_delivery.py
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).parent / "check-hook-delivery.py"

FAILURES = []
CHECKS = 0


def check(name, condition, detail=""):
    global CHECKS
    CHECKS += 1
    if condition:
        print(f"ok    {name}")
        return
    FAILURES.append(name)
    print(f"FAIL  {name}" + (f"\n      {detail}" if detail else ""))


def write(path, text=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_repo(root, hooks, with_dir=True):
    """A checkout shaped like ai-config: a `hooks/` directory of scripts."""
    repo = root / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    if with_dir:
        for name in hooks:
            write(repo / "hooks" / name, "# hook\n")
    return repo


def make_home(root, pins, records=None, records_text=None):
    """A scratch HOME with a plugin cache and optional install records.

    `pins` maps a pin directory name to the hook filenames it carries.
    `records` is written as `installed_plugins.json`; `records_text` writes
    raw text instead, for the unreadable case.
    """
    home = root / "home"
    base = home / ".claude" / "plugins" / "cache" / "Morrison-Lab" / "ai-config"
    for pin, names in pins.items():
        for name in names:
            write(base / pin / "hooks" / name, "# hook\n")
    target = home / ".claude" / "plugins" / "installed_plugins.json"
    if records_text is not None:
        write(target, records_text)
    elif records is not None:
        write(target, json.dumps(records))
    return home


def run(home, repo, project=None, home_as=None):
    """Run the script with `home` as the user's home directory.

    `home_as` spells that same directory differently -- with a `..` component
    -- so the pins the script builds from `Path.home()` are non-canonical
    while the install records name the canonical form. That is the only case
    in this suite where resolving the PIN side, rather than the record side,
    is what makes the match succeed.

    It must be `..` rather than `.`: `PurePath` normalises a `.` component
    away at construction, so a path spelled that way compares equal without
    any resolving and the case would pass for the wrong reason.
    """
    env = dict(os.environ)
    env["HOME"] = str(home_as or home)
    env["USERPROFILE"] = str(home_as or home)   # Path.home() reads this on Windows
    env.pop("HOMEDRIVE", None)
    env.pop("HOMEPATH", None)
    cmd = [sys.executable, str(SCRIPT), "--repo", str(repo)]
    cmd += ["--project", str(project if project else repo)]
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return r.returncode, r.stdout + r.stderr


def pin_record(install_path, scope="project", project_path=None):
    e = {"installPath": str(install_path), "scope": scope}
    if project_path is not None:
        e["projectPath"] = str(project_path)
    return e


def main():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        repo = make_repo(root, ["a.py", "b.py", "c.sh"])

        # --- the named pin, complete and incomplete ------------------------
        home = make_home(root, {"good": ["a.py", "b.py", "c.sh"]})
        cache = home / ".claude" / "plugins" / "cache" / "Morrison-Lab" / "ai-config"
        recs = {"plugins": {"ai-config@Morrison-Lab": [
            pin_record(cache / "good", "project", repo)]}}
        write(home / ".claude" / "plugins" / "installed_plugins.json",
              json.dumps(recs))
        code, out = run(home, repo)
        check("a named pin carrying every hook exits 0", code == 0, out)
        check("and it is labelled for THIS project",
              "INSTALLED for THIS project" in out, out)

        home = make_home(root / "h2", {"stale": ["a.py"]})
        cache = (root / "h2" / "home" / ".claude" / "plugins" / "cache"
                 / "Morrison-Lab" / "ai-config")
        recs = {"plugins": {"ai-config@Morrison-Lab": [
            pin_record(cache / "stale", "project", repo)]}}
        write(home / ".claude" / "plugins" / "installed_plugins.json",
              json.dumps(recs))
        code, out = run(home, repo)
        check("a named pin missing hooks exits 1", code == 1, out)
        check("and it names the missing hooks", "b.py" in out and "c.sh" in out,
              out)

        # --- the orphan downgrade, and its precondition --------------------
        home = make_home(root / "h3", {"orphan": ["a.py"]},
                         records={"plugins": {"ai-config@Morrison-Lab": []}})
        code, out = run(home, repo)
        check("a gap in a pin the READ records do not name exits 0",
              code == 0, out)
        check("and the orphan gap is still reported",
              "orphan pin(s) are also missing hooks" in out, out)

        # The regression. Same broken install, records absent instead of empty.
        home = make_home(root / "h4", {"orphan": ["a.py"]})
        code, out = run(home, repo)
        check("a gap still exits 1 when the records file is ABSENT",
              code == 1, out)
        check("and the run says the labels are advisory",
              "could not be read" in out, out)

        home = make_home(root / "h5", {"orphan": ["a.py"]},
                         records_text="{ not json")
        code, out = run(home, repo)
        check("a gap still exits 1 when the records file is CORRUPT",
              code == 1, out)

        home = make_home(root / "h6", {"orphan": ["a.py"]},
                         records_text=json.dumps({"plugins": "not-a-dict"}))
        code, out = run(home, repo)
        check("a gap still exits 1 when the records have the wrong shape",
              code == 1, out)

        # `entries or []` substitutes for a falsy value only, so a truthy
        # non-list reached the loop and crashed before any output.
        home = make_home(root / "h6b", {"orphan": ["a.py"]}, records_text=json.dumps(
            {"plugins": {"ai-config@Morrison-Lab": 7}}))
        code, out = run(home, repo)
        check("a truthy non-list entries value degrades rather than crashing",
              code == 1 and "Traceback" not in out, out)

        # An installPath that is not a string is filtered before it can reach
        # `Path()`, so the run stays clean rather than raising TypeError.
        home = make_home(root / "h6c", {"orphan": ["a.py"]}, records_text=json.dumps(
            {"plugins": {"ai-config@Morrison-Lab": [
                {"installPath": ["not", "a", "string"], "scope": "user"}]}}))
        code, out = run(home, repo)
        check("a non-string installPath does not crash the run",
              "Traceback" not in out, out)

        # A string that is simply not a real path is dropped quietly rather
        # than warned about: `Path().resolve()` is non-strict, so it returns
        # a path for anything spellable. The warn branch in `entries_for`
        # covers a genuine syscall failure, which no portable fixture can
        # provoke -- it is asserted here only that such a record does not
        # become a crash or a spurious match.
        home = make_home(root / "h6d", {"orphan": ["a.py"]}, records_text=json.dumps(
            {"plugins": {"ai-config@Morrison-Lab": [
                {"installPath": "C:\\no\\such\\pin", "scope": "user"}]}}))
        code, out = run(home, repo)
        check("a record naming no existing pin leaves that pin an orphan",
              "Traceback" not in out and "ORPHAN" in out, out)

        # A non-canonical installPath is exactly what `.resolve()` is for, and
        # nothing else in the suite distinguishes resolving from comparing raw.
        home = make_home(root / "h7b", {"named": ["a.py"]})
        cache = (root / "h7b" / "home" / ".claude" / "plugins" / "cache"
                 / "Morrison-Lab" / "ai-config")
        # A `.` component is normalised away by `PurePath` at construction,
        # so it is NOT a non-canonical path as far as comparison goes. `..`
        # is kept, which makes it the only spelling that actually exercises
        # `.resolve()`.
        noncanon = os.path.join(str(cache), "named", "..", "named")
        write(home / ".claude" / "plugins" / "installed_plugins.json",
              json.dumps({"plugins": {"ai-config@Morrison-Lab": [
                  {"installPath": noncanon, "scope": "project",
                   "projectPath": str(repo)}]}}))
        code, out = run(home, repo)
        check("a non-canonical installPath still names its pin",
              "ORPHAN" not in out, out)
        check("and its gap therefore fails as a NAMED pin",
              code == 1 and "INSTALLED pin is missing" in out, out)
        # TWO pins, one named and one not. A single-pin fixture cannot tell
        # the conditional increment from an unconditional one, because the
        # only pin present is the named one either way.
        home = make_home(root / "h7d", {"named": ["a.py"], "loose": ["a.py"]})
        cache = (root / "h7d" / "home" / ".claude" / "plugins" / "cache"
                 / "Morrison-Lab" / "ai-config")
        write(home / ".claude" / "plugins" / "installed_plugins.json",
              json.dumps({"plugins": {"ai-config@Morrison-Lab": [
                  pin_record(cache / "named", "project", repo)]}}))
        code, out = run(home, repo)
        check("the summary counts ONLY the pins a record names",
              "against 2 pin(s), 1 of them named by an install record" in out,
              out)

        # The mirror: the RECORD is canonical and the PIN is not, because the
        # home directory itself was spelled with a `.` component. Only
        # resolving the pin side matches these.
        home = make_home(root / "h7c", {"named": ["a.py"]})
        cache = (root / "h7c" / "home" / ".claude" / "plugins" / "cache"
                 / "Morrison-Lab" / "ai-config")
        write(home / ".claude" / "plugins" / "installed_plugins.json",
              json.dumps({"plugins": {"ai-config@Morrison-Lab": [
                  {"installPath": str((cache / "named").resolve()),
                   "scope": "project", "projectPath": str(repo)}]}}))
        (root / "h7c" / "side").mkdir(parents=True, exist_ok=True)
        code, out = run(home, repo,
                        home_as=Path(os.path.join(str(root / "h7c"), "side",
                                                  "..", "home")))
        check("a non-canonical HOME still matches its pin to the record",
              "ORPHAN" not in out and code == 1, out)

        # --- a checkout with no hooks/ is not a vacuous pass ---------------
        bare = make_repo(root / "h7", [], with_dir=False)
        home = make_home(root / "h7", {"good": ["a.py"]})
        code, out = run(home, bare)
        check("a --repo with no hooks/ exits 2 rather than passing vacuously",
              code == 2, out)
        check("and it says what it could not find",
              "no hooks directory" in out, out)

        # --- no cache at all is not a failure -------------------------------
        home = (root / "h8" / "home")
        (home / ".claude" / "plugins").mkdir(parents=True, exist_ok=True)
        code, out = run(home, repo)
        check("no plugin cache at all exits 0", code == 0, out)

    # --- describe_entries arithmetic, in process -------------------------
    import importlib.util
    spec = importlib.util.spec_from_file_location("chd", SCRIPT)
    chd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(chd)

    project = str(Path(tempfile.gettempdir()) / "proj")
    both = {"scope": "user", "projectPath": project, "installPath": "X"}
    other = {"scope": "project", "projectPath": project + "-other",
             "installPath": "X"}
    label = chd.describe_entries([both, other], project)
    check("a record matching BOTH predicates does not hide another project's",
          "1 other project install(s)" in label, label)

    triple = [dict(both), dict(both), dict(both)]
    label = chd.describe_entries(triple, project)
    check("fully overlapping records do not produce a negative residual",
          "other project install(s)" not in label, label)

    label = chd.describe_entries([], project)
    check("a pin no record names is labelled ORPHAN", "ORPHAN" in label, label)

    # `Path.resolve()` on a string carrying a NUL raises ValueError on POSIX
    # and returns quietly on Windows, so a fixture written as a real NUL only
    # exercises the catch on one of the two platforms -- and the platform it
    # skips is the one the fix was wrongly derived from. Substituting the
    # module's own `Path` makes the case run identically everywhere.
    class _Exploding(type(Path())):
        def resolve(self, strict=False):
            raise ValueError("embedded null character in path")

    real_path, chd.Path = chd.Path, _Exploding
    try:
        warned = []
        got = chd.entries_for(real_path("X"),
                              [{"installPath": "a\0b", "scope": "user"}],
                              warn=warned.append)
        ok = got == [] and warned and "could not resolve" in warned[0]
    except ValueError:
        ok = False
        warned = ["ValueError escaped entries_for"]
    finally:
        chd.Path = real_path
    check("a ValueError from resolve() is warned about, not raised",
          ok, "; ".join(warned) if warned else "no warning emitted")

    print(f"\n{CHECKS} checks, {len(FAILURES)} failure(s)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
