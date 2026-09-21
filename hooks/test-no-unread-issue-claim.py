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
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time

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
    # `RX_ISSUE`'s lookbehind and lookahead are both called load-bearing and
    # neither was exercised: deleting either left the suite green.
    ([PROMPT, READ_BODY_ONLY,
      say("The branch feat#1566 still needs your call.")], False,
     "a number glued to a word is not an issue reference"),
    ([PROMPT, READ_BODY_ONLY,
      say("Ticket #123456789 still needs your call.")], False,
     "a digit run longer than an issue number is not one"),

    # `RX_INITIAL` only neutralises a capital before ANOTHER capital. Weaken
    # the lookahead to bare whitespace and a real sentence end after a lone
    # capital is deleted, merging two sentences and naming a closed issue --
    # the misattribution this file rates worst.
    ([PROMPT, READ_COMMENTS,
      say("#1622 is closed, reported by J. now #1566 still needs your call.")],
     False,
     "an initial rule that fired before a LOWERCASE word would merge two "
     "sentences and name the closed issue"),

    # The fenced/span replacement is a period so the removed region acts as a
    # sentence BOUNDARY. A space would join instead, which is only visible
    # with the cue on one side of a span and the number on the other.
    ([PROMPT, READ_BODY_ONLY,
      say("This still needs your call `inline code here` #1566 is "
          "unrelated.")], False,
     "a code span SEPARATES a cue from a later number rather than joining "
     "them"),

    # The `-c` shorthand for `--comments`, which nothing exercised.
    ([PROMPT, bash("gh issue view 1566 -R o/r -c"), say(CLAIM)], False,
     "the `-c` shorthand discharges it too"),

    # The MCP call with `issue_number` BEFORE the comments method, which is
    # a separate pattern from the one the existing MCP case exercises.
    ([PROMPT,
      tool("mcp__github__issue_read",
           {"issue_number": 1566, "owner": "o", "repo": "r",
            "method": "get_comments"}),
      say(CLAIM)], False,
     "an MCP call naming the issue before the method discharges it as well"),
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

    # A claim WRAPPED across a bare newline -- this repo's semantic-line-breaks
    # house style. Splitting on every newline silently disabled the guard here,
    # trading the bullet false positive for a false negative on its core
    # function. Four shapes, because the regression was invisible to a suite
    # whose every multi-line case was deliberately TWO claims.
    ([PROMPT, READ_BODY_ONLY,
      say("The naming question in #1566\nstill needs your decision.")], True,
     "a claim wrapped at a bare newline still fires (cue after the number)"),
    ([PROMPT, READ_BODY_ONLY,
      say("#1566 is the one item outstanding --\nit is yours to call.")], True,
     "wrapped after an em-dash-style break still fires"),
    ([PROMPT, READ_BODY_ONLY,
      say("Everything else shipped.\nOnly #1566\nremains blocked on you.")],
     True,
     "a claim wrapped TWICE still fires"),
    ([PROMPT, READ_BODY_ONLY,
      say("The decision on #1566\nis still yours to make.")], True,
     "wrapped between the number and the cue still fires"),

    # The scoped PR prefix gets BOTH directions: `for` is admitted only
    # directly after a PR noun.
    ([PROMPT, READ_BODY_ONLY,
      say("Apply the fix for #1566 -- it still needs your input.")], True,
     "a genuine escalation phrased 'the fix for #N' is NOT swallowed"),
    ([PROMPT, READ_BODY_ONLY,
      say("The PR for #1566 is awaiting review.")], False,
     "'the PR for #N' IS excluded -- the cue describes the pull request"),
    ([PROMPT, READ_BODY_ONLY,
      say("The pull request for #1566 is awaiting review.")], False,
     "the spelled-out form is excluded too"),

    # A NUMBERED list usually elaborates one claim introduced by a lead-in,
    # so splitting there separates a claim from its own subject.
    ([PROMPT, READ_BODY_ONLY,
      say("The two remaining tasks for #1566:\n"
          "1. the docs pass is done\n"
          "2. it still needs your final sign-off")], True,
     "a numbered list ELABORATING one claim is not split away from its subject"),
    ([PROMPT, READ_BODY_ONLY,
      say("The naming question in #1566 is basically settled --\n"
          "2. more voices are wanted, so it remains open.")], True,
     "a continuation line that happens to start with a digit is not a boundary"),

    # Lettered, roman and Unicode bullets are the same structure as `-*+`.
    ([PROMPT, say("Progress notes:\n"
                  "a) Investigated flaky CI, still pending a fix upstream\n"
                  "b) Closed #1622 after merging the associated PR")], False,
     "a lettered list splits, so a cue in item a) does not reach item b)"),
    ([PROMPT, say("Notes:\n"
                  "• CI is still pending upstream\n"
                  "• Closed #1622 after merging")], False,
     "a Unicode bullet list splits too"),

    # --- the lead-in gap, and why it stays open (rounds 4 and 5) -------------
    # KNOWN GAP, asserted so it cannot change silently. A `_list_subject`
    # discriminator closed this and was reverted: review found four ways it
    # mis-attached, the worst sending a second issue's claim to the FIRST
    # issue in the paragraph while the genuinely unread one went unnamed.
    # Misattribution is worse than a miss -- see the docstring.
    ([PROMPT, READ_BODY_ONLY,
      say("Remaining on #1566:\n"
          "- a written migration script\n"
          "- your decision on rollout timing")], False,
     "KNOWN GAP: a cue in a list item does not reach the lead-in's issue"),
    # The shape that made the discriminator unacceptable. If a future attempt
    # reintroduces scoping, it must not name #1566 (whose comments WERE read)
    # while #1544's claim goes unflagged.
    ([PROMPT, READ_COMMENTS,
      say("Notes for #1566:\n- item one is fine\n"
          "Notes for #1544:\n- still needs your review")], False,
     "two lead-ins must not misattribute the second issue's claim to the first"),
    ([PROMPT, say("Progress notes:\n"
                  "- Investigated flaky CI, still pending a fix upstream\n"
                  "- Closed #1622 after merging")], False,
     "a list whose lead-in names NO issue keeps its items independent"),
    ([PROMPT, READ_BODY_ONLY,
      say("Remaining on #1566 and #1544:\n"
          "- your decision on rollout timing")], False,
     "a lead-in naming TWO issues does not say which an item's cue is about, "
     "so it attaches to neither"),
    ([PROMPT, READ_BODY_ONLY,
      say("Remaining on #1566\n- your decision on rollout timing")], False,
     "a lead-in without a colon is not a scope"),

    # A --jq filter legitimately contains a pipe.
    ([PROMPT,
      bash("gh issue view 1566 -R o/r --jq '.comments[] | .body' --json comments"),
      say(CLAIM)], False,
     "a --jq pipe before the comments flag must not break the discharge match"),

    # Mixed state: one discharged, one not. That this FIRES is asserted here;
    # that it names the RIGHT number is asserted in
    # check_mixed_state_names_the_undischarged_issue, because a fire/quiet
    # result cannot tell the two apart.
    ([PROMPT, READ_COMMENTS,
      say("#1566 is settled. But #1544 still needs your call.")], True,
     "a discharged issue in the same message does not excuse an undischarged one"),

    # --- round 6 -------------------------------------------------------------
    # A NESTED fence. Documenting this guard means quoting its own trigger
    # phrases, and the natural way to quote a fenced example is a wider fence
    # around it. A whole-document backtick-run regex pairs the runs wrongly
    # and hands the quoted claim back as prose.
    ([PROMPT, READ_BODY_ONLY,
      say("Here is how the guard documents itself:\n"
          "````\n"
          "Example transcript:\n"
          "```\n"
          "#1566 still needs your call.\n"
          "```\n"
          "That is the trigger shape.\n"
          "````\n"
          "Everything else is done.")], False,
     "a nested fence is quoted material, not an assertion"),
    ([PROMPT, READ_BODY_ONLY,
      say("> #1566 still needs your call.\n\nThat was last week's recap.")],
     False,
     "a blockquote is quoted material too"),

    # A personal initial is not a sentence end. Both the terminator rule and
    # the list-marker rule used to cut the claim in two here, leaving the cue
    # in a sentence carrying no issue number -- the silent miss this file
    # rates worst.
    ([PROMPT, READ_BODY_ONLY,
      say("#1566 is the one item outstanding, per\n"
          "J. Smith's review, and it\n"
          "still needs your final call.")], True,
     "an initial mid-claim does not split the claim from its issue"),
    ([PROMPT, READ_BODY_ONLY,
      say("I opened the PR. It still needs your call on #1566.")], True,
     "an acronym ending a real sentence still splits, so the cue stays with "
     "the number that follows it"),
    ([PROMPT, READ_BODY_ONLY,
      say("Closed #1622 after merging the PR. "
          "Separately, CI is still blocked on the runner image.")], False,
     "an acronym ending a real sentence still splits, so a LATER cue does not "
     "reach back to the number"),

    # A DOTTED abbreviation ends a sentence, and the next one ordinarily
    # begins with a capital -- so the initial rule matched its last letter
    # and deleted a real terminator, merging two sentences and attributing
    # the second's cue to the first's issue. The issue named there is stated
    # as CLOSED, which is what makes the resulting warning misdirection
    # rather than noise.
    # Each of these puts the NUMBER in the first sentence, the CUE in the
    # second, the abbreviation on the boundary between them, and leaves the
    # issue undischarged -- so a merged boundary fires and names an issue the
    # message says is closed. A fixture that discharges the issue, or that
    # keeps cue and number on the same side, stays quiet either way and
    # asserts nothing.
    ([PROMPT, READ_BODY_ONLY,
      say("#1622 is closed in the U.S. Now the runner image still needs "
          "your call.")], False,
     "a dotted abbreviation ending a sentence still splits"),
    ([PROMPT, READ_BODY_ONLY,
      say("#1622 shipped to the E.U. P.S. The runner image is blocked on "
          "your review.")], False,
     "a run of dotted abbreviations does not swallow the boundary either"),
    ([PROMPT, READ_BODY_ONLY,
      say("Everything shipped in the E.U. But #1566 still needs your call.")],
     True,
     "and an abbreviation does not silence a claim in the sentence after it"),

    # One case per cue, each phrased so that cue is the ONLY one matching.
    # `pending` got this treatment first, after deleting it left the suite
    # green; a later mutation pass found eleven more in the same state, so
    # the remedy is applied to the whole list rather than to the one that
    # happened to be measured.
    ([PROMPT, READ_BODY_ONLY,
      say("#1566 is pending a decision from you.")], True,
     "'pending' alone is a cue"),
    ([PROMPT, READ_BODY_ONLY,
      say("#1566 is blocked on the runner image.")], True,
     "'blocked on' alone is a cue"),
    ([PROMPT, READ_BODY_ONLY,
      say("#1566 awaits the maintainer review.")], True,
     "'awaits' alone is a cue"),
    ([PROMPT, READ_BODY_ONLY,
      say("#1566 is waiting on the upstream release.")], True,
     "'waiting on' alone is a cue"),
    ([PROMPT, READ_BODY_ONLY,
      say("#1566 needs a decision.")], True,
     "'needs a decision' alone is a cue"),
    ([PROMPT, READ_BODY_ONLY,
      say("#1566 sits until your call arrives.")], True,
     "'your call' alone is a cue"),
    ([PROMPT, READ_BODY_ONLY,
      say("#1566 stays yours for now.")], True,
     "'stays yours' alone is a cue"),
    ([PROMPT, READ_BODY_ONLY,
      say("#1566 is still outstanding.")], True,
     "'still outstanding' alone is a cue"),
    ([PROMPT, READ_BODY_ONLY,
      say("#1566 sits unanswered.")], True,
     "'unanswered' alone is a cue"),
    ([PROMPT, READ_BODY_ONLY,
      say("#1566 gates the Phase 3 work.")], True,
     "'gates' alone is a cue"),
    ([PROMPT, READ_BODY_ONLY,
      say("#1566 is the only open work left.")], True,
     "'open work' alone is a cue"),
    ([PROMPT, READ_BODY_ONLY,
      say("#1566 is not yet decided.")], True,
     "'not yet decided' alone is a cue"),

    # A blockquote at the very START of the message. This pins that a leading
    # blockquote is stripped AT ALL, which is what the mid-message case
    # cannot show. It does not pin the substituted character: a differential
    # sweep across blockquote positions found no input where the period and
    # the empty string give different verdicts, which is why the hook
    # substitutes the empty string and says so.
    ([PROMPT, READ_BODY_ONLY,
      say("> #1566 still needs your call.\nEverything else shipped.")], False,
     "a blockquote opening the message is quoted material"),

    # The PR-prefix exclusion is now looked for in a bounded window, so the
    # window has to be wider than the longest match the pattern can produce.
    # Both directions: ordinary spacing is still excluded, and a gap padded
    # past the pattern's own bound is deliberately no longer a PR prefix.
    ([PROMPT, READ_BODY_ONLY,
      say("The pull request  for  #1566 is awaiting review.")], False,
     "a PR prefix with wider-than-usual spacing is still excluded"),
    ([PROMPT, READ_BODY_ONLY,
      say("The pull request for\n#1566 is awaiting review.")], False,
     "and a PR prefix broken across a line wrap is still excluded"),
    # The bound itself, from both sides, one character apart. Without these
    # the `{0,8}` could be any value from 8 to 39 and the suite would not
    # notice, which is what a review measured.
    ([PROMPT, READ_BODY_ONLY,
      say("The pull request" + " " * 8 + "for #1566 is awaiting review.")],
     False,
     "a gap exactly AT the pattern's bound is still excluded"),
    ([PROMPT, READ_BODY_ONLY,
      say("The pull request" + " " * 9 + "for #1566 is awaiting review.")],
     True,
     "DOCUMENTED BOUND: one character past it, the text is no longer read as "
     "a PR prefix, so the claim is treated as an issue claim"),

    # The run INSIDE `pull request`, which a round bounded the other two
    # without noticing. Nothing distinguished a bounded one from `\s+` here
    # until this case existed.
    ([PROMPT, READ_BODY_ONLY,
      say("The pull" + " " * 12 + "request #1566 is awaiting review.")], True,
     "the run between `pull` and `request` is bounded like the others"),
    ([PROMPT, READ_BODY_ONLY,
      say("The pull" + " " * 8 + "request for #1566 is awaiting review.")],
     False,
     "the pull/request run at exactly its bound is still excluded"),
    ([PROMPT, READ_BODY_ONLY,
      say("The pull" + " " * 9 + "request for #1566 is awaiting review.")],
     True,
     "and one character past it is not"),
    ([PROMPT, READ_BODY_ONLY,
      say("The pull request for" + " " * 8 + "#1566 is awaiting review.")],
     False,
     "the trailing run after `for` at exactly its bound is still excluded"),
    ([PROMPT, READ_BODY_ONLY,
      say("The pull request for" + " " * 9 + "#1566 is awaiting review.")],
     True,
     "and one character past THAT one is not either"),

    # A prefix at the pattern's full maximum length, which is what pins
    # `PREFIX_WINDOW`'s floor. Every window down to 20 passed the suite
    # before this case existed, because nothing came near the maximum.
    ([PROMPT, READ_BODY_ONLY,
      say("The pull" + " " * 8 + "request" + " " * 8 + "for" + " " * 8
          + "#1566 is awaiting review.")], False,
     "a prefix at the pattern's longest possible match still fits the "
     "lookback window"),

    # An UNCLOSED fence leaves the rest as prose rather than swallowing it,
    # so one stray backtick run cannot silence every later claim.
    ([PROMPT, READ_BODY_ONLY,
      say("Here is the command:\n```\ngh pr list\n\n#1566 still needs your "
          "call.")], True,
     "an unclosed fence does not swallow the claims after it"),

    # A blank line ends a sentence even where the paragraph before it carries
    # no terminal punctuation. Deleting that alternative also left the suite
    # green, because every multi-paragraph fixture happened to end its first
    # paragraph with a period.
    ([PROMPT, READ_BODY_ONLY,
      say("Blocked on the runner image\n\n#1566 was closed as complete.")],
     False,
     "a blank line separates paragraphs even with no terminator before it"),

    # Both sides of the check are matched as strings, so a zero-padded
    # reference and a bare command argument have to be canonicalised or an
    # issue whose comments WERE read gets reported as unread.
    ([PROMPT, READ_COMMENTS,
      say("#01566 still needs your call.")], False,
     "a zero-padded reference is the same issue as the one whose comments "
     "were read"),
    ([PROMPT, READ_BODY_ONLY,
      say("#01566 still needs your call.")], True,
     "and zero-padding does not excuse an undischarged issue either"),
    ([PROMPT, bash("gh issue view 01566 -R o/r --comments"),
      say("#1566 still needs your call.")], False,
     "the canonicalisation runs on the COMMAND side too, not only the claim"),
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


def check_mixed_state_names_the_undischarged_issue():
    """The warning must name the issue that was NOT discharged.

    Fire/quiet cannot reach this. Mutating `missing[0]` to `numbers[0]` --
    report the first asserted number regardless of whether its comments were
    read -- leaves every fire/quiet case passing, including the mixed-state
    one, while the guard names the already-read issue and lets the real one
    through silently.
    """
    # BOTH issues must be ASSERTED for this to discriminate. An earlier
    # version said "#1566 is settled", which carries no cue -- so #1566 was
    # never asserted, `numbers` held one element, and `numbers[0]` and
    # `missing[0]` were the same value. The mutation was a no-op and the test
    # passed for the wrong reason.
    out = run([PROMPT, READ_COMMENTS,
               say("#1566 still needs your call, "
                   "and #1544 still needs your call too.")])
    ctx = (out.get("hookSpecificOutput") or {}).get("additionalContext") or ""
    msg = out.get("systemMessage") or ""
    ok = "1544" in ctx and "1544" in msg and "1566" not in msg
    print(f"{'ok  ' if ok else 'FAIL'}  the warning names the UNDISCHARGED "
          f"issue, not the one whose comments were read")
    return 0 if ok else 1


def check_unreadable_transcript_is_silent():
    """No transcript means no evidence either way: fail open."""
    payload = {"transcript_path": "/nonexistent/path.jsonl"}
    r = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True)
    ok = r.returncode == 0 and not r.stdout.strip()
    print(f"{'ok  ' if ok else 'FAIL'}  an unreadable transcript is silent")
    return 0 if ok else 1


def check_two_undischarged_names_the_first():
    """With more than one issue outstanding, the warning names one of them.

    Every other case leaves `missing` a single element, so `missing[0]` and
    `missing[-1]` are the same value and the selection is unasserted. Both
    choices name a genuinely undischarged issue, so this pins the documented
    one rather than a correctness property.
    """
    out = run([PROMPT, say("#1544 is blocked on you, and so is #1566.")])
    ctx = (out.get("hookSpecificOutput") or {}).get("additionalContext", "")
    ok = "#1544" in ctx and "issue #1566 as open" not in ctx
    print(f"{'ok  ' if ok else 'FAIL'}  two undischarged issues name the "
          f"first, not the last")
    return 0 if ok else 1


def check_scan_cost_stays_linear():
    """A long recap must not scan quadratically and blow the hook's budget.

    A bare newline is deliberately not a sentence boundary here, so a recap
    listing one `blocked on #N` line per issue is ONE sentence carrying
    hundreds of matches. Re-scanning from the sentence's start for each match
    made 136 KB of that shape take 10.05 seconds against a 10-second timeout
    in `hooks.json` -- the guard silently switching itself off on the longest
    transcripts, which are the ones most likely to carry a real claim.

    The budget below is deliberately far above the measured 0.05s and far
    below the timeout, so it fails on a return to quadratic scanning and not
    on a slow machine.
    """
    spec = importlib.util.spec_from_file_location("h", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    text = "blocked on #1566 " * 8000
    start = time.time()
    found = mod.asserted_issues(text)
    elapsed = time.time() - start
    ok = len(found) == 8000 and elapsed < 2.0
    print(f"{'ok  ' if ok else 'FAIL'}  a 130 KB single-sentence recap scans "
          f"in well under the hook's timeout ({elapsed:.2f}s)")
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
             check_mixed_state_names_the_undischarged_issue,
             check_unreadable_transcript_is_silent,
             check_two_undischarged_names_the_first,
             check_scan_cost_stays_linear]
    for check in adhoc:
        failures += check()
    print(f"\n{len(CASES) + len(adhoc)} checks, {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
