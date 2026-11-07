#!/usr/bin/env python3
"""Stop-hook guard: a reply that parks work as "waiting on" another tracked item.

THE MEASURED CASE (2026-11-06, Morrison-Lab project thread)
-----------------------------------------------------------
A thread finishing the mds/mcs consolidation ended its turn with
"mds#649 waits on gha#1544" and stopped. gha#1544 was an open issue with a
clean, unmerged PR (gha#1545) that the thread was free to drive, and the
gha repo carries a standing merge grant. Nothing about the dependency
needed the user. Six hours later the user wrote "why did you stop? don't
stop", and then "never do that again".

A dependency on another issue or PR is work, not a wall: the agent can
claim the blocking item, implement it, drive its PR, and come back. Only a
step that genuinely needs a person (an approval, a secret, a manual click
on a device) is a reason to stop.

WHAT IT CHECKS
--------------
The final user-visible reply (a hearthbot or other reply-tool payload,
else the last assistant text), with code spans and fences stripped, has a
sentence that BOTH

    * uses a parking phrase ("waits on", "waiting for", "blocked on",
      "blocked by", "depends on", "on hold until", "held up by",
      "until ... merges/lands"), AND
    * names a tracked item (an issue/PR URL, owner/repo#N, or #N).

A sentence that names a person-only gate in the same breath ("needs you",
"your approval", "needs Ezra", "a human", "manual") passes, since that is
the one legitimate reason to wait.

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
    _SPAN_RE = re.compile(r"`[^`\n]*`")

    def strip_code(text):  # noqa: D103
        return _SPAN_RE.sub(" ", _FENCE_RE.sub(" ", text))

HOOK = "no-park-on-tracked-blocker"

PARK_RX = re.compile(
    r"\b(?:"
    r"wait(?:s|ing)?\s+(?:on|for)"
    r"|blocked\s+(?:on|by)"
    r"|held\s+(?:up\s+)?(?:on|by)"
    r"|on\s+hold\s+(?:for|until|pending)"
    r"|(?:held|parked)\s+pending"
    r"|depends\s+on"
    r"|until\s+[^.!?\n]{0,60}?\b(?:merges|lands|is\s+merged|ships|closes)"
    r")\b",
    re.I,
)
REF_RX = re.compile(
    r"https?://[^\s/]+/[^\s]*?/(?:issues|pull|pulls|merge_requests)/\d+"
    r"|\b[\w.-]+/[\w.-]+#\d+\b"
    r"|\b[A-Za-z][\w.-]*#\d+\b"
    r"|(?<![\w/#&])#\d+\b",
    re.I,
)
PERSON_GATE_RX = re.compile(
    r"\bneeds?\s+(?:you|your|ezra|the\s+user|a\s+(?:human|person|maintainer|reviewer))\b"
    r"|\b(?:your|ezra['\u2019]s|the\s+user['\u2019]s|a\s+maintainer['\u2019]s)\s+"
    r"(?:approval|go-?ahead|answer|decision|review|click|sign-?in|merge)\b"
    r"|\b(?:wait(?:s|ing)?\s+(?:on|for)|blocked\s+(?:on|by))\s+"
    r"(?:you|ezra|the\s+(?:user|maintainer|owner)|users?|a\s+(?:human|person|maintainer))\b"
    r"|\bmwc\b|\bapproval\b|\bmanual\s+(?:step|action|click)\b",
    re.I,
)
# A sentence that says the dependency is gone is a report, not a park.
RESOLVED_RX = re.compile(
    r"\bno\s+longer\b|\bunblocked\b|\bnot\s+(?:blocked|waiting)\b"
    r"|\bdepends\s+on\s+nothing\b",
    re.I,
)
SENTENCE_SPLIT_RX = re.compile(r"(?<=[.!?])\s+|\n\s*\n|\n(?=\s*(?:[-*+]|\d+[.)])\s)")
REPLY_TOOL_RX = re.compile(r"(^|__)(reply|post_message|update_message|edit_message)$", re.I)


def _blocks(m):
    msg = m.get("message")
    if not isinstance(msg, dict):
        msg = {}
    return msg.get("content") or m.get("content") or []


def last_reply_text(path):
    """The final user-visible reply in the transcript at `path`, or ''."""
    last_text, last_reply = "", ""
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                try:
                    m = json.loads(line)
                except Exception:
                    continue
                if not isinstance(m, dict):
                    continue
                if not (m.get("type") == "assistant" or m.get("role") == "assistant"):
                    continue
                blocks = _blocks(m)
                if isinstance(blocks, str):
                    if blocks.strip():
                        last_text = blocks
                    continue
                for b in blocks:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "text" and (b.get("text") or "").strip():
                        last_text = b["text"]
                    if b.get("type") == "tool_use" and REPLY_TOOL_RX.search(b.get("name") or ""):
                        txt = (b.get("input") or {}).get("text")
                        if isinstance(txt, str) and txt.strip():
                            last_reply = txt
    except Exception:
        return ""
    return last_reply or last_text


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
