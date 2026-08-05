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
# Case 1: the verbatim incident. Paths are the real ones from ucdavis/bcs#579.
# ---------------------------------------------------------------------------
NAME_ONLY = tool("Bash", {"command": "gh pr diff 579 --name-only"})

INCIDENT = txt(
    "===\n"
    "🛑 **BLOCKER**\n"
    "Three HPC validation artifacts changed in this PR:\n"
    "`inst/extdata/ett-validation-true-effects.rds`, "
    "`inst/extdata/ett-validation-accuracy-results.rds`, and "
    "`inst/extdata/msm-validation-results.rds`.\n"
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

ESCALATE_ONE_FILE = txt(
    "🛑 **BLOCKER**\n"
    "`inst/extdata/ett-validation-true-effects.rds` changed. "
    "Your call: regenerate downstream, or hold?"
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
    ([txt("@d-morrison can you confirm `results/model.parquet` should be "
          "regenerated after this?")],
     "@-mention escalation naming a .parquet"),
    ([txt("Needs a decision: `data/cohort.sas7bdat` differs from main.")],
     "decision-seeking phrasing naming a .sas7bdat"),
]

SILENT = [
    ([MENTION_ONLY],
     "mentions an .rds path with no escalation signal"),
    ([ESCALATE_TEXT_FILE],
     "escalation about a text file, no serialized artifact named"),
    ([GREP_ONLY],
     "a grep and an echo of the path, no assistant message at all"),
    ([ESCALATE_ONE_FILE, SCOPED_CHECK],
     "escalation discharged by a scoped readRDS of THAT path"),
    ([SCOPED_CHECK, ESCALATE_ONE_FILE],
     "same, with the check running BEFORE the escalation"),
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
            ["python3", HOOK],
            input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True,
            env=dict(os.environ, TMPDIR=tmp),
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
    env = dict(os.environ, TMPDIR=shared)
    payload = json.dumps({"transcript_path": same})
    out = [
        subprocess.run(["python3", HOOK], input=payload, capture_output=True,
                       text=True, env=env).stdout.strip()
        for _ in range(2)
    ]
    results.append(("REMIND" if out[0] else "silent", "REMIND",
                    "same transcript, first prompt"))
    results.append(("REMIND" if out[1] else "silent", "silent",
                    "same transcript again -- fires once per escalation"))
finally:
    shutil.rmtree(shared, ignore_errors=True)

# A malformed transcript must fail open and silent, not crash.
bad = tempfile.mkdtemp()
try:
    p = os.path.join(bad, "t.jsonl")
    with open(p, "w") as fh:
        fh.write("{not json at all\n")
    proc = subprocess.run(
        ["python3", HOOK], input=json.dumps({"transcript_path": p}),
        capture_output=True, text=True, env=dict(os.environ, TMPDIR=bad),
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
