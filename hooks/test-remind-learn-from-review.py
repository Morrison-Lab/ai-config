"""Test the remind-learn-from-review guard.

The value is concentrated in the negative cases. This hook fires on accepting a
reviewer's finding, and the phrases that signal acceptance ("good catch",
"you're right") are also said to the USER and in non-review contexts. A guard
that nags on those, or on a Rebut, or when the learning was already recorded,
gets switched off -- and then the case it exists for goes unprotected too.

Run: python3 hooks/test-remind-learn-from-review.py hooks/remind-learn-from-review.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


def tool(name, inp):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": name, "input": inp}]}}


# A review-surface action, establishing PR-review context.
REVIEW = tool("resolve_review_thread", {"threadId": "x"})
# Accepting a finding; the sentence also names the reviewer, so it carries its
# own context as well.
ACCEPT = say("Good catch -- the reviewer is right, the regex misses the "
             "anchored form.")
# Discharges: the learning half, the mechanism half, and the one-off judgment.
MEM_WRITE = tool("Write", {"file_path": "memories/git.md", "content": "..."})
HOOK_WRITE = tool("Write", {"file_path": "hooks/no-x.py", "content": "..."})
UMS_BASH = tool("Bash", {"command": "echo running ums pass"})


# (events, should_remind, label)
CASES = [
    # The exact case this exists for: a reviewer finding accepted, nothing
    # recorded after it.
    ([REVIEW, ACCEPT], True,
     "accepted finding with no follow-up reminds"),
    # The acceptance sentence names the reviewer, so context needs no tool.
    ([ACCEPT], True,
     "acceptance naming the reviewer carries its own context"),

    # Discharged, by any of the three routes.
    ([REVIEW, ACCEPT, MEM_WRITE], False,
     "a memory write after the acceptance discharges it"),
    ([REVIEW, ACCEPT, HOOK_WRITE], False,
     "building a hook after the acceptance discharges it"),
    ([REVIEW, ACCEPT, UMS_BASH], False,
     "a ums pass after the acceptance discharges it"),
    ([REVIEW, say("Good catch from the reviewer -- but this is a one-off "
                  "typo, no rule would catch it.")], False,
     "an explicit one-off judgment discharges it"),

    # A Rebut is the opposite disposition and must never fire.
    ([REVIEW, say("The reviewer is wrong here; the pattern is valid. "
                  "Rebutting with the repro.")], False,
     "a rebuttal does not remind"),

    # Acceptance vocabulary with NO review context must not fire -- this is the
    # 'good catch' said to the user.
    ([say("Good catch, thanks! I'll add that to the plan.")], False,
     "acceptance with no review context does not remind"),

    # Quoting the rule (inline code) is stripped by visible_prose, so it must
    # not fire even though 'reviewer' is present.
    ([REVIEW, say("The `good catch` convention for a reviewer is discussed "
                  "in the fragment.")], False,
     "an inline-code mention of the phrase does not remind"),

    # Ordering: a recording BEFORE the acceptance does not discharge a later
    # one.
    ([MEM_WRITE, REVIEW, ACCEPT], True,
     "a memory write preceding the acceptance does not count"),
]


def run(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    try:
        # Fresh sentinel dir per case, so the once-per-acceptance guard does
        # not make later cases silently pass.
        env = dict(os.environ, TMPDIR=tempfile.mkdtemp())
        out = subprocess.run(
            [sys.executable, HOOK], input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True, env=env,
        )
        # It must NEVER block: no Stop-hook decision, ever, and always exit 0.
        assert out.returncode == 0, f"non-zero exit: {out.returncode}"
        assert '"decision"' not in out.stdout, "must never emit a block decision"
        return "[hook: remind-learn-from-review]" in out.stdout
    finally:
        os.unlink(path)


def main():
    passes = failures = 0
    for events, expected, label in CASES:
        try:
            got = run(events)
        except AssertionError as e:
            print(f"FAIL: {label} ({e})")
            failures += 1
            continue
        if got == expected:
            print(f"PASS: {label}")
            passes += 1
        else:
            print(f"FAIL: {label} (expected remind={expected}, got {got})")
            failures += 1

    # Fail open on an unreadable transcript.
    out = subprocess.run(
        [sys.executable, HOOK], input='{"transcript_path": "/nonexistent"}',
        capture_output=True, text=True,
    )
    if out.returncode == 0 and "[hook:" not in out.stdout:
        print("PASS: fails open on an unreadable transcript")
        passes += 1
    else:
        print("FAIL: should fail open on an unreadable transcript")
        failures += 1

    # The complement it was built to cover: the first-person sibling must NOT
    # fire on an accepted reviewer finding, which is exactly why this hook is
    # needed. If that ever changes, one of the two is redundant.
    sibling = os.path.join(os.path.dirname(HOOK), "remind-ums-after-error.py")
    if os.path.exists(sibling):
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w") as fh:
            fh.write(json.dumps(REVIEW) + "\n")
            fh.write(json.dumps(ACCEPT) + "\n")
        out = subprocess.run(
            [sys.executable, sibling],
            input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True,
            env=dict(os.environ, TMPDIR=tempfile.mkdtemp()),
        )
        os.unlink(path)
        if "UMS reminder" not in out.stdout:
            print("PASS: remind-ums-after-error does not fire on an accepted "
                  "reviewer finding (first-person only)")
            passes += 1
        else:
            print("FAIL: remind-ums-after-error now covers this; merge the two")
            failures += 1

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
