#!/usr/bin/env python3
"""Tests for hooks/warn-human-review-before-clean-verdict.py (ai-config#4247).

Run: python3 hooks/test-warn-human-review-before-clean-verdict.py [hook path]
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "warn-human-review-before-clean-verdict.py")

SHA = "a" * 40


def rec(**kw):
    return json.dumps(kw) + "\n"


def push(command="git push -u origin b"):
    return rec(type="assistant", message={"content": [
        {"type": "tool_use", "input": {"command": command}}]})


def text(body):
    return rec(type="user", message={"content": [
        {"type": "tool_result", "content": body}]})


PUSHED = push()
CLEAN = text("### Verdict: Ready for merge\n\nReviewed-Commit: " + SHA + "\n")
PAYLOAD = text('<!-- review-data: {"commit_sha": "' + SHA
               + '", "verdict": "CLEAN", "findings": []} -->')
OTHER = text("### Verdict: Needs more work\n\nReviewed-Commit: " + SHA + "\n")
QUOTED = text("Write `### Verdict: Ready for merge` only if nothing is left.")
NEGATED = text("The PR is not fully clean yet.")
MENTION = text("remember to git push after the review")
ADD = "gh pr edit 7 --add-reviewer d-morrison"
API = ("gh api repos/o/r/pulls/7/requested_reviewers -X POST "
       "-f 'reviewers[]=d-morrison'")

# (name, tool, tool_input, transcript text or None for no file, warns, who)
CASES = [
    ("add-reviewer, nothing clean", "Bash", {"command": ADD}, PUSHED, True, "d-morrison"),
    ("api request, nothing clean", "Bash", {"command": API}, PUSHED, True, "d-morrison"),
    ("mcp reviewers, nothing clean", "mcp__github__update_pull_request",
     {"reviewers": ["d-morrison"]}, PUSHED, True, "d-morrison"),
    ("not-clean verdict", "Bash", {"command": ADD}, PUSHED + OTHER, True, "d-morrison"),
    ("clean verdict after push", "Bash", {"command": ADD}, PUSHED + CLEAN, False, None),
    ("clean verdict before the last push", "Bash", {"command": ADD},
     CLEAN + PUSHED, True, "d-morrison"),
    ("escaped review-data payload counts", "Bash", {"command": ADD},
     PUSHED + PAYLOAD, False, None),
    ("quoted instruction is not a verdict", "Bash", {"command": ADD},
     PUSHED + QUOTED, True, "d-morrison"),
    ("not fully clean is not a verdict", "Bash", {"command": ADD},
     PUSHED + NEGATED, True, "d-morrison"),
    ("a mere mention of git push keeps the boundary", "Bash", {"command": ADD},
     PUSHED + CLEAN + MENTION, False, None),
    ("DELETE removes a reviewer", "Bash",
     {"command": "gh api -X DELETE repos/o/r/pulls/7/requested_reviewers "
                 "-f 'reviewers[]=d-morrison'"}, PUSHED, False, None),
    ("create_pull_request with reviewers", "mcp__github__create_pull_request",
     {"reviewers": ["d-morrison"]}, PUSHED, True, "d-morrison"),
    ("gh pr create --reviewer", "Bash",
     {"command": "gh pr create --title t --reviewer d-morrison"}, PUSHED, True, "d-morrison"),
    ("gh pr create -r", "Bash",
     {"command": "gh pr create -r d-morrison"}, PUSHED, True, "d-morrison"),
    ("gh pr create with no reviewer", "Bash",
     {"command": "gh pr create --title t"}, PUSHED, False, None),
    ("--add-reviewer=NAME form", "Bash",
     {"command": "gh pr edit 7 --add-reviewer=d-morrison"}, PUSHED, True, "d-morrison"),
    ("comma list names only the person", "Bash",
     {"command": "gh pr edit 7 --add-reviewer claude,d-morrison"}, PUSHED, True, "d-morrison"),
    ("DELETE then a real request in one line", "Bash",
     {"command": "gh api -X DELETE repos/o/r/pulls/7/requested_reviewers "
                 "-f 'reviewers[]=x'; " + ADD}, PUSHED, True, "d-morrison"),
    ("git -C dir push moves the boundary", "Bash", {"command": ADD},
     CLEAN + push("git -C /tmp/r push origin b"), True, "d-morrison"),
    ("MCP push moves the boundary", "Bash", {"command": ADD},
     CLEAN + rec(type="assistant", message={"content": [
         {"type": "tool_use", "name": "mcp__github__push_files", "input": {}}]}),
     True, "d-morrison"),
    ("raw non-JSON line is tolerated", "Bash", {"command": ADD},
     PUSHED + "plain text line\n" + CLEAN, False, None),
    ("verdict and commit in separate records", "Bash", {"command": ADD},
     PUSHED + text("### Verdict: Ready for merge") + text("Reviewed-Commit: " + SHA),
     True, "d-morrison"),
    ("push on a later line", "Bash", {"command": ADD},
     CLEAN + push("cd /tmp/r\ngit push origin b"), True, "d-morrison"),
    ("push after then", "Bash", {"command": ADD},
     CLEAN + push("if true; then git push origin b; fi"), True, "d-morrison"),
    ("push in a subshell", "Bash", {"command": ADD},
     CLEAN + push("(git push origin b)"), True, "d-morrison"),
    ("long option chain after git stays fast", "Bash", {"command": ADD},
     PUSHED + CLEAN + push("git " + "-a " * 200 + "foo"), False, None),
    ("text naming an MCP push tool is not a push", "Bash", {"command": ADD},
     PUSHED + CLEAN + text("hooks.json binds mcp__github__push_files"), False, None),
    ("multi-line body with a reviewer", "Bash",
     {"command": "gh pr create --title t --body \"line1\nline2; x\" "
                 "--reviewer d-morrison"}, PUSHED, True, "d-morrison"),
    ("a verdict the agent wrote itself", "Bash", {"command": ADD},
     PUSHED + rec(type="assistant", message={"content": [
         {"type": "text", "text": "### Verdict: Ready for merge\n"
                                  "Reviewed-Commit: " + SHA}]}),
     True, "d-morrison"),
    ("no push at all, clean verdict", "Bash", {"command": ADD}, CLEAN, False, None),
    ("bot reviewer", "Bash",
     {"command": "gh pr edit 7 --add-reviewer copilot-pull-request-reviewer[bot]"},
     PUSHED, False, None),
    ("claude reviewer", "mcp__github__update_pull_request",
     {"reviewers": ["claude"]}, PUSHED, False, None),
    ("mixed reviewers names only the person", "mcp__github__update_pull_request",
     {"reviewers": ["claude", "d-morrison"]}, PUSHED, True, "d-morrison"),
    ("unrelated command", "Bash", {"command": "gh pr view 7"}, PUSHED, False, None),
    ("gh api GET of the endpoint", "Bash",
     {"command": "gh api repos/o/r/pulls/7/requested_reviewers"}, PUSHED, False, None),
    ("no transcript file", "Bash", {"command": ADD}, None, False, None),
    ("other tool", "Read", {"file_path": "/x"}, PUSHED, False, None),
    ("update_pull_request without reviewers", "mcp__github__update_pull_request",
     {"title": "t"}, PUSHED, False, None),
]


def run(tool, tool_input, transcript):
    path = "/nonexistent/transcript.jsonl"
    handle = None
    if transcript is not None:
        handle = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
        handle.write(transcript)
        handle.close()
        path = handle.name
    event = {"tool_name": tool, "tool_input": tool_input, "transcript_path": path}
    try:
        proc = subprocess.run([sys.executable, HOOK], input=json.dumps(event),
                              capture_output=True, text=True)
    finally:
        if handle:
            os.unlink(handle.name)
    return proc.returncode, proc.stdout


def main():
    failures = 0
    for name, tool, tool_input, transcript, warns, who in CASES:
        code, out = run(tool, tool_input, transcript)
        ok = code == 0
        if warns:
            ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""
            ok = ok and f"({who})" in ctx
        else:
            ok = ok and out == ""
        if not ok:
            failures += 1
            print(f"FAIL {name}: code={code} out={out!r}")
    for bad in ("", "not json", "[]"):
        proc = subprocess.run([sys.executable, HOOK], input=bad,
                              capture_output=True, text=True)
        if proc.returncode != 0 or proc.stdout:
            failures += 1
            print(f"FAIL malformed input {bad!r}")
    print("ok" if not failures else f"{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
