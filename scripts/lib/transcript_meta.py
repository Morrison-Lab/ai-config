#!/usr/bin/env python3
"""Predicate: is this transcript entry a loaded skill's body?

Claude Code injects several different kinds of harness-generated content as
a `type: "user"` transcript entry with `isMeta: true` -- and only ONE of
them is a loaded skill's body. Morrison-Lab/ai-config#3860's first fix
treated every `isMeta` entry as "not a real user turn", which is too broad:
a coordinator review of that fix found a SCHEDULED CHECK-IN CONTINUATION
(from a `ScheduleWakeup`/cron fire, delivered through a queue
enqueue/dequeue pair) also arrives as `isMeta: true`, and it IS a genuine
new turn carrying real elapsed time -- collapsing it into the skill-load
carve-out silently expired a clock reading (or any other turn-scoped state)
across a real gap, reintroducing the exact class of bug the guard exists to
catch.

THE DISCRIMINATOR
------------------
`sourceToolUseID` is present on a skill-load entry and absent on every
other observed `isMeta` shape. Verified against 1,072 real `isMeta: true`
entries across 896 local transcripts under `~/.claude/projects` (measured
2026-09-22):

  * `sourceToolUseID` present (108 entries): 103 begin
    "Base directory for this skill: ..."; the other 5 are a skill
    re-invocation notice ("(Re-invocation of /post-merge -- the skill
    instructions were previously loaded...") or a skill's own rendered body
    ("# Update Config Skill\n..."). All 108 are skill-load content.
  * `sourceToolUseID` absent, `promptSource: "sdk"` (270 entries): a
    dispatched/scheduled task continuation ("Check CI/review status on
    Morrison-Lab/ai-config PR #2070...", "Quota-sprint orchestrator
    tick..."). A genuine new turn with real elapsed time -- this is the
    scheduled-continuation shape the coordinator's review named.
  * `sourceToolUseID` absent, no `promptSource` (694 entries): harness
    "Stop hook feedback" and "[SYSTEM NOTIFICATION - NOT USER INPUT]"
    injections. Not a skill load either, and out of scope for this
    predicate -- narrowing the #3860 carve-out to the skill-load shape
    specifically is the whole point of this module, not broadening it to
    cover every harness-injected shape.

No `(sourceToolUseID present, promptSource: "sdk")` combination occurred in
the sample, so the two are mutually exclusive in practice.
"""
from __future__ import annotations


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
