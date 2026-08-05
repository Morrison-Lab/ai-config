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
    ("gh -R owner/repo pr merge 411 --squash", "gh pr merge with -R flag before subcommands"),
    ("gh pr -R owner/repo merge 411 --squash", "gh pr merge with -R flag between pr and merge"),
    ("gh --repo owner/repo pr merge 411", "gh pr merge with --repo flag before subcommands"),
    ("/usr/bin/gh pr merge 411", "full executable path"),
    ("env gh pr merge 411", "env wrapper prefix"),
    ("exec gh pr merge 411", "exec wrapper prefix"),
    ("command gh pr merge 411", "command wrapper prefix"),
    ("echo $(gh pr merge 411)", "subshell command substitution"),
    ("glab mr merge 12", "glab mr merge"),
    ("glab -R owner/repo mr merge 12", "glab mr merge with -R flag before subcommands"),
    ("glab mr --repo owner/repo merge 12", "glab mr merge with --repo flag between mr and merge"),
    ("gh api -X PUT /repos/owner/repo/pulls/123/merge", "gh api PR merge with integer ID"),
    ("gh api /repos/owner/repo/pulls/$PR_NUM/merge -X PUT", "gh api PR merge with shell variable ID"),
    ("gh api /repos/owner/repo/pulls/${PR_NUM}/merge -X PUT", "gh api PR merge with braced shell variable ID"),
    ("echo foo && gh pr merge 123", "compound command with merge segment"),
]

ALLOW = [
    ("gh pr view 411", "read-only gh pr view"),
    ("gh pr comment 411 --body 'gh pr merge failed'", "quoted string containing trigger text"),
    ("gh pr comment 411 --body 'ALLOW_MERGE=1 in comment body'", "ALLOW_MERGE inside string argument"),
    ("ALLOW_MERGE=1 gh pr merge 411 --squash", "explicit ALLOW_MERGE=1 env flag"),
    ("echo ALLOW_MERGE=1 && gh pr view 411", "ALLOW_MERGE in benign command"),
]


def verdict(cmd: str, env: dict = None) -> str:
    p = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}}),
        capture_output=True,
        text=True,
        env=env,
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

# Test active MWC grant integration and session isolation
script_path = Path(__file__).parent.parent / "skills" / "session-lock" / "scripts" / "ai-session.sh"
session_a = f"test-mwc-a-{os.getpid()}"
session_b = f"test-mwc-b-{os.getpid()}"

subprocess.run([str(script_path), "register", "--id", session_a], check=True, capture_output=True)
subprocess.run([str(script_path), "register", "--id", session_b], check=True, capture_output=True)
subprocess.run([str(script_path), "enable-mwc", "--id", session_a], check=True, capture_output=True)

try:
    # Session A has MWC enabled -> allowed
    env_a = dict(os.environ, AI_SESSION_ID=session_a)
    v_a = verdict("gh pr merge 411 --squash", env=env_a)
    wrong += (v_a != "allow")
    print(f"  {v_a:<6} active MWC grant for session A")

    # Session B does NOT have MWC enabled -> blocked (cross-session isolation)
    env_b = dict(os.environ, AI_SESSION_ID=session_b)
    v_b = verdict("gh pr merge 411 --squash", env=env_b)
    wrong += (v_b != "BLOCK")
    print(f"  {v_b:<6} cross-session isolation for session B")
finally:
    subprocess.run([str(script_path), "release", "--id", session_a], check=True, capture_output=True)
    subprocess.run([str(script_path), "release", "--id", session_b], check=True, capture_output=True)

total = len(BLOCK) + len(ALLOW) + 2
print(f"\n{total - wrong}/{total} correct" + ("" if wrong == 0 else f"  ({wrong} WRONG)"))
sys.exit(1 if wrong else 0)
