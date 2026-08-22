"""Test the remind-learn-from-review guard.

The value is concentrated in the negative cases. This hook fires on accepting a
reviewer's finding, and the phrases that signal acceptance ("good catch",
"you're right") are also said to the USER and in non-review contexts. A guard
that nags on those, or on a Rebut, or that goes SILENT because the ordinary fix
looks like a recorded learning, gets switched off -- and then the case it
exists for goes unprotected too.

Several cases below are regression tests for the ai-config#1075 review, pasted
close to the reviewer's own examples per algorithmatize-checks' "test against
the incident verbatim":
  * the fix itself (an edit to shared/CLAUDE.md/memories) is NOT a discharge;
  * a Read/Grep of a hook/CI path is NOT a mechanism;
  * routine prose ("no check is failing", "already tracked in #N") is NOT a
    one-off judgment;
  * review context must be NEAR the acceptance, not merely earlier in the
    session;
  * "good pointer" must not match "good point";
  * a non-dict JSON payload must fail open and silent.

Run: python3 hooks/test-remind-learn-from-review.py hooks/remind-learn-from-review.py
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


def tool(name, inp):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": name, "input": inp}]}}


# A review-surface action, establishing PR-review context.
REVIEW = tool("resolve_review_thread", {"threadId": "x"})
# Accepting a finding; the sentence also names the reviewer, so it carries its
# own context.
ACCEPT = say("Good catch -- the reviewer is right, the regex misses the "
             "anchored form.")

# Discharges.
UMS_BASH = tool("Bash", {"command": "echo running the ums pass now"})
UMS_TASK = tool("Task", {"description": "record learnings",
                         "prompt": "run ums to record what the review taught"})
HOOK_WRITE = tool("Write", {"file_path": "hooks/no-x.py", "content": "..."})

# NON-discharges (the fix, or a read, or routine prose).
FIX_SHARED = tool("Edit", {"file_path": "shared/workflow/fully-clean.md",
                           "old_string": "a", "new_string": "b"})
FIX_MEMORY = tool("Write", {"file_path": "memories/git.md", "content": "..."})
READ_HOOK = tool("Read", {"file_path": "hooks/no-offer-to-file.py"})
GREP_CI = tool("Grep", {"pattern": "x", "path": ".github/workflows/"})

# Neutral filler carrying no review word and no acceptance, to push an
# acceptance out of REVIEW_WINDOW of the last review signal.
FILLER = [say(f"Working on the next file, step {n}.") for n in range(8)]


# (events, should_remind, label)
CASES = [
    # The case this exists for: a reviewer finding accepted, nothing recorded.
    ([REVIEW, ACCEPT], True,
     "accepted finding with no follow-up reminds"),
    ([ACCEPT], True,
     "acceptance naming the reviewer carries its own context"),

    # Discharged only by an EXPLICIT learning / mechanism / one-off.
    ([REVIEW, ACCEPT, UMS_BASH], False,
     "an explicit ums pass discharges it"),
    ([REVIEW, ACCEPT, UMS_TASK], False,
     "a subagent dispatched to run ums discharges it"),
    ([REVIEW, ACCEPT, HOOK_WRITE], False,
     "writing a hook file discharges it (mechanism)"),
    ([REVIEW, say("Good catch from the reviewer -- but this is a one-off "
                  "typo, no rule would have caught it.")], False,
     "an explicit one-off judgment discharges it"),

    # Regression (finding 2): the FIX is not the lesson. Editing the flagged
    # corpus file, or any memory file, must NOT discharge.
    ([REVIEW, ACCEPT, FIX_SHARED], True,
     "editing the flagged shared/ file (the fix) does not discharge"),
    ([REVIEW, ACCEPT, FIX_MEMORY], True,
     "a bare memory write is not an explicit learning pass"),

    # Regression (finding 3): a read builds nothing.
    ([REVIEW, ACCEPT, READ_HOOK], True,
     "reading a hook file does not discharge"),
    ([REVIEW, ACCEPT, GREP_CI], True,
     "grepping .github/workflows/ does not discharge"),

    # Regression (finding 5): routine prose is not a one-off judgment.
    ([REVIEW, ACCEPT, say("All green: no check is failing on this head.")],
     True, "'no check is failing' does not discharge"),
    ([REVIEW, ACCEPT, say("The finding is already tracked in #1065.")], True,
     "'already tracked in #N' does not discharge"),
    ([REVIEW, ACCEPT, say("There is no rule about this yet, so I added one.")],
     True, "'no rule about this' does not discharge"),

    # A Rebut is the opposite disposition and must never fire.
    ([REVIEW, say("The reviewer is wrong here; the pattern is valid. "
                  "Rebutting with the repro.")], False,
     "a rebuttal does not remind"),

    # Regression (finding 4): review context must be NEAR. An earlier review
    # action followed by unrelated agreement with the user is not an accept.
    ([REVIEW] + FILLER + [say("You're right, let's use tabs instead.")], False,
     "agreement far from any review signal does not remind (staleness)"),
    ([REVIEW, say("You're right, let's use tabs instead.")], True,
     "agreement immediately after a review signal still counts"),

    # Regression (finding 6): word boundary. "good pointer" is not "good point".
    ([REVIEW, say("That is a good pointer to the reviewer's docs.")], False,
     "'good pointer' does not match 'good point'"),

    # Acceptance with no review context anywhere must not fire.
    ([say("Good catch, thanks! I'll add that to the plan.")], False,
     "acceptance with no review context does not remind"),

    # Quoting the rule (inline code) is stripped by visible_prose.
    ([REVIEW, say("The `good catch` convention for a reviewer is discussed "
                  "in the fragment.")], False,
     "an inline-code mention of the phrase does not remind"),

    # Ordering: a discharge BEFORE the acceptance does not count.
    ([UMS_BASH, REVIEW, ACCEPT], True,
     "a ums pass preceding the acceptance does not count"),

    # ai-config#1965. `\b` treats `-`, `/`, and `.` as boundaries, so
    # `\bums\b` fired inside a PATH and a mere READ discharged this reminder
    # too. Both directions are here deliberately: the defect was that a read
    # of the UMS fragment and a genuine `run ums` were indistinguishable.
    ([REVIEW, ACCEPT,
      tool("Bash", {"command": "cat shared/workflow/run-ums-proactively.md"})],
     True, "reading the UMS rule fragment does not discharge"),
    ([REVIEW, ACCEPT, tool("Bash", {"command": "ls skills/ums-notes/"})],
     True, "listing a hyphenated ums-* directory does not discharge"),
    ([REVIEW, ACCEPT,
      tool("Bash", {"command": "open memories/record-learnings-policy.md"})],
     True, "reading a record-learnings-* path does not discharge"),
    ([REVIEW, ACCEPT,
      tool("Bash", {"command": "python3 hooks/test-remind-ums-after-error.py"})],
     True, "running the sibling's test file does not discharge"),
    ([REVIEW, ACCEPT, tool("Bash", {"command": "grep -n ums README.md"})],
     False, "bare-word `ums` in a command still discharges"),
    ([REVIEW, ACCEPT, tool("Task", {"prompt": "Please run ums."})],
     False, "sentence-final `ums.` still discharges -- a bare dot is not a path"),
    ([REVIEW, ACCEPT, tool("Task", {"prompt": "memorize this correction"})],
     False, "bare `memorize` still discharges"),
    # Review finding on #1968: the slash-command spelling must survive the
    # path guard, while a path ending in the same word must not.
    ([REVIEW, ACCEPT, tool("Task", {"prompt": "Run /ums to record this"})],
     False, "the slash-command spelling `/ums` still discharges"),
    ([REVIEW, ACCEPT, tool("Bash", {"command": "ls skills/ums"})],
     True, "a path ending in `ums` does not discharge"),
]


def run(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    try:
        env = dict(os.environ, TMPDIR=tempfile.mkdtemp())
        out = subprocess.run(
            [sys.executable, HOOK], input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True, env=env,
        )
        assert out.returncode == 0, f"non-zero exit: {out.returncode}"
        assert '"decision"' not in out.stdout, "must never emit a block decision"
        return "[hook: remind-learn-from-review]" in out.stdout
    finally:
        os.unlink(path)


def main():
    passes = failures = 0
    for events, expected, label in CASES:
        try:
            got = run(events)
        except AssertionError as e:
            print(f"FAIL: {label} ({e})")
            failures += 1
            continue
        if got == expected:
            print(f"PASS: {label}")
            passes += 1
        else:
            print(f"FAIL: {label} (expected remind={expected}, got {got})")
            failures += 1

    # Fail open on an unreadable transcript.
    out = subprocess.run(
        [sys.executable, HOOK], input='{"transcript_path": "/nonexistent"}',
        capture_output=True, text=True,
    )
    if out.returncode == 0 and "[hook:" not in out.stdout:
        print("PASS: fails open on an unreadable transcript")
        passes += 1
    else:
        print("FAIL: should fail open on an unreadable transcript")
        failures += 1

    # Regression (finding 7): a non-dict JSON payload must fail open and silent.
    for bad in ('"just-a-string"', "null", "[1,2]", "42"):
        out = subprocess.run(
            [sys.executable, HOOK], input=bad, capture_output=True, text=True)
        if out.returncode == 0 and not out.stdout and not out.stderr:
            print(f"PASS: non-dict payload {bad!r} fails open and silent")
            passes += 1
        else:
            print(f"FAIL: non-dict payload {bad!r} did not fail silent "
                  f"(rc={out.returncode}, out={out.stdout!r}, err={out.stderr[:60]!r})")
            failures += 1

    # The complement it was built to cover: the first-person sibling must NOT
    # fire on an accepted reviewer finding, which is exactly why this hook is
    # needed. If that ever changes, one of the two is redundant.
    sibling = os.path.join(os.path.dirname(HOOK), "remind-ums-after-error.py")
    if os.path.exists(sibling):
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w") as fh:
            fh.write(json.dumps(REVIEW) + "\n")
            fh.write(json.dumps(ACCEPT) + "\n")
        out = subprocess.run(
            [sys.executable, sibling],
            input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True,
            env=dict(os.environ, TMPDIR=tempfile.mkdtemp()),
        )
        os.unlink(path)
        if "UMS reminder" not in out.stdout:
            print("PASS: remind-ums-after-error does not fire on an accepted "
                  "reviewer finding (first-person only)")
            passes += 1
        else:
            print("FAIL: remind-ums-after-error now covers this; merge the two")
            failures += 1

    # The cases above all run through `getattr(_ums, "UMS_WORD", ...)`, so
    # they exercise the SIBLING's pattern and never the literal fallback.
    # The fallback exists only so this degrades to silence rather than
    # crashing, and it is free to drift precisely because nothing reaches it
    # (ai-config#1965). Import a copy with no sibling beside it to pin it.
    lone = tempfile.mkdtemp()
    shutil.copy(HOOK, os.path.join(lone, os.path.basename(HOOK)))
    spec = importlib.util.spec_from_file_location(
        "_lone", os.path.join(lone, os.path.basename(HOOK)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if getattr(mod, "_ums", None) is not None:
        print("FAIL: sibling still importable -- the fallback was not exercised")
        failures += 1
    for cmd, want in [
        ("cat shared/workflow/run-ums-proactively.md", False),
        ("ls skills/ums-notes/", False),
        ("open memories/record-learnings-policy.md", False),
        ("python3 hooks/test-remind-ums-after-error.py", False),
        ("ls skills/ums", False),
        ("./ums-helper", False),
        ("grep -n ums README.md", True),
        ("Run /ums to record this", True),
        ("/memorize this correction", True),
        ("Please run ums.", True),
        ("memorize this correction", True),
        ("run record-learnings on it", True),
        ("update memories and skills", True),
    ]:
        got = bool(mod.UMS_WORD.search(cmd))
        if got == want:
            print(f"PASS: fallback UMS_WORD {'matches' if want else 'skips'} {cmd!r}")
            passes += 1
        else:
            print(f"FAIL: fallback UMS_WORD {'missed' if want else 'matched'} {cmd!r}")
            failures += 1
    shutil.rmtree(lone, ignore_errors=True)

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
