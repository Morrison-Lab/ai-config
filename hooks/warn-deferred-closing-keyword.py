#!/usr/bin/env python3
"""PreToolUse reminder: a closing keyword next to #N inside a deferring or
negating sentence.

`shared/workflow/issue-first.md`'s "A closing keyword plus #N closes #N even
when the sentence negates it" states the hazard. GitHub scans a PR body and a
commit message for `close/closes/closed/fix/fixes/fixed/resolve/resolves/
resolved` followed by an issue reference and closes the target on merge. The
parser is purely lexical: it reads neither negation, nor tense, nor the rest of
the sentence.

WHY A HOOK RATHER THAN THE RULE ALONE
-------------------------------------
Three occurrences, which is `shared/principles/deterministic-tools.md`'s bar.

ai-config#1718's squash commit closed #1717 through a negated sentence, and
that occurrence produced the prose rule. Morrison-Lab/gha#460 then closed #322
with `I have not closed #322 --- items 1, 3, 4, and 5 remain open there.`
ucdavis/bcs#982 closed #923 with a sentence promising a LATER pull request
would do it:

    ... follow in a data PR that closes #923.

The third is the shape the rule does not name. It carries no negation at all,
so a reader checking the rule sees "even when the sentence negates it" and
correctly concludes the rule is about something else. The author of that body
was demonstrably thinking about closing keywords --- the same pull request's
title reads `(refs #923)` --- and wrote the hazard one paragraph away, which is
the read-time-versus-composition-time gap `shared/workflow/algorithmatize-
checks.md` says to mechanize rather than restate.

Nothing downstream reports it either. The merge succeeds, the issue closes with
`stateReason=COMPLETED`, and the timeline's `closed` event carries no commit
id --- so a keyword close and a deliberate manual close are indistinguishable
afterwards. In the bcs case the mistake surfaced two days later, by accident.

THE CHECK
---------
Extract the body text a command or MCP call is about to send, then warn when a
closing keyword sits next to an issue reference AND BOTH of:

* the match does not begin its line. The idiomatic intentional form is a line
  reading `Closes #N`, so a match at the start of a line (after optional
  whitespace and an optional list marker) is presumed deliberate.
* the sentence containing the match carries a deferral or negation cue.

Requiring both is what keeps the reminder quiet. A body whose only closing
keyword is a bare `Closes #N` line never fires; nor does an ordinary
mid-sentence `this closes #123` with no cue in it.

Body sources, in the order they occur in practice: an inline `--body` /
`--body-file` argument, a `-F body=@<file>` / `-f body=` argument, a heredoc,
and the MCP tools' `body` field. A `--body-file` path is read when it is
readable; an unreadable one yields no body rather than an error.

WHY WARN RATHER THAN BLOCK
--------------------------
The guard cannot read intent, and a closing keyword in a deferring sentence is
occasionally what the author means --- "this supersedes and closes #4" reads as
a deferral cue to a lexical matcher. A blocked `gh pr create` is expensive,
since the pull request is the artifact that makes work visible, while the
remedy here costs one word: write `Refs #N`, or move the number off the
keyword.

FAILS OPEN
----------
Any parse trouble, an unrecognized payload shape, an unreadable body file, or a
missing command returns 0 silently.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys

# GitHub's own keyword set, per its documentation on linking a pull request to
# an issue. Matched case-insensitively, as GitHub matches it.
CLOSING_KEYWORDS = (
    "close", "closes", "closed",
    "fix", "fixes", "fixed",
    "resolve", "resolves", "resolved",
)

# A keyword, then optional punctuation and whitespace, then an issue reference:
# `#12`, `owner/repo#12`, or a full issue URL. GitHub allows a colon between
# them, which is why the separator class is not whitespace alone.
RX_CLOSING_REF = re.compile(
    r"\b(" + "|".join(CLOSING_KEYWORDS) + r")\b[ \t:]*"
    r"(?:(?:https?://\S*?/issues/\d+)|(?:[\w.-]+/[\w.-]+)?#\d+)",
    re.IGNORECASE,
)

# Cues that the sentence is about someone else closing the issue, or about not
# closing it. `will` and `follow` cover the deferral shape; the rest cover
# negation and postponement.
DEFERRAL_CUES = (
    "not", "n't", "never", "without",
    "later", "future", "eventually", "subsequent", "subsequently",
    "follow", "follows", "following", "follow-up", "followup",
    "will", "would", "shall",
    "rather than", "instead", "once", "after", "pending",
    "another", "separate", "second",
)

RX_CUE = re.compile(
    r"(?:" + "|".join(
        cue if " " in cue or cue.startswith("n'") else r"\b" + cue + r"\b"
        for cue in DEFERRAL_CUES
    ) + r")",
    re.IGNORECASE,
)

# A list marker or blockquote may precede a deliberate `Closes #N` line.
RX_LINE_LEAD = re.compile(r"^[ \t]*(?:[-*+]\s+|>\s*|\d+[.)]\s+)?$")

BASH_TOOLS = ("Bash", "bash", "run_command", "execute_command", "terminal", "shell")

# Only a pull-request DESCRIPTION, an issue DESCRIPTION, or a commit message
# is scanned by GitHub's closing-keyword parser. A plain comment is not, so a
# comment-posting tool is deliberately absent here: warning there would assert
# something false. The Bash path excludes `gh pr comment` / `gh issue comment`
# and the comments REST endpoints for the same reason.
MCP_BODY_TOOLS = (
    "mcp__github__create_pull_request",
    "mcp__github__update_pull_request",
    "mcp__github__issue_write",
    "mcp__github__create_issue",
)

# `gh pr create`, `gh pr edit`, `gh issue create`, `gh issue edit`, `git commit`
# and their glab counterparts, at a command position.
RX_BODY_COMMAND = re.compile(
    r"(?:^|[;&|\n({`])\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"(?:gh\s+(?:pr|issue)\s+(?:create|edit)"
    r"|glab\s+(?:mr|issue)\s+(?:create|update)"
    r"|git\s+commit"
    r"|gh\s+api\b)",
    re.MULTILINE,
)

# `gh api` reaches both descriptions and comments. Only the first is scanned
# by GitHub, so a comments endpoint --- `.../issues/1/comments`, or a specific
# comment at `.../issues/comments/5` --- is not this hook's business.
RX_COMMENTS_ENDPOINT = re.compile(r"/comments(?:/\d+)?(?:[?\s'\"]|$)")

RX_GH_API = re.compile(
    r"(?:^|[;&|\n({`])\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*gh\s+api\b",
    re.MULTILINE,
)

RX_HEREDOC = re.compile(
    r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?[^\n]*\n"
    r"(.*?)\n[ \t]*\1\b",
    re.DOTALL,
)

NOTE_TEMPLATE = """\
This body places a closing keyword next to an issue reference inside a sentence
that reads as a deferral or a negation:

    {quote}

GitHub's parser matches `{match}` as a substring. It does not read the rest of
the sentence, so a line saying a LATER pull request will close the issue, or
that the issue is NOT being closed, closes it on merge.

Measured three times: ai-config#1718 closed #1717 that way; Morrison-Lab/gha#460
closed #322 with "I have not closed #322 --- items 1, 3, 4, and 5 remain open
there."; ucdavis/bcs#982 closed #923 with "... follow in a data PR that closes
#923.", and nobody noticed for two days. The close is silent, and the timeline's
`closed` event carries no commit id, so it cannot be attributed afterwards.

The remedy costs one word --- keep the number off the keyword:

    Refs #N
    a later data PR will close it (#N)

Carry on if the close is intended. This is a reminder, not a refusal.
"""


def sentence_around(text: str, start: int, end: int) -> str:
    """The sentence containing the match, bounded by sentence-ending punctuation
    or a blank line. Kept deliberately simple: an over-wide span only makes the
    cue test more permissive, which this reminder can afford."""
    left = max(
        text.rfind(". ", 0, start),
        text.rfind("\n\n", 0, start),
        text.rfind("! ", 0, start),
        text.rfind("? ", 0, start),
    )
    left = 0 if left < 0 else left + 2
    candidates = [
        pos for pos in (
            text.find(". ", end),
            text.find("\n\n", end),
            text.find("! ", end),
            text.find("? ", end),
        ) if pos >= 0
    ]
    right = min(candidates) + 1 if candidates else len(text)
    return text[left:right].strip()


def begins_line(text: str, start: int) -> bool:
    """True when the match starts its line, allowing a list marker or blockquote."""
    line_start = text.rfind("\n", 0, start) + 1
    return bool(RX_LINE_LEAD.match(text[line_start:start]))


def evaluate_body(body: str) -> str | None:
    """Return warning text for the first risky closing reference in BODY."""
    if not body:
        return None
    for match in RX_CLOSING_REF.finditer(body):
        if begins_line(body, match.start()):
            continue
        sentence = sentence_around(body, match.start(), match.end())
        if not RX_CUE.search(sentence):
            continue
        quote = " ".join(sentence.split())
        if len(quote) > 300:
            quote = quote[:297] + "..."
        return NOTE_TEMPLATE.format(quote=quote, match=match.group(0))
    return None


BODY_FLAGS = ("--body", "-b", "--message", "-m", "--description")
BODY_FILE_FLAGS = ("--body-file", "-F", "--file", "-f")


def _read_file(path: str) -> str:
    if not path or path == "-":
        return ""
    expanded = os.path.expanduser(path)
    try:
        with open(expanded, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return ""


def bodies_from_command(command: str) -> list:
    """Every body-shaped string a command carries: inline arguments, files it
    names, and heredoc bodies."""
    bodies = []
    for match in RX_HEREDOC.finditer(command):
        bodies.append(match.group(2))
    without_heredocs = RX_HEREDOC.sub("", command)
    try:
        tokens = shlex.split(without_heredocs)
    except ValueError:
        return bodies
    for index, token in enumerate(tokens):
        following = tokens[index + 1] if index + 1 < len(tokens) else ""
        for flag in BODY_FLAGS:
            if token == flag:
                bodies.append(following)
            elif token.startswith(flag + "="):
                bodies.append(token[len(flag) + 1:])
        for flag in BODY_FILE_FLAGS:
            value = None
            if token == flag:
                value = following
            elif token.startswith(flag + "="):
                value = token[len(flag) + 1:]
            if value is None:
                continue
            # `gh api -F body=@file` and `-f body=text` carry a field name.
            if "=" in value:
                name, _, rest = value.partition("=")
                if name.strip() != "body":
                    continue
                value = rest
            if value.startswith("@"):
                bodies.append(_read_file(value[1:]))
            elif flag in ("--body-file", "--file"):
                bodies.append(_read_file(value))
            else:
                bodies.append(value)
    return bodies


def targets_a_comment_endpoint(command: str) -> bool:
    """True when the only body-carrying command here is a `gh api` call against
    a comments endpoint, whose body GitHub never scans for closing keywords."""
    if not RX_GH_API.search(command):
        return False
    if not RX_COMMENTS_ENDPOINT.search(command):
        return False
    # A compound command may also carry a real description write; only the
    # pure-`gh api`-to-comments case is out of scope.
    without_api = RX_GH_API.sub(" ", command)
    return not RX_BODY_COMMAND.search(without_api)


def evaluate_bash(command: str) -> str | None:
    """Return warning text when a body-carrying command holds a risky reference."""
    if not command or not RX_BODY_COMMAND.search(command):
        return None
    if targets_a_comment_endpoint(command):
        return None
    for body in bodies_from_command(command):
        note = evaluate_body(body)
        if note:
            return note
    return None


def evaluate_mcp(tool_name: str, tool_input: dict) -> str | None:
    """Return warning text when an MCP body field holds a risky reference."""
    if tool_name not in MCP_BODY_TOOLS:
        return None
    return evaluate_body(str(tool_input.get("body") or ""))


def _emit(note: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": note,
        }
    }))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0

    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}

    if tool_name in BASH_TOOLS:
        command = (
            tool_input.get("command")
            or tool_input.get("CommandLine")
            or tool_input.get("cmd")
            or tool_input.get("script")
            or ""
        )
        note = evaluate_bash(str(command))
    else:
        note = evaluate_mcp(tool_name, tool_input)

    if note:
        _emit(note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
