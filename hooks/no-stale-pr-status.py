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
    r"gh\s+run\s+view|checkSuites|mergeStateStatus",
    re.I,
)


def scan(path):
    """Return (last_push_idx, last_query_idx, last_assistant_text)."""
    last_push = last_query = -1
    text = ""
    i = 0
    with open(path, errors="ignore") as fh:
        for line in fh:
            i += 1
            try:
                m = json.loads(line)
            except Exception:
                continue
            role = m.get("type")
            blocks = (m.get("message") or {}).get("content") or []
            if not isinstance(blocks, list):
                continue
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use":
                    blob = json.dumps(b.get("input") or {})
                    if RX_PUSH.search(blob):
                        last_push = i
                    if RX_QUERY.search(blob):
                        last_query = i
                elif b.get("type") == "text" and role == "assistant":
                    if b.get("text", "").strip():
                        text = b["text"]
    return last_push, last_query, text


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        path = payload.get("transcript_path") or ""
        last_push, last_query, text = scan(path)
    except Exception:
        return 0  # fail open

    if not text:
        return 0
    hit = RX_ASSERT.search(text)
    if not hit:
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
        open(sentinel, "w").close()
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
