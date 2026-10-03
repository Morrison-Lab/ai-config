#!/usr/bin/env python3
"""PreToolUse warn: a reply names a PR, MR or issue by number with no link.

ai-config#4224. The user asked for a link on every artifact a reply names,
more than once ("always give me hyperlinks!", then "how many times do I have
to tell you that?"), and the rule was already in memory and in repo
instructions. It is decidable at the moment of sending: a reply tool call
whose text holds a forge reference such as `#4224`, `!125` or
`Morrison-Lab/lds#342` that is not inside a Markdown link, a URL or a code
span.

Scope: the user-visible reply tools (`mcp__hearthbot__reply`, `post_message`,
`update_message`) and nothing else. Warns, never blocks: a bare number is
cheap to fix by resending, and a blocked reply costs the user a turn.

Deliberate limits, so the warning stays rare enough to be read:
  - Only the three number forms above. A description such as "the referee
    note" has no lexical marker, so it is out of scope.
  - Text inside fenced code, inline code, Markdown links and bare URLs is
    removed first.
  - A `#` followed by a digit run is a reference only at a word boundary and
    only when the digits are not part of a hex colour or an anchor.
  - Ordinals such as "#1 priority" or "Step #2" cannot be told from issue
    numbers by text alone, so they are listed and the note says to ignore
    them. Parenthesised and bold references ("(#4224)", "**#4224**") warn.
  - A `#N` directly after `.`, `-`, `/` or `&` ("fixed.#12", "PR-#12") is not
    flagged: this trades a missed warning for fewer false ones on paths,
    entities and fragments.
"""
import json
import re
import sys

REPLY_TOOL = re.compile(r"(^|__)(reply|post_message|update_message)$")
# A fence runs to its closing fence, or to the end of the text when unclosed.
FENCE = re.compile(
    r"^ {0,3}(```+|~~~+).*?(?:^ {0,3}\1[`~]*[ \t]*$|\Z)", re.M | re.S)
# A code span closes on a backtick run of the same length, across lines.
INLINE_CODE = re.compile(r"(?<!`)(`+)(?!`).*?(?<!`)\1(?!`)", re.S)
MD_LINK = re.compile(r"!?\[[^\]\n]*\]\([^)\n]*\)")
# `[text][label]` links and `[label]: url` definitions.
REF_LINK = re.compile(r"\[[^\]\n]*\]\[[^\]\n]*\]")
REF_DEF = re.compile(r"^ {0,3}\[[^\]\n]+\]:[ \t].*$", re.M)
BARE_URL = re.compile(r"https?://\S+")
REF = re.compile(
    r"(?<![\w/&#.-])"
    r"(?:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)?[#!]\d{1,5}\b"
)

NOTE = """\
[hook: warn-bare-forge-reference] This reply names {refs} by number with no \
link. The user wants a link on every PR, MR or issue a reply mentions, in \
the sentence that names it, because the number alone cannot be opened.
Resend with each reference written as [owner/repo#N](URL). Get the URL from \
the tool result that created or listed the item; do not type an ID from \
memory. If a listed reference is not a forge item (an ordinal such as a \
list position), ignore this note."""


def strip_links_and_code(text: str) -> str:
    for pattern in (FENCE, INLINE_CODE, MD_LINK, REF_LINK, REF_DEF, BARE_URL):
        text = pattern.sub(" ", text)
    return text


def bare_refs(text: str) -> list[str]:
    seen: list[str] = []
    for match in REF.finditer(strip_links_and_code(text)):
        ref = match.group(0)
        if ref not in seen:
            seen.append(ref)
    return seen


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    if not REPLY_TOOL.search(str(payload.get("tool_name") or "")):
        return 0
    tool_input = payload.get("tool_input")
    text = tool_input.get("text") if isinstance(tool_input, dict) else None
    if not isinstance(text, str):
        return 0
    refs = bare_refs(text)
    if not refs:
        return 0
    shown = ", ".join(f"`{r}`" for r in refs[:5])
    if len(refs) > 5:
        shown += f" and {len(refs) - 5} more"
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": NOTE.format(refs=shown),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
