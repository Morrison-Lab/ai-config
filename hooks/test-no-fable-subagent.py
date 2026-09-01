#!/usr/bin/env python3
"""Test the no-fable-subagent guard.

Case #1 is the incident shape verbatim, per
`shared/workflow/algorithmatize-checks.md`: an `adversarial-reviewer`
dispatch with no `model`, which on the session that produced ai-config#2929
inherited Fable thirteen times with nothing in any call recording it.

Run:  python3 hooks/test-no-fable-subagent.py hooks/no-fable-subagent.py
"""
import json
import os
import subprocess
import sys

HOOK = os.path.abspath(sys.argv[1])


def run(payload, env_extra=None):
    env = {k: v for k, v in os.environ.items() if k != "ALLOW_FABLE_SUBAGENT"}
    env.update(env_extra or {})
    proc = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                          capture_output=True, text=True, env=env, timeout=30)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)["hookSpecificOutput"]


def agent(**tool_input):
    return {"tool_name": "Agent", "tool_input": tool_input}


CASES = []


def case(payload, env_extra, expect_deny, label):
    CASES.append((payload, env_extra, expect_deny, label))


# --- the incident: no model at all, inherited Fable -------------------------
case(agent(subagent_type="adversarial-reviewer", prompt="review the diff"), None, True,
     "an adversarial-reviewer dispatch with no model is denied (the #2929 shape)")
case(agent(subagent_type="general-purpose", prompt="x", model=None), None, True,
     "model: null is no model")
case(agent(subagent_type="general-purpose", prompt="x", model="  "), None, True,
     "a blank model is no model")
case({"tool_name": "Task", "tool_input": {"subagent_type": "Explore", "prompt": "x"}}, None, True,
     "the Task spelling of the dispatch tool is guarded too")

# --- Fable by name, in every spelling the harness accepts ------------------
case(agent(subagent_type="general-purpose", prompt="x", model="fable"), None, True,
     "model: fable is denied")
case(agent(subagent_type="general-purpose", prompt="x", model="Fable"), None, True,
     "the match is case-insensitive")
case(agent(subagent_type="general-purpose", prompt="x", model="claude-fable-5-1"), None, True,
     "the full model id is denied")

# --- the escape valve, and only for the Fable branch -----------------------
case(agent(subagent_type="general-purpose", prompt="x", model="fable"),
     {"ALLOW_FABLE_SUBAGENT": "1"}, False,
     "ALLOW_FABLE_SUBAGENT=1 passes a Fable dispatch the user granted")
case(agent(subagent_type="general-purpose", prompt="x"),
     {"ALLOW_FABLE_SUBAGENT": "1"}, True,
     "the override does not excuse an absent model: inheritance stays invisible")
case(agent(subagent_type="general-purpose", prompt="x", model="fable"),
     {"ALLOW_FABLE_SUBAGENT": "yes"}, True,
     "only the literal 1 is the override")

# --- every other explicit model passes through -----------------------------
for model in ("sonnet", "opus", "haiku", "claude-opus-5", "claude-sonnet-5"):
    case(agent(subagent_type="general-purpose", prompt="x", model=model), None, False,
         f"model: {model} passes through")

# --- a malformed model is refused, not read as absent or as a tier ---------
case(agent(subagent_type="general-purpose", prompt="x", model=["fable"]), None, True,
     "a non-string model is refused as malformed")

# --- other tools are none of this guard's business ------------------------
case({"tool_name": "Bash", "tool_input": {"command": "echo fable"}}, None, False,
     "a Bash call mentioning fable is ignored")
case({"tool_name": "SendMessage", "tool_input": {"to": "x", "message": "use fable"}}, None, False,
     "SendMessage is not a dispatch")

failures = 0
for payload, env_extra, expect_deny, label in CASES:
    out = run(payload, env_extra)
    denied = out.get("permissionDecision") == "deny"
    assert "allow" != out.get("permissionDecision"), f"{label}: emitted allow, which bypasses the prompt"
    if denied:
        assert out.get("permissionDecisionReason"), f"{label}: deny with no reason"
        assert "2929" in out["permissionDecisionReason"], f"{label}: reason cites no issue"
    if denied != expect_deny:
        failures += 1
        print(f"FAIL: {label}: expected {'deny' if expect_deny else 'pass'}, got {json.dumps(out)}")
    else:
        print(f"ok: {label}")

# An unreadable payload passes through rather than denying blind.
proc = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True, timeout=30)
assert proc.returncode == 0 and "deny" not in proc.stdout, "garbage stdin must not deny"
print("ok: an unreadable payload passes through")

if failures:
    sys.exit(f"{failures} of {len(CASES)} cases failed")
print(f"PASS: {len(CASES)} cases; an Agent dispatch must name its model and may name "
      "Fable only under ALLOW_FABLE_SUBAGENT=1")
