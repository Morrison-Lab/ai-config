#!/usr/bin/env python3
"""Tests for hooks/no-tight-github-polling.py (ai-config#5970).

Run: python3 hooks/test-no-tight-github-polling.py [hooks/no-tight-github-polling.py]
"""
import json
import os
import subprocess
import sys
import tempfile
import uuid

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "no-tight-github-polling.py")
TMP = tempfile.mkdtemp(prefix="test-no-tight-github-polling-")

CASES = [  # (command, denied)
    ("gh pr checks 12 --watch", True),
    ("gh pr checks 12 --watch -R a/b --interval=30", True),
    ("gh pr checks 12 --watch --interval 120", False),
    ("gh run watch 99 -i60", True),
    ("gh run watch 99 --interval 300", False),
    ('echo "gh pr checks 12 --watch"', False),
    ("timeout 600 gh run watch 99", True),
    ("watch -n 5 gh pr checks 3", True),
    ("watch gh api repos/a/b/pulls/3", True),
    ("watch -n 1 ls", False),
    ("watch -n 300 gh pr checks 3", False),
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
    # Each loop is judged on its own body (agy review of #5974).
    ("while pgrep -x pytest; do sleep 5; done; gh pr checks 5", False),
    ("for x in 1 2; do echo x; done; while true; do gh pr checks 5; sleep 5; done", True),
    ("sleep 120; while true; do gh pr checks 5; sleep 5; done", True),
    ("while true; do if a; then sleep 120; else sleep 1; fi; gh pr checks 5; done", True),
    ("for i in {1..30}; do gh api repos/a/b/pulls/1; sleep 5; done", True),
    ("watch -n 5 'gh pr checks 3'", True),
    ('while true; do bash -c "gh pr checks 5"; sleep 5; done', True),
    ("sudo -u me gh run watch 99", True),
    ("cat <<'EOF'\nwhile true; do gh pr checks 5; sleep 1; done\nEOF", False),
    # agy review of #5976.
    ('while true; do for x in a b; do gh pr checks "$x"; sleep "$d"; done; done', False),
    ("watch -n 5 'date; gh pr checks 3'", True),
]


def call(tool, tool_input, session=None, env_extra=None):
    """Whether the hook denies; each call has a fresh session unless one is given."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("AI_CONFIG_")}
    env.update(TMPDIR=TMP, **(env_extra or {}))
    payload = {"tool_name": tool, "tool_input": tool_input,
               "session_id": session or str(uuid.uuid4())}
    proc = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                          capture_output=True, text=True, env=env, timeout=30)
    assert proc.returncode == 0 and not proc.stderr, proc.stderr
    return bool(proc.stdout.strip())


def denied(tool, command, env_extra=None, session=None):
    return call(tool, {"command": command}, session, env_extra)


checks = [(f"Bash {c!r}", denied("Bash", c), want) for c, want in CASES]
checks += [
    ("Monitor is gated too", denied("Monitor", "gh run watch 7"), True),
    ("other tools pass", call("Read", {"file_path": "x"}), False),
    ("floor is configurable",
     denied("Bash", "gh pr checks 1 --watch --interval 30", {"AI_CONFIG_GH_POLL_FLOOR": "20"}),
     False),
    ("kill switch", denied("Bash", "gh run watch 7", {"AI_CONFIG_NO_GITHUB_POLL_GUARD": "1"}),
     False),
]

# Repeated identical reads: in order, since each session keeps a log.
T = "mcp__github__pull_request_read"
runs = {"method": "get_check_runs", "owner": "a", "repo": "b", "pullNumber": 3}
comments = dict(runs, method="get_comments")
comment = {"owner": "a", "repo": "b", "issue_number": 3, "body": "x"}
ann = "gh api repos/a/b/check-runs/123/annotations"
batch = "python3 scripts/batch-read-annotations.py --repo a/b --sha abc"
post = "gh api repos/a/b/issues/3/comments -f body=x"
s1, s2, s3, s4 = (str(uuid.uuid4()) for _ in range(4))
no_cooldown = {"AI_CONFIG_GH_REPEAT_COOLDOWN": "0"}
checks += [
    ("first MCP read", call(T, runs, s1), False),
    ("identical MCP read repeated", call(T, runs, s1), True),
    ("other arguments pass", call(T, comments, s1), False),
    ("another session passes", call(T, runs), False),
    ("cooldown 0 passes", call(T, runs, s1, no_cooldown), False),
    ("read before a write", call(T, comments, s2), False),
    ("MCP write passes", call("mcp__github__add_issue_comment", comment, s2), False),
    ("read after a write passes", call(T, comments, s2), False),
    ("read again with no write", call(T, comments, s2), True),
    ("first annotation read", denied("Bash", ann, session=s3), False),
    ("annotations keep the long cooldown", denied("Bash", ann, no_cooldown, s3), True),
    ("override passes", denied("Bash", "ALLOW_REPEAT_GITHUB_READ=1 " + ann, session=s3), False),
    ("gh pr view first", denied("Bash", "gh pr view 3 -R a/b", session=s3), False),
    ("gh pr view repeated", denied("Bash", "gh pr view 3 -R a/b", session=s3), True),
    ("git push passes", denied("Bash", "git push -u origin x", session=s3), False),
    ("gh pr view after a push", denied("Bash", "gh pr view 3 -R a/b", session=s3), False),
    ("a POST is a write", denied("Bash", post, session=s3), False),
    ("a repeated POST is still a write", denied("Bash", post, session=s3), False),
    ("batch annotations first", denied("Bash", batch, session=s4), False),
    ("batch annotations repeated", denied("Bash", batch, session=s4), True),
    ("GET search repeated",
     [denied("Bash", "gh api -X GET search/issues -f q=x", session=s4) for _ in "ab"][1], True),
    ("non-GitHub Bash passes", denied("Bash", "ls -la", session=s4), False),
    ("rate_limit repeated",
     [denied("Bash", "gh api rate_limit", session=s4) for _ in "ab"][1], False),
    ("override reaches a bash -c body",
     [denied("Bash", 'ALLOW_REPEAT_GITHUB_READ=1 bash -c "gh pr view 9 -R a/b"', session=s4)
      for _ in "ab"][1], False),
    ("gh pr view 8 first", denied("Bash", "gh pr view 8 -R a/b", session=s4), False),
    ("-XDELETE is a write", denied("Bash", "gh api -XDELETE repos/a/b/x", session=s4), False),
    ("read after -XDELETE passes", denied("Bash", "gh api rate_limit; gh pr view 8 -R a/b",
                                          session=s4), False),
    ("-fbody=x is a write",
     [denied("Bash", "gh pr view 7 -R a/b", session=s4),
      denied("Bash", "gh api -fbody=x repos/a/b/issues/3/comments", session=s4),
      denied("Bash", "gh pr view 7 -R a/b", session=s4)][2], False),
]
fails = [f"{label}: expected {'deny' if want else 'pass'}"
         for label, got, want in checks if got != want]
if fails:
    print("\n".join(fails))
    print(f"FAIL: {len(fails)} of {len(checks)}")
    sys.exit(1)
print(f"PASS: {len(checks)} cases")
