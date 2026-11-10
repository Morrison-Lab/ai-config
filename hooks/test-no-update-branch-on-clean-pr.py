#!/usr/bin/env python3
"""Tests for hooks/no-update-branch-on-clean-pr.py.

Run: python3 hooks/test-no-update-branch-on-clean-pr.py [hooks/no-update-branch-on-clean-pr.py]
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "no-update-branch-on-clean-pr.py")
TOOL = "mcp__github__update_pull_request_branch"
CLEAN47 = "Morrison-Lab/ids#47 is FULLY CLEAN on HEAD 98ed862a! [stale-base rule]"
OLD47 = "Morrison-Lab/ids#47 is FULLY CLEAN on HEAD 98ed862a!"
HDR47 = "Checking ARDI / fully-clean status for Morrison-Lab/ids#47..."
HDR99 = "Checking ARDI / fully-clean status for Morrison-Lab/other#99..."
DRIFT = "main gained 3 commit(s) since this head's merge base, including changes to .github/workflows/x.yml."

# (name, tool, owner, repo, number, transcript text or None for a missing file, should_deny)
CASES = [
    ("clean PR is denied", TOOL, "Morrison-Lab", "ids", 47, CLEAN47, True),
    ("repo match ignores case", TOOL, "morrison-lab", "ids", 47, CLEAN47, True),
    ("other PR number untouched", TOOL, "Morrison-Lab", "ids", 48, CLEAN47, False),
    ("other repo untouched", TOOL, "Morrison-Lab", "lds", 47, CLEAN47, False),
    ("no clean line untouched", TOOL, "Morrison-Lab", "ids", 47, "just chatting", False),
    ("later base-drift report for this PR lifts the denial", TOOL, "Morrison-Lab", "ids", 47,
     CLEAN47 + "\n" + HDR47 + "\n" + DRIFT, False),
    ("earlier base-drift report does not lift it", TOOL, "Morrison-Lab", "ids", 47,
     HDR47 + "\n" + DRIFT + "\n" + CLEAN47, True),
    ("a drift report under another PR's header does not lift it", TOOL, "Morrison-Lab", "ids", 47,
     CLEAN47 + "\n" + HDR99 + "\n" + DRIFT, True),
    ("a drift report with no checker header does not lift it", TOOL, "Morrison-Lab", "ids", 47,
     CLEAN47 + "\n" + DRIFT, True),
    ("a drift-like sentence under the PR's earlier clean-run header does not lift it",
     TOOL, "Morrison-Lab", "ids", 47,
     HDR47 + "\n" + CLEAN47 + "\nUnrelated: " + DRIFT, True),
    ("drift under this PR's header after another PR's still lifts it", TOOL, "Morrison-Lab", "ids", 47,
     CLEAN47 + "\n" + HDR99 + "\n" + HDR47 + "\n" + DRIFT, False),
    ("an old checker line without the stale-base marker is not trusted", TOOL, "Morrison-Lab", "ids", 47, OLD47, False),
    ("other tool ignored", "mcp__github__merge_pull_request", "Morrison-Lab", "ids", 47, CLEAN47, False),
    ("unreadable transcript fails open", TOOL, "Morrison-Lab", "ids", 47, None, False),
]


def run(tool, owner, repo, num, path):
    payload = {"tool_name": tool,
               "tool_input": {"owner": owner, "repo": repo, "pullNumber": num},
               "transcript_path": path}
    r = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return "deny" in r.stdout


def main() -> int:
    bad = 0
    for name, tool, owner, repo, num, text, want in CASES:
        if text is None:
            path = "/nonexistent/transcript.jsonl"
        else:
            f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
            f.write(text)
            f.close()
            path = f.name
        got = run(tool, owner, repo, num, path)
        ok = got == want
        bad += not ok
        print(("ok   " if ok else "FAIL ") + name)
        if text is not None:
            os.unlink(path)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
