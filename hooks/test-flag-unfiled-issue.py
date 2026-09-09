"""Test the flag-unfiled-issue guard.

The value is concentrated in the negative cases. A guard that fires on an
already-filed status report, or on the phrase sitting inside a code fence,
gets switched off -- and then the case it exists for goes unprotected too.

Run: python3 hooks/test-flag-unfiled-issue.py hooks/flag-unfiled-issue.py
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
COMMENT = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "gh issue comment 897 --body 'new evidence'"}}]}}
UNRELATED = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {"command": "git status --short"}}]}}


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


# (events, should_warn, label)
CASES = [
    # THE MEASURED INCIDENT'S OWN PHRASING.
    ([say("The stale equation-number comments are still unfiled. "
          "Stopping here for now.")], True,
     "'is still unfiled' status report with no filing warns"),
    ([say("That gap was still unfiled as of yesterday's recap.")], True,
     "past-tense 'was still unfiled' warns"),
    ([say("The regex drift remains unfiled.")], True,
     "'remains unfiled' warns"),

    # THE REST OF THE PHRASE LIST.
    ([say("This has not been filed.")], True, "'has not been filed' warns"),
    ([say("This hasn't been filed yet.")], True, "'hasn't been filed' warns"),
    ([say("The typo fix has not yet been filed.")], True,
     "'has not yet been filed' warns"),
    ([say("This needs an issue.")], True, "'needs an issue' warns"),
    ([say("This should be filed.")], True, "'should be filed' warns"),
    ([say("The finding remains untracked.")], True,
     "'remains untracked' (copula-bound) warns"),
    ([say("It is still untracked.")], True,
     "'is still untracked' (copula-bound) warns"),
    ([say("Status: still needs a tracking issue.")], True,
     "'still needs a tracking issue' warns"),
    ([say("I owe #700 an issue documenting this.")], True,
     "'I owe ... an issue' warns"),
    ([say("I owe the reviewer an issue for the follow-up work.")], True,
     "'I owe ... an issue' with an intervening object still warns"),

    # DISCHARGED: filing after the assertion, with no closing narration.
    ([say("Worth noting: that gap is still unfiled."), FILE_CLI], False,
     "filing right after the assertion, with no trailing prose, discharges"),
    ([say("This needs an issue."), COMMENT], False,
     "commenting onto an existing issue right after the assertion discharges"),
    # DISCHARGED: filing followed by a closing message that itself carries
    # no trigger phrase -- `text` becomes that closing message, which the
    # ASSERT patterns do not match at all.
    ([say("That gap is still unfiled."), FILE_CLI, say("Filed it as #701.")],
     False, "a closing 'filed it' reply after filing does not warn"),
    # NOT discharged: filing BEFORE the assertion does not clear a LATER one.
    ([FILE_CLI, say("Also, that other regression is still unfiled.")], True,
     "a filing preceding the assertion does not count"),

    # ALREADY-FILED REPORTING IS CORRECT BEHAVIOUR AND MUST NOT WARN.
    ([say("Filed as #1043 -- that item was still unfiled until now.")], False,
     "citing a filed issue number (#N) does not warn"),
    ([say("The stale equation-number comments were still unfiled, and I "
          "have now filed them as "
          "https://github.com/UCD-SERG/serocalculator/issues/694.")], False,
     "citing a filed issue URL (no #N) does not warn"),
    ([say("This needs an issue; tracked in #897 already.")], False,
     "citing an existing tracking issue does not warn"),

    # ORDINARY PROSE THAT MUST NEVER FIRE.
    ([say("An untracked local change is real work and still not a "
          "completion.")], False,
     "'untracked' as a bare adjective (no copula) does not warn"),
    ([say("git status --short showed one untracked file in the tree.")],
     False, "git's own 'untracked file' vocabulary does not warn"),
    ([say("The reviewer decides whether to act on it; I filed it as "
          "#1379.")], False,
     "deferring the ACTION while reporting the filing does not warn"),
    ([UNRELATED, say("All five PRs are clean.")], False,
     "an ordinary recap does not warn"),

    # QUOTATION IS NOT ASSERTION -- the self-implicating-example mitigation.
    ([say("The pattern `is still unfiled` already matched on main.")], False,
     "a pattern name in a code span is a quotation, not an assertion"),
    ([say("Its trigger phrases include `needs an issue` and "
          "`should be filed`.")], False,
     "two quoted alternatives, no claim about filing anything"),
    ([say("Example:\n```\nis still unfiled\n```\nthat is the pattern.")],
     False, "the assertion inside a code fence is an illustration"),
    ([say("A reviewer wrote:\n\n> This is still unfiled.\n\nNoted.")], False,
     "the assertion inside a blockquote is someone else's"),
    # The boundary: stripping must not swallow a REAL assertion beside a
    # quote of the pattern.
    ([say("The `needs an issue` phrasing is fine, but this one is still "
          "unfiled.")], True,
     "a genuine assertion still warns when a code span sits beside it"),
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
        return '"systemMessage"' in out
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
            print(f"FAIL: {label} (expected warn={expected}, got {got})")
            failures += 1

    # This hook must never emit "decision": "block" -- it is warn-only by
    # design (see the docstring's "WHY THIS WARNS RATHER THAN BLOCKS").
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps(say("That gap is still unfiled.")) + "\n")
    out = subprocess.run(
        [sys.executable, HOOK], input=json.dumps({"transcript_path": path}),
        capture_output=True, text=True,
    ).stdout
    os.unlink(path)
    if '"decision"' not in out and '"block"' not in out:
        print("PASS: never emits a block decision")
        passes += 1
    else:
        print("FAIL: emitted a block decision -- this hook must warn only")
        failures += 1

    # Fires at most once per distinct message.
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps(say("That gap is still unfiled.")) + "\n")
    env = dict(os.environ, TMPDIR=tempfile.mkdtemp())
    first = subprocess.run(
        [sys.executable, HOOK], input=json.dumps({"transcript_path": path}),
        capture_output=True, text=True, env=env,
    ).stdout
    second = subprocess.run(
        [sys.executable, HOOK], input=json.dumps({"transcript_path": path}),
        capture_output=True, text=True, env=env,
    ).stdout
    os.unlink(path)
    if '"systemMessage"' in first and '"systemMessage"' not in second:
        print("PASS: fires at most once per distinct message")
        passes += 1
    else:
        print("FAIL: sentinel dedup did not suppress the repeat")
        failures += 1

    out = subprocess.run(
        [sys.executable, HOOK], input='{"transcript_path": "/nonexistent"}',
        capture_output=True, text=True,
    )
    if out.returncode == 0 and "systemMessage" not in out.stdout:
        print("PASS: fails open on an unreadable transcript")
        passes += 1
    else:
        print("FAIL: should fail open on an unreadable transcript")
        failures += 1

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
