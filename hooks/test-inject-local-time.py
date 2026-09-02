#!/usr/bin/env python3
"""Tests for hooks/inject-local-time.sh (ai-config#1080).

The hook prints the current Pacific time for the model to quote verbatim, and
must refuse to label a non-Pacific reading as local. Four cases:

  1. First rung: the `date` stub answers PDT only when the hook sets
     `TZ=America/Los_Angeles`, and GMT otherwise -- the output carries the
     Pacific reading plus the verbatim-use line.
  2. Second rung: the stub answers GMT under the TZ override and PDT when
     TZ is unset (a system zone that is already Pacific, the Git Bash
     shape) -- the hook must fall past the first rung and still print a
     Pacific reading.
  3. Third rung: the stub answers GMT either way, and a `powershell` stub
     answers PDT only when invoked as `-NoProfile -Command` with the
     Pacific-zone conversion program -- the hook must fall through both
     `date` rungs and still hand PowerShell the real conversion.
  4. Negative control: GMT either way plus a `powershell` stub that fails --
     the hook prints the UTC-only fallback and the explicit "do NOT state a
     PDT/PST time" warning, never a GMT value labelled local.

Every case runs against stubs rather than the ambient host, so the suite
passes and fails for the same reasons on macOS, on Ubuntu CI, and on a host
with no TZ database. Case 2 is the Git Bash shape ai-config#1918 measured,
where the TZ override answers GMT and the system zone is already Pacific.
Case 4 is what tells a hook that checks the zone from one that merely
prints whatever `date` said.
"""
import os
import re
import stat
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "inject-local-time.sh")
LOCAL = re.compile(r"^Current time -- local: \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} P[DS]T \| UTC: \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", re.M)
VERBATIM = "Use the local value verbatim in recaps."
FALLBACK = re.compile(r"^Current time -- UTC: \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z \(no Pacific reading available", re.M)
WARN = "Do NOT state a PDT/PST time in this turn without measuring it first."


def run(env):
    # An ambient TZ=America/Los_Angeles would make the plain `date` call look
    # like the override call to the stub, so the second-rung case could pass
    # without the hook ever falling past the first rung. Strip it.
    env = dict(env)
    env.pop("TZ", None)
    p = subprocess.run(["sh", HOOK], capture_output=True, text=True, env=env)
    return p.returncode, p.stdout


wrong = 0


def check(desc, cond):
    global wrong
    wrong += not cond
    print(f"  {'ok' if cond else 'WRONG':<6} {desc}")


def stubs(tz_answer, plain_answer, powershell_body):
    """A temp dir holding a `date` stub and a `powershell` stub for PATH.

    The `date` stub answers `tz_answer` when TZ is America/Los_Angeles,
    which is the hook's first rung.
    It answers `plain_answer` otherwise, which is the second rung,
    and the real UTC shape for `date -u`.
    The `powershell` stub runs `powershell_body` only for a
    `-NoProfile -Command <program>` call, exits 1 for anything else, and
    records the program beside itself for the whole-text comparison.
    Keying on TZ is what lets a case pin one rung:
    a stub that ignored TZ would pass the first-rung case identically
    if the hook skipped straight to the second."""
    d = tempfile.mkdtemp()
    date_stub = os.path.join(d, "date")
    with open(date_stub, "w") as fh:
        # The stub answers only for the two format strings the hook actually
        # passes, so dropping or mangling "$FMT" fails here rather than
        # returning the preformatted fixture regardless.
        fh.write("#!/bin/sh\n"
                 "if [ \"$1\" = -u ]; then\n"
                 "  [ \"$2\" = '+%%Y-%%m-%%dT%%H:%%M:%%SZ' ] || exit 1\n"
                 "  printf '2026-01-01T00:00:00Z\\n'; exit 0\n"
                 "fi\n"
                 "[ \"$1\" = '+%%Y-%%m-%%d %%H:%%M:%%S %%Z' ] || exit 1\n"
                 "if [ \"${TZ:-}\" = America/Los_Angeles ]; then printf '%s\\n'; else printf '%s\\n'; fi\n"
                 % (tz_answer, plain_answer))
    ps_stub = os.path.join(d, "powershell")
    with open(ps_stub, "w") as fh:
        # Answer only for the hook's invocation shape, and record the program
        # so the third-rung case can compare it whole against the expected
        # text (see EXPECTED_PS_PROGRAM); a fragment match let a rewired
        # argument through.
        fh.write("#!/bin/sh\n"
                 "[ \"$1\" = -NoProfile ] || exit 1\n"
                 "[ \"$2\" = -Command ] || exit 1\n"
                 "printf '%s' \"$3\" > \"$(dirname \"$0\")/ps-program\"\n"
                 + powershell_body + "\n")
    for f in (date_stub, ps_stub):
        os.chmod(f, os.stat(f).st_mode | stat.S_IXUSR)
    return d


def with_stubs(d):
    return dict(os.environ, PATH=d + os.pathsep + os.environ.get("PATH", ""))


# The hook's third-rung program, whitespace-normalised. A change to the hook's
# conversion is a change to this constant, which is the point: the stub cannot
# run PowerShell, so equality with the known-good program is the check.
EXPECTED_PS_PROGRAM = " ".join("""
        $tz = [System.TimeZoneInfo]::FindSystemTimeZoneById('Pacific Standard Time')
        $t  = [System.TimeZoneInfo]::ConvertTimeFromUtc([DateTime]::UtcNow, $tz)
        $z  = if ($tz.IsDaylightSavingTime($t)) { 'PDT' } else { 'PST' }
        '{0:yyyy-MM-dd HH:mm:ss} {1}' -f $t, $z
""".split())

PDT = "2026-01-01 00:00:00 PDT"
GMT = "2026-01-01 00:00:00 GMT"

print("first rung (only the TZ override answers PDT):")
rc, out = run(with_stubs(stubs(PDT, GMT, "exit 1")))
check("exit 0", rc == 0)
check("prints the Pacific local reading and the UTC reading", bool(LOCAL.search(out)))
check("prints the verbatim-use instruction", VERBATIM in out)
check("does not print the fallback warning", WARN not in out)

print("\nsecond rung (TZ override answers GMT, plain date answers PDT):")
rc, out = run(with_stubs(stubs(GMT, PDT, "exit 1")))
check("exit 0", rc == 0)
check("prints the Pacific reading the system zone supplied", bool(LOCAL.search(out)))
check("never labels the GMT reading as local", "GMT" not in out)

print("\nthird rung (both date rungs answer GMT, PowerShell answers PDT):")
d = stubs(GMT, GMT, "printf '%s\\n'" % PDT)
rc, out = run(with_stubs(d))
check("exit 0", rc == 0)
check("prints the Pacific reading PowerShell supplied", bool(LOCAL.search(out)))
check("never labels the GMT reading as local", "GMT" not in out)
with open(os.path.join(d, "ps-program")) as fh:
    program = " ".join(fh.read().split())
check("hands PowerShell the complete conversion program, compared whole",
      program == EXPECTED_PS_PROGRAM)

print("\nnegative control (both date rungs answer GMT, PowerShell fails):")
rc, out = run(with_stubs(stubs(GMT, GMT, "exit 1")))
check("exit 0 (a failed reading is reported, not a crash)", rc == 0)
check("prints the UTC-only fallback line", bool(FALLBACK.search(out)))
check("prints the do-NOT-state warning", WARN in out)
check("never labels the GMT reading as local", "local:" not in out and "GMT" not in out)

total = 15
print(f"\n{total - wrong}/{total} correct" + ("" if wrong == 0 else f"  ({wrong} WRONG)"))
sys.exit(1 if wrong else 0)
