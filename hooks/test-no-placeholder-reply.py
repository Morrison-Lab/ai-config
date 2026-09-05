"""Test the no-placeholder-reply guard.

The value is concentrated in the negative cases, and one of them is the whole
reason the matcher is anchored on the WHOLE message: this corpus discusses the
banned string constantly, so a substring matcher would block every reply that
quotes the rule it enforces -- including the guard's own docstring, this test,
and the CLAUDE.md section it cites.

The other negative worth its own case is the no-change tick. CLAUDE.md
REQUIRES a scheduled check that found nothing to say so in one line, so a
guard that blocked "Nothing to report." would forbid the behaviour it exists
to protect.

Run: python3 hooks/test-no-placeholder-reply.py hooks/no-placeholder-reply.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

TOOL = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {"command": "git status --short"}}]}}


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


# (events, should_block, label)
CASES = [
    # Case one is the reported input, verbatim, per algorithmatize-checks'
    # "Test the instrument against the incident that prompted it".
    ([TOOL, say("No response requested.")], True,
     "the reported string, verbatim, blocks"),
    ([TOOL, say("no response needed")], True,
     "an unpunctuated lowercase variant blocks"),
    ([TOOL, say("No reply required.")], True,
     "'reply' in place of 'response' blocks"),
    ([TOOL, say("*No response requested.*")], True,
     "emphasis dressing is stripped before matching"),
    ([TOOL, say("(No reply needed)")], True,
     "bracket dressing is stripped before matching"),
    ([TOOL, say("N/A")], True, "a bare N/A blocks"),
    ([TOOL, say("Acknowledged.")], True, "a bare acknowledgement blocks"),
    ([TOOL, say("Nothing further.")], True, "'nothing further' blocks"),

    # THE critical negative: the guard must not fire on prose that quotes the
    # banned string. Every rule file, issue, and PR body in this corpus does.
    ([TOOL, say(
        "CLAUDE.md bans replying `No response requested.` outright, so the "
        "guard anchors on the whole message rather than searching inside it."
    )], False, "a message QUOTING the banned string does not block"),

    # The no-change tick CLAUDE.md requires. Blocking these would forbid the
    # prescribed behaviour.
    ([TOOL, say("Nothing to report --- the poll found no change.")], False,
     "the prescribed no-change tick does not block"),
    ([TOOL, say("No change.")], False,
     "'no change' reports an outcome and does not block"),
    ([TOOL, say("Done.")], False,
     "a terse completion report does not block"),

    # Ordinary replies.
    ([TOOL, say("Merged #1578; branch re-cut from main at 0b7b6a6c.")], False,
     "an ordinary short recap does not block"),
    ([TOOL], False, "a turn with no assistant prose does not block"),

    # Antigravity format cases
    ([
        {"source": "MODEL", "type": "PLANNER_RESPONSE", "tool_calls": [{"name": "run_command", "args": {"CommandLine": "git status"}}]},
        {"source": "MODEL", "type": "PLANNER_RESPONSE", "content": "No response requested."}
    ], True, "antigravity placeholder blocks"),
    ([
        {"source": "MODEL", "type": "PLANNER_RESPONSE", "tool_calls": [{"name": "run_command", "args": {"CommandLine": "git status"}}]},
        {"source": "MODEL", "type": "PLANNER_RESPONSE", "content": "Merged #1578; branch re-cut from main at 0b7b6a6c."}
    ], False, "antigravity non-placeholder does not block"),
    # Thinking block format with placeholder text block
    ([
        {"type": "assistant", "message": {"content": [
            {"type": "thinking", "thinking": "Let me see if any response is needed."},
            {"type": "text", "text": "No response requested."}
        ]}}
    ], True, "thinking block + placeholder text block blocks"),
    # Thinking block format with substantive text block
    ([
        {"type": "assistant", "message": {"content": [
            {"type": "thinking", "thinking": "Let me see if any response is needed."},
            {"type": "text", "text": "Completed task successfully."}
        ]}}
    ], False, "thinking block + substantive text block does not block"),
    # String content assistant message
    ([{"type": "assistant", "content": "No response requested."}], True,
     "assistant string content placeholder blocks"),
]


def run(events, key_name="transcript_path"):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    try:
        # Fresh sentinel dir per case, so the once-per-message guard does not
        # make later cases silently pass.
        env = dict(os.environ, TMPDIR=tempfile.mkdtemp())
        out = subprocess.run(
            [sys.executable, HOOK], input=json.dumps({key_name: path}),
            capture_output=True, text=True, env=env,
        ).stdout
        return '"decision": "block"' in out or '"decision":"block"' in out
    finally:
        os.unlink(path)


def run_direct_payload(payload):
    env = dict(os.environ, TMPDIR=tempfile.mkdtemp())
    out = subprocess.run(
        [sys.executable, HOOK], input=json.dumps(payload),
        capture_output=True, text=True, env=env,
    ).stdout
    return '"decision": "block"' in out or '"decision":"block"' in out


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

    # Alternative transcript payload keys (transcriptPath, transcript, history_file)
    for key in ("transcriptPath", "transcript", "history_file"):
        got = run([say("No response requested.")], key_name=key)
        if got:
            print(f"PASS: payload key '{key}' resolves transcript correctly")
            passes += 1
        else:
            print(f"FAIL: payload key '{key}' failed to trigger block")
            failures += 1

    # Direct payload fields without transcript file
    direct_cases = [
        ({"reply": "No response requested."}, True, "direct reply field blocks"),
        ({"last_assistant_message": "No response requested."}, True, "direct last_assistant_message field blocks"),
        ({"message": {"content": [{"type": "text", "text": "No response requested."}]}}, True, "direct message object blocks"),
        ({"content": "No response requested."}, True, "direct content string blocks"),
        ({"reply": "Completed wave-1 review and tests passed."}, False, "direct reply substantive does not block"),
    ]
    for payload, expected, label in direct_cases:
        got = run_direct_payload(payload)
        if got == expected:
            print(f"PASS: {label}")
            passes += 1
        else:
            print(f"FAIL: {label} (expected block={expected}, got {got})")
            failures += 1

    # The once-per-message sentinel: a second run over the same message must
    # not block again, so a block cannot loop.
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps(say("No response requested.")) + "\n")
    env = dict(os.environ, TMPDIR=tempfile.mkdtemp())
    payload = json.dumps({"transcript_path": path})
    first = subprocess.run([sys.executable, HOOK], input=payload,
                           capture_output=True, text=True, env=env).stdout
    second = subprocess.run([sys.executable, HOOK], input=payload,
                            capture_output=True, text=True, env=env).stdout
    os.unlink(path)
    if "block" in first and "block" not in second:
        print("PASS: the sentinel stops a block repeating on the same message")
        passes += 1
    else:
        print("FAIL: sentinel did not suppress the repeat block")
        failures += 1

    # The complement: no-offer-to-file.py must NOT fire on a bare placeholder,
    # which is why this hook is needed rather than a widening of that one. If
    # that ever changes, one of the two is redundant and should be merged.
    sibling = os.path.join(os.path.dirname(HOOK), "no-offer-to-file.py")
    if os.path.exists(sibling):
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w") as fh:
            fh.write(json.dumps(say("No response requested.")) + "\n")
        out = subprocess.run(
            [sys.executable, sibling],
            input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True,
            env=dict(os.environ, TMPDIR=tempfile.mkdtemp()),
        ).stdout
        os.unlink(path)
        if "block" in out:
            print("FAIL: no-offer-to-file.py already covers a bare placeholder")
            failures += 1
        else:
            print("PASS: no-offer-to-file.py does not cover this shape")
            passes += 1

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
