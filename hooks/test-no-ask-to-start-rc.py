#!/usr/bin/env python3
"""Tests for hooks/no-ask-to-start-rc.py.

Run: python3 hooks/test-no-ask-to-start-rc.py [hooks/no-ask-to-start-rc.py]
"""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "no-ask-to-start-rc.py")
POST = "mcp__hearthbot__post_message"
RELAY = "mcp__hearthbot__message_thread"
COMMENT = "mcp__github__add_issue_comment"

# (name, tool, field, text, should_deny)
CASES = [
    ("please start RC", POST, "text", "Please start Remote Control on cf463-02 so I can run the dry run.", True),
    ("can you run claude remote-control", POST, "text", "Can you run `claude remote-control` in ~/Documents/claude-fetch?", True),
    ("you need to launch RC", POST, "text", "You'll need to launch RC on the XPS before I can continue.", True),
    ("need you to start", POST, "text", "I need you to start a Remote Control session on the Mac.", True),
    ("imperative", POST, "text", "Start Remote Control on cf463-02. Then reply here.", True),
    ("passive on your machine", POST, "text", "Remote Control needs to be started on your machine first.", True),
    ("from your terminal", POST, "text", "From your terminal, run claude remote-control in that folder.", True),
    ("message_thread", RELAY, "text", "Ezra needs to start Remote Control; please ask him.", False),
    ("github comment body", COMMENT, "body", "Could you start Remote Control on cf463-02 and rerun?", True),
    ("quoted ask", POST, "text", 'You said: "please start Remote Control" earlier, so I did.', False),
    ("quoted in PR body", "mcp__github__create_pull_request", "body", 'Adds a hook that denies messages like "please start Remote Control".', False),
    ("open RC UI pointer", POST, "text", "Open Remote Control to see the session.", False),
    ("fenced block", POST, "text", "Example:\n```\nPlease start Remote Control\n```\nDone.", False),
    ("blockquote", POST, "text", "> Please start Remote Control\nThat was the old wording.", False),
    ("would you mind", POST, "text", "Would you mind starting Remote Control?", True),
    ("restart", POST, "text", "Can you restart Remote Control?", True),
    ("trailing negation does not cancel", POST, "text", "Please start Remote Control, don't forget.", True),
    ("passive session started", POST, "text", "I need a Remote Control session started on your Mac.", True),
    ("let me know when started", POST, "text", "Let me know when you've started Remote Control.", True),
    ("yourself after ask", POST, "text", "You can start remote control yourself if you want.", False),
    ("title field", COMMENT, "title", "Please start Remote Control", True),
    ("decision question", "mcp__hearthbot__request_decision", "question", "Can you start Remote Control on the XPS?", True),
    ("apology then ask", POST, "text", "Do not worry: please start Remote Control.", True),
    ("not running then ask", POST, "text", "Remote Control is not running; please start it, Remote Control on the Mac.", True),
    ("please comma", POST, "text", "Please, start Remote Control.", True),
    ("please kindly", POST, "text", "Please kindly start Remote Control.", True),
    ("go ahead and", POST, "text", "Go ahead and start Remote Control.", True),
    ("terminal and start", POST, "text", "Open a terminal and start Remote Control.", True),
    ("bullet imperative", POST, "text", "- start Remote Control on the Mac", True),
    ("RemoteControl one word", POST, "text", "Please start RemoteControl.", True),
    ("question about past ask", POST, "text", "Why did I ask you to start Remote Control?", False),
    ("nested card field", "mcp__hearthbot__post_widget", "body", {"a": ["Please start Remote Control"]}, True),
    ("unrelated stop then ask", POST, "text", "Stop what you're doing and please start Remote Control.", True),
    ("past-tense report opening a sentence", POST, "text", "Started Remote Control on cf463-02.", False),
    ("done then started report", POST, "text", "Done. Started remote control on the XPS; session is running.", False),
    ("launched report", POST, "text", "Launched Remote Control on cf463-02 (session abc).", False),
    ("bullet describing the hook", "mcp__github__create_pull_request", "body", "- Start Remote Control sessions via start_remote_control instead of asking.", False),
    ("run remote control tests", "mcp__github__create_pull_request", "body", "Run remote control tests: all pass.", False),
    ("enable support", "mcp__github__create_pull_request", "body", "Enable remote control support in the config schema.", False),
    ("you can start sessions with the tool", POST, "text", "You can start Remote Control sessions with start_remote_control.", False),
    ("once you start then card", POST, "text", "Once you start Remote Control sessions, the card appears.", False),
    ("for me", POST, "text", "Can you start Remote Control for me?", True),
    ("backticked command no punctuation", POST, "text", "Can you run `claude remote-control` for me", True),
    ("parenthetical", POST, "text", "Please start Remote Control (cf463-02).", True),
    ("dash form", POST, "text", "Please start Remote Control - cf463-02.", True),
    ("flag after command", POST, "text", "Can you run claude remote-control --spawn worktree?", True),
    ("the command noun", POST, "text", "Please run the claude remote-control command.", True),
    ("fire up", POST, "text", "Could you fire up Remote Control on cf463-02?", True),
    ("single-quoted example in PR body", "mcp__github__create_pull_request", "body", "It denies 'Can you run claude remote-control?' in replies.", False),
    ("backticked example in PR body", "mcp__github__create_pull_request", "body", "It denies `Please start Remote Control on cf463-02`.", False),
    ("bullet plan in PR body", "mcp__github__create_pull_request", "body", "## Test plan\n- Start Remote Control on cf463-02\n- Run the dry run", False),
    ("numbered steps in comment", COMMENT, "body", "Steps taken:\n1. Start Remote Control on cf463-02\n2. Report", False),
    ("bullet ask in hearthbot still denied", POST, "text", "- Start Remote Control on cf463-02", True),
    ("backticked command ask still denied", POST, "text", "Please run `claude remote-control` on cf463-02.", True),
    ("apostrophes are not quotes", POST, "text", "Can't wait; please start Remote Control on the Mac, it's quick.", True),
    ("agent started it", POST, "text", "I started a Remote Control session on cf463-02 and the dry run passed.", False),
    ("agent will start", POST, "text", "I'll start Remote Control on the XPS now.", False),
    ("negated ask", POST, "text", "I won't ask you to start Remote Control; I do it myself.", False),
    ("no need", POST, "text", "No need to run Remote Control yourself; the thread starts it.", False),
    ("RC as other word", POST, "text", "Run the rc settings check on the file.", False),
    ("start unrelated", POST, "text", "Start the render and open the report.", False),
    ("rc in code", POST, "text", "Run rc.local after the build.", False),
    ("unrelated tool", "Bash", "text", "Please start Remote Control.", False),
    ("no text", POST, "text", None, False),
]


def run(tool, field, text):
    payload = {"tool_name": tool, "tool_input": {field: text} if text is not None else {}}
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload), capture_output=True, text=True)
    return p.returncode, p.stdout


def main():
    fails = 0
    for name, tool, field, text, deny in CASES:
        rc, out = run(tool, field, text)
        denied = '"permissionDecision": "deny"' in out
        ok = rc == 0 and denied == deny
        print(("  ok      " if ok else "  FAIL    ") + name)
        fails += 0 if ok else 1
    p = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True)
    ok = p.returncode == 0 and not p.stdout
    print(("  ok      " if ok else "  FAIL    ") + "fails open on garbage stdin")
    fails += 0 if ok else 1
    total = len(CASES) + 1
    print(f"\n{total - fails}/{total} correct")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
