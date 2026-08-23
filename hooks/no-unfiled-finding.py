#!/usr/bin/env python3
"""Stop-hook guard: catch asserting a finding is worth an issue, unfiled.

`no-offer-to-file.py` catches the OFFER -- "worth an issue?", "want me to
file this?". Every pattern there carries an offer verb or a trailing `?`.
The declarative form asks nothing and slips straight past it:

    FLAG -- a mechanism bug worth its own issue.

That form is worse than the offer, not milder. An offer at least hands the
user a decision. A declarative flag hands them nothing, and naming the defect
*feels* like the diligent act, so the finding reads as handled while nothing
durable exists. `report-mistakes-proactively` makes the same point about
offers; this is that trade with the request removed.

The existing guard contributes to the blind spot: the shape it catches is the
one you get warned about, so the shape it misses is the one that ships.

Decidable from the transcript, which is why this is a hook and not a rule:

    message asserts something is worth an issue
    AND no issue-create or issue-comment call follows it

Both discharges count, because `report-mistakes-proactively` step 2 routes a
duplicate finding to a COMMENT on the existing issue rather than a new one.

Fails OPEN on any parse trouble, and fires at most once per distinct message.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

# Declarative filing-intent. Deliberately keyed on the ASSERTION, not on the
# FLAG marker: most flags are legitimately not issue-shaped (a merge-order
# note, a status heads-up), and a guard that fires on those gets switched off
# and takes the real case with it.
ASSERT = [
    r"worth (its own |a |an )?(issue|filing|tracking|a tracking issue)",
    r"worth (tracking|filing) (this |that |it )?separately",
    r"(needs|deserves|warrants) (its own |a |an )?(issue|tracking issue|follow-?up)",
    r"should be (filed|tracked)\b",
    r"(this|that) (is|reads as) a (separate |real )?(bug|defect)[^.]{0,40}\b(file|track)",
    r"\bfile (this|that|it) (as )?(a |an )?(separate |follow-?up )?issue\b",
    # Third-party deferral: the decision is handed to someone who is not in the
    # conversation, so no offer verb and no `?` appear and every pattern above
    # misses it. Three parts, all required, because any two over-fire -- a
    # deferral CONSTRUCTION, a named party, and a tracking word in the same
    # sentence.
    #
    # The construction took six review rounds, and the shape below is the third
    # distinct ANSWER rather than the sixth tuning of one. Recording the
    # rejected shapes and the stopping rule, because the useful part is which
    # axis was wrong rather than where any bound ended up.
    #
    # Rejected, all of which treated the words between the verb and the
    # connector as a WILDCARD and tuned its width:
    #
    #   1. Connector required immediately after the verb. Killed "left the
    #      reviewer a note" and also every real deferral with a noun-phrase
    #      object -- "leave THIS DECISION to the maintainer".
    #   2. Bare pronoun (it/this/that) allowed in the gap. Same failure, one
    #      noun phrase later.
    #   3. Any short wildcard gap, connector required BEFORE the party. That
    #      admits the benefactive: `to`/`for` is ambiguous in English between
    #      the deferral sense ("leave this decision TO the reviewer") and the
    #      dative one ("leave a note FOR the reviewer"), which is the same
    #      sentence as "leave the reviewer a note" with the recipient moved.
    #      Both have the identical surface shape, so NO width of wildcard
    #      separates them.
    #
    # What separates them is WHAT IS BEING HANDED OVER. You defer a DECISION
    # and you leave a NOTE, so the object is named rather than matched.
    #
    # Two consequences of that principle, each found by a round that applied it
    # more strictly than the list did:
    #
    # - The list admits only UNAMBIGUOUS decision nouns. `question` was in it
    #   and had to go: "the question of whether to file" is a decision, but "I
    #   left a question for the reviewer" is the same benefactive the principle
    #   exists to exclude, so the word carries both senses and cannot
    #   discriminate.
    # - `flag` REQUIRES its object, where the other verbs do not. "Deferring to
    #   the reviewer" is already a complete deferral, while "flagging for the
    #   reviewer" is ordinary English for bringing something to someone's
    #   attention and defers nothing. Leaving the object optional there fired
    #   on this corpus's own `FLAG` status convention, which the docstring at
    #   the top of this file explicitly names as a class that must not fire.
    #
    # STOPPING RULE, because this is a lexical guard standing in for a semantic
    # judgment and the supply of unmatched phrasings is endless. The list is
    # DELIBERATELY INCOMPLETE, and a phrasing it misses is an accepted false
    # negative rather than a defect. The asymmetry that licenses that: a missed
    # nag costs a finding that was probably filed anyway, while a false nag on
    # ordinary prose is what gets a guard switched off and takes the real cases
    # with it.
    #
    # Note which direction the rule governs. It licenses declining to chase a
    # FALSE NEGATIVE invented by an adversarial reader. It says nothing about a
    # FALSE POSITIVE, which is the failure the asymmetry is built around -- so
    # a demonstrated over-fire is always in scope, however contrived its
    # sentence looks.
    r"(?:defer(?:ring|red)?|leav(?:e|ing)|left)\s+"
    r"(?:(?:it|this|that)\s+)?(?:up\s+)?"
    r"(?:(?:the|this|that|a|an|my|our|their|its)\s+)?"
    r"(?:(?:\w+\s+)?(?:decision|call|judgment|judgement|choice|matter|concern)\s+)?"
    r"\b(?:to|for)\b[^.!?]{0,15}?"
    r"\b(reviewer|maintainer|owner|team|human)\b"
    r"[^.!?]{0,80}\b(issue|tracker|tracking|filing|follow-?up)\b",
    r"flag(?:ging)?\s+"
    r"(?:(?:the|this|that|a|an|my|our|their|its)\s+)?"
    r"(?:\w+\s+)?(?:decision|call|judgment|judgement|choice|matter|concern)\s+"
    r"\b(?:to|for)\b[^.!?]{0,15}?"
    r"\b(reviewer|maintainer|owner|team|human)\b"
    r"[^.!?]{0,80}\b(issue|tracker|tracking|filing|follow-?up)\b",
    r"\b(reviewer|maintainer|owner|team)(?:'s|s')?\s+"
    r"(call|discretion|judgment|judgement|to (?:judge|decide|say))\b[^.!?]{0,80}"
    r"\b(issue|tracker|tracking|filing|follow-?up)\b",
]
RX_ASSERT = re.compile("|".join(ASSERT), re.I)

# Already-filed talk. A message reporting an issue that exists is the
# CORRECT behaviour and must never be blocked.
RX_ALREADY = re.compile(
    r"\bfiled (as |it |them )?#?\d+|\btracked (in|by) #?\d+|"
    r"\bopened #?\d+|\bcommented on #?\d+|\bsee #\d+|\(#\d+\)",
    re.I,
)

# Discharge: creating an issue, or commenting a finding onto an existing one.
RX_FILE = re.compile(
    r"create_issue|gh\s+issue\s+create|gh\s+issue\s+comment|"
    r"issues/\d+/comments|mcp__github__create_issue|"
    r"add_issue_comment",
    re.I,
)


def scan(path):
    """Return (last_file_idx, last_assistant_idx, last_assistant_text)."""
    last_file = -1
    last_say = -1
    text = ""
    i = 0
    with open(path, errors="ignore") as fh:
        for line in fh:
            i += 1
            try:
                m = json.loads(line)
            except Exception:
                continue
            role = m.get("type")
            blocks = (m.get("message") or {}).get("content") or []
            if not isinstance(blocks, list):
                continue
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use":
                    # The harness tool names its verb only in `name`; a CLI
                    # call carries it in the command string.
                    blob = (b.get("name") or "") + " " + json.dumps(
                        b.get("input") or {})
                    if RX_FILE.search(blob):
                        last_file = i
                elif b.get("type") == "text" and role == "assistant":
                    if b.get("text", "").strip():
                        text = b["text"]
                        last_say = i
    return last_file, last_say, text


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        last_file, last_say, text = scan(payload.get("transcript_path") or "")
    except Exception:
        return 0  # fail open

    if not text:
        return 0
    hit = RX_ASSERT.search(text)
    if not hit:
        return 0
    # The message cites an issue, so the finding is already recorded.
    if RX_ALREADY.search(text):
        return 0
    # Something was filed at or after this message was composed.
    if last_file > last_say:
        return 0

    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-unfiled-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    print(json.dumps({
        "decision": "block",
        "reason": (
            f"Your message asserts a finding is worth tracking -- "
            f"\"{hit.group(0).strip()}\" -- and no issue was filed or "
            "commented on in this transcript afterwards.\n\n"
            "This is the DECLARATIVE form of the offer-to-file anti-pattern, "
            "and it is the worse one. An offer at least hands the reader a "
            "decision; naming the defect and moving on hands them nothing, "
            "while feeling like the diligent act. The finding then reads as "
            "handled and nothing durable exists.\n\n"
            "Do it now, in this same message:\n\n"
            "  1. Dupe-check:  gh issue list --state all --search '<terms>'\n"
            "  2. File it, or comment the new evidence onto the existing "
            "issue if one covers it\n"
            "  3. Cite the identifier the API actually returned -- never one "
            "you predicted\n\n"
            "If this finding genuinely is not issue-shaped -- a merge-order "
            "note, a status heads-up, a risk with no defect behind it -- say "
            "what it is instead of calling it worth an issue."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
