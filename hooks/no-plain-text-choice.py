#!/usr/bin/env python3
"""PreToolUse: ask a multiple-choice question on a decision card, not in plain text.

ai-config#5826. Ezra, 2026-11-18: "anytime you ask me a multiple choice question,
can you use a multiple choice card?" Any agent that asks him a question with a fixed
set of answers (lettered or numbered options, "Option A or B", "start now or file?")
uses `request_decision`.

Scope: the user-visible text tools (post_message, reply, update_message,
edit_message), in every session. `request_decision` itself and agent-to-agent
messages are not matched. Denies a text that holds a question and either two or
more option lines / "Option N" labels, or a "now or file/later" choice. A deny is
possible because the failing shape is lexical (ai-config#4741). An open-ended
question with no fixed answers is left alone. Fenced code is ignored.
`ALLOW_PLAIN_CHOICE=1` overrides. Fails open on any parse trouble.
"""
import json
import os
import re
import sys

OVERRIDE = "ALLOW_PLAIN_CHOICE"
TOOL = re.compile(r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message)$")

FENCE = re.compile(r"```.*?```", re.S)
OPTION_LINE = re.compile(
    r"^\s*(?:[-*]\s+)?(?:\(?[A-Da-d]\)|[A-Da-d][.):]|\(?[1-4]\)|[1-4][.):]|"
    r"\*{0,2}option\s+[A-D1-4]\b)\s*\S", re.M | re.I)
OPTION_LABEL = re.compile(r"\boption\s+([A-D1-4])\b", re.I)
START_OR_FILE = re.compile(
    r"\b(?:now|immediately)\s+or\s+(?:file|defer|later|tonight|queue)\w*"
    r"|\bstart\b[^.?\n]{0,40}\bor\s+file\b", re.I)
CHOICE_CUE = re.compile(
    r"\b(?:which|choose|pick|prefer|select)\b|\bor\b", re.I)

REASON = (
    "[hook: no-plain-text-choice] This message asks a multiple-choice question in plain "
    "text ({shape}) (ai-config#5826, Ezra 2026-11-18: \"anytime you ask me a multiple "
    "choice question, can you use a multiple choice card?\"). Post it with "
    "mcp__hearthbot__request_decision: one question, 2 to 4 options, one recommended. "
    "That covers \"start now or file?\" and \"which option?\" questions. Set "
    "ALLOW_PLAIN_CHOICE=1 only for a question with no fixed set of answers."
)


def user_text(tool_input: dict) -> str:
    text = tool_input.get("text")
    return FENCE.sub(" ", text) if isinstance(text, str) else ""


def choice_shape(text: str):
    """Describe the plain-text multiple-choice shape found in the text, or None."""
    questions = [s for s in re.split(r"(?<=[?])\s+|\n+", text) if s.strip().endswith("?")]
    if not questions:
        return None
    if any(START_OR_FILE.search(q) for q in questions):
        return "a start-now-or-file question"
    if len(OPTION_LINE.findall(text)) >= 2 and any(CHOICE_CUE.search(q) for q in questions):
        return "a list of lettered or numbered options"
    if len({m.upper() for m in OPTION_LABEL.findall(text)}) >= 2:
        return "labelled Option A, Option B"
    return None


def denial(payload: dict):
    if os.environ.get(OVERRIDE) or not isinstance(payload, dict):
        return None
    if not TOOL.search(str(payload.get("tool_name") or "")):
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    shape = choice_shape(user_text(tool_input))
    return REASON.format(shape=shape) if shape else None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    reason = denial(payload)
    if reason:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
