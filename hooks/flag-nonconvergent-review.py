#!/usr/bin/env python3
r"""Stop-hook guard: an adversarial review loop that is not converging.

Driving a PR to clean is supposed to terminate. Each round addresses the
last round's findings, the next round finds fewer, and eventually one comes
back clean. When that is not what is happening -- round after round returning
findings of the SAME category, several of them introduced by the previous
round's own fix -- the loop is not converging, and continuing to patch is
worse than stopping to ask whether the design is wrong.

Nothing else in this corpus notices. Every individual round looks like
diligence: real findings, honestly addressed, with a commit explaining each.
The non-convergence is a property of the SEQUENCE, visible only by counting
across rounds, and the session driving it is the least placed to see it --
each round feels like progress because each round fixes something real.

THE MEASUREMENT (2026-09-04/05)
--------------------------------
One session, two loops.

`ucdavis/hac.sap#43` took fifteen rounds. Rounds 3-6 each produced only
test-coverage gaps, and the same class -- an assertion satisfied by a
different unfilled default than the site under test -- recurred five times,
twice inside assertions written to fix the previous instance.

A hook authored in the same session took four rounds and about 41 findings.
Its round-four review said so directly: "Findings 1, 3 and 4 are the same
three classes this round was written to retract ... reappearing inside the
fix for them." The value being defended was one true positive across 2101
real test files. Calling time at round two would have been right, and the
session said so only at round four -- after the cost was sunk.

WHAT IT CHECKS
--------------
Adversarial reviews report `[FINDINGS_COUNT: N]` and, in their `review-data`
block, a `category` per finding. Both are countable from the transcript. The
guard warns when, in this session:

    * at least MIN_ROUNDS review verdicts have been seen, AND
    * the most recent one is non-clean, AND
    * either some category has appeared in at least RECUR_ROUNDS distinct
      rounds, or the finding counts show no downward trend across the last
      three.

It reports the counts and the recurring categories and asks one question:
is the design wrong? It never blocks, and it fires once per session per
round count, so a long loop is not nagged on every turn.

WHAT IT DOES NOT DO
-------------------
It does not say to stop. A loop can legitimately run long -- a large diff, a
reviewer finding genuinely new ground each round, a deliberately exhaustive
sweep. Converging slowly and not converging look similar from inside and
differ in whether the CATEGORIES repeat, which is why that is the trigger
rather than the round count alone.

Fails OPEN.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

MIN_ROUNDS = 4
RECUR_ROUNDS = 3

RX_COUNT = re.compile(r"\[FINDINGS_COUNT:\s*(\d+)\]")
RX_CATEGORY = re.compile(r'"category"\s*:\s*"([^"]+)"')

NOTE = """This session has run {rounds} adversarial review rounds and the latest is
not clean. Finding counts, oldest first: {counts}.

{detail}

Each round on its own looks like diligence -- real findings, honestly
addressed. Non-convergence is a property of the SEQUENCE, and the session
driving it is the least placed to see it, because every round fixes something
real.

Before starting another round, answer one question in the reply: is the
DESIGN wrong rather than the implementation? Concretely --

  * What does this artifact buy, measured? If the answer is small, say so.
  * Is there an existing instrument that already catches this class? The
    thing a guard duplicates is usually cheaper and already trusted.
  * Would a different shape end the loop -- dissolving the coupling rather
    than instrumenting it, per shared/principles/deterministic-tools.md?

Continuing is a legitimate answer. Continuing without having asked is what
this warns about. Measured 2026-09-04/05: two loops in one session, fifteen
rounds and four, the second returning "the same three classes this round was
written to retract ... reappearing inside the fix for them"."""

RECUR_LINE = ("Categories recurring across rounds: {cats}. A category that "
              "comes back is the signal -- it means the fix for it introduced "
              "another instance of it.")
FLAT_LINE = ("The last three counts show no downward trend, so the rounds are "
             "not narrowing.")


def records(path):
    with open(path, errors="ignore") as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except Exception:
                continue


def _text_of(rec):
    """Every text block in one transcript record, concatenated."""
    parts = []
    for holder in (rec.get("message") or {}, rec):
        content = holder.get("content")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for b in content:
                if isinstance(b, dict):
                    if isinstance(b.get("text"), str):
                        parts.append(b["text"])
                    # A subagent's report arrives as a tool result.
                    c = b.get("content")
                    if isinstance(c, str):
                        parts.append(c)
                    elif isinstance(c, list):
                        parts.extend(
                            x.get("text", "") for x in c if isinstance(x, dict)
                        )
    return "\n".join(p for p in parts if p)


def scan(path):
    """(counts, categories_per_round) for every review verdict in order."""
    counts, cats = [], []
    for rec in records(path):
        text = _text_of(rec)
        if not text:
            continue
        for m in RX_COUNT.finditer(text):
            counts.append(int(m.group(1)))
            # Categories from the review-data block nearest this verdict.
            cats.append(set(RX_CATEGORY.findall(text)))
    return counts, cats


def verdict(counts, cats):
    """(should_warn, detail) -- the judgement, separated for testing."""
    if len(counts) < MIN_ROUNDS or not counts[-1]:
        return False, ""
    recurring = sorted(
        c for c in set().union(*cats) if sum(c in s for s in cats) >= RECUR_ROUNDS
    ) if cats and any(cats) else []
    # "No downward trend" stated simply: across the last three rounds the
    # count ended no lower than it started. `[5, 3, 4, 6]` is flat;
    # `[10, 9, 15, 7]` is not, however jagged, because it ended lower.
    # An earlier revision compared against the minimum of all earlier rounds,
    # which called a jagged-but-narrowing loop flat.
    last3 = counts[-3:]
    flat = len(last3) == 3 and last3[-1] >= last3[0] and last3[-1] > 0
    if not recurring and not flat:
        return False, ""
    detail = []
    if recurring:
        detail.append(RECUR_LINE.format(cats=", ".join(recurring)))
    if flat:
        detail.append(FLAT_LINE)
    return True, " ".join(detail)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0
    path = payload.get("transcript_path") or ""
    if not path or not os.path.isfile(path):
        return 0
    try:
        counts, cats = scan(path)
        warn, detail = verdict(counts, cats)
        if not warn:
            return 0
        # Keyed on the round count as well as the session, so a long loop
        # warns once per NEW round rather than on every turn.
        key = hashlib.sha256(f"{path}:{len(counts)}".encode()).hexdigest()[:16]
        sentinel = os.path.join(
            tempfile.gettempdir(), f".claude-nonconvergent-review-{key}")
        if os.path.exists(sentinel):
            return 0
        try:
            open(sentinel, "w").close()
        except Exception:
            pass
        context = NOTE.format(
            rounds=len(counts),
            counts=", ".join(str(c) for c in counts),
            detail=detail,
        )
        out = {"hookSpecificOutput": {
            "hookEventName": "Stop", "additionalContext": context}}
        if not os.environ.get("ANTIGRAVITY_AGENT"):
            out["systemMessage"] = (
                f"Review loop: {len(counts)} rounds, latest not clean. "
                "Ask whether the design is wrong before another round.")
        print(json.dumps(out))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
