#!/usr/bin/env python3
"""PreToolUse deny: a brief widens the user's ask into a sweep they never asked for.

Ezra, 2026-11-20 23:56 PST: he said "do that" to "move the ids equation-label
check into gha", and the coordinator's brief to the new thread also told it to
label every unlabeled equation in all the notes repos and roll the check out
everywhere. His reply: "did I say to sweep?". The PR-side guards
(no-unrequested-sweep-pr.py, warn-sweep-pr-without-ask.py) fire only once PRs
are being opened, after the widened brief has already handed a thread the work;
this guard fires on the brief itself.

DENIES an Agent/Task launch, SendMessage, thread start or thread message whose
text holds, in a clause that is not negated, not a question and not an offer
("offer", "follow-up", "ask the user", "file an issue"):
  - the word "sweep";
  - "all|every|each ... repo(s)/repositories", "everywhere" or "existing
    content|pages|chapters|notes" in a sentence with a content-edit verb
    (label, fix, convert, update, rewrite, apply, backfill, migrate, rename,
    replace, roll out, bring, edit, change).
unless the user's own words since their latest message carry the same breadth
(a sweep ask, or an all-repos/everywhere clause), read with user_bodies() from
remind-plain-english-merge-word.py, so a coordinator <note> never counts, or a
verified decision-card tap mentions a sweep or all repos. No agent-side bypass:
reword the brief to the asked step and put the rest in it as an offer.
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
    r"|mcp__claude-code-remote__send_message|mcp__claude-code-remote__create_session"
    r"|mcp__Claude_Code_Remote__create_session)$")
BROAD = re.compile(r"\bsweep(?:s|ing)?\b", re.I)
ALL_REPOS = re.compile(
    r"\b(?:all|every|each)\b[\w ]{0,30}?\b(?:repos?|repositories)\b|\beverywhere\b"
    r"|\b(?:all\s)?existing\s(?:content|pages|chapters|notes)\b", re.I)
EDIT_VERB = re.compile(
    r"\b(?:label|relabel|fix|convert|update|rewrite|apply|backfill|migrate|rename|replace"
    r"|roll|bring|edit|change)\w*\b", re.I)
NEGATED = re.compile(r"\b(?:don'?t|do\s+not|never|no|not|stop|without|isn'?t|must\s+not)\b", re.I)
OFFER = re.compile(
    r"\b(?:offer|follow[- ]?up|suggest|propose|ask\s+(?:the\s+user|ezra|him|them)|file\s+an?\s+issue)\w*",
    re.I)
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


def clauses(text):
    for sentence in SENTENCE.findall(text):
        if sentence.rstrip().endswith("?"):
            continue
        yield from CLAUSE.split(sentence)


def live(clause, match):
    return bool(match) and not NEGATED.search(clause[:match.start()])


def widening(text):
    """The first widening phrase in a brief, or None."""
    for sentence in SENTENCE.findall(text):
        if sentence.rstrip().endswith("?") or OFFER.search(sentence):
            continue
        for clause in CLAUSE.split(sentence):
            hit = BROAD.search(clause)
            if live(clause, hit):
                return hit.group(0)
        repos = ALL_REPOS.search(sentence)
        if live(sentence, repos) and EDIT_VERB.search(sentence):
            return repos.group(0)
    return None


def user_grants(text, typed):
    for clause in clauses(typed(text)):
        if live(clause, BROAD.search(clause)) or live(clause, ALL_REPOS.search(clause)):
            return True
    return False


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
    """Whether the user's words since their latest message carry a sweep's breadth."""
    cards_pending, cards, grant, seen = {}, {}, False, set()
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
            grant = any(user_grants(b, typed) for b in bodies) or any(CARD_BROAD.search(t) for t in taps)
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
    user_bodies, typed = load_helpers()
    if granted(path, user_bodies, typed):
        return None
    return REASON.format(hit=hit)


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
