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

# A fresh reading. Covers the CLI and the MCP surfaces.
RX_QUERY = re.compile(
    r"gh\s+pr\s+checks|statusCheckRollup|get_check_runs|"
    r"gh\s+run\s+view|checkSuites|mergeStateStatus|"
    r"python3?\s+.*(?<!test_)\bcheck-pr-fully-clean\.py",
    re.I,
)

RX_FAIL_QUERY = re.compile(
    r"\\u274c|\u274c|\bNOT fully clean\b|contains findings|conclusion.*failure|status.*in_progress|No review comment has been posted",
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
    r"\b(not|never|cannot|unable)\b|n['’]t\b", re.I,
)
# Sentence boundaries: a terminator followed by whitespace, or a blank line.
# Deliberately coarse -- this only needs to find SOME earlier boundary, not
# parse prose correctly.
RX_SENTENCE_BREAK = re.compile(r"[.!?](?:\s|$)|\n\s*\n")


def find_unnegated_assert(text):
    """Return the first ASSERT match not negated earlier in its sentence."""
    for hit in RX_ASSERT.finditer(text):
        sentence_start = 0
        for boundary in RX_SENTENCE_BREAK.finditer(text, 0, hit.start()):
            sentence_start = boundary.end()
        preceding = text[sentence_start:hit.start()]
        if not RX_NEGATION.search(preceding):
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
            role = m.get("type")
            blocks = (m.get("message") or {}).get("content")
            if blocks is None:
                blocks = m.get("content") or []
            if not isinstance(blocks, list):
                continue
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use":
                    tool_name = (b.get("name") or "").lower()
                    if tool_name in ("view_file", "read_file", "grep_search", "list_dir"):
                        continue
                    # The name matters as much as the input: an MCP write names
                    # its verb only there (mcp__github__push_files), while the
                    # MCP read names its own in a `method` input parameter.
                    blob = tool_name + " " + json.dumps(
                        b.get("input") or {})
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

    print(json.dumps({
        "decision": "block",
        "reason": (
            f"Your message asserts a PR's check state -- "
            f"\"{hit.group(0).strip()}\" -- but the most recent status query in "
            "this transcript is OLDER than your most recent push. The reading "
            "you are about to report describes a commit that is no longer the "
            "head.\n\n"
            "This is a claim about whether work is finished, so the reader may "
            "merge on it.\n\n"
            "Re-query now, in this same message, and state the head SHA "
            "alongside the counts:\n\n"
            "    git rev-parse --short origin/<branch>\n"
            "    gh pr view <N> -R <owner>/<repo> --json headRefOid "
            "--jq '.headRefOid[0:8]'\n"
            "    gh pr checks <N> -R <owner>/<repo> | awk -F'\\t' '{print $2}' "
            "| sort | uniq -c\n\n"
            "Confirm the two SHAs agree before reporting. Note also that a "
            "freshly pushed head often shows a small green count simply "
            "because most jobs have not been scheduled yet -- an early reading "
            "is stale AND taken before the check set finished expanding."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
