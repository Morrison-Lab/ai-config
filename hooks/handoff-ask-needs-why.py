#!/usr/bin/env python3
"""PreToolUse and Stop: a hand-off ask must say why no other way works, and what was tried.

ai-config#6068. Ezra, 2026-11-21: "when you ask me to do something you were
supposed to do yourself, you must tell me why no other way would work", then
"and tell me all the ways you tried". The same evening the coordinator asked
him to press merge on ai-config#6066 because a safety classifier had blocked a
thread's merge step, and named neither the block nor the routes it had tried;
he answered "no fix the check".

Denies a user-visible hearthbot message (reply, post_message, update_message,
edit_message, request_decision) when one sentence hands the user a step that is
the agent's own work (merge, press or click a button, run, push, re-run,
restart, install, edit, delete and the like, asked with "please", "can you",
"you'll need to", "I need you to", "once you ...", or an imperative that opens
the sentence) and the message does not carry both

  * why no other way works ("no other way", "the only way", "why I can't"), and
  * the ways tried ("I tried", "What I tried:", "I retried").

A request_decision card is too short for both, so it passes when a
post_message, reply or edit earlier in the same turn carried them.
A sentence about a secret, token, password, sign-in or connector is exempt,
since those steps were never the agent's to do.
The Stop registration scans a plain final message (fenced blocks removed) and
blocks once per turn through stop_notice.
ALLOW_HANDOFF_WITHOUT_WHY=1 overrides. Fails open on parse trouble.
"""
import json
import os
import re
import sys

_LIB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "scripts", "lib"
)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
try:
    from agent_notice import stop_notice
    from transcript_meta import is_real_user_turn
except Exception:  # broken install: fail open
    stop_notice = None
    is_real_user_turn = None
try:
    from fences import strip_fences
except Exception:
    strip_fences = None

TOOL = re.compile(
    r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message|request_decision)$")
EXPLAIN_TOOL = re.compile(r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message)$")

# The agent's own steps. Approve, review, pick, choose, decide, confirm and type
# are the user's to give, so they are left out.
VERB = (
    r"(?:merge|press|click|tap|hit|run|re-?run|push|restart|reinstall|install|paste|"
    r"enable|disable|add|set|delete|remove|close|reopen|edit|change|update|upload|"
    r"re-?trigger|trigger|dispatch|start|stop|cancel|rename|move|create|fix|resolve|"
    r"retry|apply|deploy|slide|rebase|cherry-pick|label|kick\s+off)"
)
FILLER = r"(?:(?:just|quickly|manually|also|now|then|please|go\s+and|first)\s+){0,2}"
LEAD = (
    r"\b(?:please|can\s+you|could\s+you|would\s+you|will\s+you|(?:I\s+)?need\s+you\s+to|"
    r"you(?:'ll|\s+will|'d|\s+would)?\s+(?:need|have)\s+to|you\s+must|you\s+should|"
    r"(?:it's|it\s+is)\s+up\s+to\s+you\s+to|ask(?:ing)?\s+you\s+to|for\s+you\s+to|"
    r"(?:once|when|after|as\s+soon\s+as)\s+you)\s+"
)
HANDOFF = re.compile(
    LEAD + FILLER + VERB + r"\b"
    r"|(?:^|[\n:]|^\W+)\s*(?:press|click|tap|hit)\b[^.!?\n]{0,40}\b(?:merge|button|re-?run|approve)\b"
    r"|(?:^|[\n:])\s*(?:merge|re-?run|push|restart)\s+(?:it|them|the\s+PRs?|PR|#\d+|\w+#\d+|this|that)\b",
    re.I)

# Steps only the user can do: a secret, or a sign-in or connector.
EXEMPT = re.compile(
    r"\b(?:secrets?|tokens?|passwords?|passphrases?|credentials?|api\s+keys?|"
    r"sign(?:ed)?[- ]?in|log(?:ged)?[- ]?in|re-?connect|connectors?|re-?authenticate)\b",
    re.I)
NEGATED = re.compile(r"\b(?:don't|do\s+not|no\s+need|never|without\s+you)\b", re.I)

WHY = re.compile(
    r"\bno\s+other\s+(?:way|route|option|path)s?\b|\bthe\s+only\s+(?:way|route|option|path)\b"
    r"|\bonly\s+you\s+can\b|\bwhy\s+(?:I|we|this|it)\s+(?:can't|cannot|couldn't|could\s+not)\b"
    r"|\bwhy\s+no\s+other\b|\bnone\s+of\s+(?:them|those|these)\s+(?:worked|works|work)\b",
    re.I)
TRIED = re.compile(
    r"\b(?:I|we)\s+(?:have\s+|'ve\s+|also\s+)?(?:tried|attempted|retried)\b"
    r"|\b(?:I|we)'ve\s+(?:tried|attempted|retried)\b"
    r"|\b(?:what|ways?|routes?|everything|all)\s+(?:I|we)\s+tried\b|\btried\s*:|\battempts?\s*:",
    re.I)

SPLIT = re.compile(r"(?<=[.!?;])\s+|\n+")

REASON = (
    '[hook: handoff-ask-needs-why] "{sentence}" hands the user a step that is your own work, '
    "and the message does not say {missing}. Ezra, 2026-11-21 (ai-config#6068): \"when you ask me "
    "to do something you were supposed to do yourself, you must tell me why no other way would work\" "
    "and \"tell me all the ways you tried\". First try every route you have (retry a denied step "
    "unchanged once, another tool or API, a fresh session, fixing the check that blocked you). If "
    "the hand-off still stands, put both in the message: why no other way works (name the block and "
    "why it holds), and every way you tried, each with its result (\"What I tried: ...\"). For a "
    "decision card, post them in a message first, in the same turn. "
    "See shared/workflow/lab-operating-rules.md."
)


def user_text(tool_input: dict) -> str:
    parts = [tool_input.get("text"), tool_input.get("question"), tool_input.get("reason")]
    for opt in tool_input.get("options") or []:
        if isinstance(opt, dict):
            parts += [opt.get("label"), opt.get("consequence")]
    return "\n".join(p for p in parts if isinstance(p, str))


def handoff_sentence(text: str) -> str:
    for sentence in SPLIT.split(text):
        match = HANDOFF.search(sentence)
        if not match or EXEMPT.search(sentence):
            continue
        if NEGATED.search(sentence[:match.start() + 1]) or NEGATED.search(match.group(0)):
            continue
        return " ".join(sentence.split())
    return ""


def missing(text: str) -> str:
    gaps = []
    if not WHY.search(text):
        gaps.append("why no other way works")
    if not TRIED.search(text):
        gaps.append("every way you tried")
    return " or ".join(gaps)


def explained_earlier_this_turn(path: str) -> bool:
    """True when a reply tool call since the person's last turn carried both parts."""
    if not path or is_real_user_turn is None:
        return False
    texts = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(entry, dict) or entry.get("isSidechain"):
                    continue
                if is_real_user_turn(entry):
                    texts = []
                    continue
                message = entry.get("message")
                blocks = message.get("content") if isinstance(message, dict) else None
                if entry.get("type") != "assistant" or not isinstance(blocks, list):
                    continue
                for block in blocks:
                    if (isinstance(block, dict) and block.get("type") == "tool_use"
                            and EXPLAIN_TOOL.search(str(block.get("name") or ""))
                            and isinstance(block.get("input"), dict)):
                        texts.append(str(block["input"].get("text") or ""))
    except OSError:
        return False
    return any(not missing(t) for t in texts)


def main() -> int:
    if os.environ.get("ALLOW_HANDOFF_WITHOUT_WHY") == "1":
        return 0
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    if not isinstance(payload, dict):
        return 0
    if payload.get("hook_event_name") == "Stop":
        text = payload.get("last_assistant_message")
        if not isinstance(text, str) or stop_notice is None:
            return 0
        text = strip_fences(text) if strip_fences else text
        sentence = handoff_sentence(text)
        gaps = missing(text) if sentence else ""
        if gaps:
            print(stop_notice(payload, REASON.format(sentence=sentence[:160], missing=gaps),
                              "handoff-ask-needs-why"))
        return 0
    tool = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input")
    if not TOOL.search(tool) or not isinstance(tool_input, dict):
        return 0
    text = user_text(tool_input)
    sentence = handoff_sentence(text)
    if not sentence:
        return 0
    gaps = missing(text)
    if not gaps:
        return 0
    if tool.endswith("request_decision") and explained_earlier_this_turn(
            str(payload.get("transcript_path") or "")):
        return 0
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": REASON.format(sentence=sentence[:160], missing=gaps),
    }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
