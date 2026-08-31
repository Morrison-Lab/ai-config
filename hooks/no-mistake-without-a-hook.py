#!/usr/bin/env python3
"""UserPromptSubmit reminder: an admitted mistake owes a HOOK, not just a note.

Standing `cai` (2026-08-02): "every time you make a mistake, write a hook to
prevent that mistake from recurring". This file is that rule applied to
itself.

WHY A PROSE RULE IS NOT ENOUGH HERE
-----------------------------------
Every mistake this session had a prose rule already covering it, and the rule
is what failed:

  * "always request another review" existed; PRs #1038 and #1040 sat
    unreviewed anyway (fixed by hooks/no-unreviewed-pr.py, #1041).
  * "file issues without asking" existed; a defect was flagged as "worth its
    own issue" and left unfiled (fixed by hooks/no-unfiled-finding.py, #1044).

A rule is consulted at read time and broken at composition time, which is why
re-reading it does not help. A hook fires at the boundary where the mistake
actually happens, so it is the only mechanism that reaches it. That is the
argument `shared/principles/deterministic-tools.md` makes generally, and
`shared/workflow/algorithmatize-checks.md` makes for checks.

WHY THIS INJECTS ON PROMPT AND BLOCKS ONLY AT STOP
---------------------------------------------------
Identical to remind-ums-after-error.py, and for the same reason: an error
admission is RIGHT to send. Blocking it would suppress the honest correction,
delay it reaching the user, and remove the signal that surfaced the mistake.
Admitting stays free and immediate; only the FOLLOW-UP is owed.

Its UserPromptSubmit registration therefore only adds context. Its separate
Stop registration blocks only after the admission has already been delivered,
and only until the owed hook work follows; it never suppresses the admission.

RELATIONSHIP TO remind-ums-after-error.py
-----------------------------------------
Same trigger, different obligation, so they are complements rather than
duplicates:

  remind-ums-after-error  -- an admitted error owes a RECORDED LEARNING
  this hook               -- an admitted error owes a MECHANISM

Both can be owed at once, and a memory write does not discharge this one. The
admission regex is IMPORTED from that module rather than copied, so the two
cannot drift apart -- per the corpus's own DRY rule.

NOT EVERY MISTAKE IS HOOKABLE, AND SAYING SO IS A VALID DISCHARGE
-----------------------------------------------------------------
A hook needs a condition decidable from the transcript. A one-off factual
slip, a judgment call that went the wrong way, or a domain error has no such
condition, and inventing a hook for it produces a guard that misfires and gets
switched off -- taking the real cases with it (`algorithmatize-checks`, and
the draft carve-out in #1041). So stating plainly that a mistake is not
mechanizable, and why, discharges this too.
"""
import importlib.util
import json
import os
import re
import sys

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


_ums = _sibling("remind-ums-after-error.py")

# Reuse the sibling's detection so the two hooks cannot drift. The fallback
# exists only so this hook degrades to silence rather than crashing if the
# sibling is missing -- it must never become a second, divergent copy.
ADMISSION = getattr(_ums, "ADMISSION", None)
visible_prose = getattr(_ums, "visible_prose", lambda t: t)

# Writing or registering a hook. `hooks.json` counts because registration is
# the second half of the work, per README's activation gate.
HOOK_WORK = re.compile(
    r"hooks/[\w.-]+\.py|hooks\.json|install-hooks\.py|PreToolUse|"
    r"UserPromptSubmit|\bStop\s+hook\b",
    re.I,
)

# An explicit judgment that the mistake is not mechanizable. Discharges the
# obligation, because forcing a hook here is worse than none.
NOT_HOOKABLE = re.compile(
    r"not (mechaniz|hookab|automat)|no (decidable|mechanical) (condition|test)|"
    r"cannot be (caught|detected) (by|with) a hook|not a hookable",
    re.I,
)


def scan(path):
    """Return (admission_text, admitted_at, addressed_at)."""
    admit_txt, admit_at, done_at = None, -1, -1
    with open(path, errors="ignore") as fh:
        for i, line in enumerate(fh):
            try:
                m = json.loads(line)
            except Exception:
                continue
            role = m.get("type") or m.get("role")
            blocks = (m.get("message") or {}).get("content") or m.get("content") or []

            # Antigravity tool calls
            if m.get("type") in {"PLANNER_RESPONSE", "GENERIC"} or m.get("source") == "MODEL" or "tool_calls" in m:
                for tc in m.get("tool_calls") or []:
                    if isinstance(tc, dict):
                        blob = (tc.get("name") or "") + " " + json.dumps(tc.get("args") or tc.get("input") or {})
                        if HOOK_WORK.search(blob):
                            done_at = i

            # Antigravity text content
            if m.get("type") in {"PLANNER_RESPONSE", "GENERIC"} or m.get("source") == "MODEL":
                raw_content = m.get("content")
                if isinstance(raw_content, str) and raw_content.strip():
                    prose = visible_prose(raw_content)
                    if ADMISSION is not None and ADMISSION.search(prose):
                        admit_txt, admit_at = ADMISSION.search(prose).group(0), i
                    if NOT_HOOKABLE.search(prose) or HOOK_WORK.search(prose):
                        done_at = i

            if isinstance(blocks, list):
                for b in blocks:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "tool_use":
                        blob = (b.get("name") or "") + " " + json.dumps(
                            b.get("input") or {})
                        if HOOK_WORK.search(blob):
                            done_at = i
                    elif b.get("type") == "text" and (role == "assistant" or m.get("type") == "assistant"):
                        txt = b.get("text") or ""
                        if not txt.strip():
                            continue
                        prose = visible_prose(txt)
                        if ADMISSION is not None and ADMISSION.search(prose):
                            admit_txt, admit_at = ADMISSION.search(prose).group(0), i
                        if NOT_HOOKABLE.search(prose) or HOOK_WORK.search(prose):
                            done_at = i
            elif isinstance(blocks, str) and role == "assistant" and blocks.strip():
                prose = visible_prose(blocks)
                if ADMISSION is not None and ADMISSION.search(prose):
                    admit_txt, admit_at = ADMISSION.search(prose).group(0), i
                if NOT_HOOKABLE.search(prose) or HOOK_WORK.search(prose):
                    done_at = i
    return admit_txt, admit_at, done_at


def main() -> int:
    if ADMISSION is None:
        return 0  # sibling unavailable; degrade to silence
    try:
        payload = json.load(sys.stdin)
        path = payload.get("transcript_path") or ""
        admit_txt, admit_at, done_at = scan(path)
    except Exception:
        return 0  # fail open

    if admit_at < 0:
        return 0
    # `>=` rather than `>`: a single message can both admit the mistake and
    # do the work (or judge it unmechanizable), and that is the ideal case.
    # Hook work strictly BEFORE the admission still does not discharge it,
    # since that index is lower.
    if done_at >= admit_at:
        return 0

    message = (
        "[hook: no-mistake-without-a-hook] You admitted a mistake earlier in "
        f"this session (\"{admit_txt.strip()}\") and no hook work followed "
        "it.\n\n"
        "Standing rule: every mistake owes a MECHANISM, not just a note. "
        "Every mistake this session already had a prose rule covering it, and "
        "the rule is what failed -- a rule is consulted at read time and "
        "broken at composition time, so re-reading it does not reach the "
        "moment it breaks.\n\n"
        "Ask: is there a condition decidable from the transcript that would "
        "have caught this?\n\n"
        "  * If yes -- write the hook (model it on hooks/no-offer-to-file.py "
        "for a message that is wrong to send, or on "
        "hooks/remind-ums-after-error.py for an obligation that follows a "
        "message which is right to send), add tests, mutation-check them, and "
        "register it in hooks/hooks.json. Do NOT activate it before its PR "
        "merges (README's activation gate).\n"
        "  * If no -- say so explicitly, and say why. A hook for a one-off "
        "factual slip or a judgment call misfires and gets switched off, "
        "taking the real cases with it. Stating that it is not mechanizable "
        "discharges this.\n\n"
        "This is separate from the UMS pass the sibling hook asks for: that "
        "one records the learning, this one prevents the recurrence. Both can "
        "be owed at once."
    )
    if os.getenv("AI_CONFIG_STOP") == "1":
        print(json.dumps({"decision": "block", "reason": message}))
    else:
        print(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
