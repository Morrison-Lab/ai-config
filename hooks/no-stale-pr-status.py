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
import hashlib
import json
import os
import re
import sys
import tempfile

# A bare pass/fail count says nothing about WHERE it came from: a local test
# suite and a check-run query both read "<n> pass". The trigger stays broad,
# because staleness after a push is worth warning about either way -- but the
# WORDING must not assert the number is a check-state claim when it may not be.
# Fired three times on a local suite count (ai-config#1859: "10 pass" and
# "30 pass", 2026-08-21; "33 pass", 2026-08-22). A warning that visibly
# misdescribes its own match trains the reader to skim it, which is
# `algorithmatize-checks`'s "Limits" failure arriving through the remedy.
RX_BARE_COUNT = re.compile(r"^\d+\s+pass$", re.I)

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
    r"\b0 fail",
    r"\bzero fail",
    r"\bready to merge\b",
    r"\bfully clean\b",
    r"\bno failures\b",
    r"\bconflict-free\b",
]
RX_ASSERT = re.compile("|".join(ASSERT), re.I)

# A push invalidates any earlier reading.
RX_PUSH = re.compile(r"git\s+push|create_or_update_file|push_files", re.I)

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
# What is NOT taken from it is its first-person anchor. That file requires an
# explicit `I`/`my` subject in every alternative, because its job is to detect
# an admission and "the review was wrong" is a statement about someone else.
# This guard's job is different, and the issue's own measured sentence proves
# the anchor cannot transfer: in `But "fully clean" was wrong too` the subject
# is the quoted claim, not a person. Attachment does that work here instead --
# see RX_CLAUSE_SEPARATOR below.
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
# conjunction, or a markdown boundary (a table cell, a new list item). None of
# those appears between the claim and its retraction in the measured sentence,
# where the two are adjacent.
#
# Attachment replaces the character window an earlier round used. A window
# cannot tell "green -- the badge is wrong" from "green was wrong", since both
# put the retraction within a few characters; a clause separator can.
RX_CLAUSE_SEPARATOR = re.compile(
    r"--|[,;()|]"
    r"|\n[ \t]*[-*+>#]"
    r"|\b(?:but|and|or|so|yet|however|though|although|while|whereas"
    r"|after|before|since|because|once|when|unless|if)\b",
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


def _sentence_start(text, hit):
    """Start of the sentence containing `hit`, coarsely."""
    start = 0
    for boundary in RX_SENTENCE_BREAK.finditer(text, 0, hit.start()):
        start = boundary.end()
    return start


def _trailing_end(text, hit):
    """End of the clause following `hit`, for the retraction scan."""
    end = RX_TRAILING_BREAK.search(text, hit.end())
    return end.start() if end else len(text)


def _attaches(connector):
    """True when nothing in `connector` breaks a retraction off the claim."""
    return not RX_CLAUSE_SEPARATOR.search(connector)


def _is_retracted(text, hit):
    """True if a retraction attaches to the ASSERT match, either side of it."""
    for after in RX_RETRACTION.finditer(text, hit.end(), _trailing_end(text, hit)):
        return _attaches(text[hit.end():after.start()])
    start = _sentence_start(text, hit)
    before = None
    for before in RX_RETRACTION.finditer(text, start, hit.start()):
        pass
    return before is not None and _attaches(text[before.end():hit.start()])


def _is_negated(text, hit):
    """True if the ASSERT match is negated or retracted within its sentence.

    Plain negation stays scoped to the text BEFORE the phrase, which is the
    pre-existing behaviour and must not be widened: "All checks green at this
    head, and I have not merged it yet" is a genuine stale-clean claim whose
    trailing negation is about something else entirely. Only the retraction
    vocabulary reads in both directions, and only when it attaches.
    """
    if RX_NEGATION.search(text[_sentence_start(text, hit):hit.start()]):
        return True
    return _is_retracted(text, hit)

def all_unnegated_asserts(text):
    """Every un-negated ASSERT match, in textual order.

    `find_unnegated_assert` returns the FIRST, which is the right answer for
    "should this fire". It is the wrong answer for "how should this be
    worded", because the strongest claim in a message is not always the
    earliest one.
    """
    return [hit for hit in RX_ASSERT.finditer(text) if not _is_negated(text, hit)]


def find_unnegated_assert(text):
    """Return the first ASSERT match not negated or retracted in its sentence."""
    for hit in RX_ASSERT.finditer(text):
        if not _is_negated(text, hit):
            return hit
    return None


def scan(path):
    """Return (last_push_idx, last_query_idx, last_failing_query_idx, last_assistant_text)."""
    last_push = last_query = last_failing_query = -1
    text = ""
    i = 0
    query_tool_use_ids = set()
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
                        if tool_name in ("view_file", "read_file", "grep_search", "list_dir"):
                            continue
                        args = tc.get("args") or tc.get("input") or (tc.get("function") or {}).get("arguments") or {}
                        blob = tool_name + " " + json.dumps(args)
                        tool_id = tc.get("id") or str(id(tc))
                        if RX_PUSH.search(blob):
                            last_push = i
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
                        if tool_name in ("view_file", "read_file", "grep_search", "list_dir"):
                            continue
                        blob = tool_name + " " + json.dumps(b.get("input") or {})
                        tool_id = b.get("id") or b.get("tool_use_id") or ""
                        if RX_PUSH.search(blob):
                            last_push = i
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
                    elif b.get("type") == "text" and role == "assistant":
                        if b.get("text", "").strip():
                            text = b["text"]
            elif isinstance(blocks, str) and role == "assistant" and blocks.strip():
                text = blocks
    return last_push, last_query, last_failing_query, text


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        path = payload.get("transcript_path") or ""
        last_push, last_query, last_failing_query, text = scan(path)
    except Exception:
        return 0  # fail open

    if not text:
        return 0
    hit = find_unnegated_assert(text)
    if not hit:
        return 0

    # If the last status query reported a failing or not-clean state, block clean assertions.
    if last_failing_query > last_query and last_failing_query > last_push:
        print(json.dumps({
            "decision": "block",
            "reason": (
                f"Your message asserts a PR's clean state -- \"{hit.group(0).strip()}\" -- "
                "but the most recent status query tool result in this transcript reported a FAILING or IN-PROGRESS check state. "
                "You cannot declare a PR fully clean when a status query returned failure or in-progress checks."
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

    print(json.dumps({
        "decision": "block",
        "reason": (
            f"{lead} -- "
            f"\"{hit.group(0).strip()}\" -- but the most recent status query in "
            "this transcript is OLDER than your most recent push. The reading "
            "you are about to report describes a commit that is no longer the "
            "head.\n\n"
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
