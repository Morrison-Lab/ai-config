#!/usr/bin/env python3
"""Test no-implicit-session-environment.py: create_session names its environment.

Run:  python3 hooks/test-no-implicit-session-environment.py hooks/no-implicit-session-environment.py
"""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1]
passes = failures = 0
TOOL = "mcp__claude-code-remote__create_session"


def run(payload):
    res = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                         capture_output=True, encoding="utf-8")
    out = json.loads(res.stdout) if res.stdout.strip() else {}
    return res.returncode, out


def decision(out):
    return (out.get("hookSpecificOutput") or {}).get("permissionDecision")


def check(name, cond):
    global passes, failures
    passes += cond
    failures += (not cond)
    print(("PASS: " if cond else "FAIL: ") + name)


def call(tool_input, tool=TOOL):
    return {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input}


# The measured case: no environment_id at all.
rc, out = run(call({"title": "Polish block A", "source_url": "https://github.com/Morrison-Lab/lds",
                    "prompt": "polish"}))
check("missing environment_id is denied", rc == 0 and decision(out) == "deny")
reason = (out.get("hookSpecificOutput") or {}).get("permissionDecisionReason", "")
check("the reason names list_environments and the issue",
      "list_environments" in reason and "ai-config#4819" in reason)

rc, out = run(call({"prompt": "x", "environment_id": ""}))
check("an empty environment_id is denied", decision(out) == "deny")

rc, out = run(call({"prompt": "x", "environment_id": "   "}))
check("a whitespace environment_id is denied", decision(out) == "deny")

rc, out = run(call({"prompt": "x", "environment_id": "env_01FsTeprQaVKBbsBxkWtNWMR"}))
check("an explicit environment_id passes silently", rc == 0 and out == {})

rc, out = run(call({"prompt": "x"}, tool="create_session"))
check("an unprefixed create_session tool name is still guarded", decision(out) == "deny")

rc, out = run(call({"prompt": "x"}, tool="mcp__claude-code-remote__create_trigger"))
check("a different tool is ignored", rc == 0 and out == {})

rc, out = run(call({"prompt": "x"}, tool="Bash"))
check("Bash is ignored", rc == 0 and out == {})

rc, out = run(call({"prompt": "x"}, tool="mcp__x__recreate_session"))
check("a tool that only ends in create_session is ignored", rc == 0 and out == {})

rc, out = run(call({"prompt": "x", "environment_id": 123}))
check("a non-string environment_id is denied", decision(out) == "deny")

rc, out = run(call({"prompt": "x", "environment_id": ["env_x"]}))
check("a list environment_id is denied", decision(out) == "deny")

rc, out = run(call("not a dict"))
check("a non-dict tool_input is treated as empty and denied", rc == 0 and decision(out) == "deny")

res = subprocess.run([sys.executable, HOOK], input="[1]", capture_output=True, encoding="utf-8")
check("a non-dict payload exits 0 with no output", res.returncode == 0 and not res.stdout.strip())

rc, out = run(call({"prompt": "x"}))
check("the deny names the PreToolUse event",
      (out.get("hookSpecificOutput") or {}).get("hookEventName") == "PreToolUse")

for flag in ("--dry-run", "--simulate"):
    res = subprocess.run([sys.executable, HOOK, flag, json.dumps(call({"prompt": "x"}))],
                         capture_output=True, encoding="utf-8", input="")
    check(f"{flag} reports the deny", decision(json.loads(res.stdout or "{}")) == "deny")
res = subprocess.run([sys.executable, HOOK, "--dry-run",
                      json.dumps(call({"prompt": "x", "environment_id": "env_a"}))],
                     capture_output=True, encoding="utf-8", input="")
dry_out = json.loads(res.stdout or "{}")
check("--dry-run on a compliant call prints an empty decision",
      res.returncode == 0 and "permissionDecision" not in dry_out.get("hookSpecificOutput", {}))

# The registered matcher must name every spelling the harness uses for this tool, and each one
# must be a name the hook decides on; a rename of either side would otherwise leave the guard
# bound to nothing. The harness reports the claude-code-remote server under two spellings
# (hooks.json's add_repo matcher lists both; memories/subagent-worktrees.md records the second).
SPELLINGS = {TOOL, "mcp__Claude_Code_Remote__create_session"}
hooks_json = os.path.join(os.path.dirname(os.path.realpath(HOOK)), "hooks.json")
with open(hooks_json, encoding="utf-8") as fh:
    registered = json.load(fh)
matchers = [group.get("matcher") for group in registered["hooks"].get("PreToolUse", [])
            for h in group.get("hooks", [])
            if h.get("script") == os.path.basename(HOOK)]
check("hooks.json registers the hook exactly once", len(matchers) == 1)
bound = set((matchers[0] if matchers else "").split("|"))
check("hooks.json binds both create_session spellings and nothing else", bound == SPELLINGS)
for name in sorted(SPELLINGS):
    rc, out = run(call({"prompt": "x"}, tool=name))
    check(f"{name} without environment_id is denied", decision(out) == "deny")

res = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, encoding="utf-8")
check("unparseable input exits 0 with no output", res.returncode == 0 and not res.stdout.strip())

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
