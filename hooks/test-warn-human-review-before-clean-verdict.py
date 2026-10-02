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

PUSHED = '{"command": "git push -u origin b"}\n'
CLEAN = "### Verdict: Ready for merge\n"
OTHER = "### Verdict: Needs more work\n"
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
