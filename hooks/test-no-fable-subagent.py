#!/usr/bin/env python3
"""Test no-fable-subagent.py: a subagent never runs on Fable without a grant.

Run:  python3 hooks/test-no-fable-subagent.py hooks/no-fable-subagent.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]
passes = failures = 0


def transcript(model):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n")
        fh.write(json.dumps({"type": "assistant", "message": {"model": model, "content": []}}) + "\n")
        fh.write(json.dumps({"type": "user", "message": {"content": "next"}}) + "\n")
    return path


def run(payload, env_extra=None):
    env = dict(os.environ)
    env.pop("FABLE_SUBAGENT_OK", None)
    env.update(env_extra or {})
    res = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                         capture_output=True, encoding="utf-8", env=env)
    out = json.loads(res.stdout) if res.stdout.strip() else {}
    return res.returncode, out


def check(name, cond):
    global passes, failures
    passes += cond
    failures += (not cond)
    print(("PASS: " if cond else "FAIL: ") + name)


FABLE = transcript("claude-fable-5-1")
SONNET = transcript("claude-sonnet-5")


def agent(model=None, tpath=FABLE, **extra):
    inp = {"description": "x", "prompt": "do it", "subagent_type": "general-purpose"}
    if model is not None:
        inp["model"] = model
    inp.update(extra)
    p = {"tool_name": "Agent", "tool_input": inp}
    if tpath:
        p["transcript_path"] = tpath
    return p


def decision(out):
    return (out.get("hookSpecificOutput") or {}).get("permissionDecision")


rc, out = run(agent(model="fable", tpath=SONNET))
check("model=fable is denied even in a non-Fable session", decision(out) == "deny")
check("the denial names the override and the cheaper tiers",
      "FABLE_SUBAGENT_OK" in out["hookSpecificOutput"]["permissionDecisionReason"]
      and "sonnet" in out["hookSpecificOutput"]["permissionDecisionReason"])

rc, out = run(agent())
check("no model in a Fable session is denied (inherit is the violation)", decision(out) == "deny")
check("the denial names the inherited session model",
      "claude-fable-5-1" in out["hookSpecificOutput"]["permissionDecisionReason"])

rc, out = run(agent(model="sonnet"))
check("model=sonnet in a Fable session is silent", out == {})

rc, out = run(agent(model="haiku"))
check("model=haiku in a Fable session is silent", out == {})

rc, out = run(agent(tpath=SONNET))
check("no model in a Sonnet session is silent", out == {})

rc, out = run(agent(tpath=None))
check("no model and no transcript is not denied", decision(out) is None)
check("no model and no transcript adds a note",
      "could not be read" in (out.get("hookSpecificOutput") or {}).get("additionalContext", ""))

rc, out = run(agent(tpath="/nonexistent/transcript.jsonl"))
check("no model and an unreadable transcript is not denied", decision(out) is None)

rc, out = run(agent(model="fable"), {"FABLE_SUBAGENT_OK": "1"})
check("FABLE_SUBAGENT_OK=1 lets an explicit fable launch through", out == {})

rc, out = run(agent(), {"FABLE_SUBAGENT_OK": "1"})
check("FABLE_SUBAGENT_OK=1 lets an inherited launch through", out == {})

rc, out = run(agent(model="Claude Fable 5.1"))
check("a display-name model containing Fable is denied", decision(out) == "deny")

wf = {"tool_name": "Workflow", "tool_input": {"script": "export const meta={}"}, "transcript_path": FABLE}
rc, out = run(wf)
check("Workflow in a Fable session warns, never denies",
      decision(out) is None and "agent()" in (out.get("hookSpecificOutput") or {}).get("additionalContext", ""))
check("Workflow warning carries a systemMessage", bool(out.get("systemMessage")))

wf["transcript_path"] = SONNET
rc, out = run(wf)
check("Workflow in a Sonnet session is silent", out == {})

rc, out = run({"tool_name": "Bash", "tool_input": {"command": "echo fable"}, "transcript_path": FABLE})
check("a Bash call is ignored", out == {})

res = subprocess.run([sys.executable, HOOK, "--dry-run", json.dumps(agent(model="sonnet"))],
                     capture_output=True, encoding="utf-8")
check("--dry-run prints the empty PreToolUse shape when silent",
      json.loads(res.stdout) == {"hookSpecificOutput": {"hookEventName": "PreToolUse"}})

res = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, encoding="utf-8")
check("malformed stdin exits 0 with no output", res.returncode == 0 and not res.stdout.strip())

for p in (FABLE, SONNET):
    os.unlink(p)
print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
