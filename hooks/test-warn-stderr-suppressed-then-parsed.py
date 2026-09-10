#!/usr/bin/env python3
"""Tests for warn-stderr-suppressed-then-parsed.py."""
import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "warn-stderr-suppressed-then-parsed.py")

spec = importlib.util.spec_from_file_location("hook", HOOK)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

failures = []

def check(label, got, want):
    if got != want:
        failures.append(f"{label}: got {got!r}, want {want!r}")

def fires(command, module=hook):
    return len(module.find_offenses(command)) > 0

def reported(command, module=hook):
    offenses = module.find_offenses(command)
    if not offenses:
        return None
    return offenses[0]

# Positives
check("redirected to file fires", fires("cmd 2>/dev/null > out.json"), True)
check("redirected to file names reason", reported("cmd 2>/dev/null > out.json")[1], "redirected to `out.json`")
check("piped into next command fires", fires("cmd 2>/dev/null | jq ."), True)
check("piped names reason", reported("cmd 2>/dev/null | jq .")[1], "piped into the next command")
check("captured by command substitution fires", fires("var=$(cmd 2>/dev/null)"), True)
check("captured names reason", reported("var=$(cmd 2>/dev/null)")[1], "captured by a command substitution")
check("captured by backticks fires", fires("var=`cmd 2>/dev/null`"), True)
check("captured by backticks names reason", reported("var=`cmd 2>/dev/null`")[1], "captured by a command substitution")
check("redirected with append fires", fires("cmd 2>/dev/null >> out.json"), True)


# Group Positives
for label, cmd in [
    ("subshell redirected", "(cmd 2>/dev/null) > out.json"),
    ("subshell piped", "(cmd 2>/dev/null) | jq ."),
    ("brace group redirected", "{ cmd 2>/dev/null; } > out.json"),
    ("loop redirected", "for f in a b; do cmd 2>/dev/null; done > out.json"),
    ("case redirected", "case  in\n  a) cmd 2>/dev/null ;;\n  *) other ;;\nesac > out.json"),
    ("case with parenthesised pattern redirected", "case  in\n  (a) cmd 2>/dev/null ;;\n  *) other ;;\nesac > out.json"),
    ("select redirected", "select x in a b; do cmd 2>/dev/null; done > out.json"),
]:
    check(f"{label} fires", fires(cmd), True)

for label, cmd in [
    ("group output discarded", "(cmd 2>/dev/null) >/dev/null"),
    ("group output merged", "(cmd 2>/dev/null) >/dev/null 2>&1"),
    ("case output discarded", "case $x in a) cmd 2>/dev/null ;; esac >/dev/null 2>&1"),
]:
    check(f"{label} is ignored", fires(cmd), False)

check("nested substitution reported filename", reported('cmd 2>/dev/null > "$(mktemp)"')[1], 'redirected to `"$(mktemp)"`')

# The measured incident from ai-config#2998
INCIDENT = 'glab api "projects/.../pipelines/$p/jobs" > "$SP/j.json" 2>/dev/null'
check("the measured incident fires", fires(INCIDENT), True)
check("the incident names the reason", reported(INCIDENT)[1], 'redirected to `"$SP/j.json"`')

# Negatives
check("not consumed is ignored", fires("cmd 2>/dev/null"), False)
check("not consumed with condition is ignored", fires("cmd 2>/dev/null && echo OK"), False)
check("stdout and stderr to /dev/null is ignored", fires("cmd >/dev/null 2>&1 && echo OK"), False)
check("ampersand redirect to /dev/null is ignored", fires("cmd &>/dev/null"), False)
check("stderr to /dev/null and stdout to /dev/null is ignored", fires("cmd 2>/dev/null >/dev/null"), False)
check("stderr to /dev/null and stdout to /dev/null (other order) is ignored", fires("cmd >/dev/null 2>/dev/null"), False)
check("pipe receiver suppresses its own stderr but outputs to terminal is ignored", fires("cmd | jq . 2>/dev/null"), False)
check("merged stderr rather than suppressed is ignored", fires("cmd 2>&1 | jq ."), False)
check("nothing suppressed is ignored", fires("cmd | jq ."), False)
check("file descriptor 12 is not mistaken for 2", fires("cmd 12>/dev/null > out.json"), False)
check("redirecting stdout to stderr is not mistaken for file", fires("cmd 2>/dev/null >&2"), False)
check("closed stderr with stdout to file fires", fires("cmd 2>&- > out.json"), True)
check("redirecting to something that includes /dev/null but isnt it fires", fires("cmd 2>/dev/null > /dev/null-file"), True)



def run_hook(command, tool_name="Bash"):
    payload = json.dumps({
        "tool_name": tool_name,
        "tool_input": {"command": command},
    })
    env = dict(os.environ)
    env.pop("ANTIGRAVITY_AGENT", None)
    return subprocess.run([sys.executable, HOOK], input=payload, env=env,
                          capture_output=True, text=True, timeout=10)


# End-to-end: the payload handling and the output shape, which is what
# scripts/check-hook-output-shape.py requires a warn-only hook's test to pin.
proc = run_hook(INCIDENT)
check("firing command exits 0", proc.returncode, 0)
check("firing command prints no traceback", "Traceback" in proc.stderr, False)
payload = json.loads(proc.stdout)
check("emits PreToolUse context",
      payload["hookSpecificOutput"]["hookEventName"], "PreToolUse")
check("carries additionalContext",
      "stderr" in payload["hookSpecificOutput"]["additionalContext"], True)
check("carries a systemMessage outside Antigravity",
      "suppressed" in payload.get("systemMessage", ""), True)
check("never emits permissionDecision",
      "permissionDecision" in payload["hookSpecificOutput"], False)

proc = run_hook("git status --short")
check("non-firing command prints nothing", proc.stdout.strip(), "")
check("non-firing command exits 0", proc.returncode, 0)

proc = run_hook(INCIDENT, tool_name="Read")
check("a non-shell tool is ignored", proc.stdout.strip(), "")

if failures:
    print("FAILED:")
    for line in failures:
        print("  " + line)
    sys.exit(1)
print("all tests passed")
