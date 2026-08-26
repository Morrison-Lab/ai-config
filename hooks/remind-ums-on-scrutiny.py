#!/usr/bin/env python3
"""UserPromptSubmit reminder: scrutiny of your work owes a UMS pass.

Standing rule (Morrison-Lab/ai-config#2261): run UMS when you read a review
of your work, when you receive critical feedback on it, or when a questioned
claim turns out to have been wrong. The last of those is the path this file
exists for.

WHY THE EXISTING HOOKS DO NOT COVER THIS
----------------------------------------
`remind-ums-after-error.py` keys on a FIRST-PERSON admission ("I was wrong")
and deliberately excludes correcting someone else. `remind-learn-from-review.py`
keys on ACCEPTING a finding. A clean-verdict UMS pass is later still.

Two decidable paths skip all of those:

  * You READ a review (Rebut, Defer, or no findings) and start ARD. The
    review taught something; Address and the verdict have not happened.
  * Someone questions a claim ("are you sure about that?"), you check, the
    claim was wrong, and you answer with the corrected fact. That reads as a
    closed Q&A. You never said "I was wrong", so the admission hook is silent.

The written rule also covers critical feedback that is not a review and not
a question. That remainder is not lexically decidable without nagging on
ordinary debugging ("this doesn't work yet"), so it stays a rule, not a
matcher. This hook covers the two slices that are.

WHY THIS INJECTS RATHER THAN BLOCKS
-----------------------------------
Identical to the two UMS reminders above. Reading a review and correcting a
claim are RIGHT to do; blocking either would suppress the work. Only the
FOLLOW-UP is owed. So this fires on the next prompt and can only ever ADD
context.

WHAT DISCHARGES IT
------------------
An EXPLICIT UMS / memorize / record-learnings action (UMS_WORD on Bash, Task,
Agent, or Skill), reused from the admission sibling so the three cannot drift
on what counts as a learning pass.

A bare Write/Edit of `shared/` / `memories/` / `CLAUDE.md` does NOT
discharge. After a review-read that edit is usually the ARD *fix*, which is
the same trap `remind-learn-from-review.py` documents (ai-config#1075): the
fix is not the lesson. Questioning-then-correcting has the same shape when
the wrong claim lived in a corpus file.

Erring toward OVER-firing is deliberate: a missed reminder is silent and
loses the lesson, while a spurious one costs one line.

Fails OPEN and SILENT: any parse trouble prints nothing at all.
Fires at most once per unpaid epoch (sentinel keyed by transcript path plus
the last UMS index), so a babysitting loop that re-fetches review comments
does not nag every turn.
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
        spec = importlib.util.spec_from_file_location("_sib_ums_scrutiny", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


_ums = _sibling("remind-ums-after-error.py")

visible_prose = getattr(_ums, "visible_prose", lambda t: t)
ADMISSION = getattr(_ums, "ADMISSION", None)
UMS_WORD = getattr(_ums, "UMS_WORD", None)

# Fetching a PR review or review comments. Deliberately NOT the bare word
# "review", which appears in almost every ARDI turn and would nag constantly.
# `issues/N/comments` is the endpoint that carries `**Claude finished` review
# bodies; include it because that is how this corpus actually reads a review
# (over-firing on a non-PR issue-comment fetch is the accepted cost).
# Paste markers live in REVIEW_PASTE and are NOT applied to tool_use blobs:
# a Grep of this file, or an adversarial-reviewer brief that names the
# verdict heading, is not a review-read.
REVIEW_FETCH = re.compile(
    r"get_review_comments|get_reviews|get_comments|"
    r"/pulls/\d+/(comments|reviews)\b|"
    r"/issues/\d+/comments|"
    r"gh\s+pr\s+view\b[^\n]*(--comments|\bcomments\b|\breviews\b)",
    re.I,
)
REVIEW_PASTE = re.compile(r"\*\*Claude finished|### Verdict", re.I)

# User (or reviewer-as-user) questioning a claim. Narrow on purpose: operational
# "did you push?" and "are you done?" must not match. The given example is
# "are you sure about that?".
QUESTIONING = re.compile(
    r"""(
      are\s+you\s+sure\b
    | are\s+you\s+certain\b
    | is\s+that\s+(?:even\s+)?(?:true|correct|accurate|right)\b
    | (?:i\s+don'?t\s+think|i\s+do\s+not\s+think)\s+that\b
    | that\s+doesn'?t\s+(?:sound|seem)\s+(?:right|correct)\b
    )""",
    re.I | re.X,
)

# Assistant correction of a prior claim. The first-person admission sibling
# already covers "I was wrong". Extra alternatives here must name that the
# prior value was displaced, not merely restate the current one.
#
# Discriminator (ai-config#2261 review): a COMMA contrast against a number
# ("Actually, it's 12, not 9." / "The figure is 12, not 9 as I said.")
# is the closed-Q&A path the issue names. Bare "not N" is not a contrast:
# "I'm not 100% sure" and "Not 5 minutes ago" must stay silent.
# "The correct figure is 12" and "Actually, it is 12" restate a confirmed
# claim and must stay silent too.
CORRECTION_EXTRA = re.compile(
    r"""(
      i\s+misspoke\b
    | that\s+(?:count|figure|number|claim)\s+was\s+
        (?:wrong|incorrect|off)\b
    | ,\s*not\s+\d+\b
    | not\s+\d+\s+as\s+i\s+said\b
    )""",
    re.I | re.X,
)


def records(path):
    with open(path, errors="ignore") as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except Exception:
                continue


def _blocks(m):
    content = (m.get("message") or {}).get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        return content
    return []


def _text_of(blocks):
    parts = []
    for b in blocks:
        if isinstance(b, str):
            parts.append(b)
        elif isinstance(b, dict) and b.get("type") == "text":
            parts.append(b.get("text") or "")
    return "\n".join(parts)


def _is_tool_result(blocks):
    for b in blocks:
        if isinstance(b, dict) and b.get("type") == "tool_result":
            return True
    return False


def _is_correction(prose):
    if not prose.strip():
        return False
    if ADMISSION is not None and ADMISSION.search(prose):
        return True
    return bool(CORRECTION_EXTRA.search(prose))


def scan(path):
    """Return (kind, quote, event_at, ums_at).

    kind is 'questioned-wrong' or 'review-read' or None.
    event_at is the index of the unpaid trigger; ums_at is the last explicit
    UMS action, or -1.
    """
    ums_at = -1
    last_review_at = -1
    last_question_at = -1
    last_question_txt = ""
    last_correction_at = -1
    last_correction_txt = ""
    last_assistant_at = -1

    for i, m in enumerate(records(path)):
        if m.get("isSidechain"):
            continue

        blocks = _blocks(m)
        rec_type = m.get("type")

        if rec_type == "user":
            raw = _text_of(blocks)
            prose = visible_prose(raw)
            # Paste markers on RAW text: a user-pasted review is often a
            # blockquote or fence, which visible_prose strips.
            if REVIEW_FETCH.search(prose) or REVIEW_PASTE.search(raw):
                last_review_at = i
            if _is_tool_result(blocks):
                continue
            hit = QUESTIONING.search(prose)
            if hit:
                last_question_at = i
                last_question_txt = hit.group(0).strip()
            elif (
                last_question_at >= 0
                and last_correction_at <= last_question_at
                and last_assistant_at > last_question_at
            ):
                # Close only after the assistant has replied without
                # correcting, so a queued follow-up before that reply does
                # not drop an in-flight "are you sure?" check.
                last_question_at = -1
            continue

        if rec_type != "assistant":
            continue
        last_assistant_at = i

        for b in blocks:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                name = b.get("name") or ""
                inp = b.get("input") or {}
                if not isinstance(inp, dict):
                    inp = {}
                blob = name + " " + json.dumps(inp)
                # Write/Edit bodies quote fetch patterns and paste markers.
                # Searching them treats authoring the rule as reading a review.
                # Paste markers are also omitted from this blob search so a
                # Grep or reviewer brief that names `### Verdict` stays silent.
                if name not in ("Write", "Edit", "NotebookEdit"):
                    if REVIEW_FETCH.search(blob):
                        last_review_at = i
                if name in ("Task", "Agent"):
                    ums_blob = (
                        str(inp.get("prompt", ""))
                        + str(inp.get("description", ""))
                    )
                elif name == "Bash":
                    ums_blob = str(inp.get("command", ""))
                elif name == "Skill":
                    ums_blob = (
                        str(inp.get("skill", "")) + str(inp.get("args", ""))
                    )
                else:
                    ums_blob = ""
                if ums_blob and UMS_WORD is not None and UMS_WORD.search(
                        ums_blob):
                    ums_at = i
            elif b.get("type") == "text":
                prose = visible_prose(b.get("text", ""))
                if _is_correction(prose):
                    last_correction_at = i
                    last_correction_txt = prose.strip().splitlines()[0][:80]

    unpaid_qw = (
        last_question_at >= 0
        and last_correction_at > last_question_at
        and last_correction_at > ums_at
    )
    unpaid_review = last_review_at > ums_at and last_review_at >= 0

    if unpaid_qw:
        quote = last_correction_txt or last_question_txt
        return "questioned-wrong", quote, last_correction_at, ums_at
    if unpaid_review:
        return "review-read", "review read", last_review_at, ums_at
    return None, "", -1, ums_at


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    path = payload.get("transcript_path") or ""
    if not path or not os.path.isfile(path):
        return 0
    if UMS_WORD is None:
        return 0

    try:
        kind, quote, _event_at, ums_at = scan(path)
    except Exception:
        return 0

    if not kind:
        return 0

    key = hashlib.sha256(
        f"{path}:{kind}:{ums_at}".encode()
    ).hexdigest()[:16]
    sentinel = os.path.join(
        tempfile.gettempdir(), f".claude-ums-on-scrutiny-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    if kind == "questioned-wrong":
        print(
            "[hook: remind-ums-on-scrutiny] A claim in this session was "
            "questioned and then corrected "
            f'("{quote}"), and no explicit UMS / memorize / '
            "record-learnings pass has been recorded since.\n"
            "CLAUDE.md ('Run UMS proactively') makes a questioned claim that "
            "was wrong a trigger in its own right. Answering with the "
            "corrected fact is not the pass -- record what you claimed, the "
            "query that settled it, and what replaced it.\n"
            "Delegate the pass to a subagent; that is pre-authorized standing "
            "sidecar work."
        )
    else:
        print(
            "[hook: remind-ums-on-scrutiny] An earlier turn in this session "
            "read a review of your work, and no explicit UMS / memorize / "
            "record-learnings pass has been recorded since.\n"
            "CLAUDE.md ('Run UMS proactively') makes reading a review a "
            "trigger, including Rebut, Defer, and a review with no findings. "
            "Do not wait for Address or a clean verdict.\n"
            "Delegate the pass to a subagent; that is pre-authorized standing "
            "sidecar work."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
