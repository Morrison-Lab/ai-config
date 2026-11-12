#!/usr/bin/env python3
"""PreToolUse guard: no class announcement without the user's approval.

Ezra, 2026-10-27, said twice: never post a class announcement without his
review and approval of its exact text (ai-config#4780, from mlg#228).
Detection fails closed on a discussion-topic write, `is_announcement`, the CLI
or a Canvas MCP write, even in a git or grep command chained with others.
Approval is a whole line of the user's latest typed message ("post the
announcement"), and allows one write. Not seen: a posting script file, a URL
built at run time, and whether the posted text is the text shown; the layers
in draft-in-ezras-voice and adversarial-reviewer cover those.
"""
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
ANNOUNCE = re.compile(r"is_announcement|announcement.*\.(edit|update|post|put)\(", re.I | re.S)
DECLINE = re.compile(r"\b(no|not|wait|hold|stop|cancel|later|actually)\b|n't\b", re.I)
WRITE = re.compile(r"(\b|-X\s*)(POST|PUT)\b|['\"](?i:post|put)['\"]|create_discussion_topic|\.(edit|update|post|put)\(|"
                   r"(^|\s)(-d|-F|-T|--data|--form|--json|--upload-file)")
SAFE_FIRST = {"git", "gh", "grep", "egrep", "rg"}
COMPOUND = re.compile(r"[;&|`\n<>]|\$\(|\bgh\s+api\b")
MCP_READ = re.compile(r"^(get|list|search|read|find|fetch|show|count)", re.I)
APPROVAL = re.compile(r"^\s*(yes|ok|okay|approved)?[,.!]?\s*(please\s+)?(go ahead and\s+)?"
                      r"((post|publish)\s+(it|the announcement|this announcement|that announcement)"
                      r"|send\s+(the|this|that)\s+announcement)(\s+now)?\s*[.!]*\s*$", re.I | re.M)
TAG = re.compile(r"<(/?)([a-z][\w-]*)([^>]*)>")


def is_announcement_write(tool, inp):
    if tool in ("Bash", "Monitor"):
        cmd = inp.get("command") or ""
        first = (cmd.split() or [""])[0].rsplit("/", 1)[-1]
        if first in SAFE_FIRST and not COMPOUND.search(cmd):  # one plain command
            return False
        return bool(CLI.search(cmd) or ANNOUNCE.search(cmd) or (TOPIC.search(cmd) and WRITE.search(cmd)))
    name = tool.lower()
    if not name.startswith("mcp__") or "canvas" not in name and "announc" not in name:
        return False
    verb = name.split("__")[-1]
    if any(w in verb for w in ("announc", "discussion", "topic")) and not MCP_READ.search(verb):
        return True
    flat = json.dumps(inp).replace('\\"', '"')
    return bool(TOPIC.search(flat) and re.search(r"is_announcement|\b(POST|PUT)\b", flat, re.I))


def user_words(text):
    """The user's own messages: outside every tag, or in a principal message or
    a cited user entry that sits directly in its wake or relay."""
    out, stack, pos = [], [], 0
    for m in TAG.finditer(text):
        path = [t for t, _ in stack]
        in_wake = (path[:1] == ["wake"] and path[-1:] == ["message"]
                   and set(path[1:-1]) <= {"project", "thread"})
        if not stack or (in_wake or path == ["coordinator-relay", "relay", "cited"]) and stack[-1][1]:
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
    return [p for p in out + ([text[pos:]] if not stack else []) if p.strip()]


def _blocks(entry):
    msg = entry.get("message")
    content = msg.get("content") if isinstance(msg, dict) else entry.get("content")
    return content if isinstance(content, list) else [{"type": "text", "text": content or ""}]


def verdict(path, tool, inp):
    """None to allow, or why the write is refused."""
    if is_real_user_turn is None:
        return "scripts/lib/transcript_meta.py could not be loaded"
    try:
        with open(path, encoding="utf-8") as fh:
            entries = [json.loads(line) for line in fh if line.strip()]
    except (OSError, ValueError, TypeError):
        return "the transcript could not be read"
    writes = []  # every write since the approval, failed ones included
    for entry in reversed(entries):
        if is_real_user_turn(entry) and entry.get("promptSource") != "sdk":
            text = "\n".join(strip_injected_text(b.get("text") or "")
                             for b in _blocks(entry) if b.get("type") == "text")
            last = (user_words(text) or [""])[-1]  # the user's last message only
            if not APPROVAL.search(last) or DECLINE.search(last):
                return "the user's latest message does not approve posting it"
            if [tool, inp] in writes:  # the call being judged, already logged
                writes.remove([tool, inp])
            return "an announcement was already posted after that approval" if writes else None
        if entry.get("type") == "assistant":
            writes += [[b.get("name"), b.get("input")] for b in _blocks(entry)
                       if b.get("type") == "tool_use"
                       and is_announcement_write(b.get("name") or "", b.get("input") or {})]
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
        why = verdict(payload.get("transcript_path") or "", tool, inp)
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
