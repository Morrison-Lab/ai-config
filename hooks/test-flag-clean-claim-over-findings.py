"""Test the flag-clean-claim-over-findings guard.

The value is concentrated in the negative cases, per every other hook test in
this repo: a guard that fires on a mere phrase quote, on documentation that
discusses the rule, or on a local file read that happens to contain review
vocabulary, gets switched off -- and then the case it exists for goes
unprotected too. The main design risk named in the hook's own docstring is
exactly that: it must not fire merely because a message quotes a verdict
phrase.

Run: python3 hooks/test-flag-clean-claim-over-findings.py \\
         hooks/flag-clean-claim-over-findings.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = (
    sys.argv[1]
    if len(sys.argv) > 1
    else os.path.join(os.path.dirname(__file__), "flag-clean-claim-over-findings.py")
)

HAZARD_BODY = (
    "### Verdict\nReady for merge\n\n"
    "### Findings\n1. `foo()` crashes on empty input.\n"
)
CLEAN_BODY = "### Verdict\nReady for merge\n\nNo issues found.\n"
NOT_CLEAN_BODY = "### Verdict\nNeeds more work\n\nStill investigating.\n"
RESOLVED_BODY = (
    "### Verdict\nReady for merge\n\n"
    "### Findings (resolved)\n1. Fixed in commit abcdef1.\n"
)


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


def fetch(cmd, tool_id, name="Bash"):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": tool_id, "name": name, "input": {"command": cmd}}]}}


def mcp_fetch(tool_id, method, pull_number):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": tool_id, "name": "mcp__github__pull_request_read",
         "input": {"method": method, "pullNumber": pull_number}}]}}


def read_file(tool_id, path):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": tool_id, "name": "Read", "input": {"file_path": path}}]}}


def result(tool_id, content):
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": tool_id, "content": content}]}}


def result_blocks(tool_id, content):
    """A tool_result whose `content` is a LIST of content blocks.

    The other transport shape. `str()` on it yields a Python repr in which every
    newline is escaped, which defeats the heading and marked-line detection the
    hazard scan relies on (round 8, finding 1).
    """
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": tool_id,
         "content": [{"type": "text", "text": content}]}]}}


def checker(pr):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash",
         "input": {"command": f"python3 scripts/check-pr-fully-clean.py {pr}"}}]}}


HAZARD_42_BLOCKS = [
    fetch("gh api repos/o/r/pulls/42/reviews", "tb1"),
    result_blocks("tb1", HAZARD_BODY),
]

CLEAN_REFETCH_42 = [
    fetch("gh api repos/o/r/pulls/42/reviews", "t9"),
    result("t9", CLEAN_BODY),
]

HAZARD_42 = [
    fetch("gh api repos/o/r/pulls/42/reviews", "t1"),
    result("t1", HAZARD_BODY),
]

# (events, should_warn, label)
CASES = [
    # THE CORE INCIDENT: a hazard body was read, and the closing reply
    # states the clean phrase and never mentions the findings at all.
    (HAZARD_42 + [say("Reported to the user: Ready for merge.")], True,
     "clean claim over an unacknowledged findings hazard warns"),

    # DISCHARGED: the reply itself acknowledges the findings.
    (HAZARD_42 + [say(
        "Ready for merge, but there are two findings still open that I "
        "flagged separately.")], False,
     "acknowledging findings in the same reply discharges"),
    (HAZARD_42 + [say(
        "Verdict: Ready. One nit remains, noted for a follow-up.")], False,
     "acknowledging a nit discharges"),

    # DISCHARGED: check-pr-fully-clean.py ran for the SAME PR afterward --
    # the corrective action this hook exists to prompt already happened.
    (HAZARD_42 + [checker(42), say("Ready for merge.")], False,
     "running the real instrument for the same PR discharges"),

    # NOT DISCHARGED: the checker ran for a DIFFERENT PR.
    (HAZARD_42 + [checker(99), say("Ready for merge.")], True,
     "running the instrument for an unrelated PR does not discharge"),

    # ONLY THE MOST RECENT HAZARD IS CONSULTED: an earlier hazard (#42) was
    # already discharged by the real instrument; a LATER, undischarged
    # hazard (#7) is what a closing "Ready for merge." recap is actually
    # about. If the hook consulted the FIRST hazard instead, the already-
    # discharged #42 would suppress the warning this later, live hazard
    # deserves.
    (HAZARD_42 + [checker(42),
                  fetch("gh api repos/o/r/pulls/7/reviews", "t10"),
                  result("t10", HAZARD_BODY),
                  say("Ready for merge.")], True,
     "a later, undischarged hazard still warns after an earlier one clears"),

    # NOT DISCHARGED: the checker ran, but BEFORE the hazard was even
    # fetched (adversarial-review finding: discharge must be order-aware,
    # not "ran at any point in this transcript").
    ([checker(42)] + HAZARD_42 + [say("Ready for merge.")], True,
     "a checker run BEFORE the hazard was fetched does not discharge it"),

    # NOT DISCHARGED: an UNTARGETED hazard (no PR number attributable to
    # its fetch) must not be discharged by a checker run for a wholly
    # UNRELATED PR merely because SOME invocation happened somewhere in
    # the transcript (adversarial-review finding).
    ([checker(99),
      {"type": "assistant", "message": {"content": [
          {"type": "tool_use", "id": "t11", "name": "mcp__github__pull_request_read",
           "input": {"method": "get_reviews"}}]}},
      result("t11", HAZARD_BODY),
      say("Ready for merge.")], True,
     "an untargeted hazard is not discharged by an unrelated PR's earlier checker run"),

    # THE MAIN DESIGN RISK, THIRD FORM (adversarial-review finding): a
    # hazard exists, and the reply mentions the clean phrase, but only
    # while discussing what a reviewer typically says -- not asserting
    # the current round is clean.
    (HAZARD_42 + [say(
        "By the way, once CI passes, a reviewer usually says something "
        "like Ready for merge in the verdict line -- that's just how "
        "this bot phrases it.")], False,
     "discussing the phrase in the abstract (hedged/reported speech) does not warn"),
    (HAZARD_42 + [say(
        "A clean review typically reads Ready for merge with no further "
        "action needed.")], False,
     "generic-framing prose ('typically reads') does not warn"),

    # ACK_RX SCOPE (adversarial-review finding): an unrelated merge-order
    # sentence mentioning a DIFFERENT PR must not discharge a genuine,
    # unacknowledged clean claim about the hazard PR just because it used
    # to share vocabulary with the escape valve.
    (HAZARD_42 + [say(
        "Note: before merging PR #99 you should merge PR #42 first.\n"
        "PR #42: Ready for merge.")], True,
     "an unrelated merge-order sentence does not discharge a real claim about the hazard PR"),

    # THIRD-ROUND adversarial-review findings: the `the way` alternative
    # collided with the ordinary opener "by the way".
    (HAZARD_42 + [say("By the way, PR #42 is Ready for merge.")], True,
     "'by the way' does not collide with GENERIC_FRAMING_RX's 'the way'"),

    # A hedge word and the claim sit in the same SENTENCE but different
    # CLAUSES (comma + conjunction) -- the hedge must not reach across
    # that break.
    (HAZARD_42 + [say(
        "You should hold off on #99, but PR #42 is Ready for merge.")], True,
     "a hedge word in an earlier, comma-separated clause does not disqualify"),
    (HAZARD_42 + [say(
        "Such as #17, this one, PR #42, is Ready for merge.")], True,
     "generic-framing in an earlier, comma-separated clause does not disqualify"),
    # Control: the SAME hedge word genuinely governing the claim (no
    # clause break between them) must still disqualify it.
    (HAZARD_42 + [say(
        "You should say PR #42 is Ready for merge once CI passes.")], False,
     "a hedge word that DOES attach (no clause break) still disqualifies"),

    # SEVENTH-ROUND (sixth review) finding: terminal punctuation GLUED
    # directly onto a following markdown marker with no whitespace
    # ("this.**Ready") satisfied neither of `_nsp`'s own break alternatives
    # (`\s` or true string-end `$`), so a hedge word from an entirely
    # UNRELATED earlier sentence reached all the way across and silently
    # suppressed a plain, unqualified claim -- a silent miss, surfaced only
    # once `_last_break_before` stopped relying on the `endpos`-truncation
    # artifact that used to paper over it by accident.
    (HAZARD_42 + [say(
        "You should never merge this.**Ready for merge**")], True,
     "a hedge word before punctuation glued to a markdown marker does not attach"),

    # PR-correlation must be scoped to the clean-claim's OWN sentence, not
    # the whole reply: an unrelated `#N` two sentences away must not read
    # as "the claim is about that PR instead."
    (HAZARD_42 + [say(
        "By the way, #99 merged last week. Ready for merge.")], True,
     "an unrelated #N mention elsewhere in the reply does not defeat PR correlation"),

    # FOURTH-ROUND adversarial-review findings.
    #
    # The PR-correlation window must tolerate a semantic-line-break wrap:
    # the hazard's own #N reference can sit on an EARLIER wrapped line of
    # the SAME sentence as the clean claim.
    (HAZARD_42 + [say(
        "Fixes flowed from PR #42's review\n"
        "and also touched on #17 -- Ready for merge.")], True,
     "the hazard PR's own reference on a wrapped earlier line still correlates"),
    (HAZARD_42 + [say(
        "The change in PR #42 addresses the review comments\n"
        "and #17's related cleanup, so this is Ready for merge.")], True,
     "a wrapped sentence naming the hazard PR before the wrap still correlates"),
    # The FORWARD-scan counterpart: an unrelated PR reference sits BEFORE
    # a wrap, and the hazard's own reference sits AFTER it. A forward
    # scan using the wrong (leading-style, `\n`-breaking) regex would
    # truncate the window at the wrap, see only the unrelated #17, and
    # wrongly suppress a claim that -- read whole -- is plainly about #42.
    (HAZARD_42 + [say(
        "Ready for merge, mentioned earlier as #17's blocker\n"
        "resolved via PR #42's fix specifically.")], True,
     "the hazard PR's own reference AFTER a wrap still correlates"),

    # FIFTH-ROUND (fourth review) finding: a plain-wrap-tolerant
    # correlation regex swept an UNRELATED PR reference on an adjacent,
    # separate BULLET into the window, silently discharging a hazard
    # whose own claim carries no PR number at all -- the opposite failure
    # direction (silent miss) from everything else this hook accepts.
    # A bullet marker after the wrap must still break the window, even
    # though plain prose continuation must not.
    (HAZARD_42 + [say(
        "- Unrelated: #99 was merged separately last night\n"
        "- Ready for merge")], True,
     "an unrelated PR on an adjacent bullet does not poison correlation"),

    # SIXTH-ROUND (fifth review) findings: the bullet-boundary fix above
    # only ported ONE of the several line-leading shapes
    # check-pr-fully-clean.py's own `_SECTION_FINDING_ITEM` treats as an
    # independent item -- a blockquote line and a bold-lead line (which
    # also covers `**Location:**`) leaked the same way a bullet did.
    (HAZARD_42 + [say(
        "> Unrelated: #99 was merged separately last night\n"
        "> Ready for merge")], True,
     "an unrelated PR on an adjacent blockquote line does not poison correlation"),
    (HAZARD_42 + [say(
        "**Unrelated:** #99 was merged separately last night\n"
        "**Ready for merge**")], True,
     "an unrelated PR on an adjacent bold-lead line does not poison correlation"),
    # The bold-lead fix ALSO exercises the endpos/lookahead trap a
    # positional regex scan hits when the marker sits IMMEDIATELY before
    # the target position: `finditer(prose, 0, pos)` makes the engine
    # treat the string as ending at `pos`, so a lookahead testing "is the
    # rest of this line non-blank" wrongly reads as blank and the marker
    # is missed entirely -- exactly the case that matters most, since it is
    # the marker closest to the claim. `_last_break_before` (unrestricted
    # scan, filtered by end position afterward) is what fixes this.
    # NOTE: the marker sits DIRECTLY adjacent to the claim (no period, no
    # intervening words) -- both are load-bearing for the discrimination.
    # A period after "last week" would ALSO break via
    # TRAILING_SENTENCE_BREAK_RX's own `[.!?;]` alternative regardless of
    # the bold-lead lookahead, and intervening words push the marker's
    # own match well clear of `pos`, so either would make this pass even
    # under the endpos/lookahead bug and defeat the point of the case.
    (HAZARD_42 + [say("**Unrelated:** #99 was merged last week\n**Ready for merge**")], True,
     "a bold-lead marker immediately before the claim is still found (endpos/lookahead trap)"),

    # A genuinely hedged claim spanning MORE than 50 characters (the old,
    # now-removed character cap) must still be disqualified -- clause
    # attachment, not a raw window, is what should decide this.
    (HAZARD_42 + [say(
        "It should be fairly safe to conclude at this point in the "
        "process that PR #42 is Ready for merge.")], False,
     "a hedge word more than 50 characters before the claim still disqualifies"),
    (HAZARD_42 + [say(
        "You could reasonably argue given the state of testing today "
        "that PR #42 is Ready for merge.")], False,
     "a second long-hedge case still disqualifies with no character cap"),

    # NO HAZARD: a genuinely clean review (no findings section at all).
    ([fetch("gh api repos/o/r/pulls/7/reviews", "t2"),
      result("t2", CLEAN_BODY),
      say("Ready for merge.")], False,
     "a clean review with no findings never becomes a hazard"),

    # NO HAZARD: the findings section is explicitly marked and confirmed
    # resolved -- check-pr-fully-clean.py's own exemption applies, so this
    # is not a hazard at all.
    ([fetch("gh api repos/o/r/pulls/8/reviews", "t3"),
      result("t3", RESOLVED_BODY),
      say("Ready for merge.")], False,
     "a resolved findings section is not a hazard"),

    # NO CLEAN CLAIM: the reply never states the clean phrase, so nothing
    # to compare against the hazard.
    (HAZARD_42 + [say("Pushed a fix; will check CI next.")], False,
     "a reply with no clean claim never warns"),

    # THE MAIN DESIGN RISK: a message merely QUOTING the verdict phrase,
    # with NO hazard anywhere in the transcript (a pure documentation /
    # rule-discussion session).
    ([say(
        "This corpus quotes `Ready for merge` and `### Verdict` "
        "constantly, so a bare phrase search misfires in both "
        "directions.")], False,
     "quoting the phrase with no hazard present never warns"),
    ([say(
        "Example:\n```\n### Verdict\nReady for merge\n```\nthat is the "
        "shape a clean verdict takes.")], False,
     "a fenced example of the verdict shape with no hazard never warns"),

    # THE MAIN DESIGN RISK, SECOND FORM: a hazard DOES exist, but the reply
    # only QUOTES the phrase (backticked) rather than stating it as fact.
    (HAZARD_42 + [say(
        "The review's heading used the phrase `Ready for merge`, for what "
        "it's worth.")], False,
     "a hazard plus a backtick-quoted mention of the phrase does not warn"),

    # NO HAZARD: reading a LOCAL corpus file that happens to contain review
    # vocabulary is not a review fetch -- gate 1 (REVIEW_FETCH/SAVED_BODY)
    # never lets this become a hazard at all.
    ([read_file("t4", "shared/workflow/fully-clean.md"),
      result("t4", HAZARD_BODY),
      say("Ready for merge.")], False,
     "reading a local doc file containing review vocabulary is not a hazard"),

    # A SAVED review body, read back from a file -- still a hazard, per
    # no-handrolled-verdict-parse.py's own SAVED_BODY clause.
    ([fetch("cat /tmp/pr-review-55.json", "t5"),
      result("t5", HAZARD_BODY),
      say("Ready for merge.")], True,
     "a saved-and-reread review body is still a hazard"),

    # An MCP-shaped fetch (remote session), with the PR number carried in
    # the tool's JSON input rather than a `gh` command string.
    ([mcp_fetch("t6", "get_reviews", 7), result("t6", HAZARD_BODY),
      say("Ready for merge.")], True,
     "an MCP pull_request_read hazard warns"),
    ([mcp_fetch("t6", "get_reviews", 7), result("t6", HAZARD_BODY),
      checker(7), say("Ready for merge.")], False,
     "the checker run discharges an MCP-attributed hazard by its pullNumber"),

    # PR CORRELATION: the hazard names one PR, and the reply's clean claim
    # is plainly about a DIFFERENT PR (both PR numbers known and disjoint).
    (HAZARD_42 + [say("PR #99 is ready for merge.")], False,
     "a clean claim about a different, known PR does not warn"),
    (HAZARD_42 + [say("PR #42 is ready for merge.")], True,
     "a clean claim naming the SAME hazard PR still warns"),

    # A body that is not review-shaped at all (no paste marker) never
    # becomes a hazard, whatever it contains.
    ([fetch("gh api repos/o/r/pulls/9/reviews", "t7"),
      result("t7", "Nothing to see here, just some findings mentioned in "
                    "passing without any verdict marker."),
      say("Ready for merge.")], False,
     "content with no review-paste marker is not a hazard"),

    # The DISCRIMINATING case for the REVIEW_PASTE gate: a body that
    # classify_verdict()/_unresolved_finding_pattern() would independently
    # score as clean-with-a-finding (a genuine `### Findings` heading and a
    # bare "Ready for merge"), but that carries NEITHER of the corpus's own
    # paste markers (`**Claude finished` / `### Verdict`). The gate 3
    # verdict/finding check alone would let this through, so this is the
    # one case that actually needs the REVIEW_PASTE gate to stay a
    # negative.
    ([fetch("gh api repos/o/r/pulls/11/reviews", "t9"),
      result("t9", "Ready for merge\n\n### Findings\n"
                    "1. `foo()` crashes on empty input.\n"),
      say("Ready for merge.")], False,
     "clean+finding content with no paste marker is still not a hazard"),

    # An ordinary recap with no reviewing activity anywhere.
    ([fetch("git status --short", "t8"), result("t8", "clean"),
      say("All done, everything looks good.")], False,
     "an unrelated recap with no review activity never warns"),
    # Round 8, finding 1: the list-shaped transport must be scanned like the
    # string one. Before the flattener this produced NO warning at all, on the
    # hook's own primary scenario.
    (HAZARD_42_BLOCKS + [say("Reported to the user: Ready for merge.")],
     True, "a list-shaped tool result is still scanned for the hazard"),

    # Round 8, finding 3: the ordinary loop must not warn. Fetch a hazard, fix
    # it, re-fetch genuinely clean, then report clean. This is the corpus's
    # central workflow, so nagging here is what gets a hook switched off.
    (HAZARD_42 + [say("Pushed a fix; requesting re-review.")] + CLEAN_REFETCH_42
     + [say("Ready for merge -- the re-review came back with nothing open.")],
     False, "a clean re-fetch of the same PR supersedes an earlier hazard"),

    # Only a CLEAN re-read supersedes. A second hazard leaves it standing,
    # which is the safe direction.
    (HAZARD_42 + [say("Pushed a fix; requesting re-review.")]
     + [fetch("gh api repos/o/r/pulls/42/reviews", "t10"),
        result("t10", HAZARD_BODY)]
     + [say("Ready for merge.")],
     True, "a second hazard for the same PR does not supersede the first"),

    # A clean re-read of a DIFFERENT PR clears nothing.
    (HAZARD_42 + [fetch("gh api repos/o/r/pulls/99/reviews", "t11"),
                  result("t11", CLEAN_BODY)]
     + [say("Ready for merge.")],
     True, "a clean re-fetch of a different PR does not supersede the hazard"),

    # A re-read that is NOT clean must leave the hazard standing. This reaches
    # the supersede branch (the second fetch is not itself a hazard, so it falls
    # past the hazard arm), which the second-hazard case above does not: there
    # the re-read IS a hazard and never reaches that branch at all. Without this
    # case, widening the branch to clear on ANY re-read survives mutation.
    (HAZARD_42 + [fetch("gh api repos/o/r/pulls/42/reviews", "t12"),
                  result("t12", NOT_CLEAN_BODY)]
     + [say("Ready for merge.")],
     True, "a not-clean re-read of the same PR does not supersede the hazard"),

]


def run(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    try:
        # Fresh sentinel dir per case, so the once-per-message guard does
        # not make later cases silently pass.
        env = dict(os.environ, TMPDIR=tempfile.mkdtemp())
        out = subprocess.run(
            [sys.executable, HOOK], input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True, env=env,
        ).stdout
        return '"systemMessage"' in out
    finally:
        os.unlink(path)


def main():
    passes = failures = 0
    for events, expected, label in CASES:
        got = run(events)
        if got == expected:
            print(f"PASS: {label}")
            passes += 1
        else:
            print(f"FAIL: {label} (expected warn={expected}, got {got})")
            failures += 1

    # This hook must never emit "decision": "block" -- it is warn-only by
    # design (see the docstring's "WARN, NEVER BLOCK").
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in HAZARD_42 + [say("Reported to the user: Ready for merge.")]:
            fh.write(json.dumps(e) + "\n")
    # Fresh sentinel dir, like the once-per-message case below: without it the
    # hook can short-circuit on a sentinel left by an earlier run of this same
    # reply text and never reach the print this case inspects. Reproduced in
    # round 8 -- a mutation emitting a block decision left the suite fully
    # green.
    out = subprocess.run(
        [sys.executable, HOOK], input=json.dumps({"transcript_path": path}),
        capture_output=True, text=True,
        env=dict(os.environ, TMPDIR=tempfile.mkdtemp()),
    ).stdout
    os.unlink(path)
    if '"decision"' not in out and '"block"' not in out:
        print("PASS: never emits a block decision")
        passes += 1
    else:
        print("FAIL: emitted a block decision -- this hook must warn only")
        failures += 1

    # A valid-JSON payload that is not an object must fail OPEN, not raise.
    # json.load succeeds for each of these; only the following .get would fail,
    # which is why the load and the lookup belong in one try (round 8,
    # finding 2).
    for bad in ("[1,2,3]", "42", "null", '"hello"'):
        proc = subprocess.run(
            [sys.executable, HOOK], input=bad,
            capture_output=True, text=True,
            env=dict(os.environ, TMPDIR=tempfile.mkdtemp()),
        )
        if proc.returncode == 0 and not proc.stdout.strip() and "Traceback" not in proc.stderr:
            passes += 1
        else:
            print(
                "FAIL: non-dict payload %s did not fail open "
                "(rc=%s, stderr=%r)" % (bad, proc.returncode, proc.stderr[:200])
            )
            failures += 1
    print("PASS: a valid-JSON non-dict payload fails open")

    # Fires at most once per distinct message.
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in HAZARD_42 + [say("Reported to the user: Ready for merge.")]:
            fh.write(json.dumps(e) + "\n")
    env = dict(os.environ, TMPDIR=tempfile.mkdtemp())
    first = subprocess.run(
        [sys.executable, HOOK], input=json.dumps({"transcript_path": path}),
        capture_output=True, text=True, env=env,
    ).stdout
    second = subprocess.run(
        [sys.executable, HOOK], input=json.dumps({"transcript_path": path}),
        capture_output=True, text=True, env=env,
    ).stdout
    os.unlink(path)
    if '"systemMessage"' in first and '"systemMessage"' not in second:
        print("PASS: fires at most once per distinct message")
        passes += 1
    else:
        print("FAIL: sentinel dedup did not suppress the repeat")
        failures += 1

    # Fails open on an unreadable transcript.
    out = subprocess.run(
        [sys.executable, HOOK], input='{"transcript_path": "/nonexistent"}',
        capture_output=True, text=True,
    )
    if out.returncode == 0 and "systemMessage" not in out.stdout:
        print("PASS: fails open on an unreadable transcript")
        passes += 1
    else:
        print("FAIL: should fail open on an unreadable transcript")
        failures += 1

    # Fails open on unparseable stdin.
    out = subprocess.run(
        [sys.executable, HOOK], input="not json",
        capture_output=True, text=True,
    )
    if out.returncode == 0 and "systemMessage" not in out.stdout:
        print("PASS: fails open on unparseable hook input")
        passes += 1
    else:
        print("FAIL: should fail open on unparseable hook input")
        failures += 1

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
