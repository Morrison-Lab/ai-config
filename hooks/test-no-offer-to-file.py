#!/usr/bin/env python3
"""Test the no-offer-to-file guard.

Verifies that offers to file or record in ordinary prose are blocked, while
trigger phrases quoted inside backtick code spans, fenced code blocks, or
standard non-offer replies pass cleanly.

Run: python3 hooks/test-no-offer-to-file.py hooks/no-offer-to-file.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

TOOL = {
    "type": "assistant",
    "message": {
        "content": [{"type": "tool_use", "input": {"command": "git status"}}]
    },
}


def say(text):
    return {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": text}]},
    }


CASES = [
    # True positives: direct offers in prose
    ([TOOL, say("Want me to file an issue for this?")], True, "want me to file blocks"),
    ([TOOL, say("Should I record this learning?")], True, "should I record blocks"),
    ([TOOL, say("Shall I save this in memory?")], True, "shall I save blocks"),
    ([TOOL, say("Say the word and I will file an issue.")], True, "say the word and I will file blocks"),
    ([TOOL, say("Is this worth filing as an issue?")], True, "worth filing blocks"),
    ([TOOL, say("Let me know if you'd like me to file a bug report.")], True, "let me know if you would like me to file blocks"),
    ([TOOL, say("I could file an issue about this?")], True, "i could file an issue blocks"),
    ([TOOL, say("Want me to file the issue and open that PR?")], True, "bundled offer blocks"),

    # True positives: the DECLARATIVE PREFERENCE shape (ai-config#3520).
    # Verbatim sentence that slipped past every pattern on 2026-09-10.
    (
        [TOOL, say(
            "That's arguably a guard gap (a tag-only push ships no commits), "
            "but I've filed enough guard issues this session that I'd rather "
            "you tell me whether it's worth a ninth than assume it."
        )], "warn", "declarative preference deferring a filing decision warns",
    ),
    (
        [TOOL, say("I'll leave the call to you on whether this needs an issue.")],
        "warn", "leave the call to you plus filing domain warns",
    ),
    (
        [TOOL, say("Your call whether that's worth tracking as an issue.")],
        "warn", "your call whether plus a filing artifact warns",
    ),

    # Negative: the same deferral with NO filing/recording domain in the
    # message is an ordinary judgment handback, not an unfiled finding.
    (
        [TOOL, say("Both rebases are equally safe, so I'd rather you decide which one to take.")],
        "pass", "deferral with no filing vocabulary stays silent",
    ),
    (
        [TOOL, say("Your call whether to squash or rebase merge this branch.")],
        "pass", "your call whether about merge strategy stays silent",
    ),

    # Negative: the DEFER phrase and the DOMAIN word are in DIFFERENT
    # sentences. A whole-message conjunction would block these; the
    # sentence-scoped gate must not (ai-config#3520 review round 1).
    (
        [TOOL, say(
            "Filed as #3519. Separately, both rebases are equally safe, "
            "so I'd rather you decide which one to take."
        )], "pass", "deferral in a different sentence from the filing report stays silent",
    ),
    (
        [TOOL, say(
            "I opened the tracking issue already. Your call whether to squash "
            "or rebase this branch."
        )], "pass", "your call whether about merge, with an issue elsewhere, stays silent",
    ),
    (
        [TOOL, say("I'd rather you decide which of these files to keep.")],
        "pass", "literal use of files as a noun stays silent",
    ),

    # Negative: DEFER plus an AMBIGUOUS word that is not a filing artifact.
    # These are the round-3 reviewer's own probes; the narrowed DOMAIN is what
    # keeps them silent (ai-config#3520).
    (
        [TOOL, say("I'd rather you decide how to record the vote tally in the spreadsheet.")],
        "pass", "record as an ordinary verb stays silent",
    ),
    (
        [TOOL, say("Your call whether the memory allocator needs tuning here.")],
        "pass", "memory as a computing term stays silent",
    ),
    (
        [TOOL, say("I'll leave the decision to you about which tickets to buy for the show.")],
        "pass", "tickets in a non-forge sense stays silent",
    ),
    (
        [TOOL, say("I'll leave that call to you on whether to open a follow-up.")],
        "warn", "leave that call to you (extra noun) still warns",
    ),

    # Negative cases: trigger phrases quoted inside inline code spans
    (
        [TOOL, say("We shouldn't add a hook for `want me to file` because it is too broad.")],
        False,
        "trigger phrase in inline code span does not block",
    ),
    (
        [TOOL, say("The regex matches `should I record` or `worth filing?` examples.")],
        False,
        "multiple trigger phrases in inline code spans do not block",
    ),

    # Negative cases: trigger phrases inside fenced code blocks
    (
        [
            TOOL,
            say(
                "Here is an example:\n```\nwant me to file an issue?\n```\nThat was a quote."
            ),
        ],
        False,
        "trigger phrase in fenced code block does not block",
    ),

    # Negative cases: ordinary prose and completions
    (
        [TOOL, say("Filed as [#1948](https://github.com/Morrison-Lab/ai-config/issues/1948).")],
        False,
        "past-tense filing report does not block",
    ),
    (
        [TOOL, say("Implementation complete and all tests pass.")],
        False,
        "standard completion report does not block",
    ),
    ([TOOL], False, "turn with no text does not block"),

    # Antigravity format cases
    (
        [
            {"source": "MODEL", "type": "PLANNER_RESPONSE", "tool_calls": [{"name": "run_command", "args": {"CommandLine": "git status"}}]},
            {"source": "MODEL", "type": "PLANNER_RESPONSE", "content": "Want me to file an issue for this?"}
        ],
        True,
        "antigravity format offer blocks",
    ),
    (
        [
            {"source": "MODEL", "type": "PLANNER_RESPONSE", "tool_calls": [{"name": "run_command", "args": {"CommandLine": "git status"}}]},
            {"source": "MODEL", "type": "PLANNER_RESPONSE", "content": "Filed as [#1948](https://github.com/Morrison-Lab/ai-config/issues/1948)."}
        ],
        False,
        "antigravity format non-offer does not block",
    ),
]


def run(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    try:
        env = dict(os.environ, TMPDIR=tempfile.mkdtemp())
        out = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps({"transcript_path": path}),
            capture_output=True,
            text=True,
            env=env,
        ).stdout
        if '"decision": "block"' in out or '"decision":"block"' in out:
            return "block"
        if '"systemMessage"' in out:
            return "warn"
        return "pass"
    finally:
        os.unlink(path)


def main():
    passes = failures = 0
    for events, expected, label in CASES:
        raw = run(events)
        # Legacy cases use True/False for block; DEFER cases use "warn".
        got = raw if isinstance(expected, str) else (raw == "block")
        if got == expected:
            print(f"PASS: {label}")
            passes += 1
        else:
            print(f"FAIL: {label} (expected {expected}, got {got})")
            failures += 1

    # Sentinel behavior: same message twice should not block on second run
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps(say("Want me to file an issue?")) + "\n")
    env = dict(os.environ, TMPDIR=tempfile.mkdtemp())
    payload = json.dumps({"transcript_path": path})
    first = subprocess.run(
        [sys.executable, HOOK],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
    ).stdout
    second = subprocess.run(
        [sys.executable, HOOK],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
    ).stdout
    os.unlink(path)

    if "block" in first and "block" not in second:
        print("PASS: sentinel stops repeating block on same message")
        passes += 1
    else:
        print("FAIL: sentinel did not suppress repeat block")
        failures += 1


    # Warn-arm idempotence: the same deferral message twice must warn once.
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps(say(
            "I've filed enough issues today that I'd rather you tell me whether "
            "this one is worth it."
        )) + "\n")
    env = dict(os.environ, TMPDIR=tempfile.mkdtemp())
    payload = json.dumps({"transcript_path": path})
    w1 = subprocess.run([sys.executable, HOOK], input=payload,
                        capture_output=True, text=True, env=env).stdout
    w2 = subprocess.run([sys.executable, HOOK], input=payload,
                        capture_output=True, text=True, env=env).stdout
    os.unlink(path)
    if '"systemMessage"' in w1 and '"systemMessage"' not in w2:
        print("PASS: warn arm fires once per message")
        passes += 1
    else:
        print("FAIL: warn arm should fire once per message")
        failures += 1
    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
