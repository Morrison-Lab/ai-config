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
serial compute plus a 500-task SLURM array, requested over three `.rds` files
that were byte-different re-serializations of the same run -- each deserialized
to an object `identical()` to its predecessor, provenance attribute included.

The check that settles it costs two lines:

    git show <base>:<path> > /tmp/old.rds
    Rscript -e 'identical(readRDS("/tmp/old.rds"), readRDS("<path>"))'

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
ARTIFACT_PATH = re.compile(
    r"(?<![A-Za-z0-9_./-])([A-Za-z0-9_.-]*[A-Za-z0-9_-][A-Za-z0-9_./-]*"
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
    if name == "Bash":
        return str(inp.get("command", ""))
    if name in ("Write", "Edit", "NotebookEdit"):
        return " ".join(
            str(inp.get(k, "")) for k in
            ("file_path", "content", "new_string", "new_source")
        )
    if name in ("Task", "Agent"):
        return str(inp.get("prompt", "")) + " " + str(inp.get("description", ""))
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
        if m.get("type") != "assistant":
            continue
        blocks = (m.get("message") or {}).get("content") or []
        if not isinstance(blocks, list):
            continue

        for b in blocks:
            if not isinstance(b, dict):
                continue

            if b.get("type") == "text":
                raw = b.get("text", "")
                hit = ESCALATION.search(visible_prose(raw))
                if not hit:
                    continue
                for p in ARTIFACT_PATH.findall(raw):
                    escalated.append((p, hit.group(0).strip(), i))

            elif b.get("type") == "tool_use":
                blob = tool_blob(b.get("name") or "", b.get("input") or {})
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
        "Settle it before the human acts on the escalation:\n"
        f"    git show <base>:{artifact} > /tmp/old.bin\n"
        f"    # then compare the two deserialized objects, e.g. in R:\n"
        f"    #   identical(readRDS('/tmp/old.bin'), readRDS('{artifact}'))\n"
        "If they are identical, retract the escalation rather than letting it "
        "buy compute that changes nothing (ucdavis/bcs#579).\n"
        "If this reminder is a false positive -- the escalation is about the "
        "file's size, path, or whether it should be tracked at all, rather than "
        "about its contents -- disregard it and carry on." + others
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
