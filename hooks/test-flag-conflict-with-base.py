#!/usr/bin/env python3
"""Test the flag-conflict-with-base guard.

Tests that a `git push` whose branch conflicts with the repository's default
branch surfaces a PreToolUse warning naming the conflicting paths and the
reversion risk, while clean branches, pushes of the base branch itself,
branches merely behind the base, and non-push commands stay silent.

Three properties get their own fixtures because a plausible implementation
gets each one wrong silently:

  * the base branch is resolved FROM THE REPOSITORY (`REPO_TRUNK`, whose
    default branch is `trunk`), not assumed to be `main`;
  * the fetch is load-bearing (`REPO_STALE`, where the conflicting commit
    exists on the remote but not yet in the clone's remote-tracking ref) --
    without it the check compares against the base as cloned and reports
    clean, which is a detector that never ran;
  * a branch merely BEHIND the base is staleness, not divergence
    (`REPO_BEHIND`), and must stay silent or the guard fires on every branch.

Run: python3 hooks/test-flag-conflict-with-base.py hooks/flag-conflict-with-base.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.abspath(
    "hooks/flag-conflict-with-base.py")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}

TEMP_DIRS = []

# The sentence ucdavis/bcs#908 removed, and the bound it replaced it with.
# Using the real text keeps the fixture recognizable as the measured case.
OLD_LINE = "The truth is known exactly by construction.\n"
NEW_LINE = "The truth is computed by Monte Carlo to a bounded standard error.\n"
REFLOWED = "The truth is known exactly\nby construction.\n"


def _git(d, *args):
    return subprocess.run(["git", "-C", d, *args], capture_output=True,
                          text=True, env=ENV, check=True).stdout.strip()


def _write(d, name, text):
    with open(os.path.join(d, name), "w", encoding="utf-8") as handle:
        handle.write(text)


def _origin(default_branch="main"):
    """A throwaway upstream repository with one commit on `default_branch`."""
    d = tempfile.mkdtemp(prefix="base-conflict-origin-")
    TEMP_DIRS.append(d)
    _git(d, "init", "-q", "-b", default_branch)
    _write(d, "simulation.qmd", OLD_LINE)
    _write(d, "other.qmd", "Untouched.\n")
    _git(d, "add", "-A")
    _git(d, "commit", "-qm", "base")
    return d


def _clone(origin):
    d = tempfile.mkdtemp(prefix="base-conflict-work-")
    TEMP_DIRS.append(d)
    subprocess.run(["git", "clone", "-q", origin, d], capture_output=True,
                   text=True, env=ENV, check=True)
    return d


def _advance_origin(origin):
    """The sibling PR merging: the base replaces the sentence."""
    _write(origin, "simulation.qmd", NEW_LINE)
    _git(origin, "commit", "-qam", "sibling PR: replace the claim")


def build(default_branch="main", branch="feat/estimand", conflict=True,
          fetch_into_clone=True, stay_on_base=False, branch_commits=True):
    """An (origin, clone) pair in one of the fixture shapes."""
    origin = _origin(default_branch)
    work = _clone(origin)
    _advance_origin(origin)
    if fetch_into_clone:
        _git(work, "fetch", "-q", "origin", default_branch)
    if not stay_on_base:
        _git(work, "checkout", "-q", "-b", branch)
    if branch_commits:
        if conflict:
            # The reflow of the very sentence the base just replaced.
            _write(work, "simulation.qmd", REFLOWED)
        else:
            _write(work, "other.qmd", "Edited somewhere else entirely.\n")
        _git(work, "commit", "-qam", "branch work")
    return work


# Conflicting branch, remote-tracking ref already current: the plain case.
REPO_CONFLICT = build()
# Same, but the default branch is named `trunk`.
REPO_TRUNK = build(default_branch="trunk")
# Conflicting branch whose clone has NOT fetched the sibling's merge. Only the
# hook's own fetch can see the conflict here.
REPO_STALE = build(fetch_into_clone=False)
# Branch edits a different file: merges cleanly.
REPO_CLEAN = build(conflict=False)
# HEAD is the base branch itself.
REPO_ON_BASE = build(stay_on_base=True)
# Branch has no commits of its own: behind the base, not diverged.
REPO_BEHIND = build(branch_commits=False)

# The hook's own fetch ADVANCES `REPO_STALE`'s remote-tracking ref, so the
# fixture stops being stale the first time any case runs against it -- and the
# mutation harness runs every case once per mutation. Left uncorrected, the
# negative control (S8) and the positive case (W5) both silently stop
# depending on the fetch, which is precisely the coincident-fixture failure
# `shared/coding/fact-check-code-logic.md` names. Caught here by the mutation
# run, not by reading the suite.
STALE_BASE_SHA = _git(REPO_STALE, "rev-parse", "refs/remotes/origin/main")


def restale():
    """Put `REPO_STALE`'s remote-tracking ref back where the clone left it."""
    _git(REPO_STALE, "update-ref", "refs/remotes/origin/main", STALE_BASE_SHA)


def run_hook(command, cwd, hook_path=HOOK, extra_env=None):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    env = {**ENV, **(extra_env or {})}
    proc = subprocess.run([sys.executable, hook_path],
                          input=json.dumps(payload), capture_output=True,
                          text=True, cwd=cwd, env=env)
    if proc.returncode != 0:
        sys.exit(f"FATAL: hook exited {proc.returncode} on {command!r}\n"
                 f"{proc.stderr.strip()}")
    if not proc.stdout.strip():
        return "silent", None
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        sys.exit(f"FATAL: hook emitted non-JSON on stdout ({exc}): "
                 f"{proc.stdout!r}")
    hso = out.get("hookSpecificOutput") or {}
    if "permissionDecision" in hso:
        sys.exit("FATAL: hook emitted permissionDecision="
                 f"{hso['permissionDecision']!r}; this guard must only warn")
    return ("WARN" if hso.get("additionalContext") else "silent"), out


# (id, command, cwd, extra_env, prepare, description). `prepare` runs
# immediately before the hook, so a fixture the hook itself mutates can be
# put back; `None` means the fixture is already in the right state.
SHOULD_WARN = [
    ("W1", "git push origin feat/estimand", REPO_CONFLICT, None, None,
     "branch conflicting with the base warns"),
    ("W2", f"git -C {REPO_CONFLICT} push origin feat/estimand", ROOT, None, None,
     "the push's own -C selects the repository"),
    ("W3", f"cd {REPO_CONFLICT} && git push", ROOT, None, None,
     "a cd followed by a bare push warns"),
    ("W4", "git push origin feat/estimand", REPO_TRUNK, None, None,
     "a repository whose default branch is `trunk` still warns"),
    ("W5", "git push origin feat/estimand", REPO_STALE, None, restale,
     "the hook's own fetch surfaces a conflict the clone could not yet see"),
]

SHOULD_STAY_SILENT = [
    ("S1", "git push origin feat/estimand", REPO_CLEAN, None, None,
     "a branch that merges cleanly with the base stays silent"),
    ("S2", "git push origin main", REPO_ON_BASE, None, None,
     "pushing the base branch itself stays silent"),
    ("S3", "git push origin feat/estimand", REPO_BEHIND, None, None,
     "a branch merely behind the base is staleness, not divergence"),
    ("S4", "git push --dry-run origin feat/estimand", REPO_CONFLICT, None, None,
     "a --dry-run push transfers nothing and stays silent"),
    ("S5", "git push --delete origin feat/estimand", REPO_CONFLICT, None, None,
     "a --delete push stays silent"),
    ("S6", "git status", REPO_CONFLICT, None, None,
     "a non-push git command stays silent"),
    ("S7", "echo 'git push origin main'", REPO_CONFLICT, None, None,
     "a command merely quoting a push stays silent"),
    # The negative control for W5, and the reason the fetch is not decoration:
    # with the fetch suppressed, the same repository and the same command
    # report clean. A guard without the fetch would look exactly like this on
    # every stale clone.
    ("S8", "git push origin feat/estimand", REPO_STALE,
     {"BASE_CONFLICT_NO_FETCH": "1"}, restale,
     "without the fetch, the stale clone reports clean (negative control)"),
]

NON_COMMAND_PAYLOADS = [
    ({"tool_name": "Bash", "tool_input": None}, "null tool_input"),
    ({"tool_name": "Bash"}, "absent tool_input"),
    ({"tool_name": "Bash", "tool_input": {"command": 12345}},
     "command is not a string"),
    ({"tool_name": "Edit", "tool_input": {"file_path": "a.md"}},
     "non-Bash tool"),
]


def test_main():
    wrong = 0
    print("should WARN:")
    for case_id, command, cwd, extra_env, prepare, desc in SHOULD_WARN:
        if prepare:
            prepare()
        got, out = run_hook(command, cwd=cwd, extra_env=extra_env)
        is_ok = got == "WARN"
        if is_ok and out:
            ctx = out["hookSpecificOutput"].get("additionalContext", "")
            # The finding must name the conflicting path and the risk, or the
            # reader gets a merge chore rather than a reversion warning.
            if "simulation.qmd" not in ctx or "REVERT" not in ctx:
                is_ok = False
            if case_id == "W4" and "origin/trunk" not in ctx:
                is_ok = False
        wrong += not is_ok
        print(f"  {got:<6} {case_id:<4} {desc}")

    print("\nshould STAY SILENT:")
    for case_id, command, cwd, extra_env, prepare, desc in SHOULD_STAY_SILENT:
        if prepare:
            prepare()
        got, _ = run_hook(command, cwd=cwd, extra_env=extra_env)
        is_ok = got == "silent"
        wrong += not is_ok
        print(f"  {got:<6} {case_id:<4} {desc}")

    print("\nmalformed payloads (must exit 0, emit nothing):")
    for payload, desc in NON_COMMAND_PAYLOADS:
        proc = subprocess.run([sys.executable, HOOK],
                              input=json.dumps(payload), capture_output=True,
                              text=True, cwd=REPO_CONFLICT, env=ENV)
        is_ok = proc.returncode == 0 and not proc.stdout.strip()
        wrong += not is_ok
        print(f"  {'ok  ' if is_ok else 'WRONG':<6} {desc}")

    proc = subprocess.run([sys.executable, HOOK], input="not json",
                          capture_output=True, text=True, cwd=REPO_CONFLICT,
                          env=ENV)
    is_ok = proc.returncode == 0 and not proc.stdout.strip()
    wrong += not is_ok
    print(f"  {'ok  ' if is_ok else 'WRONG':<6} unparseable stdin fails open")

    return wrong


# Each entry mutates ONE documented clause out of the hook and states which
# cases must flip. A clause whose mutation flips nothing is a clause no test
# depends on -- which is the whole point of running these rather than reading
# the suite. See `shared/coding/fact-check-code-logic.md`, "Mutate the fix,
# not only the test".
MUTATIONS = {
    "M5 exit status": (
        "the legacy three-argument merge-tree always exits 0, so keying on "
        "its status can never fire",
        [('["merge-tree", "--write-tree", base_ref, "HEAD"]',
          '["merge-tree", base_ref, base_ref, "HEAD"]')],
        {"W1", "W2", "W3", "W4", "W5"},
    ),
    "fetch the base": (
        "without the fetch, a stale clone reports clean",
        [('got = _git(["fetch", "--quiet", "origin", base], cwd=git_root, timeout=20)',
          'got = None')],
        {"W5"},
    ),
    "M3 resolve base": (
        "assuming the base is named `main` misses a repository whose default "
        "is not",
        [('    head = _git_ok(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"],\n'
          '                   cwd=git_root)',
          '    head = None'),
         ('FALLBACK_BASES = ("main", "master", "trunk", "develop", "devel")',
          'FALLBACK_BASES = ("main",)')],
        {"W4"},
    ),
    "M4 skip the base": (
        "without the base-branch skip, pushing the base itself warns about "
        "its own divergence",
        [("        if _current_branch(git_root) == base:\n            continue",
          "        if False:\n            continue")],
        {"S2"},
    ),
    "M4 skip contained": (
        "without the ancestor skip, a branch merely behind the base is "
        "reported as diverged",
        [('        if _git_ok(["merge-base", "--is-ancestor", "HEAD", base_ref],\n'
          '                   cwd=git_root) is not None:\n            continue',
          '        if False:\n            continue')],
        {},
    ),
}


def test_mutations():
    with open(HOOK, encoding="utf-8") as handle:
        source = handle.read()

    print("\nmutation tests:")
    mutation_wrong = 0
    for clause, (statement, edits, expected_flips) in MUTATIONS.items():
        mutated = source
        for find, replace in edits:
            count = mutated.count(find)
            if count != 1:
                sys.exit(f"FATAL: anchor not present once in {HOOK} "
                         f"(found {count}):\n{find}")
            mutated = mutated.replace(find, replace)

        fd, path = tempfile.mkstemp(suffix=".py",
                                    dir=os.path.dirname(HOOK))
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(mutated)

        try:
            flipped = set()
            for case_id, cmd, cwd, extra_env, prepare, _ in SHOULD_WARN:
                if prepare:
                    prepare()
                got, _out = run_hook(cmd, cwd=cwd, hook_path=path,
                                     extra_env=extra_env)
                if got != "WARN":
                    flipped.add(case_id)
            for case_id, cmd, cwd, extra_env, prepare, _ in SHOULD_STAY_SILENT:
                if prepare:
                    prepare()
                got, _out = run_hook(cmd, cwd=cwd, hook_path=path,
                                     extra_env=extra_env)
                if got != "silent":
                    flipped.add(case_id)
        finally:
            os.unlink(path)

        ok = flipped == set(expected_flips)
        mutation_wrong += not ok
        note = f"flipped {sorted(flipped)}" if flipped else "flipped nothing"
        print(f"  {'ok  ' if ok else 'WRONG'} {clause:<20} {statement}\n"
              f"         {note}")

    return mutation_wrong


if __name__ == "__main__":
    w1 = test_main()
    w2 = test_mutations()
    for d in TEMP_DIRS:
        shutil.rmtree(d, ignore_errors=True)
    sys.exit(1 if (w1 or w2) else 0)
