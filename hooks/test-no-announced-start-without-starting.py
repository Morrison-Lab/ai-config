#!/usr/bin/env python3
"""Test the no-announced-start-without-starting guard.

The cases that matter most are the NEGATIVE ones. A guard that blocks every
sentence about what happens next would push authors toward saying less about
sequencing, so the conditional-exemption tests are load-bearing, not padding.

Run: python3 hooks/test-no-announced-start-without-starting.py \
       hooks/no-announced-start-without-starting.py
"""
import glob
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]


def clear_sentinels():
    """The guard fires once per distinct message, keyed by a hash of it.

    Those sentinel files outlive the process, so a second run of this suite
    would see every block case already spent and report a false pass. Clearing
    them is what makes the suite repeatable.
    """
    pattern = os.path.join(tempfile.gettempdir(), ".claude-announced-start-*")
    for path in glob.glob(pattern):
        try:
            os.unlink(path)
        except OSError:
            pass


def say(text):
    return {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": text}]},
    }


def say_antigravity(text):
    return {
        "step_index": 1,
        "source": "MODEL",
        "type": "PLANNER_RESPONSE",
        "content": text,
    }


def tool(name, **inp):
    return {
        "type": "assistant",
        "message": {"content": [{"type": "tool_use", "name": name, "input": inp}]},
    }


def post(text):
    return tool("mcp__hearthbot__post_message", text=text)


def end_turn():
    return tool("mcp__hearthbot__no_reply_needed")


def run(messages):
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as fh:
        for m in messages:
            fh.write(json.dumps(m) + "\n")
        path = fh.name
    out = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"transcript_path": path}),
        capture_output=True,
        text=True,
    )
    return out.stdout.strip()


def blocked(text):
    out = run([say(text)])
    if not out:
        return False
    return json.loads(out).get("decision") == "block"


CASES_BLOCK = [
    # The measured instance.
    "I'll start on it while the arrays run.",
    # The other measured instance, with the stopping-point pairing that makes
    # it read as compliance.
    # A realistic closing block: the announcement sits above a multi-sentence
    # Stopping Point declaration, which is why that block is stripped before
    # the tail is taken. Without the strip, the announcement falls outside
    # the window and the measured instance goes unmatched.
    "I'm starting it now: issue, branch, PR.\n\n"
    "**Stopping Point**: Not a clean stopping point / work remains queued: "
    "#1045 awaiting CI. Seven arrays run until 06:30. Then #1016, #1036, "
    "#1015, #1007 and #1000.",
    "I'll begin the refactor.",
    "I am now starting the month_pool propagation fix.",
    "I'll do that now.",
    "Starting on it now.",
    # Measured 2026-10-08: the verbless form, followed by the plan it
    # announced and no tool call.
    "Starting now. I'll delete the caches first, then move the two folders "
    "to D: and leave links behind so their old paths still work.",
    "Done scanning. **Starting now.**",
    "Starting now...",
    "Starting now\u2026",
    "Starting immediately.",
    "I'll get started on the migration.",
    "**Stopping Point**: Not a clean stopping point / work remains queued: Continuing GIA Phase 2 to claim and implement the next backlog issue.",
]

CASES_PASS = [
    # Round-3 review finding on ai-config#3887, verified there by direct
    # execution. "start with" is expository -- it says where an explanation
    # begins, not that work is about to be done -- and the colon-joined
    # delivery shares a splitter sentence with the match, so the tail window
    # alone could not save it.
    "I'll start with the easy part of the analysis: the data looks clean "
    "and complete.",
    "I'll start with the numbers, then the caveats.",
    # The review finding on ai-config#3887: an ordinary mid-reply narrative
    # transition, in a reply that then delivers what it announced. Blocking
    # this is how a guard earns being switched off.
    "Next, I'll summarize the findings below.\n\n"
    "Finding 1 is a false positive; finding 2 is real and is fixed in "
    "4053b6f3. Both are addressed.",
    # An announcement early in a reply that goes on to do the work.
    "I'll start on the combiner change.\n\n"
    "Done: the map is carried through, the article reads it, and the tests "
    "cover the legacy artifact. Pushed as abc1234.",
    # Gated on something outside this turn's control: a real plan.
    "I'll start on it once the review lands.",
    "I'll push after you confirm.",
    "Next, I'll run the spellcheck when CI finishes.",
    "I'll begin the refactor if you'd rather not wait.",
    "I'll resubmit the arrays as soon as the PR merges.",
    "I'll merge it pending your authorization.",
    # Past tense: the work happened.
    "I started on it and filed #1043.",
    "Filed the issue and cut the branch.",
    # No commitment at all.
    "The sweep is 76 of 175 chunks in, with no failures.",
    "**Stopping Point**: Clean stopping point reached.",
    # Expository "starting now": a rule taking effect, not work announced.
    "Starting now, the rule covers every repo.",
    "Starting now: the rule takes effect for every repo.",
    # A heading titled "Starting now", and a `;`-split fragment carrying its
    # own plan.
    "## Starting now\n\nThe rule covers repos.",
    "Starting now; deleting caches.",
    # A colon-led lead-in followed by the delivered content.
    "Starting now: the summary follows.\n\n"
    "The scan found 35 GB of caches.\n\n"
    "Two folders can move to D:.\n\n"
    "Nothing was deleted.",
    # Quoting the rule must not trip it.
    "The banned shape is `I'll start on it` with nothing following.",
]


def main():
    clear_sentinels()
    failures = 0
    for text in CASES_BLOCK:
        if not blocked(text):
            failures += 1
            print(f"FAIL (should block): {text!r}")
        else:
            print(f"PASS block: {text.splitlines()[0][:60]!r}")
    for text in CASES_PASS:
        if blocked(text):
            failures += 1
            print(f"FAIL (should pass): {text!r}")
        else:
            print(f"PASS allow: {text[:60]!r}")

    # Test Antigravity transcript schema directly.
    clear_sentinels()
    agy_text = "**Stopping Point**: Not a clean stopping point / work remains queued: Continuing GIA Phase 2 to claim and implement the next backlog issue."
    agy_out = run([say_antigravity(agy_text)])
    if not agy_out or json.loads(agy_out).get("decision") != "block":
        failures += 1
        print(f"FAIL Antigravity schema test: out={agy_out}")
    else:
        print("PASS Antigravity schema block")

    # The guard must fire once per distinct message, so a second identical
    # Stop does not block forever.
    clear_sentinels()
    text = "I'll start on the next issue."
    first = blocked(text)
    second = blocked(text)
    if not first or second:
        failures += 1
        print(f"FAIL once-per-message: first={first} second={second}")
    else:
        print("PASS once-per-message")

    # ai-config#5050: Projects threads reply through post_message tool calls.
    posted_block = [
        "Next I'm opening the first workflow PR.",
        "Merged the first PR.\n\nNext, I'll file the second issue.",
        "Done with CI.\n\nI'm now opening the follow-up PR.",
        # agy review on #5052: work verbs and a closing "summarize" with
        # nothing delivered are still unstarted announcements.
        "Next, I'll review the PR.",
        "Next, I'll add the unit tests.",
        "Next, I'll summarize the findings.",
        # Claude review on #5052: a colon with no delivered content.
        "I read the PR. Next, I'll review: the file at src/a.py.",
        "I read the PR. Next, I'll fix: the bug in the parser.",
        "Looked at the issue. Next, I'll add:",
        # agy review on #5052: the colon in "Next:" is not a delivery colon.
        "Next: I'll open the first workflow PR and run the test suite.",
        "Next up: I'm opening the first workflow PR and running the test suite.",
    ]
    posted_block += [
        # Padding after a colon must not exempt (Claude review on #5052): no
        # proxy for "delivers" is ungameable, so a colon never exempts. The
        # cost is one block per message, answered by rewording.
        "I read the PR. Next, I'll review: the file at src/a.py which has the "
        "parser bug in it.",
        "Looked at it. Next, I'll fix: the the the the the the the the.",
        "I looked at the code. Next, I'll explain the key insight: the loop "
        "never terminates because of an off-by-one error.",
    ]
    posted_block += [
        # Claude review on #5052: immediate-future "I'm <adjective> to" forms
        # that the gerund requirement dropped.
        "I read the issue. Next, I'm about to fix the bug.",
        "Next, I'm set to deploy the fix.",
        "Next, I'm ready to deploy the fix.",
        "Next, I'm due to start the migration.",
    ]
    posted_block += [
        # Claude review on #5052: the open class of immediate-future phrasings.
        "I read the issue. Next, I'm poised to fix the bug.",
        "I read the issue. Next, I'm prepared to fix the bug.",
        "I read the issue. Next, I'm slated to fix the bug.",
        "I read the issue. Next, I'm scheduled to fix the bug.",
        "I read the issue. Next, I'm committed to fixing the bug.",
        "I read the issue. Next, I'm all set to fix the bug.",
    ]
    posted_block += [
        # agy review on #5068: these verbs also announce real actions.
        "I read the issue. Next, I'll pass --force-with-lease to git push.",
        "I read the issue. Next, I'll pass the token to the script.",
        "I read the issue. Next, I'll leave a comment on the PR.",
        "I read the issue. Next, I'll leave a review note.",
        "I read the issue. Next, I'll stop the background daemon.",
        # Claude review on #5068: the other added words, with a real action in the clause.
        "I read the issue. Next, I'll skip the linter and push directly to main.",
        "I read the issue. Next, I'll defer the migration to next week and push this hotfix now.",
        # Known misses under the positive verb list (#5071): the verb right
        # after "Next, I'm" is "done", "finished" or "tired", not a work verb,
        # so "Next, I'm done reviewing, let me merge the PR." is not flagged.
        # The trade accepted in #5071: a missed edge case beats the
        # whack-a-mole of the exclusion list.
        "I read the issue. Next, I'll merge the PR.",
        # Claude review on #5074: consonant-doubling gerunds.
        "I read the issue. Next, I'm formatting the file now.",
        "I read the issue. Next, I'm debugging the parser now.",
        "I read the issue. Next, I'm grepping the logs now.",
        "I read the issue. Next, I'm tagging the release now.",
        "I read the issue. Next, I'm digging into the logs now.",
        "I read the issue. Next, I'm rerunning the pipeline now.",
        "I read the issue. Next, I'm beginning the migration now.",
        "I read the issue. Next, I'm cancelling the stale runs now.",
        "I read the issue. Next, I'm skipping the linter and pushing now.",
        "I read the issue. Next, I'm stopping the daemon now.",
        "I read the issue. Next, I'm pushing this straight to main.",
    ]
    posted_pass = [
        # Claude review on #5052: declining, uncertainty and stative gerunds
        # announce no work.
        "I looked at the repo. Next, I'm not going to fix this now, since it's out of scope.",
        "I checked the logs. Next, I'm uncertain whether this is worth pursuing.",
        "I checked the logs. I'm now realizing this was a mistake.",
        "Next, I'll not touch the config.",
        # ai-config#5061: declining or stopping work announces no work.
        "Next, I'll leave this alone for now.",
        "Next, I'll skip this for now.",
        "Next, I'll defer this to the backlog.",
        "Next, I'll pass on this one.",
        "Next, I'll stop here.",
        "Next, I'm done for today.",
        "Next, I'm finished with this task.",
        "Next I'm opening the first workflow PR once the review lands.",
        "Next I'll file it, but I'm blocked on the repo grant.",
        "Next I'm waiting for the runner thread.",
        "Next, I'll summarize the findings below.\n\nFinding 1 is fixed.\n\n"
        "Finding 2 is filed as #12.",
        "Opened the PR and filed the issue.",
    ]
    for text in posted_block:
        clear_sentinels()
        out = run([post(text), end_turn()])
        if not out or json.loads(out).get("decision") != "block":
            failures += 1
            print(f"FAIL (post_message should block): {text!r}")
        else:
            print(f"PASS post_message block: {text.splitlines()[0][:50]!r}")
    for text in posted_pass:
        clear_sentinels()
        out = run([post(text), end_turn()])
        if out:
            failures += 1
            print(f"FAIL (post_message should pass): {text!r}")
        else:
            print(f"PASS post_message allow: {text[:50]!r}")

    # Review finding on #5052: every user-visible reply tool is read.
    for name in ("mcp__hearthbot__reply", "mcp__hearthbot__update_message"):
        clear_sentinels()
        out = run([tool(name, text="Next I'm opening the first workflow PR."), end_turn()])
        if not out or json.loads(out).get("decision") != "block":
            failures += 1
            print(f"FAIL ({name} should block)")
        else:
            print(f"PASS {name} block")

    # agy review on #5052: a trailing text block must not hide a sent
    # announcement, and an empty-text reply call is not work.
    for label, msgs in (
        (
            "trailing text block",
            [
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "mcp__hearthbot__post_message",
                                "input": {"text": "Next I'm opening the first workflow PR."},
                            },
                            {"type": "text", "text": "Posted status update."},
                        ]
                    },
                },
                end_turn(),
            ],
        ),
        (
            "empty-text reply call",
            [post("Next I'm opening the first workflow PR."), tool("reply"), end_turn()],
        ),
    ):
        clear_sentinels()
        out = run(msgs)
        if not out or json.loads(out).get("decision") != "block":
            failures += 1
            print(f"FAIL ({label} should block)")
        else:
            print(f"PASS {label} block")

    # Work after the announcement (any non-hearthbot tool call) clears it.
    clear_sentinels()
    out = run([post("Next I'm opening the first workflow PR."), tool("Bash"), end_turn()])
    if out:
        failures += 1
        print(f"FAIL work after announcement should pass: out={out}")
    else:
        print("PASS work after announcement")

    print(f"\n{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
