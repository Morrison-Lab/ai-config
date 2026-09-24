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
  4. The body carries no `review-data:` machine payload -- a real review
     emits one, so a body with one is a review stating its own verdict and is
     none of this hook's business.
  5. The body carries ARD disposition vocabulary (Addressed / Rebutted /
     Deferred, "addressed in", "closed in", "answered below"). This is the
     discriminator that separates a disposition ANSWERING findings from a
     self-review STATING them -- `shared/workflow/self-review-fallback.md`
     requires the second to carry a real verdict, including a not-clean one,
     and warning on those is how a guard gets switched off.

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
_checker = _instrument()

classify_verdict = getattr(_checker, "classify_verdict", None)

RX_COMMENT_POST = getattr(_rebuttal, "RX_COMMENT_POST", None)
extract_body_text = getattr(_rebuttal, "extract_body_text", None)

MCP_POST_TOOLS = tuple(getattr(_disclosure, "MCP_POST_TOOLS", (
    "mcp__github__add_issue_comment",
    "mcp__github__add_reply_to_pull_request_comment",
))) + (
    "mcp__github__update_issue_comment",
    "mcp__github__add_comment_to_pending_review",
)

BASH_TOOL_NAMES = ("Bash", "bash", "run_command", "execute_command", "terminal", "shell")

# A real review emits this marker beside its verdict. Matched anywhere, because
# a body carrying one is a review whatever else it says.
RX_REVIEW_PAYLOAD = re.compile(r"review-data\s*:", re.I)

# ARD disposition vocabulary. The point is a body that ANSWERS findings.
RX_DISPOSITION = re.compile(
    r"(?:^|\n)\s{0,4}(?:[-*+]\s+|\d+[.)]\s+|\*\*)?\s*"
    r"(?:Addressed|Rebutted|Deferred)\b"
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


def echoed_verdict(body):
    """The matched disposition phrase when `body` should warn, else None."""
    if not body or classify_verdict is None:
        return None
    try:
        if classify_verdict(body) != "not-clean":
            return None
    except Exception:
        return None
    if RX_REVIEW_PAYLOAD.search(body):
        return None
    hit = RX_DISPOSITION.search(body)
    if not hit:
        return None
    return " ".join(hit.group(0).split())


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
