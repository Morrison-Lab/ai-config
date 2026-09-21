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


def run(home, repo, project=None):
    env = dict(os.environ)
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)          # Path.home() reads this on Windows
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

    check("a pin no record names is labelled ORPHAN",
          "ORPHAN" in chd.describe_entries([], project))

    print(f"\n{CHECKS} checks, {len(FAILURES)} failure(s)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
