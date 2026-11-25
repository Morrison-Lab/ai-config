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

ai-config#6075. Ezra, 2026-11-22: "why not use tools to commit", then "dont bs
me", after the coordinator told him a thread "has no other way to commit" when
the GitHub API tools could commit. That message asked him for nothing, so the
hand-off check above never saw it. A second check now covers a claim that a
step cannot be done ("no other way to commit", "can't push", "unable to
merge"), in the same reply tools and in relays (message_coordinator,
message_thread), where a thread's claim reaches the coordinator first:

  * the message must name the alternatives it checked ("I tried", "checked",
    "ruled out"), and
  * a claim about committing or pushing must name the GitHub API tools
    (`mcp__github__push_files`, `create_or_update_file`, the contents API)
    among them, since those commit without local git.

A sentence that ties the step to the user's grant ("without your mwc") is a
statement of permission, not of impossibility, and is left alone.

A third check follows Ezra's rule of the same night: "you must adversarially
check every claim that my input is needed". A message claims his input is
needed when a sentence says so ("needs your approval", "waiting on you",
"blocked on Ezra", "only you can"), when it hands him a step (the hand-off
check above), and always for a request_decision card. Such a message, from a
thread or from the coordinator relaying it, is denied unless a subagent
launched since the person's last turn, without error, was briefed to refute the
claim adversarially by finding a route without the user ("adversarially ...
a route without Ezra"). The brief is matched by words, so the hook proves that
a check was asked for, not that it was done well.
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
    from tool_names import is_subagent_tool, subagent_brief
except Exception:  # broken install: fail open
    stop_notice = None
    is_real_user_turn = None
    is_subagent_tool = None
    subagent_brief = None
try:
    from fences import strip_fences
except Exception:
    strip_fences = None

TOOL = re.compile(
    r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message|request_decision)$")
EXPLAIN_TOOL = re.compile(r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message)$")
RELAY_TOOL = re.compile(r"^mcp__hearthbot__(?:message_coordinator|message_thread)$")

# A claim that a step cannot be done at all: the impossibility words sit right
# before the step, so "I can't find the merge commit" is not one.
CLAIM_STEP = (
    r"(?:commit(?:s|ting|ted)?|push(?:es|ing|ed)?|merg(?:e|es|ing|ed)|re-?run|deploy|rebase|"
    r"open\s+(?:a|the)\s+PR|slide|dispatch|trigger)\b"
)
ADVERB = r"(?:(?:just|actually|really|directly|safely|also|even|yet|ever|currently|itself)\s+){0,2}"
IMPOSSIBLE = re.compile(
    r"\b(?:no\s+other\s+(?:way|route|option|path|means)|the\s+only\s+(?:way|route|option|path)|"
    r"(?:has|have|had)\s+no\s+(?:way|means|route)|no\s+way|(?:impossible|not\s+possible))\s+to\s+"
    + ADVERB + CLAIM_STEP
    + r"|\b(?:can't|cannot|can\s+not|couldn't|could\s+not|unable\s+to|not\s+able\s+to|"
    r"has\s+no\s+permission\s+to|have\s+no\s+permission\s+to)\s+" + ADVERB + CLAIM_STEP
    + r"|\b" + CLAIM_STEP + r"[^.\n]{0,40}\b(?:won't|will\s+not|can't|cannot)\s+work\b",
    re.I)
# A sentence reporting the route that did work, or a gate that lifts, claims nothing impossible.
CLAIM_CANCEL = re.compile(r"\binstead\b|\bworked\b|\bsucceeded\b|\buntil\b|\bunless\b", re.I)
GIT_WRITE = re.compile(r"\b(?:commit(?:s|ting|ted)?|push(?:es|ing|ed)?)\b", re.I)
# Tied to the user's grant or word: a statement of permission, not of impossibility.
PERMISSION = re.compile(
    r"\b(?:without|until|before|unless)\s+(?:your|you|Ezra)\b|\byour\s+(?:mwc|approval|grant|word|go-?ahead|yes)\b",
    re.I)
CHECKED = re.compile(
    r"\b(?:I|we)\s+(?:have\s+|'ve\s+|also\s+)?(?:tried|attempted|retried|checked|ruled\s+out)\b"
    r"|\b(?:I|we)'ve\s+(?:tried|attempted|retried|checked|ruled\s+out)\b"
    r"|\b(?:what|ways?|routes?|everything|all)\s+(?:I|we)\s+(?:tried|checked)\b"
    r"|\b(?:tried|checked|ruled\s+out)\s*:|\battempts?\s*:|\balternatives?\s+checked\b",
    re.I)
# A claim that the user's input is needed (Ezra, 2026-11-22, ai-config#6075).
NEEDS_INPUT = re.compile(
    r"\b(?:needs?|needed|requires?|required|waiting\s+(?:on|for)|waits?\s+(?:on|for)|"
    r"blocked\s+on|awaiting|held\s+(?:on|for))\s+"
    r"(?:your|Ezra's|the\s+user's|the\s+owner's|you|Ezra|the\s+user|the\s+owner)\b"
    r"|\b(?:needs?|requires?)\s+(?:a\s+)?(?:human|manual\s+(?:step|action|approval))\b"
    r"|\bonly\s+(?:you|Ezra|the\s+user|the\s+owner|a\s+human)\s+can\b"
    r"|\b(?:you|Ezra|the\s+user|the\s+owner|a\s+human)\s+(?:has|have|need|needs|must)\s+to\s+"
    r"(?:approve|decide|confirm|choose|pick|answer|sign\s+off|review)\b"
    r"|\bon\s+hold\s+(?:until|till|for)\s+(?:you|Ezra|the\s+user)\b"
    r"|\b(?:it's|it\s+is)\s+(?:up\s+to\s+you|your\s+call)\b",
    re.I)
NOT_NEEDED = re.compile(
    r"\b(?:no|nothing|not|never|doesn't|does\s+not|don't|do\s+not|isn't|is\s+not|no\s+longer|without)\b",
    re.I)
# The brief of an adversarial check: it hunts for a route that needs no one.
ADVERSARIAL_BRIEF = re.compile(r"\badversarial(?:ly)?\b|\brefute\b|\bdisprove\b", re.I)
ROUTE_BRIEF = re.compile(
    r"\b(?:route|way|path|alternative)s?\b[^.\n]{0,80}\b(?:without|needs?\s+no|not\s+need)\b"
    r"|\bwithout\s+(?:Ezra|the\s+user|the\s+owner|human)\b",
    re.I)
GITHUB_API = re.compile(
    r"\bGitHub\s+(?:API|MCP|tools?)\b|\bMCP\b|\bREST\s+API\b|\bpush_files\b"
    r"|\bcreate_or_update_file\b|\bcontents\s+API\b|\bgit\s+data\s+API\b",
    re.I)

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
    # "If you can paste the links" hands the step back as a condition. Only the
    # modal forms are a lead here; a bare "if you <verb>" is caught below only
    # when an "I'll" clause follows, so "If you push to main, CI runs." passes.
    r"if\s+you(?:'d|\s+would|\s+can|\s+could)|"
    r"(?:once|when|after|as\s+soon\s+as)\s+you(?:'ve|\s+have)?)\s+"
)
# The user named as the one who acts, anywhere in a sentence that names a step.
ACTOR = re.compile(
    r"\b(?:yourself|on\s+you|over\s+to\s+you|your\s+(?:click|press|tap|hands?))\b", re.I)
ACTOR_STEP = re.compile(r"\b" + VERB + r"\b", re.I)
HANDOFF = re.compile(
    LEAD + FILLER + r"(?:" + VERB + r"|" + VERB_ING + r")\b"
    r"|\bwould\s+you\s+mind\s+" + FILLER + VERB_ING + r"\b"
    # "If you paste the links, I'll add them" (2026-11-25: a thread asked Ezra to
    # paste video links that his own machine could find).
    r"|\bif\s+you\s+" + FILLER + VERB + r"\b[^.!?\n]{0,120}?,\s*(?:I'll|I\s+will|I\s+can|I'd|then\s+I)\b"
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


CLAIM_REASON = (
    '[hook: handoff-ask-needs-why] "{sentence}" claims a step cannot be done, and the message '
    "does not name {missing}. Ezra, 2026-11-22 (ai-config#6075): \"why not use tools to commit\", "
    "\"dont bs me\", after a relay said a thread had no other way to commit while the GitHub API "
    "tools could. Before calling a step impossible, try the other routes, then name each one you "
    "checked and its result (\"Checked: ...\"). If one of them works, use it instead of the claim. "
    "See shared/workflow/lab-operating-rules.md."
)


INPUT_REASON = (
    '[hook: handoff-ask-needs-why] "{sentence}" claims the user\'s input is needed, and no '
    "adversarial check ran this turn. Ezra, 2026-11-22 (ai-config#6075): \"you must adversarially "
    "check every claim that my input is needed\". Launch a separate subagent (Agent or Task) whose "
    "brief contains \"adversarially\" (or \"refute\") and asks for \"a route without the user\" "
    "(another tool or API, a retry, a standing grant, a fixed check), and let it finish without "
    "error; this hook reads the brief for those words. Send the claim only if it finds no such "
    "route, and then say what it checked. That day's false claims were \"no other way to commit\" (the GitHub API tools "
    "could) and \"waiting on your approval\" (the thread was not stuck). This holds for a thread and "
    "for the coordinator relaying it. See shared/workflow/lab-operating-rules.md."
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


# transcript-shapes-skip: antigravity -- the transcript is read only for hearthbot tools and Claude Code subagent calls, which Antigravity does not have.
def turn_tool_uses(path: str) -> list:
    """(name, input, failed) for each tool call since the person's last turn."""
    if not path or is_real_user_turn is None:
        return []
    uses, failed = [], set()
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
                    uses, failed = [], set()
                    continue
                message = entry.get("message")
                blocks = message.get("content") if isinstance(message, dict) else None
                if not isinstance(blocks, list):
                    continue
                for block in blocks:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_use" and isinstance(block.get("input"), dict):
                        uses.append((str(block.get("id") or ""), str(block.get("name") or ""),
                                     block["input"]))
                    elif block.get("type") == "tool_result" and block.get("is_error"):
                        failed.add(str(block.get("tool_use_id") or ""))
    except OSError:
        return []
    return [(name, tool_input, use_id in failed) for use_id, name, tool_input in uses]


def explained_earlier_this_turn(path: str) -> bool:
    """True when the reply tool calls since the person's last turn carried both parts."""
    texts = [str(inp.get("text") or "") for name, inp, _ in turn_tool_uses(path)
             if EXPLAIN_TOOL.search(name)]
    # The why and the tries may sit in two messages of the same turn.
    return bool(texts) and not missing("\n".join(texts))


def adversarial_check_ran(path: str) -> bool:
    """True when a subagent since the person's last turn was briefed to find a route without them."""
    for name, tool_input, failed in turn_tool_uses(path):
        if failed or is_subagent_tool is None or not is_subagent_tool(name):
            continue
        brief = subagent_brief(tool_input) if subagent_brief else str(tool_input.get("prompt") or "")
        if ADVERSARIAL_BRIEF.search(brief) and ROUTE_BRIEF.search(brief):
            return True
    return False


def input_claim(text: str, tool: str) -> str:
    """The first sentence claiming the user's input is needed, or ""; a card is one by construction."""
    for sentence in SPLIT.split(own_words(text)):
        match = NEEDS_INPUT.search(sentence)
        # A negation anywhere in the clause before the claim cancels it.
        clause = re.split(r"[,;:]", sentence[:match.start()])[-1] if match else ""
        if match and not NOT_NEEDED.search(clause + match.group(0)):
            return " ".join(sentence.split())
    if tool.endswith("request_decision"):
        return " ".join(text.split())
    return handoff_sentence(text)


def input_claim_reason(text: str, tool: str, path: str) -> str:
    """The denial for a needs-your-input claim with no adversarial check behind it, or ""."""
    sentence = input_claim(text, tool)
    if not sentence or adversarial_check_ran(path):
        return ""
    return INPUT_REASON.format(sentence=sentence[:160])


def handoff_reason(text: str) -> str:
    """The denial for a hand-off ask that lacks the why or the tries, or ""."""
    sentence = handoff_sentence(text)
    gaps = missing(text) if sentence else ""
    return REASON.format(sentence=sentence[:160], missing=gaps) if gaps else ""


def claim_sentence(text: str) -> str:
    """The first sentence, in the agent's own words, claiming a step cannot be done."""
    for sentence in SPLIT.split(own_words(text)):
        if EXEMPT.search(sentence) or PERMISSION.search(sentence) or CLAIM_CANCEL.search(sentence):
            continue
        if IMPOSSIBLE.search(sentence):
            return " ".join(sentence.split())
    return ""


def claim_reason(text: str) -> str:
    """The denial for a can't-do claim that names no alternatives checked, or ""."""
    sentence = claim_sentence(text)
    if not sentence:
        return ""
    gaps = []
    if not CHECKED.search(text):
        gaps.append("the alternatives you checked, each with its result")
    if GIT_WRITE.search(sentence) and not GITHUB_API.search(text):
        gaps.append("the GitHub API tools (mcp__github__push_files, create_or_update_file), "
                    "which commit and push without local git, and why they fail here")
    if not gaps:
        return ""
    return CLAIM_REASON.format(sentence=sentence[:160], missing="; ".join(gaps))


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
        path = str(payload.get("transcript_path") or "")
        reason = handoff_reason(text) or claim_reason(text) or input_claim_reason(text, "", path)
        if reason:
            print(stop_notice(payload, reason, "handoff-ask-needs-why"))
        return 0
    tool = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict) or not (TOOL.search(tool) or RELAY_TOOL.search(tool)):
        return 0
    text = user_text(tool_input)
    reason = ""
    if TOOL.search(tool):
        reason = handoff_reason(text)
        if reason and tool.endswith("request_decision") and explained_earlier_this_turn(
                str(payload.get("transcript_path") or "")):
            reason = ""
    if not reason and not tool.endswith("request_decision"):
        reason = claim_reason(text)
    if not reason:
        reason = input_claim_reason(text, tool, str(payload.get("transcript_path") or ""))
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
