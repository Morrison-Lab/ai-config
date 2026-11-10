#!/usr/bin/env python3
"""PreToolUse deny: `gh api -X PATCH` on a comment id overwrites the comment.

ai-config#1152. Replying to a review comment and editing one are two routes
on the same comment id:

    # REPLY: adds alongside theirs (the PR number is in the path)
    gh api -X POST repos/<o>/<r>/pulls/<N>/comments/<id>/replies -F body=@f
    # EDIT: overwrites theirs (no PR number)
    gh api -X PATCH repos/<o>/<r>/pulls/comments/<id> -F body=@f

On Morrison-Lab/ai-config#1151 the PATCH form was used to "reply" to five
claude[bot] findings and replaced all five. Each call returned success,
because success is what an overwrite looks like on a repo with write access,
and the REST surface has no edit-history read, so a restore cannot be diffed.

Why a deny and not a warning: the action is silent, destructive and not fully
recoverable, and the condition is decidable from the command text alone (no
network call, no authorship lookup, which would fail open). The measured
false-positive surface in the issue is zero: the one legitimate
PATCH-on-a-comment-id use (a sticky comment) runs inside a workflow step, not
a local Bash call. A deliberate edit of your own comment is cleared with an
`ALLOW_COMMENT_PATCH=1` prefix on that command.

Scope: `pulls/comments/<id>` and `issues/comments/<id>`, both the same
hazard. Only a segment whose command word is `gh api` is read, so a commit
message or a heredoc that merely quotes the command never fires. Fails open
on any parse trouble.
"""
import json
import re
import shlex
import sys

OVERRIDE = "ALLOW_COMMENT_PATCH"
SEGMENT_SPLIT = re.compile(r"&&|\|\||[;|\n]")
COMMENT_PATH = re.compile(r"/?repos/[^/\s]+/[^/\s]+/(?:pulls|issues)/comments/\d+(?:$|[?#])")
ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

REASON = """\
[hook: no-patch-comment-id] `gh api -X PATCH` on a comment id OVERWRITES \
that comment (ai-config#1152; on #1151 it replaced five claude[bot] \
findings, and the REST surface exposes no edit history to restore from).
To REPLY to a review comment, POST to the replies route, which has the PR \
number in the path:
  gh api -X POST repos/<owner>/<repo>/pulls/<N>/comments/<id>/replies -F body=@<file>
To post a new comment on the PR thread, use `gh pr comment` or \
`add_issue_comment`.
If you really are editing your OWN comment, prefix this command with \
`ALLOW_COMMENT_PATCH=1`."""


def patches(argv):
    """True when argv (after `gh api`) asks for the PATCH method."""
    for i, tok in enumerate(argv):
        low = tok.lower()
        if low in ("-x", "--method"):
            if i + 1 < len(argv) and argv[i + 1].upper() == "PATCH":
                return True
        elif low.startswith("--method="):
            if tok.split("=", 1)[1].upper() == "PATCH":
                return True
        elif low.startswith("-x") and len(tok) > 2 and tok[2:].upper() == "PATCH":
            return True
    return False


def offending(command):
    """True when some segment is an un-overridden PATCH on a comment id."""
    for segment in SEGMENT_SPLIT.split(command):
        try:
            argv = shlex.split(segment)
        except ValueError:
            continue
        overridden = False
        while argv and ENV_ASSIGN.match(argv[0]):
            if argv[0] == OVERRIDE + "=1":
                overridden = True
            argv = argv[1:]
        if len(argv) < 2 or argv[0] != "gh" or argv[1] != "api":
            continue
        args = argv[2:]
        if overridden or not patches(args):
            continue
        if any(COMMENT_PATH.search(a) for a in args):
            return True
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return 0
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not offending(command):
        return 0
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": REASON,
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
