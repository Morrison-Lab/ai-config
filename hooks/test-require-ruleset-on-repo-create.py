"""Test the require-ruleset-on-repo-create guard.

Run: python3 hooks/test-require-ruleset-on-repo-create.py hooks/require-ruleset-on-repo-create.py

The trigger is assembled from pieces so this file's own text never contains it
as one token (the guard inspects Bash command text).
"""
import json
import subprocess
import sys

HOOK = sys.argv[1]
C = "gh repo " + "create"
APPLY = "examples/branch-rulesets/apply-all.sh"

BLOCK = [
    (C + " Morrison-Lab/answer-space --public", "the incident: plain create"),
    (C + " Morrison-Lab/x --template Morrison-Lab/qwt --private", "template create"),
    ("cd /tmp && " + C + " Morrison-Lab/x", "create after cd"),
    ("GH_TOKEN=t " + C + " Morrison-Lab/x", "leading env assignment"),
    (C + " Morrison-Lab/x && " + APPLY + " Morrison-Lab/x", "applier without --apply (dry run)"),
    (C + " Morrison-Lab/x && " + APPLY + " --apply other", "applier names another repo"),
    (C + " Morrison-Lab/x && " + APPLY + " --apply", "applier names no repo"),
    (C + " Morrison-Lab/x && gh api repos/Morrison-Lab/x/rulesets", "ruleset READ is not a write"),
    (C + " Morrison-Lab/x && gh api -X POST repos/Morrison-Lab/y/rulesets --input r.json",
     "ruleset write to another repo"),
    (C, "create with no name (interactive)"),
    (C + " -d 'a desc' Morrison-Lab/x", "value flag before the name"),
]

ALLOW = [
    (C + " Morrison-Lab/x --public && " + APPLY + " --apply x", "applier by short name"),
    (C + " Morrison-Lab/x && " + APPLY + " --apply Morrison-Lab/x", "applier by full name"),
    (C + " Morrison-Lab/x && bash " + APPLY + " --apply x", "applier through bash"),
    (C + " Morrison-Lab/x --template Morrison-Lab/qwt --clone && cd x && "
     ".github/scripts/apply-rulesets.sh", "template's own applier"),
    (C + " Morrison-Lab/x && gh api -X POST repos/Morrison-Lab/x/rulesets --input r.json",
     "direct ruleset POST"),
    (C + " --help", "help is not a create"),
    ("echo '" + C + " Morrison-Lab/x'", "quoted in echo"),
    ("grep -n '" + C + "' notes.md", "quoted in grep"),
    ("gh repo view Morrison-Lab/x", "other gh repo subcommand"),
    ("ls", "unrelated"),
]


def run(payload):
    out = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                         capture_output=True, text=True, check=False)
    return '"deny"' in out.stdout


def bash(cmd):
    return {"tool_name": "Bash", "tool_input": {"command": cmd}}


fails = 0
for cmd, why in BLOCK:
    if not run(bash(cmd)):
        fails += 1
        print(f"FAIL (should block): {why}: {cmd}")
for cmd, why in ALLOW:
    if run(bash(cmd)):
        fails += 1
        print(f"FAIL (should allow): {why}: {cmd}")
if not run({"tool_name": "mcp__github__create_repository",
            "tool_input": {"name": "x", "organization": "Morrison-Lab"}}):
    fails += 1
    print("FAIL (should block): MCP create_repository")
if run({"tool_name": "mcp__github__get_me", "tool_input": {}}):
    fails += 1
    print("FAIL (should allow): unrelated MCP tool")

total = len(BLOCK) + len(ALLOW) + 2
print(f"{total - fails} of {total} passed")
sys.exit(1 if fails else 0)
