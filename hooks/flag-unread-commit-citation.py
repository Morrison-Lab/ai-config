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
    inside a line indented >=4 spaces that also looks like `git log`/`git
    show` output (starts with a hex run, `commit `, `Author:`, `Date:`,
    `diff --git`, `@@`, or a `+++`/`---` diff header) -- a pasted excerpt is
    evidence being relayed, not a claim being made. This is a narrower net
    than CommonMark's indented-code-block rule (which has no notion of
    "looks like a log"), chosen because a true false negative here (missing
    an indented citation that is NOT quoted output) is cheaper than a false
    positive that nags on every properly-indented list continuation.
  - it is preceded on the same line by a reporting label ("Reviewed
    Commit:", "Reviewed-Commit:", "HEAD=", "head commit:") -- the artifact
    is reporting its own position, not asserting a fact about the commit.

DISCHARGE
---------
A citation of SHA `X` is discharged by, since the current turn began:
  - `git show X` / `git diff X` / `git cat-file ... X` (X present as an
    argument token, not merely a flag)
  - `git log ... -p ... X` (X present AND a `-p`/`--patch` flag present --
    `git log --oneline` or a bare `git log X` lists commits without
    reading any of them, and must NOT discharge; that is the exact failure
    mode this guard exists to catch)
  - `gh api repos/OWNER/REPO/commits/X`
  - `mcp__github__get_commit` with `sha`/`ref`/`commit_sha` matching X

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


# The SHA the artifact is REPORTING about itself, not asserting a fact
# about -- a claim-comment trailer or a session header, never a citation.
RX_REPORTING_LABEL = re.compile(
    r"(?:Reviewed[- ]Commit|Reviewed\s+commit|HEAD|head\s+commit|"
    r"Head\s+SHA|commit\s+hash)\s*[:=]\s*$", re.I)

# A pasted `git log`/`git show` excerpt, indented (quoted) rather than
# asserted -- evidence being relayed, not a claim being made.
RX_LOG_OUTPUT_LINE = re.compile(
    r"^(?:[0-9a-fA-F]{7,40}\b|commit\s|Author:|Date:|Merge:|diff --git|"
    r"@@|index |\+{3}\s|-{3}\s)")


def _strip_evidence_blocks(text):
    """Blank fenced code blocks and indented git-log/show-style output."""
    text = strip_fences(text)
    lines = text.split("\n")
    out = []
    for line in lines:
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        if indent >= 4 and RX_LOG_OUTPUT_LINE.match(stripped):
            out.append("")
        else:
            out.append(line)
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
        if RX_REPORTING_LABEL.search(clean[line_start:start]):
            continue
        if len(token) < 8 and not _has_cue(clean, start, end):
            continue
        out.append((start, end, token))
    return out


# --------------------------------------------------------------------------
# Discharge: what in the transcript would settle a cited SHA
# --------------------------------------------------------------------------

RX_GIT_SHOW_DIFF_CATFILE = re.compile(
    r"\bgit\s+(?:show|diff|cat-file)\b([^\n;&|]*)", re.I)
RX_GIT_LOG = re.compile(r"\bgit\s+log\b([^\n;&|]*)", re.I)
RX_PATCH_FLAG = re.compile(r"(?:^|\s)(?:-p\b|--patch\b)", re.I)
RX_GH_API_COMMIT = re.compile(r"/commits?/([0-9a-fA-F]{7,40})\b", re.I)
RX_GH_API_PR_COMMITS = re.compile(
    r"\bgh\s+api\s+\S*/pulls/\d+/commits\b", re.I)


def _shas_in_segment(segment):
    return {t for t in RX_HEX_TOKEN.findall(segment) if _looks_like_sha(t)}


def _bash_discharges(command):
    """(specific_shas: set[str], broad: bool) this Bash command would settle."""
    specific = set()
    for m in RX_GIT_SHOW_DIFF_CATFILE.finditer(command):
        specific |= _shas_in_segment(m.group(1))
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


def _in_scope_path(path):
    return bool(path) and not RX_SCRATCH_PATH.search(path)


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
    """The body a Bash forge-comment/review post would send, or None."""
    if RX_COMMENT_POST is None or strip_heredocs is None or extract_body_text is None:
        return None
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
        return body
    return None


def _post_from_payload(tool_name, tool_input, cwd):
    """(body, surface) for the artifact this tool call would write, or (None, None)."""
    if tool_name in BASH_TOOL_NAMES:
        command = (tool_input.get("command") or tool_input.get("CommandLine")
                   or tool_input.get("cmd") or tool_input.get("script"))
        if isinstance(command, str) and command.strip():
            body = _bash_comment_body(command, cwd)
            if body:
                return body, "comment body"
        return None, None
    if tool_name in WRITE_TOOL_NAMES:
        target = _target_path(tool_input)
        if target and _in_scope_path(target):
            content = _extract_write_content(tool_input)
            if isinstance(content, str) and content.strip():
                return content, f"edit to `{os.path.basename(target)}`"
        return None, None
    if tool_name in MCP_POST_TOOLS:
        body = tool_input.get("body")
        return (body, "comment body") if isinstance(body, str) else (None, None)
    return None, None


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
        body, surface = _post_from_payload(tool_name, tool_input, cwd)
        if not body:
            if is_dry_run:
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
            return 0

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

        if not is_dry_run:
            key = hashlib.sha256(
                (tpath + "|" + body + "|" + unresolved).encode()).hexdigest()[:16]
            sentinel = os.path.join(
                tempfile.gettempdir(), f".claude-unread-commit-{key}")
            if os.path.exists(sentinel):
                return 0
            try:
                open(sentinel, "w").close()
            except Exception:
                pass

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
