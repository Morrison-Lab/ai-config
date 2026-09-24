"""Test the flag-self-authored-verdict-echo guard.

The value is concentrated in the negative cases, as in every other hook test
here: a guard that fires on a genuine self-review, on a body that merely
mentions a verdict, or on a comment carrying a real review payload gets
switched off -- and then the case it exists for goes unprotected too.

The positive case is the real incident: the round-2 disposition comment on
Morrison-Lab/mln#49, which opened by reproducing the reviewer's call at line
start and so acquired a standing not-clean verdict for its own author.

Two of the negatives are the remedies that DO NOT work, kept as tests because
the natural fix is to reach for one of them: a blockquoted echo and a
code-spanned echo both still classify not-clean, so the guard must still fire
on them. Getting those backwards would send the next reader to a fix that
silently does nothing.

Run: python3 hooks/test-flag-self-authored-verdict-echo.py \\
         hooks/flag-self-authored-verdict-echo.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = (
    sys.argv[1]
    if len(sys.argv) > 1
    else os.path.join(os.path.dirname(__file__), "flag-self-authored-verdict-echo.py")
)
ROOT = os.path.dirname(os.path.dirname(os.path.realpath(HOOK)))

NOT_CLEAN = "Needs more work"

# The incident: a disposition opening with the reviewer's call at line start.
ECHO_DISPOSITION = (
    "## Review round 2 --- adversarial review at `75acd84`\n\n"
    "Verdict: **%s**, five findings. All five are addressed in\n"
    "[`f120e5a`](https://example.invalid/c/f120e5a) or in the description.\n\n"
    "**1--2. Addressed.** The backstop step's gate was wrong in both directions.\n"
) % NOT_CLEAN.lower()

# The same echo, blockquoted. Measured 2026-09-24: still classifies not-clean.
ECHO_BLOCKQUOTED = (
    "## Review round 2\n\n"
    "> Verdict: **%s**, five findings.\n\n"
    "All five are addressed in `f120e5a`.\n\n"
    "**1. Addressed.** The gate was wrong.\n"
) % NOT_CLEAN.lower()

# The same echo in a single-backtick span that crosses a line break. Measured
# 2026-09-24: the per-line citation scan cannot close it, so it still matches.
ECHO_CODE_SPAN = (
    "## Disposition\n\n"
    "The comment opens `Verdict: **%s**, five findings. All five are\n"
    "addressed in f120e5a`, which is the reviewer's call rather than mine.\n\n"
    "**1. Addressed.** The gate was wrong.\n"
) % NOT_CLEAN.lower()

# The ARD bullet form with no "addressed in" phrase anywhere -- the shape an
# earlier draft of RX_DISPOSITION missed, which made the payload-exemption
# negative below pass for the wrong reason.
ECHO_BULLET_ONLY = (
    "## Round 3\n\n"
    "Verdict: **%s**, two findings.\n\n"
    "**1. Addressed.** The gate was wrong.\n"
    "**2. Rebutted.** The cited line does not exist.\n"
) % NOT_CLEAN.lower()

# A genuine self-review. States its own verdict; answers nothing.
SELF_REVIEW = (
    "## Self-review at `abc1234`\n\n"
    "### Verdict\n**%s**\n\n"
    "### Findings\n1. `foo()` crashes on empty input.\n"
    "2. The retry loop has no ceiling.\n"
) % NOT_CLEAN

# A genuine self-review that DOES carry disposition vocabulary, negated.
# The `SELF_REVIEW` fixture above states findings in vocabulary this hook
# never matches, so it passed under a negation-blind fire condition too --
# an adversarial review reproduced the gap here, on the honest sentence a
# self-review writes when it has found work and not yet done it.
SELF_REVIEW_NEGATED = (
    "## Self-review at `abc1234`\n\n"
    "### Verdict\n**%s**\n\n"
    "None of the findings are addressed yet --- I have not started\n"
    "implementation.\n\n"
    "1. `foo()` crashes on empty input.\n"
    "2. The retry loop has no ceiling.\n"
) % NOT_CLEAN

# The same blindness reached through the bare phrases rather than the
# quantifier: each of these is a statement that something was NOT done.
NEGATED_PHRASES = (
    "### Verdict\n**%s**\n\n"
    "This is not closed in the current diff. The concern was not answered\n"
    "below because it is out of scope, and the root cause was never\n"
    "addressed in the fix.\n"
) % NOT_CLEAN

# The OVER-correction of the negation fix. The negator is real, but it is
# broken off from the disposition by a semicolon or a conjunction, so it
# governs a different clause. A blind scan back to the sentence start
# silenced all three; a second-round adversarial review reproduced them.
# These are POSITIVE cases: each is an ordinary round-two disposition.
# The review's own table offered "None are deferred; all five are addressed
# in `f120e5a`" as a fourth row, and it IS one -- an earlier revision of this
# comment claimed `classify_verdict()` returns `''` for it "whatever verdict
# form it carries", which is false and was corrected by a later review round.
# Measured: `Changes requested`, `Blocked`, `Not ready to merge` and
# `Not clean` all classify `not-clean`, so the row reaches gate 4 and pins
# this fix under each of them. The row suppresses a verdict under one family,
# `Needs ... work` -- which is this suite's own `NOT_CLEAN` -- because of the
# 60-CHARACTER suffix window on `classify_verdict()`'s `Needs ... work` guard
# (`check-pr-fully-clean.py:2347`, `scan[match.end():match.end() + 60]`;
# ai-config#3937). An earlier revision of this comment called it a paragraph
# window, which named the wrong mechanism (review finding 10).
# Eight forms were measured with the row and without it, and the row changes
# the answer for `Needs more work` and `Needs work` and no other; `Request
# changes` and `Do not merge` return `''` with or without it, being no
# recognized verdict at all. That is why the fixture below spells its verdict
# out instead of interpolating `NOT_CLEAN`. Measuring one form and generalizing
# to all of them is the population-vs-recall failure this corpus names
# repeatedly; the row is adopted below rather than dropped.
# The REGRESSION the fix for the over-correction above shipped, and the four
# bodies a third-round adversarial review reproduced it on. Reusing
# `flag-clean-claim-over-findings.py`'s attach test whole imported that hook's
# separator vocabulary with it, which is tuned to a hedge rather than a
# negator: it breaks on a bare comma, on brackets, and on `yet`. Each of these
# is an honest self-review sentence whose negator plainly governs its
# disposition, and each began warning under that vocabulary. Two are saved by
# `SCOPE_BREAK_RX` dropping those tokens and two by `RX_ASIDE` eliding the
# aside before the scan, so the pair of mechanisms needs the pair of cases --
# neither alone kills both mutations.
HONEST_YET_IN_CONNECTOR = (
    "### Verdict\n**%s**\n\n"
    "No finding is yet addressed in the diff above.\n"
) % NOT_CLEAN

HONEST_PARENTHETICAL = (
    "### Verdict\n**%s**\n\n"
    "Nothing (not even the trivial rename) is addressed in this branch.\n"
) % NOT_CLEAN

HONEST_BREAK_IN_COMMA_ASIDE = (
    "### Verdict\n**%s**\n\n"
    "None of these, though small and fiddly, are addressed in this push.\n"
) % NOT_CLEAN

# A negator INSIDE an aside qualifies the aside, never the sentence. Each of
# these five is an affirmative verdict echo wearing one: the sentence claims
# the work IS addressed, and only the parenthetical, bracket, or appositive
# carries a negator. Blanking asides from the connector alone left that inner
# negator eligible as `last`, so all five went silent (review round 4,
# findings 1 and 2). Their controls are the four HONEST_* fixtures above,
# where the negator sits OUTSIDE the aside and must keep governing.
ECHO_NEGATOR_IN_PARENTHETICAL = (
    "### Verdict\n**%s**\n\n"
    "Two findings (none of which matter) are addressed in `f120e5a`.\n"
) % NOT_CLEAN

ECHO_NEGATOR_IN_BRACKET = (
    "### Verdict\n**%s**\n\n"
    "The blockers [none are new] are addressed in `f120e5a`.\n"
) % NOT_CLEAN

ECHO_NEGATOR_IN_COMMA_ASIDE = (
    "### Verdict\n**%s**\n\n"
    "Five items, none trivial, are addressed in `f120e5a`.\n"
) % NOT_CLEAN

# `, and,` and `, but,` are clause boundaries wearing an aside's punctuation.
# RX_ASIDE is leftmost-first, so it ate the conjunction SCOPE_BREAK_RX retains
# as a break and left the negator governing the clause after it.
ECHO_CONJUNCTION_COMMA_PAIR_AND = (
    "### Verdict\n**%s**\n\n"
    "Nothing is blocking, and, as noted, all five are addressed in `f120e5a`.\n"
) % NOT_CLEAN

# Round 6, finding 2: the same clause boundary with an adverbial between the
# conjunction and its comma. Only punctuation separates these from
# ECHO_CONJUNCTION_COMMA_PAIR_AND above.
ECHO_COORD_ADVERBIAL_AND = (
    "### Verdict\n**%s**\n\n"
    "Nothing is blocking, and as noted, all five are addressed in `f120e5a`.\n"
) % NOT_CLEAN

ECHO_COORD_ADVERBIAL_BUT = (
    "### Verdict\n**%s**\n\n"
    "Nothing is blocking, but in the end, all five are addressed in `f120e5a`.\n"
) % NOT_CLEAN

ECHO_COORD_ADVERBIAL_SO = (
    "### Verdict\n**%s**\n\n"
    "Nothing is blocking, so after review, all five are addressed in `f120e5a`.\n"
) % NOT_CLEAN

# Round 7, finding 2: the six honest self-reviews round 6's widening cost.
# Each negator governs its clause ACROSS an interrupting comma aside that
# happens to open with a coordinator, which is a shape ordinary prose writes
# constantly -- the reviewer counted 2383 such spans in `shared/*.md` against
# five of the bare `, and,` form the widening was aimed at.
HONEST_COORD_ASIDES = (
    ("a bare adverbial (so far)",
     "No finding, so far, is addressed in `f120e5a`."),
    ("a hedging clause (so far as I can tell)",
     "Nothing, so far as I can tell, is addressed in `f120e5a`."),
    ("a parenthetical clause (and I checked each one)",
     "None of the findings, and I checked each one, are addressed in `f120e5a`."),
    ("an emphatic aside (and this is the key point)",
     "None of these, and this is the key point, are addressed in `f120e5a`."),
    ("an alternative aside (or nit for that matter)",
     "No blocker, or nit for that matter, is addressed in `f120e5a`."),
    ("an exception aside (but the docs)",
     "Nothing, but the docs, is addressed in `f120e5a`."),
)


def honest_aside_body(sentence):
    """A not-clean self-review whose one sentence is `sentence`."""
    return "### Verdict\n**%s**\n\n%s\n" % (NOT_CLEAN, sentence)


# Round 6, finding 8: a `yet` boundary followed by a genuine comma aside.
ECHO_YET_BEFORE_ASIDE = (
    "### Verdict\n**%s**\n\n"
    "Nothing is blocking, yet, because of the rename, all five are addressed"
    " in `f120e5a`.\n"
) % NOT_CLEAN

ECHO_CONJUNCTION_COMMA_PAIR_BUT = (
    "### Verdict\n**%s**\n\n"
    "None of it is done, but, crucially, all five are addressed in `f120e5a`.\n"
) % NOT_CLEAN

HONEST_BREAK_IN_PARENTHETICAL = (
    "### Verdict\n**%s**\n\n"
    "Nothing (and this matters) is addressed in this branch.\n"
) % NOT_CLEAN

# Round 5, finding 1. Round 4 blanked comma asides across the WHOLE window,
# and the alternation is leftmost-first, so it paired the comma CLOSING an
# introductory phrase with the comma OPENING the real appositive -- deleting
# the sentence's own negator. Both of these are honest dispositions saying
# the work is NOT done, and both began warning. Measured against `00085a22`:
# the first reported `are addressed`, the second `addressed in`.
#
# They are the control the suite lacked. Every HONEST_* fixture above puts
# the negator at the start of its clause; only a comma BEFORE the negator
# reaches the mis-pairing, so none of them could catch it.
HONEST_INTRO_COMMA_BEFORE_NEGATOR = (
    "### Verdict\n**%s**\n\n"
    "Of the 18 findings, none, including #9, are addressed in `f120e5a`.\n"
) % NOT_CLEAN

HONEST_INTRO_COMMA_NEGATED_NOUN = (
    "### Verdict\n**%s**\n\n"
    "Per the brief, no finding, however minor, is addressed in `f120e5a`.\n"
) % NOT_CLEAN

# Round 5, finding 2. `RX_ASIDE` restated four of `SCOPE_BREAK_RX`'s eighteen
# clause openers as its own list, so `, however,` -- a clause boundary
# wearing an aside's punctuation, exactly like `, and,` below -- was elided
# and the negator went on governing the clause after it. Silent at
# `00085a22`, measured. Its control is HONEST_BREAK_IN_COMMA_ASIDE above,
# where the same class of word opens a span with real content after it and
# must still be elided.
ECHO_BARE_HOWEVER_COMMA_PAIR = (
    "### Verdict\n**%s**\n\n"
    "Nothing is blocking, however, all five are addressed in `f120e5a`.\n"
) % NOT_CLEAN

# The reviewer's own fourth row. Its verdict is spelled out rather than
# interpolated from `NOT_CLEAN`, per the comment above: under "Needs more
# work" this body is stopped at gate 3 by ai-config#3937 and would pin
# nothing.
# The other half of the window bound, and the half no case reached until a
# mutation sweep asked for it. `SCOPE_BREAK_RX` carries no sentence-ending
# period, so the attach test alone cannot tell a negator in the CURRENT
# clause from one a sentence or a paragraph back -- only the scan back to the
# last clause start does. Each of these is a genuine echo whose only negator
# belongs to an earlier sentence, and each goes silent if that bound is
# widened to the whole body.
NEGATOR_A_SENTENCE_BACK = (
    "### Verdict\n**%s**\n\n"
    "Nothing here is a blocker. The retry ceiling is addressed in `f120e5a`.\n"
) % NOT_CLEAN

NEGATOR_A_PARAGRAPH_BACK = (
    "### Verdict\n**%s**\n\n"
    "None of this is deferred.\n\n"
    "The retry ceiling is addressed in `f120e5a`.\n"
) % NOT_CLEAN

REVIEWER_ROW = (
    "### Verdict\n**Changes requested**\n\n"
    "None are deferred; all five are addressed in `f120e5a`.\n"
)

NEGATOR_IN_OTHER_CLAUSE = (
    "### Verdict\n**%s**\n\n"
    "Nothing was deferred; the retry ceiling is addressed in `f120e5a`.\n"
) % NOT_CLEAN

HEDGE_IN_OTHER_CLAUSE = (
    "### Verdict\n**%s**\n\n"
    "You should hold off on #99, but all five are addressed in `abc123`.\n"
) % NOT_CLEAN

NEGATOR_IN_PRIOR_BULLET = (
    "### Verdict\n**%s**\n\n"
    "- No further pushes planned\n"
    "- Addressed in `f120e5a`\n"
) % NOT_CLEAN

# A formal review SUBMITTED through the review surface, carrying ARD labels
# because it re-reports one item as fixed, and its own not-clean verdict.
# Fire condition 5 exists to leave this alone; the inherited MCP tuple
# reached it until the two review surfaces were subtracted by name.
FORMAL_REVIEW_BODY = (
    "### Findings\n\n"
    "**1. Addressed.** The caller now re-reads the ref.\n"
    "**2.** The retry loop still has no ceiling.\n\n"
    "### Verdict: %s\n"
) % NOT_CLEAN

# A closed markdown-italic ARD label. `_` is a word character, so the verb
# has no word boundary after it and a `\b`-terminated pattern cannot match.
ITALIC_ARD_LABEL = (
    "## Disposition at `f120e5a`\n\n"
    "### Verdict\n**%s**\n\n"
    "_Addressed_ in the push above.\n"
) % NOT_CLEAN

# A disposition that quotes the REVIEWER's payload back, to say what the
# review concluded. The payload is not this comment's own, so it must not
# exempt the comment -- `classify_verdict()` reads it as this author's
# verdict all the same, which is the incident's own shape.
QUOTED_PAYLOAD = (
    "## Disposition at `f120e5a`\n\n"
    "Verdict: **%s**, the reviewer said.\n\n"
    "**1. Addressed.** Fixed in `abc123`.\n\n"
    "It concluded:\n\n"
    "> <!-- review-data:\n"
    '> {"schema_version": "1.1", "verdict": "NOT_CLEAN"}\n'
    "> -->\n"
) % NOT_CLEAN

# A real review, carrying the machine payload a review emits.
REVIEW_WITH_PAYLOAD = (
    "### Verdict\n**%s**\n\n"
    "<details><summary>Structured Review Data (JSON)</summary>\n"
    '<!-- review-data: {"schema_version": "1.1", "verdict": "NOT_CLEAN"} -->\n'
    "</details>\n\n"
    "**1. Addressed.** Carried deliberately: this body has disposition\n"
    "vocabulary AND a not-clean verdict, so only the payload exemption keeps\n"
    "the guard silent. Without that, the case would pass for the wrong reason.\n"
) % NOT_CLEAN

# The rendering that works: the call described, never reproduced.
DESCRIBED_NOT_ECHOED = (
    "## Review round 2 --- adversarial review at `75acd84`\n\n"
    "The second review round returned a not-clean call with five findings. Its\n"
    "exact wording is deliberately not reproduced here.\n\n"
    "All five are addressed in `f120e5a`.\n\n"
    "**1--2. Addressed.** The backstop step's gate was wrong.\n"
)

# A clean disposition: answers findings, states nothing not-clean.
CLEAN_DISPOSITION = (
    "## Disposition at `727693d8`\n\n"
    "Every finding from the last round is addressed in `f120e5a`.\n"
    "14 check runs, 13 success and 1 skipped.\n"
)

# Prose about the mechanism with no disposition vocabulary at all.
DOCS_ABOUT_THE_RULE = (
    "The scanner reads a line-start verdict label as authored. A body stating\n"
    "**%s** therefore becomes this author's own standing verdict.\n"
) % NOT_CLEAN


_CASE = [0]

# Every subprocess gets a TMPDIR created for THIS run. The hook writes a
# once-per-(transcript, body) sentinel under `tempfile.gettempdir()`, so a
# suite reusing the system temp dir passes on its first run and then reports
# every positive case as a failure on every run after -- which reads exactly
# like the guard being broken rather than like the suite not being repeatable.
# Measured while writing this file: the second run failed all five positives.
_TMP = tempfile.mkdtemp(prefix="verdict-echo-tests-")


def run(tool_name, tool_input, cwd=None, tmpdir=None):
    # A distinct transcript_path per case as well, because two cases sharing a
    # body would otherwise see the second suppressed by the first's sentinel,
    # which reads the same way.
    _CASE[0] += 1
    payload = {"tool_name": tool_name, "tool_input": tool_input,
               "cwd": cwd or ROOT,
               "transcript_path": "/nonexistent/case-%d.jsonl" % _CASE[0]}
    env = dict(os.environ)
    env["TMPDIR"] = tmpdir or _TMP
    proc = subprocess.run(
        [sys.executable, HOOK], input=json.dumps(payload),
        capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        return None
    out = (proc.stdout or "").strip()
    if not out:
        return None
    try:
        return json.loads(out)
    except Exception:
        return None


def fired(tool_name, tool_input, cwd=None, tmpdir=None):
    out = run(tool_name, tool_input, cwd, tmpdir=tmpdir)
    if not out:
        return False
    ctx = (out.get("hookSpecificOutput") or {}).get("additionalContext")
    return bool(ctx)


def mcp(body, tool="mcp__github__add_issue_comment", tmpdir=None):
    return fired(tool, {"owner": "o", "repo": "r", "issue_number": 1, "body": body},
                 tmpdir=tmpdir)


FAILURES = []


def check(name, got, want):
    if got != want:
        FAILURES.append(f"{name}: expected fired={want}, got fired={got}")
    print(f"  {'ok  ' if got == want else 'FAIL'}  {name}")


def main():
    # Import the hook's own predicate for the unit-level cases, so a change to
    # the classifier is visible here and not only through the subprocess.
    import importlib.util
    spec = importlib.util.spec_from_file_location("_hook_under_test", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    if mod.classify_verdict is None:
        print("SKIP: check-pr-fully-clean.py's classify_verdict is unavailable")
        return 0

    print("Negative control on the classifier itself:")
    # Guards against a vacuous suite: if the classifier stopped reading these as
    # not-clean, every positive case below would pass for the wrong reason.
    for label, body in (("line-start echo", ECHO_DISPOSITION),
                        ("blockquoted echo", ECHO_BLOCKQUOTED),
                        ("code-spanned echo", ECHO_CODE_SPAN)):
        got = mod.classify_verdict(body)
        check(f"classifier still reads {label} as not-clean", got, "not-clean")
    tools = getattr(mod, "MCP_POST_TOOLS", ())
    check("the MCP tool list carries no duplicate",
          len(tools) == len(set(tools)) and len(tools) > 0, True)
    check("classifier reads the described form as no-verdict",
          mod.classify_verdict(DESCRIBED_NOT_ECHOED), "")

    print("Positive cases (must fire):")
    check("line-start echo in a disposition", mcp(ECHO_DISPOSITION), True)
    check("blockquoting does not exempt it", mcp(ECHO_BLOCKQUOTED), True)
    check("a code span does not exempt it", mcp(ECHO_CODE_SPAN), True)
    check("the ARD bullet form alone is disposition vocabulary",
          mcp(ECHO_BULLET_ONLY), True)
    check("a closed italic ARD label still matches", mcp(ITALIC_ARD_LABEL), True)
    check("a QUOTED review payload does not exempt the comment",
          mcp(QUOTED_PAYLOAD), True)
    check("an edit to an existing comment is covered",
          mcp(ECHO_DISPOSITION, "mcp__github__update_issue_comment"), True)
    check(
        "a gh pr comment carrying the echo",
        fired("Bash", {"command":
                       "gh pr comment 49 --body \"%s\"" %
                       ECHO_DISPOSITION.replace('"', "'")}),
        True,
    )

    check("a negator in a neighbouring clause still warns",
          mcp(NEGATOR_IN_OTHER_CLAUSE), True)
    check("a hedge in a neighbouring clause still warns",
          mcp(HEDGE_IN_OTHER_CLAUSE), True)
    check("a negator in a previous bullet still warns",
          mcp(NEGATOR_IN_PRIOR_BULLET), True)
    check("the reviewer's own semicolon row still warns",
          mcp(REVIEWER_ROW), True)
    check("a negator a sentence back does not reach the disposition",
          mcp(NEGATOR_A_SENTENCE_BACK), True)
    check("a negator a paragraph back does not reach the disposition",
          mcp(NEGATOR_A_PARAGRAPH_BACK), True)
    check("a heredoc-written body is read, not called unreadable",
          fired("Bash", {"command":
                         "cat > /tmp/vb.md <<'EOF'\n%s\nEOF\n"
                         "gh pr comment 49 --body-file /tmp/vb.md"
                         % ECHO_DISPOSITION}),
          True)

    print("Negative cases (must stay silent):")
    check("a genuine self-review stating its own verdict",
          mcp(SELF_REVIEW), False)
    check("a self-review whose disposition vocabulary is NEGATED",
          mcp(SELF_REVIEW_NEGATED), False)
    check("negated disposition phrases stay silent",
          mcp(NEGATED_PHRASES), False)
    check("a real review carrying a review-data payload",
          mcp(REVIEW_WITH_PAYLOAD), False)
    check("the call described rather than reproduced",
          mcp(DESCRIBED_NOT_ECHOED), False)
    check("a clean disposition", mcp(CLEAN_DISPOSITION), False)
    check("prose about the rule with no disposition vocabulary",
          mcp(DOCS_ABOUT_THE_RULE), False)
    check("an empty body", mcp(""), False)
    check("a negator reaching past `yet` stays silent",
          mcp(HONEST_YET_IN_CONNECTOR), False)
    check("a negator reaching past a parenthetical stays silent",
          mcp(HONEST_PARENTHETICAL), False)
    check("a break token inside a comma aside does not sever the negator",
          mcp(HONEST_BREAK_IN_COMMA_ASIDE), False)
    check("a break token inside a parenthetical does not sever the negator",
          mcp(HONEST_BREAK_IN_PARENTHETICAL), False)
    check("a negator inside a parenthetical does not govern the sentence",
          mcp(ECHO_NEGATOR_IN_PARENTHETICAL), True)
    check("a negator inside a bracket does not govern the sentence",
          mcp(ECHO_NEGATOR_IN_BRACKET), True)
    # ACCEPTED MISS, and pinned as one rather than deleted. Round 4 made this
    # warn by blanking comma asides window-wide; round 5 measured that the
    # same blanking warns on five honest self-reviews (the two HONEST_INTRO_*
    # fixtures above are two of them), because a comma span's extent is a
    # guess. No regex separates "Five items, none trivial, are addressed"
    # from "Of the 18 findings, none, including #9, are addressed" without
    # knowing which noun the verb agrees with, so the tie goes to silence --
    # the cheap direction for a warn-only hook. Tracked as ai-config#3947.
    check("a negator in a lone comma appositive is an accepted miss",
          mcp(ECHO_NEGATOR_IN_COMMA_ASIDE), False)
    check("an intro comma before the negator stays silent",
          mcp(HONEST_INTRO_COMMA_BEFORE_NEGATOR), False)
    check("an intro comma before a negated noun stays silent",
          mcp(HONEST_INTRO_COMMA_NEGATED_NOUN), False)
    check("a bare `, however,` pair is a clause boundary, not an aside",
          mcp(ECHO_BARE_HOWEVER_COMMA_PAIR), True)
    check("a `, and,` pair is a clause boundary, not an aside",
          mcp(ECHO_CONJUNCTION_COMMA_PAIR_AND), True)
    # Round 6 made these three warn by disqualifying any comma span that
    # OPENS with a coordinator. Round 7 reverted that: measured with only the
    # pattern swapped, the widening bought these three and cost six false
    # alarms on honest negated self-reviews (finding 2). For a warn-only
    # guard that trade is the wrong way round, so they are accepted misses,
    # tracked as ai-config#3953, and pinned here so the widening cannot
    # return without this expectation changing with it.
    check("a coordinator plus an adverbial is an accepted miss (and)",
          mcp(ECHO_COORD_ADVERBIAL_AND), False)
    check("a coordinator plus an adverbial is an accepted miss (but)",
          mcp(ECHO_COORD_ADVERBIAL_BUT), False)
    check("a coordinator plus an adverbial is an accepted miss (so)",
          mcp(ECHO_COORD_ADVERBIAL_SO), False)
    # The six sentences that widening cost. Each is an honest self-review
    # whose negator governs the clause across an interrupting aside, and
    # each is the population fire condition 6 exists to protect.
    for _label, _sentence in HONEST_COORD_ASIDES:
        check("an honest negated self-review survives %s" % _label,
              mcp(honest_aside_body(_sentence)), False)
    # Round 6, finding 8. `_ASIDE_COORDINATORS` carried `|yet|nor`, which no
    # case pinned: dropping it left the whole suite green. It was also the
    # wrong answer, because eliding is leftmost-first -- refusing the
    # `, yet,` span spent the elision on the NEXT comma pair, and that pair
    # was the genuine aside carrying a real scope break.
    check("a yet-clause boundary ahead of a real aside still warns",
          mcp(ECHO_YET_BEFORE_ASIDE), True)
    check("a `, but,` pair is a clause boundary, not an aside",
          mcp(ECHO_CONJUNCTION_COMMA_PAIR_BUT), True)
    # Two heredocs, and the one the post reads is the SECOND. An earlier draft
    # took whichever heredoc came first, so this body was read through the
    # release notes and reported unreadable.
    # Review round 4, findings 5, 13 and 14: the tie was an unanchored
    # substring, the terminator was not end-anchored, and only one of the
    # three body-file spellings was recognized. Each failed silently -- a
    # body scanned that is never posted, a body truncated above its own
    # verdict echo, a body never scanned at all.
    check("a basename collision does not tie to the wrong heredoc",
          fired("Bash", {"command":
                         "cat > /tmp/vb.md.bak <<'A'\n%s\nA\n"
                         "gh pr comment 49 --body-file /tmp/vb.md"
                         % ECHO_DISPOSITION}),
          False)
    check("a body line beginning with the delimiter word does not truncate",
          fired("Bash", {"command":
                         "cat > /tmp/v.md <<'EOF'\nIntro line.\n"
                         "EOF is the delimiter we use.\n%s\nEOF\n"
                         "gh pr comment 1 --body-file /tmp/v.md"
                         % ECHO_DISPOSITION}),
          True)
    check("a heredoc tied through -F body=@ is read",
          fired("Bash", {"command":
                         "cat > /tmp/notes.md <<'A'\nRelease notes.\nA\n"
                         "cat > /tmp/v.md <<'B'\n%s\nB\n"
                         "gh api repos/o/r/issues/1/comments -F body=@/tmp/v.md"
                         % ECHO_DISPOSITION}),
          True)
    # Review finding 18: every `<<` is a scan start, and an unterminated one
    # scans to the end, so cost is quadratic in the OPENER COUNT -- 3200
    # openers in a 25 KiB command took 4.6s in a hook that runs on every Bash
    # call. The bound is on the count and not the length, so the pair below
    # is the point: the pathological small command is refused, and a single
    # heredoc carrying a full-size comment body still ties.
    # The command below carries a REAL, tie-able heredoc, so without the bound
    # it returns that body. An earlier draft used openers with no terminator,
    # which returns None with or without the bound -- a case that passes under
    # its own mutation and therefore tests nothing.
    _many = ("x <<EOF\n" * (mod.MAX_HEREDOC_OPENERS + 1)
             + "cat > /tmp/v.md <<'A'\n%s\nA\n"
               "gh pr comment 1 --body-file /tmp/v.md\n" % ECHO_DISPOSITION)
    check("a command past the opener bound is refused rather than scanned",
          mod._heredoc_body_for(_many, _many) is None, True)
    # Round 6, finding 1. `_many` puts one opener per line, so it passed
    # while the counter's trailing `[^\n]*\n` folded every opener SHARING a
    # line into one match: 3200 counted as 1, the bound stopped bounding, and
    # `RX_HEREDOC`'s quadratic scan ran unchecked for 13.35 s on a 6463-byte
    # command -- paid as a stall of the Bash call this hook gates. The axis
    # the defect lives on is openers-per-line, which no case varied.
    check("openers sharing one line are counted individually",
          len(mod.RX_HEREDOC_OPENER.findall("x <<A <<B <<C\n")), 3)
    _oneline = ("x " + "<<EOF " * (mod.MAX_HEREDOC_OPENERS + 1) + "\n"
                + "cat > /tmp/v.md <<'A'\n%s\nA\n"
                  "gh pr comment 1 --body-file /tmp/v.md\n" % ECHO_DISPOSITION)
    check("a one-line command past the opener bound is refused too",
          mod._heredoc_body_for(_oneline, _oneline) is None, True)
    # Round 7, finding 1. The opener count is one of TWO cost variables.
    # `RX_HEREDOC`'s capturing `([^\n]*)` prefix may match empty, so the
    # engine restarts at every character of every line and each restart walks
    # that line -- cost is the sum of the SQUARES of the line lengths, and a
    # command with NO opener at all reaches it. The pair below is the point,
    # both arms carrying the same 25600 bytes and a real tie-able heredoc:
    # the one-line arm is refused and the line-broken arm still ties.
    _post = ("cat > /tmp/v.md <<'A'\n%s\nA\n"
             "gh pr comment 1 --body-file /tmp/v.md\n" % ECHO_DISPOSITION)
    _longline = "echo '" + "q" * 25600 + "' > /tmp/blob.txt\n" + _post
    check("a long single line is refused however few openers it carries",
          mod._heredoc_body_for(_longline, _longline) is None, True)
    _broken = ("echo '" + "q" * 79 + "' >> /tmp/blob.txt\n") * 320 + _post
    check("the same bytes broken into lines are still read",
          mod._heredoc_body_for(_broken, _broken) is not None, True)
    # ... and the case a plain LENGTH cap would have broken instead: a
    # heredoc BODY is not scanned, so a full-size body on one line is cheap.
    _fatbody = ("cat > /tmp/v.md <<'A'\n%s\n%s\nA\n"
                "gh pr comment 1 --body-file /tmp/v.md\n"
                % (ECHO_DISPOSITION, "y" * 65536))
    check("a 64 KiB body on one line is still read",
          fired("Bash", {"command": _fatbody}), True)
    # Round 7, finding 6. Counting openers over the RAW command let the
    # body's own prose vote: a disposition discussing heredoc parsing wrote
    # `<<EOF` forty times and exempted itself, which is round 5's finding 3
    # through a second token. Bodies are skipped now, so this one is read.
    _proseopeners = ("cat > /tmp/v.md <<'A'\n%s\n" % ECHO_DISPOSITION
                     + "The opener is written `<<EOF` on this line.\n"
                     * (mod.MAX_HEREDOC_OPENERS + 8)
                     + "A\ngh pr comment 1 --body-file /tmp/v.md\n")
    check("opener-shaped prose in the body does not reach the bound",
          fired("Bash", {"command": _proseopeners}), True)
    # An UNTERMINATED heredoc has no body to skip, and is the pathological
    # case itself, so its lines must still be counted.
    check("an unterminated heredoc's lines still count toward the bound",
          mod._scan_budget("x <<EOF\n" * 200)[0] > mod.MAX_HEREDOC_OPENERS,
          True)
    # Round 7, finding 5. `-F body=@-` and `--body-file -` name STDIN, not a
    # file, so the heredoc feeding them is the single-heredoc case. Adding
    # the `-F/--field` branch captured `-` as a filename and silenced the
    # idiom; the `--body-file` spelling escaped only by accident of spacing.
    for _flag in ("-F body=@-", "--field body=@-", "--body-file -"):
        _stdin = ("gh api repos/o/r/issues/1/comments %s <<'EOF'\n%s\nEOF\n"
                  % (_flag, ECHO_DISPOSITION))
        check("a heredoc piped to stdin via `%s` is read" % _flag,
              mod._heredoc_body_for(_stdin, _stdin) is not None, True)
    # Round 5, finding 3. The bound counted every `<<` in the raw command,
    # including the ones the BODY writes, so a verdict echo whose prose
    # quoted a shift operator 33 times exempted itself -- silently, because
    # an unreadable body warns about nothing. Openers are counted with the
    # opener SHAPE now, so this body is read and warns.
    _shifty = ("cat > /tmp/v.md <<'A'\n%s\n" % ECHO_DISPOSITION
               + "The sample writes `$((1 << 0))` on this line.\n"
               * (mod.MAX_HEREDOC_OPENERS + 1)
               + "A\ngh pr comment 1 --body-file /tmp/v.md\n")
    check("shift operators in the body do not reach the opener bound",
          fired("Bash", {"command": _shifty}), True)
    # Round 5, finding 4. `$` under MULTILINE matches before `\n` and at end
    # of string, never before `\r`, so end-anchoring the terminator made
    # every CRLF command unreadable -- and CLAUDE.md routes backtick-carrying
    # bodies into exactly this heredoc form on the platform most likely to
    # deliver CRLF.
    _crlf = ("cat > /tmp/v.md <<'A'\n%s\nA\n"
             "gh pr comment 1 --body-file /tmp/v.md\n"
             % ECHO_DISPOSITION).replace("\n", "\r\n")
    check("a CRLF write-then-post command is still read",
          fired("Bash", {"command": _crlf}), True)
    # Round 5, finding 5. The tie anchored the basename's right edge only, so
    # the mirror of finding 5 was still open: `--body-file /tmp/v.md` matched
    # a heredoc writing `/tmp/backup-v.md` and scanned a body that is never
    # posted. Its sibling below is the collision the same gap caused in the
    # other direction -- two hits, `len(hits) != 1`, and silence on a body
    # that plainly warrants the warning.
    check("a left-edge basename collision does not tie to the wrong heredoc",
          fired("Bash", {"command":
                         "cat > /tmp/backup-v.md <<'A'\n%s\nA\n"
                         "gh pr comment 1 --body-file /tmp/v.md"
                         % ECHO_DISPOSITION}),
          False)
    check("a same-suffix neighbour does not collide the real heredoc away",
          fired("Bash", {"command":
                         "cat > /tmp/prev-v.md <<'A'\nEarlier notes.\nA\n"
                         "cat > /tmp/v.md <<'B'\n%s\nB\n"
                         "gh pr comment 1 --body-file /tmp/v.md"
                         % ECHO_DISPOSITION}),
          True)
    # Round 5, finding 6. Bash ends a plain `<<EOF` only on a delimiter at
    # column 0 -- verified by running it -- so an indented `    EOF` inside
    # the body is body TEXT. Terminating there truncated the body above its
    # own verdict echo, which is finding 14 through a second door.
    check("an indented delimiter does not terminate a plain heredoc",
          fired("Bash", {"command":
                         "cat > /tmp/v.md <<'EOF'\nExample heredoc:\n"
                         "    EOF\n%s\nEOF\n"
                         "gh pr comment 1 --body-file /tmp/v.md"
                         % ECHO_DISPOSITION}),
          True)
    # ... and the dash form still ends on a TAB-indented one, which is the
    # only indentation bash strips.
    check("a tab-indented delimiter terminates a `<<-` heredoc",
          fired("Bash", {"command":
                         "cat > /tmp/v.md <<-'EOF'\n%s\n\tEOF\n"
                         "gh pr comment 1 --body-file /tmp/v.md"
                         % ECHO_DISPOSITION}),
          True)
    _big = ("cat > /tmp/v.md <<'A'\n" + "filler line\n" * 5000
            + ECHO_DISPOSITION + "\nA\ngh pr comment 1 --body-file /tmp/v.md\n")
    _tied = mod._heredoc_body_for(_big, _big)
    check("one heredoc carrying a 60,000-byte body still ties",
          _tied is not None and "f120e5a" in _tied, True)
    check("a heredoc tied through --field body=@ is read",
          fired("Bash", {"command":
                         "cat > /tmp/notes.md <<'A'\nRelease notes.\nA\n"
                         "cat > /tmp/v.md <<'B'\n%s\nB\n"
                         "gh api repos/o/r/issues/1/comments --field body=@/tmp/v.md"
                         % ECHO_DISPOSITION}),
          True)
    check("the heredoc tied to --body-file is the one read",
          fired("Bash", {"command":
                         "cat > /tmp/notes.md <<'A'\nRelease notes.\nA\n"
                         "cat > /tmp/vb.md <<'B'\n%s\nB\n"
                         "gh pr comment 49 --body-file /tmp/vb.md"
                         % ECHO_DISPOSITION}),
          True)
    # Fire condition 5 leaves a SUBMITTED formal review alone. Each review
    # surface is subtracted from the post tuple by name, and the body itself
    # is checked through each of them -- the tuple assertion alone would pass
    # against a guard that never looked at the body at all.
    for _surface in ("mcp__github__pull_request_review_write",
                     "mcp__github__discussion_comment_write",
                     "mcp__github__add_comment_to_pending_review"):
        check("%s is not a post surface" % _surface,
              _surface not in mod.MCP_POST_TOOLS, True)
        check("a formal review on %s is left alone" % _surface,
              fired(_surface, {"body": FORMAL_REVIEW_BODY}), False)
    # The plain-comment route is a deliberate residual, not an oversight: a
    # fallback self-review posted with `add_issue_comment` still warns.
    # Tracked as ai-config#3938 rather than asserted quiet here.
    check("a tab-led backtick run is indented code, not a fence",
          "```" in mod.authored_text("a\n\t```\nb\n\t```\nc\n"), True)

    check("a non-comment Bash command",
          fired("Bash", {"command": "git status"}), False)
    check("an unrelated tool",
          fired("Read", {"file_path": "/etc/hostname"}), False)

    print("Once per body (the sentinel):")
    shared = tempfile.mkdtemp(prefix="verdict-echo-sentinel-")
    try:
        # Both calls share a transcript AND a TMPDIR, so the second is the
        # repeat the sentinel exists to suppress. Asserted because this is the
        # behaviour that made an earlier draft of this suite unrepeatable.
        payload = {"tool_name": "mcp__github__add_issue_comment",
                   "tool_input": {"owner": "o", "repo": "r",
                                  "issue_number": 1, "body": ECHO_DISPOSITION},
                   "cwd": ROOT, "transcript_path": "/nonexistent/sentinel.jsonl"}
        env = dict(os.environ)
        env["TMPDIR"] = shared
        seen = []
        for _ in range(2):
            proc = subprocess.run([sys.executable, HOOK],
                                  input=json.dumps(payload),
                                  capture_output=True, text=True, env=env)
            out = (proc.stdout or "").strip()
            ctx = None
            if out:
                try:
                    ctx = (json.loads(out).get("hookSpecificOutput") or {}
                           ).get("additionalContext")
                except Exception:
                    ctx = None
            seen.append(bool(ctx))
        check("first post of a body warns", seen[0], True)
        check("an identical repost stays silent", seen[1], False)
    finally:
        shutil.rmtree(shared, ignore_errors=True)

    if FAILURES:
        print("\nFAILURES:")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("\nAll cases passed.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)
