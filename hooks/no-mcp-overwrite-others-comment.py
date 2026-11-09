#!/usr/bin/env python3
"""PreToolUse deny: `mcp__github__update_issue_comment` on someone else's comment.

ai-config#5153, the MCP counterpart of no-patch-comment-id.py (#1152).
That hook reads `gh api -X PATCH` command text; this tool edits an
`issues/comments/<id>` comment through a tool call, so it never reaches it.

Why a lookup here, unlike #1152: the tool legitimately edits the agent's own
status comments, so a blanket deny would be unusable. Whether the comment is
yours is not in the tool input, so the hook asks GitHub for the comment's
author and the authenticated login and DENIES when they differ.
Comments the agent posts carry the account holder's login, so this cannot
tell an agent's comment from a human's, only yours from someone else's, such
as a claude[bot] review. That is the case #1151 overwrote.

Fails open when either lookup fails (no gh, no access, no network): an
unverifiable author is not evidence of someone else's comment.
`ALLOW_COMMENT_PATCH=1` in the hook's environment clears it.
"""
import json
import os
import subprocess
import sys

TOOL = "mcp__github__update_issue_comment"
OVERRIDE = "ALLOW_COMMENT_PATCH"

REASON = """\
[hook: no-mcp-overwrite-others-comment] `{tool}` REPLACES comment {cid} on \
{owner}/{repo}, which was written by `{author}`, not by the authenticated \
account `{me}` (ai-config#5153; the same overwrite as #1151, which replaced \
five claude[bot] findings with no edit history to restore from).
To reply instead, post a new comment (`add_issue_comment`) or, for a review \
comment, `add_reply_to_pull_request_comment`.
If you really mean to edit it, set `ALLOW_COMMENT_PATCH=1` for the session."""


def gh_login(args):
    """Return the login printed by `gh api <args> --jq .<field>`, else None."""
    try:
        r = subprocess.run(["gh", "api", *args], capture_output=True,
                           text=True, timeout=8)
    except (OSError, subprocess.SubprocessError):
        return None
    out = r.stdout.strip()
    return out if r.returncode == 0 and out else None


def lookup(owner, repo, cid):
    """Return (comment author, authenticated login); either may be None."""
    author = gh_login([f"repos/{owner}/{repo}/issues/comments/{cid}",
                       "--jq", ".user.login"])
    me = gh_login(["user", "--jq", ".login"])
    return author, me


def denial(payload, look=lookup):
    """Return the deny reason for an update of another login's comment."""
    if payload.get("tool_name") != TOOL or os.environ.get(OVERRIDE) == "1":
        return None
    args = payload.get("tool_input")
    if not isinstance(args, dict):
        return None
    owner, repo = args.get("owner"), args.get("repo")
    cid = args.get("comment_id", args.get("commentId"))
    if not (isinstance(owner, str) and isinstance(repo, str) and cid):
        return None
    author, me = look(owner, repo, cid)
    if not author or not me or author.lower() == me.lower():
        return None
    return REASON.format(tool=TOOL, cid=cid, owner=owner, repo=repo,
                         author=author, me=me)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    reason = denial(payload)
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
