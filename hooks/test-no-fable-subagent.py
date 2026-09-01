#!/usr/bin/env python3
"""Test the no-fable-subagent guard.

Case #1 is the incident shape verbatim, per
`shared/workflow/algorithmatize-checks.md`: an `adversarial-reviewer`
dispatch with no `model`, from a session whose transcript records
`claude-fable-5-1` as its model -- which on the session that produced
ai-config#2929 inherited Fable thirteen times with nothing in any call
recording it.

The transcripts are fixtures written at run time, shaped like the real
JSONL: assistant entries carry `message.model`, and the harness's own
`<synthetic>` placeholder entries are present so the reader has to skip
them. Nothing is committed.

Run:  python3 hooks/test-no-fable-subagent.py hooks/no-fable-subagent.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.abspath(sys.argv[1])
TMP = tempfile.mkdtemp(prefix="no-fable-subagent-")


def transcript(name, models):
    """Write a JSONL transcript whose assistant entries carry `models` in order."""
    path = os.path.join(TMP, name + ".jsonl")
    with open(path, "w") as fh:
        fh.write(json.dumps({"type": "user", "message": {"role": "user", "content": "hi"}}) + "\n")
        for model in models:
            fh.write(json.dumps({"type": "assistant", "message": {"role": "assistant", "model": model, "content": []}}) + "\n")
        # The harness appends placeholder entries after the last real one.
        fh.write(json.dumps({"type": "assistant", "message": {"role": "assistant", "model": "<synthetic>", "content": []}}) + "\n")
    return path


FABLE_SESSION = transcript("fable", ["claude-fable-5-1", "claude-fable-5-1"])
SONNET_SESSION = transcript("sonnet", ["claude-sonnet-5"])
SWITCHED_AWAY = transcript("switched-away", ["claude-fable-5-1", "claude-opus-5"])
SWITCHED_TO = transcript("switched-to", ["claude-opus-5", "claude-fable-5-1"])
NO_ASSISTANT = transcript("empty", [])


def run(payload, env_extra=None):
    env = {k: v for k, v in os.environ.items() if k not in ("ALLOW_FABLE_SUBAGENT", "ANTIGRAVITY_AGENT")}
    env.update(env_extra or {})
    proc = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                          capture_output=True, text=True, env=env, timeout=30)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def agent(session=None, **tool_input):
    payload = {"tool_name": "Agent", "tool_input": tool_input}
    if session is not None:
        payload["transcript_path"] = session
    return payload


CASES = []


def case(payload, env_extra, expect, label):
    """`expect` is "deny", "warn", or "pass"."""
    CASES.append((payload, env_extra, expect, label))


# --- the incident: no model at all, inherited Fable -------------------------
case(agent(FABLE_SESSION, subagent_type="adversarial-reviewer", prompt="review the diff"), None, "deny",
     "an adversarial-reviewer dispatch with no model on a Fable session is denied (the #2929 shape)")
case(agent(FABLE_SESSION, subagent_type="general-purpose", prompt="x", model=None), None, "deny",
     "model: null is no model")
case(agent(FABLE_SESSION, subagent_type="general-purpose", prompt="x", model="  "), None, "deny",
     "a blank model is no model")
case({"tool_name": "Task", "tool_input": {"subagent_type": "Explore", "prompt": "x"},
      "transcript_path": FABLE_SESSION}, None, "deny",
     "the Task spelling of the dispatch tool is guarded too")
case(agent(SWITCHED_TO, subagent_type="general-purpose", prompt="x"), None, "deny",
     "the LAST assistant entry decides: a session that switched onto Fable inherits Fable")

# --- no model, but the session is not on Fable: warn, never deny -----------
case(agent(SONNET_SESSION, subagent_type="general-purpose", prompt="x"), None, "warn",
     "an omitted model on a Sonnet session passes with a name-the-tier warning")
case(agent(SWITCHED_AWAY, subagent_type="general-purpose", prompt="x"), None, "warn",
     "a session that switched off Fable inherits the later model, not the earlier one")
case(agent(NO_ASSISTANT, subagent_type="general-purpose", prompt="x"), None, "warn",
     "a transcript with only placeholder entries leaves the session model unknown: warn, not deny")
case(agent(None, subagent_type="general-purpose", prompt="x"), None, "warn",
     "no transcript_path at all (the Antigravity adapter's shape) passes with a warning")
case({"tool_name": "Agent", "tool_input": {"subagent_type": "general-purpose", "isolation": "worktree",
                                            "workspace": "/w", "prompt": "x"}}, None, "warn",
     "the Antigravity adapter's exact Agent payload (no model key, no transcript) is not denied")
case(agent(os.path.join(TMP, "missing.jsonl"), subagent_type="general-purpose", prompt="x"), None, "warn",
     "an unreadable transcript_path is unknown, not Fable")

# --- Fable by name, in every spelling the harness accepts ------------------
# On a Sonnet session, so the deny is attributable to the name alone.
case(agent(SONNET_SESSION, subagent_type="general-purpose", prompt="x", model="fable"), None, "deny",
     "model: fable is denied")
case(agent(SONNET_SESSION, subagent_type="general-purpose", prompt="x", model="Fable"), None, "deny",
     "the match is case-insensitive")
case(agent(SONNET_SESSION, subagent_type="general-purpose", prompt="x", model="claude-fable-5-1"), None, "deny",
     "the full model id is denied")
case(agent(None, subagent_type="general-purpose", prompt="x", model="fable"), None, "deny",
     "a named Fable is denied with no transcript at all")

# --- the escape valve, for the named and the inherited Fable alike ---------
case(agent(SONNET_SESSION, subagent_type="general-purpose", prompt="x", model="fable"),
     {"ALLOW_FABLE_SUBAGENT": "1"}, "pass",
     "ALLOW_FABLE_SUBAGENT=1 passes a Fable dispatch the user granted")
case(agent(FABLE_SESSION, subagent_type="general-purpose", prompt="x"),
     {"ALLOW_FABLE_SUBAGENT": "1"}, "warn",
     "the override covers inheriting Fable too, and the name-the-tier warning still fires")
case(agent(SONNET_SESSION, subagent_type="general-purpose", prompt="x", model="fable"),
     {"ALLOW_FABLE_SUBAGENT": "yes"}, "deny",
     "only the literal 1 is the override")

# --- every other explicit model passes through, whatever the session ------
for model in ("sonnet", "opus", "haiku", "claude-opus-5", "claude-sonnet-5"):
    case(agent(FABLE_SESSION, subagent_type="general-purpose", prompt="x", model=model), None, "pass",
         f"model: {model} passes through silently, even on a Fable session")

# --- a malformed model is refused, not read as absent or as a tier ---------
case(agent(SONNET_SESSION, subagent_type="general-purpose", prompt="x", model=["fable"]), None, "deny",
     "a non-string model is refused as malformed")

# --- other tools are none of this guard's business ------------------------
case({"tool_name": "Bash", "tool_input": {"command": "echo fable"}, "transcript_path": FABLE_SESSION}, None, "pass",
     "a Bash call mentioning fable is ignored, even on a Fable session")
case({"tool_name": "SendMessage", "tool_input": {"to": "x", "message": "use fable"}}, None, "pass",
     "SendMessage is not a dispatch")


def classify(out):
    hso = out["hookSpecificOutput"]
    assert "allow" != hso.get("permissionDecision"), "emitted allow, which bypasses the prompt"
    if hso.get("permissionDecision") == "deny":
        assert hso.get("permissionDecisionReason"), "deny with no reason"
        assert "2929" in hso["permissionDecisionReason"], "reason cites no issue"
        assert "additionalContext" not in hso and "systemMessage" not in out, "a deny must not also warn"
        return "deny"
    if hso.get("additionalContext"):
        assert "2929" in hso["additionalContext"], "warning cites no issue"
        assert out.get("systemMessage"), "a warning needs a systemMessage so it is visible"
        return "warn"
    assert "systemMessage" not in out, "a silent pass must not carry a systemMessage"
    return "pass"


failures = 0
for payload, env_extra, expect, label in CASES:
    out = run(payload, env_extra)
    try:
        got = classify(out)
    except AssertionError as exc:
        failures += 1
        print(f"FAIL: {label}: {exc}: {json.dumps(out)}")
        continue
    if got != expect:
        failures += 1
        print(f"FAIL: {label}: expected {expect}, got {got}: {json.dumps(out)}")
    else:
        print(f"ok: {label}")

# The deny reason names the session model it read, so the reader can check it.
out = run(agent(FABLE_SESSION, subagent_type="general-purpose", prompt="x"))
assert "claude-fable-5-1" in out["hookSpecificOutput"]["permissionDecisionReason"], out
print("ok: the inherited-Fable deny names the model the transcript recorded")

# Under the Antigravity adapter the additionalContext stands alone (no systemMessage).
out = run(agent(SONNET_SESSION, subagent_type="general-purpose", prompt="x"), {"ANTIGRAVITY_AGENT": "1"})
assert out["hookSpecificOutput"].get("additionalContext") and "systemMessage" not in out, out
print("ok: under ANTIGRAVITY_AGENT the warning is additionalContext only")

# An unreadable payload passes through rather than denying blind.
proc = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True, timeout=30)
assert proc.returncode == 0 and "deny" not in proc.stdout, "garbage stdin must not deny"
print("ok: an unreadable payload passes through")

if failures:
    sys.exit(f"{failures} of {len(CASES)} cases failed")
print(f"PASS: {len(CASES)} cases; an Agent dispatch may run on Fable, named or inherited, "
      "only under ALLOW_FABLE_SUBAGENT=1, and an omitted model elsewhere only warns")
