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
The last user-visible output of the current turn (a reply-tool payload
such as hearthbot post_message or claude-code-remote send_message, or
assistant text, whichever came last since the person last wrote), with
code spans and fences stripped, has a sentence whose parking phrase
("waits on", "waiting for", "blocked on/by", "depends/depending on",
"on hold until", "held until", "held up by") takes a tracked item as its
object, or that says "until <item> merges/lands/is ready".
A tracked item is an issue/PR URL, owner/repo#N, repo#N, or #N, but not a
file anchor such as README.md#2.

The object rule keeps reports out: "PR #12 is waiting on the runner" and
"I merged gha#1545, which mds#649 was waiting on" name the item, but not as
what is waited on. A sentence naming a person-only gate ("needs you",
"your approval") passes; a bare "mwc" or "approval" elsewhere does not.

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
# anchor such as README.md#2 is not an item.
_REF = (
    r"(?:https?://[^\s/]+/[^\s]*?/(?:issues|pull|pulls|merge_requests)/\d+"
    r"|[\w.-]+/[\w-]+(?:\.[\w-]+)*(?<!\.md)(?<!\.qmd)(?<!\.html)(?<!\.rst)(?<!\.txt)#\d+\b"
    r"|\b[A-Za-z][\w-]*#\d+\b"
    r"|(?<![\w/#&.])#\d+\b)"
)
REF_RX = re.compile(_REF, re.I)

# Words that may sit between a parking phrase and the item it names, as in
# "waits on the PR for gha#1544" or "blocked by [#12](...)".
_FILLER = (
    r"(?:(?:the|a|an|its|their|that|this|PR|pull\s+request|MR|issue|fix|change|"
    r"work|merge\s+of|landing\s+of|upstream|in|from|both|and|or|being)\s+|[\[(*_\"'])*"
)
_PHRASE = (
    r"\b(?:wait(?:s|ing)?\s+(?:on|for)"
    r"|blocked\s+(?:on|by)"
    r"|held\s+(?:up\s+)?(?:on|by|until)"
    r"|on\s+hold\s+(?:for|until|pending)"
    r"|(?:held|parked)\s+pending"
    r"|depend(?:s|ing|ent)?\s+on)\s+"
)
# The park counts only when the phrase's OBJECT is the tracked item, so
# "PR #12 is waiting on the macOS runner" and "I merged gha#1545, which
# mds#649 was waiting on" are reports, not parks.
PARK_RX = re.compile(
    _PHRASE + _FILLER + _REF
    + r"|\buntil\s+(?:[^.!?\n]|\.(?!\s)){0,100}?" + _REF
    + r"(?:[^.!?\n]|\.(?!\s)){0,40}?\b(?:merges|lands|is\s+merged|ships|closes|is\s+ready)\b",
    re.I,
)
# A sentence whose park is on a person-only step passes.
PERSON_GATE_RX = re.compile(
    r"\bneeds?\s+(?:you|your|ezra|the\s+user|a\s+(?:human|person|maintainer|reviewer))\b"
    r"|\b(?:your|ezra['\u2019]s|the\s+user['\u2019]s|a\s+maintainer['\u2019]s)\s+"
    r"(?:approval|go-?ahead|answer|decision|review|click|sign-?in|merge)\b",
    re.I,
)
# A sentence that says the dependency is gone is a report, not a park.
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
REPLY_TOOL_RX = re.compile(
    r"(^|__)(reply|post_message|update_message|edit_message|send_message)$", re.I
)


def _blocks(m):
    msg = m.get("message")
    if not isinstance(msg, dict):
        msg = {}
    return msg.get("content") or m.get("content") or []


def _is_user_turn(m):
    """True for a line a person (not a tool result) wrote."""
    if not (m.get("type") == "user" or m.get("role") == "user"):
        return False
    blocks = _blocks(m)
    if isinstance(blocks, str):
        return bool(blocks.strip())
    return any(isinstance(b, dict) and b.get("type") == "text" for b in blocks)


def last_reply_text(path):
    """The last user-visible output of the current turn at `path`, or ''.

    The turn starts at the last line a person wrote, so an earlier turn's
    reply can neither block nor hide this one. Within the turn the latest
    output wins, whether a reply-tool payload or plain text.
    """
    last = ""
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
                    last = ""
                    continue
                if not (m.get("type") == "assistant" or m.get("role") == "assistant"):
                    continue
                blocks = _blocks(m)
                if isinstance(blocks, str):
                    if blocks.strip():
                        last = blocks
                    continue
                for b in blocks:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "text" and (b.get("text") or "").strip():
                        last = b["text"]
                    if b.get("type") == "tool_use" and REPLY_TOOL_RX.search(b.get("name") or ""):
                        inp = b.get("input") or {}
                        txt = inp.get("text") or inp.get("message")
                        if isinstance(txt, str) and txt.strip():
                            last = txt
    except Exception:
        return ""
    return last


def find_park(text):
    """The first sentence parking work on a tracked item, or None."""
    prose = strip_code(text)
    for sentence in SENTENCE_SPLIT_RX.split(prose):
        if not PARK_RX.search(sentence):
            continue
        if not REF_RX.search(sentence):
            continue
        if PERSON_GATE_RX.search(sentence):
            continue
        if RESOLVED_RX.search(sentence):
            continue
        return sentence.strip()
    return None


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
