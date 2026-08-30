"""Test the no-empty-promise Stop guard.

Both directions matter, and the negative one matters more. The guard blocks,
so a false positive stops a correct reply from going out -- and a blocking
guard that misfires is the one people switch off, taking the real cases with
it (README, "A hook that misfires is worse than a missing one").

Three near-misses are load-bearing:
  * an ordinary next-action statement ("I'll open the PR now") is not a
    promise -- the generalizer is what makes one;
  * a capability limit ("I'll never be able to know the exact time") uses the
    same words and commits to nothing;
  * quoting the rule while discussing it, which this corpus does constantly.

The #1946 block below adds the other axis: a promise stated as a DEBT ("I owe
#1937 the ARDI loop") discharges on an armed FIRING as well as on a durable
record, while a RULE promise still discharges only on the durable one. The
near-misses that decide whether that is usable are the arming-shaped calls
that deliver nothing -- `stop: true`, a cron LIST, an `ardi` run that already
happened, and the word "schedule" sitting in a read-only brief.

Run: python3 hooks/test-no-empty-promise.py hooks/no-empty-promise.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

WROTE_FRAGMENT = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Write",
     "input": {"file_path": "shared/workflow/no-empty-promises.md",
               "content": "..."}}]}}
WROTE_HOOK = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Write",
     "input": {"file_path": "hooks/no-empty-promise.py", "content": "..."}}]}}
WROTE_MEMORY = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Edit",
     "input": {"file_path": "memories/preferences.md",
               "old_string": "a", "new_string": "b"}}]}}
FILED_ISSUE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Bash",
     "input": {"command": "gh issue create -R o/r --title x --body y"}}]}}
UNRELATED = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Bash", "input": {"command": "git status"}}]}}
WROTE_VIA_BASH = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Bash",
     "input": {"command": "cat > shared/workflow/x.md <<'EOF'\nrule\nEOF"}}]}}
DISPATCHED_UMS = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Task",
     "input": {"prompt": "Run a ums pass recording this learning.",
               "description": "owed UMS pass"}}]}}
# A brief that DESCRIBES writing is still only a brief. What discharges a
# delegated mechanism is the subagent's own write, below.
DISPATCHED_WRITE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Task",
     "input": {"prompt": "Write the new rule into shared/workflow/x.md.",
               "description": "author the fragment"}}]}}
# A sidechain record does not reach a Stop hook's transcript at all --
# measured 2026-08-20, 0 of 126 session transcripts carried one. These
# fixtures therefore pin that sidechain content is IGNORED, not that it
# discharges: a fixture is not evidence about the harness it imitates
# (shared/workflow/fixtures-are-not-evidence.md).
SUBAGENT_WROTE = {"type": "assistant", "isSidechain": True, "message": {
    "content": [{"type": "tool_use", "name": "Write",
                 "input": {"file_path": "shared/workflow/x.md",
                           "content": "the rule"}}]}}
SUBAGENT_SAID = {"type": "assistant", "isSidechain": True, "message": {
    "content": [{"type": "text",
                 "text": "Going forward I will always do X."}]}}
# --- Round-7 review fixtures. Each of these DISCHARGED or BLOCKED wrongly
# before the fix, and none was reachable by the prior 44 cases, because every
# read fixture happened to name a path with no `ums`/`memorize` in it.
CAT_UMS_PATH = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Bash",
     "input": {"command": "cat shared/workflow/run-ums-proactively.md"}}]}}
CAT_MEMORIZE_PATH = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Bash",
     "input": {"command": "cat skills/memorize/SKILL.md"}}]}}
DISPATCHED_READ_UMS = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Task",
     "input": {"prompt": "Summarize what shared/workflow/run-ums-proactively.md says.",
               "description": "read the fragment"}}]}}
CAT_WITH_STDERR = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Bash",
     "input": {"command": "cat shared/workflow/ardi.md 2>/dev/null | head -40"}}]}}
CP_OUT_OF_RULE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Bash",
     "input": {"command": "cp shared/workflow/a.md /tmp/"}}]}}
# A write the permission system refused ships nothing.
WRITE_ATTEMPT = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "tu1", "name": "Write",
     "input": {"file_path": "CLAUDE.md", "content": "x"}}]}}
WRITE_DENIED = {"type": "user", "message": {"content": [
    {"type": "tool_result", "tool_use_id": "tu1", "is_error": True,
     "content": "Permission to use Write was denied"}]}}
WRITE_OK = {"type": "user", "message": {"content": [
    {"type": "tool_result", "tool_use_id": "tu1", "content": "ok"}]}}

# How a delegated build actually ends: the parent stages the artifact.
STAGED_ARTIFACT = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Bash",
     "input": {"command": "git add hooks/request-reviewer-on-ready.py"}}]}}
# A read-only dispatch whose brief merely cites a rule surface. Subagent
# briefs in this corpus cite such paths constantly, so this is the realistic
# shape rather than a contrived one (review finding on #1724).
DISPATCHED_READ = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Task",
     "input": {"prompt": "Just read hooks/no-foo.py and tell me what it does.",
               "description": "inspect hooks/no-foo.py"}}]}}
DISPATCHED_READ_RULE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Task",
     "input": {"prompt": "Summarize what CLAUDE.md says about worktrees.",
               "description": "read CLAUDE.md"}}]}}
# Reads over rule surfaces -- ordinary work in this corpus, and the reason a
# bare path match on any tool payload is unsound.
READ_RULE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Read", "input": {"file_path": "CLAUDE.md"}}]}}
GREP_RULE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Grep",
     "input": {"pattern": "verdict", "path": "shared/workflow/ardi.md"}}]}}
CAT_RULE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Bash",
     "input": {"command": "cat shared/workflow/ardi.md | head -40"}}]}}
# --- #1946 fixtures: an owed ACTION discharges on an armed firing.
# Tool names verified against 232 local transcripts on 2026-08-22 rather than
# invented: ScheduleWakeup 302 occurrences, Monitor 126, CronCreate 18,
# CronList 13 -- so the CronList near-miss below is a real shape, not a
# contrived one.
ARMED_WAKEUP = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "ScheduleWakeup",
     "input": {"delaySeconds": 300, "noop": False,
               "reason": "Waiting on the re-review verdict for #1937.",
               "prompt": "Continue the ARDI loop on ai-config #1937."}}]}}
ARMED_CRON = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "CronCreate",
     "input": {"schedule": "*/10 * * * *", "prompt": "Check #1937."}}]}}
ARMED_MCP_TASK = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "mcp__scheduled-tasks__create_scheduled_task",
     "input": {"prompt": "Re-check #1937's review."}}]}}
ARMED_SKILL = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Skill",
     "input": {"skill": "schedule", "args": "check #1937 in 10 minutes"}}]}}
ARMED_POLLER = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Bash",
     "input": {"command": "python3 hooks/monitor-open-prs.py"}}]}}
# Ending a dynamic loop is the OPPOSITE of arming one.
STOPPED_WAKEUP = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "ScheduleWakeup", "input": {"stop": True}}]}}
# A read of the schedule, not an arming of one.
LISTED_CRONS = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "CronList", "input": {}}]}}
# The `ardi` skill runs the round that is ALREADY done by the time the debt
# sentence is composed; the debt is about the NEXT round.
RAN_ARDI = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Skill",
     "input": {"skill": "ardi", "args": "#1937 drive to clean"}}]}}
# Prose in `args` must not reach SCHEDULER_SKILLS -- only the `skill` field.
ASKED_ABOUT_SCHEDULE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Task",
     "input": {"prompt": "What does the schedule skill do, and does loop "
                         "call workaround-watcher?",
               "description": "read-only lookup"}}]}}
ARM_ATTEMPT = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "tu9", "name": "ScheduleWakeup",
     "input": {"delaySeconds": 300, "prompt": "check #1937"}}]}}
ARM_DENIED = {"type": "user", "message": {"content": [
    {"type": "tool_result", "tool_use_id": "tu9", "is_error": True,
     "content": "Permission to use ScheduleWakeup was denied"}]}}

PROMPT = {"type": "user", "message": {"content": [
    {"type": "text", "text": "next task please"}]}}
TOOL_RESULT = {"type": "user", "message": {"content": [
    {"type": "tool_result", "content": "ok"}]}}


# Running a negative control against another revision of the hook: copy that
# revision AND `remind-ums-after-error.py` into one directory and point this
# suite at the copy. `no-empty-promise.py` imports `visible_prose` from that
# sibling and returns 0 unconditionally when the import fails, so a copy
# placed on its own goes silent on EVERY case -- which reports as a suite-wide
# failure rather than as the missing dependency it is.


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


def bash(command):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": command}}]}}


def dispatch(prompt):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Task",
         "input": {"prompt": prompt, "description": "read-only lookup"}}]}}


# (events, should_block, label)
CASES = [
    # Promises with nothing behind them.
    ([say("Going forward, I'll run the checker before reporting status.")],
     True, "'going forward, I'll' with no mechanism blocks"),
    ([say("From now on I won't skip the UMS pass."), UNRELATED],
     True, "'from now on I won't' with unrelated tool work blocks"),
    ([say("I'll always link PRs in tables.")],
     True, "'I'll always' blocks"),
    ([say("I won't make that mistake again.")],
     True, "'won't ... again' blocks"),
    ([say("Next time I'll check the branch first.")],
     True, "'next time I'll' blocks"),
    ([say("I'll no longer trust a cached verdict.")],
     True, "'I'll no longer' blocks"),
    ([say("I promise to run the sweep first.")],
     True, "a bare performative blocks"),

    # Discharged by shipping something durable.
    ([say("Going forward I'll run the checker."), WROTE_FRAGMENT,
      say("Recorded the rule.")],
     False, "a shared/ fragment write discharges it"),
    ([say("From now on I won't skip it."), WROTE_MEMORY],
     False, "a memories/ write discharges it"),
    ([say("I'll always request the reviewer."), WROTE_HOOK],
     False, "a hooks/ write discharges it"),
    ([say("Going forward I'll do X."), FILED_ISSUE],
     False, "filing the tracking issue discharges it"),
    ([say("Going forward I'll do X --- enforced by "
          "`hooks/no-empty-promise.py`, added in this PR.")],
     True, "prose naming the mechanism does NOT discharge it (review #1724)"),
    ([say("Going forward I will add `hooks/no-foo.py` for it.")],
     True, "the future-tense self-naming near-miss blocks (review #1724)"),
    ([say("Going forward I'll check `shared/` before writing anything.")],
     True, "a bare directory mention does NOT discharge the promise"),
    ([WROTE_VIA_BASH, say("Going forward I'll do X.")],
     False, "a shell heredoc write to a rule surface discharges it"),
    ([DISPATCHED_UMS, say("Going forward I'll do X.")],
     False, "dispatching the recording pass discharges it"),
    ([DISPATCHED_WRITE, say("Going forward I'll do X.")],
     True, "a brief DESCRIBING a write does not discharge it (review #1724)"),
    ([DISPATCHED_WRITE, SUBAGENT_WROTE, say("Going forward I'll do X.")],
     True, "a sidechain write is NOT visible here, so it cannot discharge"),
    ([DISPATCHED_WRITE, STAGED_ARTIFACT, say("Going forward I'll do X.")],
     False, "staging the delegated artifact discharges it"),
    ([SUBAGENT_SAID, say("Going forward I'll do X.")],
     True, "a subagent's own prose is neither my promise nor my mechanism"),

    # The noun/verb ambiguity that defeated the previous round's verb
    # heuristic: each of these cites a rule surface while writing nothing.
    ([say("Going forward, I will always check the rule first."),
      dispatch("Summarize the latest edit to shared/workflow/x.md.")],
     True, "the noun 'edit' near a path does not discharge (review #1724)"),
    ([say("Going forward, I will always check the rule first."),
      dispatch("What does the latest update to memories/preferences.md say?")],
     True, "the noun 'update' near a path does not discharge"),
    ([say("Going forward, I will always check the rule first."),
      dispatch("Find the record in memories/github.md about tokens.")],
     True, "the noun 'record' near a path does not discharge"),
    ([say("Going forward, I will always check the rule first."),
      dispatch("Who is the author of shared/workflow/ardi.md?")],
     True, "the noun 'author' near a path does not discharge"),
    ([say("Going forward I will add `hooks/no-foo.py` for it."),
      DISPATCHED_READ],
     True, "a read-only dispatch citing a hook path does NOT discharge it"),
    ([say("Going forward, I will always check the rule first."),
      DISPATCHED_READ_RULE],
     True, "a read-only dispatch citing CLAUDE.md does NOT discharge it"),

    # Reads must NOT discharge -- the second half of the same review finding.
    ([say("Going forward, I will always check the rule first."), READ_RULE],
     True, "reading CLAUDE.md does NOT discharge a promise (review #1724)"),
    ([say("Going forward, I will always check the rule first."), GREP_RULE],
     True, "grepping a shared/ fragment does NOT discharge it"),
    ([say("Going forward, I will always check the rule first."), CAT_RULE],
     True, "cat-ing a shared/ fragment does NOT discharge it"),

    # Near-misses that must pass.
    ([say("I'll open the PR now and report back.")],
     False, "an ordinary next-action statement is not a promise"),
    ([say("I will push the fix, then wait for the review.")],
     False, "a plan for this turn is not a promise"),
    ([say("I'll never be able to know the exact time without a clock read.")],
     False, "a capability limit is not a promise"),
    ([say("You said you would always link PRs in tables.")],
     False, "a second-person statement is not my promise"),
    ([say("The reviewer will always re-derive the claim from scratch.")],
     False, "a third-person prediction is not a promise"),
    ([say("I was wrong about the default branch --- it is `master` here.")],
     False, "an admission with no promise attached passes"),
    ([UNRELATED, say("All five PRs are clean.")],
     False, "an ordinary recap does not block"),

    # Discussing the rule must not trip it -- this corpus quotes the trigger
    # phrases constantly, including in this very file.
    ([say("The guard fires on `going forward, I will` in prose.")],
     False, "an inline-code mention does not block"),
    ([say("> Going forward, I will do X.\n\nThat is the shape it catches.")],
     False, "a blockquote does not block"),
    ([say("```\nFrom now on I won't skip it.\n```\nThat is a fenced example.")],
     False, "a fenced example does not block"),

    # --- Round-7 review findings, all reproduced before fixing.
    # F1: a bare `ums`/`memorize` matched inside a hyphenated PATH, so
    # reading the corpus's most-cited fragments discharged a promise.
    ([say("Going forward I'll do X."), CAT_UMS_PATH],
     True, "cat of run-ums-proactively.md does NOT discharge (review #1724)"),
    ([say("Going forward I'll do X."), CAT_MEMORIZE_PATH],
     True, "cat of skills/memorize/SKILL.md does NOT discharge"),
    ([say("Going forward I'll do X."), DISPATCHED_READ_UMS],
     True, "a read-only dispatch naming a ums path does NOT discharge"),
    # F1's own over-correction: `.` in the exclusion class rejected a
    # sentence-final period, so the commonest phrasing stopped discharging.
    ([say("Going forward I'll do X."), dispatch("Investigate this, then run ums.")],
     False, "an action word before a full stop still discharges (review #1724)"),
    ([say("Going forward I'll do X."), dispatch("File the issue, then memorize.")],
     False, "'memorize.' at a sentence end still discharges"),
    ([say("Going forward I'll do X."), dispatch("Open ums.md and summarize it.")],
     True, "a dotted FILENAME still does not discharge"),
    # Review finding on #1968. `_NOT_PATH` originally rejected ANY preceding
    # `/`, which silently dropped `/ums` -- the spelling this corpus actually
    # uses to invoke a skill, and the one likeliest to appear in a dispatch
    # prompt. A path and an invocation differ in what precedes the slash.
    ([say("Going forward I'll do X."), dispatch("Then run /ums on this.")],
     False, "the slash-command spelling `/ums` still discharges (#1968)"),
    ([say("Going forward I'll do X."), dispatch("/memorize the outcome.")],
     False, "`/memorize` at the start of a prompt still discharges"),
    ([say("Going forward I'll do X."), dispatch("Open skills/ums and read it.")],
     True, "a path ending in `ums` still does not discharge"),

    # Round 9: a bare skill word in a BASH payload is a search term, not an
    # action -- `grep -n ums README.md` discharged a promise.
    ([say("Going forward I'll do X."), bash("grep -n ums README.md")],
     True, "grep for 'ums' does NOT discharge (review #1724)"),
    ([say("Going forward I'll do X."), bash('grep -rn "ums" .')],
     True, "a recursive grep for 'ums' does NOT discharge"),
    ([say("Going forward I'll do X."), bash("grep -c memorize CLAUDE.md")],
     True, "grep for 'memorize' does NOT discharge"),
    ([say("Going forward I'll do X."), bash("echo checking for ums mentions")],
     True, "echoing the word 'ums' does NOT discharge"),
    ([say("Going forward I'll do X."), bash("gh issue create -R o/r --title x --body y")],
     False, "a real filing COMMAND still discharges from bash"),

    # F2: `>` matched a stderr redirect, and cp/mv read OUT of a rule surface.
    ([say("Going forward I'll do X."), CAT_WITH_STDERR],
     True, "`2>/dev/null` on a read does NOT make it a write"),
    ([say("Going forward I'll do X."), CP_OUT_OF_RULE],
     True, "copying OUT of a rule surface does NOT discharge"),
    # F3: the capability exclusion guarded only the always/never branch.
    ([say("I won't be able to know the exact time again.")],
     False, "a capability limit with 'again' does not block (review #1724)"),
    ([say("We won't see that error again once the cache clears.")],
     False, "a prediction with 'again' does not block"),
    # F4: `every time`/`each time` are ordinary technical connectives here.
    ([say("We will lose the summary every time compaction fires.")],
     False, "descriptive 'every time' does not block (review #1724)"),
    ([say("I will have to re-fetch each time the base moves.")],
     False, "descriptive 'each time' does not block"),
    # F5: an attempted write is not a shipped mechanism.
    ([WRITE_ATTEMPT, WRITE_DENIED, say("Going forward I'll always do X.")],
     True, "a DENIED write does not discharge (review #1724)"),
    ([WRITE_ATTEMPT, WRITE_OK, say("Going forward I'll always do X.")],
     False, "a successful write still discharges"),
    ([WRITE_ATTEMPT, say("Going forward I'll always do X.")],
     False, "a write with no result yet still discharges"),

    # Ordering and turn scope.
    # Order within the turn is deliberately not tested: the ordinary shape is
    # to build the mechanism and then state the rule in the closing message,
    # so requiring the write to come AFTER would block the correct case.
    ([WROTE_FRAGMENT, say("Going forward I'll do X.")],
     False, "a mechanism written EARLIER in the same turn discharges it"),
    ([say("Going forward I'll do X."), PROMPT, say("Here is the answer.")],
     False, "a promise in an EARLIER turn is not re-blocked"),
    ([say("Going forward I'll do X."), TOOL_RESULT, WROTE_MEMORY],
     False, "a tool_result does not end the turn"),
    # A promise stated as a DEBT rather than as a modal (#1792). No "I'll"
    # appears anywhere in these, so every modal alternative above misses
    # them, and the bookkeeping tone is what makes them pass self-review.
    ([say("The UMS pass is owed by me.")],
     True, "'owed by me' with no mechanism blocks"),
    ([say("I owe you a hook for this one.")],
     True, "'I owe you' with no mechanism blocks"),
    ([say("I still owe that follow-up entry.")],
     True, "'I still owe' with no mechanism blocks"),
    ([say("I'll wait here until it finishes.")],
     True, "'I'll wait here' blocks without a mechanism"),
    ([say("I'll wait right here until it finishes.")],
     True, "'I'll wait right here' blocks without a mechanism"),
    ([say("I will wait right here.")],
     True, "'I will wait right here' blocks without a mechanism"),
    ([say("I'll wait right here."), ARMED_WAKEUP],
     False, "'I'll wait right here' discharged by setting a timer"),
    ([say("We owe a tracking issue on this."), UNRELATED],
     True, "'we owe' with unrelated tool work blocks"),
    ([say("The UMS pass is owed by me."), WROTE_FRAGMENT],
     False, "'owed by me' discharged by a fragment write"),
    ([say("I owe a hook here."), FILED_ISSUE],
     False, "'I owe' discharged by a filed issue"),

    # The negatives that decide whether this alternative is usable at all.
    # This corpus says "owed" constantly in ordinary rule prose, so a bare
    # `owed` match would block every reply that cites those rules.
    ([say("An owed UMS pass is pre-authorized sidecar work.")],
     False, "'an owed UMS pass' names no owner and does not block"),
    ([say("Say in the same reply that the pass is owed and when it runs.")],
     False, "'the pass is owed' names no owner and does not block"),
    ([say("That review is owed by the reviewer, not by me.")],
     False, "'owed by' a third party does not block"),
    ([say("I owed you an answer yesterday and gave it.")],
     False, "past-tense 'owed' reports rather than promises"),

    # --- #1946: an owed ACTION owes a firing, not only a record.
    # The user's own example, verbatim in shape.
    ([say("Stopping Point: Not a clean stopping point --- #1937 is open "
          "awaiting re-review at 98d79c81, and I owe it the ARDI loop.")],
     True, "the owed-ARDI-loop recap blocks with nothing armed (#1946)"),
    ([say("Stopping Point: #1937 awaits re-review and I owe it the ARDI "
          "loop."), ARMED_WAKEUP],
     False, "an armed ScheduleWakeup discharges an owed action"),
    ([say("I owe #1937 the ARDI loop."), ARMED_CRON],
     False, "CronCreate discharges an owed action"),
    ([say("I owe #1937 the ARDI loop."), ARMED_MCP_TASK],
     False, "a scheduled task discharges an owed action"),
    ([say("I owe #1937 the ARDI loop."), ARMED_SKILL],
     False, "the schedule skill discharges an owed action"),
    ([say("I owe #1937 the ARDI loop."), ARMED_POLLER],
     False, "arming the detached PR poller discharges an owed action"),
    # A future CI/reviewer action is also a delivery claim. The incident was
    # a pushed GitLab branch followed by the forecast that a pipeline would
    # produce a review, without keeping the session alive to inspect either.
    ([say("GitLab will automatically launch the next review round.")],
     True, "an automation forecast without monitoring blocks"),
    ([say("The next pipeline will produce a review."), ARMED_WAKEUP],
     False, "an armed wakeup discharges an automation forecast"),
    ([say("GitHub Actions will run CI.")],
     True, "a GitHub Actions CI forecast without monitoring blocks"),
    ([say("The review bot will post a review."), ARMED_WAKEUP],
     False, "a review-monitoring wakeup discharges the forecast"),
    ([say("GitLab will launch the next review round."),
      {"type": "assistant", "message": {"content": [
          {"type": "tool_use", "name": "ScheduleWakeup",
           "input": {"delaySeconds": 300, "prompt": "Tidy local notes."}}]}}],
     True, "an unrelated wakeup does not discharge an automation forecast"),
    ([say("The next pipeline should automatically run.")],
     False, "a tentative automation expectation is not a delivery claim"),
    ([say("The pipeline is running for the current head.")],
     False, "current in-progress state is not an automation forecast"),
    # The durable floor still clears a debt -- it is the wrong instinct, not
    # an invalid mechanism, and blocking it would wedge the honest case where
    # the debt is somebody else's to schedule.
    ([say("I owe a follow-up entry here."), WROTE_MEMORY],
     False, "a durable record still discharges an owed action"),

    # Near-misses on the arming side. Each of these LOOKS like a scheduler
    # call and delivers nothing.
    ([say("I owe #1937 the ARDI loop."), STOPPED_WAKEUP],
     True, "`stop: true` ends the loop and does NOT discharge (#1946)"),
    ([say("I owe #1937 the ARDI loop."), LISTED_CRONS],
     True, "listing crons is a read and does NOT discharge"),
    ([say("I owe #1937 the ARDI loop."), RAN_ARDI],
     True, "running ardi THIS turn does not discharge the NEXT round"),
    ([say("I owe #1937 the ARDI loop."), ASKED_ABOUT_SCHEDULE],
     True, "'the schedule skill' in brief prose does NOT discharge"),
    ([ARM_ATTEMPT, ARM_DENIED, say("I owe #1937 the ARDI loop.")],
     True, "a DENIED arming does not discharge"),
    ([ARM_ATTEMPT, say("I owe #1937 the ARDI loop.")],
     False, "an arming with no result yet still discharges"),

    # The asymmetry: a timer keeps an owed ACTION and cannot keep a RULE.
    ([say("Going forward I'll always check the remote first."), ARMED_WAKEUP],
     True, "a timer does NOT discharge a rule promise (#1946)"),
    ([say("From now on I won't skip the sweep."), ARMED_CRON],
     True, "CronCreate does NOT discharge a rule promise"),
    # A turn carrying one of each is blocked on the STRICTER requirement, and
    # blocked once rather than twice.
    ([say("Going forward I'll always check first, and I owe #1937 the ARDI "
          "loop."), ARMED_WAKEUP],
     True, "a rule beside a debt is judged on the rule's requirement"),
    ([say("Going forward I'll always check first, and I owe #1937 the ARDI "
          "loop."), WROTE_FRAGMENT],
     False, "a durable write clears both kinds at once"),

    # --- Review round on #1947, Finding 1. `POLLER_CMD` was a bare path
    # regex, so merely NAMING the poller discharged an owed action -- in a
    # session working on the poller hooks, where these reads are the likeliest
    # commands of all. Each was reproduced against the PR head before the fix.
    ([say("I owe #1937 the ARDI loop."), bash("cat hooks/monitor-open-prs.py")],
     True, "cat of the poller does NOT discharge (review #1947)"),
    ([say("I owe #1937 the ARDI loop."),
      bash("grep -n check hooks/monitor-open-prs.py")],
     True, "grepping the poller does NOT discharge"),
    ([say("I owe #1937 the ARDI loop."), bash("echo hooks/monitor-open-prs.py")],
     True, "echoing the poller path does NOT discharge"),
    ([say("I owe #1937 the ARDI loop."), bash("ls -la hooks/monitor-open-prs.py")],
     True, "listing the poller does NOT discharge"),
    # The arming shapes that must keep working.
    ([say("I owe #1937 the ARDI loop."), bash("python3 hooks/monitor-open-prs.py")],
     False, "running the poller discharges"),
    ([say("I owe #1937 the ARDI loop."),
      bash("nohup python3 ~/.claude/hooks/monitor-open-prs.py --monitor "
           ">/dev/null 2>&1 &")],
     False, "a backgrounded poller with an absolute path discharges"),
    ([say("I owe #1937 the ARDI loop."), bash("./hooks/monitor-open-prs.py")],
     False, "a direct exec of the poller discharges"),

    # The same finding's SECOND half: testing the arming before the durable
    # write made `git add` on a poller file return "scheduled", which a RULE
    # promise does not accept -- so a turn that had shipped its mechanism was
    # blocked and told to do what it had just done. Durable must win.
    ([say("Going forward I'll always arm the watcher."),
      bash("git add hooks/no-unmonitored-pr.py && git commit -m fix")],
     False, "committing a poller hook is DURABLE, so it clears a rule (#1947)"),
    ([say("Going forward I'll always arm the watcher."),
      bash("sed -i 's/a/b/' hooks/ensure-open-pr-monitor.py")],
     False, "editing a poller hook in place is durable, not merely scheduled"),
    # Control: the same shape on a non-poller hook, which never regressed.
    ([say("Going forward I'll always arm the watcher."),
      bash("git add hooks/other.py && git commit -m fix")],
     False, "the non-poller control still discharges a rule promise"),

    # A plugin exposes the same skill under a qualified name, and only the
    # bare one matched.
    ([say("I owe #1937 the ARDI loop."),
      {"type": "assistant", "message": {"content": [
          {"type": "tool_use", "name": "Skill",
           "input": {"skill": "ai-config:workaround-watcher",
                     "args": "watch #1937"}}]}}],
     False, "a plugin-prefixed scheduling skill discharges (#1947)"),

    # `noop: true` is NOT `stop: true`. Read against ScheduleWakeup's schema:
    # `noop` decides how the tick is DISPLAYED and is "required unless `stop`
    # is true", so it is mandatory on every genuine arming -- and a quiet hold
    # is exactly the `noop: true` case. Pinned so the rebuttal is mechanical
    # rather than remembered.
    ([say("I owe #1937 the ARDI loop."),
      {"type": "assistant", "message": {"content": [
          {"type": "tool_use", "name": "ScheduleWakeup",
           "input": {"delaySeconds": 600, "noop": True,
                     "reason": "quiet hold on #1937's review",
                     "prompt": "Continue the ARDI loop on #1937."}}]}}],
     False, "`noop: true` is a display flag and still discharges (#1947)"),

    # --- Review round 2 on #1947. The execution anchor from round 1 still
    # admitted a plain read wrapped in `sh -c`/`bash -c` -- a commoner idiom
    # than the `python3 -c` residual round 1 had accepted, so the lookahead
    # now retires both.
    ([say("I owe #1937 the ARDI loop."),
      bash('sh -c "cat hooks/monitor-open-prs.py"')],
     True, "`sh -c` wrapping a read does NOT discharge (review #1947 r2)"),
    ([say("I owe #1937 the ARDI loop."),
      bash('bash -c "grep -n check hooks/monitor-open-prs.py"')],
     True, "`bash -c` wrapping a grep does NOT discharge"),
    ([say("I owe #1937 the ARDI loop."),
      bash('sh -ec "cat hooks/monitor-open-prs.py"')],
     True, "a combined short flag (`sh -ec`) is covered too"),
    ([say("I owe #1937 the ARDI loop."),
      bash("python3 -c \"print(open('hooks/monitor-open-prs.py').read())\"")],
     True, "the round-1 `python3 -c` residual is now closed as well"),
    # Disqualifying the interpreter must NOT discard the whole command: any
    # other exec token still anchors, so a genuine arming inside `bash -c`
    # keeps discharging.
    ([say("I owe #1937 the ARDI loop."),
      bash('bash -c "python3 hooks/monitor-open-prs.py --monitor"')],
     False, "a real arming inside `bash -c` still discharges (#1947 r2)"),

    # --- Review round 3 on #1947. The `_NOT_DASH_C` lookahead was pinned to
    # the token immediately after the interpreter, so ANY flag between them
    # walked past it -- as did a versioned interpreter name, since
    # `\bpython3\b` matches inside `python3.11`. All four are ordinary
    # commands (`-x` trace, `-u` unbuffered, a side-by-side interpreter), and
    # each silently discharged a debt with nothing armed.
    #
    # The fix is not a fourth lookahead: `POLLER_CMD` is gone and
    # `_poller_executed()` tokenizes with `shlex` instead, because "is this
    # token being executed?" is a fact about shell grammar rather than about
    # character adjacency.
    ([say("I owe #1937 the ARDI loop."),
      bash('bash -x -c "cat hooks/monitor-open-prs.py"')],
     True, "a flag between interpreter and `-c` does NOT discharge (#1947 r3)"),
    ([say("I owe #1937 the ARDI loop."),
      bash('python3 -u -c "cat hooks/monitor-open-prs.py"')],
     True, "`python3 -u -c` wrapping a read does NOT discharge"),
    ([say("I owe #1937 the ARDI loop."),
      bash('python3.11 -c "cat hooks/monitor-open-prs.py"')],
     True, "a versioned interpreter does NOT discharge a wrapped read"),
    ([say("I owe #1937 the ARDI loop."),
      bash('python3.12 -B -u -c "cat hooks/monitor-open-prs.py"')],
     True, "several flags plus a versioned interpreter does NOT discharge"),
    ([say("I owe #1937 the ARDI loop."), bash("head -20 hooks/monitor-open-prs.py")],
     True, "`head` on the poller does NOT discharge"),
    # Real armings the lexer must keep accepting, including the shapes the
    # regex never handled at all.
    ([say("I owe #1937 the ARDI loop."),
      bash("python3.11 hooks/monitor-open-prs.py --monitor")],
     False, "a versioned interpreter RUNNING the poller discharges (#1947 r3)"),
    ([say("I owe #1937 the ARDI loop."),
      bash("/usr/bin/env python3 hooks/monitor-open-prs.py --monitor")],
     False, "`/usr/bin/env python3` discharges"),
    ([say("I owe #1937 the ARDI loop."),
      bash("env PATH=/opt/homebrew/bin:$PATH python3 hooks/monitor-open-prs.py "
           "--monitor")],
     False, "an env-prefixed arming discharges (the shape that fixed #1953)"),

    # --- Review round 4 on #1947, reported as non-blocking and fixed anyway.
    # `shlex` splits on whitespace and quoting, NOT on shell operators, so a
    # separator with no space before it rides along on the path token and the
    # anchored match rejected it. A regression the round-3 rewrite introduced
    # (the old regex used an unanchored search), failing in the safe
    # direction, and a semicolon with no space is an ordinary way to write a
    # command.
    ([say("I owe #1937 the ARDI loop."),
      bash("python3 hooks/monitor-open-prs.py; echo done")],
     False, "a trailing `;` on the path token still discharges (#1947 r4)"),
    ([say("I owe #1937 the ARDI loop."),
      bash("python3 hooks/monitor-open-prs.py&")],
     False, "a trailing `&` with no space still discharges"),
    # The anchor is stripped, not dropped: a token that merely ENDS with the
    # path must still be rejected, which is what the `$` was protecting.
    ([say("I owe #1937 the ARDI loop."),
      bash("cat hooks/monitor-open-prs.py; echo done")],
     True, "stripping the separator does NOT reopen the read bypass (#1947 r4)"),

    # --- Review round 5 on #1947. The `-c` recursion applied SHELL semantics
    # uniformly, but only a shell's `-c` takes a nested command line. Python's
    # takes source, where a bare path is an expression -- `python3 -c
    # hooks/monitor-open-prs.py` raises `NameError: name 'hooks' is not
    # defined` and runs nothing, yet discharged.
    ([say("I owe #1937 the ARDI loop."),
      bash("python3 -c hooks/monitor-open-prs.py")],
     True, "`python3 -c <bare path>` does NOT discharge (#1947 r5)"),
    ([say("I owe #1937 the ARDI loop."),
      bash("python3 -c hooks/monitor-open-prs.py --monitor")],
     True, "`python3 -c <path> --monitor` does NOT discharge"),
    ([say("I owe #1937 the ARDI loop."),
      bash("python3.11 -c hooks/monitor-open-prs.py")],
     True, "a versioned Python's `-c` does NOT discharge either"),
    # The shell half must keep working: `bash -c <path>` really does execute
    # it, which is the asymmetry the fix turns on.
    ([say("I owe #1937 the ARDI loop."), bash("bash -c hooks/monitor-open-prs.py")],
     False, "`bash -c <bare path>` DOES execute it, so it discharges (#1947 r5)"),

    # A false NEGATIVE the same walk-back fixed, not reported by the review:
    # an ordinary interpreter flag between the interpreter and the script made
    # a genuine arming stop discharging. `-u` is the one you actually want on
    # a poller.
    ([say("I owe #1937 the ARDI loop."),
      bash("python3 -u hooks/monitor-open-prs.py")],
     False, "an interpreter flag before the script still discharges (#1947 r5)"),
    ([say("I owe #1937 the ARDI loop."),
      bash("python3 -B -u hooks/monitor-open-prs.py --monitor")],
     False, "several interpreter flags before the script still discharge"),

    # --- ai-config#1966. `BASH_WRITE` decides what counts as a durable
    # write, so a false match there is a false DISCHARGE -- the silent
    # direction. `\b` sits between a name and a following `-`, so `--write\b`
    # matched curl's `--write-out` and `git\s+(?:add|commit|...)\b` matched
    # `git commit-tree`. Both directions are pinned, because the defect was
    # precisely that a real write and these were indistinguishable.
    #
    # The curl line is verbatim from the issue. It pairs a rule-surface path
    # (a URL ending in CLAUDE.md) with a flag that writes nothing, so a pure
    # HTTP status check read as having shipped a mechanism.
    ([say("Going forward I'll always check this before replying."),
      bash("curl -s --write-out '%{http_code}' "
           "https://example.com/CLAUDE.md")],
     True, "`curl --write-out` writes nothing and does NOT discharge (#1966)"),
    ([say("Going forward I'll always check this before replying."),
      bash("git commit-tree -p HEAD -m 'shared/workflow/fully-clean.md' $TREE")],
     True, "`git commit-tree` is not `git commit` and does NOT discharge"),
    ([say("Going forward I'll always check this before replying."),
      bash("git commit-graph write && cat shared/workflow/fully-clean.md")],
     True, "`git commit-graph write` does NOT discharge"),

    # The true-positive half. Each of these still has to work, or the guard
    # has been tightened past the defect into the behaviour itself.
    ([say("Going forward I'll always check this before replying."),
      bash("python3 scripts/semantic-line-breaks.py --write "
           "shared/workflow/fully-clean.md")],
     False, "a genuine `--write` flag still discharges"),
    ([say("Going forward I'll always check this before replying."),
      bash("git commit -m 'record it' shared/workflow/fully-clean.md")],
     False, "`git commit` still discharges"),
    ([say("Going forward I'll always check this before replying."),
      bash("git add shared/workflow/fully-clean.md")],
     False, "`git add` still discharges"),
    ([say("Going forward I'll always check this before replying."),
      bash("git rm shared/workflow/fully-clean.md")],
     False, "`git rm` still discharges"),
    ([say("Going forward I'll always check this before replying."),
      bash("git mv shared/workflow/fully-clean.md shared/workflow/fc.md")],
     False, "`git mv` still discharges"),
    ([say("Going forward I'll always check this before replying."),
      bash("sed -i 's/a/b/' shared/workflow/fully-clean.md")],
     False, "`sed -i` still discharges (no hyphenated sibling to guard)"),
    ([say("Going forward I'll always check this before replying."),
      bash("sed -i.bak 's/a/b/' shared/workflow/fully-clean.md")],
     False, "`sed -i.bak` still discharges -- `.` is already a non-word char"),
    ([say("Going forward I'll always check this before replying."),
      bash("tee -a shared/workflow/fully-clean.md < /tmp/note")],
     False, "`tee` still discharges"),
    ([say("Going forward I'll always check this before replying."),
      bash("cat CLAUDE.md | tee shared/workflow/fully-clean.md")],
     False, "`tee` mid-pipeline still discharges"),
    ([say("Going forward I'll always check this before replying."),
      bash("mkdir -p skills/new-guard")],
     False, "`mkdir` still discharges"),
    # `memories/notes` deliberately does NOT work here, and that is
    # MECHANISM_PATH rather than BASH_WRITE: each of its alternatives demands
    # a FILE, so a bare directory cannot discharge a promise. Pinned so the
    # `mkdir` case above is not read as the guard failing.
    ([say("Going forward I'll always check this before replying."),
      bash("mkdir -p memories/notes")],
     True, "creating a bare DIRECTORY does not discharge (MECHANISM_PATH)"),
    # Second review finding on #1968: the earlier comment justified leaving
    # `tee`/`mkdir` on a plain `\b` by the hyphenated-sibling axis, which is
    # the wrong axis -- `\btee\b` matched inside a PATH, so a READ discharged
    # a promise. Latent (no such path exists in this repo today) but wrong in
    # exactly the way the rest of this diff is about.
    ([say("Going forward I'll always check this before replying."),
      bash("cat shared/workflow/tee-notes.md")],
     True, "a path containing `tee` is a READ and does NOT discharge (#1968)"),
    ([say("Going forward I'll always check this before replying."),
      bash("grep -n x shared/workflow/mkdir-guide.md")],
     True, "a path containing `mkdir` does NOT discharge"),
    # `commit` is NOT the only member of that group with a hyphenated
    # sibling: `git --list-cmds=main,others` also reports `add--interactive`,
    # the deprecated interactive backend. Pinned so the exclusion is a
    # checked decision rather than an assumption -- and pinned in the LOUD
    # direction, since a genuine staging that stops discharging costs an
    # extra block the author clears in one command.
    ([say("Going forward I'll always check this before replying."),
      bash("git add--interactive shared/workflow/fully-clean.md")],
     True, "`git add--interactive` is excluded with the rest of the group"),
]


def run(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    try:
        r = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True,
        )
        assert r.returncode == 0, f"must exit 0, got {r.returncode}"
        if not r.stdout.strip():
            return False
        payload = json.loads(r.stdout)
        return payload.get("decision") == "block"
    finally:
        os.unlink(path)


def main():
    passes = failures = 0
    for events, expected, label in CASES:
        try:
            got = run(events)
        except AssertionError as exc:
            print(f"FAIL: {label} ({exc})")
            failures += 1
            continue
        if got == expected:
            print(f"PASS: {label}")
            passes += 1
        else:
            print(f"FAIL: {label} (expected block={expected}, got {got})")
            failures += 1

    # Fails open rather than crashing when the transcript is unreadable.
    out = subprocess.run(
        [sys.executable, HOOK], input='{"transcript_path": "/nonexistent"}',
        capture_output=True, text=True,
    )
    if out.returncode == 0 and not out.stdout.strip():
        print("PASS: fails open on an unreadable transcript")
        passes += 1
    else:
        print("FAIL: should fail open on an unreadable transcript")
        failures += 1

    # A standing adversarial sweep over flag permutations. Three consecutive
    # review rounds each found one more way to wrap a READ of the poller in an
    # interpreter, and each fix covered only the shape that had been reported.
    # Enumerating the space is what stops the fourth round: this fails on any
    # combination that discharges, not merely on the ones someone thought of.
    import importlib.util as _ilu
    import itertools
    _spec = _ilu.spec_from_file_location("_nep", HOOK)
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    path = "hooks/monitor-open-prs.py"
    leaks = []
    for interp in ("sh", "bash", "dash", "python3", "python3.11", "python3.12"):
        for count in (0, 1, 2):
            for combo in itertools.permutations(("-x", "-u", "-O", "-e", "-B"),
                                                count):
                flags = " ".join(combo)
                command = f'{interp} {flags} -c "cat {path}"'.replace("  ", " ")
                if _mod.discharges("Bash", {"command": command}) is not None:
                    leaks.append(command)
    if leaks:
        print(f"FAIL: {len(leaks)} flag permutation(s) discharge a wrapped "
              f"read, e.g. {leaks[0]}")
        failures += 1
    else:
        print("PASS: no flag permutation discharges a wrapped read of the "
              "poller")
        passes += 1

    # Round 5's shape, swept rather than sampled: a Python interpreter's `-c`
    # takes source, so no flag combination in front of it may discharge a bare
    # path.
    py_leaks = []
    for interp in ("python", "python3", "python3.11", "python3.12"):
        for count in (0, 1, 2):
            for combo in itertools.permutations(("-u", "-B", "-O", "-E"),
                                                count):
                flags = " ".join(combo)
                command = f"{interp} {flags} -c {path}".replace("  ", " ")
                if _mod.discharges("Bash", {"command": command}) is not None:
                    py_leaks.append(command)
    if py_leaks:
        print(f"FAIL: {len(py_leaks)} `python -c <bare path>` permutation(s) "
              f"discharge, e.g. {py_leaks[0]}")
        failures += 1
    else:
        print("PASS: no `python -c <bare path>` permutation discharges")
        passes += 1

    # The mirror direction: a genuine arming must survive the same wrappers.
    missed = [
        c for c in (
            f"python3 {path}",
            f"python3.11 {path} --monitor",
            f"./{path}",
            f'bash -c "python3 {path} --monitor"',
            f"nohup python3 ~/.claude/{path} --monitor >/dev/null 2>&1 &",
            f"/usr/bin/env python3 {path} --monitor",
            f"python3 -u {path}",
            f"bash -c {path}",
            f"python3 {path}; echo done",
        )
        if _mod.discharges("Bash", {"command": c}) != "scheduled"
    ]
    if missed:
        print(f"FAIL: {len(missed)} genuine arming(s) stopped discharging, "
              f"e.g. {missed[0]}")
        failures += 1
    else:
        print("PASS: every genuine arming shape still discharges")
        passes += 1

    # Malformed stdin must not crash the Stop event either.
    out = subprocess.run(
        [sys.executable, HOOK], input="not json",
        capture_output=True, text=True,
    )
    if out.returncode == 0 and not out.stdout.strip():
        print("PASS: fails open on malformed stdin")
        passes += 1
    else:
        print("FAIL: should fail open on malformed stdin")
        failures += 1

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
