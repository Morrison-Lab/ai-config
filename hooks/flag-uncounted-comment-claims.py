#!/usr/bin/env python3
"""PreToolUse reminder: an outgoing forge-comment body asserts a count or an
enumerated list, with no deriving command anywhere nearby.

`hooks/remind-brief-premises.py` already carries this exact heuristic --
`shared/workflow/challenge-the-assignment.md`'s point that a claim which
merely INSTRUCTS ("here is what I found") reads with the sender's authority
rather than with evidence behind it -- but only on Agent/Task/SendMessage
BRIEFS. A forge comment is the same shape of artifact, posted to a wider
audience, and it went uncovered.

THE INCIDENT (Morrison-Lab/ai-config#2377)
-------------------------------------------
2026-08-26, a sparta ARDIA session. `remind-brief-premises.py` correctly
flagged an unverified "[cardinality] two comments ..." claim inside an Agent
brief. The SAME session then posted TWO forge comments
(`gh pr comment --body-file`) each asserting an enumerated file list recalled
from memory rather than derived. One was wrong: it claimed the fingerprinted
scripts were `cycle-charge-flee` / `interval-labels` /
`multi-unit-form-up-modes` / `group-attack`, when the derived truth was
`brace-vs-unbraced-charge` / `defensive-doctrine-plan` / `interval-labels` /
`reserve-trailing-advance` (and 18 files on `main`). It needed a public
correction comment on sparta#1401.

The pattern/anti-pattern pair this hook exists to enforce, quoted from the
issue: Do paste the deriving command (or its output count) beside any
enumerated claim in a comment body; Don't restate a population from working
memory because a related list was just read -- both slips happened minutes
after reading adjacent-but-different lists.

WHY A SEPARATE HOOK RATHER THAN WIDENING remind-brief-premises.py's OWN MATCH
-------------------------------------------------------------------------
That hook's `PATH` clause is anchored to THIS corpus's own tracked
directories (`shared/`, `memories/`, `skills/`, `hooks/`, `scripts/`,
`codex-skills/`, `CLAUDE.md`, `MEMORY.md`) -- correct for an Agent brief,
which is almost always about ai-config's own corpus state. A forge comment
fires in EVERY repo a session works in, and the incident itself was about
sparta's OWN game-script files, which carry none of those prefixes. So the
claim detector below is deliberately corpus-agnostic: a COUNT plus a
LISTABLE_NOUN, or a listable noun followed by a hand-typed list of
identifier-shaped tokens -- no path anchor at all. The trade is precision:
`remind-brief-premises.py` can key its discharge to the SPECIFIC path a claim
names; this hook cannot, so its discharge (below) is scoped differently on
purpose.

The command-detection and body-extraction machinery is NOT reinvented here.
`flag-uncited-rebuttal.py`'s `parse_comment_post()` already reads a
`gh pr comment` / `gh issue comment` / `gh api .../comments` body from
disk when it is file-based (`--body-file`, `-F body=@file`) or from the
command text when it is a literal (`--body`, `-f body=...`), per this
corpus's own "PowerShell CLI Command Safety" convention that the file is
always written before the `gh` call -- so it already exists by the time this
hook runs. Importing it (per the `_sibling()` pattern `remind-ums-on-scrutiny.py`
and `no-empty-promise.py` already use for a hyphenated module) is what
"the hook can read `--body-file`'s content" in the issue means in practice;
writing a second parser for the same six body-argument shapes would drift
from that one exactly the way `require-agent-disclosure.py`'s own docstring
warns four separate flags did before they were centralised.

WHAT COUNTS AS A CLAIM
-----------------------
Two shapes, deliberately narrower than a bare number-plus-noun anywhere in
the comment, because a forge comment says "found 2 issues" or "three commits"
constantly for things that need no re-deriving (this hook fires on EVERY
outgoing comment in EVERY repo, a far larger and more varied population than
Agent briefs):

  * CARDINALITY -- a COUNT (digit run or a number word) followed, within a
    small gap, by a plural noun drawn from LISTABLE_NOUN -- a curated
    vocabulary of countable, listable ARTIFACTS (files, scripts, lines,
    tests, comments, mentions, sites, findings, PRs, commits, hooks, ...).
    The noun carries the precision burden that `remind-brief-premises.py`'s
    PATH clause carries there: an unscoped "any plural noun" would fire on
    "three days" or "two people" just as readily as "18 files".
  * ENUMERATION -- a LISTABLE_NOUN followed shortly by a hand-typed list of
    two or more IDENTIFIER-shaped tokens (a letter, then at least one
    hyphen/underscore/dot-separated segment) joined by `/` or `,`. This is
    the shape the incident's wrong list took --
    "`cycle-charge-flee` / `interval-labels` / ..." -- and it fires even with
    no explicit numeral in front. The hyphen/underscore/dot requirement is
    what keeps this off ordinary prose lists this corpus posts constantly
    ("Addressed, Rebutted, or Deferred" has no such token in it).

DISCHARGE
---------
Two tiers, both requiring the derivation to be CAUSALLY near this exact
post -- never a whole-session scan.

  1. A counting/listing-shaped command (`grep -c`, `rg --count`, `wc -l`,
     `find ... | wc -l`, `jq ... | length`, or any `grep`/`rg`/`find`/`jq`
     invocation) sitting in a CODE SPAN inside the comment body itself --
     the "paste the deriving command beside the claim" the issue asks for.
  2. The same shape in another SEGMENT of the same Bash call (the
     `N=$(gh api .../comments | jq length); gh pr comment ... --body "..."`
     idiom) -- checked over the command text with the extracted body
     substring removed, so a body that merely MENTIONS the word "grep" in
     prose cannot discharge itself by accident.

A CARDINALITY claim needs a COUNTING command specifically (`grep -c`,
`wc -l`, ...); an ENUMERATION claim is satisfied by any inspecting one
(`grep`, `find`, ...) -- listing files IS deriving the list, the same
asymmetry `remind-brief-premises.py` draws between its "cardinality" and
"content" claim kinds ("listing lines is not counting them" runs the other
way here: listing files *is* deriving an enumeration).

WHY NO TRANSCRIPT-WIDE (WHOLE-SESSION) DISCHARGE
--------------------------------------------------
`remind-brief-premises.py` also discharges a claim from an EARLIER
`grep`/`Read` anywhere in the session transcript, keyed to the SAME path. A
population-agnostic version of that check -- "was ANY counting command run
earlier this session" -- has no path key to scope it, and a real ARDI/PR-
babysitting session runs `grep`/`wc -l`/`find` constantly for unrelated
reasons across dozens of turns. Adding that tier would discharge nearly every
real comment in a live session, which is exactly the over-broad-discharge
failure `remind-brief-premises.py`'s own docstring names -- "silence is
indistinguishable from compliance". So this hook deliberately stops at the
two CAUSALLY-SCOPED tiers above and accepts the narrower coverage.

SCOPE: Bash ONLY, not MCP
--------------------------
`require-agent-disclosure.py` covers both the Bash CLI forms and the
`mcp__github__*` comment tools, because a remote/web session has no `gh` at
all. This hook covers Bash only, per the issue's stated trigger surface
("PreToolUse Bash commands matching gh pr comment / gh issue comment /
gh api ...comments"). Extending it to the MCP tools is a real gap for a
remote session and is left for a follow-up rather than folded in here.

WHY THIS INJECTS RATHER THAN BLOCKS
-------------------------------------
Same posture as every sibling in this file's family
(`remind-brief-premises.py`, `flag-uncited-rebuttal.py`,
`require-agent-disclosure.py`): a missed claim is cheap to correct with a
follow-up comment, while a blocked `gh pr comment` interrupts the one action
that makes work visible to other sessions. Emits only `additionalContext`
and a `systemMessage`; no `permissionDecision`.

Fires once per distinct (command, claim-set) per session, via the same
transcript-path-keyed `/tmp` sentinel `remind-brief-premises.py` uses, so a
retried identical command does not nag twice.

Fails OPEN and SILENT: any parse trouble prints nothing at all.

See `hooks/test-flag-uncounted-comment-claims.py` for the fixtures.
"""
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def _sibling(name, key):
    """Import a hyphenated sibling module, or None if unavailable.

    Same pattern `remind-ums-on-scrutiny.py` and `no-empty-promise.py` use.
    Fails open: if a sibling hook is ever renamed or moved, this hook goes
    silent rather than raising, per the file-wide fail-open contract.
    """
    path = os.path.join(HERE, name)
    try:
        spec = importlib.util.spec_from_file_location(key, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


_premises = _sibling("remind-brief-premises.py", "_sib_comment_cardinality_premises")
_rebuttal = _sibling("flag-uncited-rebuttal.py", "_sib_comment_cardinality_rebuttal")

# Reused verbatim -- all four are already corpus-agnostic in
# remind-brief-premises.py (they operate on arbitrary text, not on the PATH
# clause), so nothing here re-derives them.
COUNT = getattr(
    _premises, "COUNT",
    r"\d[\d,]*|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
    r"|zero|no",
)
NOT_PLURAL = getattr(_premises, "NOT_PLURAL", {
    "is", "was", "has", "does", "goes", "this", "its", "us", "thus",
    "less", "plus", "yes", "as", "hers", "theirs", "whose",
})
NOT_A_NOUN = getattr(_premises, "NOT_A_NOUN", re.compile(r"[_./\d]"))
DERIVE_ANY = getattr(
    _premises, "DERIVE_ANY",
    re.compile(
        r"\b(?:git\s+)?(?:grep|rg|ag|ack)(?![-\w])|\bsed\s+-n\b|\bwc\s+-"
        r"|\bjq(?![-\w])|\|\s*length\b",
    ),
)
DERIVE_COUNT = getattr(
    _premises, "DERIVE_COUNT",
    re.compile(
        r"\b(?:git\s+)?(?:grep|rg|ag)(?![-\w])\s+(?:-[a-z]*c[a-z]*\b|--count\b)"
        r"|\bwc\s+-[a-z]*l\b|\|\s*wc\b|\|\s*length\b|\bcount\s*\(",
    ),
)
visible_prose = getattr(_premises, "visible_prose", lambda t: t)
code_segments = getattr(_premises, "code_segments", lambda t: [])

# The one piece of real reuse this hook exists to do: reading a comment's
# body off disk (`--body-file`, `-F body=@file`) or out of the command text
# (`--body`, `-f body=...`) for `gh pr comment` / `gh issue comment` /
# `gh api .../comments` and `.../comments/N/replies`. See the module
# docstring's "not reinvented here" section.
parse_comment_post = getattr(_rebuttal, "parse_comment_post", None)

# ---------------------------------------------------------------- vocabulary
# Countable, listable ARTIFACTS -- the noun carries the precision burden a
# path anchor carries in remind-brief-premises.py. Deliberately excludes
# generic measure words (minutes, dollars, times, people, days) that would
# fire on ordinary cardinality prose no forge comment needs to re-derive.
# Deliberately EXCLUDES the review-housekeeping words a forge comment uses
# in routine, self-evident summary prose ("found 2 issues", "three commits",
# "fixes one bug") -- an adversarial review of this hook (ai-config#2377
# round 1) measured that vocabulary firing on exactly those two phrasings,
# which is precisely the noise this hook's own docstring says it must not
# create. `issues?`/`prs?`/`pulls?`/`commits?`/`findings?`/`changes?`/
# `edits?`/`fixes?`/`bugs?`/`errors?`/`warnings?`/`rounds?`/`regressions?`
# were all in an earlier version of this list and are gone for that reason.
# What remains is ARTIFACT-enumeration vocabulary: the kind of noun a
# session names when it lists concrete, checkable things (files, scripts,
# skills, tests), not when it summarizes what a review round did.
LISTABLE_NOUN_PATTERN = (
    r"files?|scripts?|lines?|tests?|comments?|mentions?|sites?"
    r"|occurrences?|references?|instances?|entries?|threads?"
    r"|checks?|workflows?|functions?|methods?|classes?|modules?"
    r"|examples?|cases?|items?|rows?|columns?|records?|hooks?"
    r"|skills?|memories?|branches?|repos?|repositories?|places?"
    r"|spots?|locations?|callers?|usages?|matches?|hits?|results?"
)
LISTABLE_NOUN_RE = re.compile(r"(?:" + LISTABLE_NOUN_PATTERN + r")", re.I)

# An identifier- or filename-shaped token: a letter, then at least one
# hyphen/underscore/dot-separated segment. Requiring that separator is what
# keeps this off an ordinary word list ("Addressed, Rebutted, or Deferred"
# has no such token), while still matching `cycle-charge-flee`, `foo.gd`,
# `some_script`.
TOKEN = r"[A-Za-z][A-Za-z0-9]*(?:[-_.][A-Za-z0-9]+)+"

# CARDINALITY: `\bCOUNT [ \t]+ (bounded gap) PLURAL_LISTABLE_NOUN\b`. Two
# fixes layered on top of each other, both found by adversarial review of
# this hook (ai-config#2377), and the second is a direct side effect of the
# first.
#
# Round 1: with a lazy `{0,2}?` WORD-counted gap and an unconstrained noun
# group, the engine accepted the very first word it tried (zero gap) without
# ever needing to look further, so a real match like "18 new files" was
# never reached -- "new" satisfied an unconstrained noun group and the match
# returned before "files" was ever examined. Requiring the noun to end in
# `s` INSIDE the group itself (rather than filtering afterward) is what
# forces the engine to keep expanding the gap until it actually finds a
# plural word, mirroring remind-brief-premises.py's `plural_after`.
#
# Round 2: making the gap backtrack at all is what exposed a second bug --
# a WORD-counted gap (`(?:[\w./-]+\s+){0,2}?`) has no sense of a sentence or
# paragraph boundary, so once it needs to search past the first word, it
# happily walks straight through a period or a newline to find a plural noun
# in an ENTIRELY DIFFERENT SENTENCE: "Reviewed PR 12 on GitHub. Scripts
# still need work" matched "12 on GitHub. Scripts" as one claim, and
# "Filed as issue 5 in Slack.\nResults are pending" matched "5 in Slack.
# Results" -- both real review-comment phrasing, not contrived corpus text.
# `ENUM_RE` already had this guard (`[^\n.:]`) from round 1; this regex did
# not, because round 1's own bug happened to make the gap unreachable in
# practice. Switching from a word-counted gap to a CHARACTER-bounded one
# excluding newline/period/colon -- the same shape `ENUM_RE` uses -- closes
# both the sentence-crossing and paragraph-crossing cases at once: neither
# character can ever appear inside the gap, so the match simply fails
# rather than reaching into the next sentence.
#
# `CARDINALITY_COUNT` below is `COUNT` minus the word "no", found while
# verifying the ENUM_RE fix for ai-config#2377 round 2 against the review's
# own repro sentence: "No occurrences found in skills/select-model/SKILL.md"
# still fired a `('cardinality', 'No occurrences')` claim after the
# enumeration half was fixed, because `COUNT` (imported from
# remind-brief-premises.py, where it is correctly generic) treats "no" as a
# numeral alongside "zero". "No occurrences", "no matches", "no dead
# branches" are negations -- ordinary review-comment hedging, not a specific
# derived count someone could have gotten wrong -- and they are extremely
# common phrasing, which is exactly the erosion-of-trust risk the review
# comment itself named. "zero" is kept: it is unambiguous ("zero files
# remain" is a real, checkable count) in a way the negation particle "no" is
# not. This is a LOCAL exclusion, not a change to the shared `COUNT`
# constant -- `remind-brief-premises.py`'s own Agent-brief use of "no" is a
# different population (a brief instructing an agent, not review-comment
# prose) and is out of scope for this hook's fix.
CARDINALITY_COUNT = (
    r"\d[\d,]*|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
    r"|zero"
)
CARDINALITY_RE = re.compile(
    rf"\b({CARDINALITY_COUNT})\b[ \t]+[^\n.:]{{0,24}}?([A-Za-z][\w-]*s)\b", re.I,
)

# ENUMERATION: a listable noun, an optional short gap (never crossing a
# sentence boundary) and optional colon, then >=2 TOKENs joined by `/` or `,`.
#
# `(?![-_./])` immediately after the noun is load-bearing, not decorative:
# without it, a corpus path whose own segments happen to contain hyphens --
# `skills/select-model/SKILL.md`, this repo's own standard citation shape --
# reads as "skills" (the noun, taken straight from the path) followed by a
# two-item `/`-joined list ("select-model", "SKILL.md"). A narrower `(?!/)`
# is not enough on its own: a listable noun that is itself the FIRST
# hyphenated segment of a longer compound identifier (`checks?` matching
# "check" inside `check-open-prs-before-duplicating`) reads the rest of that
# same identifier as a `/`-joined list the same way. Requiring the noun be
# followed by neither a path separator NOR a hyphen/underscore/dot is what
# tells a single identifier's own internal structure apart from a hand-typed
# list of SEVERAL identifiers, without giving up the "no explicit numeral
# needed" case the incident's own wrong claim used -- a real list still
# needs only a colon or a space between the noun and its items, never a
# hyphen glued straight onto the noun. Measured in an adversarial review of
# this hook (ai-config#2377 round 1): the unguarded pattern matched 43% of
# this repo's own shared/**/*.md + skills/**/*.md files, the large majority
# of them exactly this class of false positive.
#
# That guard only protects the position IMMEDIATELY after the matched noun,
# and a DIFFERENT listable noun earlier in the same sentence still reaches
# the same false positive by a different route: the gap's own character
# class allowed `/`, so it could swallow an entire BARE directory segment
# (one with no internal hyphen/underscore/dot of its own -- "skills", not
# "select-model") plus its trailing slash, and resume the token-list match
# mid-path. "No occurrences found in skills/select-model/SKILL.md" matched
# noun "occurrences" (correctly passing the post-noun lookahead, since it is
# followed by a space) with a gap of "found in skills/" that swallowed the
# slash itself, so the token list started at "select-model/SKILL.md" -- a
# single-file citation misread as a two-item list. Found in an adversarial
# review of this hook (ai-config#2377 round 2), reproduced with
# `find_claims('No occurrences found in skills/select-model/SKILL.md after
# the fix.')`. Excluding `/` from the gap's own character class closes this:
# a real enumeration's gap is prose ("are:", "found in the"), never the
# list's own separator, so a gap that would need to cross a `/` to reach a
# token list is exactly the "this is a path, not a hand-typed list" signal
# -- and `skills`, tried as its own noun candidate once the gap can no
# longer swallow it, fails the SAME `(?![-_./])` lookahead that was already
# guarding this case directly.
#
# THE PATH-VS-LIST GRAMMAR CLASS -- NINE ROUTES ACROSS NINE REVIEW ROUNDS
# (SEVEN FIXED, TWO PRE-DISPOSITIONED -- SEE THE STANDING STATEMENT BELOW).
# Renamed from "false-positive class" once route 6 found the mirror-image
# failure: the SAME underlying confusion -- `TOKEN` cannot tell "one file's
# own path, N directory segments then a filename" from "several hand-typed
# identifiers joined by `/`", because both are letters, hyphens, and dots
# joined by a slash -- produces an over-broad match in one direction
# (routes 1-5, false positives) and a match that stops too soon in the
# other (routes 6-9, false negatives). Routes 1-2 are about WHERE the match
# starts (the noun); routes 3-5 are about WHAT the captured list's items
# look like, and after the third one of THOSE the fix stopped being "count
# separators and items harder" and became a CLASS BOUNDARY, drawn once in
# `looks_like_one_path()` below rather than re-derived per shape:
#   1. The NOUN itself sits directly against the path with no separator
#      (`skills/select-model/SKILL.md` reading "skills" as the noun). Closed
#      by the `(?![-_./])` lookahead right after the noun, above.
#   2. A DIFFERENT, earlier noun's gap swallows a bare (non-hyphenated)
#      directory segment plus its slash, resuming the match mid-path
#      ("No occurrences found in skills/..."). Closed by excluding `/` from
#      the gap's own character class, above.
#   3. The path's OWN two segments are independently hyphen/dot-shaped
#      (`ai-config/claude-hook-adapter.py`, `local-bin/encrypt-gh-token.sh`)
#      and satisfy `TOKEN` on BOTH sides with no gap involved at all --
#      "No hits found in local-bin/encrypt-gh-token.sh" matches the noun
#      immediately adjacent, using neither of the tricks routes 1 and 2
#      closed. A three-or-more-segment version of the same thing
#      (`codex-skills/pre-push-review/SKILL.md`) was a fourth, narrower
#      route past an early exactly-two-item version of this same fix.
#   5. TWO SEPARATE path citations, joined by a COMMA
#      (`ai-config/claude-hook-adapter.py, local-bin/encrypt-gh-token.sh`),
#      each independently hyphen/dot-shaped and each containing its own
#      internal `/`. Every earlier fix for routes 3-4 keyed on "every
#      separator in the whole span is `/`" -- correct for ONE path split
#      into segments, wrong the moment TWO citations are cited together
#      with the ordinary English list separator.
#
# DESIGN DECISION (ai-config#2386 review round 5): patching route 5 the same
# way as routes 3-4 -- special-casing "a `,` may join two all-`/` runs" --
# would be a SIXTH regex-shaped patch on a problem that has now produced a
# new shape in three consecutive rounds. Five rounds hitting one grammar is
# itself the signal: the level `looks_like_one_path()` was operating at
# (count separators, count items, ask whether the SPAN look like a path) is
# the wrong level. The level that actually settles it is the ITEM: an
# extension-terminated, SLASH-CONTAINING token is citation-shaped, full
# stop, independent of how many of them appear or what joins them. A list
# whose items are ALL citation-shaped this way is a list of citations, never
# a hand-typed enumeration of identifiers -- so `looks_like_one_path()` now
# classifies the captured span by splitting on `,` FIRST (the one separator
# that is never itself part of a real path) and asking whether every
# resulting piece looks like one citation, rather than asking whether the
# WHOLE span does.
#
# This trades away real coverage, and the trade is deliberate rather than
# incidental: a genuine hand-typed enumeration of several FULL paths
# (`the affected files: scripts/alpha.py, scripts/beta.py, scripts/gamma.py`)
# now goes UNDETECTED as an enumeration claim. That is accepted because the
# guard's actual purpose is catching a RECALLED-NOT-DERIVED population
# claim, and a population claim about files essentially always carries an
# explicit count somewhere nearby ("the 3 affected files ...") -- which
# `CARDINALITY_RE` still catches, unaffected by any of this. What
# `ENUM_RE`/`looks_like_one_path()` give up is narrower: an enumeration with
# NO accompanying count, where every item is independently a real path
# citation. The original incident this hook exists for was never that shape
# -- its wrong claim named bare SCRIPT IDENTIFIERS (`cycle-charge-flee`,
# `interval-labels`, ...), not full paths with directories and extensions --
# so this class boundary does not weaken the one case the hook was built to
# catch. A bare identifier list, with or without a count, stays fully
# covered; a list of concrete path citations, which is closer to a
# reference than to a recalled population, stops being treated as one.
#
# No regex lookahead placed near the noun can close routes 3-5 -- the noun
# is not even adjacent to the part that is wrong -- which is why all three
# are closed downstream, by inspecting the captured list's own items in
# `looks_like_one_path()`, rather than by tightening the match itself.
#
#   6. A FALSE NEGATIVE, the first one in this class -- every route above is
#      an over-broad match; this one is a match that stops too SOON. `TOKEN`
#      cannot end on a bare trailing `/`, so when a directory citation
#      (`codex-skills/pre-push-review/`) sits BEFORE a comma in the middle
#      of a real enumeration, the token-list clause has no way to consume
#      that trailing slash and simply stops there -- the comma, and every
#      recalled identifier after it, fall completely outside the match.
#      "The fingerprinted scripts: codex-skills/pre-push-review/,
#      cycle-charge-flee, interval-labels." -- the exact composite shape
#      (one genuine citation, prefixed to a recalled list) the founding
#      incident itself used -- went entirely undetected: `find_claims`
#      returned `[]`, not a suppressed enumeration claim but no match at
#      all. `looks_like_citation`'s own per-item design was never the
#      problem here (a mixed list correctly fires once it reaches the
#      classifier, since not every piece is citation-shaped) -- the bug is
#      UPSTREAM, in the matcher, which never handed the classifier the full
#      span to classify. Closed by letting the token-list clause's own
#      separator optionally absorb a dangling `/` immediately before the
#      real `,`-or-`/` separator (`\s*/?(?:,|/)\s*` in place of
#      `\s*(?:,|/)\s*`), so a trailing-slash directory mid-list no longer
#      terminates the match -- it terminates the SAME way an ordinary
#      2-segment path already does when nothing valid follows it (via the
#      existing `trailing_char` fallback), but now the parser can also walk
#      past it when there IS something valid after, exactly as it already
#      does past an ordinary `,` or `/` between any other two items.
#
#      Verifying route 6 with an adversarial derivation swept up an ADJACENT
#      false positive, from a DIFFERENT, PRE-EXISTING cause: `TOKEN` has
#      always required every path SEGMENT to itself carry an internal
#      hyphen/underscore/dot, so a real citation whose own middle segment is
#      a bare word (`ai-config/memories/tools.md` -- "memories" has none)
#      truncates the match early, the same shape as route 6 but for a
#      different reason `TOKEN` itself cannot fix without giving up the
#      precision that keeps ordinary prose off this list entirely. The
#      truncated fragment left behind (bare `"ai-config"`, immediately
#      followed by the unconsumed `/memories/tools.md`) was being read as a
#      plain identifier rather than as the start of a cut-short citation.
#      Closed in `looks_like_citation()` by checking `trailing_char` BEFORE
#      requiring an internal `/` in the piece itself -- see that function's
#      own docstring. The underlying limitation (a bare-segment path is
#      never detected as an enumeration ITEM at all, so a real citation
#      shaped that way still goes unflagged when mixed with recalled
#      identifiers) is tracked separately as ai-config#2404: fixing it means
#      widening `TOKEN`, a materially larger and riskier change than
#      anything routes 1-6 needed, and belongs in its own design pass.
#
#   7. Route 6's own `trailing_char` fix was ITSELF too coarse: it treated
#      ANY `/` sitting immediately after the match as proof the preceding
#      item was a citation, with no regard for what followed that `/`. A
#      bare recalled identifier immediately followed by a coincidental,
#      UNRELATED `/`-suffix (a date, `cycle-charge-flee/2026`; a branch
#      name, `cycle-charge-flee/main`) got silently promoted to "citation"
#      and the whole mixed list -- the founding incident's own composite
#      shape -- went undetected. This is the identical LOCAL SHAPE as route
#      6's own fix target (a bare piece, no internal `/`, immediately
#      followed by another `/`): `ai-config` before `/memories/tools.md`
#      and `cycle-charge-flee` before `/2026` are LEXICALLY INDISTINGUISHABLE
#      from a single character of lookahead, which is why naively requiring
#      an internal `/` before `trailing_char` can apply (the reviewer's own
#      first-pass suggestion) would have REOPENED route 6's fix rather than
#      closing route 7 -- the two bugs cannot both be fixed by a piece-and-
#      one-character heuristic. What distinguishes them is what comes AFTER
#      the dangling `/`: `/memories/tools.md` is entirely `/`-segments
#      (however bare) that eventually resolve to a real extension; `/2026`
#      is not even segment-shaped (no path segment, bare or not, starts
#      with a digit); `/main` IS segment-shaped but resolves to neither an
#      extension nor a bare trailing `/`. Closed by widening `trailing_char`
#      into a bounded, whitespace-terminated CONTINUATION and classifying
#      it with `looks_like_path_continuation()` rather than a single
#      character -- see that function and `looks_like_citation()` for the
#      full mechanism.
#
#      SEVEN ROUNDS ON ONE GRAMMAR is the signal a structural rewrite --
#      not another item on this list -- deserves serious consideration
#      before shipping an eighth special case, and it was: a PRE-PASS that
#      scans raw prose for citation-shaped spans and replaces each with a
#      placeholder BEFORE `ENUM_RE` ever runs, so the citation grammar and
#      the list grammar never share a match to disagree about. Rejected,
#      not out of caution but because it does not actually buy what it
#      promises: `ai-config/memories/tools.md`'s own bare "memories"
#      segment defeats a PRE-PASS SCAN exactly the way it defeats `TOKEN`
#      inside `ENUM_RE` -- the scan cannot find "ai-config/memories/tools.md"
#      as one span either, so it would mask nothing, and the identical
#      truncated-fragment ambiguity resurfaces one layer up, needing the
#      SAME continuation-lookahead refinement to resolve. A pre-pass would
#      ALSO have reopened a NEW risk this design avoids: masking a long
#      citation down to a short placeholder can shrink the distance between
#      an unrelated COUNT and a distant noun below `CARDINALITY_RE`'s/
#      `ENUM_RE`'s own 24-character gap bounds, manufacturing cardinality
#      false positives that do not exist in the unmasked text. Given the
#      fix needed is the SAME either way, the narrow, already-reviewed
#      `looks_like_citation`/`looks_like_one_path` apparatus was extended
#      in place rather than rewritten wholesale seven rounds into this PR.
#      A genuinely NEW route 8 would need a shape none of the seven routes
#      or this analysis anticipated; testing "all orderings" for route 7
#      (see `ACCEPTED_MISS_COINCIDENTAL_SLASH_ITEM_FIRST` in the test suite)
#      found exactly one more residual, and it traces to ai-config#2404's
#      ALREADY-TRACKED limitation (a coincidental-slash identifier as the
#      very FIRST list item defeats the token-list clause's own SEPARATOR,
#      a different mechanism than `trailing_char`/`continuation`), not to a
#      new, unrelated route.
#
#   8. `looks_like_path_continuation()`'s extension check cannot tell a real
#      file extension from a version-number tail (`feature/v2.1`), so a
#      coincidental version-like suffix reopens route 7's exact failure
#      through the same `PATH_EXTENSION_RE` this whole class already
#      accepted one trade for (see that regex's own comment, extended for
#      this route). PINNED AS AN ACCEPTED RESIDUAL
#      (`ACCEPTED_MISS_VERSION_SUFFIX_*`), not fixed with a ninth predicate.
#   9. `looks_like_path_continuation()`'s OTHER branch --
#      `continuation.endswith("/")`, untouched by routes 7-8 -- has the same
#      gap: ANY coincidental continuation ending in a bare trailing `/`
#      (`cycle-charge-flee/main/`, `cycle-charge-flee/v2/`) is unconditionally
#      read as a directory citation, with nothing requiring the segment
#      itself to be meaningfully path-like. Scoped to exactly the 2-item
#      case, same as routes 6-8: a 3rd bare item elsewhere in the list still
#      independently fails the citation test, so `looks_like_one_path`'s
#      `all()` still returns `False` and the claim fires -- masked there,
#      not fixed. PINNED AS AN ACCEPTED RESIDUAL
#      (`ACCEPTED_MISS_TRAILING_SLASH_SUFFIX_*`), not fixed.
#
# STANDING PRE-DISPOSITION (ai-config#2386 review round 9, generalizing
# rounds 8-9's own per-instance decisions into a rule): routes 8 and 9 are
# not the last two coincidental-slash-continuation shapes `TOKEN`'s design
# admits -- they are two DEMONSTRATED instances of an open-ended class
# (`looks_like_path_continuation()` classifying a bounded, hand-derived
# regex shape can never enumerate every string a coincidental `/`-suffix in
# ordinary English prose might take). Nine review rounds establishing that
# pattern twice in a row is itself the evidence, not a coincidence to
# re-litigate a tenth time. ANY future coincidental-slash-continuation shape
# found reachable through this mechanism -- version suffixes, bare trailing
# slashes, or a shape not yet enumerated here -- is THEREFORE a
# PRE-DISPOSITIONED accepted residual of this hook's warn-only, fail-open
# design, exactly like routes 8 and 9, without needing its own round of
# review to establish that disposition fresh. `ai-config#2404` is the
# single tracked home for any future narrowing work across this entire
# class (routes 8, 9, and whatever comes after) -- add a new variant there
# rather than opening a new issue. A future review round that finds another
# member of this class should CITE THIS BLOCK rather than reopening the
# fix-vs-accept question; a pinned regression fixture for any newly
# DEMONSTRATED instance is still welcome, purely as documentation of what
# was checked, but is not a precondition for treating the class itself as
# already disposed of.
ENUM_RE = re.compile(
    rf"\b(?:{LISTABLE_NOUN_PATTERN})\b(?![-_./])[^\n.:/]{{0,24}}?:?\s*"
    rf"({TOKEN}(?:\s*/?(?:,|/)\s*{TOKEN}){{1,}})",
    re.I,
)

# Splits a captured token-list group on COMMAS ONLY, never on `/`. This is
# the round-5 design decision itself, mechanically: a `,` is never part of a
# real path, so it is the one separator safe to split on FIRST, before
# asking what each resulting piece looks like. A piece may still contain
# its own internal `/`-joined segments (a real path's own structure), which
# `looks_like_citation` below inspects on its own terms.
COMMA_SPLIT_RE = re.compile(r"\s*,\s*")

# The "this is a FILENAME" signal when an item ends in an extension-shaped
# suffix, per `looks_like_citation` below.
#
# GENERIC, not a curated extension list. An earlier version enumerated
# specific extensions (`.py`, `.md`, `.sh`, ...), and an adversarial sweep
# for ai-config#2386 round 5 -- deriving 600+ real path-like strings from
# this repo's own `*.md`/`*.qmd` files and stress-testing `find_claims`
# against each -- found dozens of real citations the curated list simply
# didn't know about (`.io`, `.jpg`, `.gz`, `.paper`, `.sbatch`, a GitHub
# repo styled `owner/name.git`): every one is a real extension SOMEWHERE,
# and a whitelist can only ever be a photograph of the ones already seen.
# A short alphanumeric suffix after a final dot is the general shape a file
# extension takes; nothing in a genuine hand-typed identifier list needs
# an item to look like that, so treating the shape itself as the signal is
# both simpler and closes the gap a whitelist cannot close by construction.
# The trade (documented, not hidden): a version-style item ending in a bare
# number after a dot ("v1.2") also matches this shape -- accepted since no
# case in this corpus's own comment history takes that form and the cost is
# a missed reminder, never a wrong one.
#
# THAT TRADE DOES NOT TRANSFER CLEANLY to `looks_like_path_continuation()`'s
# use of this same regex (added in round 7, ai-config#2386), and round 8's
# review said so explicitly. Here the version-shaped span is not the FLAGGED
# item's own text -- it is dangling content after a DIFFERENT, unrelated
# bare identifier (`cycle-charge-flee/feature/v2.1`-style: a coincidental
# branch/version suffix, not a citation at all). `_BARE_SEGMENT` parses
# `v2`/`v3` as an ordinary segment, and `.1` then satisfies this regex
# exactly as `.md` would, so `feature/v2.1` reads as "resolves to an
# extension" and the WHOLE mixed list -- founding-incident shape, real
# citation plus recalled identifiers -- goes silent. That is a materially
# worse cost than the original trade: not "one version-named item
# misclassified" but "the entire enumeration undetected," the same severity
# routes 6 and 7 were both fixed for.
#
# ACCEPTED ANYWAY, explicitly rather than left implicit, per round 8's own
# framing -- this hook is warn-only and fail-open, and eight rounds on one
# grammar is reason enough to stop adding narrower predicates rather than
# start a ninth. Pinned as `ACCEPTED_MISS_VERSION_SUFFIX_*` in the test
# suite (both of round 8's own repro sentences), the same way every other
# accepted miss in this file is pinned rather than left to a comment alone.
# The known next step, if this residual ever bites in a real comment: require
# the extension to contain at least one LETTER (ruling out purely-numeric
# tails like `.1`/`.3` while still accepting `.md`/`.py`/`.io`) -- tracked as
# part of ai-config#2404, the same issue already tracking this file's other
# `TOKEN`/extension-parsing residuals, rather than opened as a new one.
PATH_EXTENSION_RE = re.compile(r"\.[A-Za-z0-9]{1,8}$")

# A path SEGMENT that may itself be bare (no internal hyphen/underscore/dot
# at all) -- deliberately looser than `TOKEN`, which requires at least one
# such separator. Used only to describe what a genuine continuation past a
# dangling `/` could look like, never to decide what counts as an
# enumeration ITEM -- that job stays `TOKEN`'s alone.
_BARE_SEGMENT = r"[A-Za-z][A-Za-z0-9]*(?:[-_.][A-Za-z0-9]+)*"

# One or more `/segment` hops, each segment possibly bare, with an optional
# final bare `/`. This is the SHAPE `looks_like_path_continuation` requires
# a dangling continuation to have before it will even ask whether that
# continuation resolves to an extension -- see that function.
CONTINUATION_RE = re.compile(rf"(?:/{_BARE_SEGMENT})+/?")


def looks_like_path_continuation(continuation):
    """True when `continuation` -- text that starts with `/` and runs to
    the next whitespace in the source -- genuinely continues a path,
    rather than being a coincidental slash sitting next to unrelated
    prose.

    Found in an adversarial review of this hook (ai-config#2386 round 7),
    which discovered that the round-6 fix's `trailing_char` check --
    "is the very next character in the source a `/`?" -- cannot tell a
    genuine continuation from a coincidental one, because BOTH shapes are
    IDENTICAL at the single-character level:

      * `ai-config/memories/tools.md` (round 6's own fix target): TOKEN
        truncates the match after "ai-config" because "memories" has no
        internal hyphen/underscore/dot, leaving a dangling `/` that
        genuinely continues into a real file (`/memories/tools.md`).
      * `cycle-charge-flee/2026` and `cycle-charge-flee/main` (round 7's
        repro): a bare recalled identifier happens to sit next to an
        unrelated `/`-prefixed suffix (a year, a branch name) that has
        NOTHING to do with a citation.

    Both are "a piece with no internal `/`, immediately followed by
    another `/` in the source" -- indistinguishable from a single
    character of lookahead. What DOES distinguish them is what the
    continuation eventually resolves to: `/memories/tools.md` is entirely
    `/`-segments (however bare) ending in a real extension; `/2026` is not
    even segment-shaped (`2026` starts with a digit, which no path
    segment -- bare or not -- can); `/main` IS segment-shaped but resolves
    to neither an extension nor a bare trailing `/`, so it stays
    unclassified rather than being guessed at.

    A bare trailing `/` with NOTHING attached (the ordinary case a
    directory citation takes when it is the last thing in a sentence,
    `codex-skills/pre-push-review/ were found`) is the simple case and is
    handled by the caller directly -- this function is only reached when
    something IS attached to the slash.

    TWO ACCEPTED RESIDUALS remain in the classification below, found in
    rounds 8 and 9 (routes 8-9 in the class doc-comment above `ENUM_RE`,
    which also carries the standing pre-disposition covering any FURTHER
    variant of this same shape): `PATH_EXTENSION_RE` cannot tell a real
    extension from a version-number tail (`/main/v2.1` -- route 8), and the
    `continuation.endswith("/")` branch below cannot tell a genuine
    directory citation from a coincidental suffix that merely happens to
    end in a bare `/` (`/main/` -- route 9, the mirror of the very `/main`
    example above that this docstring already says "stays unclassified" --
    it does, right up until one more trailing slash is appended). Both are
    pinned as regression fixtures (`ACCEPTED_MISS_VERSION_SUFFIX_*` and
    `ACCEPTED_MISS_TRAILING_SLASH_SUFFIX_*`) rather than narrowed further.
    """
    m = CONTINUATION_RE.match(continuation)
    if not m or m.end() != len(continuation):
        return False
    return continuation.endswith("/") or bool(PATH_EXTENSION_RE.search(continuation))


def dangling_continuation(prose, pos):
    """The non-whitespace run starting at `pos` in `prose`, if `prose[pos]`
    is `/` -- otherwise `""`. A path segment never contains whitespace, so
    this is exactly the span a continuation past a dangling `/` could
    plausibly occupy; `looks_like_path_continuation` classifies it. Bounded
    to 200 characters, matching this file's other gap bounds -- nothing a
    genuine path continuation needs approaches that length.
    """
    if prose[pos:pos + 1] != "/":
        return ""
    m = re.match(r"\S{0,200}", prose[pos:])
    return m.group(0) if m else ""


def looks_like_citation(text, continuation=""):
    """True when a single comma-separated PIECE of a captured list is
    itself shaped like a citation to one file or directory -- the item-level
    test the round-5 design decision (documented above `ENUM_RE`) is built
    on.

    A piece is a citation when it has an internal `/` with either an
    extension-shaped ending or a bare trailing `/` (a directory reference:
    `codex-skills/pre-push-review/` -- the round-5 sweep's single largest
    false-positive bucket before that round's fix, 104 of 140 hits, since a
    bare N-segment directory path has no extension anywhere to key on), OR
    -- checked FIRST, independent of any internal `/` in the piece itself --
    when `continuation` (the text immediately following the WHOLE match in
    the source, supplied only for the piece that actually abuts it; see
    `dangling_continuation`) is a bare `/` or genuinely continues a path
    (`looks_like_path_continuation`).

    The `continuation` check has to come before the internal-`/`
    requirement, not after it, because of a separate, PRE-EXISTING
    limitation `TOKEN` has always had: it requires every path SEGMENT to
    itself carry an internal hyphen/underscore/dot, so a real citation whose
    own middle segment is a bare word (`ai-config/memories/tools.md` --
    "memories" has no separator) truncates the whole `ENUM_RE` match right
    after the segment before it, leaving a piece like bare `"ai-config"` --
    no internal `/` of its own -- immediately followed by the unconsumed
    `/memories/tools.md` in the source. Checking the continuation first
    means that truncated fragment is judged as what it actually is: the
    START of a second, real citation cut short by the SAME segment
    limitation that keeps this hook from ever matching such a path in full
    -- rather than as a bare identifier. Round 6 first closed this with a
    single-character `trailing_char == "/"` check; round 7 found that
    single character cannot tell a genuine continuation from a coincidental
    one (`cycle-charge-flee/2026`), which is why `continuation` is now the
    full non-whitespace run rather than one character, classified by
    `looks_like_path_continuation`. Widening `TOKEN` itself to accept a
    bare segment is a separate, much larger design question (it is the
    precision mechanism that keeps ordinary English prose off this list in
    the first place) and stays out of scope, tracked as ai-config#2404.
    """
    if text.endswith("/"):
        return True
    if continuation == "/" or looks_like_path_continuation(continuation):
        return True
    if "/" not in text:
        return False
    return bool(PATH_EXTENSION_RE.search(text))


def looks_like_one_path(group_text, continuation=""):
    """True when a captured ENUM_RE list is entirely made of path citations.

    Named for route 3 of the path-citation class documented above `ENUM_RE`
    -- "one file's own path, misread as a hand-typed list" -- and widened by
    round 5's design decision to cover any number of SEPARATE citations
    joined however they are joined, not only one path's own segments.

    Splits on `,` FIRST (via `COMMA_SPLIT_RE`), since a comma is never part
    of a real path, then asks whether EVERY resulting piece looks like one
    citation (`looks_like_citation`, above) on its own. A single piece with
    no comma covers routes 3-4 (one path, N `/`-joined segments); two or
    more pieces cover route 5 (two or more SEPARATE citations, comma-joined,
    each with its own internal `/`) -- both are the same underlying
    question at different granularities, which is why one function answers
    both rather than two.

    A bare identifier -- no internal `/` at all -- can never pass
    `looks_like_citation`, at any position, so a genuine comma-joined list
    of plain identifiers (`cycle-charge-flee, interval-labels`), or even of
    bare EXTENSION-terminated filenames with no directory component
    (`foo.py, bar.py`), still fires: neither piece contains a `/`, so
    neither ever reads as a citation. Only a piece that itself looks like a
    path -- because it names one, directory and all -- is exempted.
    """
    pieces = COMMA_SPLIT_RE.split(group_text)
    last = len(pieces) - 1
    return all(
        looks_like_citation(piece, continuation if i == last else "")
        for i, piece in enumerate(pieces)
    )

# ENUMERATION, bulleted-list form: a listable noun introducing a markdown
# bullet list, each line an identifier-shaped token. `ENUM_RE` only sees
# items joined inline on one line ("a / b / c"); a poster listing the same
# claim as a bulleted list -- arguably the more natural way to present a
# file enumeration in a forge comment -- was invisible to it. `{2,}` bullet
# lines, matching ENUM_RE's own >=2-items bar. `/` excluded from the gap for
# the same reason it is excluded from `ENUM_RE`'s (ai-config#2377 round 2):
# an intro line ending in a colon and citing a path ("No occurrences found
# in skills/select-model/SKILL.md:") followed by unrelated bulleted content
# below it would otherwise let the gap swallow the whole path, including its
# slash, on the way to that colon.
ENUM_BULLET_RE = re.compile(
    rf"\b(?:{LISTABLE_NOUN_PATTERN})\b(?![-_./])[^\n/]{{0,40}}?:\s*\n"
    r"((?:[ \t]*[-*]\s+[^\n]*\n?){2,})",
    re.I,
)
BULLET_TOKEN_RE = re.compile(rf"^[ \t]*[-*]\s+`?({TOKEN})`?", re.M)


def find_claims(body_text):
    """[(kind, quote)] for every cardinality/enumeration claim in body_text.

    Scans `visible_prose(body_text)` -- fences and blockquotes dropped,
    inline code unwrapped -- so a code span cannot itself supply a claim's
    noun (matching remind-brief-premises.py's NOT_A_NOUN reasoning) while an
    identifier a poster wrote in backticks (the common case for a file list)
    still reads as plain text.
    """
    prose = visible_prose(body_text)
    found, seen = [], set()

    for m in CARDINALITY_RE.finditer(prose):
        noun = m.group(2)
        low = noun.lower()
        if low in NOT_PLURAL or NOT_A_NOUN.search(noun):
            continue
        if not LISTABLE_NOUN_RE.fullmatch(low):
            continue
        quote = " ".join(m.group(0).split())
        key = ("cardinality", quote.lower())
        if key in seen:
            continue
        seen.add(key)
        found.append(("cardinality", quote))

    for m in ENUM_RE.finditer(prose):
        if looks_like_one_path(m.group(1), dangling_continuation(prose, m.end())):
            continue
        quote = " ".join(m.group(0).split())
        key = ("enumeration", quote.lower())
        if key in seen:
            continue
        seen.add(key)
        found.append(("enumeration", quote))

    for m in ENUM_BULLET_RE.finditer(prose):
        tokens = BULLET_TOKEN_RE.findall(m.group(1))
        if len(tokens) < 2:
            continue
        quote = " ".join(m.group(0).split())
        key = ("enumeration", quote.lower())
        if key in seen:
            continue
        seen.add(key)
        found.append(("enumeration", quote))

    return found


def _derived_in_body(body_text, need_count):
    """A counting/listing command sits in one of body_text's own code spans."""
    for _n, seg in code_segments(body_text):
        if DERIVE_COUNT.search(seg):
            return True
        if not need_count and DERIVE_ANY.search(seg):
            return True
    return False


def _derived_in_other_segments(command, body_text, need_count):
    """A counting/listing command sits elsewhere in the same Bash call.

    The extracted body substring is removed first, so a body that merely
    MENTIONS "grep" in ordinary prose cannot discharge itself -- this must
    be shell text the command would actually run, not text the command
    would merely post.
    """
    if body_text and body_text in command:
        outside = command.replace(body_text, "", 1)
    else:
        outside = command
    if need_count:
        return bool(DERIVE_COUNT.search(outside))
    return bool(DERIVE_ANY.search(outside))


def evaluate(command, cwd, tpath=""):
    """Return the undischarged claims as [(kind, quote)].

    Split out of `main` so the test suite can exercise it directly, per
    `shared/workflow/algorithmatize-checks.md`'s test-one-clause-at-a-time
    guidance that the sibling hooks in this file already follow.
    """
    if parse_comment_post is None:
        return []
    try:
        parsed = parse_comment_post(command, cwd)
    except Exception:
        return []
    if not parsed:
        return []
    _owner, _repo, _number, body_text = parsed
    if not body_text or not body_text.strip():
        return []

    found = find_claims(body_text)
    if not found:
        return []

    undischarged = []
    for kind, quote in found:
        need_count = kind == "cardinality"
        if _derived_in_body(body_text, need_count):
            continue
        if _derived_in_other_segments(command, body_text, need_count):
            continue
        undischarged.append((kind, quote))
    return undischarged


NOTE = (
    "This forge-comment body asserts a count or an enumerated list, and a "
    "posted comment is where an unverified population survives best -- once "
    "it is on the record, a reader treats it as checked rather than as "
    "recalled from memory.\n\n"
    "Unverified claim(s):\n{claims}\n\n"
    "Either paste the deriving command beside the claim in the comment "
    "body, or run one before posting. A count needs a counting command "
    "(`grep -c`, `wc -l`, `find ... | wc -l`); listing files is enough for "
    "an enumerated list, but not for a count.\n\n"
    "If you already derived these (a command run earlier in this same Bash "
    "call, or already pasted in the body), this is a false positive -- post "
    "anyway."
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        return 0

    cwd = payload.get("cwd") or os.getcwd()

    try:
        tpath = payload.get("transcript_path") or ""
        undischarged = evaluate(command, cwd, tpath)
        if not undischarged:
            return 0

        key = hashlib.sha256(
            (tpath + "|" + command + "|"
             + "|".join(q for _, q in undischarged)).encode()
        ).hexdigest()[:16]
        sentinel = os.path.join(
            tempfile.gettempdir(), f".claude-comment-cardinality-{key}"
        )
        if os.path.exists(sentinel):
            return 0
        try:
            open(sentinel, "w").close()
        except Exception:
            pass

        listed = "\n".join(
            f'  - [{k}] "{q}"' for k, q in undischarged[:3]
        )
        if len(undischarged) > 3:
            listed += f"\n  - ... and {len(undischarged) - 3} more"

        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": NOTE.format(claims=listed),
            },
            "systemMessage": (
                f"Forge comment asserts a count/enumeration ({len(undischarged)} "
                "unverified claim(s)); paste the deriving command or verify "
                "first."
            ),
        }))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
