#!/usr/bin/env python3
"""Tests for hooks/warn-red-own-pr-at-stop.py.

Run: python3 hooks/test-warn-red-own-pr-at-stop.py [hook path]

The warning is a Stop hook's `systemMessage`, so every positive case reads that
key and checks it names the PR and the failing check. Every case that is not
meant to crash also asserts an empty stderr, so a hook that crashes (and fails
open, exit 0, printing nothing) cannot pass as a clean negative.

The wake-event fixture (`wake`) is INVENTED, not copied from a real transcript:
no real sample of a `check_run` webhook wake event was available when this was
written, so its `<github-webhook-activity>` wrapper and JSON body are a guess at
the shape. The hook finds check runs by structure (a dict with `name` and
`conclusion`, PRs under `pull_requests`), not by the wrapper, so the guess only
has to be close. Replace the fixture with a real sample once one is captured.
"""
import importlib.util
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


def call(name, tool_input, result="", is_error=False):
    """An assistant tool_use followed by its user tool_result."""
    ident = f"toolu_{next(_ids)}"
    block = {"type": "tool_result", "tool_use_id": ident, "content": result}
    if is_error:
        block["is_error"] = True
    return (
        rec(type="assistant", message={"content": [
            {"type": "tool_use", "id": ident, "name": name, "input": tool_input}]})
        + rec(type="user", message={"content": [block]}))


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


def usertext(body):
    return rec(type="user", message={"content": [{"type": "text", "text": body}]})


def partial_listing(number, runs, total):
    return call("mcp__github__pull_request_read",
                {"method": "get_check_runs", "pullNumber": number},
                json.dumps({"total_count": total, "check_runs": runs}))


def listing(number, runs):
    return call("mcp__github__pull_request_read",
                {"method": "get_check_runs", "owner": "o", "repo": "r",
                 "pullNumber": number},
                json.dumps({"total_count": len(runs), "check_runs": runs}))


def run_of(name, conclusion):
    return {"name": name, "status": "completed" if conclusion else "in_progress",
            "conclusion": conclusion}


def push(command="git push origin b", result="ok", is_error=False):
    return call("Bash", {"command": command}, result, is_error)


def head_run(name, conclusion, sha):
    return dict(run_of(name, conclusion), head_sha=sha)


def red7(*more):
    """PR 7 owned, with a failing `tests` check, followed by more transcript."""
    return created(7) + wake("tests", "failure", 7) + "".join(more)


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
    ("wake seen before the PR is registered is attributed later",
     wake("tests", "failure", 7) + created(7), [7], "tests"),
    ("gh pr create with other URLs in the result owns the last one",
     call("Bash", {"command": "gh pr create --title t"},
          "see https://github.com/o/r/pull/3 for context\n"
          "https://github.com/o/r/pull/8\n") + wake("tests", "failure", 8),
     [8], "tests"),
    ("paginated listing merges instead of replacing",
     created(7) + wake("tests", "failure", 7)
     + partial_listing(7, [run_of("lint", "success")], 5), [7], "tests"),
    ("empty listing merges instead of replacing",
     created(7) + wake("tests", "failure", 7) + partial_listing(7, [], 0), [7], "tests"),
    ("error result merges instead of replacing",
     created(7) + wake("tests", "failure", 7)
     + call("mcp__github__pull_request_read",
            {"method": "get_check_runs", "pullNumber": 7}, "Error: 502 Bad Gateway"),
     [7], "tests"),
    ("rejected push is not acting", created(7) + wake("tests", "failure", 7)
     + call("Bash", {"command": "git push origin b"},
            " ! [rejected]        b -> b (non-fast-forward)\n"), [7], "tests"),
    ("push with error: output is not acting", created(7) + wake("tests", "failure", 7)
     + call("Bash", {"command": "git push origin b"}, "error: failed to push"),
     [7], "tests"),
    ("dry-run push is not acting", created(7) + wake("tests", "failure", 7)
     + push("git push --dry-run origin b"), [7], "tests"),
    ("errored MCP file write is not acting", created(7) + wake("tests", "failure", 7)
     + call("mcp__github__push_files", {}, "error: 409 conflict"), [7], "tests"),
    ("text events: failure on one line, PR named on another",
     created(7) + usertext("check_run name=tests conclusion=failure\nsee #7 for context"),
     [], None),
    ("text events: failure with its PR on the same line",
     created(7) + usertext("check_run name=tests conclusion=failure for #7"), [7], "tests"),
    ("text events: a later success text clears a failure text",
     created(7) + usertext("check_run name=tests conclusion=failure for #7")
     + usertext("check_run name=tests conclusion=success for #7"), [], None),
    ("text events do not span two events",
     created(7) + usertext("check_run name=lint conclusion=success for #7\n"
                           "other name=tests then conclusion=failure for #7"), [], None),
    ("quota words outside the title and summary do not exempt",
     created(7) + wake("review / claude-review", "failure", 7,
                       {"app": {"description": "usage quota app"},
                        "output": {"summary": "Verdict: Needs more work"}}),
     [7], "review / claude-review"),
    ("echo gh pr create is not a create",
     call("Bash", {"command": "echo gh pr create"},
          "https://github.com/o/r/pull/7\n") + wake("tests", "failure", 7), [], None),
    ("closing a PR by another number leaves this one",
     created(7) + wake("tests", "failure", 7)
     + call("Bash", {"command": "gh pr close 8"}, "ok"), [7], "tests"),
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
    ("subscribing does not make a PR own", subscribed(9) + wake("tests", "failure", 9),
     [], None),
    ("gh pr merge drops the PR", created(7) + wake("tests", "failure", 7)
     + call("Bash", {"command": "gh pr merge 7 --squash"}, "ok"), [], None),
    ("gh pr close drops the PR", created(7) + wake("tests", "failure", 7)
     + call("Bash", {"command": "gh pr close https://github.com/o/r/pull/7"}, "ok"),
     [], None),
    ("update_pull_request state closed drops the PR",
     created(7) + wake("tests", "failure", 7)
     + call("mcp__github__update_pull_request", {"pullNumber": 7, "state": "closed"}, "ok"),
     [], None),
    ("update_pull_request without closing keeps the PR",
     created(7) + wake("tests", "failure", 7)
     + call("mcp__github__update_pull_request", {"pullNumber": 7, "title": "t"}, "ok"),
     [7], "tests"),
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
    # --- Adversarial-review round 2 ---
    # A blocked or failed merge/close/update does not drop the PR.
    ("errored gh pr merge keeps the PR", red7(
        call("Bash", {"command": "gh pr merge 7 --squash"}, "merge blocked", True)),
     [7], "tests"),
    ("gh pr merge with Exit code 1 keeps the PR", red7(
        call("Bash", {"command": "gh pr merge 7"}, "Exit code 1\nnot mergeable")),
     [7], "tests"),
    ("errored gh pr close keeps the PR", red7(
        call("Bash", {"command": "gh pr close 7"}, "boom", True)), [7], "tests"),
    ("errored merge_pull_request keeps the PR", red7(
        call("mcp__github__merge_pull_request", {"pullNumber": 7}, "not mergeable", True)),
     [7], "tests"),
    ("merge_pull_request error text keeps the PR", red7(
        call("mcp__github__merge_pull_request", {"pullNumber": 7},
             "Error: Pull Request is not mergeable")), [7], "tests"),
    ("errored update_pull_request close keeps the PR", red7(
        call("mcp__github__update_pull_request", {"pullNumber": 7, "state": "closed"},
             "422", True)), [7], "tests"),
    # gh pr create forms; a failed create is not adopted.
    ("git push && gh pr create counts as own",
     call("Bash", {"command": "git push -u origin b && gh pr create --fill"},
          "https://github.com/o/r/pull/8\n") + wake("tests", "failure", 8),
     [8], "tests"),
    ("cd x && gh pr create counts as own",
     call("Bash", {"command": "cd x && gh pr create --fill"},
          "https://github.com/o/r/pull/8\n") + wake("tests", "failure", 8),
     [8], "tests"),
    ("GH_TOKEN=x gh pr create counts as own",
     call("Bash", {"command": "GH_TOKEN=x gh pr create --fill"},
          "https://github.com/o/r/pull/8\n") + wake("tests", "failure", 8),
     [8], "tests"),
    ("failed gh pr create printing an existing PR URL is not adopted",
     call("Bash", {"command": "gh pr create --fill"},
          "a pull request for branch b already exists:\nhttps://github.com/o/r/pull/8\n",
          True) + wake("tests", "failure", 8), [], None),
    ("Exit code 1 gh pr create is not adopted",
     call("Bash", {"command": "gh pr create --fill"},
          "Exit code 1\nhttps://github.com/o/r/pull/8\n") + wake("tests", "failure", 8),
     [], None),
    ("errored create_pull_request is not adopted",
     call("mcp__github__create_pull_request", {"title": "t"},
          json.dumps({"number": 8, "url": "https://github.com/o/r/pull/8"}), True)
     + wake("tests", "failure", 8), [], None),
    # An action counts only when it had an effect.
    ("errored comment is not acting", red7(
        call("mcp__github__add_issue_comment",
             {"owner": "o", "repo": "r", "issue_number": 7, "body": "b"}, "403", True)),
     [7], "tests"),
    ("errored gh pr comment is not acting", red7(
        call("Bash", {"command": "gh pr comment 7 --body x"}, "failed to post", True)),
     [7], "tests"),
    ("errored branch update is not acting", red7(
        call("mcp__github__update_pull_request_branch",
             {"owner": "o", "repo": "r", "pullNumber": 7}, "conflict", True)),
     [7], "tests"),
    ("Everything up-to-date is not acting", red7(
        push(result="Everything up-to-date\n")), [7], "tests"),
    ("branch-delete push is not acting", red7(
        push("git push origin --delete b"), push("git push origin :b")),
     [7], "tests"),
    ("push to a URL remote is not acting", red7(
        push("git push https://github.com/other/repo.git b")), [7], "tests"),
    ("errored push is not acting", red7(
        push("git push origin b", "hook declined", True)), [7], "tests"),
    ("push whose output has a mid-line error: still acts", red7(
        push(result="remote: note: error: none, this is the hook banner\n"
                    "To github.com:o/r.git\n   a1..b2  b -> b\n")), [], None),
    ("fatal: push output is not acting", red7(
        push(result="fatal: unable to access 'https://x'\n")), [7], "tests"),
    # One odd record does not disable the scan.
    ("non-scalar conclusion is skipped, the rest still scanned",
     created(7) + wake("lint", ["failure"], 7) + wake("tests", "failure", 7),
     [7], "tests"),
    ("non-ASCII digits in an issue_number are not a number", red7(
        call("mcp__github__add_issue_comment",
             {"owner": "o", "repo": "r", "issue_number": "²", "body": "b"}, "ok")),
     [7], "tests"),
    ("Arabic-Indic digits in gh pr close are not a number", red7(
        call("Bash", {"command": "gh pr close ٧"}, "ok")), [7], "tests"),
    ("many unparseable braces still finish and find the event",
     created(7) + wake("tests", "failure", 7, {"note": "{" * 20000}), [7], "tests"),
    # Evidence keyed by check name plus head SHA.
    ("late success on an old head does not clear a failure on a newer head",
     created(7) + listing(7, [head_run("lint", "success", "aaa")])
     + listing(7, [head_run("tests", "failure", "bbb")])
     + wake("tests", "success", 7, {"head_sha": "aaa"}), [7], "tests"),
    ("success on a newer head clears an older head's failure",
     created(7) + wake("tests", "failure", 7, {"head_sha": "aaa"})
     + wake("tests", "success", 7, {"head_sha": "bbb"}), [], None),
    ("success on the same head clears that head's failure",
     created(7) + wake("tests", "failure", 7, {"head_sha": "aaa"})
     + wake("tests", "success", 7, {"head_sha": "aaa"}), [], None),
    ("failure on a newer head survives success on the older one",
     created(7) + wake("tests", "success", 7, {"head_sha": "aaa"})
     + wake("tests", "failure", 7, {"head_sha": "bbb"}), [7], "tests"),
    # A tool-result echo flagged isMeta is not a wake event.
    ("meta tool-result echo is not a wake event",
     created(7) + rec(type="user", isMeta=True, sourceToolUseID="toolu_1",
                      message={"content": [{"type": "text", "text":
                          json.dumps({"check_run": {"name": "tests",
                                                    "conclusion": "failure",
                                                    "pull_requests": [{"number": 7}]}})}]}),
     [], None),
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
    return proc.returncode, proc.stdout, proc.stderr


def main():
    failures = 0
    for name, transcript, prs, check in CASES:
        code, out, err = run(transcript)
        ok = code == 0 and err == ""
        if prs:
            message = ""
            if out:
                message = json.loads(out).get("systemMessage", "")
            ok = ok and all(f"#{n}" in message for n in prs) and check in message \
                and "does not block the stop" in message
        else:
            ok = ok and out == ""
        if not ok:
            failures += 1
            print(f"FAIL {name}: code={code} out={out!r} err={err!r}")
    # Two PRs, one red: only the red one is named.
    _, out, _ = run(created(7) + created(8) + wake("tests", "failure", 8))
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
        code, out, err = run(transcript, stdin)
        if code != 0 or out or err:
            failures += 1
            print(f"FAIL fail-open {name}: code={code} out={out!r} err={err!r}")
    # One unparseable-by-recursion record is skipped, reported once, and the rest of
    # the scan still finds the failure.
    code, out, err = run(created(7) + "[" * 100000 + "\n" + wake("tests", "failure", 7))
    if code != 0 or "#7" not in out or "skipped 1 unreadable record" not in err:
        failures += 1
        print(f"FAIL per-record fail-open: code={code} out={out!r} err={err!r}")
    # decoded() is not quadratic: it stops after MAX_BRACE_TRIES braces that do not parse.
    spec = importlib.util.spec_from_file_location("hook_under_test", HOOK)
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    calls = []

    class Counting(hook.json.JSONDecoder):
        def raw_decode(self, text, idx=0):
            calls.append(idx)
            return super().raw_decode(text, idx)

    real = hook.json.JSONDecoder
    hook.json.JSONDecoder = Counting
    try:
        list(hook.decoded("{" * 20000))
    finally:
        hook.json.JSONDecoder = real
    if len(calls) > hook.MAX_BRACE_TRIES:
        failures += 1
        print(f"FAIL decoded() tried {len(calls)} braces, limit {hook.MAX_BRACE_TRIES}")
    # An unreadable transcript is not silent: one stderr line, still exit 0.
    directory = tempfile.mkdtemp()
    try:
        proc = subprocess.run([sys.executable, HOOK],
                              input=json.dumps({"transcript_path": directory}),
                              capture_output=True, text=True)
    finally:
        os.rmdir(directory)
    if proc.returncode != 0 or proc.stdout or len(proc.stderr.strip().splitlines()) != 1:
        failures += 1
        print(f"FAIL unreadable transcript: {proc.returncode} {proc.stdout!r} {proc.stderr!r}")
    print("ok" if not failures else f"{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
