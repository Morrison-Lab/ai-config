#!/usr/bin/env python3
"""Stop-hook guard: catch a reply announcing a future merge nobody has confirmed.

A coordinator post that says "each thread merges as soon as it is clean" reads
as a status report, but it is a promise about an action that has not happened
and, under the strict merge policy, may not be allowed to. The reader acts on
it: they stop watching the PR. Observed 2026-10-16 in a project thread: the
announcement went out, no merge ever ran, and the PRs sat open.

Modelled on no-offer-to-file.py and reusing its transcript reader, so a
project-thread reply (`reply` / `post_message` / `update_message` tool call) is
read the same way. It fires only when ALL hold:
  1. the reply announces a future merge ("merges as soon as", "I'll merge",
     "will merge", "each thread merges automatically") in prose, outside code
     spans;
  2. the same sentence does not make the merge conditional on the user's own
     say-so, and the merger is not the user; and
  3. since the last user turn, no result of a MERGE call (the merge tool, or a
     `gh pr merge` / `glab mr merge` / `.../merge` command) reports a merge.
     Results of other calls never count: reading a merged PR's state or a
     file that quotes "successfully merged" is not a merge.

Fires once per distinct message (sentinel keyed by content hash) so a block
cannot loop. Fails OPEN: a guard that wedges the session costs more than the
lapse it prevents, including when the sibling module it reuses cannot load.
"""
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile

try:
    _spec = importlib.util.spec_from_file_location(
        "no_offer_to_file",
        os.path.join(os.path.dirname(os.path.realpath(__file__)), "no-offer-to-file.py"),
    )
    _offer = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_offer)
    last_assistant_text = _offer.last_assistant_text
    sentence_around = _offer.sentence_around
    strip_code = _offer.strip_code
except Exception:
    sys.exit(0)

ANNOUNCE_RX = re.compile(
    # first person, any future frame
    r"\b(i|we)('ll| will| am going to| plan to| intend to)\b[^.!?\n]{0,20}?\bmerg(e|ing)\b"
    r"|\b(i|we)'ll be merging\b"
    # a subject followed by a merge verb and an auto/timing frame
    r"|\b(it|they|each|every|all|both|threads?|prs?|pr \S+|#\d+)\b[^.!?\n]{0,40}?"
    r"\bmerges?\b[^.!?\n]{0,10}?\b(as soon as|once|when|after|on green|automatically|shortly)\b"
    r"|\bmerges? (automatically|on green)\b"
    # passive or modal future
    r"|\bwill (be |auto-?|then )?merged?\b"
    r"|\b(is|are|am|i'm|we're) (going|set|about) to (be )?merged?\b"
    r"|\b(i'm|we're) going to merge\b"
    r"|\bgets? merged\b"
    r"|\bplans? to merge\b"
    r"|\b(to be merged|queued for merge)\b[^.!?\n]{0,10}?\b(as soon as|once|when|after)\b",
    re.I,
)

# The merge waits on the user's own words (a condition on CI or on conflicts
# is not one), or the user is the one who merges.
USER_SUBJECT = r"(you|ezra|the user|d-morrison)"
CONDITIONAL_RX = re.compile(
    r"\b(only|unless|until|if|after|once|when)\b[^.!?\n]{0,25}?\b" + USER_SUBJECT + r"\b"
    r"[^.!?\n]{0,30}?\b(say|says|said|confirm|confirms|approve|approves|tell|tells"
    r"|give|gives|grant|grants|ask|asks|authori[sz]e|okay|ok)\b"
    r"|\bexplicit(ly)? (merge|go|word|approval|permission|grant)"
    r"|\b" + USER_SUBJECT + r"\b[^.!?\n]{0,10}?\bwill (merge|do the merge)"
    # first-person refusal or deferral: the stance the block asks for
    r"|\b(will not|won't|never|cannot|can't|nothing)\b[^.!?\n]{0,30}?\bmerg"
    r"|\bmerg[^.!?\n]{0,20}?\b(without|nothing)\b"
    r"|\b(wait for|ask|before)\b[^.!?\n]{0,15}?\b" + USER_SUBJECT + r"\b|\bbefore i merge\b",
    re.I,
)

# What a merge call reads as when it ran.
CONFIRMED_RX = re.compile(
    r"successfully merged|merged pull request|squashed and merged"
    r"|\"merged\"\s*:\s*true",
    re.I,
)
MERGE_CALL_RX = re.compile(
    r"(^|__)merge_pull_request$|\b(gh pr|glab mr) merge\b|/pulls/\S+/merge\b|/merge_requests/\S+/merge\b",
    re.I,
)


# Harness-injected text in a user-role message is not something the user said.
SYSTEM_TEXT_RX = re.compile(r"<system-reminder|\[SYSTEM NOTIFICATION", re.I)


def find_announcement(prose):
    """The first unconditional future-merge announcement in `prose`, or None."""
    for m in ANNOUNCE_RX.finditer(prose):
        if not CONDITIONAL_RX.search(sentence_around(prose, m.start(), m.end())):
            return m
    return None


def _blocks(m):
    blocks = (m.get("message") or {}).get("content") or m.get("content")
    return blocks if isinstance(blocks, list) else []


def _is_merge_call(block):
    inp = block.get("input")
    inp = inp if isinstance(inp, dict) else {}
    return any(
        MERGE_CALL_RX.search(str(part or ""))
        for part in (block.get("name"), inp.get("command"))
    )


def _result_text(block):
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    return ""


def _is_user_turn(m):
    """A genuine user message: user role with at least one non-tool-result block."""
    if m.get("type") != "user" and m.get("role") != "user":
        return False
    content = (m.get("message") or {}).get("content") or m.get("content")
    if isinstance(content, str):
        return bool(content.strip())
    return any(
        isinstance(b, dict)
        and b.get("type") != "tool_result"
        and not SYSTEM_TEXT_RX.match(str(b.get("text") or "").lstrip())
        for b in _blocks(m)
    )


def merge_confirmed(path):
    """True when, since the last user turn, a non-error MERGE call reported a merge."""
    merge_ids = set()
    confirmed = False
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                try:
                    m = json.loads(line)
                except Exception:
                    continue
                if _is_user_turn(m):
                    merge_ids, confirmed = set(), False
                for b in _blocks(m):
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "tool_use" and _is_merge_call(b):
                        merge_ids.add(b.get("id"))
                    elif (
                        b.get("type") == "tool_result"
                        and b.get("tool_use_id") in merge_ids
                        and not b.get("is_error")
                        and CONFIRMED_RX.search(_result_text(b))
                    ):
                        confirmed = True
    except Exception:
        return False
    return confirmed


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    path = payload.get("transcript_path") or ""
    text = last_assistant_text(path)
    if not text:
        return 0

    hit = find_announcement(strip_code(text))
    if not hit or merge_confirmed(path):
        return 0

    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-merge-announce-guard-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w", encoding="utf-8").close()
    except Exception:
        pass

    print(json.dumps({
        "decision": "block",
        "reason": (
            "Your message announces a future merge that no merge call since "
            f"the last user turn confirms: \"{hit.group(0).strip()}\".\n\n"
            "A reader takes \"merges as soon as it is clean\" as a plan that is "
            "running, and stops watching. Either the merge is authorized and "
            "you do it now and report it in the past tense, or it waits on the "
            "user's explicit merge words and the message should say exactly "
            "that. Rewrite the sentence to state the current state of each PR "
            "(open, clean, waiting on the user's merge words) instead of "
            "predicting a merge."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
