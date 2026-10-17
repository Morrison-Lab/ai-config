"""Test the remind-generalize-maintainer-pr-comment hook.

Feeds UserPromptSubmit payloads. The hook must print a reminder for a GitHub
comment or review event authored by the maintainer, print nothing otherwise,
fire once per distinct event, and never block.

Run:  python3 hooks/test-remind-generalize-maintainer-pr-comment.py hooks/remind-generalize-maintainer-pr-comment.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

if len(sys.argv) < 2 or not os.path.isfile(sys.argv[1]):
    sys.exit(f"Usage: python3 {sys.argv[0]} <path-to-hook>")
HOOK = sys.argv[1]


def event(kind, login, body="Define this directly.", source="github"):
    data = json.dumps({"comment": {"user": {"login": login}, "body": body}})
    return (f'<wake reason="external-event"><event source="{source}" kind="{kind}" '
            f'trust="relay">{data}</event></wake>')


def run(prompt, twice=False, env=None):
    sentinel = tempfile.mkdtemp()
    outs = []
    try:
        for _ in range(2 if twice else 1):
            p = subprocess.run([sys.executable, HOOK], input=json.dumps({"prompt": prompt}),
                               capture_output=True, text=True,
                               env=dict(os.environ, TMPDIR=sentinel, **(env or {})))
            if p.returncode != 0:
                sys.exit(f"FATAL: hook exited {p.returncode}\n{p.stderr.strip()}")
            if '"decision"' in p.stdout:
                sys.exit(f"FATAL: block-shaped output\n{p.stdout}")
            outs.append("REMIND" if p.stdout.strip() else "silent")
    finally:
        shutil.rmtree(sentinel, ignore_errors=True)
    return outs if twice else outs[0]


CASES = [
    (event("review_comment", "d-morrison"), "REMIND", "maintainer review comment"),
    (event("issue_comment", "d-morrison"), "REMIND", "maintainer issue comment"),
    (event("pull_request_review", "d-morrison"), "REMIND", "maintainer review"),
    (event("review_comment", "someone-else"), "silent", "other author"),
    (event("check_run", "d-morrison"), "silent", "not a comment kind"),
    (event("review_comment", "d-morrison", source="slack"), "silent", "not a github event"),
    ("Please fix the failing test in foo.py.", "silent", "plain prompt"),
    ("d-morrison said hello in chat", "silent", "name without an event"),
]
bad = 0
for prompt, want, label in CASES:
    got = run(prompt)
    if got != want:
        bad += 1
        print(f"FAIL {label}: want {want}, got {got}")
twice = run(event("review_comment", "d-morrison"), twice=True)
if twice != ["REMIND", "silent"]:
    bad += 1
    print(f"FAIL fires once per event: {twice}")
got = run(event("review_comment", "ezra-m"), env={"MAINTAINER_LOGINS": "ezra-m"})
if got != "REMIND":
    bad += 1
    print(f"FAIL MAINTAINER_LOGINS override: {got}")
if run("{not json") != "silent":
    bad += 1
    print("FAIL malformed payload must be silent")
total = len(CASES) + 3
print(f"{total - bad}/{total} passed")
sys.exit(1 if bad else 0)
