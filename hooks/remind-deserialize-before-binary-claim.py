#!/usr/bin/env python3
"""UserPromptSubmit reminder: escalating about a binary artifact owes a deserialization.

Serialization is not canonical, so a changed git blob is NOT evidence that
content changed. `git diff` reports the file as modified, `gh pr diff
--name-only` lists it, and nothing in either output reveals that the
deserialized values are identical. The two facts -- "the blob changed" and
"the contents changed" -- feel like one fact while a status message is being
composed, which is exactly when the second gets asserted from the first.

The cost is asymmetric. An escalation of this shape asks a human to authorize
work: regenerate the dependent artifacts, or hold the change. In the incident
this mechanizes (ucdavis/bcs#579, 2026-08-05) that was roughly 1.5 hours of
serial compute plus a 500-task SLURM array, requested from a `--name-only`
listing alone.

Measured afterward against the merge's parent `d1dd05e3^`, TWO of those three
`.rds` files carried values equal to their predecessors and differed only in a
freshly stamped provenance attribute, while the third
(`msm-validation-accuracy-results.rds`) had genuinely changed -- bias by 121%,
rmse by 18%, coverage by 3%.

Re-verified 2026-08-05 with BOTH sides taken from git (`d1dd05e3^` against
`d1dd05e3`), rather than from the working tree, since the working-tree form is
the very mistake described below and the two "unchanged" rows are exactly what
it would have produced had it been wrong here. It was not: the split
reproduces, and `attr(x, "provenance")` is the single attribute that moved on
all three. So the escalation was not baseless; it was
UNMEASURED, which is the defect. Two thirds of what it asked to regenerate had
not changed, and nothing in the path list distinguished the third from the
other two.

THE OBVIOUS CHECK IS THE WRONG ONE
----------------------------------
    Rscript -e 'identical(readRDS(old), readRDS(new))'   # returns FALSE

`identical()` returns FALSE for all three, because a re-run stamps fresh
provenance -- `git_commit`, `bcs_version`, `renv_lock_hash`, `timestamp` -- even
when every value is unchanged. Reading that FALSE as "the contents changed"
lands back on the original error with a command's authority behind it.

THREE QUESTIONS, THREE INSTRUMENTS
----------------------------------
The three get conflated because one command seems to answer all of them. They
are separate, and only the third is what an escalation about regeneration
actually turns on.

  Q1. Did the BYTES change?
      `git diff`, `gh pr diff --name-only`, or a blob hash.
      Already answered by the time this fires, and answering it is what
      produced the escalation. It is not evidence about Q2 or Q3.

  Q2. Was the artifact RE-RUN at all?
      Read the provenance stamp. In `ucdavis/bcs` these live in a SINGLE
      `provenance` attribute holding a 12-field list, not as top-level
      attributes -- so index into it rather than into `attributes()`, which
      returns NULLs for every one of these names:

          attr(readRDS(f), "provenance")[c("git_commit", "bcs_version",
                                           "timestamp")]

      A changed stamp means a fresh run produced this file. It does NOT mean
      any value moved, which is exactly why `identical()` is the wrong
      instrument: it folds Q2 into Q3 and reports the union as if it were Q3.

  Q3. Did the VALUES move?
      This is the one the escalation rests on, and it needs the stamp excluded:

          all.equal(unclass(o), unclass(n), check.attributes = FALSE)

      TRUE for the two re-serializations, a list of per-column relative
      differences for the one real change.

TAKE BOTH SIDES FROM GIT
------------------------
    git cat-file blob <base>:<path> > /tmp/old.bin && \
    git cat-file blob <head>:<path> > /tmp/new.bin && \
    Rscript -e 'o <- readRDS("/tmp/old.bin"); n <- readRDS("/tmp/new.bin");
                all.equal(unclass(o), unclass(n), check.attributes = FALSE)'

Written as ONE chained command deliberately, for two reasons. The `&&` makes
the comparison conditional on both extractions succeeding, so a bad revision
spec fails loudly instead of silently comparing against an empty or stale temp
file. And this guard's discharge reads one tool call at a time, requiring the
deserialization and the artifact's path to appear TOGETHER (see DISCHARGE
below) -- run as three separate calls, the `Rscript` names only the temp files,
so it would not discharge and the reminder would repeat at someone who had
already done the right thing. Measured, not assumed: chained is silent here,
split fires.

An earlier revision of this file recommended reading the second side from the
WORKING TREE (`readRDS("<path>")`), which is only correct when the checkout
contains the change being asked about. On 2026-08-05 that exact shape was run
from a branch that did not contain the merge in question, so both sides were
the same blob, the comparison returned "identical", and the false conclusion
was published to a GitHub issue and used to close a second issue as invalid.
`git merge-base --is-ancestor <commit> HEAD` returned false and the
working-tree file hashed to the base blob.

That failure is mechanized by the sibling guard
`hooks/remind-both-sides-from-git.py` (ai-config#1186); see the boundary
section below.

WHY THIS INJECTS RATHER THAN BLOCKS
-----------------------------------
The obvious shape is a `Stop` hook blocking the escalation, copying
`no-offer-to-file.py`. That shape is wrong here.

A `Stop` guard suppresses a message that is WRONG TO SEND. This message often
is not. Plenty of legitimate escalations about a binary artifact have nothing
to do with its contents: how large it is, where it lives, whether it should be
tracked at all, whether it belongs in the release. A blocking guard misfires on
every one of those, and per README ("A hook that misfires is worse than a
missing one") it then gets switched off -- taking the real cases with it.

And when the contents genuinely did change, the escalation is not merely
allowed but correct: the human really does need to authorize the regeneration.
A guard cannot tell those apart, which is precisely why it must warn rather
than decide.

So this fires on the next prompt and only ever adds context. There is no code
path here that can suppress, delay, or alter a message.

Firing after the escalation has gone out is later than ideal and still ahead of
the cost. The expensive thing is not the message; it is the compute the human
authorizes in reply. A reminder landing on the next prompt arrives before that
reply is acted on, which is while retracting is still cheap.

DISCHARGE
---------
Scoped to the PATH, deliberately. A `readRDS` anywhere in the transcript must
not discharge a claim about a different file: an over-broad discharge produces
silence, and silence is indistinguishable from compliance
(`shared/workflow/algorithmatize-checks.md`, "A reminder guard's discharge
condition is a second matcher, and its failure is silence").

Discharge also requires POSITIVE evidence -- a tool_use that actually ran a
deserialization naming that path. Prose asserting the check happened does not
count, per `shared/principles/fail-fast.md`'s "A guard's discharge fires on
positive success, not the absence of failure". A sentence claiming a file was
compared is the very claim under suspicion.

Any such deserialization in the transcript discharges, before or after the
escalation. The obligation is that the content question got settled, not that
it got settled first; by the time this fires, a later measurement has already
made the reminder moot.

Fires once per (path, escalation) pair, because a reminder repeated every turn
is noise, and noise is what gets a guard ignored.

Fails OPEN and SILENT: any parse trouble prints nothing at all.

BOUNDARY WITH remind-both-sides-from-git.py
-------------------------------------------
Stated because a guard that deliberately does not fire on a case is
indistinguishable, from the outside, from one that fails to.

This guard's discharge is satisfied by a deserialization that names the path,
INCLUDING one whose second side came from the working tree -- that is, by the
broken comparison described above. Verified rather than assumed: a transcript
of the 2026-08-05 incident, with the escalation and both of its commands,
produces empty stdout and rc=0 here. The same transcript with the comparison
removed fires, so the silence is a discharge rather than a detector that never
ran.

That is deliberate. The two guards ask different questions on either side of
the same conclusion:

  - This one asks whether the content question was settled AT ALL. A `readRDS`
    of the path genuinely did occur, so by this guard's question it was.
  - `remind-both-sides-from-git.py` asks whether the two operands were the two
    things you meant to compare. That is where a working-tree second side is
    wrong, and it fires on exactly the transcript this one is silent on.

Tightening this discharge to reject a working-tree second side was considered
and rejected. It would mean re-implementing that guard's four-clause fire
condition here, giving one predicate two independent implementations free to
drift apart; and on the incident both guards would then fire about one
mistake, which is the noise this file already argues gets a guard ignored.
A hole covered by a sibling that ships the detection is a boundary, not a gap.

The composition is only sound while BOTH are registered. If
`remind-both-sides-from-git.py` is ever removed or left inert, the
wrong-second-side case stops being covered anywhere, and this guard's silence
on it becomes a real gap rather than a delegated one.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

# Escalation signal. The boxed markers come from CLAUDE.md's chat-output
# tagging convention -- the categories reserved for "output a user is waiting
# on", matched by their emoji or their bold label. QUESTION, BLOCKER, and
# RECOMMENDATION are the decision-seeking three; ANSWER and the unboxed
# informational tags (UPDATE, FLAG, DONE, ALL CLEAR) are deliberately absent,
# since reporting a fact asks nothing of anyone.
ESCALATION = re.compile(
    r"""(
      \U0001F6D1 | \u2753 | \U0001F9ED                 # stop sign, question, compass
    | \*\*(BLOCKER|QUESTION|RECOMMENDATION)\*\*
    | @[A-Za-z0-9][-A-Za-z0-9]{0,38}\b                 # @-mention of a human
    | needs?\s+(a\s+)?(decision|your\s+call|sign[- ]?off)
    | your\s+call\b
    | escalat(e|ing|ed|ion)
    | (should|shall)\s+(i|we)\s+
    | (do|would)\s+you\s+want\s+(me\s+)?to\b
    | (please\s+)?(confirm|advise|decide)\b
    | waiting\s+on\s+(you|your)\b
    )""",
    re.I | re.X,
)

# Serialized-artifact extensions. Anything whose on-disk bytes are a
# re-serializable encoding of an object, so a blob diff says nothing about
# value equality.
SERIAL_EXT = (
    "rds|rdata|rda|rdb|rdx"
    "|parquet|feather|arrow|orc|avro"
    "|xlsx|xlsm|xls|ods"
    "|sas7bdat|xpt|dta|sav|por"
    "|pkl|pickle|joblib"
    "|npz|npy|h5|hdf5|nc|mat"
    "|db|sqlite|sqlite3|duckdb"
    "|fst|qs|rdsx"
    "|pb|onnx|safetensors"
)

# A path with one of those extensions. Requires at least one path-ish or
# word character before the dot so a bare ".rds" is not a path, and allows an
# optional directory prefix.
#
# The optional `(?:(?:~|\.{1,2})?/)?` prefix admits absolute and
# home/dot-relative paths -- `/scratch/x.rds`, `~/x.rds`, `./x.rds`,
# `../x.rds`. Without it the pattern could not match those AT ALL: the body's
# own leading classes exclude `/`, so a match could not start on one, and every
# later position failed the lookbehind because the character before it was the
# `/`. That silently excluded exactly the shapes an HPC escalation uses most
# (`/scratch/...`, `/work/...`), and the failure direction was silence, which
# is indistinguishable from having nothing to report.
#
# The lookbehind still forbids a match starting mid-token, which is what stops
# `y.rds` matching inside `xy.rds`; `~` is in that class so a `~/`-rooted path
# is matched whole rather than from its slash.
ARTIFACT_PATH = re.compile(
    r"(?<![A-Za-z0-9_./~-])((?:(?:~|\.{1,2})?/)?"
    r"[A-Za-z0-9_.-]*[A-Za-z0-9_-][A-Za-z0-9_./-]*"
    r"\.(?:" + SERIAL_EXT + r"))(?![A-Za-z0-9])",
    re.I,
)

# Deserialization signals. Each one READS the artifact into an object, so its
# presence beside a path is evidence that path's contents were examined rather
# than merely listed.
DESERIALIZE = re.compile(
    r"""(
      readRDS | load_?rdata | \bload\s*\( | attach\s*\(
    | open_dataset | read_parquet | read_feather | read_ipc | read_arrow
    | read_excel | read_xlsx | read\.xlsx | read_sas | read_sav | read_dta
    | read_stata | read_spss | haven:: | arrow:: | qs:: | fst::
    | pd\.read_ | pandas\.read_ | pickle\.load | joblib\.load
    | np\.load | numpy\.load | h5py | netCDF4 | scipy\.io
    | duckdb | sqlite3 | dbConnect | read_fst | qread
    | identical\s*\( | all\.equal\s*\( | waldo::compare | assert_frame_equal
    )""",
    re.I | re.X,
)

FENCE = re.compile(r"```.*?```", re.S)
QUOTED = re.compile(r"^\s*>.*$", re.M)
TICKED = re.compile(r"`[^`\n]*`")


def visible_prose(text):
    """Drop code fences, blockquotes, and inline code.

    Quoting the rule while discussing it is the main false-positive source for
    the ESCALATION half, and it is nearly always inside one of those three.
    Paths are matched against the RAW text instead, because a path in a status
    message is routinely written in backticks -- stripping inline code first
    would discard the very thing clause 2 looks for.
    """
    text = FENCE.sub(" ", text)
    text = QUOTED.sub(" ", text)
    return TICKED.sub(" ", text)


def records(path):
    with open(path, errors="ignore") as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except Exception:
                continue


def tool_blob(name, inp):
    """The text of a tool call in which a deserialization could appear.

    Only tool_use inputs are read. A command that RAN is positive evidence; a
    sentence saying one ran is the claim under suspicion.
    """
    if not isinstance(inp, dict):
        return ""
    if name in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"):
        return str(inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or inp.get("script") or "")
    if name in ("Write", "Edit", "NotebookEdit", "write", "edit", "write_to_file", "replace_file_content"):
        return " ".join(
            str(inp.get(k, "")) for k in
            ("file_path", "path", "TargetFile", "target_file", "filePath", "content", "new_string", "new_source", "CodeContent", "ReplacementContent")
        )
    if name in ("Task", "Agent", "invoke_subagent"):
        return str(inp.get("prompt") or inp.get("Prompt") or "") + " " + str(inp.get("description") or "")
    # Anything else: serialize the whole input rather than guess its schema.
    try:
        return json.dumps(inp)
    except Exception:
        return ""


def same_artifact(a, b):
    """True when two written paths denote the same artifact.

    Equal, or one is a path-component suffix of the other -- so a check run
    from inside the artifact's own directory (`readRDS("x.rds")`) discharges an
    escalation that named `inst/extdata/x.rds`.

    Deliberately NOT a bare substring or basename test. Same-basename,
    different-directory pairs are ordinary in a data repo
    (`arrow/raw_data.parquet` beside `R/raw_data.rds`), and a basename test
    would let a deserialization of one discharge a claim about the other.
    That is a silent discharge, the dangerous direction: an over-warn is
    visible and gets fixed, silence is indistinguishable from compliance.
    """
    if a == b:
        return True
    return a.endswith("/" + b) or b.endswith("/" + a)


def path_deserialized(blob, path):
    """True when this one blob both deserializes AND names this path.

    Both conditions in the SAME blob is what makes the discharge path-scoped.
    Matching them separately across the transcript would let a `readRDS` of
    file B discharge a claim about file A, which is the over-broad discharge
    this guard exists to avoid.

    Paths are re-extracted from the blob with the same ARTIFACT_PATH pattern
    rather than substring-matched, so `y.rds` never matches inside `xy.rds`.
    """
    if not DESERIALIZE.search(blob):
        return False
    return any(same_artifact(q, path) for q in ARTIFACT_PATH.findall(blob))


def scan(path):
    """Return (escalated_paths, deserialized_blobs).

    escalated_paths: [(artifact_path, escalation_text, record_index)]
    """
    escalated, blobs = [], []

    for i, m in enumerate(records(path)):
        # A subagent's own turns are not my outgoing message.
        if m.get("isSidechain"):
            continue

        tool_calls = []
        text_blocks = []

        is_assistant = m.get("type") == "assistant" or m.get("role") == "assistant"
        blocks = (m.get("message") or {}).get("content") or m.get("content") or []
        if isinstance(blocks, list):
            for b in blocks:
                if isinstance(b, dict):
                    if b.get("type") == "tool_use":
                        tool_calls.append((b.get("name") or "", b.get("input") or {}))
                    elif b.get("type") == "text" and is_assistant:
                        text_blocks.append(b.get("text") or "")
        elif isinstance(blocks, str) and is_assistant:
            text_blocks.append(blocks)

        if m.get("type") in {"PLANNER_RESPONSE", "GENERIC"} or m.get("source") == "MODEL":
            content = m.get("content")
            if isinstance(content, str):
                text_blocks.append(content)
            elif isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "text":
                        text_blocks.append(b.get("text") or "")
                    elif isinstance(b, str):
                        text_blocks.append(b)
            for tc in m.get("tool_calls") or []:
                if isinstance(tc, dict):
                    tname = tc.get("name") or (tc.get("function") or {}).get("name") or ""
                    targs = tc.get("args") or tc.get("input") or (tc.get("function") or {}).get("arguments") or {}
                    if isinstance(targs, str):
                        try:
                            targs = json.loads(targs)
                        except Exception:
                            targs = {"command": targs}
                    tool_calls.append((tname, targs if isinstance(targs, dict) else {}))

        for raw_text in text_blocks:
            hit = ESCALATION.search(visible_prose(raw_text))
            if not hit:
                continue
            for p in ARTIFACT_PATH.findall(raw_text):
                escalated.append((p, hit.group(0).strip(), i))

        for name, inp in tool_calls:
            blob = tool_blob(name, inp)
            if blob:
                blobs.append(blob)

    return escalated, blobs


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    path = payload.get("transcript_path") or ""
    if not path or not os.path.isfile(path):
        return 0

    try:
        escalated, blobs = scan(path)
    except Exception:
        return 0

    owed = []
    for artifact, signal, idx in escalated:
        if any(path_deserialized(b, artifact) for b in blobs):
            continue
        if artifact not in [o[0] for o in owed]:
            owed.append((artifact, signal, idx))

    if not owed:
        return 0

    artifact, signal, idx = owed[0]

    # Keyed on the transcript path too, so the sentinel is per session.
    key = hashlib.sha256(
        f"{path}:{artifact}:{idx}".encode()
    ).hexdigest()[:16]
    sentinel = os.path.join(
        tempfile.gettempdir(), f".claude-deserialize-before-claim-{key}"
    )
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    others = ""
    if len(owed) > 1:
        others = (
            f"\n{len(owed) - 1} other serialized path(s) in this session are in "
            "the same position: " + ", ".join(o[0] for o in owed[1:]) + "."
        )

    print(
        f"Deserialization reminder: an escalation in this session (\"{signal}\") "
        f"named the serialized artifact `{artifact}`, and no command in this "
        "transcript has deserialized that specific path.\n"
        "Serialization is not canonical, so a changed git blob is not evidence "
        "that the CONTENT changed. `git diff` and `gh pr diff --name-only` "
        "report a re-serialization of identical values exactly as they report a "
        "real change.\n"
        "Settle it before the human acts on the escalation, taking BOTH sides "
        "from git and keeping it to ONE chained command (the && fails loudly "
        "on a bad revision spec, and this reminder clears only when the "
        "deserialization and the path appear in the same call):\n"
        f"    git cat-file blob <base>:{artifact} > /tmp/old.bin && \\\n"
        f"    git cat-file blob <head>:{artifact} > /tmp/new.bin && \\\n"
        "    Rscript -e 'o <- readRDS(\"/tmp/old.bin\"); "
        "n <- readRDS(\"/tmp/new.bin\"); "
        "all.equal(unclass(o), unclass(n), check.attributes = FALSE)'\n"
        "Read the second side from git rather than from the working tree: the "
        "working-tree copy is whatever this checkout happens to hold, so if it "
        "does not contain the change under discussion both sides are the same "
        "blob and the comparison returns 'identical'.\n"
        "Compare values rather than whole objects: a provenance-stamped "
        "artifact gets a fresh commit, version, and timestamp on every re-run, "
        "so bare `identical()` returns FALSE even when nothing changed -- and "
        "reading that FALSE as a real change is the original error with a "
        "command's authority behind it. Whether it was RE-RUN and whether the "
        "VALUES moved are separate questions: read the artifact's provenance "
        "stamp for the first, `all.equal()` above for the second.\n"
        "If the values match, retract the escalation rather than letting it buy "
        "compute that changes nothing. Check each path separately: in "
        "ucdavis/bcs#579 two of three artifacts were unchanged and the third "
        "had genuinely moved.\n"
        "If this reminder is a false positive -- the escalation is about the "
        "file's size, path, or whether it should be tracked at all, rather than "
        "about its contents -- disregard it and carry on." + others
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
