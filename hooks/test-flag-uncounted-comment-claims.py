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

# Regression fixtures for an adversarial review of this hook (ai-config#2377
# round 1), which found two blocking bugs in the original regexes -- see the
# comments on CARDINALITY_RE and ENUM_RE in the hook itself for the
# mechanism. Both are pinned here so neither regresses silently.

# Bug 1: a count followed by an adjective before the noun ("18 NEW files")
# was invisible, because the noun group had no plural-`s` requirement baked
# into the regex itself, so a lazy gap quantifier never backtracked past the
# adjective to find the real noun.
CARDINALITY_WITH_ADJECTIVE = "There are 18 new files on main."

# Bug 2: routine review-summary phrasing this corpus posts constantly
# ("found 2 issues", "three commits") used to fire, because the curated
# noun vocabulary originally included review-housekeeping words. It must
# not fire post-fix.
ROUTINE_REVIEW_PHRASING = "I found 2 issues while reviewing; three commits fixed them."

# Bug 2's sibling: a two-level corpus path whose own segments are hyphenated
# (`skills/<slug>/SKILL.md`, this repo's own standard citation shape) was
# misread as a listable noun ("skills") followed by a hand-typed two-item
# list. A third variant -- a listable noun that is itself the FIRST
# hyphenated segment of a longer compound identifier (`checks?` matching
# "check" inside `check-open-prs-before-duplicating`) -- reached the same
# false positive by a different route and needed the same fix widened.
PATH_CITATION = "See skills/select-model/SKILL.md for the routing logic."
COMPOUND_IDENTIFIER_PATH = (
    "The rule lives in skills/check-open-prs-before-duplicating/SKILL.md."
)

# The bulleted-list form of the incident's own enumeration claim -- the same
# content ENUM_RE already catches when slash-joined on one line, but as a
# markdown bullet list, which the original regex could not see at all.
BULLETED_LIST = (
    "The fingerprinted scripts:\n"
    "- cycle-charge-flee\n"
    "- interval-labels\n"
    "- multi-unit-form-up-modes\n"
    "- group-attack\n"
)

# Round 2 of the same adversarial review: fixing bug 1 by letting
# CARDINALITY_RE's gap backtrack exposed a second bug -- a WORD-counted gap
# has no sense of a sentence or paragraph boundary, so it happily walked
# through a period or a newline to find a plural noun in a DIFFERENT
# sentence. Both are real review-comment phrasing, not contrived text.
CROSS_SENTENCE_PERIOD = (
    "Reviewed PR 12 on GitHub. Scripts still need work before merge."
)
CROSS_PARAGRAPH_NEWLINE = (
    "Filed as issue 5 in Slack.\nResults are pending review from the team."
)

# ai-config#2386 review round 1 (claude-review, comment 5435096586): the
# path-citation guard on ENUM_RE only protects the position immediately
# after the noun it actually matched. A DIFFERENT listable noun earlier in
# the same sentence ("occurrences") let the gap swallow a whole bare
# directory segment ("skills") plus its trailing slash, resuming the
# token-list match mid-path.
PATH_CITATION_WITH_EARLIER_NOUN = (
    "No occurrences found in skills/select-model/SKILL.md after the fix."
)
# The same shape, reached via the bulleted-list pattern instead of the
# inline one -- an intro line citing a path and ending in a colon, followed
# by unrelated bulleted content.
PATH_CITATION_BEFORE_BULLETS = (
    "No occurrences found in skills/select-model/SKILL.md:\n"
    "- item1\n"
    "- item2\n"
)

# Found while verifying the fix above, in the SAME review repro sentence:
# CARDINALITY_RE's imported COUNT treats "no" as a numeral alongside "zero",
# so "No occurrences" (a negation -- nothing was found, not a specific
# derived count) still read as a cardinality claim after the enumeration
# half was fixed. "zero" stays a real count; "no" does not.
NEGATION_WITH_LISTABLE_NOUN = "There are no dead branches."
ZERO_IS_KEPT = "There are zero files remaining."


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

    # Regression: bug 1 (adjective between count and noun).
    claims = mod.find_claims(CARDINALITY_WITH_ADJECTIVE)
    check("find_claims catches a count with an adjective before the noun",
          claims, [("cardinality", "18 new files")])

    # Regression: bug 2 (routine review-summary phrasing must stay silent).
    check("find_claims silent on routine 'found N issues'/'N commits' phrasing",
          mod.find_claims(ROUTINE_REVIEW_PHRASING), [])

    # Regression: bug 2's path-citation variant, both shapes.
    check("find_claims silent on a skills/<slug>/SKILL.md path citation",
          mod.find_claims(PATH_CITATION), [])
    check("find_claims silent on a noun-prefixed compound-identifier path",
          mod.find_claims(COMPOUND_IDENTIFIER_PATH), [])

    # New coverage: a bulleted-list enumeration (finding 4).
    claims = mod.find_claims(BULLETED_LIST)
    check("find_claims catches a bulleted-list enumeration",
          any(k == "enumeration" and "cycle-charge-flee" in q
              for k, q in claims),
          True)

    # Regression: round 2 of the same review -- fixing bug 1's backtracking
    # exposed a gap with no sentence/paragraph boundary. Must stay silent.
    check("find_claims silent on a count and noun split by a sentence period",
          mod.find_claims(CROSS_SENTENCE_PERIOD), [])
    check("find_claims silent on a count and noun split by a paragraph break",
          mod.find_claims(CROSS_PARAGRAPH_NEWLINE), [])

    # Regression: PR #2386 review round 1 -- ENUM_RE's noun-adjacent guard
    # did not stop a DIFFERENT listable noun earlier in the sentence from
    # swallowing a bare directory segment plus its slash into the gap.
    check("find_claims silent when an earlier noun's gap swallows a path",
          mod.find_claims(PATH_CITATION_WITH_EARLIER_NOUN), [])
    check("find_claims silent on the same shape before a bulleted list",
          mod.find_claims(PATH_CITATION_BEFORE_BULLETS), [])

    # Regression: found while verifying the fix above, in the same repro
    # sentence -- CARDINALITY_RE's COUNT treated "no" as a numeral, so a
    # negation ("no dead branches") read as a cardinality claim. "zero"
    # stays a real, checkable count.
    check("find_claims silent on a negation with a listable noun",
          mod.find_claims(NEGATION_WITH_LISTABLE_NOUN), [])
    check("find_claims still catches an explicit 'zero' cardinality claim",
          mod.find_claims(ZERO_IS_KEPT), [("cardinality", "zero files")])

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
