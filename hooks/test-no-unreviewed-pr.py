"""Test the no-unreviewed-pr guard.

The guard's value is concentrated in the negative cases: a draft PR
legitimately defers review (a draft does not trigger the review bot), and a
session that already requested a reviewer must not be nagged. A guard that
fires on correct behaviour gets disabled, and then the case it exists for
goes unprotected too.

Run: python3 hooks/test-no-unreviewed-pr.py hooks/no-unreviewed-pr.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

CREATE_CLI = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "gh pr create --base main --title 'x' --body 'y'"}}]}}
# The harness tool names its verb only in `name`; the input carries title/body.
# A scan reading the input alone would never see this as opening a PR.
CREATE_TOOL = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "create_pull_request",
     "input": {"title": "x", "body": "y"}}]}}
CREATE_DRAFT = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "gh pr create --draft --base main --title 'x'"}}]}}
DRAFT_TOOL = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "create_pull_request",
     "input": {"title": "x", "draft": True}}]}}
READY = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {"command": "gh pr ready 1038"}}]}}
REQUEST = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": ("gh api repos/o/r/pulls/1038/requested_reviewers -X POST "
                    "-f 'reviewers[]=copilot-pull-request-reviewer[bot]'")}}]}}
ADD_REVIEWER = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "gh pr edit 1038 --add-reviewer d-morrison"}}]}}
UNRELATED = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {"command": "git status --short"}}]}}


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


# (events, should_block, label)
CASES = [
    # The failure this exists for: PR opened, recap written, no request.
    ([CREATE_CLI, say("Opened #1038. Review owed.")], True,
     "gh pr create with no reviewer request blocks"),
    ([CREATE_TOOL, say("Opened the PR.")], True,
     "harness create_pull_request with no request blocks"),
    ([READY, say("Marked it ready.")], True,
     "gh pr ready with no request blocks"),

    # Discharged: a request after the open.
    ([CREATE_CLI, REQUEST, say("Opened #1038 and requested review.")], False,
     "a reviewer request after create does not block"),
    ([CREATE_CLI, ADD_REVIEWER, say("Opened and assigned a human.")], False,
     "--add-reviewer also discharges it"),

    # A draft legitimately defers review, per pr-on-claim.
    ([CREATE_DRAFT, say("Opened as a draft; implementing now.")], False,
     "a draft PR does not block"),
    ([DRAFT_TOOL, say("Opened as a draft.")], False,
     "the harness draft flag does not block"),

    # Order matters: drafting first, then readying, re-arms the guard.
    ([CREATE_DRAFT, READY, say("Marked it ready.")], True,
     "readying a draft later re-arms the guard"),
    # ... and requesting after that readying discharges it again.
    ([CREATE_DRAFT, READY, REQUEST, say("Ready, review requested.")], False,
     "requesting after readying discharges it"),

    # Nothing opened: the guard must stay silent in an ordinary session.
    ([UNRELATED, say("All clean.")], False,
     "a session that opened no PR does not block"),
    ([REQUEST, say("Re-requested review on #1029.")], False,
     "a bare re-request with no open does not block"),

    # Stale request: requested BEFORE opening a second PR.
    ([REQUEST, CREATE_CLI, say("Opened another PR.")], True,
     "a request preceding the open does not count"),

    # Draft-gating: a ready PR converted BACK to draft to hold it behind a
    # prerequisite (CLAUDE.md, "Surface merge-order constraints"). Review is
    # legitimately deferred again, so the guard must go quiet. This is the
    # only case that reaches the `last_draft > last_open` branch -- the
    # create-a-draft cases exit earlier, at `last_open < 0`, so they pass
    # with that branch deleted and do not test it.
    ([CREATE_CLI, DRAFT_TOOL, say("Held as a draft behind #1029.")], False,
     "converting a ready PR back to draft defers review again"),
]


def run(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    try:
        # A fresh sentinel dir per case, so the once-per-message guard does
        # not make later cases silently pass.
        env = dict(os.environ, TMPDIR=tempfile.mkdtemp())
        out = subprocess.run(
            [sys.executable, HOOK], input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True, env=env,
        ).stdout
        return '"decision": "block"' in out or '"decision":"block"' in out
    finally:
        os.unlink(path)


def main():
    passes = failures = 0
    for events, expected, label in CASES:
        got = run(events)
        if got == expected:
            print(f"PASS: {label}")
            passes += 1
        else:
            print(f"FAIL: {label} (expected block={expected}, got {got})")
            failures += 1

    # Fails open on unreadable input rather than wedging the session.
    out = subprocess.run(
        [sys.executable, HOOK], input='{"transcript_path": "/nonexistent"}',
        capture_output=True, text=True,
    )
    if out.returncode == 0 and "block" not in out.stdout:
        print("PASS: fails open on an unreadable transcript")
        passes += 1
    else:
        print("FAIL: should fail open on an unreadable transcript")
        failures += 1

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
