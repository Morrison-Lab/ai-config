#!/usr/bin/env python3
"""PreToolUse warning: a disposition comment that echoes the verdict it answers.

THE MISTAKE (Morrison-Lab/mln#49, measured 2026-09-24)
-------------------------------------------------------
An agent answered a review round by opening its reply with the reviewer's own
call, reproduced verbatim at line start so the reply could then take the
findings one by one. The comment was a DISPOSITION -- it said what had been
Addressed, Rebutted and Deferred, and named the commit that closed each item.
It stated no verdict of its own.

A line-anchored verdict scanner cannot tell those apart. `classify_verdict()`
in `scripts/check-pr-fully-clean.py` read the echoed line as this author's own
authored verdict, so the author acquired a standing not-clean verdict on a PR
whose reviewer had since returned a clean one. Per ai-config#2274 a later
all-clear from a DIFFERENT reviewer does not supersede a standing not-clean
from another author, so the PR scored not fully clean on a head where every
check was green (14 check runs, 13 success and 1 skipped) and the live review
verdict was clean. Nothing about the PR was wrong; the blocker was the shape of
the reply.

WHY THIS NEEDS A GUARD RATHER THAN CARE
-----------------------------------------
The failure is silent and runs in the blocking direction, which is the
combination a prose rule cannot reach. Nothing turns red, no check reports it,
and the comment reads as scrupulous: quoting the call you are answering is
exactly what good practice looks like from the inside. It is discovered only by
running the fully-clean instrument and reading WHY it refused -- and a session
that has just posted a careful disposition has no reason to suspect its own
comment is the cause.

Two adjacent remedies were measured on the incident and BOTH FAIL, which is why
the guidance in the message is what it is rather than the obvious advice:

  - Blockquoting the echoed line does not help. `classify_verdict` reads a
    blockquoted line exactly as it reads a bare one.
  - A backtick code span does not help either, at one backtick or at two, once
    the span runs across a line break: the per-line citation scan cannot close
    it, so the phrase stays visible to the scan.

The rendering that works is not to reproduce the phrase -- describe the call and
link the review instead. That is the same remedy
`shared/writing/examples-are-scanned.md` gives for a document that trips the
rule it is describing, and the second-order case bit here too: the comment
EXPLAINING the mechanism re-tripped it by quoting the phrase.

WHY IT REUSES check-pr-fully-clean.py's OWN CLASSIFIER
--------------------------------------------------------
`no-handrolled-verdict-parse.py`'s docstring is the standing cautionary tale
for hand-rolling a second verdict detector: a bare phrase search misreads in
both directions. So this hook does not invent one. It imports
`scripts/check-pr-fully-clean.py` by path and calls its own
`classify_verdict()` -- the exact function whose reading caused the incident,
so the guard and the instrument cannot disagree about what a verdict is.
`flag-clean-claim-over-findings.py` imports the same function for the Stop
surface; this is the PreToolUse surface, over a body about to be posted.

FIRE CONDITION (all of)
-------------------------
  1. The call posts or edits a forge comment (Bash `gh pr comment`,
     `gh issue comment`, `gh api .../comments`, or an MCP comment tool).
  2. The body is readable.
  3. `classify_verdict(body)` returns "not-clean".
  4. The body carries no `review-data:` machine payload OF ITS OWN -- a real
     review emits one, so a body with one is a review stating its own verdict
     and is none of this hook's business. Tested against the body with fenced
     and blockquoted lines blanked, because a disposition may quote the
     reviewer's payload back to say what the review concluded, and a quoted
     one is not this author's verdict.
  5. The body carries ARD disposition vocabulary (Addressed / Rebutted /
     Deferred, "addressed in", "closed in", "answered below"). This is the
     discriminator that separates a disposition ANSWERING findings from a
     self-review STATING them -- `shared/workflow/self-review-fallback.md`
     requires the second to carry a real verdict, including a not-clean one,
     and warning on those is how a guard gets switched off.
  6. That vocabulary is not NEGATED or hedged within its own clause. "None of
     the findings are addressed yet" is the honest sentence a self-review
     writes when it has found work and not done it, and an earlier draft
     warned on it -- which is condition 5's own failure reached from the
     other side. The disqualifiers are the ones `classify_verdict()` applies
     to its own bare patterns, reused rather than re-derived, and the window
     errs toward disqualifying: a missed warning costs one unguarded
     comment, a false one teaches the author to ignore the hook.

It WARNS and never blocks. Whether an echo is the author's own call is a
judgment the lexical condition only approximates, and refusing to post a
disposition would be far worse than posting one that scores oddly.

Fails open on every unexpected shape, per the file-wide contract.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(HERE)


def _sibling(name, key):
    """Import a hyphenated sibling module, or None if unavailable."""
    path = os.path.join(HERE, name)
    try:
        spec = importlib.util.spec_from_file_location(key, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def _instrument():
    """`scripts/check-pr-fully-clean.py` as a module, or None."""
    path = os.path.join(ROOT, "scripts", "check-pr-fully-clean.py")
    try:
        spec = importlib.util.spec_from_file_location(
            "_sib_verdict_echo_instrument", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


_rebuttal = _sibling("flag-uncited-rebuttal.py", "_sib_verdict_echo_rebuttal")
_disclosure = _sibling("require-agent-disclosure.py", "_sib_verdict_echo_disclosure")
_clean_claim = _sibling("flag-clean-claim-over-findings.py",
                        "_sib_verdict_echo_clean_claim")
_checker = _instrument()

classify_verdict = getattr(_checker, "classify_verdict", None)

RX_COMMENT_POST = getattr(_rebuttal, "RX_COMMENT_POST", None)
extract_body_text = getattr(_rebuttal, "extract_body_text", None)

_INHERITED_POST_TOOLS = tuple(getattr(_disclosure, "MCP_POST_TOOLS", (
    "mcp__github__add_issue_comment",
    "mcp__github__add_reply_to_pull_request_comment",
)))
# EDITING a comment is this hook's case as much as posting one: the incident's
# first two attempted fixes were edits. The sibling's tuple already carries
# some of these, so the union is deduplicated in order rather than concatenated
# -- an adversarial review found `add_comment_to_pending_review` listed twice.
MCP_POST_TOOLS = tuple(dict.fromkeys(_INHERITED_POST_TOOLS + (
    "mcp__github__update_issue_comment",
    "mcp__github__add_comment_to_pending_review",
)))

BASH_TOOL_NAMES = ("Bash", "bash", "run_command", "execute_command", "terminal", "shell")

# A real review emits this marker beside its verdict, so a body carrying its
# OWN one is a review rather than a disposition. It is matched against the
# authored view only: a disposition may quote the reviewer's payload back to
# explain what was said, and an adversarial review found that a quoted payload
# exempted the comment from this warning while `classify_verdict()` still read
# that same embedded payload as the comment's own verdict -- the incident's own
# shape, reached through a quoted payload instead of quoted prose.
RX_REVIEW_PAYLOAD = re.compile(r"review-data\s*:", re.I)

RX_FENCE = re.compile(r"^\s{0,3}(?P<d>`{3,}|~{3,})\s*(?P<info>.*)$")


def authored_text(body):
    """`body` with fenced-code and blockquote lines blanked.

    Line-oriented and deliberately simple, mirroring the same fence rule
    `check-review-execution.sh` uses for its own authored-heading scan: a
    fence closes only on a run of the SAME character, at least as long as
    the opener, with nothing but whitespace after it. Blanking rather than
    deleting keeps every line number and every sentence boundary, so a
    scan over the result cannot join two lines that were never adjacent.
    """
    out = []
    fence = None
    for line in (body or "").split("\n"):
        m = RX_FENCE.match(line)
        if fence is None:
            if m:
                fence = m.group("d")
                out.append("")
                continue
        else:
            if (m and m.group("d")[0] == fence[0]
                    and len(m.group("d")) >= len(fence)
                    and not m.group("info").strip()):
                fence = None
            out.append("")
            continue
        out.append("" if line.lstrip().startswith(">") else line)
    return "\n".join(out)

# ARD disposition vocabulary. The point is a body that ANSWERS findings.
# The ARD bullet label is the commonest form by far and the easiest to miss:
# a disposition writes `**1. Addressed.**` or `**1--2. Rebutted.**`, so the
# numeric label sits INSIDE the bold run, between it and the verb. An earlier
# draft allowed the bold run but not the label, and a review fixture using only
# that form was silently unmatched -- which made a negative case pass for the
# wrong reason.
_ARD_LABEL = r"(?:\d+(?:\s*(?:--|-|to)\s*\d+)?\s*[.):]\s*)?"
RX_DISPOSITION = re.compile(
    r"(?:^|\n)\s{0,4}(?:[-*+]\s+|\d+[.)]\s+|\*{1,2}|_{1,2})?\s*" + _ARD_LABEL +
    # NOT `\b`: an adversarial review found the underscore branch above dead,
    # because `_` is a word character, so `_Addressed_` has no boundary after
    # the final `d`. A non-alphanumeric lookahead admits the closing emphasis
    # while still refusing `Addressedly`.
    r"(?:Addressed|Rebutted|Deferred)(?=[^A-Za-z0-9]|$)"
    r"|\b(?:are|all|each|both|every one|five|four|three|two)\s+"
    r"(?:\w+\s+){0,3}addressed\b"
    r"|\baddressed\s+in\b|\bclosed\s+in\b|\banswered\s+(?:below|point by point)\b",
    re.I,
)

NOTE = (
    "[flag-self-authored-verdict-echo] This {surface} classifies as a NOT-CLEAN "
    "verdict by `scripts/check-pr-fully-clean.py`'s own `classify_verdict()`, "
    "while reading as a disposition that ANSWERS findings rather than a review "
    "stating them (matched: {vocab}).\n\n"
    "If the not-clean phrasing is the reviewer's call quoted back, posting it "
    "gives THIS author a standing not-clean verdict on the PR. Per "
    "ai-config#2274 a later clean verdict from a different reviewer does not "
    "supersede it, so the PR scores not fully clean however green it is, and "
    "nothing reports why.\n\n"
    "Two obvious fixes were measured on Morrison-Lab/mln#49 and BOTH FAIL: "
    "blockquoting the line (`classify_verdict` reads a blockquoted line exactly "
    "as a bare one) and wrapping it in a backtick code span (of one backtick or "
    "two -- once the span crosses a line break the per-line citation scan cannot "
    "close it). Describe the call and link the review instead of reproducing the "
    "phrase.\n\n"
    "If this body IS your own verdict -- a self-review per "
    "`shared/workflow/self-review-fallback.md` -- post it as written; this "
    "warning does not apply."
)


def _split_segments(text):
    """Split a command into shell segments, preferring the sibling's splitter.

    Never a bare `re.split` on newlines: a `--body "..."` literal routinely
    spans lines, so splitting on `\n` cuts the body in half and the posting
    segment stops matching. Measured while writing this hook.
    """
    splitter = getattr(_disclosure, "split_segments", None)
    if callable(splitter):
        try:
            return list(splitter(text))
        except Exception:
            pass
    return [seg for seg in re.split(r"(?<![\\])[;&|]+", text) if seg.strip()]


def _bash_body(command, cwd):
    """(kind, body) for a Bash command that posts a comment, else (None, None)."""
    if RX_COMMENT_POST is None or extract_body_text is None:
        return None, None
    stripped = command
    strip_hd = getattr(_rebuttal, "strip_heredocs", None)
    if callable(strip_hd):
        try:
            stripped = strip_hd(command)
        except Exception:
            stripped = command
    for segment in _split_segments(stripped):
        if not segment.strip() or not RX_COMMENT_POST.search(segment):
            continue
        body = extract_body_text(segment, cwd)
        if body is None:
            body = extract_body_text(command, cwd)
        if body is None:
            return "unreadable", None
        return "body", body
    if RX_COMMENT_POST.search(stripped):
        body = extract_body_text(command, cwd)
        if body is not None:
            return "body", body
        return "unreadable", None
    return None, None


def _post_from_payload(tool_name, tool_input, cwd):
    """(kind, body, surface) for the action this tool call would perform."""
    if tool_name in BASH_TOOL_NAMES:
        command = (tool_input.get("command") or tool_input.get("CommandLine")
                   or tool_input.get("cmd") or tool_input.get("script"))
        if not isinstance(command, str) or not command.strip():
            return None, None, None
        kind, body = _bash_body(command, cwd)
        return kind, body, "comment body"
    if tool_name in MCP_POST_TOOLS:
        body = tool_input.get("body")
        if isinstance(body, str) and body.strip():
            return "body", body, "comment body"
    return None, None, None


# A negated or hedged disposition phrase means the OPPOSITE of answering a
# finding, so it must not fire. An adversarial review reproduced the gap end to
# end: "None of the findings are addressed yet" is an ordinary honest
# self-review, and this hook warned on it -- contradicting its own fire
# condition 5, and warning on a self-review is exactly how a guard gets
# switched off. `flag-clean-claim-over-findings.py` already carries the
# disqualifiers `classify_verdict()` applies to its own bare patterns, so they
# are reused rather than re-derived; the negator set is widened with the
# determiner forms ("none of the findings", "neither") that a disposition scan
# meets and a clean-claim scan does not.
_FALLBACK_PREFIX_DISQUALIFY = re.compile(
    r"(?i)\b(?:should|would|could|might|may|claims?|says?|said|saying|"
    r"seems?|apparently|maybe|perhaps|if|unless|hypothetically)\b"
)
PREFIX_DISQUALIFY_RX = (getattr(_clean_claim, "PREFIX_DISQUALIFY_RX", None)
                        or _FALLBACK_PREFIX_DISQUALIFY)
NEGATION_RX = re.compile(
    r"(?i)(?:\bnot\b|\bnever\b|\bno\b|\bnone\b|\bneither\b|\bnor\b|"
    r"\bnothing\b|\bwithout\b|\bun(?:addressed|resolved)\b|n't\b|"
    r"\byet\s+to\b|\bfail(?:s|ed)?\s+to\b)"
)

# The clause the phrase sits in, bounded by a sentence end or a PARAGRAPH
# break. Deliberately not a bare `\n`: this corpus writes semantic line
# breaks, so a negator and the phrase it governs routinely sit on adjacent
# lines of one sentence ("... was never\naddressed in the fix"), and a
# newline boundary cut the negator off -- reproduced against the suite's
# own `NEGATED_PHRASES` fixture. A blank line is a real block boundary and
# still bounds the window.
RX_CLAUSE_START = re.compile(r"[.!?]|\n\s*\n")


def _disqualified(prose, match_start):
    """True when a negator or hedge governs the phrase at `match_start`.

    The window is the phrase's own CLAUSE -- back to the nearest sentence
    end or line break -- so a negation in a previous sentence does not
    reach it. Where that window is ambiguous this errs toward
    disqualifying, which is the cheap direction here: a missed warning
    costs one un-guarded comment, while a false warning lands on a genuine
    self-review and teaches the author to ignore the hook.
    """
    starts = [m.end() for m in RX_CLAUSE_START.finditer(prose, 0, match_start)]
    window = prose[(starts[-1] if starts else 0):match_start]
    return bool(NEGATION_RX.search(window) or PREFIX_DISQUALIFY_RX.search(window))


def echoed_verdict(body):
    """The matched disposition phrase when `body` should warn, else None."""
    if not body or classify_verdict is None:
        return None
    try:
        if classify_verdict(body) != "not-clean":
            return None
    except Exception:
        return None
    prose = authored_text(body)
    if RX_REVIEW_PAYLOAD.search(prose):
        return None
    for hit in RX_DISPOSITION.finditer(prose):
        # The bullet branch starts at the preceding newline, so the clause
        # window would otherwise be the LINE ABOVE the bullet. Anchor on the
        # phrase's own first word instead.
        word = re.search(r"[A-Za-z0-9]", hit.group(0))
        start = hit.start() + (word.start() if word else 0)
        if _disqualified(prose, start):
            continue
        return " ".join(hit.group(0).split())
    return None


def _read_payload():
    """(payload, is_dry_run), accepting `--dry-run <command>` for tests."""
    argv = sys.argv[1:]
    is_dry_run = False
    if argv and argv[0] == "--dry-run":
        is_dry_run = True
        argv = argv[1:]
        if argv:
            return {"tool_name": "Bash", "tool_input": {"command": argv[0]}}, True
    try:
        payload = json.load(sys.stdin)
        return (payload if isinstance(payload, dict) else {}), is_dry_run
    except Exception:
        return {}, is_dry_run


def main() -> int:
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    cwd = payload.get("cwd") or os.getcwd()
    tpath = payload.get("transcript_path") or ""

    try:
        kind, body, surface = _post_from_payload(
            payload.get("tool_name"), tool_input, cwd)
        vocab = echoed_verdict(body) if kind == "body" else None
        if not vocab:
            if is_dry_run:
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
            return 0

        if not is_dry_run:
            key = hashlib.sha256(
                (tpath + "|" + (body or "")).encode()).hexdigest()[:16]
            sentinel = os.path.join(
                tempfile.gettempdir(), f".claude-verdict-echo-{key}")
            if os.path.exists(sentinel):
                return 0
            try:
                open(sentinel, "w").close()
            except Exception:
                pass

        context = NOTE.format(surface=surface or "comment body", vocab=vocab)
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": context,
            },
        }
        if not os.environ.get("ANTIGRAVITY_AGENT"):
            out["systemMessage"] = (
                "Verdict-echo reminder: this comment classifies as a NOT-CLEAN "
                "verdict from you while reading as a disposition. If that "
                "phrasing is the reviewer's call quoted back, describe it "
                "instead -- blockquoting and code spans do not exempt it."
            )
        print(json.dumps(out))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
