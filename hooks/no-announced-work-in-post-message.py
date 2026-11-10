#!/usr/bin/env python3
"""PreToolUse guard: a post_message must not announce next work while steps remain unstarted.

Layer 2 of the defense-in-depth rule (ai-config#5051, issue #5053).

WHY A SECOND LAYER
------------------
`no-announced-start-without-starting.py` is a Stop hook, so it fires after the
message has been sent (ai-config#4830): the person has already read "Next I'm
opening the first workflow PR" when it blocks. This hook runs at send time, on
the `mcp__hearthbot__post_message` call itself, so an announcement of unstarted
work never reaches the person. It works with the Stop hook switched off, and
the Stop hook works with this one switched off.

WHAT IT DENIES
--------------
A post_message whose closing sentences unconditionally announce next work
(the same matchers as the Stop hook, imported from it so the two never drift)
while the thread's latest `update_progress_checklist` still has an unstarted
`○` step.
A named blocker or wait in the sentence exempts it, exactly as in the Stop hook.

WHY IT NEEDS THE CHECKLIST
--------------------------
Mid-turn, "I'm opening the PR" is often true and followed by the tool call.
Without the checklist this hook cannot tell that from an empty promise, and a
deny that fires on true narration gets switched off. An unstarted step on the
checklist is the evidence that there is work the message is promising but the
turn has not begun. The remedy is cheap: do the step, then report it in the
past tense.

Fails open on any parse trouble.
"""
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))


def _load_stop_hook():
    spec = importlib.util.spec_from_file_location(
        "announced_start", os.path.join(HERE, "no-announced-start-without-starting.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def last_checklist(path):
    """Text of the latest update_progress_checklist call in the transcript, or None."""
    found = None
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                try:
                    m = json.loads(line)
                except Exception:
                    continue
                blocks = (m.get("message") or {}).get("content") or []
                if not isinstance(blocks, list):
                    continue
                for b in blocks:
                    if (
                        isinstance(b, dict)
                        and b.get("type") == "tool_use"
                        and str(b.get("name") or "").endswith("update_progress_checklist")
                    ):
                        text = (b.get("input") or {}).get("text")
                        if isinstance(text, str):
                            found = text
    except Exception:
        return None
    return found


def has_unstarted_step(checklist):
    """True when a checklist line starts with the unstarted glyph.

    The glyphs are the format the update_progress_checklist tool documents
    for itself: a step line starts with a check mark (done), a six-spoked
    asterisk (in progress) or an open circle (not started). The tool's
    description is the source, so this hook does not rest on its own fixture.
    """
    return bool(checklist) and any(
        ln.lstrip().startswith("○") for ln in checklist.splitlines()
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        stop = _load_stop_hook()
        if not stop.REPLY_TOOL_RX.search(str(payload.get("tool_name") or "")):
            return 0
        text = (payload.get("tool_input") or {}).get("text")
        if not isinstance(text, str) or not text.strip():
            return 0
        found = stop.offending_sentence(stop.strip_code(text))
        if not found:
            return 0
        if not has_unstarted_step(last_checklist(payload.get("transcript_path") or "")):
            return 0
    except Exception:
        return 0
    sentence, phrase = found
    reason = (
        f'This message announces work it has not begun: "{phrase}".\n\n'
        f"In: {sentence}\n\n"
        "Your checklist still has an unstarted step. Do that step first "
        "(make the tool call), then send the message in the past tense "
        "('opened the PR'). If it cannot start yet, name the blocker or the "
        "wait in the same sentence ('once the review lands', 'blocked on X'). "
        "ai-config#5053."
    )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                    "additionalContext": reason,
                },
                "systemMessage": "Blocked: do the announced step before posting.",
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
