"""Test the no-unread-issue-claim guard.

The positive cases are the 2026-09-21 measurement in shape: a message
reporting #1566 as awaiting the user's decision, in a session that read only
that issue's body.

The negative cases decide whether the guard survives. Reading the comments
discharges it; an ordinary mention of an issue number is not a claim about
its state; a cue about something else in the same message must not attach to
an unrelated number; and a PR reference is out of scope. A guard that warns
when the comments WERE read, or on every recap that names an issue, is one
that gets switched off, taking the real case with it.

Run: python3 hooks/test-no-unread-issue-claim.py hooks/no-unread-issue-claim.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

PROMPT = {"type": "user", "message": {"content": "work the backlog"}}


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


def tool(name, inp):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": "t1", "name": name, "input": inp}]}}


def bash(cmd):
    return tool("Bash", {"command": cmd})


# The two reads that matter, and the one that does not.
READ_BODY_ONLY = bash("gh issue view 1566 -R o/r --json body --jq .body")
READ_COMMENTS = bash("gh issue view 1566 -R o/r --json comments --jq '.comments[]'")
READ_COMMENTS_FLAG = bash("gh issue view 1566 -R o/r --comments")
READ_COMMENTS_API = bash("gh api repos/o/r/issues/1566/comments --paginate")
READ_OTHER_COMMENTS = bash("gh issue view 999 -R o/r --comments")

# The measured claim, near-verbatim.
CLAIM = ("#1566's deliverable is a decision with a genuine do-nothing option, "
         "so it is yours rather than mine.")
CLAIM_BLOCKED = "Both #1544 and #1546 are blocked on discussion #1597."

# (events, should_fire, label)
CASES = [
    # --- the measurement ------------------------------------------------------
    ([PROMPT, READ_BODY_ONLY, say(CLAIM)], True,
     "#3823: a decision escalated after a BODY-only read warns"),
    ([PROMPT, say(CLAIM)], True,
     "the same claim with no read at all warns"),
    ([PROMPT, READ_BODY_ONLY,
      say("#1566 still needs your call on sim determinism.")], True,
     "'still needs your call' is a state claim"),
    ([PROMPT, READ_OTHER_COMMENTS, say(CLAIM)], True,
     "reading a DIFFERENT issue's comments does not discharge #1566"),

    # --- reading the comments discharges it -----------------------------------
    ([PROMPT, READ_COMMENTS, say(CLAIM)], False,
     "a --json comments read discharges it"),
    ([PROMPT, READ_COMMENTS_FLAG, say(CLAIM)], False,
     "the --comments flag discharges it"),
    ([PROMPT, READ_COMMENTS_API, say(CLAIM)], False,
     "the REST comments endpoint discharges it"),
    ([PROMPT, READ_COMMENTS, READ_BODY_ONLY, say(CLAIM)], False,
     "a later body-only read does not UNDO an earlier comments read"),

    # --- not a state claim ----------------------------------------------------
    ([PROMPT, say("Merged #1566 as 7100f687.")], False,
     "reporting a merge is not a claim that the issue is open"),
    ([PROMPT, say("Filed #1621 for the terrain overlay.")], False,
     "filing an issue is not a claim that it is blocked"),
    ([PROMPT, say("Closed #1566 as completed.")], False,
     "closing an issue is not a claim that it awaits anyone"),

    # --- the cue must share a sentence with the reference ---------------------
    # The cue here is REAL ("blocked on"), and sits in a sentence with no
    # issue reference; the reference sits in a sentence with no cue. Dropping
    # sentence scoping makes this fire, so it is the test that pins it.
    ([PROMPT, say("The deploy is blocked on infra. "
                  "Separately, #1566 was closed.")], False,
     "a REAL cue in a different sentence must not attach to the number"),

    # --- scope ----------------------------------------------------------------
    ([PROMPT, say("PR #1622 is awaiting review.")], False,
     "a PR reference is out of scope -- this guard is about issues"),
    ([PROMPT, say("Blocked on the review at "
                  "https://github.com/o/r/pull/1622 for now.")], False,
     "a pull URL is not an issue reference"),
    ([PROMPT, READ_BODY_ONLY,
      say("The guard fires when a message says `#1566 awaits your decision`.")],
     False,
     "a trigger phrase inside a CODE SPAN is a quotation, not an assertion"),

    # --- defects found by adversarial review ---------------------------------
    # The MCP discharge path was DEAD: the patterns key on `issue_read`, which
    # lives in the tool NAME, and only `input` was being searched. Remote
    # sessions have no `gh`, so this was a systematic false positive exactly
    # where the MCP route is mandatory.
    ([PROMPT,
      tool("mcp__github__issue_read",
           {"method": "get_comments", "owner": "o", "repo": "r",
            "issue_number": 1566}),
      say(CLAIM)], False,
     "an MCP issue_read for comments discharges it -- the tool NAME carries "
     "the match, so searching only `input` made this path dead code"),

    # A bulleted recap is this corpus's default reporting shape. A `\n- item`
    # has no whitespace after the newline, so a `\s+`-anchored split treated
    # the whole recap as ONE sentence and attached an unrelated cue to an
    # issue reported as closed.
    ([PROMPT, say("Progress notes:\n"
                  "- Investigated flaky CI, still pending a fix upstream\n"
                  "- Closed #1622 after merging the associated PR")], False,
     "an unrelated cue in ANOTHER bullet must not attach to an issue "
     "reported as closed"),
    ([PROMPT, say("I have several PRs pending; #1622 is one example.")], False,
     "a semicolon separates clauses -- the cue must not reach across it"),

    # The cue describes the PR, not the issue.
    ([PROMPT, READ_BODY_ONLY,
      say("The PR for #1622 is awaiting review.")], False,
     "'the PR for #N' attributes the cue to the PR, not to issue #N"),

    # A --jq filter legitimately contains a pipe.
    ([PROMPT,
      bash("gh issue view 1566 -R o/r --jq '.comments[] | .body' --json comments"),
      say(CLAIM)], False,
     "a --jq pipe before the comments flag must not break the discharge match"),

    # Mixed state: one discharged, one not. The undischarged one must win.
    ([PROMPT, READ_COMMENTS,
      say("#1566 is settled. But #1544 still needs your call.")], True,
     "a discharged issue in the same message does not excuse an undischarged one"),
]


def write_transcript(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    return path


def run(events):
    tpath = write_transcript(events)
    try:
        payload = {"transcript_path": tpath}
        env = dict(os.environ)
        env.pop("ANTIGRAVITY_AGENT", None)
        r = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                           capture_output=True, text=True, env=env)
        assert r.returncode == 0, f"hook exited {r.returncode}: {r.stderr}"
        assert "permissionDecision" not in r.stdout, "guard must never block"
        if not r.stdout.strip():
            return {}
        return json.loads(r.stdout)
    finally:
        os.unlink(tpath)


def fired(out):
    if not out:
        return False
    return bool((out.get("hookSpecificOutput") or {}).get("additionalContext"))


def check_message_names_the_number():
    """The warning must name the issue it is about, and how to discharge it."""
    out = run([PROMPT, READ_BODY_ONLY, say(CLAIM)])
    ctx = (out.get("hookSpecificOutput") or {}).get("additionalContext") or ""
    msg = out.get("systemMessage") or ""
    ok = ("1566" in ctx and "1566" in msg
          and "--comments" in ctx
          and "\n" not in msg)
    print(f"{'ok  ' if ok else 'FAIL'}  the warning names the issue and the "
          f"command that discharges it, with a one-line systemMessage")
    return 0 if ok else 1


def check_unreadable_transcript_is_silent():
    """No transcript means no evidence either way: fail open."""
    payload = {"transcript_path": "/nonexistent/path.jsonl"}
    r = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True)
    ok = r.returncode == 0 and not r.stdout.strip()
    print(f"{'ok  ' if ok else 'FAIL'}  an unreadable transcript is silent")
    return 0 if ok else 1


def main():
    failures = 0
    for events, should_fire, label in CASES:
        got = fired(run(events))
        ok = got == should_fire
        failures += 0 if ok else 1
        tag = "fire " if should_fire else "quiet"
        print(f"{'ok  ' if ok else 'FAIL'}  [{tag}] {label}")
    adhoc = [check_message_names_the_number,
             check_unreadable_transcript_is_silent]
    for check in adhoc:
        failures += check()
    print(f"\n{len(CASES) + len(adhoc)} checks, {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
