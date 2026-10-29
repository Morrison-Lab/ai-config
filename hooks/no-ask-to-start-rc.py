#!/usr/bin/env python3
"""PreToolUse: do not ask the user to start or run Remote Control.

Ezra, 2026-10-15: "you can launch sessions on that machine without me; stop
forgetting." Ezra, 2026-10-29 14:54 and 14:55 UTC, after the coordinator asked him to
start Remote Control on cf463-02: "you can run remote control yourself" and "you
should have known that". The standing permission is recorded in
shared/workflow/fetch-untrusted-files.md (ai-config#4516) and
shared/workflow/lab-operating-rules.md.

Blocks (deny) an outgoing message that asks the user to start, run, launch or
restart Remote Control or `claude remote-control`: the hearthbot reply tools
(post_message, message_thread, message_coordinator, edit_message,
request_decision, post_widget) and the forge comment, PR and issue tools. It reads
every string in the tool input, nested cards and option lists included. The denial points at
`start_remote_control`, which the agent calls itself on cf463-02 and the XPS.

It is not an ask when the words are quoted (double quotes, a fenced block, a
blockquote line), when a negation such as "never" or "no need" comes before the
ask in its sentence, or when "yourself" follows it. A paraphrase it does not
recognise gets through; this is a wording check. Fails open on parse trouble.
"""
import json
import re
import sys

TOOL = re.compile(
    r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message|message_thread|message_coordinator|request_decision|post_widget)$"
    r"|^mcp__github__(?:add_issue_comment|update_issue_comment|add_reply_to_pull_request_comment"
    r"|add_comment_to_pending_review|pull_request_review_write|create_pull_request|update_pull_request|issue_write)$")

SENTENCE_BREAK = re.compile(
    r"(?<!\be\.g\.)(?<!\bi\.e\.)(?<!\bvs\.)(?<!\betc\.)(?<=[.!?])\s+|\n+", re.I)

# Quoted words mention an ask, they do not make one.
QUOTED = re.compile(
    r"```.*?```|^>.*$|\"[^\"\n]*\"|\u201c[^\u201d\n]*\u201d|(?<!\w)'[^'\n]{3,}'(?!\w)"
    r"|`(?!\s*claude\b)[^`\n]*`", re.S | re.M)
# A PR or issue body lists the agent's own plan and record as bullets and numbered steps.
# A bare item is the agent's own step, by design; an ask to the user carries a cue.
# An item aimed at the reader ("please", "can you", "you") stays, so a bulleted ask is still caught.
LIST_ITEM = re.compile(
    r"^\s*(?:[-*+]|\d+[.)])\s(?!.*\b(?:please|can you|could you|would you|you|your)\b).*$", re.M | re.I)

RC = r"(?:remote[-\u2010\u2011 ]{0,3}control|(?-i:\bRC\b))"
BASE = r"(?:start|run|launch|restart|reconnect|spin(?: up)?|fire up|kick off|enable|turn on|bring up)"
# Past and -ing forms are asks only after a lead-in aimed at the user ("once you've started");
# at the start of a sentence they are the agent's own status report.
VERB = r"(?:" + BASE + r"|started|launched|restarted|starting|launching|restarting|running|spinning(?: up)?)"
# The ask ends at the name: "start Remote Control on the Mac", not "run remote control tests".
RC_END = (r"(?:\s+(?:session|server|command))?"
          r"(?=`?\s*(?:$|[;,.!?(\u2014])|`?\s+(?:-\w|--\w|-\s)|`?\s+(?:on|from|in|at|now|first|again|please|and|before|so|for|with)\b)")
FILL = r"[^.!?\n]{0,60}?"

ASKS = (
    # "please start RC", "can you run Remote Control", "you need to launch claude remote-control"
    re.compile(
        r"\b(?:please,?(?: kindly)?|kindly|go ahead and|can you|could you|would you(?: mind)?|will you|mind|you(?:'ll| will)? need to|you have to|you must|"
        r"you can|you could|you should|(?:I )?need you to|(?:I )?want you to|I(?:'d| would) like you to|"
        r"ask(?:ing)? you to|have you|if you (?:can|could|would)|once you(?:'ve| have)|when you(?:'ve| have))\s+"
        + VERB + r"\b" + FILL + RC + RC_END, re.I),
    # sentence-opening imperative: "Start Remote Control on cf463-02."
    re.compile(r"(?:^|[.!?\n]\s*)(?:[-*]\s+|\d+[.)]\s+)?" + BASE + r"\b" + FILL + RC + RC_END, re.I),
    # "Open a terminal and start Remote Control"
    re.compile(r"\bopen (?:a|your|the) (?:terminal|shell|console)\b" + FILL + BASE + r"\b" + FILL + RC + RC_END, re.I),
    # passive: "Remote Control needs to be started on the Mac"
    re.compile(RC + FILL + r"\b(?:needs?|has|have|must|should) (?:to )?be (?:started|launched|run|enabled)\b"
               + FILL + r"\b(?:by you|on (?:your|the) |from (?:your|the) )", re.I),
    # "I need a Remote Control session started on your Mac"
    re.compile(r"\b(?:need|want) (?:an? )?" + RC + r"(?: session)?\s+(?:to be )?(?:started|launched|restarted)\b", re.I),
    # "on your machine, start RC" and "from your terminal run claude remote-control"
    re.compile(r"\b(?:on|from|in) (?:your|the) (?:machine|laptop|Mac|box|terminal|computer|XPS)\b" + FILL + VERB + r"\b" + FILL + RC, re.I),
)

# A negation counts only before the ask, so "start RC, don't forget" is still an ask.
NEGATION = re.compile(
    r"\b(?:never|won't|will not|don't|do not|doesn't|not (?:ask|need)|no need|without asking|"
    r"without you|instead of asking|rather than asking|stop asking|why did I|did I|do I)\b", re.I)
CLAUSE_BREAK = re.compile(r"[;:,\u2014]|\s-+\s")
YOURSELF = re.compile(r"^[^.!?\n]{0,25}\byourself\b", re.I)

REASON = (
    "[hook: no-ask-to-start-rc] This message asks the user to start or run Remote Control. "
    "Ezra's standing permission (2026-10-15; again 2026-10-29: \"you can run remote control yourself\") "
    "lets you start it yourself on cf463-02 or the XPS. Call mcp__hearthbot__start_remote_control "
    "(its card is the only approval), brief the session, and report in the past tense. "
    "Ask only for a permission prompt the box itself raises, or when cf463-02 needs sudo. "
    "shared/workflow/fetch-untrusted-files.md; shared/workflow/lab-operating-rules.md."
)


def asked(text: str, forge: bool = False) -> bool:
    text = QUOTED.sub(" ", text)
    if forge:
        text = LIST_ITEM.sub(" ", text)
    for sentence in SENTENCE_BREAK.split(text):
        for pattern in ASKS:
            for match in pattern.finditer(sentence):
                if NEGATION.search(CLAUSE_BREAK.split(sentence[:match.start()])[-1] + match.group(0)[:14]):
                    continue
                if YOURSELF.search(sentence[match.end():]):
                    continue
                return True
    return False


def strings(value, depth=0):
    """Every string in a tool input, whatever its field name, so a card or option list is read too."""
    if isinstance(value, str):
        yield value
    elif depth < 4 and isinstance(value, dict):
        for item in value.values():
            yield from strings(item, depth + 1)
    elif depth < 4 and isinstance(value, list):
        for item in value:
            yield from strings(item, depth + 1)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    if not TOOL.search(str(payload.get("tool_name") or "")):
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    forge = str(payload.get("tool_name")).startswith("mcp__github__")
    if any(asked(text, forge) for text in strings(tool_input)):  # nested cards and option lists included
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": REASON,
            }
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
