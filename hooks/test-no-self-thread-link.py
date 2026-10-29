#!/usr/bin/env python3
"""Tests for hooks/no-self-thread-link.py (ai-config#4843).

Run: python3 hooks/test-no-self-thread-link.py [hooks/no-self-thread-link.py]
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "no-self-thread-link.py")
POST = "mcp__hearthbot__post_message"
OWN = "cmsg_01OWN"
THREAD_LOG = (f'You are a Thread Session created by this project. '
              f'<wake><thread ts="{OWN}"><message>hi</message></thread></wake>')
COORD_LOG = f'<wake><thread ts="{OWN}"><message>hi</message></thread></wake>'
SELF = f"[Qualify residual risk](#{OWN})"
OTHER = "[Runner work](#cmsg_01OTHER)"

# (name, transcript text or None, text, expect denial)
CASES = [
    ("self link in a thread", THREAD_LOG, f"This is in {SELF}.", True),
    ("self link by URL", THREAD_LOG, f"See https://claude.ai/code/project/c?thread={OWN}.", True),
    ("other thread is fine", THREAD_LOG, f"Merge word goes in {OTHER}.", False),
    ("self and other still blocks", THREAD_LOG, f"{SELF} and {OTHER}", True),
    ("self link in code is ignored", THREAD_LOG, f"```\n(#{OWN})\n```", False),
    ("coordinator is never blocked", COORD_LOG, f"Merge word in {SELF}.", False),
    ("no transcript", None, f"This is in {SELF}.", False),
    ("prefix of another id is not self", THREAD_LOG, "[x](#cmsg_01OWNER)", False),
]


def run(tool, text, transcript):
    event = {"tool_name": tool, "tool_input": {"text": text}}
    path = None
    if transcript is not None:
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
            f.write(transcript)
            path = f.name
        event["transcript_path"] = path
    try:
        proc = subprocess.run([sys.executable, HOOK], input=json.dumps(event),
                              capture_output=True, text=True)
    finally:
        if path:
            os.unlink(path)
    return proc.returncode, proc.stdout


def main():
    failures = 0
    for name, transcript, text, deny in CASES:
        code, out = run(POST, text, transcript)
        ok = code == 0
        if deny:
            hso = json.loads(out)["hookSpecificOutput"] if out else {}
            ok = ok and hso.get("permissionDecision") == "deny" and OWN in hso.get(
                "permissionDecisionReason", "")
        else:
            ok = ok and out == ""
        if not ok:
            failures += 1
            print(f"FAIL {name}: code={code} out={out!r}")
    code, out = run("Bash", f"This is in {SELF}.", THREAD_LOG)
    if code != 0 or out:
        failures += 1
        print("FAIL other tool")
    for bad in ("", "not json", "[]", json.dumps({"tool_name": POST, "tool_input": []}),
                json.dumps({"tool_name": POST, "tool_input": {"text": 5}}),
                json.dumps({"tool_name": POST, "tool_input": {"text": SELF},
                            "transcript_path": "/nonexistent"})):
        proc = subprocess.run([sys.executable, HOOK], input=bad,
                              capture_output=True, text=True)
        if proc.returncode != 0 or proc.stdout:
            failures += 1
            print(f"FAIL malformed input {bad!r}")
    print("ok" if not failures else f"{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
