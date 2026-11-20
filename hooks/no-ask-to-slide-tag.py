#!/usr/bin/env python3
"""PreToolUse: do not ask anyone's leave to slide a floating infra tag.

ai-config#6052. Ezra, 2026-11-20: "never ask me before sliding an infra tag;
always just do it". The same day, threads held Morrison-Lab/gha's `v3` slide,
citing a rule that only a runner thread slides, and the coordinator asked him.

Denies a hearthbot message (post_message, reply, update_message, edit_message,
request_decision, message_coordinator, message_thread) when one sentence names a
tag slide (`slide v3`, "the tag slide", `slide-major-tag`) and asks for leave
("want me to", "your go-ahead", "type slide v3") or hands the slide to someone
else ("the runner thread slides", "leave the slide to"). A sentence that says
the slide went ahead without asking is left alone, and so is a hold on a gate
("holding the slide until the review returns"), which names no person.
A request_decision card that names a slide anywhere is an ask by construction.
Fails open on parse trouble.
"""
import json
import re
import sys

TOOL = re.compile(
    r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message|"
    r"request_decision|message_coordinator|message_thread)$")

SLIDE = re.compile(
    r"\bslid(?:e|es|ing)\s+(?:the\s+)?(?:`?v\d+`?|(?:floating\s+|major\s+)?tags?)\b"
    r"|\bv\d+`?\s+(?:tag\s+)?slides?\b|\btag[- ]slides?\b|\bslide-major-tag\b|\bslide-tag\b|\bslides?\b(?=[^.?!\n]{0,30}\bv\d+\b)",
    re.I)

ASK = re.compile(
    r"\b(?:shall|should|can|may)\s+I\b|\bwant\s+me\s+to\b|\b(?:ok|okay)\s+(?:to|if)\b"
    r"|\byour\s+(?:word|go[- ]ahead|ok|okay|approval|permission|sign[- ]off|call)\b"
    r"|\b(?:approve|authori[sz]e|confirm)\s+(?:the\s+)?(?:tag\s+)?slid"
    r"|\b(?:needs?|requires?|awaits?|awaiting)\s+(?:your|explicit|human|ezra|a\s+human)\b"
    r"|\b(?:type|say|reply)\s+[\"'`\u201c]?slide\b|\bsay\s+the\s+word\b|\bif\s+you\s+(?:want|like|agree)\b"
    r"|\bwait(?:s|ing)?\s+(?:on|for)\s+(?:you|your|ezra|the\s+user|a\s+human|the\s+runner|the\s+coordinator)\b"
    r"|\b(?:leave|leaves|leaving|left|hand|hands|handing|defer|defers|deferring)\s+the\s+(?:tag\s+)?slide\b"
    r"|\b(?:only\s+)?the\s+runner(?:\s+thread|\s+session)?\s+(?:will\s+)?(?:slides?|dispatch)",
    re.I)

DONE = re.compile(r"\bwithout\s+(?:asking|waiting\s+for\s+(?:you|ezra)|your\s+word)\b|\bnever\s+ask", re.I)

# Clauses, not only sentences: "The deck needs your approval; slide v3 done." is two.
SPLIT = re.compile(r"(?<=[.!?;])\s+|\n+")

REASON = (
    '[hook: no-ask-to-slide-tag] "{sentence}" asks leave to slide a floating tag, or hands '
    "the slide to someone else (ai-config#6052; Ezra, 2026-11-20: \"never ask me before "
    "sliding an infra tag; always just do it\"). Any agent that finished an infra PR slides "
    "the tag itself once the gates pass (green tip, no pending review, the permission audit, "
    "`expected_sha`; see skills/slide-tag/SKILL.md), then reports old SHA, new SHA and the PRs "
    "it carries. If a gate fails, say which one and what you are doing about it, without asking."
)


def user_text(tool_input):
    parts = [tool_input.get("text"), tool_input.get("question")]
    for opt in tool_input.get("options") or []:
        if isinstance(opt, dict):
            parts += [opt.get("label"), opt.get("consequence")]
    return "\n".join(p for p in parts if isinstance(p, str))


def asking_sentence(text):
    for sentence in SPLIT.split(text):
        if SLIDE.search(sentence) and ASK.search(sentence) and not DONE.search(sentence):
            return " ".join(sentence.split())
    return None


def main():
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict) or not TOOL.search(str(payload.get("tool_name") or "")):
            return 0
        tool_input = payload.get("tool_input")
        if not isinstance(tool_input, dict):
            return 0
        text = user_text(tool_input)
        sentence = asking_sentence(text)
        if not sentence and payload["tool_name"].endswith("request_decision"):
            # A decision card about a slide is itself the ask.
            sentence = next((" ".join(s.split()) for s in SPLIT.split(text) if SLIDE.search(s)), None)
    except (ValueError, TypeError, AttributeError):
        return 0
    if sentence:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": REASON.format(sentence=sentence[:160]),
        }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
