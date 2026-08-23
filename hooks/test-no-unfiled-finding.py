"""Test the no-unfiled-finding guard.

The value is concentrated in the negative cases. A guard that fires on a
legitimate flag, or on a message correctly reporting an already-filed issue,
gets switched off -- and then the case it exists for goes unprotected too.

Run: python3 hooks/test-no-unfiled-finding.py hooks/no-unfiled-finding.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

FILE_CLI = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "gh issue create --title x --body y"}}]}}
# The harness tool names its verb only in `name`; the input has title/body.
FILE_TOOL = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "create_issue",
     "input": {"title": "x", "body": "y"}}]}}
# report-mistakes-proactively step 2: a dupe-check can route the finding to a
# comment on an existing issue instead of a new one. That must discharge too.
COMMENT = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "gh issue comment 897 --body 'new evidence'"}}]}}
UNRELATED = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {"command": "git status --short"}}]}}


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


# (events, should_block, label)
CASES = [
    # The exact failure this exists for -- declarative, no question mark, so
    # no-offer-to-file.py does not fire on it.
    ([say("FLAG -- a mechanism bug worth its own issue. Moving on.")], True,
     "declarative 'worth its own issue' with no filing blocks"),
    ([say("That regex gap needs a tracking issue.")], True,
     "'needs a tracking issue' blocks"),
    ([say("This should be filed separately.")], True,
     "'should be filed' blocks"),
    ([say("Worth tracking separately from the current work.")], True,
     "'worth tracking separately' blocks"),

    # Discharged, by either route.
    ([say("Worth its own issue."), FILE_CLI, say("Filed it.")], False,
     "filing after the assertion does not block"),
    ([say("Worth an issue."), FILE_TOOL, say("Done.")], False,
     "the harness create_issue tool discharges it"),
    ([say("Worth an issue."), COMMENT, say("Added to the existing one.")],
     False, "commenting onto an existing issue discharges it"),

    # Already-filed reporting is the CORRECT behaviour and must pass.
    ([say("Filed as #1043 -- worth its own issue, now tracked.")], False,
     "citing a filed issue number does not block"),
    ([say("Worth an issue; tracked in #897 already.")], False,
     "citing an existing tracking issue does not block"),

    # Flags that are not issue-shaped must not trip it.
    ([say("FLAG -- #1038 must merge before #1036; they conflict.")], False,
     "a merge-order flag does not block"),
    ([say("FLAG -- claude-review is red for the known context reason.")],
     False, "a status heads-up does not block"),
    ([UNRELATED, say("All five PRs are clean.")], False,
     "an ordinary recap does not block"),

    # Ordering: a filing BEFORE the assertion does not discharge a later one.
    ([FILE_CLI, say("Also, that other gap is worth its own issue.")], True,
     "a filing preceding the assertion does not count"),
]


def run(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    try:
        # Fresh sentinel dir per case, so the once-per-message guard does not
        # make later cases silently pass.
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

    # The complement it was built to cover: no-offer-to-file.py must NOT fire
    # on the declarative form, which is exactly why this hook is needed. If
    # that ever changes, one of the two is redundant and should be merged.
    sibling = os.path.join(os.path.dirname(HOOK), "no-offer-to-file.py")
    if os.path.exists(sibling):
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w") as fh:
            fh.write(json.dumps(
                say("FLAG -- a mechanism bug worth its own issue.")) + "\n")
        out = subprocess.run(
            [sys.executable, sibling],
            input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True,
        ).stdout
        os.unlink(path)
        if "block" not in out:
            print("PASS: no-offer-to-file does not cover the declarative form")
            passes += 1
        else:
            print("FAIL: no-offer-to-file now covers this; merge the two hooks")
            failures += 1

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
