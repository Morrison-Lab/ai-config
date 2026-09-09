"""Test the flag-dispatch-over-uncommitted guard.

Three decisions carry the value, and each has a negative case because each
would otherwise misfire on ordinary work:

WRITE-CAPABLE ONLY: an `isolation: worktree` launch gets a fresh tree, and a
brief that declares the agent read-only cannot destroy anything. Warning on
those trains the reader to ignore this.

PROMPT PATHS FIRST: the dispatch that lost work named a worktree in a
DIFFERENT repository from the session cwd, so a cwd-only check misses the
real case.

WARN, NEVER BLOCK: handing an agent a dirty tree to review is legitimate.

Run: python3 hooks/test-flag-dispatch-over-uncommitted.py \
         hooks/flag-dispatch-over-uncommitted.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]


def make_repo(dirty, untracked=False):
    """A real git repo, optionally dirty (tracked edit) and/or untracked."""
    d = tempfile.mkdtemp()
    run = lambda *a: subprocess.run(["git", "-C", d, *a], capture_output=True)
    run("init", "-q")
    run("config", "user.email", "t@t")
    run("config", "user.name", "t")
    open(os.path.join(d, "f.txt"), "w").write("one\n")
    run("add", "-A")
    run("commit", "-qm", "init")
    if dirty:
        open(os.path.join(d, "f.txt"), "w").write("two\n")
    if untracked:
        open(os.path.join(d, "build_output.log"), "w").write("cruft\n")
    return d


def run_hook(tool_input, cwd, tool="Agent"):
    payload = json.dumps({"tool_name": tool, "tool_input": tool_input,
                          "cwd": cwd})
    r = subprocess.run([sys.executable, HOOK], input=payload,
                       capture_output=True, text=True)
    assert '"permissionDecision"' not in r.stdout, "guard must never block"
    assert '"decision": "block"' not in r.stdout, "guard must never block"
    if not r.stdout.strip():
        return False
    ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
    return "flag-dispatch-over-uncommitted" in ctx


def main():
    passes = failures = 0
    dirty = make_repo(True)
    clean = make_repo(False)

    def check(label, got, want):
        nonlocal passes, failures
        if got == want:
            print(f"PASS: {label}"); passes += 1
        else:
            print(f"FAIL: {label} (expected {want}, got {got})"); failures += 1

    # The reported incident: a dirty tree named in the prompt, cwd elsewhere.
    check("a dirty worktree named in the prompt warns (the reported case)",
          run_hook({"prompt": f"Review the diff in {dirty} please."}, clean),
          True)
    check("a dirty session cwd warns",
          run_hook({"prompt": "Review the diff."}, dirty), True)
    check("a clean tree does not warn",
          run_hook({"prompt": f"Review {clean}."}, clean), False)

    # WRITE-CAPABLE gate.
    check("an isolation:worktree launch does not warn",
          run_hook({"prompt": f"Review {dirty}.", "isolation": "worktree"},
                   dirty), False)
    for phrase in ("Read-only; do not edit anything.",
                   "Work read-only inside that worktree.",
                   "Do NOT edit any files."):
        check(f"a read-only brief does not warn ({phrase[:22]}...)",
              run_hook({"prompt": f"Review {dirty}. {phrase}"}, dirty), False)

    # Untracked-only dirt must NOT warn. `git checkout -- .`, the command
    # this hook's warning is about, does not touch untracked files, so
    # firing on a stray log or .DS_Store would make a claim about a
    # destructive command that cannot destroy what triggered it -- on a
    # large fraction of ordinary dispatches.
    untracked_only = make_repo(False, untracked=True)
    check("a repo dirty only with untracked cruft does not warn",
          run_hook({"prompt": f"Work in {untracked_only}."}, clean), False)
    both = make_repo(True, untracked=True)
    check("a tracked edit still warns even alongside untracked cruft",
          run_hook({"prompt": f"Work in {both}."}, clean), True)

    # A SCOPED exclusion is not a read-only brief. "do not edit the tests,
    # only the source" permits writing, and reading it as read-only silenced
    # the guard on exactly the dispatch it exists for.
    for phrase in ("Do not edit the tests, only the source.",
                   "do not modify the fixtures, only the docs"):
        check(f"a scoped exclusion still warns ({phrase[:26]}...)",
              run_hook({"prompt": f"Work in {dirty}. {phrase}"}, clean), True)

    # `remote` isolation runs the agent elsewhere entirely, so the local
    # dirty tree is unreachable and a warning would be spurious.
    check("an isolation:remote launch does not warn",
          run_hook({"prompt": f"Review {dirty}.", "isolation": "remote"},
                   dirty), False)

    # Tool gate. Both dispatch names must fire: the harness reports a
    # subagent launch under either, and registering for one is a false
    # negative that remind-brief-premises.py already had and fixed.
    check("a Task-named dispatch warns too",
          run_hook({"prompt": f"Review {dirty}."}, clean, tool="Task"), True)
    check("a non-dispatch tool does not warn",
          run_hook({"prompt": f"Review {dirty}."}, dirty, tool="Bash"), False)

    # The manifest must bind BOTH names, or the code accepting them is
    # unreachable for the one it is not registered under.
    man = json.load(open(os.path.join(os.path.dirname(HOOK), "hooks.json")))
    bound = {e["matcher"] for group in man["hooks"].values() for e in group
             for h in e["hooks"]
             if h.get("script") == os.path.basename(HOOK)}
    check("registered for both Agent and Task",
          {"Agent", "Task"} <= bound, True)

    # A path in the prompt that is not a repo must not crash or warn.
    check("a non-repo path in the prompt does not warn",
          run_hook({"prompt": "See /tmp for scratch files."}, clean), False)
    check("a nonexistent path in the prompt does not warn",
          run_hook({"prompt": "See /no/such/dir/at/all here."}, clean), False)

    # The warning must name what is uncommitted, or the reader cannot act.
    payload = json.dumps({"tool_name": "Agent", "cwd": clean,
                          "tool_input": {"prompt": f"Review {dirty}."}})
    out = subprocess.run([sys.executable, HOOK], input=payload,
                         capture_output=True, text=True).stdout
    # Degrade to an empty context rather than raising. A mutation that stops
    # the hook firing at all would otherwise crash the suite here with a
    # JSONDecodeError instead of failing these two cases, which reads as a
    # broken test rather than as a killed mutant.
    try:
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    except Exception:
        ctx = ""
    check("the warning names the dirty path", dirty in ctx, True)
    check("the warning names the changed file", "f.txt" in ctx, True)

    # The candidate cap is a budget guard, not a matching rule: each path
    # costs a `git status`, and the hook's own registered timeout is 10s.
    # Exercised on `candidates()` directly, since standing up seven slow
    # repositories to observe it end-to-end would test the clock, not this.
    import importlib.util
    spec = importlib.util.spec_from_file_location("hookmod", HOOK)
    hookmod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hookmod)
    many = [tempfile.mkdtemp() for _ in range(9)]
    got = hookmod.candidates(" ".join(many), clean)
    # Assert a real bound, not the module's own constant. Reading
    # MAX_CANDIDATES here made the assertion self-referential: raising the
    # cap to 99 raised the bound with it and the test still passed. The
    # budget is what matters -- each candidate costs a `git status` and the
    # hook's registered timeout is 10s, so the cap has to stay small.
    # A literal, not `hookmod.MAX_CANDIDATES` -- reading the constant
    # under test made this self-referential once already. Kept tight
    # against the intended cap so raising it by even one fails here.
    check("the candidate list is capped at 3", len(got) <= 3, True)
    # Read the REGISTERED timeout from hooks.json rather than hard-coding
    # it: the budget is a relation between two files, and asserting a number
    # typed here would pass while the manifest said something else. An
    # earlier version asserted <= 20 under a name claiming 10.
    manifest = json.load(open(os.path.join(os.path.dirname(HOOK), "hooks.json")))
    registered = [h["timeout"]
                  for group in manifest["hooks"].values()
                  for entry in group
                  for h in entry["hooks"]
                  if h.get("script") == os.path.basename(HOOK)]
    # The hook is bound under BOTH dispatch names, so several registrations
    # are expected. What must hold is that they agree: a differing timeout
    # between them would make the budget a function of which name the
    # harness happened to use.
    check("every registration carries the same timeout",
          bool(registered) and len(set(registered)) == 1, True)
    budget = min(registered) if registered else 0
    check(f"worst-case status time fits the registered {budget}s budget",
          hookmod.STATUS_TIMEOUT_S * hookmod.MAX_CANDIDATES < budget, True)
    check("the cap keeps prompt paths ahead of the cwd",
          got[0] in many, True)

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
