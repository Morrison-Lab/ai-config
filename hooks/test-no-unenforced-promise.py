#!/usr/bin/env python3
"""Test the no-unenforced-promise guard.

Verifies that a hearthbot message making a standing first-person promise is
refused unless its paragraph names a hook, script or workflow that exists,
and that one-off plans, past-tense reports, quotes and statements of what a
mechanism does pass.

Run: python3 hooks/test-no-unenforced-promise.py hooks/no-unenforced-promise.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "no-unenforced-promise.py")

# Tonight's two coordinator messages (2026-11-26) must both be refused.
INCIDENT_1 = "From now on, I'll check every PR for conflicts before I call it ready."
INCIDENT_2 = "Until the hook lands, I'll get the conflict check from a thread."

CASES = [
    (INCIDENT_1, True, "the 'from now on' incident is refused"),
    (INCIDENT_2, True, "the 'until the hook lands' incident is refused"),
    ("Going forward, I will read mergeability first.", True, "'going forward, I will' is refused"),
    ("I'll always read the PR live before reporting it.", True, "'I'll always' is refused"),
    ("I will make sure every PR is checked.", True, "'I will make sure' is refused"),
    ("We'll never skip the preview check again.", True, "'we'll never' is refused"),
    ("Until #6157 merges, we'll check by hand.", True, "'until X merges, we'll' is refused"),
    ("Moving forward I won't call a PR ready unread.", True, "'moving forward I won't' is refused"),
    ("From now on, I'll check conflicts; I'll add `hooks/no-such-hook-xyz.py` for it.", True,
     "a hook that does not exist yet does not count"),
    ("Done.\n\nFrom now on, I'll check conflicts.\n\nSee `no-unfetched-pr-state-claim.py`.", True,
     "a hook named in another paragraph does not count"),

    # Named, existing mechanism
    ("From now on, `no-unfetched-pr-state-claim.py` refuses a ready claim, so I'll "
     "never call a PR ready unread.", False, "a promise naming an existing hook passes"),
    ("Going forward I'll follow it; hooks/no-empty-promise.py enforces it.", False,
     "a path to an existing hook passes"),
    ("From now on I'll run it through check-pr-fully-clean before merging.", False,
     "an existing script named without extension passes"),

    # Not a standing promise
    ("I'll post the PR link here when it's open.", False, "a one-off plan passes"),
    ("I added a hook, so from now on the coordinator's ready claims are denied.", False,
     "a past-tense report with no first-person modal passes"),
    ("The hook denies a ready claim from now on.", False, "a statement about a hook passes"),
    ('You wrote "from now on, I\'ll check every PR" earlier.', False, "quoted words pass"),
    ("The coordinator said:\n\n> Until the hook lands, I'll get the check from a thread.", False,
     "a blockquote passes"),
    ("The hook catches `from now on, I'll` phrasing.", False, "a code span passes"),
    ("In the future tense section, nothing changes.", False, "no modal passes"),
    ("Done.", False, "unrelated text passes"),
]


def run(payload):
    return subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                          capture_output=True, text=True,
                          env=dict(os.environ, CLAUDE_PROJECT_DIR=tempfile.mkdtemp()))


def denied(text, tool="mcp__hearthbot__post_message"):
    out = run({"tool_name": tool, "tool_input": {"text": text}}).stdout
    if not out.strip():
        return False
    spec = json.loads(out)["hookSpecificOutput"]
    assert spec["hookEventName"] == "PreToolUse"
    assert "[hook: no-unenforced-promise]" in spec["permissionDecisionReason"]
    return spec["permissionDecision"] == "deny"


def main():
    passes = failures = 0

    def check(ok, label):
        nonlocal passes, failures
        print(("PASS: " if ok else "FAIL: ") + label)
        if ok:
            passes += 1
        else:
            failures += 1

    for text, expected, label in CASES:
        check(denied(text) == expected, label)

    for tool in ("mcp__hearthbot__message_coordinator", "mcp__hearthbot__message_thread",
                 "mcp__hearthbot__reply", "mcp__hearthbot__edit_message"):
        check(denied(INCIDENT_1, tool), f"{tool} is covered")

    check(all(denied(INCIDENT_2) for _ in range(3)), "a resend is refused every time")
    check(not denied(INCIDENT_1, "Bash"), "a non-message tool is ignored")

    out = run({"tool_name": "mcp__hearthbot__post_message",
               "tool_input": {"text": INCIDENT_1}}).stdout
    check("from now on" in out.lower() and "ai-config#6157" in out,
          "the reason quotes the phrase and names the issue")

    bad = subprocess.run([sys.executable, HOOK], input="not json",
                         capture_output=True, text=True)
    check(bad.returncode == 0 and not bad.stdout.strip(), "unreadable payload fails open")

    with tempfile.TemporaryDirectory() as tmp:
        lone = os.path.join(tmp, "no-unenforced-promise.py")
        with open(HOOK, encoding="utf-8") as src, open(lone, "w", encoding="utf-8") as dst:
            dst.write(src.read())
        orphan = subprocess.run([sys.executable, lone], input="{}",
                                capture_output=True, text=True)
    check(orphan.returncode == 0 and not orphan.stdout.strip(),
          "missing sibling module fails open")

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
