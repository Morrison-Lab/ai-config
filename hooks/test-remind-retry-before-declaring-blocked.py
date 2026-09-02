"""Test the remind-retry-before-declaring-blocked hook.

Builds a synthetic transcript per case and feeds the hook a UserPromptSubmit
payload pointing at it. The hook must print a reminder for an auto-mode
classifier denial with no later re-attempt, and print NOTHING for everything
else.

Four properties this suite is specifically written to pin:

  1. It must never exit non-zero and never emit a decision-shaped payload.
     This hook may only ADD context; reporting a denial is right to send, and
     only the premature claim of permanence is the problem.
  2. A USER's own denial, a deterministic permission-rule denial, and a hook
     refusal must all stay silent. A user declining is a decision to respect,
     and a rule denial returns the same answer by construction -- nagging at
     either is what would get the guard switched off.
  3. The classifier's sentence appearing in ordinary tool output must stay
     silent, on both of the two guards that hold it out: the START anchor and
     the `is_error` requirement. Each guard has its own control group, and the
     mutation block at the bottom removes one guard at a time and checks that
     that group then FIRES -- so neither group can be an inert control that
     passes under a broken hook too.
  4. The message must match the denial count, and the count must reset on a
     successful run. Asserting only that SOMETHING printed cannot tell those
     apart, and both are places where the wrong branch would contradict the
     evidence the hook is built on.

Run:  python3 hooks/test-remind-retry-before-declaring-blocked.py \
          hooks/remind-retry-before-declaring-blocked.py
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

# The four denial texts, transcribed from real transcripts under
# ~/.claude/projects (2026-09-02). Only the first is ours.
CLASSIFIER = (
    "Permission for this action was denied by the Claude Code auto mode "
    "classifier. Reason: Blocked by classifier. If you have other tasks that "
    "don't depend on this action, continue working on those."
)
USER_REJECTED = (
    "The user doesn't want to proceed with this tool use. The tool use was "
    "rejected (eg. if it was a file edit, the new_string was NOT written to "
    "the file). STOP what you are doing and wait for the user to tell you "
    "how to proceed."
)
PERMISSION_RULE = (
    "Permission to use Bash with command ALLOW_UNREVIEWED_PUSH=1 git push "
    "-u origin HEAD has been denied."
)
HOOK_REFUSAL = (
    "git push blocked by the pre-push self-review policy: No "
    "`adversarial-reviewer` subagent was dispatched in this session."
)
AUTOMODE_UNAVAILABLE = (
    "claude-sonnet-5[1m] is temporarily unavailable, so auto mode cannot "
    "decide whether to allow this action."
)

PUSH = "ALLOW_UNREVIEWED_PUSH=1 git push -u origin HEAD"


def use(tid, command=PUSH, name="Bash", sidechain=False):
    return {
        "type": "assistant",
        "isSidechain": sidechain,
        "message": {"content": [
            {"type": "tool_use", "id": tid, "name": name,
             "input": {"command": command}},
        ]},
    }


def use_raw(tid, name, inp, sidechain=False):
    return {
        "type": "assistant",
        "isSidechain": sidechain,
        "message": {"content": [
            {"type": "tool_use", "id": tid, "name": name, "input": inp},
        ]},
    }


def result(tid, text, kind=None, sidechain=False, is_error=False):
    """One tool result.

    `is_error` and `kind` default to the SUCCESSFUL shape, so a case has to
    say explicitly that it is modelling a denial. Every real classifier denial
    measured on 2026-09-02 carried both.
    """
    rec = {
        "type": "user",
        "isSidechain": sidechain,
        "message": {"content": [
            {"type": "tool_result", "tool_use_id": tid, "content": text,
             "is_error": is_error},
        ]},
    }
    if kind:
        rec["toolDenialKind"] = kind
    return rec


def denial(tid, kind="automode-blocked", sidechain=False):
    """The real shape: classifier text, `is_error`, and the denial kind."""
    return result(tid, CLASSIFIER, kind, sidechain, is_error=True)


def txt(s):
    return {"type": "assistant", "isSidechain": False,
            "message": {"content": [{"type": "text", "text": s}]}}


REMIND = [
    ([use("t1"), denial("t1")], "classifier denial, nothing after it"),
    # The text path alone, with no `toolDenialKind` on the carrier record --
    # the harness layout this hook must still read if that field goes away.
    ([use("t1"), result("t1", CLASSIFIER, is_error=True)],
     "classifier denial recognised from its text and is_error alone"),
    # The field path alone. A future wording change to the sentence must not
    # silence the guard where the structured signal is present.
    ([use("t1"), result("t1", "Denied.", "automode-blocked")],
     "classifier denial recognised from toolDenialKind alone"),
    ([use("t1"), denial("t1"), use("t2", "git status"), result("t2", "clean")],
     "a DIFFERENT command afterwards is not a re-attempt"),
    ([use("t1"), denial("t1"), use("t2"), denial("t2")],
     "denied, retried, denied again, no third attempt"),
    ([use("t1", "git push origin a"), denial("t1"),
      use("t2", "git push origin b"), denial("t2")],
     "two distinct denied commands, neither re-attempted"),
    # A retry of the FIRST command does not discharge a later denial of the
    # second: the reminder is per command, not per session.
    ([use("t1", "git push origin a"), denial("t1"),
      use("t2", "git push origin b"), denial("t2"),
      use("t3", "git push origin a"), result("t3", "ok")],
     "the other command retried, this one still not"),
    ([use_raw("t1", "Write", {"file_path": "/repo/x.py", "content": "a"}),
      denial("t1")],
     "a non-Bash tool denial fires too"),
    ([use("t1"), denial("t1"),
      txt("The push path is closed; handing this to you.")],
     "prose after the denial does not discharge it"),
    # A well-formed JSON line that is not an object has no `.get`. It must
    # cost that ONE line, not the whole scan: the enclosing except would
    # swallow the error and silence the hook for the rest of the session.
    ([use("t1"), denial("t1"), None],
     "a null record does not silence the rest of the transcript"),
    ([use("t1"), denial("t1"), []],
     "a list record does not silence the rest of the transcript"),
    ([5, use("t1"), denial("t1")],
     "a bare number record before the denial is skipped"),
    # The stretch resets on an allowed run, so this is a FIRST denial of the
    # current stretch. The wording block below pins that it advises a retry.
    ([use("t1"), denial("t1"), use("t2"), result("t2", "ok"),
      use("t3"), denial("t3")],
     "denied, allowed to run, denied again"),
]

# Control group A, for the START anchor. The classifier's sentence appears
# constantly as ordinary tool output in this corpus -- a grep of the hooks
# directory, a failing test run that echoes it. These carry `is_error` (the
# command really did fail) but do not START with the sentence.
ANCHOR_CONTROLS = [
    ([use("t1", "grep -rn 'auto mode classifier' hooks/"),
      result("t1", "hooks/remind-retry-before-declaring-blocked.py:12: "
             + CLASSIFIER, is_error=True)],
     "a failing grep whose output quotes the sentence"),
    ([use("t1", "python3 hooks/test-remind-retry-before-declaring-blocked.py"),
      result("t1", "FAIL: expected silence, got:\n" + CLASSIFIER,
             is_error=True)],
     "this suite's own failure output quoting the sentence"),
]

# Control group B, for the `is_error` requirement. A SUCCESSFUL read of a
# stored denial -- a jq of a saved transcript, a head of a log -- starts with
# the sentence and is not a denial of the read.
IS_ERROR_CONTROLS = [
    ([use("t1", "jq -r '.message.content[0].content' session.jsonl | head -1"),
      result("t1", CLASSIFIER)],
     "a successful jq of a stored denial"),
    ([use("t1", "head -1 /tmp/denial.txt"), result("t1", CLASSIFIER)],
     "a successful head of a saved denial"),
]

SILENT = [
    ([], "empty transcript"),
    ([txt("All good, nothing denied.")], "no tool calls at all"),
    ([use("t1"), result("t1", "ok")], "a successful command"),
    ([use("t1"), denial("t1"), use("t2")],
     "denied, then the identical command re-attempted"),
    ([use("t1"), denial("t1"),
      use("t2", "ALLOW_UNREVIEWED_PUSH=1   git push -u origin\n  HEAD")],
     "a re-attempt differing only in whitespace still counts as a retry"),
    ([use("t1"), denial("t1"), use("t2"), denial("t2"), use("t3")],
     "denied twice, then re-attempted a third time"),
    ([use("t1"), result("t1", USER_REJECTED, "user-rejected", is_error=True)],
     "the USER's own denial is a decision to respect, not a sample"),
    ([use("t1"),
      result("t1", PERMISSION_RULE, "permission-rule", is_error=True)],
     "a deterministic permission-rule denial returns the same answer"),
    ([use("t1"), result("t1", HOOK_REFUSAL, "permission-rule", is_error=True)],
     "a PreToolUse hook refusal is not the classifier"),
    ([use("t1"), result("t1", AUTOMODE_UNAVAILABLE, "automode-unavailable",
                        is_error=True)],
     "auto mode unavailable is an outage, deliberately out of scope"),
    ([use("t1", sidechain=True), denial("t1", sidechain=True)],
     "a SUBAGENT's denial is not this session's to retry"),
    ([denial("t9")], "a denial whose tool_use is not in the transcript"),
    ([use_raw("t1", "Bash", {"command": ""}), denial("t1")],
     "an empty command has no identity to key on"),
    ([{"type": "assistant", "message": {"content": "not a list"}},
      use("t1"), denial("t1"), use("t2")],
     "a string-content record is skipped, and the retry still discharges"),
    # A user's rejection sits BETWEEN two classifier denials. It must not
    # reset the stretch, because the message for a stretch of 1 recommends a
    # re-run -- which would answer a decision to respect by re-running the
    # command the user just declined. The wording block below pins the count.
    ([use("t1"), denial("t1"), use("t2"),
      result("t2", USER_REJECTED, "user-rejected", is_error=True),
      use("t3"), denial("t3"), use("t4")],
     "a user rejection between denials, then a real re-attempt"),
    *ANCHOR_CONTROLS,
    *IS_ERROR_CONTROLS,
]


def write_transcript(recs):
    fd, tpath = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")
    return tpath


def append_records(tpath, recs):
    with open(tpath, "a") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")


def invoke(tpath, sentinel_dir):
    p = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"transcript_path": tpath}),
        capture_output=True, text=True,
        env=dict(os.environ, TMPDIR=sentinel_dir),
    )
    if p.returncode != 0:
        sys.exit(f"FATAL: hook exited {p.returncode}\n{p.stderr.strip()}")
    # Any JSON payload at all is a failure here: a UserPromptSubmit reminder
    # writes plain prose to stdout, and every shape that could suppress or
    # alter a message is expressed as JSON. Deliberately NOT a bare-word
    # search for "block" -- this hook echoes the denied COMMAND back, and a
    # command may legitimately name a file whose own name carries that word,
    # including this hook's.
    lowered = p.stdout.lower()
    if (lowered.lstrip().startswith("{")
            or "\"decision\"" in lowered
            or "\"permissiondecision\"" in lowered):
        sys.exit(
            "FATAL: hook emitted a decision-shaped payload. This hook must "
            f"only ever add context, never suppress a message.\n{p.stdout}"
        )
    return p.stdout


def run(recs, sentinel_dir=None):
    """Run the hook against a synthetic transcript.

    `sentinel_dir` shares one sentinel directory across calls, so a caller can
    exercise the dedup key itself; the default gives each case a fresh one.
    """
    tpath = write_transcript(recs)
    own_dir = sentinel_dir is None
    if own_dir:
        sentinel_dir = tempfile.mkdtemp()
    try:
        out = invoke(tpath, sentinel_dir)
    finally:
        os.unlink(tpath)
        if own_dir:
            shutil.rmtree(sentinel_dir, ignore_errors=True)
    return "REMIND" if out.strip() else "silent"


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

# Malformed input, on the three surfaces that can carry it. Each must fail
# OPEN and SILENT rather than raising: a guard that dies on a partial write
# would take the session's next prompt with it.
print("\nmalformed input (fail open and silent):")
malformed = []
sdir = tempfile.mkdtemp()
try:
    fd, bad = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        fh.write("not json at all\n")
        fh.write("{\"type\": \"assistant\", truncated...\n")
        fh.write(json.dumps(use("t1")) + "\n")
        fh.write(json.dumps(denial("t1"))[:40] + "\n")
    try:
        malformed.append((
            "REMIND" if invoke(bad, sdir).strip() else "silent",
            "unparseable lines are skipped, not fatal"))
    finally:
        os.unlink(bad)

    missing = os.path.join(sdir, "does-not-exist.jsonl")
    malformed.append((
        "REMIND" if invoke(missing, sdir).strip() else "silent",
        "a transcript path that does not exist"))

    p = subprocess.run(
        [sys.executable, HOOK], input="{not json",
        capture_output=True, text=True, env=dict(os.environ, TMPDIR=sdir))
    malformed.append((
        "REMIND" if (p.stdout.strip() or p.returncode) else "silent",
        "an unparseable stdin payload"))

    # Valid JSON that is not an object. Each of these parses cleanly and has
    # no `.get`, so a hook that only guards the parse exits 1 with a
    # traceback -- on the one code path that is supposed to be silent.
    for raw in ("null", "[]", '"x"', "5"):
        p = subprocess.run(
            [sys.executable, HOOK], input=raw,
            capture_output=True, text=True, env=dict(os.environ, TMPDIR=sdir))
        malformed.append((
            "REMIND" if (p.stdout.strip() or p.returncode) else "silent",
            f"a well-formed but non-object payload: {raw}"))
finally:
    shutil.rmtree(sdir, ignore_errors=True)

for got, desc in malformed:
    wrong += got != "silent"
    print(f"  {got:<7} {desc}")

# The sentinel fires once per distinct denied command PER COUNT, and must not
# reach across sessions. Every case here shares one sentinel directory, which
# is what makes the scoping observable: two transcripts carrying the same
# denial are two sessions and both must remind, while a repeat against the
# same transcript is a repeat.
print("\nsentinel scope (one shared sentinel dir):")
seq = []
shared = tempfile.mkdtemp()
try:
    denied_a = [use("t1"), denial("t1")]
    seq.append((run(denied_a, shared), "REMIND", "session A, first prompt"))
    seq.append((run(denied_a, shared), "REMIND", "session B, same denial"))

    same = write_transcript(denied_a)
    try:
        seq.append(("REMIND" if invoke(same, shared).strip() else "silent",
                    "REMIND", "same transcript, first prompt"))
        seq.append(("REMIND" if invoke(same, shared).strip() else "silent",
                    "silent", "same transcript again -- fires once"))

        # The session did what the reminder said: re-ran the command. It was
        # denied again. That is the moment the advice CHANGES, and the moment
        # the session most needs to hear it -- so the count-2 reminder must
        # not be swallowed by the count-1 sentinel.
        append_records(same, [use("t2"), denial("t2")])
        seq.append(("REMIND" if invoke(same, shared).strip() else "silent",
                    "REMIND", "the retry was denied too -- count 2 fires"))
        seq.append(("REMIND" if invoke(same, shared).strip() else "silent",
                    "silent", "and then goes quiet at that count"))

        # The command then RAN, and was denied again. The stretch is back
        # to 1, so a sentinel keyed on the stretch would collide with the
        # count-1 reminder already written above and swallow this one -- the
        # single case the reset logic exists to produce.
        append_records(same, [use("t3"), result("t3", "ok"),
                              use("t4"), denial("t4")])
        seq.append(("REMIND" if invoke(same, shared).strip() else "silent",
                    "REMIND", "denied again after a success -- still fires"))
        seq.append(("REMIND" if invoke(same, shared).strip() else "silent",
                    "silent", "and then goes quiet at that denial"))

        # A SECOND, distinct denied command in the same session is its own
        # reminder. Keying the sentinel on the session alone would swallow it.
        append_records(same, [use("t5", "git push origin other"), denial("t5")])
        seq.append(("REMIND" if invoke(same, shared).strip() else "silent",
                    "REMIND", "a second distinct denied command fires"))
        seq.append(("REMIND" if invoke(same, shared).strip() else "silent",
                    "silent", "and then goes quiet too"))
    finally:
        os.unlink(same)
finally:
    shutil.rmtree(shared, ignore_errors=True)

for got, want, desc in seq:
    wrong += got != want
    print(f"  {got:<7} {desc}")

# Which command gets named, and what the message says about it. A case
# asserting only that SOMETHING fired cannot see either, and both are places
# where the wrong branch contradicts the evidence the hook rests on.
print("\nmessage content:")
content = []
sdir = tempfile.mkdtemp()
try:
    one = write_transcript([use("t1"), denial("t1")])
    two = write_transcript([use("t1"), denial("t1"), use("t2"), denial("t2")])
    # Two commands denied in the SAME turn, neither retried. The newest is
    # reported first, and the older one must still surface on a later prompt
    # rather than being lost behind the newer one's sentinel.
    both = write_transcript([
        use("t1", "git push origin alpha"), denial("t1"),
        use("t2", "git push origin beta"), denial("t2")])
    # Pattern 43's measured shape: one goal in three phrasings, each denied
    # once. Every variant carries a stretch and total of 1, so a warning
    # attached to either count fires zero times here -- which is the shape
    # that produced the rule.
    variants = write_transcript([
        use("t1", "ALLOW_UNREVIEWED_PUSH=1 git push -u origin HEAD"),
        denial("t1"),
        use("t2", "export ALLOW_UNREVIEWED_PUSH=1 && git push -u origin HEAD"),
        denial("t2"),
        use("t3", "env ALLOW_UNREVIEWED_PUSH=1 git push -u origin HEAD"),
        denial("t3")])
    # Denied, ran successfully, denied again: one denial in the current
    # stretch, so the retry advice is right and "2 times" would be wrong.
    reset = write_transcript([
        use("t1"), denial("t1"), use("t2"), result("t2", "ok"),
        use("t3"), denial("t3")])
    # Three things that are NOT a successful run, each sitting between two
    # classifier denials. Counting any of them as a reset would understate the
    # count the message quotes, and would re-arm the retry advice -- after the
    # user's own refusal, in the third case.
    noreset = [
        (write_transcript([
            use("t1"), denial("t1"),
            use("t2"), result("t2", PERMISSION_RULE, "permission-rule",
                              is_error=True),
            use("t3"), denial("t3")]),
         "a permission-rule denial does not reset the stretch"),
        (write_transcript([
            use("t1"), denial("t1"),
            use("t2"), result("t2", USER_REJECTED, "user-rejected",
                              is_error=True),
            use("t3"), denial("t3")]),
         "the user's own rejection does not reset the stretch"),
        # The same rejection with the `toolDenialKind` field absent. That
        # field is present on all 6 measured records, so this pins the second
        # signal -- the one case where trusting the field alone would answer a
        # decision to respect with "re-run it once".
        (write_transcript([
            use("t1"), denial("t1"),
            use("t2"), result("t2", USER_REJECTED, is_error=True),
            use("t3"), denial("t3")]),
         "a user rejection with no toolDenialKind still does not reset it"),
    ]
    # A run the classifier ALLOWED resets the stretch even though the command
    # then failed. `is_error` is not a reliable failure signal on a real tool
    # result, so the hook does not try to read one -- and the stretch answers
    # "how many refusals in a row", which an allowed run ends either way.
    failed_run = write_transcript([
        use("t1"), denial("t1"),
        use("t2"), result("t2", "fatal: no upstream configured", is_error=True),
        use("t3"), denial("t3")])
    try:
        out_one = invoke(one, sdir)
        out_two = invoke(two, sdir)
        out_both = [invoke(both, sdir), invoke(both, sdir)]
        out_reset = invoke(reset, sdir)
        out_noreset = [(invoke(t, sdir), d) for t, d in noreset]
        out_failed = invoke(failed_run, sdir)
        out_variants = invoke(variants, sdir)
    finally:
        for p in (one, two, both, reset, failed_run, variants,
                  *[t for t, _ in noreset]):
            os.unlink(p)
    content += [
        ("Re-run the same command once" in out_one,
         "one denial: advises a single retry"),
        ("denied once so far" in out_one,
         "one denial: supplies the measured wording"),
        (PUSH in out_one, "one denial: names the denied command"),
        # #2994's success WAS the third attempt after two denials, so a
        # second-denial message whose only imperative was "hand the user the
        # decision" would stop the session one attempt short of the thing
        # that worked -- the incident, reproduced by following the hook.
        ("denied 2 times so far" in out_two,
         "two denials: reports the count, not 'cannot'"),
        # Oldest first. The original command is the one the evidence is
        # about; the newest is whatever the session most recently reworded it
        # into. Reporting newest first replays #2994 by naming the settings
        # edit before the push it was a workaround for.
        ("git push origin alpha" in out_both[0],
         "concurrent denials: the oldest is reported first"),
        ("git push origin beta" in out_both[1],
         "concurrent denials: the newer one is not lost behind it"),
        # The stretch drives the advice and the TOTAL is what gets
        # reported. Quoting the stretch under "so far" wording would tell the
        # session to report one denial where the transcript records two.
        ("denied a tool call once in a row" in out_reset,
         "an allowed run resets the stretch"),
        ("2 times in this session" in out_reset,
         "the session total is reported alongside it"),
        ("denied 2 times so far" in out_reset,
         "the wording to report quotes the total, not the stretch"),
        ("Re-run the same command once" in out_reset,
         "an allowed run restores the retry advice"),
        ("denied a tool call once in a row" in out_failed,
         "a run the classifier allowed resets it even if it failed"),
        ("denied 3 distinct commands" in out_variants,
         "three phrasings of one goal reach the variation warning"),
        ("stop generating new shapes" in out_variants,
         "the variation warning says what to stop doing"),
        ("if they are rephrasings of one goal" in out_variants.lower(),
         "and hedges, because it cannot tell variants from unrelated work"),
        ("stop generating new shapes" not in out_one,
         "a single denied command gets no variation warning"),
        # Pattern 43's Do bullet and #2994's measurement pull opposite ways
        # here. A guard is the wrong place to settle that, so the message
        # states both and hands the decision over -- which is what the Do
        # bullet asks for.
        ("Pattern 43 says to stop probing" in out_two,
         "two denials: states Pattern 43's rule"),
        ("succeeding on its third attempt" in out_two,
         "two denials: states #2994's measurement beside it"),
        ("let them choose" in out_two,
         "two denials: hands the decision to the user"),
    ]
    content += [("denied 2 times so far" in out, desc)
                for out, desc in out_noreset]
    content += [("Pattern 43 says to stop probing" in out,
                 desc.replace("does not reset the stretch",
                              "leaves the stretch at 2")
                     .replace("still does not reset it",
                              "still leaves the stretch at 2"))
                for out, desc in out_noreset]
finally:
    shutil.rmtree(sdir, ignore_errors=True)

for ok, desc in content:
    wrong += not ok
    print(f"  {'ok' if ok else 'WRONG':<7} {desc}")

# Revert mutations, one per guard on the text path. Each control group must
# FIRE once its own guard is removed; a group that stays silent under both
# spellings pins nothing, which is the inert-control failure this corpus's
# hook suites are reviewed for.
print("\nrevert mutations (each control group must fire without its guard):")
with open(HOOK, encoding="utf-8") as fh:
    source = fh.read()
MUTATIONS = [
    ("START anchor removed",
     "return content.lstrip().startswith(CLASSIFIER_MARKER)",
     "return CLASSIFIER_MARKER in content",
     ANCHOR_CONTROLS),
    ("is_error requirement removed",
     '    if not block.get("is_error"):\n        return False\n',
     "",
     IS_ERROR_CONTROLS),
]
mutation = []
real_hook = HOOK
for name, old, new, controls in MUTATIONS:
    if old not in source:
        sys.exit(
            f"FATAL: the {name} anchor was not found in the hook, so that "
            "mutation is inert and its control group pins nothing"
        )
    fd, mutant_path = tempfile.mkstemp(suffix=".py")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(source.replace(old, new, 1))
    try:
        HOOK = mutant_path
        mutation += [(run(recs), f"{name}: {desc}") for recs, desc in controls]
    finally:
        HOOK = real_hook
        os.unlink(mutant_path)
for got, desc in mutation:
    wrong += got != "REMIND"
    print(f"  {got:<7} {desc}")

total = (len(REMIND) + len(SILENT) + len(malformed) + len(seq)
         + len(content) + len(mutation))
print(f"\n{total - wrong}/{total} correct" + ("" if wrong == 0 else f"  ({wrong} WRONG)"))
sys.exit(1 if wrong else 0)
