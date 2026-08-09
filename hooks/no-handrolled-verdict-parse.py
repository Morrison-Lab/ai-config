#!/usr/bin/env python3
"""PreToolUse guard: refuse a hand-rolled review-verdict parse.

`scripts/check-pr-fully-clean.py` is this corpus's verdict authority, and
[`shared/workflow/ardi.md`](../shared/workflow/ardi.md) already mandates it for
the single-PR loop. Nothing mandated it for a multi-PR **sweep**, which is
exactly where a hand-rolled parser goes in --- so
[`deterministic-tools`](../shared/principles/deterministic-tools.md)'s
constraint ("use the instrument that exists") got violated in the presence of
the instrument.

WHY A PHRASE SEARCH CANNOT WORK
-------------------------------
A verdict comment routinely QUOTES other verdicts. Citing the previous round,
pasting a repro block, discussing what a phrase should classify as --- all of
that lands verdict vocabulary in the body before the comment reaches its own
`### Verdict` section. So the FIRST match is usually somebody else's verdict.

Measured 2026-08-08 (ai-config#1297, recorded in
[`fully-clean.md`](../shared/workflow/fully-clean.md)), one sweep, two PRs, and
it misread in OPPOSITE directions:

  #1278  first match `Ready for merge` at offset 2980, inside a fenced python
         block quoting `classify_verdict("Ready for merge\\nonce CI passes.")`
         real verdict at 5421: **Needs more work**          -> false-CLEAN
  #1257  first match `Needs more work` at offset 775, inside a parenthetical
         citing the PRIOR round
         real verdict at 2401: **Ready for merge**          -> false-BLOCKED

The bidirectionality is what makes it unfixable by tuning: it cannot be
corrected with an offset or a "the reviewer errs pessimistic" assumption. The
false-clean direction is the expensive one --- it produced a MERGE
RECOMMENDATION on a PR whose verdict was blocking.

WHY PreToolUse RATHER THAN Stop
-------------------------------
Deliberate, and the alternative was really considered.

A `Stop` guard would have to key on the resulting CLAIM, and the claim-shaped
matcher is far too broad: legitimately reporting "the review says needs more
work", after reading a body carefully, is a correct thing to say and must not
be blocked. Narrowing that matcher enough to be safe narrows it into silence.

The parse itself is the decidable event, and it is decidable at the moment the
command is about to run --- before the wrong reading enters context at all. By
`Stop` time the false-clean verdict has already shaped the recap, and may
already have been acted on.

The block is also trivially satisfiable, which is what keeps a `deny` honest
(README, "A hook that misfires is worse than a missing one"): the remedy is one
documented command, and a genuinely-needed hand parse clears it with a one-token
env prefix.

THE CHECK
---------
All five must hold:

  1. a VERDICT phrase appears in the command
  2. that phrase sits in a MATCHING position --- an argument to jq
     test/capture/match/..., to grep/rg, to awk/sed, or to a python `re.` call.
     Merely echoing or printing the phrase is not a parse.
  3. the data is REVIEW-DERIVED --- the same command names a review-comment
     source (`issues/N/comments`, `pulls/N/comments`, `--json comments`, ...)
     or reads a saved body file.
  4. NO `check-pr-fully-clean.py` invocation earlier in the transcript FOR THAT
     PR (see the discharge note below)
  5. NO `ALLOW_HANDROLLED_VERDICT_PARSE=1` env-assignment prefix

Clause 3 is what keeps the negatives silent, and it carries most of the
precision: a `grep` of this repo's own docs for `Ready for merge` has 1 and 2
and fails 3, as does a grep of this file.

THE DISCHARGE IS PER-PR, ON PURPOSE
-----------------------------------
[`algorithmatize-checks`](../shared/workflow/algorithmatize-checks.md)'s "A
reminder guard's discharge condition is a second matcher" names the trap: an
over-broad discharge makes a guard go silent, and silence reads as compliance.
Discharging on ANY `check-pr-fully-clean.py` call anywhere in the session would
do exactly that --- one call early in a sweep would license hand-rolling every
remaining PR in it, which is the incident's own shape.

So the PR numbers in the offending command must all have been passed to
`check-pr-fully-clean.py`. Where the command names no PR number the guard falls
back to "any invocation discharges": still armed (a session with zero
invocations still fires), lenient only about WHICH PR. That leniency is
deliberate at the ambiguous edge, because this is a `deny` --- a guard that
blocks work it cannot attribute is a guard that gets switched off.

KNOWN GAP
---------
A body saved to an arbitrarily-named file (`gh api ... > /tmp/x.json`, then
`jq ... /tmp/x.json`) fails clause 3 in the second command and is not caught.
Widening clause 3 to any file at all would fire on every `jq` in the session.
Recorded rather than papered over.

Fails OPEN on any parse trouble. A guard that breaks Bash when a regex
misbehaves costs more than the mistake it prevents.
"""
import json
import re
import sys

# Verdict vocabulary. Sourced from the phrases the incident's own `capture()`
# alternation used, plus the two structural markers `fully-clean.md` names as
# the correct anchors -- a search for THOSE is the same hand-rolled parse.
VERDICT_PHRASE = re.compile(
    r"Ready for merge|Needs more work|Needs minor changes|Needs one fix|"
    r"Needs work|###\s*Verdict|\*\*Claude finished",
    re.I,
)

# Tools that MATCH text, as opposed to printing it. The phrase has to sit in an
# argument to one of these for the command to be a parse at all.
MATCHER_TOKEN = re.compile(
    r"\bjq\b|--jq\b|\bgrep\b|\begrep\b|\brg\b|\bag\b|\bawk\b|\bsed\b|"
    r"\bre\.(?:search|match|fullmatch|findall|finditer|compile|split|sub)\b|"
    r"\b(?:test|capture|scan|splits|startswith|endswith)\s*\(",
    re.I,
)
# How far after a matcher token the phrase may sit and still count as its
# argument. Generous, because clause 3 carries the precision -- a wide window
# here costs a false positive only when the command ALSO reads review comments.
MATCH_WINDOW = 400

# Clause 3: the command's data is review-derived. Two alternatives, and no
# more -- a `gh pr view N --json comments` form was dropped as redundant, since
# the `--json` alternative already decides it.
REVIEW_SOURCE = re.compile(
    # REST: repos/O/R/issues/N/comments, .../pulls/N/reviews, and the
    # repo-wide forms that omit the number.
    r"(?:issues|pulls)/(?:\d+/)?(?:comments|reviews)"
    # gh pr view --json comments, --json state,reviews
    r"|--json\s+[\w,]*(?:comments|reviews)",
    re.I,
)
# A body previously saved to a data file.
#
# Matched on the NAME, and only for data-ish extensions. Both restrictions are
# load-bearing. Matching any file whose name contains "verdict" would fire on
# this hook's own source and on its test -- the README's cautionary example
# exactly. And an earlier draft also matched any `/tmp/*.json` at all, which was
# both untested and inconsistent with the KNOWN GAP above: it is the same claim
# as "an arbitrarily-named saved body is not caught", made twice in opposite
# directions. Dropped in favour of the stated gap.
SAVED_BODY = re.compile(
    r"\S*(?:review|comment|verdict|body)\S*\.(?:json|jsonl|txt)\b",
    re.I,
)

# PR numbers this command is parsing.
PR_IN_COMMAND = [
    re.compile(r"issues/(\d+)/comments", re.I),
    re.compile(r"pulls/(\d+)/(?:comments|reviews)", re.I),
    re.compile(r"gh\s+pr\s+(?:view|diff|checks)\s+(\d+)", re.I),
]

# An INVOCATION of the instrument, and the PR it was run against.
#
# The leading interpreter (or `./`) is load-bearing rather than decoration: a
# bare `check-pr-fully-clean\.py` also matches `cat scripts/check-pr-fully-
# clean.py` and `grep -n foo scripts/check-pr-fully-clean.py`, so READING the
# script would discharge the guard. The `view_file` skip below cannot catch
# those, because they arrive as Bash.
#
# An earlier draft guarded this with a `(?<!test_)(?<!test-)` lookbehind
# instead, to keep a run of the script's own test suite from discharging it.
# That clause was measured DEAD: the suite is `scripts/test_check_pr_fully_
# clean.py`, whose name carries underscores, so the hyphenated string never
# appears in it and the lookbehind could not fire. Removed rather than shipped
# untested (ai-config#1304, "measured-dead guard components").
CHECKER_CALL = re.compile(
    r"(?:python3?\s+|\./)\S*check-pr-fully-clean\.py"
    r"((?:\s+-{1,2}\S+)*\s+(\d+))?",
    re.I,
)

# The explicit override. A real leading env assignment, not a mention.
OVERRIDE = re.compile(
    r"(?:^|[|;&]\s*|\(\s*)(?:\w+=\S*\s+)*ALLOW_HANDROLLED_VERDICT_PARSE=1\b")


def phrase_in_matcher_position(cmd):
    """Clause 1 AND 2: a verdict phrase sitting in a matcher's argument."""
    for m in MATCHER_TOKEN.finditer(cmd):
        window = cmd[m.end():m.end() + MATCH_WINDOW]
        hit = VERDICT_PHRASE.search(window)
        if hit:
            return hit.group(0)
    return None


def is_review_derived(cmd):
    """Clause 3."""
    return bool(REVIEW_SOURCE.search(cmd) or SAVED_BODY.search(cmd))


def prs_in(cmd):
    found = set()
    for rx in PR_IN_COMMAND:
        found.update(rx.findall(cmd))
    return found


def checked_prs(path):
    """Scan the transcript for check-pr-fully-clean.py calls.

    Returns (ran_at_all, set_of_pr_numbers).
    """
    ran = False
    prs = set()
    if not path:
        return ran, prs
    with open(path, errors="ignore") as fh:
        for line in fh:
            try:
                msg = json.loads(line)
            except Exception:
                continue
            blocks = (msg.get("message") or {}).get("content")
            if blocks is None:
                blocks = msg.get("content") or []
            if not isinstance(blocks, list):
                continue
            for b in blocks:
                if not isinstance(b, dict) or b.get("type") != "tool_use":
                    continue
                name = (b.get("name") or "").lower()
                # Reading the script is not running it. A `Grep` whose PATTERN
                # is the invocation is the case that needs this: the pattern
                # carries an interpreter, so it satisfies CHECKER_CALL exactly
                # as a real run would.
                #
                # `read`/`grep`/`glob` are the names this harness actually
                # emits, measured from a live transcript. The `view_file`
                # family is carried from `no-stale-pr-status.py`, where it is
                # dead for that reason -- kept only so a harness that does emit
                # those names is covered, not because it fires here.
                if name in ("read", "grep", "glob",
                            "view_file", "read_file", "grep_search", "list_dir"):
                    continue
                blob = json.dumps(b.get("input") or {})
                for m in CHECKER_CALL.finditer(blob):
                    ran = True
                    if m.group(2):
                        prs.add(m.group(2))
    return ran, prs


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if (payload.get("tool_name") or "") != "Bash":
            return 0
        cmd = (payload.get("tool_input") or {}).get("command") or ""
        if not cmd:
            return 0

        # 5: explicit override.
        if OVERRIDE.search(cmd):
            return 0
        # 1 + 2: a verdict phrase in a matching position.
        phrase = phrase_in_matcher_position(cmd)
        if not phrase:
            return 0
        # 3: the data is review-derived.
        if not is_review_derived(cmd):
            return 0
        # 4: the instrument has not already answered for this PR.
        ran, checked = checked_prs(payload.get("transcript_path") or "")
        targets = prs_in(cmd)
        if targets:
            if targets <= checked:
                return 0
        elif ran:
            return 0
    except Exception:
        return 0  # fail open

    unchecked = sorted(targets - checked) if targets else []
    which = f" for PR #{', #'.join(unchecked)}" if unchecked else ""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"This command matches the verdict phrase \"{phrase.strip()}\" "
                "against a PR's review comments. That is a hand-rolled verdict "
                f"parse, and `check-pr-fully-clean.py` has not been run{which}.\n\n"
                "A verdict comment routinely QUOTES other verdicts -- the "
                "previous round's, a repro block, a discussion of what a phrase "
                "should classify as -- all before its own `### Verdict` section. "
                "So a phrase search finds somebody else's verdict, and it "
                "misreads in BOTH directions.\n\n"
                "Measured 2026-08-08, one sweep (ai-config#1297):\n"
                "  #1278  matched `Ready for merge` inside a quoted python "
                "block; real verdict **Needs more work**   -> false-CLEAN\n"
                "  #1257  matched `Needs more work` inside a parenthetical "
                "citing the prior round; real verdict **Ready for merge**   "
                "-> false-BLOCKED\n\n"
                "The false-clean direction produced a merge recommendation on a "
                "PR whose verdict was blocking.\n\n"
                "Call the instrument instead:\n\n"
                "    python3 scripts/check-pr-fully-clean.py <PR>\n\n"
                "If you genuinely must parse by hand, `fully-clean.md` says to "
                "anchor on the LAST `### Verdict` heading -- the last, not the "
                "first -- after selecting candidate comments on the "
                "`**Claude finished` body marker. Then prefix this command with "
                "`ALLOW_HANDROLLED_VERDICT_PARSE=1` (a real env assignment, not "
                "a mention) to say the choice was deliberate."
            ),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
