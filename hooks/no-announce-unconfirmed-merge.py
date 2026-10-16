#!/usr/bin/env python3
"""Stop-hook guard: catch a reply announcing a future merge nobody has confirmed.

A coordinator post that says "each thread merges as soon as it is clean" reads
as a status report, but it is a promise about an action that has not happened
and, under the strict merge policy, may not be allowed to. The reader acts on
it: they stop watching the PR. Observed 2026-10-16 in a project thread: the
announcement went out, no merge ever ran, and the PRs sat open.

Modelled on no-offer-to-file.py and reusing its transcript reader, so a
project-thread reply (`reply` / `post_message` / `update_message` tool call) is
read the same way. It fires only when BOTH hold:
  1. the reply announces a future merge ("merges as soon as", "will merge",
     "each thread merges") in prose, outside code spans, and the same sentence
     does not make the merge conditional on the user's own say-so; and
  2. the transcript holds no confirmed merge (a merge tool result reading
     "successfully merged", "Squashed and merged", `"merged": true`, ...).

Fires once per distinct message (sentinel keyed by content hash) so a block
cannot loop. Fails OPEN: a guard that wedges the session costs more than the
lapse it prevents.
"""
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile

_HERE = os.path.dirname(os.path.realpath(__file__))
_spec = importlib.util.spec_from_file_location(
    "no_offer_to_file", os.path.join(_HERE, "no-offer-to-file.py")
)
_offer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_offer)
last_assistant_text = _offer.last_assistant_text
sentence_around = _offer.sentence_around
strip_code = _offer.strip_code

ANNOUNCE_RX = re.compile(
    r"\b(each|every|all)\b[^.!?\n]{0,40}?\bmerges?\b"
    r"|\bmerg(es|ing)\b[^.!?\n]{0,30}?\b(as soon as|once|when|after)\b"
    r"|\bwill (be |auto-?|then )?merged?\b"
    r"|\b(is|are) (going|set|about) to (be )?merged?\b"
    r"|\bto be merged (as soon as|once|when|after)\b",
    re.I,
)

# The merge waits on the user's own words: that is the correct stance, not an
# announcement the user can be misled by.
CONDITIONAL_RX = re.compile(
    r"\bonly (after|when|if|on)\b"
    r"|\bunless\b"
    r"|\buntil (you|ezra|the user|i am told)\b"
    r"|\bif (you|ezra|the user) (say|confirm|approve|tell|want|ask)"
    r"|\b(after|once|when) (you|ezra|the user)\b[^.!?\n]{0,30}?"
    r"\b(say|confirm|approve|tell|give|grant|ask)"
    r"|\bexplicit(ly)? (merge|go|word|approval|permission|grant)",
    re.I,
)

# A merge that actually happened shows up in a tool result.
CONFIRMED_RX = re.compile(
    r"successfully merged|merged pull request|squashed and merged"
    r"|\"merged\"\s*:\s*true|\"state\"\s*:\s*\"MERGED\"",
    re.I,
)


def find_announcement(prose):
    """The first unconditional future-merge announcement in `prose`, or None."""
    for m in ANNOUNCE_RX.finditer(prose):
        if not CONDITIONAL_RX.search(sentence_around(prose, m.start(), m.end())):
            return m
    return None


def _result_text(block):
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            b.get("text", "") for b in content if isinstance(b, dict)
        )
    return ""


def merge_confirmed(path):
    """True when a non-error tool result in the transcript reports a merge."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                try:
                    m = json.loads(line)
                except Exception:
                    continue
                blocks = (m.get("message") or {}).get("content") or m.get("content")
                if not isinstance(blocks, list):
                    continue
                for b in blocks:
                    if (
                        isinstance(b, dict)
                        and b.get("type") == "tool_result"
                        and not b.get("is_error")
                        and CONFIRMED_RX.search(_result_text(b))
                    ):
                        return True
    except Exception:
        return False
    return False


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
            "Your message announces a future merge that no tool result in this "
            f"session confirms: \"{hit.group(0).strip()}\".\n\n"
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
