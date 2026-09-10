#!/usr/bin/env python3
"""PreToolUse guard: a commit SHA written into a durable artifact that nothing in the transcript has read.

`shared/principles/dont-take-my-word-for-it.md` says investigate assertions
independently; this is the instrument for the specific assertion that keeps
slipping through, per issue #3471's SHA half.

THE MEASUREMENT (2026-09-09, ai-config#3471)
---------------------------------------------
Twice in one session, both about `ucdavis/rampp#166`:

  1. A case entry asserted "`2d37c48` added `pkg::fn()` support ...
     `08f5a73` narrowed it after a hand-traced case showed the regex also
     matched `pkg:::fn()`". Both halves were false: `2d37c48` excluded `:::`
     by design (its own diff comment says so), and `08f5a73` fixed an
     unrelated foreign-package conflation. The narrative was reconstructed
     from `git log --oneline` without opening either patch.
  2. The same entry said a defect was fixed by a later commit, when it had
     actually been fixed in the working tree before any commit -- invisible
     in the log by construction.

Adversarial review caught both by reading the actual patches. A guard would
have caught the first cheaply: the SHAs were never opened. (The second is
out of this guard's reach -- there is no commit to cite, so there is nothing
for a citation check to see. `flag-unmeasured-timestamp.py`'s own docstring
notes the same asymmetry for its own surface: a mechanism can only catch the
half of a mistake that leaves a decidable trace.)

WHAT IT CHECKS
--------------
    a durable-artifact write (Write/Edit/NotebookEdit on a non-scratch file,
        or a forge comment/review body about to post via `gh`/`glab` or an
        `mcp__github__` comment tool) cites a git commit SHA
    AND no command in the transcript, since the current turn began, reads
        that commit (as opposed to merely listing it)

WHY THIS IS A SEPARATE FILE FROM THE TIMESTAMP GUARD, BUT REUSES ITS PARTS
---------------------------------------------------------------------------
The forge-comment detection (which `gh`/`glab` invocations post a body, and
how to read that body off a `--body-file`, a `-f`/`--body` literal, or a
`gh pr review` flag) is exactly `flag-unmeasured-timestamp.py`'s own
problem, already solved there by importing `flag-uncited-rebuttal.py`'s
`RX_COMMENT_POST`/`strip_heredocs`/`extract_body_text` and adding the
`gh pr review` case on top. Rather than re-solve that a third time, this
file imports `flag-unmeasured-timestamp.py` itself (via the same `_sibling()`
loader every warn-only hook in this directory uses) and pulls its already-
assembled pieces: `RX_REVIEW_POST`, `RX_REVIEW_BODY_FLAG`, `_split_segments`,
`_blank_quotes`, `_short_flag_body`, `RX_DELETING`, `RX_EDIT_LAST`,
`BASH_TOOL_NAMES`, `WRITE_TOOL_NAMES`, `MCP_POST_TOOLS`. What is genuinely
new here is the target this guard is looking FOR (a commit SHA, not a clock
time) and WHERE it is allowed to have been read (a `git`/`gh` read command,
not a `date` call) -- so the small amount of glue below
(`_bash_comment_body`, `_extract_write_content`, `_target_path`) re-derives
only the parts that differ (this guard checks any non-scratch tracked file,
not only session notebooks and memory files, so it cannot reuse the sibling's
path-filtered extractor directly).

TURN BOUNDARY: IMPORTED, NOT RE-DERIVED
-----------------------------------------
`no-unmeasured-clock-claim.py`'s `scan()` computes `turn_start` as the index
of the most recent REAL user prompt -- deliberately not the previous
assistant text block, because that put the window boundary inside the
current turn and expired a reading taken at its top (ai-config#1917). That
definition is subtle and has already been debugged once; this file imports
`scan()` (via the same sibling loader) and uses only its `turn_start` return
value, discarding the clock-specific `last_clock`/`text`/`measured` fields
that have no SHA analogue.

What `scan()` does NOT give this guard is a record of which git/gh commands
ran and where -- it only tracks the position of the last opaque clock read,
because for a clock claim there is exactly one thing worth having read (the
current time) and only ONE occurrence matters. A SHA claim can cite several
different commits in one body, and reading commit A does not discharge a
claim about commit B, so this guard needs the full set of read commands
with their SHAs, not just "was anything read". That is genuinely new work,
so `_collect_tool_uses()` below does its own single pass over the same
transcript file, using the identical line-by-line index scheme `scan()`
uses (one increment per JSONL line) so its indices compare directly against
the imported `turn_start` with no re-derivation of the turn boundary itself.

SHA DETECTION
-------------
Word-bounded hex runs, 7-40 characters, filtered to those containing at
least one a-f letter -- a pure-digit run of that length is a much likelier
false positive (a line count, a date, a concatenated PR/issue number) than a
7-40 character hex string that happens to contain no letter at all. A
7-character token additionally needs a cue: adjacent backticks (a code
span), a preceding "commit"/"SHA"/"hash" word, or a `/commit/` URL segment.
An 8+ character token needs no cue -- shorter random hex collisions with
ordinary words are common (`deadbeef`, `cafe123`), longer ones are not.

A SHA is excluded from consideration when:
  - it falls inside a fenced code block (`scripts/lib/fences.py`'s
    `strip_fences`, which is genuinely fence-aware rather than a whole-file
    regex, so nested/four-backtick fences do not throw it out of phase), or
    inside an indented (>=4 space) PARAGRAPH that looks like a pasted `git
    log`/`git show` excerpt -- either it contains a strong marker line
    (`commit `, `Author:`, `Date:`, `diff --git`, `@@`, a `+++`/`---` diff
    header) or it has TWO OR MORE bare hex-prefixed lines (the `--oneline`
    shape). A SINGLE indented line starting with a hex run is left alone --
    adversarial review measured that the naive per-line version of this
    check silenced a genuine hand-written claim ("2d37c48 is where it
    broke, per my reading.", merely indented) as readily as it silenced a
    real paste, since both start with a bare hex run (ai-config#3471).
  - it is preceded on the same line by a reporting label ("Reviewed
    Commit:", "Reviewed-Commit:", "HEAD=", "head commit:"), or by one of a
    broader set of position-report PHRASINGS this corpus's own session
    notebooks and PR-status recaps use constantly: "at head `X`", "MERGED
    (squash, `X`)", "pushed at `X`", "Committed `X`", "checked out `X`".
    Adversarial review sampled ~500 real citations across two live session
    notebooks and found the large majority were exactly this shape --
    reporting the artifact's OWN current position, not asserting a fact
    about what the commit did. This heuristic is deliberately generous
    (it trades an occasional real assertion phrased like a status line for
    silence on the corpus's single commonest true-positive-free pattern),
    not exhaustive.

SCOPE: PROSE EXTENSIONS ONLY, NOT "ANY TRACKED FILE"
------------------------------------------------------
The `Write`/`Edit`/`NotebookEdit` surface is narrowed to `.md`/`.markdown`/
`.txt`/`.rst`/`.qmd`/`.rmd` targets, not every non-scratch file. Two false-
positive classes forced this, both found by adversarial review against this
repo's own tree: a GitHub Actions SHA pin (`uses: actions/checkout@<sha>`)
in a workflow YAML, and a lockfile hash field -- neither is a narrative
claim, and a pin can never be discharged at all, since the object it names
lives in another repository entirely. Narrowing to the extensions where a
case entry, memory file, or doc prose actually lives keeps the measured
failure (a `.md` case entry) in scope while removing that whole class. It
also means this hook's own `.py` source -- whose docstring necessarily
quotes the measurement's SHAs -- is never itself in scope, so editing this
file does not trip the guard it defines
(`shared/writing/examples-are-scanned.md`).

DISCHARGE
---------
A citation of SHA `X` is discharged by, since the current turn began:
  - `git show X` / `git diff X` (X present as an argument token, not merely
    a flag, AND no no-patch flag present -- see below)
  - `git cat-file -p X` / `git log ... -p ... X` (X present AND a `-p`/
    `--patch` flag present -- `git log --oneline` or a bare `git log X`
    lists commits without reading any of them, and must NOT discharge;
    that is the exact failure mode this guard exists to catch)
  - `gh api repos/OWNER/REPO/commits/X`
  - `mcp__github__get_commit` with `sha`/`ref`/`commit_sha` matching X

`git show`/`git diff` default to printing the patch, so a plain `git show X`
is a genuine read -- but `-s`/`--no-patch`/`--stat`/`--name-only`/
`--name-status`/`--oneline`/`--quiet`/`--format=` all suppress it.
`git show -s --format=%s X` prints exactly one line, the same shape as
`git log --oneline`, and adversarial review found it discharged before this
flag check existed -- reopening on the `show` side the exact hole the `-p`
gate closes on the `log` side. `git cat-file` needs `-p` for the same
reason `git log` does: `-t`/`-s`/`-e` print only the object's type, size, or
existence, never its content.

And, as a broad discharge that clears EVERY citation in the body rather than
one specific SHA (because the command's own text does not name which commit
it is about):
  - `gh api repos/OWNER/REPO/pulls/N/commits` and its MCP mirror
    `mcp__github__list_commits` -- both return the PR's commit list
    (messages included), which is enough to check a claim about which
    commit did what even though the SHA is not a parameter of the call.
    This is a deliberately conservative (favors fewer false positives)
    choice: precise per-SHA correlation is not recoverable from the command
    text alone, and this guard warns rather than blocks.

A cited SHA matches a discharge SHA by common hex prefix (either is a
prefix of the other, case-insensitive) -- both are already >=7 characters
by construction, so an abbreviated citation discharges against a full SHA a
`git show` command read, and vice versa.

UNREADABLE BODIES
-----------------
A forge-comment body this hook cannot read (`--body-file -` stdin, a
missing `--body-file` target) does not silently pass: it asks the reduced
question flag-unmeasured-timestamp.py's own UNREADABLE branch asks for its
surface ("did ANY relevant read happen in this turn at all", since the
specific cited SHA cannot be recovered) rather than staying quiet, because
CLAUDE.md's own PowerShell/backtick-safety section mandates exactly
`--body-file`/`-F body=@file` for a body carrying backticks -- and every SHA
citation in this corpus is written backticked. Silently trusting an
unreadable body would exempt precisely the posting route this hook's own
target shape is written through (adversarial review, ai-config#3471).

KNOWN SCOPE LIMIT
-----------------
`mcp__github__issue_write` and PR create/update body tools match the
registered `mcp__github__.*` hooks.json matcher but are not in the imported
`MCP_POST_TOOLS`, so a SHA narrative written directly into an issue or PR
body (rather than a comment on one) is not checked. This mirrors
flag-unmeasured-timestamp.py's own scope, which has the identical gap for
the same reason -- `MCP_POST_TOOLS` is a COMMENT-posting registry, not every
tool that can carry prose. Accepted rather than closed here: widening it
changes what a sibling hook's identically-named import means, and an issue
or PR body is a smaller, more visible target than a buried comment thread.

WARN, NEVER BLOCK
-----------------
Citing a commit you did not open is often fine -- relaying a reviewer's
finding, quoting a PR body, repeating a teammate's claim verbatim. A wrong
attribution misleads a later reader but breaks nothing, while a blocked
write interrupts work for a check that cannot tell "verified" from
"relayed" by the artifact alone. So the warning names the SHA and the
command that would settle it, leaving the decision with the author.

Fails open on any exception, per every hook in this directory. Fires once
per distinct (transcript, body, SHA) via a `/tmp` sentinel.

See `hooks/test-flag-unread-commit-citation.py` for the fixtures.
"""
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

try:
    from scripts.lib.fences import strip_fences
except Exception:
    def strip_fences(text, **_kw):  # fail open: treat nothing as fenced
        return text


def _sibling(name, key):
    """Import a hyphenated sibling module, or None if unavailable.

    Same pattern every cross-referencing hook in this directory uses
    (`flag-unmeasured-timestamp.py`, `no-empty-promise.py`, ...). Fails
    open, per the file-wide contract.
    """
    path = os.path.join(HERE, name)
    try:
        spec = importlib.util.spec_from_file_location(key, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


_ts = _sibling("flag-unmeasured-timestamp.py", "_sib_unread_commit_ts")
_clock = _sibling("no-unmeasured-clock-claim.py", "_sib_unread_commit_clock")

scan = getattr(_clock, "scan", None)

RX_COMMENT_POST = getattr(_ts, "RX_COMMENT_POST", None)
strip_heredocs = getattr(_ts, "strip_heredocs", None)
extract_body_text = getattr(_ts, "extract_body_text", None)
RX_REVIEW_POST = getattr(_ts, "RX_REVIEW_POST", None)
RX_REVIEW_BODY_FLAG = getattr(_ts, "RX_REVIEW_BODY_FLAG", None)
_split_segments = getattr(_ts, "_split_segments", None)
_blank_quotes = getattr(_ts, "_blank_quotes", None)
_short_flag_body = getattr(_ts, "_short_flag_body", None)
RX_DELETING = getattr(_ts, "RX_DELETING", re.compile(r"(?!)"))
RX_EDIT_LAST = getattr(_ts, "RX_EDIT_LAST", re.compile(r"(?!)"))
BASH_TOOL_NAMES = getattr(_ts, "BASH_TOOL_NAMES",
                           ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"))
WRITE_TOOL_NAMES = getattr(_ts, "WRITE_TOOL_NAMES", (
    "Write", "Edit", "write_to_file", "replace_file_content", "apply_diff",
    "NotebookEdit", "StrReplace", "EditNotebook", "MultiEdit",
))
MCP_POST_TOOLS = getattr(_ts, "MCP_POST_TOOLS", (
    "mcp__github__add_issue_comment",
    "mcp__github__add_reply_to_pull_request_comment",
))

# --------------------------------------------------------------------------
# SHA detection
# --------------------------------------------------------------------------

RX_HEX_TOKEN = re.compile(r"\b[0-9a-fA-F]{7,40}\b")


def _looks_like_sha(token):
    """A pure-digit run is a much likelier false positive than a hex run
    that contains an actual hex letter (a line count, a date, a PR number)."""
    return any(c in "abcdefABCDEF" for c in token)


# The SHA the artifact is REPORTING -- its own current position -- rather
# than asserting a fact about what that commit DID. Trailer labels
# ("Reviewed-Commit:", "HEAD="), and the position-report phrasings this
# corpus's own session notebooks and PR-status recaps use constantly
# ("clean at head `X`", "MERGED (squash, `X`)", "pushed at `X`", "Committed
# `X`"): adversarial review measured this against ~500 real citations in
# two live session notebooks and found the large majority were exactly this
# shape, not a narrative claim needing verification (ai-config#3471). This
# heuristic is deliberately generous rather than exhaustive -- it trades
# missing an occasional real assertion phrased like a status line for not
# nagging on the commonest true-positive-free pattern in this corpus.
RX_REPORTING_LABEL = re.compile(
    r"(?:Reviewed[- ]Commit|Reviewed\s+commit|HEAD|head\s+commit|"
    r"Head\s+SHA|commit\s+hash)\s*[:=]\s*$", re.I)
RX_REPORTING_CONTEXT = re.compile(
    r"\b(?:at\s+head|head\s+is\s+now\s+at|squash(?:-merged)?\s*,?|"
    r"pushed(?:\s+(?:at|to))?|merged\s*\(?|clean\s+at(?:\s+head)?|"
    r"checked\s+out|committed|now\s+at)"
    # No trailing \b: several alternatives above end in punctuation
    # (",", "(") rather than a word character, so a \b there would require
    # a word/non-word transition that does not exist -- e.g. "squash," is
    # immediately followed by whitespace, both non-word, so \b fails right
    # where the match should succeed (measured against "MERGED (squash,
    # `X`)", adversarial review, ai-config#3471).
    r"\s*[:,(`]?\s*$", re.I)

# A pasted `git log`/`git show` excerpt, indented (quoted) rather than
# asserted -- evidence being relayed, not a claim being made. `STRONG`
# markers (a diff/log header line) are unambiguous on their own; a bare
# hex-prefixed line (the `--oneline` shape) is ambiguous by itself -- a
# single indented line reading "2d37c48 is where it broke, per my reading"
# is a hand-written claim, not a paste -- so it is only treated as pasted
# evidence when it co-occurs with a second such line in the same indented
# paragraph (adversarial review, ai-config#3471).
RX_STRONG_LOG_MARKER = re.compile(
    r"^(?:commit\s|Author:|Date:|Merge:|diff --git|@@|index |\+{3}\s|-{3}\s)")
RX_BARE_HEX_LINE = re.compile(r"^[0-9a-fA-F]{7,40}\b\s")


def _strip_evidence_blocks(text):
    """Blank fenced code blocks and indented git-log/show-style output.

    Operates on contiguous indented (>=4 space) PARAGRAPHS rather than
    per-line, so a lone hand-written claim that happens to start with a SHA
    is not silenced merely for being indented -- see RX_STRONG_LOG_MARKER's
    docstring above.
    """
    text = strip_fences(text)
    lines = text.split("\n")
    n = len(lines)
    out = list(lines)
    i = 0
    while i < n:
        stripped = lines[i].lstrip(" ")
        indent = len(lines[i]) - len(stripped)
        if indent >= 4 and stripped:
            block = []
            j = i
            while j < n:
                s2 = lines[j].lstrip(" ")
                ind2 = len(lines[j]) - len(s2)
                if ind2 >= 4 and s2:
                    block.append(s2)
                    j += 1
                else:
                    break
            has_strong = any(RX_STRONG_LOG_MARKER.match(s) for s in block)
            has_bare_hex = sum(1 for s in block if RX_BARE_HEX_LINE.match(s))
            if has_strong or has_bare_hex >= 2:
                for idx in range(i, j):
                    out[idx] = ""
            i = j
        else:
            i += 1
    return "\n".join(out)


def _has_cue(text, start, end):
    """A 7-char token needs a nearby cue: a code span, a commit-ish word,
    or a `/commit/<sha>` URL segment."""
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end == -1:
        line_end = len(text)
    prefix = text[line_start:start]
    suffix = text[end:line_end]
    if prefix.endswith("`") and suffix.startswith("`"):
        return True
    if re.search(r"/commit/$", prefix):
        return True
    if re.search(r"\b(?:commit|sha|hash)\b\s*[:#]?\s*$", prefix, re.I):
        return True
    if re.search(r"\bcommit\b", prefix[-20:], re.I):
        return True
    return False


def find_citations(text):
    """[(start, end, token)] for SHA-shaped citations in `text`."""
    clean = _strip_evidence_blocks(text)
    out = []
    for m in RX_HEX_TOKEN.finditer(clean):
        token = m.group(0)
        if not _looks_like_sha(token):
            continue
        start, end = m.start(), m.end()
        line_start = clean.rfind("\n", 0, start) + 1
        prefix = clean[line_start:start]
        if RX_REPORTING_LABEL.search(prefix) or RX_REPORTING_CONTEXT.search(prefix):
            continue
        if len(token) < 8 and not _has_cue(clean, start, end):
            continue
        out.append((start, end, token))
    return out


# --------------------------------------------------------------------------
# Discharge: what in the transcript would settle a cited SHA
# --------------------------------------------------------------------------

RX_GIT_SHOW = re.compile(r"\bgit\s+show\b([^\n;&|]*)", re.I)
RX_GIT_DIFF = re.compile(r"\bgit\s+diff\b([^\n;&|]*)", re.I)
RX_GIT_CATFILE = re.compile(r"\bgit\s+cat-file\b([^\n;&|]*)", re.I)
RX_GIT_LOG = re.compile(r"\bgit\s+log\b([^\n;&|]*)", re.I)
RX_PATCH_FLAG = re.compile(r"(?:^|\s)(?:-p\b|--patch\b)", re.I)
# `-s`/`--no-patch`/`--stat`/`--name-only`/`--name-status`/`--oneline`/
# `--quiet`/`--format=` all suppress the patch on `git show`/`git diff` --
# `git show -s --format=%s <sha>` prints one line, exactly `git log
# --oneline`'s shape, and must not discharge for the same reason that must
# not (adversarial review, ai-config#3471).
RX_NO_PATCH_FLAG = re.compile(
    r"(?:^|\s)(?:-s\b|--no-patch\b|--stat\b|--name-only\b|--name-status\b|"
    r"--oneline\b|--quiet\b|-q\b|--format=)", re.I)
RX_GH_API_COMMIT = re.compile(r"/commits?/([0-9a-fA-F]{7,40})\b", re.I)
RX_GH_API_PR_COMMITS = re.compile(
    r"\bgh\s+api\s+\S*/pulls/\d+/commits\b", re.I)


def _shas_in_segment(segment):
    return {t for t in RX_HEX_TOKEN.findall(segment) if _looks_like_sha(t)}


def _bash_discharges(command):
    """(specific_shas: set[str], broad: bool) this Bash command would settle."""
    specific = set()
    for m in RX_GIT_SHOW.finditer(command):
        rest = m.group(1)
        if not RX_NO_PATCH_FLAG.search(rest):
            specific |= _shas_in_segment(rest)
    for m in RX_GIT_DIFF.finditer(command):
        rest = m.group(1)
        if not RX_NO_PATCH_FLAG.search(rest):
            specific |= _shas_in_segment(rest)
    for m in RX_GIT_CATFILE.finditer(command):
        # `git cat-file -p <sha>` prints the object's content; `-t`/`-s`/`-e`
        # print only its type, size, or existence -- reusing RX_PATCH_FLAG's
        # `-p` clause since that is the one cat-file flag that reads content.
        rest = m.group(1)
        if RX_PATCH_FLAG.search(rest):
            specific |= _shas_in_segment(rest)
    for m in RX_GIT_LOG.finditer(command):
        rest = m.group(1)
        if RX_PATCH_FLAG.search(rest):
            specific |= _shas_in_segment(rest)
    for m in RX_GH_API_COMMIT.finditer(command):
        specific.add(m.group(1))
    broad = bool(RX_GH_API_PR_COMMITS.search(command))
    return specific, broad


def _mcp_discharges(tool_name, tool_input):
    """(specific_shas, broad) this MCP tool call would settle."""
    if tool_name == "mcp__github__get_commit":
        val = (tool_input.get("sha") or tool_input.get("ref")
               or tool_input.get("commit_sha"))
        return ({str(val)} if isinstance(val, str) and val else set()), False
    if tool_name == "mcp__github__list_commits":
        return set(), True
    return set(), False


def _collect_tool_uses(path):
    """[(index, tool_name, tool_input), ...] for every tool_use block.

    Indexed the same way `no-unmeasured-clock-claim.py`'s `scan()` indexes
    lines (one increment per JSONL line read), so the imported `turn_start`
    compares directly against these indices with no re-derivation of the
    turn boundary itself.
    """
    out = []
    i = 0
    try:
        with open(path, errors="ignore") as fh:
            for line in fh:
                i += 1
                try:
                    m = json.loads(line)
                except Exception:
                    continue
                blocks = (m.get("message") or {}).get("content")
                if blocks is None:
                    blocks = m.get("content") or []
                if not isinstance(blocks, list):
                    continue
                for b in blocks:
                    if isinstance(b, dict) and b.get("type") == "tool_use":
                        out.append((i, b.get("name") or "", b.get("input") or {}))
    except OSError:
        pass
    return out


def _turn_start(path):
    if scan is None or not path or not os.path.exists(path):
        return -1
    try:
        _last_clock, turn_start, _text, _measured = scan(path)
        return turn_start
    except Exception:
        return -1


def _discharged_since(path, turn_start):
    """(specific_shas, broad) discharged anywhere at or after `turn_start`."""
    specific = set()
    broad = False
    for idx, name, inp in _collect_tool_uses(path):
        if idx < turn_start:
            continue
        if name in BASH_TOOL_NAMES:
            command = (inp.get("command") or inp.get("CommandLine")
                       or inp.get("cmd") or inp.get("script"))
            if isinstance(command, str):
                s, b = _bash_discharges(command)
                specific |= s
                broad = broad or b
        else:
            s, b = _mcp_discharges(name, inp)
            specific |= s
            broad = broad or b
    return specific, broad


def _sha_covered(token, discharged, broad):
    if broad:
        return True
    tl = token.lower()
    for d in discharged:
        dl = d.lower()
        n = min(len(tl), len(dl))
        if tl[:n] == dl[:n]:
            return True
    return False


# --------------------------------------------------------------------------
# Extracting the body a tool call would write
# --------------------------------------------------------------------------

RX_SCRATCH_PATH = re.compile(
    r"(?:^|[/\\])(?:tmp|scratchpad|node_modules|\.git)(?:[/\\]|$)", re.I)

# Narrowed to prose/documentation extensions, not "any non-scratch file"
# (adversarial review, ai-config#3471): a GitHub Actions SHA pin
# (`uses: actions/checkout@<sha>`) and a lockfile hash field are both
# 7-40 char hex tokens in a tracked, non-scratch file, and neither is a
# narrative claim about what a commit did -- a pin can never be discharged
# at all, since the object lives in another repository entirely. Scoping to
# the extensions where a case entry, memory file, or doc prose actually
# lives keeps the measured failure (a `.md` case entry) in scope while
# removing that whole false-positive class. This also means this hook's own
# `.py` source -- which quotes the measurement's SHAs in its docstring --
# is never itself in scope, so editing this file does not trip the guard it
# defines (shared/writing/examples-are-scanned.md).
RX_DOC_EXTENSION = re.compile(r"\.(?:md|markdown|txt|rst|qmd|rmd)$", re.I)


def _in_scope_path(path):
    return (bool(path) and not RX_SCRATCH_PATH.search(path)
            and bool(RX_DOC_EXTENSION.search(path)))


def _target_path(tool_input):
    return (
        tool_input.get("file_path")
        or tool_input.get("path")
        or tool_input.get("TargetFile")
        or tool_input.get("target_file")
        or tool_input.get("filePath")
        or tool_input.get("notebook_path")
        or ""
    )


def _extract_write_content(tool_input):
    content = (
        tool_input.get("content")
        or tool_input.get("text")
        or tool_input.get("replacement")
        or tool_input.get("new_string")
        or tool_input.get("new_source")
        or tool_input.get("CodeContent")
        or tool_input.get("ReplacementContent")
        or ""
    )
    if not content and "edits" in tool_input and isinstance(tool_input["edits"], list):
        content = "\n".join(
            e.get("replacement") or e.get("new_string") or ""
            for e in tool_input["edits"] if isinstance(e, dict)
        )
    if not content and "cells" in tool_input and isinstance(tool_input["cells"], list):
        content = "\n".join(
            c.get("source") or c.get("text") or c.get("new_source") or ""
            for c in tool_input["cells"] if isinstance(c, dict)
        )
    return content


def _bash_comment_body(command, cwd):
    """("body", text) / ("unreadable", None) / (None, None) for a Bash
    forge-comment/review post.

    Distinguishing "posts, but this check cannot read the body" from "does
    not post" matters here exactly as it does in flag-unmeasured-timestamp.py:
    CLAUDE.md's own PowerShell/backtick-safety section mandates `--body-file`
    / `-F body=@file` precisely for a body carrying backticks, and every SHA
    citation in this corpus is written as `` `2d37c48` `` -- backticked. So
    the prescribed posting route for this guard's own target shape is
    exactly the one a naive "body is None -> nothing to check" would let
    through silently (adversarial review, ai-config#3471).
    """
    if RX_COMMENT_POST is None or strip_heredocs is None or extract_body_text is None:
        return None, None
    stripped = strip_heredocs(command)
    segments = _split_segments(stripped) if _split_segments else [stripped]
    for segment in segments:
        flags_only = _blank_quotes(segment) if _blank_quotes else segment
        if RX_DELETING.search(flags_only):
            continue
        if RX_EDIT_LAST.search(flags_only) and not (
                RX_REVIEW_BODY_FLAG and RX_REVIEW_BODY_FLAG.search(flags_only)):
            continue
        posts = bool(RX_COMMENT_POST.search(segment)) or (
            bool(RX_REVIEW_POST and RX_REVIEW_POST.search(segment))
            and bool(RX_REVIEW_BODY_FLAG and RX_REVIEW_BODY_FLAG.search(flags_only)))
        if not posts:
            continue
        body = extract_body_text(segment, cwd)
        if body is None and _short_flag_body:
            body = _short_flag_body(segment, cwd)
        if body is None:
            return "unreadable", None
        return "body", body
    return None, None


def _post_from_payload(tool_name, tool_input, cwd):
    """(kind, body, surface) for the artifact this tool call would write.

    `kind` is "body" (content in `body`), "unreadable" (posts, but this
    check cannot read what), or None (out of scope).
    """
    if tool_name in BASH_TOOL_NAMES:
        command = (tool_input.get("command") or tool_input.get("CommandLine")
                   or tool_input.get("cmd") or tool_input.get("script"))
        if isinstance(command, str) and command.strip():
            kind, body = _bash_comment_body(command, cwd)
            if kind == "body" and body:
                return "body", body, "comment body"
            if kind == "unreadable":
                return "unreadable", None, "comment body"
        return None, None, None
    if tool_name in WRITE_TOOL_NAMES:
        target = _target_path(tool_input)
        if target and _in_scope_path(target):
            content = _extract_write_content(tool_input)
            if isinstance(content, str) and content.strip():
                return "body", content, f"edit to `{os.path.basename(target)}`"
        return None, None, None
    if tool_name in MCP_POST_TOOLS:
        body = tool_input.get("body")
        if isinstance(body, str):
            return "body", body, "comment body"
        return None, None, None
    return None, None, None


NOTE = (
    "[flag-unread-commit-citation] This {surface} cites commit `{sha}`, and "
    "no command reading that commit (`git show`, `git log -p`, `git diff`, "
    "`git cat-file`, `gh api repos/OWNER/REPO/commits/<sha>`, `gh api "
    "repos/OWNER/REPO/pulls/N/commits`, `mcp__github__get_commit`) appears "
    "in this transcript since the current turn began. A `git log "
    "--oneline` that merely lists the SHA does not count -- that is the "
    "exact failure this check exists for (ai-config#3471: a case entry's "
    "narrative for two commits, reconstructed from `git log --oneline` "
    "alone, turned out backwards on both). Read the commit before asserting "
    "what it did, or say the claim is relayed rather than verified."
)

UNREADABLE_NOTE = (
    "[flag-unread-commit-citation] This posts a forge comment whose body "
    "this check cannot read (it comes from a file not yet on disk, from "
    "stdin, or from an editor). If it cites a commit SHA, confirm you have "
    "actually read that commit (`git show`/`git log -p`/etc.) rather than "
    "reconstructing the claim from `git log --oneline` alone -- see "
    "CLAUDE.md, \"Don't take anyone's word for it\", and ai-config#3471."
)
UNREADABLE_SHA = "(body not readable)"


def _read_payload():
    args = sys.argv[1:]
    is_dry_run = "--dry-run" in args or "--simulate" in args
    if is_dry_run:
        positional = [a for a in args if not a.startswith("-")]
        if positional:
            raw_cmd = positional[0].strip()
            if raw_cmd.startswith("{") and raw_cmd.endswith("}"):
                try:
                    return json.loads(raw_cmd), True
                except Exception:
                    pass
            return {"tool_name": "Bash", "tool_input": {"command": raw_cmd}}, True
    try:
        payload = json.load(sys.stdin)
        return (payload if isinstance(payload, dict) else {}), is_dry_run
    except Exception:
        return {}, is_dry_run


def main() -> int:
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    cwd = payload.get("cwd") or os.getcwd()
    tpath = payload.get("transcript_path") or ""

    try:
        kind, body, surface = _post_from_payload(tool_name, tool_input, cwd)
        if kind is None:
            if is_dry_run:
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
            return 0

        if kind == "unreadable":
            # Cannot correlate to a specific SHA, so this only asks "did ANY
            # commit-reading command run in this turn at all" -- mirroring
            # flag-unmeasured-timestamp.py's UNREADABLE branch, which asks
            # the same reduced question ("was the clock read at all") for
            # the surface it cannot see into either.
            turn_start = _turn_start(tpath)
            discharged, broad = _discharged_since(tpath, turn_start)
            if discharged or broad:
                if is_dry_run:
                    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
                return 0
            unresolved = UNREADABLE_SHA
            body_for_key = ""
        else:
            citations = find_citations(body)
            if not citations:
                if is_dry_run:
                    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
                return 0

            turn_start = _turn_start(tpath)
            discharged, broad = _discharged_since(tpath, turn_start)

            unresolved = None
            for _start, _end, token in citations:
                if not _sha_covered(token, discharged, broad):
                    unresolved = token
                    break

            if unresolved is None:
                if is_dry_run:
                    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
                return 0
            body_for_key = body

        if not is_dry_run:
            key = hashlib.sha256(
                (tpath + "|" + body_for_key + "|" + unresolved).encode()).hexdigest()[:16]
            sentinel = os.path.join(
                tempfile.gettempdir(), f".claude-unread-commit-{key}")
            if os.path.exists(sentinel):
                return 0
            try:
                open(sentinel, "w").close()
            except Exception:
                pass

        if unresolved == UNREADABLE_SHA:
            context = UNREADABLE_NOTE
            message = (
                "Commit citation reminder: this comment's body cannot be "
                "read by this check. If it cites a commit SHA, confirm you "
                "actually read that commit before posting.")
        else:
            context = NOTE.format(surface=surface or "comment body", sha=unresolved)
            message = (
                f"Commit citation reminder: this {surface or 'comment body'} "
                f"cites `{unresolved}` with no read of that commit in this "
                f"turn. Run `git show {unresolved}` (or equivalent) before "
                f"restating what it did.")
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": context,
            },
        }
        if not os.environ.get("ANTIGRAVITY_AGENT"):
            out["systemMessage"] = message
        print(json.dumps(out))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
