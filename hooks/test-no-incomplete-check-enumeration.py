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
      say("#651 is fully clean at a5f4f3f2.")], "warn",
     "a subagent dispatched about the SAME PR, before the CI reading, is "
     "outside the timing window but matches the claim's target -- the "
     "matches_target arm must carry it (compare the unrelated-#9999 case "
     "directly above, identical in shape, which blocks)"),

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
]

# (events, must_contain, must_not_contain, label) -- finding 2 regression
# (ai-config#3472): the WARN explanation must be derived from the condition
# that actually fired, not from an independent predicate that can disagree
# with it. This case has hit_core match ("fully clean" -- original
# vocabulary) with a RELEVANT subagent report whose index sits before the
# eventual PUSH: the old predicate `last_subagent >= 0 and last_complete <=
# last_subagent` evaluates False here (last_complete=3 > last_subagent=2),
# so it would wrongly print the vocabulary explanation even though the
# claim used no merge-ready vocabulary at all and the real reason is the
# subagent's stale report.
CONTENT_CASES = [
    ([AGENT_DISPATCH, AGENT_REPORT, CHECKER_3468, PUSH,
      say("#3468 is fully clean.")],
     "dispatched subagent's OWN report",
     "without the vocabulary this guard originally keyed on",
     "source_note must name the subagent as the reason, never fabricate "
     "the vocabulary explanation, when hit_core matched and a relevant "
     "subagent -- not vocabulary -- is why WARN fired"),
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
