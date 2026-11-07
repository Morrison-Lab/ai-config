#!/usr/bin/env python3
"""Test the no-park-on-tracked-blocker guard.

Run: python3 hooks/test-no-park-on-tracked-blocker.py hooks/no-park-on-tracked-blocker.py
"""
import json
import os
import subprocess
import sys
import tempfile
import uuid

HOOK = sys.argv[1]


def say(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def reply(text):
    return {
        "type": "assistant",
        "message": {"content": [{
            "type": "tool_use",
            "name": "mcp__hearthbot__post_message",
            "input": {"text": text},
        }]},
    }


def send(text):
    return {
        "type": "assistant",
        "message": {"content": [{
            "type": "tool_use",
            "name": "mcp__claude-code-remote__send_message",
            "input": {"message": text},
        }]},
    }


def user(text):
    return {"type": "user", "message": {"content": [{"type": "text", "text": text}]}}


def tool_result():
    return {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}}


def run(entries, active=False):
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e) + "\n")
        path = fh.name
    payload = {
        "transcript_path": path,
        "session_id": str(uuid.uuid4()),
        "stop_hook_active": active,
    }
    try:
        out = subprocess.run(
            [sys.executable, HOOK], input=json.dumps(payload),
            capture_output=True, text=True, timeout=20,
        ).stdout.strip()
    finally:
        os.unlink(path)
    return json.loads(out) if out else {}


def blocked(entries, active=False):
    return run(entries, active).get("decision") == "block"


CASES = [
    # (name, entries, expect_block)
    ("measured case", [reply("**Stopping Point**: Not clean; mds#649 waits on gha#1544.")], True),
    ("blocked by url", [say("This is blocked by https://github.com/o/r/issues/12 for now.")], True),
    ("depends on bare ref", [say("The stub change depends on #1545.")], True),
    ("until merges", [say("I'll hold the mds PR until gha#1545 merges.")], True),
    ("person gate passes", [say("mcs#99 waits on your approval.")], False),
    ("needs you passes", [say("gha#12 is blocked: it needs you to rotate the secret.")], False),
    ("no ref passes", [say("CI is still waiting on the runner.")], False),
    ("code span passes", [say("The phrase `waits on gha#1` is what the hook matches.")], False),
    ("plain status passes", [say("I merged mds#679, which closed #656.")], False),
    ("every output in the turn counts", [say("x waits on #3."), reply("All merged.")], True),
    ("wrapped line still caught", [say("mds#649 waits\non gha#1544, so I stopped.")], True),
    ("pending phrasing", [say("The stub PR is held pending gha#1545.")], True),
    ("no longer passes", [say("Unblocked: #5 no longer depends on #6.")], False),
    ("depends on nothing passes", [say("Done: closes #5; this depends on nothing.")], False),
    ("past tense passes", [say("I waited for #12 to merge, and it did.")], False),
    ("user gate passes", [say("Blocked on user: #5")], False),
    ("ezra's approval passes", [say("#5 is blocked on Ezra's approval.")], False),
    ("mwc passes", [say("PR #5 waits on mwc from the user.")], False),
    ("human-readable is not a gate", [say("It is human-readable, but waits on #5.")], True),
    ("separate bullets stay separate", [say("- waits on a fix\n- merged #4")], False),
    ("malformed lines tolerated", [[1], "x", {"type": "assistant", "message": "str"},
                                   say("x waits on #5.")], True),
    # ai-config#5063 review findings (agy, 2026-11-07).
    ("earlier turn's park does not block", [reply("mds#649 waits on gha#1544."), user("go"),
                                            say("I drove gha#1544 and merged mds#649; all done.")], False),
    ("earlier turn's all-clear does not hide", [reply("All clean."), user("go"),
                                                say("mds#649 waits on gha#1544.")], True),
    ("tool result is not a new turn", [reply("mds#649 waits on gha#1544."), tool_result()], True),
    ("CI wait with a later ref passes", [say("Waiting on CI for #12.")], False),
    ("ref as subject passes", [say("PR #12 is waiting on the macOS runner before auto-merge fires.")], False),
    ("past-tense which-clause passes", [say("I merged gha#1545, which mds#649 was waiting on.")], False),
    ("table rows stay separate", [say("| #12 | Merged |\n| Release | Waiting on tag build |")], False),
    ("status lines stay separate", [say("Merged #12\nWaiting on the deploy job")], False),
    ("until url merges", [say("Holding mds#685 until https://github.com/o/r/pull/12 merges.")], True),
    ("until dotted repo merges", [say("Holding it until owner/repo.name#7 merges.")], True),
    ("depending on", [say("Stopping here, depending on gha#1544.")], True),
    ("depend on", [say("Both mds#649 and mds#650 depend on gha#1544.")], True),
    ("held until ready", [say("mds#649 is held until gha#1544 is ready.")], True),
    ("bare mwc does not exempt", [say("Even with mwc active, mds#649 waits on gha#1544.")], True),
    ("bare approval does not exempt", [say("The token-approval PR (#649) waits on gha#1544.")], True),
    ("bare no longer does not exempt", [say("mds#649 no longer fails lint, and now waits on gha#1544.")], True),
    ("file anchor is not an item", [say("The test waits on [section 2](README.md#2) of the spec.")], False),
    ("send_message payload checked", [send("mds#649 waits on gha#1544.")], True),
    ("park then closing line still blocks", [send("mds#649 waits on gha#1544."), say("Reported in the thread.")], True),
    ("ref in a code span still an item", [say("mds#649 waits on `gha#1544`.")], True),
    ("filler before the item", [say("mds#649 waits on the PR for gha#1544.")], True),
    ("CI-noun object then a ref line", [say("Status: waiting on upstream\n#12 merged cleanly")], False),
    ("gate in another clause does not exempt", [say("gha#10 is unblocked now, but mds#649 waits on gha#1544.")], True),
    ("which-clause person gate exempts", [say("This waits on #5, which requires a manual action on a device.")], False),
    ("until without a parking verb passes", [say("I ran the watcher loop until #12 is merged, and all checks are now green.")], False),
    ("parked on", [say("mds#649 is parked on gha#1544.")], True),
    ("once item merges", [say("I'll pick mds#649 back up once gha#1544 merges.")], True),
    ("needs to merge first", [say("gha#1544 needs to merge first.")], True),
    ("meta line is not a user turn", [reply("mds#649 waits on gha#1544."),
                                      {"type": "user", "isMeta": True,
                                       "message": {"content": [{"type": "text", "text": "note"}]}}], True),
    ("reminder is not a user turn", [reply("mds#649 waits on gha#1544."), user("<system-reminder>x</system-reminder>")], True),
    ("json anchor is not an item", [say("The test waits on docs/spec.json#2.")], False),
    ("possessive ref is not the object", [say("I'll wait for #12's CI.")], False),
    # Round 3 (agy): bypasses.
    ("which-unblocked does not exempt", [say("mds#649 waits on gha#1544, which is unblocked.")], True),
    ("which-depends-on-nothing does not exempt", [say("mds#649 waits on gha#1544, which depends on nothing.")], True),
    ("since-no-longer-blocked does not exempt",
     [say("mds#649 waits on gha#1544, since gha#1544 is no longer blocked.")], True),
    ("bare and splits clauses", [say("gha#10 is unblocked and mds#649 waits on gha#1544.")], True),
    ("wrapped filler before ref", [say("mds#649 waits on the\ngha#1544 PR.")], True),
    ("linked ref before merges",
     [say("I'll pick mds#649 back up once [gha#1545](https://github.com/o/r/pull/1545) merges.")], True),
    ("linked ref needs to merge first", [say("[gha#1544](https://github.com/o/r/pull/1544) needs to merge first.")], True),
    ("needs to be merged first", [say("gha#1544 needs to be merged first.")], True),
    ("code span with PR prefix", [say("mds#649 waits on `PR #1544`.")], True),
    ("workflow PR is an item", [say("mds#649 waits on the workflow PR gha#1544.")], True),
    ("test fix in item", [say("mds#649 waits on the test fix in gha#1544.")], True),
    ("awaiting", [say("mds#649 is awaiting gha#1544.")], True),
    ("is blocking", [say("gha#1544 is blocking mds#649.")], True),
    ("gated on", [say("mds#649 is gated on gha#1544.")], True),
    ("still pending", [say("mds#649 is still pending gha#1544.")], True),
    # Round 3 (agy): false positives.
    ("wrapped person gate", [say("mcs#99 waits on\n#12 for your approval.")], False),
    ("wrapped phrase then manual gate", [say("mcs#99 waits\non #12, which requires a manual action.")], False),
    ("wrapped no longer", [say("#5 no longer\nwaits on #6.")], False),
    ("stopping point label is not a park verb",
     [say("**Stopping Point**: Clean; I polled until #12 is merged, and all checks are green.")], False),
    ("past-tense until is a report", [say("I waited until #12 is merged, and all checks are now green.")], False),
    ("until with your approval", [say("I'm holding #5 until #6 merges with your approval.")], False),
    ("auto-merge report", [say("Auto-merge will fire once #12 is ready.")], False),
    ("auto-close report", [say("GitHub closes #10 automatically when #12 merges.")], False),
    ("deploy report", [say("The deploy workflow runs after #12 lands.")], False),
    ("codecov for item", [say("Waiting on codecov for #12.")], False),
    ("benchmark results for item", [say("Waiting on benchmark results for #12.")], False),
    ("leading because gate", [say("Because this needs your approval, mcs#99 waits on #12.")], False),
    ("semicolon it-clause gate", [say("mcs#99 waits on #12; it needs your approval.")], False),
    ("requires your secret", [say("mcs#99 waits on #12, which requires your secret.")], False),
    ("needs a secret", [say("mcs#99 waits on #12, which needs a secret.")], False),
    ("until you approve", [say("mcs#99 waits on #12 until you approve it.")], False),
    ("possessive url", [say("I'll wait for https://github.com/o/r/pull/12's CI.")], False),
    ("possessive code span", [say("I'll wait for `#12`'s CI.")], False),
    ("possessive link", [say("I'll wait for [#12](https://github.com/o/r/pull/12)'s CI.")], False),
    # Round 4 (agy): gate positions.
    ("comma-and it-clause gate", [say("mcs#99 waits on #12, and it needs your approval.")], False),
    ("comma-but it-clause gate", [say("mcs#99 waits on #12, but it requires a manual action.")], False),
    ("comma-and until-you gate", [say("mcs#99 waits on #12, and until you approve it I cannot merge.")], False),
    ("compound which-clause gate", [say("mcs#99 waits on #12, which touches prod and needs your approval.")], False),
    ("compound because-clause gate",
     [say("Because #12 touches prod and needs your approval, mcs#99 waits on #12.")], False),
    # Round 4: a form spanning clauses is judged by its last clause.
    ("form after an unblocked clause",
     [say("I'll merge #10 since it is unblocked, and I'll resume #11 once #12 merges.")], True),
    ("form after an approval clause",
     [say("I'll ask for your approval on #10, and I'll pick #11 back up once #12 merges.")], True),
    ("until-form after an approval clause",
     [say("I'm leaving #10 for your approval and holding #11 until #12 merges.")], True),
    ("until-form after an unblocked clause",
     [say("I'm keeping #10 as unblocked and holding #11 until #12 merges.")], True),
    # Round 4: modifiers and plurals before "for <item>".
    ("open PR for item", [say("mds#649 waits on the open PR for gha#1544.")], True),
    ("upstream PR for item", [say("mds#649 waits on the upstream PR for gha#1544.")], True),
    ("workflow fix for item", [say("mds#649 waits on the workflow fix for gha#1544.")], True),
    ("pull requests for item", [say("mds#649 waits on the pull requests for gha#1544.")], True),
    ("resolution of item", [say("mds#649 is blocked on the resolution of gha#1544.")], True),
    # Round 4: the object ends at a clause boundary or conjunction.
    ("colon ends object", [say("Waiting on CI: #12 merged cleanly.")], False),
    ("dash ends object", [say("Waiting on the runner \u2014 #12 is already merged.")], False),
    ("and ends object", [say("Waiting on the runner and #12 is already merged.")], False),
    ("CI in item", [say("Waiting on CI in #12.")], False),
    ("while ends object", [say("Waiting on the runner while #12 finishes CI.")], False),
    ("because ends object", [say("Waiting on CI because #12 flushed the cache.")], False),
    ("wrap after merge ends object", [say("Waiting on the merge\n#12 is already deployed.")], False),
    ("wrap after fix ends object", [say("Waiting on the fix\n#12 merged cleanly.")], False),
    ("indented wrap after filler", [say("mds#649 waits on the\n     gha#1544 PR.")], True),
    # Round 4: reports.
    ("blocks a non-item", [say("PR #5063 blocks a reply that parks work.")], False),
    ("fix blocks inputs", [say("The fix in #12 blocks invalid inputs from crashing the worker.")], False),
    ("no longer gated", [say("#5 is no longer gated on #6.")], False),
    ("no longer parked", [say("#5 is no longer parked on #6.")], False),
    ("no longer awaits", [say("#5 no longer awaits #6.")], False),
    ("not gated", [say("#5 is not gated on #6.")], False),
    ("after waiting report", [say("After waiting on #12 to pass CI, I merged it.")], False),
    ("spent waiting report", [say("I spent two minutes waiting for #12 to finish CI, then merged it.")], False),
    ("stays until is a report", [say("The workaround stays in place until #12 lands.")], False),
    ("keep polling until merges is a park", [say("I'll keep polling CI until #12 merges.")], True),
    # Round 4: code and late person gates.
    ("fenced ref is code", [say("The parser waits on\n```\n#12\n```\nin the fixture.")], False),
    ("for your sign-off", [say("mcs#99 waits on #12 for your sign-off.")], False),
    ("for your token", [say("mcs#99 waits on #12 for your token.")], False),
    ("for a manual merge", [say("mcs#99 waits on #12 for a manual merge.")], False),
    # Claude review of d5b7501a: a leading while/after clause is not narrative.
    ("leading while clause park", [say("While mds#649 waits on gha#1544, I'll do something else.")], True),
    ("while waiting then future", [say("While waiting on #12, I will do something else.")], True),
    ("leading after clause park",
     [say("After mds#649 waits on gha#1544 a while longer, I'll check again.")], True),
    ("while waiting past report", [say("While waiting on #12, I fixed the lint warnings.")], False),
    # Round 5 (agy).
    ("while earlier in clause", [say("I'm pausing work here while mds#649 waits on gha#1544.")], True),
    ("after in a noun phrase", [say("The follow-up PR after #10 waits on gha#1544.")], True),
    ("CI pending on item", [say("CI is pending on #12.")], False),
    ("checks pending on item", [say("2 checks are still pending on #12.")], False),
    ("does not depend", [say("mds#649 does not depend on gha#1544.")], False),
    ("not dependent", [say("mds#649 is not dependent on gha#1544.")], False),
    ("no longer on hold", [say("mds#649 is no longer on hold for gha#1544.")], False),
    ("not held up", [say("mds#649 is not held up by gha#1544.")], False),
    ("for you to approve", [say("mcs#99 waits on #12 for you to approve it.")], False),
    ("for manual approval", [say("mcs#99 waits on #12 for manual approval.")], False),
    ("until Ezra approves", [say("mcs#99 waits on #12 until Ezra approves it.")], False),
    ("gated on mwc", [say("mcs#99 waits on #12, which is gated on mwc.")], False),
    ("bare since carries no exemption", [say("mds#649 waits on gha#1544 since gha#1544 is unblocked.")], True),
    ("status line carries no exemption", [say("#10: unblocked\nmds#649 waits on gha#1544")], True),
    ("paused until", [say("mds#649 is paused until gha#1544 merges.")], True),
    ("deferred until", [say("mds#649 is deferred until gha#1544 merges.")], True),
    ("patch for item", [say("mds#649 waits on the patch for gha#1544.")], True),
    ("blocking the PR for item", [say("gha#1544 is blocking the PR for mds#649.")], True),
    # Round 5 (agy, on the narrative change).
    ("stopping while waiting", [say("Stopping here while waiting on #12.")], True),
    ("pausing while waiting", [say("I'm pausing mds#649 while waiting on gha#1544.")], True),
    ("while waiting then present", [say("While waiting on #12, I'm working on #13.")], True),
    ("past narrative with a later future",
     [say("After waiting on #12 to pass CI, I merged it and I'll start #13 next.")], False),
    ("while still waiting report", [say("While still waiting on #12, I fixed the lint warnings.")], False),
    ("spent a long duration", [say("I spent about two more minutes waiting for #12, then merged it.")], False),
    # Claude reviews of 45165a5c and e5ad0766: the past verb must be the wait's own.
    ("past then unrelated future", [say("After waiting on #12 to pass CI, I merged it, and I will tag a release.")], False),
    ("spent then future", [say("I spent two minutes waiting for #12 to finish CI, and I will now clean up.")], False),
    ("while earlier then future", [say("While waiting on #12 earlier, I filed a follow-up; I will check back tomorrow.")], False),
    ("unrelated past verb does not exempt",
     [say("I've already merged #20, but after waiting on #12, I'll start #13 instead.")], True),
    ("everything after item", [say("Everything after #10 depends on gha#1544.")], True),
    # Antigravity transcript shape.
    ("antigravity park blocks", [{"type": "USER_INPUT", "content": "go", "step_index": 1},
                                 {"type": "PLANNER_RESPONSE", "content": "mds#649 waits on gha#1544.",
                                  "step_index": 2}], True),
    ("antigravity earlier turn does not block",
     [{"type": "PLANNER_RESPONSE", "content": "mds#649 waits on gha#1544.", "step_index": 1},
      {"type": "USER_INPUT", "content": "go", "step_index": 2},
      {"type": "PLANNER_RESPONSE", "content": "Merged both; all done.", "step_index": 3}], False),
    # Round 6 (opencode/glm-5.3-flash-free on cf463-02).
    ("odd text block does not hide a park",
     [say("mds#649 waits on gha#1544."),
      {"type": "assistant", "message": {"content": [{"type": "text", "text": 123}]}}], True),
    ("string tool input does not hide a park",
     [say("mds#649 waits on gha#1544."),
      {"type": "assistant", "message": {"content": [{
          "type": "tool_use", "name": "mcp__hearthbot__post_message", "input": "x"}]}}], True),
    ("numeric tool name does not hide a park",
     [say("mds#649 waits on gha#1544."),
      {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": 5, "input": {}}]}}], True),
    ("while waiting I left the rest", [say("While waiting on #12, I left the rest for the morning.")], True),
    ("after waiting I finally stopped", [say("After waiting on gha#1544 all morning, I finally stopped.")], True),
    ("after waiting then stopped", [say("After waiting on #12, then stopped.")], True),
    ("the wait is over", [say("The wait on gha#1544 is over, and mds#649 is merged cleanly.")], False),
    ("comma then your sign-off", [say("mcs#99 waits on #12, for your sign-off.")], False),
    ("the maintainer's sign-off", [say("mcs#99 waits on #12 for the maintainer's sign-off.")], False),
    ("upstream maintainers to sign off", [say("mcs#99 waits on #12 for upstream maintainers to sign off.")], False),
    ("the user's OK", [say("mcs#99 waits on #12 for the user's OK.")], False),
    ("once item is green", [say("I'll rerun the export once CI on #12 is green.")], True),
    ("comma then a non-person for clause", [say("mcs#99 waits on #12, for the CI rerun.")], True),
    # Round 6b (glm-5.3 on ef3ec136).
    ("past verb after so", [say("After waiting on #12 for CI, the run went green, so I merged it.")], False),
    ("comma-less after report", [say("After waiting on #12 I merged it.")], False),
    ("comma-less while report", [say("While waiting on #12 I merged #13.")], False),
    ("subjectless then merged", [say("After waiting on #12 for CI, then merged the follow-up.")], True),
    ("comma-less while then stopping", [say("While waiting on #12 I stopped.")], True),
    # Round 7 (glm-5.3 on eb8f08f3).
    ("ended up merging", [say("After waiting on #12, I ended up merging it before lunch.")], False),
    ("put a patch up", [say("While waiting on #12, I put the final patch up in #13 and merged the docs fix.")], False),
    ("kept CI green", [say("While waiting on #12, I kept the CI green and filed the release notes.")], False),
    ("left review comments", [say("After waiting on #12, I left review comments on the sub-issues.")], False),
    ("ended there", [say("After waiting on #12, I ended there.")], True),
    ("put it aside", [say("While waiting on #12, I put the export aside.")], True),
    ("then called it a day", [say("After waiting on #12, then called it a day.")], True),
    ("once item gets approved", [say("I'll tag the release once gha#1544 gets approved.")], True),
    ("for the team to review", [say("mcs#99 waits on #12, for the team to review the patch.")], False),
    ("for them to review", [say("mcs#99 waits on #12, for them to review it.")], False),
    ("for a named person to sign off", [say("mcs#99 waits on #12, for Dana to sign off.")], False),
    ("for the bot to review", [say("mcs#99 waits on #12, for the review bot to review it.")], True),
    ("for CI to finish", [say("mcs#99 waits on #12 for CI to finish.")], True),
    # Claude review of bceff310: a stop verb with a work object is a report.
    ("left a comment then future", [say("After waiting on #12 to pass CI, I left a comment, and I will tag a release.")], False),
    ("held a meeting then future", [say("After waiting on #12 to pass CI, I held a meeting, and I will tag a release.")], False),
    ("kept notes then future", [say("While waiting on #12, I kept my notes updated, and I will check back tomorrow.")], False),
    ("put a comment then future", [say("After waiting on #12 to pass CI, I put a comment on it, and I will tag a release.")], False),
    ("held off on the rest", [say("While waiting on #12, I held off on the rest.")], True),
    # glm review of bceff310: stopping in other words, the subject check,
    # and "so" carried through ", and so", "; so" and ", So".
    ("so called it a day", [say("After waiting on #12 for CI, the run went green, so I called it a day.")], True),
    ("decided to stop", [say("After waiting on #12 I decided to stop for the night.")], True),
    ("so decided to stop", [say("After waiting on #12 for CI, the run went green, so I decided to stop.")], True),
    ("so wrapped up", [say("After waiting on #12 for CI, the run went green, so I wrapped up.")], True),
    ("subject before the wait", [say("I checked the build, after waiting on #12 for CI, then merged it.")], False),
    ("and so merged", [say("After waiting on #12 for CI, the run went green, and so I merged it.")], False),
    ("semicolon so merged", [say("After waiting on #12 for CI, the run went green; so I merged it.")], False),
    ("capital So merged", [say("After waiting on #12 for CI, the run went green, So I merged it.")], False),
    # Claude review of 3f2b2ca6: those verbs report work only with a work object.
    ("held the fix in place", [say("After waiting on #12, I held the fix in place.")], True),
    ("held the branch steady", [say("After waiting on #12, I held the branch steady.")], True),
    ("held notes in a draft", [say("While waiting on #12, I held my notes in a draft.")], True),
    ("ended my investigation", [say("After waiting on #12, I ended my investigation.")], True),
    ("put findings in the doc", [say("After waiting on #12, I put my findings in the doc.")], True),
    ("kept an eye on it", [say("After waiting on #12, I kept my eye on the dashboard.")], True),
    ("left notes in the doc", [say("While waiting on #12, I left my notes in the doc.")], True),
    # glm review of d0061280.
    ("for Dependabot to approve", [say("mcs#99 waits on #12, for Dependabot to approve the bump.")], True),
    ("for Renovate to approve", [say("mcs#99 waits on #12, for Renovate to approve the bump.")], True),
    ("for the canary to confirm", [say("mcs#99 waits on #12, for the canary to confirm the rollout.")], True),
    ("waits on them refs", [say("mds#649 waits on them (gha#100, gha#101).")], True),
    ("for Dana to merge", [say("mcs#99 waits on #12, for Dana to merge the patch.")], False),
    ("for Dana to sign", [say("mcs#99 waits on #12, for Dana to sign the release.")], False),
    ("for the lead reviewer", [say("mcs#99 waits on #12, for the lead reviewer to sign off.")], False),
    ("for the release manager", [say("mcs#99 waits on #12, for the release manager to sign off.")], False),
    ("put the hotfix up", [say("While waiting on #12, I put the hotfix up for tomorrow's release.")], False),
    # Claude review of b45e9d54: a stop word with an object reports work.
    # A plan is not a report, and a stop verb stops whatever its object
    # (KNOWN LIMITS); another verb for the work makes it pass.
    ("stop by tomorrow", [say("After waiting on #12, I'll stop by to check on #13 tomorrow.")], True),
    ("fixed the leak", [say("After waiting on #12, I fixed the leak in the retry logic and merged it.")], False),
    ("stop-loss logic", [say("After waiting on #12, I fixed the stop-loss logic and merged it.")], False),
    ("signed off on the release", [say("After waiting on #12, I signed off on the release and merged it.")], False),
    ("wrapped up the docs", [say("After waiting on #12, I wrapped up the documentation and merged it.")], False),
    ("stopped the leak", [say("After waiting on #12, I stopped the leak in the retry logic and merged it.")], True),
    # glm review of b45e9d54.
    ("merged then called it a day", [say("After waiting on #12 for CI, I merged it, so I called it a day.")], False),
    ("wrapped up a fix then merged", [say("While waiting on #12, I wrapped up the flaky-test fix, and I merged it.")], False),
    ("for the merge queue", [say("mds#649 waits on #12, for the merge queue to merge it.")], True),
    ("them for approval", [say("I sent the patch to both reviewers; mds#649 waits on them (#12) for approval.")], False),
    ("then called it a day", [say("After waiting on #12 for CI, then called it a day.")], True),
    # Claude review of 42e59183: every stop time counts.
    ("signed off for the evening", [say("After waiting on #12, I signed off for the evening.")], True),
    ("signed off for the morning", [say("After waiting on #12, I signed off for the morning.")], True),
    ("logged off for the evening", [say("After waiting on #12, I logged off for the evening.")], True),
    ("left the rest for the afternoon", [say("While waiting on #12, I left the rest for the afternoon.")], True),
    # Claude review of fd98389a: a stop before the wait, with no comma.
    ("signed off after waiting", [say("I signed off for the evening after waiting on #12.")], True),
    ("called it a day after waiting", [say("I called it a day after waiting on #12.")], True),
    ("logged off after waiting", [say("I logged off for the night after waiting on #12.")], True),
    ("wrapped up after waiting", [say("I wrapped up after waiting on #12.")], True),
    ("merged after waiting", [say("I merged it after waiting on #12.")], False),
    # Claude review of cf664932: a reason or a time after the stop word is a report.
    ("wrapped up before the deadline", [say("After waiting on #12, I wrapped up before the deadline.")], False),
    ("wrapped up since ready", [say("After waiting on #12, I wrapped up since the release was ready.")], False),
    ("logged off once deployed", [say("After waiting on #12, I logged off once the deploy finished.")], False),
    ("called it a day when shipped", [say("After waiting on #12, I called it a day when the release shipped.")], False),
    ("signed off because fine", [say("After waiting on #12, I signed off because the release looked fine.")], False),
    ("signed off as manager", [say("After waiting on #12, I signed off as the release manager.")], False),
    # glm reviews of 42e59183 through ea935254.
    ("switched off for the night", [say("After waiting on #12, I switched off for the night.")], True),
    ("took a break then a night", [say("After waiting on #12, I took a break, so I called it a night.")], True),
    ("stop here for today", [say("After waiting on #12, I decided to stop here for today.")], True),
    ("stop here for now", [say("After waiting on #12, I decided to stop here for now.")], True),
    ("wrapped things up", [say("After waiting on #12, I wrapped things up for the day.")], True),
    ("signed off notes for the day", [say("After waiting on #12, I signed off the release notes for the day.")], True),
    ("approval by the label bot", [say("mds#649 waits on gha#1544 for approval by the label bot.")], True),
    ("signed off the notes", [say("After waiting on #12, I signed off the release notes.")], False),
    ("decided to stop comma", [say("After waiting on #12 I decided to stop, and #13 can wait.")], True),
    # Claude review of ea935254: a reason naming another item, or a stop
    # before an action, is still a stop.
    ("signed off before reviewing #13", [say("After waiting on #12, I signed off before continuing to review #13.")], True),
    ("signed off before anything else", [say("After waiting on #12, I signed off before doing anything else.")], True),
    ("wrapped up before starting #13", [say("After waiting on #12, I wrapped up before starting #13.")], True),
    ("called it a day before #13", [say("After waiting on #12, I called it a day before looking at #13.")], True),
    ("signed off since #13 is owed", [say("After waiting on #12, I signed off since I still need to review #13.")], True),
    ("wrapped up because of #13", [say("After waiting on #12, I wrapped up because I plan to pick up #13 tomorrow.")], True),
    ("signed off when #13's review", [say("After waiting on #12, I signed off when #13's review comes up tomorrow.")], True),
    ("logged off as #13 is owed", [say("While waiting on #12, I logged off as I still owe #13 a look tomorrow.")], True),
    ("signed off because #12 merged", [say("After waiting on #12, I signed off because #12 merged.")], False),
    # Claude review of aa5742e0: a bare "and" before other work ends no stop.
    ("wrapped things up and merged", [say("After waiting on #12, I wrapped things up and merged #13.")], False),
    ("wrapped everything up and filed", [say("While waiting on #12, I wrapped everything up and filed the release notes.")], False),
    ("wrapped up and merged", [say("After waiting on #12, I wrapped up and merged #13.")], False),
    ("called it a day and logged off", [say("After waiting on #12, I called it a day and logged off.")], True),
    ("wrapped things up and signed off", [say("After waiting on #12, I wrapped things up and signed off.")], True),
    # Claude review of 612d9300: every stop verb counts after a bare "and".
    ("wrapped up and halted", [say("After waiting on #12, I wrapped things up and halted.")], True),
    ("wrapped up and shelved it", [say("After waiting on #12, I wrapped things up and shelved it.")], True),
    ("wrapped up and left it there", [say("After waiting on #12, I wrapped things up and left it there.")], True),
    ("wrapped up and held off", [say("After waiting on #12, I wrapped things up and held off.")], True),
    ("wrapped up and left comments", [say("After waiting on #12, I wrapped things up and left review comments.")], False),
    # Claude review of 0ef18d1a: a stop verb with a real object is other news.
    ("wrapped up and quit smoking", [say("After waiting on #12, I wrapped things up and quit smoking.")], False),
    ("wrapped up and suspended the job", [say("After waiting on #12, I wrapped things up and suspended the other job for review.")], False),
    ("wrapped up and postponed the meeting", [say("After waiting on #12, I wrapped things up and postponed the meeting to next week.")], False),
    ("wrapped up and quit side project", [say("While waiting on #12, I wrapped things up and quit my side project.")], False),
    ("wrapped up and suspended work", [say("After waiting on #12, I wrapped things up and suspended work.")], True),
    # Claude review of 0cf39895: a time or a dash after the stop verb ends it.
    ("halted - see you tomorrow", [say("After waiting on #12, I wrapped things up and halted - see you tomorrow.")], True),
    ("halted em dash", [say("After waiting on #12, I wrapped things up and halted \u2014 see you tomorrow.")], True),
    ("halted today", [say("After waiting on #12, I wrapped things up and halted today.")], True),
    ("halted for now", [say("After waiting on #12, I wrapped things up and halted for now.")], True),
    # glm review of fd98389a: a time of day after the day is still a time.
    ("stop until tomorrow afternoon", [say("After waiting on gha#1544, I decided to stop until tomorrow afternoon.")], True),
    ("sole string-input reply blocks",
     [{"type": "assistant", "message": {"content": [{
         "type": "tool_use", "name": "mcp__hearthbot__post_message",
         "input": "mds#649 waits on gha#1544."}]}}], True),
]


def main():
    failures = 0
    for name, entries, expect in CASES:
        got = blocked(entries)
        if got != expect:
            failures += 1
            print(f"FAIL {name}: expected block={expect}, got {got}")
    if blocked([say("mds#649 waits on gha#1544.")], active=True):
        failures += 1
        print("FAIL stop_hook_active must not block")
    for raw in ("null", "[]", '"x"', "5"):
        res = subprocess.run([sys.executable, HOOK], input=raw, capture_output=True, text=True, timeout=20)
        if res.returncode != 0 or res.stdout.strip():
            failures += 1
            print(f"FAIL non-object payload {raw}: rc={res.returncode} {res.stderr.strip()[:80]}")
    total = len(CASES) + 5
    print(f"{total - failures} of {total} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
