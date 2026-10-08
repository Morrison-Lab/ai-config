#!/usr/bin/env python3
"""PreToolUse warn: a hedge word sits beside a claim the agent could check.

The user's standing rule (2026-10-08): never say "likely" or "probably" about
something you can check; check it, then state the result. "Lds#477 is probably
waiting on CI" is a status the agent can read in one call.

Scope: the user-visible reply tools (`reply`, `post_message`, `update_message`)
and the GitHub comment and review tools. Warns, never blocks, and fails open.

A sentence is flagged when it holds BOTH:
  - a hedge: likely, probably, presumably, "I think", "should be";
  - a checkable item: a PR or issue reference (`#N`, `owner/repo#N`, a
    pull or issues URL), a CI or check status word, or merged, open, closed.

Both must be in the same sentence, so a hedge about a design choice in one
sentence and a PR link in the next does not warn. Fenced code and inline code
are removed first. "should be able to" and "should be fine" are not flagged:
they predict behaviour rather than report a state.
"""
import json
import re
import sys

TOOL = re.compile(
    r"(^|__)(reply|post_message|update_message|add_issue_comment|"
    r"update_issue_comment|add_reply_to_pull_request_comment|"
    r"add_comment_to_pending_review|pull_request_review_write)$"
)
FENCE = re.compile(
    r"^ {0,3}(```+|~~~+).*?(?:^ {0,3}\1[`~]*[ \t]*$|\Z)", re.M | re.S)
INLINE_CODE = re.compile(r"(?<!`)(`+)(?!`).*?(?<!`)\1(?!`)", re.S)
HEDGE = re.compile(
    r"\b(likely|probably|presumably|i think|should be(?! (able|fine|ok|okay)\b))\b",
    re.I)
CHECKABLE = re.compile(
    r"(?<![\w/&.-])(?:[\w.-]+/[\w.-]+|[\w-]+)?#\d{1,5}\b"
    r"|/(?:pull|pulls|issues)/\d+"
    r"|\b(?:ci|checks?|check runs?|build|builds|green|red|passing|passed|"
    r"failing|failed|merged|open|closed|conflicts?)\b",
    re.I)
SENTENCE_END = re.compile(r"\n|(?<!\be\.g)(?<!\bi\.e)(?<!\betc)[.!?]+(?=\s|$)")

NOTE = """\
[hook: warn-hedged-checkable-claim] This message hedges ({hedges}) in a \
sentence about something you can check: "{sentence}"
The user's rule: never say "likely" or "probably" about something you can \
check. Read the PR, issue or check now (for a PR, its mergeable state and \
every check run), then state the result without the hedge. If the item is \
not checkable from here, say that instead of guessing."""


def sentences(text: str):
    start = 0
    for m in SENTENCE_END.finditer(text):
        yield text[start:m.start()]
        start = m.end()
    yield text[start:]


def hedged_claims(text: str):
    text = INLINE_CODE.sub(" ", FENCE.sub(" ", text))
    hits = []
    for sent in sentences(text):
        hedges = HEDGE.findall(sent)
        if hedges and CHECKABLE.search(sent):
            words = [h[0] if isinstance(h, tuple) else h for h in hedges]
            hits.append((sent.strip(), sorted({w.lower() for w in words})))
    return hits


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    if not TOOL.search(str(payload.get("tool_name") or "")):
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    text = tool_input.get("text")
    if not isinstance(text, str):
        text = tool_input.get("body")
    if not isinstance(text, str):
        return 0
    hits = hedged_claims(text)
    if not hits:
        return 0
    sentence, hedges = hits[0]
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": NOTE.format(
                hedges=", ".join(hedges), sentence=sentence[:200]),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
