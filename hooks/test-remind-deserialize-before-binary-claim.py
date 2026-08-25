"""Test the remind-deserialize-before-binary-claim hook.

Builds a synthetic transcript per case and feeds the hook a UserPromptSubmit
payload pointing at it. The hook must print a reminder for an escalation that
names a serialized artifact nobody deserialized, and print NOTHING otherwise.

Four properties this suite exists to pin:

  1. It must never exit non-zero and never emit a `block` decision. This hook
     may only ADD context. An escalation about a binary artifact is frequently
     right to send -- about its size, its path, whether it should be tracked --
     and a guard that suppresses those gets switched off.
  2. Case #1 is the verbatim incident (ucdavis/bcs#579), pasted in unaltered
     rather than tidied, per algorithmatize-checks' "Test the instrument
     against the incident that prompted it, verbatim".
  3. The discharge is PATH-SCOPED: deserializing file B must not discharge an
     escalation about file A. An over-broad discharge produces silence, which
     is indistinguishable from compliance.
  4. The discharge requires a tool_use that RAN. Prose asserting the check
     happened is the claim under suspicion, not evidence for it.

Run:  python3 hooks/test-remind-deserialize-before-binary-claim.py \
          hooks/remind-deserialize-before-binary-claim.py
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


# ---------------------------------------------------------------------------
# Case 1: the verbatim incident. The three paths are the .rds entries returned
# by `gh pr diff 579 --name-only` on ucdavis/bcs#579, read from the PR rather
# than recalled -- an earlier draft of this file invented
# `msm-validation-results.rds` for the third one.
# ---------------------------------------------------------------------------
NAME_ONLY = tool("Bash", {"command": "gh pr diff 579 --name-only"})

INCIDENT = txt(
    "===\n"
    "🛑 **BLOCKER**\n"
    "Three HPC validation artifacts changed in this PR:\n"
    "`inst/extdata/ett-validation-true-effects.rds`, "
    "`inst/extdata/ett-validation-accuracy-results.rds`, and "
    "`inst/extdata/msm-validation-accuracy-results.rds`.\n"
    "Regenerating the dependent artifacts is a ~1.5h serial run plus a "
    "500-task SLURM array. Your call: regenerate, or hold the change?\n"
    "==="
)

# ---------------------------------------------------------------------------
# Negative-case material
# ---------------------------------------------------------------------------
MENTION_ONLY = txt(
    "Rebuilt the pipeline. The output landed at "
    "`inst/extdata/ett-validation-true-effects.rds` as expected, and the "
    "run finished in four minutes."
)

ESCALATE_TEXT_FILE = txt(
    "🛑 **BLOCKER**\n"
    "`docs/analysis-notes.txt` conflicts with the rewrite on main. "
    "Your call: keep ours, or take theirs?"
)

GREP_ONLY = tool(
    "Bash",
    {"command": "grep -rn 'ett-validation-true-effects.rds' data-raw/ && "
                "echo inst/extdata/ett-validation-true-effects.rds"},
)

SCOPED_CHECK = tool(
    "Bash",
    {"command":
        "git show origin/main:inst/extdata/ett-validation-true-effects.rds "
        "> /tmp/old.rds && Rscript -e "
        "'identical(readRDS(\"/tmp/old.rds\"), "
        "readRDS(\"inst/extdata/ett-validation-true-effects.rds\"))'"},
)

# Deserializes a DIFFERENT artifact. Must not discharge the escalation above.
OTHER_FILE_CHECK = tool(
    "Bash",
    {"command":
        "Rscript -e 'identical(readRDS(\"/tmp/a.rds\"), "
        "readRDS(\"inst/extdata/msm-vs-truth-chunk-004.rds\"))'"},
)

# Same basename, different directory -- ordinary in a data repo. A basename
# test would let this discharge the escalation below, which is a SILENT
# discharge: the dangerous direction.
SAME_BASENAME_CHECK = tool(
    "Bash",
    {"command":
        "Rscript -e 'identical(readRDS(\"backup/model.parquet\"), "
        "readRDS(\"backup/model.parquet\"))'"},
)

ESCALATE_PARQUET = txt(
    "🛑 **BLOCKER** `results/model.parquet` changed. Your call: regenerate?"
)

# Ran from inside the artifact's own directory, so the path is written bare.
RELATIVE_CHECK = tool(
    "Bash",
    {"command": "cd inst/extdata && Rscript -e "
                "'identical(readRDS(\"/tmp/old.rds\"), "
                "readRDS(\"ett-validation-true-effects.rds\"))'"},
)

ESCALATE_ONE_FILE = txt(
    "🛑 **BLOCKER**\n"
    "`inst/extdata/ett-validation-true-effects.rds` changed. "
    "Your call: regenerate downstream, or hold?"
)

# The remedy this guard's own reminder prints, in the single chained form it
# prints it in. A guard whose prescribed fix does not satisfy its own discharge
# keeps firing at someone who did exactly what it asked, which trains them to
# ignore it. Split across three separate tool calls this does NOT discharge --
# the Rscript would name only the temp files, not the artifact -- which is why
# the reminder chains the commands rather than listing them.
RECOMMENDED_REMEDY = tool(
    "Bash",
    {"command":
        "git cat-file blob origin/main:"
        "inst/extdata/ett-validation-true-effects.rds > /tmp/old.bin && "
        "git cat-file blob HEAD:"
        "inst/extdata/ett-validation-true-effects.rds > /tmp/new.bin && "
        "Rscript -e 'all.equal(unclass(readRDS(\"/tmp/old.bin\")), "
        "unclass(readRDS(\"/tmp/new.bin\")), check.attributes = FALSE)'"},
)

# Absolute and home/dot-relative paths. Before the ARTIFACT_PATH fix these
# matched NOWHERE -- not in escalation text and not in a command blob -- so the
# guard was silently blind to every one of them. That is the shape an HPC
# escalation uses most (`/scratch/...`, `/work/...`), which is the context this
# guard exists for, and the failure direction was silence.
#
# Covered on BOTH sides, because they fail independently: the fire side (is the
# path seen in the escalation at all) and the discharge side (is it seen in the
# command that deserializes it).
ESCALATE_ABSOLUTE = txt(
    "🛑 **BLOCKER**\n"
    "`/scratch/user/run42/results.rds` changed after the SLURM job. "
    "Your call: regenerate downstream, or hold?"
)

ESCALATE_HOME = txt(
    "🛑 **BLOCKER** `~/out/model.parquet` changed. Your call: regenerate?"
)

ESCALATE_DOTREL = txt(
    "🛑 **BLOCKER** `./results.rds` differs from main. Please advise."
)

ABSOLUTE_CHECK = tool(
    "Bash",
    {"command":
        "git cat-file blob origin/main:/scratch/user/run42/results.rds "
        "> /tmp/old.bin && Rscript -e "
        "'all.equal(unclass(readRDS(\"/tmp/old.bin\")), "
        "unclass(readRDS(\"/scratch/user/run42/results.rds\")), "
        "check.attributes = FALSE)'"},
)

# Deserializes a DIFFERENT absolute path. Path-scoping must hold for absolute
# paths exactly as it does for relative ones.
OTHER_ABSOLUTE_CHECK = tool(
    "Bash",
    {"command": "Rscript -e 'readRDS(\"/scratch/user/run99/results.rds\")'"},
)

# Prose ASSERTING the check ran, with no tool_use behind it.
PROSE_CLAIM = txt(
    "I compared the two versions with "
    "identical(readRDS(old), readRDS('inst/extdata/ett-validation-true-effects.rds')) "
    "and they matched."
)

MENTION_AND_SIDECHAIN = txt(
    "🛑 **BLOCKER** `inst/extdata/ett-validation-true-effects.rds` needs a "
    "decision.",
    sidechain=True,
)

REMIND = [
    ([NAME_ONLY, INCIDENT],
     "INCIDENT verbatim: --name-only, then a BLOCKER naming three .rds files"),
    ([ESCALATE_ONE_FILE],
     "escalation naming one .rds, nothing deserialized at all"),
    ([ESCALATE_ONE_FILE, OTHER_FILE_CHECK],
     "PATH-SCOPED: deserializes a DIFFERENT .rds, so the claim stays owed"),
    ([ESCALATE_ONE_FILE, PROSE_CLAIM],
     "prose asserts the comparison ran, but no tool_use did"),
    ([txt("@the repository owner can you confirm `results/model.parquet` should be "
          "regenerated after this?")],
     "@-mention escalation naming a .parquet"),
    ([txt("Needs a decision: `data/cohort.sas7bdat` differs from main.")],
     "decision-seeking phrasing naming a .sas7bdat"),
    ([ESCALATE_PARQUET, SAME_BASENAME_CHECK],
     "SAME BASENAME, different directory: must not discharge"),
    ([ESCALATE_ABSOLUTE],
     "ABSOLUTE path in the escalation, nothing deserialized"),
    ([ESCALATE_HOME],
     "HOME-relative (~/) path in the escalation, nothing deserialized"),
    ([ESCALATE_DOTREL],
     "DOT-relative (./) path in the escalation, nothing deserialized"),
    ([ESCALATE_ABSOLUTE, OTHER_ABSOLUTE_CHECK],
     "PATH-SCOPED for absolute paths: a different /scratch path must not "
     "discharge"),
]

SILENT = [
    ([MENTION_ONLY],
     "mentions an .rds path with no escalation signal"),
    ([ESCALATE_TEXT_FILE],
     "escalation about a text file, no serialized artifact named"),
    ([GREP_ONLY],
     "a grep and an echo of the path, no assistant message at all"),
    ([ESCALATE_ONE_FILE, SCOPED_CHECK],
     "escalation discharged by a scoped readRDS of THAT path -- note the "
     "second side is the WORKING TREE, which is the documented boundary "
     "with remind-both-sides-from-git.py, pinned below"),
    ([SCOPED_CHECK, ESCALATE_ONE_FILE],
     "same, with the check running BEFORE the escalation"),
    ([ESCALATE_ONE_FILE, RELATIVE_CHECK],
     "check run from the artifact's own directory, path written bare"),
    ([ESCALATE_ONE_FILE, RECOMMENDED_REMEDY],
     "the remedy this guard's own reminder prints discharges it"),
    ([ESCALATE_ABSOLUTE, ABSOLUTE_CHECK],
     "ABSOLUTE path discharged by a two-sided check naming that same path"),
    ([MENTION_AND_SIDECHAIN],
     "a subagent's own escalation is not my outgoing message"),
    ([], "empty transcript"),
]


def run(records):
    """Run the hook against a one-off transcript in a private TMPDIR.

    A private TMPDIR per case keeps the once-per-escalation sentinel from
    leaking between cases (or between runs of this suite).
    """
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "transcript.jsonl")
        with open(path, "w") as fh:
            for r in records:
                fh.write(json.dumps(r) + "\n")
        proc = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True,
            env=dict(os.environ, TMPDIR=tmp, TEMP=tmp, TMP=tmp),
        )
        return proc
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


results = []

for records, desc in REMIND:
    p = run(records)
    got = "REMIND" if p.stdout.strip() else "silent"
    results.append((got, "REMIND", desc))
    if p.returncode != 0:
        results.append((f"exit{p.returncode}", "exit0", f"exit status: {desc}"))
    if "block" in p.stdout.lower() and "decision" in p.stdout.lower():
        results.append(("blocked", "no-block", f"never blocks: {desc}"))

for records, desc in SILENT:
    p = run(records)
    got = "REMIND" if p.stdout.strip() else "silent"
    results.append((got, "silent", desc))
    if p.returncode != 0:
        results.append((f"exit{p.returncode}", "exit0", f"exit status: {desc}"))

# Fires once per escalation: a second run against the SAME transcript, in the
# same TMPDIR, must stay quiet.
shared = tempfile.mkdtemp()
try:
    same = os.path.join(shared, "t.jsonl")
    with open(same, "w") as fh:
        for r in (NAME_ONLY, INCIDENT):
            fh.write(json.dumps(r) + "\n")
    env = dict(os.environ, TMPDIR=shared, TEMP=shared, TMP=shared)
    payload = json.dumps({"transcript_path": same})
    out = [
        subprocess.run([sys.executable, HOOK], input=payload, capture_output=True,
                       text=True, env=env).stdout.strip()
        for _ in range(2)
    ]
    results.append(("REMIND" if out[0] else "silent", "REMIND",
                    "same transcript, first prompt"))
    results.append(("REMIND" if out[1] else "silent", "silent",
                    "same transcript again -- fires once per escalation"))
finally:
    shutil.rmtree(shared, ignore_errors=True)

# The BOUNDARY, pinned rather than asserted.
#
# This guard is deliberately silent on a comparison whose second side came
# from the working tree (SCOPED_CHECK above), because the sibling guard
# `remind-both-sides-from-git.py` fires on exactly that shape. A docstring
# saying so is a claim; this makes it falsifiable, and turns the composition
# into something that breaks loudly if the sibling is removed or stops
# detecting the case.
#
# Both halves are checked, because either one alone proves nothing: silence
# here plus silence there would be a real gap wearing a boundary's clothes.
SIBLING = os.path.join(os.path.dirname(os.path.abspath(HOOK)),
                       "remind-both-sides-from-git.py")
if not os.path.isfile(SIBLING):
    sys.exit(
        f"FATAL: sibling guard not found at {SIBLING}. This suite asserts a "
        "boundary rather than a gap: the wrong-second-side case is delegated "
        "to that hook, so if it is gone the delegation is unbacked and this "
        "guard's silence on that case is a genuine hole."
    )

boundary = tempfile.mkdtemp()
sibling_tmp = tempfile.mkdtemp()
try:
    tp = os.path.join(boundary, "t.jsonl")
    with open(tp, "w") as fh:
        for r in (ESCALATE_ONE_FILE, SCOPED_CHECK):
            fh.write(json.dumps(r) + "\n")
    payload = json.dumps({"transcript_path": tp})
    mine = subprocess.run(
        [sys.executable, HOOK], input=payload, capture_output=True, text=True,
        env=dict(os.environ, TMPDIR=boundary, TEMP=boundary, TMP=boundary),
    )
    theirs = subprocess.run(
        [sys.executable, SIBLING], input=payload, capture_output=True, text=True,
        env=dict(os.environ, TMPDIR=sibling_tmp, TEMP=sibling_tmp, TMP=sibling_tmp),
    )
    results.append(("REMIND" if mine.stdout.strip() else "silent", "silent",
                    "BOUNDARY: this guard is silent on a working-tree "
                    "second side"))
    results.append(("REMIND" if theirs.stdout.strip() else "silent", "REMIND",
                    "BOUNDARY: the sibling guard FIRES on that same "
                    "transcript, so the case is delegated, not dropped"))
finally:
    shutil.rmtree(boundary, ignore_errors=True)
    shutil.rmtree(sibling_tmp, ignore_errors=True)

# A malformed transcript must fail open and silent, not crash.
bad = tempfile.mkdtemp()
try:
    p = os.path.join(bad, "t.jsonl")
    with open(p, "w") as fh:
        fh.write("{not json at all\n")
    proc = subprocess.run(
        [sys.executable, HOOK], input=json.dumps({"transcript_path": p}),
        capture_output=True, text=True, env=dict(os.environ, TMPDIR=bad, TEMP=bad, TMP=bad),
    )
    results.append(("REMIND" if proc.stdout.strip() else "silent", "silent",
                    "malformed transcript fails open and silent"))
    results.append((f"exit{proc.returncode}", "exit0",
                    "malformed transcript exit status"))
finally:
    shutil.rmtree(bad, ignore_errors=True)

wrong = 0
for got, want, desc in results:
    wrong += got != want
    flag = "" if got == want else f"   <-- expected {want}"
    print(f"  {got:<7} {desc}{flag}")

total = len(results)
print(f"\n{total - wrong}/{total} correct" + ("" if wrong == 0 else f"  ({wrong} WRONG)"))
sys.exit(1 if wrong else 0)
