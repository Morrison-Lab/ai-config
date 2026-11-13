#!/usr/bin/env python3
"""Tests for hooks/prefer-mcp-over-bash-in-cloud.py (ai-config#5613).

Run: python3 hooks/test-prefer-mcp-over-bash-in-cloud.py [hooks/prefer-mcp-over-bash-in-cloud.py]
"""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "prefer-mcp-over-bash-in-cloud.py")

# (command, denied in a cloud session)
CASES = [
    ("gh pr view 12 -R Morrison-Lab/gha", True),
    ("gh pr merge 12 --squash", True),
    ("gh -R a/b issue list", True),
    ("FOO=1 gh issue create -R a/b --title x", True),
    ("sudo gh run list", True),
    ("git status && gh pr checks 5", True),
    ("gh workflow run x.yml", True),
    ("gh release list", True),
    ("gh api repos/a/b/pulls/3", True),
    ("gh api -X GET repos/a/b/issues", True),
    ("gh api -X GET search/code -f q=foo --paginate", False),
    ("gh api search/issues -f q=bar", False),
    ("curl -s https://api.github.com/repos/a/b", True),
    ("curl -s https://api.github.com/search/code?q=x", False),
    ("curl -s https://example.com/api", False),
    ("gh auth status", False),
    ("gh search code foo", False),
    ("gh secret list -R a/b", False),
    ("git push -u origin x", False),
    ('echo "gh pr view 3"', False),
    ("grep -n 'gh pr view' file.md", False),
    ("cat <<'EOF'\ngh pr view 3\nEOF", False),
    ("ALLOW_BASH_OVER_MCP=1 gh api repos/a/b/commits/abc", False),
    ("gh api repos/a/b/check-runs/1/annotations", False),
    ("gh api graphql -f query=x", False),
    ("gh pr checkout 12", False),
    ("gh run watch 99", False),
    ("gh release create v1.0.0", False),
    ("gh --repo=a/b pr view 3", True),
    ("gh -Ra/b issue list", True),
    ('bash -c "gh pr view 3"', True),
    ("gh api search/../repos/a/b/pulls", True),
    ("curl https://api.github.com/search/../repos/a/b", True),
    ("gh pr view 3 # ALLOW_BASH_OVER_MCP=1", True),
    ("echo ALLOW_BASH_OVER_MCP=1; gh pr view 3", True),
]


def run(command, remote="true"):
    env = dict(os.environ)
    env.pop("CLAUDE_CODE_REMOTE", None)
    if remote is not None:
        env["CLAUDE_CODE_REMOTE"] = remote
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True, env=env)
    return p.returncode, '"permissionDecision": "deny"' in p.stdout


def main():
    fails = 0
    for command, want in CASES:
        rc, denied = run(command)
        ok = rc == 0 and denied == want
        fails += 0 if ok else 1
        print(f"  {'ok' if ok else 'FAIL':<6} {'deny' if denied else 'allow':<6} {command!r}")
    extra = [
        ("silent outside a cloud session", run("gh pr view 3", remote=None), (0, False)),
        ("silent when CLAUDE_CODE_REMOTE is false", run("gh pr view 3", remote="false"), (0, False)),
    ]
    for desc, got, want in extra:
        ok = got == want
        fails += 0 if ok else 1
        print(f"  {'ok' if ok else 'FAIL':<6} {desc}")
    p = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True,
                       env=dict(os.environ, CLAUDE_CODE_REMOTE="true"))
    ok = p.returncode == 0 and not p.stdout
    fails += 0 if ok else 1
    print(f"  {'ok' if ok else 'FAIL':<6} fails open on garbage stdin")
    total = len(CASES) + len(extra) + 1
    print(f"\n{total - fails}/{total} correct")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
