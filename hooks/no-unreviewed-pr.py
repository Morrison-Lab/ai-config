#!/usr/bin/env python3
"""Stop-hook guard: catch opening a PR without requesting a reviewer.

Opening a PR auto-triggers the repo's *own* review workflow, so review
genuinely is in motion -- for that half. It does NOT summon Copilot, which
reviews only when explicitly requested. The auto-triggered half running is
exactly what disguises the missing half: the PR shows review-shaped activity
in its checks while no reviewer has read the diff.

That matters more in this repo than it would elsewhere, because
`claude-review` currently fails repo-wide on context size (ai-config#897).
When it is down, Copilot is the ONLY working reviewer, so a PR opened without
an explicit request gets no review at all.

The condition is exactly decidable from the transcript, which is why this is
a hook rather than a rule to remember:

    a PR was created or marked ready this session
    AND no reviewer request came after it

Fails OPEN on any parse trouble, and fires at most once per distinct message,
so it cannot wedge a session.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

# Opening a PR, or taking a draft out of draft. `create_pull_request` is the
# harness tool; `gh pr create` and `gh pr ready` are the CLI forms.
RX_OPEN = re.compile(
    r"gh\s+pr\s+create|gh\s+pr\s+ready|create_pull_request|"
    r"\"?draft\"?\s*[:=]\s*false",
    re.I,
)

# Requesting a reviewer. Covers the REST endpoint, the CLI flag, and the MCP
# tool. `requested_reviewers` is the stable token across all three.
RX_REQUEST = re.compile(
    r"requested_reviewers|request_copilot_review|"
    r"gh\s+pr\s+edit[^\n]*--add-reviewer|"
    r"gh\s+pr\s+review[^\n]*--request",
    re.I,
)

# Marking a PR draft is a deliberate reason NOT to request review yet: a draft
# does not trigger the review bot, per shared/workflow/pr-on-claim.md. Only a
# *later* ready/create should re-arm this guard, which the index compare below
# handles naturally.
RX_DRAFT = re.compile(r"\"?draft\"?\s*[:=]\s*true|--draft\b", re.I)


def scan(path):
    """Return (last_open_idx, last_request_idx, last_draft_idx, text)."""
    last_open = last_request = last_draft = -1
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
                    # The name matters as much as the input: the harness tool
                    # names its verb only in `name`, while a CLI invocation
                    # carries it in the command string.
                    blob = (b.get("name") or "") + " " + json.dumps(
                        b.get("input") or {})
                    # Draft is checked first: `gh pr create --draft` matches
                    # both patterns, and it is the draft that decides.
                    if RX_DRAFT.search(blob):
                        last_draft = i
                    elif RX_OPEN.search(blob):
                        last_open = i
                    if RX_REQUEST.search(blob):
                        last_request = i
                elif b.get("type") == "text" and role == "assistant":
                    if b.get("text", "").strip():
                        text = b["text"]
    return last_open, last_request, last_draft, text


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        path = payload.get("transcript_path") or ""
        last_open, last_request, last_draft, text = scan(path)
    except Exception:
        return 0  # fail open

    if not text:
        return 0
    # No PR was opened or readied this session, so nothing is owed.
    if last_open < 0:
        return 0
    # A request after the open is exactly what discharges the obligation.
    if last_request > last_open:
        return 0
    # The most recent action was drafting, which legitimately defers review.
    if last_draft > last_open:
        return 0

    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-unreviewed-pr-{key}")
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
            "You opened or readied a PR in this session and no reviewer "
            "request follows it in the transcript.\n\n"
            "Opening a PR auto-triggers the repo's own review workflow but "
            "does NOT summon Copilot, which reviews only when explicitly "
            "requested. The auto-triggered half is what disguises this: the "
            "PR shows review-shaped activity while nothing has read the "
            "diff. In this repo `claude-review` currently fails repo-wide on "
            "context size (ai-config#897), so Copilot is often the only "
            "working reviewer and the PR gets no review at all.\n\n"
            "Request it now, in this same message:\n\n"
            "    gh api repos/<owner>/<repo>/pulls/<N>/requested_reviewers \\\n"
            "      -X POST -f 'reviewers[]=copilot-pull-request-reviewer[bot]' "
            "\\\n      --jq '.requested_reviewers[].login'\n\n"
            "Then verify it landed:\n\n"
            "    gh pr view <N> --json reviewRequests "
            "--jq '.reviewRequests[].login'\n\n"
            "If the PR is deliberately a DRAFT, that is a legitimate reason "
            "to defer -- a draft does not trigger the review bot (see "
            "shared/workflow/pr-on-claim.md). Say so explicitly rather than "
            "leaving it unstated.\n\n"
            "Writing \"review owed\" or \"still need to request review\" into "
            "a recap does not discharge this. Naming the debt reads as "
            "diligence while the work stays undone, which is the same "
            "anti-pattern shared/workflow/report-mistakes-proactively.md "
            "bans for filing."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
