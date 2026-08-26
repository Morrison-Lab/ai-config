#!/usr/bin/env python3
"""Stop-hook guard: catch declaring a PR clean on a short check list alone.

`gh pr checks` does not enumerate every check run on a head. Measured
2026-08-19 on ucdavis/bcs#651 at a5f4f3f2: it printed 21 rows, all passing,
while `commits/<sha>/check-runs` returned 24 runs, one of them a `failure`
(`review / antigravity-review`). The PR was reported fully clean on the
strength of the shorter list.

GraphQL `statusCheckRollup` is a different short surface, not a second
measurement of that omission. On Morrison-Lab/ai-config#2277 (2026-08-26)
the rollup matched the endpoint (8==8); the false Ready-for-merge claim
failed because the complete instrument (`check-pr-fully-clean.py`) exited 1
for missing automated review. The hook still treats the rollup as a partial
reading: a terminal clean claim needs the complete instrument, not any short
CI list that happens to look green.

That omission (for `gh pr checks`) is invisible by construction. A short list
and a clean list are the same observable -- there is no gap in the output, no
warning, and the counts look healthy. So the reader cannot tell a complete
enumeration from an incomplete one, and neither can the author, which is why
this is a hook rather than a rule to remember.

It is distinct from its sibling `no-stale-pr-status.py`, which asks whether a
reading is CURRENT. A reading can be perfectly current and still incomplete;
that hook's RX_QUERY accepts `gh pr checks` / `statusCheckRollup` as a fresh
reading, correctly for staleness and insufficiently for a terminal claim.
This one asks whether the reading could authorize the claim.

The condition is decidable from the transcript:

    message declares the PR clean
    AND a partial reading (`gh pr checks` or `statusCheckRollup`) appears
    AND no complete enumeration appears after the last push

where a complete enumeration is `check-pr-fully-clean.py` (which consumes the
endpoint and reports a verdict) or a direct `commits/<sha>/check-runs` read.

Deliberately narrow on the assertion side. A progress report -- "13 pass, 5
pending" -- is honest and must not trip this; only a terminal claim does.

Fails OPEN on any parse trouble, and fires at most once per distinct message,
so it cannot wedge a session.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

# Terminal claims only. "N pass, M pending" is a progress report and is fine.
RX_DECLARE = re.compile(
    r"\bfully clean\b|"
    r"\bready (to|for) merge\b|"
    r"\bready for you to merge\b|"
    r"\bsafe to merge\b|"
    r"\bnothing (is )?(failing|red)\b|"
    r"\b(all|every) checks? (are |is )?green\b",
    re.I,
)

# Incomplete instruments for a terminal clean claim.
# `gh pr checks` can omit runs (bcs#651); `statusCheckRollup` is a short
# rollup that is not the complete instrument (ai-config#2277).
RX_PARTIAL = re.compile(
    r"gh\s+pr\s+checks|"
    r"\bstatusCheckRollup\b",
    re.I,
)

# Instruments that see every check run on the head.
RX_COMPLETE = re.compile(
    r"(?<!test_)\bcheck-pr-fully-clean\.py|"
    r"commits/[0-9a-f]{7,40}/check-runs|"
    r"\bget_check_runs\b",
    re.I,
)

RX_PUSH = re.compile(r"git\s+push|create_or_update_file|push_files", re.I)


def scan(path):
    """Return (last_push, last_partial, last_complete, last_assistant_text)."""
    last_push = last_partial = last_complete = -1
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
            blocks = (m.get("message") or {}).get("content")
            if blocks is None:
                blocks = m.get("content") or []
            if not isinstance(blocks, list):
                continue
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use":
                    blob = (b.get("name") or "") + " " + json.dumps(b.get("input") or {})
                    if RX_PUSH.search(blob):
                        last_push = i
                    if RX_COMPLETE.search(blob):
                        last_complete = i
                    elif RX_PARTIAL.search(blob):
                        last_partial = i
                elif b.get("type") == "text" and role == "assistant":
                    if b.get("text", "").strip():
                        text = b["text"]
    return last_push, last_partial, last_complete, text


def already_fired(text):
    """Fire at most once per distinct message, so a block cannot wedge a session."""
    digest = hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()[:16]
    marker = os.path.join(tempfile.gettempdir(), "no-incomplete-check-enum-" + digest)
    if os.path.exists(marker):
        return True
    try:
        open(marker, "w").close()
    except Exception:
        pass
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        path = payload.get("transcript_path") or ""
        last_push, last_partial, last_complete, text = scan(path)
    except Exception:
        return 0  # fail open

    if not text:
        return 0
    hit = RX_DECLARE.search(text)
    if not hit:
        return 0

    # No partial reading in play: nothing to warn about.
    if last_partial < 0:
        return 0

    # A complete enumeration after the last push covers the claim. Ordering
    # against the partial read does not matter: `gh pr checks` run afterwards
    # for a readable summary does not un-verify what the complete read saw.
    # Only a PUSH invalidates it, by moving the head out from under it.
    if last_complete > last_push:
        return 0

    if already_fired(text):
        return 0

    print(json.dumps({
        "decision": "block",
        "reason": (
            f"Your message declares a PR clean -- \"{hit.group(0).strip()}\" -- but the "
            "supporting reading in this transcript is `gh pr checks` or "
            "`statusCheckRollup`, neither of which is the complete instrument for a "
            "terminal clean claim.\n\n"
            "Measured 2026-08-19 on ucdavis/bcs#651 at a5f4f3f2: `gh pr checks` printed "
            "21 rows, all passing, while the commit endpoint returned 24 runs including "
            "a `failure`. The PR was reported fully clean on the shorter list. A short "
            "list and a clean list look identical -- there is no gap in the output and "
            "no warning, so neither the reader nor you can tell them apart.\n\n"
            "`statusCheckRollup` is a different short surface: on ai-config#2277 "
            "(2026-08-26) it matched the endpoint (8==8), but a Ready-for-merge claim "
            "still rested on it instead of `check-pr-fully-clean.py`, which exited 1 "
            "for missing automated review.\n\n"
            "Run an instrument that sees every run, then report from it:\n\n"
            "    python3 scripts/check-pr-fully-clean.py <PR> -R <owner>/<repo>\n\n"
            "reading its EXIT STATUS three ways -- 0 clean, 1 a verdict of not-clean "
            "(confirm the output has `  - ` finding bullets, since an unhandled "
            "exception also exits 1), anything else the check having failed to answer.\n\n"
            "Or read the endpoint directly, with --paginate, since an unfinished or "
            "failing run on page 2 returns the same empty result as a clean head:\n\n"
            "    gh api \"repos/<owner>/<repo>/commits/<sha>/check-runs?per_page=100\" "
            "--paginate --jq '.check_runs[]|select(.conclusion!=\"success\" and "
            ".conclusion!=\"skipped\")|\"\\(.conclusion) \\(.name)\"'\n\n"
            "Note the repo may also use legacy commit statuses, which that endpoint does "
            "not cover; add `commits/<sha>/status` where it does.\n\n"
            "If you meant a progress report rather than a terminal claim, say the counts "
            "without declaring the PR clean -- \"13 pass, 5 pending\" trips nothing."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
