#!/usr/bin/env python3
"""PreToolUse guard: no class announcement without the user's approval.

Ezra, 2026-10-27, said twice: never post a class announcement without his
review and approval of its exact text (ai-config#4780, from mlg#228).
Detection fails closed (a discussion-topic write, the CLI, a Canvas MCP
write). Approval is a whole line of the user's latest typed message, such as
"post the announcement", so no negation or quote passes; one write each.
A posting script file is not seen; the layers in draft-in-ezras-voice and
adversarial-reviewer cover it.
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

CLI = re.compile(r"\bcanvas\s+announcements?\s+(create|post|update|edit|publish)\b", re.I)
TOPIC = re.compile(r"discussion_topic", re.I)
WRITE = re.compile(r"\b(POST|PUT)\b|is_announcement|create_discussion_topic|\.(edit|update|post|put)\(|"
                   r"(^|\s)(-d|--data\S*|-F|--form|--json)[\s=@]")
SAFE_FIRST = {"git", "gh", "grep", "egrep", "rg"}
RUNNERS = re.compile(r"curl|wget|http|python|node|ruby|canvas\s+api|\$\(|`|<\(", re.I)
MCP_READ = re.compile(r"^(get|list|search|read|find|fetch|show|count)", re.I)
APPROVAL = re.compile(r"^\s*(yes|ok|okay|approved)?[,.!]?\s*(please\s+)?(go ahead and\s+)?"
                      r"(post|publish|send)\s+(it|the announcement|this announcement|"
                      r"that announcement)(\s+now)?\s*[.!]*\s*$", re.I | re.M)
TAG = re.compile(r"<(/?)([a-z][\w-]*)([^>]*)>")


def is_announcement_write(tool, inp):
    if tool == "Bash":
        cmd = inp.get("command") or ""
        first = (cmd.split() or [""])[0].rsplit("/", 1)[-1]
        if first in SAFE_FIRST and not RUNNERS.search(cmd):
            return False
        return bool(CLI.search(cmd) or (TOPIC.search(cmd) and WRITE.search(cmd)))
    name = tool.lower()
    if not name.startswith("mcp__") or "canvas" not in name:
        return False
    verb = name.split("__")[-1]
    if ("announc" in verb or "discussion" in verb) and not MCP_READ.search(verb):
        return True
    flat = json.dumps(inp).replace('\\"', '"')
    return bool(TOPIC.search(flat) and re.search(r"is_announcement|\b(POST|PUT)\b", flat, re.I))


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
        if (in_wake or path == ["coordinator-relay", "relay", "cited"]) and stack[-1][1]:
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


def _blocks(entry):
    msg = entry.get("message")
    content = msg.get("content") if isinstance(msg, dict) else entry.get("content")
    return content if isinstance(content, list) else [{"type": "text", "text": content or ""}]


def verdict(path):
    """None to allow, or why the write is refused."""
    if is_real_user_turn is None:
        return "scripts/lib/transcript_meta.py could not be loaded"
    try:
        with open(path, encoding="utf-8") as fh:
            entries = [json.loads(line) for line in fh if line.strip()]
    except (OSError, ValueError, TypeError):
        return "the transcript could not be read"
    done = {b.get("tool_use_id") for e in entries for b in _blocks(e)
            if b.get("type") == "tool_result" and not b.get("is_error")}
    writes = 0
    for entry in reversed(entries):
        if is_real_user_turn(entry) and entry.get("promptSource") != "sdk":
            text = "\n".join(strip_injected_text(b.get("text") or "")
                             for b in _blocks(entry) if b.get("type") == "text")
            if not APPROVAL.search(user_words(text)):
                return "the user's latest message does not approve posting it"
            return "an announcement was already posted after that approval" if writes else None
        if entry.get("type") == "assistant":
            writes += sum(1 for b in _blocks(entry) if b.get("type") == "tool_use"
                          and b.get("id") in done
                          and is_announcement_write(b.get("name") or "", b.get("input") or {}))
    return "no message from the user approves posting it"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        tool, inp = payload.get("tool_name") or "", payload.get("tool_input")
    except Exception as exc:  # unreadable payload: nothing to judge
        print(f"no-unapproved-announcement: unchecked ({exc})", file=sys.stderr)
        return 0
    try:
        hit = isinstance(inp, dict) and is_announcement_write(tool, inp)
    except Exception:  # detection failed: fall back to a crude, closed check
        hit = bool(re.search(r"discussion_topic|announc", json.dumps(inp), re.I))
    if not hit:
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
                "the exact text in chat and ask the user to reply with the line "
                "\"post the announcement\"; then post that text once."),
        }}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
