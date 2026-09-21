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

# The pin surface (ai-config#3392), from the 2026-09-20 recurrence on
# Lacaedemon/sparta#1615. `REAL_HEAD` is that PR's actual head; `PADDED_HEAD`
# shares its first 8 characters and is invented past them -- the exact shape of
# a value built by padding out the abbreviation a gate printed.
REAL_HEAD = "d46910953d5ea64ee58a295dd56a6f2b1ac55d80"
PADDED_HEAD = "d46910959e3d84fd1e5b8b0e6b2ad5e0b1d5a2f9"
assert REAL_HEAD[:8] == PADDED_HEAD[:8], "the padded fixture must share a prefix"
assert REAL_HEAD != PADDED_HEAD

# Only the ABBREVIATION reaches the transcript, which is the whole setup: the
# session has seen `d4691095` and has never seen the full forty characters.
HEAD_RUN = tool_result(
    "PR #1615 (feat/621-far-tier-winner-pursuit): HEAD=d4691095\n"
    "FULLY CLEAN on HEAD d4691095!")

# The corrected reading: the full forty characters, as `--json headRefOid`
# returns them. Kept separate from HEAD_RUN deliberately -- a case that means
# "the session read the whole value" must not be fed the abbreviation-only
# fixture, or it would pass for the wrong reason.
HEAD_FULL_RUN = tool_result(f"head={REAL_HEAD}")


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

    # --- the shape the guard was BUILT for, which it originally missed -------
    # This corpus's own convention for a backtick-safe body writes the file with
    # a heredoc in the same Bash call and passes it by an unexpanded variable,
    # so at PreToolUse time no file exists to read. The first version of this
    # hook was silent on its own motivating command; these pin that it is not.
    ([PROMPT],
     bash("SC=/tmp/scratch\n"
          "cat > \"$SC/issue-ex04.md\" <<'BODY'\n"
          + body_with(INVENTED + "...") + "\n"
          "BODY\n"
          "gh issue create --repo Morrison-Lab/mlg --title \"t\" "
          "--body-file \"$SC/issue-ex04.md\""),
     True,
     "#3779 verbatim: a heredoc body passed by an unexpanded $VAR warns"),
    ([PROMPT, MD5_RUN],
     bash("cat > \"$SC/b.md\" <<'BODY'\n" + body_with(REAL_MD5) + "\nBODY\n"
          "gh issue create -R o/r -t T --body-file \"$SC/b.md\""),
     False,
     "the same heredoc shape carrying a MEASURED digest stays quiet"),
    ([PROMPT],
     bash('gh issue create -R o/r -t T -b "md5 ' + INVENTED + 'aabbcc here"'), True,
     "gh issue create -b: the short literal flag the comment surface already read"),
    ([PROMPT],
     bash('gh pr create -b "md5 ' + INVENTED + 'aabbcc here"'), True,
     "gh pr create -b warns, so the pr arm of RX_CREATE_POST is pinned"),
    ([PROMPT],
     bash('gh issue edit 3 -R o/r -b "md5 ' + INVENTED + 'aabbcc here"'), True,
     "gh issue edit -b warns, so the edit arm of RX_CREATE_POST is pinned"),
    ([PROMPT],
     bash('glab issue create -d "md5 ' + INVENTED + 'aabbcc here"'), True,
     "glab spells the body -d/--description, which no gh-shaped regex matches"),
    ([PROMPT],
     bash('glab mr create --description "md5 ' + INVENTED + 'aabbcc here"'), True,
     "glab mr create --description warns, so the mr arm is pinned"),

    # --- ordinary prose must not supply the digest keyword -------------------
    ([PROMPT],
     mcp("mcp__github__add_issue_comment",
         "We shall keep the cafebabe1 fixture.\n\n" + MARKER), False,
     "'shall' must not match the `sha` keyword -- unanchored, it did"),
    ([PROMPT],
     mcp("mcp__github__add_issue_comment",
         "See shared/coding/ascii.md and deadbeef1 here.\n\n" + MARKER), False,
     "'shared/' must not match `sha`; this corpus writes it constantly"),
    ([PROMPT],
     mcp("mcp__github__add_issue_comment",
         "Avoid using 1234abcd as the seed.\n\n" + MARKER), False,
     "'Avoid' must not match the `oid` keyword"),

    # --- the URL exemption must survive a realistic path length -------------
    ([PROMPT],
     mcp("mcp__github__add_issue_comment",
         "See https://raw.githubusercontent.com/Morrison-Lab/ai-config/"
         "40b91d4488b33cd3eb9b8172c21a1d5cf902f0bf/hooks/x.py\n\n" + MARKER), False,
     "a permalink whose path exceeds KEYWORD_WINDOW keeps the URL exemption"),
    ([PROMPT],
     mcp("mcp__github__add_issue_comment",
         "See https://gitlab.com/morrison-lab/teaching/ai-config/-/commit/"
         "40b91d4488b33cd3eb9b8172c21a1d5cf902f0bf\n\n" + MARKER), False,
     "a nested-group GitLab commit URL keeps it too"),

    # --- a 40-character sha1 is the commonest digest in a git workflow -------
    ([PROMPT],
     mcp("mcp__github__add_issue_comment",
         "Reverted 40b91d4488b33cd3eb9b8172c21a1d5cf902f0bf.\n\n" + MARKER), True,
     "a bare 40-character sha1 warns on canonical length alone"),
    ([PROMPT, tool_result("HEAD is 40b91d4488b33cd3eb9b8172c21a1d5cf902f0bf")],
     mcp("mcp__github__add_issue_comment",
         "Reverted 40b91d4488b33cd3eb9b8172c21a1d5cf902f0bf.\n\n" + MARKER), False,
     "the same sha1, measured, is silent"),

    # --- the transcript's real record shape ---------------------------------
    ([PROMPT, {"type": "user", "toolUseResult": {"stdout": f"MD5 = {REAL_MD5}"},
               "message": {"content": [{"type": "tool_result", "content": "(truncated)"}]}}],
     mcp("mcp__github__add_issue_comment", body_with(REAL_MD5)), False,
     "a value present only in toolUseResult.stdout still discharges"),

    # --- the three bounds, each pinned by a case only it decides ------------
    ([PROMPT],
     mcp("mcp__github__add_issue_comment",
         "The md5 column of the table is described at length in the section "
         "below, which also covers provenance and retention, and cafebabe1 is "
         "the fixture name." + MARKER), False,
     "a digest word more than KEYWORD_WINDOW characters before the token does "
     "not reach it -- widening the window would make this a hit"),
    ([PROMPT],
     mcp("mcp__github__add_issue_comment",
         "The blob is " + "a1" * 60 + " in full." + MARKER), False,
     "a hex run longer than MAX_HEX is not a digest shape -- raising the cap "
     "would make an arbitrary long hex dump a hit"),
    ([PROMPT],
     mcp("mcp__github__add_issue_comment",
         "See https://example.com/x and then md5 " + INVENTED + "aabbcc here." + MARKER),
     True,
     "a URL EARLIER on the line does not exempt a token outside it -- without "
     "the $ anchor the exemption would swallow this"),

    ([PROMPT],
     mcp("mcp__github__add_issue_comment",
         "The env var is DEADBEEFDEADBEEFDEADBEEFDEADBEEFXYZ in the config."
         + MARKER), False,
     "a canonical-length hex PREFIX of a longer alphanumeric identifier is not "
     "a digest -- the trailing boundary must exclude any alphanumeric, not "
     "just another hex character"),
    ([PROMPT],
     mcp("mcp__github__add_issue_comment",
         "Token zzDEADBEEFDEADBEEFDEADBEEFDEADBEEF ends the line." + MARKER), False,
     "the same on the leading side, which the lookbehind already covered"),

    # --- out of scope ---------------------------------------------------------
    ([PROMPT],
     bash("git log --oneline -5"), False,
     "a command that posts no body is out of scope"),
    ([PROMPT],
     bash("gh pr review 5 -R Morrison-Lab/mlg --approve"), False,
     "a review with no body flag posts no prose"),

    # --- the pin surface (ai-config#3392) -------------------------------------
    # The 2026-09-20 recurrence on Lacaedemon/sparta#1615: the gate printed the
    # abbreviated head, and a 40-character value was padded out from it.
    ([PROMPT, HEAD_RUN],
     bash(f"gh api -X PUT repos/L/s/pulls/1615/update-branch "
          f"-f expected_head_sha={PADDED_HEAD}"), True,
     "#3392: a pin padded out from an abbreviation the gate printed warns"),
    ([PROMPT, HEAD_RUN],
     bash(f"gh pr merge 1615 -R L/s --squash --match-head-commit {PADDED_HEAD}"),
     True,
     "the same fabrication through --match-head-commit warns"),
    ([PROMPT],
     bash(f"gh api -X PUT repos/L/s/pulls/1/update-branch "
          f"-f expected_head_sha={'b' * 40}"), True,
     "a pin invented outright, with no observed prefix, warns"),
    ([PROMPT, HEAD_RUN],
     {"tool_name": "mcp__github__update_pull_request_branch",
      "tool_input": {"owner": "L", "repo": "s", "pullNumber": 1,
                     "expectedHeadSha": PADDED_HEAD}}, True,
     "the MCP spelling carries the pin as a named parameter and warns"),

    # A correctly-read pin must stay silent, or the guard gets switched off.
    ([PROMPT, HEAD_FULL_RUN],
     bash(f"gh api -X PUT repos/L/s/pulls/1615/update-branch "
          f"-f expected_head_sha={REAL_HEAD}"), False,
     "the full head the session actually read is silent"),
    ([PROMPT, HEAD_FULL_RUN],
     bash(f"gh pr merge 1615 -R L/s --squash --match-head-commit {REAL_HEAD}"),
     False,
     "the same real value through --match-head-commit is silent"),
    ([PROMPT, tool_result(f"head={REAL_HEAD} base=main state=OPEN")],
     bash(f"gh pr merge 1 -R L/s --squash --match-head-commit {REAL_HEAD}"),
     False,
     "a head read as part of a wider --jq line still discharges the pin"),
    ([PROMPT, {"type": "user", "message": {"content":
      f"merge it, the head is {REAL_HEAD}"}}],
     bash(f"gh pr merge 1 -R L/s --squash --match-head-commit {REAL_HEAD}"),
     False,
     "a head the USER supplied is measured -- it entered from outside the model"),
    ([PROMPT, assistant_says_hash(REAL_HEAD)],
     bash(f"gh pr merge 1 -R L/s --squash --match-head-commit {REAL_HEAD}"),
     True,
     "the model's OWN prior assertion does not discharge a pin either"),
    ([PROMPT, HEAD_RUN],
     bash("gh api -X PUT repos/L/s/pulls/1/update-branch "
          "-f expected_head_sha=\"$PINNED\""), False,
     "a pin passed via a shell variable carries no literal SHA to check"),
    ([PROMPT, HEAD_RUN],
     bash(f"gh pr view 1615 -R L/s --json headRefOid"), False,
     "a command that merely READS the head is not a pin"),

    # --- pin regressions found by adversarial review -------------------------
    ([PROMPT, HEAD_FULL_RUN],
     bash(f"gh pr merge 100 -R o/r --match-head-commit {REAL_HEAD} && "
          f"gh pr merge 200 -R o/r --match-head-commit {'b' * 40}"), True,
     "a MEASURED pin first must not mask a fabricated one after it -- "
     "`search` stops at the first match where `finditer` does not"),
    ([PROMPT, HEAD_RUN],
     bash(f"# old attempt: gh pr merge 5 -R o/r --match-head-commit {'b' * 40}\n"
          f"echo done"), False,
     "a commented-out command never runs and must not warn"),
    ([PROMPT, HEAD_RUN],
     bash("cat > skills/example/SKILL.md <<'EOF'\n"
          f"Example: `gh pr merge N --match-head-commit {'b' * 40}`\n"
          "EOF"), False,
     "a heredoc DOCUMENTING the command is prose, not an invocation -- this "
     "corpus writes such examples constantly"),
    ([PROMPT, HEAD_RUN],
     bash(f"gh pr merge 1 -R o/r#1 --match-head-commit {'b' * 40}"), True,
     "a `#` inside a word is not a comment introducer and must not blind the scan"),
    # The corpus's own canonical merge shape: `Closes #N` inside a quoted
    # --body, with the pin AFTER it on the same line. A quote-unaware comment
    # stripper discards everything from that `#` onward and goes silent on
    # exactly the command this guard exists for.
    ([PROMPT, HEAD_RUN],
     bash(f'gh pr merge 1 -R o/r --body "Closes #123" '
          f"--match-head-commit {'b' * 40}"), True,
     "a `#` INSIDE a quoted --body must not blind the scan to a pin after it"),
    ([PROMPT, HEAD_RUN],
     bash(f"gh pr merge 1 -R o/r --body 'closes #123' "
          f"--match-head-commit {'b' * 40}"), True,
     "the same with single quotes"),
    # The mirror: blanking quoted content to find the comment would destroy a
    # QUOTED pin, which is how the corpus actually writes the flag.
    ([PROMPT, HEAD_RUN],
     bash(f'gh pr merge 1 -R o/r --squash --match-head-commit "{"b" * 40}"'),
     True,
     "a QUOTED pin is still scanned -- blanking quotes outright would lose it"),
    ([PROMPT, HEAD_FULL_RUN],
     bash(f'gh pr merge 1 -R o/r --body "Closes #7" '
          f'--match-head-commit "{REAL_HEAD}"'), False,
     "and a quoted, correctly-read pin beside a quoted `#` stays silent"),
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


def check_pin_warning_distinguishes_padding():
    """The pin warning must say WHICH failure it is, not merely that one occurred.

    Fire-or-quiet cannot reach this: padded and invented-outright both fire, so
    a mutation that collapses the two changes no verdict and every case above
    still passes. The distinction is the actionable half -- "you padded
    `d4691095`" names the remedy, "this is unmeasured" does not -- so it gets
    an assertion of its own.
    """
    padded = run([PROMPT, HEAD_RUN],
                 bash(f"gh pr merge 1 -R L/s --match-head-commit {PADDED_HEAD}"))
    invented = run([PROMPT, HEAD_RUN],
                   bash(f"gh pr merge 1 -R L/s --match-head-commit {'b' * 40}"))
    pctx = (padded.get("hookSpecificOutput") or {}).get("additionalContext") or ""
    ictx = (invented.get("hookSpecificOutput") or {}).get("additionalContext") or ""
    ok = ("d4691095" in pctx and "padded" in pctx.lower()
          and "padded" not in ictx.lower()
          # The misdiagnosis is the reason this surface warrants its own note.
          and "422" in pctx and "concurrent writer" in pctx)
    print(f"{'ok  ' if ok else 'FAIL'}  the pin warning names the padded "
          f"prefix, and says so ONLY when a prefix was observed")
    return 0 if ok else 1


def check_pin_does_not_suppress_body_finding():
    """A pin and a body digest in one command are independent findings.

    The first implementation returned as soon as the pin fired, so a chained
    call carrying both reported only the pin -- and the body finding, which
    has a different remedy, was silently dropped. Fire-or-quiet cannot reach
    this either: the call fires either way.
    """
    out = run([PROMPT, HEAD_RUN],
              bash(f"gh api -X PUT repos/o/r/pulls/1/update-branch "
                   f"-f expected_head_sha={PADDED_HEAD} && "
                   f'gh issue create -R o/r --body "commit {INVENTED}... fixed it"'))
    ctx = (out.get("hookSpecificOutput") or {}).get("additionalContext") or ""
    ok = PADDED_HEAD in ctx and INVENTED in ctx
    print(f"{'ok  ' if ok else 'FAIL'}  a pin finding does not suppress an "
          f"unmeasured digest in the same command's body")
    return 0 if ok else 1


def check_dry_run_warns_on_pin():
    """`--dry-run` must reach the pin surface, or the affordance is inert there."""
    out = run([], bash(f"gh pr merge 1 -R o/r --match-head-commit {'b' * 40}"),
              extra_args=("--dry-run",))
    ctx = (out.get("hookSpecificOutput") or {}).get("additionalContext") or ""
    ok = "b" * 40 in ctx and "pin" in ctx.lower()
    print(f"{'ok  ' if ok else 'FAIL'}  --dry-run warns on an unmeasured pin")
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


def check_dry_run_warns():
    """`--dry-run '<command>'` must be able to warn, or the affordance is inert.

    It supplies no transcript, so a fail-open reading of "no transcript" makes
    the flag silent under every input -- which is what the first version did.
    """
    import subprocess
    ok = True
    for cmd, want in (
            ('gh issue create -R o/r --body "md5 3e2b9e10aabbcc"', True),
            ('gh issue create -R o/r --body "Canvas assignment 10134103"', False)):
        r = subprocess.run([sys.executable, HOOK, '--dry-run', cmd],
                           capture_output=True, text=True)
        out = json.loads(r.stdout) if r.stdout.strip() else {}
        fired = bool((out.get('hookSpecificOutput') or {}).get('additionalContext'))
        ok = ok and (fired == want)
    print(f"{'ok  ' if ok else 'FAIL'}  --dry-run warns on an unmeasured digest "
          f"and stays quiet on a decimal id")
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
    # Derived, not hand-maintained: the previous `len(CASES) + 3` constant went
    # stale the moment a fourth check was added, and the suite then under-
    # reported its own size. A list cannot drift from the calls it holds.
    ADHOC = [
        check_output_shape,
        check_pin_warning_distinguishes_padding,
        check_pin_does_not_suppress_body_finding,
        check_dry_run_warns_on_pin,
        check_unreadable_transcript_is_silent,
        check_dry_run_warns,
    ]
    for check in ADHOC:
        failures += check()
    if SHAPE_ERRORS:
        failures += 1
        print(f"FAIL  {len(SHAPE_ERRORS)} payload(s) had no surfacing field: "
              f"{SHAPE_ERRORS}")
    print(f"\n{len(CASES) + len(ADHOC)} checks, {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
