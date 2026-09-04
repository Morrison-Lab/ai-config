"""Test the no-stale-pr-status guard.

The guard's whole value is the third case below: a message that honestly
reports work in flight ("checks are running") must NOT be blocked. A guard
that fires on honest status reporting gets disabled, and then the case it
exists for goes unprotected too.

Run: python3 hooks/test-no-stale-pr-status.py hooks/no-stale-pr-status.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

PUSH = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {"command": "git push -q"}}]}}
QUERY = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {"command": "gh pr checks 493 -R o/r"}}]}}
MCP_QUERY = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {"method": "get_check_runs", "pullNumber": 493}}]}}
# An MCP write carries its verb in the tool NAME, not in the input -- verified
# against real transcripts, where the input holds only owner/repo/branch/files.
# So a scan reading the input alone never sees this as a push.
MCP_PUSH = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "mcp__github__push_files",
     "input": {"owner": "o", "repo": "r", "branch": "main",
               "files": [{"path": "f.py", "content": "x"}]}}]}}


SENTINEL_PREFIX = ".claude-stale-status-"


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


CHECK_CLEAN_QUERY = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "t1", "name": "run_command", "input": {"command": "python3 scripts/check-pr-fully-clean.py 1167"}}]}}
CHECK_CLEAN_FAIL_RESULT = {"type": "user", "message": {"content": [
    {"type": "tool_result", "tool_use_id": "t1", "content": "\u274c PR is NOT fully clean:\n  - Check run 'validate' is still in status 'in_progress'"}]}}

READ_FILE_QUERY = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "t2", "name": "view_file", "input": {"AbsolutePath": "/path/to/scripts/check-pr-fully-clean.py"}}]}}
READ_FILE_RESULT = {"type": "user", "message": {"content": [
    {"type": "tool_result", "tool_use_id": "t2", "content": "print('\u274c PR is NOT fully clean:')"}]}}

# (events, should_block, label)
CASES = [
    ([QUERY, PUSH, say("493 is green, conflict-free.")], True,
     "the real incident: queried, pushed, then claimed green"),
    ([QUERY, PUSH, say("11 pass, 0 fail -- ready to merge.")], True,
     "counts quoted from a pre-push reading"),
    ([QUERY, PUSH, say("All checks green at this head.")], True,
     "'all green' after a push"),
    ([QUERY, MCP_PUSH, say("All checks green, ready to merge.")], True,
     "an MCP push_files is a push -- the reading predates it"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT, say("PR #1167 is fully clean.")], True,
     "claiming fully clean when check-pr-fully-clean.py returned NOT fully clean"),

    ([READ_FILE_QUERY, READ_FILE_RESULT, say("Checked the file contents.")], False,
     "reading script source containing failure text must not trip query block"),

    ([PUSH, QUERY, say("493 is green: 11 pass.")], False,
     "queried AFTER the push -- the claim is current"),
    ([MCP_PUSH, QUERY, say("493 is green: 11 pass.")], False,
     "queried after the MCP push -- the same claim is current"),
    ([PUSH, MCP_QUERY, say("All green, 0 fail.")], False,
     "MCP get_check_runs counts as a query too"),
    ([QUERY, PUSH, say("Pushed the fix; checks are running now.")], False,
     "honest in-flight reporting must not be blocked"),
    ([QUERY, PUSH, say("Waiting on test-coverage and docs; will report when settled.")], False,
     "naming pending checks is not an assertion of green"),
    ([QUERY, say("All checks green.")], False,
     "nothing pushed, so no reading can have gone stale"),
    ([PUSH, QUERY, say("Merged and tidied up.")], False,
     "no status assertion at all"),

    ([QUERY, PUSH, say("PR #1689 is not fully clean -- the review check is still running.")], False,
     "negated assertion in the same clause must not block"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("check-pr-fully-clean.py currently reports NOT clean (correctly "
          "-- it only counts bot-authored verdicts toward its own 'fully "
          "clean' determination by design).")], False,
     "negation in an earlier clause of the same sentence, ASSERT phrase used referentially"),
    ([QUERY, PUSH, say("Not ready to merge yet; still waiting on CI.")], False,
     "negated 'ready to merge' must not block"),
    ([QUERY, PUSH, say("493 isn't fully clean yet.")], False,
     "contraction negation must not block -- the ASSERT phrase has to actually "
     "appear in the sentence (isn't green never matches RX_ASSERT at all, so "
     "that phrasing alone doesn't exercise the n't path)"),
    ([QUERY, PUSH, say("This is green. Not fully clean, though -- one check is still pending.")], True,
     "an unnegated assertion earlier in the message still blocks even when a later sentence is negated"),
    ([QUERY, PUSH, say("Pushed. No findings remain, so the PR is ready to merge.")], True,
     "bare 'no' attached to a different noun must not suppress the guard -- "
     "this is a genuine stale-clean claim"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("There are no unresolved threads and #1689 is fully clean.")], True,
     "bare 'no' earlier in the sentence must not suppress an unrelated ASSERT phrase"),

    ([QUERY, PUSH, say("| #1690 | not clean |\n| #1689 | ready to merge |")], True,
     "a bare newline must count as a sentence boundary -- a negation on one "
     "table row must not suppress an unrelated claim on the next row"),
    ([QUERY, PUSH, say("- #1690 not clean\n- #1689 ready to merge")], True,
     "same as above for a bulleted list"),
    ([QUERY, PUSH, say("**Not clean yet.** All checks green now.")], True,
     "markdown bold-close punctuation right after the terminator must not "
     "swallow the sentence boundary"),
    ([QUERY, PUSH, say('Quoting the review: "not clean." All checks green now.')], True,
     "a closing quote right after the terminator must not swallow the "
     "sentence boundary either"),

    ([QUERY, PUSH, say("PR #1 is not clean; PR #2 is fully clean.")], True,
     "a semicolon-joined clause is its own sentence boundary too -- a "
     "negation before the ';' must not suppress an unrelated genuine "
     "stale-clean claim after it (ai-config#1770)"),

    # ai-config#3038. A retraction puts the claim first and the correction
    # after it, so a prefix-only negation scan reads a withdrawal as a fresh
    # assertion -- and the retraction vocabulary is not negation vocabulary.
    ([QUERY, PUSH, say('But "fully clean" was wrong too, and for a third reason.')], False,
     "the measured sentence: a retraction quoting the phrase it retracts"),
    ([QUERY, PUSH, say('My earlier "ready to merge" call was incorrect.')], False,
     "retraction vocabulary AFTER the phrase, in the same sentence"),
    ([QUERY, PUSH, say("I overstated the 11 pass reading.")], False,
     "retraction vocabulary BEFORE the phrase, with no clause break between"),
    ([QUERY, PUSH, say('The reviewer is wrong that #1689 is conflict-free.')], False,
     "'is wrong' is a retraction even without a first-person subject -- the "
     "measured sentence has none either, so the source hook's first-person "
     "anchor cannot be ported"),
    ([QUERY, PUSH, say('My earlier "fully clean" call\nwas wrong.')], False,
     "a retraction wrapped onto the next line under semantic line breaks -- "
     "the trailing scan must not stop at a bare newline"),

    ([QUERY, PUSH, say("All checks green. My earlier count was wrong, but that is "
                       "a separate claim.")], True,
     "a retraction in a LATER sentence must not suppress an unnegated claim"),

    # The attachment guard. Each of these puts retraction vocabulary in the
    # same sentence as a genuine stale-clean claim, in a DIFFERENT clause.
    # Delete RX_CLAUSE_SEPARATOR and every one of them stops blocking.
    ([QUERY, PUSH, say("PR #1689 is fully clean -- the earlier blocker was inaccurate.")], True,
     "a prose dash separates the retraction from the claim"),
    ([QUERY, PUSH, say("The reviewer was wrong about the lint failure, but all "
                       "checks green.")], True,
     "a comma and 'but' separate a leading third-person retraction from the claim"),
    ([QUERY, PUSH, say("All checks green, but the reviewer overstated the risk.")], True,
     "'overstated' in a trailing 'but' clause retracts nothing about the claim"),
    ([QUERY, PUSH, say("All checks green after I misread the earlier log.")], True,
     "a subordinating conjunction separates a first-person retraction too"),
    ([QUERY, PUSH, say("| #1689 | fully clean |\n| #1690 | my count was wrong |")], True,
     "a table cell boundary separates the rows -- the trailing scan crosses a "
     "bare newline, so the markdown boundary is what has to stop it here"),
    ([QUERY, PUSH, say("#1689 is fully clean after the reviewer confirmed every "
                       "finding was addressed, including the one about the wrong "
                       "variable name.")], True,
     "an unrelated 'wrong' several clauses away must not suppress a genuine claim"),

    # Attachment reads the two directions separately, and each direction has
    # its own failure. Trailing first: a retraction that does not attach says
    # nothing about a LEADING one that does, so the trailing verdict must not
    # short-circuit the leading scan. Make the trailing scan return its verdict
    # instead of falling through and this stops allowing.
    ([QUERY, PUSH, say("I was wrong that #1689 is fully clean, and the count "
                       "was overstated too.")], False,
     "a leading retraction survives an unrelated trailing retraction word in "
     "the same clause"),
    # Leading second: a retraction states its claim as its own object, and
    # `when` is the complementizer for that, so the leading scan alone drops it.
    # Set RX_LEADING_SEPARATOR to RX_CLAUSE_SEPARATOR and this stops allowing.
    ([QUERY, PUSH, say("I was wrong when I said all checks green.")], False,
     "'wrong when I said' is one clause -- the plainest correction there is"),
    # `because` deliberately still breaks, in BOTH directions: it introduces a
    # reason rather than the retraction's object, so the claim still stands.
    ([QUERY, PUSH, say("All checks green because the earlier reading was "
                       "wrong.")], True,
     "a reason clause is not a retraction of the claim it explains"),
    # `when` is the only direction-asymmetric separator. `:` breaks attachment
    # in BOTH directions, so it needs a blocking case on each side. Delete `:`
    # from _CLAUSE_SEPARATORS and all three below stop blocking -- silently,
    # since a suppressed guard emits nothing.
    ([QUERY, PUSH, say("All checks green: the earlier reviewer was wrong.")], True,
     "a colon separates a trailing retraction from the claim"),
    # The leading pair. A colon after a retraction introduces the CORRECTED
    # claim at least as often as the retracted one, and that reading is a fresh
    # stale-clean assertion. Put `:` back in RX_CLAUSE_SEPARATOR alone and both
    # of these stop blocking while the trailing case above stays green.
    ([QUERY, PUSH, say("I was wrong: all checks green now.")], True,
     "a colon after a retraction introduces a fresh claim, not the withdrawn "
     "one -- the same sentence with a period blocks, so the colon must too"),
    ([QUERY, PUSH, say("Correcting my earlier status: #1689 is fully clean.")], True,
     "correcting an earlier status is not retracting the claim that follows "
     "the colon"),

    # Round 3 review. A prose dash is a clause separator too, and listing only
    # the ASCII double hyphen made the verdict turn on one keystroke: the
    # `--` case above blocked while every other spelling of the same sentence
    # allowed, which is the silent direction. Delete the dash alternative from
    # _CLAUSE_SEPARATORS and all four of these stop blocking.
    ([QUERY, PUSH, say("PR #1689 is fully clean - the earlier blocker was "
                       "inaccurate.")], True,
     "a spaced single hyphen separates the retraction from the claim"),
    ([QUERY, PUSH, say("PR #1689 is fully clean \u2014 the earlier blocker was "
                       "inaccurate.")], True,
     "so does an em-dash -- assistant prose is not held to this repo's "
     "ASCII-punctuation rule, so the guard has to read the glyph"),
    ([QUERY, PUSH, say("PR #1689 is fully clean \u2013 the earlier blocker was "
                       "inaccurate.")], True,
     "so does an en-dash"),
    ([QUERY, PUSH, say("I was wrong \u2014 all checks green now.")], True,
     "the dash is shared like the colon: after a retraction it introduces the "
     "corrected claim, which is a fresh stale-clean assertion"),
    # The whitespace requirement on the ASCII hyphen is what keeps a hyphenated
    # word from reading as a clause break. Drop it and this stops allowing.
    ([QUERY, PUSH, say("I overstated the pre-push reading of all checks green.")], False,
     "an unspaced hyphen inside a word is not a clause separator"),
    ([QUERY, PUSH, say("All checks green / the earlier note was wrong.")], True,
     "a spaced slash separates them too"),
    ([QUERY, PUSH, say("All checks green \u2192 the earlier note was wrong.")], True,
     "so does an arrow"),
    ([QUERY, PUSH, say("All checks green \u2026 the earlier note was wrong.")], True,
     "so does an ellipsis glyph, which the ASCII spelling already handled "
     "through the sentence-break scan"),

    # `now that` is a reason connective like `because`, and only the two-word
    # spelling is one -- a bare `now` separates nothing. Delete it from
    # _CLAUSE_SEPARATORS and this stops blocking.
    ([QUERY, PUSH, say("All checks green now that the earlier reading was "
                       "wrong.")], True,
     "'now that' introduces a reason, so the claim it explains still stands"),

    # The relative pronouns join `when` in the trailing-only set: after the
    # claim they open a clause about a different noun, so they break there.
    # Delete each from _TRAILING_ONLY_SEPARATORS and its case stops blocking.
    ([QUERY, PUSH, say("#1689 is fully clean where the earlier note was "
                       "wrong.")], True,
     "'where' opens a clause about a different proposition"),
    ([QUERY, PUSH, say("#1689 is fully clean per the note which was wrong.")], True,
     "'which' modifies the note, not the claim"),
    ([QUERY, PUSH, say("#1689 is fully clean per the reviewer who was wrong.")], True,
     "'who' modifies the reviewer, not the claim"),
    ([QUERY, PUSH, say("#1689 is fully clean per the reviewer whose note was "
                       "wrong.")], True,
     "'whose' modifies the reviewer's note, not the claim"),
    ([QUERY, PUSH, say("All checks green according to the reviewer whom I "
                       "earlier said was wrong.")], True,
     "'whom' likewise"),
    # And the other direction, which is why they are trailing-only rather than
    # shared. Move either into _CLAUSE_SEPARATORS alone and these stop allowing.
    ([QUERY, PUSH, say("I was wrong where I said all checks green.")], False,
     "before the claim a relative pronoun takes it as the retraction's own "
     "object, exactly as 'when' does"),
    ([QUERY, PUSH, say("Correcting my earlier status which claimed all checks "
                       "green.")], False,
     "same for 'which'"),
    # `that` is the commonest word on either side of that split, so leaving it
    # out left the guard switchable off by one word. Delete it from
    # _TRAILING_ONLY_SEPARATORS and the two blocking cases stop blocking; move
    # it into _CLAUSE_SEPARATORS and the two allow cases stop allowing.
    ([QUERY, PUSH, say("#1689 is fully clean per the note that was wrong.")], True,
     "'that' is a restrictive relative pronoun after the claim -- it modifies "
     "the note, exactly as 'which' does"),
    ([QUERY, PUSH, say("All checks green per the check that was mistaken.")], True,
     "same shape without a PR number"),
    ([QUERY, PUSH, say("I was wrong that all checks green.")], False,
     "before the claim 'that' is the complementizer taking it as the "
     "retraction's own object"),

    # `until` is a time connective like `after` and `before` beside it, so a
    # retraction reaching across it is about a different proposition. Its
    # terminative sense is a separate question this guard does not read: only
    # the retraction vocabulary withdraws a claim, so a claim bounded by a time
    # is still a claim. Delete `until` from _CLAUSE_SEPARATORS and this stops
    # blocking.
    ([QUERY, PUSH, say("All checks green until I noticed my earlier count was "
                       "overstated.")], True,
     "what follows 'until' is a time, so the retraction here is about the "
     "earlier COUNT rather than about the claim -- not because a bounded "
     "claim still holds, which 'until' in fact denies"),

    # A bracketed aside is a parenthesized one in the other bracket style, and
    # pinning only the parens let the verdict turn on which style was typed.
    # Delete the parens from _CLAUSE_SEPARATORS, or the brackets from
    # _TRAILING_ONLY_SEPARATORS, and the matching case stops blocking.
    ([QUERY, PUSH, say("All checks green (the earlier note was wrong).")], True,
     "a parenthesized aside is about the note, not the claim"),
    ([QUERY, PUSH, say("All checks green [the earlier note was wrong].")], True,
     "so is the same aside in square brackets"),
    # Before the claim a bracketed span is USUALLY markdown, so a citation
    # inside a leading retraction must not read as an aside. RX_MARKDOWN_SPAN
    # deletes the markdown shapes from the connector; delete that sub and all
    # three of these stop allowing, which blocks a plain retraction -- the
    # class ai-config#3038 was filed to stop blocking.
    ([QUERY, PUSH, say("Retracting the status [#1689][pr] all checks green.")], False,
     "a reference-style markdown link inside a leading retraction is not a "
     "clause break"),
    ([QUERY, PUSH, say("I misread [^1] all checks green.")], False,
     "nor is a footnote marker"),
    ([QUERY, PUSH, say("I was wrong in [the note](http://x/y) that said all "
                       "checks green.")], False,
     "nor is an inline link, whose parens would otherwise break the "
     "connector too"),
    # Deleting the markdown rather than exempting the bracket CHARACTER is
    # what keeps the two aside styles in step. Take the brackets back out of
    # _CLAUSE_SEPARATORS and the first two stop blocking while the paren case
    # keeps blocking, which is the same style-dependent verdict the trailing
    # pair above was written to remove.
    ([QUERY, PUSH, say("[The earlier note was wrong] all checks green.")], True,
     "a leading bracketed aside is a clause break, exactly as the paren one "
     "below is -- it retracts the note and then asserts a fresh green state"),
    ([QUERY, PUSH, say("(The earlier note was wrong) all checks green.")], True,
     "the identical sentence in parens, pinned beside it so the two families "
     "cannot diverge again unnoticed"),
    ([QUERY, PUSH, say("The earlier reading was wrong [ci] all checks green "
                       "now.")], True,
     "a bare bracketed token is not one of the markdown shapes, so it stays "
     "an aside -- nothing distinguishes a shortcut link from one"),
    # The sub runs on the trailing connector too, for the same reason: with the
    # brackets shared, a citation between the claim and its retraction would
    # read as an aside. Drop the sub from the trailing branch alone and this
    # stops allowing.
    ([QUERY, PUSH, say('My earlier "ready to merge" call [^1] was '
                       'incorrect.')], False,
     "a footnote marker between the claim and its retraction is not an aside "
     "either"),

    # The head noun of a trailing relative clause is USUALLY some other noun,
    # which is what puts the relative pronouns in the trailing-only set. When
    # it refers back to the claim instead, the clause withdraws exactly the
    # claim, so RX_METALINGUISTIC_HEAD drops that head phrase from the
    # connector. Delete the RX_METALINGUISTIC_HEAD.sub call and all three of
    # these stop allowing.
    ([QUERY, PUSH, say("All checks green is a claim that was wrong.")], False,
     "the head noun refers back to the claim, so the relative clause retracts "
     "it rather than modifying some other noun"),
    ([QUERY, PUSH, say("#1689 is fully clean is the line that was wrong.")], False,
     "same shape naming the line rather than the claim"),
    ([QUERY, PUSH, say("All checks green is a claim which was wrong.")], False,
     "the hole predates 'that' -- the 'which' spelling blocked from the round "
     "that added the relative pronouns"),
    ([QUERY, PUSH, say("All checks green is a claim that was overstated.")], False,
     "an auxiliary may sit between the pronoun and the retraction -- a bare "
     "\\Z anchor on RX_METALINGUISTIC_HEAD blocks this participle form"),
    # Only the head phrase is dropped, never the rest of the connector. Widen
    # the carve-out to swallow the whole connector and this stops blocking.
    ([QUERY, PUSH, say("All checks green is a claim that survives, though my "
                       "count was wrong.")], True,
     "a separator past the head phrase still breaks attachment"),
    # The carve-out must also REACH the retraction. Unanchor its right end and
    # both of these stop blocking: the head noun matches, so the phrase is
    # stripped, while the relative clause is about a different noun entirely.
    ([QUERY, PUSH, say("#1689 is fully clean is the note that the reviewer "
                       "misread.")], True,
     "an object relative puts its own subject after the pronoun, so the error "
     "sits on the reviewer and the claim still stands"),
    ([QUERY, PUSH, say("All checks green is the reading that the earlier "
                       "reviewer overstated.")], True,
     "same shape with a different head noun and retraction verb"),

    # The copula guard. Attributive "wrong" sits in the SAME clause as the
    # claim, so attachment cannot rule it out; only the copula requirement can.
    # Delete the `(?:was|were|is|are)\s+` prefix from RX_RETRACTION and this
    # stops blocking.
    ([QUERY, PUSH, say("All checks green with the wrong path fixed.")], True,
     "attributive 'wrong' in the same clause is not a retraction -- the "
     "copula is required"),

    # Plain negation stays scoped to the text BEFORE the phrase. Reading it
    # after the phrase too silently disabled the guard on the archetypal recap
    # shape, where the negation is about something other than the claim.
    ([QUERY, PUSH, say("All checks green at this head, and I have not merged it yet.")], True,
     "a trailing plain negation about a different clause must not suppress "
     "the claim"),
    ([QUERY, PUSH, say("#1689 is fully clean and there are no findings I did not "
                       "address.")], True,
     "nor must a trailing 'did not' -- this is the phrasing the RX_NEGATION "
     "comment says the guard must keep catching"),
]


def run(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    # The guard fires once per distinct message; clear sentinels so repeated
    # runs of this suite stay deterministic.
    for f in os.listdir(tempfile.gettempdir()):
        if f.startswith(SENTINEL_PREFIX):
            try:
                os.remove(os.path.join(tempfile.gettempdir(), f))
            except OSError:
                pass
    out = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"transcript_path": path}),
        capture_output=True, text=True,
    ).stdout.strip()
    os.remove(path)
    return bool(out)




# ai-config#1859: the WORDING must match what was actually detected.
# A bare "<n> pass" with no PR reference near it may well be a local test-suite
# count, and asserting it is "a PR's check state" was wrong three times
# ("10 pass", "30 pass", "33 pass"). The staleness verdict is unchanged --
# only the sentence describing the match. Asserted here rather than in CASES
# because CASES compares fire/no-fire and would pass either way, which is how
# a detector that is right about the important part and wrong about the
# visible part survives a green suite.
ATTRIBUTION = [
    ("Local suite: 33 pass.",
     "states a pass/fail count",
     "a bare count with no PR reference reads as possibly-local"),
    ("Tests: 33 pass. Pushed to #1919 and checks are running.",
     "asserts a PR's check state",
     "the same count near a PR reference is a check-state claim"),
    ("All checks green.",
     "asserts a PR's check state",
     "an explicit check-state phrase keeps the strong wording"),

    # Review round 1 on #1922. Both were reproduced against the hook by the
    # reviewer, and both are the SAME defect this PR removes, pointing the
    # other way: a message that is not soft at all, softened.
    ("11 pass, 0 fail -- ready to merge.",
     "asserts a PR's check state",
     "a later non-count phrase settles it, not just the first match"),
    ("PR checks: 11 pass, 0 fail.",
     "asserts a PR's check state",
     "the plain word PR counts as a nearby reference"),
    ("The pull request has 11 pass.",
     "asserts a PR's check state",
     "so does the spelled-out form"),
    ("MR checks: 11 pass, 0 fail.",
     "asserts a PR's check state",
     "the MR abbreviation counts as a nearby reference (#2667)"),
    ("The merge request !47 has 11 pass.",
     "asserts a PR's check state",
     "the spelled-out merge request and !N counts as a nearby reference (#2667)"),
]

# The REST check-runs endpoint must count as a status query. `fully-clean.md`
# mandates it over `gh pr checks`, so a guard blind to it warns precisely when
# the stronger command was used -- and tells the author to re-run the weaker
# one. Found by the guard firing on this PR's own session.
QUERY_FORMS = [
    ("gh pr checks 1922 -R Morrison-Lab/ai-config", "the gh porcelain"),
    ("gh api --paginate repos/o/r/commits/abc1234/check-runs --jq '.x'",
     "the paginated REST check-runs endpoint"),
    ("gh api repos/o/r/commits/abc1234/status", "the legacy commit-status endpoint"),
    ("gh pr view 1922 --json statusCheckRollup", "the rollup field"),
    ("glab ci status -R group/project", "GitLab glab ci status (#2667)"),
    ("glab ci list -R group/project", "GitLab glab ci list (#2667)"),
    ("glab ci view -R group/project", "GitLab glab ci view (#2667)"),
    ("glab mr view 47 -R group/project", "GitLab glab mr view (#2667)"),
    ("glab pipeline view 1234 -R group/project", "GitLab glab pipeline view (#2667)"),
    ("glab api projects/123/pipelines/456/jobs", "GitLab REST pipelines endpoint (#2667)"),
    ("glab api projects/group%2Fproject/merge_requests/47", "GitLab REST merge_requests endpoint (#2667)"),
]


def check_query_forms():
    """Every spelling of a status query must discharge the staleness warning."""
    failures = 0
    for cmd, label in QUERY_FORMS:
        events = [PUSH,
                  {"type": "assistant", "message": {"content": [
                      {"type": "tool_use", "input": {"command": cmd}}]}},
                  say("All checks green at head abc1234.")]
        fired = run(events)
        ok = not fired
        failures += 0 if ok else 1
        print(f"{'ok  ' if ok else 'FAIL'}  query-form: {label}")
    return failures


def check_attribution():
    """Each warning must describe what it matched, not what it assumed."""
    failures = 0
    for message, expected, label in ATTRIBUTION:
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w") as fh:
            for e in (QUERY, PUSH, say(message)):
                fh.write(json.dumps(e) + "\n")
        for f in os.listdir(tempfile.gettempdir()):
            if f.startswith(SENTINEL_PREFIX):
                try:
                    os.remove(os.path.join(tempfile.gettempdir(), f))
                except OSError:
                    pass
        out = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True,
        ).stdout.strip()
        os.remove(path)
        reason = (json.loads(out).get("reason") if out else "") or ""
        ok = expected in reason
        failures += 0 if ok else 1
        print(f"{'ok  ' if ok else 'FAIL'}  attribution: {label}")
    return failures


def main():
    failures = 0
    for events, want_block, label in CASES:
        got = run(events)
        ok = got == want_block
        if not ok:
            failures += 1
        print(f"{'ok  ' if ok else 'FAIL'}  "
              f"{'block' if want_block else 'allow'}: {label}")
    failures += check_attribution()
    failures += check_query_forms()
    total = len(CASES) + len(ATTRIBUTION) + len(QUERY_FORMS)
    print(f"\n{total - failures}/{total} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
