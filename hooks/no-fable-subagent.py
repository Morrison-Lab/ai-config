#!/usr/bin/env python3
"""PreToolUse guard: no subagent runs on Fable without explicit permission.

User directive, 2026-09-01 (ai-config#2927): "don't ever [spawn subagents
using Fable] without my explicit specific permission."

The launch that violates it never names Fable. An `Agent` call with no
`model` inherits the conductor's model, so in a Fable session the cheapest
thing to type -- omit the parameter -- is the most expensive thing to run,
and nothing reports the substitution. Measured in the session that received
the directive: 10 `Agent` launches, 8 of them inherited `claude-fable-5-1`
this way (six adversarial reviews, two sidecars), and the account then hit
its usage limit. The two launches that set `model: sonnet` were the only
ones that did not.

## What it decides

For an `Agent` launch (also reported as `Task` or `invoke_subagent`):

  - `model` names Fable (`fable` anywhere in the value, case-insensitive)
    -> DENY, unless `FABLE_SUBAGENT_OK=1` is set.
  - `model` is absent and the session's own model is Fable -> DENY on the
    same terms, because inheriting is how the violation happens.
  - `model` names any other tier -> silent.
  - `model` is absent and the session model cannot be read -> silent, with
    an `additionalContext` note saying the check could not run. Failing
    open here is deliberate: a hook that blocks every launch whenever a
    transcript is unreadable would stop work on a guess.

For a `Workflow` launch in a Fable session: WARN only. Its `agent()` calls
inherit the same way, but they live inside a script this hook cannot
inspect, so it says so and leaves the decision visible rather than blocking
a run that may set `model` on every call.

The session model comes from the transcript the harness names in the
payload (`transcript_path`), read from the tail: the latest `assistant`
record that carries `message.model` decides. No other hook reads that
field; `no-unmeasured-clock-claim.py` reads the same file for its clock
text, and that is the precedent for reading the transcript at all.

## The override is a grant, not a habit

`FABLE_SUBAGENT_OK=1` exists so that a launch the user explicitly approved
can proceed. Set it for that launch, in that command, after the user has
said yes to that launch; a session-wide export is the anti-pattern the
directive names, wearing an environment variable.

Run with `--dry-run '<payload json>'` to see the verdict without acting.
"""
import json
import os
import sys
from pathlib import Path

OVERRIDE_ENV = "FABLE_SUBAGENT_OK"
# The subagent-launch tool is reported under three names across harnesses;
# `remind-ums-after-error.py` and `docs/cursor-hook-mapping.md` carry the same set.
AGENT_TOOLS = ("Agent", "Task", "invoke_subagent")
TAIL_BYTES = 400_000


def _read_payload():
    args = sys.argv[1:]
    dry = "--dry-run" in args or "--simulate" in args
    if dry:
        positional = [a for a in args if not a.startswith("-")]
        if positional:
            raw = positional[0].strip()
            if raw.startswith("{"):
                try:
                    return json.loads(raw), True
                except Exception:
                    pass
            return {"tool_name": "Agent", "tool_input": {"prompt": raw}}, True
    try:
        payload = json.load(sys.stdin)
        return (payload if isinstance(payload, dict) else {}), dry
    except Exception as exc:
        print(f"no-fable-subagent: unreadable hook input ({exc})", file=sys.stderr)
        return {}, dry


def session_model(payload):
    """The model of the latest assistant record in the session transcript, or None."""
    tpath = payload.get("transcript_path") or payload.get("transcriptPath")
    if not isinstance(tpath, str) or not tpath.strip():
        return None
    path = Path(tpath.strip())
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            fh.seek(max(0, size - TAIL_BYTES))
            chunk = fh.read().decode("utf-8", "replace")
    except OSError:
        return None
    for line in reversed(chunk.splitlines()):
        if '"assistant"' not in line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("type") != "assistant":
            continue
        model = (rec.get("message") or {}).get("model")
        if isinstance(model, str) and model:
            return model
    return None


def is_fable(model):
    return isinstance(model, str) and "fable" in model.lower()


def decide(payload):
    """(decision, text): decision in {"deny", "warn", None}."""
    tool = payload.get("tool_name") or ""
    inp = payload.get("tool_input") or {}
    if tool in AGENT_TOOLS:
        model = inp.get("model")
        if isinstance(model, str) and model.strip():
            if not is_fable(model):
                return None, ""
            what = f"`model: {model}` names Fable"
        else:
            sess = session_model(payload)
            if sess is None:
                return "note", (
                    "no-fable-subagent: this Agent launch sets no `model`, so it "
                    "inherits the session model, and the transcript could not be "
                    "read to tell whether that is Fable. Pass `model` explicitly "
                    "(`sonnet` or `haiku` for bounded work).")
            if not is_fable(sess):
                return None, ""
            what = f"no `model` is set, so the launch inherits the session model `{sess}`"
        if os.environ.get(OVERRIDE_ENV) == "1":
            return None, ""
        return "deny", (
            "MECHANISTIC PROHIBITION: no subagent runs on Fable without the "
            "user's explicit, specific permission (ai-config#2927).\n\n"
            f"    This launch: {what}.\n\n"
            "Pass `model: \"sonnet\"` (or `haiku`) for mechanical or bounded "
            "work, or, if the user has said yes to running THIS launch on "
            f"Fable, re-run it with {OVERRIDE_ENV}=1 set for that one command. "
            "Do not export the override for the session.")
    if tool == "Workflow":
        sess = session_model(payload)
        if is_fable(sess):
            return "warn", (
                f"no-fable-subagent: this session runs on `{sess}`, so every "
                "`agent()` call in the workflow script that omits `model` will "
                "run on Fable. The user's standing directive (ai-config#2927) "
                "forbids that without explicit permission; set `model` on each "
                "`agent()` call or get the grant before running.")
    return None, ""


def main():
    payload, dry = _read_payload()
    if not payload:
        return 0
    decision, text = decide(payload)
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse"}}
    if decision == "deny":
        out["hookSpecificOutput"]["permissionDecision"] = "deny"
        out["hookSpecificOutput"]["permissionDecisionReason"] = text
        print(json.dumps(out))
        return 0
    if decision in ("warn", "note"):
        out["hookSpecificOutput"]["additionalContext"] = text
        out["systemMessage"] = text.split("\n")[0]
        print(json.dumps(out))
        return 0
    if dry:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
