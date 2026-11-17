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


def make_repo(files, attrs=None):
    """A repo with origin/main at a base commit and a branch adding `files` ({path: lines}).

    `attrs`, when given, is the base commit's `.gitattributes`.
    """
    d = tempfile.mkdtemp()
    git(d, "init", "-q", "-b", "main")
    with open(os.path.join(d, "base.txt"), "w", encoding="utf-8") as f:
        f.write("base\n")
    if attrs is not None:
        with open(os.path.join(d, ".gitattributes"), "w", encoding="utf-8") as f:
            f.write(attrs)
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


def run(command, cwd, raw=None, pr=None):
    """Run the hook; `pr` is the open PR the API would return (None for none)."""
    payload = raw if raw is not None else json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd})
    env = {**os.environ, "NO_OVERSIZED_PR_PUSH_PR_JSON": json.dumps(pr)}
    p = subprocess.run([sys.executable, HOOK], input=payload, capture_output=True,
                       text=True, env=env)
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

    figs = make_repo({"c/_fig-a-3d.qmd": 250, "c/_fig-b-3d.qmd": 250, "c/x.qmd": 10})
    many_figs = make_repo({f"c/_fig-{i}.qmd": 5 for i in range(11)})

    # lds#2355 shape: two committed generator outputs plus a small hand edit.
    by_module = {"c/_sub/definitions/_by-module.qmd": 270,
                 "c/_sub/results/_by-module.qmd": 270, "c/x.qmd": 10}
    gen_marked = make_repo(by_module, attrs="**/_by-module.qmd linguist-generated\n")
    gen_true = make_repo(by_module, attrs="**/_by-module.qmd linguist-generated=true\n")
    gen_false = make_repo(by_module, attrs="**/_by-module.qmd linguist-generated=false\n")
    gen_unmarked = make_repo(by_module)

    renames = make_repo({f"old/r{i}.qmd": 5 for i in range(12)})
    git(renames, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(renames, "mv", "old", "new")
    git(renames, "commit", "-q", "-m", "move")

    # gha#2082 shape: a new capability plus the registration lists gha CI requires.
    capability = {"check-x/action.yml": 10, "check-x/check-x.py": 100,
                  "check-x/tests/test_check_x.py": 80,
                  ".github/workflows/check-x.yml": 20, "examples/check-x.yml": 10,
                  "website/reference/check-x.qmd": 20, "website/_quarto.yml": 1,
                  "README.md": 3, "CLAUDE.md": 2, "changelog.d/add-check-x.added.md": 2,
                  ".github/workflows/_selftest.yml": 20, "check-x/README.md": 1}
    new_cap = make_repo(capability)
    no_workflow = make_repo({k: v for k, v in capability.items()
                             if k != ".github/workflows/check-x.yml"})
    big_cap = make_repo({**capability, "check-x/check-x.py": 400})
    big_readme = make_repo({**capability, "README.md": 250})
    other_fragments = make_repo({**capability, **{f"changelog.d/other-{i}.md": 1
                                                  for i in range(8)}})

    def push_tip(d):
        """Publish the branch to a bare origin, as an earlier approved push did."""
        bare = tempfile.mkdtemp()
        git(bare, "init", "-q", "--bare")
        git(d, "remote", "add", "origin", bare)
        git(d, "push", "-q", "origin", "feature")
        git(d, "update-ref", "refs/remotes/origin/feature", "HEAD")
        return bare

    def add_files(d, names, message):
        for name in names:
            with open(os.path.join(d, name), "a", encoding="utf-8") as f:
                f.write("x\n")
        git(d, "add", "-A")
        git(d, "commit", "-qm", message)

    # A branch pushed over the cap, then a small fix on top of it.
    pushed = make_repo({f"f{i}.qmd": 1 for i in range(12)})
    push_tip(pushed)
    add_files(pushed, ["f0.qmd"], "fix")
    pushed_big = make_repo({f"f{i}.qmd": 1 for i in range(12)})
    push_tip(pushed_big)
    add_files(pushed_big, [f"g{i}.qmd" for i in range(11)], "more")
    # Pushed under the cap, then pushed over it by a small commit.
    crossing = make_repo({f"f{i}.qmd": 1 for i in range(10)})
    push_tip(crossing)
    add_files(crossing, ["f10.qmd"], "cross")
    # The tracking ref says over-cap, but the server's branch is not that tip.
    stale = make_repo({f"f{i}.qmd": 1 for i in range(12)})
    stale_bare = push_tip(stale)
    git(stale_bare, "update-ref", "refs/heads/feature",
        subprocess.run(["git", "rev-parse", "HEAD~1"], cwd=stale, capture_output=True,
                       text=True, check=True).stdout.strip())
    add_files(stale, ["f0.qmd"], "fix")

    cases = [
        ("a new gha capability's registration files are not counted (gha#2082)",
         run("git push", new_cap), False),
        ("registration files count without the new reusable workflow",
         run("git push", no_workflow), True),
        ("a new capability's own lines still count", run("git push", big_cap), True),
        ("a registration file's lines still count", run("git push", big_readme), True),
        ("changelog fragments not naming the capability still count",
         run("git push", other_fragments), True),
        ("a stale tracking ref does not stand in for the server's tip",
         run("git push", stale), True),
        ("an open PR labelled size-exempt passes",
         run("git push", sweep, pr={"labels": [{"name": "size-exempt"}], "body": ""}), False),
        ("an open PR saying mechanical, content-identical passes",
         run("git push", sweep, pr={"labels": [], "body": "A mechanical, content-identical move."}),
         False),
        ("an open PR with neither exemption is still measured",
         run("git push", sweep, pr={"labels": [{"name": "P1"}], "body": "A sweep."}), True),
        ("a small fix on top of an already-pushed over-cap tip passes",
         run("git push", pushed), False),
        ("an over-cap addition on top of an over-cap tip is denied",
         run("git push", pushed_big), True),
        ("a small push that takes an under-cap tip over the cap is denied",
         run("git push", crossing), True),
        ("12 pure renames are not counted", run("git push", renames), False),
        ("new figure subfiles' lines are free", run("git push", figs), False),
        ("new figure subfiles still count as files", run("git push", many_figs), True),
        ("sweep of 25 files is denied", run("git push -u origin feature", sweep), True),
        ("500-line change is denied", run("git push", big), True),
        ("small branch passes", run("git push", small), False),
        ("exactly at the cap passes", run("git push", edge), False),
        ("one file over the cap is denied", run("git push", over), True),
        ("frozen and lock files are not counted", run("git push", ignored), False),
        ("linguist-generated paths are not counted", run("git push", gen_marked), False),
        ("linguist-generated=true paths are not counted", run("git push", gen_true), False),
        ("linguist-generated=false paths still count", run("git push", gen_false), True),
        ("unmarked generator output still counts", run("git push", gen_unmarked), True),
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
