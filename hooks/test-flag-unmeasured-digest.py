"""Test the flag-unmeasured-digest guard.

The positive case is the 2026-09-18 measurement (ai-config#3779) verbatim in
shape: an issue body citing `3e2b9e10...` as the md5 of two files, in a session
where no command had produced those characters.

The negative cases decide whether the guard survives. A digest the session
actually measured, quoted whole or abbreviated, is exactly what the rule
prescribes and must not fire. Neither must a decimal id that happens to be
seven digits long, a short hex colour, a hex run inside a URL, or a non-body
tool call. A guard that warns on a correctly-measured hash is a guard that gets
switched off, taking the real case with it.

Run: python3 hooks/test-flag-unmeasured-digest.py hooks/flag-unmeasured-digest.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

SHAPE_ERRORS = []

MARKER = "_Posted by Claude Code (AI agent) --- not written by a human._"

# The two real values from the measurement.
REAL_MD5 = "fc967f3e60b170150f3bd94158cc776a"
INVENTED = "3e2b9e10"

PROMPT = {"type": "user", "message": {"content": "import the course materials"}}


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


def tool_result(text, tool_id="t1"):
    """A tool result as it arrives in a live transcript: a user-typed record."""
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": tool_id, "content": text}]}}


def tool_result_blocks(text, tool_id="t1"):
    """The same, with `content` as a list of content blocks."""
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": tool_id,
         "content": [{"type": "text", "text": text}]}]}}


def assistant_says_hash(value):
    """An ASSISTANT message carrying the value.

    This must NOT discharge: the model asserting a digest is the very thing
    under test, so treating its own prior output as evidence would let a
    fabricated value launder itself by being mentioned twice.
    """
    return say(f"The digest is {value}.")


MD5_RUN = tool_result(f"MD5 (ex04_math.pdf) = {REAL_MD5}\n"
                      f"MD5 (ex05_linear_regression.pdf) = {REAL_MD5}")


def bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def mcp(tool, body):
    return {"tool_name": tool, "tool_input": {"owner": "Morrison-Lab", "repo": "mlg",
                                              "issue_number": 3, "body": body}}


def body_with(value):
    return f"(md5 of both: `{value}`)\n\n" + MARKER


# (transcript events, payload, should_fire, label)
CASES = [
    # --- the measurement, and its shape --------------------------------------
    ([PROMPT, say("Comparing the two files.")],
     bash(f'gh issue create -R Morrison-Lab/mlg --body "{body_with(INVENTED + "...")}"'),
     True,
     "#3779: a truncated digest no command produced warns"),
    ([PROMPT],
     mcp("mcp__github__add_issue_comment", body_with(INVENTED + "...")), True,
     "#3779: the same value through mcp__github__add_issue_comment warns"),
    ([PROMPT, MD5_RUN],
     mcp("mcp__github__add_issue_comment", body_with(INVENTED + "...")), True,
     "#3779 exactly: a REAL md5 was measured, and the body cites a different value"),
    ([PROMPT],
     mcp("mcp__github__add_issue_comment",
         "Fixed in commit deadbeef.\n\n" + MARKER), True,
     "a short commit SHA typed from memory warns"),
    ([PROMPT],
     mcp("mcp__github__add_issue_comment",
         "sha256: " + "a" * 64 + "\n\n" + MARKER), True,
     "a full-length sha256 nothing produced warns"),
    ([PROMPT],
     mcp("mcp__github__add_issue_comment",
         "Both files are `d41d8cd98f00b204e9800998ecf8427e` throughout.\n\n"
         + MARKER), True,
     "a bare 32-character run with NO keyword and no truncation warns on its "
     "canonical length alone -- neither other rule can reach this one"),
    ([PROMPT, assistant_says_hash(REAL_MD5)],
     mcp("mcp__github__add_issue_comment", body_with(REAL_MD5)), True,
     "the model's OWN earlier assertion is not a measurement and does not discharge"),
    ([PROMPT],
     mcp("mcp__github__add_issue_comment",
         f"Reverted in {INVENTED}... after the failure.\n\n" + MARKER), True,
     "a truncated value with NO digest keyword near it warns on the "
     "truncation alone -- the keyword rule cannot reach this one"),

    # --- a measured value must stay quiet, or the guard gets switched off -----
    ([PROMPT, MD5_RUN],
     mcp("mcp__github__add_issue_comment", body_with(REAL_MD5)), False,
     "the digest the session measured, quoted whole, is silent"),
    ([PROMPT, MD5_RUN],
     mcp("mcp__github__add_issue_comment", body_with(REAL_MD5[:8] + "...")), False,
     "a legitimate ABBREVIATION of a measured digest is silent, by prefix"),
    ([PROMPT, tool_result_blocks(f"MD5 = {REAL_MD5}")],
     mcp("mcp__github__add_issue_comment", body_with(REAL_MD5)), False,
     "a tool_result whose content is a list of blocks is read too"),
    ([PROMPT, MD5_RUN, say("later"), {"type": "user", "message": {"content": "next"}}],
     mcp("mcp__github__add_issue_comment", body_with(REAL_MD5)), False,
     "a digest measured in an EARLIER turn still discharges -- a hash does not expire"),
    ([{"type": "user", "message": {"content": f"the hash is {REAL_MD5}"}}],
     mcp("mcp__github__add_issue_comment", body_with(REAL_MD5)), False,
     "a value the USER supplied discharges"),

    # --- shapes that are not digests -----------------------------------------
    ([PROMPT],
     mcp("mcp__github__add_issue_comment",
         "Canvas assignment 10134103 and 10299267.\n\n" + MARKER), False,
     "a seven-plus-digit decimal id is not a digest: no a-f, so never a hit"),
    ([PROMPT],
     mcp("mcp__github__add_issue_comment",
         "The label colour is #d73a4a.\n\n" + MARKER), False,
     "a six-character hex colour is below MIN_HEX"),
    ([PROMPT],
     mcp("mcp__github__add_issue_comment",
         "Set the commit colour to abc123 in the theme.\n\n" + MARKER), False,
     "a six-character hex run beside a digest keyword is still below MIN_HEX "
     "-- lowering the floor to 6 would make every short hex colour a hit"),
    ([PROMPT],
     mcp("mcp__github__add_issue_comment",
         "See https://github.com/o/r/commit/abc1234def5678 for it.\n\n" + MARKER),
     False,
     "a hex run inside a URL is a link to something real, not a cited value"),
    ([PROMPT],
     mcp("mcp__github__add_issue_comment",
         "The sha256 is " + "1" * 64 + ".\n\n" + MARKER), False,
     "a canonical-length run with no a-f is not hex-distinctive enough to test"),
    ([PROMPT],
     mcp("mcp__github__add_issue_comment",
         "Renamed the deadbeef fixture.\n\n" + MARKER), False,
     "a hex-looking WORD with no digest keyword and no canonical length is silent"),

    # --- out of scope ---------------------------------------------------------
    ([PROMPT],
     bash("git log --oneline -5"), False,
     "a command that posts no body is out of scope"),
    ([PROMPT],
     bash("gh pr review 5 -R Morrison-Lab/mlg --approve"), False,
     "a review with no body flag posts no prose"),
]


def write_transcript(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    return path


def run(events, payload, extra_args=()):
    """Run the hook end-to-end; return the parsed stdout payload, or {}.

    A FRESH `TMPDIR` per call: the fire-once sentinel lives in
    `tempfile.gettempdir()`, and several cases post the same body, so a
    sentinel written by one would silently suppress a later one.
    """
    tpath = write_transcript(events) if events else ""
    tmpdir = tempfile.mkdtemp()
    try:
        full = dict(payload, transcript_path=tpath, cwd=os.getcwd())
        env = dict(os.environ, TMPDIR=tmpdir)
        env.pop("ANTIGRAVITY_AGENT", None)
        r = subprocess.run(
            [sys.executable, HOOK, *extra_args], input=json.dumps(full),
            capture_output=True, text=True, env=env)
        assert r.returncode == 0, f"hook exited {r.returncode}: {r.stderr}"
        assert "permissionDecision" not in r.stdout, "guard must never block"
        if not r.stdout.strip():
            return {}
        return json.loads(r.stdout)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        if tpath:
            os.unlink(tpath)


def fired(out):
    """True when the payload carries a warning the harness would surface."""
    if not out:
        return False
    ctx = (out.get("hookSpecificOutput") or {}).get("additionalContext")
    if not ctx or not isinstance(out.get("systemMessage"), str):
        SHAPE_ERRORS.append(sorted(out))
        return False
    return True


def check_output_shape():
    """The warning names the offending token and says how to measure it."""
    out = run([PROMPT], mcp("mcp__github__add_issue_comment",
                            body_with(INVENTED + "...")))
    ctx = (out.get("hookSpecificOutput") or {}).get("additionalContext") or ""
    msg = out.get("systemMessage") or ""
    ok = (INVENTED in ctx and INVENTED in msg
          and "md5" in ctx
          and "\n" not in msg
          and (out.get("hookSpecificOutput") or {}).get("hookEventName") == "PreToolUse")
    print(f"{'ok  ' if ok else 'FAIL'}  the warning names the token and a "
          f"command that produces it, in both additionalContext and a "
          f"one-line systemMessage")
    return 0 if ok else 1


def check_unreadable_transcript_is_silent():
    """No readable transcript means no evidence either way: fail open.

    Warning on every digest in a session the guard cannot inspect would make
    it noise in exactly the sessions where it can prove nothing.
    """
    out = run([], mcp("mcp__github__add_issue_comment", body_with(REAL_MD5)))
    ok = not fired(out)
    print(f"{'ok  ' if ok else 'FAIL'}  an unreadable transcript is silent, "
          f"not a blanket warning")
    return 0 if ok else 1


def main():
    failures = 0
    for events, payload, should_fire, label in CASES:
        out = run(events, payload)
        got = fired(out)
        ok = got == should_fire
        failures += 0 if ok else 1
        print(f"{'ok  ' if ok else 'FAIL'}  "
              f"[{'fire ' if should_fire else 'quiet'}] {label}")
    failures += check_output_shape()
    failures += check_unreadable_transcript_is_silent()
    if SHAPE_ERRORS:
        failures += 1
        print(f"FAIL  {len(SHAPE_ERRORS)} payload(s) had no surfacing field: "
              f"{SHAPE_ERRORS}")
    print(f"\n{len(CASES) + 2} checks, {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
