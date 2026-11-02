#!/usr/bin/env python3
"""PreToolUse: one approval ask per message; a credential gets its own ask.

ai-config#4875. Ezra, 2026-11-02: a message asked for two approvals (extra CI
runners, and use of the ssh key ~/.ssh/id_ed25519_condor). He replied with a
bare "yes", which was relayed as covering both, then asked "what's the condor
key question?", so he had not read the second ask. A bare yes covers only the
primary ask, and any use of a credential or key is its own single-question ask.

Denies

  * a user-visible message or decision card (post_message, edit_message,
    update_message, reply, message_thread, message_coordinator, request_decision,
    post_widget) carrying two or more approval asks; and
  * the same carrying an ask to use a credential or key together with any
    other approval ask; and
  * a start_remote_control whose instructions cite one yes/approval as
    covering several actions or a credential.

A message that says a bare yes covers only the first ask is exempt.
Sibling of no-stepwise-approval-ask.py (asks too often); this one asks too
much at once. Fails open on parse trouble.
"""
import json
import re
import sys

REPLY_TOOL = re.compile(
    r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message|message_thread|"
    r"message_coordinator|request_decision|post_widget)$")
RC_TOOL = re.compile(r"^mcp__hearthbot__start_remote_control$")

CRED = (r"(?:ssh[- ]?keys?|private keys?|api[- ]?keys?|id_(?:ed25519|rsa|ecdsa)\w*|"
        r"\w*token|secrets?|credentials?|passwords?|passphrase|keyring|keychain)")
ASK = re.compile(
    r"\b(?:may\s+I|can\s+I|shall\s+I|should\s+I|do\s+I\s+have\s+your\s+(?:ok|okay|approval|permission)|"
    r"(?:ok|okay)\s+(?:to|if\s+I)|is\s+it\s+(?:ok|okay)|do\s+you\s+approve|need(?:s)?\s+your\s+"
    r"(?:ok|okay|approval|permission)|ask(?:ing)?\s+(?:for\s+)?(?:your\s+)?(?:approval|permission)|"
    r"permission\s+to|your\s+approval|want\s+me\s+to|would\s+you\s+like\s+me\s+to|"
    r"approve\s+(?:me|the|using|use))\b", re.I)
CRED_ASK = re.compile(
    r"\b(?:use|using|load|read|unlock|sign\s+with|ssh\s+with|authenticate\s+with|with)\b"
    r"[^.!?\n]{0,60}?\b" + CRED + r"\b", re.I)
EXEMPT = re.compile(r"\bbare\s+(?:\"?yes\"?|ok(?:ay)?)\s+(?:covers|only\s+covers)\s+(?:only|just)\b"
                    r"|\b(?:yes|ok(?:ay)?)\s+(?:covers|means)\s+only\b", re.I)
SENT = re.compile(r"(?<=[.!?])\s+|\n+")

RC_CITES = re.compile(r"\b(?:yes|approved|approval|go-?ahead)\b", re.I)
RC_BUNDLE = re.compile(r"\b(?:both|all\s+(?:of\s+)?(?:these|them|three|two|the\s+above)|"
                       r"covers?\s+(?:both|all)|and\s+(?:also\s+)?(?:use|using))\b", re.I)

REASON = (
    "[hook: no-bundled-approval-ask] {what}. A bare yes covers only the primary ask; Ezra "
    "answered yes to a message that also asked for his ssh key and had not read that part "
    "(2026-11-02, ai-config#4875). Send one ask per message, and give any use of a credential "
    "or key its own single-question ask. If asks must travel together, say that a bare yes "
    "covers only the first. shared/workflow/lab-operating-rules.md."
)


def flatten(tool_input):
    parts = []
    for key in ("text", "question", "reason", "instructions"):
        v = tool_input.get(key)
        if isinstance(v, str):
            parts.append(v)
    for opt in tool_input.get("options") or []:
        if isinstance(opt, dict):
            parts.extend(str(opt.get(k, "")) for k in ("label", "consequence"))
    return "\n".join(parts)


def strip_quotes(text):
    return re.sub(r"```.*?```|^>.*$", "", text, flags=re.S | re.M)


def check_message(text):
    text = strip_quotes(text)
    if EXEMPT.search(text):
        return None
    # Two phrasings of one either/or question ("Should I push, or would you
    # like me to wait?") are one ask, so a sentence with "or" counts once.
    # A credential ask still pairs with every other ask phrase, "or" or not.
    n_asks = sum(1 if ASK.search(s) and re.search(r"\bor\b", s) else len(ASK.findall(s))
                 for s in SENT.split(text))
    has_cred = any(ASK.search(s) and CRED_ASK.search(s) for s in SENT.split(text))
    if has_cred and len(ASK.findall(text)) >= 2:
        return "This message asks to use a credential or key alongside another ask"
    if n_asks >= 2:
        return "This message carries {} approval asks".format(n_asks)
    return None


ROUTINE = re.compile(r"\b(?:allow-?listed|routine|as usual|standing\s+grant|already\s+approved)\b", re.I)


def new_cred_use(text):
    """A credential use that is not a described routine, allow-listed one."""
    return any(CRED_ASK.search(s) and not ROUTINE.search(s) for s in SENT.split(text))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    tool = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    what = None
    if REPLY_TOOL.search(tool):
        what = check_message(flatten(tool_input))
    elif RC_TOOL.search(tool):
        text = tool_input.get("instructions")
        # Any approval wording, negated or not, plus a non-routine credential use is denied:
        # the brief must call a routine use routine or allow-listed.
        cites = isinstance(text, str) and RC_CITES.search(text) and not EXEMPT.search(text)
        if cites and (RC_BUNDLE.search(text) or new_cred_use(text)):
            what = "These instructions cite one yes/approval as covering several actions or a credential"
    if what:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": REASON.format(what=what)}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
