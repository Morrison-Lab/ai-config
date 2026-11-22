#!/usr/bin/env python3
"""PreToolUse and Stop: a hand-off ask must say why no other way works, and what was tried.

ai-config#6068. Ezra, 2026-11-21: "when you ask me to do something you were
supposed to do yourself, you must tell me why no other way would work", then
"and tell me all the ways you tried". The same evening the coordinator asked
him to press merge on ai-config#6066 because a safety classifier had blocked a
thread's merge step, and named neither the block nor the routes it had tried;
he answered "no fix the check".

Denies a user-visible hearthbot message (reply, post_message, update_message,
edit_message, request_decision) when one sentence, in the agent's own words
(fenced code, blockquotes and double-quoted spans removed), hands the user a
step that is the agent's own work (merge, press the merge button, run, push,
re-run, restart, install, delete and the like, asked with "please", "can you",
"you'll need to", "I need you to", "once you ...", "would you mind ...", or a
sentence naming the user as actor: "yourself", "it's on you", "your click")
and the message does not carry both

  * why no other way works ("no other way", "the only way", "why I can't"), and
  * the ways tried ("I tried", "What I tried:", "I retried").

A request_decision card is too short for both, so it passes when the
post_message, reply or edit calls earlier in the same turn carried them.
The why and the tries are matched as phrases, so a hollow "No other way.
I tried." passes; the reviewer rule in adversarial-reviewer.md covers that.
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

# Steps on a system that are the agent's own work. Approve, review, pick, choose,
# decide, confirm and type are the user's to give, and ordinary English verbs
# (update, start, stop, move, set, add, fix) read as requests of another kind,
# so both are left out.
VERB = (
    r"(?:merge|press|click|tap|run|re-?run|push|force-push|restart|reinstall|install|paste|"
    r"enable|disable|delete|reopen|upload|re-?trigger|trigger|dispatch|cancel|"
    r"retry|deploy|slide|rebase|cherry-pick|squash|re-?request|kick\s+off)"
)
VERB_ING = (
    r"(?:merging|pressing|clicking|tapping|running|re-?running|pushing|restarting|installing|"
    r"pasting|deleting|triggering|dispatching|retrying|deploying|rebasing|squashing)"
)
FILLER = (
    r"(?:(?:just|quickly|manually|also|now|then|please|first|kindly|do|"
    r"go\s+ahead\s+and|go\s+and|approve\s+and|squash\s+and)\s+){0,2}"
)
LEAD = (
    r"\b(?:please|kindly|can\s+you|could\s+you|would\s+you|will\s+you|"
    r"(?:I\s+)?need\s+you\s+to|needs\s+you\s+to|I'd\s+like\s+you\s+to|"
    r"you(?:'ll|\s+will|'d|\s+would)?\s+(?:need|have)\s+to|you\s+must|you\s+should|"
    r"you\s+can|you\s+could|over\s+to\s+you\s+to|(?:it's|it\s+is)\s+(?:yours|(?:up\s+)?to\s+you|on\s+you)\s+to|"
    r"ask(?:ing)?\s+you\s+to|for\s+you\s+to|"
    r"(?:once|when|after|as\s+soon\s+as)\s+you(?:'ve|\s+have)?)\s+"
)
# The user named as the one who acts, anywhere in a sentence that names a step.
ACTOR = re.compile(
    r"\b(?:yourself|on\s+you|over\s+to\s+you|your\s+(?:click|press|tap|hands?))\b", re.I)
ACTOR_STEP = re.compile(r"\b" + VERB + r"\b", re.I)
HANDOFF = re.compile(
    LEAD + FILLER + r"(?:" + VERB + r"|" + VERB_ING + r")\b"
    r"|\bwould\s+you\s+mind\s+" + FILLER + VERB_ING + r"\b"
    r"|\b(?:once|when|after)\s+you(?:'ve|\s+have)\s+"
    r"(?:merged|pushed|pressed|clicked|re-?run|restarted|deployed|rebased|installed|deleted)\b"
    r"|(?:^|[\n:])\s*(?:press|click|tap|hit)\s+(?:on\s+)?(?:the\s+)?(?:green\s+)?[`'\"*]*"
    r"(?:merge|re-?run|approve)\b",
    re.I)
# Quoted words are someone else's: a blockquote line or a double-quoted span.
QUOTED = re.compile(r"^[ \t]*>.*$|\"[^\"\n]*\"|\u201c[^\u201d\n]*\u201d", re.M)

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


def own_words(text: str) -> str:
    """`text` without fenced code, blockquote lines or double-quoted spans."""
    text = strip_fences(text) if strip_fences else text
    return QUOTED.sub(" ", text)


def handoff_sentence(text: str) -> str:
    """The first sentence of `text`, in the agent's own words, that hands the user a step."""
    for sentence in SPLIT.split(own_words(text)):
        if EXEMPT.search(sentence):
            continue
        match = HANDOFF.search(sentence)
        if match is None and ACTOR.search(sentence):
            match = ACTOR_STEP.search(sentence)
        if match is None:
            continue
        # A negation only cancels the ask when it sits right before it.
        if NEGATED.search(sentence[max(match.start() - 25, 0):match.end()]):
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


# transcript-shapes-skip: antigravity -- only a Claude Code request_decision call reads the transcript, and Antigravity has no hearthbot tools.
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
    # The why and the tries may sit in two messages of the same turn.
    return bool(texts) and not missing("\n".join(texts))


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
