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
    ([QUERY, PUSH, say("493 isn't green yet.")], False,
     "contraction negation must not block"),
    ([QUERY, PUSH, say("This is green. Not fully clean, though -- one check is still pending.")], True,
     "an unnegated assertion earlier in the message still blocks even when a later sentence is negated"),
]


def run(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    # The guard fires once per distinct message; clear sentinels so repeated
    # runs of this suite stay deterministic.
    for f in os.listdir(tempfile.gettempdir()):
        if f.startswith(".claude-stale-status-"):
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


def main():
    failures = 0
    for events, want_block, label in CASES:
        got = run(events)
        ok = got == want_block
        if not ok:
            failures += 1
        print(f"{'ok  ' if ok else 'FAIL'}  "
              f"{'block' if want_block else 'allow'}: {label}")
    print(f"\n{len(CASES) - failures}/{len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
