#!/usr/bin/env python3
"""PreToolUse: a failure called pre-existing must come with its fix.

Ezra, 2026-11-24, on psw#703: "why didn't you fix the missing curl package?"
and "so why didn't you?". The PR's `lint-changed-files` job failed because the
runner could not build the R package `curl`. The agent showed the job failed on
`main` too, wrote that into the PR body, and stopped. psw#707 had already fixed
it on `main`; merging `main` in turned the check green. The rule the agent
followed ("leave pre-existing failures alone and note them",
shared/workflow/persistent-pr-loop.md) keeps a PR scoped. It never meant a
red check stays red.

Blocks (deny) an outgoing reply, relay, PR body or forge comment whose
paragraph says a failure is pre-existing, not caused by this PR, unrelated to
it, or also failing on main, unless the same paragraph names the fix: a PR or
issue reference (`#N`, `/pull/N`, `/issues/N`), or a merge of main into the
branch. A link to a job or run is evidence of the failure, not its fix, so it
does not count. Quoted text (code, double quotes, blockquote lines) is skipped.
A wording check; a paraphrase it does not recognise gets through. Fails open.
"""
import json
import re
import sys

TOOL = re.compile(
    r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message|message_thread|message_coordinator)$"
    r"|^mcp__github__(?:add_issue_comment|update_issue_comment|add_reply_to_pull_request_comment"
    r"|add_comment_to_pending_review|pull_request_review_write|create_pull_request|update_pull_request)$")

FENCE = re.compile(r"```.*?```", re.S)
QUOTED = re.compile(
    r"```.*?```|`[^`\n]*`|^[ \t]*>.*$|\"[^\"\n]*\"|\u201c[^\u201d\n]*\u201d", re.S | re.M)

_PR = r"(?:PR|pull request|change|diff|branch)"
CLAIM = re.compile(
    r"\bpre-?existing\b"
    r"|\bnot (?:caused|introduced) by (?:this|the|my|our) " + _PR
    + r"|\bunrelated to (?:this|the|my|our) " + _PR
    + r"|\bnot (?:this|the) " + _PR + r"'?s\b"
    r"|\boutside (?:this|the) " + _PR + r"'?s scope\b"
    r"|\b(?:this|the) " + _PR + r" (?:does not|doesn't|did not|didn't) (?:cause|introduce|touch|change)\b"
    r"|\b(?:this|the) " + _PR + r" changes no\b"
    r"|\b(?:also )?fail(?:s|ed|ing)? (?:on|in) (?:`?main`?|the base|master)\b"
    r"|\b(?:on|in) (?:`?main`?|master) (?:too|as well)\b"
    r"|\balready (?:red|failing|broken) (?:on|in) (?:`?main`?|master)\b",
    re.I)
FAILURE = re.compile(
    r"\b(?:fail\w*|red|error\w*|broken|break\w*|lint\w*|CI|check\w*|job|warning\w*|annotation\w*)\b", re.I)
FIX = re.compile(
    r"(?<![\w/])#\d+\b|/pull/\d+\b|/issues/\d+\b|![0-9]+\b"
    r"|\bmerg(?:e|ed|ing) (?:`?origin/main`?|`?main`?|the base)(?: branch)? (?:in|into)\b"
    r"|\bmerg(?:e|ed|ing) in (?:`?origin/main`?|`?main`?)\b",
    re.I)

REASON = (
    "[hook: no-unfixed-preexisting-failure] This text calls a failure pre-existing, "
    "or not this PR's, and names no fix for it. Ezra, 2026-11-24 (psw#703, the curl "
    "lint failure): \"why didn't you fix the missing curl package?\" A note is not the "
    "last step. In the same paragraph, name the fix: merge main in when main already "
    "has one (link the PR that fixed it), or link the infra PR you opened to fix the "
    "cause (infra has a standing merge grant), or link the issue you filed when the "
    "fix is not yours to make. Check sibling repos for the same failure. "
    "shared/workflow/persistent-pr-loop.md."
)


def unfixed(text: str) -> bool:
    # Paragraphs split before quotes are blanked, so the fix test still sees
    # "merged `main` in" while the claim test skips quoted words.
    for raw in re.split(r"\n\s*\n", FENCE.sub(" ", text)):
        para = QUOTED.sub(" ", raw)
        if CLAIM.search(para) and FAILURE.search(para) and not FIX.search(raw.replace("`", "")):
            return True
    return False


def strings(value, depth=0):
    if isinstance(value, str):
        yield value
    elif depth < 4 and isinstance(value, dict):
        for item in value.values():
            yield from strings(item, depth + 1)
    elif depth < 4 and isinstance(value, list):
        for item in value:
            yield from strings(item, depth + 1)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict) or not TOOL.search(str(payload.get("tool_name") or "")):
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    try:
        hit = any(unfixed(t) for t in strings(tool_input))
    except Exception:
        return 0
    if hit:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": REASON,
        }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
