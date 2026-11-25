#!/usr/bin/env python3
"""PreToolUse deny: a brief widens the user's ask into a sweep they never asked for.

Ezra, 2026-11-20 23:56 PST: he said "do that" to "move the ids equation-label
check into gha", and the coordinator's brief to the new thread also told it to
label every unlabeled equation in all the notes repos and roll the check out
everywhere. His reply: "did I say to sweep?". The PR-side guards
(no-unrequested-sweep-pr.py, warn-sweep-pr-without-ask.py) fire only once PRs
are being opened, after the widened brief has already handed a thread the work;
this guard fires on the brief itself.

DENIES a brief (an Agent/Task launch, SendMessage, thread start, thread or
coordinator message, remote-control instructions, a scheduled send) holding a
widening in a clause (split at , ; :) that is not a question, holds no offer
("offer", "follow-up", "ask the user", "file an issue") and has no negation
before the phrase:
  - "sweep" (kind "sweep");
  - "all|every|each ... repo(s)", "everywhere" or "existing content|pages|
    chapters|notes|equations|figures" in a clause with a content-edit verb
    and no PR, CI, merge, hook or branch word (kind "scope");
  - three or more notes repos named in one sentence with an edit verb and no
    offer, negation or infra word (kind "scope").
unless the user's own words since their latest message ask for that kind: a
"sweep" clause or a typed gia/gii/gip/gmd/ardia grants both kinds, an
all-repos/everywhere clause or three named repos grants "scope". Read with
user_bodies() from remind-plain-english-merge-word.py, so a coordinator <note>
never counts; a verified decision-card tap mentioning a sweep or all repos
grants both. No agent-side bypass: brief the asked step and offer the rest.
Fails open on a missing transcript, a missing helper or parse trouble.
"""
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "scripts", "lib"))
import card_answer  # noqa: E402

BRIEF_TOOLS = re.compile(
    r"^(?:Agent|Task|SendMessage|mcp__hearthbot__start_thread|mcp__hearthbot__message_thread"
    r"|mcp__hearthbot__message_coordinator|mcp__hearthbot__start_remote_control"
    r"|mcp__claude-code-remote__send_message|mcp__claude-code-remote__send_later"
    r"|mcp__claude-code-remote__create_session|mcp__Claude_Code_Remote__create_session)$")
BROAD = re.compile(r"\bsweep(?:s|ing)?\b", re.I)
SCOPE = re.compile(
    r"\b(?:all|every|each)\b[^.;:?!\n]{0,80}?\b(?:repos?|repositories)\b|\beverywhere\b"
    r"|\bexisting\s(?:content|pages|chapters|notes|equations|figures)\b", re.I)
NOTES_REPO = re.compile(r"\b(?:lds|mds|pds|sds|rme|mcs|psw|psc|win|cie|ids|cds|wai)\b", re.I)
EDIT_VERB = re.compile(
    r"\b(?:label|relabel|fix|convert|update|rewrite|apply|backfill|migrate|rename|replace"
    r"|roll|bring|edit|change|add|enable|install|wire|clean|sweep)\w*\b", re.I)
# A clause about PRs, CI or hooks is driving infrastructure, not editing content.
INFRA = re.compile(r"\bPRs?\b|\bCI\b|\bpull\s+requests?\b|\bmerg\w*|\bhooks?\b|\bbranch(?:es)?\b", re.I)
NEGATED = re.compile(r"\b(?:don'?t|do\s+not|never|no|not|stop|without|isn'?t|must\s+not)\b", re.I)
OFFER = re.compile(
    r"\b(?:offer|follow[- ]?up|suggest|propose|ask\s+(?:the\s+user|ezra|him|them)|file\s+an?\s+issue)\w*",
    re.I)
# A typed backlog-run skill asks for many PRs across repos by design (as in no-unrequested-sweep-pr.py).
BACKLOG_SKILL = re.compile(r"(?:^|\s)/?(?:gia|gii|gip|gmd|giardia|ardia|ardiaei)\b", re.I)
SENTENCE = re.compile(r"[^.!?\n]+[.!?]*")
CLAUSE = re.compile(r"[,;:]")
CARD_BROAD = re.compile(r"\bsweep|\ball\s+(?:the\s+)?(?:notes\s+)?repos|\beverywhere\b", re.I)

REASON = (
    "[hook: no-unrequested-sweep-in-brief] This brief widens the user's ask: it says \"{hit}\", "
    "and nothing the user wrote since their latest message asks for a sweep or that breadth. "
    "Ezra, 2026-11-20: \"did I say to sweep?\", after a brief turned \"do that\" (move one check "
    "into gha) into labeling every equation in all the notes repos. Brief only the step the user "
    "asked for, and put the wider work in the brief as something to offer the user as a follow-up. "
    "Rewording the same sweep to dodge this check is the same failure. See "
    "shared/workflow/no-sweeps-by-default.md."
)


def load_helpers():
    path = Path(__file__).resolve().parent / "remind-plain-english-merge-word.py"
    spec = importlib.util.spec_from_file_location("_nusib_merge_word", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.user_bodies, module.typed


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings(v)


def live(clause, match):
    return bool(match) and not NEGATED.search(clause[:match.start()])


def named_repos(sentence):
    """Three or more notes repos named in one sentence, or None."""
    names = {m.group(0).lower() for m in NOTES_REPO.finditer(sentence)}
    return ", ".join(sorted(names)) if len(names) >= 3 else None


def widening(text):
    """(kind, phrase) for the first widening in a brief, or None; kind is "sweep" or "scope"."""
    for sentence in SENTENCE.findall(text):
        if sentence.rstrip().endswith("?"):
            continue
        for clause in CLAUSE.split(sentence):
            if OFFER.search(clause):
                continue
            hit = BROAD.search(clause)
            if live(clause, hit):
                return "sweep", hit.group(0)
            hit = SCOPE.search(clause)
            if live(clause, hit) and EDIT_VERB.search(clause) and not INFRA.search(clause):
                return "scope", hit.group(0)
        names = named_repos(sentence)
        if names and EDIT_VERB.search(sentence) and not (
                OFFER.search(sentence) or NEGATED.search(sentence) or INFRA.search(sentence)):
            return "scope", names
    return None


def user_grants(text, typed):
    """The kinds of breadth the user's words ask for: a subset of {"sweep", "scope"}."""
    text = typed(text)
    if BACKLOG_SKILL.search(text):
        return {"sweep", "scope"}
    kinds = set()
    for sentence in SENTENCE.findall(text):
        if sentence.rstrip().endswith("?"):
            continue
        if named_repos(sentence) and not NEGATED.search(sentence):
            kinds.add("scope")
        for clause in CLAUSE.split(sentence):
            if live(clause, BROAD.search(clause)):
                kinds.update({"sweep", "scope"})
            elif live(clause, SCOPE.search(clause)):
                kinds.add("scope")
    return kinds


def prompt_text(content):
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return None
    if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
        return None
    return "\n".join(b.get("text", "") for b in content
                     if isinstance(b, dict) and b.get("type") == "text")


def granted(transcript_path, user_bodies, typed):
    """The kinds of breadth the user's words since their latest message ask for."""
    cards_pending, cards, grant, seen = {}, {}, set(), set()
    with open(transcript_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict) or rec.get("isSidechain"):
                continue
            card_answer.track_cards(rec, cards_pending, cards)
            if rec.get("type") != "user" or rec.get("isMeta") or rec.get("isCompactSummary"):
                continue
            msg = rec.get("message")
            text = prompt_text(msg.get("content") if isinstance(msg, dict) else None)
            if not text:
                continue
            taps = card_answer.answers_in_record(rec, cards)
            relayed = "<coordinator-relay" in text
            bodies = [b for b in user_bodies(text) if b.strip() and not (relayed and b.strip() in seen)]
            if not bodies and not taps:
                continue
            seen.update(b.strip() for b in bodies)
            grant = set().union(*(user_grants(b, typed) for b in bodies))
            if any(CARD_BROAD.search(t) for t in taps):
                grant |= {"sweep", "scope"}
    return grant


def decide(payload):
    if not BRIEF_TOOLS.match(payload.get("tool_name") or ""):
        return None
    hit = widening("\n".join(strings(payload.get("tool_input"))))
    if not hit:
        return None
    path = payload.get("transcript_path") or payload.get("transcriptPath")
    if not isinstance(path, str) or not os.path.isfile(path):
        return None
    kind, phrase = hit
    user_bodies, typed = load_helpers()
    if kind in granted(path, user_bodies, typed):
        return None
    return REASON.format(hit=phrase)


def main():
    try:
        payload = json.load(sys.stdin)
        reason = decide(payload) if isinstance(payload, dict) else None
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
