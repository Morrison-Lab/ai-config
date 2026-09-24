#!/usr/bin/env python3
"""Tests for scripts/lib/transcript_meta.py (ai-config#3860).

Three real transcript-entry shapes, all carrying `isMeta: true`, pinned from
a survey of 1,072 such entries across 896 local transcripts under
`~/.claude/projects` (measured 2026-09-22) -- see the module docstring for
the full derivation. Only the first is a loaded skill's body, and only that
one should match `is_skill_load_meta()`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from transcript_meta import (  # noqa: E402
    is_harness_meta,
    is_hook_feedback,
    is_hook_feedback_text,
    is_skill_load_meta,
)

passed = 0
failed = 0


def check(name: str, condition: bool) -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"PASS: {name}")
    else:
        failed += 1
        print(f"FAIL: {name}")


# Shape 1: a loaded skill's body. `sourceToolUseID` present. 108/1072 in the
# survey, 103 of them literally starting "Base directory for this skill: ".
SKILL_LOAD = {
    "parentUuid": "91267062-db58-41c6-bc7a-a83593f2a168",
    "isSidechain": False,
    "promptId": "bd82d96d-6082-4f07-971c-b8b110e601b1",
    "type": "user",
    "isMeta": True,
    "turnCompanion": True,
    "sourceToolUseID": "toolu_01FNVQSkNkJssA9EBMZSu5Xr",
    "message": {
        "role": "user",
        "content": [{
            "type": "text",
            "text": "Base directory for this skill: C:\\Users\\dougm\\"
                    ".claude\\skills\\register-oaicopilot-models\n\n"
                    "# register-oaicopilot-models: add new models ...",
        }],
    },
}

# A skill re-invocation notice is the same family: `sourceToolUseID` present,
# text does not start with "Base directory for this skill:".
SKILL_REINVOCATION = {
    "type": "user",
    "isMeta": True,
    "sourceToolUseID": "toolu_02abc",
    "message": {
        "role": "user",
        "content": [{
            "type": "text",
            "text": "(Re-invocation of /post-merge -- the skill "
                    "instructions were previously loaded; the assistant "
                    "should proceed.)",
        }],
    },
}

# Shape 2: a scheduled check-in continuation (ScheduleWakeup/cron fire, via
# a queue enqueue/dequeue pair). NO `sourceToolUseID`. 270/1072 in the
# survey, `promptSource: "sdk"`. A genuine new turn with real elapsed time.
SCHEDULED_CONTINUATION = {
    "parentUuid": "19eae7c6-9701-40fa-a718-15bf531ea464",
    "isSidechain": False,
    "promptId": "8047b2ec-d7f8-42da-94e6-3924cc9e57be",
    "type": "user",
    "isMeta": True,
    "permissionMode": "auto",
    "promptSource": "sdk",
    "message": {
        "role": "user",
        "content": "Check CI/review status on Morrison-Lab/ai-config PRs "
                    "#2070 (head 7ecc61d7) and #2079 (head f17f9d01).",
    },
}

# Shape 3: harness "Stop hook feedback" / system-notification injections. NO
# `sourceToolUseID`, no `promptSource`. 694/1072 in the survey -- the
# majority shape. Out of scope for this predicate (see module docstring):
# narrowing the #3860 carve-out to the skill-load shape is the point, not
# broadening it to cover every harness-injected shape.
HOOK_FEEDBACK = {
    "type": "user",
    "isMeta": True,
    "message": {
        "role": "user",
        "content": "Stop hook feedback:\n[hook: no-mistake-without-a-hook] "
                    "You admitted a mistake earlier in this session.",
    },
}

check("skill-load body matches (has sourceToolUseID)",
      is_skill_load_meta(SKILL_LOAD))
check("skill re-invocation notice matches (has sourceToolUseID)",
      is_skill_load_meta(SKILL_REINVOCATION))
check("scheduled continuation does NOT match (no sourceToolUseID)",
      not is_skill_load_meta(SCHEDULED_CONTINUATION))
check("hook feedback does NOT match (no sourceToolUseID)",
      not is_skill_load_meta(HOOK_FEEDBACK))

# A real user message (no isMeta at all) never matches, whatever else it
# carries -- isMeta is a necessary condition, not just sourceToolUseID.
REAL_USER_WITH_SOURCE_FIELD = {
    "type": "user",
    "sourceToolUseID": "toolu_should_not_matter",
    "message": {"role": "user", "content": [{"type": "text", "text": "hi"}]},
}
check("a non-isMeta entry never matches, even if it happens to carry "
      "sourceToolUseID",
      not is_skill_load_meta(REAL_USER_WITH_SOURCE_FIELD))

# isMeta: false explicitly must not match either.
check("isMeta: false does not match",
      not is_skill_load_meta({"type": "user", "isMeta": False,
                               "sourceToolUseID": "toolu_x"}))

# Non-dict input fails open (silent), not a crash.
check("non-dict input returns False rather than raising",
      is_skill_load_meta(None) is False)
check("a list input returns False rather than raising",
      is_skill_load_meta([1, 2, 3]) is False)

# ---------------------------------------------------------------------------
# is_harness_meta (ai-config#3914)
# ---------------------------------------------------------------------------
check("hook feedback is recognized as harness meta (isMeta, no sourceToolUseID, no promptSource)",
      is_harness_meta(HOOK_FEEDBACK))
check("scheduled continuation is NOT harness meta (promptSource: 'sdk')",
      not is_harness_meta(SCHEDULED_CONTINUATION))
check("skill load is NOT harness meta (has sourceToolUseID)",
      not is_harness_meta(SKILL_LOAD))
check("real user turn is NOT harness meta (no isMeta)",
      not is_harness_meta(REAL_USER_WITH_SOURCE_FIELD))
check("non-dict input to is_harness_meta returns False",
      is_harness_meta(None) is False)

# ---------------------------------------------------------------------------
# is_hook_feedback_text (ai-config#3914)
# ---------------------------------------------------------------------------
check("Stop hook feedback preamble matches",
      is_hook_feedback_text("Stop hook feedback:\nMeasured 2026-08-19 on ucdavis/bcs#651 at a5f4f3f2..."))
check("Stop hook feedback with hook bracket matches",
      is_hook_feedback_text("Stop hook feedback:\n[hook: no-incomplete-check-enumeration] Measured 2026-08-19..."))
check("PreToolUse hook additional context matches",
      is_hook_feedback_text("PreToolUse:Write hook additional context:\nSome details"))
check("PreToolUse with brackets matches",
      is_hook_feedback_text("PreToolUse:<Write> hook additional context:\nSome details"))
check("UserPromptSubmit hook additional context matches",
      is_hook_feedback_text("UserPromptSubmit hook additional context:\nContext here"))
check("Stand-alone [hook: <name>] matches",
      is_hook_feedback_text("[hook: no-mistake-without-a-hook] You admitted a mistake earlier in this session."))
check("<name> hook status matches",
      is_hook_feedback_text("warn-stale-issue-edit hook warning: check is missing"))
check("<name> hook success matches",
      is_hook_feedback_text("no-mistake-without-a-hook hook success:\nClean"))
check("[SYSTEM NOTIFICATION - NOT USER INPUT] matches",
      is_hook_feedback_text("[SYSTEM NOTIFICATION - NOT USER INPUT] Command timed out"))
check("[SYSTEM NOTIFICATION] matches",
      is_hook_feedback_text("[SYSTEM NOTIFICATION] Something occurred"))
check("Ordinary user text does not match hook preamble",
      not is_hook_feedback_text("Implement https://github.com/Morrison-Lab/ai-config/issues/2282."))
check("User prompt referencing hook in the middle does not match",
      not is_hook_feedback_text("Regarding the Stop hook feedback, please fix #123."))
check("Non-string input to is_hook_feedback_text returns False",
      is_hook_feedback_text(None) is False)

# ---------------------------------------------------------------------------
# is_hook_feedback (entry-level, ai-config#3914)
# ---------------------------------------------------------------------------
check("HOOK_FEEDBACK entry matches is_hook_feedback via is_harness_meta",
      is_hook_feedback(HOOK_FEEDBACK))
SYNTHETIC_HOOK_ENTRY = {
    "type": "user",
    "message": {"role": "user", "content": [
        {"type": "text", "text": "Stop hook feedback:\nMeasured 2026-08-19 on ucdavis/bcs#651..."}
    ]},
}
check("Synthetic hook entry without isMeta matches is_hook_feedback via preamble",
      is_hook_feedback(SYNTHETIC_HOOK_ENTRY))
SYNTHETIC_HOOK_STRING_CONTENT = {
    "type": "user",
    "message": {"role": "user", "content": "Stop hook feedback:\nMeasured 2026-08-19 on ucdavis/bcs#651..."},
}
check("Synthetic hook entry with string content matches is_hook_feedback via preamble",
      is_hook_feedback(SYNTHETIC_HOOK_STRING_CONTENT))
check("Real user entry does NOT match is_hook_feedback",
      not is_hook_feedback(REAL_USER_WITH_SOURCE_FIELD))
check("Scheduled continuation does NOT match is_hook_feedback",
      not is_hook_feedback(SCHEDULED_CONTINUATION))

print(f"\n{passed} passed, {failed} failed")
if failed:
    sys.exit(1)

