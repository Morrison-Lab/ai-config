"""Test the no-incomplete-check-enumeration guard.

The guard's whole value is the allow cases: a progress report ("13 pass, 5
pending") must NOT be blocked, and neither must a clean claim already backed
by a complete enumeration. A guard that fires on honest reporting gets
disabled, and then the case it exists for goes unprotected too.

Extended 2026-09-09, written up in ai-config#3472 (the false claims
themselves were made in chat on Morrison-Lab/ai-config#3468 and
d-morrison/macros#87 -- those are the subject PRs, not write-ups), with two
more evidence gaps the original hook missed: broader merge-readiness
vocabulary ("green, awaiting your merge"), and a terminal claim resting
solely on a dispatched subagent's own report rather than on any reading the
conducting session took itself. Both extensions WARN (`systemMessage`)
rather than BLOCK, so this suite asserts the *shape* of the payload -- not
just whether one was printed -- to tell a block from a warn from a silent
allow. See README's "Writing a warn-only hook" section: `bool(out)` alone
cannot make that distinction.

Run: python3 hooks/test-no-incomplete-check-enumeration.py \
         hooks/no-incomplete-check-enumeration.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

PARTIAL = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {"command": "gh pr checks 651 -R ucdavis/bcs"}}]}}
# GraphQL rollup is also a short surface, not the complete instrument
# (ai-config#2277, 2026-08-26).
PARTIAL_ROLLUP = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "gh pr view 2277 --json statusCheckRollup"}}]}}
CHECKER = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "python3 scripts/check-pr-fully-clean.py 651 -R ucdavis/bcs"}}]}}
CHECKER_2277 = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "python3 scripts/check-pr-fully-clean.py 2277 "
                   "-R Morrison-Lab/ai-config"}}]}}
CHECKER_3468 = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "python3 scripts/check-pr-fully-clean.py 3468 "
                   "-R Morrison-Lab/ai-config"}}]}}
# One turn carrying BOTH a push and a complete read -- two tool_use blocks in
# a single message, the shape a real session produces when it pushes and then
# verifies. Both land on the SAME transcript index, so neither `last_push >
# last_complete` nor `last_subagent > last_complete` can fire (#3475 round 2).
PUSH_AND_CHECKER_SAME_TURN = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {"command": "git push -q origin HEAD"}},
    {"type": "tool_use", "input": {
        "command": "python3 scripts/check-pr-fully-clean.py 3468 "
                   "-R Morrison-Lab/ai-config"}}]}}
# An unrelated subagent's report and a partial CI reading returned together
# in ONE turn -- parallel tool calls, results batched. They share a transcript
# index, so `_relevant_last_subagent`'s strict `idx > last_partial` excludes
# the report from the window (#3475 round 4: this boundary decides BLOCK vs
# WARN and was pinned by nothing).
SAME_INDEX_REPORT_AND_PARTIAL = {"type": "user", "message": {"content": [
    {"type": "tool_result", "tool_use_id": "agentX", "content": "done with #9999"},
    {"type": "tool_use", "input": {"command": "gh pr checks 651"}}]}}
# A subagent dispatched and reporting only on #100 (#3475 round 7). Used to
# show that a passing mention of #100 in a message whose CLAIM is about a
# different PR must not make that subagent count as the claim's evidence.
# The subagent genuinely IS the claim's evidence, but the message names a
# closer, unrelated PR before the claim phrase (#3475 round 8).
AGENT_500_DISPATCH = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "a500", "name": "Agent",
     "input": {"prompt": "drive #500 to a clean verdict and report back"}}]}}
AGENT_500_REPORT = {"type": "user", "message": {"content": [
    {"type": "tool_result", "tool_use_id": "a500",
     "content": "#500 is clean: CI green, review CLEAN"}]}}
AGENT_100_DISPATCH = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "a100", "name": "Agent",
     "input": {"prompt": "drive #100 to clean"}}]}}
AGENT_100_REPORT = {"type": "user", "message": {"content": [
    {"type": "tool_result", "tool_use_id": "a100", "content": "#100 done"}]}}
ENDPOINT = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "gh api repos/ucdavis/bcs/commits/a5f4f3f2/check-runs?per_page=100 --paginate"}}]}}
MCP_ENDPOINT = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {"method": "get_check_runs", "pullNumber": 651}}]}}
PUSH = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {"command": "git push -q origin HEAD"}}]}}
# The test file names the checker but must not count as having run it.
TEST_FILE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "python3 scripts/test_check-pr-fully-clean.py"}}]}}

# A sidecar subagent dispatch and its report landing back in the transcript,
# correlated by tool_use_id the way `remind-brief-premises.py` does it. The
# report text mirrors the real incident, made in chat on
# Morrison-Lab/ai-config#3468 (write-up: ai-config#3472).
AGENT_DISPATCH = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "agent1", "name": "Agent",
     "input": {"prompt": "open a PR #3468 for the ratio-macro migration"}}]}}
AGENT_REPORT = {"type": "user", "message": {"content": [
    {"type": "tool_result", "tool_use_id": "agent1",
     "content": "status: CLEAN / MERGEABLE, CI green, @claude review verdict CLEAN"}]}}
# A tool_result whose id does NOT belong to any dispatched agent -- an
# ordinary Bash result must never be misread as a subagent report.
UNRELATED_RESULT = {"type": "user", "message": {"content": [
    {"type": "tool_result", "tool_use_id": "bash1", "content": "ok"}]}}

# Finding 1 (ai-config#3472): a subagent dispatched for a COMPLETELY
# different PR, well before any CI reading is even taken, must not count
# as "involved" in a later, unrelated claim -- the reviewer reproduced this
# flipping the original BLOCK case to a WARN when scoped globally instead
# of to the claim's own evidence window.
UNRELATED_AGENT_DISPATCH = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "agentX", "name": "Agent",
     "input": {"prompt": "look into unrelated task #9999, nothing to do "
                          "with 651"}}]}}
UNRELATED_AGENT_REPORT = {"type": "user", "message": {"content": [
    {"type": "tool_result", "tool_use_id": "agentX", "content": "done with #9999"}]}}

# Finding 1, second half (ai-config#3472 review round 2): the OTHER arm of
# `_relevant_last_subagent`. A subagent dispatched about the SAME PR as the
# claim, landing BEFORE any CI reading, is outside the timing window yet is
# plainly part of this claim's evidence chain -- so `matches_target` must
# carry it. Without a case that isolates this arm, deleting the branch
# entirely left the whole suite passing.
SAME_PR_AGENT_DISPATCH = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "agentY", "name": "Agent",
     "input": {"prompt": "drive #651 to a clean verdict and report back"}}]}}
SAME_PR_AGENT_REPORT = {"type": "user", "message": {"content": [
    {"type": "tool_result", "tool_use_id": "agentY",
     "content": "#651 is clean: CI green, review CLEAN"}]}}

# Finding 2 (ai-config#3472): a relevant subagent report whose index is
# BEFORE the last complete read, but where a later PUSH (not the subagent)
# is what actually leaves the reading needed -- the old, independent
# `last_subagent >= 0 and last_complete <= last_subagent` predicate picks
# the vocab-note here (3 <= 2 is False) even though hit_core matched
# (original vocabulary) and the real reason WARN fired is the subagent,
# not vocabulary. The correct derivation must mention the subagent and
# must NOT claim the vocabulary reason.


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


# (events, expected, label) where expected is "block", "warn", or "allow".
CASES = [
    ([PARTIAL, say("#651 is fully clean at a5f4f3f2.")], "block",
     "the real incident: declared fully clean off gh pr checks alone"),
    ([PARTIAL_ROLLUP, say("#2277 is ready for merge.")], "block",
     "statusCheckRollup alone cannot back a terminal clean claim"),
    ([PARTIAL_ROLLUP, CHECKER_2277, say("#2277 is fully clean.")], "allow",
     "rollup then checker -- claim rests on the complete read"),
    ([PARTIAL_ROLLUP, say("8 success, 0 pending on the rollup.")], "allow",
     "rollup progress report is not a terminal claim"),
    ([PARTIAL, say("21 pass, 0 pending -- ready to merge.")], "block",
     "'ready to merge' backed only by the partial list"),
    ([PARTIAL, say("All checks green, so this is ready for merge.")], "block",
     "'all checks green' off the partial list"),
    ([CHECKER, PUSH, PARTIAL, say("#651 is fully clean.")], "block",
     "the complete read predates the push, so it no longer covers the head"),
    ([PARTIAL, TEST_FILE, say("#651 is fully clean.")], "block",
     "running the checker's TEST file is not running the checker"),

    ([CHECKER, PARTIAL, say("#651 is fully clean.")], "allow",
     "checker ran after nothing was pushed -- claim is covered"),
    ([PARTIAL, CHECKER, say("#651 is fully clean.")], "allow",
     "checker ran last, so the claim rests on the complete read"),
    ([PARTIAL, ENDPOINT, say("#655 is fully clean and ready to merge.")], "block",
     "paginated check-runs is check-half only, not a fully-clean read"),
    ([PARTIAL, MCP_ENDPOINT, say("#651 is fully clean.")], "block",
     "get_check_runs is check-half only, not a fully-clean read"),
    ([ENDPOINT, say("#655 is fully clean and ready to merge.")], "block",
     "check-runs alone cannot back a terminal clean claim"),
    ([MCP_ENDPOINT, say("#651 is fully clean.")], "block",
     "get_check_runs alone cannot back a terminal clean claim"),
    ([PARTIAL_ROLLUP, ENDPOINT, say("#2277 is ready for merge.")], "block",
     "rollup plus check-runs still lacks check-pr-fully-clean.py"),
    ([PARTIAL, say("13 pass, 5 pending -- update-snapshots still running.")], "allow",
     "a progress report is honest and must not be blocked"),
    ([PARTIAL, say("Waiting on the three OS legs; I'll report when they land.")], "allow",
     "naming what is outstanding is not a terminal claim"),
    ([say("#651 is fully clean.")], "allow",
     "no partial reading in play, so there is nothing to warn about"),
    ([PARTIAL, say("Merged and tidied up.")], "allow",
     "no clean declaration at all"),

    # Antigravity format cases
    ([
        {"source": "MODEL", "type": "PLANNER_RESPONSE", "tool_calls": [{"name": "run_command", "args": {"CommandLine": "gh pr checks 651 -R ucdavis/bcs"}}]},
        {"source": "MODEL", "type": "PLANNER_RESPONSE", "content": "#651 is fully clean at a5f4f3f2."}
    ], "block", "antigravity format declared fully clean off gh pr checks blocks"),
    ([
        {"source": "MODEL", "type": "PLANNER_RESPONSE", "tool_calls": [{"name": "run_command", "args": {"CommandLine": "python3 scripts/check-pr-fully-clean.py 651 -R ucdavis/bcs"}}]},
        {"source": "MODEL", "type": "PLANNER_RESPONSE", "content": "#651 is fully clean."}
    ], "allow", "antigravity format with complete check allows"),

    # --- Extension cases: 2026-09-09, written up in ai-config#3472 (subject
    # PRs where the false claims were made in chat: Morrison-Lab/ai-config#3468,
    # d-morrison/macros#87) ---

    ([AGENT_DISPATCH, AGENT_REPORT,
      say("#3468 is fully clean: CI green, @claude verdict CLEAN, no open threads.")],
     "warn",
     "the real incident: a subagent's report relayed with no reading of its own"),
    ([AGENT_DISPATCH, AGENT_REPORT, CHECKER_3468,
      say("#3468 is fully clean.")], "allow",
     "checker ran AFTER the subagent's report -- claim is covered"),
    ([CHECKER_3468, AGENT_DISPATCH, AGENT_REPORT,
      say("#3468 is fully clean.")], "warn",
     "checker ran BEFORE the subagent's report -- stale relative to it"),
    ([AGENT_DISPATCH, UNRELATED_RESULT,
      say("#3468 is fully clean.")], "allow",
     "an unrelated tool_result (wrong id) is not a subagent report"),
    ([PARTIAL, say("#87 is green, awaiting your merge.")], "warn",
     "d-morrison/macros#87: merge-readiness vocabulary outside the original set"),
    ([say("#87 is green, awaiting your merge.")], "allow",
     "merge-ready phrasing with no reading and no subagent -- nothing to warn about"),
    ([PARTIAL, CHECKER, say("#87 is green, awaiting your merge.")], "allow",
     "checker ran last -- the merge-ready phrasing is covered"),
    ([PARTIAL, say("13 pass, 5 pending, waiting on your review.")], "allow",
     "not merge-readiness vocabulary -- 'your review' is not 'your merge'"),

    # --- Finding 1 regression (ai-config#3472): subagent relevance must be
    # scoped to the claim's own evidence, not the whole transcript ---

    ([UNRELATED_AGENT_DISPATCH, UNRELATED_AGENT_REPORT, PARTIAL,
      say("#651 is fully clean at a5f4f3f2.")], "block",
     "an unrelated earlier subagent dispatch (different PR, before the CI "
     "reading) must NOT downgrade the original BLOCK case to a warn"),
    ([PARTIAL, UNRELATED_AGENT_DISPATCH, UNRELATED_AGENT_REPORT,
      say("#651 is fully clean at a5f4f3f2.")], "warn",
     "the same unrelated dispatch, but landing AFTER the CI reading, is in "
     "the claim's evidence window and DOES count (timing-based, per spec)"),
    ([SAME_PR_AGENT_DISPATCH, SAME_PR_AGENT_REPORT, PARTIAL,
      say("#651 is fully clean at a5f4f3f2.")], "block",
     "a same-PR subagent BEFORE the CI reading no longer softens the "
     "canonical case to a warn: the newest evidence is the partial "
     "reading, and target matching stopped routing the decision in round "
     "8 -- it only adds a reason now"),

    # --- Finding 4 regression (ai-config#3472): merge-readiness vocabulary
    # needs a PR/git anchor, not just the bare phrase ---

    ([PARTIAL,
      say("The covariates are good to merge with the outcome table before "
          "we run the model.")], "allow",
     "an ordinary data-frame merge shares the vocabulary but names no PR "
     "-- must not warn"),
    ([PARTIAL,
      say("This branch's covariates are good to merge with the outcome "
          "table.")], "warn",
     "same data-merge sentence, but 'branch' anchors it as PR-readiness "
     "vocabulary within the window"),

    ([PARTIAL, say("#87 is yours now -- your call to merge.")], "warn",
     "'your call to merge' is in the merge-ready vocabulary and was "
     "otherwise untested"),

    # --- #3475 finding 2: with NO CI reading anywhere, `idx > last_partial`
    # was `idx > -1`, true for every event -- so the scoping fix was silently
    # inert in exactly the transcripts that have no partial reading at all,
    # re-admitting the whole transcript through the branch written to stop it.

    ([UNRELATED_AGENT_DISPATCH, SAME_INDEX_REPORT_AND_PARTIAL,
      say("#651 is fully clean at a5f4f3f2.")], "block",
     "an unrelated subagent report sharing a turn with a partial reading is "
     "NOT after it, so it stays outside the window and the original case "
     "still blocks -- the strict `>` boundary, which nothing else pins"),
    ([AGENT_100_DISPATCH, AGENT_100_REPORT,
      say("#100 was closed as a duplicate. #200 is fully clean.")], "warn",
     "matching is permissive on purpose (round 8): a nearby #100 the "
     "subagent worked on earns a WARN, whose cost is noise. What it must "
     "NOT do is block, or suppress a block -- see the #651 case below"),
    ([UNRELATED_AGENT_DISPATCH, UNRELATED_AGENT_REPORT,
      say("Earlier I looked at #9999, which is an unrelated issue in a "
          "different repository and has nothing whatever to do with the "
          "work in front of us here today, mentioned only because it "
          "came up in passing. Moving on to the actual subject: #200 is "
          "fully clean.")], "allow",
     "the window is what keeps permissive matching from reaching a "
     "mention this far from the claim -- whole-message matching would "
     "warn here on the strength of a sentence that disclaims relevance"),
    ([AGENT_500_DISPATCH, AGENT_500_REPORT,
      say("#500: implemented the changes over in #501 as a follow-on. "
          "It's fully clean.")], "warn",
     "the subagent genuinely IS this claim's evidence, but the nearest "
     "reference before the claim is #501 -- narrowing the match to the "
     "single labelled PR silenced the guard entirely here (round 8), so "
     "matching stays permissive over the window"),
    ([AGENT_100_DISPATCH, AGENT_100_REPORT, PARTIAL,
      say("#100 was closed as a duplicate. #651 is fully clean at "
          "a5f4f3f2.")], "block",
     "the canonical BLOCK shape must still block when the message happens "
     "to name another PR that a subagent did work on -- otherwise the "
     "round-1 regression reopens for any multi-PR status recap"),
    ([UNRELATED_AGENT_DISPATCH, UNRELATED_AGENT_REPORT,
      say("#123 is fully clean.")], "allow",
     "no CI reading anywhere: an unrelated dispatch must not make a claim "
     "about a different PR look subagent-sourced (there is no window to be "
     "inside when last_partial is -1)"),
]

# (events, must_contain, must_not_contain, label). The WARN explanation must
# be derived from the condition that ACTUALLY fired, and must never assert
# something the transcript contradicts.
#
# The first case is the one #3475's review caught this suite baking in
# backwards. Shape: AGENT_DISPATCH, AGENT_REPORT, CHECKER_3468, PUSH, claim.
# The session DID run the complete instrument, after the subagent's report --
# so "you are relying on a subagent's report, not a reading you ran yourself"
# is simply false here. What left the claim uncovered is the ordinary PUSH
# after that read. Naming the subagent would be a false statement from a hook
# whose whole purpose is grounding claims in what the transcript shows.
#
# The second case keeps the subagent reason honest in the situation it was
# written for: the report is the LAST evidence, with no complete read after it.
CONTENT_CASES = [
    ([AGENT_DISPATCH, AGENT_REPORT, CHECKER_3468, PUSH,
      say("#3468 is fully clean.")],
     "a `git push` landed after it",
     "dispatched subagent's OWN report",
     "a complete read AFTER the subagent means the push, not the subagent, "
     "is why the claim is uncovered -- the message must say so and must not "
     "blame the subagent"),
    ([CHECKER_3468, AGENT_DISPATCH, AGENT_REPORT,
      say("#3468 is fully clean.")],
     "dispatched subagent's OWN report",
     "a `git push` landed after it",
     "with the subagent's report as the LAST evidence, the subagent reason "
     "is the true one and the push reason must not appear"),
    ([AGENT_100_DISPATCH, AGENT_100_REPORT,
      say("#100 was closed as a duplicate. #200 is fully clean.")],
     "not something the transcript settles",
     "The most recent evidence in this transcript for that claim is a "
     "dispatched",
     "a proximity match is a reason to look, not a fact about what the "
     "claim rests on -- the message must hedge rather than assert that a "
     "#100 subagent is the #200 claim's evidence"),
    ([AGENT_DISPATCH, AGENT_REPORT, PUSH_AND_CHECKER_SAME_TURN,
      say("#3468 is fully clean.")],
     "SAME turn",
     "not a reading you ran yourself",
     "push and complete read in one turn: every `>` guard is false, so "
     "without a tie reason the WARN ships an empty explanation -- and it "
     "must not blame the subagent, since a complete read did happen"),
    ([PARTIAL,
      say("Unrelated to this: #4242 is an issue in another repo, filed "
          "months ago and nothing to do with the work here, mentioned only "
          "because it came up in passing during an unrelated conversation "
          "earlier today about something else entirely. Anyway, this is "
          "fully clean.")],
     "the PR you named",
     "#4242",
     "a far-away reference the message itself calls unrelated must not be "
     "taken as the claim's subject -- an honest vague label beats a "
     "confident wrong one"),
    ([PARTIAL,
      say("#100 was closed as a duplicate. #200 is green, awaiting your "
          "merge.")],
     "#200",
     "about #100",
     "a message naming two PRs must label the claim with the one the claim "
     "is about, not the first reference in the message"),
    ([PARTIAL, PUSH,
      say("#100 is good to merge whenever you're ready.")],
     "no complete instrument read appears anywhere",
     "A complete instrument read is in this transcript",
     "a push after a partial reading, with no complete read ever -- the "
     "message must not claim a complete read exists"),
    ([AGENT_DISPATCH, AGENT_REPORT, PARTIAL,
      say("#3468 is green, awaiting your merge.")],
     "SHORT CI surface",
     "dispatched subagent's OWN report",
     "a partial reading AFTER the subagent's report is the newest evidence, "
     "so the message must name the short CI surface and must not claim the "
     "subagent's report is the most recent thing in the transcript"),
]


def run(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    # The guard fires once per distinct message; clear sentinels so repeated
    # runs of this suite stay deterministic.
    for f in os.listdir(tempfile.gettempdir()):
        if f.startswith("no-incomplete-check-enum-"):
            try:
                os.remove(os.path.join(tempfile.gettempdir(), f))
            except OSError:
                pass
    out = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"transcript_path": path}),
        capture_output=True, text=True,
    ).stdout.strip()
    os.remove(path)
    return out


def classify(out):
    """block / warn / allow, from the raw stdout -- never from bool(out)."""
    if not out:
        return "allow"
    try:
        payload = json.loads(out)
    except Exception:
        return "unparseable:" + out[:80]
    if payload.get("decision") == "block":
        if "reason" not in payload:
            return "malformed-block (decision without reason)"
        return "block"
    # A "decision": "block" payload already returned above, so reaching
    # here means decision is absent or something else -- checking it again
    # was dead code (finding 5, ai-config#3472): unreachable, since the
    # earlier `decision == "block"` branch always returns first.
    if "systemMessage" in payload:
        return "warn"
    return "unparseable:" + out[:80]


def main():
    failures = 0
    total = 0
    for events, want, label in CASES:
        total += 1
        got = classify(run(events))
        ok = got == want
        if not ok:
            failures += 1
        print(f"{'ok  ' if ok else 'FAIL'}  {want:>5} (got {got:>5}): {label}")

    for events, must_contain, must_not_contain, label in CONTENT_CASES:
        total += 1
        out = run(events)
        ok = must_contain in out and must_not_contain not in out
        if not ok:
            failures += 1
        print(f"{'ok  ' if ok else 'FAIL'}  {'content':>5}: {label}")

    print(f"\n{total - failures}/{total} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
