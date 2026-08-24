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
deliberately broken matcher is not testing the matcher, so each load-bearing
rule is broken on purpose and asserted to change a result: the pipe test, the
`pipefail` suppression, the `PIPESTATUS` suppression, the `&` redirect
carve-out, the single-quote exclusion, the comment skip, the assignment
carve-out, and the in-paren separator guard.
`memories/regex-negation-needs-adversarial-tests` records the case that
motivated this: an 18-of-18 passing suite that hid two real bugs.

Two of these mutate a POSITIVE into a miss rather than a negative into a fire,
which is the direction that catches an over-broad carve-out.
"""
import importlib.util
import json
import os
import shutil
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


def reported(command, module=hook):
    """The (pipeline, read) pair the matcher would name, or None.

    `fires()` collapses the tuple, which makes the suite blind to a garbled
    diagnostic --- the hook naming a pipeline that does not exist. Adversarial
    review caught exactly that (a phantom `1 | head -20` recovered from the
    tail of `2>&1`), so the archetype asserts the pair rather than the bool.
    """
    return module.find_misread(command)


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

# The DIAGNOSTIC, not just the verdict. `2>&1` must not be mistaken for a
# segment separator, which would recover a phantom pipeline of `1 | head -20`.
check("the incident names the real pipeline",
      reported(INCIDENT)[0],
      "python3 scripts/check-pr-fully-clean.py 111 "
      "-R UCD-SERG/ucd-serg.github.io 2>&1 | head -20")
check("the incident names the real read", reported(INCIDENT)[1],
      'echo "exit=$?"')

# Redirects containing `&` are not separators. Each of these is a real misread
# that a naive `&` split would report as quiet.
check("a trailing 2>&1 after the pipeline fires",
      fires("cmd | head -20 2>&1; echo $?"), True)
check("1>&2 after the pipeline fires",
      fires("cmd | grep x 1>&2; echo $?"), True)
check("&> after the pipeline fires",
      fires("cmd | head -20 &> /tmp/out; echo $?"), True)
check("|& is a pipe, not a separator",
      fires("cmd |& head -20; echo $?"), True)

# A trailing `|` continues the pipeline onto the next line.
check("a pipeline continued across lines fires",
      fires("cmd |\n  head -20\necho $?"), True)

# `${?}` is the same read spelled differently.
check("${?} after a pipe fires",
      fires("cmd | head -20; echo ${?}"), True)

# Merely naming the option does not disarm the guard, in any of the ways this
# corpus names it. Every one of these was quiet under a looser suppression
# test, and every one is a genuine misread.
check("grepping for the word pipefail still fires",
      fires('grep -rn pipefail hooks/ | head -20; echo "exit=$?"'), True)
check("grepping for PIPESTATUS still fires",
      fires("rg PIPESTATUS shared/ | head -5; rc=$?"), True)
check("a quoted mention of set -o pipefail still fires",
      fires('grep -rn "set -o pipefail" hooks/; cmd | head -20; echo $?'),
      True)
check("echoing a reminder about pipefail still fires",
      fires('echo "remember to set -o pipefail"; cmd | head -20; echo $?'),
      True)
check("an earlier PIPESTATUS read still fires",
      fires("rc=${PIPESTATUS[0]}; cmd | head -20; echo $?"), True)
check("the bare word PIPESTATUS still fires",
      fires("echo PIPESTATUS; cmd | head -20; echo $?"), True)

# The two cases above are true but NOT discriminating: each passes against a
# hook with the relevant guard degraded, because something else already keeps
# it quiet. Review caught that. These two separate the guards.
#
# Needs RX_PIPESTATUS to require a real `$` expansion: with a bare-word
# matcher the word in the READING segment would suppress.
check("the word PIPESTATUS in the reading segment still fires",
      fires('cmd | head -20; echo "$? PIPESTATUS"'), True)
# Needs the quote strip: `set` IS at a command position here, and only
# stripping the quoted argument removes the `pipefail` inside it.
check("set with a quoted pipefail argument still fires",
      fires('set -- "set -o pipefail"; cmd | head -20; echo $?'), True)

# `local`/`export`/`declare`/`readonly` are COMMANDS, so `$?` is the builtin's
# status and `pipefail` does not flip it. Measured, `export OUT=$(... | cat);
# echo $?` gives 0 with and without `pipefail`. Warning here would name a
# mechanism that is not operating and offer two remedies that do not work.
for keyword in ("local", "export", "declare", "readonly"):
    check(f"{keyword} before an assignment does not fire",
          fires(f"{keyword} OUT=$(cmd | tail -1); echo $?"), False)

# An assignment used as a command PREFIX: the following command's status wins.
# Measured, `V=$(echo x | grep -q zzz) true; echo $?` gives 0 for `true`.
check("an assignment used as a command prefix does not fire",
      fires("V=$(echo x | grep -q zzz) true; echo $?"), False)

# A comment is not a command and does not set `$?`, so a comment sitting
# between the pipeline and the read must not hide the pipeline. Measured,
# `cmd | head -20` then a comment line then `echo $?` reports the pipeline's
# status. The round-2 comment skip introduced this miss.
check("a comment between the pipeline and the read still fires",
      fires("cmd | head -20\n# why\necho $?"), True)

# `pipefail` set inside the subshell IS in force -- measured rc=1.
check("set -o pipefail inside a subshell suppresses",
      fires("( set -o pipefail; cmd | head -20 ); echo $?"), False)

# ...but only for pipes that subshell actually encloses. Each of these carries
# a real `set -o pipefail` whose scope EXCLUDES the pipe, and each measured 0
# without an outer pipefail and 1 with one, so each is a genuine misread.
check("pipefail scoped to a subshell the pipe is outside still fires",
      fires("(set -o pipefail; make) | tail -20; echo $?"), True)
check("pipefail in a nested group the pipe is outside still fires",
      fires("( ( set -o pipefail ); cmd | head ); echo $?"), True)
check("pipefail in an earlier subshell still fires",
      fires("( set -o pipefail; true ); cmd | head; echo $?"), True)

# `set -o pipefail` need not be the group's FIRST command. Measured,
# `( true; set -o pipefail; grep -q zzz /dev/null | cat ); echo $?` gives 1,
# so the option is in force and a warning would be false.
check("pipefail later in the group suppresses",
      fires("( true; set -o pipefail; cmd | head ); echo $?"), False)
check("pipefail after set -e in the group suppresses",
      fires("( set -e; set -o pipefail; cmd | head ); echo $?"), False)

# Anything paren-bearing before the `set` must not truncate the search. Each
# of these measures rc=1, so the read is correct and a warning would be false.
# An earlier scan stopped at the first `(` or `)` of any kind and warned on
# all of them.
for prefix in ('cd "$(dirname /tmp/x)"', "n=$((1+1))", "(true)",
               "arr=(a b)", ": $(echo x)", "echo $((2*3))"):
    check(f"pipefail after `{prefix}` in the group suppresses",
          fires(f"( {prefix}; set -o pipefail; cmd | head ); echo $?"), False)

# ...but a nested group's option still must not protect the parent, in either
# spelling. Both measure rc=0.
check("pipefail in a nested group does not suppress",
      fires("( ( set -o pipefail ); cmd | head ); echo $?"), True)
check("pipefail after a command in a nested group does not suppress",
      fires("( ( a; set -o pipefail ); cmd | head ); echo $?"), True)

# A backgrounded `set` runs in a subshell and never reaches the caller.
# Measured rc=0, so this is a real misread.
check("a backgrounded set -o pipefail does not suppress",
      fires("( set -o pipefail & cmd | head ); echo $?"), True)

# Arithmetic does not set `$?`, so it must not shadow a following read.
# Measured, `true | false; echo "n=$((1+1)) rc=$?"` prints rc=1.
check("arithmetic in double quotes does not shadow the read",
      fires('cmd | head -20; echo "n=$((1+1)) rc=$?"'), True)
check("bare arithmetic does not shadow the read",
      fires("cmd | head -20; n=$((1+1)); echo $?"), False)

# An escaped quote inside a substitution must not abort the whole scan. This
# silenced everything downstream of it for one round.
check("an escaped quote inside a substitution does not disarm the scan",
      fires('echo "$(printf %s \\\')" ; cmd | head -20; echo "rc=$?"'), True)

# An unbalanced substitution must degrade locally, not disarm the command.
check("an unbalanced substitution does not disarm the scan",
      fires('echo "$(oops" ; cmd | head -20; echo "rc=$?"'), True)

# A `$?` following a command substitution reads the SUBSTITUTION's status, not
# any earlier pipeline. Measured: `true | cat; echo "x $(exit 7) (rc=$?)"`
# prints rc=7. Not tracking substitutions inside double quotes produced this
# guard's one measured false positive, on fail-fast.md's own example.
check("a $? after a substitution in double quotes does not fire",
      fires('cmd | head -20; echo "n=$(wc -l < f) rc=$?"'), False)
check("fail-fast.md's own example does not fire",
      fires('grep -q PATTERN file | head\n'
            'echo "hits: $(wc -l < out.txt) (rc=$?)"'), False)
check("a $? after an unquoted substitution does not fire",
      fires("cmd | head -20; echo $(wc -l < f) $?"), False)

# Two assignments in one segment: the LAST substitution owns the status, so
# the pipeline in the first does not. Measured 0 with and without pipefail.
check("a second assignment in the segment does not fire",
      fires("out=$(cmd | head -1) other=$(true); echo $?"), False)

# A trailing redirect does not change whose status `$?` reports.
check("an assignment with a trailing redirect still fires",
      fires("out=$(cmd | head -1) 2>/dev/null; echo $?"), True)

# Bare `(( ))` arithmetic: `|` is bitwise OR, not a pipe.
check("bare arithmetic is not a pipe",
      fires("(( x = a | b )); echo $?"), False)

# Extglob alternation is not a pipe.
check("extglob alternation is not a pipe",
      fires("ls @(a|b); echo $?"), False)
check("negated extglob alternation is not a pipe",
      fires("rm -- !(keep|also); echo $?"), False)

# A command substitution on the right of an ASSIGNMENT takes the pipeline's
# own status, so this is the target bug rather than an exclusion. Measured:
#   out=$(grep -q zzz /dev/null | cat); echo $?              -> 0
#   set -o pipefail; out=$(grep -q zzz /dev/null | cat)      -> 1
check("a pipeline assigned from a substitution fires",
      fires("out=$(cmd | head -1); echo $?"), True)
check("an array-element assignment from a substitution fires",
      fires("arr[0]=$(cmd | tail -1); echo $?"), True)
check("an appending assignment from a substitution fires",
      fires("out+=$(cmd | tail -1); echo $?"), True)

# A bare subshell's status is its last command's, so a pipeline inside one
# reads exactly as a top-level pipeline does.
check("a pipeline inside a bare subshell fires",
      fires("( cmd | head -20 ); echo $?"), True)

# Comments are the third prose surface. A comment CORRECTLY describing this
# bug must not trip the guard that enforces it.
check("a comment mentioning $? does not fire",
      fires("make test | tail -5\n# TODO capture $? properly\necho ok"), False)
check("a comment explaining the bug does not fire",
      fires("python3 x.py | head -20\n# note: $? is head's here\ntrue"), False)

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

# The `|| rc=$?` capture idiom attached to a pipeline. One of the two hits
# from the corpus-wide negative control (645 fenced blocks, 8 discriminating,
# 2 fired -- see the hook docstring for the method and for the false positive
# an earlier run of it reported), and a true positive by
# `errexit-is-not-uniform.md`'s own detector list, which says to flag
# `|| fallback` attached to a pipeline with no `pipefail`.
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
#
# NOTE the shape of this case. The obvious spelling --- `cmd | head -20;
# rc=${PIPESTATUS[0]}` --- contains no `$?` at all, so it is quiet whether or
# not the PIPESTATUS guard exists, and asserting on it tests nothing. Review
# caught that vacuity; this version carries a real `$?` beside the
# `${PIPESTATUS[0]}`, so only the guard keeps it quiet.
check("PIPESTATUS in the reading segment suppresses",
      fires('cmd | head -20; echo "$? and ${PIPESTATUS[0]}"'), False)

# The vacuous form stays in the suite as a regression marker, labelled so that
# nobody later mistakes it for coverage of the guard.
check("PIPESTATUS alone is quiet (vacuous: contains no $?)",
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

# A `|` that is not a pipeline. Each was measured against bash: the status
# `$?` reports belongs to the outer command, so a warning would assert
# something false.
check("process substitution is not a pipe",
      fires("diff <(sort a | cat) <(sort b | cat); echo $?"), False)

# A command substitution used as an ARGUMENT: the outer command's status wins.
check("command substitution as an argument is not a pipe",
      fires('echo "$(cmd | head -1)"; echo $?'), False)

# A nested bare group inside a substitution must not desynchronize the paren
# stack. Under a counter these fired, naming a pipeline with an unbalanced `)`.
# Label matches the assertion: this one FIRES. The assignment substitution
# owns the status, so it is a genuine instance; what the nested bare group
# must not do is desynchronize the paren stack and produce an unbalanced `)`
# in the diagnostic.
check("a nested group inside an assignment substitution fires cleanly",
      fires("out=$( (cd /tmp) ; cat f | head -1 ); echo $?"), True)
check("...and its diagnostic has balanced parens",
      reported("out=$( (cd /tmp) ; cat f | head -1 ); echo $?")[0].count("(")
      == reported("out=$( (cd /tmp) ; cat f | head -1 ); echo $?")[0].count(")"),
      True)
check("a nested group inside process substitution stays quiet",
      fires("diff <( (cd /tmp); sort a | uniq ) <(sort b); echo $?"), False)

# Arithmetic is not a substitution and carries no pipe.
check("arithmetic expansion is not a pipe",
      fires("n=$(( 1 + 2 )); echo $?"), False)

check("regex alternation inside [[ ]] is not a pipe",
      fires("[[ $x =~ ^(a|b)$ ]]; echo $?"), False)

check("the noclobber redirect >| is not a pipe",
      fires("cmd >| /tmp/out; echo $?"), False)

# Backgrounding: `$?` is the async launch's status, not the pipeline's.
check("a backgrounded pipeline does not fire",
      fires("cmd | head -20 & echo $?"), False)

# Nothing at all to match.
check("an unrelated command does not fire",
      fires("git status --short"), False)

# Documented blind spots. These ARE the bug and the guard misses them, which
# is a deliberate limit rather than an oversight -- catching them means parsing
# shell compound statements. Asserted so the limit is visible and so a later
# implementation that fixes one turns this line red on purpose.
for label, command in [
    ("for loop", "for f in 1; do cmd | head; done; echo $?"),
    ("if block", "if true; then cmd | head; fi; echo $?"),
    ("brace group", "{ cmd | head; }; echo $?"),
    # The whole-segment assignment guards cost these three. Each is a real
    # misread (measured 0 without `pipefail`, 1 with it). Recorded rather than
    # fixed: tightening the guards is what stopped the false positives above,
    # and for a warn-only hook a miss is the cheap direction.
    ("nested substitution in an assignment",
     "out=$(cmd | head -$(nproc)); echo $?"),
    ("arithmetic inside an assignment's substitution",
     "out=$(cmd | head -$((1+1))); echo $?"),
    ("a second assignment ahead of the substitution",
     "A=1 B=$(cmd | head -1); echo $?"),
    # `&>` is absent from the trailing-redirect group, while `>>log 2>&1` is
    # accepted.
    ("an &> redirect after an assignment",
     "out=$(cmd | head -1) &>/dev/null; echo $?"),
    # The read sits INSIDE the group holding the pipe, so there is no
    # preceding sibling segment to test.
    ("a read inside the group holding the pipe",
     "( cmd | head; echo $? )"),
    # The read is nested in a substitution, which the shadowing rule drops.
    ("a read nested inside a substitution",
     "cmd | head; echo $(echo $?)"),
    # A `pipefail` set in a BRACE group, which is not tracked like a paren
    # group. This one is a false POSITIVE rather than a miss: measured rc=1,
    # so the option is in force and the warning is wrong.
]:
    check(f"KNOWN BLIND SPOT: {label} is missed", fires(command), False)

check("KNOWN FALSE POSITIVE: pipefail in a brace group still warns",
      fires("{ set -o pipefail; }; cmd | head; echo $?"), True)


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
mutant = load_mutant("if any(RX_SET_PIPEFAIL.search(RX_QUOTED.sub(\" \", s[\"text\"]))",
                     "if any(False and RX_SET_PIPEFAIL.search(s[\"text\"])")
if mutant is not None:
    check("MUTATION pipefail: pipefail negative goes red",
          fires('set -o pipefail; cmd | head -20; echo "exit=$?"', mutant),
          True)

# 2b. Break the PIPESTATUS suppression on the reading segment. The
#     non-vacuous PIPESTATUS negative must start firing; the vacuous spelling
#     must NOT, which is what proves it was never testing this guard.
mutant = load_mutant('if RX_PIPESTATUS.search(segments[index]["text"]):',
                     "if False:")
if mutant is not None:
    check("MUTATION PIPESTATUS: the non-vacuous negative goes red",
          fires('cmd | head -20; echo "$? and ${PIPESTATUS[0]}"', mutant),
          True)
    check("MUTATION PIPESTATUS: the vacuous spelling stays quiet",
          fires("cmd | head -20; rc=${PIPESTATUS[0]}", mutant), False)

# 2c. Break the redirect carve-out for `&`. The archetype's diagnostic must
#     degrade to the phantom pipeline review found.
mutant = load_mutant('            if previous in ("<", ">"):\n'
                     "                i += 1\n"
                     "                continue\n",
                     "")
if mutant is not None:
    got = reported(INCIDENT, mutant)
    check("MUTATION redirect: the diagnostic degrades to a phantom pipeline",
          got is not None and got[0] == "1 | head -20", True)

# 3. Break the single-quote exclusion. Documentation must start firing.
mutant = load_mutant('        if quote == "\'":', "        if False:")
if mutant is not None:
    check("MUTATION single-quote: documentation goes red",
          fires("""bash -c 'false | tail -1; echo "rc=$?"'""", mutant), True)

# 4. Break the comment skip. A comment describing the bug must start firing.
mutant = load_mutant(
    '        if char == "#" and (i == 0 or text[i - 1] in " \\t\\n;&|("):',
    "        if False:")
if mutant is not None:
    check("MUTATION comment: a comment about $? goes red",
          fires("make test | tail -5\n# TODO capture $? properly\necho ok",
                mutant), True)

# 5. Break the assignment carve-out, so `$(` always hides. The assignment case
#    is a REAL instance, so mutating this turns a positive into a miss.
mutant = load_mutant(
    "            assigned = RX_ASSIGN_PREFIX.search(text[start:i]) is not None",
    "            assigned = False")
if mutant is not None:
    check("MUTATION assignment: the assigned pipeline is missed",
          fires("out=$(cmd | head -1); echo $?", mutant), False)

# 6. Break the in-paren separator guard. A `;` inside a substitution then ends
#    the outer segment and exposes an unbalanced `)` in the diagnostic.
mutant = load_mutant("        if parens:\n"
                     '            if two in ("&&", "||"):\n'
                     "                i += 2\n"
                     "                continue\n"
                     '            if char in ("&", ";", "\\n"):\n'
                     "                i += 1\n"
                     "                continue\n",
                     "")
if mutant is not None:
    # Without the guard, a `;` inside the substitution cuts the outer segment,
    # so the assignment is split across two segments, the whole-segment
    # assignment test no longer matches, and a genuine instance is missed.
    ASSIGN_NESTED = "out=$( (cd /tmp) ; cat f | head -1 ); echo $?"
    check("MUTATION paren separator: a real instance is missed",
          fires(ASSIGN_NESTED, mutant), False)
    check("MUTATION paren separator: the real hook catches it",
          fires(ASSIGN_NESTED), True)

# 7. Break the substitution shadowing. A `$?` that belongs to a substitution
#    must start being attributed to the pipeline again.
mutant = load_mutant(
    "                shadowed = any(begin <= close < offset "
    "for close in closes)",
    "                shadowed = False")
if mutant is not None:
    check("MUTATION shadowing: a substitution's own status is misattributed",
          fires('cmd | head -20; echo "n=$(wc -l < f) rc=$?"', mutant), True)

# 8. Break the per-group pipefail scope. A genuinely protected pipe must start
#    warning.
mutant = load_mutant(
    "            paren_pf.append(_paren_sets_pipefail(text, i))",
    "            paren_pf.append(False)")
if mutant is not None:
    check("MUTATION paren pipefail: a protected pipe warns",
          fires("( set -o pipefail; cmd | head -20 ); echo $?", mutant), True)

# 9. Break the single-`$(` guard on a whole-segment assignment. A second
#    assignment in the segment must start firing.
mutant = load_mutant('                          and body.count("$(") == 1\n',
                     "")
if mutant is not None:
    check("MUTATION single-subst: a second assignment fires",
          fires("out=$(cmd | head -1) other=$(true); echo $?", mutant), True)

# 10. Break the arithmetic carve-out in the DOUBLE-QUOTE branch, which is
#     where it was missing for a round.
mutant = load_mutant(
    "                if text[i + 2:i + 3] == \"(\":\n"
    "                    i += 3\n"
    "                    continue\n",
    "")
if mutant is not None:
    check("MUTATION quoted arithmetic: a real misread goes quiet",
          fires('cmd | head -20; echo "n=$((1+1)) rc=$?"', mutant), False)

# ---------------------------------------------------------------------------
# DIFFERENTIAL ORACLE -- ask bash instead of asking a reviewer.
# ---------------------------------------------------------------------------
# Three review rounds running, the fix for one round's finding produced the
# next round's finding, every time inside the `pipefail`-scope machinery. That
# is the recurrence `shared/principles/deterministic-tools.md` says to answer
# with an instrument rather than with more care, so the question is decided by
# running bash rather than by reasoning about it.
#
# The oracle: a `$?` read is a MISREAD exactly when prefixing the command with
# `set -o pipefail` changes the status it prints. If the answer moves, `$?` was
# reporting a pipeline's last stage; if it does not, `$?` belongs to something
# else and a warning would assert something false.
#
# `grep -q zzz /dev/null` is the producer throughout: it exits 1, reads no
# input, and cannot SIGPIPE, so `pipefail` is the only thing that can move the
# answer.
#
# EXCEPTIONS are the guard's known limits, listed with the direction of each.
# The point of naming them here rather than omitting the cases is that the
# oracle then reports any limit that is NOT on the list, including one
# introduced by a later edit.

PRODUCER = "grep -q zzz /dev/null"


def bash_says_misread(command):
    """True when `set -o pipefail` changes what the command prints."""
    plain = subprocess.run(["bash", "-c", command],
                           capture_output=True, text=True, timeout=10)
    guarded = subprocess.run(["bash", "-c", "set -o pipefail\n" + command],
                             capture_output=True, text=True, timeout=10)
    return plain.stdout != guarded.stdout


# (command, why it is exempt). Every entry was measured; each is a case the
# lexical scanner cannot decide without parsing shell properly.
KNOWN_LIMITS = {
    f"for f in 1; do {PRODUCER} | cat; done; echo $?":
        "miss: compound statement, `done` is the predecessor",
    f"if true; then {PRODUCER} | cat; fi; echo $?":
        "miss: compound statement, `fi` is the predecessor",
    f"{{ {PRODUCER} | cat; }}; echo $?":
        "miss: compound statement, `}` is the predecessor",
    f"{{ set -o pipefail; }}; {PRODUCER} | cat; echo $?":
        "FALSE POSITIVE: brace groups are not scope-tracked like parens",
    f"( {PRODUCER} | cat; echo $? )":
        "miss: the read is inside the group holding the pipe",
    f"{PRODUCER} | cat; echo $(echo $?)":
        "miss: the read is nested in a substitution",
    f"set -o pipefail & {PRODUCER} | cat; echo $?":
        "miss: top-level backgrounded `set`, mirror of the in-paren case",
    f"out=$({PRODUCER} | head -$(echo 1)); echo $?":
        "miss: nested substitution inside an assignment",
    f"A=1 B=$({PRODUCER} | cat); echo $?":
        "miss: a second assignment ahead of the substitution",
    f"out=$({PRODUCER} | cat) &>/dev/null; echo $?":
        "miss: `&>` is not in the trailing-redirect group",
    f"( if true; then set -o pipefail; fi; {PRODUCER} | cat ); echo $?":
        "FALSE POSITIVE: `set` inside a compound statement in the group",
}

ORACLE_CASES = [
    # Plain shapes the guard must get right.
    f"{PRODUCER} | cat; echo $?",
    f'{PRODUCER} | cat; echo "rc=$?"',
    # `rc=$?` alone prints nothing, so the oracle would see no difference and
    # wrongly call it not-a-misread. Echo the captured value.
    f"{PRODUCER} | cat; rc=$?; echo $rc",
    f"{PRODUCER} | cat; echo ${{?}}",
    f"{PRODUCER} | cat 2>&1; echo $?",
    f"{PRODUCER} |& cat; echo $?",
    f"{PRODUCER} | cat && echo $?",
    f"{PRODUCER} | cat\necho $?",
    f"{PRODUCER} |\n  cat\necho $?",
    f"{PRODUCER} | cat\n# a comment\necho $?",
    # Not a misread: no pipe, or the status belongs to something else.
    "true; echo $?",
    f"{PRODUCER}; echo $?",
    f"{PRODUCER} | cat; true; echo $?",
    f"{PRODUCER} | cat & echo $?",
    f'{PRODUCER} | cat; echo "n=$(wc -l < /dev/null) rc=$?"',
    f'{PRODUCER} | cat; echo "n=$((1+1)) rc=$?"',
    f"echo \"$({PRODUCER} | cat)\"; echo $?",
    "[[ x =~ ^(a|b)$ ]]; echo $?",
    "ls @(a|b) 2>/dev/null; echo $?",
    # `pipefail` in force, in each spelling.
    f"set -o pipefail; {PRODUCER} | cat; echo $?",
    f"( set -o pipefail; {PRODUCER} | cat ); echo $?",
    f"( true; set -o pipefail; {PRODUCER} | cat ); echo $?",
    f'( cd "$(dirname /tmp/x)"; set -o pipefail; {PRODUCER} | cat ); echo $?',
    f"( arr=(a b); set -o pipefail; {PRODUCER} | cat ); echo $?",
    f"( cd /tmp && set -o pipefail && {PRODUCER} | cat ); echo $?",
    f"( set -o pipefail &>/dev/null; {PRODUCER} | cat ); echo $?",
    f"(\n  # don't drop the status\n  set -o pipefail\n  {PRODUCER} | cat\n);"
    " echo $?",
    f"x=$(set -o pipefail; {PRODUCER} | cat); echo $?",
    # `pipefail` NOT in force, despite appearances.
    f"( ( set -o pipefail ); {PRODUCER} | cat ); echo $?",
    f"( ( a; set -o pipefail ); {PRODUCER} | cat ); echo $?",
    f"( set -o pipefail; true ); {PRODUCER} | cat; echo $?",
    # The producer must be INSIDE the protected group, or `pipefail` has
    # nothing to change and the oracle sees no difference for the wrong
    # reason.
    f"(set -o pipefail; {PRODUCER}) | cat; echo $?",
    f"( set -o pipefail & {PRODUCER} | cat ); echo $?",
    f'grep -rn "set -o pipefail" /dev/null; {PRODUCER} | cat; echo $?',
    f'echo "remember to set -o pipefail"; {PRODUCER} | cat; echo $?',
    # Assignment forms.
    f"out=$({PRODUCER} | cat); echo $?",
    f"out=$({PRODUCER} | cat) 2>/dev/null; echo $?",
    f"out=$({PRODUCER} | cat) other=$(true); echo $?",
    f"export OUT=$({PRODUCER} | cat); echo $?",
    f"V=$({PRODUCER} | cat) true; echo $?",
    f"( {PRODUCER} | cat ); echo $?",
]

# Every known limit is also an oracle case, so the exemption list cannot hold
# an entry nothing exercises.
ORACLE_CASES += [c for c in KNOWN_LIMITS if c not in ORACLE_CASES]

if shutil.which("bash") is None:
    print("NOTE: bash not on PATH; differential oracle skipped")
else:
    examined = agreed = exempt = 0
    for command in ORACLE_CASES:
        examined += 1
        try:
            expected = bash_says_misread(command)
        except Exception as exc:                      # pragma: no cover
            failures.append(f"ORACLE could not run {command!r}: {exc}")
            continue
        got = fires(command)
        if command in KNOWN_LIMITS:
            exempt += 1
            if got == expected:
                failures.append(
                    f"ORACLE: {command!r} is listed in KNOWN_LIMITS "
                    f"({KNOWN_LIMITS[command]}) but the guard now agrees with "
                    "bash -- remove the exemption")
            continue
        if got != expected:
            failures.append(
                f"ORACLE disagrees with bash on {command!r}: "
                f"bash says misread={expected}, guard fires={got}")
        else:
            agreed += 1
    # Report what was examined, not only what disagreed: a zero-disagreement
    # run and a harness that never ran leave the same evidence otherwise.
    print(f"differential oracle: {examined} shapes examined against bash, "
          f"{agreed} agreed, {exempt} exempt as known limits")

# Every KNOWN_LIMITS entry must actually be exercised, so the list cannot
# silently accumulate stale exemptions.
for command in KNOWN_LIMITS:
    if command not in ORACLE_CASES:
        failures.append(
            f"KNOWN_LIMITS entry is never run by the oracle: {command!r}")

if failures:
    print("FAILED:")
    for line in failures:
        print("  " + line)
    sys.exit(1)
print("all tests passed")
