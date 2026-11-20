#!/usr/bin/env python3
"""Tests for hooks/no-tight-github-polling.py (ai-config#5970).

Run: python3 hooks/test-no-tight-github-polling.py [hooks/no-tight-github-polling.py]
"""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "no-tight-github-polling.py")

CASES = [  # (command, denied)
    ("gh pr checks 12 --watch", True),
    ("gh pr checks 12 --watch -R a/b --interval=30", True),
    ("gh pr checks 12 --watch --interval 120", False),
    ("gh run watch 99 -i60", True),
    ("timeout 600 gh run watch 99", True),
    ("watch -n 5 gh pr checks 3", True),
    ("watch gh api repos/a/b/pulls/3", True),
    ("watch -n 1 ls", False),
    ("while true; do gh pr checks 5; sleep 1m; done", True),
    ("while true; do gh pr checks 5; sleep 3m; done", False),
    ("until gh run view 1 --json status | grep -q completed; do sleep 5; done", True),
    ("for i in $(seq 1 30); do gh api repos/a/b/pulls/1 >/dev/null; sleep 30; done", True),
    ("for i in 1 2 3 4; do gh api repos/a/b/pulls/1 && break; sleep 5; done", False),
    ("for pr in $(cat prs.txt); do gh pr view $pr -R a/b; done", False),
    ("while true; do curl -s https://api.github.com/repos/a/b; sleep 20; done", True),
    ("while true; do curl -s https://example.com/x; sleep 2; done", False),
    ("while true; do python3 scripts/check-pr-fully-clean.py 5; sleep 30; done", True),
    ("while true; do gh pr checks 5; sleep \"$d\"; done", False),
    ('bash -c "while true; do gh pr checks 5; sleep 10; done"', True),
    ("ALLOW_GITHUB_POLL=1 gh pr checks 12 --watch", False),
    ("cat <<'EOF'\nwhile true; do gh pr checks 5; sleep 1; done\nEOF", False),
]


def denied(tool, command, env_extra=None):
    env = dict(os.environ)
    env.pop("AI_CONFIG_NO_GITHUB_POLL_GUARD", None)
    env.pop("AI_CONFIG_GH_POLL_FLOOR", None)
    env.update(env_extra or {})
    payload = {"tool_name": tool, "tool_input": {"command": command}}
    proc = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                          capture_output=True, text=True, env=env, timeout=30)
    assert proc.returncode == 0, proc.stderr
    return bool(proc.stdout.strip())


checks = [(f"Bash {c!r}", denied("Bash", c), want) for c, want in CASES]
checks += [
    ("Monitor is gated too", denied("Monitor", "gh run watch 7"), True),
    ("floor is configurable",
     denied("Bash", "gh run watch 1 -i 30", {"AI_CONFIG_GH_POLL_FLOOR": "20"}), False),
    ("kill switch", denied("Bash", "gh run watch 7", {"AI_CONFIG_NO_GITHUB_POLL_GUARD": "1"}),
     False),
]
fails = [f"{label}: expected {'deny' if want else 'pass'}"
         for label, got, want in checks if got != want]
if fails:
    print("\n".join(fails))
    print(f"FAIL: {len(fails)} of {len(checks)}")
    sys.exit(1)
print(f"PASS: {len(checks)} cases")
