"""Test the flag-stale-branch-mutation guard against real scratch git repos.

This hook reads LIVE repository state and persists a small per-(session,
repo) state file across separate hook invocations, so a fixture here is a
SEQUENCE of steps against one real repo: some steps invoke the hook (as the
harness would, before the tool runs), some steps run the git command for
real (simulating the tool actually executing, or simulating some OTHER
actor's interference). Only the verdict of the LAST hook-invoking step is
asserted; earlier hook calls in a sequence are there to build up state, the
same way `test-no-clobbering-push.py` builds a real remote before testing
against it.

Test case W1 is the incident sequence, as close to verbatim as a scripted
scratch-repo fixture can be: the same three branch names, the same three
Bash calls (checkout, commit, push), and the same "something else moved the
checkout in between" shape -- a bare `git checkout -b` run directly against
the repo, standing in for the subagent's own unisolated git commands, per
`shared/workflow/algorithmatize-checks.md`'s "Test the instrument against
the incident that prompted it".

The second half is a MUTATION check, per `shared/principles/fail-fast.md`.
Two clauses are reverted, independently, in a temporary copy of the hook's
SOURCE (never the module object -- this hook ships no external import, so a
plain text copy in a temp file behaves identically to the original, same as
`test-flag-unchained-branch-switch.py`), and the case whose verdict must flip
is confirmed to flip.

Run:  python3 hooks/test-flag-stale-branch-mutation.py \\
          hooks/flag-stale-branch-mutation.py
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid

HOOK = os.path.abspath(sys.argv[1])
_TMPDIRS = []
_COUNTER = [0]


def _run(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True, check=check)


def _write(path, name, content):
    with open(os.path.join(path, name), "w", encoding="utf-8") as handle:
        handle.write(content)


def _new_repo():
    """A fresh repo on `main` with one commit."""
    path = tempfile.mkdtemp()
    _TMPDIRS.append(path)
    _run(path, "init", "-q", "-b", "main")
    _run(path, "config", "user.email", "t@t.com")
    _run(path, "config", "user.name", "t")
    _write(path, "base.txt", "base\n")
    _run(path, "add", "base.txt")
    _run(path, "commit", "-qm", "base")
    return path


def _new_session():
    _COUNTER[0] += 1
    return f"test-session-{_COUNTER[0]}-{uuid.uuid4().hex[:8]}"


def call_hook(hook_path, command, cwd, session_id, extra_payload=None):
    """Invoke the hook once, as PreToolUse would, and return its parsed
    hookSpecificOutput (or {} if it printed nothing)."""
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "session_id": session_id,
        "cwd": cwd,
    }
    if extra_payload:
        payload.update(extra_payload)
    proc = subprocess.run(
        [sys.executable, hook_path],
        input=json.dumps(payload),
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        sys.exit(f"FATAL: hook exited {proc.returncode}\n{proc.stderr.strip()}")
    if not proc.stdout.strip():
        return {}
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        sys.exit(f"FATAL: hook emitted non-JSON on stdout ({exc}): {proc.stdout!r}")
    hso = out.get("hookSpecificOutput") or {}
    if "permissionDecision" in hso:
        sys.exit(f"FATAL: hook emitted permissionDecision="
                 f"{hso['permissionDecision']!r}; this guard must only ever add "
                 "context, never allow/deny/ask")
    return hso


def verdict_of(hso):
    return "WARN" if hso.get("additionalContext") else "silent"


# ------------------------------------------------------------- scenarios
#
# Each scenario is a function (hook_path) -> (verdict, context_text) for its
# LAST hook call, run against a fresh repo and a fresh session id.

def sc_incident(hook_path):
    """W1: the incident, as close to verbatim as a scratch repo allows."""
    repo = _new_repo()
    sid = _new_session()
    call_hook(hook_path,
              "git checkout main && git checkout -b fix/909-spellcheck-awk-newline",
              repo, sid)
    _run(repo, "checkout", "-q", "main")
    _run(repo, "checkout", "-q", "-b", "fix/909-spellcheck-awk-newline")
    # "the adversarial-reviewer subagent... left the checkout on a different
    # branch" -- simulated as a direct git command, standing in for the
    # subagent's own unisolated tool calls.
    _run(repo, "checkout", "-q", "-b", "fix/892-slurm-env-and-srun-status")
    _write(repo, "base.txt", "changed\n")
    _run(repo, "add", "base.txt")
    hso = call_hook(hook_path, "git commit -m 'wip'", repo, sid)
    return verdict_of(hso), hso.get("additionalContext", "")


def sc_incident_push(hook_path):
    """The same incident's THIRD step: the push that reported false success."""
    repo = _new_repo()
    sid = _new_session()
    call_hook(hook_path, "git checkout -b fix/909-spellcheck-awk-newline", repo, sid)
    _run(repo, "checkout", "-q", "-b", "fix/909-spellcheck-awk-newline")
    _run(repo, "checkout", "-q", "-b", "fix/892-slurm-env-and-srun-status")
    hso = call_hook(hook_path,
                    "git push -u origin fix/909-spellcheck-awk-newline",
                    repo, sid)
    return verdict_of(hso), hso.get("additionalContext", "")


def sc_checkout_then_commit_same_branch(hook_path):
    """The ordinary case: checkout and commit chained in ONE call, nothing
    interfered. Must stay silent."""
    repo = _new_repo()
    sid = _new_session()
    hso = call_hook(hook_path,
                    "git checkout -b feat/x && git commit -am 'wip'",
                    repo, sid)
    return verdict_of(hso), hso.get("additionalContext", "")


def sc_cross_call_no_interference(hook_path):
    """Checkout in call 1 (real), commit in call 2, nothing interfered.
    Exercises the actual==selected drift check directly (call 2 carries no
    switch of its own), unlike the single-call case above."""
    repo = _new_repo()
    sid = _new_session()
    call_hook(hook_path, "git checkout -b feat/y", repo, sid)
    _run(repo, "checkout", "-q", "-b", "feat/y")
    _write(repo, "base.txt", "changed\n")
    _run(repo, "add", "base.txt")
    hso = call_hook(hook_path, "git commit -m 'wip'", repo, sid)
    return verdict_of(hso), hso.get("additionalContext", "")


def sc_no_prior_selection(hook_path):
    """A session that never explicitly checked anything out this session --
    nothing to compare against, must stay silent."""
    repo = _new_repo()
    sid = _new_session()
    _write(repo, "base.txt", "changed\n")
    _run(repo, "add", "base.txt")
    hso = call_hook(hook_path, "git commit -m 'first commit ever'", repo, sid)
    return verdict_of(hso), hso.get("additionalContext", "")


def sc_git_switch(hook_path):
    """`git switch`, not `git checkout`, is tracked the same way."""
    repo = _new_repo()
    sid = _new_session()
    call_hook(hook_path, "git switch -c feat/z", repo, sid)
    _run(repo, "switch", "-q", "-c", "feat/z")
    _run(repo, "checkout", "-q", "-b", "feat/other")
    hso = call_hook(hook_path, "git merge --no-edit main", repo, sid)
    return verdict_of(hso), hso.get("additionalContext", "")


def sc_detached_head(hook_path):
    repo = _new_repo()
    sid = _new_session()
    call_hook(hook_path, "git checkout -b feat/d", repo, sid)
    _run(repo, "checkout", "-q", "-b", "feat/d")
    _run(repo, "checkout", "-q", "--detach", "HEAD")
    _write(repo, "base.txt", "changed\n")
    _run(repo, "add", "base.txt")
    hso = call_hook(hook_path, "git commit -m 'wip'", repo, sid)
    return verdict_of(hso), hso.get("additionalContext", "")


def sc_nongit_cwd(hook_path):
    path = tempfile.mkdtemp()
    _TMPDIRS.append(path)
    sid = _new_session()
    hso = call_hook(hook_path, "git commit -m 'wip'", path, sid)
    return verdict_of(hso), hso.get("additionalContext", "")


def sc_malformed_tool_input(hook_path):
    repo = _new_repo()
    sid = _new_session()
    payload = {"tool_name": "Bash", "tool_input": None,
              "session_id": sid, "cwd": repo}
    proc = subprocess.run([sys.executable, hook_path], input=json.dumps(payload),
                          capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"FATAL: hook exited {proc.returncode}\n{proc.stderr.strip()}")
    return ("silent" if not proc.stdout.strip() else "WARN"), ""


def sc_different_tool(hook_path):
    repo = _new_repo()
    sid = _new_session()
    call_hook(hook_path, "git checkout -b feat/e", repo, sid)
    _run(repo, "checkout", "-q", "-b", "feat/e")
    _run(repo, "checkout", "-q", "-b", "feat/other2")
    payload = {"tool_name": "Agent",
              "tool_input": {"description": "x", "prompt": "x",
                             "command": "git commit -m x"},
              "session_id": sid, "cwd": repo}
    proc = subprocess.run([sys.executable, hook_path], input=json.dumps(payload),
                          capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"FATAL: hook exited {proc.returncode}\n{proc.stderr.strip()}")
    return ("silent" if not proc.stdout.strip() else "WARN"), ""


def sc_push_unrelated_branch(hook_path):
    """Drift IS present, but the push names some THIRD branch, not the one
    this session selected -- deliberately out of scope (see the hook's
    docstring), must stay silent."""
    repo = _new_repo()
    sid = _new_session()
    call_hook(hook_path, "git checkout -b feat/f", repo, sid)
    _run(repo, "checkout", "-q", "-b", "feat/f")
    _run(repo, "checkout", "-q", "-b", "feat/other3")
    hso = call_hook(hook_path, "git push origin main", repo, sid)
    return verdict_of(hso), hso.get("additionalContext", "")


def sc_quoted_mention_in_commit_message(hook_path):
    """A commit MESSAGE that mentions `git checkout` must not itself count
    as a real switch (which would silently overwrite the recorded
    selection)."""
    repo = _new_repo()
    sid = _new_session()
    call_hook(hook_path, "git checkout -b feat/g", repo, sid)
    _run(repo, "checkout", "-q", "-b", "feat/g")
    _run(repo, "checkout", "-q", "-b", "feat/other4")
    _write(repo, "base.txt", "changed\n")
    _run(repo, "add", "base.txt")
    hso = call_hook(
        hook_path,
        "git commit -m \"note: previously ran git checkout main; git checkout -b decoy\"",
        repo, sid)
    return verdict_of(hso), hso.get("additionalContext", "")


def sc_comment_mention(hook_path):
    """A `#`-comment mentioning `git checkout` is not a real switch."""
    repo = _new_repo()
    sid = _new_session()
    call_hook(hook_path, "git checkout -b feat/h", repo, sid)
    _run(repo, "checkout", "-q", "-b", "feat/h")
    _run(repo, "checkout", "-q", "-b", "feat/other5")
    _write(repo, "base.txt", "changed\n")
    _run(repo, "add", "base.txt")
    hso = call_hook(hook_path,
                    "# git checkout decoy\ngit commit -m 'wip'",
                    repo, sid)
    return verdict_of(hso), hso.get("additionalContext", "")


def sc_heredoc_mention(hook_path):
    """A heredoc body writing out `git checkout` text (never executed) is
    not a real switch."""
    repo = _new_repo()
    sid = _new_session()
    call_hook(hook_path, "git checkout -b feat/i", repo, sid)
    _run(repo, "checkout", "-q", "-b", "feat/i")
    _run(repo, "checkout", "-q", "-b", "feat/other6")
    _write(repo, "base.txt", "changed\n")
    _run(repo, "add", "base.txt")
    hso = call_hook(
        hook_path,
        "cat <<'EOF' > /dev/null\ngit checkout decoy\nEOF\ngit commit -m 'wip'",
        repo, sid)
    return verdict_of(hso), hso.get("additionalContext", "")


def sc_stale_state_ttl(hook_path):
    """A state file older than the TTL is treated as unrecorded, not as a
    stale-but-live selection."""
    import hashlib
    repo = _new_repo()
    sid = _new_session()
    call_hook(hook_path, "git checkout -b feat/j", repo, sid)
    _run(repo, "checkout", "-q", "-b", "feat/j")
    _run(repo, "checkout", "-q", "-b", "feat/other7")
    common_dir = _run(repo, "rev-parse", "--git-common-dir").stdout.strip()
    if not os.path.isabs(common_dir):
        common_dir = os.path.normpath(os.path.join(repo, common_dir))
    key = hashlib.sha256(f"{sid}\n{common_dir}".encode()).hexdigest()[:16]
    state_path = os.path.join(tempfile.gettempdir(),
                              f".claude-branch-select-{key}.json")
    with open(state_path, "w", encoding="utf-8") as fh:
        json.dump({"branch": "feat/j", "ts": time.time() - 999999}, fh)
    _write(repo, "base.txt", "changed\n")
    _run(repo, "add", "base.txt")
    hso = call_hook(hook_path, "git commit -m 'wip'", repo, sid)
    return verdict_of(hso), hso.get("additionalContext", "")


def sc_pathspec_checkout_keeps_selection(hook_path):
    """`git checkout <file>` restores a file and selects no branch, so it
    must leave the recorded selection alone.

    Without the pathspec test, `base.txt` is recorded as the selected
    branch, and the very next ordinary commit -- on the branch this session
    really did check out, with no drift at all -- compares against it and
    warns. That is a false positive on an undrifted command, which is the
    one outcome this hook must never produce."""
    repo = _new_repo()
    sid = _new_session()
    call_hook(hook_path, "git checkout -b feat/path1", repo, sid)
    _run(repo, "checkout", "-q", "-b", "feat/path1")
    _write(repo, "base.txt", "scratch\n")
    call_hook(hook_path, "git checkout base.txt", repo, sid)
    _run(repo, "checkout", "-q", "--", "base.txt")
    _write(repo, "base.txt", "changed\n")
    _run(repo, "add", "base.txt")
    hso = call_hook(hook_path, "git commit -m 'wip'", repo, sid)
    return verdict_of(hso), hso.get("additionalContext", "")


def sc_pathspec_dot_keeps_selection(hook_path):
    """`git checkout .` -- the routine discard-all-local-edits form -- is a
    pathspec, not a branch called `.`. git rejects `.` as a ref component
    outright, so no branch of that name can exist."""
    repo = _new_repo()
    sid = _new_session()
    call_hook(hook_path, "git checkout -b feat/path2", repo, sid)
    _run(repo, "checkout", "-q", "-b", "feat/path2")
    call_hook(hook_path, "git checkout .", repo, sid)
    _write(repo, "base.txt", "changed\n")
    _run(repo, "add", "base.txt")
    hso = call_hook(hook_path, "git commit -m 'wip'", repo, sid)
    return verdict_of(hso), hso.get("additionalContext", "")


def sc_pathspec_does_not_mask_real_drift(hook_path):
    """The negative control for the two cases above.

    A pathspec checkout must leave the recorded selection intact rather than
    clearing it, so a GENUINE drift after one still warns, and the warning
    names the real selected branch."""
    repo = _new_repo()
    sid = _new_session()
    call_hook(hook_path, "git checkout -b feat/path3", repo, sid)
    _run(repo, "checkout", "-q", "-b", "feat/path3")
    call_hook(hook_path, "git checkout .", repo, sid)
    _run(repo, "checkout", "-q", "-b", "feat/other-path")
    _write(repo, "base.txt", "changed\n")
    _run(repo, "add", "base.txt")
    hso = call_hook(hook_path, "git commit -m 'wip'", repo, sid)
    return verdict_of(hso), hso.get("additionalContext", "")


def sc_create_flag_operand_is_never_a_pathspec(hook_path):
    """A token after `-b` names a branch to CREATE and admits no pathspec,
    so the pathspec test must not fire on it even when a file of that name
    exists. Selecting `base.txt` here is correct, so a later commit on a
    different branch drifts and warns."""
    repo = _new_repo()
    sid = _new_session()
    call_hook(hook_path, "git checkout -b base.txt", repo, sid)
    _run(repo, "checkout", "-q", "-b", "base.txt")
    _run(repo, "checkout", "-q", "-b", "feat/elsewhere")
    _write(repo, "base.txt", "changed\n")
    _run(repo, "add", "base.txt")
    hso = call_hook(hook_path, "git commit -m 'wip'", repo, sid)
    return verdict_of(hso), hso.get("additionalContext", "")


def sc_switch_operand_is_never_a_pathspec(hook_path):
    """`git switch` takes no pathspec, so a file-shaped operand there is
    still a branch name. Guards against the pathspec test being applied to
    the wrong subcommand."""
    repo = _new_repo()
    sid = _new_session()
    _run(repo, "checkout", "-q", "-b", "base.txt")
    _run(repo, "checkout", "-q", "-b", "feat/elsewhere2")
    call_hook(hook_path, "git switch base.txt", repo, sid)
    _write(repo, "base.txt", "changed\n")
    _run(repo, "add", "base.txt")
    hso = call_hook(hook_path, "git commit -m 'wip'", repo, sid)
    return verdict_of(hso), hso.get("additionalContext", "")


SHOULD_WARN = [
    ("W1", sc_incident, "TEST CASE: the incident, commit step"),
    ("W2", sc_incident_push, "TEST CASE: the incident, push step (sharper message)"),
    ("W3", sc_git_switch, "git switch (not checkout) is tracked the same way"),
    # These three carry a REAL `git commit` alongside a MENTION of a switch
    # that must not be read as a real one. If the mention were misread as a
    # real switch, this call would take the "explicit switch present" path
    # and return silently (and would corrupt the recorded selection with the
    # decoy branch name) instead of warning about the genuine drift -- so the
    # correct verdict here is WARN, and it doubles as the negative control
    # for the masking: W4/W5/W6's own content assertions below confirm the
    # warning names the REAL selected branch, never the decoy.
    ("W4", sc_quoted_mention_in_commit_message,
     "a commit MESSAGE mentioning git checkout is not read as a real switch"),
    ("W5", sc_comment_mention, "a `#`-comment mentioning git checkout is not read as a real switch"),
    ("W6", sc_heredoc_mention, "a heredoc BODY mentioning git checkout is not read as a real switch"),
    # The pathspec test must not go so far as to CLEAR the selection: these
    # three confirm a real drift still warns after a pathspec checkout, that
    # a `-b` operand is exempt from the test, and that `switch` never applies
    # it. Together they are the negative control for S13/S14.
    ("W7", sc_pathspec_does_not_mask_real_drift,
     "a pathspec checkout leaves the selection intact, so real drift still warns"),
    ("W8", sc_create_flag_operand_is_never_a_pathspec,
     "a `-b` operand is a branch to create even when a file of that name exists"),
    ("W9", sc_switch_operand_is_never_a_pathspec,
     "`git switch` takes no pathspec, so a file-shaped operand is still a branch"),
]

SHOULD_STAY_SILENT = [
    ("S1", sc_checkout_then_commit_same_branch,
     "checkout and commit chained in ONE call, no interference"),
    ("S2", sc_cross_call_no_interference,
     "checkout in an earlier call, commit in a later one, no interference"),
    ("S3", sc_no_prior_selection,
     "session never explicitly checked anything out -- nothing to compare"),
    ("S4", sc_detached_head, "detached HEAD -- no branch to compare against"),
    ("S5", sc_nongit_cwd, "cwd is not a git repository"),
    ("S6", sc_malformed_tool_input, "malformed tool_input -- fails open"),
    ("S7", sc_different_tool, "a different tool entirely, even carrying git text"),
    ("S8", sc_push_unrelated_branch,
     "drift present, but the push names a branch this session never selected"),
    ("S12", sc_stale_state_ttl, "a state file older than the TTL is treated as unrecorded"),
    ("S13", sc_pathspec_checkout_keeps_selection,
     "`git checkout <file>` is a pathspec restore, not a branch selection"),
    ("S14", sc_pathspec_dot_keeps_selection,
     "`git checkout .` is a pathspec restore, not a branch called `.`"),
]

if not os.path.isfile(HOOK):
    sys.exit(f"FATAL: hook not found at {HOOK}")


def run_all(hook_path):
    results = {}
    for case_id, fn, _desc in SHOULD_WARN + SHOULD_STAY_SILENT:
        verdict, ctx = fn(hook_path)
        results[case_id] = (verdict, ctx)
    return results


print("Running scenarios against the real hook...")
RESULTS = run_all(HOOK)

wrong = 0
print("should WARN:")
for case_id, _fn, desc in SHOULD_WARN:
    got, _ctx = RESULTS[case_id]
    wrong += got != "WARN"
    print(f"  {got:<6} {case_id}  {desc}")

print("\nshould STAY SILENT:")
for case_id, _fn, desc in SHOULD_STAY_SILENT:
    got, _ctx = RESULTS[case_id]
    wrong += got != "silent"
    print(f"  {got:<6} {case_id}  {desc}")

total = len(SHOULD_WARN) + len(SHOULD_STAY_SILENT)
print(f"\n{total - wrong}/{total} correct" + ("" if wrong == 0 else f"  ({wrong} WRONG)"))

# Content assertions: the sharper push message must actually name the push
# hazard, not just fire.
w2_ctx = RESULTS["W2"][1]
content_wrong = 0
if "NAMED ref" not in w2_ctx and "NAMED" not in w2_ctx:
    print("FAIL: W2's message does not call out that git push names a ref, not HEAD")
    content_wrong += 1
if "fix/909-spellcheck-awk-newline" not in w2_ctx:
    print("FAIL: W2's message does not name the pushed branch")
    content_wrong += 1
w1_ctx = RESULTS["W1"][1]
if "fix/892-slurm-env-and-srun-status" not in w1_ctx or "fix/909-spellcheck-awk-newline" not in w1_ctx:
    print("FAIL: W1's message does not name both the selected and actual branch")
    content_wrong += 1

for case_id, real_branch in (("W4", "feat/g"), ("W5", "feat/h"), ("W6", "feat/i")):
    ctx = RESULTS[case_id][1]
    if real_branch not in ctx:
        print(f"FAIL: {case_id}'s message does not name the REAL selected branch "
             f"({real_branch}) -- the decoy mention may have overwritten it")
        content_wrong += 1
    if "decoy" in ctx:
        print(f"FAIL: {case_id}'s message names the DECOY branch -- the quoted/"
             "commented/heredoc mention was read as a real switch")
        content_wrong += 1

# ------------------------------------------------------------ mutation harness

with open(HOOK, encoding="utf-8") as handle:
    SOURCE = handle.read()

# Two independent clauses, reverted one at a time in a temp copy of the
# SOURCE. Each must flip the verdict of at least one declared case.
MUTATIONS = {
    "no-drift-guard": (
        "the actual==selected check that keeps an undisturbed checkout silent",
        [("    if actual == selected:\n        return None  # no drift",
          "    if False:\n        return None  # no drift")],
        {"S2"},  # S2 is the case that reaches this line without an in-call switch
    ),
    "push-must-match-selected": (
        "the push special case requires the NAMED branch to equal what this "
        "session selected, not just any drift",
        [('        if branch and branch == selected:',
          "        if branch:")],
        {"S8"},
    ),
}

print("\nmutation tests (revert one clause, see which cases flip):")
mutation_wrong = 0
with tempfile.TemporaryDirectory() as tmp:
    for clause, (statement, edits, expected_flips) in MUTATIONS.items():
        mutated = SOURCE
        for find, replace in edits:
            if mutated.count(find) != 1:
                sys.exit(f"FATAL: clause {clause}'s anchor is not present exactly "
                         f"once in {HOOK} (found {mutated.count(find)}). Re-derive "
                         f"the anchor.\n---\n{find}\n---")
            mutated = mutated.replace(find, replace)

        mutant_path = os.path.join(tmp, f"mutant-{clause}.py")
        with open(mutant_path, "w", encoding="utf-8") as fh:
            fh.write(mutated)

        flipped = set()
        for case_id in expected_flips | {"S1", "S3"}:  # a couple of controls too
            fn = dict((c, f) for c, f, _ in SHOULD_WARN + SHOULD_STAY_SILENT)[case_id]
            expected = "WARN" if case_id in dict((c, 1) for c, _, _ in SHOULD_WARN) else "silent"
            got, _ctx = fn(mutant_path)
            if got != expected:
                flipped.add(case_id)

        ok = expected_flips <= flipped
        mutation_wrong += not ok
        note = ("flipped " + ", ".join(sorted(flipped))) if flipped else "NOTHING FLIPPED -- untested"
        print(f"  {'ok  ' if ok else 'WRONG'} {clause:<28} {statement}\n         {note}")

print(f"\n{len(MUTATIONS) - mutation_wrong}/{len(MUTATIONS)} clauses behaved as declared under reversion")

sys.exit(1 if (wrong or content_wrong or mutation_wrong) else 0)
