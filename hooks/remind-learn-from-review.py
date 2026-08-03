#!/usr/bin/env python3
"""UserPromptSubmit reminder: an ACCEPTED reviewer finding owes a learning.

Standing goal (Morrison-Lab/ai-config#1065): "every PR gets a clean review on
the first push -- learn from your mistakes so you don't repeat them, and
algorithmatize whenever possible". A reviewer's valid finding is a first-push
miss, so accepting one is a learn-from-mistakes trigger in its own right. This
file is that goal applied at the boundary where it is decidable.

WHY THE EXISTING HOOKS DO NOT COVER THIS
----------------------------------------
`remind-ums-after-error.py` and `no-mistake-without-a-hook.py` both key on a
FIRST-PERSON admission ("I was wrong", "my mistake"), and the former's
docstring is explicit that correcting SOMEONE ELSE must never fire it. Agreeing
with a reviewer is the commoner case and the one they miss by construction: you
admit nothing, you accept a finding. So the whole learn-from-mistakes
machinery -- record the learning, consider a mechanism -- never engages for the
mistakes a reviewer catches, which is exactly the class #1065 is about.

The condition is decidable from the transcript, which is why this is a hook
rather than a rule to remember:

    an acceptance of a reviewer's finding  AND  review context established
    AND  no learning or mechanism recorded after it

WHY THIS INJECTS RATHER THAN BLOCKS
-----------------------------------
Identical to `remind-ums-after-error.py`, and for the same reason. Accepting a
reviewer's finding and fixing it is RIGHT to do; blocking that would suppress a
correct action. Only the FOLLOW-UP is owed. So this fires on the next prompt
and can only ever ADD context -- there is no code path here that suppresses,
delays, or alters a message.

WHAT DISCHARGES IT
------------------
Any of, recorded at or after the acceptance:
  * a memory/skill/shared/CLAUDE.md write, or a `ums`/record-learnings pass
    (the learning half) -- detection reused from the sibling so the two cannot
    drift;
  * hook or check work -- `hooks/*.py`, `hooks.json`, a CI step (the mechanism
    half);
  * an explicit statement that the finding is a one-off with no rule or hook
    behind it. Forcing a mechanism onto a genuine one-off produces a guard that
    misfires and gets switched off (see `algorithmatize-checks`'s "Limits"), so
    saying so is a valid discharge -- the same carve-out
    `no-mistake-without-a-hook.py` makes.

Fires once per distinct acceptance (sentinel keyed by content hash), and fails
OPEN and SILENT: any parse trouble prints nothing at all.
"""
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def _sibling(name):
    """Import a hyphenated sibling module, or None if unavailable."""
    path = os.path.join(HERE, name)
    try:
        spec = importlib.util.spec_from_file_location("_sib", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


_ums = _sibling("remind-ums-after-error.py")

# Reuse the sibling's prose cleaner and its learning-detection patterns so the
# two hooks cannot drift on what counts as a recorded learning. Fallbacks exist
# only so this degrades to silence rather than crashing if the sibling is
# missing -- they must never become a second, divergent copy.
visible_prose = getattr(_ums, "visible_prose", lambda t: t)
UMS_PATH = getattr(
    _ums, "UMS_PATH",
    re.compile(r"(memories?/|MEMORY\.md|CLAUDE\.md|/skills/|^skills/|/shared/|^shared/)", re.I))
UMS_WORD = getattr(
    _ums, "UMS_WORD",
    re.compile(r"\bums\b|update\s+memories|record[- ]learnings|memorize", re.I))

# Accepting a reviewer's finding. Deliberately the AGREEMENT vocabulary only: a
# Rebut ("the review is wrong") is the opposite disposition and must never fire
# this, so no bare "the finding" without an agreement verb, and nothing that a
# rebuttal would also match.
ACCEPT = re.compile(
    r"""(
      good\s+catch
    | nice\s+catch
    | great\s+catch
    | you(?:'re|\s+are)\s+right
    | (?:the\s+)?review(?:er)?(?:'s|\s+is)\s+right
    | (?:that|this)(?:'s|\s+is)\s+(?:a\s+)?(?:correct|valid|fair|good)\s+
        (?:catch|point|finding|call)
    | (?:valid|fair)\s+(?:point|concern|finding|catch)
    | (?:good|fair)\s+point
    | the\s+finding\s+is\s+(?:correct|right|valid)
    | (?:agreed|correct),?\s+(?:the\s+)?review(?:er)?
    )""",
    re.I | re.X,
)

# Review context, so a "good catch" to the USER, or in a non-PR context, does
# not fire. Established by a review-surface tool call anywhere at or before the
# acceptance, OR by the acceptance sentence itself naming the review.
REVIEW_TOOL = re.compile(
    r"resolve_review_thread|add_reply_to_pull_request_comment|"
    r"add_comment_to_pending_review|pull_request_review_write|"
    r"get_review_comments|get_reviews|request_copilot_review|"
    r"gh\s+pr\s+review|/pulls/\d+/(comments|reviews)",
    re.I,
)
REVIEW_WORD = re.compile(
    r"\breview(?:er)?\b|\bfinding\b|\bnit\b|\bcopilot\b|\bjules\b|claude-review",
    re.I,
)

# Building a mechanism from the finding -- the algorithmatize half.
HOOK_WORK = re.compile(
    r"hooks/[\w.-]+\.py|hooks\.json|install-hooks\.py|\.github/workflows/", re.I)

# An explicit judgment that the finding is not a learnable pattern. Discharges,
# because forcing a rule or hook onto a one-off is worse than none.
NOT_ENCODABLE = re.compile(
    r"one[- ]off|not\s+(?:a\s+)?(?:pattern|generaliz|mechaniz|hookab|recurring)|"
    r"no\s+(?:rule|hook|check|mechanism|decidable)|"
    r"already\s+(?:covered|encoded|a\s+rule|tracked)|"
    r"not\s+worth\s+(?:a\s+)?(?:rule|hook|encoding|recording)|"
    r"could\s?n(?:o|')t\s+have\s+(?:known|caught)",
    re.I,
)


def records(path):
    with open(path, errors="ignore") as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except Exception:
                continue


def scan(path):
    """Return (accept_text, accept_at, discharge_at).

    accept_at is the index of the last acceptance for which review context is
    already established; -1 if none. discharge_at is the last index carrying a
    learning, a mechanism, or a not-encodable judgment.
    """
    accept_txt, accept_at, discharge_at = None, -1, -1
    review_ctx = False  # a review-surface tool call has been seen

    for i, m in enumerate(records(path)):
        # A subagent's own turns are not my outgoing message; skip them the way
        # the sibling does.
        if m.get("isSidechain"):
            continue
        blocks = (m.get("message") or {}).get("content") or []
        if not isinstance(blocks, list):
            continue
        is_assistant = m.get("type") == "assistant"

        for b in blocks:
            if not isinstance(b, dict):
                continue

            if b.get("type") == "tool_use":
                name = b.get("name") or ""
                inp = b.get("input") or {}
                if not isinstance(inp, dict):
                    inp = {}
                blob = name + " " + json.dumps(inp)
                if REVIEW_TOOL.search(blob):
                    review_ctx = True
                if HOOK_WORK.search(blob):
                    discharge_at = i
                if name in ("Write", "Edit", "NotebookEdit"):
                    if UMS_PATH.search(str(inp.get("file_path", ""))):
                        discharge_at = i
                    continue
                if name in ("Task", "Agent"):
                    blob2 = str(inp.get("prompt", "")) + str(inp.get("description", ""))
                elif name == "Bash":
                    blob2 = str(inp.get("command", ""))
                elif name == "Skill":
                    blob2 = str(inp.get("skill", "")) + str(inp.get("args", ""))
                else:
                    blob2 = ""
                if blob2 and (UMS_WORD.search(blob2) or HOOK_WORK.search(blob2)):
                    discharge_at = i

            elif b.get("type") == "text" and is_assistant:
                prose = visible_prose(b.get("text", ""))
                if not prose.strip():
                    continue
                if NOT_ENCODABLE.search(prose) or HOOK_WORK.search(prose):
                    discharge_at = i
                hit = ACCEPT.search(prose)
                if hit and (review_ctx or REVIEW_WORD.search(prose)):
                    accept_txt, accept_at = hit.group(0).strip(), i

    return accept_txt, accept_at, discharge_at


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    path = payload.get("transcript_path") or ""
    if not path or not os.path.isfile(path):
        return 0

    try:
        accept_txt, accept_at, discharge_at = scan(path)
    except Exception:
        return 0  # fail open

    if accept_at < 0:
        return 0
    # `>=` rather than `>`: a single message can both accept the finding and
    # record the learning (or judge it a one-off), and that is the ideal case.
    # Recording strictly BEFORE the acceptance does not discharge it.
    if discharge_at >= accept_at:
        return 0

    key = hashlib.sha256(f"{path}:{accept_txt}:{accept_at}".encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-learn-from-review-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    print(
        "[hook: remind-learn-from-review] You accepted a reviewer's finding "
        f"earlier in this session (\"{accept_txt}\") and recorded no learning "
        "or mechanism after it.\n\n"
        "Standing goal (Morrison-Lab/ai-config#1065): every PR gets a clean "
        "review on the first push -- so a reviewer's valid finding is a "
        "first-push miss to learn from, not just an item to fix and close. "
        "Fixing it discharges the PR; it does not discharge the lesson, and the "
        "two feel identical from the inside.\n\n"
        "This is the external-correction case hooks/remind-ums-after-error.py "
        "misses by construction: it keys on a first-person admission (\"I was "
        "wrong\"), and here you agreed with someone else instead.\n\n"
        "Do two things beyond the fix (see "
        "shared/workflow/learn-from-review-findings.md):\n"
        "  1. Record the class of mistake -- what you overlooked and what the "
        "reviewer saw. Delegate it to a subagent, as pre-authorized sidecar "
        "work.\n"
        "  2. Ask whether it is algorithmatizable "
        "(shared/workflow/algorithmatize-checks.md): a finding with a decidable "
        "condition -- a banned token, a stale cross-reference, a missing test "
        "-- is one a pre-push check or a hook can catch every time thereafter, "
        "so the next reviewer never has to.\n\n"
        "If the finding is a genuine one-off (a typo, a fact you could not have "
        "known, a judgment call), say so explicitly and why -- that discharges "
        "this as completely as recording it. What this catches is the silent "
        "third option: fix it, resolve the thread, and record nothing.\n\n"
        "This only ever adds context; it never blocks. Accepting a finding is "
        "right -- only the follow-up is owed."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
