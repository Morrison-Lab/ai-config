#!/usr/bin/env python3
"""Regression tests for compare-shell-forms.py.

Test case number one is the incident that prompted the tool, copied verbatim
rather than retyped or tidied, per `algorithmatize-checks.md`'s rule that a
guard is validated against the reported input and not against a summary of it.

Every command literal below is built from a RAW string. Nested escaping is the
exact bug this whole tool exists to measure, and it has already corrupted this
material three times, so the literals must not pass through an escape layer on
their way into the test.

The end-to-end cases really do spawn bash. That is deliberate: the value of this
tool is that it applies exactly one shell layer, and only a real run can show
that it does.
"""
import importlib.util
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

spec = importlib.util.spec_from_file_location(
    "compare_shell_forms", Path(__file__).parent / "compare-shell-forms.py"
)
csf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(csf)

passes = 0
failures = 0


def check(name, condition):
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}")
        failures += 1


def run_all(commands):
    """Run every form through the real pipeline and return (results, verdict)."""
    bash = csf.find_bash()
    if bash is None:
        return None, None
    env = csf.interpreter_env()
    with tempfile.TemporaryDirectory(prefix="shellforms-test-") as workdir:
        results = [
            csf.run_form(cmd, bash, env, workdir, i)
            for i, cmd in enumerate(commands, start=1)
        ]
    return results, csf.classify(results)


# --- 1. The incident, verbatim -------------------------------------------
# PR #1304's reproduction command. The four-backslash spelling does NOT
# reproduce the corruption the prose promises; the two-backslash one does.
# A reviewer flagged this twice and was rebutted from a measurement taken
# through a harness that added a second shell, which collapsed the doubled
# pair again and made the two forms indistinguishable.
FOUR = r'''python -c "print(repr('            if pat == r\"changes\\\\s+requested\\\\b\":'))"'''
TWO = r'''python -c "print(repr('            if pat == r\"changes\\s+requested\\b\":'))"'''

# Probes for the host-dependent warning case below. They are SEPARATE commands
# rather than flags added to TWO, because TWO is the incident copied verbatim
# and reproducing it exactly is what that case is for -- adding `-W` to it
# would test a command nobody ran.
PYVER_PROBE = r'''python -c "import sys; print('PYVER=%d.%d' % sys.version_info[:2])"'''
FORCED_WARN = r'''python -W always -c "print('x\s')"'''


def _parse_pyver(stdout):
    """(major, minor) of the interpreter the SHELL FORMS invoke, or None."""
    for line in stdout.splitlines():
        if line.startswith("PYVER="):
            try:
                major, minor = line[len("PYVER="):].strip().split(".")
                return int(major), int(minor)
            except ValueError:
                return None
    return None

results, verdict = run_all([FOUR, TWO])

if results is None:
    print("SKIP: bash unavailable, end-to-end cases not run")
else:
    check("the incident's two spellings are reported DIFFERING", verdict == csf.DIFFERING)

    four, two = results[0], results[1]

    # The four-backslash form: Python receives an escaped backslash, so the
    # literal survives and nothing warns. This is the form that does NOT
    # reproduce, which is the whole finding.
    check(
        "four backslashes leave a literal backslash-b in the output",
        r"requested\\b" in four["stdout"],
    )
    check(
        "four backslashes produce no backspace",
        r"\x08" not in four["stdout"],
    )
    check(
        "four backslashes produce no SyntaxWarning",
        "SyntaxWarning" not in four["stderr"],
    )

    # The two-backslash form: Python receives \b, which is a backspace, and \s,
    # which is not a valid escape and therefore warns. This form reproduces.
    check(
        "two backslashes produce a backspace",
        r"requested\x08" in two["stdout"],
    )
    # Which warning the interpreter emits for `\s` is a property of the HOST,
    # not of the two shell forms this file exists to compare. Python 3.12
    # promoted an invalid escape sequence from DeprecationWarning to
    # SyntaxWarning, and the two differ in default visibility as well as in
    # class: a SyntaxWarning prints on a default run, a DeprecationWarning does
    # not. So `"SyntaxWarning" in stderr` passed on CI's pinned 3.12 and failed
    # on any older interpreter -- the same file, the same assertions, a
    # different branch, with nothing in the output saying so (ai-config#1382).
    #
    # Note the subject is the `python` the SHELL FORM invokes, which need not be
    # the `python3` running this file, so the version is probed through the same
    # pipeline rather than read from this process's own sys.version_info.
    probe, _ = run_all([PYVER_PROBE])
    subject = _parse_pyver(probe[0]["stdout"]) if probe else None
    check("the subject interpreter's version is knowable", subject is not None)

    # Host-INDEPENDENT, and the load-bearing half: whatever the class, the
    # interpreter says the escape is invalid once warnings are made visible.
    forced, _ = run_all([FORCED_WARN])
    check(
        "the invalid escape is reported on every interpreter, once warnings show",
        forced is not None and "invalid escape sequence" in forced[0]["stderr"],
    )

    # Host-DEPENDENT, with BOTH branches pinned rather than one asserted and the
    # other left to chance.
    if subject is not None and subject >= (3, 12):
        check(
            f"on {subject[0]}.{subject[1]} (>= 3.12) the default run shows SyntaxWarning",
            "SyntaxWarning" in two["stderr"],
        )
    else:
        check(
            f"on {subject[0]}.{subject[1]} (< 3.12) it is a DeprecationWarning, "
            "hidden on a default run",
            "SyntaxWarning" not in two["stderr"]
            and forced is not None
            and "DeprecationWarning" in forced[0]["stderr"],
        )

# --- 2. An identical pair -------------------------------------------------
# Two different spellings with the same observable behaviour must compare
# IDENTICAL, or the tool cries wolf and stops being run.
    _, same_verdict = run_all(["echo hi", r'printf "%s\n" hi'])
    check("two equivalent spellings compare IDENTICAL", same_verdict == csf.IDENTICAL)

# --- 3. An induced harness failure ---------------------------------------
# A form that never ran must not be reported as a result about the forms.
    _, broken_verdict = run_all(["echo hi", "definitely_no_such_binary_xyz hi"])
    check(
        "a missing binary is HARNESS FAILURE, not DIFFERING",
        broken_verdict == csf.HARNESS_FAILURE,
    )

# The nastier direction: when BOTH forms fail the same way their signatures
# match exactly, so a naive implementation reports IDENTICAL. That is the
# false all-clear this outcome exists to prevent.
    _, both_broken = run_all(
        ["definitely_no_such_binary_xyz a", "definitely_no_such_binary_xyz b"]
    )
    check(
        "two identically-failing forms are HARNESS FAILURE, not IDENTICAL",
        both_broken == csf.HARNESS_FAILURE,
    )

# --- 4. Per-component isolation ------------------------------------------
# Each of these differs in exactly ONE component of the comparison signature,
# so dropping that component from `classify` flips this case and nothing else.

    # stderr only: same stdout, same exit status.
    _, stderr_only = run_all(["echo x", "echo x; echo warn >&2"])
    check(
        "forms differing only in stderr compare DIFFERING",
        stderr_only == csf.DIFFERING,
    )

    # exit status only: same (empty) stdout and stderr. This also pins the
    # narrow harness-failure rule -- `false` exits 1 on its own terms and must
    # be COMPARED, not written off as a broken run.
    _, rc_only = run_all(["true", "false"])
    check(
        "forms differing only in exit status compare DIFFERING",
        rc_only == csf.DIFFERING,
    )
    check(
        "a legitimate non-zero exit is not a harness failure",
        not csf.looks_like_harness_failure(1, ""),
    )

# --- 5. Pure classification units ----------------------------------------
# These need no subprocess, so they still run if bash is missing.
OK = {"command": "c", "returncode": 0, "stdout": "a", "stderr": "",
      "harness_failure": False}
OK2 = dict(OK, stdout="b")
BROKEN = dict(OK, harness_failure=True)

check("classify: matching signatures are IDENTICAL", csf.classify([OK, dict(OK)]) == csf.IDENTICAL)
check("classify: differing stdout is DIFFERING", csf.classify([OK, OK2]) == csf.DIFFERING)
check("classify: any harness failure dominates", csf.classify([OK, BROKEN]) == csf.HARNESS_FAILURE)
check("classify: no results is HARNESS FAILURE", csf.classify([]) == csf.HARNESS_FAILURE)
check("127 is a harness failure", csf.looks_like_harness_failure(127, ""))
check("126 is a harness failure", csf.looks_like_harness_failure(126, ""))
# A command's OWN failure is a result, not a broken harness. `grep pat
# missing.txt` prints a not-found message and exits 2; reporting that as
# "not a result about the forms" hides a real difference between two
# spellings, which is what narrowing the exit-code rule was for in the first
# place. The marker must not fire on its own.
check(
    "a not-found message alone is NOT a harness failure",
    not csf.looks_like_harness_failure(2, "grep: missing.txt: No such file or directory"),
)
check(
    "a command's own non-zero exit is NOT a harness failure",
    not csf.looks_like_harness_failure(1, ""),
)
check(
    "bash's own not-found still is, via 127",
    csf.looks_like_harness_failure(127, "bash: foo: command not found"),
)

# The report must state what it examined, not only what it found.
check(
    "render reports the number of forms compared",
    "forms compared: 2" in csf.render([OK, OK2], csf.DIFFERING),
)
check(
    "render makes a harness failure unmistakable",
    "NOT a result about the forms" in csf.render([OK, BROKEN], csf.HARNESS_FAILURE),
)

print(f"\n{passes} passed, {failures} failed")
sys.exit(0 if failures == 0 else 1)
