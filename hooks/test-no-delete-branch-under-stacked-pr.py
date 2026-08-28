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
import json, os, sys
mode = os.environ.get("FAKE_GH_MODE", "child")
args = sys.argv[1:]

# Record the argv so the test can assert WHAT was queried, not merely that
# something was. A shim that ignores argv lets a mutated query ship green:
# swapping `headRefName` for `baseRefName`, or dropping `--base`, both make
# the guard warn on nearly every merge and neither changes a single result
# here unless the query itself is under test.
log = os.environ.get("FAKE_GH_LOG")
if log:
    with open(log, "a") as fh:
        fh.write(json.dumps(args) + "\\n")

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
    elif mode == "not-a-list":
        print('{"number": 750}')
    elif mode == "no-number-key":
        print('[{"title": "a"}]')
    elif mode == "null-number":
        print('[{"number": null}]')
    elif mode == "scalar":
        print('7')
    elif mode == "garbage":
        print('not json at all')
    elif mode == "fail":
        sys.stderr.write("boom\\n")
        sys.exit(1)
    sys.exit(0)
sys.exit(0)
"""


def run(command, mode="child", with_gh=True, capture_argv=False):
    """Run the hook. With capture_argv, also return the gh argvs it issued."""
    calls = []
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ)
        if capture_argv:
            env["FAKE_GH_LOG"] = os.path.join(tmp, "argv.log")
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
        if capture_argv:
            log = env.get("FAKE_GH_LOG")
            if log and os.path.exists(log):
                calls = [json.loads(line) for line in open(log) if line.strip()]
    return (proc, calls) if capture_argv else proc


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
    # Review finding: pflag accepts clustered boolean shorthand, so `-sd` is a
    # real `--delete-branch`. A matcher knowing only the bare `-d` reads it as
    # no delete -- the silent direction.
    ("gh pr merge 749 -R ucdavis/bcs -sd", "child",
     "clustered short flags: -sd is --squash --delete-branch"),
    ("gh pr merge 749 -R ucdavis/bcs -ds", "child", "clustered, other order"),
    # `gh pr merge` documents a URL and a branch name as targets, and
    # `gh pr view` resolves all three -- so the guard passes the token through
    # rather than classifying it.
    ("gh pr merge https://github.com/ucdavis/bcs/pull/749 -R ucdavis/bcs "
     "--squash --delete-branch", "child", "a URL target"),
    ("gh pr merge my-feature-branch -R ucdavis/bcs --squash --delete-branch",
     "child", "a branch-name target"),
    ("gh pr merge -R ucdavis/bcs -t 'Some title' 749 --delete-branch", "child",
     "a value-taking flag's argument is not mistaken for the PR target"),
    # `gh pr close` carries the SAME -d/--delete-branch flag (verified against
    # `gh pr close --help`). Deleting the branch is the hazard, not merging, so
    # a guard watching only `merge` leaves the incident reachable one
    # subcommand over.
    ("gh pr close 749 -R ucdavis/bcs --delete-branch", "child",
     "gh pr close --delete-branch is the same hazard"),
    ("gh pr close 749 -R ucdavis/bcs -d", "child", "gh pr close, short flag"),
    ("gh pr merge 749 -Rucdavis/bcs --delete-branch", "child",
     "-Rowner/repo concatenated, with neither space nor equals"),
    ("sudo gh pr merge 749 -R ucdavis/bcs --squash --delete-branch", "child",
     "a leading word before the command"),
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
    ("gh pr merge 749 -R ucdavis/bcs --squash --delete-branch=false", "child",
     "an explicitly disabled delete flag"),
    # Review finding: the docstring promises "Exit 0 always", and these four
    # shapes crashed it. `gh` returning valid JSON that is not a list of
    # objects carrying `number` is not hypothetical -- a schema change, an
    # error object, or an extension wrapping the output all produce it.
    ("gh pr merge 749 -R ucdavis/bcs --squash --delete-branch", "not-a-list",
     "gh returns a JSON object rather than a list"),
    ("gh pr merge 749 -R ucdavis/bcs --squash --delete-branch", "no-number-key",
     "list entries carry no `number` key"),
    ("gh pr merge 749 -R ucdavis/bcs --squash --delete-branch", "scalar",
     "gh returns a bare JSON scalar"),
    ("gh pr merge 749 -R ucdavis/bcs --squash --delete-branch", "garbage",
     "gh returns output that is not JSON at all"),
    ("gh pr merge 749 -R ucdavis/bcs --squash --delete-branch", "null-number",
     "an entry whose `number` is explicitly null"),
    # A clustered flag with no `d` in it is not a delete. Without this the
    # cluster branch can be mutated to fire on ANY cluster and stay green.
    ("gh pr merge 749 -R ucdavis/bcs -sm", "child",
     "a clustered flag carrying no d is not a delete"),
    ("gh pr view 749 -R ucdavis/bcs --delete-branch", "child",
     "a non-deleting gh pr subcommand, even carrying the flag text"),
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

    # The QUERY itself is under test, not merely that a query happened. Each
    # of these fields is load-bearing, and mutating any one of them leaves
    # every decision assertion above passing.
    _, calls = run("gh pr merge 749 -R ucdavis/bcs --squash --delete-branch",
                   "child", capture_argv=True)
    views = [c for c in calls if "view" in c]
    lists = [c for c in calls if "list" in c]
    if not views:
        failures.append("no `gh pr view` was issued to resolve the head branch")
    else:
        v = views[0]
        if "headRefName" not in " ".join(v):
            failures.append(
                "the view must ask for headRefName -- the branch this merge "
                f"DELETES. baseRefName is a different branch: {v}")
        if "-R" not in v or "ucdavis/bcs" not in v:
            failures.append(f"the view must be scoped to the named repo: {v}")
        if "749" not in v:
            failures.append(f"the view must name the PR being merged: {v}")
    if not lists:
        failures.append("no `gh pr list` was issued to find stacked children")
    else:
        l = lists[0]
        if "--base" not in l:
            failures.append(
                "the list must filter on --base: without it every open PR in "
                f"the repo reads as a stacked child: {l}")
        if "parent-branch" not in l:
            failures.append(
                f"the list must filter on the merged PR's head branch: {l}")
        if "--state" not in l or "open" not in l:
            failures.append(
                f"the list must be restricted to OPEN PRs: {l}")

    # The value-flag cases must be checked on the ARGV, not on warn-vs-silent:
    # the shim's `gh pr view` ignores its argument, so dropping "-t" from
    # VALUE_FLAGS misparses the target and the outcome never changes. This is
    # the test whose stated purpose was previously unenforced.
    for cmd, flag, why in [
        ("gh pr merge -R ucdavis/bcs -t 'Some title' 749 --delete-branch",
         "-t", "a subject"),
        ("gh pr merge -R ucdavis/bcs -b 'Some body' 749 --delete-branch",
         "-b", "a body"),
        ("gh pr merge -R ucdavis/bcs -A me@example.com 749 --delete-branch",
         "-A", "an author email"),
        # close-only, and the flag that adding `close` support let through:
        # its value was read as the PR target, silencing the guard on the very
        # command the subcommand support was added for.
        ("gh pr close -R ucdavis/bcs -c 'Closing this' 749 --delete-branch",
         "-c", "a closing comment"),
        ("gh pr close -R ucdavis/bcs --comment 'Closing' 749 -d",
         "--comment", "a closing comment, long form"),
    ]:
        _, calls = run(cmd, "child", capture_argv=True)
        views = [c for c in calls if "view" in c]
        if not views:
            failures.append(f"no view issued for the {flag} case ({why})")
        elif "749" not in views[0]:
            failures.append(
                f"{flag} consumed the PR target: the value ({why}) was queried "
                f"instead of 749 -- {views[0]}")

    # A deleting subcommand must be recognized by NAME, not by "anything under
    # `gh pr`". Without this, loosening the matcher to argv[1]=="pr" survives.
    _, calls = run("gh pr close 749 -R ucdavis/bcs --delete-branch", "child",
                   capture_argv=True)
    if not [c for c in calls if "view" in c]:
        failures.append("gh pr close --delete-branch issued no query at all")

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
