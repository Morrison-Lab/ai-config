"""Test the no-delete-branch-under-stacked-pr guard.

The command strings below are the real shapes, not invented ones. The incident
command was:

    gh pr merge 749 -R ucdavis/bcs --squash --delete-branch

and the sibling `no-unauthorized-merge` guard requires an explicit `-R`, so
every merge this corpus issues carries one. That is why a missing `-R` is
treated as "cannot determine" rather than as a case to warn on.

The network is stubbed. `gh` is replaced by a shim on PATH whose behaviour is
chosen by an env var, so the test asserts the guard's *decision* rather than
GitHub's state -- and so it runs offline.

Run:  python3 hooks/test-no-delete-branch-under-stacked-pr.py \\
          hooks/no-delete-branch-under-stacked-pr.py
"""
import json
import os
import stat
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

GH_SHIM = """#!/usr/bin/env python3
import os, sys
mode = os.environ.get("FAKE_GH_MODE", "child")
args = sys.argv[1:]
if "view" in args:
    print(os.environ.get("FAKE_GH_BRANCH", "parent-branch"))
    sys.exit(0)
if "list" in args:
    if mode == "child":
        print('[{"number": 750, "title": "stacked child"}]')
    elif mode == "two-children":
        print('[{"number": 750, "title": "a"}, {"number": 752, "title": "b"}]')
    elif mode == "none":
        print('[]')
    elif mode == "fail":
        sys.stderr.write("boom\\n")
        sys.exit(1)
    sys.exit(0)
sys.exit(0)
"""


def run(command, mode="child", with_gh=True):
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ)
        if with_gh:
            shim = os.path.join(tmp, "gh")
            with open(shim, "w") as fh:
                fh.write(GH_SHIM)
            os.chmod(shim, os.stat(shim).st_mode | stat.S_IEXEC)
            env["PATH"] = tmp + os.pathsep + env.get("PATH", "")
            env["FAKE_GH_MODE"] = mode
        else:
            # A PATH with no `gh` at all.
            env["PATH"] = tmp
        payload = {"tool_name": "Bash", "tool_input": {"command": command}}
        proc = subprocess.run(
            [sys.executable, HOOK], input=json.dumps(payload),
            capture_output=True, text=True, env=env, timeout=30,
        )
    return proc


SHOULD_WARN = [
    ("gh pr merge 749 -R ucdavis/bcs --squash --delete-branch", "child",
     "the incident command verbatim"),
    ("gh pr merge 749 -R ucdavis/bcs --squash -d", "child",
     "the short -d spelling"),
    ("ALLOW_MERGE=1 gh pr merge 749 -R ucdavis/bcs --merge --delete-branch",
     "child", "env-prefixed, as the merge guard requires"),
    ("gh pr merge 749 --repo ucdavis/bcs --squash --delete-branch", "child",
     "--repo long form"),
    ("gh pr merge 749 -R ucdavis/bcs --squash --delete-branch", "two-children",
     "several stacked children"),
    ("gh pr merge 749 -R ucdavis/bcs --squash --delete-branch && "
     "git checkout main", "child",
     "the real flag still warns when the command is chained"),
    ("gh pr merge 749 --repo=ucdavis/bcs --squash --delete-branch", "child",
     "--repo=owner/name with an equals sign"),
]

SHOULD_STAY_SILENT = [
    ("gh pr merge 749 -R ucdavis/bcs --squash --delete-branch", "none",
     "nothing is stacked on the branch"),
    ("gh pr merge 749 -R ucdavis/bcs --squash --delete-branch", "fail",
     "the query failed -- silence beats guessing"),
    ("gh pr merge 749 -R ucdavis/bcs --squash", "child",
     "no --delete-branch, so no branch is removed"),
    ("gh pr view 749 -R ucdavis/bcs --json state", "child",
     "not a merge at all"),
    ("git push origin --delete some-branch", "child",
     "a bare branch delete is a different command"),
    ("gh pr merge -R ucdavis/bcs --squash --delete-branch", "child",
     "no PR number to resolve"),
    ("gh pr merge 749 --squash --delete-branch", "child",
     "no -R, so the repo is ambiguous"),
    # The review finding: a chained post-merge cleanup carries `git branch -d`,
    # whose `-d` a whole-string scan cannot distinguish from `gh pr merge -d`.
    # This is the repo's own post-merge sequence, so a guard that fires here
    # fires on the commonest chain there is.
    ("gh pr merge 749 -R ucdavis/bcs --squash && git checkout main && "
     "git branch -d some-branch", "child",
     "chained `git branch -d` is not this merge's delete flag"),
    ("gh pr merge 749 -R ucdavis/bcs --squash; git branch -d other", "child",
     "same, separated by a semicolon"),
    ("git branch -d some-branch && gh pr merge 749 -R ucdavis/bcs --squash",
     "child", "same, with the cleanup first"),
    ("gh pr merge https://github.com/ucdavis/bcs/pull/749 -R ucdavis/bcs "
     "--squash --delete-branch", "child",
     "a URL target yields no number to query with"),
    ("gh pr merge 749 -R ucdavis/bcs --squash --delete-branch=false", "child",
     "an explicitly disabled delete flag"),
]


def main():
    failures = []

    for command, mode, why in SHOULD_WARN:
        proc = run(command, mode)
        if proc.returncode != 0:
            failures.append(f"WARN case exited {proc.returncode}: {why}")
            continue
        # Assert the PAYLOAD SHAPE, not just that something was printed: a
        # hook whose output is not the shape the harness reads is inert, and
        # a stderr-only version of this guard was exactly that.
        try:
            emitted = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError:
            failures.append(f"warn output is not JSON: {why}\n  {proc.stdout[:120]}")
            continue
        hso = emitted.get("hookSpecificOutput") or {}
        if hso.get("hookEventName") != "PreToolUse":
            failures.append(f"missing/incorrect hookEventName: {why}")
        if "additionalContext" not in hso:
            failures.append(f"missing additionalContext: {why}")
        if "systemMessage" not in emitted:
            failures.append(f"missing systemMessage: {why}")
        if "#750" not in json.dumps(emitted):
            failures.append(f"warning does not name the child PR: {why}")

    for command, mode, why in SHOULD_STAY_SILENT:
        proc = run(command, mode)
        if proc.returncode != 0:
            failures.append(f"SILENT case exited {proc.returncode}: {why}")
        elif proc.stdout.strip() or proc.stderr.strip():
            failures.append(
                f"expected silence, got output: {why}\n  {command}\n"
                f"  {(proc.stdout or proc.stderr).strip()[:120]}")

    # `gh` absent entirely: the guard must not raise, and must not warn.
    proc = run("gh pr merge 749 -R ucdavis/bcs --squash --delete-branch",
               with_gh=False)
    if proc.returncode != 0 or proc.stdout.strip() or proc.stderr.strip():
        failures.append("with no gh on PATH the guard must exit 0 and stay silent")

    # Malformed stdin must not raise either.
    proc = subprocess.run([sys.executable, HOOK], input="not json",
                          capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        failures.append("malformed stdin must exit 0")

    if failures:
        print("FAIL")
        for f in failures:
            print("  - " + f)
        return 1
    total = len(SHOULD_WARN) + len(SHOULD_STAY_SILENT) + 2
    print(f"ok - {total} cases "
          f"({len(SHOULD_WARN)} warn, {len(SHOULD_STAY_SILENT)} silent, 2 degraded)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
