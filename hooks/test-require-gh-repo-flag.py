"""Test the require-gh-repo-flag guard.

Must live in a file rather than a Bash heredoc: the guard inspects the Bash
command text, so any inline test containing its trigger strings blocks itself.
That self-shadowing is worth knowing about -- writing docs or tests that quote
a gated command has to go through a non-Bash tool.
"""
import json
import subprocess
import sys

HOOK = sys.argv[1]

# assembled so the literal trigger never appears as one token in this file's
# own text either -- belt and braces if this is ever catted from a shell
G = "gh "

BLOCK = [
    (G + "secret set CLAUDE_CODE_OAUTH_TOKEN", "the real incident: bare secret set"),
    ("cd /tmp && " + G + "secret set FOO", "compound: cd && gh secret set"),
    (G + "pr merge 25 --squash", "pr merge"),
    ("GH_TOKEN=x " + G + "run rerun --job 1", "leading env assignment"),
    ('GITHUB_TOKEN="my token" ' + G + "secret set FOO",
     "double-quoted env value containing a space"),
    ("GITHUB_TOKEN='my token' " + G + "secret set FOO",
     "single-quoted env value containing a space"),
    (G + "api repos/{owner}/{repo}/x -X POST", "api with cwd-resolved placeholders"),
    (G + "repo delete something", "repo delete"),
]

ALLOW = [
    (G + "secret set FOO -R a/b", "explicit -R"),
    (G + "pr merge 25 --repo a/b", "explicit --repo"),
    (G + "pr view 25 --json state", "read-only"),
    (G + "run list -R a/b --limit 5", "read-only with -R"),
    (G + "pr comment 25 --body-file x.md", "deliberately ungated (low harm, high frequency)"),
    (G + "api repos/a/b/actions/runs/1", "api with an explicit path"),
    ("printf '%s' '{\"c\":\"" + G + "secret set FOO\"}' | python3 h.py",
     "FALSE POSITIVE FIXED: trigger inside a quoted payload"),
    ("echo 'run: " + G + "pr merge 1' >> notes.md", "documenting the command"),
    ("git status --short", "not a gh command"),
]


import os

if not os.path.isfile(HOOK):
    sys.exit(f"FATAL: hook not found at {HOOK} -- a missing file would otherwise "
             "read as 'allow' on every case and print a perfect pass")


def verdict(cmd):
    p = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}}),
        capture_output=True, text=True,
    )
    # a crashed hook must NOT read as 'allow' -- that is the failure mode where
    # the pass path and the broken path print the same thing
    if p.returncode != 0:
        sys.exit(f"FATAL: hook exited {p.returncode} on {cmd!r}\n{p.stderr.strip()}")
    return "BLOCK" if '"permissionDecision": "deny"' in p.stdout else "allow"


wrong = 0
print("should BLOCK:")
for cmd, desc in BLOCK:
    v = verdict(cmd)
    wrong += v != "BLOCK"
    print(f"  {v:<6} {desc}")
print("\nshould ALLOW:")
for cmd, desc in ALLOW:
    v = verdict(cmd)
    wrong += v != "allow"
    print(f"  {v:<6} {desc}")

total = len(BLOCK) + len(ALLOW)
print(f"\n{total - wrong}/{total} correct" + ("" if wrong == 0 else f"  ({wrong} WRONG)"))
sys.exit(1 if wrong else 0)
