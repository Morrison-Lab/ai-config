#!/usr/bin/env python3
"""PreToolUse guard: every launch of an agent, thread or session records a deliberate model choice.

User directive, 2026-11-16 (Ezra, "daytb" to the coordinator's recommendation):
whenever a coordinator or orchestrator starts a thread, session or subagent it
picks the best-fit model for the task, using the `select-model` and `recm`
criteria; and before giving new work to an EXISTING thread it stops and decides
whether a new thread (and which model) would fit better.

Why a deny hook: "default model" is the cheapest thing to type and nothing
reports that no choice was made. A running thread's model cannot be changed by
a message, so the choice only exists at launch. A reminder would be read past
(ai-config#4741); the omission is detectable from the call, so it is denied.

## What it decides

  - `Agent` / `Task` / `invoke_subagent` with no non-blank `model`  -> DENY.
    (`no-fable-subagent.py` separately denies Fable unless the user said yes.)
  - Thread/session START tools (`mcp__hearthbot__start_thread`,
    `create_session`) with no non-blank `model` field and no
    `Model-fit: <model> -- <reason>; Fable: <asked | not the best fit because ...>`
    line in any string field -> DENY.
  - `message_thread` with neither a `Why-not-new-thread: <reason>` line nor a
    `No-new-work: <what it carries>` line (a relay of an answer, a pinned sha,
    a head to merge) -> DENY: it forces the "should this be a new thread, and which model?"
    question before work is handed to an existing thread. A message that
    really belongs in the existing thread says why, e.g.
    `Why-not-new-thread: same files, context is needed`.
  - Everything else -> silent. Never emits `allow`.

The thread tool names are matched by suffix so the hearthbot and
claude-code-remote prefixes both work. The Model-fit line exists because a
tool may not expose a `model` parameter; the line then records the choice.

Run with `--dry-run '<payload json>'` to see the verdict without acting.
"""
import json
import re
import sys

AGENT_TOOLS = ("Agent", "Task", "invoke_subagent")
START_SUFFIXES = ("mcp__hearthbot__start_thread", "__create_session")
MESSAGE_SUFFIX = "mcp__hearthbot__message_thread"
# The line must name Fable: a launch that passes `model` cannot be checked, but a
# Model-fit line can, so it is where "always consider Fable" is enforced.
MODEL_FIT = re.compile(r"^\s*Model-fit:\s*\S.*\bFable:\s*\S", re.M | re.I)
# A message either assigns work (and says why not a new thread) or declares
# that it assigns none (a relay of an answer, a pinned sha, a head to merge).
WHY_NOT_NEW = re.compile(r"^\s*(Why-not-new-thread|No-new-work):\s*\S.*\S", re.M | re.I)


def _payload():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    pos = [a for a in args if not a.startswith("-")]
    if dry and pos and pos[0].strip().startswith("{"):
        try:
            return json.loads(pos[0]), True
        except Exception:
            return {}, True
    try:
        p = json.load(sys.stdin)
        return (p if isinstance(p, dict) else {}), dry
    except Exception:
        return {}, dry


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def decide(payload):
    tool = payload.get("tool_name") or ""
    inp = payload.get("tool_input")
    if not isinstance(inp, dict):
        return None
    model = inp.get("model")
    has_model = isinstance(model, str) and bool(model.strip())
    text = "\n".join(_strings(inp))
    if tool in AGENT_TOOLS:
        if has_model:
            return None
        return ("This subagent launch names no `model`, so it inherits the "
                "conductor's model without anyone choosing it. Pick the best "
                "fit with the select-model / recm criteria and pass it: "
                "`sonnet` or `haiku` for bounded edits, lookups and "
                "mechanical work; `opus` for large content passes and hard "
                "reasoning. Consider Fable too: when it would be the best fit, ask "
                "the user on a decision card whether to use it (it needs their yes).")
    if tool.endswith(START_SUFFIXES):
        if has_model or MODEL_FIT.search(text):
            return None
        return ("This thread/session start records no model choice. A running "
                "thread's model cannot be changed, so choose now with the "
                "select-model / recm criteria: pass `model`, or put a line "
                "`Model-fit: <model> -- <why>; Fable: <asked | not the best fit because ...>` in the "
                "instructions, naming Fable as considered. When Fable would be "
                "the best fit, ask the user on a decision card first (it needs their yes).")
    if tool.endswith(MESSAGE_SUFFIX):
        if WHY_NOT_NEW.search(text):
            return None
        return ("Before giving work to an existing thread, decide whether a "
                "new thread would be better (fresh context, a different "
                "model: a message cannot change a thread's model). Add a line "
                "`Why-not-new-thread: <reason>` to the message, for example "
                "`Why-not-new-thread: same PR and files, context is needed`. A "
                "message that assigns no new work (a relay, a sha) says "
                "`No-new-work: <what it carries>` instead.")
    return None


def main():
    payload, dry = _payload()
    if not payload:
        return 0
    reason = decide(payload)
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse"}}
    if reason:
        out["hookSpecificOutput"]["permissionDecision"] = "deny"
        out["hookSpecificOutput"]["permissionDecisionReason"] = (
            "MECHANISTIC REQUIREMENT (Ezra, 2026-11-16): choose the model "
            "deliberately.\n\n" + reason + "\n\nSee skills/select-model/SKILL.md "
            "(which model) and skills/choose-thread/SKILL.md (new thread or "
            "existing thread).")
        print(json.dumps(out))
    elif dry:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
