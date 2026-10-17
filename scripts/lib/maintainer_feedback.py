"""Maintainer feedback that a push has not answered yet (ai-config#4611).

A maintainer's comment, review or inline comment is feedback until a later
push answers it. `check-pr-fully-clean.py` calls this; the merge hook
`hooks/enforce-mwc-review-gate.py` keeps its own copy because a hook runs
without `scripts/lib` on its path, and
`scripts/test_maintainer_feedback.py` pins the two copies to the same verdicts.
"""

import os
import re
from typing import Any, Dict, List, Set

# The agent-disclosure marker an agent appends to a comment it posts under the
# maintainer's login.
AGENT_AUTHORSHIP_RE = re.compile(
    r"posted by\b[^\n]*\(ai agent\)|\*\*claude finished|\U0001f916",
    re.IGNORECASE,
)

# A bare merge grant or approval, not a request for change. One optional
# token, so no two quantifiers can match the same text.
EXEMPT_RE = re.compile(
    r"/?(?:ai-config:)?(?:mwc|maw|merge(?:[- ]it)?|lgtm|approved?"
    r"|looks good|ship it)(?: ?#?(?:all|\d+))?[.!]?",
    re.IGNORECASE,
)


def maintainer_logins() -> Set[str]:
    """Lowercased logins in `MAINTAINER_LOGINS` (default `d-morrison`)."""
    raw = os.environ.get("MAINTAINER_LOGINS", "d-morrison")
    return {x.strip().lower() for x in raw.split(",") if x.strip()}


def unread_maintainer_feedback(pr_data: Dict[str, Any]) -> List[str]:
    """Descriptions of maintainer items posted after the head commit.

    Input: the PR as `gh pr view --json` returns it, plus `reviewComments`
    (`pulls/<n>/comments` entries with `createdAt`, `author`, `body`).
    Output: one `"<kind> by <login> at <timestamp>"` string per item, empty
    when none. A payload without `commits` cannot name the head date and
    reports nothing.

    Skipped as not feedback: an item at or before the head commit, a blank
    body (an Approve click with no text), a body with the agent-disclosure
    marker, and a bare grant or approval.
    """
    commits = pr_data.get("commits") or []
    head_date = (commits[-1].get("committedDate") or "") if commits else ""
    if not head_date:
        return []
    logins = maintainer_logins()
    items = (
        [("comment", c.get("author"), c.get("createdAt"), c.get("body"))
         for c in pr_data.get("comments") or []]
        + [("review", r.get("author"), r.get("submittedAt"), r.get("body"))
           for r in pr_data.get("reviews") or []]
        + [("inline comment", c.get("author"), c.get("createdAt"), c.get("body"))
           for c in pr_data.get("reviewComments") or []]
    )
    found = []
    for kind, author, when, body in items:
        login = ((author or {}).get("login") or "").lower().removesuffix("[bot]")
        body = body or ""
        if login not in logins or (when or "") <= head_date:
            continue
        text = body.strip()
        if not text or AGENT_AUTHORSHIP_RE.search(body) or EXEMPT_RE.fullmatch(text):
            continue
        found.append(f"{kind} by {login} at {when}")
    return found
