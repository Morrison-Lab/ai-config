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

    # Third-party deferral: no offer verb, no question mark, and the decision
    # named as somebody else's.
    #
    # The FIRST case below already matched before this PR, via the pre-existing
    # `warrants a follow-up` alternative -- verified against main's own regex.
    # It is kept because it is the phrasing that produced the section, not
    # because it was ever uncovered. The four that follow are the ones a
    # reviewer supplied as walking straight past the pre-widening patterns
    # (ai-config#2007), and they are what the widening is actually for.
    ([say("Flagging for the reviewer's call on whether it warrants a follow-up issue.")], True,
     "the original phrasing blocks"),
    ([say("Flagging for the reviewer to judge whether this belongs in the tracker.")], True,
     "deferral phrased as belonging in the tracker blocks"),
    ([say("I'll defer to the reviewer on whether to open an issue for this.")], True,
     "explicit deferral about opening an issue blocks"),
    ([say("Leaving it to the reviewer's discretion on whether this is worth pursuing an issue.")], True,
     "deferral to discretion blocks"),
    ([say("Deferring to the maintainer on whether this needs tracking.")], True,
     "a maintainer is as much a third party as a reviewer"),

    # The boundary the widening must not cross. Whether to ACT on a finding IS
    # genuinely a reviewer's call; only whether to RECORD it is nobody's to
    # defer, so a tracking word inside the same sentence is required.
    ([say("Whether to act on this is the reviewer's call.")], False,
     "deferring the ACTION, not the recording, is correct"),
    ([say("I'll leave the reviewer to judge whether the approach is right.")], False,
     "deferring a design judgment names no tracking"),
    ([say("The team will decide whether to ship this behind a flag.")], False,
     "an ordinary product decision is not a filing deferral"),
    ([say("I left the reviewer a note about the benchmark.")], False,
     "'left the reviewer' with no tracking word is ordinary prose"),
    # Cursor Bugbot, ai-config#2007: a bare verb plus a party plus a tracking
    # word is not a deferral. The construction is what defers -- "leaving it TO
    # the reviewer" versus "leaving the reviewer a note".
    ([say("I left the reviewer a note about the tracking issue.")], False,
     "a note ABOUT a tracking issue defers nothing"),
    ([say("I leave the reviewer a note on the follow-up issue each round.")], False,
     "the present-tense form of the same ordinary sentence"),
    # Cursor Bugbot, ai-config#2007 round 2: with `to` required, past-tense
    # `left it to` is a real deferral and must fire. Dropping `left` to fix the
    # note-leaving false positive was the wrong lever -- the `to` does that work.
    ([say("Left it to the maintainer on whether this needs tracking.")], True,
     "past-tense deferral construction blocks"),
    ([say("I left it to the reviewer on whether to file a follow-up.")], True,
     "past-tense with a first-person subject blocks"),
    # Claude review, ai-config#2007 round 3: a NOUN-PHRASE object between the
    # verb and the connector is a natural way to phrase this, and requiring the
    # connector immediately after the verb dropped all of it. What discriminates
    # is ORDER -- the connector precedes the party in a deferral, and follows it
    # in note-leaving, where the party is the verb's indirect object.
    ([say("I'll leave this decision to the maintainer regarding the tracking issue.")], True,
     "a noun-phrase object before the connector still blocks"),
    ([say("Leaving the call to the reviewer about opening a follow-up issue.")], True,
     "'the call' as the object, not a bare pronoun"),
    ([say("Deferring judgment to the maintainer about the tracker entry.")], True,
     "a bare noun object with no determiner"),
    ([say("I'll leave that choice to the team about filing this.")], True,
     "determiner plus noun as the object"),
    ([say("Flagging this concern for the reviewer regarding the tracking issue.")], True,
     "the same shape on the flag/for connector"),
    # The boundary the widened gap must not cross: note-leaving with a `to`
    # later in the sentence. The party arrives BEFORE the connector there.
    ([say("I left the reviewer a note pointing to the tracker.")], False,
     "a trailing `to` after the party is not a deferral construction"),
    # Claude review, ai-config#2007 round 4: `to`/`for` is ambiguous between the
    # deferral sense ("leave this decision TO the reviewer") and the benefactive
    # one ("leave a note FOR the reviewer" = "leave the reviewer a note"). Both
    # have the identical surface shape, so no wildcard width separates them --
    # what does is WHAT IS HANDED OVER. You defer a decision and you leave a note.
    ([say("I left a note for the reviewer about the tracking issue.")], False,
     "benefactive `for`: the dative-shifted form of the note-leaving case"),
    ([say("I left a comment for the maintainer on the follow-up issue.")], False,
     "the same shape with a different artifact noun"),
    ([say("Leaving a message for the team about the tracker.")], False,
     "present participle, still an artifact rather than a decision"),
    # Cursor Bugbot, ai-config#2007 round 5: the named-object allowlist was
    # itself too tight. `leave it UP TO` takes a particle, and a decision noun
    # takes premodifiers ("the FILING decision"). The premodifier slot is bound
    # to the head noun rather than free-standing -- a free one re-admitted the
    # benefactive, since "a NOTE for" would fill it. Caught by keeping the three
    # benefactive cases above while widening, which is the point of them.
    ([say("I'll leave it up to the reviewer whether to open an issue.")], True,
     "the `up to` particle form blocks"),
    ([say("Leaving the filing decision to the maintainer about the tracker.")], True,
     "a premodified decision noun blocks"),
    ([say("Left the tracking decision to the team on this follow-up.")], True,
     "past tense plus a premodified decision noun"),
    # Claude review, ai-config#2007 round 6. Two FALSE POSITIVES, which the
    # stopping rule above does not license declining -- it governs invented
    # false NEGATIVES only.
    #
    # `question` carried both senses: "the question of whether to file" is a
    # decision, "I left a question for the reviewer" is the benefactive. A word
    # that names both cannot discriminate, so it left the list.
    ([say("I left a question for the reviewer about the tracking issue.")], False,
     "`question` as an artifact noun, same shape as the note case"),
    ([say("Leaving a question for the maintainer on the follow-up issue.")], False,
     "the participle form of the same"),
    # `flag` needs its object where the other verbs do not: "deferring to the
    # reviewer" is a complete deferral, "flagging for the reviewer" is ordinary
    # English for drawing attention. Left optional, it fired on this corpus's
    # own FLAG status convention -- the class this hook's docstring names as
    # the one that must never fire.
    ([say("Flagging for the team: the follow-up issue is stale and nobody owns it.")], False,
     "a bare status FLAG defers nothing"),
    ([say("Flagging for the reviewer -- the tracker already has an entry for this.")], False,
     "the same with an em-dash aside"),
    # Claude review, ai-config#2007 round 7: `call` is the one alternative in
    # the possessive pattern with a common non-judgment reading, and with the
    # marker optional an ordinary noun-noun compound satisfied it. That pattern
    # has no verb and no connector to lean on, so the possessive is the only
    # thing separating a decision from a meeting.
    ([say("The team call on Monday will cover the tracker.")], False,
     "`team call` is a meeting, not a decision handed over"),
    ([say("The owner call is scheduled before the follow-up.")], False,
     "the same compound with a different party word"),
    # Measured 2026-08-23: this guard blocked a status recap that was DISCUSSING
    # its own regex, because a pattern name sat in a code span. A message about
    # the guard cites the guard, and every citation is an assertion in form and
    # a quotation in fact -- the sibling hook strips code spans for exactly this.
    ([say("The pattern `warrants a follow-up` already matched on main.")], False,
     "a pattern name in a code span is a quotation, not an assertion"),
    ([say("Its alternatives are `worth its own issue` and `needs an issue`.")], False,
     "two quoted alternatives, still no claim about filing anything"),
    ([say("A reviewer wrote:\n\n> This warrants a follow-up issue.\n\nNoted.")], False,
     "the assertion inside a blockquote is someone else's"),
    ([say("Example:\n```\nworth its own issue\n```\nthat is the pattern.")], False,
     "the assertion inside a code fence is an illustration"),
    # The boundary: stripping must not swallow a REAL assertion beside a quote.
    ([say("The `warrants` alternative is fine, but this needs a tracking issue.")], True,
     "a genuine assertion still blocks when a code span sits beside it"),
    # `pursuing` was tried as a tracking word and removed: deferring whether
    # something is worth PURSUING is an action decision, which this section
    # says is correctly the reviewer's.
    ([say("Whether this is worth pursuing is the reviewer's call.")], False,
     "pursuing is an action word, not a word of record"),
    ([say("Deferring to the reviewer on whether this is worth pursuing.")], False,
     "a full deferral construction still passes when the deferred thing is an ACTION"),
    ([say("The reviewer decides whether to act on it; I have filed it as #1379.")], False,
     "already filed, and the deferral is about acting"),

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
