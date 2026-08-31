"""Test the no-stale-pr-status guard.

The guard's whole value is the third case below: a message that honestly
reports work in flight ("checks are running") must NOT be blocked. A guard
that fires on honest status reporting gets disabled, and then the case it
exists for goes unprotected too.

Run: python3 hooks/test-no-stale-pr-status.py hooks/no-stale-pr-status.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

PUSH = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {"command": "git push -q"}}]}}
QUERY = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {"command": "gh pr checks 493 -R o/r"}}]}}
MCP_QUERY = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {"method": "get_check_runs", "pullNumber": 493}}]}}
# An MCP write carries its verb in the tool NAME, not in the input -- verified
# against real transcripts, where the input holds only owner/repo/branch/files.
# So a scan reading the input alone never sees this as a push.
MCP_PUSH = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "mcp__github__push_files",
     "input": {"owner": "o", "repo": "r", "branch": "main",
               "files": [{"path": "f.py", "content": "x"}]}}]}}


SENTINEL_PREFIX = ".claude-stale-status-"


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


CHECK_CLEAN_QUERY = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "t1", "name": "run_command", "input": {"command": "python3 scripts/check-pr-fully-clean.py 1167"}}]}}
CHECK_CLEAN_FAIL_RESULT = {"type": "user", "message": {"content": [
    {"type": "tool_result", "tool_use_id": "t1", "content": "\u274c PR is NOT fully clean:\n  - Check run 'validate' is still in status 'in_progress'"}]}}

READ_FILE_QUERY = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "t2", "name": "view_file", "input": {"AbsolutePath": "/path/to/scripts/check-pr-fully-clean.py"}}]}}
READ_FILE_RESULT = {"type": "user", "message": {"content": [
    {"type": "tool_result", "tool_use_id": "t2", "content": "print('\u274c PR is NOT fully clean:')"}]}}

# (events, should_block, label)
CASES = [
    ([QUERY, PUSH, say("493 is green, conflict-free.")], True,
     "the real incident: queried, pushed, then claimed green"),
    ([QUERY, PUSH, say("11 pass, 0 fail -- ready to merge.")], True,
     "counts quoted from a pre-push reading"),
    ([QUERY, PUSH, say("All checks green at this head.")], True,
     "'all green' after a push"),
    ([QUERY, MCP_PUSH, say("All checks green, ready to merge.")], True,
     "an MCP push_files is a push -- the reading predates it"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT, say("PR #1167 is fully clean.")], True,
     "claiming fully clean when check-pr-fully-clean.py returned NOT fully clean"),

    ([READ_FILE_QUERY, READ_FILE_RESULT, say("Checked the file contents.")], False,
     "reading script source containing failure text must not trip query block"),

    ([PUSH, QUERY, say("493 is green: 11 pass.")], False,
     "queried AFTER the push -- the claim is current"),
    ([MCP_PUSH, QUERY, say("493 is green: 11 pass.")], False,
     "queried after the MCP push -- the same claim is current"),
    ([PUSH, MCP_QUERY, say("All green, 0 fail.")], False,
     "MCP get_check_runs counts as a query too"),
    ([QUERY, PUSH, say("Pushed the fix; checks are running now.")], False,
     "honest in-flight reporting must not be blocked"),
    ([QUERY, PUSH, say("Waiting on test-coverage and docs; will report when settled.")], False,
     "naming pending checks is not an assertion of green"),
    ([QUERY, say("All checks green.")], False,
     "nothing pushed, so no reading can have gone stale"),
    ([PUSH, QUERY, say("Merged and tidied up.")], False,
     "no status assertion at all"),

    ([QUERY, PUSH, say("PR #1689 is not fully clean -- the review check is still running.")], False,
     "negated assertion in the same clause must not block"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("check-pr-fully-clean.py currently reports NOT clean (correctly "
          "-- it only counts bot-authored verdicts toward its own 'fully "
          "clean' determination by design).")], False,
     "negation in an earlier clause of the same sentence, ASSERT phrase used referentially"),
    ([QUERY, PUSH, say("Not ready to merge yet; still waiting on CI.")], False,
     "negated 'ready to merge' must not block"),
    ([QUERY, PUSH, say("493 isn't fully clean yet.")], False,
     "contraction negation must not block -- the ASSERT phrase has to actually "
     "appear in the sentence (isn't green never matches RX_ASSERT at all, so "
     "that phrasing alone doesn't exercise the n't path)"),
    ([QUERY, PUSH, say("This is green. Not fully clean, though -- one check is still pending.")], True,
     "an unnegated assertion earlier in the message still blocks even when a later sentence is negated"),
    ([QUERY, PUSH, say("Pushed. No findings remain, so the PR is ready to merge.")], True,
     "bare 'no' attached to a different noun must not suppress the guard -- "
     "this is a genuine stale-clean claim"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("There are no unresolved threads and #1689 is fully clean.")], True,
     "bare 'no' earlier in the sentence must not suppress an unrelated ASSERT phrase"),

    ([QUERY, PUSH, say("| #1690 | not clean |\n| #1689 | ready to merge |")], True,
     "a bare newline must count as a sentence boundary -- a negation on one "
     "table row must not suppress an unrelated claim on the next row"),
    ([QUERY, PUSH, say("- #1690 not clean\n- #1689 ready to merge")], True,
     "same as above for a bulleted list"),
    ([QUERY, PUSH, say("**Not clean yet.** All checks green now.")], True,
     "markdown bold-close punctuation right after the terminator must not "
     "swallow the sentence boundary"),
    ([QUERY, PUSH, say('Quoting the review: "not clean." All checks green now.')], True,
     "a closing quote right after the terminator must not swallow the "
     "sentence boundary either"),

    ([QUERY, PUSH, say("PR #1 is not clean; PR #2 is fully clean.")], True,
     "a semicolon-joined clause is its own sentence boundary too -- a "
     "negation before the ';' must not suppress an unrelated genuine "
     "stale-clean claim after it (ai-config#1770)"),
]


def run(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    # The guard fires once per distinct message; clear sentinels so repeated
    # runs of this suite stay deterministic.
    for f in os.listdir(tempfile.gettempdir()):
        if f.startswith(SENTINEL_PREFIX):
            try:
                os.remove(os.path.join(tempfile.gettempdir(), f))
            except OSError:
                pass
    out = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"transcript_path": path}),
        capture_output=True, text=True,
    ).stdout.strip()
    os.remove(path)
    return bool(out)




# ai-config#1859: the WORDING must match what was actually detected.
# A bare "<n> pass" with no PR reference near it may well be a local test-suite
# count, and asserting it is "a PR's check state" was wrong three times
# ("10 pass", "30 pass", "33 pass"). The staleness verdict is unchanged --
# only the sentence describing the match. Asserted here rather than in CASES
# because CASES compares fire/no-fire and would pass either way, which is how
# a detector that is right about the important part and wrong about the
# visible part survives a green suite.
ATTRIBUTION = [
    ("Local suite: 33 pass.",
     "states a pass/fail count",
     "a bare count with no PR reference reads as possibly-local"),
    ("Tests: 33 pass. Pushed to #1919 and checks are running.",
     "asserts a PR's check state",
     "the same count near a PR reference is a check-state claim"),
    ("All checks green.",
     "asserts a PR's check state",
     "an explicit check-state phrase keeps the strong wording"),

    # Review round 1 on #1922. Both were reproduced against the hook by the
    # reviewer, and both are the SAME defect this PR removes, pointing the
    # other way: a message that is not soft at all, softened.
    ("11 pass, 0 fail -- ready to merge.",
     "asserts a PR's check state",
     "a later non-count phrase settles it, not just the first match"),
    ("PR checks: 11 pass, 0 fail.",
     "asserts a PR's check state",
     "the plain word PR counts as a nearby reference"),
    ("The pull request has 11 pass.",
     "asserts a PR's check state",
     "so does the spelled-out form"),
    ("MR checks: 11 pass, 0 fail.",
     "asserts a PR's check state",
     "the MR abbreviation counts as a nearby reference (#2667)"),
    ("The merge request !47 has 11 pass.",
     "asserts a PR's check state",
     "the spelled-out merge request and !N counts as a nearby reference (#2667)"),
]

# The REST check-runs endpoint must count as a status query. `fully-clean.md`
# mandates it over `gh pr checks`, so a guard blind to it warns precisely when
# the stronger command was used -- and tells the author to re-run the weaker
# one. Found by the guard firing on this PR's own session.
QUERY_FORMS = [
    ("gh pr checks 1922 -R Morrison-Lab/ai-config", "the gh porcelain"),
    ("gh api --paginate repos/o/r/commits/abc1234/check-runs --jq '.x'",
     "the paginated REST check-runs endpoint"),
    ("gh api repos/o/r/commits/abc1234/status", "the legacy commit-status endpoint"),
    ("gh pr view 1922 --json statusCheckRollup", "the rollup field"),
    ("glab ci status -R group/project", "GitLab glab ci status (#2667)"),
    ("glab ci list -R group/project", "GitLab glab ci list (#2667)"),
    ("glab ci view -R group/project", "GitLab glab ci view (#2667)"),
    ("glab mr view 47 -R group/project", "GitLab glab mr view (#2667)"),
    ("glab pipeline view 1234 -R group/project", "GitLab glab pipeline view (#2667)"),
    ("glab api projects/123/pipelines/456/jobs", "GitLab REST pipelines endpoint (#2667)"),
    ("glab api projects/group%2Fproject/merge_requests/47", "GitLab REST merge_requests endpoint (#2667)"),
]


def check_query_forms():
    """Every spelling of a status query must discharge the staleness warning."""
    failures = 0
    for cmd, label in QUERY_FORMS:
        events = [PUSH,
                  {"type": "assistant", "message": {"content": [
                      {"type": "tool_use", "input": {"command": cmd}}]}},
                  say("All checks green at head abc1234.")]
        fired = run(events)
        ok = not fired
        failures += 0 if ok else 1
        print(f"{'ok  ' if ok else 'FAIL'}  query-form: {label}")
    return failures


def check_attribution():
    """Each warning must describe what it matched, not what it assumed."""
    failures = 0
    for message, expected, label in ATTRIBUTION:
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w") as fh:
            for e in (QUERY, PUSH, say(message)):
                fh.write(json.dumps(e) + "\n")
        for f in os.listdir(tempfile.gettempdir()):
            if f.startswith(SENTINEL_PREFIX):
                try:
                    os.remove(os.path.join(tempfile.gettempdir(), f))
                except OSError:
                    pass
        out = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True,
        ).stdout.strip()
        os.remove(path)
        reason = (json.loads(out).get("reason") if out else "") or ""
        ok = expected in reason
        failures += 0 if ok else 1
        print(f"{'ok  ' if ok else 'FAIL'}  attribution: {label}")
    return failures


def main():
    failures = 0
    for events, want_block, label in CASES:
        got = run(events)
        ok = got == want_block
        if not ok:
            failures += 1
        print(f"{'ok  ' if ok else 'FAIL'}  "
              f"{'block' if want_block else 'allow'}: {label}")
    failures += check_attribution()
    failures += check_query_forms()
    total = len(CASES) + len(ATTRIBUTION) + len(QUERY_FORMS)
    print(f"\n{total - failures}/{total} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
