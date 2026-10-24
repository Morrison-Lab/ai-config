#!/usr/bin/env python3
"""Test grant-personal-permissions.py: allow only Skill(mwc) and one bare merge.

Run:  python3 hooks/test-grant-personal-permissions.py hooks/grant-personal-permissions.py
"""
import json
import subprocess
import sys

HOOK = sys.argv[1]
passes = failures = 0


def run_raw(stdin_text):
    res = subprocess.run([sys.executable, HOOK], input=stdin_text,
                         capture_output=True, encoding="utf-8")
    return res.returncode, res.stdout


def run(payload):
    rc, stdout = run_raw(json.dumps(payload))
    return rc, (json.loads(stdout) if stdout.strip() else {}), stdout


def check(name, cond):
    global passes, failures
    passes += cond
    failures += (not cond)
    print(("PASS: " if cond else "FAIL: ") + name)


def decision(out):
    return (out.get("hookSpecificOutput") or {}).get("permissionDecision")


def bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def skill(name):
    return {"tool_name": "Skill", "tool_input": {"skill": name}}


ALLOW = [
    ("Skill mwc", skill("mwc")),
    ("Skill ai-config:mwc", skill("ai-config:mwc")),
    ("bare gh pr merge", bash("gh pr merge 123 --squash")),
    ("bare glab mr merge", bash("glab mr merge 45")),
    ("ALLOW_MERGE=1 prefix", bash("ALLOW_MERGE=1 gh pr merge 123 --squash")),
    ("-R repo flag", bash("gh pr merge 123 -R Morrison-Lab/ai-config --squash")),
    ("quoted subject", bash('gh pr merge 123 --squash --subject "Fix the thing"')),
    # Flags and targets are left to no-unauthorized-merge.py and settings rules.
    ("cross-repo --repo", bash("gh pr merge 5 --repo other/repo --squash")),
    ("--admin", bash("gh pr merge 5 --admin")),
]
for name, payload in ALLOW:
    rc, out, _ = run(payload)
    check(f"allows: {name}", rc == 0 and decision(out) == "allow"
          and "ai-config#4374" in out["hookSpecificOutput"]["permissionDecisionReason"])

SILENT = [
    ("other skill", skill("ardi")),
    ("mwc-extra", skill("mwc-extra")),
    ("other:mwc", skill("other:mwc")),
    ("gh pr view", bash("gh pr view 123")),
    ("gh pr mergeable", bash("gh pr mergeable 123")),
    ("&& chain", bash("gh pr merge 123 && rm -rf x")),
    ("; chain", bash("gh pr merge 123; echo hi")),
    ("| pipe", bash("gh pr merge 123 | tee log")),
    ("> redirect", bash("gh pr merge 123 > out.txt")),
    ("$(...) substitution", bash("gh pr merge $(echo 123)")),
    ("backticks", bash("gh pr merge `echo 123`")),
    ("$N variable", bash("gh pr merge $N")),
    ("second line", bash("gh pr merge 123\nrm -rf x")),
    ("trailing &", bash("gh pr merge 123 &")),
    ("quoted 'a; b'", bash("gh pr merge 123 --subject 'a; b'")),
    ("quoted ( in subject", bash('gh pr merge 123 --subject "Fix (x)"')),
    ("PATH= prefix", bash("PATH=/tmp gh pr merge 123")),
    ("GH_HOST= prefix", bash("GH_HOST=evil.example gh pr merge 123")),
    ("env wrapper", bash("env gh pr merge 123")),
    ("sudo wrapper", bash("sudo gh pr merge 123")),
    ("echo wrapper", bash("echo gh pr merge 123")),
    ("unbalanced quote", bash('gh pr merge 123 --subject "oops')),
    ("empty command", bash("")),
    ("non-string command", {"tool_name": "Bash", "tool_input": {"command": ["gh", "pr", "merge"]}}),
    ("PowerShell tool", {"tool_name": "PowerShell", "tool_input": {"command": "gh pr merge 123"}}),
    ("MCP merge tool", {"tool_name": "mcp__github__merge_pull_request",
                        "tool_input": {"owner": "o", "repo": "r", "pullNumber": 1}}),
    ("non-dict tool_input", {"tool_name": "Skill", "tool_input": "mwc"}),
]
for name, payload in SILENT:
    rc, out, stdout = run(payload)
    check(f"no decision: {name}", rc == 0 and stdout.strip() == "")

rc, stdout = run_raw(json.dumps({"tool_name": "Read", "tool_input": {"file_path": "/x"}}))
check("unrelated input prints nothing", rc == 0 and stdout == "")

rc, stdout = run_raw("not json")
check("invalid JSON exits 0 and prints nothing", rc == 0 and stdout == "")

res = subprocess.run([sys.executable, HOOK, "--dry-run", "gh pr merge 1"],
                     capture_output=True, encoding="utf-8")
check("--dry-run with a bare command shows the allow",
      decision(json.loads(res.stdout)) == "allow")

res = subprocess.run([sys.executable, HOOK, "--dry-run", json.dumps(skill("ardi"))],
                     capture_output=True, encoding="utf-8")
check("--dry-run prints the empty PreToolUse shape when silent",
      json.loads(res.stdout) == {"hookSpecificOutput": {"hookEventName": "PreToolUse"}})

res = subprocess.run([sys.executable, HOOK, "--simulate", "gh pr merge 1"],
                     input="", capture_output=True, encoding="utf-8")
check("--simulate is not a dry-run flag", res.returncode == 0 and res.stdout == "")

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
