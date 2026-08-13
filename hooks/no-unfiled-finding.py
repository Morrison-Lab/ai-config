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
