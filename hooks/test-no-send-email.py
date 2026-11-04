#!/usr/bin/env python3
"""Test no-send-email.py: an agent never sends an email; drafting is fine.

Run:  python3 hooks/test-no-send-email.py hooks/no-send-email.py
"""
import json
import subprocess
import sys

HOOK = sys.argv[1]
passes = failures = 0


def denied(payload):
    res = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                         capture_output=True, encoding="utf-8")
    out = json.loads(res.stdout) if res.stdout.strip() else {}
    return res.returncode == 0 and \
        (out.get("hookSpecificOutput") or {}).get("permissionDecision") == "deny"


def check(name, cond):
    global passes, failures
    passes += cond
    failures += (not cond)
    print(("PASS: " if cond else "FAIL: ") + name)


def bash(cmd):
    return {"tool_name": "Bash", "tool_input": {"command": cmd}}


for cmd in ["echo hi | mail -s subj a@b.org", "sendmail -t < msg.txt",
            "sudo /usr/sbin/sendmail a@b.org", "cd x && mutt -s hi a@b.org",
            "git send-email --to a@b.org patch", "FOO=1 msmtp a@b.org",
            "curl --url smtps://smtp.x.org --mail-from a@b.org -T m.txt",
            "python3 -c 'import smtplib'"]:
    check(f"denies {cmd}", denied(bash(cmd)))
for name in ["mcp__claude_ai_Gmail__send_email", "mcp__gmail__send_draft",
             "mcp__Gmail__sendEmail", "mcp__outlook__reply_to_email"]:
    check(f"denies {name}", denied({"tool_name": name, "tool_input": {}}))

for cmd in ["git send-pack origin", "grep -r mail hooks", "echo mail",
            "ls mailbox", "git commit -m 'draft the email'"]:
    check(f"allows {cmd}", not denied(bash(cmd)))
for name in ["mcp__claude_ai_Gmail__create_draft", "mcp__gmail__search_threads",
             "mcp__github__add_issue_comment"]:
    check(f"allows {name}", not denied({"tool_name": name, "tool_input": {}}))

print(f"{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
