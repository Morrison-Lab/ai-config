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
DIRTY = "GitHub reports mergeable_state 'dirty' (ai-config#5143)"
BEHIND = "GitHub holds this PR as 'behind' and no missing required check explains it"
CONTENT_NOTE = "NOTE: head is 4 commit(s) behind main; none of them changed .github/workflows/ (ai-config#2982)"

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
    ("a later conflict report lifts it", TOOL, "Morrison-Lab", "ids", 47,
     CLEAN47 + "\n" + HDR47 + "\n" + DIRTY, False),
    ("a later up-to-date-required report lifts it", TOOL, "Morrison-Lab", "ids", 47,
     CLEAN47 + "\n" + HDR47 + "\n" + BEHIND, False),
    ("a later content-only drift NOTE does not lift it", TOOL, "Morrison-Lab", "ids", 47,
     CLEAN47 + "\n" + HDR47 + "\n" + CONTENT_NOTE, True),
]

# (name, Bash command, transcript text, should_deny).
API47 = "gh api -X PUT repos/Morrison-Lab/ids/pulls/47/update-branch"
BASH_CASES = [
    ("gh api update-branch path is denied", API47 + " -f expected_head_sha=abc", CLEAN47, True),
    ("gh api update-branch on another PR untouched",
     "gh api -X PUT repos/Morrison-Lab/ids/pulls/48/update-branch", CLEAN47, False),
    ("gh api on another repo untouched",
     "gh api -X PUT repos/Morrison-Lab/other/pulls/47/update-branch", CLEAN47, False),
    ("gh api path built from variables fails open",
     'gh api -X PUT "repos/$REPO/pulls/$N/update-branch"', CLEAN47, False),
    ("a quoted literal path still counts",
     'gh api -X PUT "repos/Morrison-Lab/ids/pulls/47/update-branch"', CLEAN47, True),
    ("gh pr update-branch is not covered yet", "gh pr update-branch 47 -R Morrison-Lab/ids",
     CLEAN47, False),
    ("after && it still counts", "git fetch && " + API47, CLEAN47, True),
    ("the second update in a compound command is checked",
     "gh api -X PUT repos/Morrison-Lab/ids/pulls/48/update-branch; " + API47, CLEAN47, True),
    ("a GH_REPO prefix does not hide it", "GH_REPO=Morrison-Lab/x " + API47, CLEAN47, True),
    ("an env wrapper still counts", "env " + API47, CLEAN47, True),
    ("a nice wrapper still counts", "nice " + API47, CLEAN47, True),
    ("a time wrapper still counts", "time " + API47, CLEAN47, True),
    ("an exec wrapper still counts", "exec " + API47, CLEAN47, True),
    ("inside if/then still counts", "if true; then " + API47 + "; fi", CLEAN47, True),
    ("inside x=$( ) still counts", "x=$(" + API47 + ")", CLEAN47, True),
    ("later drift report lifts the Bash denial", API47, CLEAN47 + "\n" + HDR47 + "\n" + DRIFT, False),
    ("unrelated Bash command untouched", "gh pr view 47 -R Morrison-Lab/ids", CLEAN47, False),
    ("quoted in a comment body is not denied",
     'gh issue comment 5 --body "do not run ' + API47 + '"', CLEAN47, False),
    ("then inside a quoted body is not denied",
     'gh issue comment 5 --body "then ' + API47 + '"', CLEAN47, False),
    ("do inside an echoed string is not denied", 'echo "do ' + API47 + '"', CLEAN47, False),
    ("a parenthesised mention in a string is not denied", 'echo "(' + API47 + ')"', CLEAN47, False),
    ("a semicolon inside a single-quoted body is not denied",
     "gh issue comment 5 --body 'ok; " + API47 + "'", CLEAN47, False),
    ("a quoted multi-line body is not denied",
     'gh issue comment 5 --body "line one\n' + API47 + '"', CLEAN47, False),
    ("the do of to-do is not a keyword", "to-do " + API47, CLEAN47, False),
    ("a path inside another gh api call's quoted body is not denied",
     'gh api repos/Morrison-Lab/ids/issues/5/comments -f body="do not run ' + API47 + '"',
     CLEAN47, False),
    ("a quoted path with a leading slash still counts",
     'gh api -X PUT "/repos/Morrison-Lab/ids/pulls/47/update-branch"', CLEAN47, True),
    ("a backslash-newline continuation still counts",
     "gh api -X PUT \\\n  repos/Morrison-Lab/ids/pulls/47/update-branch", CLEAN47, True),
    ("a mention inside a # comment is not denied",
     "git status # then " + API47, CLEAN47, False),
    ("a # inside a word is not a comment", "x=a#b; " + API47, CLEAN47, True),
]


def run(tool, owner, repo, num, path, command=None):
    tool_input = ({"command": command} if command is not None
                  else {"owner": owner, "repo": repo, "pullNumber": num})
    payload = {"tool_name": tool, "tool_input": tool_input, "transcript_path": path}
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
    for name, command, text, want in BASH_CASES:
        f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
        f.write(text)
        f.close()
        got = run("Bash", None, None, None, f.name, command=command)
        ok = got == want
        bad += not ok
        print(("ok   " if ok else "FAIL ") + name)
        os.unlink(f.name)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
