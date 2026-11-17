"""Maintainer feedback that no agent reply has answered yet (ai-config#4611, #5577).

A maintainer's comment, review or inline comment is feedback until a later
agent reply answers it; a push alone does not. `check-pr-fully-clean.py` calls this; the merge hook
`hooks/enforce-mwc-review-gate.py` keeps its own copy because a hook runs
without `scripts/lib` on its path, and
`scripts/test_maintainer_feedback.py` pins the two copies to the same verdicts,
and the three copies of the maintainer-login reader to the same logins.
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

# The footer an agent puts on a reply it posts under the maintainer's login.
# Such a reply answers the maintainer items before it (ai-config#5577).
# Narrower than AGENT_AUTHORSHIP_RE: the robot emoji and "Claude finished" also
# mark automated review output, which answers nothing.
AGENT_REPLY_RE = re.compile(r"posted by\b[^\n]*\(ai agent\)", re.IGNORECASE)

# A bare merge grant or approval, not a request for change. One optional
# token, so no two quantifiers can match the same text.
EXEMPT_RE = re.compile(
    r"/?(?:ai-config:)?(?:mwc|maw|merge(?:[- ]it)?|lgtm|approved?"
    r"|looks good|ship it)(?: ?#?(?:all|\d+))?[.!]?",
    re.IGNORECASE,
)


# A review an agent posts under the maintainer's login is a review, not
# feedback to answer: it opens `Independent review of head <sha>` or carries a
# `<!-- review-data:` payload. Without this exemption the review of the current
# head was itself "feedback newer than the push" and blocked the PR it cleared
# (epi202#4, 2026-11-02). Its verdict is read by check_latest_verdict.
REVIEW_COMMENT_RE = re.compile(
    r"\A\s*Independent review of head\s+`?[0-9a-f]{7,40}`?(?![0-9a-z])"
    r"|<!--\s*review-data:",
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
    """Descriptions of maintainer items that no agent reply has answered yet.

    Input: the PR as `gh pr view --json` returns it, plus `reviewComments`
    (`pulls/<n>/comments` entries with `createdAt`, `author`, `body`).
    Output: one `"<kind> by <login> at <timestamp>"` string per item, empty
    when none.

    An item is answered only by a later agent reply: an item under a
    maintainer login whose body carries the agent footer (`AGENT_REPLY_RE`)
    and is not itself a head review. A push answers nothing, since a merge of
    the base branch is a push too (ai-config#5577; the rule before was "newer
    than the head commit", ai-config#4611).

    Skipped as not feedback: a blank body (an Approve click with no text), a
    body with the agent-disclosure marker, a bare grant or approval, and an
    agent's head review. A payload without `commits` reports nothing, as
    before; the real fetch always supplies it.
    """
    commits = pr_data.get("commits") or []
    if not commits or not commits[-1].get("committedDate"):
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
    mine = []
    for kind, author, when, body in items:
        login = ((author or {}).get("login") or "").lower().removesuffix("[bot]")
        if login in logins:
            mine.append((kind, login, when or "", body or ""))
    last_reply = max(
        (when for _, _, when, body in mine
         if AGENT_REPLY_RE.search(body) and not REVIEW_COMMENT_RE.search(body)),
        default="")
    found = []
    for kind, login, when, body in mine:
        if when < last_reply:
            continue
        text = body.strip()
        if not text or AGENT_AUTHORSHIP_RE.search(body) or EXEMPT_RE.fullmatch(text) \
                or REVIEW_COMMENT_RE.search(body):
            continue
        found.append(f"{kind} by {login} at {when}")
    return found
