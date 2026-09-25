#!/usr/bin/env python3
"""Stop-hook guard: catch asserting a PR's check state from a pre-push reading.

A CI status reading measures one commit and expires the instant a new commit
lands -- including your own. The failure is not forgetting to check. It is
checking, pushing, and then reporting the earlier reading in the recap, where
the query happened near the start of a long turn and nothing since announced
that the number went stale.

It matters more than an ordinary stale fact because it is a claim about
whether work is *finished*: "green, all findings resolved" invites a merge.

The condition is exactly decidable from the transcript, which is why this is a
hook rather than a rule to remember:

    message asserts check state  AND  last push is later than last status query

Fails OPEN on any parse trouble, and fires at most once per distinct message,
so it cannot wedge a session.
"""
import bisect
import hashlib
import json
import os
import re
import sys
import tempfile

try:
    _LIB = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
        "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import git_subcommand, simple_commands
except Exception as _exc:  # broken install; fail open and say so
    git_subcommand = simple_commands = None

# A bare pass/fail count says nothing about WHERE it came from: a local test
# suite and a check-run query both read "<n> pass". The trigger stays broad,
# because staleness after a push is worth warning about either way -- but the
# WORDING must not assert the number is a check-state claim when it may not be.
# Fired three times on a local suite count (ai-config#1859: "10 pass" and
# "30 pass", 2026-08-21; "33 pass", 2026-08-22). A warning that visibly
# misdescribes its own match trains the reader to skim it, which is
# `algorithmatize-checks`'s "Limits" failure arriving through the remedy.
RX_BARE_COUNT = re.compile(r"^\d+\s+pass$", re.I)

# A bare count is what `no-incomplete-check-enumeration.py` PRESCRIBES as the
# safe progress-report form -- its blocking message says verbatim that
# "13 pass, 5 pending" trips nothing, and its source carries the same claim as
# a comment. `find_unnegated_assert` matched `13 pass` in that exact string,
# so one guard's remedy was the other's trigger, using the first guard's own
# example. Measured 2026-09-24: a message reading "9 pass, 8 skipped, 2 runs
# still in progress, none failing" was blocked as a clean assertion by the
# failing-query branch, which sits above the softening path below and so
# reached neither RX_BARE_COUNT nor RX_PR_NEARBY.
# The discriminator is self-disclosure: a message that STATES its own pending
# or failing work is reporting progress, whatever counts it also carries, and
# cannot be concealing the thing this guard exists to surface.
#
# Round 9, finding 6. The vocabulary splits in two, and the first draft ran
# them together. One half STATES a not-clean or failing state outright and
# has no everyday sense that could reach it by accident. The other half is
# polysemous -- `pending`, `queued`, `in progress`, `in flight`, `still
# running` are all ordinary English about anything at all -- so on its own it
# discloses nothing about a check, and four sentences disclosing no pending
# CHECK work at all were exempting themselves: "Merge pending your approval",
# "The release is queued for Friday", "The write-up is still in progress" and
# "Her application is pending" each turned a bare "9 pass" into an exempt
# progress report. That is the expensive direction here, since the exemption
# is what stops this guard firing.
#
# So the polysemous half must sit in CHECK context: a count adjacent to it,
# which is the prescribed progress form the exemption exists for, or a check
# noun governing it. The two forms this exemption was added to admit are
# unaffected -- "13 pass, 5 pending" matches on the count and "2 runs still
# in progress" on the count and the noun together.
# The failing-count alternative is round 14, finding 2. Round 13 excluded a
# zero from the COUNT slot so "0 checks queued" could not buy the exemption,
# and that reopened the very false positive the exemption exists to prevent:
# "14 pass, 1 fail, 0 pending." is an honest progress report whose pending
# count has genuinely drained to zero, and it lost its exemption because
# nothing here recognised "1 fail" as a disclosure in its own right. It
# carries the same zero-exclusion as the count slot, so "0 failures" is not a
# disclosure of anything.
#
# The noun forms are in the alternation because the first draft omitted them
# and nothing red said so. `fail(?:ing|ed|s)?` matches `fail`, `failing`,
# `failed` and `fails`, and `failures` is none of those -- the trailing `\b`
# refuses `fail` inside it. So "14 pass, 1 failure, 0 pending." was still
# blocked, which is finding 2's own false positive surviving its fix in the
# commonest spelling there is. The row written to pin the zero-exclusion was
# vacuous for the same reason: it said "0 failures" and blocked because
# NOTHING matched, so dropping the exclusion left the suite at 159/159. Only
# the mutation sweep could see it, since a row that is right at both commits
# has no prior-commit baseline to fail against.
_PENDING_WORD = r"in[- ]progress|still running|pending|queued|in flight"
# Round 18, finding 5. `tests`, `builds`, `suites` and `stages` were absent,
# so "14 pass, 3 tests still running" blocked while the synonymous
# "3 checks still running" was exempt. Widening the NOUN set is the cheap
# direction even though widening the exemption generally is not, and the two
# pull opposite ways for a reason worth stating: the polysemy the comment
# above guards against lives in `_PENDING_WORD`, not here, so adding a CI
# noun CONSTRAINS a polysemous pending word to check context rather than
# loosening it. "The write-up is still in progress" gains no exemption from
# any noun in this list.
_CHECK_NOUN = (
    r"check(?:-runs?|s)?|runs?|jobs?|workflows?|pipelines?|reviews?|CI"
    r"|tests?|builds?|suites?|stages?"
)
# The failing count has to LAND on a clause end or on a word that keeps it
# current, because the count alone says nothing about what it counts. Round
# 15, finding 2: "All 14 checks pass. I fixed 3 errors in the docs." bought
# the whole disclosed-pending exemption on "3 errors", so the clean claim in
# front of it went unblocked over a failing status query -- the guard silent
# on exactly the sentence it exists to surface. That is the expensive
# direction, since a missed disclosure only costs the author a rewording
# while a false exemption costs the guard its purpose.
#
# What the tail admits is a terminator, the end of the text, or a small
# closed set of words that leave the count describing present state
# ("3 errors remain", "2 failures outstanding"). A preposition or a second
# verb re-targets the count at something that is not this PR's check state,
# and is refused.
#
# An earlier draft of this comment claimed "3 checks failed." worked and
# that the block message said so. Both were false, and the second was
# checkable by grep: the count alternative required the digit to be
# ADJACENT to the verb, so every natural spelling with the noun in between
# -- "3 checks failed", "1 check failed", "3 jobs failed", "2 runs failing"
# -- was refused, and the block message never mentioned the form. That is a
# false alarm on the commonest honest disclosure there is, and the comment
# sent its reader to a remedy that did not work (round 16, finding 4). The
# noun slot below is `_CHECK_NOUN`, the same vocabulary the pending
# alternatives use, so the two stay one set rather than drifting into two.
# "3 checks failed on main" is still refused, by the tail, which is the
# intended direction: it names a count somewhere other than this PR.
_FAILING_TAIL = (
    r"(?=[ \t]*(?:[.,;:!?)\]\u2014\u2013]|\n|\Z"
    r"|(?:remain(?:s|ing)?|outstanding|left|still)(?![-\w])))"
)
_DISCLOSES_STATE = (
    r"\bnot (?:yet )?(?:fully )?clean\b|\bstill failing\b|"
    r"\bnot a clean stopping point\b|"
    r"\b(?!0+(?!\d))\d+\s+(?:(?:%s)\s+)?"
    r"(?:fail(?:ures?|ing|ed|s)?|error(?:s|ed)?)\b" % _CHECK_NOUN
    + _FAILING_TAIL
)
# Polarity, found by the adversarial review of this branch. The vocabulary
# was split once already (round 9, just above) so a polysemous word could not
# exempt itself outside check context. The same reasoning applies to POLARITY
# and was not applied: a sentence DENYING pending work satisfied this
# exemption, switching the guard off on exactly the clean assertion it exists
# to surface. Measured on the pre-fix pattern, against a transcript whose
# most recent status query reported a failing state:
#
#   "14 pass."                    blocks
#   "14 pass, 0 pending."         exempt, on the count
#   "14 pass, no checks pending." exempt, on the noun
#   "14 pass, 0 checks queued."   exempt, on the count
#   "14 pass, zero jobs pending." exempt, on the noun
#
# Two independent leaks. The count slot accepted a zero, and the check-noun
# branch had no leading-negator guard at all.
#
# The count fix is in the pattern. The negator fix is not, because a negator
# sits at a variable distance from the phrase it governs and Python's `re`
# takes only a fixed-width lookbehind.
#
# `RX_NEGATION` is deliberately NOT reused. It excludes bare "no" on purpose,
# because in ASSERT context "no" is usually a determiner on some other noun
# ("No findings remain, so the PR is ready to merge"). Here bare "no"
# attached to the check noun is the entire polarity signal, so this wants its
# own set. The bounds are `(?<![-\w])` / `(?![-\w])` rather than `\b`: a
# hyphen is a non-word character, so `\bno\b` matches inside `no-op` and
# `\bzero\b` inside `zero-findings`, and in a NEGATOR set a spurious match
# silences the exemption with nothing red.
# Round 18, finding 8. The set held six spellings of absence and missed the
# ones a status TABLE uses: "checks pending: nil" and "checks pending: n/a"
# each bought the exemption they deny. The whole group is adopted rather than
# the two that were typed, because seventeen rounds of adding the spelling
# the last reviewer happened to write is what the round-18 review named as
# the structural problem with these closed sets.
_NEGATOR_ALT = (
    r"(?<![-\w])(?:no|none|zero|nothing|neither|not)(?![-\w])"
    r"(?!\s+longer(?![-\w]))"
    # The new spellings go in their OWN alternative, after the guarded one.
    # Folding them into it put `no` in front of its own `no longer` lookahead
    # in an alternative that no longer carried it, so "no longer blocked"
    # became a negator -- a widening that silently undoes round 12.
    r"|(?<![-\w])(?:nil|empty|nada|zilch)(?![-\w])"
    r"|(?<![-\w])n/a(?![-\w])"
    r"|(?<![-\w.])0+(?![-\w])(?!\.\d)"
)
_PENDING_NEGATOR = re.compile(_NEGATOR_ALT, re.I)
# Clause-scoped rather than sentence-scoped, and that is the whole
# difficulty. A negator inverts only the phrase it governs, so a
# sentence-wide window lets an unrelated earlier negation suppress a genuine
# disclosure: "No findings remain, 2 checks still pending." discloses two
# pending checks and must stay exempt. Breaking on commas as well as sentence
# terminators is what separates the two -- the window there is " 2 " rather
# than the whole sentence.
#
# "no longer" is carved out as an idiom of RESOLUTION rather than of denial:
# "no longer blocked, 2 checks pending" discloses pending work.
#
# A bare zero is a negator too, and it is not redundant with the count slot's
# own zero-exclusion: "0 checks queued" is matched by the NOUN branch, at
# `checks`, where the slot never sees the zero at all. Dropping it reopened
# exactly one of the four leaks this fix is for.
#
# Its LEADING bound excludes a dot so a version is not read as a zero count,
# and its trailing bound excludes only a dot that a DIGIT follows. Round 13
# excluded a trailing dot outright, which also excluded the commonest shape
# there is: a zero ending a sentence. "14 pass, checks pending 0." was then
# not a denial at all, and the two rows added for round 14's finding 1
# failed on that alone -- a guard written for `v1.0` swallowing `0.` is the
# hazard `shared/writing/examples-are-scanned.md` names, met in a regex.
# `(?!\.\d)` keeps `0.9012` and `1.0` out while letting `0.` back in.
#
# The leading bound is only sound because the clause breaker below refuses
# to split inside a decimal. With a bare `.` in the break class, "14 pass. v1.0 has 3
# checks pending." left a window of "0 has ", whose leading 0 is the tail of
# `v1.0` with its dot already consumed as a boundary, so the negator fired
# and blocked a genuine disclosure. A version in a recap is common here, so
# that false alarm would have been the frequent error, not the rare one.
#
# Hence `(?<!\d)\.(?!\d)`: a dot flanked by digits is a decimal point rather
# than a clause terminator. The other terminators need no such guard.
# `and` / `but` join independent clauses without a comma, so "no checks
# pending and 3 jobs queued" read as one clause and its genuine disclosure
# was suppressed by the earlier denial (round 14, finding 8). They are
# bounded with `(?<![-\w])` rather than `\b` for the reason `_PENDING_NEGATOR`
# is: a hyphen is a non-word character, so `\band \b` would match inside
# `and-then`-shaped compounds.
_PENDING_CONJUNCTION = r"(?<![-\w])(?:and|but)(?![-\w])"
RX_PENDING_CLAUSE_BREAK = re.compile(
    r"(?<!\d)\.(?!\d)|[!?;:,\u2014\u2013]|\n|" + _PENDING_CONJUNCTION
)
# The trailing negator is ANCHORED to the match rather than scanned over the
# rest of the clause, and that difference is the whole of round 15, finding
# 3. Round 14 read a trailing denial by slicing to the next value break,
# which let any negator anywhere in the tail vote: "3 checks pending with
# nothing else outstanding" discloses three pending checks AND reports
# nothing about the rest, and the `nothing` in that second, independent
# phrase cancelled the disclosure -- turning an honest progress report into
# a block. "on none of the release jobs" and "with zero drama" did the
# same. Round 15 and round 16 both cited "with no failures" here instead,
# which is a sentence the guard blocks either way: "no failures" is itself
# a clean claim, so the assert scan finds it whatever the exemption does,
# and it demonstrates nothing about the tail (round 17, finding 9).
#
# A denial that really governs the phrase follows it IMMEDIATELY: as the
# value of a label ("Checks pending: 0"), as a bare value ("checks pending
# 0"), or as a copular predicate ("checks pending are none"). Those are the
# three round-14 shapes this has to keep refusing, and each is reachable
# from the match's own end without looking at the rest of the sentence.
# Anything after a preposition or a second verb is a separate claim.
#
# Anchoring also retires the second break class. Round 14 needed one because
# a colon binds in one direction only -- it breaks BEFORE ("No findings: 2
# checks pending" discloses) and attaches AFTER ("Checks pending: 0" denies)
# -- and one class could not do both. The colon now lives in this pattern's
# own optional `:?`, so `RX_PENDING_VALUE_BREAK`, the clause ENDS it
# computed, and the `j < len(ends)` guard that could never be false (round
# 15, finding 6) are all gone with it.
#
# TWO adjacent unbounded runs is the shape to avoid here, and the first
# draft had it: `[ \t]*:?[ \t]*` lets the engine try every split of one run
# of spaces between the two, which is quadratic in that run's length on a
# FAILING match. Measured on the shipped draft, `discloses_pending` over a
# disclosure phrase followed by n spaces and an `x`: 0.02s at 500, 0.14s at
# 1000, 0.43s at 2000, 1.42s at 4000 and 5.63s at 8000, against this hook's
# registered 10-second timeout, where the round-14 code cost 0.0017s. That
# is round 15 finding 1's own defect, reintroduced by the fix for it (round
# 16, finding 1).
#
# The comment this replaces argued the pair was linear because matches are
# non-overlapping, so a run is scanned by at most one hit's tail. That
# bounds how many times `match` is CALLED and says nothing about what one
# call costs, which is where the quadratic was.
#
# Written as one run plus an optional connector carrying its own run, a
# failing match backtracks the single run one position at a time: O(n), not
# O(n^2). Same series: 0.0004s at 1000, 0.0029s at 8000.
#
# The connector set is closed ON PURPOSE. Round 15 replaced a free-text
# scan of the clause tail with this anchored match, because scanning let
# "3 checks pending with zero drama" read as a denial. So the set is the
# connectors that ATTACH a value to a label and carry no meaning of their
# own -- a colon, an equals sign, an opening paren, and a dash.
# The dash is a RUN of any length rather than an enumeration of spellings:
# round 16 spelled it as exactly two hyphens, which is this corpus's house
# substitute for an em dash
# (`shared/coding/ascii-punctuation-in-source.md`) but not its commonest
# one. Counted at `7b9fb345`, the merge base for this change, over its 746
# tracked `*.md` files: `grep -hoE ' --- '` returns 9604 against
# `grep -hoE ' -- '`'s 1200. The count is taken at a commit rather than in
# a working tree because documenting the ratio adds dashes and moves it.
# So the form an author writing in house style actually types was the form
# that read as a disclosure (round 17, finding 1).
#
# The optional word before the copula is why that copula is MANDATORY
# rather than optional beside it. An unconditional word slot re-opens
# round 15 finding 3 exactly: "with" fills it and "zero" satisfies the
# negator, so "3 checks pending with zero drama" reads as a denial.
# Measured directly -- with the slot unconditional, that sentence and the
# two beside it in the suite ("with nothing else outstanding", "on none of
# the release jobs") all flip from disclosure to denial. Requiring the
# copula admits "Checks pending today are none" and refuses all three,
# because none of them carries one.
# Round 18, finding 1. The connector was a CLOSED set and missed the arrow
# and the markdown table pipe, so "checks pending -> 0" and a table row's
# "| checks pending | 0 |" each bought the exemption while the enumerated
# "checks pending: 0" blocked. Round 17 finding 1 had already closed this
# class once for ` -- ` against ` --- `, which is the argument for inverting
# it rather than adding two more members: a connector is now ANY run of
# punctuation that is not a clause or sentence separator. The excluded
# characters are the ones that BREAK the attachment -- `.!?;` end the
# sentence and `,` separates -- so "checks pending, 0 of them" still reads
# as two clauses rather than as a denial.
_PENDING_TRAILING_NEGATOR = re.compile(
    r"[ \t]*(?:[^\w\s.,!?;]+[ \t]*)?"
    r"(?:(?:\w+[ \t]+)?(?:are|is|was|were|remain|remains)[ \t]+)?"
    r"(?:" + _NEGATOR_ALT + r")",
    re.I,
)
RX_DISCLOSES_PENDING = re.compile(
    _DISCLOSES_STATE
    + r"|\b(?!0+(?!\d))\d+\s+(?:(?:%s)\s+)?(?:still\s+)?(?:%s)\b"
    % (_CHECK_NOUN, _PENDING_WORD)
    + r"|\b(?:%s)\s+(?:(?:are|is|remain|remains)\s+)?(?:still\s+)?(?:%s)\b"
    % (_CHECK_NOUN, _PENDING_WORD),
    re.I,
)


# A coordinating conjunction opens a new coordinate clause, so it can never
# be filler INSIDE one. Round 16 let it fill the gap between a resolution
# verb and a count, which is how "Two fixes and 3 errors remain" came to
# read as a denial (round 17, finding 5).
# Round 18, finding 9. The subordinators were half present: `while`,
# `whereas`, `though` and `although` were listed and `so`, `because`,
# `since`, `when`, `once`, `after`, `before`, `unless` and `until` were not,
# so "I fixed it and 3 checks failed" stayed a disclosure while "I fixed it
# so 3 checks failed" blocked. Same class, same closed-set omission.
_CONJUNCTION_ALT = (
    r"and|but|or|then|yet|plus|while|whereas|though|although"
    r"|so|because|since|when|once|after|before|unless|until"
)


# A count the author says they RESOLVED is not a disclosure, and the tail
# above cannot see that: the tense lives in front of the count, not behind
# it. Round 15 closed "I fixed 3 errors in the docs" by refusing the
# preposition, which caught that sentence and not its class -- "I fixed 3
# errors.", "That resolved 2 failures.", "The last round closed 3
# failures." all end on a terminator the tail admits, and each bought the
# whole exemption for a clean claim standing over a failing status query
# (round 16, finding 2).
#
# The window is bounded at 48 characters and anchored at its own end, so
# this is O(1) per hit rather than another prefix scan. At most two words
# may sit between the verb and the count ("fixed the last 3 errors"),
# which is what keeps "I fixed the CI and 3 errors remain" a disclosure:
# three words intervene, so the verb does not reach the count.
_RESOLVED_LEAD = re.compile(
    r"(?<![-\w])(?:fix(?:ed|es)|resolv(?:ed|es)|clos(?:ed|es)|remov(?:ed|es)|"
    r"correct(?:ed|s)|address(?:ed|es)|clear(?:ed|s)|eliminat(?:ed|es)|"
    r"repair(?:ed|s)|squash(?:ed|es)|drop(?:ped|s)|undid|reverted|"
    # Round 18, finding 4: `patched`, `handled`, `deleted`, `silenced` and
    # `suppressed` are resolutions in the same force as `fixed`, and their
    # absence let "I patched 3 errors" buy the exemption "I fixed 3 errors"
    # is refused. An omission here is the EXPENSIVE direction, since it is
    # what lets a resolved count read as live pending work.
    r"patch(?:ed|es)|handl(?:ed|es)|delet(?:ed|es)|silenc(?:ed|es)|"
    r"suppress(?:ed|es))"
    r"[ \t]+(?:(?!(?:%s)(?![-\w]))\w+[ \t]+){0,2}\Z" % _CONJUNCTION_ALT,
    re.I,
)
_RESOLVED_LEAD_WINDOW = 48

# Only a count of things that FAILED can have been fixed. Round 16 keyed the
# exemption on the hit merely starting with a digit, which let a past-tense
# verb retract a count of work still QUEUED: "Addressed review and 3 runs
# still in progress" and "Fixed lint and 3 checks pending" both read as
# denials, so an honest progress report was refused (round 17, findings 4
# and 5). Addressing a review cannot finish a run that has not started, so
# the tense says nothing about the queue -- and the first of those two
# sentences is close to the remedy this very guard prints, which is the
# jointly-unsatisfiable pair ai-config#2274 records.
_FAILING_COUNT_HIT = re.compile(
    r"\d+\s+(?:(?:%s)\s+)?(?:fail|error)" % _CHECK_NOUN,
    re.I,
)

# A count the author attributes to ANOTHER target is not a disclosure about
# this PR, and round 16 left that judgment depending on word order.
# "3 checks failed on main" is refused, because `_FAILING_TAIL` admits only
# a terminator or a word of continuation after the count -- but front-load
# the same re-target and "On main, 3 checks failed" read as a disclosure of
# this PR's failures and exempted the clean claim beside it (round 17,
# finding 3). The two orders now agree.
#
# The gap between the lead word and the count admits spaces, tabs and
# commas, and NOT a sentence terminator: without that bound,
# "...still in progress. 3 checks failed." matched across the full stop and
# the second sentence stopped disclosing anything. A self-referential
# object ("on this PR", "in the current branch") is refused, since that is
# a disclosure about the PR in hand rather than a re-target.
_RETARGET_LEAD = re.compile(
    r"(?<![-\w])(?:"
    r"(?:on|in|for|at|from|across|over)(?![ \t]+(?:this|our|the current))"
    r"|last[ \t]+(?:week|month|night|time|round)|yesterday|earlier"
    r"|previously|before"
    r")(?:[ \t,]+(?!(?:%s)(?![-\w]))\w+){0,3}[ \t,]+\Z" % _CONJUNCTION_ALT,
    re.I,
)


def _clause_starts(text, breaker):
    """Every clause start under `breaker`, in ONE pass over `text`.

    The round-13 shape called a helper per hit that re-scanned the whole
    prefix from index 0 each time, so cost was O(hits x length): measured
    8.98s at 117 KB and 20.55s at 175 KB against this hook's registered
    10-second timeout, and a timed-out Stop hook is a guard whose silence
    reads as approval (round 14, finding 4). Scanning once and bisecting per
    hit is O(n + k log n) and needs no threshold to be safe.
    """
    starts = [0]
    for boundary in breaker.finditer(text):
        starts.append(boundary.end())
    return starts


def discloses_pending(text):
    r"""True if `text` states its own pending or failing work.

    A match whose own clause carries a negator does not count: it DENIES the
    pending work rather than disclosing it, and reading that as a disclosure
    switches this guard off on the claim it exists to surface.

    The negator is looked for on BOTH sides of the match and never inside it.
    Round 13 scanned the clause PREFIX only, which is not the clause the
    docstring claimed: "checks pending 0" and "Checks pending: 0" are
    denials whose negator trails the phrase it governs, and both stayed
    exempt (round 14, finding 1). Excluding the match's own span is what
    keeps `_DISCLOSES_STATE`'s own negative idioms working -- "not yet
    clean" carries a negator inside the match and is a disclosure, so a
    window spanning the match would deny every one of them.

    Neither side is read by SLICING any more. Round 14 cut the clause prefix
    out of `text` per hit and searched the copy, which is O(clause) twice
    over per hit and so quadratic on the shape that has no clause breaks at
    all -- one long line. Measured on the round-14 code: 0.04s at 4288
    characters, 0.18s at 8584 and 0.73s at 17152, doubling the length
    quadrupling the time, on a hook registered at a 10-second timeout (round
    15, finding 1). Every negator in `text` is now found in ONE pass, and
    each hit asks by bisection whether one of them lies wholly inside its
    own clause prefix. The trailing side is anchored and costs O(1).

    Scanning the whole text rather than a slice also FIXES the lookbehind at
    a clause start, which a slice could not see: `0` directly after a `.`
    is the tail of a version number rather than a count, and on a slice
    beginning at that `0` the `(?<![-\w.])` bound had nothing to look at.
    """
    starts = _clause_starts(text, RX_PENDING_CLAUSE_BREAK)
    negs = [(mo.start(), mo.end()) for mo in _PENDING_NEGATOR.finditer(text)]
    neg_starts = [begin for begin, _ in negs]
    for hit in RX_DISCLOSES_PENDING.finditer(text):
        clause = starts[bisect.bisect_right(starts, hit.start()) - 1]
        # The FIRST negator at or after the clause start decides the prefix:
        # matches are non-overlapping and ordered, so if that one ends past
        # the hit, every later one does too.
        k = bisect.bisect_left(neg_starts, clause)
        if k < len(negs) and negs[k][1] <= hit.start():
            continue
        lead = text[max(0, hit.start() - _RESOLVED_LEAD_WINDOW):hit.start()]
        counted = hit.group()[:1].isdigit()
        if counted and _FAILING_COUNT_HIT.match(
                hit.group()) and _RESOLVED_LEAD.search(lead):
            continue
        # Round 18, finding 6. This sat INSIDE the digit branch, so a
        # re-targeted disclosure that names no number was never tested
        # against it: "On main, 3 checks failed" was recognised as a
        # re-target and "On main, checks are still running" was not, though
        # `_RETARGET_LEAD` matches the same lead in both. Only the RESOLVED
        # lead needs a digit, because only a count can have been fixed.
        if _RETARGET_LEAD.search(lead):
            continue
        # A COUNT is its own disclosure, and nothing trailing it retracts one.
        # The tail exists for a bare phrase -- "Checks pending: none" names no
        # quantity, so the `none` supplies it -- and round 16 applied it to
        # counted hits as well, which refused four honest reports at once:
        # "3 checks pending with zero drama", "-- zero drama", "(zero drama)"
        # and "-- nothing else outstanding" each disclose three pending checks
        # and then say something independent about the rest (round 17, finding
        # 6). The known miss this buys is the self-contradicting
        # "3 checks pending -- none", which now reads as a disclosure of three.
        # Gated on `counted` EXPLICITLY rather than on an `elif` chained to
        # the branch above it. Hoisting the re-target guard out of the digit
        # branch (finding 6) moved that `elif` onto the re-target test, so
        # every counted hit started falling through to this tail and the
        # four round-17 finding-6 rows went red at once. The flag says what
        # the gate is about, and cannot be re-aimed by an edit above it.
        if not counted and _PENDING_TRAILING_NEGATOR.match(text, hit.end()):
            continue
        return True
    return False


# What makes a count a claim about THIS PR/MR rather than about a local run.
# Proximity, not presence anywhere in the message: a recap routinely mentions
# a PR/MR number paragraphs away from an unrelated test count.
RX_PR_NEARBY = re.compile(
    r"#\d+|!\d+|/pull/\d+|/merge_requests/\d+|\bgh pr\b|\bglab mr\b|\bglab ci\b"
    r"|\bcheck[- ]runs?\b|\bstatusCheckRollup\b|\bpipelines?\b|\bjobs?\b"
    r"|\bCI\b|\bworkflow\b|\bhead SHA\b|\bheadRefOid\b"
    # The plain word is the most natural way to reference a PR/MR in prose, and
    # omitting it classified a message opening "PR checks: ..." as having no
    # PR reference at all. Erring toward the STRONG wording is the safe
    # direction, so a loose match here costs nothing.
    r"|\bPRs?\b|\bMRs?\b|\bpull requests?\b|\bmerge requests?\b",
    re.I,
)
NEARBY_WINDOW = 250

# Assertions about a PR's check state. Deliberately narrow: "checks are
# running" or "waiting on CI" are honest and must not trip this.
ASSERT = [
    r"\b\d+\s+pass\b",
    r"\ball (checks|green)\b",
    r"\bchecks? (are |is )?(all )?green\b",
    r"\b(is|are|now) green\b",
    r"\bgreen,\s",
    # Anchored to the CI vocabulary, not the test-runner's. `0 failed` is how
    # every test harness reports a green suite, and a local run's tally says
    # nothing about a PR -- so an unanchored `0 fail` fires on a mutation
    # check of a hook's own tests while its sibling `\b\d+\s+pass\b`, which
    # requires a boundary after `pass`, deliberately ignores the same line.
    # The two patterns matched disjoint things: `14 passed, 0 failed` tripped
    # only the fail rule, and `25 pass, 2 pending` only the pass rule
    # (ai-config#2016). Keep the CI phrasings and drop the participle.
    r"\b0 fail(s|ures)?\b",
    r"\bzero fail(s|ures)?\b",
    r"\bready to merge\b",
    r"\bfully clean\b",
    r"\bno failures\b",
    r"\bconflict-free\b",
]
RX_ASSERT = re.compile("|".join(ASSERT), re.I)

# An MCP write carries its verb in the tool NAME (mcp__github__push_files,
# mcp__github__create_or_update_file, etc.).
RX_MCP_PUSH = re.compile(
    r"mcp__.*__(?:push_files|create_or_update_file)|\b(?:push_files|create_or_update_file)\b",
    re.I,
)

# A push invalidates any earlier reading. Kept for unparseable-command fallback.
RX_PUSH = re.compile(r"git\s+push|create_or_update_file|push_files", re.I)

LOCAL_FILE_TOOLS = {
    "view_file", "read_file", "grep_search", "list_dir", "find_by_name",
    "write_to_file", "replace_file_content", "edit", "write", "str_replace_editor",
    "multiedit", "view", "read",
}


def _check_push(tool_name: str, args: any) -> tuple[bool, str]:
    """Return (is_push, push_summary).

    Detect genuine push events (CLI git push or MCP file push) while avoiding
    false positives from push vocabulary appearing quoted in commit messages,
    heredocs, sed substitutions, or local file edits (ai-config#3958).
    """
    tool_lower = (tool_name or "").lower()

    # 1. MCP push: verb is in the tool name.
    if RX_MCP_PUSH.search(tool_lower):
        return True, tool_name

    # 2. Extract shell command string if present.
    cmd_str = None
    if isinstance(args, dict):
        cmd_str = args.get("command") or args.get("CommandLine") or args.get("cmd")
    elif isinstance(args, str):
        cmd_str = args

    if cmd_str and isinstance(cmd_str, str):
        if simple_commands is not None and git_subcommand is not None:
            cmds = simple_commands(cmd_str)
            if cmds is not None:
                for argv in cmds:
                    res = git_subcommand(argv)
                    if res and res[0] == "push":
                        summary = " ".join(argv[:4])
                        return True, summary
                return False, ""

        # Fallback when simple_commands returns None (parse error) or shellcmd is absent.
        # Fail closed on unparseable shell command containing git push.
        m = re.search(r"\bgit\s+push\b", cmd_str, re.I)
        if m:
            summary = cmd_str.strip().splitlines()[0][:60]
            return True, summary
        return False, ""

    # 3. Fallback for non-dict args or unrecognized tool wrappers.
    blob = (tool_name or "") + " " + json.dumps(args or {})
    m = RX_PUSH.search(blob)
    if m:
        return True, m.group(0)
    return False, ""

# A tool_result saying the call NEVER RAN. A push the harness refused moved no
# commit, so counting it as a push invalidates a reading that is still current
# and fires this guard on a premise that was never true.
#
# Anchored at the start of each result PART, deliberately. Both strings are
# harness prefixes on a refusal, and this corpus quotes them constantly -- an
# unanchored match would read a transcript DISCUSSING a blocked push as one. The
# two shapes are the only unambiguous ones: a runtime `Exit code N` still counts
# as a push, because `git push && something-else` can fail after the push
# succeeded.
#
# Per PART rather than per result, because `^` with no `re.M` anchors at string
# start and a `content` list arrives as several parts. An earlier revision
# joined them with newlines before searching, which left the anchor reachable
# only by the first part -- so a refusal delivered as a second part read as a
# real push, and the guard fired on a premise that was never true.
#
# Round 18, finding 7 corrected this comment's polarity. It used to call that
# the expensive direction, which contradicts the governing asymmetry stated
# above: a missed refusal makes the guard FIRE over a reading that was still
# current, and a false block costs the author a rewording. Measured both ways
# -- a detected refusal allows, a missed one blocks -- so missing a refusal is
# the CHEAP direction. For this predicate the expensive direction is
# over-matching: reading a real push as a refusal drops it from the
# comparison, and the guard then goes silent over a genuinely stale claim.
# The three shapes now agree, since a string result is a one-part list.
RX_NEVER_RAN = re.compile(
    r"^\s*(?:\\n)*\s*PreToolUse:[^\n]*hook error:"
    r"|^\s*(?:\\n)*\s*Permission for this action was denied",
    re.I,
)

# A fresh reading. Covers the CLI and the MCP surfaces for both GitHub and GitLab (#2667).
RX_QUERY = re.compile(
    r"gh\s+pr\s+checks|statusCheckRollup|get_check_runs|"
    r"gh\s+run\s+view|checkSuites|mergeStateStatus|"
    # The REST check-runs endpoint, hyphenated. `fully-clean.md` MANDATES this
    # over `gh pr checks` -- "take the check-run half of criterion 1 from the
    # paginated check-runs endpoint" -- so omitting it meant the guard warned
    # of a stale reading at the one query the corpus tells you to prefer, and
    # told the author to re-run the weaker command instead. The MCP spelling
    # `get_check_runs` was covered; the CLI/REST spelling was not.
    r"commits/[^\s]+/check-runs|commits/[^\s]+/status|"
    r"python3?\s+.*(?<!test_)\bcheck-pr-fully-clean\.py|"
    r"glab\s+ci\s+(?:status|list|view)|"
    r"glab\s+mr\s+view|"
    r"glab\s+pipeline\s+view|"
    r"projects/[^\s]+/pipelines|"
    r"projects/[^\s]+/merge_requests",
    re.I,
)

RX_FAIL_QUERY = re.compile(
    r"\\u274c|\u274c|\bNOT fully clean\b|contains findings|conclusion.*failure|status.*in_progress|"
    r"No review comment has been posted|\bPartial review\b|\bdiff was truncated\b|\bomitted region was not assessed\b",
    re.I,
)

# A negation anywhere earlier in the same sentence as an ASSERT match means
# the sentence is reporting the failing/negative state, not claiming the
# clean one -- "PR is NOT fully clean" and "check-pr-fully-clean.py reports
# NOT clean (... its own 'fully clean' determination ...)" both contain the
# literal ASSERT phrase while stating the opposite. Sentence-scoped rather
# than a fixed character window: a negation can sit in an earlier clause of
# a long sentence (a parenthetical, a comma splice) well before the ASSERT
# phrase itself.
#
# "n't" has no `\b` before it: `\b` requires a word-boundary transition, but
# in every real contraction (isn't, aren't, doesn't, can't, won't) the
# character before `n` is itself a word character, so a leading `\b` can
# never match there and the contraction case silently never fires.
#
# Bare "no" is deliberately excluded. It reads like a negation but is
# usually a determiner attached to a DIFFERENT noun in the sentence than the
# ASSERT phrase ("No findings remain, so the PR is ready to merge." / "no
# unresolved threads and #1689 is fully clean") -- both genuine stale-clean
# claims this guard exists to catch, so treating "no" as a sentence-wide
# negation signal silently disables the guard on exactly the phrasing this
# repo's own recap convention uses most.
RX_NEGATION = re.compile(
    r"\b(not|never|cannot|unable)\b|n['\u2019]t\b", re.I,
)
# Sentence boundaries: a terminator (optionally followed by markdown/quote
# closing punctuation, e.g. "yet.**" or "clean.\"") then whitespace or
# end-of-string -- OR any single newline. A bare newline has to count on its
# own, not just a blank line: a table row or list item ("| ... | not clean |
# \n| ... | ready to merge |") is a full independent clause in this repo's
# own recap conventions, and treating only a BLANK line as a break let a
# negation on one row silently suppress an unrelated claim on the next.
# `;` is included alongside `.!?`: a semicolon-joined clause ("PR #1 is not
# clean; PR #2 is fully clean.") is its own independent clause the same way a
# table row is, and the same fail-open shape as the newline/markdown bugs
# ai-config#1764 fixed -- a negation before the `;` was silently suppressing
# an unrelated genuine claim after it (ai-config#1770).
# Deliberately coarse -- this only needs to find SOME earlier boundary, not
# parse prose correctly.
RX_SENTENCE_BREAK = re.compile(r"[.!?;][\"'\)\]*_`]*(?:\s|$)|\n")

# Retraction vocabulary. A correction is rarely phrased as "the PR is not
# fully clean"; it says the earlier claim "was wrong". `RX_NEGATION` matches
# none of that, so a reply WITHDRAWING a cleanliness claim read as making one
# and was blocked -- measured 2026-09-02 on the sentence: But "fully clean"
# was wrong too, and for a third reason (ai-config#3038).
#
# Blocking a correction specifically is worse than an ordinary false positive:
# the cheapest way to satisfy the guard is to stop mentioning the earlier
# claim at all, which is the opposite of what CLAUDE.md asks for.
#
# The word list is taken from `hooks/remind-ums-after-error.py`, which already
# enumerates this family for the same reason (ai-config#1210 -- a retraction of
# a figure rarely carries an explicit "incorrectly"), plus four terms that file
# does not carry: `inaccurate`, `premature`, `misstated`, `misspoke`.
#
# What is NOT taken from it is its first-person anchor. That file anchors most
# of its alternatives on an explicit `I`/`my` subject -- `correcting this` and
# `retracting that claim` among the several that do not -- because its job is
# to detect an admission, and "the review was wrong" is a statement about
# someone else. This guard's job is different, and the issue's own measured
# sentence proves the anchor cannot transfer: in `But "fully clean" was wrong
# too` the subject is the quoted claim, not a person. Attachment does that
# work here instead -- see RX_CLAUSE_SEPARATOR below.
#
# The copula is required for the adjective forms, because bare `wrong` is most
# often attributive ("the wrong branch", "the wrong file") and says nothing
# about a claim being withdrawn.
RX_RETRACTION = re.compile(
    r"\b(?:was|were|is|are)\s+"
    r"(?:wrong|incorrect|false|mistaken|inaccurate|premature)\b"
    r"|\b(?:over|under)(?:stated|estimated|counted|reported|claimed)\b"
    r"|\bretract(?:ing|ed|s)?\b"
    r"|\bcorrecting\s+(?:myself|my|this)\b"
    r"|\bmis(?:read|counted|stated|characterized|spoke)\b",
    re.I,
)

# A retraction withdraws the ASSERT phrase only when it ATTACHES to it. This
# is what keeps the widening from causing the opposite, invisible failure --
# a genuine stale-clean claim silently suppressed because some other clause of
# the same sentence happens to say "wrong". Every one of these blocks:
#
#   The reviewer was wrong about the lint failure, but all checks green.
#   PR #1689 is fully clean -- the earlier blocker was inaccurate.
#   All checks green, but the reviewer overstated the risk.
#   All checks green after I misread the earlier log.
#
# In each, the retraction and the claim sit in DIFFERENT clauses, and the text
# between them says so: a comma, a prose dash, a coordinating or subordinating
# conjunction, the bracket or paren opening an aside, or a markdown boundary (a
# table cell, a new list item). None of those appears between the claim and its
# retraction in the measured sentence, where the two are adjacent.
#
# Attachment replaces the character window an earlier round used. A window
# cannot tell "green -- the badge is wrong" from "green was wrong", since both
# put the retraction within a few characters; a clause separator can.
#
# Two families of separator are direction-asymmetric, so the set is split
# rather than shared. `when` is a complementizer: in "I was wrong when I said
# all checks green." the claim is the content of the retracted saying, so
# `when` must not break a LEADING retraction off the claim it withdraws. After
# the claim the same word opens a separate clause, so it still breaks there.
# The relative pronouns `where`, `which`, `who`, `whose`, and `whom` are the
# second family, for the same reason. Before the claim they can take it as
# their own object, so "Correcting my earlier status which claimed all checks
# green." withdraws exactly the claim that follows. After the claim they open
# a relative clause about a different noun instead, so "#1689 is fully clean
# per the reviewer whose note was wrong." leaves the claim standing and still
# has to block. USUALLY, not always: when the head noun refers back to the
# claim itself the relative clause withdraws exactly the assertion this guard
# protects, and RX_METALINGUISTIC_HEAD below is that carve-out.
#
# `that` belongs in the same set, and it is the commonest relative pronoun in
# English -- so omitting it left the guard switchable off by one word, the same
# defect the dash spelling had. It is the complementizer leading ("I was wrong
# that all checks green.") and the restrictive relative pronoun trailing
# ("#1689 is fully clean per the note that was wrong."), which is exactly the
# trailing-only shape. It cannot join the shared set, because the leading
# reading is the plainest correction there is. Adding it is also what forced
# the carve-out: the metalinguistic hole was already open for the `which`
# spelling and rare there, and `that` is the spelling people actually write on
# a restrictive relative, so widening without the carve-out would have turned a
# rare false block into a common one.
#
# `:` is a clause boundary in BOTH directions and stays in the shared set. It
# introduces the CORRECTED claim at least as often as the retracted one --
# "I was wrong: all checks green now." withdraws some earlier claim and then
# asserts a fresh, stale one -- so reading it as attachment silently disables
# the guard on a genuine stale-clean assertion. That is the invisible failure,
# since a suppressed guard emits nothing, and the identical sentence with a
# period ("I was wrong. All checks green now.") already blocks, so nothing
# should turn on the one character. The cost of the symmetric reading is a
# visible warning on "I overstated it: 11 pass was the pre-push reading.",
# whose own text already discloses the reading is pre-push; the cost of the
# asymmetric one is a stale claim that nothing reports.
#
# A prose DASH is the same case as `:`, and listing only the ASCII double
# hyphen left the guard switchable off by one keystroke: "PR #1689 is fully
# clean -- the earlier blocker was inaccurate." blocked while the identical
# sentence spelled with an em-dash, an en-dash, or a spaced single hyphen did
# not. The text this guard reads is assistant prose in a transcript, which
# `shared/coding/ascii-punctuation-in-source.md` does not govern, so every
# spelling has to be listed -- as `\uXXXX` escapes, so this file itself stays
# ASCII. Only the ASCII hyphen and the slash need surrounding whitespace,
# because those two also sit inside ordinary words and paths
# (`conflict-free`, `pre-push`, `hooks/foo.py`); the other glyphs never do.
#
# A square-bracketed aside is the same case as a parenthesized one AFTER the
# claim, and listing only the parens made the verdict turn on the bracket
# style: "All checks green (the earlier note was wrong)." blocked while the
# identical sentence in brackets did not. Both open an aside about something
# other than the claim, so both break the TRAILING attachment.
#
# The brackets stay SHARED, exactly as the parens do, and the leading direction
# is handled by removing markdown rather than by exempting the character. A
# leading bracketed span in this corpus is usually markdown rather than an
# aside -- a reference-style link ("[#1689][pr]"), a footnote marker ("[^1]"),
# an inline link -- so reading it as a clause break blocks the plain retraction
# it sits inside: "Retracting the status [#1689][pr] all checks green." and "I
# misread [^1] all checks green." both flipped from ALLOW to BLOCK when the
# brackets were first shared, which is the false-block class this guard exists
# to stop. Exempting the bracket CHARACTER instead is what an earlier round
# tried, and it reintroduces the defect this same block was written to remove,
# one direction over: with the brackets trailing-only, "[The earlier note was
# wrong] all checks green." allowed while the identical sentence in parens
# blocked, so the verdict turned on the bracket style again. RX_MARKDOWN_SPAN
# below deletes the markdown shapes from the connector and leaves every other
# bracket standing, which keeps the two families in step.
#
# Nothing else moves. `because`, `since`, `after`, `before`, `until`, `once`,
# `unless`, `if`, and `now that` introduce a reason or a time rather than the
# retraction's object, so a retraction reaching across one of them is about a
# different proposition and STAYS blocked in both directions -- "All checks
# green because the earlier reading was wrong." still asserts green. `until`
# belongs beside them on that same ground, and not on a shared part of speech:
# what follows it is a time, so the retraction in "All checks green until I
# noticed my earlier count was overstated." is about the COUNT rather than
# about the claim. Its terminative sense ("P until Q" ends P at Q) is a
# different question, and one this guard does not read: a claim bounded by a
# time is still a claim, and only the retraction vocabulary withdraws one. The
# two-word `now that` has to be spelled out, since a bare `now` is no
# separator at all.
_CLAUSE_SEPARATORS = (
    r"--|[,;:()\[\]|]"
    r"|[\u2013\u2014\u2192\u2026]|\s[-/]\s"
    r"|\n[ \t]*[-*+>#]"
    r"|\b(?:but|and|or|so|yet|however|though|although|while|whereas"
    r"|after|before|until|since|because|once|unless|if|now\s+that)\b"
)
# The complementizers and the relative pronouns, which break attachment only
# AFTER the claim -- before it a pronoun can take the claim as its own object.
_TRAILING_ONLY_SEPARATORS = (
    r"|\b(?:when|that|where|which|who|whose|whom)\b"
)

# The markdown spans that are not clause breaks in either direction: a footnote
# marker, a reference-style link, an inline link. They are deleted from the
# connector before it is scanned, so the brackets can stay in the shared set
# without a citation inside a retraction reading as an aside. A bare "[ci]" is
# deliberately NOT here: nothing distinguishes a shortcut link from a bracketed
# aside, and the aside is the reading that keeps the guard on.
RX_MARKDOWN_SPAN = re.compile(
    r"\[\^[^\[\]]*\]"
    r"|\[[^\[\]]*\](?:\[[^\[\]]*\]|\([^()]*\))"
)
RX_CLAUSE_SEPARATOR = re.compile(
    _CLAUSE_SEPARATORS + _TRAILING_ONLY_SEPARATORS, re.I)
RX_LEADING_SEPARATOR = re.compile(_CLAUSE_SEPARATORS, re.I)

# The one shape where a trailing relative pronoun does NOT open a clause about
# a different noun: the head noun refers back to the claim itself. "All checks
# green is a claim that was wrong." names the assertion and then withdraws it,
# so breaking on the pronoun blocks a plain retraction -- the very class this
# guard exists to stop blocking. The hole predates `that`: measured against the
# previous commit, "All checks green is a claim which was wrong." already
# blocked before `that` joined the set.
#
# Only this head phrase is dropped from the connector, never the rest of it, so
# a separator anywhere else still breaks: "All checks green is a claim that
# survives, though my count was wrong." still blocks on the comma, and "All
# checks green because the note is a claim that was wrong." still blocks on
# `because`. The LEFT end stays unanchored because an ASSERT match often ends
# mid-phrase (`\ball (checks|green)\b` matches only "All checks"), so the
# connector opens with the tail of the claim rather than with the copula.
#
# The RIGHT end is anchored, and leaving it open was a fail-open. Keying on the
# head noun alone never asks what the relative clause is ABOUT, so any sentence
# putting the error on some other noun -- "#1689 is fully clean is the note
# that the reviewer misread.", "All checks green is the reading that the
# earlier reviewer overstated." -- had its head phrase stripped and went
# silently ALLOW, which is the direction that emits nothing. The grammar
# decides it: in a SUBJECT relative the pronoun IS the claim and the verb
# follows it directly, while an OBJECT relative puts its own subject in
# between. So the carve-out must reach the retraction.
RX_METALINGUISTIC_HEAD = re.compile(
    r"\b(?:is|was|were|are)\s+"
    r"(?:the|a|an|this|that|my|our|its)?\s*"
    r"(?:earlier|prior|previous|one|only|original)?\s*"
    r"(?:claim|statement|line|note|status|report|reading|call|verdict"
    r"|assertion|assessment|sentence|wording)\s+"
    r"(?:that|which)\s+"
    r"(?:(?:was|were|is|are|has|had|have|been)\s+"
    r"|(?:clearly|plainly|simply|obviously|evidently|apparently|admittedly"
    r"|wrongly|incorrectly|mistakenly|badly|wildly|grossly|overwhelmingly"
    r"|entirely|partly|largely|mostly|probably|certainly|frankly|honestly"
    r"|actually|really)\s+"
    r"|(?:now|then|later|already|always|still|never|ever|just|once|again)\s+)*\Z",
    re.I,
)

# The trailing scan deliberately does NOT treat a bare newline as a sentence
# end, mirroring `scripts/check-pr-fully-clean.py`'s SENTENCE_END. This corpus
# writes semantic line breaks, so a retraction routinely wraps onto the next
# line ('My earlier "fully clean" call\nwas wrong'), and terminating on `\n`
# would hide exactly the correction this guard must stop blocking. The prefix
# scan keeps RX_SENTENCE_BREAK, where a bare newline IS a boundary because a
# table row or list item is an independent clause (ai-config#1764); the
# markdown alternatives in RX_CLAUSE_SEPARATOR above are what keep the trailing
# scan from crossing one of those.
RX_TRAILING_BREAK = re.compile(r"[.!?;]|\n[ \t]*\n")


# A terminator and its closers sitting flush against the hit, with no
# whitespace after them. `RX_SENTENCE_BREAK` needs `\s|$` after the closers,
# and under `finditer(text, 0, hit.start())` the `$` matches AT the endpos --
# so the per-hit scan sees a boundary there that a whole-text scan does not.
# Precomputing the starts therefore needs this one O(1) test beside the
# bisect, or the two forms disagree on "...clean.All checks pass".
RX_SENTENCE_BREAK_ABUT = re.compile(r"[.!?;][\"\'\)\]*_`]*\Z")


def sentence_starts(text):
    """Every sentence start in `text`, in ONE pass, for `_sentence_start`."""
    return _clause_starts(text, RX_SENTENCE_BREAK)


def _sentence_start(text, hit, starts=None):
    """Start of the sentence containing `hit`, coarsely.

    Round 18, finding 2. Without `starts` this rescans from index 0 for
    every hit, so a caller looping over N asserts pays O(N x length): an
    ordinary multi-PR recap cost 3.97s at 70 KB and 9.31s at 105 KB against
    this hook's registered 10-second timeout, and a timed-out Stop hook
    fails open, which in a blocking guard is a silent approval. This is the
    same defect round 14 fixed in `discloses_pending` and the same one this
    branch documents in `shared/coding/regex-backtracking-pitfalls.md`; it
    survived because neither cost row reached this path (finding 3).
    Pass `starts` from `sentence_starts` to get O(n + k log n).
    """
    pos = hit.start()
    if starts is None:
        start = 0
        for boundary in RX_SENTENCE_BREAK.finditer(text, 0, pos):
            start = boundary.end()
        return start
    if RX_SENTENCE_BREAK_ABUT.search(text, max(0, pos - 64), pos):
        return pos
    return starts[bisect.bisect_right(starts, pos) - 1]


def _trailing_end(text, hit):
    """End of the clause following `hit`, for the retraction scan."""
    end = RX_TRAILING_BREAK.search(text, hit.end())
    return end.start() if end else len(text)


def _attaches(connector, separators=RX_CLAUSE_SEPARATOR):
    """True when nothing in `connector` breaks a retraction off the claim."""
    return not separators.search(connector)


def _is_retracted(text, hit, starts=None):
    """True if a retraction attaches to the ASSERT match, either side of it.

    The trailing scan falls THROUGH when its match does not attach, rather than
    returning that verdict. A trailing retraction belonging to another clause
    says nothing about a leading one that does attach, and returning on it
    suppressed the leading retraction whenever an unrelated retraction word
    followed in the same clause -- "I was wrong that #1689 is fully clean, and
    the count was overstated too." blocked, which is the very class this guard
    was widened to stop blocking.
    """
    for after in RX_RETRACTION.finditer(text, hit.end(), _trailing_end(text, hit)):
        connector = RX_METALINGUISTIC_HEAD.sub(
            "", RX_MARKDOWN_SPAN.sub("", text[hit.end():after.start()]), count=1)
        if _attaches(connector):
            return True
        break
    start = _sentence_start(text, hit, starts)
    before = None
    for before in RX_RETRACTION.finditer(text, start, hit.start()):
        pass
    return before is not None and _attaches(
        RX_MARKDOWN_SPAN.sub("", text[before.end():hit.start()]),
        RX_LEADING_SEPARATOR)


def _is_negated(text, hit, starts=None):
    """True if the ASSERT match is negated or retracted within its sentence.

    Plain negation stays scoped to the text BEFORE the phrase, which is the
    pre-existing behaviour and must not be widened: "All checks green at this
    head, and I have not merged it yet" is a genuine stale-clean claim whose
    trailing negation is about something else entirely. Only the retraction
    vocabulary reads in both directions, and only when it attaches.
    """
    if RX_NEGATION.search(text[_sentence_start(text, hit, starts):hit.start()]):
        return True
    return _is_retracted(text, hit, starts)


def all_unnegated_asserts(text):
    """Every un-negated ASSERT match, in textual order.

    `find_unnegated_assert` returns the FIRST, which is the right answer for
    "should this fire". It is the wrong answer for "how should this be
    worded", because the strongest claim in a message is not always the
    earliest one.

    A GENERATOR rather than a list, which is the second half of round 18
    finding 2: both call sites stop early -- one at the first non-bare-count
    candidate, the other at the first hit that settles the wording -- and a
    materialised list denied them that. On a 105 KB recap the answer was
    candidate 0 at offset 60 and the eager form still computed 5999 more.
    """
    starts = sentence_starts(text)
    for hit in RX_ASSERT.finditer(text):
        if not _is_negated(text, hit, starts):
            yield hit


def find_unnegated_assert(text):
    """Return the first ASSERT match not negated or retracted in its sentence."""
    return next(all_unnegated_asserts(text), None)


def _result_parts(block):
    """The tool_result's text parts, whichever of the three shapes it arrived in.

    A LIST, not a joined string, because `RX_NEVER_RAN` anchors at `^` with no
    `re.M`: joining first would move every part after the first away from a
    string start, so a refusal arriving as a later content part read as a real
    push and fired this guard on a premise that was never true. Each part is a
    result in its own right and gets its own anchor.
    """
    content = block.get("content")
    if content is None:
        content = block.get("text") or ""
    if isinstance(content, str):
        return [content]
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                parts.append(part.get("text") or "")
            elif isinstance(part, str):
                parts.append(part)
        return parts
    return []


def _never_ran(block):
    """True when this tool_result says the call was refused before it ran.

    An explicit `is_error: false` overrides the text: a result the harness
    marked successful did run, whatever it quotes. An ABSENT `is_error` is
    not read as false, because a transcript format that omits the field
    would otherwise reinstate the bug this function exists to fix.
    """
    if block.get("is_error") is False:
        return False
    return any(RX_NEVER_RAN.search(part) for part in _result_parts(block))


def scan(path):
    """Return (last_push_idx, last_query_idx, last_failing_query_idx, last_assistant_text, last_push_cmd)."""
    last_query = last_failing_query = -1
    text = ""
    i = 0
    query_tool_use_ids = set()
    # (line index, tool_use id, push summary) per push ATTEMPT, plus the ids
    # the harness
    # refused. `last_push` is resolved at the end from the difference, because
    # the refusal arrives in a later block than the request.
    push_attempts = []
    push_tool_use_ids = set()
    blocked_push_ids = set()
    with open(path, errors="ignore") as fh:
        for line in fh:
            i += 1
            try:
                m = json.loads(line)
            except Exception:
                continue
            role = m.get("type") or m.get("role")
            blocks = (m.get("message") or {}).get("content")
            if blocks is None:
                blocks = m.get("content") or []

            # Antigravity tool calls
            if m.get("type") in {"PLANNER_RESPONSE", "GENERIC"} or m.get("source") == "MODEL" or "tool_calls" in m:
                for tc in m.get("tool_calls") or []:
                    if isinstance(tc, dict):
                        tool_name = (tc.get("name") or (tc.get("function") or {}).get("name") or "").lower()
                        if tool_name in LOCAL_FILE_TOOLS:
                            continue
                        args = tc.get("args") or tc.get("input") or (tc.get("function") or {}).get("arguments") or {}
                        blob = tool_name + " " + json.dumps(args)
                        tool_id = tc.get("id") or str(id(tc))
                        is_push, push_cmd = _check_push(tool_name, args)
                        if is_push:
                            push_attempts.append((i, tool_id, push_cmd))
                            if tool_id:
                                push_tool_use_ids.add(tool_id)
                        if RX_QUERY.search(blob):
                            last_query = i
                            if tool_id:
                                query_tool_use_ids.add(tool_id)

            # Antigravity text content
            if m.get("type") in {"PLANNER_RESPONSE", "GENERIC"} or m.get("source") == "MODEL":
                raw_content = m.get("content")
                if isinstance(raw_content, str) and raw_content.strip():
                    text = raw_content

            if isinstance(blocks, list):
                for b in blocks:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "tool_use":
                        tool_name = (b.get("name") or "").lower()
                        if tool_name in LOCAL_FILE_TOOLS:
                            continue
                        args = b.get("input") or {}
                        blob = tool_name + " " + json.dumps(args)
                        tool_id = b.get("id") or b.get("tool_use_id") or ""
                        is_push, push_cmd = _check_push(tool_name, args)
                        if is_push:
                            push_attempts.append((i, tool_id, push_cmd))
                            if tool_id:
                                push_tool_use_ids.add(tool_id)
                        if RX_QUERY.search(blob):
                            last_query = i
                            if tool_id:
                                query_tool_use_ids.add(tool_id)
                    elif b.get("type") == "tool_result":
                        tool_id = b.get("tool_use_id") or b.get("id") or ""
                        if tool_id and query_tool_use_ids and tool_id in query_tool_use_ids:
                            content_text = json.dumps(b.get("content") or b.get("text") or "")
                            if RX_FAIL_QUERY.search(content_text):
                                last_failing_query = i
                        if tool_id and tool_id in push_tool_use_ids:
                            if _never_ran(b):
                                blocked_push_ids.add(tool_id)
                    elif b.get("type") == "text" and role == "assistant":
                        if b.get("text", "").strip():
                            text = b["text"]
            elif isinstance(blocks, str) and role == "assistant" and blocks.strip():
                text = blocks
    # A push whose result says it never ran moved nothing. An attempt with no
    # tool_use id at all still counts: a missed push is the expensive
    # direction for this guard, since it licenses a merge on a stale reading.
    survivors = [
        (idx, cmd) for idx, tid, cmd in push_attempts if tid not in blocked_push_ids
    ]
    if survivors:
        last_push, last_push_cmd = max(survivors, key=lambda pair: pair[0])
    else:
        last_push, last_push_cmd = -1, ""
    return last_push, last_query, last_failing_query, text, last_push_cmd


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        path = payload.get("transcript_path") or ""
        last_push, last_query, last_failing_query, text, last_push_cmd = scan(path)
    except Exception:
        return 0  # fail open

    if not text:
        return 0
    hit = find_unnegated_assert(text)
    if not hit:
        return 0

    # If the last status query reported a failing or not-clean state, block clean assertions.
    if last_failing_query > last_query and last_failing_query > last_push:
        fail_hit = hit
        if discloses_pending(text):
            # Re-aim past every bare count: the message already discloses its
            # own pending work, so a count in it is the prescribed progress
            # form rather than a clean claim. A non-count assert in the same
            # message still blocks.
            #
            # The filter is blind to WHICH PR each count concerns, so it skips
            # a count about a different PR from the one the disclosure names:
            # "#50 has 2 checks still in progress. 9 pass on #49." goes
            # unblocked. An earlier version of this comment asserted the
            # opposite, which the code never enforced (the disclosed-pending
            # exemption finding; an earlier revision cited it as "round 10,
            # finding 4", an ordinal a later review of the same branch also
            # used for an unrelated finding).
            # Whether to consult `RX_PR_NEARBY` here the way the staleness
            # branch below does is ai-config#3968 -- it widens a BLOCKING
            # guard, so it wants its own measured change rather than a
            # correction bolted onto a comment fix.
            # Round 9, finding 7. This was a hand-rolled copy of
            # `all_unnegated_asserts` with a filter bolted on, so the
            # negation rule existed in two places and only one of them was
            # the helper every other caller uses.
            fail_hit = next(
                (cand for cand in all_unnegated_asserts(text)
                 if not RX_BARE_COUNT.match(cand.group(0).strip())),
                None,
            )
        if fail_hit is not None:
            print(json.dumps({
                "decision": "block",
                "reason": (
                    f"Your message asserts a PR's clean state -- \"{fail_hit.group(0).strip()}\" -- "
                    "but the most recent status query tool result in this transcript reported a FAILING or IN-PROGRESS check state. "
                    "You cannot declare a PR fully clean when a status query returned failure or in-progress checks.\n\n"
                    "This match is by TEXT and TIME, not by pull request: the failing query may "
                    "concern a DIFFERENT PR from the one your sentence is about, and a message "
                    "covering several PRs trips it on any one of them. So check that premise "
                    "rather than conceding it -- if the failing reading is about another PR, the "
                    "claim may stand and the correction you owe is none. Re-query the PR the "
                    "sentence names, because confirming that costs one query, but do not retract "
                    "a claim the evidence supports.\n\n"
                    "If this is a progress report, state the pending work in the same message -- "
                    "a bare \"N pass\" count alongside a disclosed in-progress or pending state is "
                    "the form `no-incomplete-check-enumeration.py` prescribes, and no longer fires "
                    "ON THIS BRANCH. The disclosure has to be AFFIRMATIVE and non-zero to count: "
                    "\"0 checks pending\" and \"no checks pending\" deny pending work rather than "
                    "disclosing it, so they do not exempt anything. When the pending count really "
                    "has drained to zero, disclose what is still failing instead -- "
                    "\"14 pass, 1 fail, 0 pending\" is exempt on the failing count. When nothing "
                    "is pending AND nothing is failing, this branch is not the one to escape: "
                    "re-query and state what you read. The staleness branch below is NOT exempt and still fires on "
                    "that same form, deliberately: disclosing pending work answers the question "
                    "THIS branch asks and not that one, since a reading taken before your last "
                    "push may describe a commit that is no longer the head whatever it discloses. "
                    "Its own escape is to re-query and state the head SHA, so the two are not "
                    "jointly unsatisfiable."
                ),
            }))
            return 0

    # Nothing pushed this session, so no reading can have gone stale.
    if last_push < 0:
        return 0
    # A query after the last push is exactly what makes the claim current.
    if last_query > last_push:
        return 0

    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-stale-status-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        with open(sentinel, "w"):
            pass
    except Exception:
        pass

    # Attribution, per ai-config#1859. A bare count with no PR reference near
    # it may well be a local test run, so say what was MATCHED rather than
    # asserting what it MEANS. The staleness finding is unchanged either way --
    # the issue's guidance was to soften the wording, not narrow the trigger.
    # Every un-negated assertion in the message votes, not just the first one
    # `find_unnegated_assert` happened to return. A message can open with a
    # bare "11 pass" and go on to say "ready to merge"; deciding from the
    # first match alone then softens a claim that is not soft at all -- the
    # same misdescription this fix exists to remove, pointing the other way.
    # Any non-bare-count phrase, or any count with a PR reference near it,
    # settles it as a check-state claim.
    soft = True
    for other in all_unnegated_asserts(text):
        window = text[max(0, other.start() - NEARBY_WINDOW):
                      other.end() + NEARBY_WINDOW]
        if not RX_BARE_COUNT.match(other.group(0).strip()):
            soft = False
            break
        if RX_PR_NEARBY.search(window):
            soft = False
            break
    if soft:
        lead = "Your message states a pass/fail count"
        consequence = (
            "If that count came from a local test run rather than from this "
            "PR's checks, say so explicitly -- the fix is to label it, not to "
            "re-query. If it is a claim about the PR, a reader may merge on it."
        )
    else:
        lead = "Your message asserts a PR's check state"
        consequence = (
            "This is a claim about whether work is finished, so the reader may "
            "merge on it."
        )

    push_spec = f" ({last_push_cmd})" if last_push_cmd else ""
    print(json.dumps({
        "decision": "block",
        "reason": (
            f"{lead} -- "
            f"\"{hit.group(0).strip()}\" -- but the most recent status query in "
            f"this transcript is OLDER than your most recent push{push_spec}, so "
            "the reading you are about to report MAY describe a commit that is "
            "no longer the head.\n\n"
            "This comparison is by TIME, not by repository or branch: a push "
            "to a different repo, or to a branch this claim is not about, "
            "trips it just the same. So check that premise rather than "
            "conceding it -- if the push cannot have moved the head you are "
            "reporting on, the reading was current and the correction you owe "
            "is none. Re-query anyway, because confirming that costs one "
            "query, but do not write a retraction the evidence does not "
            "support.\n\n"
            f"{consequence}\n\n"
            "Re-query now, in this same message, and state the head SHA "
            "alongside the counts:\n\n"
            "    git rev-parse --short origin/<branch>\n"
            "    # GitHub:\n"
            "    gh pr view <N> -R <owner>/<repo> --json headRefOid "
            "--jq '.headRefOid[0:8]'\n"
            "    gh pr checks <N> -R <owner>/<repo> | awk -F'\\t' '{print $2}' "
            "| sort | uniq -c\n"
            "    # GitLab:\n"
            "    glab mr view <IID> -R <group>/<project>\n"
            "    glab ci status -R <group>/<project>\n\n"
            "Confirm the two SHAs agree before reporting. Note also that a "
            "freshly pushed head often shows a small green count simply "
            "because most jobs have not been scheduled yet -- an early reading "
            "is stale AND taken before the check set finished expanding."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
