#!/usr/bin/env python3
"""PreToolUse guard: an `Agent` dispatch never runs on Fable unasked, named or inherited.

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

So the guard reads two artifacts, both of which exist at the moment the
decision is made: the call's own `tool_input`, and the session transcript
the harness hands every hook as `transcript_path`, whose assistant entries
each record `message.model` -- the model the session is actually running
on, which is what an omitted `model` inherits.

  - `model` naming Fable     -> DENY, unless `ALLOW_FABLE_SUBAGENT=1` is set
    in the environment. A grant is the user's words in the transcript, which
    is not lexically decidable here, so the marker is the escape valve --
    the same shape as `ALLOW_FORCE_PUSH=1` in `no-clobbering-push.py` -- and
    setting it means stating in the reply which words granted the dispatch.
  - `model` absent or blank, session on Fable -> DENY on the same terms.
    The dispatch would inherit Fable, which is the incident shape exactly,
    and the omission is the violation. The override applies here too, since
    "run this on Fable" granted in the user's words covers the inherited
    form as much as the named one.
  - `model` absent or blank, session NOT on Fable -> pass through with a
    warning (`additionalContext` plus `systemMessage`) asking that the tier
    be named. An inherited Sonnet or Opus worker breaks no rule, and
    `when-to-orchestrate.md`'s "Route each agent's model/effort" section
    says to omit `model` unless confident a different tier fits -- so a deny
    here would contradict the corpus's own guidance and fire on every
    non-Fable session for no spend the user forbade.
  - `model` absent, session model unknown -> pass through with the same
    warning. The Antigravity adapter (`plugins/ai-config/claude-hook-adapter.py`)
    builds an `Agent` payload with no `model` key at all and adds
    `transcript_path` only when it has one; a guard that denied on absence
    alone would refuse every Antigravity dispatch. Denying on evidence the
    hook does not have is guessing, and guessing toward deny is still
    guessing.
  - any other explicit model -> pass through. No `permissionDecision:
    "allow"` is ever emitted: naming `allow` would BYPASS a prompt the user
    would otherwise have seen, which is a hook making the harness more
    permissive than it was without it.

The session model is the `message.model` of the LAST assistant entry in the
transcript, read from the tail. A session can switch model mid-run (a
`/model` change, an overload fallback), so the earliest entry would be
wrong, and the latest is the one an inherited dispatch would run on. The
harness's own `<synthetic>` placeholder entries are skipped.

## Why deny rather than warn

`flag-unassigned-worktree.py`, the other `Agent` guard, warns, and records
why: it catches a visibility lapse, and a warning restores visibility
completely. This one catches a spend the user forbade, and a warning that
fires as the forbidden worker starts has already lost. The asymmetry runs
the other way too: a wrong deny costs one re-issued call with `model` set,
while a missed one is exactly the dispatch the directive names.
That asymmetry holds only where the spend is Fable's. Where the session is
not on Fable, or the hook cannot tell, an omitted `model` is a visibility
lapse of the kind `flag-unassigned-worktree.py` catches, and a warning
restores that visibility completely.

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
TAIL_BYTES = 256 * 1024

REASON_INHERIT_FABLE = (
    "This Agent dispatch names no `model`, so the worker would inherit the "
    "session's model, and this session is running on Fable "
    "(`{session_model}` per the transcript) -- so that is a Fable subagent, "
    "which the user forbade without explicit, specific permission "
    "(ai-config#2929, #2924). Pass `model` explicitly: `sonnet` or `haiku` for "
    "mechanical, bounded work, `opus` for judgment-heavy work. Never inherit "
    "or name Fable unless the user granted it for this dispatch in their own "
    f"words; then set {OVERRIDE}=1 and say which words granted it."
)

NOTE_NO_MODEL = (
    "This Agent dispatch names no `model`, so the worker inherits the "
    "session's model ({session_model}). That is allowed here, since the "
    "session is not on Fable, but the tier is then a fact about the session "
    "that a later reader of the call cannot recover. Name it: `sonnet` or "
    "`haiku` for mechanical, bounded work, `opus` for judgment-heavy work "
    "(ai-config#2929)."
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


def session_model(transcript_path):
    """The `message.model` of the last assistant entry, or None if unknown.

    Reads only the tail of the file: a long session's transcript runs to
    many megabytes and the answer is always at the end. Placeholder entries
    (`<synthetic>`) are skipped, since they name no real model.
    """
    if not transcript_path:
        return None
    try:
        with open(transcript_path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - TAIL_BYTES))
            tail = fh.read().decode("utf-8", errors="ignore")
    except OSError:
        return None
    for line in reversed(tail.splitlines()):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict) or entry.get("type") != "assistant":
            continue
        message = entry.get("message")
        model = message.get("model") if isinstance(message, dict) else None
        if isinstance(model, str) and model and not model.startswith("<"):
            return model
    return None


def is_fable(model):
    return "fable" in model.lower()


def decide(payload, env):
    """(deny_reason, warning) for `payload`; both None to pass silently.

    A deny reason always wins over a warning, and at most one is set.
    """
    if payload.get("tool_name") not in AGENT_TOOLS:
        return None, None
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return None, None
    model = tool_input.get("model")
    granted = env.get(OVERRIDE) == "1"
    if model is not None and not isinstance(model, str):
        return REASON_MALFORMED.format(model=model), None
    if model is not None and model.strip():
        if is_fable(model) and not granted:
            return REASON_FABLE.format(model=model), None
        return None, None
    inherited = session_model(payload.get("transcript_path"))
    if inherited is not None and is_fable(inherited) and not granted:
        return REASON_INHERIT_FABLE.format(session_model=inherited), None
    shown = inherited if inherited is not None else "unknown to this hook"
    return None, NOTE_NO_MODEL.format(session_model=shown)


def main():
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        # An unreadable payload is not an Agent dispatch this guard can judge;
        # fail toward the ordinary permission flow rather than denying blind.
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0
    output = {"hookEventName": "PreToolUse"}
    out = {"hookSpecificOutput": output}
    reason, warning = decide(payload, os.environ)
    if reason is not None:
        output["permissionDecision"] = "deny"
        output["permissionDecisionReason"] = reason
    elif warning is not None:
        output["additionalContext"] = warning
        if not os.environ.get("ANTIGRAVITY_AGENT"):
            out["systemMessage"] = (
                "Agent dispatch without `model`: the worker inherits the "
                "session's model. Name the tier (ai-config#2929)."
            )
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
