#!/usr/bin/env python3
"""Stop-hook guard: a reply says "I can't" or "only you can", and the turn never searched the tool list.

THE MEASURED CASE (2026-11-09, Data 571 runner thread, ai-config#5136)
Ezra asked the runner to switch its own permission mode.  It replied "I can't,
only you control that" without looking at its tools, though it had a mode-switch
tool.  Ezra: "never forget to check your available tools".

WHAT IT CHECKS
The final reply claims an inability or hands the action to the user ("I can't
switch", "I'm unable to", "only you can"), AND the turn made no ToolSearch call.
A tool in the visible list leaves no trace in the transcript, so a session with
no deferred tools can still be warned once.

WHY A WARNING AND NOT A DENY
Whether a tool exists is not decidable from the transcript, and some claims are
true (permission rules in settings files change only through a prompt Ezra
approves).  The stop is interrupted once per message (agent_notice.stop_notice).
"The user did X" claims the user never made cannot be checked lexically; the
rule covers them in prose.

transcript-shapes-skip: antigravity -- Antigravity sessions have no deferred-tool search, so the ToolSearch condition cannot hold there.

See shared/workflow/check-tools-before-saying-cant.md.  Lexical, and fails OPEN.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

_LIB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
from agent_notice import stop_notice  # noqa: E402

REPLY_TOOL_RX = re.compile(r"(^|__)(reply|post_message|update_message)$", re.I)
APOS = "['\u2019]?"
# A bare "I can't" is mostly idiom ("I can't believe", "I can't tell", "I can't find"),
# so it counts only before an action verb or "from this session" (review of #5137).
ACTION = (r"(?:do|change|switch|set|run|start|stop|access|reach|create|edit|modify|merge|push"
          r"|open|install|enable|disable|approve|grant|use|send|write|add|attach|post|delete"
          r"|update|make|perform|fetch|download|clone|connect|control|invoke|call|touch)")
CLAIM_RX = re.compile(
    rf"\b(?:i|we)\s+(?:can{APOS}t|cannot|can not)\s+(?:\w+\s+){{0,2}}?{ACTION}\b"
    rf"|\b(?:i|we)\s+(?:can{APOS}t|cannot|can not)\b[^.\n]{{0,60}}\b(?:from this session|on my own|myself)\b"
    rf"|\b(?:i|we) (?:am|are|'m) (?:unable|not able) to\b"
    rf"|\b(?:i{APOS}m|we{APOS}re) (?:unable|not able) to\b"
    rf"|\b(?:i|we) have no (?:tool|way|means) (?:to|for)\b"
    rf"|\b(?:i|we) (?:do not|don{APOS}t) have (?:a|the|any) (?:tool|way|means|access)\b"
    r"|\bonly (?:you|ezra|the user|a human|a person)\s+(?:can|could|may|control|controls|has|have)\b"
    r"|\bno (?:tool|way|means) (?:exists )?(?:to|for)\b"
    r"|\bnot something (?:i|we) can\b",
    re.I)
QUOTED_RX = re.compile(r"`[^`]*`|\"[^\"]*\"|\u201c[^\u201d]*\u201d")


def _blocks(msg):
    blocks = (msg.get("message") or {}).get("content") or msg.get("content") or []
    return blocks if isinstance(blocks, list) else []


def read_turn(path):
    """(final visible reply text, whether the turn called ToolSearch)."""
    last_text = last_reply = ""
    saw_reply_tool = searched = False
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                try:
                    m = json.loads(line)
                except Exception:
                    continue
                if m.get("type") == "user" or m.get("role") == "user":
                    content = _blocks(m)
                    if not any(isinstance(b, dict) and b.get("type") == "tool_result"
                               for b in content):
                        searched = False
                    continue
                if not (m.get("type") == "assistant" or m.get("role") == "assistant"):
                    continue
                blocks = _blocks(m)
                txt = "".join(b.get("text", "") for b in blocks
                              if isinstance(b, dict) and b.get("type") == "text")
                if txt.strip():
                    last_text = txt
                for b in blocks:
                    if not isinstance(b, dict) or b.get("type") != "tool_use":
                        continue
                    name = b.get("name") or ""
                    if name == "ToolSearch":
                        searched = True
                    if REPLY_TOOL_RX.search(name):
                        saw_reply_tool = True
                        inp = b.get("input")
                        t = inp.get("text") if isinstance(inp, dict) else None
                        if isinstance(t, str) and t.strip():
                            last_reply = t
    except Exception:
        return "", True
    return (last_reply if saw_reply_tool else last_text), searched


def find_claim(text):
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", QUOTED_RX.sub("", text)):
        m = CLAIM_RX.search(sentence)
        if m:
            return sentence.strip()[:160]
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        text, searched = read_turn(payload.get("transcript_path") or "")
    except Exception:
        return 0
    claim = find_claim(text) if text else None
    if not claim or searched:
        return 0
    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-cant-tools-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w", encoding="utf-8").close()
    except Exception:
        pass
    print(stop_notice(
        payload,
        f"Your reply says you cannot do something, or that only the user can: \"{claim}\". "
        "This turn never searched for tools. Check your visible tool list, then call "
        "ToolSearch (deferred tools are not in it, e.g. mcp__ccd_session_mgmt__set_session_permission_mode, "
        "add_repo, start_remote_control) before claiming a limit, and use the tool if one fits "
        "(Ezra, 2026-11-09: \"never forget to check your available tools\"). Never say the "
        "user did something they did not say. Real limits stay: never edit permission rules "
        "in settings files except through a prompt Ezra approves. If a tool search finds "
        "nothing, say what you searched. See shared/workflow/check-tools-before-saying-cant.md.",
        "flag-cant-without-tool-check",
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
