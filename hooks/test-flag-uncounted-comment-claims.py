"""Tests for flag-uncounted-comment-claims.py.

Reproduces the incident it was named for (`Morrison-Lab/ai-config#2377`):
two `gh pr comment --body-file` posts, each asserting an enumerated file
list recalled from memory rather than derived, one of them wrong. The true-
positive fixture below reuses the incident's own wrong claim, paraphrased:
a "N files" cardinality claim and a hand-typed list of hyphenated script
names under the label "scripts".

Structured like its two siblings this hook reuses machinery from
(`test-remind-brief-premises.py` for the claim-detection unit checks,
`test-flag-uncited-rebuttal.py` for the end-to-end subprocess harness): one
guard clause isolated per case, so a failure names which clause broke rather
than "the hook is wrong somehow".

Run:  python3 hooks/test-flag-uncounted-comment-claims.py hooks/flag-uncounted-comment-claims.py
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

SUBJECT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "flag-uncounted-comment-claims.py")


def load(path):
    spec = importlib.util.spec_from_file_location("subject_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


failures = 0


def check(label, got, want):
    global failures
    if got != want:
        print(f"FAIL: {label}: got {got!r}, want {want!r}")
        failures += 1
    else:
        print(f"PASS: {label}")


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

# The incident, paraphrased: a wrong enumerated list AND a wrong count in
# one comment body, neither backed by a deriving command.
INCIDENT_BODY = (
    "The fingerprinted scripts: cycle-charge-flee / interval-labels / "
    "multi-unit-form-up-modes / group-attack, and 18 files on main."
)

# Ordinary prose this hook must stay silent on: an ARD disposition summary,
# which lists three dispositions with no hyphenated tokens and no
# listable-noun-plus-count claim.
ARD_SUMMARY = "Addressed, Rebutted, or Deferred every finding this round."

# A cardinality claim about a non-listable subject (people/time), which
# LISTABLE_NOUN's curated vocabulary deliberately excludes.
NON_LISTABLE = "This took about three hours across two people."

# Regression fixtures for an adversarial review of this hook (ai-config#2377
# round 1), which found two blocking bugs in the original regexes -- see the
# comments on CARDINALITY_RE and ENUM_RE in the hook itself for the
# mechanism. Both are pinned here so neither regresses silently.

# Bug 1: a count followed by an adjective before the noun ("18 NEW files")
# was invisible, because the noun group had no plural-`s` requirement baked
# into the regex itself, so a lazy gap quantifier never backtracked past the
# adjective to find the real noun.
CARDINALITY_WITH_ADJECTIVE = "There are 18 new files on main."

# Bug 2: routine review-summary phrasing this corpus posts constantly
# ("found 2 issues", "three commits") used to fire, because the curated
# noun vocabulary originally included review-housekeeping words. It must
# not fire post-fix.
ROUTINE_REVIEW_PHRASING = "I found 2 issues while reviewing; three commits fixed them."

# Bug 2's sibling: a two-level corpus path whose own segments are hyphenated
# (`skills/<slug>/SKILL.md`, this repo's own standard citation shape) was
# misread as a listable noun ("skills") followed by a hand-typed two-item
# list. A third variant -- a listable noun that is itself the FIRST
# hyphenated segment of a longer compound identifier (`checks?` matching
# "check" inside `check-open-prs-before-duplicating`) -- reached the same
# false positive by a different route and needed the same fix widened.
PATH_CITATION = "See skills/select-model/SKILL.md for the routing logic."
COMPOUND_IDENTIFIER_PATH = (
    "The rule lives in skills/check-open-prs-before-duplicating/SKILL.md."
)

# The bulleted-list form of the incident's own enumeration claim -- the same
# content ENUM_RE already catches when slash-joined on one line, but as a
# markdown bullet list, which the original regex could not see at all.
BULLETED_LIST = (
    "The fingerprinted scripts:\n"
    "- cycle-charge-flee\n"
    "- interval-labels\n"
    "- multi-unit-form-up-modes\n"
    "- group-attack\n"
)

# Round 2 of the same adversarial review: fixing bug 1 by letting
# CARDINALITY_RE's gap backtrack exposed a second bug -- a WORD-counted gap
# has no sense of a sentence or paragraph boundary, so it happily walked
# through a period or a newline to find a plural noun in a DIFFERENT
# sentence. Both are real review-comment phrasing, not contrived text.
CROSS_SENTENCE_PERIOD = (
    "Reviewed PR 12 on GitHub. Scripts still need work before merge."
)
CROSS_PARAGRAPH_NEWLINE = (
    "Filed as issue 5 in Slack.\nResults are pending review from the team."
)

# ai-config#2386 review round 1 (claude-review, comment 5435096586): the
# path-citation guard on ENUM_RE only protects the position immediately
# after the noun it actually matched. A DIFFERENT listable noun earlier in
# the same sentence ("occurrences") let the gap swallow a whole bare
# directory segment ("skills") plus its trailing slash, resuming the
# token-list match mid-path.
PATH_CITATION_WITH_EARLIER_NOUN = (
    "No occurrences found in skills/select-model/SKILL.md after the fix."
)
# The same shape, reached via the bulleted-list pattern instead of the
# inline one -- an intro line citing a path and ending in a colon, followed
# by unrelated bulleted content.
PATH_CITATION_BEFORE_BULLETS = (
    "No occurrences found in skills/select-model/SKILL.md:\n"
    "- item1\n"
    "- item2\n"
)

# Found while verifying the fix above, in the SAME review repro sentence:
# CARDINALITY_RE's imported COUNT treats "no" as a numeral alongside "zero",
# so "No occurrences" (a negation -- nothing was found, not a specific
# derived count) still read as a cardinality claim after the enumeration
# half was fixed. "zero" stays a real count; "no" does not.
NEGATION_WITH_LISTABLE_NOUN = "There are no dead branches."
ZERO_IS_KEPT = "There are zero files remaining."

# ai-config#2386 review round 2 (claude-review, comment 5435218793): a THIRD
# route to the same path-citation false-positive class, needing neither of
# the first two tricks. A two-segment path whose directory AND filename are
# BOTH independently hyphen/dot-shaped satisfies ENUM_RE's own two-token
# list clause directly -- no gap-crossing needed, fires with the noun
# immediately adjacent. Both paths are real citations in this corpus
# (`ai-config/claude-hook-adapter.py` is cited in AGENTS.md).
PATH_BOTH_SEGMENTS_HYPHENATED_1 = (
    "No hits found in local-bin/encrypt-gh-token.sh after the sweep."
)
PATH_BOTH_SEGMENTS_HYPHENATED_2 = (
    "See files ai-config/claude-hook-adapter.py for the mapping."
)
PATH_BOTH_SEGMENTS_HYPHENATED_3 = (
    "Several references still point to ai-config/claude-hook-adapter.py "
    "directly."
)

# The true-positive counter-case the fix must NOT break: a genuine two-item
# `/`-joined enumeration whose second item does not end in a file
# extension. `looks_like_one_path` only rejects the (exactly-two-items,
# `/`-only, extension-terminated) shape, so this must still fire.
TWO_ITEM_SLASH_LIST_NOT_A_PATH = (
    "The fingerprinted scripts: brace-vs-unbraced-charge / "
    "defensive-doctrine-plan, and 18 files on main."
)
# A comma-joined two-item list is never rejected regardless of extension,
# since `,` is a list signal at any length -- confirms the rejection is
# keyed on the separator, not merely the item count.
TWO_ITEM_COMMA_LIST = (
    "The fingerprinted scripts: cycle-charge-flee, interval-labels, "
    "and 18 files on main."
)

# ai-config#2386 review round 4 (claude-review, comment 5435303313): a
# FOURTH route into the path-citation class. `looks_like_one_path`'s round-3
# fix only recognized EXACTLY two items; `ENUM_RE`'s own token-list clause
# places no cap on item count, so a real three-or-more-segment hyphenated
# path sailed past a `len(items) == 2` check untouched.
PATH_THREE_SEGMENTS_HYPHENATED = (
    "No matches in codex-skills/pre-push-review/SKILL.md were found."
)
PATH_MANY_SEGMENTS_HYPHENATED = (
    "See references in tracking-your-work-with-issues/using-issues/"
    "linking-a-pull-request-to-an-issue.md for details."
)

# ai-config#2386 review round 5: an adversarial sweep -- deriving 780+ real
# path-like strings from this repo's own shared/**/*.md + skills/**/*.md,
# embedded in review-comment-style sentences -- found 140 residual
# enumeration false positives across five categories the round-4 fix did
# not reach: a curated extension whitelist missing real extensions
# (`.io`, `.jpg`, `.gz`, `.paper`), bare trailing-slash directory
# references, and (the largest single cause, once the first two were
# fixed) a domain-plus-path citation whose FIRST segment ends in a
# TLD-shaped suffix that satisfied the "no earlier item may be
# extension-shaped" refinement's OWN extension check, defeating it.
PATH_UNCOMMON_EXTENSION = (
    "No matches in d-morrison/methods.paper were found."
)
PATH_TRAILING_SLASH_DIRECTORY = (
    "No matches in codex-skills/pre-push-review/ were found."
)
PATH_DOMAIN_SHAPED = (
    "No matches in adv-r.hadley.nz/conditions.html were found."
)
# The DELIBERATELY ACCEPTED cost of closing the domain-shaped case: dropping
# the "no earlier item may be extension-shaped" refinement means a genuine
# multi-file list joined by `/` with no comma is now ALSO silenced. This is
# no longer a true-positive fixture -- it PINS the accepted miss, so a
# future edit that reintroduces the refinement (and reopens the domain-
# citation false positive) has to consciously change this assertion too.
ACCEPTED_MISS_SLASH_ONLY_MULTI_FILE_LIST = (
    "See files foo.py / bar.py / baz.py in this update."
)

# ai-config#2386 review round 5 (claude-review, comment 5435642539): a
# FIFTH route -- TWO SEPARATE path citations joined by a comma, each
# independently hyphen/dot-shaped and each containing its own `/`. Every
# fix for routes 3-4 keyed on "every separator in the whole span is `/`",
# which is correct for one path split into segments and wrong the moment
# two citations are cited together with an ordinary comma. Both paths are
# the exact citations already used in `PATH_BOTH_SEGMENTS_HYPHENATED_1`/`_2`
# above, cited together instead of singly.
PATH_PAIR_COMMA_JOINED = (
    "See files ai-config/claude-hook-adapter.py, "
    "local-bin/encrypt-gh-token.sh for the mapping."
)
PATH_PAIR_COMMA_JOINED_2 = (
    "No hits in ai-config/claude-hook-adapter.py, "
    "local-bin/encrypt-gh-token.sh after the sweep."
)
# A distinct comma-pair, deliberately not identical to either literal
# review repro above, so this pins the MECHANISM (any two path citations
# joined by a comma) rather than only the two specific strings a reviewer
# happened to type.
PATH_PAIR_COMMA_JOINED_3 = (
    "See references in codex-skills/pre-push-review/SKILL.md, "
    "shared/workflow/ardi.md for the routing logic."
)

# ai-config#2386 review round 5's design decision (see the "PATH-CITATION
# FALSE-POSITIVE CLASS" doc comment above ENUM_RE): rather than patch route
# 5 the same narrow way as routes 3-4, `looks_like_one_path` was rewritten
# to classify the captured list per ITEM -- split on `,` first, then ask
# whether every resulting piece independently looks like one path citation
# (an internal `/`, extension-terminated or trailing-`/`). That closes
# routes 3-5 in one rule, but ALSO means a genuine hand-typed enumeration
# of several FULL paths (directory and extension both present) is no
# longer detected as an enumeration claim at all, comma-joined or not. This
# is accepted, not incidental: the guard's actual purpose is a
# RECALLED-NOT-DERIVED population claim, and such a claim about files
# essentially always carries an explicit count nearby ("the 3 affected
# files ..."), which CARDINALITY_RE still catches unaffected by any of
# this. The incident this hook exists for was never this shape either --
# its wrong claim named bare script IDENTIFIERS, not full paths with
# directories and extensions.
ACCEPTED_MISS_GENUINE_ALL_PATHS_COMMA_LIST = (
    "The affected files: scripts/alpha.py, scripts/beta.py, "
    "scripts/gamma.py."
)
# The mirror true positive the class boundary is drawn to PRESERVE: a
# comma-joined list of BARE filenames with no directory component (no
# internal `/` in any item) is never a citation under the item-level test,
# so it still fires -- unlike a `/`-joined bare-file list, which stays an
# accepted miss (see ACCEPTED_MISS_SLASH_ONLY_MULTI_FILE_LIST above; that
# fixture's own separator, not its extensions, is what keeps it silent).
BARE_FILENAMES_COMMA_JOINED = "See files foo.py, bar.py in this update."

# ai-config#2386 review round 6 (claude-review, comment 5435782017): the
# FIRST false negative in this class -- every route above is an over-broad
# match; this is a match that stops too soon. TOKEN cannot end on a bare
# trailing `/`, so a directory citation BEFORE a comma mid-enumeration
# truncated the match before the comma, dropping every recalled identifier
# after it. This is the founding incident's own composite shape: one
# genuine citation prefixed to a recalled list. All three orderings
# (citation first/middle/last) are pinned, for both citation flavors
# (trailing-slash directory and extension-terminated file).
MIXED_LIST_CITATION_FIRST_TRAILING_SLASH = (
    "The fingerprinted scripts: codex-skills/pre-push-review/, "
    "cycle-charge-flee, interval-labels."
)
MIXED_LIST_CITATION_MIDDLE_TRAILING_SLASH = (
    "The fingerprinted scripts: cycle-charge-flee, "
    "codex-skills/pre-push-review/, interval-labels."
)
MIXED_LIST_CITATION_LAST_TRAILING_SLASH = (
    "The fingerprinted scripts: cycle-charge-flee, interval-labels, "
    "codex-skills/pre-push-review/."
)
MIXED_LIST_CITATION_FIRST_EXTENSION = (
    "The fingerprinted scripts: local-bin/encrypt-gh-token.sh, "
    "cycle-charge-flee, group-attack."
)
MIXED_LIST_CITATION_MIDDLE_EXTENSION = (
    "The fingerprinted scripts: cycle-charge-flee, "
    "local-bin/encrypt-gh-token.sh, group-attack."
)
MIXED_LIST_CITATION_LAST_EXTENSION = (
    "The fingerprinted scripts: cycle-charge-flee, group-attack, "
    "local-bin/encrypt-gh-token.sh."
)
# All-citations lists in the same orderings must stay silent -- the
# mixed-list fix must not reopen route 5 (a list of ONLY citations).
ALL_CITATIONS_ORDER_TRAILING_SLASH_FIRST = (
    "No hits in codex-skills/pre-push-review/, "
    "ai-config/claude-hook-adapter.py, "
    "local-bin/encrypt-gh-token.sh after the sweep."
)
ALL_CITATIONS_ORDER_TRAILING_SLASH_MIDDLE = (
    "No hits in ai-config/claude-hook-adapter.py, "
    "codex-skills/pre-push-review/, "
    "local-bin/encrypt-gh-token.sh after the sweep."
)
ALL_CITATIONS_ORDER_TRAILING_SLASH_LAST = (
    "No hits in ai-config/claude-hook-adapter.py, "
    "local-bin/encrypt-gh-token.sh, "
    "codex-skills/pre-push-review/ after the sweep."
)

# The adjacent false positive found while verifying route 6 with an
# adversarial derivation: a real citation whose own middle segment is a
# bare (non-hyphenated) word ("memories") truncates the match early, the
# same shape as route 6 but for a DIFFERENT, pre-existing reason (TOKEN
# requires every path segment to itself be hyphen/underscore/dot-shaped --
# tracked separately as ai-config#2404). The truncated fragment
# ("ai-config") was being read as a bare identifier rather than as the cut-
# short start of a second citation.
TRUNCATED_CITATION_FRAGMENT = (
    "No matches in UCD-SERG/ucd-serg.github.io, "
    "ai-config/memories/tools.md were found."
)

# ai-config#2386 review round 7 (claude-review, comment 5436013319): a
# coincidental slash sitting next to a bare recalled identifier (a date, a
# branch name) was being read, via round 6's single-character
# `trailing_char` check, as proof that identifier was itself a citation --
# silencing a genuine mixed list (real citation + bare recalled identifier)
# in exactly the founding incident's own composite shape. Both repro
# sentences from the review, plus the citation in first vs. last position
# relative to the coincidental-slash item -- ordering the way round 6/7's
# other fixtures do, by where the CITATION sits, since (see below) where
# the coincidental item itself sits is what actually still matters here.
COINCIDENTAL_SLASH_DIGIT_SUFFIX = (
    "No hits in local-bin/encrypt-gh-token.sh, "
    "cycle-charge-flee/2026 planned."
)
COINCIDENTAL_SLASH_BRANCH_SUFFIX = (
    "No hits in local-bin/encrypt-gh-token.sh, "
    "cycle-charge-flee/main was checked."
)
COINCIDENTAL_SLASH_CITATION_FIRST = (
    "The fingerprinted scripts: local-bin/encrypt-gh-token.sh, "
    "cycle-charge-flee/2026, interval-labels."
)

# ACCEPTED RESIDUAL, found while verifying round 7's fix in "all orderings"
# and tracked as an addendum to ai-config#2404: when the coincidental-slash
# item is the VERY FIRST item in the list (immediately after the
# introducing noun), the token-list clause's own separator
# (`\s*/?(?:,|/)\s*`) cannot skip past the non-token content between the
# stray `/` and the real `,` to reach the rest of the list at all --
# `ENUM_RE` fails to match ANYWHERE in the sentence, not merely
# misclassifies. This is a DIFFERENT mechanism than round 7's own finding
# (mid-match separator parsing, not post-match `continuation`
# classification), shares ai-config#2404's root cause (content adjacent to
# a `/` that `TOKEN` cannot parse), and is out of scope for the same
# reason: a real fix needs the same broader `TOKEN`-parsing redesign that
# issue already tracks. Pinned here as an ACCEPTED miss, not silently
# left untested, so a future editor sees it was found and weighed rather
# than missed.
ACCEPTED_MISS_COINCIDENTAL_SLASH_ITEM_FIRST = (
    "The fingerprinted scripts: cycle-charge-flee/2026, "
    "local-bin/encrypt-gh-token.sh, interval-labels."
)

# ai-config#2386 review round 8 (claude-review, comment 5436238489): these
# two sentences were ORIGINALLY pinned and named as "version suffix defeats
# PATH_EXTENSION_RE via looks_like_path_continuation()". Round 10 (comment
# 5436484201) demonstrated that diagnosis was WRONG for these two specific
# sentences: `local-bin/encrypt-gh-token.sh` already satisfies `ENUM_RE`'s
# own `{1,}` minimum on its own two hyphenated segments, so the match ends
# at the following comma and `feature/v2.1` is never even reached --
# `dangling_continuation()` returns `""` (confirmed: the character right
# after the match is `,`, not `/`), so `looks_like_path_continuation()` and
# `PATH_EXTENSION_RE` are NEVER INVOKED for these fixtures. The real cause
# is `TOKEN` truncation at the plain word "feature" (no internal hyphen/
# underscore/dot of its own), the SAME `ai-config#2404` family as
# `ACCEPTED_MISS_COINCIDENTAL_SLASH_ITEM_FIRST` above -- confirmed by
# reproducing the identical silence with the version-suffix removed
# entirely (`"...encrypt-gh-token.sh, feature was tested."` -> also `[]`).
# Renamed from `ACCEPTED_MISS_VERSION_SUFFIX_*` to name the TRUE mechanism,
# so a future reader (and a future implementer of ai-config#2404's
# "letter-required extension" remedy) is not misdirected: that remedy
# would NOT close either of these two fixtures, since the extension check
# it would narrow is never reached for them.
ACCEPTED_MISS_BARE_WORD_TRUNCATION_TWO_ITEM = (
    "No hits in local-bin/encrypt-gh-token.sh, feature/v2.1 was tested."
)
ACCEPTED_MISS_BARE_WORD_TRUNCATION_THREE_ITEM = (
    "The fingerprinted scripts: local-bin/encrypt-gh-token.sh, "
    "feature/v2.1, interval-labels."
)

# The GENUINE extension-vs-version-tail confusion DOES exist -- just not in
# the two fixtures above. Reached when the coincidental item's OWN leading
# segment ("cycle-charge-flee") is itself TOKEN-shaped (unlike "feature"),
# so `ENUM_RE`'s main match captures the whole `cycle-charge-flee/v2.1` as
# two internally-joined tokens directly (no `dangling_continuation` needed
# at all) -- and `v2.1` genuinely satisfies `PATH_EXTENSION_RE` the way a
# real extension would. This is what the letter-required-extension remedy
# tracked under ai-config#2404 would actually need to close. A third,
# unrelated bare item unmasks it again (`looks_like_one_path`'s `all()`),
# the same way route 9's trailing-slash-suffix residual is masked by a
# third item -- so only the 2-item form is pinned as an accepted miss here.
ACCEPTED_MISS_GENUINE_EXTENSION_VS_VERSION_TWO_ITEM = (
    "No hits in local-bin/encrypt-gh-token.sh, "
    "cycle-charge-flee/v2.1 was tested."
)

# ai-config#2386 review round 9 (claude-review, comment 5436345773): the
# THIRD variant of the same continuation-classification gap, this time in
# `looks_like_path_continuation()`'s OTHER branch --
# `continuation.endswith("/")` -- which routes 7-8 never exercised. Appending
# one bare `/` to round 7's own already-fixed `cycle-charge-flee/main`
# fixture reopens the identical silencing. Scoped to exactly the 2-item
# case, same as routes 6-8: with a third bare item elsewhere in the list,
# the claim still fires (pinned below as a positive confirmation, not an
# accepted miss), since that third item independently fails the citation
# test regardless of what happens to the coincidental one.
ACCEPTED_MISS_TRAILING_SLASH_SUFFIX_TWO_ITEM = (
    "No hits in local-bin/encrypt-gh-token.sh, "
    "cycle-charge-flee/main/ was checked."
)
ACCEPTED_MISS_TRAILING_SLASH_SUFFIX_VERSION = (
    "No hits in local-bin/encrypt-gh-token.sh, "
    "cycle-charge-flee/v2/ was tested."
)
# The 3-item case is NOT an accepted miss -- a third bare identifier in the
# list still makes the claim fire, since `looks_like_one_path`'s `all()`
# fails on that item regardless of the coincidental one's own
# misclassification. Pinned as a positive regression, matching the
# reviewer's own verification.
TRAILING_SLASH_SUFFIX_THREE_ITEM_STILL_FIRES = (
    "The fingerprinted scripts: local-bin/encrypt-gh-token.sh, "
    "interval-labels, cycle-charge-flee/v2/ was checked."
)

# ai-config#2386 review round 10 (claude-review, comment 5436484201): a
# genuinely NEW false-positive gap, OUTSIDE the pre-dispositioned
# coincidental-slash-continuation class (round 9's standing statement) --
# this is a code path that performed no citation classification at all,
# not a member of the classified-but-imperfect family that block covers.
# The bulleted-list enumeration loop never called `looks_like_one_path`,
# so a bulleted list of genuine path citations -- the exact shape routes
# 1-5 spent five rounds closing for the inline form -- fired unfiltered.
# Both citations are the exact strings this file's own inline fixtures
# (`PATH_BOTH_SEGMENTS_HYPHENATED_1`/`_2`) already use as real content.
BULLETED_ALL_CITATIONS_MUST_NOT_FIRE = (
    "The fingerprinted scripts:\n"
    "- ai-config/claude-hook-adapter.py\n"
    "- local-bin/encrypt-gh-token.sh\n"
)
# A bulleted list mixing citations with recalled bare identifiers -- the
# composite shape the inline mixed-list fixtures (rounds 6-7) already
# cover -- must still fire, mirroring the inline `all()` semantics.
BULLETED_MIXED_CITATION_AND_IDENTIFIERS = (
    "The fingerprinted scripts:\n"
    "- ai-config/claude-hook-adapter.py\n"
    "- cycle-charge-flee\n"
    "- interval-labels\n"
)
# A bulleted list of a trailing-slash directory citation plus an
# extension-terminated one -- both citation FLAVORS this file's inline
# fixtures already cover, now exercised via the bullet path.
BULLETED_ALL_CITATIONS_TRAILING_SLASH_AND_EXTENSION = (
    "The fingerprinted scripts:\n"
    "- codex-skills/pre-push-review/\n"
    "- local-bin/encrypt-gh-token.sh\n"
)

# ACCEPTED RESIDUAL, found by the round-10 two-sided derivation sweep
# (ai-config#2386 comment 5436484201's own instruction to re-run it against
# bulleted forms) -- not requested by either of round 10's two findings, and
# confirmed NOT a regression from round 10's fix: reproduces identically
# against the pre-round-10 hook (`git show HEAD:hooks/...` before this PR's
# round-10 commit). Same root cause as `ACCEPTED_MISS_BARE_WORD_TRUNCATION_*`
# above -- `TOKEN` requires an internal separator, so "tests" in
# "tests/testthat.R" cannot match it -- but a DIFFERENT failure shape:
# `BULLET_TOKEN_RE` is anchored to a bullet's line start, so when the
# leading segment of a multi-segment path fails `TOKEN`, the WHOLE line
# fails to match (not a partial capture the way the inline route's
# mid-string truncation works), and the item is dropped from the token
# count entirely rather than misclassified. In a 2-item bulleted list this
# collapses the token count to 1 (the single bare identifier), which is
# below `find_claims`'s `len(tokens) < 2` floor, so the whole claim goes
# unrecognized. Scoped to exactly 2 items: at 3+ the remaining items supply
# enough tokens on their own regardless of this one's loss (swept and
# confirmed: 0 failures at n=3,4,5 against 30 sampled orderings each).
# Tracked as part of ai-config#2404, the same TOKEN-separator-requirement
# family as the fixtures above, rather than opened as a new issue.
BULLETED_ACCEPTED_MISS_BARE_WORD_LEADING_SEGMENT_TWO_ITEM = (
    "The fingerprinted scripts:\n"
    "- tests/testthat.R\n"
    "- warn-pr-create\n"
)


def body_file_with(text):
    fh = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                     encoding="utf-8")
    fh.write(text)
    fh.close()
    return fh.name


def run_hook(command, cwd=None, tpath=""):
    """Run the hook end-to-end over an arbitrary Bash command; return stdout.

    Gives the subprocess a FRESH `TMPDIR` per call, per
    `test-remind-brief-premises.py`'s own runner: the hook's fire-once
    sentinel lives in `tempfile.gettempdir()`, keyed by a hash of the
    command and its claims, and this suite calls the hook many times with
    overlapping (command, claim) pairs (the same incident text posted via
    `--body-file` and then again via inline `--body`, for instance). Without
    isolation a sentinel written by one case silently suppresses a LATER
    case in the same test run -- and, worse, silently suppresses a case in a
    SEPARATE run of this file minutes later, since the real `/tmp` sentinel
    outlives the process. Python's `tempfile.gettempdir()` checks `TMPDIR`
    first on every platform this suite runs on, so this is enough.
    """
    tmpdir = tempfile.mkdtemp()
    try:
        payload = {"tool_name": "Bash", "tool_input": {"command": command},
                   "cwd": cwd or os.getcwd(), "transcript_path": tpath}
        proc = subprocess.run([sys.executable, SUBJECT], input=json.dumps(payload),
                              capture_output=True, text=True,
                              env=dict(os.environ, TMPDIR=tmpdir))
        return proc.stdout.strip()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# --------------------------------------------------------------------------
# Unit-level checks on the pure functions
# --------------------------------------------------------------------------

def unit_checks(mod):
    # find_claims: the incident text yields both claim shapes.
    claims = mod.find_claims(INCIDENT_BODY)
    kinds = sorted(k for k, _ in claims)
    check("find_claims on the incident text finds both claim kinds",
          kinds, ["cardinality", "enumeration"])
    check("find_claims cardinality quote names the count",
          any(q == "18 files" for k, q in claims if k == "cardinality"), True)
    check("find_claims enumeration quote carries the hyphenated list",
          any("cycle-charge-flee" in q for k, q in claims if k == "enumeration"),
          True)

    # False positive guards: an ordinary ARD summary and a non-listable
    # cardinality claim must both find nothing.
    check("find_claims silent on an ARD disposition summary",
          mod.find_claims(ARD_SUMMARY), [])
    check("find_claims silent on a non-listable cardinality claim",
          mod.find_claims(NON_LISTABLE), [])

    # A plain content claim ("CLAUDE.md carries...") with no count and no
    # hyphenated list is not this hook's concern either.
    check("find_claims silent on a bare content assertion",
          mod.find_claims("CLAUDE.md carries the units convention."), [])

    # Regression: bug 1 (adjective between count and noun).
    claims = mod.find_claims(CARDINALITY_WITH_ADJECTIVE)
    check("find_claims catches a count with an adjective before the noun",
          claims, [("cardinality", "18 new files")])

    # Regression: bug 2 (routine review-summary phrasing must stay silent).
    check("find_claims silent on routine 'found N issues'/'N commits' phrasing",
          mod.find_claims(ROUTINE_REVIEW_PHRASING), [])

    # Regression: bug 2's path-citation variant, both shapes.
    check("find_claims silent on a skills/<slug>/SKILL.md path citation",
          mod.find_claims(PATH_CITATION), [])
    check("find_claims silent on a noun-prefixed compound-identifier path",
          mod.find_claims(COMPOUND_IDENTIFIER_PATH), [])

    # New coverage: a bulleted-list enumeration (finding 4).
    claims = mod.find_claims(BULLETED_LIST)
    check("find_claims catches a bulleted-list enumeration",
          any(k == "enumeration" and "cycle-charge-flee" in q
              for k, q in claims),
          True)

    # Regression: round 2 of the same review -- fixing bug 1's backtracking
    # exposed a gap with no sentence/paragraph boundary. Must stay silent.
    check("find_claims silent on a count and noun split by a sentence period",
          mod.find_claims(CROSS_SENTENCE_PERIOD), [])
    check("find_claims silent on a count and noun split by a paragraph break",
          mod.find_claims(CROSS_PARAGRAPH_NEWLINE), [])

    # Regression: PR #2386 review round 1 -- ENUM_RE's noun-adjacent guard
    # did not stop a DIFFERENT listable noun earlier in the sentence from
    # swallowing a bare directory segment plus its slash into the gap.
    check("find_claims silent when an earlier noun's gap swallows a path",
          mod.find_claims(PATH_CITATION_WITH_EARLIER_NOUN), [])
    check("find_claims silent on the same shape before a bulleted list",
          mod.find_claims(PATH_CITATION_BEFORE_BULLETS), [])

    # Regression: found while verifying the fix above, in the same repro
    # sentence -- CARDINALITY_RE's COUNT treated "no" as a numeral, so a
    # negation ("no dead branches") read as a cardinality claim. "zero"
    # stays a real, checkable count.
    check("find_claims silent on a negation with a listable noun",
          mod.find_claims(NEGATION_WITH_LISTABLE_NOUN), [])
    check("find_claims still catches an explicit 'zero' cardinality claim",
          mod.find_claims(ZERO_IS_KEPT), [("cardinality", "zero files")])

    # Regression: PR #2386 review round 2 -- a THIRD route to the path-
    # citation class. A two-segment path whose directory AND filename are
    # both independently hyphen/dot-shaped satisfies ENUM_RE's own two-token
    # clause directly, with no gap-crossing trick and the noun adjacent.
    check("find_claims silent on a hyphenated-directory/hyphenated-file path (1)",
          mod.find_claims(PATH_BOTH_SEGMENTS_HYPHENATED_1), [])
    check("find_claims silent on a hyphenated-directory/hyphenated-file path (2)",
          mod.find_claims(PATH_BOTH_SEGMENTS_HYPHENATED_2), [])
    check("find_claims silent on a hyphenated-directory/hyphenated-file path (3)",
          mod.find_claims(PATH_BOTH_SEGMENTS_HYPHENATED_3), [])

    # True-positive counter-cases the round-2 fix must NOT break: a genuine
    # two-item enumeration, slash- or comma-joined, whose second item is not
    # itself filename-shaped.
    claims = mod.find_claims(TWO_ITEM_SLASH_LIST_NOT_A_PATH)
    check("find_claims still catches a genuine 2-item slash list (not a path)",
          any(k == "enumeration" and "brace-vs-unbraced-charge" in q
              for k, q in claims),
          True)
    claims = mod.find_claims(TWO_ITEM_COMMA_LIST)
    check("find_claims still catches a genuine 2-item comma list",
          any(k == "enumeration" and "cycle-charge-flee" in q
              for k, q in claims),
          True)

    # looks_like_one_path unit checks: the classifier itself, isolated from
    # the surrounding regex.
    check("looks_like_one_path rejects a 2-item slash pair ending in an extension",
          mod.looks_like_one_path("local-bin/encrypt-gh-token.sh"), True)
    check("looks_like_one_path keeps a 2-item slash pair with no extension",
          mod.looks_like_one_path("brace-vs-unbraced-charge/defensive-doctrine-plan"),
          False)
    check("looks_like_one_path keeps a comma-joined pair even with an extension",
          mod.looks_like_one_path("foo.py, bar.py"), False)
    # Round 4 generalized past exactly-two-items: a 3+-item slash list
    # extension-terminated at the end IS now rejected as one path -- this
    # assertion is the inverse of round 3's own (now superseded) fixture,
    # which pinned the pre-generalization "3+ items always keeps firing"
    # behaviour the review found too narrow.
    check("looks_like_one_path rejects a 3+-item slash list, extension-terminated",
          mod.looks_like_one_path("a-b/c-d/e-f.py"), True)
    check("looks_like_one_path keeps a 3+-item slash list with no extension",
          mod.looks_like_one_path("a-b/c-d/e-f"), False)
    # Review round 5 (comment 5435642539) design decision: comma-joined
    # PATH citations (each piece independently `/`-shaped and extension-
    # terminated) are now rejected regardless of how many there are.
    check("looks_like_one_path rejects a comma-joined pair of path citations",
          mod.looks_like_one_path(
              "ai-config/claude-hook-adapter.py, local-bin/encrypt-gh-token.sh"),
          True)
    check("looks_like_one_path rejects a comma-joined TRIPLE of path citations",
          mod.looks_like_one_path(
              "scripts/alpha.py, scripts/beta.py, scripts/gamma.py"),
          True)
    # The mirror: a comma-joined pair where only ONE piece is path-shaped
    # must still fire -- `all()` over the pieces is load-bearing, not `any()`.
    check("looks_like_one_path keeps a mixed pair (one path, one bare identifier)",
          mod.looks_like_one_path(
              "ai-config/claude-hook-adapter.py, interval-labels"),
          False)

    # Regression: PR #2386 review round 4 -- the length-generalized fix.
    check("find_claims silent on a 3-segment hyphenated path",
          mod.find_claims(PATH_THREE_SEGMENTS_HYPHENATED), [])
    check("find_claims silent on a many-segment hyphenated path",
          mod.find_claims(PATH_MANY_SEGMENTS_HYPHENATED), [])

    # Regression: PR #2386 review round 5 -- the adversarial-sweep fixes.
    check("find_claims silent on an uncommon-extension path citation",
          mod.find_claims(PATH_UNCOMMON_EXTENSION), [])
    check("find_claims silent on a bare trailing-slash directory reference",
          mod.find_claims(PATH_TRAILING_SLASH_DIRECTORY), [])
    check("find_claims silent on a domain-plus-path citation",
          mod.find_claims(PATH_DOMAIN_SHAPED), [])
    # The pinned accepted miss (see the fixture's own comment): dropping the
    # "no earlier item extension-shaped" refinement silences this too. A
    # future change that touches looks_like_one_path should see this flip
    # rather than silently regaining (and losing) coverage either way.
    check("find_claims ACCEPTS missing a slash-only multi-file list (documented)",
          mod.find_claims(ACCEPTED_MISS_SLASH_ONLY_MULTI_FILE_LIST), [])

    # Regression: review round 5 (comment 5435642539) -- the design-decision
    # fix. A comma-joined pair (or triple) of independent path citations
    # must stay silent, whichever literal strings are used.
    check("find_claims silent on a comma-joined path pair (repro 1)",
          mod.find_claims(PATH_PAIR_COMMA_JOINED), [])
    check("find_claims silent on a comma-joined path pair (repro 2)",
          mod.find_claims(PATH_PAIR_COMMA_JOINED_2), [])
    check("find_claims silent on a comma-joined path pair (distinct mechanism check)",
          mod.find_claims(PATH_PAIR_COMMA_JOINED_3), [])
    # The pinned NEW accepted miss the design decision trades away: a
    # genuine comma-joined enumeration of several FULL paths (directory and
    # extension both present, no count attached) is no longer flagged as an
    # enumeration claim. See the fixture's own comment for the rationale.
    check("find_claims ACCEPTS missing a genuine all-paths comma list (documented)",
          mod.find_claims(ACCEPTED_MISS_GENUINE_ALL_PATHS_COMMA_LIST), [])
    # The mirror true positive the boundary is drawn to preserve: bare
    # filenames (no directory, so no internal `/`) joined by a comma are
    # never citations under the item-level test, so this still fires.
    claims = mod.find_claims(BARE_FILENAMES_COMMA_JOINED)
    check("find_claims still catches a comma-joined list of bare filenames",
          any(k == "enumeration" and "foo.py" in q for k, q in claims),
          True)

    # Regression: review round 6 (comment 5435782017) -- the false-negative
    # fix. A mixed list (one citation, several recalled identifiers) must
    # fire in EVERY ordering, for both citation flavors.
    for label, fixture in [
        ("trailing-slash, citation FIRST", MIXED_LIST_CITATION_FIRST_TRAILING_SLASH),
        ("trailing-slash, citation MIDDLE", MIXED_LIST_CITATION_MIDDLE_TRAILING_SLASH),
        ("trailing-slash, citation LAST", MIXED_LIST_CITATION_LAST_TRAILING_SLASH),
        ("extension-terminated, citation FIRST", MIXED_LIST_CITATION_FIRST_EXTENSION),
        ("extension-terminated, citation MIDDLE", MIXED_LIST_CITATION_MIDDLE_EXTENSION),
        ("extension-terminated, citation LAST", MIXED_LIST_CITATION_LAST_EXTENSION),
    ]:
        claims = mod.find_claims(fixture)
        enum_claims = [c for c in claims if c[0] == "enumeration"]
        check(f"find_claims catches a mixed list ({label})",
              bool(enum_claims), True)

    # All-citations lists in the same orderings must stay silent -- the
    # false-negative fix must not reopen route 5.
    for label, fixture in [
        ("trailing-slash FIRST", ALL_CITATIONS_ORDER_TRAILING_SLASH_FIRST),
        ("trailing-slash MIDDLE", ALL_CITATIONS_ORDER_TRAILING_SLASH_MIDDLE),
        ("trailing-slash LAST", ALL_CITATIONS_ORDER_TRAILING_SLASH_LAST),
    ]:
        claims = mod.find_claims(fixture)
        enum_claims = [c for c in claims if c[0] == "enumeration"]
        check(f"find_claims stays silent on an all-citations list ({label})",
              enum_claims, [])

    # Regression: the adjacent false positive found while verifying round 6
    # -- a truncated citation fragment (from the separate, pre-existing
    # bare-segment limitation, ai-config#2404) must not be misread as a
    # bare identifier.
    check("find_claims silent on a truncated-citation-fragment pair",
          mod.find_claims(TRUNCATED_CITATION_FRAGMENT), [])
    check("looks_like_citation recognizes a bare fragment via a bare '/' continuation",
          mod.looks_like_citation("ai-config", continuation="/"), True)
    check("looks_like_citation still requires internal '/' with no continuation",
          mod.looks_like_citation("ai-config", continuation=""), False)
    # Regression: PR #2386 review round 7 -- the refined continuation check.
    # A coincidental slash (a date, a branch name) must NOT promote a bare
    # identifier to citation status, even though it has the exact same
    # single-character shape as the truncated-fragment case above.
    check("looks_like_citation rejects a coincidental digit-led continuation",
          mod.looks_like_citation("cycle-charge-flee", continuation="/2026"), False)
    check("looks_like_citation rejects a coincidental bare-word continuation",
          mod.looks_like_citation("cycle-charge-flee", continuation="/main"), False)
    check("looks_like_citation still accepts a genuine multi-hop continuation",
          mod.looks_like_citation("ai-config", continuation="/memories/tools.md"), True)

    # Regression: review round 7 (comment 5436013319) -- the refined
    # continuation fix. The reviewer's own two repro sentences, plus the
    # citation-first ordering, must fire; the coincidental-slash-item-first
    # ordering is a pinned, documented, accepted miss (see the fixture's
    # own comment -- a different mechanism than this round's fix, tracked
    # as an addendum to ai-config#2404).
    for label, fixture in [
        ("digit suffix, citation first", COINCIDENTAL_SLASH_DIGIT_SUFFIX),
        ("branch suffix, citation first", COINCIDENTAL_SLASH_BRANCH_SUFFIX),
        ("citation first, coincidental item middle", COINCIDENTAL_SLASH_CITATION_FIRST),
    ]:
        claims = mod.find_claims(fixture)
        enum_claims = [c for c in claims if c[0] == "enumeration"]
        check(f"find_claims catches a mixed list with a coincidental slash ({label})",
              bool(enum_claims), True)
    check("find_claims ACCEPTS missing a list starting with the coincidental-slash item",
          mod.find_claims(ACCEPTED_MISS_COINCIDENTAL_SLASH_ITEM_FIRST), [])

    # Regression: review round 8 (comment 5436238489), RENAMED in round 10
    # (comment 5436484201) once the true mechanism was demonstrated (TOKEN
    # truncation at the bare word "feature", not an extension-check
    # confusion). Both of the reviewer's own repro sentences, pinned as
    # deliberate, tested accepted misses.
    check("find_claims ACCEPTS missing a 2-item list truncated at a bare word",
          mod.find_claims(ACCEPTED_MISS_BARE_WORD_TRUNCATION_TWO_ITEM), [])
    check("find_claims ACCEPTS missing a 3-item list truncated at a bare word",
          mod.find_claims(ACCEPTED_MISS_BARE_WORD_TRUNCATION_THREE_ITEM), [])
    # The genuine extension-vs-version-tail confusion, confirmed reachable
    # via a different repro shape (see the fixture's own comment) -- this
    # is what ai-config#2404's letter-required-extension remedy would
    # actually need to close, unlike the two fixtures directly above.
    check("find_claims ACCEPTS missing a 2-item list via a genuine version-tail extension match",
          mod.find_claims(ACCEPTED_MISS_GENUINE_EXTENSION_VS_VERSION_TWO_ITEM), [])

    # Regression: review round 9 (comment 5436345773) -- the third variant,
    # in looks_like_path_continuation()'s bare-trailing-slash branch. Both
    # of the reviewer's own repro sentences, pinned as deliberate, tested
    # accepted misses; the 3-item case is pinned as a POSITIVE regression
    # (it still fires), matching the reviewer's own verification.
    check("find_claims ACCEPTS missing a 2-item list with a trailing-slash-suffix citation",
          mod.find_claims(ACCEPTED_MISS_TRAILING_SLASH_SUFFIX_TWO_ITEM), [])
    check("find_claims ACCEPTS missing a 2-item list with a version+trailing-slash citation",
          mod.find_claims(ACCEPTED_MISS_TRAILING_SLASH_SUFFIX_VERSION), [])
    claims = mod.find_claims(TRAILING_SLASH_SUFFIX_THREE_ITEM_STILL_FIRES)
    enum_claims = [c for c in claims if c[0] == "enumeration"]
    check("find_claims still catches the 3-item trailing-slash-suffix case (masked, not fixed)",
          bool(enum_claims), True)

    # Regression: review round 10 (comment 5436484201) -- a genuinely new,
    # out-of-class false positive: the bulleted-list loop never filtered
    # through looks_like_one_path the way the inline loop always has.
    check("find_claims silent on a bulleted list of genuine path citations",
          mod.find_claims(BULLETED_ALL_CITATIONS_MUST_NOT_FIRE), [])
    check("find_claims silent on a bulleted trailing-slash + extension citation pair",
          mod.find_claims(BULLETED_ALL_CITATIONS_TRAILING_SLASH_AND_EXTENSION), [])
    claims = mod.find_claims(BULLETED_MIXED_CITATION_AND_IDENTIFIERS)
    enum_claims = [c for c in claims if c[0] == "enumeration"]
    check("find_claims still catches a bulleted mixed citation+identifier list",
          bool(enum_claims), True)
    # Accepted residual (found by round 10's own two-sided sweep, confirmed
    # pre-existing -- see the fixture's comment): a bulleted 2-item list
    # loses this one to token-count collapse, the bulleted-route sibling of
    # ACCEPTED_MISS_BARE_WORD_TRUNCATION_* above.
    check("find_claims ACCEPTS missing a bulleted 2-item list via bare-word leading-segment truncation",
          mod.find_claims(BULLETED_ACCEPTED_MISS_BARE_WORD_LEADING_SEGMENT_TWO_ITEM), [])

    # Discharge: a counting command in the body's own code span discharges
    # a cardinality claim; a bare listing command does NOT (needs COUNT).
    body_with_count_deriv = "There are `grep -rc fingerprint scripts/` -- 18 files."
    check("cardinality discharged by an in-body counting command",
          mod._derived_in_body(body_with_count_deriv, need_count=True), True)
    body_with_list_deriv_only = "There are `grep -rl fingerprint scripts/` -- 18 files."
    check("cardinality NOT discharged by an in-body listing-only command",
          mod._derived_in_body(body_with_list_deriv_only, need_count=True), False)
    check("enumeration IS discharged by an in-body listing-only command",
          mod._derived_in_body(body_with_list_deriv_only, need_count=False), True)

    # Discharge: a deriving command in another segment of the same Bash
    # call, with the body substring removed so the body's own prose cannot
    # accidentally satisfy this.
    body = "There are 18 files fingerprinted."
    cmd_with_sibling_deriv = f'grep -rc fingerprint scripts/; gh pr comment 1 --body "{body}"'
    check("cardinality discharged by a sibling-segment counting command",
          mod._derived_in_other_segments(cmd_with_sibling_deriv, body,
                                          need_count=True), True)
    cmd_no_deriv = f'gh pr comment 1 --body "{body}"'
    check("cardinality NOT discharged with no deriving command anywhere",
          mod._derived_in_other_segments(cmd_no_deriv, body, need_count=True),
          False)


# --------------------------------------------------------------------------
# End-to-end cases
# --------------------------------------------------------------------------

def end_to_end_checks():
    # True positive: --body-file reading the incident text off disk.
    path = body_file_with(INCIDENT_BODY)
    out = run_hook(f"gh pr comment 1401 -R Morrison-Lab/sparta --body-file {path}")
    check("true positive (--body-file): hook fires", bool(out), True)
    if out:
        payload = json.loads(out)
        ctx = (payload.get("hookSpecificOutput") or {}).get("additionalContext")
        check("true positive: additionalContext names the unverified claims",
              bool(ctx and "18 files" in ctx), True)
        check("true positive: systemMessage is present",
              "systemMessage" in payload, True)
        check("true positive: no permissionDecision key",
              "permissionDecision" in json.dumps(payload), False)

    # True positive: an inline --body literal, same claim.
    out = run_hook(
        'gh pr comment 1401 -R Morrison-Lab/sparta --body '
        f'"{INCIDENT_BODY}"'
    )
    check("true positive (inline --body): hook fires", bool(out), True)

    # True positive: gh api against a .../comments endpoint with -F body=@file.
    path2 = body_file_with(INCIDENT_BODY)
    out = run_hook(
        "gh api repos/Morrison-Lab/sparta/issues/1401/comments "
        f"-F body=@{path2}"
    )
    check("true positive (gh api .../comments -F body=@file): hook fires",
          bool(out), True)

    # Guard: ordinary ARD-summary comment -> silent.
    path3 = body_file_with(ARD_SUMMARY)
    out = run_hook(f"gh pr comment 1401 --body-file {path3}")
    check("guard: ARD disposition summary -> silent", bool(out), False)

    # Guard: discharged by a counting command in the same Bash call.
    body = "There are 18 files fingerprinted."
    out = run_hook(
        'grep -rc fingerprint scripts/ ; '
        f'gh pr comment 1401 --body "{body}"'
    )
    check("guard: discharged by a sibling-segment counting command -> silent",
          bool(out), False)

    # Guard: discharged by a counting command pasted in the body itself.
    body_with_deriv = "`grep -rc fingerprint scripts/` -- 18 files fingerprinted."
    out = run_hook(f'gh pr comment 1401 --body "{body_with_deriv}"')
    check("guard: discharged by an in-body counting command -> silent",
          bool(out), False)

    # Guard: non-Bash tool -> silent.
    payload = {"tool_name": "Read", "tool_input": {"file_path": "x"}}
    proc = subprocess.run([sys.executable, SUBJECT], input=json.dumps(payload),
                          capture_output=True, text=True)
    check("guard: non-Bash tool -> silent", bool(proc.stdout.strip()), False)

    # Guard: a Bash command that does not post a forge comment at all.
    out = run_hook("git status")
    check("guard: non-comment-posting Bash command -> silent", bool(out), False)

    # Guard: malformed JSON on stdin fails open.
    proc = subprocess.run([sys.executable, SUBJECT], input="not json",
                          capture_output=True, text=True)
    check("guard: malformed stdin JSON -> silent, no traceback",
          proc.stdout.strip(), "")


def main():
    global failures
    mod = load(SUBJECT)
    unit_checks(mod)
    end_to_end_checks()

    if failures:
        print(f"\n{failures} failure(s)")
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
