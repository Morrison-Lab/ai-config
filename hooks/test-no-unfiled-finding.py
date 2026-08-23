"""Test the no-unfiled-finding guard.

The value is concentrated in the negative cases. A guard that fires on a
legitimate flag, or on a message correctly reporting an already-filed issue,
gets switched off -- and then the case it exists for goes unprotected too.

Run: python3 hooks/test-no-unfiled-finding.py hooks/no-unfiled-finding.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

FILE_CLI = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "gh issue create --title x --body y"}}]}}
# The harness tool names its verb only in `name`; the input has title/body.
FILE_TOOL = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "create_issue",
     "input": {"title": "x", "body": "y"}}]}}
# report-mistakes-proactively step 2: a dupe-check can route the finding to a
# comment on an existing issue instead of a new one. That must discharge too.
COMMENT = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "gh issue comment 897 --body 'new evidence'"}}]}}
UNRELATED = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {"command": "git status --short"}}]}}


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


# (events, should_block, label)
CASES = [
    # The exact failure this exists for -- declarative, no question mark, so
    # no-offer-to-file.py does not fire on it.
    ([say("FLAG -- a mechanism bug worth its own issue. Moving on.")], True,
     "declarative 'worth its own issue' with no filing blocks"),
    ([say("That regex gap needs a tracking issue.")], True,
     "'needs a tracking issue' blocks"),
    ([say("This should be filed separately.")], True,
     "'should be filed' blocks"),
    ([say("Worth tracking separately from the current work.")], True,
     "'worth tracking separately' blocks"),

    # Discharged, by either route.
    ([say("Worth its own issue."), FILE_CLI, say("Filed it.")], False,
     "filing after the assertion does not block"),
    ([say("Worth an issue."), FILE_TOOL, say("Done.")], False,
     "the harness create_issue tool discharges it"),
    ([say("Worth an issue."), COMMENT, say("Added to the existing one.")],
     False, "commenting onto an existing issue discharges it"),

    # Already-filed reporting is the CORRECT behaviour and must pass.
    ([say("Filed as #1043 -- worth its own issue, now tracked.")], False,
     "citing a filed issue number does not block"),
    ([say("Worth an issue; tracked in #897 already.")], False,
     "citing an existing tracking issue does not block"),

    # ORDINARY PROSE THAT MUST NEVER FIRE.
    #
    # These twelve are already silent against the patterns above -- they are
    # here to keep it that way. Every one was produced by a reviewer while
    # probing a proposed WIDENING of this guard (ai-config#2017, closed
    # unmerged), and each one that widening made fire.
    #
    # That is what makes them worth keeping after the widening was abandoned.
    # A negative case earns its place by being a sentence someone actually
    # tried to make the guard swallow, and the cheapest time to collect such
    # sentences is while somebody is attacking the guard. Discarding them with
    # the branch would throw away the only durable product of nine review
    # rounds.
    #
    # Two of them are worth reading rather than skimming, because they are
    # this corpus's own house style rather than contrived English: the FLAG
    # status line, which the docstring at the top of this file names as the
    # class that must never fire, and the "the reviewer decides whether to
    # act" sentence, which is correct behaviour this guard exists to protect.
    ([say("The reviewer decides whether to act on it; I have filed it as #1379.")], False,
     "deferring the ACTION while reporting the filing"),
    ([say("Whether to act on this is the reviewer's call.")], False,
     "whether to ACT is genuinely the reviewer's call"),
    ([say("I'll leave the reviewer to judge whether the approach is right.")], False,
     "a design judgment names no tracking"),
    ([say("The team will decide whether to ship this behind a flag.")], False,
     "an ordinary product decision"),
    ([say("I left the reviewer a note about the tracking issue.")], False,
     "note-leaving with the party as indirect object"),
    ([say("I left a note for the reviewer about the tracking issue.")], False,
     "the dative-shifted form of the same sentence"),
    ([say("I left a question for the reviewer about the tracking issue.")], False,
     "`question` reads as an artifact here, not a decision"),
    ([say("Flagging for the team: the follow-up issue is stale and nobody owns it.")], False,
     "this corpus's own FLAG status convention"),
    ([say("The team call on Monday will cover the tracker.")], False,
     "`team call` is a meeting"),
    ([say("I asked the maintainer to decide which issue to prioritize next.")], False,
     "ordinary infinitival English, no deferral of whether to record"),
    ([say("I left my judgment for the reviewer about the tracking issue.")], False,
     "a written record of a judgment already made"),
    ([say("Deferring to the reviewer on whether this is worth pursuing.")], False,
     "pursuing is an action decision, correctly theirs"),
    # QUOTATION IS NOT ASSERTION.
    #
    # A message about this guard cites its own patterns, and every citation is
    # an assertion in form and a quotation in fact. Measured repeatedly: a
    # recap explaining a fix to one alternative was blocked by that
    # alternative, because the name sat in a code span.
    ([say("The pattern `warrants a follow-up` already matched on main.")], False,
     "a pattern name in a code span is a quotation"),
    ([say("Its alternatives are `worth its own issue` and `needs an issue`.")], False,
     "two quoted alternatives, no claim about filing anything"),
    ([say("A reviewer wrote:\n\n> This warrants a follow-up issue.\n\nNoted.")], False,
     "the assertion inside a blockquote is someone else's"),
    ([say("Example:\n```\nworth its own issue\n```\nthat is the pattern.")], False,
     "the assertion inside a code fence is an illustration"),
    # The boundary: stripping must not swallow a REAL assertion beside a quote.
    ([say("The `warrants` alternative is fine, but this needs a tracking issue.")], True,
     "a genuine assertion still blocks when a code span sits beside it"),
    # The inverse hazard, and the reason a removed block becomes a TERMINATOR
    # rather than a space. `defect` and `file` here are 400 characters apart
    # and cannot satisfy the bounded pattern; collapsing the fence to a space
    # would delete every `.` between them and CREATE the match.
    ([say("That is a real defect\n```\n" + "x" * 400 + "\n```\nand we should file it later.")],
     False,
     "stripping must not bridge a bounded gap it was never meant to close"),
    # Flags that are not issue-shaped must not trip it.
    ([say("FLAG -- #1038 must merge before #1036; they conflict.")], False,
     "a merge-order flag does not block"),
    ([say("FLAG -- claude-review is red for the known context reason.")],
     False, "a status heads-up does not block"),
    ([UNRELATED, say("All five PRs are clean.")], False,
     "an ordinary recap does not block"),

    # Ordering: a filing BEFORE the assertion does not discharge a later one.
    ([FILE_CLI, say("Also, that other gap is worth its own issue.")], True,
     "a filing preceding the assertion does not count"),
]


def run(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    try:
        # Fresh sentinel dir per case, so the once-per-message guard does not
        # make later cases silently pass.
        env = dict(os.environ, TMPDIR=tempfile.mkdtemp())
        out = subprocess.run(
            [sys.executable, HOOK], input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True, env=env,
        ).stdout
        return '"decision": "block"' in out or '"decision":"block"' in out
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
            print(f"FAIL: {label} (expected block={expected}, got {got})")
            failures += 1

    # The complement it was built to cover: no-offer-to-file.py must NOT fire
    # on the declarative form, which is exactly why this hook is needed. If
    # that ever changes, one of the two is redundant and should be merged.
    sibling = os.path.join(os.path.dirname(HOOK), "no-offer-to-file.py")
    if os.path.exists(sibling):
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w") as fh:
            fh.write(json.dumps(
                say("FLAG -- a mechanism bug worth its own issue.")) + "\n")
        out = subprocess.run(
            [sys.executable, sibling],
            input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True,
        ).stdout
        os.unlink(path)
        if "block" not in out:
            print("PASS: no-offer-to-file does not cover the declarative form")
            passes += 1
        else:
            print("FAIL: no-offer-to-file now covers this; merge the two hooks")
            failures += 1

    out = subprocess.run(
        [sys.executable, HOOK], input='{"transcript_path": "/nonexistent"}',
        capture_output=True, text=True,
    )
    if out.returncode == 0 and "block" not in out.stdout:
        print("PASS: fails open on an unreadable transcript")
        passes += 1
    else:
        print("FAIL: should fail open on an unreadable transcript")
        failures += 1

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
