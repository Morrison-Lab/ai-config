#!/usr/bin/env python3
"""Stop-hook guard: a reply that parks work as "waiting on" another tracked item.

THE MEASURED CASE (2026-11-06, Morrison-Lab project thread)
-----------------------------------------------------------
A thread finishing the mds/mcs consolidation ended its turn with
"mds#649 waits on gha#1544" and stopped. gha#1544 was an open issue with a
clean, unmerged PR (gha#1545) that the thread was free to drive, and the
gha repo carries a standing merge grant. Nothing about the dependency
needed the user. Six hours later the user wrote "why did you stop? don't
stop", and then "never do that again". A dependency on another issue or PR
is work to do; only a step that needs a person is a reason to stop.

WHAT IT CHECKS
--------------
Any user-visible output of the current turn (a reply-tool payload such as
hearthbot post_message or claude-code-remote send_message, or assistant
text, since the person last wrote), with code fences and non-ref code
spans stripped, has a sentence whose parking phrase ("waits on",
"blocked on/by", "parked on", "depends/depending on", "held until",
"held pending") takes a tracked item as its object within six tokens, or
that says "holding X until <item> merges", "once <item> lands", or
"<item> needs to merge first". Every output counts, so a park followed by
a closing line is still caught.
A tracked item is an issue/PR URL, owner/repo#N, repo#N, or #N, but not a
file anchor such as README.md#2.

The object rule keeps reports out: "PR #12 is waiting on the runner" and
"I merged gha#1545, which mds#649 was waiting on" name the item, but not as
what is waited on, and a CI noun ("Waiting on CI for #12") ends the object.
A person-only gate ("needs you", "your approval", "requires a manual
action") exempts only its own clause and trailing which-clauses; a bare
"mwc" or "approval" elsewhere does not.

WHY IT BLOCKS ONCE RATHER THAN EVERY TIME
-----------------------------------------
The deny form is the default (ai-config#4741). It blocks the stop once per
turn through agent_notice.stop_notice, so the agent must either start the
blocking work or say which person-only step stops it. A second stop in the
same turn passes, because a lexical match cannot tell a dependency the
agent cannot touch (another org's repo, a person's PR it may not push to)
from one it can, and a hook that never lets go would trap that case.
"""
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.realpath(__file__))
_LIB = os.path.join(os.path.dirname(_HERE), "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

try:
    from agent_notice import stop_notice
except Exception:  # pragma: no cover - library missing in an odd install
    def stop_notice(payload, message, hook):  # noqa: D103
        if payload.get("stop_hook_active"):
            return json.dumps({"systemMessage": message})
        return json.dumps({"decision": "block", "reason": message, "systemMessage": message})

try:
    from fences import strip_code
except Exception:  # pragma: no cover
    _FENCE_RE = re.compile(r"```.*?```|~~~.*?~~~", re.S)
    _SPAN_RE = re.compile(r"(`+)[\s\S]*?\1")

    def strip_code(text):  # noqa: D103
        return _SPAN_RE.sub(" ", _FENCE_RE.sub(" ", text))

HOOK = "no-park-on-tracked-blocker"

# A tracked item: an issue/PR URL, owner/repo#N, repo#N, or #N. A file
# anchor (README.md#2, docs/spec.json#2) is not an item. A bare x/y#N stays
# an item, as GitHub's own autolinker reads it, so docs/setup#2 is accepted
# as a known false positive.
_REF = (
    r"(?:https?://[^\s/]+/[^\s)\]]*?/(?:issues|pull|pulls|merge_requests)/\d+"
    r"|(?<![\w./-])[\w-]+/[\w-]+(?:\.[\w-]+)?(?<!\.json)(?<!\.md)(?<!\.qmd)(?<!\.html)"
    r"(?<!\.rst)(?<!\.txt)(?<!\.yml)(?<!\.yaml)(?<!\.py)(?<!\.R)#\d+\b"
    r"|(?<![\w./-])[A-Za-z][\w-]*#\d+\b"
    r"|(?<![\w/#&.])#\d+\b)"
    r"(?!['\u2019]s\b)"
)
REF_RX = re.compile(_REF, re.I)
_REF_SPAN_RX = re.compile(r"(`+)\s*(" + _REF + r")\s*\1", re.I)

# A parking phrase whose object is read token by token (see _object_is_ref).
PHRASE_RX = re.compile(
    r"\b(?:wait(?:s|ing)?\s+(?:on|for)"
    r"|blocked\s+(?:on|by|until)"
    r"|held\s+(?:up\s+)?(?:on|by|until)"
    r"|parked\s+(?:on|behind|until)"
    r"|on\s+hold\s+(?:for|until|pending)"
    r"|(?:held|parked|is|are|remains?|stays?)\s+pending"
    r"|depend(?:s|ing|ent)?\s+on)\s+",
    re.I,
)
_DONE = r"(?:merges|lands|ships|closes|is\s+(?:merged|ready|fixed|done|closed|resolved)|gets\s+merged)"
# Forms that name the item inside the phrase rather than after it.
FORM_RX = [
    # "holding X until gha#1 merges": needs a parking verb before "until".
    re.compile(
        r"\b(?:hold\w*|held|park\w*|wait\w*|stop\w*|paus\w*|leav\w*|defer\w*|keep\w*|resum\w*)\b"
        r"(?:[^.!?\n]|\.(?!\s)){0,80}?\buntil\s+(?:[^.!?\n]|\.(?!\s)){0,60}?" + _REF
        + r"(?:[^.!?\n]|\.(?!\s)){0,40}?\b" + _DONE + r"\b",
        re.I,
    ),
    # "after gha#1 merges" / "once gha#1 lands": present tense, so future.
    re.compile(r"\b(?:after|once|when)\s+(?:\S+\s+){0,3}?" + _REF + r"\s+" + _DONE + r"\b", re.I),
    # "gha#1 needs to merge first".
    re.compile(_REF + r"\s+(?:needs|has|must)\s+(?:to\s+)?(?:merge|land|ship)\s+first\b", re.I),
]
# A wait on CI, a runner or a build is not a wait on a tracked item, even
# when an item is named after it ("Waiting on CI for #12").
_NOT_ITEM = re.compile(
    r"^(?:ci|checks?|runners?|builds?|jobs?|workflows?|tests?|deploy\w*|tags?|pipelines?|actions?)$",
    re.I,
)
_TOKEN_STRIP = "[](){}*_\"'`<>,:"
# A clause that gates the park on a person-only step.
PERSON_GATE_RX = re.compile(
    r"\bneeds?\s+(?:you|your|ezra|the\s+user|a\s+(?:human|person|maintainer|reviewer))\b"
    r"|\b(?:your|ezra['\u2019]s|the\s+user['\u2019]s|a\s+maintainer['\u2019]s)\s+"
    r"(?:approval|go-?ahead|answer|decision|review|click|sign-?in|merge)\b"
    r"|\b(?:wait(?:s|ing)?\s+(?:on|for)|blocked\s+(?:on|by)|needs?|requires?)\s+"
    r"(?:an?\s+)?(?:mwc|manual|you|users?|ezra|the\s+(?:user|maintainer|owner)|"
    r"(?:a\s+)?(?:human|person|maintainer))\b"
    r"|\bmanual\s+(?:step|action|click)\b",
    re.I,
)
# A clause that says the dependency is gone is a report, not a park.
RESOLVED_RX = re.compile(
    r"\bno\s+longer\s+(?:waits?|waiting|blocked|depends?|held)\b"
    r"|\bunblocked\b|\bnot\s+(?:blocked|waiting)\b|\bdepends\s+on\s+nothing\b",
    re.I,
)
# Sentences end at terminal punctuation, a blank line, a list item, or a
# table row; a wrapped line inside one sentence stays joined.
SENTENCE_SPLIT_RX = re.compile(
    r"(?<=[.!?])\s+|\n\s*\n|\n(?=\s*(?:[-*+]|\d+[.)])\s)|\n(?=\s*\|)|(?<=\|)\s*\n"
)
# Clauses split a sentence for the gates, so a gate in one clause cannot
# exempt a park in another. A single newline also ends a clause, so status
# lines joined into one sentence stay apart.
CLAUSE_SPLIT_RX = re.compile(r"[;,]\s+|:\s+|\n|\s[\u2014\u2013]\s|\s--\s")
_TRAILING_CLAUSE_RX = re.compile(r"^\s*(?:which|that|since|because|as)\b", re.I)
REPLY_TOOL_RX = re.compile(
    r"(^|__)(reply|post_message|update_message|edit_message|send_message)$", re.I
)


def _blocks(m):
    msg = m.get("message")
    if not isinstance(msg, dict):
        msg = {}
    return msg.get("content") or m.get("content") or []


def _is_user_turn(m):
    """True for a line a person wrote: not a tool result, a meta line or a reminder."""
    if not (m.get("type") == "user" or m.get("role") == "user") or m.get("isMeta"):
        return False
    blocks = _blocks(m)
    if isinstance(blocks, str):
        texts = [blocks]
    else:
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in blocks):
            return False
        texts = [b.get("text") or "" for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
    return any(t.strip() and not t.lstrip().startswith("<") for t in texts)


def turn_outputs(path):
    """Every user-visible output of the current turn at `path`, in order.

    The turn starts at the last line a person wrote, so an earlier turn's
    reply can neither block nor hide this one. Every output counts, so a
    reply-tool park followed by a closing line is still checked.
    """
    outs = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                try:
                    m = json.loads(line)
                except Exception:
                    continue
                if not isinstance(m, dict):
                    continue
                if _is_user_turn(m):
                    outs = []
                    continue
                if not (m.get("type") == "assistant" or m.get("role") == "assistant"):
                    continue
                blocks = _blocks(m)
                if isinstance(blocks, str):
                    if blocks.strip():
                        outs.append(blocks)
                    continue
                for b in blocks:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "text" and (b.get("text") or "").strip():
                        outs.append(b["text"])
                    if b.get("type") == "tool_use" and REPLY_TOOL_RX.search(b.get("name") or ""):
                        inp = b.get("input") or {}
                        txt = inp.get("text") or inp.get("message")
                        if isinstance(txt, str) and txt.strip():
                            outs.append(txt)
    except Exception:
        return []
    return outs


def _object_is_ref(rest):
    """True when the phrase's object, within six tokens on its line, is an item."""
    line = rest.split("\n", 1)[0]
    line = re.split(r"[.!?;,](?:\s|$)", line, maxsplit=1)[0]
    for i, tok in enumerate(line.split()[:6]):
        if REF_RX.fullmatch(tok.strip(_TOKEN_STRIP)) or REF_RX.match(tok.lstrip(_TOKEN_STRIP)):
            return True
        if _NOT_ITEM.match(tok.strip(_TOKEN_STRIP)):
            return False
        if REF_RX.search(tok):
            return True
    return False


def _gate_region(sentence, pos):
    """The clause holding `pos`, plus trailing which-clauses and asides."""
    bounds = [0] + [m.end() for m in CLAUSE_SPLIT_RX.finditer(sentence)] + [len(sentence) + 1]
    for k in range(len(bounds) - 1):
        if bounds[k] <= pos < bounds[k + 1]:
            region = sentence[bounds[k]:bounds[k + 1]]
            j = k + 1
            while j < len(bounds) - 1 and _TRAILING_CLAUSE_RX.match(sentence[bounds[j]:bounds[j + 1]]):
                region += " " + sentence[bounds[j]:bounds[j + 1]]
                j += 1
            return region
    return sentence


def _park_positions(sentence):
    for m in PHRASE_RX.finditer(sentence):
        if _object_is_ref(sentence[m.end():]):
            yield m.start()
    for rx in FORM_RX:
        for m in rx.finditer(sentence):
            yield m.start()


def find_park(text):
    """The first sentence parking work on a tracked item, or None."""
    prose = strip_code(_REF_SPAN_RX.sub(r" \2 ", text)).replace("](", "] (")
    for sentence in SENTENCE_SPLIT_RX.split(prose):
        for pos in _park_positions(sentence):
            region = _gate_region(sentence, pos)
            if PERSON_GATE_RX.search(region) or RESOLVED_RX.search(region):
                continue
            return sentence.strip()
    return None


def last_reply_text(path):
    """All of the current turn's outputs, joined (kept for callers)."""
    return "\n\n".join(turn_outputs(path))


MESSAGE = (
    "This reply parks work as waiting on another tracked item: \"{hit}\".\n\n"
    "Standing rule (Ezra, 2026-11-07: \"never do that again\"): a dependency on "
    "another issue or PR is work you can do, not a reason to stop. Claim the "
    "blocking item, implement it or drive its PR to clean, then come back to "
    "the dependent work, in this turn.\n\n"
    "Stop only for a step that needs a person (an approval, a secret, a manual "
    "action on a device), and name that step in the reply."
)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    text = last_reply_text(payload.get("transcript_path") or "")
    if not text:
        return 0
    hit = find_park(text)
    if not hit:
        return 0
    print(stop_notice(payload, MESSAGE.format(hit=hit[:200]), HOOK))
    return 0


if __name__ == "__main__":
    sys.exit(main())
