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
import time

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

# The bulleted-bold-label finding. A BULLETED list of BOLD ARD labels:
# ordinary Markdown
# for a disposition list, and the shape `RX_DISPOSITION`'s prefix could not
# reach while its list marker and its emphasis run were two branches of one
# alternation rather than two optional groups. Measured against the prior
# commit: every row below returned no match, so the guard was silent on the
# artifact it exists for.
ECHO_BULLET_BOLD_ARD = (
    "## Round 3\n\n"
    "Verdict: **%s**, two findings.\n\n"
    "- **1--2. Rebutted.** The regex already handles it.\n"
    "- **3. Addressed.** The gate was wrong.\n"
) % NOT_CLEAN.lower()

# The numbered-list rendering of the same thing.
ECHO_NUMBERED_BOLD_ARD = (
    "## Round 3\n\n"
    "Verdict: **%s**, one finding.\n\n"
    "1. **Addressed.** The gate was wrong.\n"
) % NOT_CLEAN.lower()

# The zero-quantifier finding. The most HONEST disposition comment there is: it
# reports that nothing was fixed. `NEGATION_RX` carried no zero-quantifier,
# so each of these warned -- and a warning on a comment that fixed nothing is
# the direction that gets a warn-only guard switched off.
#
# The vocabulary is `scripts/check-pr-fully-clean.py`'s own `_NEGATOR_RE`
# group (`zero|hardly|barely|scarcely`), so `barely` and `scarcely` are here
# as well as `hardly`: taking one member of a group and leaving its synonyms
# behind is how two guards drift into disagreeing about the same sentence
# (the incomplete-corpus-group finding).
HONEST_ZERO_ADDRESSED = (
    "### Verdict\n**%s**\n\n"
    "Zero findings are addressed in this push.\n"
) % NOT_CLEAN

HONEST_NUMERIC_ZERO_ADDRESSED = (
    "### Verdict\n**%s**\n\n"
    "0 findings are addressed in this push.\n"
) % NOT_CLEAN

HONEST_HARDLY_ADDRESSED = (
    "### Verdict\n**%s**\n\n"
    "Hardly any are addressed in `abc1234`.\n"
) % NOT_CLEAN

HONEST_BARELY_ADDRESSED = (
    "### Verdict\n**%s**\n\n"
    "Barely any are addressed in `abc1234`.\n"
) % NOT_CLEAN

HONEST_SCARCELY_ADDRESSED = (
    "### Verdict\n**%s**\n\n"
    "Scarcely any are addressed in `abc1234`.\n"
) % NOT_CLEAN

# Each of these four words negates whatever noun FOLLOWS it, which need not
# be the disposition: `Hardly a blocker` negates the blocker and `Zero
# tolerance` the tolerance, while the claim beside them is a plain echo. An
# earlier revision admitted all four unanchored, on the reasoning that the
# corpus group in `check-pr-fully-clean.py`'s `_NEGATOR_RE` should be taken
# whole. That reasoning was a purpose mismatch: `_NEGATOR_RE` asks whether a
# whole verdict contains negation vocabulary, where a stray hit costs
# nothing, and this asks whether a negator GOVERNS one claim, where a stray
# hit silences the guard. Measured through the hook, the unanchored form
# went silent on all five clauses below while the parent warned on every
# one. They are anchored to the quantifier now -- `hardly any`, `zero
# findings`, `zero of` -- which is the same remedy the digit already used,
# and it is the `few` argument this file states two blocks down, applied to
# the four tokens that shipped with the property rather than the one that
# was declined for it.
ECHO_HARDLY_A_BLOCKER = (
    "### Verdict\n**%s**\n\n"
    "Hardly a blocker, all five are addressed in `abc1234`.\n"
) % NOT_CLEAN

ECHO_BARELY_A_MINUTE = (
    "### Verdict\n**%s**\n\n"
    "Barely a minute later, all five are addressed in `abc1234`.\n"
) % NOT_CLEAN

ECHO_SCARCELY_WORTH = (
    "### Verdict\n**%s**\n\n"
    "Scarcely worth noting, all five are addressed in `abc1234`.\n"
) % NOT_CLEAN

ECHO_HARDLY_SURPRISING = (
    "### Verdict\n**%s**\n\n"
    "Hardly surprising, all five are addressed in `abc1234`.\n"
) % NOT_CLEAN

ECHO_ZERO_TOLERANCE = (
    "### Verdict\n**%s**\n\n"
    "Zero tolerance for that, all five are addressed in `abc1234`.\n"
) % NOT_CLEAN

HONEST_HARDLY_ANYTHING = (
    "### Verdict\n**%s**\n\n"
    "Hardly anything is addressed in `abc1234`.\n"
) % NOT_CLEAN

# `few` and a bare `0` were each considered and DECLINED -- neither is in
# that corpus group, so declining them departs from nothing. Each is kept
# as a POSITIVE case so a later widening has to break a test rather than a
# silence.
#
# `few` inverts on its article -- "a few are addressed" reports that some
# WERE -- and a word-level pattern cannot see the article, so admitting `few`
# silenced the claim this guard exists for.
ECHO_A_FEW_ADDRESSED = (
    "### Verdict\n**%s**\n\n"
    "A few are addressed in `abc1234`.\n"
) % NOT_CLEAN

ECHO_QUITE_A_FEW_ADDRESSED = (
    "### Verdict\n**%s**\n\n"
    "Quite a few are addressed in `abc1234`.\n"
) % NOT_CLEAN

# A bare `0` matches any zero after a non-word character, so a version string
# or an ordinal silenced the sentence beside it. The zero is anchored to the
# noun it quantifies instead, following `no-stale-pr-status.py`'s own
# `\b0 fail(s|ures)?\b`.
ECHO_VERSION_ZERO = (
    "### Verdict\n**%s**\n\n"
    "Release v1.0 shipped, all three are addressed in `abc1234`.\n"
) % NOT_CLEAN

ECHO_LINE_ZERO = (
    "### Verdict\n**%s**\n\n"
    "On line 0 of the file, all three are addressed in `abc1234`.\n"
) % NOT_CLEAN

# The task-list finding. GitHub renders a disposition list as a task list as
# readily as a plain one, and a numbered item may sit inside a bullet.
ECHO_TASK_LIST_DONE = (
    "## Round 3\n\n"
    "Verdict: **%s**, one finding.\n\n"
    "- [x] **Addressed.** The gate was wrong.\n"
) % NOT_CLEAN.lower()

ECHO_TASK_LIST_OPEN = (
    "## Round 3\n\n"
    "Verdict: **%s**, one finding.\n\n"
    "- [ ] **Addressed.** The gate was wrong.\n"
) % NOT_CLEAN.lower()

ECHO_BULLET_THEN_NUMBER = (
    "## Round 3\n\n"
    "Verdict: **%s**, one finding.\n\n"
    "- 1. **Addressed.** The gate was wrong.\n"
) % NOT_CLEAN.lower()

# The unpinned-marker-gap mutation finding. The bullet branch's `[ \t]+` is
# what holds it to actual list items: CommonMark requires whitespace after
# the marker, and making that gap optional makes each of these match while
# none is a list item. Nothing pinned that, so the mutation left the suite
# fully green.
#
# Each body carries a verdict so it still classifies not-clean; the dashed
# line is the only thing that could supply a disposition phrase, so a fire
# here means the prefix matched prose.
PROSE_DASH_BARE = (
    "### Verdict\n**%s**\n\n"
    "-Addressed. was the shorthand in the old template.\n"
) % NOT_CLEAN

PROSE_PLUS_BARE = (
    "### Verdict\n**%s**\n\n"
    "+Addressed. was the shorthand in the old template.\n"
) % NOT_CLEAN

PROSE_DASH_BOLD = (
    "### Verdict\n**%s**\n\n"
    "-**Addressed** was the shorthand in the old template.\n"
) % NOT_CLEAN

PROSE_DASH_BOLD_LABEL = (
    "### Verdict\n**%s**\n\n"
    "-**1. Rebutted.** was the shorthand in the old template.\n"
) % NOT_CLEAN

# Every single-word negator is bounded against a HYPHEN, not just a word
# character. A hyphen is a non-word character, so `\bno\b` matched the `no` of
# `no-op` and of every `no-*.py` hook filename this corpus writes, and
# `\bzero\b` the `zero-findings`, `zero-cost` and `zero-width` compounds
# (98 of them here). In each the negator is a hyphenated adjective modifying
# something else, so the sentence beside it is a genuine positive
# disposition claim and the guard went silent on it.
#
# The `no|not|none|nothing` half of that predates this branch; `zero` added
# one more instance, which is why the whole set is bounded rather than that
# one token. These stay POSITIVE cases: the compound must NOT suppress.
#
# Each compound is written UNFENCED deliberately. The guard blanks code
# spans before scanning, so `no-op` in backticks never reaches the negator
# pattern at all -- a fixture written that way passes under the `\b` mutant
# too and pins nothing. Measured: the two `no-` cases survived that mutation
# while fenced, and kill it unfenced.
ECHO_COMPOUND_ZERO_FINDINGS = (
    "### Verdict\n**%s**\n\n"
    "The zero-findings run aside, all three are addressed in `abc1234`.\n"
) % NOT_CLEAN

ECHO_COMPOUND_ZERO_COST = (
    "### Verdict\n**%s**\n\n"
    "A zero-cost check aside, all three are addressed in `abc1234`.\n"
) % NOT_CLEAN

ECHO_COMPOUND_NO_OP = (
    "### Verdict\n**%s**\n\n"
    "The no-op path aside, all three are addressed in `abc1234`.\n"
) % NOT_CLEAN

ECHO_COMPOUND_HOOK_FILENAME = (
    "### Verdict\n**%s**\n\n"
    "The no-stale-pr-status guard aside, all three are addressed in `abc1234`.\n"
) % NOT_CLEAN

ECHO_COMPOUND_NOTHING_BURGER = (
    "### Verdict\n**%s**\n\n"
    "Nothing-burger aside, all three are addressed in `abc1234`.\n"
) % NOT_CLEAN

# The digit form is STRICTLY NARROWER than the word form, and that residual
# is pinned rather than closed: anchoring the digit to `findings?` is what
# keeps a version string from silencing the sentence, and the noun set is
# open-ended, so any enumeration of it is arbitrary. `Zero of the findings`
# suppresses; `0 of the findings` does not.
HONEST_WORD_ZERO_OF_THE = (
    "### Verdict\n**%s**\n\n"
    "Zero of the findings are addressed in this push.\n"
) % NOT_CLEAN

ECHO_DIGIT_ZERO_OF_THE = (
    "### Verdict\n**%s**\n\n"
    "0 of the findings are addressed in this push.\n"
) % NOT_CLEAN

# The negator boundary class is ASCII-only, and these two cases say why.
# `SCOPE_BREAK_RX` already treats the Unicode en and em dashes as clause
# separators, so a negator before one does not govern what follows, while
# the unspaced ASCII hyphen is deliberately NOT a scope break -- it joins.
# So the en-dash compound warns (the `zero` is out of scope) and the em
# dash suppresses (the `none` after it is in scope, and the claim really
# is negative). Measured over 2370 corpus files, U+2013 and U+2014 are the
# only Unicode dashes present at all, at 64 and 5694 occurrences.
#
# The first row was written expecting SILENCE, reasoning from `NEGATION_RX`
# in isolation, and failed -- which is the whole value of writing it. The
# regex does match `zero` there; the governing window is what overrides it.
# Admitting the dashes to the boundary class would flip the second row and
# leave the first unchanged, so that widening is all cost.
ECHO_ENDASH_ZERO_COMPOUND = (
    "### Verdict\n**%s**\n\n"
    "The zero\u2013findings run aside, all three are addressed in `abc1234`.\n"
) % NOT_CLEAN

HONEST_EMDASH_AFTER_NEGATOR = (
    "### Verdict\n**%s**\n\n"
    "No\u2014none of the three are addressed in `abc1234`.\n"
) % NOT_CLEAN

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
# (`check-pr-fully-clean.py:2368`, `scan[match.end():match.end() + 60]`;
# ai-config#3937). An earlier revision of this comment called it a paragraph
# window, which named the wrong mechanism (review finding 10).
# Eight forms were measured with the row and without it, at three SEPARATIONS,
# because that window is a character count and so the body shape decides it.
# At the blank line this fixture actually uses, the row changes no answer at
# all: it starts past the 60 characters, so every form classifies the same with
# it and without it. The suppression appears only when the row sits nearer --
# one newline, or the same line -- and then only for `Needs more work` and
# `Needs work`; `Request changes` and `Do not merge` return `''` at every
# separation, being no recognized verdict at all. An earlier revision of this
# comment reported the eight-form result without naming the separation it held
# fixed, and offered it as the reason the fixture below spells its verdict out.
# That reason was false for the fixture as written: interpolating `NOT_CLEAN`
# here leaves the suite at 124/124, the row being too far away to suppress
# anything. The real reason is that `Changes requested` is a verdict family no
# other fixture in this file carries -- so this row is what pins the fix
# outside `Needs ... work`,
# under a verdict the 60-character window never reaches at any separation.
# The count that used to sit in that sentence was wrong, and wrong in the
# way the sentence is about. It read "every one of the other 67
# interpolates `NOT_CLEAN`", which named the interpolating SUBSET and
# presented it as the whole population. Derived from the file on
# 2026-09-24, at the commit that corrects it: 72 module-level fixture
# constants (excluding `HOOK`, `ROOT`, `NOT_CLEAN`, `FAILURES` and
# `EXAMINED`), so 71 others; 68 interpolate `NOT_CLEAN` and four do not
# (`HONEST_COORD_ASIDES`, `REVIEWER_ROW` itself, `DESCRIBED_NOT_ECHOED`,
# `CLEAN_DISPOSITION`). The load-bearing half was true throughout and is
# what the sentence now rests on: no other FIXTURE in this file carries
# `Changes requested`, which is narrower than "nowhere else in this file"
# -- several comments here name it, this one included. A figure that has to be re-derived to stay true is
# better left out of a claim that does not need it (round 14, finding 6).
#
# Measuring one form, or one body shape, and generalizing to all of them is the
# population-vs-recall failure this corpus names repeatedly; the row is adopted
# below rather than dropped.
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

# A bracketed span that OPENS before the phrase and CLOSES after it is the one
# shape on which eliding brackets over the whole body and eliding them per
# window disagree (`_disqualifier_spans`): the whole-body pass blanks the span
# and with it the semicolon that severs the negator from the phrase, so the
# negator attaches and the hook goes silent. The per-window pass slices at the
# phrase, leaves the opening delimiter unmatched, and keeps the semicolon. The
# straddle fallback is what routes this hit back to the exact per-window path;
# without it this body is a MISSED disclosure, which is the expensive
# direction. Measured over 200000 random bodies, 85 of them differ this way.
ECHO_BREAK_IN_STRADDLING_PARENTHETICAL = (
    "### Verdict\n**%s**\n\n"
    "No findings are outstanding "
    "(one was a duplicate; the other two are addressed in `f120e5a`).\n"
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
# constantly, and far commoner than the bare `, and,` form the widening was
# aimed at. Round 8, finding 8: the earlier figures here cited `shared/*.md`,
# a glob that matches ZERO files in this repo, so the ratio was unverifiable
# as written. Re-derived 2026-09-24 over `shared/**/*.md` (158 files), with
# the patterns given so the numbers can be checked rather than taken:
#
#   aside = r",\s*(?:so|and|or|but|yet|nor)\b[^,\n]{0,120},"   -> 1497
#   bare  = r",\s*(?:and|or|but|so)\s*,"                      ->    6
#
# 250 to 1, and the direction is what matters rather than the magnitude.
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

# Round 9, finding 5. `_disqualified` elides code spans before scanning, and
# nothing pinned it: mutating that call to pass the raw prose through changed
# the verdict on 0 of the 40 fixture bodies, so the whole step could be
# deleted in silence. It is load-bearing because a span routinely carries
# punctuation the scope scan reads as structure -- a path's `.` is a sentence
# end to `RX_CLAUSE_START`, so an unelided `scripts/check.py` cuts the window
# between this sentence's negator and its disposition phrase and the honest
# line warns. Measured: with the elision the body is silent, without it both
# `Changes requested` and `Blocked` report `addressed in`.
HONEST_NEGATOR_ACROSS_CODE_SPAN = (
    "### Verdict\n**%s**\n\n"
    "Nothing in `scripts/check.py` is addressed in `f120e5a`.\n"
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

# ...and the paragraph-back row above cannot pin the blank line ITSELF,
# because its first paragraph also ends in a full stop, so `_clause_start_ends`
# reaches the same window start through the terminator. Dropping the
# blank-line branch from that scan therefore killed nothing. This row carries
# no terminator at all, so the blank line is the only boundary between the
# negator and the phrase: with the branch the phrase discloses, and without it
# the negator governs from the paragraph above and the hook goes silent.
ECHO_NEGATOR_ACROSS_BLANK_LINE = (
    "### Verdict\n**%s**\n\n"
    "No findings remain outstanding\n\n"
    "All five are addressed in `f120e5a`\n"
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

# The ONE body that answers differently, and the reason that narrowing is
# not pinned by the cost ceiling. Round 13 narrowed the label's gaps from
# `\s` to `[ \t]` and justified it by cost; a round-14 review measured the
# revert and found the suite still 124/124 and the ceiling 0.16s against
# 0.20s, so nothing in this file could see it. The gap here spans a newline,
# which `\s` crosses and `[ \t]` does not: a "3" alone on one line and a
# ". Rebutted" on the next is not a numbered disposition, and reading it as
# one warns on a body that echoes nothing.
#
# It covers the THIRD of the label's four gaps -- the one before the
# punctuation -- and not the other three, which round 14's comment here got
# wrong in both the count and the coverage (round 15, finding 4). Measured
# by widening one slot at a time: slot 3 takes this row to 124/125 and slots
# 1, 2 and 4 leave the suite untouched. ai-config#3982 tracks the rest.
#
# The disposition word is `Rebutted` deliberately. The first draft used
# `Addressed` and fired under BOTH spellings, because `RX_DISPOSITION` has
# later alternatives that need no label at all and `\baddressed\s+in\b`
# matched the sentence outright -- a row that cannot see the construct it
# names, which is this suite's own vacuous-assertion failure.
LABEL_GAP_SPANS_NEWLINE = (
    "## Round 2\n\n"
    "The reviewer's call was **%s**, quoted here from its report.\n\n"
    "3\n"
    ". Rebutted, for the reason set out below.\n"
) % NOT_CLEAN

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
# Every `check` call increments this, so the summary reports the population
# examined rather than only the verdict over it. A suite that prints "all
# passed" and nothing else reads identically whether it ran 84 cases or two,
# which is the shape `algorithmatize-checks.md` and gha's own suites both
# rule out -- report what was examined, not only what was found (round 8,
# finding 7).
EXAMINED = 0


def check(name, got, want):
    global EXAMINED
    EXAMINED += 1
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
    check("a bulleted list of bold ARD labels matches",
          mcp(ECHO_BULLET_BOLD_ARD), True)
    check("a numbered list of bold ARD labels matches",
          mcp(ECHO_NUMBERED_BOLD_ARD), True)
    check("a completed task-list disposition matches",
          mcp(ECHO_TASK_LIST_DONE), True)
    check("an open task-list disposition matches",
          mcp(ECHO_TASK_LIST_OPEN), True)
    check("a numbered item nested in a bullet matches",
          mcp(ECHO_BULLET_THEN_NUMBER), True)
    check("`a few are addressed` reports that some WERE, so it still warns",
          mcp(ECHO_A_FEW_ADDRESSED), True)
    check("`quite a few are addressed` still warns",
          mcp(ECHO_QUITE_A_FEW_ADDRESSED), True)
    check("a version string's zero does not silence the sentence beside it",
          mcp(ECHO_VERSION_ZERO), True)
    check("an ordinal zero does not silence the sentence beside it",
          mcp(ECHO_LINE_ZERO), True)
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
    check("a blank line alone ends the negator's clause",
          mcp(ECHO_NEGATOR_ACROSS_BLANK_LINE), True)
    check("a break inside a parenthetical straddling the phrase still warns",
          mcp(ECHO_BREAK_IN_STRADDLING_PARENTHETICAL), True)
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
    check("\"Zero findings are addressed\" is an honest report, not an echo",
          mcp(HONEST_ZERO_ADDRESSED), False)
    check("a zero anchored to the noun it quantifies reads as a negator",
          mcp(HONEST_NUMERIC_ZERO_ADDRESSED), False)
    check("`hardly any are addressed` reads as a negator",
          mcp(HONEST_HARDLY_ADDRESSED), False)
    check("`barely any are addressed` reads as a negator",
          mcp(HONEST_BARELY_ADDRESSED), False)
    check("`scarcely any are addressed` reads as a negator",
          mcp(HONEST_SCARCELY_ADDRESSED), False)
    check("`hardly a blocker` negates the blocker, not the claim",
          mcp(ECHO_HARDLY_A_BLOCKER), True)
    check("`barely a minute` negates the minute",
          mcp(ECHO_BARELY_A_MINUTE), True)
    check("`scarcely worth noting` negates the noting",
          mcp(ECHO_SCARCELY_WORTH), True)
    check("`hardly surprising` negates the surprise",
          mcp(ECHO_HARDLY_SURPRISING), True)
    check("`zero tolerance` negates the tolerance",
          mcp(ECHO_ZERO_TOLERANCE), True)
    check("`hardly anything` is still an honest negation",
          mcp(HONEST_HARDLY_ANYTHING), False)
    check("a `zero-findings` compound does not suppress the claim beside it",
          mcp(ECHO_COMPOUND_ZERO_FINDINGS), True)
    check("a `zero-cost` compound does not suppress it either",
          mcp(ECHO_COMPOUND_ZERO_COST), True)
    check("a `no-op` compound does not suppress it",
          mcp(ECHO_COMPOUND_NO_OP), True)
    check("a hyphenated hook name does not suppress it",
          mcp(ECHO_COMPOUND_HOOK_FILENAME), True)
    check("a `Nothing-burger` compound does not suppress it",
          mcp(ECHO_COMPOUND_NOTHING_BURGER), True)
    check("the WORD zero quantifies an open noun phrase and suppresses",
          mcp(HONEST_WORD_ZERO_OF_THE), False)
    check("the DIGIT zero is anchored to `findings`, so this residual warns",
          mcp(ECHO_DIGIT_ZERO_OF_THE), True)
    check("an en dash is already a scope break, so the compound warns",
          mcp(ECHO_ENDASH_ZERO_COMPOUND), True)
    check("an em dash after a negator is punctuation, not a compound join",
          mcp(HONEST_EMDASH_AFTER_NEGATOR), False)
    check("a bare dash is not a list marker", mcp(PROSE_DASH_BARE), False)
    check("a bare plus is not a list marker", mcp(PROSE_PLUS_BARE), False)
    check("a dash glued to a bold run is not a list marker",
          mcp(PROSE_DASH_BOLD), False)
    check("a dash glued to a bold ARD label is not a list marker",
          mcp(PROSE_DASH_BOLD_LABEL), False)
    check("a real review carrying a review-data payload",
          mcp(REVIEW_WITH_PAYLOAD), False)
    check("the call described rather than reproduced",
          mcp(DESCRIBED_NOT_ECHOED), False)
    check("a clean disposition", mcp(CLEAN_DISPOSITION), False)
    check("an ARD label whose own gap spans a newline is not a disposition",
          mcp(LABEL_GAP_SPANS_NEWLINE), False)
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
    check("punctuation inside a code span does not sever the negator",
          mcp(HONEST_NEGATOR_ACROSS_CODE_SPAN), False)
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
    # Round 8, finding 1. A THIRD cost axis the other two cannot see: an
    # untied opener makes `RX_HEREDOC` scan to the end of the string.
    # Measured at 3.6 MB of 4-character lines, 0 untied took 0.33s and 31
    # took 33.84s while the restart cost moved by 3000 and the opener count
    # stayed inside its bound -- 35s against a registered 10-second timeout.
    # Asserted as a comparison rather than a wall-clock measurement, which
    # would be a flaky test of a fast machine.
    # ONE-character lines on purpose. The restart cost is the sum of the
    # SQUARES of the line lengths, so 4-character lines already score more
    # than the command's own length and the assertion below passes with the
    # length term deleted -- a vacuous case, confirmed by mutation. At width
    # 1 the sum of squares is half the length, so only the term can carry it
    # over.
    _body = "\n".join(["x"] * 300000)
    _untied = "cat <<NOPE\n" + _body
    _tied = "cat <<NOPE\n" + _body + "\nNOPE\n"
    _untied_cost = mod._scan_budget(_untied)[1]
    _tied_cost = mod._scan_budget(_tied)[1]
    check("an untied opener is charged the whole command length",
          _untied_cost > len(_untied), True)
    # ... and a TIED one is not, which is what keeps the 64 KiB body above
    # admitted. Its body is skipped, so it scores a few hundred against the
    # untied form's millions. Charging the term per opener regardless would
    # pass the check above and silence that case.
    check("a tied heredoc pays no length term",
          _tied_cost < 1000 and _untied_cost > 1000 * _tied_cost, True)
    # Round 9, finding 1. That measurement held the opener's LINE at 4
    # characters, so it could not see which factor the term scales with, and
    # the term it produced -- untied COUNT times total length -- was wrong.
    # `RX_HEREDOC` opens with `([^\n]*)`, which matches empty, so `finditer`
    # restarts at every character of the untied opener's line rather than
    # once per opener sitting on it. Varying the line length instead, at
    # 200000 trailing lines, L=400/800/1600/2400 took
    # 5.60s/11.26s/22.78s/34.40s and all four were admitted.
    #
    # Isolated against a no-opener control of the same shape, so the sum of
    # squares -- which grows with the line length too -- cannot carry the
    # assertion. The remainder is the term itself, and the two remainders
    # stand in the ratio of the two line lengths only under the line-length
    # model; under the count model both equal the command length.
    _pad = "x" * 990
    _short_term = (mod._scan_budget("cat <<NOPE\n" + _body)[1]
                   - mod._scan_budget("cat ppNOPE\n" + _body)[1])
    _long_term = (mod._scan_budget("cat <<NOPE " + _pad + "\n" + _body)[1]
                  - mod._scan_budget("cat ppNOPE " + _pad + "\n" + _body)[1])
    check("the untied term scales with the opener LINE's length",
          _long_term > 50 * _short_term, True)
    # ... and once per line, not once per opener. Both lines are 13
    # characters, so every other term is identical and only the count model
    # separates them.
    _one_opener = mod._scan_budget("cat <<A ppppp\n" + _body)[1]
    _two_openers = mod._scan_budget("cat <<A <<B q\n" + _body)[1]
    check("two untied openers on one line cost what one does",
          _one_opener == _two_openers, True)
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
    # The case above indents with SPACES, so it survives a mutation that
    # strips TABS unconditionally -- the delimiter still fails to match, for
    # the wrong reason. Round 8, finding 2. Only a TAB-indented delimiter
    # inside a PLAIN heredoc separates the conditional `(?(2)[\t]*)` from an
    # unconditional `[\t]*`: bash strips leading tabs for `<<-` alone, so
    # here the tabbed line is body text and the body runs on to the echo.
    check("a tab-indented delimiter does not terminate a plain heredoc",
          fired("Bash", {"command":
                         "cat > /tmp/v.md <<'EOF'\nExample heredoc:\n"
                         "\tEOF\n%s\nEOF\n"
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

    print()
    print("Bounded cost on a pathological body:")
    # `RX_DISPOSITION`'s prefix anchors on a newline and then admitted more
    # whitespace, and `\s` matches a newline, so on a run of blank lines the
    # engine retried every suffix from every start -- quadratic. Measured on
    # the shipped pattern before it was narrowed to `[ \t]`, a single comment
    # body cost 0.6s at 2000 blank lines, 15.0s at 10000, 64.2s at 20000 and
    # 241.0s at 40000. A PreToolUse hook that takes four minutes is a hang,
    # and the body that triggers it is one a reviewer can paste by accident.
    #
    # Two sites carried the defect and they compound, so a single-site
    # mutation survives a ceiling set only against the double. Measured at
    # 20000 blank lines, with the row's own reported time:
    #
    #   neither reverted (as shipped)              0.21s
    #   the prefix reverted to `\s{0,4}` alone      0.16s
    #   the emphasis gap reverted to `\s*` alone    12.10s
    #   both reverted                             63.44s
    #
    # Those are samples under load rather than constants: a later sweep of
    # the same four states read 12.98s and 67.25s for the two reverted
    # cases. The ceiling holds at either reading, which is the point of
    # leaving this much headroom.
    #
    # Reverting the prefix alone costs nothing, because the emphasis gap is
    # then the only site that can re-consume a newline and one site is
    # linear; the two together are what multiply. The ceiling is therefore
    # 5s rather than 30s -- about 24x the measured cost, which is ample
    # headroom on a slow runner, and still red on the 12.10s single-site
    # regression a 30s ceiling let through.
    #
    # It is the only instrument that can catch a reintroduced `\s`: the
    # verdict is unchanged either way, so every other row in this suite
    # passes under all four states above (measured directly: 0 verdict
    # differences across 302 bodies).
    flood = "\n" * 20000 + "All three are addressed. Needs more work."
    env = dict(os.environ)
    env["TMPDIR"] = tempfile.mkdtemp(prefix="verdict-echo-flood-")
    try:
        payload = {"tool_name": "mcp__github__add_issue_comment",
                   "tool_input": {"owner": "o", "repo": "r",
                                  "issue_number": 1, "body": flood},
                   "cwd": ROOT, "transcript_path": "/nonexistent/flood.jsonl"}
        started = time.time()
        subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True, env=env)
        elapsed = time.time() - started
    finally:
        shutil.rmtree(env["TMPDIR"], ignore_errors=True)
    check(f"20000 blank lines finish under 5s (took {elapsed:.2f}s)",
          elapsed < 5.0, True)

    # Round 19, finding 2: the CALLER-side twin of that quadratic, which the
    # flood above cannot see because its body carries exactly one disposition
    # hit. `_disqualified` ran a clause scan per hit and `_governs` drained a
    # `finditer` over a growing window per hit, so k hits over n characters
    # cost O(n*k). A profile of a 1500-hit body put 2.712s of 2.919s inside
    # `_governs` alone, which is why hoisting the clause split by itself
    # moved the number hardly at all.
    #
    # Every hit must be DISQUALIFIED for the loop to run to completion: the
    # first hit that is not returns, and a body of plain dispositions times
    # one iteration. A negator on the line above each label disqualifies all
    # of them, and the body carries no sentence terminator, so every hit's
    # window is the whole prefix -- the worst case rather than a typical one.
    #
    # Measured at 3000 hits: 16.24s before, 0.19s after, against the same 5s
    # ceiling. The residual is the straddle fallback, which keeps the old
    # per-window path exactly and so keeps its cost: a bracketed span
    # enclosing every hit reads 5.30s at 2000 hits, unchanged from before
    # this round. Tracked rather than fixed here, since it is the behaviour
    # that already shipped.
    hits = "Needs more work\n\n" + "no findings\nAddressed\n" * 3000
    env = dict(os.environ)
    env["TMPDIR"] = tempfile.mkdtemp(prefix="verdict-echo-hits-")
    try:
        payload = {"tool_name": "mcp__github__add_issue_comment",
                   "tool_input": {"owner": "o", "repo": "r",
                                  "issue_number": 1, "body": hits},
                   "cwd": ROOT, "transcript_path": "/nonexistent/hits.jsonl"}
        started = time.time()
        subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True, env=env)
        elapsed = time.time() - started
    finally:
        shutil.rmtree(env["TMPDIR"], ignore_errors=True)
    check(f"3000 disqualified disposition hits finish under 5s "
          f"(took {elapsed:.2f}s)", elapsed < 5.0, True)

    if FAILURES:
        print(f"\n{EXAMINED - len(FAILURES)}/{EXAMINED} passed")
        print("FAILURES:")
        for f in FAILURES:
            print("  -", f)
        return 1
    print(f"\n{EXAMINED}/{EXAMINED} passed")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)
