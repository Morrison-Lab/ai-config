"""Test the no-stale-pr-status guard.

The guard's whole value is the third case below: a message that honestly
reports work in flight ("checks are running") must NOT be blocked. A guard
that fires on honest status reporting gets disabled, and then the case it
exists for goes unprotected too.

Run: python3 hooks/test-no-stale-pr-status.py hooks/no-stale-pr-status.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

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

# A push ATTEMPT and the four shapes its result can take. The guard used to set
# `last_push` from the tool_use alone, so a push the harness refused counted as
# a push that happened -- invalidating a reading that was still current.
PUSH_ATTEMPT = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "p1", "input": {"command": "git push -q"}}]}}
PUSH_BLOCKED = {"type": "user", "message": {"content": [
    {"type": "tool_result", "tool_use_id": "p1", "is_error": True,
     "content": "PreToolUse:Bash [python3 hooks/no-push-without-self-review.py]"
                " hook error: git push blocked by the pre-push self-review policy"}]}}
PUSH_DENIED = {"type": "user", "message": {"content": [
    {"type": "tool_result", "tool_use_id": "p1", "is_error": True,
     "content": "Permission for this action was denied by the Claude Code"
                " auto-mode classifier."}]}}
# A non-zero EXIT is not a refusal: `git push && something-else` can fail after
# the push has already moved the branch.
PUSH_EXIT_FAILED = {"type": "user", "message": {"content": [
    {"type": "tool_result", "tool_use_id": "p1", "is_error": True,
     "content": "Exit code 1\nerror: failed to push some refs"}]}}
# The refusal wording QUOTED rather than reported. This corpus writes about
# blocked pushes constantly, so an unanchored match would read a transcript
# discussing one as a push that never ran.
PUSH_QUOTES_REFUSAL = {"type": "user", "message": {"content": [
    {"type": "tool_result", "tool_use_id": "p1",
     "content": "Exit code 0\nThe docstring says: PreToolUse:Bash hook error:"
                " git push blocked by the pre-push self-review policy"}]}}
# An explicit `is_error: false` overrides the text: a result the harness marked
# successful DID run, whatever it happens to quote. An ABSENT `is_error` is not
# read as false, so a transcript format omitting the field keeps the fix.
PUSH_MARKED_OK = {"type": "user", "message": {"content": [
    {"type": "tool_result", "tool_use_id": "p1", "is_error": False,
     "content": "PreToolUse:Bash hook error: git push blocked"}]}}
PUSH_SECOND_ATTEMPT = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "p2", "input": {"command": "git push -q"}}]}}
# Round 13, finding 9. A `content` LIST, which is the shape `_result_parts`
# exists for and which no row previously used. `RX_NEVER_RAN` anchors at `^`
# with no `re.M`, so joining the parts before searching left the anchor
# reachable only by the first one and a refusal delivered as a later part read
# as a real push. Both directions are pinned, because the anchor has to keep
# doing its job per part: the refusal STARTS the second part here, and merely
# sits inside the second part below.
PUSH_BLOCKED_PARTS = {"type": "user", "message": {"content": [
    {"type": "tool_result", "tool_use_id": "p1", "is_error": True,
     "content": [
         {"type": "text", "text": "Running git push -q"},
         {"type": "text",
          "text": "PreToolUse:Bash [python3 hooks/no-push-without-self-review.py]"
                  " hook error: git push blocked by the pre-push self-review policy"}]}]}}
PUSH_PARTS_QUOTE_REFUSAL = {"type": "user", "message": {"content": [
    {"type": "tool_result", "tool_use_id": "p1",
     "content": [
         {"type": "text", "text": "Exit code 0"},
         {"type": "text",
          "text": "The docstring says: PreToolUse:Bash hook error: git push"
                  " blocked by the pre-push self-review policy"}]}]}}


# (events, should_block, label)
CASES = [
    ([QUERY, PUSH, say("493 is green, conflict-free.")], True,
     "the real incident: queried, pushed, then claimed green"),
    ([QUERY, PUSH, say("11 pass, 0 fail -- ready to merge.")], True,
     "counts quoted from a pre-push reading"),
    ([QUERY, PUSH, say("All checks green at this head.")], True,
     "'all green' after a push"),

    # ai-config#2016: `0 fail` was unanchored, so it matched the participle
    # every test runner prints for a green suite. Its sibling
    # `\b\d+\s+pass\b` requires a boundary after `pass` and therefore
    # ignores `14 passed` -- so the two patterns matched disjoint things, and
    # the only one firing on a local mutation check was the fail rule. Fired
    # on four consecutive turns of a bcs session, each reporting a hook's own
    # test tally, none asserting anything about a pull request.
    ([QUERY, PUSH, say("Mutation check on the hook's own suite: 15 passed, "
                       "0 failed. Pushed the fix.")], False,
     "a local test-runner tally is not a PR status claim"),
    ([QUERY, PUSH, say("PR checks: 11 pass, 0 failures.")], True,
     "the CI phrasing '0 failures' still asserts"),
    ([QUERY, MCP_PUSH, say("All checks green, ready to merge.")], True,
     "an MCP push_files is a push -- the reading predates it"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT, say("PR #1167 is fully clean.")], True,
     "claiming fully clean when check-pr-fully-clean.py returned NOT fully clean"),

    # `no-incomplete-check-enumeration.py` PRESCRIBES the bare-count form as
    # the safe progress report -- its blocking message says verbatim that
    # "13 pass, 5 pending" trips nothing, and its source repeats the claim as
    # a comment. This guard's ASSERT list matched `13 pass` in that exact
    # string, so following one guard's remedy tripped the other, using the
    # first guard's own example. Measured 2026-09-24 on a message reading
    # "9 pass, 8 skipped, 2 runs still in progress, none failing", which the
    # failing-query branch blocked as a clean assertion.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("13 pass, 5 pending.")], False,
     "the sibling guard's own prescribed progress form must not block here"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("19 checks on #3928: 9 pass, 8 skipped, 2 still in progress, "
          "none failing.")], False,
     "a count in a message disclosing its own pending work is a progress report"),
    # The exemption is self-disclosure, not the presence of a count: a message
    # may disclose ONE PR's pending checks and still call ANOTHER clean, and
    # that second claim is exactly what this branch exists to catch.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("#3928 has 2 checks still in progress. #49 is fully clean.")], True,
     "disclosing one PR's pending work does not license calling another clean"),
    # ... but the exemption is blind to WHICH PR each count concerns, so a
    # bare COUNT about a second PR rides on the first PR's disclosure and
    # goes unblocked. That is the guard's actual behaviour rather than its
    # intended one -- whether to scope it by `RX_PR_NEARBY` is
    # ai-config#3968 -- and it was asserted in a comment and pinned by
    # nothing, so a scoping change would have landed with a green suite.
    # It is the counterpart of the case above: a CLEAN CLAIM about the
    # second PR blocks, a plain count about it does not.
    #
    # The mutation that kills this row and nothing else is the #3968 fix
    # itself: skip a bare count only while the message names at most one
    # PR. The obvious mutation does not reach it -- the match object is
    # `9 pass` alone, so a `#` test over `cand.group(0)` is a no-op and
    # leaves the suite fully green, and disabling the exemption outright
    # kills five rows rather than this one.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("#50 has 2 checks still in progress. 9 pass on #49.")], False,
     "a count about a second PR rides on the first PR's disclosure"),
    # ... and the exemption is scoped to THIS branch. The staleness branch
    # still fires on the sibling's prescribed form, deliberately: disclosure
    # answers "did a query report failure", not "is your reading older than
    # your push". Round 8, finding 6 --- the hook's message and README both
    # claimed the exemption unscoped, and every case above exercises the
    # failing-query branch, so nothing pinned which branch it reached.
    ([QUERY, PUSH, say("13 pass, 5 pending.")], True,
     "the disclosure exemption does not reach the staleness branch"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("9 pass.")], True,
     "a bare count with nothing disclosed still blocks"),
    # A push the harness REFUSED moved no commit, so the earlier query is not
    # stale. The guard read the tool_use and never the result, so every
    # refused push counted -- 79 of them in one session's own transcript.
    # Queries already tracked their tool_use_id and read the matching result;
    # the push side simply never did.
    ([QUERY, PUSH_ATTEMPT, PUSH_BLOCKED, say("All checks pass.")], False,
     "a push blocked by a PreToolUse hook does not make a query stale"),
    ([QUERY, PUSH_ATTEMPT, PUSH_DENIED, say("All checks pass.")], False,
     "a push denied by the permission classifier does not make a query stale"),
    # The other direction, which is the expensive one: dropping a push that DID
    # run licenses a merge on a stale reading, so every shape that is not an
    # unambiguous refusal still counts.
    ([QUERY, PUSH_ATTEMPT, PUSH_EXIT_FAILED, say("All checks pass.")], True,
     "a push that ran and exited non-zero still makes a query stale"),
    ([QUERY, PUSH_ATTEMPT, PUSH_QUOTES_REFUSAL, say("All checks pass.")], True,
     "a result QUOTING the refusal wording is not a refusal"),
    ([QUERY, PUSH, say("All checks pass.")], True,
     "a push with no tool_use id at all still makes a query stale"),
    ([QUERY, PUSH_ATTEMPT, PUSH_MARKED_OK, say("All checks pass.")], True,
     "an explicit is_error false overrides the refusal wording"),
    ([QUERY, PUSH_ATTEMPT, PUSH_BLOCKED_PARTS, say("All checks pass.")], False,
     "a refusal arriving as a LATER content part is still a refusal"),
    ([QUERY, PUSH_ATTEMPT, PUSH_PARTS_QUOTE_REFUSAL, say("All checks pass.")],
     True,
     "a later content part QUOTING the refusal wording is not a refusal"),
    ([QUERY, PUSH_ATTEMPT, PUSH_BLOCKED, PUSH_SECOND_ATTEMPT,
      say("All checks pass.")], True,
     "a real push after a blocked one still makes a query stale"),
    # Round 9, finding 6. `pending`, `queued`, `in progress`, `in flight` and
    # `still running` are ordinary English about anything at all, so matching
    # them bare let four sentences that disclose no pending CHECK work exempt
    # a bare count. The exemption is the thing that stops this guard firing,
    # so a false exemption is the expensive direction. The polysemous half
    # now needs a count or a check noun; the state half -- "not fully clean",
    # "still failing", "not a clean stopping point" -- does not, because none
    # of those has a sense that is not about the work.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("9 pass. Merge pending your approval.")], True,
     "'pending your approval' is not a disclosed pending check"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("12 pass. The release is queued for Friday.")], True,
     "a queued RELEASE is not a disclosed pending check"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("9 pass. The write-up is still in progress.")], True,
     "a write-up in progress is not a disclosed pending check"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("9 pass. Her application is pending.")], True,
     "an application pending is not a disclosed pending check"),
    # ... and the check-context forms the narrowing must keep.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("9 pass. Checks are still running.")], False,
     "a check noun governing the vocabulary still exempts"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("9 pass, but the PR is not fully clean.")], False,
     "the state half needs no check noun to exempt"),
    # Polarity, from the adversarial review of this branch. The round-9 split
    # above stopped a polysemous word exempting itself outside check context
    # and left the mirror case open: a sentence DENYING pending work bought
    # the exemption by naming the thing it denies, which switches this guard
    # off on exactly the clean assertion it exists to surface. All four
    # measured sentences exempted before the fix; none of the 139 rows that
    # predate these distinguishes them from a real disclosure.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass, 0 pending.")], True,
     "a ZERO count denies pending work rather than disclosing it"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass, 0 checks queued.")], True,
     "a zero count denies it with a check noun too"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass, no checks pending.")], True,
     "a negator before the check noun denies pending work"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass, zero jobs pending.")], True,
     "`zero` before the check noun denies it as `no` does"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass, 0 of 14 checks pending.")], True,
     "a bare zero governs a count the slot itself cannot see"),
    # ... and the disclosures the polarity guard must NOT reach. A negator
    # inverts only the phrase it governs, so the window is the CLAUSE; a
    # sentence-wide one suppresses the first of these, which is this repo's
    # own commonest recap opening.
    #
    # Every row here opens with a clean assertion, and that is load-bearing
    # rather than scene-setting. Written without one they were VACUOUS: the
    # hook returns at `find_unnegated_assert` before the exemption is ever
    # consulted, so each passed with the construct it names deleted, while
    # reading exactly like coverage. The second row is also comma-free,
    # because a comma puts the negator outside the window on its own and the
    # carve-out is then never reached.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. No findings remain, 2 checks still pending.")], False,
     "a negation in ANOTHER clause leaves the disclosure standing"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. No longer blocked and 2 checks are still pending.")], False,
     "`no longer` is resolution, not denial"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. v1.0 has 3 checks pending.")], False,
     "a version's zero is not a zero count"),
    # ...and the same for a version whose zero LEADS it, which the round-14
    # narrowing of that bound could have reopened: `0.9012` must still not
    # read as a denial, while `0.` ending a sentence must.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. Bumped to 0.9012 with 3 checks pending.")], False,
     "a version's LEADING zero is not a zero count either"),
    # A hyphen is a non-word character, so `\bno\b` matches inside `no-op`
    # and `\bzero\b` inside `zero-findings`. In a NEGATOR set that silences
    # the exemption with nothing red, so the bounds are `(?<![-\w])` /
    # `(?![-\w])`. This row is what makes that choice falsifiable.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. The no-op rebase left 2 checks pending.")], False,
     "a negator inside a hyphenated compound is not a negator"),

    # Round 14, finding 1: the round-13 window was the clause PREFIX, which
    # is not the clause its own docstring claimed. A negator that TRAILS the
    # phrase it governs was never scanned, so each of these denials bought
    # the exemption and switched the guard off. The negator is now looked
    # for on both sides of the match and never inside it -- inside is what
    # `not yet clean` needs, and the row below pins that it still works.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass, checks pending 0.")], True,
     "a zero TRAILING the check noun denies it"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass, checks pending are none.")], True,
     "a word negator trailing the check noun denies it"),
    # A colon is a clause break for the PREFIX scan and must not be one for
    # the SUFFIX scan: here it is what attaches the zero to the noun it
    # denies, so breaking there hid the negator entirely.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. Checks pending: 0.")], True,
     "a label's colon does not hide the value that denies it"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. No findings: 2 checks pending.")], False,
     "...while the prefix scan still breaks on that same colon"),
    # Round 14, finding 2: round 13 excluded a zero from the count slot and
    # reopened the false positive the exemption exists to prevent. These are
    # honest progress reports whose pending count has genuinely drained to
    # zero while a failure stands, and round 13 blocked all of them.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass, 1 fail, 0 pending.")], False,
     "a disclosed failing count is a disclosure, zero pending or not"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass, 2 failed, 0 checks pending.")], False,
     "...in its inflected forms too"),
    # The NOUN forms were missing from the first draft of that alternative,
    # so this row -- the commonest spelling of a failing count there is --
    # was still blocked, and the zero row below passed vacuously because
    # `failures` matched nothing at all rather than being excluded as a zero.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass, 1 failure, 0 pending.")], False,
     "...and in its noun forms, which is how a failing count is usually written"),
    # Two rows, because the obvious one cannot isolate the zero-exclusion.
    # "0 failures" is itself a non-bare clean assertion, so the re-aim finds
    # it and blocks whether or not the exemption fired -- dropping the
    # exclusion left the whole suite green. "0 failed" is not an assertion,
    # so there the exemption alone decides and the mutation flips the row.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass, 0 failed, 0 pending.")], True,
     "a ZERO failing count discloses nothing, so the exemption stays shut"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass, 0 failures, 0 pending.")], True,
     "...and its noun form is covered twice over, being a clean claim itself"),
    # Round 14, finding 8: `and` and `but` join independent clauses without
    # a comma, so this read as one clause and the leading denial suppressed
    # a genuine disclosure of three queued jobs.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. No checks pending and 3 jobs queued.")], False,
     "a conjunction breaks the clause as a comma does"),
    # A breaker with no space after it puts the match's own start exactly ON
    # a clause start, which is the one index where bisect_right and
    # bisect_left disagree: left hands back the PREVIOUS clause, so the
    # earlier denial governs a disclosure it has nothing to do with. Found by
    # mutating the search, which the rest of the suite could not see.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. No findings remain;3 jobs queued.")], False,
     "a clause starting flush against its breaker is its own clause"),
    # Round 15, finding 3: the round-14 SUFFIX scan ran to the next value
    # break, so any negator anywhere in the tail cancelled the disclosure.
    # Each of these discloses pending work in its first phrase and reports
    # something ABSENT in a second, independent one, and round 14 read the
    # second as denying the first -- blocking an honest progress report. The
    # trailing negator is anchored to the match now, so a preposition or a
    # second verb between them ends its reach.
    #
    # The finding's OWN sentence cannot pin that, and saying so is the point:
    # "no failures" is itself a non-bare clean claim, so the re-aim finds it
    # and the hook blocks whichever way the exemption goes -- the same
    # twice-over shape as the "0 failures" row above. The three rows after it
    # isolate the anchor, because "nothing else outstanding", "none of the
    # release jobs" and "zero drama" assert nothing about this PR's checks.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass, 3 checks pending with no failures.")], True,
     "the finding's own sentence blocks either way, on its second claim"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass, 3 checks pending with nothing else outstanding.")], False,
     "...for each word in the negator set, not just the commonest one"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass, 3 checks pending on none of the release jobs.")], False,
     "...and for a negator that is the object of that preposition"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass, 3 checks pending with zero drama.")], False,
     "...including the bare-zero arm, which reads no differently"),
    # Round 16, finding 2. Round 15 closed the finding-2 leak by refusing a
    # preposition after the count, which caught that sentence and not its
    # class: the tense sits IN FRONT of the count, so every past-tense
    # sentence about a count already resolved still ended on a terminator
    # the tail admits. Each of these blocks at HEAD~1 only by accident of
    # phrasing and not at all as shipped; measured at the parent, all four
    # went unblocked over a failing status query.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. I fixed 3 errors.")], True,
     "a resolved count ending on a terminator buys no exemption"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. That resolved 2 failures.")], True,
     "...for the verb in its own right, not just the first-person form"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. The last round closed 3 failures.")], True,
     "...with two words between the verb and the count"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. I fixed the CI and 3 errors remain.")], False,
     "...but three words is out of reach, so this still discloses"),
    # Round 16, finding 3. Anchoring the trailing negator admitted only an
    # empty connector, a colon and a copula, so every other way of joining
    # a label to its value read as a disclosure and exempted the clean
    # claim. The first row is the one that matters: `--` is this corpus's
    # own house substitute for an em dash, so it is what an author writing
    # in house style types. All four block at HEAD~2 and not at HEAD~1.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. Checks pending -- none.")], True,
     "a denial joined by the house em-dash substitute is still a denial"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. Checks pending - none.")], True,
     "...and by a single hyphen"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. Checks pending = 0.")], True,
     "...and by an equals sign, with the bare-zero arm"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. Checks pending (none).")], True,
     "...and by a paren, which closes after the negator"),
    # Round 17, finding 1. The connector was spelled as EXACTLY two hyphens,
    # and this corpus's dominant spaced dash is three: 9618 occurrences of
    # `---` against 1214 of `--` over the 746 tracked `*.md` files,
    # measured 2026-09-25 with `grep -hoE`. So the form an
    # author writing in house style actually types read as a disclosure and
    # exempted the clean claim beside it. The run is unbounded now rather
    # than enumerated, which is one closed set fewer to keep current.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. Checks pending --- none.")], True,
     "a denial joined by the corpus's dominant dash is still a denial"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. Checks pending ---- none.")], True,
     "...and by any longer run, which the unbounded form covers"),
    # Round 17, finding 6. A COUNT is its own disclosure. Round 16 let the
    # trailing negator retract one, which refused four honest reports whose
    # second phrase is independent of the first. The three sibling rows
    # above ("with zero drama" and friends) pass at both commits because a
    # WORD connector was already refused; these three carry a connector the
    # tail admits, so they are the ones that isolate the count rule.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass, 3 checks pending -- zero drama.")], False,
     "a counted disclosure is not retracted by a dash and a negator"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass, 3 checks pending (zero drama).")], False,
     "...nor by a parenthesis"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass, 3 checks pending -- nothing else outstanding.")], False,
     "...for another word in the negator set"),
    # ...and the miss that rule buys, stated rather than left to be found:
    # a sentence that discloses a count and then denies it outright now
    # reads as the disclosure. It is self-contradicting either way, and the
    # four rows above are ordinary prose.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. 3 checks pending -- none.")], False,
     "a counted disclosure denied outright is a known miss, not a block"),
    # Round 17, finding 3. A count re-targeted off this PR was refused by
    # the tail and admitted by the lead, so one word order disclosed and
    # the other did not. The first row is the tail form, already pinned
    # above; these three are the front-loaded forms it disagreed with.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. On main, 3 checks failed.")], True,
     "a re-target in front of the count buys no more exemption than behind"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. In the sibling repo 3 checks failed.")], True,
     "...with three words between the preposition and the count"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. Last week 3 checks failed.")], True,
     "...and for a temporal re-target, which names no place at all"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. On this PR, 3 checks failed.")], False,
     "...but a self-referential object is a disclosure, not a re-target"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. 2 runs still in progress. 3 checks failed.")], False,
     "...and the lead cannot reach across a sentence boundary"),
    # Round 17, findings 4 and 5. A past-tense verb in front of a count is
    # an exemption only for a count of things that FAILED: a review can be
    # addressed while the runs it triggered are still queued. And a
    # coordinating conjunction opens a new clause, so it can never be
    # filler inside one. The first of these is close to the remedy this
    # guard itself prints, which is the jointly-unsatisfiable pair.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. Addressed review and 3 runs still in progress.")], False,
     "a resolution verb does not retract a count of work still queued"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. Fixed lint and 3 checks pending.")], False,
     "...for the pending alternative in its own right"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. Two fixes and 3 errors remain.")], False,
     "a conjunction is not filler, so the verb does not reach the count"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. Fixed CI and 3 errors remain.")], False,
     "...with no article to pad the window past its two-word bound"),
    # Round 16, finding 3, the other side. The connector set is closed on
    # purpose: admitting an arbitrary word would let "with" fill the slot
    # and "no" satisfy the negator, which is round 15 finding 3 reopened.
    # An adverb is admitted anyway, by the optional word in front of the
    # MANDATORY copula -- so this row pins a recognized denial rather than
    # a miss, and it is the copula that separates it from "with zero
    # drama". Round 16 described it as a deliberate miss, which inverts the
    # mechanism: a genuine miss here reads as a disclosure and exempts the
    # clean claim silently, which is the opposite of what this row sees
    # (round 17, finding 7).
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. Checks pending today are none.")], True,
     "an adverb before the copula is admitted, so the denial is recognized"),
    # Round 16, finding 4. The count alternative required the digit to be
    # adjacent to the verb, so the commonest honest disclosure there is was
    # a false alarm -- and the comment above it told the author to write
    # exactly the form that did not work. The noun slot is `_CHECK_NOUN`,
    # shared with the pending alternatives. The last row pins that the tail
    # still refuses a count re-targeted somewhere other than this PR.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. 3 checks failed.")], False,
     "a count with its noun between it and the verb still discloses"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. 1 check failed.")], False,
     "...in the singular"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. 2 jobs failing.")], False,
     "...for another noun in the shared vocabulary"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. 3 checks failed on main.")], True,
     "...but the tail still refuses one re-targeted off this PR"),
    # Round 15, finding 2: a failing count says nothing about what it counts,
    # so an unattached one bought the whole exemption and let the clean claim
    # in front of it through. The count now has to land on a clause end or on
    # a word that keeps it current. The middle row is a count of something
    # that is not a check at all; the last two pin the admitted side, one
    # landing on a state word and one on the end of the text.
    #
    # The sentence has to carry a BARE count and nothing else, because the
    # re-aim blocks on any non-bare assert regardless: with "fully clean" in
    # front of it the defect is invisible, and a row written that way would
    # have passed at both commits. Measured against the parent commit: these
    # two do not block there and do here.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. I fixed 3 errors in the docs.")], True,
     "a failing count re-targeted by a preposition buys no exemption"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. I corrected 2 failures of imagination.")], True,
     "...whatever the count is actually counting"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. 3 errors remain.")], False,
     "...while a word that keeps the count current still discloses"),
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. 2 failures outstanding")], False,
     "...at the end of the text, where there is no terminator to land on"),
    # That row lands on a state WORD, so it says nothing about the tail's
    # end-of-text arm; this one has neither a terminator nor a state word
    # after it, and dropping `\Z` flips it alone.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass. 3 failures")], False,
     "...and a bare failing count ending the text still discloses"),
    # Three rows found by mutating the round-15 code rather than by the
    # review, each pinning a boundary the sentences above cannot reach.
    #
    # A negator sitting EXACTLY on a clause start is the one index where the
    # two bisect sides disagree about the negator list, and a line break is
    # how that happens in ordinary writing: the breaker ends on the capital.
    # Reading right past it turns a denial into a disclosure, which is the
    # direction that switches the guard off.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass.\nNo checks pending.")], True,
     "a denial opening its own line still denies"),
    # The decimal guard on the clause breaker is load-bearing in BOTH
    # directions, and only this one is dangerous. Round 14 recorded the false
    # ALARM: splitting inside `v1.0` left a window whose leading `0` read as
    # a denial. Splitting also SHORTENS the window, which drops a real
    # negator out of it -- here the `no` that denies the pending checks --
    # and the guard then goes silent on the count in front of it.
    ([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT,
      say("14 pass, no v1.0 checks pending.")], True,
     "a version number inside a denial does not split it into two clauses"),

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
    ([QUERY, PUSH, say("All checks green is a claim that was later overstated.")], False,
     "an adverb may sit beside the auxiliary too"),
    ([QUERY, PUSH, say("All checks green is a claim that has now been retracted.")], False,
     "and between two auxiliaries"),
    ([QUERY, PUSH, say("All checks green is a claim that reviewers overstated.")], True,
     "an unmarked plural subject fills no slot in the head phrase, so that "
     "object relative still breaks attachment"),
    ([QUERY, PUSH, say("All checks green is a claim that family overstated.")], True,
     "the adverb slot is a closed list, so a lowercase noun ending in -ly "
     "fills no slot and the object relative still breaks attachment"),
    ([QUERY, PUSH, say("All checks green is a claim that supply overstated.")], True,
     "same shape with a verb-or-noun ending in -ly"),
    ([QUERY, PUSH, say("All checks green is a claim that Kelly overstated.")], True,
     "a capitalized name fills no adverb slot either"),
    ([QUERY, PUSH, say("All checks green is a claim that was clearly overstated.")], False,
     "a listed adverb between the auxiliary and the retraction still "
     "attaches"),
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


def check_cost():
    r"""Bounded cost on the two shapes that have each gone quadratic here.

    This suite had no timing assertion of any kind until round 16, which is
    why it could not see either. The verdict is identical under a quadratic
    and a linear pattern, so every other row in this file passes in both
    states -- a cost ceiling is the only instrument that can tell them
    apart, exactly as in the sibling suite for the verdict-echo hook.

    The two shapes are independent and a fix for one does not bound the
    other, so both are asserted:

    A LONG CLAUSE WITH MANY HITS. Round 15, finding 1: the prefix scan
    re-sliced and re-searched a growing window once per hit, so k hits over
    n characters cost O(n*k). What makes the loop run to completion is that
    every hit is SKIPPED -- the first hit it does not skip returns True and
    the rest are never read, which is how round 16's own shape came to time
    a body of 8000 disclosures after looking at one of them (round 17,
    finding 2). A resolution verb in front of each count skips all 8000.
    Measured at 160017 characters: 0.107s as shipped, against 40.99s with
    the per-hit prefix rescan reinstated and 41.50s with the window
    unbounded -- the two regressions this shape exists to catch, each
    confirmed to turn it red and each invisible to round 16's version.

    ONE LONG RUN OF SPACES. Round 16, finding 1: the rewrite spelled the
    trailing negator with two adjacent unbounded `[ \t]*` runs, so a
    FAILING match tried every split of one run between them. Measured at
    8000 spaces: 5.63s as that commit shipped, 0.003s once written as one
    run plus an optional connector. Note the asymmetry that makes this the
    easier one to miss: cost is quadratic in the length of a single run and
    only linear in how many runs there are, so a padded markdown table does
    not trigger it and nothing short of one long run will.

    The ceiling is 5s against a whole-process baseline of about 0.04s,
    which the larger shape takes to 0.107s -- ample headroom on a slow
    runner, and still red on every regression above by two to three orders
    of magnitude.
    """
    failures = 0
    # Both shapes must OPEN with a clean claim. `main()` returns at
    # `find_unnegated_assert` when there is none, so a pathological body
    # with no assertion in it never reaches `discloses_pending` at all --
    # the first draft of this check omitted the opener and passed against
    # the very commit whose regression it was written to catch, in 0.04s.
    CLEAN = "All checks pass. "
    # Every hit in the first shape is SKIPPED, which is what makes the loop
    # run to completion. Round 16 wrote it as a repeated bare disclosure,
    # so the very first hit returned True and the other 7999 were never
    # reached: the check passed in 0.07s against a body it had not read,
    # and it would have passed identically with the per-hit prefix rescan
    # reinstated (round 17, finding 2). A resolved lead in front of each
    # count skips every one of them, so the per-hit work is what is timed.
    shapes = [
        (CLEAN + "fixed 3 errors left " * 8000,
         "many skipped hits, loop run to completion"),
        (CLEAN + "3 checks pending" + " " * 16000 + "x",
         "one long run of spaces"),
    ]
    for text, label in shapes:
        started = time.time()
        run([CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT, say(text)])
        elapsed = time.time() - started
        ok = elapsed < 5.0
        failures += 0 if ok else 1
        print(f"{'ok  ' if ok else 'FAIL'}  cost: {label} "
              f"under 5s (took {elapsed:.2f}s)")
    return failures


COST_CHECKS = 2


def run(events):
    td = tempfile.mkdtemp()
    try:
        path = os.path.join(td, "transcript.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            for e in events:
                fh.write(json.dumps(e) + "\n")
        env = dict(os.environ, TMPDIR=td, TEMP=td, TMP=td)
        out = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True, env=env,
        ).stdout.strip()
        return bool(out)
    finally:
        shutil.rmtree(td, ignore_errors=True)




# ai-config#1859: the WORDING must match what was actually detected.
# A bare "<n> pass" with no PR reference near it may well be a local test-suite
# count, and asserting it is "a PR's check state" was wrong three times
# ("10 pass", "30 pass", "33 pass"). The staleness verdict is unchanged --
# only the sentence describing the match. Asserted here rather than in CASES
# because CASES compares fire/no-fire and would pass either way, which is how
# a detector that is right about the important part and wrong about the
# visible part survives a green suite.
ATTRIBUTION = [
    # The comparison behind this block is by TIME alone: the most recent
    # status query against the most recent push, with no notion of which
    # repository or branch either touched. A push to a DIFFERENT repo
    # therefore trips it over a reading that was perfectly current. Firing
    # there is the safe direction and stays, but the message must not assert
    # the premise -- an earlier wording said flatly that the reading
    # "describes a commit that is no longer the head", which is false in that
    # case, and the author conceded a retraction the evidence did not support.
    ("All checks green on the four PRs.",
     "by TIME, not by repository or branch",
     "the message discloses that the comparison is repo-blind"),
    ("All checks green on the four PRs.",
     "MAY describe a commit",
     "the staleness is stated as possible, not asserted"),
    ("All checks green on the four PRs.",
     "do not write a retraction the evidence does not support",
     "the message warns against over-conceding to it"),
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


# The failing-query branch is PR-blind in the same way the staleness branch is
# repo-blind: it pairs any unnegated ASSERT in the message against any failing
# query in the transcript, without checking they concern the same PR. Firing
# is still the safe direction; the message must say what it matched.
ATTRIBUTION_FAILING_QUERY = [
    ("#3928 has 2 checks still in progress. #49 is fully clean.",
     "by TEXT and TIME, not by pull request",
     "the message discloses that the match is PR-blind"),
    ("#3928 has 2 checks still in progress. #49 is fully clean.",
     "may concern a DIFFERENT PR",
     "it names the specific way the premise can miss"),
    ("#3928 has 2 checks still in progress. #49 is fully clean.",
     "do not retract a claim the evidence supports",
     "it warns against over-conceding, as the staleness branch does"),
    ("#3928 has 2 checks still in progress. #49 is fully clean.",
     "no longer fires",
     "it names the progress-report form that is now exempt"),
]


def check_attribution(table=None, events=None, prefix="attribution"):
    """Each warning must describe what it matched, not what it assumed."""
    failures = 0
    table = ATTRIBUTION if table is None else table
    events = (QUERY, PUSH) if events is None else events
    for message, expected, label in table:
        td = tempfile.mkdtemp()
        try:
            path = os.path.join(td, "transcript.jsonl")
            with open(path, "w", encoding="utf-8") as fh:
                for e in tuple(events) + (say(message),):
                    fh.write(json.dumps(e) + "\n")
            env = dict(os.environ, TMPDIR=td, TEMP=td, TMP=td)
            out = subprocess.run(
                [sys.executable, HOOK],
                input=json.dumps({"transcript_path": path}),
                capture_output=True, text=True, env=env,
            ).stdout.strip()
            reason = (json.loads(out).get("reason") if out else "") or ""
            ok = expected in reason
            failures += 0 if ok else 1
            print(f"{'ok  ' if ok else 'FAIL'}  {prefix}: {label}")
        finally:
            shutil.rmtree(td, ignore_errors=True)
    return failures


PUSH_ATTRIBUTION = [
    (PUSH, "(git push -q)", "CLI git push summary in reason"),
    (MCP_PUSH, "(mcp__github__push_files)", "MCP push tool name in reason"),
    ({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "run_command", "input": {"command": "git push origin main"}}]}},
     "(git push origin main)", "CLI chained/argument push in reason"),
]


def check_push_attribution():
    """Warning must name the push command or tool that triggered the staleness."""
    failures = 0
    for push_event, expected, label in PUSH_ATTRIBUTION:
        td = tempfile.mkdtemp()
        try:
            path = os.path.join(td, "transcript.jsonl")
            with open(path, "w", encoding="utf-8") as fh:
                for e in (QUERY, push_event, say("All checks green at this head.")):
                    fh.write(json.dumps(e) + "\n")
            env = dict(os.environ, TMPDIR=td, TEMP=td, TMP=td)
            out = subprocess.run(
                [sys.executable, HOOK],
                input=json.dumps({"transcript_path": path}),
                capture_output=True, text=True, env=env,
            ).stdout.strip()
            reason = (json.loads(out).get("reason") if out else "") or ""
            ok = expected in reason
            failures += 0 if ok else 1
            print(f"{'ok  ' if ok else 'FAIL'}  push-attribution: {label}")
        finally:
            shutil.rmtree(td, ignore_errors=True)
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
    failures += check_attribution(
        ATTRIBUTION_FAILING_QUERY,
        (CHECK_CLEAN_QUERY, CHECK_CLEAN_FAIL_RESULT),
        "attribution (failing-query)",
    )
    failures += check_push_attribution()
    failures += check_query_forms()
    failures += check_cost()
    # `ATTRIBUTION_FAILING_QUERY` runs above and its failures are counted,
    # so leaving it out of the denominator understated the suite by four:
    # it printed `117/117 passed` over 121 executed checks, and a reader
    # comparing runs saw the population unchanged (round 7, finding 7).
    total = (len(CASES) + len(ATTRIBUTION) + len(ATTRIBUTION_FAILING_QUERY)
             + len(PUSH_ATTRIBUTION) + len(QUERY_FORMS) + COST_CHECKS)
    print(f"\n{total - failures}/{total} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
