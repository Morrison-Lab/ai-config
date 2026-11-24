#!/usr/bin/env python3
"""PreToolUse deny: the first reply to a `cai:` message says where the rule is going.

Ezra, 2026-11-24, in an mlg thread. He sent "cai: never make excuses like this;
install the software you need". The reply said only that TeX was being
installed. He asked "did you not recognize `cai:`", and then "then why didn't
you say you were going to do it in your original response to my original
`cai: ` comment?".

no-user-correction-without-mechanism.py makes the turn build a mechanism before
Stop. It does not make the reply tell the user so. This hook covers that half.

DENIES an `mcp__hearthbot__post_message` when all three hold:
- the user's latest message has a line starting `cai:` (or `ca:`);
- no reply since that message has named the routing;
- this reply does not name it either.
A reply names the routing when it mentions ai-config, a hook, a skill, a
memory or rule file, a check, or a `Mechanism:` line.
A message whose `cai:` is quoted, fenced or inside a code span does not count,
because remind-encode-user-correction.py's typed_text() strips those.
ALLOW_CAI_REPLY_WITHOUT_ROUTING=1 overrides.
Fails open on parse trouble or a missing helper.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
_LIB = os.path.join(os.path.dirname(HERE), "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

OVERRIDE = "ALLOW_CAI_REPLY_WITHOUT_ROUTING"
POST = "mcp__hearthbot__post_message"
CAI = re.compile(r"^\s*cai?\s*:", re.I | re.M)
ROUTED = re.compile(
    r"\bai-config\b|\bhooks?\b|\bskills?\b|\bmemor(?:y|ies)\b|\bAGENTS\.md\b|\bCLAUDE\.md\b"
    r"|\bshared/\S+\.md\b|\bchecks?\b|^\s*Mechanism:", re.I | re.M)

REASON = (
    "[hook: no-cai-reply-without-routing] The user's latest message starts a line with `cai:`, "
    "and no reply since then says where the rule is going. Ezra, 2026-11-24: \"why didn't you "
    "say you were going to do it in your original response to my original `cai: ` comment?\" "
    "Say in this reply which ai-config mechanism you are building (hook, skill, memory, shared "
    "fragment, gha check) and that its PR comes this turn, alongside the immediate fix. "
    "See skills/config-ai/SKILL.md."
)


def _load(name):
    from sibling import load_sibling
    return load_sibling(__file__, name, required=True)


def post_text(block):
    if block.get("type") != "tool_use" or block.get("name") != POST:
        return None
    return str((block.get("input") or {}).get("text") or "")


def owed(path, human_text, typed_text):
    """True when the latest human message has `cai:` and no post since named the routing."""
    pending = False
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            try:
                m = json.loads(line)
            except Exception:
                continue
            if not isinstance(m, dict) or m.get("isSidechain"):
                continue
            role = m.get("type") or m.get("role")
            if role == "user":
                text = human_text(m)
                if text is not None and text.strip():
                    pending = bool(CAI.search(typed_text(text)))
            elif role == "assistant" and pending:
                blocks = (m.get("message") or {}).get("content") or []
                for b in blocks if isinstance(blocks, list) else []:
                    text = post_text(b) if isinstance(b, dict) else None
                    if text is not None and ROUTED.search(text):
                        pending = False
    return pending


def denial(payload):
    if os.environ.get(OVERRIDE) or not isinstance(payload, dict):
        return None
    if payload.get("tool_name") != POST:
        return None
    text = str((payload.get("tool_input") or {}).get("text") or "")
    if ROUTED.search(text):
        return None
    path = payload.get("transcript_path") or ""
    if not path or not os.path.isfile(path):
        return None
    corr = _load("remind-encode-user-correction.py")
    mech = _load("no-user-correction-without-mechanism.py")
    return REASON if owed(path, mech.human_text, corr.typed_text) else None


def main():
    try:
        payload = json.load(sys.stdin)
        reason = denial(payload)
    except Exception:
        return 0
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
