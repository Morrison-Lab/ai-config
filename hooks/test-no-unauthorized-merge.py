#!/usr/bin/env python3
"""Test the no-unauthorized-merge guard.

Must live in a file rather than a Bash heredoc so test runner (scripts/test_hooks.py)
can invoke it directly with sys.argv[1].
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else str(Path(__file__).parent / "no-unauthorized-merge.py")

if not os.path.isfile(HOOK):
    sys.exit(f"FATAL: hook not found at {HOOK}")

BLOCK = [
    ("gh pr merge 411 --squash", "bare gh pr merge"),
    ("gh -R owner/repo pr merge 411 --squash", "gh pr merge with -R flag"),
    ("gh --repo owner/repo pr merge 411", "gh pr merge with --repo flag"),
    ("glab mr merge 12", "glab mr merge"),
    ("glab -R owner/repo mr merge 12", "glab mr merge with -R flag"),
    ("gh api -X PUT /repos/owner/repo/pulls/123/merge", "gh api PR merge"),
    ("echo foo && gh pr merge 123", "compound command with merge segment"),
]

ALLOW = [
    ("gh pr view 411", "read-only gh pr view"),
    ("gh pr comment 411 --body 'gh pr merge failed'", "quoted string containing trigger text"),
    ("ALLOW_MERGE=1 gh pr merge 411 --squash", "explicit ALLOW_MERGE=1 env flag"),
    ("echo ALLOW_MERGE=1 && gh pr view 411", "ALLOW_MERGE in benign command"),
]


def verdict(cmd: str) -> str:
    p = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}}),
        capture_output=True,
        text=True,
    )
    if p.returncode != 0:
        sys.exit(f"FATAL: hook exited {p.returncode} on {cmd!r}\n{p.stderr.strip()}")
    return "BLOCK" if '"permissionDecision": "deny"' in p.stdout else "allow"


wrong = 0
print("should BLOCK:")
for cmd, desc in BLOCK:
    v = verdict(cmd)
    wrong += (v != "BLOCK")
    print(f"  {v:<6} {desc}")

print("\nshould ALLOW:")
for cmd, desc in ALLOW:
    v = verdict(cmd)
    wrong += (v != "allow")
    print(f"  {v:<6} {desc}")

# Test active MWC grant integration
script_path = Path(__file__).parent.parent / "skills" / "session-lock" / "scripts" / "ai-session.sh"
test_id = f"test-mwc-{os.getpid()}"
subprocess.run([str(script_path), "register", "--id", test_id], check=True, capture_output=True)
subprocess.run([str(script_path), "enable-mwc", "--id", test_id], check=True, capture_output=True)

try:
    env = dict(os.environ, AI_SESSION_ID=test_id)
    p = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "gh pr merge 411 --squash"}}),
        capture_output=True,
        text=True,
        env=env,
    )
    v = "allow" if '"permissionDecision": "deny"' not in p.stdout else "BLOCK"
    wrong += (v != "allow")
    print(f"  {v:<6} active MWC grant for session")
finally:
    subprocess.run([str(script_path), "release", "--id", test_id], check=True, capture_output=True)

total = len(BLOCK) + len(ALLOW) + 1
print(f"\n{total - wrong}/{total} correct" + ("" if wrong == 0 else f"  ({wrong} WRONG)"))
sys.exit(1 if wrong else 0)
