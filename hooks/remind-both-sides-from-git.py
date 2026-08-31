#!/usr/bin/env python3
"""UserPromptSubmit reminder: a blob-vs-working-tree comparison decides nothing about a commit.

A comparison has two operands, and only one of them is named by the command
that extracts it. `git show <rev>:<path>` says exactly which revision it read.
The other side, a plain read of `<path>`, says nothing at all -- it takes
whatever the working tree happens to hold, which is a fact about the checkout
rather than about the revision under discussion.

When the checkout is not where you think, the two operands are the SAME blob
and the comparison returns "identical". Read as a statement about a commit or a
merge, that is the opposite of the truth.

THE INCIDENT (2026-08-05)
-------------------------
In a `ucdavis/bcs` checkout on `docs/dangling-memories-wikilinks` (HEAD
`e86e4786`):

    git show d1dd05e3^:inst/extdata/ett-validation-true-effects.rds > /tmp/te-old.rds

then, in R:

    identical(readRDS("/tmp/te-old.rds"),
              readRDS("inst/extdata/ett-validation-true-effects.rds"))

That returned TRUE, and was reported as "a byte-different re-serialization
whose values did not change".

`git merge-base --is-ancestor d1dd05e3 HEAD` returns false: that branch does
not contain the merge the question was about. So the working-tree file WAS the
old blob, `git hash-object` on it returns exactly the `d1dd05e3^` blob hash, and
the comparison was old against old.

The cost was not a wasted minute. The false conclusion was published to a
GitHub issue, used to retract a correct earlier finding, and used to close a
second issue as invalid. All three had to be corrected.

The correct form takes BOTH sides from git:

    git cat-file blob <base>:<path> > /tmp/old.bin
    git cat-file blob <head>:<path> > /tmp/new.bin

WHY THIS INJECTS RATHER THAN BLOCKS
-----------------------------------
Comparing a committed blob against the working tree is frequently the RIGHT
thing to do. Checking whether your own uncommitted edit changed something is
exactly that comparison, and it is both common and correct -- there the working
tree is the subject, so it is the right second side.

The hazard is narrower: drawing a conclusion about what a COMMIT or a MERGE
did, where the working tree is not the right second side at all. Nothing in the
commands distinguishes the two cases, because the difference lives in what the
comparison is being used to CLAIM, which is not observable here.

A blocking guard would therefore misfire on every legitimate
did-my-edit-change-anything check, and per README ("A hook that misfires is
worse than a missing one") it would then be switched off, taking the real cases
with it. So this warns on the next prompt and only ever adds context. There is
no code path here that suppresses, delays, or alters a message.

Firing after the comparison has run is later than the command and still ahead
of the cost. The expensive thing is not the comparison; it is the conclusion
published on top of it. A reminder landing on the next prompt arrives while
retracting is still cheap -- in the incident, before the issue comment.

RELATIONSHIP TO THE DESERIALIZE-BEFORE-BINARY-CLAIM GUARD
---------------------------------------------------------
That guard ships as `hooks/remind-deserialize-before-binary-claim.py`
(ai-config#1181). Nothing here imports or calls it, so this hook does not
depend on it -- the paragraphs below are rationale rather than a dependency.
Its own docstring states the same boundary from the other side.

The two are siblings on either side of the same conclusion, and this one
covers a hole in that one.

That guard fires when an escalation names a serialized artifact that NOTHING in
the transcript deserialized -- a check that was never run. Its discharge is a
tool call that both deserializes and names that path.

The broken comparison above SATISFIES that discharge, because a `readRDS` of
`inst/extdata/ett-validation-true-effects.rds` genuinely did occur. Verified
rather than assumed: that hook, run against a transcript of this incident,
produces no output. So a check run against the wrong second side reads there as
a check performed.

This guard asks the question that one cannot: were the two operands the two
things you meant to compare?

FIRE CONDITION
--------------
All four, scoped to one path:

  1. A revision-qualified extraction -- `git show <rev>:<path>` or
     `git cat-file blob <rev>:<path>` -- redirected to a file.
  2. A read of that SAME path with NO revision qualifier, i.e. the working-tree
     copy.
  3. That read sits in a comparison context (a deserializer, a comparison call,
     or a hashing tool).
  4. The working-tree read is at or after the extraction.

Clause 1 requires the redirect deliberately, and the narrowing is worth naming
because its failure mode is silence: `git show <rev>:<path> | md5sum` sets up
the same asymmetric comparison and is NOT detected. The redirect is what makes
an extraction distinguishable from merely LOOKING at a file, which is far more
common and would otherwise fire on every `git show` followed by an unrelated
read. The over-warn that dropping it would buy is not worth firing on the
inspect-then-read shape, which is ordinary.

DISCHARGE
---------
Either of two, and both are PATH- or COMMIT-scoped by construction. An
over-broad discharge produces silence, and silence is indistinguishable from
compliance (`shared/workflow/algorithmatize-checks.md`, "A reminder guard's
discharge condition is a second matcher, and its failure is silence"). Both
require a command that RAN, per `shared/principles/fail-fast.md`'s "A guard's
discharge fires on positive success, not the absence of failure" -- prose
asserting the checkout was verified is the very claim under suspicion.

  D-A. A `git merge-base --is-ancestor` naming a revision that matches the
       EXTRACTION'S OWN revision. Matched after normalizing away `^`, `~N`, and
       `^{...}`, so an extraction at `d1dd05e3^` is discharged by an ancestry
       check on `d1dd05e3` -- the parent and the commit are the same question.
       A `merge-base` check about an unrelated commit does NOT discharge.

  D-B. A second revision-qualified extraction of the SAME path at a DIFFERENT
       revision -- i.e. both sides came from git. Compared on the RAW revision
       strings, not the normalized ones, because `<base>` and `<base>^` are two
       legitimately different sides while normalizing would collapse them into
       one. A two-sided extraction of a DIFFERENT file does NOT discharge.

Note the two comparisons are deliberately different functions. D-A asks "is
this the same commit?", which wants normalization. D-B asks "are these two
distinct sides?", which must not normalize.

D-B does not require the redirect that clause 1 requires. The asymmetry is the
safe direction: a strict fire condition costs false negatives on an unusual
shape, while a strict discharge would nag through a correct two-sided
comparison written with a pipe, and a guard that nags through correct work is
the one that gets switched off.

SIDECHAIN
---------
Subagent turns are deliberately INCLUDED here, which differs from
remind-deserialize-before-binary-claim.py, and the difference follows from what
each guard reads. That one fires on the assistant's own outgoing MESSAGE, so a
subagent's message is not the thing under scrutiny. This one fires on TOOL
CALLS, and a subagent's broken comparison yields a false conclusion that is
reported back to the main agent and published from there -- which is the
incident's own cost shape. Filtering sidechains would go silent on exactly that
path.

Fires once per (path, extraction) pair, because a reminder repeated every turn
is noise, and noise is what gets a guard ignored.

Fails OPEN and SILENT: any parse trouble prints nothing at all.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

# A revision-qualified extraction of a path: `<rev>:<path>` as the argument to
# a command that prints a blob. `[^\s:]+` for the revision so `origin/main:p`
# works while a merge-stage read (`git show :2:file`) does not match -- that
# reads the index rather than a commit, so it is out of scope.
EXTRACT = re.compile(
    r"""\bgit\s+
        # Global flags before the subcommand. The flag-with-a-SEPARATE-value
        # forms (`-C <dir>`, `-c <key>=<val>`) need naming explicitly: a
        # pattern that only allows single-token flags matches
        # `git --git-dir=X show ...` and silently misses `git -C /r show ...`,
        # which is a false negative, and silence is the dangerous direction.
        (?: (?: -[cC] \s+ \S+ | --\S+ | -[a-zA-Z] ) \s+ )*
        (?: show
          | cat-file \s+ (?: blob | -p )
        )
        \s+ (?: -[^\s]+ \s+ )*
        (?P<rev>[^\s:|;&<>]+) : (?P<path>[^\s|;&<>]+)""",
    re.I | re.X,
)

# `git merge-base --is-ancestor <A> <B>`. The flag is located first and the
# next two whitespace tokens are taken, so other flags may precede it.
IS_ANCESTOR = re.compile(r"--is-ancestor\s+(\S+)\s+(\S+)")

# Revision suffixes that select a RELATIVE commit. Stripped when asking "same
# commit?" (D-A) and preserved when asking "two distinct sides?" (D-B).
REV_SUFFIX = re.compile(r"(?:\^\{[^}]*\}|\^[0-9]*|~[0-9]*|@\{[^}]*\})+$")

HEX = re.compile(r"[0-9a-f]{7,40}\Z", re.I)

# A comparison context. The read has to be FOR something -- a deserializer that
# turns the bytes into a value, an equality call, or a hashing tool that
# produces a digest to compare. A bare `cat` of a file is not this.
#
# `diff` and `cmp` are guarded: `git diff <path>` is a git-native comparison
# against the index or HEAD, which is not this hazard at all, so a `git `
# prefix is excluded rather than matched.
COMPARE = re.compile(
    r"""(
      readRDS | read_rds | load_?rdata | \bload\s*\( | \breadr?::
    | open_dataset | read_parquet | read_feather | read_ipc | read_arrow
    | read_excel | read_xlsx | read\.xlsx | read_sas | read_sav | read_dta
    | read_csv | read\.csv | readLines | read_fst | qread
    | pd\.read_ | pandas\.read_ | pickle\.load | joblib\.load
    | np\.load | numpy\.load | h5py | netCDF4
    | identical\s*\( | all\.equal\s*\( | waldo::compare | assert_frame_equal
    | \bhash-object\b | \bmd5sum\b | \bsha1sum\b | \bsha256sum\b | \bshasum\b
    | \bcksum\b | openssl\s+dgst
    | (?<!git\s)\bdiff\b | \bcmp\b | \bcolordiff\b
    )""",
    re.I | re.X,
)

# Characters that can sit inside a path token. Used to reject a match that is
# only part of a longer path, so `x.rds` never matches inside `other/x.rds`
# or `prefixx.rds`.
PATH_CHAR = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_./-")


def clean(tok):
    """Strip shell quoting and trailing punctuation from a captured token."""
    return tok.strip("\"'`").rstrip(",;)")


def norm_rev(rev):
    """Drop relative-commit suffixes, so `d1dd05e3^` and `d1dd05e3` agree.

    Used ONLY by D-A, which asks whether an ancestry check named the same
    commit as the extraction. D-B must not use this: `<base>` and `<base>^` are
    two legitimately different sides of a comparison, and collapsing them would
    let a single extraction discharge itself.
    """
    out = REV_SUFFIX.sub("", clean(rev))
    return out or clean(rev)


def same_commit(a, b):
    """True when two revisions name the same commit, allowing abbreviation.

    Prefix matching is restricted to hex strings of at least 7 characters, so
    an abbreviated SHA matches its full form while `HEAD` never matches
    `HEADER` and a branch name never matches a longer one.
    """
    a, b = norm_rev(a), norm_rev(b)
    if a == b:
        return True
    if HEX.match(a) and HEX.match(b) and min(len(a), len(b)) >= 7:
        return a.startswith(b) or b.startswith(a)
    return False


def path_candidates(path):
    """The path plus each of its component suffixes.

    An extraction naming `inst/extdata/x.rds` is answered by a read of
    `x.rds` run from inside that directory, so the suffixes have to be
    searchable. The occurrence test below is what keeps this from matching a
    DIFFERENT file with the same basename.
    """
    parts = path.split("/")
    return [path] + ["/".join(parts[i:]) for i in range(1, len(parts))]


def occurrences(blob, path):
    """(bare, qualified) counts for this path in this blob.

    An occurrence is only real when the character before it is not a path
    character -- otherwise `x.rds` would match inside `other/x.rds`, which is a
    different file, and inside `prefixx.rds`, which is not a path at all. That
    rejection is what makes same-basename, different-directory pairs safe.

    A real occurrence preceded by `:` is REVISION-QUALIFIED (it came out of a
    `<rev>:<path>` argument). Anything else is a working-tree read.
    """
    bare = qualified = 0
    for cand in path_candidates(path):
        start = 0
        while True:
            i = blob.find(cand, start)
            if i < 0:
                break
            start = i + 1
            end = i + len(cand)
            # Symmetric with the preceding-character test below: a path
            # character on either side means this is part of a LONGER token,
            # so `x.rds` matches neither `other/x.rds` nor `x.rds.bak`.
            if end < len(blob) and blob[end] in PATH_CHAR:
                continue
            prev = blob[i - 1] if i else ""
            if prev == ":":
                qualified += 1
            elif prev in PATH_CHAR:
                continue
            else:
                bare += 1
    return bare, qualified


def has_redirect(cmd, end):
    """True when the command segment starting at `end` writes to a file.

    Bounded at the next command separator so a LATER command's redirect is not
    credited to this extraction. `2>` and `>&` are excluded: those redirect a
    file descriptor rather than capturing the blob.
    """
    seg = re.split(r"(?:&&|\|\||;|\n)", cmd[end:], maxsplit=1)[0]
    return re.search(r"(?<![0-9&])>(?!&)", seg) is not None


def tool_blob(name, inp):
    """The text of a tool call in which these commands could appear.

    Only tool_use inputs are read. A command that RAN is positive evidence; a
    sentence saying one ran is the claim under suspicion.
    """
    if not isinstance(inp, dict):
        return ""
    if name in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"):
        return str(inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or inp.get("script") or "")
    if name in ("Write", "Edit", "NotebookEdit", "write", "edit", "write_to_file", "replace_file_content"):
        return " ".join(
            str(inp.get(k, ""))
            for k in ("file_path", "path", "TargetFile", "target_file", "filePath", "content", "new_string", "new_source", "CodeContent", "ReplacementContent")
        )
    if name in ("Task", "Agent", "invoke_subagent"):
        return str(inp.get("prompt") or inp.get("Prompt") or "") + " " + str(inp.get("description") or "")
    try:
        return json.dumps(inp)
    except Exception:
        return ""


def records(path):
    with open(path, errors="ignore") as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except Exception:
                continue


def scan(transcript):
    """Return (extractions, blobs).

    extractions: [(path, rev, index, redirected)]
    blobs:       [(index, text)]

    Subagent turns are included deliberately -- see the SIDECHAIN note in the
    module docstring.
    """
    extractions, blobs = [], []

    for i, m in enumerate(records(transcript)):
        tool_calls = []
        if m.get("type") == "assistant" or m.get("role") == "assistant":
            content = (m.get("message") or {}).get("content") or m.get("content") or []
            if isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_use":
                        tool_calls.append((b.get("name") or "", b.get("input") or {}))
        if m.get("type") in {"PLANNER_RESPONSE", "GENERIC"} or m.get("source") == "MODEL":
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

        for name, inp in tool_calls:
            blob = tool_blob(name, inp)
            if not blob:
                continue
            blobs.append((i, blob))
            for m2 in EXTRACT.finditer(blob):
                extractions.append((
                    clean(m2.group("path")),
                    clean(m2.group("rev")),
                    i,
                    has_redirect(blob, m2.end()),
                ))

    return extractions, blobs


def ancestry_revs(blobs):
    """Every revision named by a `--is-ancestor` check, collected once.

    Gathered in one pass rather than re-scanned per extraction, so the D-A
    check below is a membership test instead of an O(extractions x blobs)
    regex sweep -- see the timeout note in main().
    """
    out = []
    for _, blob in blobs:
        for a, b in IS_ANCESTOR.findall(blob):
            out.extend((a, b))
    return out


def ancestry_checked(revs, rev):
    """D-A: an ancestry check naming THIS extraction's commit.

    Scoped to the commit. A `merge-base --is-ancestor` about an unrelated
    commit leaves the obligation standing -- an unscoped version would discharge
    every extraction in the session from one check about one of them, which is
    the silent-discharge direction.
    """
    for other in revs:
        if same_commit(other, rev):
            return True
    return False


def both_sides_extracted(extractions, path, rev):
    """D-B: a second revision-qualified extraction of the SAME path.

    Scoped to the path, so a two-sided extraction of a different file does not
    discharge this one. Revisions are compared RAW rather than normalized,
    because `<base>` and `<base>^` are two distinct sides.
    """
    for p, r, _, _ in extractions:
        if p == path and clean(r) != clean(rev):
            return True
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0

    transcript = payload.get("transcript_path") or ""
    if not transcript or not os.path.isfile(transcript):
        return 0

    try:
        extractions, blobs = scan(transcript)
    except Exception:
        return 0

    # Clause 3 is evaluated ONCE per blob rather than once per
    # (extraction, blob) pair. Most tool calls carry no comparison at all, so
    # this prunes the pair scan from O(extractions x blobs) to O(blobs) in the
    # common case. That is a correctness concern rather than tidiness: a hook
    # is killed at its 10s timeout, and a killed reminder is a SILENT one,
    # which is the dangerous direction. Measured on a synthetic worst case
    # (10000 records, 500 extractions): 43.8s before all three prunes, 2.3-2.6s
    # after them, across repeated runs.
    cmp_blobs = [(j, b) for j, b in blobs if COMPARE.search(b)]  # clause 3
    anc_revs = ancestry_revs(blobs)

    # Deduplicated on (path, rev): a session that extracts the same blob
    # repeatedly owes one reminder, not one per extraction, and the pair scan
    # shrinks with it.
    seen, uniq = set(), []
    for path, rev, idx, redirected in extractions:
        if (path, rev) in seen:
            continue
        seen.add((path, rev))
        uniq.append((path, rev, idx, redirected))

    owed = []
    for path, rev, idx, redirected in uniq:
        if not redirected:                                   # clause 1
            continue
        if both_sides_extracted(extractions, path, rev):     # D-B
            continue
        if ancestry_checked(anc_revs, rev):                  # D-A
            continue
        for j, blob in cmp_blobs:
            if j < idx:                                      # clause 4
                continue
            bare, _ = occurrences(blob, path)                # clause 2
            if not bare:
                continue
            if path not in [o[0] for o in owed]:
                owed.append((path, rev, idx))
            break

    if not owed:
        return 0

    path, rev, idx = owed[0]

    key = hashlib.sha256(
        f"{transcript}:{path}:{rev}:{idx}".encode()
    ).hexdigest()[:16]
    sentinel = os.path.join(
        tempfile.gettempdir(), f".claude-both-sides-from-git-{key}"
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
            f"\n{len(owed) - 1} other path(s) in this session are in the same "
            "position: " + ", ".join(o[0] for o in owed[1:]) + "."
        )

    print(
        f"Comparison-operand reminder: this session extracted `{path}` at "
        f"`{rev}` and then read the SAME path from the working tree inside a "
        "comparison.\n"
        "Only one of those two operands names a revision. The other is "
        "whatever this checkout happens to hold, which is a fact about the "
        "checkout rather than about any commit. If the checkout does not "
        "contain the change in question, both sides are the same blob, the "
        "comparison returns \"identical\", and reading that as a statement "
        "about a commit or a merge is the OPPOSITE of the truth.\n"
        "Settle which checkout you are on, or take both sides from git:\n"
        f"    git merge-base --is-ancestor {norm_rev(rev)} HEAD; echo \"rc=$?\"\n"
        "    #   rc=0 -> this checkout contains it; rc=1 -> it does NOT\n"
        "  or, comparing two revisions directly:\n"
        f"    git cat-file blob <base>:{path} > /tmp/old.bin\n"
        f"    git cat-file blob <head>:{path} > /tmp/new.bin\n"
        "`git hash-object` on the working-tree file settles it in one step too: "
        "if it returns the blob hash you just extracted, you compared old "
        "against old.\n"
        "If this is a false positive -- you are checking whether your own "
        "UNCOMMITTED edit changed something, so the working tree is the "
        "subject and is the right second side -- disregard it and carry on."
        + others
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
