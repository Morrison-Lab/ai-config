#!/usr/bin/env python3
"""PreToolUse reminder: a brief owes a derivation for the state it asserts.

`shared/workflow/challenge-the-assignment.md` explains why a brief is the
artifact where a false premise hides best.
A brief asserts nothing in the grammatical sense --- it *instructs* --- so no
claim-checking rule fires on it, and the receiving agent inherits the premise
carrying the orchestrator's authority rather than the orchestrator's evidence.
Every step downstream can then be executed correctly and check green while the
whole task rests on something nobody looked up.

WHY THIS INJECTS RATHER THAN BLOCKS
-----------------------------------
Sending a brief is right.
Only the unverified premise inside it is wrong, and a guard cannot tell a
premise that was checked from one that was not --- it can only tell that the
sentence has the shape of a claim about a file.
Blocking on that shape would deny half the briefs this corpus writes, on a
signal that is suggestive rather than decisive.

So this only ever ADDS context.
There is no code path here that denies, escalates, or auto-approves; in
particular it never emits `permissionDecision`, whose absence defers to the
normal permission flow, and it never rewrites the prompt.
The model is free to read the note, decide the claim was already verified, and
launch the agent unchanged.

WHICH TOOLS CARRY A BRIEF
-------------------------
`Agent`/`Task` are the obvious channel, and were the only one covered until
2026-08-20. `SendMessage` is the other, and it is the higher-risk one: a
follow-up message to an already-running agent is where CORRECTIONS and NEW
premises land, so a false claim there arrives with the sender's authority and
displaces what the recipient had already verified.

Measured that day on `Morrison-Lab/ai-config#1795`: a coordinator sent a
follow-up brief asserting "this repo's local check does not predict its own
CI". It does --- `shared/writing/semantic-line-breaks.md` documents the
runnable gate --- and the claim was never guarded, because it travelled by
`SendMessage` rather than by `Agent`.

Note the registration is half of the coverage. `hooks.json`'s matcher decides
which payloads reach this script at all, so widening `BRIEF_TOOLS` without
widening the matcher changes nothing. Until 2026-08-20 the matcher read
`Agent` alone, which meant the `Task` branch above had never been reachable
either.

THE TWO INCIDENTS
-----------------
Both 2026-08-04, one session, both verified after the fact.

  1. A brief asserted that `CLAUDE.md` carries a quota carve-out phrased
     "`total_cost` 0 at `num_turns` 1".
     It does not: `grep -n "total_cost\\|num_turns" CLAUDE.md` returns nothing,
     and the sentence lives only at
     `shared/workflow/review-verdict-pitfalls.md:29`.
     The receiving agent caught it, which is luck rather than a mechanism.
  2. A later brief said `CLAUDE.md` has "five quota mentions".
     `grep -ci quota CLAUDE.md` returns 6 and `grep -oi quota CLAUDE.md | wc -l`
     returns 7.

The second is the worse one, and it is what shapes the discharge rule below.
Its correct line numbers had already been printed by the session's own earlier
`grep -n`, so the miscount came from visible data rather than from
recollection.
A discharge keyed on "this session grepped that file" would therefore have gone
silent on precisely the instance that most needed the reminder --- the
over-broad-discharge failure `shared/workflow/algorithmatize-checks.md` names,
where silence is indistinguishable from compliance.

DISCHARGE IS MATCHED TO THE CLAIM KIND
--------------------------------------
A claim is classified CONTENT ("carries", "does not mention") or CARDINALITY
("five quota mentions", "three sites").

  - A CONTENT claim is discharged by any derivation that inspects the file:
    `grep`, `git grep`, `rg`, `sed -n`, `wc`, `jq ... | length`, or a `Read`.
  - A CARDINALITY claim is discharged only by a derivation that PRODUCES A
    COUNT: `grep -c`, `rg -c`/`--count`, `wc -l`, or `jq ... | length`.

That asymmetry is the whole point.
Listing lines is not counting them, so incident 2 fires under this rule while a
naive path-match discharge would have missed it.

A derivation counts whether it sits in the brief itself, beside the claim ---
which is what the reminder asks for --- or earlier in this session's
transcript with its output actually present.

THE ONE PATHLESS CLAIM IT DETECTS
---------------------------------
Everything above is anchored to a named corpus file, so a count about the
SESSION'S OWN history passed silently until 2026-09-03: "five adversarial
rounds, ten findings" names no path, so clause A never fired (ai-config#3117).
The real figures were nine findings across five rounds.

The fix is not to drop the anchor. A pathless count matcher fires on ordinary
status prose -- "14 success, 1 skipped", "31 check runs" -- and a hook that
misfires gets switched off, taking the real cases with it.

Clause C instead uses the token this corpus emits itself. Every adversarial
review ends with a bare `[FINDINGS_COUNT: <N>]` line, so when a brief asserts
an aggregate over findings or rounds, the addends are already in the transcript
and "was anything run that reads them back" is decidable. It fires only when
two or more such values came back from this session's own `Agent`/`Task` calls,
the brief states a count of one of AGGREGATE_NOUNS that is NOT equal to one of
those values, and no command naming `FINDINGS_COUNT` ran after the last value
or sits beside the claim in the brief.

Both halves of that are narrower than they first read, and deliberately. The
claim must not merely be a count while two values happen to exist: a numeral
equal to a printed value is a per-round figure quoted off a review ("the three
findings from the last round"), and a brief that writes the addends out carries
its own derivation. And the discharge must NAME the token, so an unrelated
`wc -l` cannot switch the clause off for the rest of a session.

PRECISION, MEASURED
-------------------
Measured over every `Agent`/`Task` prompt retained in this machine's
transcripts on 2026-08-04, each replayed against its own session transcript
truncated to the records that preceded the launch, so the discharge saw exactly
what that session had derived at the time.

  - 26 prompts examined, 8 fired, 18 silent.
  - Those 8 carry 11 claims, and on inspection all 11 are genuine corpus-state
    assertions rather than incidental mentions.
    Two were the false ones above.
    The other nine were true, and none of them had been derived: they were
    asserted from recollection and happened to be right.
  - Both incidents fire.
    Incident 2 fires on its cardinality claim ALONE, its two content claims
    correctly discharged by that session's own earlier `grep -n`, which is the
    claim-kind matching doing its job.

Read 26 as a small denominator rather than a settled rate.
It is every Agent prompt this machine still holds, but transcripts rotate.
`flag-unassigned-worktree.py` measured 121 launches a few days earlier, and
`remind-ums-after-error.py` counted 138 transcripts under `~/.claude/projects`
in the same period; `find ~/.claude/projects -name '*.jsonl' | wc -l` returns
77 today, so roughly half those files are gone rather than the two counts
having been taken differently.
Two matcher false positives were found and fixed during that measurement, both
recorded at their fix sites -- a citation whose next verb belonged to the
reader, and a count that reached back across a paragraph break.

Review round 1 then found five more, four of them silent discharges, and each
is fixed and pinned by a regression case plus a control:
a same-BASENAME derivation vouching for a different file (this corpus holds 177
files named `SKILL.md`), the bare English word "grep" in prose reading as a
command, an imperative governing one clause of a compound sentence suppressing
a claim in another, `QUOTED` consuming blank-line newlines and drifting a
claim's line number away from its own adjacent derivation, and a count of four
or more digits falling back to CONTENT.
The first two are the reason the fire count moved from 7 to 8: both were
silencing real assertions in the measured corpus.

Every clause here is a heuristic, and each one's failure direction is chosen
deliberately.
The verb list, the imperative guard, and the path set all fail toward a MISSED
reminder rather than a wrong one, which for an inject-only guard costs nothing
but the reminder itself.
The discharge rules fail the other way on purpose, staying narrow, because
their wrong direction is SILENCE -- and a guard that goes quiet is
indistinguishable from a corpus where nobody ever asserts anything, which is
the failure `algorithmatize-checks` says nothing will report.

See `hooks/test-remind-brief-premises.py` for the corpus cases and the
clause-isolation mutation checks.

Fires once per distinct claim per session, because a reminder repeated on every
retry of the same call is noise, and noise is what gets a guard ignored.

Fails OPEN and SILENT: any parse trouble prints nothing at all.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

# ---------------------------------------------------------------- clause A
# A corpus path or a bare corpus filename. Bare `CLAUDE.md` and `MEMORY.md` are
# included because they are the files briefs assert about most, and both
# incidents were about `CLAUDE.md`. A bare kebab basename (`fully-clean.md`) is
# deliberately NOT a path on its own: adding it widened clause A with no new
# true positive in the measured corpus, and clause B is not tight enough to
# carry that much extra surface alone.
PATH = re.compile(
    r"""(?<![\w./-])(
        CLAUDE\.md
      | MEMORY\.md
      | (?:\./)?(?:shared|memories|skills|hooks|scripts|codex-skills)
          /[\w./-]*[\w-]
    )(?![\w/-])""",
    re.X,
)

# The same set as PATH, but reachable after a `/`, so an absolute path in a
# command (`grep -n x /repo/shared/workflow/ardi.md`) or a `Read`'s
# `file_path` resolves to the same corpus-relative key a brief would write.
# Used ONLY for derivations, never for claim detection, where the stricter
# lookbehind is what keeps `some/other/shared/x.md` out.
PATH_IN_CMD = re.compile(
    r"""(?<![\w.-])(
        CLAUDE\.md
      | MEMORY\.md
      | (?:\./)?(?:shared|memories|skills|hooks|scripts|codex-skills)
          /[\w./-]*[\w-]
    )(?![\w/-])""",
    re.X,
)


def key_for(path):
    """The discharge key for a path: corpus-relative, no leading `./`.

    NOT the basename. Keying on the basename let a derivation about one file
    discharge a claim about another entirely -- this corpus holds 177 files
    named `SKILL.md`, so a grep of `skills/gip/SKILL.md` silently vouched for
    an assertion about `skills/ardi/SKILL.md`.
    """
    return path[2:] if path.startswith("./") else path


# ---------------------------------------------------------------- clause B
# Verbs that assert what a file CONTAINS, as opposed to what should be done to
# it. "already covers" and "does not mention" are reached via the 0-2 word gap.
VERB = (
    r"carries|carry|contains|contain|says|say|states|state|asserts|assert"
    r"|documents|document|covers|cover|mentions|mention|lists|list"
    r"|defines|define|describes|describe|has|have|had|includes|include"
    r"|omits|omit|lacks|lack|records|record|notes|note|shows|show"
)

# Words allowed to sit between the path and its verb. Each must START with a
# letter, which is what stops a dash from being counted as a gap word: without
# that, "(see a.md and grep-is-not-coverage.md -- and note that ...)" parses as
# path + gap("--", "and") + verb("note") and a bare citation reads as a content
# assertion. The conjunction stoplist closes the same hole one token over.
GAP = r"(?:(?!and\b|or\b|but\b|nor\b|see\b|then\b|to\b|for\b)[A-Za-z][\w'-]*\s+){0,2}?"

# Unbounded and comma-tolerant. `\d{1,3}` capped counts at three digits, so
# "`CLAUDE.md` has 1200 lines" fell back to CONTENT and was then discharged by
# a merely-inspecting grep -- the exact silent discharge the claim-kind rule
# exists to prevent. `[\d,]*` also keeps "1,200" whole, which otherwise quoted
# back as "200".
COUNT = (
    r"\d[\d,]*"
    r"|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
    r"|zero|no"
)

# Words ending in -s that are never the plural noun of a cardinality claim.
NOT_PLURAL = {
    "is", "was", "has", "does", "goes", "this", "its", "us", "thus",
    "less", "plus", "yes", "as", "hers", "theirs", "whose",
}

# An identifier, not a word: `num_turns`, `total_cost_usd`, `foo.bars`, a path.
# Prose plural nouns do not carry underscores, dots, slashes, or digits, so
# this is what stops a code literal from supplying a cardinality claim -- see
# `visible_prose` for why it replaced an inline-code mask.
NOT_A_NOUN = re.compile(r"[_./\d]")

# An imperative opening means the sentence tells the agent to DO something to
# the file rather than telling it what the file holds. "Verify that CLAUDE.md
# carries X" is suppressed on purpose: the brief has already asked for the
# check this hook would ask for.
IMPERATIVE = re.compile(
    r"""^[\s>*+#-]*(?:\d+[.)]\s*)?(?:then\s+|first\s+|also\s+|next\s+)?
        (add|append|write|edit|create|update|put|insert|move|delete|remove
        |rename|run|read|open|grep|check|verify|confirm|re-?run|scan|search
        |look|cite|link|see|follow|use|keep|make|fix|apply|review|load
        |consult|avoid|skip|ignore|prefer|push|commit|stage|file|land|ship
        |do|don't|do\s+not|touch|copy|paste|extend|split|merge|refresh
        |regenerate|rebuild|report|start|stop|leave|hold|drop|pick)\b""",
    re.I | re.X,
)

# ---------------------------------------------------------------- clause C
# The ONE pathless cardinality claim that earns a detector, and the reason the
# rest of them do not.
#
# Clauses A and B anchor every count to a named corpus file, so a count whose
# subject is the SESSION'S OWN HISTORY passes silently: "five adversarial
# rounds, ten findings" names no path, so nothing above it fires. Measured
# 2026-09-03 on ai-config#3117, where that sentence went into a `SendMessage`
# brief and a squash commit; the real figures were nine findings across five
# rounds (2, 3, 3, 1, 0).
#
# Dropping the path anchor generally is the wrong fix and is deliberately NOT
# what this does. It would fire on ordinary status prose -- "14 success, 1
# skipped", "31 check runs", "two agents running" -- most of it legitimately
# derived, and `README.md`'s standing warning is that a hook which misfires
# gets switched off, taking the real cases with it.
#
# What makes this one case decidable is that the corpus emits its own token.
# `.claude/agents/adversarial-reviewer.md` requires every review to end with a
# bare `[FINDINGS_COUNT: <N>]` line, so when a brief asserts an aggregate over
# findings or rounds, the addends are already sitting in the transcript as
# machine-readable values. Either the session read them back or it recalled
# them, and "was an arithmetic or counting command run after those values
# appeared" is decidable rather than a judgment.
#
# So this fires ONLY when all of these hold, which is why it is narrow enough
# to keep the guard trusted:
#   - two or more `FINDINGS_COUNT` values came back from this session's own
#     `Agent`/`Task` calls (one value is not an aggregate, and a value read out
#     of some other PR's review comments is not this session's history),
#   - the brief states a count of one of AGGREGATE_NOUNS, in a clause about
#     what happened rather than what is wanted or still pending,
#   - that count is not itself one of the printed values, and the brief does
#     not write the addends out,
#   - no command naming `FINDINGS_COUNT` ran after the last value, and none is
#     pasted beside the claim in the brief itself.
FINDINGS_VALUE = re.compile(r"FINDINGS_COUNT\s*:\s*(\d+)")

# Kept to the nouns the `FINDINGS_COUNT` token is actually about. "runs",
# "checks", "commits" and the rest stay out on purpose: their values are not
# in the transcript in a form this hook can point at, so a reminder about them
# would be the pathless-count misfire above rather than this narrow case.
#
# The noun alone does not scope the claim to this session's review history --
# "reviews" and "findings" both have ordinary uses the printed values say
# nothing about. AGG_INTENT, AGG_NOT_YET and AGG_FOREIGN below SUBTRACT three
# of those uses: an intention, work not yet done, and a count about somebody
# else's forge item. Subtracting is not scoping, and the difference is worth
# stating rather than leaving to a reader. Two residuals this clause still
# cannot tell from its own, in both of which the reminder points at values the
# claim has nothing to do with: a count about somebody else's review history
# that names no PR or issue number at all ("we got seven reviews from the
# bot"), and one naming a sibling item by a BARE number ("#4242 came back with
# eight findings"), which `foreign_reference` cannot attribute either way and
# which the incident brief's own "Measured on #3107:" form requires it to read
# as the session's own.
AGGREGATE_NOUNS = {"findings", "rounds", "reviews"}

# The command that discharges clause C must NAME the token, exactly as
# clause A's discharge must name the claimed path. An earlier revision
# accepted any counting or arithmetic command -- `wc -l`, `grep -c`, a bare
# `awk` -- so one unrelated `find . -name '*.jsonl' | wc -l` switched the
# whole clause off for the rest of the session. That is the
# over-broad-discharge failure this file's docstring names, and it landed
# in the one population the clause was built for: a five-round ARDI session
# runs counting commands constantly, so the detector would have been silent
# exactly where it was needed.
DERIVE_AGGREGATE = re.compile(r"FINDINGS_COUNT")

# The values may only come back from a dispatched agent. Any other tool
# result carrying the token is somebody else's review history -- see
# `transcript_derivations`.
AGENT_TOOLS = {"Agent", "Task", "agent", "task", "dispatch_agent",
               "run_agent"}

# Clause C's own imperative list. The generic IMPERATIVE above is NOT
# widened with these: `count`, `sum`, `tally` and `total` head a noun
# phrase far more often than they open a command, and adding them there
# silently killed path-anchored claims that clause A had always caught --
# "Sum of the three sections in `shared/workflow/ardi.md` is wrong."
# stopped firing. The lookahead keeps the noun reading out here too.
AGG_IMPERATIVE = re.compile(
    r"""^[\s>*+#-]*(?:\d+[.)]\s*)?(?:then\s+|first\s+|also\s+|next\s+)?
        (count|sum|tally|total|recount)\b
        (?!\s+(?:of|is|are|was|were)\b)""",
    re.I | re.X,
)

# Clause C counts review history that ALREADY HAPPENED, so a brief stating
# an intention or describing work not yet done is not making the claim this
# clause is about. Without these, "I want two reviews of this before we
# merge." and "There are three reviews pending on the stack." both fired,
# and the appended note then asserted a false premise about each.
AGG_INTENT = re.compile(
    r"\b(?:want|wants|need|needs|plan|plans|expect|expects|intend|intends"
    r"|require|requires|request|requests|would\s+like|await|awaiting)\b",
    re.I,
)
AGG_NOT_YET = re.compile(
    r"^\s*(?:[A-Za-z][\w'-]*\s+){0,2}?"
    r"(?:pending|outstanding|queued|remaining|expected|planned|scheduled)\b",
    re.I,
)

# A count about ANOTHER PR's review history is not a count of this session's.
# `transcript_derivations` closes only the ARMING half of that -- it refuses to
# take values out of a foreign PR's comment bodies -- so a session whose own
# rounds armed the clause still fired on "sparta#1375 had 8 findings."
#
# A BARE `#3117` is deliberately not a foreign reference: the incident brief
# this clause exists for opens "Measured on #3107:", naming the PR the session
# is working. What marks a reference as somebody else's is the repo or owner
# glued to it, or the explicit "PR 4242" form.
#
# The qualifier alone is not enough, though, and reading it that way silenced
# the target case in its commonest phrasing. This corpus writes its own items
# qualified -- `README.md` and this file's own docstring both say
# `ai-config#3117` -- so "The five adversarial rounds on ai-config#3107
# produced ten findings." is a claim about THIS session's history wearing a
# repo name.
#
# The repo alone is not enough either, and reading it that way traded one
# misfire for its mirror image. This corpus's briefs name SIBLING items
# constantly, so "Address the eleven findings on ai-config#4242." was read as
# this session's own review history and the reminder pointed at values from a
# PR the claim is not about. Both halves have to match: a reference is the
# session's own when `own_repo` names its repository AND `own_items` names its
# number, and everything else is foreign.
AGG_FOREIGN = re.compile(
    r"\b(?:([\w.-]+)/)?([\w.-]+)#(\d+)|\b(?:PR|MR|issue)\s+\d+", re.I,
)

# `origin`'s URL, parsed the way `gh` itself infers a repo when none is named
# on the command line -- the same shape `hooks/flag-uncited-rebuttal.py`
# already uses, rather than a second parser for the same string.
GIT_REMOTE = re.compile(r"[:/]([\w.-]+)/([\w.-]+?)(?:\.git)?$")

_OWN_REPO = ()


def own_repo():
    """(owner, repo) for the repository this session is working in, lowercased.

    `GITHUB_REPOSITORY` first, because a workflow run sets it and it needs no
    subprocess; `git remote get-url origin` otherwise. Either half may be
    absent, and the pair is `(None, None)` when neither resolves -- in which
    case AGG_FOREIGN keeps its old behaviour and treats every qualified
    reference as somebody else's. That is the safe direction here: it costs a
    missed reminder rather than a wrong one.

    Resolved once per process and cached, including the failure, so a brief
    naming several forge items does not shell out once per match.
    """
    global _OWN_REPO
    if _OWN_REPO != ():
        return _OWN_REPO
    _OWN_REPO = (None, None)
    slug = os.environ.get("GITHUB_REPOSITORY") or ""
    if "/" in slug:
        owner, _, repo = slug.partition("/")
        _OWN_REPO = (owner.lower(), repo.lower())
        return _OWN_REPO
    try:
        out = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return _OWN_REPO
    if out.returncode != 0:
        return _OWN_REPO
    m = GIT_REMOTE.search(out.stdout.strip())
    if m:
        _OWN_REPO = (m.group(1).lower(), m.group(2).lower())
    return _OWN_REPO


# The item numbers this session is working, for the second half of the test
# above. Three sources, UNIONED rather than tried in order: `GITHUB_REF` on a
# pull-request workflow run, the branch name, and the PR number `gh` reports
# for that branch. This corpus's issue-first flow cuts branches named for the
# ISSUE (`fix/3117-brief-premises-cardinality`) while a brief names the PR, so
# neither of the last two alone covers a local session. Two digits minimum in
# a branch name, so a `v2` or an `mk3` does not claim every two-digit item in
# the repo.
GH_REF_ITEM = re.compile(r"^refs/(?:pull|merge-requests)/(\d+)/")
BRANCH_ITEM = re.compile(r"\d{2,}")

_OWN_ITEMS = None


def own_items():
    """The PR/issue numbers this session is demonstrably working, as strings.

    The union of three sources: `GITHUB_REF`, the branch name
    (`GITHUB_HEAD_REF` where a run sets it, else
    `git rev-parse --abbrev-ref HEAD`), and `gh pr view --json number` for the
    checked-out branch. None of them is a fallback for another.

    Empty when nothing resolves, and `foreign_reference` then treats every
    qualified reference as somebody else's. That is the same safe direction
    `own_repo` takes for the same reason: a missed reminder costs less than one
    pointing at a PR the claim is not about.

    Resolved once per process and cached, including the empty result, so a
    brief naming several forge items does not shell out once per match.
    """
    global _OWN_ITEMS
    if _OWN_ITEMS is not None:
        return _OWN_ITEMS
    items = set()
    m = GH_REF_ITEM.match(os.environ.get("GITHUB_REF") or "")
    if m:
        items.add(m.group(1))
    branch = os.environ.get("GITHUB_HEAD_REF") or ""
    if not branch:
        try:
            out = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=5)
            branch = out.stdout.strip() if out.returncode == 0 else ""
        except (OSError, subprocess.SubprocessError):
            branch = ""
    items.update(BRANCH_ITEM.findall(branch))
    try:
        out = subprocess.run(
            ["gh", "pr", "view", "--json", "number", "--jq", ".number"],
            capture_output=True, text=True, timeout=5)
        number = out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        number = ""
    if number.isdigit():
        items.add(number)
    _OWN_ITEMS = frozenset(items)
    return _OWN_ITEMS


def foreign_reference(text):
    """True when `text` names a forge item belonging to somebody else.

    A match with no repo qualifier (`PR 4242`) is foreign by construction --
    the number names an item this hook cannot attribute. A qualified one is
    foreign unless BOTH halves are the session's own: its repo is the one the
    session is working in, and its number is one this session is working. The
    repo alone let a count about a sibling PR in the SAME repository read as
    this session's own review history.
    """
    for m in AGG_FOREIGN.finditer(text):
        owner, repo, number = m.group(1), m.group(2), m.group(3)
        if repo is None:
            return True
        mine_owner, mine_repo = own_repo()
        if mine_repo is None or repo.lower() != mine_repo:
            return True
        if owner and mine_owner and owner.lower() != mine_owner:
            return True
        if number not in own_items():
            return True
    return False


# A forge reference: a numeral that is an item's NAME rather than a count of
# anything. Without it "Measured on #3107 the five rounds gave ten findings."
# reported `3107 the five rounds` as an undischarged claim, and 3107 can never
# equal a printed value, so no per-round-figure suppression could ever reach
# it. Worse, that bogus match CONSUMED the sentence's real claim: `finditer`
# resumes after the span it returned, so "ten findings" was never scanned.
#
# Hence a length-preserving MASK rather than a skip inside the loop. The digits
# are blanked for the count scan only; every suppression still reads the
# original text, where `PR 4242` is intact and AGG_FOREIGN can see it.
REF_NUMBER = re.compile(r"((?:#|\b(?:PR|MR|issue)\s+))(\d[\d,]*)", re.I)


def mask_references(text):
    """`text` with forge-reference digits blanked, same length throughout."""
    return REF_NUMBER.sub(lambda m: m.group(1) + " " * len(m.group(2)), text)


# Word forms `COUNT` accepts, so a claim's numeral can be compared against
# the values the transcript actually printed.
WORD_NUMBER = {
    "zero": 0, "no": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12,
}

FENCE = re.compile(r"```.*?```", re.S)
# `[ \t]*`, never `\s*`: `\s` matches a newline, so a blockquote preceded by
# blank lines swallowed those newlines into one substituted space and broke
# the line-count-preserving contract `visible_prose` depends on, drifting a
# claim's reported line away from an adjacent derivation's.
QUOTED = re.compile(r"^[ \t]*>.*$", re.M)
INLINE_CODE = re.compile(r"`([^`\n]+)`")

# ---------------------------------------------------------------- discharge
# Any command that inspects a file's contents.
#
# Deliberately narrow. An earlier draft also accepted `cat`, `head`, and
# `tail`, which made the discharge fire on ordinary prose -- "head commit",
# "head node", and "head_sha" all appear constantly in this corpus, so a
# sentence merely naming a file next to the word "head" silently discharged a
# real claim. That is the over-broad-discharge failure, and its symptom is
# silence, so nothing would have reported it.
# `(?![-\w])` after each command name, so `grep-is-not-coverage.md` is a
# filename rather than an invocation. The bare-word problem it leaves --
# "a phrase grep returning nothing" -- is closed separately, by only searching
# CODE spans of a brief rather than its prose; see `code_segments`.
DERIVE_ANY = re.compile(
    r"\b(?:git\s+)?(?:grep|rg|ag|ack)(?![-\w])|\bsed\s+-n\b|\bwc\s+-"
    r"|\bjq(?![-\w])|\|\s*length\b",
)
# Commands that produce a NUMBER. Bundled short flags are handled by the
# character class, so `grep -ci` and `grep -rc` both match.
DERIVE_COUNT = re.compile(
    r"\b(?:git\s+)?(?:grep|rg|ag)(?![-\w])\s+(?:-[a-z]*c[a-z]*\b|--count\b)"
    r"|\bwc\s+-[a-z]*l\b|\|\s*wc\b|\|\s*length\b|\bcount\s*\(",
)


def visible_prose(text):
    """Drop fenced blocks and blockquotes, and unwrap inline code.

    Backticks are removed rather than deleted with their contents, unlike
    `remind-ums-after-error.py`, because in this corpus the path itself is
    nearly always inside backticks -- deleting inline code would delete clause
    A's own anchor and the guard would never fire at all.
    They are removed rather than replaced by a space so that "`CLAUDE.md`'s"
    still reads as a possessive.

    Nothing here tracks WHICH text came from inside a code span, deliberately.
    Two earlier drafts tried, one toggling on each backtick and one pairing
    them with a regex, and both are defeated the same way: prose in this corpus
    carries odd backticks inside quoted shell strings, such as
    `grep -rn 'total_cost` 0 at'`, and a single stray one shifts the parity of
    everything after it.
    The job that mask was doing -- keeping a code literal
    from supplying a cardinality claim's plural noun -- is done instead by
    NOT_A_NOUN below, which rejects the identifier by its own shape and cannot
    be knocked out of alignment.
    """
    # Line-count-preserving, so an offset in the returned text sits on the same
    # line as in the raw prompt. The in-prompt discharge below is proximity
    # scoped, so a shifted line number would silently move a derivation out of
    # its claim's window.
    text = FENCE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    text = QUOTED.sub(" ", text)
    return text.replace("`", "")


# The two windows differ by EXACTLY one character, `,`, and that is the whole
# design: a comma can set off an aside interrupting a verb and its object, and
# a semicolon cannot -- it joins independent clauses.
#
# An earlier revision built the sentence window as `[.!?:]`, dropping `;` along
# with `,`. That let an aside-interrupted imperative reach across a semicolon
# and govern a wholly unrelated clause, silently discharging its claim. The
# invariant below is asserted by the test suite rather than left to a comment,
# because the leak was a missing character in a regex and no case in a
# by-example suite is obliged to notice one.
CLAUSE_BOUNDS = r"(?:\n|(?<=[.!?:,;])\s)"
SENTENCE_BOUNDS = r"(?:\n|(?<=[.!?:;])\s)"


def segment_start(text, pos, clauses=True):
    """Index of the start of the segment containing `pos`.

    With `clauses`, `,` and `;` end a segment as well. Without them the
    imperative guard read one verb as governing a whole compound sentence, so
    "Update the changelog, since `CLAUDE.md` carries ..." was suppressed by an
    "update" that asks for no verification of `CLAUDE.md` at all.
    """
    bounds = CLAUSE_BOUNDS if clauses else SENTENCE_BOUNDS
    best = 0
    for m in re.finditer(bounds, text[:pos]):
        best = m.end()
    return best


def segment_end(text, pos):
    """Index of the end of the clause containing `pos`.

    The mirror of `segment_start`, so a suppression can read a claim's WHOLE
    clause rather than only the words before it. AGG_FOREIGN needs that: a
    foreign reference sits after the count as often as before it ("8 findings
    on sparta#1375").
    """
    m = re.search(CLAUSE_BOUNDS, text[pos:])
    return pos + m.start() if m else len(text)


def imperative_governs(text, pos, upto, pattern=None):
    """True when an imperative verb governs the claim starting at `pos`.

    Two windows, because one alone gets a real case wrong in each direction.

    The clause-bounded window is the primary test, and it is what keeps a verb
    from governing a clause it has nothing to do with.

    The sentence window is the fallback, for an aside interrupting a verb and
    its object: "Verify, before merging, that `CLAUDE.md` carries the rule."
    There the clause window starts after the aside and clips "Verify" out
    entirely, so a brief that already asks for the check gets reminded to ask
    for it.

    The fallback window stops at a semicolon even though it does not stop at
    a comma, so an aside cannot reach across an independent clause: "Verify,
    before merging, that CI passes; `CLAUDE.md` carries X" leaves the claim
    ungoverned, which is right, because the aside has nothing to do with it.

    What separates that from the compound-sentence case is whether the verb
    had reached its object before the comma. An interrupted imperative is
    followed IMMEDIATELY by the comma ("Verify,"), while a complete one is
    not ("Update the changelog,"). So the fallback requires that adjacency
    rather than merely requiring a sentence-initial imperative, which would
    re-suppress the compound case this pair of rules exists to separate.

    The residual is a claim in a COMMA-joined clause after an interrupted
    imperative: "Verify, before merging, that CI passes, and `CLAUDE.md`
    carries X" stays suppressed, because the fallback must skip commas to
    reach back over the aside at all, so it cannot tell that comma from the
    aside's own. A semicolon there is caught; a comma is not. That is
    intrinsic to the two-window design rather than an oversight, and the
    direction is the deliberate one for this guard: a missed reminder, never
    a wrong one.

    Both this case and its opposite are pinned by the test suite rather than
    asserted here. An earlier revision of this docstring named a DIFFERENT
    residual -- "Verify the changelog, before merging, since `CLAUDE.md`
    carries X" -- which in fact fires, since the verb reaches its object
    before the comma and the fallback correctly declines. A review caught it.
    Stating a behaviour no test pinned is the exact failure this hook exists
    to flag, so the examples above are now cases rather than prose.
    """
    # Resolved at call time, never as a default argument: the test suite's
    # mutant harness swaps the module global, which a def-time default would
    # have already captured.
    pat = pattern or IMPERATIVE
    seg = segment_start(text, pos)
    if pat.match(text[seg:upto]):
        return True
    sent = segment_start(text, pos, clauses=False)
    m = pat.match(text[sent:upto])
    return bool(m and text[sent + m.end():sent + m.end() + 1] == ",")


def plural_after(text, start, span=90):
    """Return the matched phrase when a small count plus a plural noun follows."""
    window = text[start:start + span]
    for m in re.finditer(
        rf"\b({COUNT})\s+(?:[\w./-]+\s+){{0,2}}?([A-Za-z][\w./-]*s)\b", window, re.I
    ):
        noun = m.group(2)
        if noun.lower() in NOT_PLURAL or NOT_A_NOUN.search(noun):
            continue
        return m.group(0)
    return None


def numeral(tok):
    """The integer a COUNT token denotes, or None."""
    t = tok.lower().replace(",", "")
    if t.isdigit():
        return int(t)
    return WORD_NUMBER.get(t)


def claims(prompt):
    """Return [(kind, quoted_claim, path, line)] per corpus-state assertion."""
    text = visible_prose(prompt)
    found, seen = [], set()

    for pm in PATH.finditer(text):
        path, end = pm.group(1), pm.end()

        seg = segment_start(text, pm.start())
        if imperative_governs(text, pm.start(), pm.start() + len(path) + 1):
            continue

        kind = quote = None

        # PATH's <count> <plural noun>  -- "CLAUDE.md's five quota mentions"
        poss = re.match(r"'s\s+", text[end:end + 4])
        if poss:
            hit = plural_after(text, end + poss.end())
            if hit:
                kind, quote = "cardinality", f"{path}'s {hit}"

        # PATH <verb>  -- "CLAUDE.md carries ...", "CLAUDE.md does not mention"
        if kind is None:
            vm = re.match(
                rf"(?:'s)?\s+{GAP}(?:{VERB})\b", text[end:end + 60], re.I,
            )
            if vm:
                kind = "content"
                quote = (path + vm.group(0)).strip()
                hit = plural_after(text, end + vm.end())
                if hit:
                    kind, quote = "cardinality", f"{quote} {hit}"

        # <count> <plural noun> ... in PATH  -- "three sites in shared/x.md"
        if kind is None:
            # Scoped to the claim's own sentence, not a fixed character
            # window. A 110-character lookback reached back past a blank line
            # and a heading into the previous paragraph, so an unrelated
            # "three lines below it" supplied the count for a path two
            # sentences later.
            before = text[max(seg, pm.start() - 160):pm.start()]
            if re.search(r"\b(?:in|under|across|within|inside|of)\s+$", before):
                hit = plural_after(before, 0, span=len(before))
                if hit:
                    kind, quote = "cardinality", f"{hit} ... in {path}"

        if kind is None:
            continue
        key = (kind, path, quote.lower())
        if key in seen:
            continue
        seen.add(key)
        line = text.count("\n", 0, pm.start())
        found.append((kind, " ".join(quote.split()),
                      path, line))

    return found


def aggregate_claims(prompt):
    """Return [(kind, quoted_claim, value, line)] per review-history count.

    Clause C. Deliberately does NOT require a path, which is the whole point,
    and is therefore gated on the transcript actually carrying `FINDINGS_COUNT`
    values -- see `evaluate`. Without that gate this is exactly the pathless
    count matcher the clause-C comment argues against.

    Four suppressions, each closing a measured misfire:

    - The imperative guard, for the same reason it applies to clause A: a brief
      that says "count the findings across the five rounds" has already asked
      for the derivation this hook would ask for. It uses AGG_IMPERATIVE
      rather than widening IMPERATIVE, which regressed clauses A and B.
    - AGG_INTENT, because "I want two reviews of this before we merge." states
      an intention rather than a count of anything that happened.
    - AGG_NOT_YET, because "There are three reviews pending on the stack."
      counts work not yet done, which no `FINDINGS_COUNT` value is about.
    - AGG_FOREIGN, because "sparta#1375 had 8 findings." counts another PR's
      review history, and this session's own values say nothing about it. A
      reference naming the session's OWN repository is not foreign; see
      `foreign_reference`.

    One further exclusion, which is not a suppression but a parse fix: a
    numeral directly after a forge marker is an item's name, so `#3107` must
    not be read as the claim's cardinality. See `mask_references`.

    `value` is the integer the claim states, carried out so `evaluate` can
    tell an aggregate from a per-round figure quoted straight off a review.
    """
    text = visible_prose(prompt)
    # Scanned masked, suppressed against the original. The two are the same
    # length, so every offset below indexes both.
    scan = mask_references(text)
    found, seen = [], set()
    for m in re.finditer(
        rf"\b({COUNT})\s+(?:[A-Za-z][\w'-]*\s+){{0,2}}?([A-Za-z][\w-]*s)\b",
        scan, re.I,
    ):
        if m.group(2).lower() not in AGGREGATE_NOUNS:
            continue
        if imperative_governs(text, m.start(), m.end()):
            continue
        if imperative_governs(text, m.start(), m.end(), AGG_IMPERATIVE):
            continue
        start = segment_start(text, m.start())
        if AGG_INTENT.search(text[start:m.start()]):
            continue
        if AGG_NOT_YET.match(text[m.end():m.end() + 60]):
            continue
        if foreign_reference(text[start:segment_end(text, m.end())]):
            continue
        quote = " ".join(m.group(0).split())
        if quote.lower() in seen:
            continue
        seen.add(quote.lower())
        found.append(("aggregate", quote, numeral(m.group(1)),
                      text.count("\n", 0, m.start())))
    return found


# How far from a claim an in-brief derivation may sit and still discharge it.
# The reminder asks for the command pasted BESIDE the claim, so this is scoped
# rather than whole-prompt: a brief that greps a file in one place must not
# thereby vouch for an unrelated assertion about it forty lines away.
NEAR_LINES = 5


def code_segments(prompt):
    """Yield (line_number, code_text) for every code span and fenced line.

    A brief's PROSE is not a derivation, however command-shaped its vocabulary
    is. "a phrase grep returning nothing is not evidence" contains the word
    `grep` and derives nothing, and this corpus writes sentences like that
    constantly -- so an in-brief derivation must sit in a code span or a
    fenced block, which is where anyone pasting a command actually puts it.
    """
    fenced = False
    for n, line in enumerate(prompt.splitlines()):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            yield n, line
        else:
            for m in INLINE_CODE.finditer(line):
                yield n, m.group(1)


def derivations(prompt):
    """Line numbers where the brief itself derives a path.

    Returns (any_lines, count_lines), each a path -> [line] mapping.
    """
    any_p, count_p = {}, {}
    for n, seg in code_segments(prompt):
        counts = bool(DERIVE_COUNT.search(seg))
        if not counts and not DERIVE_ANY.search(seg):
            continue
        for pm in PATH_IN_CMD.finditer(seg):
            k = key_for(pm.group(1))
            if counts:
                count_p.setdefault(k, []).append(n)
            any_p.setdefault(k, []).append(n)
    return any_p, count_p


def aggregate_derivations(prompt):
    """Lines where the brief itself reads the `FINDINGS_COUNT` values back.

    Same code-span rule as `derivations`: a brief's prose is not a derivation,
    however arithmetic its vocabulary is. Same anchor as the transcript
    discharge, too -- a generic counting command pasted near the claim counts
    something, but nothing says it counted these.
    """
    return [n for n, seg in code_segments(prompt)
            if DERIVE_AGGREGATE.search(seg)]


def enumerates(text, values, line):
    """True when the brief writes out EVERY one of the transcript's values.

    A brief that writes out "the five rounds returned 2, 3, 3, 1 and 0
    findings" carries its own derivation: the addends are in front of the
    reader, so telling it to go derive them is noise.

    Every value, not two of them, and that threshold is the whole rule. Real
    `FINDINGS_COUNT` values run 0 to 3, so "at least two digits equal to a
    printed value" is satisfied by any two ordinary small integers near the
    claim: a date ("2026-09-03"), a version ("markdownlint-cli2@0.23.1"), a
    pair of `path:line` references, an inline "1) ... 2) ... 3)" step list.
    Each silenced the clause outright, which is this file's own named failure
    direction -- an over-broad discharge, whose symptom is silence, and silence
    is indistinguishable from compliance. Requiring the FULL multiset is also
    the only threshold that matches what the discharge claims: a reader can
    check a total against the addends only when all of them are present.

    Scoped to NEAR_LINES around the claim, exactly as `aggregate_derivations`
    is, and pooled across that window rather than per line, so a brief that
    lists one round per line still carries its own derivation.

    Digits only. The word forms `COUNT` accepts are ordinary English -- "no",
    "one", "two" -- so matching them would let unrelated prose discharge the
    clause wholesale.
    """
    pool = []
    for n, raw in enumerate(text.splitlines()):
        if abs(n - line) > NEAR_LINES:
            continue
        for tok in re.findall(r"\b\d[\d,]*\b", raw):
            v = numeral(tok)
            if v is not None:
                pool.append(v)
    for want in values:
        if want not in pool:
            return False
        pool.remove(want)
    return True


def near(table, base, line):
    return any(abs(n - line) <= NEAR_LINES for n in table.get(base, ()))


def transcript_derivations(path):
    """What this session derived earlier, with output present.

    Returns `(any_paths, count_paths, aggregate)`, where `aggregate` is
    `(values, derived)`: the `FINDINGS_COUNT` values this session's reviews
    printed, in order, and whether a command naming that token ran after the
    LAST of them. The ordering matters -- a command that ran before a value
    existed cannot have read that value back -- and it is what makes "with no
    deriving command between the values and the claim" decidable.

    The anchor is the last value, not the first, because the first is the one
    that makes the clause silent where it is needed most. A five-round ARDI
    session derives a running total mid-loop, and under a first-value anchor
    that round-two command discharged a round-five total it could not have
    read: rounds three, four and five had not happened yet. So the position is
    recorded rather than latched, and a derivation only counts when no value
    arrived after it.

    The values are taken ONLY from `Agent`/`Task` results, which is where a
    review returns one. Scanning every tool result armed the clause off other
    people's PRs: `.claude/agents/adversarial-reviewer.md` requires the
    reviewer to append `[FINDINGS_COUNT: N]` to its review, which lands in the
    review comment BODY, and `scripts/check-pr-fully-clean.py` then MATCHES
    that token as a not-clean marker. So one `gh pr view <other-PR> --json
    comments` carrying two of them was enough to make this session's brief
    answer for a review history it had no part in.
    """
    any_p, count_p = set(), set()
    agg_vals, agg_derived_at = [], -1
    agent_ids = set()
    pending = {}
    try:
        fh = open(path, errors="ignore")
    except Exception:
        return any_p, count_p, (agg_vals, False)

    with fh:
        for line in fh:
            try:
                m = json.loads(line)
            except Exception:
                continue
            blocks = (m.get("message") or {}).get("content") or m.get("content") or []
            if isinstance(blocks, str):
                blocks = [{"type": "text", "text": blocks}]
            elif not isinstance(blocks, list):
                blocks = []
            else:
                blocks = list(blocks)

            if "tool_calls" in m and isinstance(m["tool_calls"], list):
                for tc in m["tool_calls"]:
                    if isinstance(tc, dict):
                        tname = tc.get("name") or (tc.get("function") or {}).get("name") or ""
                        targs = tc.get("args") or tc.get("input") or (tc.get("function") or {}).get("arguments") or {}
                        if isinstance(targs, str):
                            try:
                                targs = json.loads(targs)
                            except Exception:
                                targs = {"command": targs}
                        tid = tc.get("id") or str(id(tc))
                        blocks.append({
                            "type": "tool_use",
                            "id": tid,
                            "name": tname,
                            "input": targs if isinstance(targs, dict) else {},
                        })

            is_assistant = m.get("type") == "assistant" or m.get("role") == "assistant" or m.get("source") == "MODEL" or m.get("type") in {"PLANNER_RESPONSE", "GENERIC"}
            if is_assistant:
                if m.get("isSidechain"):
                    continue
                for b in blocks:
                    if not isinstance(b, dict) or b.get("type") != "tool_use":
                        continue
                    inp = b.get("input") or {}
                    if not isinstance(inp, dict):
                        continue
                    bname = b.get("name") or ""
                    if bname in AGENT_TOOLS:
                        agent_ids.add(b.get("id"))
                    elif bname in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"):
                        cmd_str = str(inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or "")
                        pending[b.get("id")] = cmd_str
                    elif bname in ("Read", "Grep", "Glob", "view_file", "read_file", "grep_search", "find_by_name"):
                        # A Read shows the file; it never yields a count.
                        blob = str(inp.get("file_path") or inp.get("path") or inp.get("AbsolutePath") or inp.get("SearchPath") or "")
                        for pm in PATH_IN_CMD.finditer(blob):
                            any_p.add(key_for(pm.group(1)))

            elif m.get("type") == "user" or m.get("source") == "USER_EXPLICIT":
                for b in blocks:
                    if not isinstance(b, dict) or b.get("type") != "tool_result":
                        continue
                    out = str(b.get("content") or "")
                    # Read BEFORE the `pending` lookup below: a review's
                    # `[FINDINGS_COUNT: N]` comes back from an `Agent` call,
                    # which has no pending command, so a result scanned only
                    # after that lookup is one this clause never sees.
                    if not b.get("is_error") and b.get("tool_use_id") in agent_ids:
                        agg_vals += [int(v) for v in FINDINGS_VALUE.findall(out)]
                    cmd = pending.pop(b.get("tool_use_id"), None)
                    if cmd is None or b.get("is_error"):
                        continue
                    # Output must actually be present: a command whose result
                    # is empty or errored derived nothing.
                    if not out.strip():
                        continue
                    counts = bool(DERIVE_COUNT.search(cmd))
                    if agg_vals and DERIVE_AGGREGATE.search(cmd):
                        # How many values existed when this command ran, not
                        # merely that one did. Compared against the final
                        # count below, so a derivation overtaken by a later
                        # round no longer answers for it.
                        agg_derived_at = len(agg_vals)
                    if not counts and not DERIVE_ANY.search(cmd):
                        continue
                    for pm in PATH_IN_CMD.finditer(cmd):
                        k = key_for(pm.group(1))
                        if counts:
                            count_p.add(k)
                        any_p.add(k)

    return any_p, count_p, (agg_vals, agg_derived_at == len(agg_vals))


NOTE = (
    "This brief asserts state it has not derived, and a brief is where an "
    "unverified premise survives best -- it reads as instruction rather than "
    "as a claim, so nothing downstream checks it and the receiving agent "
    "inherits it with your authority.\n\n"
    "Unverified claim(s):\n{claims}\n\n"
    "Either paste the deriving command beside the claim in the brief, or tell "
    "the agent to verify before acting on it. A count needs a counting command "
    "(`grep -c`, `wc -l`); listing lines is not counting them.\n\n"
    "If you already derived these, say so in the brief and launch unchanged."
)

# The command `aggregate_note` prescribes, with `{t}` standing in for the
# transcript path. A module constant rather than an inline literal so the test
# suite can RUN the exact string the note hands the user and compare its output
# against this hook's own `agg_vals` -- a prescribed derivation that disagrees
# with the arming set is the defect this constant exists to keep pinned.
AGGREGATE_DERIVATION = (
    "jq -rn '[inputs] as $r"
    " | [$r[]|select(.type==\"assistant\")|.message.content[]?"
    "|select(.type==\"tool_use\" and (.name==\"Agent\" or .name==\"Task\"))|.id]"
    " as $a | $r[]|select(.type==\"user\")|.message.content[]?"
    "|select(.type==\"tool_result\" and (.tool_use_id as $i | $a|index($i)))"
    "|.content|tostring' \"{t}\""
    " | grep -o 'FINDINGS_COUNT: [0-9]*'"
    " | awk '{n++; s+=$2} END {print n\" rounds, \"s\" findings\"}'"
)


def aggregate_note(tpath):
    """The clause-C addendum, naming the transcript the values are actually in.

    Appended only when an `aggregate` claim is among the findings, so an
    ordinary path-anchored reminder does not carry advice about a token it is
    not about.

    The path is interpolated rather than left as a `$T` placeholder. No session
    sets `$T`, so a pasted command expanded to an empty filename and died --- a
    prescribed derivation that cannot be run derives nothing, which is this
    hook's own complaint about a brief that asserts without deriving. The hook
    already holds the path, so there was nothing to leave to the reader.

    The command is scoped the way `transcript_derivations` is, and for the same
    reason. A bare `grep` over the transcript counts every `FINDINGS_COUNT` in
    it, including values pasted from another PR's review bodies by a
    `gh pr view ... --json comments`, and including this note itself once the
    hook has fired --- so it prescribed a figure the hook would then accept as
    the derivation while disagreeing with the hook's own arming set. Reading
    only the `tool_result` blocks whose `tool_use_id` belongs to an
    `Agent`/`Task` call excludes both. The test suite RUNS both commands on a
    transcript carrying a foreign PR result and prints each figure.
    """
    t = tpath or "$HOME/.claude/projects/<this session>.jsonl"
    return (
        "\n\nThis session's reviews printed `[FINDINGS_COUNT: N]` values, and "
        "no command has read them back since. If a count above aggregates "
        "those values, derive it rather than recalling it. This reads back "
        "only the values THIS session's own `Agent`/`Task` calls returned:\n"
        "  " + AGGREGATE_DERIVATION.replace("{t}", t) + "\n"
        "Put the derived figures in the brief."
    )


def evaluate(prompt, tpath=""):
    """Return the undischarged claims as [(kind, quote)].

    Split out of `main` so the test suite can mutation-check one clause at a
    time without going through stdin, per
    `shared/workflow/algorithmatize-checks.md`: an ANDed fire condition hides
    an untested clause, because reverting one clause still passes any case a
    sibling clause keeps correct.
    """
    found = claims(prompt)
    agg_found = aggregate_claims(prompt)
    if not found and not agg_found:
        return []

    in_any, in_count = derivations(prompt)
    if tpath and os.path.isfile(tpath):
        t_any, t_count, (agg_vals, agg_derived) = transcript_derivations(tpath)
    else:
        t_any, t_count, (agg_vals, agg_derived) = set(), set(), ([], False)

    undischarged = []
    for kind, quote, path, line in found:
        base = key_for(path)
        if kind == "cardinality":
            if base in t_count or near(in_count, base, line):
                continue
        elif base in t_any or near(in_any, base, line):
            continue
        undischarged.append((kind, quote))

    # Clause C fires only against a transcript that carries the addends. Two
    # values, not one: with a single `FINDINGS_COUNT` in the session there is
    # nothing to aggregate, and firing on it would make this the pathless
    # count matcher the clause-C comment argues against.
    if agg_found and len(agg_vals) >= 2 and not agg_derived:
        in_agg = aggregate_derivations(prompt)
        agg_text = visible_prose(prompt)
        # A count clause A already anchored to a file is that clause's claim,
        # discharged by that clause's rule. Re-reporting it here would list it
        # twice, and worse, would re-fire one a counting command had cleared.
        anchored = [q.lower() for _, q, _, _ in found]
        seen_vals = set(agg_vals)
        for kind, quote, value, line in agg_found:
            if any(quote.lower() in q for q in anchored):
                continue
            # The gate above counts values in the TRANSCRIPT; this one asks
            # whether the CLAIM aggregates them. A numeral equal to one of the
            # printed values is a figure read straight off a review -- "the
            # three findings from the last round", "round 5 came back clean
            # with 0 findings" -- not a total anybody had to compute. Without
            # this, every brief written from round two onward fired, which is
            # the misfire `README.md` warns gets the whole guard switched off.
            if value is not None and value in seen_vals:
                continue
            if any(abs(n - line) <= NEAR_LINES for n in in_agg):
                continue
            # Per claim, not once for the whole brief: the addends are a
            # derivation only where they sit BESIDE the count they add up to.
            if enumerates(agg_text, agg_vals, line):
                continue
            undischarged.append((kind, quote))
    return undischarged


# The payload field carrying the brief, per tool.
#
# `Agent`/`Task` put it in `prompt`; `SendMessage` puts it in `message`.
# Antigravity uses `invoke_subagent` (Prompt) and `send_message` (Message).
BRIEF_TOOLS = {
    "Agent": "prompt",
    "Task": "prompt",
    "SendMessage": "message",
    "invoke_subagent": "Prompt",
    "send_message": "Message",
}


def _read_payload() -> tuple[dict, bool]:
    """Parse payload from sys.argv (--dry-run / --simulate) or sys.stdin."""
    args = sys.argv[1:]
    is_dry_run = "--dry-run" in args or "--simulate" in args
    if is_dry_run:
        positional = [a for a in args if not a.startswith("-")]
        if positional:
            raw_cmd = positional[0].strip()
            if raw_cmd.startswith("{") and raw_cmd.endswith("}"):
                try:
                    return json.loads(raw_cmd), True
                except Exception:
                    pass
            return {"tool_name": "Agent", "tool_input": {"prompt": raw_cmd}}, True

    try:
        payload = json.load(sys.stdin)
        return (payload if isinstance(payload, dict) else {}), is_dry_run
    except Exception as exc:
        print(f"remind-brief-premises: unreadable hook input ({exc})",

              file=sys.stderr)
        return {}, is_dry_run


def main() -> int:
    payload, is_dry_run = _read_payload()
    if not payload or not isinstance(payload, dict):
        return 0
    tool_name = payload.get("tool_name")
    if tool_name not in BRIEF_TOOLS:
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0

    prompts = []
    if tool_name == "invoke_subagent" and isinstance(tool_input.get("Subagents"), list):
        for sa in tool_input["Subagents"]:
            if isinstance(sa, dict) and isinstance(sa.get("Prompt"), str):
                prompts.append(sa["Prompt"])
    else:
        field = BRIEF_TOOLS[tool_name]
        p = tool_input.get(field) or tool_input.get(field.lower()) or tool_input.get(field.capitalize())
        if isinstance(p, str):
            prompts.append(p)

    prompts = [p for p in prompts if p.strip()]
    if not prompts:
        return 0

    prompt = "\n\n".join(prompts)

    try:
        tpath = payload.get("transcript_path") or ""
        undischarged = evaluate(prompt, tpath)
        if not undischarged:
            return 0

        key = hashlib.sha256(
            (tpath + "|" + "|".join(q for _, q in undischarged)).encode()
        ).hexdigest()[:16]
        sentinel = os.path.join(
            tempfile.gettempdir(), f".claude-brief-premises-{key}"
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

        note = NOTE.format(claims=listed)
        if any(k == "aggregate" for k, _ in undischarged):
            note += aggregate_note(tpath)
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": note,
            },
        }
        if not os.environ.get("ANTIGRAVITY_AGENT"):
            out["systemMessage"] = (
                f"Brief asserts underived state ({len(undischarged)} "
                "underived claim(s)); verify or paste the deriving command."
            )
        print(json.dumps(out))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
