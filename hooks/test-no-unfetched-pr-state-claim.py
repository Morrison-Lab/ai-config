#!/usr/bin/env python3
"""Test the no-unfetched-pr-state-claim guard.

Verifies that a reply saying a PR awaits merge or review, or that work is still
to do, is refused (PreToolUse) or blocked (Stop) unless a tool call since the
last user turn read that state live, and that past-tense, negated, quoted and
non-PR text passes.

Run: python3 hooks/test-no-unfetched-pr-state-claim.py hooks/no-unfetched-pr-state-claim.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "no-unfetched-pr-state-claim.py")

USER = {"type": "user", "message": {"content": [{"type": "text", "text": "status?"}]}}
SYSTEM = {"type": "user", "message": {"content": [
    {"type": "text", "text": "<system-reminder>wake</system-reminder>"}]}}


def call(tool_id, name="Bash", **inp):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": tool_id, "name": name, "input": inp}]}}


def result(tool_id, text="{}", is_error=False):
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": tool_id, "content": text,
         "is_error": is_error}]}}


def say(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def posted(text):
    return call("p0", name="mcp__hearthbot__post_message", text=text)


GET52 = [call("g1", name="mcp__github__pull_request_read", method="get",
              owner="Morrison-Lab", repo="mcsg", pullNumber=52), result("g1")]
GET53 = [call("g1", name="mcp__github__pull_request_read", method="get",
              owner="Morrison-Lab", repo="mcsg", pullNumber=53), result("g1")]
CHECKS52 = [call("g1", name="mcp__github__pull_request_read", method="get_check_runs",
                 owner="Morrison-Lab", repo="mcsg", pullNumber=52), result("g1")]
GHVIEW = [call("b1", command="gh pr view 52 -R Morrison-Lab/mcsg --json state"), result("b1")]
GHAPI = [call("b1", command="gh api repos/Morrison-Lab/mcsg/pulls/52"), result("b1")]
GHFILES = [call("b1", command="gh api repos/Morrison-Lab/mcsg/pulls/52/files"), result("b1")]
LISTPRS = [call("h1", name="mcp__hearthbot__list_prs"), result("h1")]
GHLIST = [call("b1", command="gh pr list -R Morrison-Lab/mcsg --state all"), result("b1")]
FETCH = [call("b1", command="git fetch origin main && git log --oneline origin/main -5"),
         result("b1")]
LOCAL_LOG = [call("b1", command="git log --oneline -5"), result("b1")]
READ_MEMORY = [call("r1", name="Read", file_path="/tmp/memory/MEMORY.md"), result("r1")]
SEARCH = [call("s1", name="mcp__github__search_issues", query="homework"), result("s1")]
OTHER_REPO = [call("g1", name="mcp__github__pull_request_read", method="get",
                   owner="Morrison-Lab", repo="mcs", pullNumber=52), result("g1")]
SAME_REPO = [call("b1", command="gh api repos/Morrison-Lab/mcsg/pulls/52 --jq .state"),
             result("b1")]
GHVIEW_URL = [call("b1", command="gh pr view https://github.com/Morrison-Lab/mcsg/pull/52"),
              result("b1")]
GHVIEW_CUR = [call("b1", command="gh pr view --json state"), result("b1")]
GREP_PULLS = [call("b1", command="grep repos/Morrison-Lab/mcsg/pulls/52 notes.md"), result("b1")]
ORIGIN_LOG = [call("b1", command="git log --oneline origin/main -5"), result("b1")]
GH_MERGE = [call("b1", command="gh pr merge 52 --squash"), result("b1")]
GH_CREATE = [call("b1", command="gh issue create -t x -b y"), result("b1")]
API_PUT = [call("b1", command="gh api repos/o/r/pulls/52/merge -X PUT"), result("b1")]
GH_API_GET = [call("b1", command="gh api repos/Morrison-Lab/mcsg/contents/Homework"),
              result("b1")]
STRING_USER = {"type": "user", "message": {
    "content": "<system-reminder>ctx</system-reminder>\nplease check status"}}
ERRORED = [call("g1", name="mcp__github__pull_request_read", method="get",
                owner="Morrison-Lab", repo="mcsg", pullNumber=52),
           result("g1", "Not Found", is_error=True)]

INCIDENT = "mcsg#52 is waiting on your merge."
HOMEWORK = "Next up is to draft Homework 2-6."

# (pre-events, text, expected_block, label). Each runs in both modes.
CASES = [
    # The incidents
    ([USER], INCIDENT, True, "the mcsg#52 incident blocks with no fetch"),
    ([USER], "It's waiting on your merge.", True, "unnumbered merge claim blocks"),
    ([USER], HOMEWORK, True, "the Homework 2-6 incident blocks with no read"),
    ([USER], "Drafting Homework 2-6 is next.", True, "'X is next' blocks"),
    # Other PR-state shapes
    ([USER], "PR #52 is ready for you to merge.", True, "ready for you to merge blocks"),
    ([USER], "The PR awaits your merge.", True, "awaits your merge blocks"),
    ([USER], "mcs#14 is still open.", True, "numbered 'still open' blocks"),
    ([USER], "The PR is in review.", True, "'PR is in review' blocks"),
    ([USER], "#52 hasn't been merged yet.", True, "hasn't been merged blocks"),
    ([USER], "The PR needs your review.", True, "PR needs your review blocks"),
    ([USER], "#52 is awaiting your merge.", True, "awaiting with no preposition blocks"),
    ([USER], "PR #52 is awaiting review.", True, "awaiting review blocks"),
    ([USER], "mcsg#52 is waiting on the merge.", True, "waiting on the merge blocks"),
    ([USER], "#52 is waiting on mwc.", True, "waiting on mwc blocks"),
    ([USER], "#52 is blocked on your merge.", True, "blocked on your merge blocks"),
    ([USER], "#52 is up for review.", True, "up for review blocks"),
    ([USER], "Hook: no, #52 is waiting on your merge.", True,
     "a 'no,' in an earlier clause does not negate"),
    ([USER], "mcsg#52 is pending review.", True, "pending review blocks"),
    # Other pending-work shapes
    ([USER], "Homework 3 still needs drafting.", True, "still needs drafting blocks"),
    ([USER], "The Week 4 worksheet hasn't been written yet.", True,
     "hasn't been written blocks"),
    ([USER], "Lab 2 is yet to be ported.", True, "yet to be ported blocks"),

    # A live read of the same PR passes
    ([USER] + GET52, INCIDENT, False, "pull_request_read get of #52 passes"),
    ([USER] + GHVIEW, INCIDENT, False, "gh pr view 52 passes"),
    ([USER] + GHAPI, INCIDENT, False, "gh api .../pulls/52 passes"),
    ([USER] + LISTPRS, INCIDENT, False, "hearthbot list_prs passes"),
    ([USER] + GHLIST, INCIDENT, False, "gh pr list passes"),
    ([USER] + GET52, "It's waiting on your merge.", False,
     "unnumbered claim passes after a PR fetch"),
    # ...and a read of something else does not
    ([USER] + GET53, INCIDENT, True, "a fetch of a different PR does not cover #52"),
    ([USER] + CHECKS52, INCIDENT, True, "check runs do not report merge state"),
    ([USER] + GHFILES, INCIDENT, True, "the PR's file list does not report merge state"),
    ([USER] + ERRORED, INCIDENT, True, "an errored fetch does not count"),
    ([USER] + FETCH, INCIDENT, True, "a git fetch does not read a PR's state"),
    ([USER] + OTHER_REPO, INCIDENT, True, "a fetch of another repo's #52 does not cover mcsg#52"),
    ([USER] + SAME_REPO, INCIDENT, False, "a fetch of mcsg#52 by repo covers mcsg#52"),
    ([USER] + GHVIEW_URL, INCIDENT, False, "gh pr view with a PR URL passes"),
    ([USER] + GREP_PULLS, INCIDENT, True, "grep of a /pulls/52 string is not a fetch"),
    ([USER] + GHVIEW_CUR, "It's waiting on your merge.", False,
     "numberless gh pr view covers an unnumbered claim"),
    ([USER] + GHVIEW_CUR, INCIDENT, True, "numberless gh pr view does not cover #52"),
    ([STRING_USER] + [], INCIDENT, True,
     "a string user turn after a reminder prefix still resets the turn"),
    (GET52 + [STRING_USER], INCIDENT, True,
     "a fetch before a reminder-prefixed string user turn does not count"),
    (GET52 + [USER], INCIDENT, True, "a fetch before the last user turn does not count"),
    (GET52 + [SYSTEM], INCIDENT, False, "a system-reminder is not a user turn"),

    # Pending work: any live forge or remote read passes, local reads do not
    ([USER] + FETCH, HOMEWORK, False, "git fetch plus log origin/main passes"),
    ([USER] + SEARCH, HOMEWORK, False, "a GitHub issue search passes"),
    ([USER] + GHLIST, HOMEWORK, False, "a PR list passes"),
    ([USER] + LOCAL_LOG, HOMEWORK, True, "a local git log does not count"),
    ([USER] + READ_MEMORY, HOMEWORK, True, "reading a memory note does not count"),
    ([USER] + ORIGIN_LOG, HOMEWORK, True, "a remote-tracking log without a fetch does not count"),
    ([USER] + GH_MERGE, HOMEWORK, True, "a forge write is not a read"),
    ([USER] + GH_CREATE, HOMEWORK, True, "an issue create is not a read"),
    ([USER] + API_PUT, HOMEWORK, True, "a gh api PUT is not a read"),
    ([USER] + GH_API_GET, HOMEWORK, False, "a gh api GET passes"),

    # Ordinary text with no PR or deliverable in view
    ([USER], "This draft needs your review before I send it.", False,
     "needs your review without a PR passes"),
    ([USER], "The spec is ready for review.", False, "ready for review without a PR passes"),
    ([USER], "Pending review comments are listed below.", False,
     "pending review without a PR passes"),
    ([USER], "The config isn't done by default.", False, "isn't done without a work item passes"),
    ([USER], "The helper hasn't been added to PATH.", False,
     "hasn't been added without a work item passes"),
    ([USER], "Next, write the tests for the parser.", False,
     "'next, write' without a work item passes"),
    ([USER], "Step 2 is next: build the image.", False, "'is next' without a work item passes"),
    ([USER], 'You said "waiting on your merge" earlier.', False, "quoted words pass"),
    ([USER], "The owner wrote:\n\n> it's waiting on your merge", False,
     "a blockquote passes"),

    # Not a pending claim
    ([USER], "mcsg#52 merged at 00:40 PDT.", False, "past tense passes"),
    ([USER], "Nothing is waiting on your merge.", False, "negated claim passes"),
    ([USER], "No PR is still open.", False, "negated weak claim passes"),
    ([USER], "The file is still open in the editor.", False,
     "'still open' without a PR in the sentence passes"),
    ([USER], "The hook catches `waiting on your merge` phrasing.", False,
     "phrase in a code span passes"),
    ([USER], "I drafted Homework 2 and opened mcsg#18.", False, "report of done work passes"),
    ([USER], "Done.", False, "unrelated text passes"),
]


def write(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    return path


def run(payload, tmpdir=None):
    env = dict(os.environ, TMPDIR=tmpdir or tempfile.mkdtemp())
    return subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                          capture_output=True, text=True, env=env)


def pretool(events, text, tmpdir=None):
    path = write(events)
    try:
        out = run({"transcript_path": path, "tool_name": "mcp__hearthbot__post_message",
                   "tool_input": {"text": text}}, tmpdir).stdout
    finally:
        os.unlink(path)
    if not out.strip():
        return False
    spec = json.loads(out)["hookSpecificOutput"]
    assert spec["hookEventName"] == "PreToolUse"
    assert "ai-config#4834" in spec["permissionDecisionReason"]
    return spec["permissionDecision"] == "deny"


def stop(events, text, tmpdir=None):
    path = write(events + [say(text)])
    try:
        out = run({"transcript_path": path}, tmpdir).stdout
    finally:
        os.unlink(path)
    if not out.strip():
        return False
    data = json.loads(out)
    assert "ai-config#4834" in data["reason"]
    return data["decision"] == "block"


def main():
    passes = failures = 0

    def check(ok, label):
        nonlocal passes, failures
        print(("PASS: " if ok else "FAIL: ") + label)
        if ok:
            passes += 1
        else:
            failures += 1

    for events, text, expected, label in CASES:
        check(pretool(events, text) == expected, f"[PreToolUse] {label}")
        check(stop(events, text) == expected, f"[Stop] {label}")

    # The missing number is named in the reason.
    path = write([USER] + GET53)
    out = run({"transcript_path": path, "tool_name": "mcp__hearthbot__post_message",
               "tool_input": {"text": INCIDENT}}).stdout
    os.unlink(path)
    check("read PR mcsg#52 live" in out, "the reason names the unfetched PR and repo")

    # A non-reply tool is ignored at PreToolUse.
    path = write([USER])
    out = run({"transcript_path": path, "tool_name": "Bash",
               "tool_input": {"command": "echo " + INCIDENT}}).stdout
    os.unlink(path)
    check(not out.strip(), "a non-reply tool call is ignored")

    # At Stop, a reply tool since the last user turn hands the text to PreToolUse.
    check(not stop([USER, posted(INCIDENT), result("p0")], INCIDENT),
          "Stop yields when a reply tool ran this turn")

    # A denied reply tool call does not hand the Stop text over.
    check(stop([USER, posted(INCIDENT), result("p0", "denied", is_error=True)], INCIDENT),
          "Stop still judges the text when the reply tool call was denied")

    # Sentinel: the same text is refused once, and a turn is refused at most twice.
    d = tempfile.mkdtemp()
    path = write([USER])
    try:
        def deny(text):
            out = run({"transcript_path": path, "tool_name": "mcp__hearthbot__post_message",
                       "tool_input": {"text": text}}, d).stdout
            return '"deny"' in out
        first, second = deny(INCIDENT), deny(INCIDENT)
        check(first and not second, "sentinel refuses the same text only once")
        third = deny("It's waiting on your merge.")
        fourth = deny("I think it may be waiting on your merge.")
        check(third and not fourth, "a reworded claim is refused at most twice per turn")
    finally:
        os.unlink(path)
    other = write([USER])
    try:
        out = run({"transcript_path": other, "tool_name": "mcp__hearthbot__post_message",
                   "tool_input": {"text": INCIDENT}}, d).stdout
    finally:
        os.unlink(other)
    check('"deny"' in out, "another transcript's sentinel does not excuse this one")

    bad = subprocess.run([sys.executable, HOOK], input="not json",
                         capture_output=True, text=True)
    check(bad.returncode == 0 and not bad.stdout.strip(), "unreadable payload fails open")

    with tempfile.TemporaryDirectory() as tmp:
        lone = os.path.join(tmp, "no-unfetched-pr-state-claim.py")
        with open(HOOK, encoding="utf-8") as src, open(lone, "w", encoding="utf-8") as dst:
            dst.write(src.read())
        orphan = subprocess.run([sys.executable, lone], input="{}",
                                capture_output=True, text=True)
    check(orphan.returncode == 0 and not orphan.stdout.strip(),
          "missing sibling module fails open")

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
