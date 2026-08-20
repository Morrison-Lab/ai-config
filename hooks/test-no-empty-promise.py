"""Test the no-empty-promise Stop guard.

Both directions matter, and the negative one matters more. The guard blocks,
so a false positive stops a correct reply from going out -- and a blocking
guard that misfires is the one people switch off, taking the real cases with
it (README, "A hook that misfires is worse than a missing one").

Three near-misses are load-bearing:
  * an ordinary next-action statement ("I'll open the PR now") is not a
    promise -- the generalizer is what makes one;
  * a capability limit ("I'll never be able to know the exact time") uses the
    same words and commits to nothing;
  * quoting the rule while discussing it, which this corpus does constantly.

Run: python3 hooks/test-no-empty-promise.py hooks/no-empty-promise.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

WROTE_FRAGMENT = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Write",
     "input": {"file_path": "shared/workflow/no-empty-promises.md",
               "content": "..."}}]}}
WROTE_HOOK = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Write",
     "input": {"file_path": "hooks/no-empty-promise.py", "content": "..."}}]}}
WROTE_MEMORY = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Edit",
     "input": {"file_path": "memories/preferences.md",
               "old_string": "a", "new_string": "b"}}]}}
FILED_ISSUE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Bash",
     "input": {"command": "gh issue create -R o/r --title x --body y"}}]}}
UNRELATED = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Bash", "input": {"command": "git status"}}]}}
PROMPT = {"type": "user", "message": {"content": [
    {"type": "text", "text": "next task please"}]}}
TOOL_RESULT = {"type": "user", "message": {"content": [
    {"type": "tool_result", "content": "ok"}]}}


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


# (events, should_block, label)
CASES = [
    # Promises with nothing behind them.
    ([say("Going forward, I'll run the checker before reporting status.")],
     True, "'going forward, I'll' with no mechanism blocks"),
    ([say("From now on I won't skip the UMS pass."), UNRELATED],
     True, "'from now on I won't' with unrelated tool work blocks"),
    ([say("I'll always link PRs in tables.")],
     True, "'I'll always' blocks"),
    ([say("I won't make that mistake again.")],
     True, "'won't ... again' blocks"),
    ([say("Next time I'll check the branch first.")],
     True, "'next time I'll' blocks"),
    ([say("I'll no longer trust a cached verdict.")],
     True, "'I'll no longer' blocks"),
    ([say("I promise to run the sweep first.")],
     True, "a bare performative blocks"),

    # Discharged by shipping something durable.
    ([say("Going forward I'll run the checker."), WROTE_FRAGMENT,
      say("Recorded the rule.")],
     False, "a shared/ fragment write discharges it"),
    ([say("From now on I won't skip it."), WROTE_MEMORY],
     False, "a memories/ write discharges it"),
    ([say("I'll always request the reviewer."), WROTE_HOOK],
     False, "a hooks/ write discharges it"),
    ([say("Going forward I'll do X."), FILED_ISSUE],
     False, "filing the tracking issue discharges it"),
    ([say("Going forward I'll do X --- enforced by "
          "`hooks/no-empty-promise.py`, added in this PR.")],
     False, "prose naming the mechanism in the same message discharges it"),
    ([say("Going forward I'll check `shared/` before writing anything.")],
     True, "a bare directory mention does NOT discharge the promise"),

    # Near-misses that must pass.
    ([say("I'll open the PR now and report back.")],
     False, "an ordinary next-action statement is not a promise"),
    ([say("I will push the fix, then wait for the review.")],
     False, "a plan for this turn is not a promise"),
    ([say("I'll never be able to know the exact time without a clock read.")],
     False, "a capability limit is not a promise"),
    ([say("You said you would always link PRs in tables.")],
     False, "a second-person statement is not my promise"),
    ([say("The reviewer will always re-derive the claim from scratch.")],
     False, "a third-person prediction is not a promise"),
    ([say("I was wrong about the default branch --- it is `master` here.")],
     False, "an admission with no promise attached passes"),
    ([UNRELATED, say("All five PRs are clean.")],
     False, "an ordinary recap does not block"),

    # Discussing the rule must not trip it -- this corpus quotes the trigger
    # phrases constantly, including in this very file.
    ([say("The guard fires on `going forward, I will` in prose.")],
     False, "an inline-code mention does not block"),
    ([say("> Going forward, I will do X.\n\nThat is the shape it catches.")],
     False, "a blockquote does not block"),
    ([say("```\nFrom now on I won't skip it.\n```\nThat is a fenced example.")],
     False, "a fenced example does not block"),

    # Ordering and turn scope.
    ([WROTE_FRAGMENT, say("Separately, going forward I'll do X.")],
     True, "mechanism work preceding the promise does not discharge it"),
    ([say("Going forward I'll do X."), PROMPT, say("Here is the answer.")],
     False, "a promise in an EARLIER turn is not re-blocked"),
    ([say("Going forward I'll do X."), TOOL_RESULT, WROTE_MEMORY],
     False, "a tool_result does not end the turn"),
]


def run(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    try:
        r = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True,
        )
        assert r.returncode == 0, f"must exit 0, got {r.returncode}"
        if not r.stdout.strip():
            return False
        payload = json.loads(r.stdout)
        return payload.get("decision") == "block"
    finally:
        os.unlink(path)


def main():
    passes = failures = 0
    for events, expected, label in CASES:
        try:
            got = run(events)
        except AssertionError as exc:
            print(f"FAIL: {label} ({exc})")
            failures += 1
            continue
        if got == expected:
            print(f"PASS: {label}")
            passes += 1
        else:
            print(f"FAIL: {label} (expected block={expected}, got {got})")
            failures += 1

    # Fails open rather than crashing when the transcript is unreadable.
    out = subprocess.run(
        [sys.executable, HOOK], input='{"transcript_path": "/nonexistent"}',
        capture_output=True, text=True,
    )
    if out.returncode == 0 and not out.stdout.strip():
        print("PASS: fails open on an unreadable transcript")
        passes += 1
    else:
        print("FAIL: should fail open on an unreadable transcript")
        failures += 1

    # Malformed stdin must not crash the Stop event either.
    out = subprocess.run(
        [sys.executable, HOOK], input="not json",
        capture_output=True, text=True,
    )
    if out.returncode == 0 and not out.stdout.strip():
        print("PASS: fails open on malformed stdin")
        passes += 1
    else:
        print("FAIL: should fail open on malformed stdin")
        failures += 1

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
