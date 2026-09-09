#!/usr/bin/env python3
"""Stop-hook guard: warn on a reply reporting a known gap as still unfiled.

`hooks/no-unfiled-finding.py` already blocks the FORWARD assertion that a
finding is worth an issue ("worth its own issue", "needs a tracking issue")
when nothing was filed. This hook covers a different shape: a RETROSPECTIVE
status report about a gap the session has already recognized -- "is still
unfiled", "hasn't been filed" -- said again, in a later reply, with the same
result. The sibling's ASSERT list is keyed on filing-intent vocabulary and
does not match this phrasing at all, so a message built entirely from this
hook's trigger phrases sails straight past it.

THE MEASURED INCIDENT
----------------------
Across roughly six consecutive replies in one session, the closing
stopping-point line stated that a known defect (a set of stale
equation-number comments in a C source file) was "still unfiled". The rule
requiring it to be filed already existed and was loaded --
shared/workflow/report-mistakes-proactively.md says to file a tracking issue
immediately, and CLAUDE.md's "Status requests do not make issues
report-only" says "File it before reporting it." The issue was filed only
after the user asked for it directly, as UCD-SERG/serocalculator#694.

So the gap is not that a rule is missing -- it is that the rule had no
mechanism for THIS phrasing, and that repeatedly reporting the debt felt
like tracking it. Disclosing an unfiled item in a status line reads as
diligence while doing the opposite: it puts the omission on the record and
does nothing about it, and each repetition makes it feel more handled than
the last.

WHY THIS IS A SEPARATE HOOK RATHER THAN A WIDENING OF THE SIBLING
-------------------------------------------------------------------
Two differences, not one. The trigger vocabulary differs (a status report
about a KNOWN gap, not a fresh claim that something is worth tracking), and
the severity differs (warn, not block -- see below). Widening the sibling's
ASSERT list to also catch "is still unfiled" would conflate a hook whose
false-positive cost is a blocked turn with one whose false-positive cost is
an extra line of context, and the phrase set here is looser (a bare
"untracked" reading in particular) in a way that earns a softer response.

Two of this hook's own phrases -- "needs an issue" and "should be filed" --
ALSO match the sibling's ASSERT list, so a message carrying one of them fires
BOTH hooks: the sibling blocks it outright, and this one's warning lands as
redundant context on that path. Kept anyway, on purpose: this hook also
fires on a message whose text differs from anything the sibling's own
per-message sentinel has seen (the two hooks keep separate sentinel
namespaces), and dropping the overlapping phrases would leave this hook
silent on wording the incident used almost verbatim.

WHY THIS WARNS RATHER THAN BLOCKS
-----------------------------------
Whether an item SHOULD have been filed is not lexically decidable from the
phrase alone. The reply may be narrating an item that is already filed and
merely restating its status ("still unfiled" describing last week, before
today's fix), or an item that belongs to a repo this session cannot file
into (see shared/workflow/upstream-issues.md's own-repo fallback), or a risk
with no defect behind it at all. Blocking a truthful status report would be
worse than the report itself, so this hook can only surface the phrase and
make the author answer the filing question -- deciding it for them would
refuse a legitimate "this is out of scope; it is not mine to file" answer.
This matches the warn-not-block precedent already set by
`no-unmeasured-clock-claim.py` and `flag-cop-out-offer.py`.

REUSE RATHER THAN RE-IMPLEMENTATION
--------------------------------------
`visible_prose` (fence/blockquote/inline-code stripping), `scan` (last
assistant text, last filing tool call, in transcript order), and
`RX_ALREADY` (a citation of an issue that already exists) are imported from
the sibling module rather than copied. All three are purely STRUCTURAL --
none of them reads the sibling's own ASSERT phrase list -- so importing them
keeps one scanner rather than two, per
shared/workflow/check-purpose-before-reusing.md: the purpose here is
identical (find the reply's own final text, and tell "already filed" from
"not filed"), and only the trigger phrases and the severity differ. Degrades
to silence if the sibling is missing or fails to import, matching
`no-empty-promise.py`'s own fallback for the same reason.

THE SELF-IMPLICATING-EXAMPLE PROBLEM
---------------------------------------
Per shared/writing/examples-are-scanned.md, a corpus entry documenting this
hook's own trigger vocabulary can trip it -- a case record quoting "is still
unfiled" as an example is, in form, the exact sentence this hook matches.
`visible_prose` suppresses the obvious case (a fenced code block or an
inline code span), which is what lets that vocabulary be quoted safely in
backticks. This mitigation is PARTIAL BY DESIGN: a sentence that discusses
the phrase in plain prose, with no backticks, still matches, and that is
acceptable for a warning in a way it would not be for a block.

Fails OPEN on any parse trouble or missing sibling, and fires at most once
per distinct message.
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


_unfiled = _sibling("no-unfiled-finding.py")

visible_prose = getattr(_unfiled, "visible_prose", None)
scan = getattr(_unfiled, "scan", None)
RX_ALREADY = getattr(_unfiled, "RX_ALREADY", None)

# `hasn't` spelled with an ASCII escape rather than a literal curly
# apostrophe, per shared/coding/ascii-punctuation-in-source.md; the plain
# `'` alternative tolerates a model that drops the apostrophe outright.
_APOS = "['’]"

# A RETROSPECTIVE status report about a gap the session already knows about,
# not a fresh claim that something is worth tracking. Deliberately bound to
# a copula (is/was/are/were/remains/stays/sits) for "unfiled" and
# "untracked" rather than matching the bare adjective, because this corpus
# discusses "an untracked local change" and "an untracked deferral" as
# ordinary noun-phrase prose constantly -- a bare `\buntracked\b` would fire
# on nearly every status recap this repo's own rule files describe.
ASSERT = [
    r"\b(?:is|was|are|were|remains?|stays?|sits?)\s+(?:still\s+)?unfiled\b",
    r"\bstill\s+unfiled\b",
    r"\bnot\s+yet\s+filed\b",
    r"\bhasn" + _APOS + r"?t\s+(?:yet\s+)?been\s+filed\b",
    r"\bhas\s+not\s+(?:yet\s+)?been\s+filed\b",
    r"\bneeds?\s+an\s+issue\b",
    r"\bshould\s+be\s+filed\b",
    r"\b(?:is|was|are|were|remains?|stays?|sits?)\s+(?:still\s+)?untracked\b",
    r"\bstill\s+needs\s+a\s+tracking\s+issue\b",
    r"\bi\s+owe\b[^.!?\n]{0,60}\ban\s+issue\b",
]
RX_ASSERT = re.compile("|".join(ASSERT), re.I)

# The sibling's own RX_ALREADY recognizes `#123`-shaped citations; it has
# no URL form, so a reply citing a plain issue URL (no `#N`, no
# surrounding parens) would otherwise still fire. Added here rather than
# widening the sibling, since the sibling's own callers never needed it.
RX_ALREADY_URL = re.compile(r"https?://\S*/issues/\d+", re.I)


def main() -> int:
    if visible_prose is None or scan is None or RX_ALREADY is None:
        return 0  # sibling unavailable; degrade to silence

    try:
        payload = json.load(sys.stdin)
        last_file, last_say, text = scan(payload.get("transcript_path") or "")
    except Exception:
        return 0  # fail open

    if not text:
        return 0
    hit = RX_ASSERT.search(visible_prose(text))
    if not hit:
        return 0
    # The message already cites the issue, so the gap is recorded, not
    # merely reported. Checked against the RAW text (not the fence-stripped
    # prose), the same way the sibling checks its own RX_ALREADY, since a
    # citation is evidence regardless of where in the message it sits.
    if RX_ALREADY.search(text) or RX_ALREADY_URL.search(text):
        return 0
    # A filing call landed at or after the last spoken text -- e.g. the
    # assertion is the only prose in the turn and a `gh issue create` (or
    # `mcp__github__issue_write`) follows it with no closing narration.
    if last_file > last_say:
        return 0

    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(),
                             f".claude-unfiled-warn-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    phrase = hit.group(0).strip()

    # `systemMessage`, not `reason` -- a `Stop` hook's `reason` is read only
    # alongside `"decision": "block"`, so a warn-only hook printing `reason`
    # alone reaches nobody. Every warn-only hook in this repo emits
    # `systemMessage` for exactly that reason; see
    # `no-unmeasured-clock-claim.py` and `flag-cop-out-offer.py`.
    print(json.dumps({"systemMessage": (
        f"Your reply reports a known gap as \"{phrase}\" and no issue-create "
        "or issue-comment call follows it in this transcript. Reporting the "
        "gap is not tracking it, however many times it gets said -- file it "
        "now (dupe-check with `gh issue list --state all --search`, then "
        "`gh issue create` / `mcp__github__issue_write`, labelled "
        "ai-authored and model:<id> per "
        "shared/workflow/label-agent-filed-issues.md), or comment the new "
        "evidence onto the issue that already covers it. If it is genuinely "
        "not yours to file -- out of scope for this repo -- say so instead "
        "of restating that it is unfiled."
    )}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
