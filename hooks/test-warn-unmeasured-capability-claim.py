#!/usr/bin/env python3
"""Tests for warn-unmeasured-capability-claim.py.

Run: python3 hooks/test-warn-unmeasured-capability-claim.py [path-to-hook]

The positive fixtures are the two claims that actually shipped to GitHub on
2026-09-17 and had to be retracted, verbatim. Using the real sentences rather
than invented ones is the point: an invented fixture is written by the same
understanding that writes the matcher, so it proves the matcher matches itself
(`shared/workflow/fixtures-are-not-evidence.md`).

Round 8 of ai-config#3737 mutated this hook fourteen times and TWELVE mutants
survived a fully green run: five `RX_ABSOLUTE` branches could be deleted, the
tooling-noun list could be cut to two entries, `WINDOW` could be raised from
400 to 1500, three MCP tools could be dropped, and the `systemMessage` -- the
only part a human reads -- could be removed outright. The suite pinned the
two-factor STRUCTURE and almost nothing either matcher actually contains. The
per-branch, per-noun, per-tool and window-boundary cases below exist because of
that, and each one was confirmed to kill its own mutant.

Every case gets a PRIVATE tempdir. The hook keeps a fire-once sentinel there,
so a suite sharing one tempdir passes on its first run and fails afterwards --
the sentinels outlive the process. That was not hypothetical: it turned a green
suite red on a re-run and made every result before it unreliable.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.realpath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "warn-unmeasured-capability-claim.py"))

failures = 0
ran = 0


def check(label, ok):
    global failures, ran
    ran += 1
    if ok:
        print(f"PASS: {label}")
    else:
        failures += 1
        print(f"FAIL: {label}")


def run(payload, env=None, tmpdir=None):
    """(fired, stdout) for one PreToolUse payload.

    `tmpdir` defaults to a fresh directory, so the hook's fire-once sentinel
    cannot leak between cases or between runs. Pass one explicitly to exercise
    the dedupe itself.
    """
    own = None
    if tmpdir is None:
        own = tempfile.mkdtemp(prefix="capclaim-case-")
        tmpdir = own
    proc = subprocess.run(
        [sys.executable, HOOK], input=json.dumps(payload),
        capture_output=True, text=True,
        env={**os.environ, "TMPDIR": tmpdir, **(env or {})})
    out = proc.stdout.strip()
    if proc.returncode != 0:
        return None, out
    if not out:
        return False, ""
    try:
        data = json.loads(out)
    except Exception:
        return None, out
    fired = bool((data.get("hookSpecificOutput") or {}).get("additionalContext"))
    return fired, out


def mcp(body, tool="mcp__github__add_issue_comment"):
    return {"tool_name": tool, "tool_input": {"body": body}}


def bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


spec = importlib.util.spec_from_file_location("capclaim", HOOK)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

# --- 1. The real retracted claims, verbatim ---------------------------------
REAL_1 = (
    "Foreground dispatch, the remedy the guard prints, is unavailable -- the "
    "harness backgrounds every `Agent` call regardless of "
    "`run_in_background: false`.")
REAL_2 = (
    "The provenance chain is unbuildable in this harness as the records "
    "currently stand, independent of any spelling the guard learns.")
REAL_3 = (
    "No key this guard could learn will authorize this session's push.")

for i, body in enumerate((REAL_1, REAL_2, REAL_3), start=1):
    fired, _ = run(mcp(body))
    check(f"the real retracted claim #{i} fires", fired is True)

# --- 2. Both factors are required -------------------------------------------
fired, _ = run(mcp(
    "There is no way to know which wording the author preferred, so I kept "
    "both and let the reader choose."))
check("an absolute idiom with no tooling noun stays silent", fired is False)

fired, _ = run(mcp(
    "The harness backgrounds this dispatch, so the guard reads the agent id "
    "from the tool result and the review lands separately."))
check("a tooling noun with no absolute idiom stays silent", fired is False)

# --- 3. Every `RX_ABSOLUTE` branch, one case each ---------------------------
#     Deleting a branch used to pass the whole suite. Each phrase below is the
#     only coverage its branch has, so a deletion now fails exactly one case
#     and names it.
for label, phrase in (
        ("is not available", "The transcript is not available to the guard."),
        ("isn't available", "The transcript isn't available to the guard."),
        ("is not possible", "Recognising this is not possible for the guard."),
        ("is not supported", "That field is not supported by the harness."),
        ("is unavailable", "Foreground dispatch is unavailable in this harness."),
        ("was unavailable", "That field was unavailable to the runner."),
        ("is unsupported", "The spelling is unsupported by this classifier."),
        ("is unreachable", "That branch of the guard is unreachable."),
        ("unbuildable", "The provenance chain is unbuildable here."),
        ("impossible", "Matching the session is impossible for the hook."),
        ("there's no way to", "There's no way to tell what the harness did."),
        ("there is no way of", "There is no way of telling what the harness did."),
        ("cannot be parsed", "The body cannot be parsed by the guard."),
        ("cannot be recovered", "The id cannot be recovered from the transcript."),
        ("no matter what", "The guard denies it no matter what the agent reports."),
        ("never fires", "The hook never fires on an MCP dispatch."),
        ("no X can Y", "No key this guard could learn will authorize it."),
):
    fired, _ = run(mcp(phrase))
    check(f"the `{label}` idiom fires", fired is True)

#     The `no X can/could Y` branch is split by MODAL, and both halves need
#     pinning because round 9 found the earlier blanket `be` exclusion failing
#     in BOTH directions while all 97 cases passed. Changing that clause
#     changed nothing in this suite, which is how an unpinned narrowing looks
#     from the inside (ai-config#3737 round 9).
#
#     Capability claims about the system, in the passive voice this hook's own
#     subject matter is usually written in. These MUST fire.
for phrase in (
        "No transcript can be read by this hook.",
        "No id can be recovered from the transcript by the guard.",
        "No verdict could be parsed by the guard.",
        "No transcript can ever be read by this hook.",
):
    fired, _ = run(mcp(phrase))
    check(f"passive capability claim fires: {phrase!r}", fired is True)

#     Claims about future WORK rather than about capability. These must NOT
#     fire, and the `ever` variants are the ones the previous form let through:
#     the engine backtracked past the optional group and tested the lookahead
#     against "ever" rather than against "be".
for phrase in (
        "No changes will be needed to the CI workflow in this hook.",
        "No changes will ever be needed to the CI workflow in this hook.",
        "No further work will be required on this guard.",
        "No migration would ever be needed for this hook.",
):
    fired, _ = run(mcp(phrase))
    check(f"future-work claim stays silent: {phrase!r}", fired is False)

#     And the affirmative that the negated and prefixed branches must NOT be
#     folded together to match. Collapsing them into one optional-`un` form
#     fires here, on prose asserting the opposite of this hook's subject.
fired, _ = run(mcp("A foreground dispatch is possible for this harness."))
check("`is possible` does not fire", fired is False)

# --- 4. Tooling nouns, including the plurals -------------------------------
#     Every noun but `dispatch` used to be a bare literal between word
#     boundaries, so a claim whose only tooling nouns were plural was silently
#     discarded -- and the one inflected entry is what made the list read as
#     stem-matched.
for noun in ("harness", "harnesses", "hook", "hooks", "guard", "guards",
             "runner", "runners", "subagent", "subagents", "agent", "agents",
             "transcript", "transcripts", "classifier", "classifiers",
             "permission", "permissions", "API", "APIs", "CLI", "CLIs",
             "MCP", "workflow", "workflows", "CI", "tool", "tools",
             "session", "sessions", "provenance", "chain", "chains"):
    fired, _ = run(mcp(f"That is impossible for the {noun} to do."))
    check(f"the tooling noun `{noun}` satisfies factor 2", fired is True)

#     The negative control the loop needs: a word that is not a tooling noun
#     at all must not satisfy factor 2, or the loop above is measuring nothing.
fired, _ = run(mcp("That is impossible for the paragraph to do."))
check("a non-tooling noun does not satisfy factor 2", fired is False)

# --- 5. The window's boundary, not merely its existence ---------------------
#     The old pair used a ~25-character gap and a ~1825-character one, so any
#     WINDOW in roughly [25, 1800] passed and the advertised 400 was pinned
#     only within a 70x range. These two straddle it.
IDIOM = "There is no way to proceed."


def spaced(gap):
    """`IDIOM`, then exactly `gap` characters, then the tooling noun.

    The filler is forced to END ON A SPACE. Slicing `"filler " * n` to an
    arbitrary length can cut mid-word, and the noun then has no word boundary
    in front of it -- so the case fails for a reason that has nothing to do
    with the window it is measuring.
    """
    return IDIOM + ("filler " * (gap // 7 + 2))[:gap - 1] + " harness is slow."


fired, _ = run(mcp(spaced(380)))
check("a tooling noun just inside the window fires", fired is True)
fired, _ = run(mcp(spaced(420)))
check("a tooling noun just outside the window stays silent", fired is False)

# --- 6. Surfaces: every MCP tool in the tuple -------------------------------
#     Dropping three of them passed the whole suite. The list is derived from
#     the hook's own tuple, so a tool added there without a case fails here
#     rather than shipping untested.
for tool in hook.MCP_POST_TOOLS:
    fired, _ = run(mcp(REAL_2, tool=tool))
    check(f"`{tool}` is in scope", fired is True)

check("the canonical discussion surface is in the tuple",
      "mcp__github__discussion_comment_write" in hook.MCP_POST_TOOLS)

#     A tool NOT in the tuple carries no body this hook judges.
fired, _ = run({"tool_name": "mcp__github__issue_read",
                "tool_input": {"issue_number": 1}})
check("a read-only forge call stays silent", fired is False)

#     Both body keys. Narrowing the pair to `("body",)` passed the suite.
fired, _ = run({"tool_name": "mcp__github__add_issue_comment",
                "tool_input": {"text": REAL_2}})
check("a `text` key is read as the body", fired is True)

# --- 7. Surfaces: the `gh`/`glab` command shapes ----------------------------
#     The first version required `gh|glab` then `issue|pr|mr` then
#     `comment|create|edit`, which reaches none of the first five below --
#     every one of them a route this corpus documents and uses.
for label, cmd in (
        ("gh issue comment",
         'gh issue comment 1 --body "the chain is unbuildable in this harness"'),
        ("gh pr comment",
         'gh pr comment 1 --body "the chain is unbuildable in this harness"'),
        ("gh api issues comments",
         'gh api repos/o/r/issues/1/comments -f body="the chain is unbuildable in this harness"'),
        ("gh api review replies",
         'gh api repos/o/r/pulls/comments/5/replies -f body="the chain is unbuildable in this harness"'),
        ("gh pr review",
         'gh pr review 1 --body "the chain is unbuildable in this harness"'),
        ("glab mr note",
         'glab mr note 1 -m "the chain is unbuildable in this harness"'),
        ("glab issue note",
         'glab issue note 1 --message "the chain is unbuildable in this harness"'),
        ("gh issue create",
         'gh issue create --title x --body "the chain is unbuildable in this harness"'),
        ("gh pr edit",
         'gh pr edit 1 --body "the chain is unbuildable in this harness"'),
):
    fired, _ = run(bash(cmd))
    check(f"`{label}` is in scope", fired is True)

#     A local commit is NOT this surface -- durability is the whole criterion.
fired, _ = run(bash(
    'git commit -m "the provenance chain is unbuildable in this harness"'))
check("a local git commit is out of scope", fired is False)

#     A non-forge command that would clear a bare verb filter. The commit above
#     also fails a verb test, so it masked the forge-name test: a mutant
#     dropping the forge check survived until this row existed.
fired, _ = run(bash(
    'git commit -m "edit the guard: this dispatch is unavailable"'))
check("a non-forge command clearing a verb filter is still out of scope",
      fired is False)

#     The patterns are position-anchored, so PROSE quoting the command -- which
#     this corpus does constantly -- is not the command being issued.
fired, _ = run(bash(
    'echo "run gh issue comment 1 --body \\"the harness is unavailable\\" later"'))
check("prose quoting a forge command is not a forge write", fired is False)

# --- 8. The quote the reminder actually shows -------------------------------
#     `_quote` used a bare `.` as a sentence boundary, so a decimal, a fragment
#     filename or a URL earlier in the body truncated the quote mid-token. The
#     quote IS this hook's product.
for label, body, must_start in (
        ("a decimal", "The run took 16.3 seconds so the harness is unavailable.",
         "The run took"),
        ("a fragment path",
         "See shared/workflow/verify-the-right-artifact.md for context; "
         "the dispatch is unavailable.", "See shared"),
        ("a URL", "See https://github.com/Morrison-Lab/ai-config/pull/1 "
         "and the dispatch is unavailable.", "See https"),
):
    hit = hook._findings(body)
    quote = hook._quote(body, hit) if hit else ""
    check(f"the quote survives {label} (got {quote[:42]!r})",
          quote.startswith(must_start))

#     And it still cuts at a real boundary rather than returning everything.
body = "The guard ran fine. The dispatch is unavailable. We moved on."
hit = hook._findings(body)
check("the quote is the sentence, not the whole body",
      hit is not None
      and hook._quote(body, hit) == "The dispatch is unavailable.")

# --- 9. Never blocks, never raises ------------------------------------------
for label, payload in (
        ("empty payload", {}),
        ("no tool_input", {"tool_name": "mcp__github__add_issue_comment"}),
        ("non-dict tool_input", {"tool_name": "mcp__github__add_issue_comment",
                                 "tool_input": "oops"}),
        ("non-str body", {"tool_name": "mcp__github__add_issue_comment",
                          "tool_input": {"body": ["a", "b"]}}),
        ("non-str command", {"tool_name": "Bash",
                             "tool_input": {"command": 17}}),
):
    fired, out = run(payload)
    check(f"{label} exits 0 without firing", fired is False)

proc = subprocess.run([sys.executable, HOOK], input="not json at all",
                      capture_output=True, text=True)
check("garbage stdin exits 0", proc.returncode == 0)

#     The output never carries a deny decision, whatever it says. The body must
#     be UNIQUE: reusing REAL_1 here made the dedupe suppress the call, so
#     `out` was "" and the assertion passed against nothing. A mutant adding a
#     deny decision survived the whole suite until this line stopped being
#     vacuous.
fired, out = run(mcp(REAL_1 + " (deny probe, unique text b7e04)"))
check("a firing emits no permissionDecision",
      fired is True and "permissionDecision" not in out)

# --- 10. Dedupe --------------------------------------------------------------
#     The two calls share one tempdir, which is what makes this the dedupe
#     rather than an artefact of the per-case isolation everywhere else.
shared = tempfile.mkdtemp(prefix="capclaim-dedupe-")
unique = REAL_2 + "  (dedupe probe, unique text 8f21c)"
first, _ = run(mcp(unique), tmpdir=shared)
second, _ = run(mcp(unique), tmpdir=shared)
check("the same body fires once, not twice", first is True and second is False)

#     The same text through a DIFFERENT tool is a second publication and gets
#     its own reminder. Keying on the body alone silently suppressed it, which
#     is exactly the shape of the incident this hook was built from: one claim,
#     an issue comment and then a PR body.
third, _ = run(mcp(unique, tool="mcp__github__create_pull_request"),
               tmpdir=shared)
check("the same body on a second surface fires again", third is True)

# --- 11. `systemMessage` -----------------------------------------------------
#     The negative control below had no positive counterpart, so deleting the
#     user-visible message outright passed the suite. It is the only part of
#     this hook a human reads.
fired, out = run(mcp(REAL_3 + " (systemMessage probe 91be2)"))
check("a firing emits a user-visible systemMessage",
      fired is True and "systemMessage" in out)

fired, out = run(mcp(REAL_3 + " (antigravity probe 4c19a)"),
                 env={"ANTIGRAVITY_AGENT": "1"})
check("under ANTIGRAVITY_AGENT it still injects context",
      fired is True and "systemMessage" not in out)

print()
print(f"{ran - failures}/{ran} cases passed"
      if failures else f"All {ran} cases passed")
sys.exit(1 if failures else 0)
