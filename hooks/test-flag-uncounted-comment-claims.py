"""Tests for flag-uncounted-comment-claims.py.

Reproduces the incident it was named for (`Morrison-Lab/ai-config#2377`):
two `gh pr comment --body-file` posts, each asserting an enumerated file
list recalled from memory rather than derived, one of them wrong. The true-
positive fixture below reuses the incident's own wrong claim, paraphrased:
a "N files" cardinality claim and a hand-typed list of hyphenated script
names under the label "scripts".

Structured like its two siblings this hook reuses machinery from
(`test-remind-brief-premises.py` for the claim-detection unit checks,
`test-flag-uncited-rebuttal.py` for the end-to-end subprocess harness): one
guard clause isolated per case, so a failure names which clause broke rather
than "the hook is wrong somehow".

Run:  python3 hooks/test-flag-uncounted-comment-claims.py hooks/flag-uncounted-comment-claims.py
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

SUBJECT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "flag-uncounted-comment-claims.py")


def load(path):
    spec = importlib.util.spec_from_file_location("subject_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


failures = 0


def check(label, got, want):
    global failures
    if got != want:
        print(f"FAIL: {label}: got {got!r}, want {want!r}")
        failures += 1
    else:
        print(f"PASS: {label}")


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

# The incident, paraphrased: a wrong enumerated list AND a wrong count in
# one comment body, neither backed by a deriving command.
INCIDENT_BODY = (
    "The fingerprinted scripts: cycle-charge-flee / interval-labels / "
    "multi-unit-form-up-modes / group-attack, and 18 files on main."
)

# Ordinary prose this hook must stay silent on: an ARD disposition summary,
# which lists three dispositions with no hyphenated tokens and no
# listable-noun-plus-count claim.
ARD_SUMMARY = "Addressed, Rebutted, or Deferred every finding this round."

# A cardinality claim about a non-listable subject (people/time), which
# LISTABLE_NOUN's curated vocabulary deliberately excludes.
NON_LISTABLE = "This took about three hours across two people."


def body_file_with(text):
    fh = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                     encoding="utf-8")
    fh.write(text)
    fh.close()
    return fh.name


def run_hook(command, cwd=None, tpath=""):
    """Run the hook end-to-end over an arbitrary Bash command; return stdout.

    Gives the subprocess a FRESH `TMPDIR` per call, per
    `test-remind-brief-premises.py`'s own runner: the hook's fire-once
    sentinel lives in `tempfile.gettempdir()`, keyed by a hash of the
    command and its claims, and this suite calls the hook many times with
    overlapping (command, claim) pairs (the same incident text posted via
    `--body-file` and then again via inline `--body`, for instance). Without
    isolation a sentinel written by one case silently suppresses a LATER
    case in the same test run -- and, worse, silently suppresses a case in a
    SEPARATE run of this file minutes later, since the real `/tmp` sentinel
    outlives the process. Python's `tempfile.gettempdir()` checks `TMPDIR`
    first on every platform this suite runs on, so this is enough.
    """
    tmpdir = tempfile.mkdtemp()
    try:
        payload = {"tool_name": "Bash", "tool_input": {"command": command},
                   "cwd": cwd or os.getcwd(), "transcript_path": tpath}
        proc = subprocess.run([sys.executable, SUBJECT], input=json.dumps(payload),
                              capture_output=True, text=True,
                              env=dict(os.environ, TMPDIR=tmpdir))
        return proc.stdout.strip()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# --------------------------------------------------------------------------
# Unit-level checks on the pure functions
# --------------------------------------------------------------------------

def unit_checks(mod):
    # find_claims: the incident text yields both claim shapes.
    claims = mod.find_claims(INCIDENT_BODY)
    kinds = sorted(k for k, _ in claims)
    check("find_claims on the incident text finds both claim kinds",
          kinds, ["cardinality", "enumeration"])
    check("find_claims cardinality quote names the count",
          any(q == "18 files" for k, q in claims if k == "cardinality"), True)
    check("find_claims enumeration quote carries the hyphenated list",
          any("cycle-charge-flee" in q for k, q in claims if k == "enumeration"),
          True)

    # False positive guards: an ordinary ARD summary and a non-listable
    # cardinality claim must both find nothing.
    check("find_claims silent on an ARD disposition summary",
          mod.find_claims(ARD_SUMMARY), [])
    check("find_claims silent on a non-listable cardinality claim",
          mod.find_claims(NON_LISTABLE), [])

    # A plain content claim ("CLAUDE.md carries...") with no count and no
    # hyphenated list is not this hook's concern either.
    check("find_claims silent on a bare content assertion",
          mod.find_claims("CLAUDE.md carries the units convention."), [])

    # Discharge: a counting command in the body's own code span discharges
    # a cardinality claim; a bare listing command does NOT (needs COUNT).
    body_with_count_deriv = "There are `grep -rc fingerprint scripts/` -- 18 files."
    check("cardinality discharged by an in-body counting command",
          mod._derived_in_body(body_with_count_deriv, need_count=True), True)
    body_with_list_deriv_only = "There are `grep -rl fingerprint scripts/` -- 18 files."
    check("cardinality NOT discharged by an in-body listing-only command",
          mod._derived_in_body(body_with_list_deriv_only, need_count=True), False)
    check("enumeration IS discharged by an in-body listing-only command",
          mod._derived_in_body(body_with_list_deriv_only, need_count=False), True)

    # Discharge: a deriving command in another segment of the same Bash
    # call, with the body substring removed so the body's own prose cannot
    # accidentally satisfy this.
    body = "There are 18 files fingerprinted."
    cmd_with_sibling_deriv = f'grep -rc fingerprint scripts/; gh pr comment 1 --body "{body}"'
    check("cardinality discharged by a sibling-segment counting command",
          mod._derived_in_other_segments(cmd_with_sibling_deriv, body,
                                          need_count=True), True)
    cmd_no_deriv = f'gh pr comment 1 --body "{body}"'
    check("cardinality NOT discharged with no deriving command anywhere",
          mod._derived_in_other_segments(cmd_no_deriv, body, need_count=True),
          False)


# --------------------------------------------------------------------------
# End-to-end cases
# --------------------------------------------------------------------------

def end_to_end_checks():
    # True positive: --body-file reading the incident text off disk.
    path = body_file_with(INCIDENT_BODY)
    out = run_hook(f"gh pr comment 1401 -R Morrison-Lab/sparta --body-file {path}")
    check("true positive (--body-file): hook fires", bool(out), True)
    if out:
        payload = json.loads(out)
        ctx = (payload.get("hookSpecificOutput") or {}).get("additionalContext")
        check("true positive: additionalContext names the unverified claims",
              bool(ctx and "18 files" in ctx), True)
        check("true positive: systemMessage is present",
              "systemMessage" in payload, True)
        check("true positive: no permissionDecision key",
              "permissionDecision" in json.dumps(payload), False)

    # True positive: an inline --body literal, same claim.
    out = run_hook(
        'gh pr comment 1401 -R Morrison-Lab/sparta --body '
        f'"{INCIDENT_BODY}"'
    )
    check("true positive (inline --body): hook fires", bool(out), True)

    # True positive: gh api against a .../comments endpoint with -F body=@file.
    path2 = body_file_with(INCIDENT_BODY)
    out = run_hook(
        "gh api repos/Morrison-Lab/sparta/issues/1401/comments "
        f"-F body=@{path2}"
    )
    check("true positive (gh api .../comments -F body=@file): hook fires",
          bool(out), True)

    # Guard: ordinary ARD-summary comment -> silent.
    path3 = body_file_with(ARD_SUMMARY)
    out = run_hook(f"gh pr comment 1401 --body-file {path3}")
    check("guard: ARD disposition summary -> silent", bool(out), False)

    # Guard: discharged by a counting command in the same Bash call.
    body = "There are 18 files fingerprinted."
    out = run_hook(
        'grep -rc fingerprint scripts/ ; '
        f'gh pr comment 1401 --body "{body}"'
    )
    check("guard: discharged by a sibling-segment counting command -> silent",
          bool(out), False)

    # Guard: discharged by a counting command pasted in the body itself.
    body_with_deriv = "`grep -rc fingerprint scripts/` -- 18 files fingerprinted."
    out = run_hook(f'gh pr comment 1401 --body "{body_with_deriv}"')
    check("guard: discharged by an in-body counting command -> silent",
          bool(out), False)

    # Guard: non-Bash tool -> silent.
    payload = {"tool_name": "Read", "tool_input": {"file_path": "x"}}
    proc = subprocess.run([sys.executable, SUBJECT], input=json.dumps(payload),
                          capture_output=True, text=True)
    check("guard: non-Bash tool -> silent", bool(proc.stdout.strip()), False)

    # Guard: a Bash command that does not post a forge comment at all.
    out = run_hook("git status")
    check("guard: non-comment-posting Bash command -> silent", bool(out), False)

    # Guard: malformed JSON on stdin fails open.
    proc = subprocess.run([sys.executable, SUBJECT], input="not json",
                          capture_output=True, text=True)
    check("guard: malformed stdin JSON -> silent, no traceback",
          proc.stdout.strip(), "")


def main():
    global failures
    mod = load(SUBJECT)
    unit_checks(mod)
    end_to_end_checks()

    if failures:
        print(f"\n{failures} failure(s)")
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
