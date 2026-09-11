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
    ("single-line case piped", "case $x in a) cmd 2>/dev/null ;; esac | jq ."),
    ("a stage after a single-line case", "case $o in a) p ;; b) q ;; esac; curl -s u 2>/dev/null | jq ."),
]:
    check(f"{label} fires", fires(cmd), True)

for label, cmd in [
    ("group output discarded", "(cmd 2>/dev/null) >/dev/null"),
    ("group output merged", "(cmd 2>/dev/null) >/dev/null 2>&1"),
    ("case output discarded", "case $x in a) cmd 2>/dev/null ;; esac >/dev/null 2>&1"),
]:
    check(f"{label} is ignored", fires(cmd), False)

check("nested substitution reported filename", reported('cmd 2>/dev/null > "$(mktemp)"')[1], 'redirected to `"$(mktemp)"`')
check("backticked redirect target is reported whole",
      reported("cmd 2>/dev/null > `echo my file`.json")[1],
      "redirected to ``echo my file`.json`")

# KNOWN LIMIT: a case statement nested inside a command substitution. The
# pattern terminator's `)` is indistinguishable here from the substitution's
# own closing parenthesis, so the group is not recognised and nothing fires.
# It under-warns, which for an advisory hook is the tolerated direction, and
# it is pinned so a later parser change reports it rather than hiding it.
check("KNOWN LIMIT: a case inside a substitution does not fire",
      fires("x=$(case $y in a) cmd 2>/dev/null ;; esac)"), False)

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

# A quoted span inside a backtick substitution must restore the backtick as the
# enclosing context. Without that, the substitution's own closing backtick reads
# as opening a second one and the whole command scans as unterminated.
check(
    "quoted span inside backticks still fires",
    fires('cmd 2>/dev/null > `echo "my file"`.json'),
    True,
)
check(
    "single-quoted span inside backticks still fires",
    fires("cmd 2>/dev/null > `echo 'my file'`.json"),
    True,
)
check(
    "quoted capture inside backticks names the substitution",
    reported('result=`curl -s "$url" 2>/dev/null` ; echo "$result" > out.json')[1],
    "captured by a command substitution",
)
check(
    "backticked target with a quoted span is reported whole",
    reported('cmd 2>/dev/null > `echo "my file"`.json')[1],
    'redirected to ``echo "my file"`.json`',
)
check(
    "merged stderr with a quoted span inside backticks stays silent",
    fires('cmd 2>&1 > `echo "my file"`.json'),
    False,
)
check(
    "discarded output with a quoted span inside backticks stays silent",
    fires('cmd 2>/dev/null > `echo "my file"` >/dev/null'),
    False,
)

# A backslash escapes inside a backtick substitution. Without that, an escaped
# backtick closed the substitution early and every following top-level command
# was swallowed as unterminated content -- a false positive, which this hook's
# own docstring rules out even though it tolerates under-warning.
check(
    "an escaped backtick does not close its substitution",
    fires(r'`echo \` foo` bar 2>/dev/null'),
    False,
)
check(
    "an escaped backtick leaves a later offense classified at top level",
    reported(r'`echo \` foo` bar 2>/dev/null > out.json')[1],
    "redirected to `out.json`",
)
check(
    "an escaped dollar-paren does not open a substitution",
    fires(r'echo \$(x) bar 2>/dev/null'),
    False,
)

# Bash's `&>` shorthand sends both streams to /dev/null, so it is normally a
# discard rather than an offense. A LATER stdout redirect reclaims stdout while
# stderr stays discarded, which is exactly the shape this hook names. Two bugs
# hid that: the `&` of `&>` matched the segment separator and split the command
# in two, and the discard was treated as final regardless of what followed it.
check("merge-null then file redirect fires", fires("cmd &>/dev/null > out.json"), True)
check("merge-null append then file redirect fires", fires("cmd &>>/dev/null > out.json"), True)
check(
    "merge-null then file redirect names the target",
    reported("cmd &>/dev/null > out.json")[1],
    "redirected to `out.json`",
)
check("merge-null alone stays silent", fires("cmd &>/dev/null"), False)
check("merge-null into a pipe stays silent", fires("cmd &>/dev/null | jq ."), False)
check(
    "a discard after a file redirect still discards",
    fires("cmd 2>/dev/null > out.json >/dev/null"),
    False,
)
check("a bare & still separates segments", fires("cmd 2>/dev/null & other > out.json"), False)

# Redirect order governs stderr exactly as it governs stdout. A suppression a
# later redirect reclaims never takes effect, so firing on it warns about a
# command whose stderr is captured or merged -- the over-warning this hook
# rules out. The reverse order is a real suppression and must still fire.
check(
    "a later stderr file redirect supersedes an earlier discard",
    fires("cmd 2>/dev/null 2>err.log > out.json"),
    False,
)
check(
    "a later merge supersedes an earlier discard",
    fires("cmd 2>/dev/null 2>&1 | jq ."),
    False,
)
check(
    "a later stderr file redirect supersedes an earlier close",
    fires("cmd 2>&- 2>err.log > out.json"),
    False,
)
check(
    "a discard after a stderr file redirect still fires",
    fires("cmd 2>err.log 2>/dev/null > out.json"),
    True,
)
check("a bare close still fires", fires("cmd 2>&- > out.json"), True)
check("fd 12 is not fd 2", fires("cmd 12>/dev/null > out.json"), False)

# Two stdout file targets in one stage: the shell writes the LAST one and
# truncates the first, so naming the first sends a reader to an empty file.
check(
    "the reported target is the redirect that takes effect",
    reported("cmd 2>/dev/null > /tmp/stage.json > /tmp/final.json")[1],
    "redirected to `/tmp/final.json`",
)
check(
    "two targets with a discard last still stays silent",
    fires("cmd 2>/dev/null > a.json > b.json >/dev/null"),
    False,
)

# `&>file` with a NON-null target sends BOTH streams to the file, so it
# reclaims an earlier stderr discard and is itself the stdout target. Only the
# /dev/null spelling was recognised before, so a later `&>file.log` reclaimed
# nothing and the hook warned about a command whose stderr is in the file and
# whose stdout never reaches the pipe or the capture.
check(
    "a later merge to a file reclaims stderr in a capture",
    fires("x=$(cmd 2>/dev/null &>file.log)"),
    False,
)
check(
    "a later merge to a file reclaims stderr before a pipe",
    fires("cmd 2>/dev/null &>file.log | jq ."),
    False,
)
check(
    "a discard after a merge to a file still fires",
    fires("cmd &>file.log 2>/dev/null > out.json"),
    True,
)
check(
    "a merge to a file is itself the reported target",
    reported("cmd &>file.log 2>/dev/null")[1],
    "redirected to `file.log`",
)
check(
    "a merge to a file before a plain redirect yields to the later target",
    reported("cmd &>file.log 2>/dev/null > out.json")[1],
    "redirected to `out.json`",
)

# An ordinary fd duplication touches no file. RX_MERGE_FILE was missing the
# digit lookbehind every sibling pattern carries, so `3>&2` read as a redirect
# to a file named `2`. The one pre-existing `>&2` case passed only because its
# digit happened to match the fd already redirected earlier in that stage.
check("fd duplication is not a file target", fires("cmd 3>&2 2>/dev/null"), False)
check("self-duplication is not a file target", fires("cmd >&1 2>/dev/null"), False)
check("the fd move form is not a file target", fires("cmd 3>&2- 2>/dev/null"), False)

# `>|` overrides noclobber and is ONE redirect operator. Its bar was being
# consumed as a pipe boundary, so a fully discarded command read as piped.
check(
    "a noclobber override to /dev/null discards, and stays silent",
    fires("cmd 2>/dev/null >|/dev/null"),
    False,
)
check(
    "a noclobber override to a real file fires",
    fires("cmd 2>/dev/null >|out.json"),
    True,
)
check(
    "a noclobber override names its target",
    reported("cmd 2>/dev/null >|out.json")[1],
    "redirected to `out.json`",
)

# `>|` is a stdout redirect operator everywhere `>` is, not only where the
# first fix happened to put it. The previous round taught the FILE pattern
# about it and left the DISCARD pattern behind, so a fully discarded stage read
# as piped. Both now come from one operator alternation.
check(
    "a discarded noclobber override before a pipe stays silent",
    fires("cmd 2>/dev/null >|/dev/null | jq"),
    False,
)
check(
    "a noclobber append override to a file fires",
    fires("cmd 2>/dev/null >>|out.json"),
    True,
)

# A bare substitution as the SOLE redirect target was blanked to spaces in the
# outer region, leaving nothing after the operator for the redirect patterns to
# match. The same target quoted, or with any literal text beside it, fired --
# so the shape decided the verdict rather than the redirect did.
check(
    "a bare command substitution target fires",
    fires("cmd 2>/dev/null > $(mktemp)"),
    True,
)
check(
    "a bare backtick target fires",
    fires("cmd 2>/dev/null > `mktemp`"),
    True,
)
check(
    "a bare substitution target is reported whole",
    reported("cmd 2>/dev/null > $(mktemp)")[1],
    "redirected to `$(mktemp)`",
)
check(
    "the mark does not make /dev/null look like a file",
    fires("cmd 2>/dev/null > /dev/null"),
    False,
)

if failures:
    print("FAILED:")
    for line in failures:
        print("  " + line)
    sys.exit(1)
print("all tests passed")
