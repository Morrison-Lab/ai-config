#!/usr/bin/env python3
"""Tests for warn-stderr-suppressed-then-parsed.py."""
import importlib.util
import os
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

if failures:
    print("FAILED:")
    for line in failures:
        print("  " + line)
    sys.exit(1)
print("all tests passed")
