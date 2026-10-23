#!/usr/bin/env python3
"""Tests for hooks/no-oversized-pr-push.py (ai-config#4698).

Run: python3 hooks/test-no-oversized-pr-push.py [hooks/no-oversized-pr-push.py]
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "no-oversized-pr-push.py")
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, env=ENV)


def make_repo(files):
    """A repo with origin/main at a base commit and a branch adding `files` ({path: lines})."""
    d = tempfile.mkdtemp()
    git(d, "init", "-q", "-b", "main")
    with open(os.path.join(d, "base.txt"), "w", encoding="utf-8") as f:
        f.write("base\n")
    git(d, "add", "-A")
    git(d, "commit", "-q", "-m", "base")
    git(d, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(d, "switch", "-q", "-c", "feature")
    for path, n in files.items():
        p = os.path.join(d, path)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write("".join(f"l{i}\n" for i in range(n)))
    git(d, "add", "-A")
    git(d, "commit", "-q", "-m", "change")
    return d


def run(command, cwd, raw=None):
    payload = raw if raw is not None else json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd})
    p = subprocess.run([sys.executable, HOOK], input=payload, capture_output=True, text=True)
    denied = False
    if p.stdout.strip():
        denied = json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    return p.returncode, denied


def new_path_cases():
    import importlib.util
    spec = importlib.util.spec_from_file_location("hook", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return [
        ("rename: plain arrow", mod.new_path("a.qmd => _freeze/b.json"), "_freeze/b.json"),
        ("rename: brace form", mod.new_path("chapters/{old => _freeze}/x.json"), "chapters/_freeze/x.json"),
        ("rename: brace with empty new side", mod.new_path("a/{old => }/x.qmd"), "a/x.qmd"),
        ("rename: no rename", mod.new_path("a/b.qmd"), "a/b.qmd"),
    ]


def check(label, ok):
    print(("  ok      " if ok else "  FAIL    ") + label)
    return 0 if ok else 1


def main():
    fails = 0
    sweep = make_repo({f"chapters/c{i}.qmd": 2 for i in range(25)})  # pds#244 shape
    big = make_repo({"big.qmd": 500})
    small = make_repo({"a.qmd": 20, "b.qmd": 20})
    edge = make_repo({f"f{i}.qmd": 30 for i in range(10)})
    over = make_repo({f"f{i}.qmd": 1 for i in range(11)})
    ignored = make_repo({**{f"_freeze/p{i}/x.json": 100 for i in range(30)}, "renv.lock": 900, "a.qmd": 5})

    cases = [
        ("sweep of 25 files is denied", run("git push -u origin feature", sweep), True),
        ("500-line change is denied", run("git push", big), True),
        ("small branch passes", run("git push", small), False),
        ("exactly at the cap passes", run("git push", edge), False),
        ("one file over the cap is denied", run("git push", over), True),
        ("frozen and lock files are not counted", run("git push", ignored), False),
        ("ALLOW_LARGE_PR=1 prefix passes", run("ALLOW_LARGE_PR=1 git push", sweep), False),
        ("chained push is still measured", run("git fetch && git push origin feature", sweep), True),
        ("git -C path push is measured at that path", run(f"git -C {sweep} push", small), True),
        ("a non-push command passes", run("git status", sweep), False),
        ("the word push in prose passes", run("echo 'git pushing is fun'", sweep), False),
        ("not a Bash call passes", run("", sweep, raw=json.dumps(
            {"tool_name": "Read", "tool_input": {"command": "git push"}, "cwd": sweep})), False),
        ("garbage stdin fails open", run("", sweep, raw="not json"), False),
        ("a directory that is not a repo fails open", run("git push", "/tmp"), False),
    ]
    for label, (rc, denied), want in cases:
        fails += check(label, rc == 0 and denied == want)
    for label, got, want in new_path_cases():
        fails += check(label, got == want)
    # On the default branch itself there is no PR to measure.
    git(sweep, "switch", "-q", "main")
    rc, denied = run("git push", sweep)
    fails += check("push from the default branch passes", rc == 0 and not denied)
    total = len(cases) + 1 + len(new_path_cases())
    print(f"\n{total - fails}/{total} correct")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
