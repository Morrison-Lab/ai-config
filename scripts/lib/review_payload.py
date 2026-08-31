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
    try:
        # swallow_unclosed=True, matching check-pr-fully-clean.py's own call:
        # the default records only an unclosed fence's OPENER line and leaves
        # its interior live, which breaks this function in both directions --
        # a truncated review's quoted CLEAN template counts as a real verdict,
        # and a quoted NOT_CLEAN payload mints a finding no ARD round can
        # discharge (the ai-config#2482 class).
        fenced, _, orphans = find_fence_spans(body, swallow_unclosed=True)
        fenced_lines = set(fenced) | set(orphans)
    except Exception:
        fenced_lines = set()

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
        try:
            data = json.loads(m.group(1).strip())
        except Exception:
            continue
        if isinstance(data, dict) and "verdict" in data:
            found = data
    return found


def payload_findings(payload: Optional[Dict[str, Any]]) -> list:
    """The payload's ``findings`` list, or ``[]`` when absent or malformed."""
    if not payload:
        return []
    findings = payload.get("findings")
    return findings if isinstance(findings, list) else []


def payload_is_blocking(payload: Optional[Dict[str, Any]]) -> bool:
    """True when the payload blocks: a not-clean verdict OR any finding.

    Findings alone block regardless of the stated verdict, because a reviewer
    that enumerates findings and then labels itself clean is contradicting
    itself, and the safe reading of a contradiction is the blocking one.
    """
    if not payload:
        return False
    if payload_findings(payload):
        return True
    return normalize_verdict(payload.get("verdict")) in NOT_CLEAN_VERDICTS


def payload_is_clean(payload: Optional[Dict[str, Any]]) -> bool:
    """True when the payload affirmatively clears: clean verdict, no findings."""
    if not payload:
        return False
    if payload_findings(payload):
        return False
    return normalize_verdict(payload.get("verdict")) in CLEAN_VERDICTS
