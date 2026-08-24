#!/usr/bin/env python3
"""Tests for warn-status-read-after-pipe.py.

The negatives carry most of the weight. This corpus writes `| head` and `$?`
constantly --- in `shared/coding/errexit-is-not-uniform.md`, in
`shared/principles/fail-fast.md`, in the hook's own docstring --- so a matcher
keyed on those two strings would fire on every session that discusses the rule
it enforces.

Each negative names the shape it protects rather than merely asserting False,
so a later reader can tell a deliberate exclusion from an accident.

The file ends with a MUTATION section. A suite that passes against a
deliberately broken matcher is not testing the matcher, so each of the three
load-bearing rules --- the pipe test, the `pipefail` suppression, and the
single-quote exclusion --- is broken on purpose and asserted to turn a test
red. `memories/regex-negation-needs-adversarial-tests` records the case that
motivated this: an 18-of-18 passing suite that hid two real bugs.
"""
import importlib.util
import json
import os
import subprocess
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "warn-status-read-after-pipe.py")

spec = importlib.util.spec_from_file_location("hook", HOOK)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

failures = []


def check(label, got, want):
    if got != want:
        failures.append(f"{label}: got {got!r}, want {want!r}")


def fires(command, module=hook):
    """True when the matcher finds a `$?` read directly after a pipeline."""
    return module.find_misread(command) is not None


def run_hook(command, tool_name="Bash"):
    payload = json.dumps({
        "tool_name": tool_name,
        "tool_input": {"command": command},
    })
    return subprocess.run([sys.executable, HOOK], input=payload,
                          capture_output=True, text=True, timeout=10)


# ---------------------------------------------------------------------------
# POSITIVES -- the shape the guard exists for.
# ---------------------------------------------------------------------------

# The measured incident, ai-config#2149. `head` succeeded, the checker did not.
INCIDENT = ('python3 scripts/check-pr-fully-clean.py 111 '
            '-R UCD-SERG/ucd-serg.github.io 2>&1 | head -20; echo "exit=$?"')
check("the measured incident fires", fires(INCIDENT), True)

check("rc=$? after a pipe fires",
      fires("python3 check.py | head -20; rc=$?"), True)

check("unquoted echo $? after a pipe fires",
      fires("make test | tail -5; echo $?"), True)

check("a test bracket on $? after a pipe fires",
      fires("cmd | tail -1; [ $? -eq 0 ] && echo ok"), True)

check("`test` on $? after a pipe fires",
      fires("cmd | tail -1; test $? -eq 0"), True)

# `&&` ends the segment, so the pipeline is still the immediate predecessor.
check("$? after a piped && chain fires",
      fires("cmd | grep -q x && echo $?"), True)

# A newline separates segments exactly as `;` does.
check("newline-separated $? after a pipe fires",
      fires('cmd | jq .\necho "exit=$?"'), True)

# Multi-stage pipelines are the same defect.
check("multi-stage pipeline fires",
      fires('cmd | grep x | wc -l; echo "rc=$?"'), True)

# The `|| rc=$?` capture idiom attached to a pipeline. This is the single hit
# from the corpus-wide negative control (705 fenced shell blocks, 1 fired), and
# it is a true positive by `errexit-is-not-uniform.md`'s own detector list,
# which says to flag `|| fallback` attached to a pipeline with no `pipefail`.
check("the || capture idiom on a pipeline fires",
      fires("git diff --cached --name-only | grep -qE '^R/.*\\.R$' || rc=$?"),
      True)


# ---------------------------------------------------------------------------
# NEGATIVES -- each names what it protects.
# ---------------------------------------------------------------------------

# `pipefail` makes the pipeline take the rightmost NON-ZERO status, so the read
# is correct and the warning would be noise.
check("set -o pipefail suppresses",
      fires('set -o pipefail; cmd | head -20; echo "exit=$?"'), False)

check("set -euo pipefail suppresses",
      fires("set -euo pipefail\ncmd | head -20\nrc=$?"), False)

# The author has taken control of the pipeline's per-stage status explicitly.
check("PIPESTATUS suppresses",
      fires("cmd | head -20; rc=${PIPESTATUS[0]}"), False)

# No pipe: `$?` is the command's own status and reading it is the correct move.
check("$? with no pipe does not fire",
      fires('python3 check.py 111; echo "exit=$?"'), False)

check("$? after a redirect does not fire",
      fires('python3 check.py >/tmp/out.txt 2>&1; rc=$?; head -20 /tmp/out.txt'),
      False)

# A pipe with no status read is just a pipe.
check("a pipe with no $? does not fire",
      fires("cmd | head -20"), False)

# An intervening command owns the status, so the read is correct.
check("an intervening command does not fire",
      fires("cmd | head -20; git status --short; echo $?"), False)

# `||` is a separator, not a pipe. Reading this wrong would fire on most
# fallback idioms in the corpus.
check("|| is not a pipe",
      fires("cmd1 || cmd2; echo $?"), False)

# Inside single quotes the shell expands nothing, so this is documentation.
# `shared/coding/errexit-is-not-uniform.md` writes exactly this line.
check("documentation inside single quotes does not fire",
      fires("""bash -c 'set -eu; false | tail -1 || echo FALLBACK; echo "rc=$?"'"""),
      False)

# A `|` inside single quotes is a regex alternation, not a pipe.
check("alternation in single quotes is not a pipe",
      fires("grep -E 'a|b' file.txt; echo $?"), False)

check("awk field separator is not a pipe",
      fires("awk -F'|' '{print $1}' data.txt; echo $?"), False)

# A `|` inside double quotes is literal text, not a pipe.
check("a pipe character in double quotes is not a pipe",
      fires('echo "a | b"; echo $?'), False)

# A heredoc BODY is content being written, not a value being consumed. This is
# the deliberate call: writing `$?` into a file is not reasoning from a misread
# status, and this corpus writes such snippets to disk routinely.
HEREDOC_QUOTED = (
    "cat <<'EOF' > note.md\n"
    'cmd | head -20; echo "exit=$?"\n'
    "EOF\n"
)
check("a quoted heredoc body does not fire", fires(HEREDOC_QUOTED), False)

HEREDOC_BARE = (
    "cat <<EOF > note.md\n"
    'cmd | head -20; echo "exit=$?"\n'
    "EOF\n"
)
check("an unquoted heredoc body does not fire either",
      fires(HEREDOC_BARE), False)

# A `\$` inside double quotes is a literal dollar, so no expansion happens.
check("an escaped dollar in double quotes does not fire",
      fires('cmd | head -20; echo "literal \\$? here"'), False)

# `$?` before the pipeline reads something earlier; the ordering rule holds.
check("$? preceding the pipeline does not fire",
      fires('echo "$?"; cmd | head -20'), False)

# Nothing at all to match.
check("an unrelated command does not fire",
      fires("git status --short"), False)


# ---------------------------------------------------------------------------
# END-TO-END -- payload handling and output shape.
# ---------------------------------------------------------------------------

proc = run_hook(INCIDENT)
check("firing command exits 0", proc.returncode, 0)
check("firing command prints no traceback", "Traceback" in proc.stderr, False)
payload = json.loads(proc.stdout)
check("emits PreToolUse context",
      payload["hookSpecificOutput"]["hookEventName"], "PreToolUse")
check("carries additionalContext",
      "pipefail" in payload["hookSpecificOutput"]["additionalContext"], True)
check("never emits permissionDecision",
      "permissionDecision" in payload["hookSpecificOutput"], False)
check("never denies", "permissionDecision" in proc.stdout, False)

proc = run_hook("git status --short")
check("non-firing command prints nothing", proc.stdout.strip(), "")
check("non-firing command exits 0", proc.returncode, 0)

proc = run_hook(INCIDENT, tool_name="Read")
check("non-Bash tool is ignored", proc.stdout.strip(), "")

for label, body in [
    ("non-dict tool_input",
     {"tool_name": "Bash", "tool_input": "not-a-dict"}),
    ("non-string command", {"tool_name": "Bash", "tool_input": {"command": 42}}),
    ("missing command", {"tool_name": "Bash", "tool_input": {}}),
    ("empty object", {}),
]:
    proc = subprocess.run([sys.executable, HOOK], input=json.dumps(body),
                          capture_output=True, text=True, timeout=10)
    check(f"{label} exits 0", proc.returncode, 0)
    check(f"{label} prints nothing to stdout", proc.stdout.strip(), "")
    check(f"{label} prints no traceback", "Traceback" in proc.stderr, False)

proc = subprocess.run([sys.executable, HOOK], input="{not json",
                      capture_output=True, text=True, timeout=10)
check("unreadable input exits 0", proc.returncode, 0)
check("unreadable input prints nothing to stdout", proc.stdout.strip(), "")


# ---------------------------------------------------------------------------
# MUTATION -- break each load-bearing rule and confirm a test goes red.
# ---------------------------------------------------------------------------

def load_mutant(old, new):
    """Re-load the hook with one deliberate edit applied."""
    with open(HOOK, encoding="utf-8") as handle:
        source = handle.read()
    if old not in source:
        failures.append(f"mutation anchor not found: {old!r}")
        return None
    module = types.ModuleType("mutant")
    module.__file__ = HOOK
    exec(compile(source.replace(old, new, 1), HOOK, "exec"), module.__dict__)
    return module


# 1. Break the pipe test. The "no pipe" negative must start firing; if it does
#    not, that test was never exercising pipe detection.
mutant = load_mutant('        if not previous["has_pipe"]:',
                     "        if False:")
if mutant is not None:
    check("MUTATION pipe-test: no-pipe negative goes red",
          fires('python3 check.py 111; echo "exit=$?"', mutant), True)
    check("MUTATION pipe-test: the incident still fires",
          fires(INCIDENT, mutant), True)

# 2. Break the pipefail suppression. The pipefail negative must start firing.
mutant = load_mutant('if any("pipefail" in s["text"]',
                     'if any(False and "pipefail" in s["text"]')
if mutant is not None:
    check("MUTATION pipefail: pipefail negative goes red",
          fires('set -o pipefail; cmd | head -20; echo "exit=$?"', mutant),
          True)

# 3. Break the single-quote exclusion. Documentation must start firing.
mutant = load_mutant('        if quote == "\'":', "        if False:")
if mutant is not None:
    check("MUTATION single-quote: documentation goes red",
          fires("""bash -c 'false | tail -1; echo "rc=$?"'""", mutant), True)

if failures:
    print("FAILED:")
    for line in failures:
        print("  " + line)
    sys.exit(1)
print("all tests passed")
