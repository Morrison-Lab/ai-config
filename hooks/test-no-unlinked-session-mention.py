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
    ("capitalised", POST, "REMOTE CONTROL SESSIONS stopped.", "REMOTE CONTROL SESSIONS"),
    ("two words between", POST, "Your remote desktop session is idle.", "Your remote desktop session"),
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
