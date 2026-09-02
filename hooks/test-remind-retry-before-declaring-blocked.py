"""Test the remind-retry-before-declaring-blocked hook.

Builds a synthetic transcript per case and feeds the hook a UserPromptSubmit
payload pointing at it. The hook must print a reminder for an auto-mode
classifier denial with no later re-attempt, and print NOTHING for everything
else.

Three properties this suite is specifically written to pin:

  1. It must never exit non-zero and never emit a `block` decision. This hook
     may only ADD context; reporting a denial is right to send, and only the
     premature claim of permanence is the problem.
  2. A USER's own denial, a deterministic permission-rule denial, and a hook
     refusal must all stay silent. A user declining is a decision to respect,
     and a rule denial returns the same answer by construction -- nagging at
     either is what would get the guard switched off.
  3. The classifier's sentence appearing INSIDE ordinary tool output (a
     `grep`, a transcript read, a read of this very file) must stay silent.
     The bottom of this file mutates the anchor away and checks that those
     controls then fire, so each is known to discriminate rather than merely
     to pass.

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


def result(tid, text, kind=None, sidechain=False):
    rec = {
        "type": "user",
        "isSidechain": sidechain,
        "message": {"content": [
            {"type": "tool_result", "tool_use_id": tid, "content": text},
        ]},
    }
    if kind:
        rec["toolDenialKind"] = kind
    return rec


def txt(s):
    return {"type": "assistant", "isSidechain": False,
            "message": {"content": [{"type": "text", "text": s}]}}


REMIND = [
    ([use("t1"), result("t1", CLASSIFIER, "automode-blocked")],
     "classifier denial, nothing after it"),
    # The text path alone, with no `toolDenialKind` on the carrier record --
    # the harness layout this hook must still read if that field goes away.
    ([use("t1"), result("t1", CLASSIFIER)],
     "classifier denial recognised from its text alone"),
    # The field path alone. A future wording change to the sentence must not
    # silence the guard where the structured signal is present.
    ([use("t1"), result("t1", "Denied.", "automode-blocked")],
     "classifier denial recognised from toolDenialKind alone"),
    ([use("t1"), result("t1", CLASSIFIER, "automode-blocked"),
      use("t2", "git status"), result("t2", "clean")],
     "a DIFFERENT command afterwards is not a re-attempt"),
    ([use("t1"), result("t1", CLASSIFIER, "automode-blocked"),
      use("t2"), result("t2", CLASSIFIER, "automode-blocked")],
     "denied, retried, denied again, no third attempt"),
    ([use("t1", "git push origin a"),
      result("t1", CLASSIFIER, "automode-blocked"),
      use("t2", "git push origin b"),
      result("t2", CLASSIFIER, "automode-blocked")],
     "two distinct denied commands, neither re-attempted"),
    # A retry of the FIRST command does not discharge a later denial of the
    # second: the reminder is per command, not per session.
    ([use("t1", "git push origin a"),
      result("t1", CLASSIFIER, "automode-blocked"),
      use("t2", "git push origin b"),
      result("t2", CLASSIFIER, "automode-blocked"),
      use("t3", "git push origin a"), result("t3", "ok")],
     "the other command retried, this one still not"),
    ([use_raw("t1", "Write", {"file_path": "/repo/x.py", "content": "a"}),
      result("t1", CLASSIFIER, "automode-blocked")],
     "a non-Bash tool denial fires too"),
    ([use("t1"), result("t1", CLASSIFIER, "automode-blocked"),
      txt("The push path is closed; handing this to you.")],
     "prose after the denial does not discharge it"),
]

# The controls the START anchor exists for. The classifier's own sentence
# appears constantly as ORDINARY tool output in this corpus -- a transcript
# scan, a grep of the hooks directory, a read of this file. Each must stay
# silent, and the mutation block at the bottom checks each then FIRES once the
# anchor is removed.
QUOTED_MARKER = [
    ([use("t1", "grep -rn 'auto mode classifier' hooks/"),
      result("t1", "hooks/remind-retry-before-declaring-blocked.py:12: "
             + CLASSIFIER)],
     "grep output quoting the denial sentence does not fire"),
    ([use("t1", "cat hooks/remind-retry-before-declaring-blocked.py"),
      result("t1", "#!/usr/bin/env python3\n"
             "CLASSIFIER_MARKER = (\n    \"" + CLASSIFIER + "\"\n)")],
     "reading this hook's own source does not fire"),
]

SILENT = [
    ([], "empty transcript"),
    ([txt("All good, nothing denied.")], "no tool calls at all"),
    ([use("t1"), result("t1", "ok")], "a successful command"),
    ([use("t1"), result("t1", CLASSIFIER, "automode-blocked"), use("t2")],
     "denied, then the identical command re-attempted"),
    ([use("t1"), result("t1", CLASSIFIER, "automode-blocked"),
      use("t2", "ALLOW_UNREVIEWED_PUSH=1   git push -u origin\n  HEAD")],
     "a re-attempt differing only in whitespace still counts as a retry"),
    ([use("t1"), result("t1", CLASSIFIER, "automode-blocked"),
      use("t2"), result("t2", CLASSIFIER, "automode-blocked"), use("t3")],
     "denied twice, then re-attempted a third time"),
    ([use("t1"), result("t1", USER_REJECTED, "user-rejected")],
     "the USER's own denial is a decision to respect, not a sample"),
    ([use("t1"), result("t1", PERMISSION_RULE, "permission-rule")],
     "a deterministic permission-rule denial returns the same answer"),
    ([use("t1"), result("t1", HOOK_REFUSAL, "permission-rule")],
     "a PreToolUse hook refusal is not the classifier"),
    ([use("t1"), result("t1", AUTOMODE_UNAVAILABLE, "automode-unavailable")],
     "auto mode unavailable is an outage, deliberately out of scope"),
    ([use("t1", sidechain=True),
      result("t1", CLASSIFIER, "automode-blocked", sidechain=True)],
     "a SUBAGENT's denial is not this session's to retry"),
    ([result("t9", CLASSIFIER, "automode-blocked")],
     "a denial whose tool_use is not in the transcript"),
    ([use_raw("t1", "Bash", {"command": ""}),
      result("t1", CLASSIFIER, "automode-blocked")],
     "an empty command has no identity to key on"),
    ([{"type": "assistant", "message": {"content": "not a list"}},
      use("t1"), result("t1", CLASSIFIER, "automode-blocked"), use("t2")],
     "a string-content record is skipped, and the retry still discharges"),
    *QUOTED_MARKER,
]


def write_transcript(recs):
    fd, tpath = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")
    return tpath


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
        fh.write(json.dumps(
            result("t1", CLASSIFIER, "automode-blocked"))[:40] + "\n")
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
finally:
    shutil.rmtree(sdir, ignore_errors=True)

for got, desc in malformed:
    wrong += got != "silent"
    print(f"  {got:<7} {desc}")

# The sentinel fires once per DISTINCT denied command, and must not reach
# across sessions. Two distinct transcripts carrying the same denial are
# different sessions, so both must remind; only a repeat against the SAME
# transcript is a repeat. Sharing one sentinel dir is what makes the
# distinction observable.
print("\nsentinel scope (one shared sentinel dir):")
seq = []
shared = tempfile.mkdtemp()
try:
    denied_a = [use("t1"), result("t1", CLASSIFIER, "automode-blocked")]
    seq.append((run(denied_a, shared), "REMIND", "session A, first prompt"))
    seq.append((run(denied_a, shared), "REMIND", "session B, same denial"))

    same = write_transcript(denied_a)
    try:
        seq.append(("REMIND" if invoke(same, shared).strip() else "silent",
                    "REMIND", "same transcript, first prompt"))
        seq.append(("REMIND" if invoke(same, shared).strip() else "silent",
                    "silent", "same transcript again -- fires once"))

        # A SECOND, distinct denied command in the same session is its own
        # reminder. Keying the sentinel on the session alone would swallow it.
        with open(same, "a") as fh:
            fh.write(json.dumps(use("t2", "git push origin other")) + "\n")
            fh.write(json.dumps(
                result("t2", CLASSIFIER, "automode-blocked")) + "\n")
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

# The message must adapt to the denial count, because mistake-patterns
# Pattern 43 forbids urging a third attempt. Asserting only that SOMETHING was
# printed cannot tell the two apart, and the second one is where a guard would
# contradict a rule this corpus already records.
print("\nmessage adapts to the denial count:")
wording = []
sdir = tempfile.mkdtemp()
try:
    one = write_transcript([use("t1"), result("t1", CLASSIFIER,
                                              "automode-blocked")])
    two = write_transcript([
        use("t1"), result("t1", CLASSIFIER, "automode-blocked"),
        use("t2"), result("t2", CLASSIFIER, "automode-blocked")])
    try:
        out_one = invoke(one, sdir)
        out_two = invoke(two, sdir)
    finally:
        os.unlink(one)
        os.unlink(two)
    wording.append(("Re-run the same command once" in out_one,
                    "one denial: advises a single retry"))
    wording.append(("denied once so far" in out_one,
                    "one denial: supplies the measured wording"))
    wording.append(("Re-run the same command once" not in out_two,
                    "two denials: does NOT advise another retry"))
    wording.append(("stop probing" in out_two,
                    "two denials: cites the stop-probing rule instead"))
    wording.append(("denied 2 times so far" in out_two,
                    "two denials: reports the count, not 'cannot'"))
    wording.append((PUSH in out_one,
                    "the denied command itself is named"))
finally:
    shutil.rmtree(sdir, ignore_errors=True)

for ok, desc in wording:
    wrong += not ok
    print(f"  {'ok' if ok else 'WRONG':<7} {desc}")

# Revert mutation: strip the START anchor so the marker is merely searched
# for. Every QUOTED_MARKER control must then FIRE. A control that stays silent
# under both spellings pins nothing, which is the inert-control failure this
# corpus's own hook suites were reviewed for.
print("\nrevert mutation (START anchor removed -- each control must fire):")
with open(HOOK, encoding="utf-8") as fh:
    source = fh.read()
anchored = "return content.lstrip().startswith(CLASSIFIER_MARKER)"
mutant = source.replace(anchored, "return CLASSIFIER_MARKER in content")
if mutant == source:
    sys.exit(
        "FATAL: the START anchor was not found in the hook, so the mutation "
        "is inert and the QUOTED_MARKER controls pin nothing"
    )
fd, mutant_path = tempfile.mkstemp(suffix=".py")
with os.fdopen(fd, "w", encoding="utf-8") as fh:
    fh.write(mutant)
real_hook = HOOK
try:
    HOOK = mutant_path
    mutation = [(run(recs), desc) for recs, desc in QUOTED_MARKER]
finally:
    HOOK = real_hook
    os.unlink(mutant_path)
for got, desc in mutation:
    wrong += got != "REMIND"
    print(f"  {got:<7} {desc}")

total = (len(REMIND) + len(SILENT) + len(malformed) + len(seq)
         + len(wording) + len(mutation))
print(f"\n{total - wrong}/{total} correct" + ("" if wrong == 0 else f"  ({wrong} WRONG)"))
sys.exit(1 if wrong else 0)
