#!/usr/bin/env python3
"""Tests for hooks/no-unlinked-session-mention.py.

Run: python3 hooks/test-no-unlinked-session-mention.py [hooks/no-unlinked-session-mention.py]
"""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "no-unlinked-session-mention.py")
REPLY = "mcp__hearthbot__reply"
POST = "mcp__hearthbot__post_message"
S = "[session](https://claude.ai/code/session_01UP3WKF9PWfKhoifszpKAEV)"
T = "[Fix the lint](#cmsg_01A)"

# (name, tool, text, expected phrase quoted in the denial; None = silent)
CASES = [
    ("Mac session", POST, "Your Mac session is waiting.", "Your Mac session"),
    ("Remote Control session", POST, "The Remote Control session is idle.", "Remote Control session"),
    ("RC session", REPLY, "Ask the RC session.", "RC session"),
    ("coordinator", POST, "The coordinator suggested it.", "coordinator"),
    ("coordinator session", POST, "The coordinator session suggested it.", "coordinator session"),
    ("update_message", "mcp__hearthbot__update_message", "Ask the cloud session.", "cloud session"),
    ("edit_message", "mcp__hearthbot__edit_message", "The thread that owns the runner is waiting.", "The thread"),
    ("capitalised", POST, "REMOTE CONTROL SESSIONS stopped.", "REMOTE CONTROL SESSIONS"),
    ("two words between", POST, "Your remote desktop session is idle.", "Your remote desktop session"),
    ("host-named chat", POST, "The cf463-02 chat is idle.", "cf463-02 chat"),
    ("documented example", POST, "The ab12-03 chat is idle.", "ab12-03 chat"),
    ("that chat", POST, "Ask that chat to retry.", "that chat"),
    ("RC chat", POST, "The RC chat is waiting.", "RC chat"),
    ("Mac chat", POST, "Your Mac chat is open.", "Your Mac chat"),
    ("other chat", POST, "Use the other chat.", "other chat"),
    ("gpt4 chat is not a host", POST, "I'll ping the gpt4 chat about this.", None),
    ("v2 chat is not a host", POST, "Check the v2 chat for details.", None),
    ("win32 chat is not a host", POST, "Our win32 chat client crashed.", None),
    ("chat linked", POST, f"The cf463-02 chat ({S}) is idle.", None),
    ("this chat is fine", POST, "I will answer in this chat.", None),
    ("project chat is fine", POST, "I posted it in the project chat.", None),
    ("linked in same paragraph", POST, f"The Mac session ({S}) is waiting.", None),
    ("thread link covers it", POST, f"The coordinator thread, {T}.", None),
    ("link in a different paragraph", POST, f"The Mac session is idle.\n\n{S}", "Mac session"),
    ("each item has its own link", POST,
     f"- Mac session {S}\n- coordinator {T}", None),
    ("second item unlinked", POST,
     f"- Mac session {S}\n- coordinator", "coordinator"),
    ("this session is not another session", POST, "I will keep this session open.", None),
    ("a session is not a mention", POST, "Open a session when ready.", None),
    ("inline code", POST, "The phrase `Mac session` is blocked.", None),
    ("fenced code", POST, "```\ncoordinator\n```\nDone.", None),
    ("other tool", "Bash", "echo coordinator", None),
    ("host-named session", POST, "The ab12-03 session is idle.", "ab12-03 session"),
    ("that thread", POST, "Ask that thread.", "that thread"),
    ("training session is fine", POST, "I have a training session tomorrow.", None),
    ("study session is fine", POST, "The study session starts at 7pm.", None),
    ("legislative session is fine", POST, "The legislative session begins in January.", None),
    ("support thread is fine", POST, "Check the support thread for updates.", None),
    ("that session", POST, "Ask that session.", "that session"),
    ("other thread", POST, "See the other thread.", "other thread"),
    ("the session", POST, "Ask the session to retry.", "the session"),
    ("host session linked", POST, f"The ab12-03 session ({S}) is idle.", None),
    ("runner thread linked", POST, f"The runner thread, {T}.", None),
    ("this thread is fine", POST, "I will keep this thread open.", None),
    ("a thread is fine", POST, "Start a thread when ready.", None),
    ("each session is fine", POST, "Each session has its own cache.", None),
    ("multi-thread is fine", POST, "The multi-thread build is faster.", None),
    ("SessionStart is fine", POST, "The SessionStart hook ran.", None),
    ("R session is fine", POST, "Restart the R session and try again.", None),
    ("main thread is fine", POST, "Check the main thread for the race.", None),
    ("database session is fine", POST, "The database session timed out.", None),
    ("worker thread is fine", POST, "Pull the error from the worker thread.", None),
    ("review thread is fine", POST, "Resolve the review thread.", None),
    ("backticks exempt a technical thread", POST, "Lock `the thread` before writing.", None),
    ("the runner thread", POST, "Ask the runner thread to retry.", "the runner thread"),
    ("the CI thread", POST, "The CI thread found it.", "The CI thread"),
    ("our metrics thread", POST, "See our metrics thread.", "our metrics thread"),
    ("hyphenated name", POST, "Ask the gha-runner thread.", "the gha-runner thread"),
    ("plural", POST, "Both of the metrics threads agree.", "the metrics threads"),
    ("named thread linked", POST, f"The CI thread ({T}) found it.", None),
    ("named thread in other paragraph", POST, f"The CI thread found it.\n\n{T}", "The CI thread"),
    ("named thread in code", POST, "The `the runner thread` string is blocked.", None),
    ("this thread stays exempt", POST, "I will keep this thread open.", None),
    ("the main thread stays exempt", POST, "The main thread blocks.", None),
    ("the email thread stays exempt", POST, "Reply on the email thread.", None),
    ("the comment thread stays exempt", POST, "Resolve the comment thread.", None),
    ("no mention", POST, "Done.", None),
]


def run(tool, text):
    event = {"tool_name": tool, "tool_input": {"text": text}}
    proc = subprocess.run([sys.executable, HOOK], input=json.dumps(event),
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout


def main():
    failures = 0
    for name, tool, text, expected in CASES:
        code, out = run(tool, text)
        ok = code == 0
        if expected is None:
            ok = ok and out == ""
        else:
            hso = json.loads(out)["hookSpecificOutput"] if out else {}
            reason = hso.get("permissionDecisionReason", "")
            ok = (ok and hso.get("permissionDecision") == "deny"
                  and f'("{expected}")' in reason)
        if not ok:
            failures += 1
            print(f"FAIL {name}: code={code} out={out!r}")
    for bad in ("", "not json", "[]", json.dumps({"tool_name": REPLY, "tool_input": []}),
                json.dumps({"tool_name": REPLY, "tool_input": {"text": 5}})):
        proc = subprocess.run([sys.executable, HOOK], input=bad,
                              capture_output=True, text=True)
        if proc.returncode != 0 or proc.stdout:
            failures += 1
            print(f"FAIL malformed input {bad!r}")
    print("ok" if not failures else f"{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
