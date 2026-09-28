"""Test the flag-idea-without-issue guard.

The value is concentrated in the negative cases: an OFFER discharged by a
filed issue, a FLAG that carries no idea-proposal vocabulary, and a marker
name quoted in a code span must never warn -- a guard that fires on those
gets switched off and takes the incident case with it.

Run: python3 hooks/test-flag-idea-without-issue.py hooks/flag-idea-without-issue.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

ISSUE_CLI = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "gh issue create --title x --body y"}}]}}
PR_CLI = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "gh pr create --title x --body y"}}]}}
UNRELATED = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {"command": "git status --short"}}]}}


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


# (events, should_warn, label)
CASES = [
    # THE MEASURED INCIDENT'S OWN SHAPE: a FLAG proposing two ideas, filed
    # for neither.
    ([say(
        "⚠️ **FLAG** --- qwt lacks the ai-config plugin "
        "declaration, so repos created from it lack it too. We could sweep "
        "existing repos for the missing declaration, and it would help to "
        "add a mechanism to propagate template changes into repos already "
        "created from a template."
    )], True, "a FLAG proposing two ideas with idea-cue vocabulary warns"),

    # A bare OFFER always counts as proposing work, no idea-cue needed.
    ([say(
        "\U0001F4A1 **OFFER** --- I can wire up a nightly job that reruns "
        "this check across every repo in the org."
    )], True, "an OFFER proposing optional work warns with no filing"),

    # A FLAG with no idea-proposal vocabulary is a plain heads-up or risk
    # note, not an idea, and must not warn.
    ([say(
        "⚠️ **FLAG** --- the deploy took eleven minutes this run, "
        "about twice the usual time."
    )], False, "a FLAG that names a risk with no proposal does not warn"),

    # DISCHARGED: an issue was filed somewhere in the turn.
    ([say(
        "⚠️ **FLAG** --- we could sweep the other repos for the "
        "same gap."
    ), ISSUE_CLI], False,
     "an issue-create call anywhere in the turn discharges the FLAG"),
    ([say(
        "\U0001F4A1 **OFFER** --- I can build a mechanism to propagate "
        "template changes automatically."
    ), PR_CLI], False,
     "a PR-create call anywhere in the turn discharges the OFFER"),

    # ALREADY-FILED CITATION IN THE SAME MESSAGE DISCHARGES.
    ([say(
        "⚠️ **FLAG** --- we could sweep for the same gap; filed "
        "as #4035."
    )], False, "citing a filed issue number (#N) in the message discharges"),
    ([say(
        "\U0001F4A1 **OFFER** --- I can add the propagation mechanism, "
        "tracked in "
        "https://github.com/Morrison-Lab/ai-config/issues/4036."
    )], False, "citing a filed issue URL in the message discharges"),

    # ORDINARY PROSE AND OTHER TAGS THAT MUST NEVER FIRE.
    ([say("✅ **ANSWER** --- yes, the migration finished cleanly.")],
     False, "an ANSWER box is not a FLAG or OFFER and never warns"),
    ([say(
        "\U0001F4CA **UPDATE** --- three of five checks have completed so "
        "far."
    )], False, "an UPDATE line is not a FLAG or OFFER and never warns"),
    ([UNRELATED, say("All five PRs are clean.")], False,
     "an ordinary recap does not warn"),

    # QUOTATION IS NOT PROPOSAL -- the self-implicating-example mitigation.
    ([say(
        "This corpus tags an optional idea with `\U0001F4A1 **OFFER**` and "
        "a heads-up with `⚠️ **FLAG**`."
    )], False, "marker names quoted in code spans are not live markers"),
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

    # This hook must never emit "decision": "block" -- it is warn-only.
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps(say(
            "\U0001F4A1 **OFFER** --- I can build that mechanism."
        )) + "\n")
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
        fh.write(json.dumps(say(
            "\U0001F4A1 **OFFER** --- I can build that mechanism."
        )) + "\n")
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
