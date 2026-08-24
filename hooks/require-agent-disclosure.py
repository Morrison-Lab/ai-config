#!/usr/bin/env python3
"""PreToolUse guard: a forge comment an agent posts must disclose that it did.

A comment posted through `gh`/`glab` under the account holder's credentials
carries THEIR login, avatar and `MEMBER` association, and reads as
`type: User` -- so nothing in the API distinguishes it from a comment they
typed. `memories/github.md` records auditors making exactly that mistake. The
forge cannot say it; the body has to.

See `shared/workflow/disclose-agent-authorship.md` for the rule and the marker.

WARNS, never blocks. Two reasons, and the second is the load-bearing one:

  * A missing disclosure is cheap to repair with a follow-up comment, while a
    blocked `gh pr comment` interrupts the one action that makes a claim
    visible to other sessions -- which is the collision the claim convention
    exists to prevent. Blocking would trade a labelling defect for a
    correctness one.
  * The body is not always in the command. `--body-file`, `-F body=@file` and
    `$VAR` expansion all put the text somewhere this hook cannot read, so a
    literal scan cannot decide the question -- it can only decide it for the
    inline-literal case. A deny built on a check that sees a fraction of its
    population would refuse compliant commands, which is the failure
    `require-gh-repo-flag.py` shipped and had to fix.

MARKER, not emoji. The disclosure marker deliberately avoids the robot emoji:
`scripts/check-pr-fully-clean.py` matches that emoji as a `REVIEW_BODY_MARKERS`
entry, so a disclosed claim comment would be admitted into the fully-clean
verdict scan as a finding-free review. This hook therefore looks for the prose
marker and, separately, warns when a body discloses using the emoji instead.

EXEMPT: a body whose whole content is a command addressed to another bot
(`@dependabot rebase`). The test is the audience -- a machine parses that body
-- not the length.

Fails OPEN: any parse problem returns 0 with no output.
"""
import json
import re
import sys

# Commands that post a comment body a human will read.
#
# ANCHORED at a command position -- start of string, or after a newline, pipe,
# semicolon, `&&`, `||` or an opening paren. Unanchored, this fires on every
# reply and every doc that merely QUOTES the command, and this corpus quotes it
# constantly (`shared/workflow/claim-pr.md` is nothing but such quotes). That is
# the failure `require-gh-repo-flag.py` shipped with and had to fix, recorded in
# README's hook section as the cautionary example.
COMMENT_COMMANDS = (
    r"gh\s+pr\s+comment",
    r"gh\s+issue\s+comment",
    r"gh\s+pr\s+review\b",
    r"glab\s+mr\s+note",
    r"glab\s+issue\s+note",
)
COMMENT_RE = re.compile(
    r"(?:^|[\n;|&(]|&&|\|\|)\s*(?:" + "|".join(COMMENT_COMMANDS) + r")")

# A heredoc means the command is WRITING text, not running it -- so a quoted
# example inside it is documentation. Erring toward silence here is the safe
# direction for a warn-only guard whose backstop is the written rule.
HEREDOC_RE = re.compile(r"<<-?\s*['\"]?\w+")

# The required marker, matched loosely enough to survive an agent-name swap
# ("Posted by Codex (AI agent) ...") but tightly enough not to match prose that
# merely mentions agents.
MARKER_RE = re.compile(r"posted by .{0,40}\(ai agent\)", re.IGNORECASE)

ROBOT = "\U0001f916"

# A body we cannot see: the text lives in a file, or the body flag's own value
# interpolates a variable. Narrowed to the BODY specifically -- a `$N` in the PR
# number says nothing about whether the body discloses, and treating it as
# unreadable would report "cannot read" over a body sitting in plain sight.
INDIRECT_RE = re.compile(
    r"--body-file|--description-file|-F\s+body=@"
    r"|--(?:body|message)\s+(?:\"[^\"]*\$|'[^']*\$|\$)")

# Whole-body commands addressed to another bot.
BOT_COMMAND_RE = re.compile(
    r"""--(?:body|message)\s+(["'])@(?:dependabot|renovate|copilot)\b[^"']*\1""",
    re.IGNORECASE,
)


def verdict(command: str):
    """Return a warning string, or None when the command is fine or unreadable."""
    if not COMMENT_RE.search(command):
        return None
    if HEREDOC_RE.search(command):
        return None
    if BOT_COMMAND_RE.search(command):
        return None
    # The marker is checked BEFORE the unreadable-body test: a command can name
    # a variable elsewhere (`gh pr comment "$N" --body "...marker..."`) and still
    # carry a body in plain sight, and reporting that as unreadable would be a
    # warning about the wrong thing.
    if MARKER_RE.search(command):
        return None
    if INDIRECT_RE.search(command):
        # Cannot see the body. Say so rather than guessing either way.
        return (
            "This command posts a forge comment whose body this check cannot "
            "read (it comes from a file or a variable). Confirm the body ends "
            "with the agent-disclosure marker:\n\n"
            "    _Posted by Claude Code (AI agent) --- not written by a human._\n\n"
            "See shared/workflow/disclose-agent-authorship.md."
        )
    if ROBOT in command:
        return (
            "This forge comment discloses with the robot emoji. Use the prose "
            "marker instead:\n\n"
            "    _Posted by Claude Code (AI agent) --- not written by a human._\n\n"
            "scripts/check-pr-fully-clean.py matches the robot emoji as a "
            "REVIEW_BODY_MARKERS entry, so a comment carrying it is admitted "
            "into the fully-clean verdict scan as a review -- and a claim or "
            "status comment carries no findings, so it scans as a CLEAN one."
        )
    return (
        "This command posts a forge comment with no agent-disclosure marker. "
        "A comment posted through `gh`/`glab` carries the account holder's own "
        "login and reads as `type: User`, so nothing distinguishes it from one "
        "they typed. End the body with:\n\n"
        "    _Posted by Claude Code (AI agent) --- not written by a human._\n\n"
        "Exempt: a body that is wholly a command to another bot "
        "(`@dependabot rebase`). See "
        "shared/workflow/disclose-agent-authorship.md."
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    reason = verdict(command)
    if not reason:
        return 0
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": reason,
        },
        # Surfaced to the USER as well, not only to the model: whether a comment
        # posted under their account discloses its authorship is their call to
        # see being made, and a model-only warning leaves them unaware it fired.
        "systemMessage": (
            "This forge comment may not disclose that an agent posted it. "
            "Comments posted through `gh`/`glab` carry your own login and read "
            "as `type: User`. See "
            "shared/workflow/disclose-agent-authorship.md."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
