#!/usr/bin/env python3
"""Stop guard: reporting an issue as open or blocked without having read its comments.

An issue BODY is frozen at filing time. Its COMMENTS carry everything since:
the measurement that already ran, the PR that already shipped half of it, the
decision that was already taken. So a claim about what an issue still needs is
a claim about its comments, and reading only the body cannot support it.

THE MEASUREMENT (2026-09-21, ai-config#3823)
---------------------------------------------
Twice on `Lacaedemon/sparta`, and the second time is what this guard is for.

  1. 2026-09-19, #1544. A session claimed the issue from its body alone and
     proposed a state dump that had already merged in #1553. It self-corrected
     within the hour.
  2. 2026-09-21, #1566. A session read the body down to its `## Options`
     heading and stopped, then told the user across many turns that the issue
     needed THEIR decision, and that two P2 issues were blocked behind it. The
     decision had been taken, recorded in a design doc, and closed out; the
     issue's five comments said so, and three commits naming that work sat in
     the repository's recent history. It surfaced only when the user asked
     "what do I need to do on 1566?".

WHY THE SECOND SHAPE NEEDS AN INSTRUMENT AND THE FIRST DID NOT
---------------------------------------------------------------
They fail in opposite directions, which is why one prose memory covered the
first and did not reach the second.

Claiming an issue and redoing merged work COLLIDES with reality quickly: you
open the file and the change is already there, so the mistake reports itself.

Escalating -- saying an issue is blocked, or awaits a human -- produces
nothing that can collide. It reads as diligence, it survives recap after
recap, and it is falsified only when a person reads it. In the measured case
it also compounded: downstream plans about two unrelated issues were built on
the false premise, so one unread comment thread produced repeated wrong
advice.

WHAT IT CHECKS
--------------
    the final assistant message asserts that issue #N is open work, is
        blocked, awaits a decision, or is waiting on the user
    AND no command in the transcript read #N's COMMENTS

A body-only read does NOT discharge it. `gh issue view <N> --json body` and
`--json title,body` are exactly what produced both measured failures, so
treating them as sufficient would make the guard inert on its own cases.

WHAT DISCHARGES IT
------------------
Any command that actually returns the comments for that number:
`gh issue view <N> --comments`, `--json comments`, `gh api .../issues/<N>/comments`,
`glab issue view <N> --comments`, or an MCP issue read naming comments.

The number must match. Reading #12's comments says nothing about #34, and a
guard that accepted any comment read anywhere would pass the moment a session
looked at one unrelated issue.

CONTRACT
--------
Warns, never blocks. An issue can legitimately BE blocked, and saying so is
often the correct report -- the guard cannot know which, only that the
cheapest supporting evidence was never gathered. Fails open on every internal
error, per the hooks' file-wide contract.
"""

import json
import os
import re
import sys

# Code regions are quoted material, not assertions. A recap explaining THIS
# guard cites its own trigger phrases, and every such citation is an assertion
# in form and a quotation in fact.
BLOCK = re.compile(r"```.*?```|^[ \t]*>[^\n]*$", re.S | re.M)
TICK = re.compile(r"`[^`\n]*`")


def visible_prose(text):
    """Drop fenced blocks, blockquotes and code spans, keeping offsets sane.

    A period is substituted rather than a space so the removed region acts as
    a sentence BOUNDARY: the cue and the issue reference must co-occur in one
    sentence, and a code span between them should separate rather than join.
    """
    if not isinstance(text, str):
        return ""
    text = BLOCK.sub(".", text)
    return TICK.sub(".", text)


# An issue reference. `PR #12` and a pull URL are excluded: this guard is
# about issues, and a PR's comments are a different question with its own
# guards.
RX_ISSUE = re.compile(
    r"(?<![A-Za-z0-9])(?<!pull/)#(\d{1,7})(?![0-9])"
)
RX_PR_PREFIX = re.compile(r"(?:\bPR|\bpull request|\bpull)\s*$", re.I)

# Asserting that the issue still needs something. Deliberately narrow: an
# ordinary mention of an issue number is not a claim about its state, and a
# guard that fired on every `#N` would be noise and get switched off.
CUES = [
    r"\bblocked\s+(?:on|by)\b",
    r"\bawait(?:s|ing)\b",
    r"\bwaiting\s+(?:on|for)\b",
    r"\bneeds?\s+(?:your|a\s+human|the\s+user|a\s+decision|an\s+answer)",
    r"\byour\s+(?:call|decision|answer|input)\b",
    # "that one is yours rather than mine" -- the commonest way an escalation
    # is actually phrased, and the shape the measured case used. Without it
    # the guard misses its own originating sentence.
    r"\b(?:is|are|stays?|remains?)\s+yours\b",
    r"\byours\s+(?:to\b|rather\s+than\b)",
    r"\bstill\s+(?:open|unanswered|outstanding|needs)\b",
    r"\bremains?\s+(?:open|unanswered|outstanding|blocked)\b",
    r"\bunanswered\b",
    r"\bgates?\b",
    r"\bopen\s+work\b",
    r"\bnot\s+(?:yet\s+)?(?:started|done|decided)\b",
    r"\bpending\b",
]
RX_CUE = re.compile("|".join(CUES), re.I)

# Reading an issue's COMMENTS, capturing the number. Three surfaces, because
# all three occur in this corpus.
READS = [
    # gh/glab issue view <N> ... with a comments flag, in either order.
    r"issue\s+view\s+[\"']?#?(\d{1,7})[\"']?[^\n|;&]*?(?:--comments|--json[^\n|;&]*comments)",
    r"issue\s+view\s+[\"']?#?(\d{1,7})[\"']?[^\n|;&]*?-c\b",
    # REST: .../issues/<N>/comments
    r"issues/(\d{1,7})/comments",
    # MCP issue read naming comments in the same call.
    r"issue_read[^\n]*?[\"']issue_number[\"']\s*:\s*(\d{1,7})[^\n]*?comments",
    r"issue_read[^\n]*?comments[^\n]*?[\"']issue_number[\"']\s*:\s*(\d{1,7})",
]
RX_READS = [re.compile(p, re.I) for p in READS]

NOTE = (
    "Unread-issue reminder: this message reports issue #{n} as open, blocked, "
    "or awaiting a decision, and nothing in this session read #{n}'s "
    "COMMENTS.\n\n"
    "An issue's BODY is frozen at filing time. Its comments carry what has "
    "happened since -- the measurement that already ran, the PR that already "
    "shipped half of it, the decision that was already taken. A body-only "
    "read cannot support a claim about what the issue still needs.\n\n"
    "    gh issue view {n} --comments\n\n"
    "Also worth one look: whether the work landed already --\n\n"
    "    git log --oneline -20 | grep -i '#{n}'\n\n"
    "Measured twice on the same repository (ai-config#3823). The second time, "
    "a decision that had already been taken and documented was reported to "
    "the user as theirs to make, across several turns, and two unrelated "
    "issues were described as blocked behind it.\n\n"
    "If the issue genuinely is blocked, say so -- this is a reminder, not a "
    "refusal."
)


def comments_read(transcript_path):
    """Set of issue numbers whose comments some command in the session read."""
    seen = set()
    if not transcript_path or not os.path.exists(transcript_path):
        return None
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                blocks = (rec.get("message") or {}).get("content") or rec.get("content") or []
                blobs = []
                if isinstance(blocks, list):
                    for b in blocks:
                        if isinstance(b, dict) and b.get("type") == "tool_use":
                            blobs.append(json.dumps(b.get("input") or {}))
                for tc in rec.get("tool_calls") or []:
                    if isinstance(tc, dict):
                        blobs.append(json.dumps(tc.get("args") or tc.get("input") or {}))
                for blob in blobs:
                    for rx in RX_READS:
                        for m in rx.finditer(blob):
                            seen.add(m.group(1))
    except Exception:
        return None
    return seen


def last_assistant_text(transcript_path):
    """The final assistant message's visible text, or ''."""
    text = ""
    if not transcript_path or not os.path.exists(transcript_path):
        return text
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                role = rec.get("type") or rec.get("role")
                blocks = (rec.get("message") or {}).get("content") or rec.get("content") or []
                if isinstance(blocks, list):
                    for b in blocks:
                        if (isinstance(b, dict) and b.get("type") == "text"
                                and role == "assistant" and (b.get("text") or "").strip()):
                            text = b["text"]
                elif isinstance(blocks, str) and role == "assistant" and blocks.strip():
                    text = blocks
    except Exception:
        return ""
    return text


def asserted_issues(text):
    """Issue numbers this text reports as open, blocked, or awaiting someone.

    The cue and the reference must share a SENTENCE. Requiring only that both
    appear in the message would fire on any recap that mentions an issue
    anywhere and says "blocked" about something else entirely.
    """
    out = []
    prose = visible_prose(text)
    for sentence in re.split(r"(?<=[.!?\n])\s+", prose):
        if not RX_CUE.search(sentence):
            continue
        for m in RX_ISSUE.finditer(sentence):
            if RX_PR_PREFIX.search(sentence[:m.start()]):
                continue
            out.append(m.group(1))
    return out


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        tpath = payload.get("transcript_path") or payload.get("transcriptPath") or ""
        text = last_assistant_text(tpath)
        if not text:
            return 0
        numbers = asserted_issues(text)
        if not numbers:
            return 0
        seen = comments_read(tpath)
        if seen is None:
            # No readable transcript means no evidence either way. Fail open
            # rather than warn on every issue mention in a session we cannot
            # inspect.
            return 0
        missing = [n for n in numbers if n not in seen]
        if not missing:
            return 0
        n = missing[0]
        out = {
            "hookSpecificOutput": {
                "hookEventName": "Stop",
                "additionalContext": NOTE.format(n=n),
            },
        }
        if not os.environ.get("ANTIGRAVITY_AGENT"):
            out["systemMessage"] = (
                f"Unread-issue reminder: #{n} is reported as open or blocked, "
                f"but its comments were never read. Run "
                f"`gh issue view {n} --comments` before asserting what it needs.")
        print(json.dumps(out))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
