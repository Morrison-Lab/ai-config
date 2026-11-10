#!/usr/bin/env python3
"""Tests for hooks/no-patch-comment-id.py.

Run: python3 hooks/test-no-patch-comment-id.py [hooks/no-patch-comment-id.py]
"""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "no-patch-comment-id.py")

PULL = "repos/Morrison-Lab/ai-config/pulls/comments/123456"
ISSUE = "repos/Morrison-Lab/ai-config/issues/comments/123456"


def run(command, tool="Bash"):
    payload = {"tool_name": tool, "tool_input": {"command": command}}
    r = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return "deny" in r.stdout


# (name, command, should_deny)
CASES = [
    ("-X PATCH on a review comment", f"gh api -X PATCH {PULL} -F body=@f", True),
    ("--method PATCH on a review comment", f"gh api --method PATCH {PULL} -F body=@f", True),
    ("--method=PATCH form", f"gh api --method=PATCH {PULL} -f body=x", True),
    ("-XPATCH glued form", f"gh api -XPATCH {PULL} -f body=x", True),
    ("lowercase method", f"gh api -X patch {PULL} -f body=x", True),
    ("issue-comment route", f"gh api -X PATCH {ISSUE} -f body=x", True),
    ("leading slash path", "gh api -X PATCH /repos/o/r/pulls/comments/9 -f body=x", True),
    ("method after the path", f"gh api {PULL} -X PATCH -f body=x", True),
    ("second command in a chain", f"cd /tmp && gh api -X PATCH {PULL} -f body=x", True),
    ("other env var prefix does not clear", f"FOO=1 gh api -X PATCH {PULL} -f body=x", True),
    ("override prefix clears it", f"ALLOW_COMMENT_PATCH=1 gh api -X PATCH {PULL} -f body=x", False),
    ("POST to the replies route", "gh api -X POST repos/o/r/pulls/7/comments/9/replies -F body=@f", False),
    ("GET on a comment id", f"gh api {PULL}", False),
    ("PATCH on the PR itself (draft flag)", "gh api -X PATCH repos/o/r/pulls/1038 -F draft=false", False),
    ("PATCH on an issue", "gh api -X PATCH repos/o/r/issues/12 -f state=closed", False),
    ("commit message quoting the command", f'git commit -m "do not gh api -X PATCH {PULL}"', False),
    ("echo quoting the command", f"echo 'gh api -X PATCH {PULL}'", False),
    ("not gh api", f"curl -X PATCH https://api.github.com/{PULL}", False),
    ("other command with the same flags", f"curl --silent -X PATCH {PULL}", False),
    ("gh but not the api subcommand", f"gh pr -X PATCH {PULL}", False),
    ("unbalanced quote fails open", "gh api -X PATCH 'repos/o/r/pulls/comments/1", False),
    ("empty command", "", False),
]


def main() -> int:
    bad = 0
    for name, command, want in CASES:
        got = run(command)
        ok = got == want
        bad += not ok
        print(("ok   " if ok else "FAIL ") + name)
    ok = not run(f"gh api -X PATCH {PULL}", tool="Read")
    bad += not ok
    print(("ok   " if ok else "FAIL ") + "non-Bash tool ignored")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
