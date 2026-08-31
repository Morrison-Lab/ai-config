"""Test the no-handrolled-verdict-parse guard.

Case 1 is the incident's own `capture(...)` alternation, pasted verbatim from
ai-config#1297's issue body rather than retyped from a summary -- per
`algorithmatize-checks.md`, you design a guard against your SUMMARY of an
incident, and the summary is what makes the guard miss.

The negatives matter as much: a guard that over-blocks gets switched off, and
then the case it exists for goes unprotected too. So a grep of this repo's own
docs for the phrase, an echo of it, a grep of this hook's own source, a careful
read followed by an honest report, and a parse discharged by the instrument all
have to pass.

Run: python3 hooks/test-no-handrolled-verdict-parse.py \\
         hooks/no-handrolled-verdict-parse.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

# ---------------------------------------------------------------------------
# The incident. `CAPTURE` is verbatim from ai-config#1297.
# ---------------------------------------------------------------------------
CAPTURE = ('capture("(?<v>Ready for merge|Needs more work|Needs minor changes'
           '|Needs work|Needs one fix)").v')

INCIDENT = (
    "gh api repos/Morrison-Lab/ai-config/issues/1278/comments --paginate "
    "| jq -r '[.[] | select(.body|test(\"\\\\*\\\\*Claude finished\"))] "
    "| last | .body | " + CAPTURE + "'"
)
INCIDENT_1257 = INCIDENT.replace("1278", "1257")


def checker(pr=None, repo=None):
    """A transcript event: an invocation of the instrument.

    `repo` produces the space-separated `-R OWNER/REPO` form the script grew in
    ai-config#1391. That form is the one CHECKER_CALL had to be widened for: a
    flag whose value is a separate token used to stop the scan before the PR
    number, so the PR went unrecorded and a later parse targeting that same PR
    was BLOCKED despite the instrument having answered for it -- a
    false-positive over-block, not a lenient discharge. The mutation case below
    pins that direction as its before/after pair (allow -> block).
    """
    cmd = "python3 scripts/check-pr-fully-clean.py"
    if repo is not None:
        cmd += f" -R {repo}"
    if pr is not None:
        cmd += f" {pr}"
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": cmd}}]}}


def checker_exit2(pr=None):
    """A transcript sequence where check-pr-fully-clean.py failed with exit 2 (e.g. gh missing)."""
    cmd = f"python3 scripts/check-pr-fully-clean.py {pr}" if pr is not None else "python3 scripts/check-pr-fully-clean.py"
    call_id = "toolu_exit2_12345"
    return [
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": call_id, "name": "Bash", "input": {"command": cmd}}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": call_id, "content": "`gh` is not installed or not on PATH.\nThis script requires the GitHub CLI; -R cannot substitute for it."}]}}
    ]


def checker_exit2_repo_resolve(pr=None):
    """A transcript sequence where check-pr-fully-clean.py failed with exit 2 on repo resolution."""
    cmd = f"python3 scripts/check-pr-fully-clean.py {pr}" if pr is not None else "python3 scripts/check-pr-fully-clean.py"
    call_id = "toolu_exit2_repo_12345"
    return [
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": call_id, "name": "Bash", "input": {"command": cmd}}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": call_id, "content": "Cannot resolve the repository from the current directory: fatal: not a git repository\nRun this from inside a git checkout, or pass -R OWNER/REPO."}]}}
    ]


def checker_with_unrelated_idless_tool_result(pr):
    """A transcript with a successful checker call followed by an unrelated id-less tool_result."""
    call_id = "toolu_success_9999"
    cmd = f"python3 scripts/check-pr-fully-clean.py {pr}"
    return [
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": call_id, "name": "Bash", "input": {"command": cmd}}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": call_id, "content": f"Checking ARDI / fully-clean status for Morrison-Lab/ai-config#{pr}...\nFULLY CLEAN on HEAD abcdef01!"}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "content": "total 8\ndrwxr-xr-x ... file.txt"}]}}
    ]


def read_checker():
    """A Grep whose PATTERN is the invocation. This is the case the tool-name
    skip exists for: the pattern carries an interpreter AND a PR number, so it
    satisfies CHECKER_CALL exactly as a real run would. `Grep` is the name this
    harness actually emits, measured from a live transcript."""
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Grep", "input": {
            "pattern": "python3 scripts/check-pr-fully-clean.py 1278",
            "path": "skills/"}}]}}


def mention_checker():
    """A Bash command that MENTIONS the invocation without running it. It
    arrives as Bash, so the tool-name skip cannot see it -- only the
    interpreter requirement in CHECKER_CALL keeps it from discharging."""
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {
            "command": "echo 'next step: check-pr-fully-clean.py 1278'"}}]}}


# (command, transcript events, should_block, label)
CASES = [
    # -- the incident, both directions ------------------------------------
    (INCIDENT, [], True,
     "THE INCIDENT: verbatim capture() over #1278's comments, no instrument"),
    (INCIDENT_1257, [], True,
     "the same sweep's other PR (#1257), the false-BLOCKED direction"),
    (INCIDENT, checker_exit2(1278), True,
     "exit-2 failure (gh missing) does NOT discharge the guard for #1278"),
    ("jq -r '.body|test(\"Ready for merge\")' /tmp/review-body.json", checker_exit2(1278), True,
     "exit-2 failure (gh missing) does NOT discharge untargeted parse"),
    (INCIDENT, checker_exit2_repo_resolve(1278), True,
     "repo resolution exit-2 failure does NOT discharge guard"),
    (INCIDENT, checker_with_unrelated_idless_tool_result(1278), False,
     "unrelated id-less tool_result does NOT wipe recorded successful checker run"),

    # -- other shapes of the same parse -----------------------------------
    ("gh api repos/o/r/issues/1278/comments | grep -m1 'Ready for merge'",
     [], True, "grep -m1 for the phrase over fetched review comments"),
    ("gh pr view 1278 -R o/r --json comments --jq "
     "'.comments[-1].body | test(\"Ready for merge\")'",
     [], True, "gh pr view --json comments piped through a jq test()"),
    ("jq -r '.body | capture(\"(?<v>Ready for merge)\").v' /tmp/review-1278.json",
     [], True, "a saved review body file re-parsed later"),
    ("gh api repos/o/r/issues/1278/comments | python3 -c "
     "\"import re,sys; print(re.search(r'Ready for merge', sys.stdin.read()))\"",
     [], True, "a python re.search over the same fetched body"),
    ("gh api repos/o/r/issues/1278/comments | jq -r "
     "'.[-1].body | scan(\"### Verdict.*\")'",
     [], True, "matching the structural marker is the same hand parse"),

    # -- discharge: the instrument answered ---------------------------------
    (INCIDENT, [checker(1278)], False,
     "discharged: check-pr-fully-clean.py already ran for THIS PR"),
    (INCIDENT, [checker()], True,
     "a bare invocation with no PR number does NOT discharge a numbered parse"),

    # -- the discharge must stay per-PR (algorithmatize-checks' trap) -------
    (INCIDENT, [checker(1257)], True,
     "running the instrument for a DIFFERENT PR must not discharge this one -- "
     "an over-broad discharge would license hand-rolling the rest of a sweep"),
    ("jq -r '.body|test(\"Ready for merge\")' /tmp/review-body.json",
     [checker(1278)], False,
     "no PR number in the command: any invocation discharges (documented "
     "leniency at the ambiguous edge)"),
    # -- a flag whose value is a separate token (ai-config#1391's -R) --------
    (INCIDENT, [checker(1278, repo="Morrison-Lab/gha")], False,
     "discharged: `-R OWNER/REPO 1278` still records the PR, though the flag's "
     "value sits between the flag and the number"),
    (INCIDENT, [checker(1257, repo="Morrison-Lab/gha")], True,
     "and the per-PR discipline survives the widening: `-R OWNER/REPO 1257` "
     "must not discharge a parse about #1278"),
    ("jq -r '.body|test(\"Ready for merge\")' /tmp/review-body.json",
     [checker(1278, repo="Morrison-Lab/gha")], False,
     "the lenient no-PR-number fallback is a property of the SUSPICIOUS "
     "command, not of what CHECKER_CALL captured -- it fires here because "
     "this parse names no PR"),

    (INCIDENT, [read_checker()], True,
     "a Grep whose PATTERN is the invocation is not a run of it"),
    (INCIDENT, [mention_checker()], True,
     "a Bash command that MENTIONS the invocation is not a run of it"),

    # -- the explicit override ---------------------------------------------
    ("ALLOW_HANDROLLED_VERDICT_PARSE=1 " + INCIDENT, [], False,
     "a real leading env assignment says the hand parse is deliberate"),
    (INCIDENT + " # ALLOW_HANDROLLED_VERDICT_PARSE=1 would suppress this",
     [], True,
     "a MENTION of the override is not an override"),

    # -- negatives: clause 2 (no matcher, just printing) --------------------
    ('echo "Ready for merge" >> /tmp/notes-issues-1278-comments.txt', [], False,
     "echoing the phrase is not parsing it"),
    ("gh api repos/o/r/issues/1278/comments --jq '.[-1].body'", [], False,
     "fetching and printing a review body, with no phrase matched at all"),

    # -- negatives: clause 3 (not review-derived) ---------------------------
    ("grep -rn 'Ready for merge' shared/workflow/", [], False,
     "grepping this repo's own docs, which quote the phrase constantly"),
    ("grep -n 'Needs more work' hooks/no-handrolled-verdict-parse.py", [], False,
     "grepping THIS HOOK's own source -- its filename contains 'verdict', so a "
     "loose saved-body heuristic would fire on the guard's own development"),
    ("grep -c '### Verdict' hooks/test-no-handrolled-verdict-parse.py", [], False,
     "grepping this very test file, for the same reason"),
    ("git log --oneline | grep 'Ready for merge'", [], False,
     "a matcher and the phrase, over data that is not a review body"),
    ("jq -r '.body|test(\"Ready for merge\")' /tmp/x.json", [], False,
     "THE KNOWN GAP, asserted rather than left accidental: a body saved to an "
     "arbitrarily-named file is not caught -- widening to any file would fire "
     "on every jq in the session"),

    # -- negatives: SELECTION is not extraction ----------------------------
    ("gh api repos/o/r/issues/1278/comments --paginate "
     "| jq -s '[.[][] | select(.body | test(\"\\\\*\\\\*Claude finished|### Verdict\"))] "
     "| last | .body'", [], False,
     "fully-clean.md's OWN documented query: select() picks the candidate "
     "comment and prints the whole body for a careful read -- blocking this "
     "would block the query the corpus tells you to run"),
    ("gh api repos/o/r/issues/1278/comments | jq -r "
     "'[.[]|select(.body|contains(\"### Verdict\"))]|last|.body' | tail -60",
     [], False,
     "the same shape with contains(), piped to a pager for reading"),
    ("gh api repos/o/r/pulls/1278/reviews | jq "
     "'[.[]|select(.body|contains(\"Needs more work\"))]'", [], False,
     "selecting the REVIEWS that mention a phrase and printing them is a "
     "filter over a corpus, not a verdict read -- this case was written as a "
     "block-case and the real-corpus measurement corrected it"),

    # -- negatives: unrelated work -----------------------------------------
    ("gh pr checks 1278 -R o/r", [], False, "an ordinary check-state query"),
    ("python3 scripts/check-pr-fully-clean.py 1278", [], False,
     "calling the instrument is obviously fine"),
    ("gh api repos/o/r/issues/1278/comments --jq '.[-1].user.login'", [], False,
     "reading a review body's metadata, matching no verdict phrase"),
]


# ---------------------------------------------------------------------------
# Clause-isolation mutants.
#
# Each reverts exactly ONE clause of the ANDed fire condition, paired with a
# case only that clause decides -- reverting one clause otherwise still passes
# any case a sibling happens to decide, which looks like a tested clause while
# testing none (`algorithmatize-checks.md`).
#
# Mutation is at SOURCE level, and the harness asserts the mutated text
# actually differs from the original before scoring. A mutation that no-ops
# reads exactly like one the tests caught, so an inapplicable mutant is its own
# reported outcome rather than a silent pass.
#
# (label, old, new, command, events, before, after)
# ---------------------------------------------------------------------------
DOC_GREP = "grep -rn 'Ready for merge' shared/workflow/"
HOOK_GREP = "grep -n 'Needs more work' hooks/no-handrolled-verdict-parse.py"
ECHO = 'echo "Ready for merge" >> /tmp/notes-issues-1278-comments.txt'
SAVED = "jq -r '.body|test(\"Ready for merge\")' /tmp/review-body.json"

MUTANTS = [
    ("the Bash-only gate",
     'if (payload.get("tool_name") or "") not in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"):\n            return 0',
     'pass',
     None, [], False, True),

    ("clause 5: the override prefix",
     "ALLOW_HANDROLLED_VERDICT_PARSE=1\\b",
     "ZZZ_NEVER_MATCHES=1\\b",
     "ALLOW_HANDROLLED_VERDICT_PARSE=1 " + INCIDENT, [], False, True),

    ("clause 2: the phrase must sit in a MATCHER's argument",
     "    for m in MATCHER_TOKEN.finditer(cmd):\n"
     "        start = m.end()",
     "    for m in [None]:\n"
     "        start = 0",
     ECHO, [], False, True),

    ("clause 3: the data must be REVIEW-derived",
     "    return bool(REVIEW_SOURCE.search(cmd) or SAVED_BODY.search(cmd))",
     "    return True",
     DOC_GREP, [], False, True),

    ("clause 3a: a saved body must be a DATA file, not any path named "
     "'verdict'",
     '\\S*(?:review|comment|verdict|body)\\S*\\.(?:json|jsonl|txt)\\b',
     '\\S*(?:review|comment|verdict|body)\\S*',
     HOOK_GREP, [], False, True),

    ("clause 2a: a phrase inside select() is SELECTION, not extraction",
     "            if any(a <= pos <= b for a, b in spans):\n"
     "                continue  # candidate selection, not extraction",
     "            if False:\n                continue",
     "gh api repos/o/r/issues/1278/comments --paginate "
     "| jq -s '[.[][] | select(.body | test(\"\\\\*\\\\*Claude finished|### Verdict\"))] "
     "| last | .body'", [], False, True),

    ("CHECKER_CALL admits a flag's separate value token",
     "(?:\\s+[^-\\s]\\S*)?",
     "",
     INCIDENT, [checker(1278, repo="Morrison-Lab/gha")], False, True),

    ("clause 4: the discharge is PER-PR",
     "        if targets <= checked:\n                return 0",
     "        if ran:\n                return 0",
     INCIDENT, [checker(1257)], True, False),

    ("clause 4a: the no-PR-number fallback discharge",
     "        elif ran:\n            return 0",
     "        elif False:\n            return 0",
     SAVED, [checker(1278)], False, True),

    ("clause 4b: a Grep FOR the invocation is not a run (tool-name skip)",
     'if name in ("read", "grep", "glob",',
     'if name in ("zzz-never-matches",',
     INCIDENT, [read_checker()], True, False),

    ("clause 4c: a discharging call needs an INTERPRETER, so a Bash grep of "
     "the script does not count",
     'r"(?:python3?\\s+|\\./)\\S*check-pr-fully-clean\\.py"',
     'r"\\S*check-pr-fully-clean\\.py"',
     INCIDENT, [mention_checker()], True, False),
]


def run(command, events, hook=None, tool_name="Bash"):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    out = subprocess.run(
        [sys.executable, hook or HOOK],
        input=json.dumps({
            "tool_name": tool_name,
            "tool_input": {"command": command},
            "transcript_path": path,
        }),
        capture_output=True, text=True,
    ).stdout.strip()
    os.remove(path)
    return bool(out)


def mutate():
    """Run every clause-isolation mutant. Returns the failure count."""
    original = open(HOOK).read()
    failures = 0
    print("\nmutation checks (each must flip its own isolating case):")
    for label, old, new, command, events, before_want, after_want in MUTANTS:
        # The Bash-only gate's isolating case is a non-Bash call, which the
        # normal path ignores by design.
        tool = "Read" if command is None else "Bash"
        cmd = INCIDENT if command is None else command

        if original.count(old) != 1:
            print(f"WRONG  {label}: mutation target appears "
                  f"{original.count(old)} times, expected exactly 1")
            failures += 1
            continue
        mutated = original.replace(old, new)
        # An inapplicable mutation looks exactly like one the tests caught, so
        # it is its own outcome rather than a silent pass.
        if mutated == original:
            print(f"WRONG  {label}: INAPPLICABLE -- the mutated source is "
                  "byte-identical to the original")
            failures += 1
            continue

        fd, mpath = tempfile.mkstemp(suffix=".py")
        with os.fdopen(fd, "w") as fh:
            fh.write(mutated)
        try:
            before = run(cmd, events, tool_name=tool)
            after = run(cmd, events, hook=mpath, tool_name=tool)
        finally:
            os.remove(mpath)

        ok = (before == before_want and after == after_want)
        failures += 0 if ok else 1
        verb = {True: "block", False: "allow"}
        print(f"{'ok  ' if ok else 'WRONG'}  {label}: "
              f"{verb[before]} -> {verb[after]}")
    return failures


def main():
    failures = 0
    for command, events, want_block, label in CASES:
        got = run(command, events)
        ok = got == want_block
        if not ok:
            failures += 1
        print(f"{'ok  ' if ok else 'FAIL'}  "
              f"{'block' if want_block else 'allow'}: {label}")
    # A non-Bash tool call must be ignored outright.
    ok = not run(INCIDENT, [], tool_name="Read")
    failures += 0 if ok else 1
    print(f"{'ok  ' if ok else 'FAIL'}  allow: a non-Bash tool call is ignored")

    failures += mutate()

    total = len(CASES) + 1 + len(MUTANTS)
    print(f"\n{total - failures}/{total} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
