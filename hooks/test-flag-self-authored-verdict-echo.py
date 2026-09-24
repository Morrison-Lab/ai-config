"""Test the flag-self-authored-verdict-echo guard.

The value is concentrated in the negative cases, as in every other hook test
here: a guard that fires on a genuine self-review, on a body that merely
mentions a verdict, or on a comment carrying a real review payload gets
switched off -- and then the case it exists for goes unprotected too.

The positive case is the real incident: the round-2 disposition comment on
Morrison-Lab/mln#49, which opened by reproducing the reviewer's call at line
start and so acquired a standing not-clean verdict for its own author.

Two of the negatives are the remedies that DO NOT work, kept as tests because
the natural fix is to reach for one of them: a blockquoted echo and a
code-spanned echo both still classify not-clean, so the guard must still fire
on them. Getting those backwards would send the next reader to a fix that
silently does nothing.

Run: python3 hooks/test-flag-self-authored-verdict-echo.py \\
         hooks/flag-self-authored-verdict-echo.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = (
    sys.argv[1]
    if len(sys.argv) > 1
    else os.path.join(os.path.dirname(__file__), "flag-self-authored-verdict-echo.py")
)
ROOT = os.path.dirname(os.path.dirname(os.path.realpath(HOOK)))

NOT_CLEAN = "Needs more work"

# The incident: a disposition opening with the reviewer's call at line start.
ECHO_DISPOSITION = (
    "## Review round 2 --- adversarial review at `75acd84`\n\n"
    "Verdict: **%s**, five findings. All five are addressed in\n"
    "[`f120e5a`](https://example.invalid/c/f120e5a) or in the description.\n\n"
    "**1--2. Addressed.** The backstop step's gate was wrong in both directions.\n"
) % NOT_CLEAN.lower()

# The same echo, blockquoted. Measured 2026-09-24: still classifies not-clean.
ECHO_BLOCKQUOTED = (
    "## Review round 2\n\n"
    "> Verdict: **%s**, five findings.\n\n"
    "All five are addressed in `f120e5a`.\n\n"
    "**1. Addressed.** The gate was wrong.\n"
) % NOT_CLEAN.lower()

# The same echo in a single-backtick span that crosses a line break. Measured
# 2026-09-24: the per-line citation scan cannot close it, so it still matches.
ECHO_CODE_SPAN = (
    "## Disposition\n\n"
    "The comment opens `Verdict: **%s**, five findings. All five are\n"
    "addressed in f120e5a`, which is the reviewer's call rather than mine.\n\n"
    "**1. Addressed.** The gate was wrong.\n"
) % NOT_CLEAN.lower()

# The ARD bullet form with no "addressed in" phrase anywhere -- the shape an
# earlier draft of RX_DISPOSITION missed, which made the payload-exemption
# negative below pass for the wrong reason.
ECHO_BULLET_ONLY = (
    "## Round 3\n\n"
    "Verdict: **%s**, two findings.\n\n"
    "**1. Addressed.** The gate was wrong.\n"
    "**2. Rebutted.** The cited line does not exist.\n"
) % NOT_CLEAN.lower()

# A genuine self-review. States its own verdict; answers nothing.
SELF_REVIEW = (
    "## Self-review at `abc1234`\n\n"
    "### Verdict\n**%s**\n\n"
    "### Findings\n1. `foo()` crashes on empty input.\n"
    "2. The retry loop has no ceiling.\n"
) % NOT_CLEAN

# A genuine self-review that DOES carry disposition vocabulary, negated.
# The `SELF_REVIEW` fixture above states findings in vocabulary this hook
# never matches, so it passed under a negation-blind fire condition too --
# an adversarial review reproduced the gap here, on the honest sentence a
# self-review writes when it has found work and not yet done it.
SELF_REVIEW_NEGATED = (
    "## Self-review at `abc1234`\n\n"
    "### Verdict\n**%s**\n\n"
    "None of the findings are addressed yet --- I have not started\n"
    "implementation.\n\n"
    "1. `foo()` crashes on empty input.\n"
    "2. The retry loop has no ceiling.\n"
) % NOT_CLEAN

# The same blindness reached through the bare phrases rather than the
# quantifier: each of these is a statement that something was NOT done.
NEGATED_PHRASES = (
    "### Verdict\n**%s**\n\n"
    "This is not closed in the current diff. The concern was not answered\n"
    "below because it is out of scope, and the root cause was never\n"
    "addressed in the fix.\n"
) % NOT_CLEAN

# A closed markdown-italic ARD label. `_` is a word character, so the verb
# has no word boundary after it and a `\b`-terminated pattern cannot match.
ITALIC_ARD_LABEL = (
    "## Disposition at `f120e5a`\n\n"
    "### Verdict\n**%s**\n\n"
    "_Addressed_ in the push above.\n"
) % NOT_CLEAN

# A disposition that quotes the REVIEWER's payload back, to say what the
# review concluded. The payload is not this comment's own, so it must not
# exempt the comment -- `classify_verdict()` reads it as this author's
# verdict all the same, which is the incident's own shape.
QUOTED_PAYLOAD = (
    "## Disposition at `f120e5a`\n\n"
    "Verdict: **%s**, the reviewer said.\n\n"
    "**1. Addressed.** Fixed in `abc123`.\n\n"
    "It concluded:\n\n"
    "> <!-- review-data:\n"
    '> {"schema_version": "1.1", "verdict": "NOT_CLEAN"}\n'
    "> -->\n"
) % NOT_CLEAN

# A real review, carrying the machine payload a review emits.
REVIEW_WITH_PAYLOAD = (
    "### Verdict\n**%s**\n\n"
    "<details><summary>Structured Review Data (JSON)</summary>\n"
    '<!-- review-data: {"schema_version": "1.1", "verdict": "NOT_CLEAN"} -->\n'
    "</details>\n\n"
    "**1. Addressed.** Carried deliberately: this body has disposition\n"
    "vocabulary AND a not-clean verdict, so only the payload exemption keeps\n"
    "the guard silent. Without that, the case would pass for the wrong reason.\n"
) % NOT_CLEAN

# The rendering that works: the call described, never reproduced.
DESCRIBED_NOT_ECHOED = (
    "## Review round 2 --- adversarial review at `75acd84`\n\n"
    "The second review round returned a not-clean call with five findings. Its\n"
    "exact wording is deliberately not reproduced here.\n\n"
    "All five are addressed in `f120e5a`.\n\n"
    "**1--2. Addressed.** The backstop step's gate was wrong.\n"
)

# A clean disposition: answers findings, states nothing not-clean.
CLEAN_DISPOSITION = (
    "## Disposition at `727693d8`\n\n"
    "Every finding from the last round is addressed in `f120e5a`.\n"
    "14 check runs, 13 success and 1 skipped.\n"
)

# Prose about the mechanism with no disposition vocabulary at all.
DOCS_ABOUT_THE_RULE = (
    "The scanner reads a line-start verdict label as authored. A body stating\n"
    "**%s** therefore becomes this author's own standing verdict.\n"
) % NOT_CLEAN


_CASE = [0]

# Every subprocess gets a TMPDIR created for THIS run. The hook writes a
# once-per-(transcript, body) sentinel under `tempfile.gettempdir()`, so a
# suite reusing the system temp dir passes on its first run and then reports
# every positive case as a failure on every run after -- which reads exactly
# like the guard being broken rather than like the suite not being repeatable.
# Measured while writing this file: the second run failed all five positives.
_TMP = tempfile.mkdtemp(prefix="verdict-echo-tests-")


def run(tool_name, tool_input, cwd=None, tmpdir=None):
    # A distinct transcript_path per case as well, because two cases sharing a
    # body would otherwise see the second suppressed by the first's sentinel,
    # which reads the same way.
    _CASE[0] += 1
    payload = {"tool_name": tool_name, "tool_input": tool_input,
               "cwd": cwd or ROOT,
               "transcript_path": "/nonexistent/case-%d.jsonl" % _CASE[0]}
    env = dict(os.environ)
    env["TMPDIR"] = tmpdir or _TMP
    proc = subprocess.run(
        [sys.executable, HOOK], input=json.dumps(payload),
        capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        return None
    out = (proc.stdout or "").strip()
    if not out:
        return None
    try:
        return json.loads(out)
    except Exception:
        return None


def fired(tool_name, tool_input, cwd=None, tmpdir=None):
    out = run(tool_name, tool_input, cwd, tmpdir=tmpdir)
    if not out:
        return False
    ctx = (out.get("hookSpecificOutput") or {}).get("additionalContext")
    return bool(ctx)


def mcp(body, tool="mcp__github__add_issue_comment", tmpdir=None):
    return fired(tool, {"owner": "o", "repo": "r", "issue_number": 1, "body": body},
                 tmpdir=tmpdir)


FAILURES = []


def check(name, got, want):
    if got != want:
        FAILURES.append(f"{name}: expected fired={want}, got fired={got}")
    print(f"  {'ok  ' if got == want else 'FAIL'}  {name}")


def main():
    # Import the hook's own predicate for the unit-level cases, so a change to
    # the classifier is visible here and not only through the subprocess.
    import importlib.util
    spec = importlib.util.spec_from_file_location("_hook_under_test", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    if mod.classify_verdict is None:
        print("SKIP: check-pr-fully-clean.py's classify_verdict is unavailable")
        return 0

    print("Negative control on the classifier itself:")
    # Guards against a vacuous suite: if the classifier stopped reading these as
    # not-clean, every positive case below would pass for the wrong reason.
    for label, body in (("line-start echo", ECHO_DISPOSITION),
                        ("blockquoted echo", ECHO_BLOCKQUOTED),
                        ("code-spanned echo", ECHO_CODE_SPAN)):
        got = mod.classify_verdict(body)
        check(f"classifier still reads {label} as not-clean", got, "not-clean")
    tools = getattr(mod, "MCP_POST_TOOLS", ())
    check("the MCP tool list carries no duplicate",
          len(tools) == len(set(tools)) and len(tools) > 0, True)
    check("classifier reads the described form as no-verdict",
          mod.classify_verdict(DESCRIBED_NOT_ECHOED), "")

    print("Positive cases (must fire):")
    check("line-start echo in a disposition", mcp(ECHO_DISPOSITION), True)
    check("blockquoting does not exempt it", mcp(ECHO_BLOCKQUOTED), True)
    check("a code span does not exempt it", mcp(ECHO_CODE_SPAN), True)
    check("the ARD bullet form alone is disposition vocabulary",
          mcp(ECHO_BULLET_ONLY), True)
    check("a closed italic ARD label still matches", mcp(ITALIC_ARD_LABEL), True)
    check("a QUOTED review payload does not exempt the comment",
          mcp(QUOTED_PAYLOAD), True)
    check("an edit to an existing comment is covered",
          mcp(ECHO_DISPOSITION, "mcp__github__update_issue_comment"), True)
    check(
        "a gh pr comment carrying the echo",
        fired("Bash", {"command":
                       "gh pr comment 49 --body \"%s\"" %
                       ECHO_DISPOSITION.replace('"', "'")}),
        True,
    )

    print("Negative cases (must stay silent):")
    check("a genuine self-review stating its own verdict",
          mcp(SELF_REVIEW), False)
    check("a self-review whose disposition vocabulary is NEGATED",
          mcp(SELF_REVIEW_NEGATED), False)
    check("negated disposition phrases stay silent",
          mcp(NEGATED_PHRASES), False)
    check("a real review carrying a review-data payload",
          mcp(REVIEW_WITH_PAYLOAD), False)
    check("the call described rather than reproduced",
          mcp(DESCRIBED_NOT_ECHOED), False)
    check("a clean disposition", mcp(CLEAN_DISPOSITION), False)
    check("prose about the rule with no disposition vocabulary",
          mcp(DOCS_ABOUT_THE_RULE), False)
    check("an empty body", mcp(""), False)
    check("a non-comment Bash command",
          fired("Bash", {"command": "git status"}), False)
    check("an unrelated tool",
          fired("Read", {"file_path": "/etc/hostname"}), False)

    print("Once per body (the sentinel):")
    shared = tempfile.mkdtemp(prefix="verdict-echo-sentinel-")
    try:
        # Both calls share a transcript AND a TMPDIR, so the second is the
        # repeat the sentinel exists to suppress. Asserted because this is the
        # behaviour that made an earlier draft of this suite unrepeatable.
        payload = {"tool_name": "mcp__github__add_issue_comment",
                   "tool_input": {"owner": "o", "repo": "r",
                                  "issue_number": 1, "body": ECHO_DISPOSITION},
                   "cwd": ROOT, "transcript_path": "/nonexistent/sentinel.jsonl"}
        env = dict(os.environ)
        env["TMPDIR"] = shared
        seen = []
        for _ in range(2):
            proc = subprocess.run([sys.executable, HOOK],
                                  input=json.dumps(payload),
                                  capture_output=True, text=True, env=env)
            out = (proc.stdout or "").strip()
            ctx = None
            if out:
                try:
                    ctx = (json.loads(out).get("hookSpecificOutput") or {}
                           ).get("additionalContext")
                except Exception:
                    ctx = None
            seen.append(bool(ctx))
        check("first post of a body warns", seen[0], True)
        check("an identical repost stays silent", seen[1], False)
    finally:
        shutil.rmtree(shared, ignore_errors=True)

    if FAILURES:
        print("\nFAILURES:")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("\nAll cases passed.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)
