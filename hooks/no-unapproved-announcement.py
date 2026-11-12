#!/usr/bin/env python3
"""PreToolUse guard: no class announcement without the user's approval.

Ezra, 2026-10-27, said twice: never post a class announcement without his
review and approval of its exact text (ai-config#4780, from mlg#228). A post
reaches every student at once and cannot be unsent, so this denies.

It fires on a Canvas discussion-topic write (the `canvas announcements` CLI,
`canvasapi`, a POST or PUT to `discussion_topics`, a Canvas MCP tool) and
allows one per turn whose latest typed user message approves it ("post the
announcement"). Negated, conditional, questioning or draft-requesting
sentences do not approve; agent-written turns never count. A posting script
file is not seen; draft-in-ezras-voice and adversarial-reviewer cover it.
Once a write is detected, any trouble reading the transcript denies.
"""
from __future__ import annotations

import json
import os
import re
import sys

try:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.realpath(__file__))), "scripts", "lib"))
    from transcript_meta import is_real_user_turn, strip_injected_text
except Exception:  # detection still runs; a detected write is then denied
    is_real_user_turn = None

NOT_WRITERS = {"git", "grep", "egrep", "rg", "gh", "echo", "printf", "cat", "less", "head", "tail", "sed", "awk", "diff"}
CLI = re.compile(r"\bcanvas\s+announcements?\s+(create|post|update|edit)\b", re.I)
TOPIC = re.compile(r"discussion_topic", re.I)
WRITE = re.compile(r"is_announcement|create_discussion_topic|\.edit\(|-x\s*['\"]?(post|put)|--request[ =]['\"]?(post|put)|"
                   r"requests\.(post|put)|method['\"]?\s*[:=]\s*['\"]?(post|put)|(^|\s)(?-i:-d|--data\S*|-F|--form)[\s=@]", re.I)
MCP_WRITE = re.compile(r"(^|_)(create|post|update|edit|put)(_|$)")
APPROVE = re.compile(r"\b(post|publish|send)\b[^.!?\n]{0,30}\bannouncements?\b"
                     r"|\bannouncements?\b[^.!?\n]{0,30}\b(approved|post it|send it|ok to post|okay to post)\b", re.I)
SPOILER = re.compile(r"\b(don'?t|do not|never|not|before|until|unless|wait|if|should|i'?ll|myself)\b|\?", re.I)
DRAFTING = re.compile(r"\b(draft|write|compose)\b", re.I)
TAG = re.compile(r"<(/?)([a-z][\w-]*)([^>]*)>")


def is_announcement_write(tool, inp):
    if tool == "Bash":
        for seg in re.split(r"&&|\|\||[|;&\n]", inp.get("command") or ""):
            words = seg.split()
            if words and words[0].rsplit("/", 1)[-1] not in NOT_WRITERS and (
                    CLI.search(seg) or (TOPIC.search(seg) and WRITE.search(seg))):
                return True
        return False
    name = tool.lower()
    if "canvas" not in name or not name.startswith("mcp__"):
        return False
    verb = name.split("__")[-1]
    if MCP_WRITE.search(verb) and ("announcement" in verb or "discussion" in verb):
        return True
    flat = json.dumps(inp).replace('\\"', '"')
    return bool(TOPIC.search(flat) and WRITE.search(flat))


def user_words(text):
    """The user's own words: outside any wake, or in a principal message or
    a cited user entry that sits directly in its wake or relay."""
    if "<wake" not in text and "<coordinator-relay" not in text:
        return text
    out, stack, pos = [], [], 0
    for m in TAG.finditer(text):
        path = [t for t, _ in stack]
        in_wake = (path[:1] == ["wake"] and path[-1:] == ["message"]
                   and set(path[1:-1]) <= {"project", "thread"})
        if (in_wake or path == ["coordinator-relay", "relay", "cited"]) \
                and stack[-1][1]:
            out.append(text[pos:m.start()])
        closing, tag, attrs = m.group(1), m.group(2), m.group(3)
        if closing:
            while stack and stack.pop()[0] != tag:
                pass
        elif not attrs.rstrip().endswith("/"):
            ok = ('trust="principal"' in attrs if tag == "message"
                  else 'author="user"' in attrs if tag == "cited" else True)
            stack.append((tag, ok and (not stack or stack[-1][1])))
        pos = m.end()
    return "\n".join(out)


def approves(text):
    for sentence in re.split(r"(?<=[.!?\n])", text):
        if APPROVE.search(sentence) and not (SPOILER.search(sentence)
                                             or DRAFTING.search(sentence)):
            return True
    return False


def _texts(entry):
    msg = entry.get("message")
    content = msg.get("content") if isinstance(msg, dict) else entry.get("content")
    return content if isinstance(content, list) else [
        {"type": "text", "text": content or ""}]


def verdict(path):
    """None to allow, or why the write is refused."""
    if is_real_user_turn is None:
        return "scripts/lib/transcript_meta.py could not be loaded"
    try:
        with open(path, encoding="utf-8") as fh:
            entries = [json.loads(line) for line in fh if line.strip()]
    except (OSError, ValueError, TypeError):
        return "the transcript could not be read"
    writes = 0
    for entry in reversed(entries):
        if is_real_user_turn(entry) and entry.get("promptSource") != "sdk":
            text = "\n".join(strip_injected_text(b.get("text") or "")
                             for b in _texts(entry) if b.get("type") == "text")
            if not approves(user_words(text)):
                return "the user's latest message does not approve posting it"
            if writes:
                return "an announcement was already written after that approval"
            return None
        if entry.get("type") == "assistant":
            writes += sum(1 for b in _texts(entry) if b.get("type") == "tool_use"
                          and is_announcement_write(b.get("name") or "",
                                                    b.get("input") or {}))
    return "no message from the user approves posting it"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        tool, inp = payload.get("tool_name") or "", payload.get("tool_input")
        if not isinstance(inp, dict) or not is_announcement_write(tool, inp):
            return 0
    except Exception as exc:  # nothing detected: fail open, saying so
        print(f"no-unapproved-announcement: unchecked ({exc})", file=sys.stderr)
        return 0
    try:
        why = verdict(payload.get("transcript_path") or "")
    except Exception as exc:  # a detected write: fail closed
        why = f"the check failed ({exc})"
    if why:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"Refused: this posts or edits a class announcement, and {why} "
                "(Ezra, 2026-10-27, ai-config#4780: never post an announcement "
                "without his review and approval of its exact text).\n\nShow "
                "the exact text in chat, wait for \"post the announcement\", "
                "then post that text once."),
        }}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
