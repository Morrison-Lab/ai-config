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
    # Omission admissions & flawed query/scan explanations (ai-config#2775).
    ([txt("You are right. Note 14169 is an unresolved, resolvable diff comment on _fig-strobe-flow.qmd, asking that hard-coded numbers be computed. My prior query missed it because it filtered discussion-level timestamps rather than every nested note. I" + chr(0x2019) + "ll inspect the anchored diff and the data already available to replace those values at their source.")],
     "issue #2775 exact quote: prior query missed it because ... filtered rather than"),
    ([txt("My prior query missed it because it filtered discussion-level timestamps rather than every nested note.")],
     "prior query missed it because"),
    ([txt("My previous scan missed that file.")], "previous scan missed"),
    ([txt("Our earlier check missed the typo.")], "our earlier check missed"),
    ([txt("My prior search missed note 14169.")], "my prior search missed"),
    ([txt("Our prior query missed the note.")], "our prior query missed"),
    ([txt("You are right, I missed note 14169.")], "you are right, I missed"),
    ([txt("You" + chr(0x2019) + "re right -- I missed that in the first pass.")],
     "you're right -- I missed"),
    ([txt("I overlooked note 14169 on the diff.")], "I overlooked note"),
    ([txt("I missed this comment during my initial review.")], "I missed this comment"),
    ([txt("I missed the comment on the diff.")], "I missed the comment"),
    ([txt("I missed the note in the review.")], "I missed the note"),
    ([txt("I missed a finding in the checklist.")], "I missed a finding"),
    ([txt("I overlooked the warning from CI.")], "I overlooked the warning"),
    ([txt("I overlooked the error in the logs.")], "I overlooked the error"),
    ([txt("It filtered discussion-level timestamps rather than every nested note.")],
     "it filtered ... rather than"),
    ([txt("That was my mistake; the count was off by one.")],
     "my mistake (ai-config#1898 anchored form still fires)"),
    # The other side of the irrealis guard (ai-config#2997). A guard scoped to
    # the window before the hit must not swallow a real admission that merely
    # shares a sentence with a hypothetical, and must not read a marker out of
    # the middle of a word.
    ([txt("Even if the poller were enough, I was wrong about the base branch.")],
     "irrealis marker on a DIFFERENT clause still fires"),
    ([txt("It is caught even if I misread the status. I was wrong about the "
          "base branch.")],
     "a guarded hit is skipped, not treated as the end of the search"),
    ([txt("The animated gif I misread as a screenshot came from the docs.")],
     "`gif` merely ends in `if` -- word-boundary control on the guard"),
    ([txt("My earlier claim was wrong about the pin.")],
     "my earlier claim was wrong (ai-config#1898 anchored form still fires)"),
]

# ai-config#1898: the two `my`-led alternatives had no `\b` before `my`,
# so a word ending in "my" supplied the possessive. These stay silent under
# the anchored pattern; the "revert mutation" block at the bottom of this
# file strips the two anchors and checks that every one of them then FIRES,
# so each control is known to discriminate rather than merely to pass.
ANCHOR_1898 = [
    ([txt("The dummy error was expected.")],
     "dummy error (word ending in my + mistake|error)"),
    ([txt("An anatomy error crept in.")],
     "anatomy error (word ending in my + mistake|error)"),
    ([txt("The academy previous claim was wrong.")],
     "academy previous claim was wrong (word ending in my + earlier-claim form)"),
]

# Irrealis clauses (ai-config#2997). Each names a mistake that explicitly has
# NOT happened, so none is an admission. The "revert mutation" block at the
# bottom of this file disables the guard and checks that every one of them then
# FIRES, so each control is known to discriminate rather than merely to pass.
IRREALIS_2997 = [
    ([txt("The poller tracks note count as well as job status, so a posted "
          "review is caught even if I misread the job status.")],
     "issue #2997 exact quote: even if I misread"),
    ([txt("Unless I misread the diff, the two branches are identical.")],
     "unless I misread"),
    ([txt("The retry exists in case I miscounted the open notes.")],
     "in case I miscounted"),
    ([txt("It is worth re-checking whether I miscounted the fragments.")],
     "whether I miscounted"),
    ([txt("Whether or not I was wrong about the pin, the check still runs.")],
     "whether or not I was wrong"),
    ([txt("Had I misread the status, the second signal would have caught it.")],
     "had I misread (subject-auxiliary inversion)"),
    ([txt("Suppose I was wrong about the base branch; the guard still holds.")],
     "suppose I was wrong"),
    ([txt("Assuming that I was wrong about the count, the conclusion is "
          "unchanged.")],
     "assuming that I was wrong"),
    ([txt("If I was wrong about the repo being public, the scan would say so.")],
     "if I was wrong (bare if)"),
    ([txt("The second signal is there lest I misread the job status.")],
     "lest I misread"),
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
    # Omission pattern boundaries (ai-config#2775).
    ([txt("The prior query missed nothing.")],
     "prior query missed nothing (negated)"),
    ([txt("The prior query missed the diff.")],
     "the prior query missed (third person)"),
    ([txt("The previous attempt missed the root cause.")],
     "the previous attempt missed (third person)"),
    ([txt("The prior search missed note 14169.")],
     "the prior search missed (third person)"),
    ([txt("The reviewer missed the comment.")],
     "reviewer missed (someone else's gap)"),
    ([txt("The reviewer missed it because of the rebase.")],
     "reviewer missed it because (third person)"),
    ([txt("The author missed it because it was unanchored.")],
     "author missed it because (third person)"),
    ([txt("The user's search missed the target.")],
     "user's search missed (someone else)"),
    ([txt("You are right that the reviewer missed that.")],
     "you are right that third party missed"),
    ([txt("You are right, the author missed this requirement in the PR.")],
     "you are right third party missed in PR"),
    ([txt("You are right that this function is recursive.")],
     "you are right without missed/mistake"),
    ([txt("I missed out on the update.")],
     "missed out (idiom, not an error admission)"),
    ([txt("The AI missed the diff.")],
     "The AI missed (third-person boundary check)"),
    ([txt("The API filtered results by date rather than author.")],
     "third-party filtered ... rather than (API ends in i)"),
    ([txt("The audit filtered results rather than users.")],
     "audit filtered ... rather than (word ending in it)"),
    ([txt("The commit filtered lines rather than files.")],
     "commit filtered ... rather than (word ending in it)"),
    ([txt("The toolkit filtered stdout rather than stderr.")],
     "toolkit filtered ... rather than (word ending in it)"),
    ([txt("The dummy query missed edge cases.")],
     "dummy query missed (word ending in my)"),
    *ANCHOR_1898,
    *IRREALIS_2997,
    ([txt("The sour query missed the target.")],
     "sour query missed (word ending in our)"),
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
    # Review finding on #1968. `/ums` is how this corpus spells the
    # invocation, so the first path guard -- which rejected any preceding
    # `/` -- silently dropped it. A path and an invocation are separated by
    # what sits BEFORE the slash, not by the slash itself.
    ([ADMIT, tool("Task", {"prompt": "Run /ums to record this"})],
     "the slash-command spelling `/ums` still discharges"),
    ([ADMIT, tool("Task", {"prompt": "/memorize this correction"})],
     "`/memorize` at the start of a prompt still discharges"),
    ([ADMIT, tool("Bash", {"command": "echo /record-learnings"})],
     "`/record-learnings` still discharges"),
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
    # The other side of the same slash: a path ending exactly in the action
    # word, with nothing after it for `_NOT_PATH_END` to catch. Only the
    # lookbehind rejects these, which is why it cannot simply drop `/`.
    ([ADMIT, tool("Bash", {"command": "ls skills/ums"})],
     "a path ending in `ums` does not discharge"),
    ([ADMIT, tool("Bash", {"command": "./ums-helper --check"})],
     "a relative path `./ums-helper` does not discharge"),
    ([ADMIT, tool("Bash", {"command": "ls ~/.claude/skills/ums"})],
     "an absolute path ending in `ums` does not discharge"),
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
            [sys.executable, HOOK],
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
            subprocess.run([sys.executable, HOOK], input=payload, capture_output=True,
                           text=True, env=env).stdout.strip()
            for _ in range(2)
        ]
        seq.append(("REMIND" if out[0] else "silent", "REMIND",
                    "same transcript, first prompt"))
        seq.append(("REMIND" if out[1] else "silent", "silent",
                    "same transcript again -- fires once per admission"))

        # ai-config#2997. The transcript GROWS, and the grown turn repeats the
        # same phrase -- which is what explaining a misfire looks like, since
        # the explanation has to name the phrase in prose. With the record
        # index in the sentinel key that is a new key and the reminder
        # re-fires, so this is the case that pins the index out of the key.
        with open(same_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(user("was that a false positive?")) + "\n")
            fh.write(json.dumps(txt(
                "It was: the hook matched on I was wrong, which sat inside a "
                "sentence describing the match rather than making it.")) + "\n")
        out_again = subprocess.run(
            [sys.executable, HOOK], input=payload, capture_output=True,
            text=True, env=env).stdout.strip()
        seq.append(("REMIND" if out_again else "silent", "silent",
                    "same phrase at a LATER index -- explaining a misfire "
                    "does not re-fire it"))

        # The control that keeps the case above from passing vacuously: the
        # sentinel is per PHRASE, not a blanket per-session mute, so a
        # different admission later in the same transcript still fires.
        with open(same_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(txt("I miscounted the open PRs.")) + "\n")
        out_other = subprocess.run(
            [sys.executable, HOOK], input=payload, capture_output=True,
            text=True, env=env).stdout.strip()
        seq.append(("REMIND" if out_other else "silent", "REMIND",
                    "a DIFFERENT admission in the same session still fires"))
    finally:
        os.unlink(same_path)
finally:
    shutil.rmtree(shared, ignore_errors=True)

for got, want, desc in seq:
    wrong += got != want
    print(f"  {got:<7} {desc}")

# Revert mutation (ai-config#1898): strip the two `\bmy` anchors from a copy of
# the hook and run the ANCHOR_1898 controls against it. Every control must
# REMIND under the mutant; one that stays silent under both patterns pins
# nothing, which is the inert-control failure #1889's review found.
print("\nrevert mutation (#1898 anchors removed -- each control must fire):")
B = chr(92)
with open(HOOK, encoding="utf-8") as fh:
    source = fh.read()
mutant = (source
          .replace(B + "bmy" + B + "s+(mistake|error)", "my" + B + "s+(mistake|error)")
          .replace(B + "bmy" + B + "s+(earlier", "my" + B + "s+(earlier"))
if mutant == source:
    sys.exit("FATAL: the #1898 anchors were not found in the hook, so the mutation is inert")
fd, mutant_path = tempfile.mkstemp(suffix=".py")
with os.fdopen(fd, "w", encoding="utf-8") as fh:
    fh.write(mutant)
real_hook = HOOK
try:
    HOOK = mutant_path
    mutation = [(run(recs), desc) for recs, desc in ANCHOR_1898]
finally:
    HOOK = real_hook
    os.unlink(mutant_path)
for got, desc in mutation:
    wrong += got != "REMIND"
    print(f"  {got:<7} {desc}")

# Revert mutation (ai-config#2997): disable the irrealis skip in a copy of the
# hook and run the IRREALIS_2997 controls against it. Every one must REMIND
# under the mutant, otherwise a control that is silent for some unrelated
# reason -- a phrase no alternative matches at all -- would pass without
# exercising the guard.
print("\nrevert mutation (#2997 irrealis guard disabled -- each control must fire):")
GUARD_LINE = "if self.lead.search(before):"
mutant_2997 = source.replace(GUARD_LINE, "if False and self.lead.search(before):")
if mutant_2997 == source:
    sys.exit(
        "FATAL: the #2997 irrealis skip was not found in the hook, so the "
        "mutation is inert"
    )
fd, mutant_path = tempfile.mkstemp(suffix=".py")
with os.fdopen(fd, "w", encoding="utf-8") as fh:
    fh.write(mutant_2997)
try:
    HOOK = mutant_path
    mutation_2997 = [(run(recs), desc) for recs, desc in IRREALIS_2997]
finally:
    HOOK = real_hook
    os.unlink(mutant_path)
for got, desc in mutation_2997:
    wrong += got != "REMIND"
    print(f"  {got:<7} {desc}")

total = len(REMIND) + len(SILENT) + len(seq) + len(mutation) + len(mutation_2997)
print(f"\n{total - wrong}/{total} correct" + ("" if wrong == 0 else f"  ({wrong} WRONG)"))
sys.exit(1 if wrong else 0)
