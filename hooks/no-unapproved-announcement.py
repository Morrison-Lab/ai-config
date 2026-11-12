#!/usr/bin/env python3
"""PreToolUse guard: no class announcement without the user's approval.

Ezra, 2026-10-27, said twice: never post a class announcement without his review and approval of its exact text
(ai-config#4780). Denies the CLI, `is_announcement`, a network write naming a topic and an MCP announcement write
unless the user's last message is only "post the announcement" ("yes, post it", ...); one write each. Gaps: #5453.
"""
import json
import os
import re
import sys

try:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "scripts", "lib"))
    from transcript_meta import is_real_user_turn, strip_injected_text
except Exception:  # detection still runs; a detected write is then denied
    is_real_user_turn = None

CLI = re.compile(r"\bcanvas\s+announcements?\s+(create|post|update|edit|publish)\b", re.I)
CODE = re.compile(r"\b(python3?|node|ruby|perl|Rscript)\b\s+(-c|-e|-\s)|<<")
QUOTED = re.compile(r"'[^']*'|\"(\\.|[^\"\\$`])*\"")  # a double-quoted span with $ or ` stays
TOPIC = re.compile(r"discussion(_|%5f)?topic|announcement", re.I)
ANNOUNCE = re.compile(r"is_announcement|get_announcements.*\.(edit|update)\(", re.I | re.S)
NET = re.compile(r"\b(curl|wget|requests\.\w+|urllib\.request|httpx\.\w+|httr::\w+|http\.client|aiohttp|canvasapi|canvas\s+api|Invoke-\w+)\b|"
                 r"(https?://|/api/v1/).*(['\"](?i:put|post)['\"]|\.(put|post)\()", re.I | re.S)
WRITE = re.compile(r"(-\w*X|--request|-Method)[\s=]*[\"']?(?i:POST|PUT)|(^|\s)(-[a-zA-Z]*[dFT]|--data|--form|--json|--upload-file)")
SAFE_FIRST = {"git", "gh", "grep", "egrep", "rg"}
COMPOUND = re.compile(r"[;&|`\n<>]|\$\(")
MCP_READ = re.compile(r"^(get|list|search|read|find|fetch|show|count)", re.I)
APPROVAL = re.compile(r"\s*((yes|ok|okay|approved|looks good|lgtm)[,.!]*\s*)?(please\s+)?(go ahead and\s+)?"
                      r"((post|publish)\s+(it|the announcement|this announcement|that announcement)"
                      r"|send\s+(the|this|that)\s+announcement)( (now|as written|please))*[ .!]*", re.I)  # matched against single-spaced words
TAG = re.compile(r"<(/?)([a-z][\w-]*)([^>]*)>", re.I)
ENVELOPE = {"wake", "project", "thread", "message", "relay", "cited", "note"}  # and every hyphenated tag


def is_announcement_write(tool, inp):
    if tool in ("Bash", "Monitor", "PowerShell"):
        cmd = inp.get("command") or ""
        first = (cmd.split() or [""])[0].rsplit("/", 1)[-1]
        bare = QUOTED.sub("", cmd)  # the command outside its quoted text
        plain = not COMPOUND.search(bare)
        if first in SAFE_FIRST and plain:  # one plain command
            return False
        net = NET.search(cmd) or first in ("http", "https", "xh")
        read = first == "curl" and not WRITE.search(cmd) and plain  # other reads deny: widening this failed open (#5453)
        cli = CLI.search(bare) or re.search(r"\b(ba|z)?sh\s+-c\b", cmd) and CLI.search(cmd)
        return bool(cli or ANNOUNCE.search(cmd) and (net or CODE.search(cmd))
                    or TOPIC.search(cmd) and net and not read)
    name = tool.lower()
    if not name.startswith("mcp__"):
        return False
    verb = name.split("__")[-1]
    if ("announc" in verb or "discussion_topic" in verb or "canvas" in name and (
            "discussion" in verb or "topic" in verb)) and not MCP_READ.search(verb):
        return True
    flat = json.dumps(inp).replace('\\"', '"')
    return bool(re.search(r"canvas|lms|instructure|http|\bapi_|\brequest\b", name.split("__")[1] + " " + verb)
                and TOPIC.search(flat) and re.search(r"is_announcement|\b(POST|PUT)\b|\"method\": \"(?i:post|put)\"", flat))


def user_words(text, top=True):
    """User text: untagged (if `top`), a principal wake message, or a relay's cited entry."""
    out, stack, pos = [], [], 0
    for m in TAG.finditer(text):
        if not re.search(r"[-_]", m.group(2)) and m.group(2).lower() not in ENVELOPE:
            continue  # the user's own markup, such as <b>, stays text
        path = [t for t, _ in stack]
        in_wake = (path[:1] == ["wake"] and path[-1:] == ["message"]
                   and set(path[1:-1]) <= {"project", "thread"})
        cited = path[-2:] == ["relay", "cited"] and path[:-2] in ([], ["coordinator-relay"])
        if (top and not stack) or stack and (in_wake or cited) and stack[-1][1]:
            out.append(text[pos:m.start()])
        closing, tag, attrs = m.group(1), m.group(2).lower(), m.group(3)
        if closing:
            while tag in [t for t, _ in stack] and stack.pop()[0] != tag:  # stray: ignored
                pass
        elif not attrs.rstrip().endswith("/"):
            ok = 'trust="principal"' in attrs if tag == "message" else 'author="user"' in attrs if tag == "cited" else True
            stack.append((tag, ok and (not stack or stack[-1][1])))
        pos = m.end()
    return [p for p in out + ([text[pos:]] if top and not stack else []) if p.strip()]


def _blocks(entry):
    msg = entry.get("message")
    content = msg.get("content") if isinstance(msg, dict) else entry.get("content")
    return content if isinstance(content, list) else [{"type": "text", "text": content or ""}]


def _user_text(entry):
    att = entry.get("attachment") or {}
    if att.get("type") == "queued_command" and att.get("commandMode") != "task-notification" \
            and (att.get("origin") or {}).get("kind") != "peer":
        return str(att.get("prompt") or ""), True
    if entry.get("type") != "user" or entry.get("promptSource") == "sdk":
        return None, False
    text = "\n".join(strip_injected_text(b.get("text") or "") for b in _blocks(entry) if b.get("type") == "text")
    real = bool(is_real_user_turn(entry)) or not entry.get("isMeta") and any(b.get("type") == "image" for b in _blocks(entry))
    return text if text.strip() or not real else "[a message with no text]", real


def verdict(path, tool, inp):
    if is_real_user_turn is None:
        return "scripts/lib/transcript_meta.py could not be loaded"
    try:
        with open(path, encoding="utf-8") as fh:
            entries = [json.loads(line) for line in fh if line.strip()]
    except (OSError, ValueError, TypeError):
        return "the transcript could not be read"
    answered = {b.get("tool_use_id") for e in entries for b in _blocks(e) if b.get("type") == "tool_result"}
    writes = []  # every write since the approval, failed ones included
    for entry in reversed(entries):
        text, top = _user_text(entry)
        words = "\n".join(user_words(text, top)) if text is not None else ""
        if words.strip():  # a harness note with no user words is skipped
            if not APPROVAL.fullmatch(" ".join(words.split())):
                return "the user's latest message is not only an approval of posting it"
            now = [w for w in writes if w[:2] == [tool, inp] and w[2] not in answered]
            if now:  # the call being judged, logged with no result yet
                writes.remove(now[0])
            return "an announcement was already posted after that approval" if writes else None
        if entry.get("type") == "assistant":
            writes += [[b.get("name"), b.get("input"), b.get("id")] for b in _blocks(entry) if b.get("type")
                       == "tool_use" and is_announcement_write(b.get("name") or "", b.get("input") or {})]
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
                f"Refused: this posts or edits a class announcement, and {why} (Ezra, 2026-10-27, ai-config#4780: "
                "never post an announcement without his review and approval of its exact text).\n\nShow the exact "
                "text in chat and ask the user to reply with only \"post the announcement\"; then post that text once."),
        }}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
