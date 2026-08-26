"""Test the no-incomplete-check-enumeration guard.

The guard's whole value is the allow cases: a progress report ("13 pass, 5
pending") must NOT be blocked, and neither must a clean claim already backed
by a complete enumeration. A guard that fires on honest reporting gets
disabled, and then the case it exists for goes unprotected too.

Run: python3 hooks/test-no-incomplete-check-enumeration.py \
         hooks/no-incomplete-check-enumeration.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

PARTIAL = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {"command": "gh pr checks 651 -R ucdavis/bcs"}}]}}
# GraphQL rollup is also a short surface, not the complete instrument
# (ai-config#2277, 2026-08-26).
PARTIAL_ROLLUP = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "gh pr view 2277 --json statusCheckRollup"}}]}}
CHECKER = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "python3 scripts/check-pr-fully-clean.py 651 -R ucdavis/bcs"}}]}}
CHECKER_2277 = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "python3 scripts/check-pr-fully-clean.py 2277 "
                   "-R Morrison-Lab/ai-config"}}]}}
ENDPOINT = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "gh api repos/ucdavis/bcs/commits/a5f4f3f2/check-runs?per_page=100 --paginate"}}]}}
MCP_ENDPOINT = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {"method": "get_check_runs", "pullNumber": 651}}]}}
PUSH = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {"command": "git push -q origin HEAD"}}]}}
# The test file names the checker but must not count as having run it.
TEST_FILE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "python3 scripts/test_check-pr-fully-clean.py"}}]}}


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


# (events, should_block, label)
CASES = [
    ([PARTIAL, say("#651 is fully clean at a5f4f3f2.")], True,
     "the real incident: declared fully clean off gh pr checks alone"),
    ([PARTIAL_ROLLUP, say("#2277 is ready for merge.")], True,
     "statusCheckRollup alone cannot back a terminal clean claim"),
    ([PARTIAL_ROLLUP, CHECKER_2277, say("#2277 is fully clean.")], False,
     "rollup then checker -- claim rests on the complete read"),
    ([PARTIAL_ROLLUP, say("8 success, 0 pending on the rollup.")], False,
     "rollup progress report is not a terminal claim"),
    ([PARTIAL, say("21 pass, 0 pending -- ready to merge.")], True,
     "'ready to merge' backed only by the partial list"),
    ([PARTIAL, say("All checks green, so this is ready for merge.")], True,
     "'all checks green' off the partial list"),
    ([CHECKER, PUSH, PARTIAL, say("#651 is fully clean.")], True,
     "the complete read predates the push, so it no longer covers the head"),
    ([PARTIAL, TEST_FILE, say("#651 is fully clean.")], True,
     "running the checker's TEST file is not running the checker"),

    ([CHECKER, PARTIAL, say("#651 is fully clean.")], False,
     "checker ran after nothing was pushed -- claim is covered"),
    ([PARTIAL, CHECKER, say("#651 is fully clean.")], False,
     "checker ran last, so the claim rests on the complete read"),
    ([PARTIAL, ENDPOINT, say("#655 is fully clean and ready to merge.")], True,
     "paginated check-runs is check-half only, not a fully-clean read"),
    ([PARTIAL, MCP_ENDPOINT, say("#651 is fully clean.")], True,
     "get_check_runs is check-half only, not a fully-clean read"),
    ([ENDPOINT, say("#655 is fully clean and ready to merge.")], True,
     "check-runs alone cannot back a terminal clean claim"),
    ([MCP_ENDPOINT, say("#651 is fully clean.")], True,
     "get_check_runs alone cannot back a terminal clean claim"),
    ([PARTIAL_ROLLUP, ENDPOINT, say("#2277 is ready for merge.")], True,
     "rollup plus check-runs still lacks check-pr-fully-clean.py"),
    ([PARTIAL, say("13 pass, 5 pending -- update-snapshots still running.")], False,
     "a progress report is honest and must not be blocked"),
    ([PARTIAL, say("Waiting on the three OS legs; I'll report when they land.")], False,
     "naming what is outstanding is not a terminal claim"),
    ([say("#651 is fully clean.")], False,
     "no partial reading in play, so there is nothing to warn about"),
    ([PARTIAL, say("Merged and tidied up.")], False,
     "no clean declaration at all"),
]


def run(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    # The guard fires once per distinct message; clear sentinels so repeated
    # runs of this suite stay deterministic.
    for f in os.listdir(tempfile.gettempdir()):
        if f.startswith("no-incomplete-check-enum-"):
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
