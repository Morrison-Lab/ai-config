#!/usr/bin/env python3
"""Test no-field-unsafe-merge-runs.py: the docx skill's merge_runs.py runs only via the wrapper.

Run:  python3 hooks/test-no-field-unsafe-merge-runs.py hooks/no-field-unsafe-merge-runs.py
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


for cmd in ["python3 /mnt/skills/public/docx/scripts/merge_runs.py doc.docx",
            "cd /mnt/skills/public/docx/scripts && python merge_runs.py /tmp/u/",
            "python3.12 scripts/merge_runs.py a.docx -o b.docx",
            "PYTHONPATH=x python3 merge_runs.py a.docx",
            "uv run merge_runs.py a.docx", "./merge_runs.py a.docx",
            "timeout 60 python3 merge_runs.py a.docx",
            "python3 -c 'from merge_runs import merge_runs; merge_runs(\"u\")'"]:
    check(f"denies {cmd}", denied(bash(cmd)))

for cmd in ["python3 scripts/docx-merge-runs-field-safe.py doc.docx",
            "grep -c fldChar /mnt/skills/public/docx/scripts/merge_runs.py",
            "md5sum /mnt/skills/public/docx/scripts/merge_runs.py",
            "cat merge_runs.py", "git commit -m 'note merge_runs.py defect'",
            "python3 scripts/test_docx_merge_runs_field_safe.py",
            "ALLOW_FIELD_UNSAFE_MERGE_RUNS=1 python3 merge_runs.py pristine.docx"]:
    check(f"allows {cmd}", not denied(bash(cmd)))
check("ignores other tools",
      not denied({"tool_name": "Read", "tool_input": {"file_path": "merge_runs.py"}}))

print(f"{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
