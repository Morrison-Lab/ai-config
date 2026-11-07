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
what is waited on. The object also ends at a clause boundary or
conjunction, at a line wrap after anything but a function word, and at a
preposition right after a non-filler word, so "Waiting on CI for #12" names
CI. "After waiting on #12" or "spent a minute waiting for #12" is
narrative when the sentence has a first-person past verb ("I merged it");
"While waiting on #12, I'm working on #13" is still a park. A line wrap
ends a clause unless the line stops mid-phrase, so a status line such as
"#10: unblocked" cannot exempt the next line.
A form spanning several clauses is judged by the clause it ends in.
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

KNOWN LIMITS
------------
This is a lexical heuristic, so its two errors cost different amounts. A
false positive costs one extra stop, which the agent answers by naming the
person-only step or saying it is a report. A miss lets a park through, as
before the hook existed. So the matcher favours catching the common park
shapes, and these are accepted rather than chased:

- A bare x/y#N (docs/setup#2) reads as owner/repo#N, as GitHub's own
  autolinker reads it.
- Parks phrased without any of the phrases or forms above ("I'll leave
  that for later", "next step is #12") are not caught.
- A person gate is honoured only in the park's own clause, a trailing
  which/that/it/until clause, or a leading because/since clause (each
  with any parts a bare and/but joins to it).
- "I'll keep polling until #12 merges" counts as a park on purpose: it
  waits on #12 rather than driving it.
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

_APOS = "['\u2019]"
# A tracked item: an issue/PR URL, owner/repo#N, repo#N, or #N. A file
# anchor (README.md#2, docs/spec.json#2) is not an item. A bare x/y#N stays
# an item, as GitHub's own autolinker reads it, so docs/setup#2 is accepted
# as a known false positive. A possessive ("#12's CI") is not an item.
_REF = (
    r"(?:https?://[^\s/]+/[^\s)\]]*?/(?:issues|pull|pulls|merge_requests)/\d+\b"
    r"|(?<![\w./-])[\w-]+/[\w-]+(?:\.[\w-]+)?(?<!\.json)(?<!\.md)(?<!\.qmd)(?<!\.html)"
    r"(?<!\.rst)(?<!\.txt)(?<!\.yml)(?<!\.yaml)(?<!\.py)(?<!\.R)#\d+\b"
    r"|(?<![\w./-])[A-Za-z][\w-]*#\d+\b"
    r"|(?<![\w/#&.])#\d+\b)"
    r"(?![\])`]*" + _APOS + r"s\b)"
)
REF_RX = re.compile(_REF, re.I)
# A code span holding only an item (optionally "PR"/"issue" before it) is
# unwrapped before code is stripped, so "waits on `gha#1544`" still counts.
_REF_SPAN_RX = re.compile(
    r"(?<!`)(`{1,2})[ \t]*((?:(?:PR|MR|issue|pull\s+request)[ \t]+)?" + _REF + r")[ \t]*\1(?!`)"
    r"(?!" + _APOS + r"s\b)",
    re.I,
)
_POSSESSIVE_LINK_RX = re.compile(r"\[([^\]\n]*)\]\([^)\s]*\)(?=" + _APOS + r"s\b)")
# What may follow an item before a completion verb: closing link brackets.
_AFTER_REF = r"[\])]*\s+"

# A parking phrase whose object is read token by token (see _object_is_ref).
PHRASE_RX = re.compile(
    r"\b(?:wait(?:s|ing)?\s+(?:on|for)"
    r"|await(?:s|ing)?"
    r"|blocked\s+(?:on|by|until)"
    r"|gated\s+(?:on|by)"
    r"|held\s+(?:up\s+)?(?:on|by|until)"
    r"|parked\s+(?:on|behind|until)"
    r"|on\s+hold\s+(?:for|until|pending)"
    r"|(?:paused|deferred|gated|on\s+hold)\s+until"
    r"|(?:held|parked|is|are|remains?|stays?)\s+(?:still\s+|currently\s+)?pending(?!\s+(?:on|for|in)\b)"
    r"|depend(?:s|ing|ent)?\s+on)\s+",
    re.I,
)
_DONE = (
    r"(?:merges|lands|ships|closes|is\s+(?:merged|ready|fixed|done|closed|resolved)"
    r"|gets\s+merged)"
)
# A present- or future-tense parking verb. Past tense ("waited", "held")
# reports what happened, and "Stopping" is the status-line label.
_PARK_VERB = (
    r"\b(?:hold(?:s|ing)?|park(?:s|ing|ed)?|wait(?:s|ing)?|paus(?:e|es|ing)"
    r"|leav(?:e|es|ing)|defer(?:s|ring)?|keep(?:s|ing)?|resum(?:e|es|ing))\b"
)
_FIRST_PERSON_FUTURE = (
    r"\b(?:I" + _APOS + r"ll|I\s+will|we" + _APOS + r"ll|we\s+will|I" + _APOS + r"m\s+going\s+to)\b"
)
# Forms that name the item inside the phrase rather than after it.
FORM_RX = [
    # "holding X until gha#1 merges": a parking verb in the same clause.
    re.compile(
        _PARK_VERB + r"(?:[^.!?\n,;:]|\.(?!\s)){0,80}?\buntil\s+(?:[^.!?\n,;:]|\.(?!\s)){0,60}?"
        + _REF + r"(?:[^.!?\n]|\.(?!\s)){0,40}?\b" + _DONE + r"\b",
        re.I,
    ),
    # "I'll pick it up once gha#1 lands": first person, future tense.
    re.compile(
        _FIRST_PERSON_FUTURE + r"(?:[^.!?\n;:]|\.(?!\s)){0,80}?\b(?:after|once|when)\s+(?:\S+\s+){0,3}?[\[(]*"
        + _REF + _AFTER_REF + _DONE + r"\b",
        re.I,
    ),
    # "gha#1 needs to merge first" / "needs to be merged first".
    re.compile(
        _REF + _AFTER_REF + r"(?:needs|has|must)\s+(?:to\s+)?(?:be\s+)?"
        r"(?:merge[ds]?|land(?:ed|s)?|ship(?:ped|s)?|fixed|resolved)\s+first\b",
        re.I,
    ),
    # "gha#1544 is blocking mds#649": the blocker is the subject.
    re.compile(
        _REF + _AFTER_REF + r"(?:blocks|is\s+blocking|is\s+holding\s+up)\s+(?:\S+\s+){0,3}?[\[(`]*" + _REF,
        re.I,
    ),
]
# Words that may sit between a parking phrase and the item, as in "waits on
# the PR for gha#1544". A preposition after any other word ends the object,
# so "Waiting on codecov for #12" names codecov, not #12.
_FILLER = {
    "the", "a", "an", "its", "their", "that", "this", "pr", "prs", "pull", "request",
    "mr", "mrs", "issue", "issues", "fix", "fixes", "change", "changes", "requests",
    "work", "merge", "patch", "bump", "refactor", "update", "landing", "resolution", "open", "upstream", "in",
    "both", "or", "being", "of", "from", "for",
}
# A preposition right after a non-filler word ends the object.
_ENDING_PREP = {"for", "to", "on", "at", "of", "in", "before", "after", "with", "from"}
# A line wrap continues the object only after one of these.
_FUNCTION_WORDS = {"the", "a", "an", "on", "for", "of", "in", "to", "this", "that", "its", "their"}
# Where the object ends: a clause boundary or a conjunction.
_OBJECT_END_RX = re.compile(
    r"[.!?;,](?:\s|$)|:\s|\s[\u2014\u2013]\s|\s--\s"
    r"|\s(?:and|but|while|because|since|then|as)\s",
    re.I,
)
_TOKEN_STRIP = "[](){}*_\"'`<>,:"
# A clause that gates the park on a person-only step.
PERSON_GATE_RX = re.compile(
    r"\bneeds?\s+(?:you|your|ezra|the\s+user|a\s+(?:human|person|maintainer|reviewer))\b"
    r"|\b(?:your|ezra" + _APOS + r"s|the\s+user" + _APOS + r"s|a\s+maintainer" + _APOS + r"s)\s+"
    r"(?:approval|go-?ahead|answer|decision|review|click|sign-?in|sign-?off|merge|input|"
    r"confirmation|token|secret|credentials?)\b"
    r"|\b(?:wait(?:s|ing)?\s+(?:on|for)|blocked\s+(?:on|by)|gated\s+(?:on|by)|await(?:s|ing)?|"
    r"needs?|requires?)\s+"
    r"(?:an?\s+)?(?:mwc|manual|you|your|users?|ezra|the\s+(?:user|maintainer|owner)|"
    r"(?:a\s+)?(?:human|person|maintainer))\b"
    r"|\b(?:needs?|requires?)\s+(?:a|an|the)\s+(?:secret|token|credentials?|password|"
    r"api\s+key|key|2fa|login|sign-?in)\b"
    r"|\buntil\s+(?:you|ezra|the\s+(?:user|maintainer|owner)|a\s+(?:human|person|maintainer))\b"
    r"|\bpending\s+your\b|\bfor\s+you\s+to\b"
    r"|\bmanual\s+(?:step|action|click|merge|review|approval|sign-?off)\b",
    re.I,
)
# A clause that says the park's own dependency is gone is a report.
RESOLVED_RX = re.compile(
    r"\bno\s+longer\s+(?:waits?|waiting|blocked|blocking|depends?|held|gated|parked|"
    r"awaits?|awaiting|pending)\b"
    r"|\bunblocked\b|\bnot\s+(?:blocked|blocking|waiting|gated|parked|awaiting|pending|dependent|held)\b"
    r"|\b(?:does|do|did)(?:\s+not|n" + _APOS + r"t)\s+(?:depend|wait|await)\b"
    r"|\bno\s+longer\s+on\s+hold\b"
    r"|\bdepends\s+on\s+nothing\b",
    re.I,
)
# Sentences end at terminal punctuation, a blank line, a list item, or a
# table row; a wrapped line inside one sentence stays joined.
SENTENCE_SPLIT_RX = re.compile(
    r"(?<=[.!?])\s+|\n\s*\n|\n(?=\s*(?:[-*+]|\d+[.)])\s)|\n(?=\s*\|)|(?<=\|)\s*\n"
)
# Clauses split a sentence for the gates, so a gate in one clause cannot
# exempt a park in another. A line wrap does not end a clause.
CLAUSE_SPLIT_RX = re.compile(r"[;,]\s+(?:(?:and|but)\s+)?|:\s+|\s[\u2014\u2013]\s|\s--\s|\s(?:and|but)\s+|\s(?=(?:since|because|while)\s)", re.I)
# A trailing clause that still modifies the park, for the person gate only.
_TRAILING_CLAUSE_RX = re.compile(
    r"^\s*(?:which|that|since|because|as|it|this|pending|until)\b", re.I
)
_LEADING_CLAUSE_RX = re.compile(r"^\s*(?:because|since|as)\b", re.I)
# A narrative report: "After waiting on #12 ...", "I spent a minute waiting
# for #12". The narrative word must lead straight into the gerund, and the
# sentence must not look ahead ("While waiting on #12, I'll ..." is a park).
_NARRATIVE_RX = re.compile(
    r"(?:\b(?:after|while)\s+(?:still\s+|now\s+)?|\bspent\s+(?:\S+\s+){0,5}?)$", re.I
)
_GERUND_PHRASE_RX = re.compile(r"(?:wait|await|depend)ing\b", re.I)
# A report needs a first-person past-tense verb ("I merged it").
_PAST_RX = re.compile(
    r"\b(?:I|we)\s+(?:then\s+|also\s+|finally\s+|just\s+)?(?:\w+ed|did|was|were|went|ran|made|"
    r"wrote|spent|found|got|took|saw|kept|left|put|built|sent|set|rebuilt|reran|re-ran)\b",
    re.I,
)
# A line wrap ends a clause unless the line ends mid-phrase.
_WRAP_JOIN = {
    "wait", "waits", "waiting", "await", "awaits", "awaiting", "blocked", "held", "parked",
    "gated", "depends", "depend", "depending", "up", "by", "until", "no", "not", "longer",
    "pending", "hold",
} | {"the", "a", "an", "on", "for", "of", "in", "to", "this", "that", "its", "their"}
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
                # Antigravity transcripts: USER_INPUT starts a turn and a
                # PLANNER_RESPONSE's content is the visible reply.
                if m.get("type") == "USER_INPUT":
                    outs = []
                    continue
                if m.get("type") == "PLANNER_RESPONSE":
                    txt = m.get("content")
                    if isinstance(txt, str) and txt.strip():
                        outs.append(txt)
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
    """True when the phrase's object, within six tokens, is an item.

    The object ends at a clause boundary or conjunction, at a line break
    after anything but a function word, and at a preposition right after a
    non-filler word.
    """
    rest = _OBJECT_END_RX.split(rest, maxsplit=1)[0]
    prev = None
    prev_content = False
    wrapped = False
    count = 0
    for raw in re.split(r"[ \t]+", rest):
        for j, tok in enumerate(raw.split("\n")):
            if j:
                wrapped = True
            if not tok:
                continue
            if wrapped and prev is not None and prev not in _FUNCTION_WORDS:
                return False
            wrapped = False
            if REF_RX.search(tok):
                return True
            low = tok.strip(_TOKEN_STRIP).lower()
            if prev_content and low in _ENDING_PREP:
                return False
            prev_content = low not in _FILLER
            prev = low
            count += 1
            if count >= 6:
                return False
    return False


def _clauses(sentence):
    """The sentence's clauses, with whether each follows a bare and/but split."""
    marks = [(m.start(), m.end(), m.group().strip().lower() in ("and", "but"))
             for m in CLAUSE_SPLIT_RX.finditer(sentence)]
    # A status line ("#10: unblocked") ends at its line wrap.
    for m in re.finditer(r"(\S+)[ \t]*\n\s*", sentence):
        if m.group(1).strip(_TOKEN_STRIP).lower() in _WRAP_JOIN:
            continue
        if not any(s <= m.end(1) < e or s < m.end() <= e for s, e, _c in marks):
            marks.append((m.end(1), m.end(), False))
    marks.sort()
    bounds = [0] + [e for _s, e, _c in marks] + [len(sentence) + 1]
    conj = [False] + [c for _s, _e, c in marks]
    return [(bounds[k], sentence[bounds[k]:bounds[k + 1]], conj[k]) for k in range(len(bounds) - 1)]


def _gate_region(sentence, pos):
    """The clause holding `pos`, its start, and the clauses a person gate may sit in.

    A trailing which/that/it clause, or a leading because/since clause,
    keeps any parts it is joined to by a bare and/but ("which touches prod
    and needs your approval").
    """
    cl = _clauses(sentence)
    for k, (start, own, _conj) in enumerate(cl):
        end = cl[k + 1][0] if k + 1 < len(cl) else len(sentence) + 1
        if not start <= pos < end:
            continue
        gate = own
        j = k + 1
        while j < len(cl) and _TRAILING_CLAUSE_RX.match(cl[j][1]):
            gate += " " + cl[j][1]
            j += 1
            while j < len(cl) and cl[j][2]:
                gate += " " + cl[j][1]
                j += 1
        j = k - 1
        while j >= 0:
            unit = cl[j][1]
            i = j
            while i > 0 and cl[i][2]:
                i -= 1
                unit = cl[i][1] + unit
            if not _LEADING_CLAUSE_RX.match(unit):
                break
            gate = unit + " " + gate
            j = i - 1
        return own, start, gate
    return sentence, 0, sentence


def _park_positions(sentence):
    """(position, narrative-check) for each park. A form is placed at its
    end, so an earlier clause it spans cannot exempt it."""
    for m in PHRASE_RX.finditer(sentence):
        if _object_is_ref(sentence[m.end():]):
            yield m.start(), True
    for rx in FORM_RX:
        for m in rx.finditer(sentence):
            yield m.end() - 1, False


def _reports_past(sentence, start, pos):
    """True when the narrative wait's own clause, or the clause right after
    it, has a first-person past verb ("After waiting on #12, I merged it").
    A past verb about other work elsewhere in the sentence does not count."""
    if _PAST_RX.search(sentence[start:pos]):
        return True
    m = re.search(r"[,;]\s+", sentence[pos:])
    if not m:
        return False
    nxt = re.split(r"[,;]\s|\s(?:and|but)\s", sentence[pos + m.end():], maxsplit=1)[0]
    return bool(_PAST_RX.search(nxt) or re.match(r"then\s+\w+ed\b", nxt, re.I))


def find_park(text):
    """The first sentence parking work on a tracked item, or None."""
    prose = strip_code(_REF_SPAN_RX.sub(r" \2", text))
    # A possessive on a link ("[#12](url)'s CI") belongs to its text.
    prose = _POSSESSIVE_LINK_RX.sub(r"\1", prose).replace("](", "] (")
    for sentence in SENTENCE_SPLIT_RX.split(prose):
        for pos, narrative in _park_positions(sentence):
            own, start, gate = _gate_region(sentence, pos)
            if PERSON_GATE_RX.search(gate) or RESOLVED_RX.search(own):
                continue
            if (
                narrative
                and _GERUND_PHRASE_RX.match(sentence, pos)
                and _NARRATIVE_RX.search(sentence[start:pos])
                and _reports_past(sentence, start, pos)
            ):
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
