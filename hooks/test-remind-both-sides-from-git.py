"""Test the both-sides-from-git guard.

Case #1 is the 2026-08-05 incident verbatim -- the real paths, the real
revision `d1dd05e3^`, pasted in unaltered rather than tidied, per
algorithmatize-checks' "Test the instrument against the incident that prompted
it, verbatim". A guard is designed against a SUMMARY of its incident, and the
summary is what lets it miss.

The value past that is concentrated in two groups.

The NEGATIVE cases matter because this guard fires on a shape that is often
correct: comparing a committed blob against the working tree is exactly how you
check whether your own uncommitted edit changed something. A guard that nags on
those gets switched off, and then the real case goes unprotected too.

The OVER-BROAD-DISCHARGE cases matter more, because their failure is silent. A
`merge-base` check about some other commit, or a two-sided extraction of some
other file, must NOT discharge this path -- an over-broad discharge produces
silence, and silence is indistinguishable from compliance.

Every case is run and reported; the suite does not abort on the first failure.
That is deliberate, so a mutation test can see WHICH cases reddened rather than
only that something did.

Run: python3 hooks/test-remind-both-sides-from-git.py hooks/remind-both-sides-from-git.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

MARKER = "Comparison-operand reminder"

ART = "inst/extdata/ett-validation-true-effects.rds"


def tool(name, inp):
    return {"type": "assistant",
            "message": {"content": [{"type": "tool_use",
                                     "name": name, "input": inp}]}}


def bash(cmd):
    return tool("Bash", {"command": cmd})


def say(text):
    return {"type": "assistant",
            "message": {"content": [{"type": "text", "text": text}]}}


# ---------------------------------------------------------------- the incident
# Pasted verbatim from the 2026-08-05 transcript. Do not tidy these two lines:
# the revision, the paths, and the quoting are the test.
INCIDENT_EXTRACT = bash(
    "git show d1dd05e3^:inst/extdata/ett-validation-true-effects.rds "
    "> /tmp/te-old.rds"
)
INCIDENT_COMPARE = bash(
    "Rscript -e 'identical(readRDS(\"/tmp/te-old.rds\"), "
    "readRDS(\"inst/extdata/ett-validation-true-effects.rds\"))'"
)
INCIDENT_CLAIM = say(
    "The file is a byte-different re-serialization whose values did not change."
)

# Discharges.
ANCESTRY_SCOPED = bash("git merge-base --is-ancestor d1dd05e3 HEAD; echo rc=$?")
ANCESTRY_OTHER = bash("git merge-base --is-ancestor 9f3ab21c origin/main")
BOTH_SIDES = bash(
    "git cat-file blob e86e4786:inst/extdata/ett-validation-true-effects.rds "
    "> /tmp/te-new.rds"
)
BOTH_SIDES_OTHER_FILE = bash(
    "git cat-file blob e86e4786:inst/extdata/msm-validation-accuracy-results.rds "
    "> /tmp/o.rds"
)

CASES = [
    # (name, records, must_fire)

    # 1. THE INCIDENT, verbatim.
    ("VERBATIM incident: blob at d1dd05e3^ vs the working tree",
     [INCIDENT_EXTRACT, INCIDENT_COMPARE, INCIDENT_CLAIM], True),

    # 2. Negatives -- these are correct or irrelevant work and must stay quiet.
    ("extraction with NO later working-tree read of that path",
     [INCIDENT_EXTRACT, bash("ls -la /tmp/te-old.rds")], False),

    ("working-tree read with NO preceding extraction",
     [INCIDENT_COMPARE], False),

    ("BOTH sides revision-qualified (the correct form)",
     [INCIDENT_EXTRACT, BOTH_SIDES, bash(
         "Rscript -e 'identical(readRDS(\"/tmp/te-old.rds\"), "
         "readRDS(\"/tmp/te-new.rds\"))'")], False),

    ("scoped merge-base --is-ancestor for THAT commit",
     [INCIDENT_EXTRACT, ANCESTRY_SCOPED, INCIDENT_COMPARE], False),

    ("comparison names a DIFFERENT path",
     [INCIDENT_EXTRACT, bash(
         "Rscript -e 'identical(readRDS(\"/tmp/te-old.rds\"), "
         "readRDS(\"inst/extdata/msm-validation-accuracy-results.rds\"))'")],
     False),

    # Clause-isolating negatives. Each exists so exactly one mutation reddens it.
    ("extraction is PIPED, not redirected (clause 1, deliberate miss)",
     [bash("git show d1dd05e3^:" + ART + " | md5sum"), INCIDENT_COMPARE], False),

    ("re-reads the SAME rev-qualified path, no working-tree side",
     [INCIDENT_EXTRACT, bash("git show d1dd05e3^:" + ART + " | md5sum")], False),

    ("working-tree read with NO comparison context",
     [INCIDENT_EXTRACT, bash("ls -la " + ART)], False),

    ("comparison read comes BEFORE the extraction",
     [INCIDENT_COMPARE, INCIDENT_EXTRACT], False),

    ("SAME BASENAME, different directory",
     [INCIDENT_EXTRACT, bash(
         "Rscript -e 'identical(readRDS(\"/tmp/te-old.rds\"), "
         "readRDS(\"scratch/copies/ett-validation-true-effects.rds\"))'")],
     False),

    ("a LONGER path that merely starts with the extracted one",
     [INCIDENT_EXTRACT, bash(
         "Rscript -e 'identical(readRDS(\"/tmp/te-old.rds\"), "
         "readRDS(\"" + ART + ".bak\"))'")], False),

    # 3. Over-broad discharge -- these MUST still fire.
    ("merge-base about an UNRELATED commit does not discharge",
     [INCIDENT_EXTRACT, ANCESTRY_OTHER, INCIDENT_COMPARE], True),

    ("two-sided extraction of a DIFFERENT file does not discharge",
     [INCIDENT_EXTRACT, BOTH_SIDES_OTHER_FILE, INCIDENT_COMPARE], True),

    ("the SAME revision extracted twice is still one side",
     [INCIDENT_EXTRACT,
      bash("git show d1dd05e3^:" + ART + " > /tmp/dup.rds"),
      INCIDENT_COMPARE], True),

    # 4. Reach.
    ("read from INSIDE the artifact's directory still fires",
     [INCIDENT_EXTRACT, bash(
         "cd inst/extdata && Rscript -e 'identical(readRDS(\"/tmp/te-old.rds\"), "
         "readRDS(\"ett-validation-true-effects.rds\"))'")], True),

    ("git -C <dir> show still fires (flag with a separate value)",
     [bash("git -C /some/repo show d1dd05e3^:" + ART + " > /tmp/te-old.rds"),
      INCIDENT_COMPARE], True),

    ("a SUBAGENT's own broken comparison still fires",
     [dict(INCIDENT_EXTRACT, isSidechain=True),
      dict(INCIDENT_COMPARE, isSidechain=True)], True),

    ("prose CLAIMING the checkout was verified does not discharge",
     [INCIDENT_EXTRACT,
      say("I confirmed with git merge-base --is-ancestor d1dd05e3 HEAD that "
          "this branch contains the merge."),
      INCIDENT_COMPARE], True),
]


def run(records):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    try:
        out = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True,
            env=dict(os.environ, TMPDIR=tempfile.mkdtemp()),
        )
    finally:
        os.unlink(path)
    return out


def main():
    passes, failed = 0, []

    for name, records, must_fire in CASES:
        out = run(records)
        fired = MARKER in out.stdout
        if fired == must_fire:
            print(f"PASS: {name}" + ("" if must_fire else "  (silent)"))
            passes += 1
        else:
            print(f"FAIL: {name} -- expected "
                  f"{'FIRE' if must_fire else 'SILENCE'}, got "
                  f"{'FIRE' if fired else 'SILENCE'}")
            failed.append(name)

    # Fails open and silent on junk input, rather than crashing the prompt.
    for label, payload in (("malformed JSON", "not json"),
                           ("non-dict payload", '"a string"'),
                           ("missing transcript", '{"transcript_path":"/nope"}')):
        out = subprocess.run([sys.executable, HOOK], input=payload,
                             capture_output=True, text=True)
        if out.returncode == 0 and not out.stdout.strip():
            print(f"PASS: {label} -- fails open and silent")
            passes += 1
        else:
            print(f"FAIL: {label} -- rc={out.returncode} out={out.stdout!r}")
            failed.append(label)

    # The sentinel must suppress a repeat for the same (path, extraction).
    r = [INCIDENT_EXTRACT, INCIDENT_COMPARE]
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for x in r:
            fh.write(json.dumps(x) + "\n")
    env = dict(os.environ, TMPDIR=tempfile.mkdtemp())
    a = subprocess.run([sys.executable, HOOK],
                       input=json.dumps({"transcript_path": path}),
                       capture_output=True, text=True, env=env)
    b = subprocess.run([sys.executable, HOOK],
                       input=json.dumps({"transcript_path": path}),
                       capture_output=True, text=True, env=env)
    os.unlink(path)
    if MARKER in a.stdout and MARKER not in b.stdout:
        print("PASS: fires once per (path, extraction), not every turn")
        passes += 1
    else:
        print("FAIL: sentinel did not suppress the repeat")
        failed.append("sentinel")

    print(f"\n{passes} passed, {len(failed)} failed")
    if failed:
        print("failed cases: " + " | ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
