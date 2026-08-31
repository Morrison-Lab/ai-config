#!/usr/bin/env python3
"""Shared reader for the reviewer's structured ``review-data`` payload.

The adversarial-reviewer contract asks every reviewer to append a
machine-readable payload after its human-readable report::

    <!-- review-data: {"schema_version": "1.0", "verdict": "CLEAN", ...} -->

Two scripts consume that payload -- ``scripts/check-pr-fully-clean.py`` for a
comment posted to a PR, and ``scripts/pre-push-review.py`` for a report
produced locally -- and they must agree, because they score the same artifact.
They did not: the local parser stripped HTML comments before every check, so a
report whose payload said ``NOT_CLEAN`` parsed as ``Verdict: CLEAN`` locally
while the PR-side consumer scored it blocking.  One extractor, imported by
both, is what keeps that from recurring.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

try:  # imported as ``scripts.lib.review_payload``
    from .fences import CODE_SPAN_RE, find_fence_spans
except ImportError:  # imported flat, with scripts/lib on sys.path
    from fences import CODE_SPAN_RE, find_fence_spans  # type: ignore[no-redef]

# Verdict strings that block, normalized to upper case with ``-`` and spaces
# folded to ``_`` so ``Not clean``, ``NOT-CLEAN`` and ``NOT_CLEAN`` are one key.
NOT_CLEAN_VERDICTS = frozenset(
    {
        "NOT_CLEAN",
        "NEEDS_WORK",
        "NEEDS_MORE_WORK",
        "CHANGES_REQUESTED",
        "BLOCK",
        "BLOCKED",
        "REJECTED",
    }
)

# Verdict strings that clear, under the same normalization.
CLEAN_VERDICTS = frozenset({"CLEAN", "READY_FOR_MERGE", "APPROVED", "APPROVE"})

# One accepted spelling only.  `review-json` was accepted here and in
# REVIEW_BODY_MARKERS while nothing in the corpus emitted or documented it --
# a second verdict-bearing input spelling with no producer, bought for nothing.
_PAYLOAD_RE = re.compile(
    r"<!--\s*review-data\s*:\s*(\{[\s\S]*?\})\s*-->",
    re.IGNORECASE,
)


def normalize_verdict(raw: Any) -> str:
    """Fold a payload ``verdict`` value to the form the frozensets above use."""
    return str(raw or "").strip().upper().replace("-", "_").replace(" ", "_")


def code_region_mask(body: str) -> bytearray:
    """Byte-per-character mask: 1 where *body* is inside a code region.

    Covers fenced blocks, orphan fence lines, CommonMark indented code blocks,
    and inline code spans.  Over-masking is the safe direction here and
    under-masking is not: a payload this mask hides falls back to the prose
    scan, which is the behaviour that predates structured review data, whereas
    a payload read out of quoted example text inverts a verdict.  The
    indented-block test is correspondingly crude -- it also catches indented
    list continuations -- for that reason.
    """
    mask = bytearray(len(body))
    # NOT wrapped in try/except.  Swallowing an exception here would set
    # `fenced_lines` empty and so disable fence masking entirely for that body
    # -- the UNDER-masking direction this docstring calls unsafe, silently and
    # with nothing red.  The sibling call in `check-pr-fully-clean.py` is
    # unwrapped for the same reason (`shared/principles/fail-fast.md`).
    #
    # swallow_unclosed=True, matching that sibling: the default records only an
    # unclosed fence's OPENER line and leaves its interior live, which breaks
    # this function in both directions -- a truncated review's quoted CLEAN
    # template counts as a real verdict, and a quoted NOT_CLEAN payload mints a
    # finding no ARD round can discharge (the ai-config#2482 class).
    fenced, _, orphans = find_fence_spans(body, swallow_unclosed=True)
    fenced_lines = set(fenced) | set(orphans)

    offset = 0
    for lineno, line in enumerate(body.split("\n")):
        end = offset + len(line)
        if lineno in fenced_lines or line.startswith("    ") or line.startswith("\t"):
            mask[offset:end] = b"\x01" * (end - offset)
        offset = end + 1

    for m in CODE_SPAN_RE.finditer(body):
        mask[m.start():m.end()] = b"\x01" * (m.end() - m.start())
    return mask


def extract_structured_review(body: str) -> Optional[Dict[str, Any]]:
    """Return the reviewer's structured payload, or ``None``.

    Two properties are load-bearing, and both were false in the first cut:

    * **The LAST valid payload wins.**  The contract puts the authoritative
      payload after the verdict and the ``Reviewed-Commit`` fingerprint, i.e.
      last, and the persona template it is copied from hardcodes
      ``"verdict": "CLEAN"``.  First-match-wins therefore let a reviewer who
      quoted the template anywhere above their own payload publish a
      ``NOT_CLEAN`` review that scored clean.
    * **Code regions are excluded**, via :func:`code_region_mask` -- fences,
      code spans, and indented blocks alike.  ``check-pr-fully-clean.py``
      already refuses to read a *finding* out of quoted text (see
      ``strip_cited_finding_vocab``, ai-config#2449); a *verdict* payload gets
      the same treatment, so a comment that merely mentions the format is not
      a review of anything.

    There is deliberately no ``<details>``-plus-JSON-fence fallback.  A payload
    inside a fence is unreachable by construction under the rule above, and a
    pattern loose enough to reach one spans arbitrary distance -- so a reviewer
    collapsing an earlier round's payload for reference minted a blocking
    finding no ARD round could discharge (the ai-config#2482 class).
    """
    if not body or not isinstance(body, str):
        return None

    mask = code_region_mask(body)
    found: Optional[Dict[str, Any]] = None
    for m in _PAYLOAD_RE.finditer(body):
        if mask[m.start()]:
            continue
        # Everything before the payload ON ITS OWN LINE must be WHITESPACE.
        # Masking code regions is not enough by itself: a payload written
        # mid-sentence in ordinary prose ("Reviewers must end with <!-- review-
        # data: ... -->") or behind a `> ` blockquote marker (what GitHub's
        # Quote reply emits) sits in no code region at all, and was read as the
        # comment's authoritative verdict -- a false CLEAN in one direction
        # and, from a narrated earlier round, an undischargeable finding in the
        # other.
        #
        # WHITESPACE rather than column zero, which an earlier cut required and
        # which was worse than the hole it closed: `build_review_prompt` and
        # both persona files render the payload three spaces in, so a reviewer
        # following the prompt's own layout had its payload silently dropped
        # and a NOT_CLEAN verdict reported clean.  One leading space was enough.
        #
        # Three spaces is deliberately still readable while four is not: four
        # is a CommonMark indented code block, which `code_region_mask` masks,
        # so the two rules meet exactly at the CommonMark boundary rather than
        # at an arbitrary one.  The prompt renders three and now says "flush
        # left, not indented" explicitly, so a four-space payload is a
        # deviation from a stated instruction reading as the code block it is.
        line_start = body.rfind("\n", 0, m.start()) + 1
        if body[line_start:m.start()].strip():
            continue
        try:
            data = json.loads(m.group(1).strip())
        except Exception:
            continue
        if isinstance(data, dict) and "verdict" in data:
            found = data
    return found


def payload_findings(payload: Optional[Dict[str, Any]]) -> list:
    """The payload's ``findings`` list, or ``[]`` when absent or not a list.

    Callers must pair this with :func:`payload_findings_malformed`: on its own
    it cannot distinguish "the reviewer listed nothing" from "the reviewer put
    something there that is not a list", and those two must not be treated
    alike.
    """
    if not payload:
        return []
    findings = payload.get("findings")
    return findings if isinstance(findings, list) else []


def payload_findings_malformed(payload: Optional[Dict[str, Any]]) -> bool:
    """True when ``findings`` is PRESENT but is not a list.

    A present-but-malformed field must never CLEAR, only block.  Folding it to
    ``[]`` made a type deviation do what an empty array does, so a payload
    reading ``"findings": "3 defects listed above"`` satisfied quorum and the
    PR gate reported fully clean -- the fail-open direction in a fail-closed
    scanner (``shared/principles/fail-fast.md``).
    """
    if not payload:
        return False
    return "findings" in payload and not isinstance(payload["findings"], list)


def payload_is_blocking(payload: Optional[Dict[str, Any]]) -> bool:
    """True when the payload blocks: a not-clean verdict, any finding, or a
    malformed ``findings`` field.

    Findings alone block regardless of the stated verdict, because a reviewer
    that enumerates findings and then labels itself clean is contradicting
    itself, and the safe reading of a contradiction is the blocking one.
    """
    if not payload:
        return False
    if payload_findings_malformed(payload):
        return True
    if payload_findings(payload):
        return True
    return normalize_verdict(payload.get("verdict")) in NOT_CLEAN_VERDICTS


def payload_is_clean(payload: Optional[Dict[str, Any]]) -> bool:
    """True when the payload affirmatively clears.

    Requires all three: a clean verdict, a ``findings`` key that is PRESENT and
    a list, and that list empty.  Requiring presence is the point -- both
    persona files and ``build_review_prompt`` tell the reviewer that "a CLEAN
    payload requires an empty findings array", and nothing enforced it, so a
    payload that simply omitted the key cleared.  An omitted required key is a
    commoner model failure than a wrong-typed one, and treating the two
    differently is the inconsistency ``payload_findings_malformed`` was added
    to remove.
    """
    if not payload:
        return False
    if not isinstance(payload.get("findings"), list):
        return False
    if payload["findings"]:
        return False
    return normalize_verdict(payload.get("verdict")) in CLEAN_VERDICTS
