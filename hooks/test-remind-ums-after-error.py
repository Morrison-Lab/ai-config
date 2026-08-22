"""Test the remind-ums-after-error hook.

Builds a synthetic transcript per case and feeds the hook a UserPromptSubmit
payload pointing at it. The hook must print a reminder for a genuine
first-person admission with no recording after it, and print NOTHING for
everything else.

Two properties this suite is specifically written to pin, because both are
what the design got wrong on the first attempt elsewhere:

  1. It must never exit non-zero and never emit a `block` decision. This hook
     may only ADD context; suppressing an error admission is the failure mode
     it exists to avoid.
  2. Correcting someone ELSE's claim, or quoting the rule, must stay silent.

Run:  python3 hooks/test-remind-ums-after-error.py hooks/remind-ums-after-error.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

if len(sys.argv) < 2:
    sys.exit(f"Usage: python3 {sys.argv[0]} <path-to-hook>")
HOOK = sys.argv[1]

if not os.path.isfile(HOOK):
    sys.exit(
        f"FATAL: hook not found at {HOOK} -- a missing file would otherwise "
        "read as 'silent' on every case and print a perfect pass"
    )


def txt(s, sidechain=False):
    return {
        "type": "assistant",
        "isSidechain": sidechain,
        "message": {"content": [{"type": "text", "text": s}]},
    }


def tool(name, inp, sidechain=False):
    return {
        "type": "assistant",
        "isSidechain": sidechain,
        "message": {"content": [{"type": "tool_use", "name": name, "input": inp}]},
    }


def user(s):
    return {"type": "user", "message": {"content": [{"type": "text", "text": s}]}}


ADMIT = txt("Checking that again -- I was wrong about the repo being public.")

REMIND = [
    # The positive direction for every alternative the `\b` anchoring touched
    # (ai-config#1756). Anchoring can fail two ways: leaking a third-person
    # match (SILENT below) or losing a real admission (these). A suite carrying
    # only one side cannot tell a correct anchor from an over-tightened one.
    ([txt("I was wrong about this.")], "first person: was wrong"),
    ([txt("I got that wrong.")], "first person: got that wrong"),
    ([txt("I mischaracterized it.")], "first person: mischaracterized"),
    ([txt("I incorrectly claimed success.")], "first person: adverb form"),
    ([txt("I overstated the waste.")], "first person: quantitative"),
    ([txt("I retract that.")], "first person: retract"),
    ([ADMIT], "bare admission, nothing after it"),
    ([ADMIT, user("ok"), txt("Continuing with the next task.")],
     "admission then unrelated work"),
    ([txt("I miscounted: the changelog lists 10, not 9.")], "miscounted"),
    ([txt("My mistake -- that query predated my own pushes.")], "my mistake"),
    ([txt("Correcting myself: rprojroot resolves a different root.")],
     "correcting myself"),
    ([txt("I mischaracterized the exposure as public.")], "mischaracterized"),
    ([txt("Retracting my earlier claim about the hook directory.")], "retracting"),
    ([txt("I incorrectly reported the PR as conflict-free.")], "incorrectly reported"),
    # Quantitative self-corrections (ai-config#1210). The first is verbatim
    # from the retraction in ucdavis/bcs#587 that the issue was filed over.
    ([txt("Correcting this issue's headline figure. I overstated the waste.")],
     "correcting this + overstated"),
    ([txt("I overstated the waste in that estimate.")], "overstated"),
    ([txt("I undercounted the open PRs.")], "undercounted"),
    ([txt("I overclaimed what the measurement showed.")],
     "overclaimed, via over + claimed"),
    ([txt("Correcting my earlier count of the fragments.")], "correcting my"),
    ([ADMIT, tool("Edit", {"file_path": "R/foo.R"})],
     "a write that is NOT to a memory/skill path does not clear it"),
    ([tool("Edit", {"file_path": "memories/tools.md"}), ADMIT],
     "a recording BEFORE the admission does not clear it"),
    # Omission self-critique (ai-config#1751). "should have" + past
    # participle is retrospective, distinct from every pattern above, which
    # all catch a FACTUAL retraction rather than a behavioral gap.
    ([txt("The user is right -- I should have proactively found the open PRs.")],
     "should have + verb, the exact quoted case"),
    ([txt("I should have checked the review before pushing.")],
     "should have + verb"),
    ([txt("I should" + chr(0x2019) + "ve verified that first.")],
     "should've, curly apostrophe"),
]

SILENT = [
    ([txt("All checks are green; nothing to correct.")], "no admission at all"),
    # A word ending in "i" followed by an admission verb. Without a `\b` before
    # each bare `i` alternative, the regex matched that trailing letter as the
    # first-person subject, so every one of these fired on a THIRD-person
    # statement -- the exact thing the module docstring says it must never do
    # (ai-config#1756). #1752 anchored the `should have` alternative and left
    # its six siblings unanchored; these pin all six.
    ([txt("The API was wrong about this endpoint.")], "acronym + 'was wrong'"),
    ([txt("The API got that wrong initially.")], "acronym + 'got that wrong'"),
    ([txt("The semi mischaracterized the exposure.")], "word ending in i + verb"),
    ([txt("The CLI incorrectly claimed success.")], "acronym + adverb form"),
    ([txt("The Delphi overstated the risk.")], "word ending in i + quantitative"),
    # "needs to" (plural) matches neither `need\s+to\s+` nor the skip-the-group
    # path, so the obvious phrasing is silent under BOTH regexes and pins
    # nothing. Caught by review on #1889; "Fermi need to retract" is the form
    # that actually exercises this alternative's anchor.
    ([txt("Scientists at Fermi need to retract the finding.")],
     "word ending in i + retract"),
    ([txt("The AI should have caught it.")], "the already-anchored sibling"),
    ([txt("The review was wrong about the pathspec.")],
     "correcting SOMEONE ELSE, not myself"),
    ([txt("That claim in the docs is incorrect.")], "someone else's claim"),
    ([txt("The reviewer's suggestion was mistaken.")], "reviewer was mistaken"),
    # The boundary the widened patterns must not cross (ai-config#1210). The
    # issue proposed `correcting\s+(my|this|the)\b`, which fires on the second
    # of these -- its own stated must-stay-silent case -- so `the` was left
    # out. Both directions are pinned here so a later widening cannot quietly
    # reintroduce it.
    ([txt("The report overstated it by a wide margin.")],
     "SOMEONE ELSE overstated, no first-person subject"),
    ([txt("Correcting the reviewer, who misread the diff.")],
     "correcting SOMEONE ELSE, not myself"),
    ([txt("The reviewer overstated the risk here.")], "reviewer overstated"),
    # The boundary the "should have" widening (ai-config#1751) must not
    # cross: a future obligation ("should have this ready by Friday",
    # main-verb "have") reads identically to a retrospective critique up to
    # the word after "have", and a third-person "should have" is someone
    # ELSE's gap, not mine.
    ([txt("I should have this done by Friday.")],
     "should have + possessive/determiner NP, future obligation not a critique"),
    ([txt("I should have a plan ready before the next push.")],
     "should have + indefinite article NP"),
    ([txt("You should have checked that yourself.")],
     "should have, but second person"),
    ([txt("The reviewer should have caught this earlier.")],
     "should have, but SOMEONE ELSE's gap"),
    # PR #1752 review: `i\s+should` with no `\b` matched the trailing "i" of
    # any word ending in that letter -- "the AI should", "the API should",
    # "this semi should" all fired as if "I" were the subject. Pinned here so
    # the boundary cannot regress.
    ([txt("The AI should have caught this earlier.")],
     "should have, but subject is 'the AI' not 'I' (word-boundary regression)"),
    ([txt("The API should have returned an error here.")],
     "should have, but subject is 'the API' not 'I' (word-boundary regression)"),
    ([txt("This semi should have been replaced before merge.")],
     "should have, but 'semi' merely ends in 'i' (word-boundary regression)"),
    ([txt("The rule fires on phrases like `I was wrong` in a message.")],
     "quoting the trigger inside inline code"),
    ([txt("The user wrote:\n\n> I was wrong about that\n\nso the rule applies.")],
     "trigger inside a blockquote"),
    ([txt("Example:\n```\nI was wrong\n```\nthat is the pattern.")],
     "trigger inside a code fence"),
    ([ADMIT, tool("Edit", {"file_path": "memories/preferences.md"})],
     "admission then a memory write clears it"),
    ([ADMIT, tool("Write", {"file_path": "/repo/shared/workflow/x.md"})],
     "admission then a shared-fragment write clears it"),
    ([ADMIT, tool("Task", {"prompt": "Run a ums pass recording this"})],
     "admission then a UMS subagent dispatch clears it"),
    ([ADMIT, tool("Bash", {"command": "git commit -m 'ums: record it'"})],
     "admission then a ums commit clears it"),
    ([txt("I was wrong about that.", sidechain=True)],
     "a SUBAGENT's admission is not my outgoing message"),
    # ai-config#1965, the TRUE-positive half. A bare-word use of an action
    # word still discharges. The defect was that these and the path reads in
    # PATH_READS below were indistinguishable, so a suite carrying only one
    # side cannot tell a correct guard from an over-tightened one.
    ([ADMIT, tool("Bash", {"command": "grep -n ums README.md"})],
     "bare-word `ums` in a command still discharges"),
    ([ADMIT, tool("Skill", {"skill": "ums"})],
     "invoking the ums skill by name still discharges"),
    ([ADMIT, tool("Task", {"prompt": "Please run ums."})],
     "sentence-final `ums.` still discharges -- a bare dot is not a path"),
    ([ADMIT, tool("Task", {"prompt": "update memories and skills for this"})],
     "the `update memories` phrase still discharges"),
    ([ADMIT, tool("Task", {"prompt": "memorize this correction"})],
     "bare `memorize` still discharges"),
    ([ADMIT, tool("Task", {"prompt": "run record-learnings on it"})],
     "bare `record-learnings` still discharges"),
]

# ai-config#1965, the FALSE-positive half. `\b` treats `-`, `/`, and `.` as
# boundaries, so `\bums\b` fired inside a PATH and a mere READ discharged the
# reminder -- silently, since this hook fails open. Reading the fragment that
# states the UMS rule was enough, so the sessions most likely to be consulting
# the rule were exactly the ones the hook stopped nagging.
PATH_READS = [
    ([ADMIT, tool("Bash", {"command": "cat shared/workflow/run-ums-proactively.md"})],
     "reading the UMS rule fragment does not discharge"),
    ([ADMIT, tool("Bash", {"command": "ls skills/ums-notes/"})],
     "listing a hyphenated ums-* directory does not discharge"),
    ([ADMIT, tool("Bash", {"command": "open memories/record-learnings-policy.md"})],
     "reading a record-learnings-* path does not discharge"),
    ([ADMIT, tool("Bash", {"command": "git show HEAD:docs/memorize-rules.md"})],
     "reading a memorize-* path does not discharge"),
    ([ADMIT, tool("Bash", {"command": "python3 hooks/test-remind-ums-after-error.py"})],
     "running this hook's own test file does not discharge"),
    ([ADMIT, tool("Bash", {"command": "cat memories/ums-cases.md"})],
     "reading a ums-* memory file does not discharge"),
    ([ADMIT, tool("Task", {"prompt": "Read shared/workflow/run-ums-proactively.md"})],
     "a dispatch that only names the fragment does not discharge"),
]
REMIND += PATH_READS


def run(recs, sentinel_dir=None):
    """Run the hook against a synthetic transcript.

    `sentinel_dir` shares one sentinel directory across calls, so a caller can
    exercise the dedup key itself; the default gives each case a fresh one.
    """
    fd, tpath = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")
    own_dir = sentinel_dir is None
    if own_dir:
        sentinel_dir = tempfile.mkdtemp()
    try:
        p = subprocess.run(
            ["python3", HOOK],
            input=json.dumps({"transcript_path": tpath}),
            capture_output=True, text=True,
            env=dict(os.environ, TMPDIR=sentinel_dir),
        )
    finally:
        os.unlink(tpath)
        if own_dir:
            shutil.rmtree(sentinel_dir, ignore_errors=True)

    if p.returncode != 0:
        sys.exit(f"FATAL: hook exited {p.returncode}\n{p.stderr.strip()}")
    if "\"decision\"" in p.stdout or "block" in p.stdout.lower():
        sys.exit(
            "FATAL: hook emitted a block-shaped decision. This hook must only "
            f"ever add context, never suppress a message.\n{p.stdout}"
        )
    return "REMIND" if p.stdout.strip() else "silent"


wrong = 0
print("should REMIND:")
for recs, desc in REMIND:
    v = run(recs)
    wrong += v != "REMIND"
    print(f"  {v:<7} {desc}")

print("\nshould stay SILENT:")
for recs, desc in SILENT:
    v = run(recs)
    wrong += v != "silent"
    print(f"  {v:<7} {desc}")

# The sentinel suppresses a repeat of the SAME admission, and must not reach
# across sessions. Two distinct transcripts carrying identical text at an
# identical record index are different sessions, so both must remind; only the
# second run against the SAME transcript is a repeat. Sharing one sentinel dir
# is what makes the distinction observable -- with the transcript path dropped
# from the key, case 2 below goes silent.
print("\nsentinel scope (one shared sentinel dir):")
shared = tempfile.mkdtemp()
try:
    seq = [
        (run([ADMIT], shared), "REMIND", "session A, first prompt"),
        (run([ADMIT], shared), "REMIND", "session B, same text and index"),
    ]
    fd, same_path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps(ADMIT) + "\n")
    try:
        env = dict(os.environ, TMPDIR=shared)
        payload = json.dumps({"transcript_path": same_path})
        out = [
            subprocess.run(["python3", HOOK], input=payload, capture_output=True,
                           text=True, env=env).stdout.strip()
            for _ in range(2)
        ]
        seq.append(("REMIND" if out[0] else "silent", "REMIND",
                    "same transcript, first prompt"))
        seq.append(("REMIND" if out[1] else "silent", "silent",
                    "same transcript again -- fires once per admission"))
    finally:
        os.unlink(same_path)
finally:
    shutil.rmtree(shared, ignore_errors=True)

for got, want, desc in seq:
    wrong += got != want
    print(f"  {got:<7} {desc}")

total = len(REMIND) + len(SILENT) + len(seq)
print(f"\n{total - wrong}/{total} correct" + ("" if wrong == 0 else f"  ({wrong} WRONG)"))
sys.exit(1 if wrong else 0)
