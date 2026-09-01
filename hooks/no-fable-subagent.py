#!/usr/bin/env python3
"""PreToolUse guard: an `Agent` dispatch names its model, and never Fable unasked.

## The rule

User directive, 2026-09-01 (Morrison-Lab/ai-config#2929, memory rule in
#2924): never spawn a subagent on Fable without the user's explicit, specific
permission for that dispatch.

## Why a hook, and why it keys on the call rather than on the intent

A subagent lands on Fable two ways, and only one is visible in the `Agent`
call. `model: "fable"` is a choice. Omitting `model` while the conductor is
on Fable is INHERITANCE: the harness runs the worker on the parent's model
and nothing in the call says so. An agent definition under `.claude/agents/`
with no `model:` in its frontmatter inherits the same way, and
`adversarial-reviewer` -- the one CLAUDE.md's pre-push rule dispatches by
name -- is such a definition.

The breach this mechanizes was the inherited kind. One session on
`claude-fable-5-1` dispatched `adversarial-reviewer` thirteen times with no
`model` parameter, and every worker ran on Fable. No review, test, or lint
could see it: the omission lives in a tool call, the one surface none of
them inspect. It surfaced only when the last dispatch died with
`rate_limit ... model sent to the API: claude-fable-5-1`.

So the guard reads the call's own `tool_input`, which is the only artifact
that exists at the moment the decision is made:

  - `model` absent or blank  -> DENY. The tier is a fact about the session
    that a later reader cannot recover, and on a Fable session the omission
    is the violation itself. The remedy costs one word.
  - `model` naming Fable     -> DENY, unless `ALLOW_FABLE_SUBAGENT=1` is set
    in the environment. A grant is the user's words in the transcript, which
    is not lexically decidable here, so the marker is the escape valve --
    the same shape as `ALLOW_FORCE_PUSH=1` in `no-clobbering-push.py` -- and
    setting it means stating in the reply which words granted the dispatch.
  - any other explicit model -> pass through. No `permissionDecision:
    "allow"` is ever emitted: naming `allow` would BYPASS a prompt the user
    would otherwise have seen, which is a hook making the harness more
    permissive than it was without it.

## Why deny rather than warn

`flag-unassigned-worktree.py`, the other `Agent` guard, warns, and records
why: it catches a visibility lapse, and a warning restores visibility
completely. This one catches a spend the user forbade, and a warning that
fires as the forbidden worker starts has already lost. The asymmetry runs
the other way too: a wrong deny costs one re-issued call with `model` set,
while a missed one is exactly the dispatch the directive names.

Matching is a case-insensitive substring test for `fable` on the model
string, so `fable`, `Fable`, and `claude-fable-5-1` all match, and a future
`claude-fable-6` matches without an edit here. A non-string `model` is
refused as malformed rather than read as absent.

Run:  python3 hooks/test-no-fable-subagent.py hooks/no-fable-subagent.py
"""
import json
import os
import sys

AGENT_TOOLS = ("Agent", "Task")
OVERRIDE = "ALLOW_FABLE_SUBAGENT"

REASON_NO_MODEL = (
    "This Agent dispatch names no `model`, so the worker would inherit the "
    "session's model -- on a Fable session that is a Fable subagent, which the "
    "user forbade without explicit, specific permission (ai-config#2929, "
    "#2924). Pass `model` explicitly: `sonnet` or `haiku` for mechanical, "
    "bounded work, `opus` for judgment-heavy work. Never `fable` unless the "
    "user granted it for this dispatch in their own words; then set "
    f"{OVERRIDE}=1 and say which words granted it."
)

REASON_FABLE = (
    "This Agent dispatch names Fable (`model: {model!r}`). The user forbade "
    "spawning a subagent on Fable without explicit, specific permission for "
    "that dispatch (ai-config#2929, #2924). Pick another tier, or -- only when "
    "the user granted this dispatch in their own words -- re-issue it with "
    f"{OVERRIDE}=1 set and say which words granted it."
)

REASON_MALFORMED = (
    "This Agent dispatch carries a `model` that is not a string "
    "({model!r}); refusing rather than guessing which tier it means "
    "(ai-config#2929)."
)


def decide(payload, env):
    """The deny reason for `payload`, or None to pass the call through."""
    if payload.get("tool_name") not in AGENT_TOOLS:
        return None
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return None
    if "model" not in tool_input or tool_input["model"] is None:
        return REASON_NO_MODEL
    model = tool_input["model"]
    if not isinstance(model, str):
        return REASON_MALFORMED.format(model=model)
    if not model.strip():
        return REASON_NO_MODEL
    if "fable" in model.lower() and env.get(OVERRIDE) != "1":
        return REASON_FABLE.format(model=model)
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        # An unreadable payload is not an Agent dispatch this guard can judge;
        # fail toward the ordinary permission flow rather than denying blind.
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0
    output = {"hookEventName": "PreToolUse"}
    reason = decide(payload, os.environ)
    if reason is not None:
        output["permissionDecision"] = "deny"
        output["permissionDecisionReason"] = reason
    print(json.dumps({"hookSpecificOutput": output}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
