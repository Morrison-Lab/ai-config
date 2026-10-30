"""Maintainer feedback that a push has not answered yet (ai-config#4611).

A maintainer's comment, review or inline comment is feedback until a later
push answers it. `check-pr-fully-clean.py` calls this; the merge hook
`hooks/enforce-mwc-review-gate.py` keeps its own copy because a hook runs
without `scripts/lib` on its path, and
`scripts/test_maintainer_feedback.py` pins the two copies to the same verdicts, and the three copies of the
maintainer-login reader to the same logins.
"""

import json
import os
import sys
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


def _configured_maintainers():
    """Comma-separated maintainer logins: `MAINTAINER_LOGINS`, else the
    "maintainers" list in the JSON file `AI_CONFIG_LOCAL` names (default
    `~/.config/ai-config/local.json`, see `ai-config.local.example.json`),
    else `d-morrison`, the repo owner, so an unconfigured install keeps its
    behaviour. A missing file or an absent or empty list is "unconfigured";
    a file that exists but is unreadable, is not a JSON object, or holds
    anything but a list of non-empty strings warns on stderr and falls back
    too. Standalone: hooks are staged one file at a time and cannot import
    a sibling module."""
    raw = os.environ.get("MAINTAINER_LOGINS")
    if raw is not None:
        return raw
    path = os.path.expanduser(
        os.environ.get("AI_CONFIG_LOCAL") or "~/.config/ai-config/local.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                names = json.load(fh).get("maintainers", [])
            if not isinstance(names, list) or not all(
                    isinstance(n, str) and n.strip() for n in names):
                raise ValueError('"maintainers" must be a list of login strings')
            if names:
                return ",".join(names)
        except (OSError, ValueError, AttributeError) as err:
            print(f"ai-config: ignoring {path}: {err}", file=sys.stderr)
    return "d-morrison"


def maintainer_logins() -> Set[str]:
    """Lowercased maintainer logins from `_configured_maintainers`."""
    raw = _configured_maintainers()
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
