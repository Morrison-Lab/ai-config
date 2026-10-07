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


def reply(text):
    return {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "name": "mcp__hearthbot__reply",
                    "input": {"text": text},
                }
            ]
        },
    }


def narrate_and_reply(narration, text):
    return {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "text", "text": narration},
                {
                    "type": "tool_use",
                    "name": "mcp__hearthbot__reply",
                    "input": {"text": text},
                },
            ]
        },
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

    # Offering to attach the repository a fix belongs in (ai-config#4337)
    (
        [TOOL, say("Filing the delimited-def problem upstream (would need add_repo) is still open.")],
        True,
        "'would need add_repo' blocks",
    ),
    ([TOOL, say("Want me to attach the macros repo and file it?")], True, "want me to attach blocks"),
    ([TOOL, say("I can attach the upstream repository too if that helps?")], True, "i can attach the repo ... ? blocks"),
    ([TOOL, say("I can attach the repo if you want.")], True, "i can attach the repo if you want blocks"),
    ([TOOL, say("Would you like me to attach the macros repository?")], True, "would you like me to attach blocks"),
    ([TOOL, say("Should I add the repository to the session?")], True, "should I add the repository blocks"),
    ([TOOL, say("Should I attach the file?")], False, "attach a file is not a repo offer"),
    ([TOOL, say("Should I attach a screenshot of the render?")], False, "attach a screenshot passes"),
    ([TOOL, say("The hook would need add_repo to be allowed in its matcher.")], False, "explaining what a hook needs passes"),
    ([TOOL, say("I called add_repo because the clone would need add_repo access first.")], False, "explaining an add_repo call passes"),
    ([TOOL, say("Attached Morrison-Lab/macros with add_repo and filed macros#108.")], False, "past-tense attach report passes"),
    ([TOOL, say("add_repo attached the repository, so the clone ran next.")], False, "add_repo mentioned as done passes"),
    ([TOOL, say("I attached it with `add_repo`; it would need a clone after that, which I ran.")], False, "attach done plus clone note passes"),

    # Statement-shaped offers (no question mark): both let through before
    (
        [TOOL, say(
            "I can also file a gha issue about the `@claude` job committing "
            "leftover session files onto PR branches, since that will happen "
            "again whenever someone writes \"@claude review\". Say if you want it."
        )],
        True,
        "statement offer 'I can also file ... Say if you want it' blocks",
    ),
    (
        [TOOL, say("I haven't filed an issue about it. Say if you want one.")],
        True,
        "statement offer 'I haven't filed an issue ... Say if you want one' blocks",
    ),
    ([TOOL, say("I haven't filed an issue about it.")], True, "haven't filed an issue alone blocks"),
    ([TOOL, say("I can file an issue for the flaky test.")], True, "i can file an issue statement blocks"),
    ([TOOL, say("I haven\u2019t filed an issue about it.")], True, "curly-apostrophe haven't filed blocks"),
    (
        [TOOL, say("The memory entry would cover this. Just say the word.")],
        True,
        "say the word near a memory mention blocks",
    ),
    (
        [TOOL, say("This deserves an issue. Let me know if you want me to file it.")],
        True,
        "let me know if you want me to file blocks",
    ),

    # Legitimate reports that share vocabulary with the statement patterns
    (
        [TOOL, say("I filed https://github.com/Morrison-Lab/gha/issues/981 about it.")],
        False,
        "report of a filed issue by URL does not block",
    ),
    (
        [TOOL, say(
            "I haven't filed an issue because "
            "https://github.com/Morrison-Lab/gha/issues/981 already tracks it."
        )],
        False,
        "not filing a duplicate does not block",
    ),
    (
        [TOOL, say(
            "Filed https://github.com/Morrison-Lab/gha/issues/981. "
            "Say if you want me to open a PR for the fix."
        )],
        False,
        "discretionary PR offer after a filed issue does not block",
    ),
    (
        [TOOL, say(
            "Filed https://github.com/Morrison-Lab/gha/issues/981 and recorded "
            "the lesson in memories/hooks.md. Say if you want it closed once the PR merges."
        )],
        False,
        "say if you want it <verb> after a filing report does not block",
    ),
    (
        [TOOL, say("Since this is already tracked, I haven't filed a new issue for it.")],
        True,
        "an unlinked 'already tracked' decline blocks",
    ),
    (
        [TOOL, say("Because #123 already covers this, I didn't file a duplicate issue.")],
        False,
        "a #N reference before a didn't-file clause does not block",
    ),
    (
        [TOOL, say(
            "The root cause is a race condition in the retry loop that was already "
            "present before this change, and the fix here just adds a lock. "
            "I haven't filed an issue about the retry-loop race, since it's out of "
            "scope for this PR and not something I want to track right now."
        )],
        True,
        "unrelated excuse word in an earlier sentence does not excuse the clause",
    ),
    (
        [TOOL, say(
            "I haven't filed an issue. The flaky test was already fixed upstream."
        )],
        True,
        "excuse word in the next sentence does not excuse the clause",
    ),
    (
        [TOOL, say(
            "Tests pass. I haven't filed an issue since "
            "https://github.com/Morrison-Lab/gha/issues/981 already tracks it."
        )],
        False,
        "excuse after a URL in the same sentence does not block",
    ),
    (
        [TOOL, say(
            "I haven't filed an issue for the other hooks (e.g. the Stop guards) "
            "because Morrison-Lab/gha#981 already covers them."
        )],
        False,
        "an e.g. abbreviation does not end the sentence",
    ),
    (
        [TOOL, say("Because Morrison-Lab/gha#981 covers this, I didn't file a duplicate.")],
        False,
        "owner/repo#N decline does not block",
    ),
    (
        [TOOL, say("Because Morrison-Lab/gha#981 covers this, I didn't file a duplicate issue.")],
        False,
        "owner/repo#N decline naming a duplicate issue does not block",
    ),
    (
        [TOOL, say(
            "I didn't file an issue: "
            "https://gitlab.com/group/proj/-/issues/12 covers it."
        )],
        False,
        "a GitLab issue URL in the same sentence does not block",
    ),
    (
        [TOOL, say(
            "The retry loop already had a lock, and I have not filed an issue "
            "about the race condition, since I want to keep this PR small."
        )],
        True,
        "comma-joined unrelated 'already' does not excuse the clause",
    ),
    (
        [TOOL, say(
            "Because we already discussed this earlier, and here is context; "
            "I have not filed an issue for the timeout bug, but that is intentional for now."
        )],
        True,
        "semicolon-joined unrelated 'already' does not excuse the clause",
    ),
    (
        [TOOL, say(
            "See https://github.com/Morrison-Lab/gha/issues/981 for context. "
            "I haven't filed an issue about the lint gap."
        )],
        True,
        "a link in a different sentence does not excuse the clause",
    ),
    (
        [TOOL, say("Since the test passes now, I haven't filed an issue about it.")],
        True,
        "a non-excuse reason before the not-filed clause still blocks",
    ),
    (
        [TOOL, say("I can file an issue-tracking script that automates this, if that's useful context.")],
        False,
        "issue as part of a compound noun does not block",
    ),
    (
        [TOOL, say("I can also file a ticket in Jira, but this repo only uses GitHub issues.")],
        False,
        "issues as an ordinary noun past a comma does not block",
    ),
    (
        [TOOL, say("The hook matches `I can also file a gha issue` statements now.")],
        False,
        "statement pattern quoted in a code span does not block",
    ),
    (
        [TOOL, say("I can't file an issue in that repo: the token lacks access.")],
        False,
        "reporting inability to file does not block",
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

    # Reply-tool visibility cases (project threads)
    (
        [TOOL, reply("Want me to file an issue for this?")],
        True,
        "reply-tool payload offer blocks",
    ),
    (
        [TOOL, reply("Filed as [#1948](https://github.com/Morrison-Lab/ai-config/issues/1948).")],
        False,
        "reply-tool payload non-offer does not block",
    ),
    (
        [
            TOOL,
            narrate_and_reply(
                "Want me to file an issue for this?",
                "Filed as [#1948](https://github.com/Morrison-Lab/ai-config/issues/1948).",
            ),
        ],
        False,
        "undelivered narration offer does not block when reply spoke",
    ),
    (
        [
            TOOL,
            narrate_and_reply(
                "Filed as [#1948](https://github.com/Morrison-Lab/ai-config/issues/1948).",
                "Want me to file an issue for this?",
            ),
        ],
        True,
        "reply-tool offer wins over clean narration",
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

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
