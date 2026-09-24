#!/usr/bin/env python3
"""Predicates for classifying harness-generated transcript metadata.

Claude Code injects several different kinds of harness-generated content as
a `type: "user"` transcript entry with `isMeta: true`: loaded skill bodies,
scheduled continuations, and harness/hook feedback. Morrison-Lab/ai-config#3860
identified that treating every `isMeta` entry as "not a real user turn" is too
broad: a SCHEDULED CHECK-IN CONTINUATION (from a `ScheduleWakeup`/cron fire,
delivered through a queue enqueue/dequeue pair) also arrives as `isMeta: true`,
and it IS a genuine new turn carrying real elapsed time -- collapsing it into
the skill-load carve-out silently expired a clock reading (or any other
turn-scoped state) across a real gap.

Conversely, Morrison-Lab/ai-config#3914 identified that harness-injected hook
feedback and system notifications (which also arrive as `type: "user"`) were
being read by issue-freshness guards as genuine user prose, retargeting guards
to incident examples cited inside hook messages.

THE THREE SHAPES
----------------
Verified against 1,072 real `isMeta: true` entries across 896 local transcripts
under `~/.claude/projects` (measured 2026-09-22):

  * `sourceToolUseID` present (108 entries): 103 begin
    "Base directory for this skill: ..."; the other 5 are a skill
    re-invocation notice ("(Re-invocation of /post-merge -- the skill
    instructions were previously loaded...") or a skill's own rendered body
    ("# Update Config Skill\n..."). All 108 are skill-load content
    (classified by `is_skill_load_meta`).
  * `sourceToolUseID` absent, `promptSource: "sdk"` (270 entries): a
    dispatched/scheduled task continuation ("Check CI/review status on
    Morrison-Lab/ai-config PR #2070...", "Quota-sprint orchestrator
    tick..."). A genuine new turn with real elapsed time.
  * `sourceToolUseID` absent, no `promptSource` (694 entries): harness
    "Stop hook feedback" and "[SYSTEM NOTIFICATION - NOT USER INPUT]"
    injections. Machine output, classified by `is_harness_meta` and
    `is_hook_feedback`.

No `(sourceToolUseID present, promptSource: "sdk")` combination occurred in
the sample, so the two are mutually exclusive in practice.
"""
from __future__ import annotations

import re

# Recognizable hook/harness output preambles injected into the transcript.
# Used to distinguish machine/hook feedback from user prose (ai-config#3914).
RX_HOOK_PREAMBLE = re.compile(
    r"""(?xi)
    ^\s*(?:
        # Stop hook feedback (Claude Code)
        Stop\ hook\ feedback:
        # PreToolUse / PostToolUse / UserPromptSubmit / Stop hook context
        | (?:[A-Za-z0-9_.:<>-]+\s+)?hook\s+additional\s+context:
        # [hook: <name>]
        | \[\s*hook:\s*[A-Za-z0-9_.-]+\s*\]
        # <name> hook <status>: (e.g. no-mistake-without-a-hook hook success:)
        | [A-Za-z0-9_.-]+\s+hook\s+(?:success|warning|warn|error|failed|failure|blocked|block|info|feedback):
        # Harness system notification
        | \[\s*SYSTEM\s+NOTIFICATION\b[^\]]*\]
    )
    """
)


def is_skill_load_meta(entry: dict) -> bool:
    """True when `entry` is a loaded skill's body, not a real user turn.

    A skill-load `isMeta` entry always carries `sourceToolUseID` (the
    `Skill` tool_use it was injected for); nothing else observed carrying
    `isMeta: true` does -- see the module docstring for the transcript
    survey this is derived from. A scheduled check-in continuation
    (`isMeta: true`, `sourceToolUseID` absent, often `promptSource: "sdk"`)
    is a genuine new turn and must NOT match this predicate.
    """
    if not isinstance(entry, dict):
        return False
    return bool(entry.get("isMeta")) and bool(entry.get("sourceToolUseID"))


def is_harness_meta(entry: dict) -> bool:
    """True when `entry` is harness-injected metadata (e.g. hook feedback, system notification),
    not a real user turn or scheduled continuation.

    In Claude Code transcripts, harness injections carry `isMeta: true`,
    no `sourceToolUseID` (unlike skill loads), and no `promptSource`
    (unlike scheduled continuations, which have `promptSource: "sdk"`).
    """
    if not isinstance(entry, dict):
        return False
    if not bool(entry.get("isMeta")):
        return False
    if bool(entry.get("sourceToolUseID")):
        return False
    if entry.get("promptSource") == "sdk":
        return False
    return True


def is_hook_feedback_text(text: str) -> bool:
    """True when `text` begins with a recognized hook or harness preamble."""
    if not isinstance(text, str):
        return False
    return bool(RX_HOOK_PREAMBLE.search(text))


def is_hook_feedback(entry: dict) -> bool:
    """True when `entry` is hook feedback or harness notification, either via
    isMeta structure (is_harness_meta) or recognized hook preamble in its text content."""
    if not isinstance(entry, dict):
        return False
    if is_harness_meta(entry):
        return True
    msg = entry.get("message")
    content = msg.get("content") if isinstance(msg, dict) else entry.get("content")
    if isinstance(content, str):
        if is_hook_feedback_text(content):
            return True
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                if is_hook_feedback_text(block.get("text", "")):
                    return True
            elif isinstance(block, str):
                if is_hook_feedback_text(block):
                    return True
    return False

