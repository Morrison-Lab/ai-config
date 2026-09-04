"""Test the no-mistake-without-a-hook reminder.

Two properties matter most, and both are negative cases. It must stay silent
when a hook was actually written, and when the mistake was explicitly judged
not mechanizable -- because a reminder that fires after you have done the work
is noise, and noise gets the hook switched off.

It must also never block: an error admission is right to send.

Run: python3 hooks/test-no-mistake-without-a-hook.py \\
         hooks/no-mistake-without-a-hook.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

WROTE_HOOK = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "create",
     "input": {"path": "hooks/no-unreviewed-pr.py", "file_text": "..."}}]}}
REGISTERED = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {"command": "python3 - <<'PY'\nhooks.json\nPY"}}]}}
MEMORY_WRITE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "edit",
     "input": {"path": "memories/github.md", "old_str": "a", "new_str": "b"}}]}}
UNRELATED = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {"command": "git status"}}]}}


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


# (events, should_remind, label)
CASES = [
    ([say("I was wrong about that."), UNRELATED], True,
     "an admission with no hook work reminds"),
    ([say("My mistake -- the count was 50, not 69."), UNRELATED], True,
     "'my mistake' reminds"),
    ([say("Correcting myself: that regex never matched.")], True,
     "'correcting myself' reminds"),

    # Discharged by doing the work.
    ([say("I was wrong."), WROTE_HOOK, say("Wrote the guard.")], False,
     "writing a hook file discharges it"),
    ([say("I was wrong."), REGISTERED, say("Registered it.")], False,
     "touching hooks.json discharges it"),

    # Discharged by an explicit judgment that it is not mechanizable.
    ([say("I was wrong. That is not mechanizable -- there is no decidable "
          "condition in the transcript for a domain error like this.")],
     False, "an explicit not-mechanizable judgment discharges it"),

    # A UMS/memory write is the SIBLING hook's discharge, not this one's.
    # Recording the learning does not prevent the recurrence.
    ([say("I was wrong."), MEMORY_WRITE, say("Recorded it.")], True,
     "a memory write alone does NOT discharge this"),

    # No admission at all: silence.
    ([UNRELATED, say("All five PRs are clean.")], False,
     "an ordinary recap does not remind"),

    # Discussing the rule must not trip it. Quoting is the main
    # false-positive source, which is why visible_prose strips code and
    # blockquotes before matching.
    ([say("The regex matches `i was wrong` in prose.")], False,
     "an inline-code mention does not remind"),
    ([say("> I was wrong about that.\n\nThat is the quoted shape.")], False,
     "a blockquote does not remind"),

    # Ordering: hook work BEFORE the admission does not discharge it.
    ([WROTE_HOOK, say("Separately, I was wrong about the count.")], True,
     "hook work preceding the admission does not count"),
]


def run(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    try:
        r = subprocess.run(
            [sys.executable, HOOK], input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True,
        )
        # Must NEVER block: an error admission is right to send.
        assert '"decision"' not in r.stdout, "this hook must not block"
        assert r.returncode == 0, "must exit 0"
        return "no-mistake-without-a-hook" in r.stdout
    finally:
        os.unlink(path)


def once_per_phrase():
    """Fires once per distinct phrase per session, per registration."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps(say("I was wrong about the base branch.")) + "\n")
    payload = json.dumps({"transcript_path": path})

    def invoke(stop=False):
        env = dict(os.environ)
        env.pop("AI_CONFIG_STOP", None)
        if stop:
            env["AI_CONFIG_STOP"] = "1"
        r = subprocess.run(
            [sys.executable, HOOK], input=payload, capture_output=True,
            text=True, env=env,
        )
        return "no-mistake-without-a-hook" in r.stdout

    try:
        checks = [
            (invoke(), True, "an admission reminds on the first prompt"),
            (invoke(), False, "the same phrase does not remind twice"),
            (invoke(stop=True), True,
             "the Stop registration still fires after the prompt-time one"),
            (invoke(stop=True), False,
             "the Stop registration also fires once per phrase"),
        ]
        with open(path, "a") as fh:
            fh.write(json.dumps(say("I miscounted the open PRs.")) + "\n")
        checks.append(
            (invoke(), True,
             "a different admission in the same session still fires"))
        return checks
    finally:
        os.unlink(path)


def window_bound():
    """The once-per-phrase cap is bounded by transcript distance, not by
    session lifetime (ai-config#2997 review finding). An existence-only
    sentinel suppressed a genuinely later, unrelated admission that happened
    to share a short common phrase with an earlier one, for the rest of the
    session. Reuses the sibling's LOOP_WINDOW/`_sentinel_gate` mechanism.
    """
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps(say("I was wrong about the base branch.")) + "\n")
    payload = json.dumps({"transcript_path": path})

    def invoke():
        env = dict(os.environ)
        env.pop("AI_CONFIG_STOP", None)
        r = subprocess.run(
            [sys.executable, HOOK], input=payload, capture_output=True,
            text=True, env=env,
        )
        return "no-mistake-without-a-hook" in r.stdout

    try:
        checks = [(invoke(), True, "an admission reminds on the first prompt")]

        # The loop case: a few turns later, re-explaining the same mistake
        # names the same phrase again. That is a repeat, not a new
        # admission, and must not re-fire.
        with open(path, "a") as fh:
            fh.write(json.dumps({"type": "user", "message": {"content": [
                {"type": "text", "text": "was that right?"}]}}) + "\n")
            fh.write(json.dumps(
                say("Confirmed -- I was wrong about the base branch.")) + "\n")
        checks.append(
            (invoke(), False,
             "the same phrase repeated within the window does not re-fire"))

        # The suppressed repeat above never advances the sentinel (still
        # recorded at record index 0), so enough filler records push the
        # NEXT occurrence of the same phrase past LOOP_WINDOW records from
        # that index, and it must read as a new, unrelated admission.
        with open(path, "a") as fh:
            for i in range(8):
                fh.write(json.dumps({"type": "user", "message": {"content": [
                    {"type": "text", "text": f"filler turn {i}"}]}}) + "\n")
            fh.write(json.dumps(
                say("I was wrong about a different thing entirely.")) + "\n")
        checks.append(
            (invoke(), True,
             "the same phrase far beyond the window fires again"))
        return checks
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
            print(f"FAIL: {label} (expected remind={expected}, got {got})")
            failures += 1

    for got, expected, label in once_per_phrase():
        if got == expected:
            print(f"PASS: {label}")
            passes += 1
        else:
            print(f"FAIL: {label} (expected remind={expected}, got {got})")
            failures += 1

    for got, expected, label in window_bound():
        if got == expected:
            print(f"PASS: {label}")
            passes += 1
        else:
            print(f"FAIL: {label} (expected remind={expected}, got {got})")
            failures += 1

    # Degrades to silence rather than crashing if the sibling it imports its
    # detection from is missing.
    out = subprocess.run(
        [sys.executable, HOOK], input='{"transcript_path": "/nonexistent"}',
        capture_output=True, text=True,
    )
    if out.returncode == 0 and "no-mistake" not in out.stdout:
        print("PASS: fails open on an unreadable transcript")
        passes += 1
    else:
        print("FAIL: should fail open on an unreadable transcript")
        failures += 1

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
