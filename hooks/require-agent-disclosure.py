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
  * The body is not always visible. `--body-file`, `--editor`, `-F <file>` and
    `$VAR` expansion all put the text somewhere a literal scan cannot read, so
    the check decides the question only for the inline-literal case. A deny
    built on a check that sees a fraction of its population would refuse
    compliant commands, which is why this stays advisory. (The kindred
    incident in `README.md`'s hook section is the opposite shape: an early
    `require-gh-repo-flag.py` matched too MUCH, firing on a heredoc that merely
    documented a gated command. Both directions end in a guard that refuses
    correct work; they arrive by different routes.)

MARKER, not emoji. The disclosure marker deliberately avoids the robot emoji:
`scripts/check-pr-fully-clean.py` matches that emoji as a `REVIEW_BODY_MARKERS`
entry, so a disclosed claim comment would be admitted into the fully-clean
verdict scan as a finding-free review. This hook therefore looks for the prose
marker and, separately, points out a body that discloses with the emoji.

EXEMPT: a body whose WHOLE content is a command addressed to another bot
(`@dependabot rebase`, the review re-request `ardi` mandates). The test is the
audience -- a machine parses that body -- not the length, so the pattern is
anchored to the whole body rather than to its first token.

PER SEGMENT, not per call. A batched round posting several comments in one
Bash call is the encouraged shape (`shared/workflow/efficient-pr-babysitting.md`),
so one disclosed body must not vouch for an undisclosed sibling. Each
command-position segment is judged on its own text.

Covers the Bash CLI forms and the `mcp__github__*` comment tools, since a
remote/web session has no `gh` at all and MCP is its only path there
(`CLAUDE.md`, "Skills that call gh/glab: fall back to tool-mappings.md").
That second half needs a SECOND registration: `hooks.json` matches hooks by
tool name, so an entry under `Bash` alone never reaches an MCP call however
many MCP tool names this file lists.

Fails OPEN: any parse problem returns 0 with no output.
"""
import json
import re
import sys

# --- what counts as posting a comment ---------------------------------------
#
# ANCHORED at a command position -- start of string, after a separator, or after
# a shell keyword that introduces a command. Unanchored, this fires on every
# reply and every doc that merely QUOTES the command, and this corpus quotes it
# constantly (`shared/workflow/claim-pr.md` is nothing but such quotes).
_ANCHOR = (
    r"(?:^|[;&|\n({`]|\b(?:then|else|elif|do|if|while|until)\s|!\s*)\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
)

# The named CLI verbs, where the command word alone settles it.
_POST_CMDS = (
    r"gh\s+pr\s+comment",
    r"gh\s+issue\s+comment",
    # A review needs a BODY flag to be a comment. `gh pr review 12 --approve`
    # posts no prose, so there is nothing to disclose and warning on it spends
    # the guard's credibility on a command it cannot be about.
    # NOT gated on a body flag by a lookahead here. The obvious spelling,
    # `(?=[^\n;|&]*--body...)`, carries the exact bound this file's own
    # `is_api_post` docstring diagnoses two blocks below: it cannot cross the
    # backslash line-continuation that `skills/ard` uses for every long command,
    # so a review whose body flag sits on a continuation line went SILENT.
    # The body-flag test is applied per segment in `is_post_segment` instead,
    # where the whole command is already in hand.
    r"gh\s+pr\s+review\b",
    # `glab ... comment` is a real alias of `... note`; both spellings ship.
    r"glab\s+mr\s+(?:note|comment)",
    r"glab\s+issue\s+(?:note|comment)",
)
POST_RE = re.compile(_ANCHOR + r"(?:" + "|".join(_POST_CMDS) + r")", re.MULTILINE)

# The raw-API routes need a TWO-PART test rather than one regex spanning the
# gap between their parts.
#
# A single pattern was tried twice and failed twice. `[^\n;|&]*` cannot cross the
# backslash line-continuation every review-thread reply in `skills/ard` uses.
# Widening it to `[^;&]{0,400}?` put the COMMENT BODY inside the gap, so an
# ordinary semicolon in the prose, or a body over 400 characters, made the
# detector silent -- on exactly the longer, more human-looking replies the rule
# is for. Both times the fixture was short and punctuation-free and passed.
#
# So test the parts independently over the whole segment, which the quote-aware
# splitter has already bounded to one command. Order-independent by
# construction, which also fixes `gh api -f body=... <url>`.
API_CMD_RE = re.compile(_ANCHOR + r"(?:gh|glab)\s+api\b", re.MULTILINE)
# A body-supplying field is what separates a POST from the review-READ that
# `CLAUDE.md` prescribes and every ARDI round runs.
# The optional quote is load-bearing: `tool-mappings`'s own canonical reply
# command is `-F "body=@<file>"`, quote first, and this corpus writes the
# quoted-whole-argument spelling for sibling flags too
# (`request-pr-review`'s `-f "reviewers[]=<r>"`). Without it the registry line
# this change annotates was completely invisible to the guard.
API_BODY_FIELD_RE = re.compile(r"(?:-f|-F|--field|--raw-field)\s+[\"']?body=")
# The comment-bearing endpoints, and the GraphQL comment mutations.
# No `/replies` alternative. GitHub's reply route is
# `POST /repos/{o}/{r}/pulls/{n}/comments/{id}/replies`, so it always contains
# `/comments` -- the alternative could never fire alone, which is why no fixture
# could isolate it and why two attempts at one were masked by their own paths.
# An untestable alternative also implies a route that does not exist.
API_COMMENT_TARGET_RE = re.compile(
    r"/comments|/notes|/discussions"
    r"|addDiscussionComment|addComment", re.IGNORECASE)


def is_api_post(segment):
    """True when this segment posts a comment through a raw forge API."""
    if not API_CMD_RE.search("\n" + segment):
        return False
    if not API_COMMENT_TARGET_RE.search(segment):
        return False
    # A GraphQL comment mutation may carry its body inside the query text or in
    # an `--input` file rather than in a `body=` field, so the field test alone
    # would miss it. The earlier version of this branch keyed on the mutation
    # NAME alone, which classified `gh api graphql --input p.json  # addDiscuss-
    # ionComment payload` -- a comment about a payload -- as a post.
    # `mutation` beside the name is what separates executing one from naming one.
    if (re.search(r"\bmutation\b", segment)
            and re.search(r"addDiscussionComment|addComment", segment,
                          re.IGNORECASE)):
        return True
    return bool(API_BODY_FIELD_RE.search(segment))


# A review with no body flag posts no prose (`gh pr review 12 --approve`), so
# there is nothing to disclose. Tested over the whole segment rather than in a
# lookahead, so a continuation line cannot hide the flag.
REVIEW_ONLY_RE = re.compile(_ANCHOR + r"gh\s+pr\s+review\b", re.MULTILINE)
ANY_BODY_FLAG_RE = re.compile(
    r"--body\b|--body=|--body-file|--message\b|--message=|-b\s|-m\s|-F\s"
    r"|(?:-f|-F|--field|--raw-field)\s+[\"']?body=")


def is_post_segment(segment):
    """True when this segment posts a forge comment by any route."""
    if POST_RE.search("\n" + segment):
        # `gh pr review` is the one named verb that may carry no body at all.
        if (REVIEW_ONLY_RE.search("\n" + segment)
                and not ANY_BODY_FLAG_RE.search(segment)):
            return False
        return True
    return is_api_post(segment)


# Segment boundaries, split QUOTE-AWARE.
#
# A plain `re.split(r"[;&|\n]+", ...)` looked adequate and was not: the marker
# sits on its own line at the END of a body, so splitting on every newline cuts
# the marker off the very command it discloses, and every correctly-disclosed
# multi-line comment -- the normal shape -- warns. Tracking quote state is the
# minimum needed to keep a body intact. It is still not a shell parser; an
# unbalanced quote degrades to treating the remainder as quoted, which merges
# segments and can only silence a warning, never invent one.
SEG_SEPARATORS = ";&|\n"

# A heredoc body is prose when it is being WRITTEN and is the comment body when
# it is being PIPED (`--body-file -`, `$(cat <<EOF)`). So it is stripped for
# ANCHORING -- otherwise a doc-writing heredoc quoting `gh pr comment` fires --
# and kept for the MARKER test, where it may be the very text that discloses.
HEREDOC_RE = re.compile(
    r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?([^\n]*)\n"
    r".*?\n[ \t]*\1\b",
    re.DOTALL,
)

# The required marker, matched loosely enough to survive an agent-name swap
# ("Posted by Codex (AI agent) ...") but tightly enough not to match prose that
# merely mentions agents.
MARKER_RE = re.compile(r"posted by .{0,40}\(ai agent\)", re.IGNORECASE)

ROBOT = "\U0001f916"
# Only a body that both carries the emoji AND reads as an attribution is
# disclosing with the wrong marker. A body merely MENTIONING the emoji
# ("the robot badge broke") discloses nothing, and telling its author to swap
# markers would replace the one applicable instruction with an inapplicable one.
# `\b` on both sides: without it "CI regenerated the snapshots" and "badge
# rewritten" matched, and because this branch returns before MISSING, a body
# that carried the emoji incidentally AND omitted the marker was told to swap
# markers rather than to add one -- the inapplicable advice this branch exists
# to avoid giving.
_ATTRIB = r"\b(?:posted|generated|written|authored)\b"
EMOJI_DISCLOSURE_RE = re.compile(
    ROBOT + r"[^\n]{0,80}" + _ATTRIB + r"|" + _ATTRIB + r"[^\n]{0,80}" + ROBOT,
    re.IGNORECASE,
)

# A body this check cannot read. `-F` is `gh pr comment`'s own shorthand for
# `--body-file` (`gh pr comment --help`), NOT `gh api`'s `-F body=@` -- two
# different flags spelled alike, so both shapes are listed rather than one
# being assumed to cover the other.
UNREADABLE_RE = re.compile(
    r"--body-file|--description-file|--editor\b|--web\b"
    # `-F <file>` is gh pr comment's own body-file shorthand. Matched as a token
    # with NO `=` in it, rather than by a negative lookahead after an optional
    # quote: the optional quote gave the engine a backtracking path where it
    # skipped the quote, failed to find `key=` starting at `"`, and so satisfied
    # the negation -- which made `-F "in_reply_to=5"` look like a file.
    r"|(?<!-)-F\s+[\"']?[^\s\"'=]+[\"']?(?:\s|$)"
    r"|--(?:body|message)[\s=]+(?:\"[^\"]*\$|'[^']*\$|\$)"
    # NOTE: the short `-b`/`-m` forms need no clause of their own. They fall
    # through to the `not HAS_INLINE_BODY_RE` branch, which already rejects a
    # value beginning with `$`. A separate alternative here was dead code whose
    # comment described a behaviour the pattern below had taken over.
    # `@file` is gh api's read-from-file sigil, and it is routinely QUOTED
    # (`-F body="@/tmp/reply.md"`), so the optional quote is load-bearing.
    r"|(?:-f|-F|--field|--raw-field)\s+[\"']?body=[\"']?(?:@|\$)"
    r"|(?:-f|-F|--field|--raw-field)\s+[\"']?body=(?:[^\"'\s]*\$)"
)
# A body flag with an inline literal value. Its absence on an interactive
# invocation means there is no body to read here at all.
# Every spelling `_POST_CMDS` accepts must appear here too, or a body sitting in
# plain sight is reported as one the check could not read -- the weaker note,
# which invites no correction. `-F body=` and `--raw-field body=` were accepted
# as posting routes and omitted here, so they drew exactly that.
HAS_INLINE_BODY_RE = re.compile(
    r"--(?:body|message)[\s=]+[\"']?[^\s\"'$]|-(?:b|m)\s+[\"']?[^\s\"'$]"
    r"|(?:-f|-F|--field|--raw-field)\s+[\"']?body=")

# Whole-body commands addressed to another bot. Anchored to the WHOLE body:
# `[^"']*` after the handle would swallow unbounded prose, exempting a comment
# that merely opens with a bot handle and then addresses a human at length.
#
# The review-re-request handle is assembled rather than written contiguously.
# `memories/mention-triggers.md`: the gate is a raw substring test over text
# GitHub renders, and a diff view renders this file -- so spelling it here
# would summon the bot from a source file.
_BOT_HANDLES = "|".join(["dependabot", "renovate", "copilot", "cl" + "aude"])
# The `\1` closing quote ends it -- NOT `$`. Anchoring to end-of-segment
# required `--body` to be the last flag, so the corpus's own two Dependabot
# sites both warned: `gh pr comment "$N" --repo "$REPO" --body "@dependabot
# rebase"   # COMMENT_PR` has a trailing comment, and `--body "..." --repo o/r`
# has a trailing flag. Acting on that warning would mean appending prose to a
# body Dependabot parses, which is the harm the exemption exists to avoid.
BOT_COMMAND_RE = re.compile(
    r"--(?:body|message)\s+([\"'])\s*@(?:" + _BOT_HANDLES + r")\b"
    r"[ \w-]{0,40}\s*\1",
    re.IGNORECASE,
)

# The same exemption tested against a RAW body, with no shell syntax around it.
# `verdict_mcp` used to synthesize `--body "<body>"` so it could reuse the
# shell-shaped pattern below; a `"` inside the body then closed that synthetic
# argument early, and `@dependabot rebase" and a long note for the humans ...`
# took the exemption. Reconstructing syntax to reuse a matcher is what reopened
# a hole the Bash path had a fixture against.
BOT_BODY_RE = re.compile(
    r"^\s*@(?:" + _BOT_HANDLES + r")\b[ \w-]{0,40}\s*$", re.IGNORECASE)


# MCP comment-posting tools.
#
# NOT derived from `tool-mappings.yml`, and the earlier claim that it named four
# of these was a miscount: that registry maps OPERATIONS, and `add_issue_comment`
# appears under two of them (COMMENT_PR and COMMENT_ISSUE), so counting rows
# double-counts one tool. It names two of the five --- `add_issue_comment` and
# `add_reply_to_pull_request_comment` --- plus COMMENT_DISCUSSION, whose row said
# no MCP tool existed until this change corrected it. `pull_request_review_write`
# and `add_comment_to_pending_review` have no operation of their own.
#
# So this list is wider than the registry by construction. Re-derive it against
# the server's tool list rather than against that file.
MCP_POST_TOOLS = (
    "mcp__github__add_issue_comment",
    "mcp__github__add_comment_to_pending_review",
    "mcp__github__add_reply_to_pull_request_comment",
    "mcp__github__pull_request_review_write",
    "mcp__github__discussion_comment_write",
)

MARKER_TEXT = "_Posted by Claude Code (AI agent) --- not written by a human._"
SEE = "See shared/workflow/disclose-agent-authorship.md."

MISSING = (
    "This posts a forge comment with no agent-disclosure marker. A comment "
    "posted through `gh`/`glab` carries the account holder's own login and "
    "reads as `type: User`, so nothing distinguishes it from one they typed. "
    "End the body with:\n\n    " + MARKER_TEXT + "\n\n"
    "Exempt: a body that is wholly a command to another bot "
    "(`@dependabot rebase`). " + SEE
)
UNREADABLE = (
    "This posts a forge comment whose body this check cannot read (it comes "
    "from a file, an editor, or a variable). Confirm the body ends with the "
    "agent-disclosure marker:\n\n    " + MARKER_TEXT + "\n\n" + SEE
)
EMOJI = (
    "This forge comment discloses with the robot emoji. Use the prose marker "
    "instead:\n\n    " + MARKER_TEXT + "\n\n"
    "scripts/check-pr-fully-clean.py matches the robot emoji as a "
    "REVIEW_BODY_MARKERS entry, so a comment carrying it is admitted into the "
    "fully-clean verdict scan as a review -- and a claim or status comment "
    "carries no findings, so it scans as a CLEAN one. " + SEE
)


def split_segments(text):
    """Split on shell separators that are OUTSIDE quotes."""
    segments, current = [], []
    quote = None
    ansi_c = False
    escaped = False
    prev = ""
    for ch in text:
        prev_ch = prev
        prev = ch
        if escaped:
            current.append(ch)
            escaped = False
            continue
        # A plain '...' takes no escapes; ANSI-C $'...' does. Treating the
        # latter as the former read `$'don\'t'` as closed and split the rest of
        # the body on its newlines, cutting the marker off its own command.
        if ch == "\\" and (quote != "'" or ansi_c):
            current.append(ch)
            escaped = True
            continue
        if quote:
            current.append(ch)
            if ch == quote:
                quote = None
                ansi_c = False
            continue
        if ch in "\"'":
            quote = ch
            ansi_c = ch == "'" and prev_ch == "$"
            current.append(ch)
            continue
        if ch in SEG_SEPARATORS:
            segments.append("".join(current))
            current = []
            continue
        current.append(ch)
    segments.append("".join(current))
    return segments


# Placeholder standing in for a heredoc body. Carries no shell separator, so it
# survives segmentation intact and keeps its body attached to the ONE segment
# that opened it.
SLOT = "\x00HEREDOC{}\x00"
SLOT_RE = re.compile(r"\x00HEREDOC(\d+)\x00")


def strip_heredocs(command):
    """Remove heredoc BODIES, keeping the opener tail and a body placeholder.

    Only the body is prose. The opener line's tail is still shell and routinely
    carries the very command being looked for -- piping a heredoc into
    `--body-file -` is the idiomatic way to post a multi-line body. Same
    reasoning, and the same lesson, as `warn-pr-create-without-dupe-check.py`.

    Returns (stripped_text, bodies). A plain strip was not enough: the body a
    segment consumes has to stay attached to THAT segment, or a doc-writing
    heredoc quoting the marker vouches for a bare comment elsewhere in the call.
    Dropping `<<` along with the body also erased the only signal that a segment
    had a heredoc at all, so the placeholder carries it.
    """
    bodies = []

    def take(m):
        bodies.append(m.group(0))
        return m.group(2) + " " + SLOT.format(len(bodies) - 1)

    return HEREDOC_RE.sub(take, command), bodies


def bodies_for(segment, bodies):
    """The heredoc bodies this segment actually opened."""
    return "\n".join(bodies[int(i)] for i in SLOT_RE.findall(segment)
                      if int(i) < len(bodies))


def judge_segment(segment, extra):
    """Return a warning for one command-position segment, or None.

    `extra` is supplied ONLY when this segment actually references a heredoc.
    Passing every heredoc body to every segment let a doc-writing heredoc that
    merely QUOTED the marker vouch for a bare comment posted later in the same
    call -- which is exactly the per-segment property this function exists to
    provide, defeated by the argument meant to support it.
    """
    text = segment + "\n" + extra
    if BOT_COMMAND_RE.search(segment):
        return None
    if MARKER_RE.search(text):
        return None
    if EMOJI_DISCLOSURE_RE.search(text):
        return EMOJI
    # A heredoc body we actually READ settles it: the body is in hand and
    # carries no marker, so this is a missing marker rather than an unseen one.
    # `--body-file -` is unreadable BY FLAG and readable in fact when its stdin
    # is the heredoc, and reporting "cannot read" over a body just read is the
    # same misdiagnosis the `-F <file>` case produced.
    if extra:
        return MISSING
    if UNREADABLE_RE.search(segment) or not HAS_INLINE_BODY_RE.search(segment):
        return UNREADABLE
    return MISSING


def verdict_bash(command):
    """Return a warning string for a Bash command, or None."""
    stripped, bodies = strip_heredocs(command)
    if not any(is_post_segment(seg) for seg in split_segments(stripped)):
        return None
    warnings = []
    for segment in split_segments(stripped):
        if not is_post_segment(segment):
            continue
        # A heredoc body IS this segment's comment body only when this segment
        # opened it. Elsewhere it is somebody else's prose.
        found = judge_segment(segment, bodies_for(segment, bodies))
        if found and found not in warnings:
            warnings.append(found)
    if not warnings:
        return None
    return "\n\n".join(warnings)


def verdict_mcp(tool_name, tool_input):
    """Return a warning string for an MCP comment tool, or None."""
    if tool_name not in MCP_POST_TOOLS:
        return None
    body = tool_input.get("body")
    if not isinstance(body, str):
        # `pull_request_review_write` submits without a body on some methods,
        # and a body we never saw is not a body we can judge.
        return None
    if BOT_BODY_RE.match(body):
        return None
    if MARKER_RE.search(body):
        return None
    if EMOJI_DISCLOSURE_RE.search(body):
        return EMOJI
    return MISSING


def verdict(command):
    """Bash-only entry point, kept for the test suite and for callers."""
    return verdict_bash(command)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0
    if tool_name == "Bash":
        reason = verdict_bash(tool_input.get("command") or "")
    else:
        reason = verdict_mcp(tool_name, tool_input)
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
            "as `type: User`. " + SEE
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
