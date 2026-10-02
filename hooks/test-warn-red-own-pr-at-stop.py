#!/usr/bin/env python3
"""Tests for hooks/warn-red-own-pr-at-stop.py.

Run: python3 hooks/test-warn-red-own-pr-at-stop.py [hook path]

The warning is a Stop hook's `systemMessage`, so every positive case reads that
key and checks it names the PR and the failing check.
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "warn-red-own-pr-at-stop.py")

_ids = iter(range(1, 10000))


def rec(**kw):
    return json.dumps(kw) + "\n"


def call(name, tool_input, result=""):
    """An assistant tool_use followed by its user tool_result."""
    ident = f"toolu_{next(_ids)}"
    return (
        rec(type="assistant", message={"content": [
            {"type": "tool_use", "id": ident, "name": name, "input": tool_input}]})
        + rec(type="user", message={"content": [
            {"type": "tool_result", "tool_use_id": ident, "content": result}]}))


def created(number):
    return call("mcp__github__create_pull_request", {"title": "t"},
                json.dumps({"number": number,
                            "url": f"https://github.com/o/r/pull/{number}"}))


def gh_created(number):
    return call("Bash", {"command": "gh pr create --title t"},
                f"https://github.com/o/r/pull/{number}\n")


def subscribed(number):
    return call("mcp__claude-code-remote__subscribe_pr_activity",
                {"owner": "o", "repo": "r", "pullNumber": number}, "subscribed")


def wake(check, conclusion, number, extra=None):
    run = {"name": check, "status": "completed", "conclusion": conclusion,
           "pull_requests": [{"number": number}]}
    run.update(extra or {})
    body = json.dumps({"event": "check_run", "action": "completed", "check_run": run})
    return rec(type="user", message={"content": [
        {"type": "text", "text": "<github-webhook-activity>" + body
                                 + "</github-webhook-activity>"}]})


def listing(number, runs):
    return call("mcp__github__pull_request_read",
                {"method": "get_check_runs", "owner": "o", "repo": "r",
                 "pullNumber": number},
                json.dumps({"total_count": len(runs), "check_runs": runs}))


def run_of(name, conclusion):
    return {"name": name, "status": "completed" if conclusion else "in_progress",
            "conclusion": conclusion}


def push(command="git push origin b"):
    return call("Bash", {"command": command}, "ok")


def branch_update(number):
    return call("mcp__github__update_pull_request_branch",
                {"owner": "o", "repo": "r", "pullNumber": number}, "ok")


def comment(number):
    return call("mcp__github__add_issue_comment",
                {"owner": "o", "repo": "r", "issue_number": number, "body": "b"}, "ok")


QUOTA = {"output": {"title": "Review skipped",
                    "summary": "Claude review did not finish: session limit reached"}}

# (name, transcript, expected PR numbers that warn, a check name that must appear)
CASES = [
    ("wake failure on an own PR", created(7) + wake("tests", "failure", 7), [7], "tests"),
    ("get_check_runs failure", created(7) + listing(7, [run_of("lint", "failure"),
                                                          run_of("tests", "success")]),
     [7], "lint"),
    ("gh pr create counts as own", gh_created(8) + wake("tests", "failure", 8), [8], "tests"),
    ("subscribe_pr_activity counts as own", subscribed(9) + wake("tests", "failure", 9),
     [9], "tests"),
    ("two own PRs, one red", created(7) + created(8) + wake("tests", "failure", 8),
     [8], "tests"),
    ("timed_out is a failure", created(7) + wake("tests", "timed_out", 7), [7], "tests"),
    ("review check failing for a fixable reason",
     created(7) + wake("review / claude-review", "failure", 7,
                       {"output": {"summary": "Verdict: Needs more work"}}),
     [7], "review / claude-review"),
    ("failure after the push is unacted", created(7) + push() + wake("tests", "failure", 7),
     [7], "tests"),
    ("comment on another PR is not acting", created(7) + created(8)
     + wake("tests", "failure", 7) + comment(8), [7], "tests"),
    ("comment before the failure is not acting",
     created(7) + comment(7) + wake("tests", "failure", 7), [7], "tests"),
    ("branch update on another PR is not acting", created(7) + wake("tests", "failure", 7)
     + branch_update(8), [7], "tests"),
    ("a different check going green leaves the red one",
     created(7) + wake("tests", "failure", 7) + wake("lint", "success", 7), [7], "tests"),
    ("failing listing after the push warns again",
     created(7) + listing(7, [run_of("tests", "failure")]) + push()
     + listing(7, [run_of("tests", "failure")]), [7], "tests"),
    ("git push as text in a commit message is not a push",
     created(7) + wake("tests", "failure", 7) + push("git commit -m 'fix git push bug'"),
     [7], "tests"),
    ("git commit with the word push is not a push",
     created(7) + wake("tests", "failure", 7) + push("git commit -m push"), [7], "tests"),
    # Negatives.
    ("PR this session did not open", wake("tests", "failure", 7), [], None),
    ("success", created(7) + wake("tests", "success", 7), [], None),
    ("skipped", created(7) + wake("tests", "skipped", 7), [], None),
    ("neutral", created(7) + wake("tests", "neutral", 7), [], None),
    ("cancelled", created(7) + wake("tests", "cancelled", 7), [], None),
    ("in progress", created(7) + wake("tests", None, 7), [], None),
    ("in-progress listing", created(7) + listing(7, [run_of("tests", None)]), [], None),
    ("acted on by a push", created(7) + wake("tests", "failure", 7) + push(), [], None),
    ("acted on by git -C push", created(7) + wake("tests", "failure", 7)
     + push("git -C /tmp/r push origin b"), [], None),
    ("acted on by an MCP file write", created(7) + wake("tests", "failure", 7)
     + call("mcp__github__push_files", {}, "ok"), [], None),
    ("acted on by update_pull_request_branch", created(7) + wake("tests", "failure", 7)
     + branch_update(7), [], None),
    ("acted on by a comment on the PR", created(7) + wake("tests", "failure", 7)
     + comment(7), [], None),
    ("acted on by gh pr comment", created(7) + wake("tests", "failure", 7)
     + call("Bash", {"command": "gh pr comment 7 --body-file b.md"}, "ok"), [], None),
    ("later all-success listing", created(7) + wake("tests", "failure", 7)
     + listing(7, [run_of("tests", "success")]), [], None),
    ("later success wake for the same check", created(7) + wake("tests", "failure", 7)
     + wake("tests", "success", 7), [], None),
    ("later listing without the failing check", created(7) + wake("tests", "failure", 7)
     + listing(7, [run_of("lint", "success")]), [], None),
    ("quota on the bot review", created(7)
     + wake("review / claude-review", "failure", 7, QUOTA), [], None),
    ("quota on require-review", created(7) + wake("review / require-review", "failure", 7,
                                                  {"output": {"title": "API quota exhausted"}}),
     [], None),
    ("merged PR is dropped", created(7) + wake("tests", "failure", 7)
     + call("mcp__github__merge_pull_request", {"pullNumber": 7}, "ok"), [], None),
    ("only an assistant message names a failure", created(7) + rec(
        type="assistant", message={"content": [
            {"type": "text", "text": json.dumps({"check_run": {
                "name": "tests", "conclusion": "failure",
                "pull_requests": [{"number": 7}]}})}]}), [], None),
    ("a quota-looking failure on a non-review check still warns",
     created(7) + wake("tests", "failure", 7, QUOTA), [7], "tests"),
]


def run(transcript, stdin=None):
    path = "/nonexistent/transcript.jsonl"
    handle = None
    if transcript is not None:
        handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".jsonl",
                                             delete=False)
        handle.write(transcript)
        handle.close()
        path = handle.name
    payload = stdin if stdin is not None else json.dumps({"transcript_path": path})
    try:
        proc = subprocess.run([sys.executable, HOOK], input=payload,
                              capture_output=True, text=True)
    finally:
        if handle:
            os.unlink(handle.name)
    return proc.returncode, proc.stdout


def main():
    failures = 0
    for name, transcript, prs, check in CASES:
        code, out = run(transcript)
        ok = code == 0
        if prs:
            message = ""
            if out:
                message = json.loads(out).get("systemMessage", "")
            ok = ok and all(f"#{n}" in message for n in prs) and check in message \
                and "do not end the turn" in message
        else:
            ok = ok and out == ""
        if not ok:
            failures += 1
            print(f"FAIL {name}: code={code} out={out!r}")
    # Two PRs, one red: only the red one is named.
    _, out = run(created(7) + created(8) + wake("tests", "failure", 8))
    if "#7" in json.loads(out)["systemMessage"].split("still")[0]:
        failures += 1
        print("FAIL green PR named in the warning")
    # Malformed transcripts and input fail open.
    garbage = "not json\n[]\n{\"type\": 3}\n" + created(7)[:20] + "\n"
    for name, transcript, stdin in (
            ("garbage lines", garbage + wake("tests", "failure", 7)[:-5], None),
            ("empty transcript", "", None),
            ("missing file", None, None),
            ("empty stdin", "", ""),
            ("non-JSON stdin", "", "not json"),
            ("stdin is a list", "", "[]"),
            ("transcript_path is a number", "", '{"transcript_path": 5}')):
        code, out = run(transcript, stdin)
        if code != 0 or out:
            failures += 1
            print(f"FAIL fail-open {name}: code={code} out={out!r}")
    print("ok" if not failures else f"{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
