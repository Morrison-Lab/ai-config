#!/usr/bin/env python3
"""PreToolUse reminder: a claim comment on an issue with no read of that
issue's COMMENTS earlier in the session.

[`claim-pr`](../skills/claim-pr/SKILL.md), [`check-history`](../skills/check-history/SKILL.md),
and `memories/preferences.md`'s "never assume; always verify" already say to
read an issue before working it -- but the rule is consulted at read time and
broken at composition time, which is the shape
[`algorithmatize-checks`](../shared/workflow/algorithmatize-checks.md) says to
mechanize rather than restate. None of those three names the specific gap
this hook closes: reading the issue's BODY satisfies "I read the issue" while
leaving its COMMENTS -- where a diagnosis, a duplicate, or an escalation is
routinely recorded -- unread.

WHAT HAPPENED
-------------
Measured on `Lacaedemon/sparta#1544` (2026-09-18). A session posted a claim
comment on the issue after reading only its BODY. The body posed a
diagnostic question ("uid 1's leader position overlaps its unit -- is this a
shape residual or a physics bug?"). The issue's COMMENTS -- two comments
above the one the session posted -- recorded that the diagnosis had already
been done and merged (PR #1553), and that the residual had been escalated to
an unanswered discussion. Reading the body alone made the question look open.

Result: a wasted claim, a wasted draft PR (#1608, opened then closed as
obsolete), and a public correction. Nothing in the moment signalled a step
was skipped -- viewing an issue and then commenting on it *feels* like having
read it, which is exactly why a rule stated as "read the issue first" does
not reach this case.

THE CHECK
---------
Fires only when ALL of these hold:

  1. The about-to-run Bash command posts a comment on an issue at a COMMAND
     POSITION: `gh issue comment <N>` or `glab issue note <N>`. (Position
     anchoring follows `warn-pr-create-without-dupe-check.py`: this corpus
     quotes both commands constantly, in fragments and in this file's own
     docstring, and an unanchored matcher would fire on prose that merely
     mentions them.) An optional `-R`/`--repo owner/repo` may sit between the
     verb and the number -- an ordinary way to target an issue outside the
     working tree's own repo, and exactly the shape a worktree-rooted session
     reaches for. Requiring the number immediately after the verb, with
     nothing tolerated in between, made a `-R`-qualified claim invisible to
     this matcher entirely (caught in review); `RX_REPO_FLAG_GAP` is the
     shared fragment that admits it, on both the trigger side here and the
     view/api discharge regexes below.
  2. The comment's body -- read from `--body`/`--body-file`/`-f body=`/
     `-F body=@file` for `gh`, or `--message`/`-m`/`-F file`/`--file file`
     for `glab` -- carries CLAIM vocabulary: "claiming"/"claim this", "is
     working on this", "picking this up", "grabbing this", "taking this",
     "please hold off". This is what keeps the hook from firing on every
     issue comment -- an ordinary status update or a closing note is not a
     claim.
  3. No earlier command in the transcript read that SAME issue's comments.

WHAT DISCHARGES IT
-------------------
A qualifying read, for the SAME issue number as the comment-post:

    gh issue view <N> --comments
    gh issue view <N> --json <fields including "comments">
    glab issue view <N> --comments   (glab issue show <N> --comments too --
                                       "show" is glab's documented alias)
    gh api repos/<owner>/<repo>/issues/<N>/comments      (a GET; a body-write
                                                            flag on that same
                                                            shape is the POST
                                                            this hook is about,
                                                            not a discharge)
    a GitHub MCP issue-read call naming that issue with method=get_comments
        (tool-mappings.yml's READ_ISSUE_COMMENTS: `mcp__github__issue_read`
        with `method: get_comments`, or a Cursor-mapped name ending in
        `issue_read`)

`gh issue view <N>` WITH NO `--comments`/`--json comments` is deliberately
NOT a discharge -- reading the body alone is exactly the failure this hook
exists to catch, so the plain view must not silence it. This is the one
distinction the hook has to get right; see the test suite's "core case".

`--state`, `--json state`, or any other field/flag on `gh issue view` does
not discharge either -- only a fields list that actually contains the token
`comments` does, matched as a whole comma-separated field rather than a
substring (so `--json bodyComments` does not falsely qualify, and a
`--json comments,title` in either field order does).

WHY WARN RATHER THAN BLOCK
---------------------------
The same asymmetry `warn-pr-create-without-dupe-check.py` names: a wasted
claim is cheap to retract -- one comment, as the measured incident's own
correction shows -- while a blocked `gh issue comment` is expensive, since
posting the claim is the action that tells other sessions and the `@claude`
bot not to start a conflicting one. So this reminds and names the query to
run, rather than refusing the post.

WHY THE CUE LIST IS SCOPED TO CLAIM VOCABULARY
------------------------------------------------
Without clause 2, this would fire on every `gh issue comment`/`glab issue
note` in the corpus's own test suites and fragments, and on every ordinary
status update, closing note, or reply a session posts to an issue it has
been working for hours. The cue list is drawn from `claim-pr`'s own claim
wording ("is working on this ... please hold off") plus the looser phrasing
sessions actually use ("claiming this", "picking this up", "grabbing this",
"taking this"). A missed true positive here is a claim comment that reads as
ordinary prose and slips through unflagged; a false positive costs one
ignorable reminder on a comment that happens to use claim-adjacent words
without being a claim.

The cue list carries no negation handling: "not claiming this fixes the root
cause" and "I'll take this offline" both match, neither is a claim. Accepted
deliberately, on the same asymmetry as the sibling `DISPUTE_CUE` in
`flag-uncited-rebuttal.py`, which carries the identical gap for the same
reason -- a warn-only reminder that occasionally fires on a rebuttal or an
aside costs one ignorable line, while teaching the cue list to parse negation
buys precision this hook does not need.

UNREADABLE BODY
----------------
When the body cannot be read (a `--body-file`/`-F file` naming a variable, a
glob, or a file not yet on disk; a `-`/stdin body; an editor-invoked body
with no flag at all), the hook cannot test clause 2 -- it cannot rule OUT
that this is a claim. Per `flag-unmeasured-timestamp.py`'s own precedent for
the identical situation (an unreadable comment body it cannot inspect for a
timestamp), the safe direction is to warn rather than assume compliance: it
still checks clause 3 (has this issue's comments been read?) and fires a
distinct, more conservative note when that also fails.

FAILS OPEN
----------
Any parse trouble, an unreadable transcript, or an unresolvable issue number
(the command names no digit -- a variable or a URL form of `gh issue comment`)
all return 0 silently, mirroring `flag-uncited-rebuttal.py`'s own "any parse
trouble ... return 0 silently" for the same reason: a reminder that cannot
establish its own precondition must not fire.

OUT OF SCOPE
------------
PR comments (`gh pr comment`) are not this hook's subject -- a PR's own
review-comment history is a different surface with its own conventions, and
`claim-pr`'s PR claim wording and workflow differ from its issue claim.
MCP-only claim posting (`mcp__github__add_issue_comment`, with no Bash `gh`/
`glab` involved) is not covered as a TRIGGER either, only as a DISCHARGE
surface (a GitHub MCP issue-read counts toward clause 3) -- the measured
incident and the task that requested this hook both named the two Bash
shapes specifically. Widening the trigger to MCP posting is a natural
follow-up, not folded in here to keep the matcher exactly as specified.
"""
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.realpath(__file__))


def _sibling(name, key):
    """Import a hyphenated sibling module, or None if unavailable.

    Same pattern `flag-unmeasured-timestamp.py` and
    `warn-unmeasured-capability-claim.py` use. Fails open, per the file-wide
    contract: this hook must not crash merely because a sibling moved.
    """
    try:
        spec = importlib.util.spec_from_file_location(
            key, os.path.join(HERE, name))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


_dupe = _sibling("warn-pr-create-without-dupe-check.py", "_sib_claim_dupe")
_rebuttal = _sibling("flag-uncited-rebuttal.py", "_sib_claim_rebuttal")

# The heredoc stripper, the quote-aware "rest of this command's flags"
# helper, and the transcript tool_use walker, reused verbatim so this hook
# agrees with its closest sibling about what a command position and a
# transcript entry are.
strip_heredocs = getattr(_dupe, "strip_heredocs", (lambda command: command))
_command_rest = getattr(_dupe, "_command_rest", None)
_tool_uses = getattr(_dupe, "_tool_uses", None)
_payload_commands = getattr(_dupe, "_payload_commands", None)

# The `gh` body extractor (handles --body, --body-file, -f body=,
# -F body=@file, all read from disk when file-based) -- the only body
# extractor in this corpus that reads the FILE-based forms, per
# `flag-uncited-rebuttal.py`'s own docstring.
extract_body_text = getattr(_rebuttal, "extract_body_text", None)
RX_BODY_FILE = getattr(_rebuttal, "RX_BODY_FILE", re.compile(r"(?!)"))
RX_F_BODY_FILE = getattr(_rebuttal, "RX_F_BODY_FILE", re.compile(r"(?!)"))
RX_F_BODY_LITERAL = getattr(_rebuttal, "RX_F_BODY_LITERAL", re.compile(r"(?!)"))
RX_BODY_LITERAL = getattr(_rebuttal, "RX_BODY_LITERAL", re.compile(r"(?!)"))

BASH_TOOL_NAMES = ("Bash", "bash", "run_command", "execute_command", "terminal", "shell")

# --------------------------------------------------------------------------
# Clause 1: does this command post a comment on an issue, at a command
# position, and which issue number?
# --------------------------------------------------------------------------

# Same separator class as `flag-uncited-rebuttal.py`'s RX_COMMENT_POST (no
# `(`/`{`): a comment-post command, unlike a PR/issue CREATE, is not
# routinely wrapped for its stdout, so the narrower class is enough and
# stays consistent with that sibling's own choice for the same kind of
# action.
#
# `-R`/`--repo owner/repo` may sit between the verb and the issue number --
# an ordinary, common way to target an issue outside the working tree's own
# repo (exactly the shape a worktree-rooted session reaches for). Requiring
# the number immediately after the verb, with nothing tolerated in between,
# made a `-R`-qualified claim invisible to this matcher entirely -- caught in
# review. The same gap applies to the discharge-side view/api regexes below,
# so the fragment is shared.
RX_REPO_FLAG_GAP = r"(?:(?:-R|--repo)\s+\S+\s+)?"
RX_GH_ISSUE_COMMENT = re.compile(
    r"(?:^|[;&|\n])\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"gh\s+issue\s+comment\s+" + RX_REPO_FLAG_GAP + r"(\d+)\b",
    re.I | re.M,
)
RX_GLAB_ISSUE_NOTE = re.compile(
    r"(?:^|[;&|\n])\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"glab\s+issue\s+note\s+" + RX_REPO_FLAG_GAP + r"(\d+)\b",
    re.I | re.M,
)


def find_claim_targets(command):
    """Yield (number, kind, text, end_pos) for each comment-post command
    position in `command` -- `kind` is "gh" or "glab", `text` is the
    heredoc-stripped command, and `end_pos` is where the issue number ends
    (so the caller can read the rest of that command's own flags)."""
    text = strip_heredocs(command)
    for m in RX_GH_ISSUE_COMMENT.finditer(text):
        yield m.group(1), "gh", text, m.end()
    for m in RX_GLAB_ISSUE_NOTE.finditer(text):
        yield m.group(1), "glab", text, m.end()


# --------------------------------------------------------------------------
# Clause 1b: `glab issue note`'s body -- `-m`/`--message` literal, or
# `-F file`/`--file file` read from disk (the same shape
# `warn-unmeasured-capability-claim.py` documents for `glab mr note`, which
# applies identically to `glab issue note`).
# --------------------------------------------------------------------------

RX_GLAB_MESSAGE_LITERAL = re.compile(
    r"(?:--message|-m)\s+(?:\"((?:[^\"\\]|\\.)*)\"|'([^']*)')", re.S)
RX_GLAB_FILE = re.compile(
    r"(?:-F|--file)[= ]+(?:\"([^\"]+)\"|'([^']+)'|(\S+))")


def _first_group(m):
    return next((g for g in m.groups() if g is not None), None)


def extract_glab_note_body(rest, cwd):
    """The body `glab issue note` would post, read from `rest` (this
    command's own flags), or None if it cannot be determined."""
    m = RX_GLAB_FILE.search(rest)
    if m:
        rel = _first_group(m)
        if not rel or rel == "-":
            return None
        path = rel if os.path.isabs(rel) else os.path.join(cwd, rel)
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                return fh.read()
        except OSError:
            return None
    m = RX_GLAB_MESSAGE_LITERAL.search(rest)
    if m:
        return _first_group(m)
    return None


# --------------------------------------------------------------------------
# Clause 2: does the body carry CLAIM vocabulary?
# --------------------------------------------------------------------------

# Drawn from `claim-pr`'s own claim wording ("is working on this ... please
# hold off") plus the looser phrasing sessions actually use. Deliberately
# lenient -- see "WHY THE CUE LIST IS SCOPED TO CLAIM VOCABULARY" above.
CLAIM_CUE = re.compile(
    r"""(
        claim(?:ing|ed)?\s+this
      | working\s+on\s+this\s+(?:issue|one)?
      | pick(?:ing|ed)?\s+this\s+up
      | grab(?:bing|bed)?\s+this
      | taking\s+this\s+(?:one|issue|up)?
      | I['\u2019]?ll\s+(?:take|work\s+on)\s+this
      | please\s+hold\s+off
    )""",
    re.I | re.X,
)


# --------------------------------------------------------------------------
# Clause 3: has this issue's COMMENTS been read anywhere earlier in the
# transcript?
# --------------------------------------------------------------------------

RX_GH_ISSUE_VIEW = re.compile(
    r"(?:^|[;&|\n])\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"gh\s+issue\s+view\s+" + RX_REPO_FLAG_GAP + r"(\d+)\b",
    re.I | re.M,
)
# "show" is glab's documented alias for "view" (gitlab-org/cli), matching
# `warn-stale-issue-edit.py`'s own precedent for the same alias.
RX_GLAB_ISSUE_VIEW = re.compile(
    r"(?:^|[;&|\n])\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"glab\s+issue\s+(?:view|show)\s+" + RX_REPO_FLAG_GAP + r"(\d+)\b",
    re.I | re.M,
)
# `gh api` accepts `--paginate` and an explicit `-X GET` ahead of the
# endpoint path; either is common enough on a plain comments-read that
# requiring the path to follow `gh api` immediately would miss it, the same
# gap the trigger-side fix above closes for `-R`/`--repo`.
#
# The tolerated `-X` value is deliberately restricted to GET (case-
# insensitively, via the compiled flags below), not `-X\s+\S+` matching any
# verb -- an earlier revision of this line accepted any value, which let
# `gh api -X POST repos/o/r/issues/N/comments --input body.json` (a comment
# POST, not a read) be misclassified as a discharging GET, since the
# body-flag deny-list a few lines down only recognizes the `gh issue
# comment`-shaped body flags reused from flag-uncited-rebuttal.py, not `gh
# api`'s own `--input`/`--input -`. Caught in review.
RX_GH_API_ISSUE_COMMENTS_GET = re.compile(
    r"(?:^|[;&|\n])\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"gh\s+api\s+(?:(?:--paginate|-X\s+GET)\s+)*\S*issues/(\d+)/comments\b",
    re.I | re.M,
)
RX_COMMENTS_FLAG = re.compile(r"(?<![A-Za-z0-9-])--comments\b")
RX_JSON_FLAG = re.compile(r"--json[\s=]+(?:\"([^\"]+)\"|'([^']+)'|(\S+))")


def _json_includes_comments(rest):
    """True when `--json`'s value is a comma-separated field list that
    contains the exact token `comments` -- not a substring match, so
    `--json bodyComments` does not falsely qualify and field order in
    `--json comments,title` / `--json title,comments` does not matter."""
    m = RX_JSON_FLAG.search(rest)
    if not m:
        return False
    value = _first_group(m) or ""
    fields = [f.strip() for f in value.split(",")]
    return "comments" in fields


def command_reads_comments(command, number):
    """True when `command` reads issue `number`'s comments at a command
    position, via any of the CLI shapes this hook recognizes."""
    text = strip_heredocs(command)
    if _command_rest is None:
        return False
    for m in RX_GH_ISSUE_VIEW.finditer(text):
        if m.group(1) != number:
            continue
        rest = _command_rest(text, m.end())
        if RX_COMMENTS_FLAG.search(rest) or _json_includes_comments(rest):
            return True
    for m in RX_GLAB_ISSUE_VIEW.finditer(text):
        if m.group(1) != number:
            continue
        rest = _command_rest(text, m.end())
        if RX_COMMENTS_FLAG.search(rest):
            return True
    for m in RX_GH_API_ISSUE_COMMENTS_GET.finditer(text):
        if m.group(1) != number:
            continue
        rest = _command_rest(text, m.end())
        # A body-write flag on this same URL shape means this occurrence is
        # a POST (the comment-post this hook is about, or an unrelated one),
        # not the GET that reads existing comments.
        if any(rx.search(rest) for rx in
               (RX_BODY_FILE, RX_F_BODY_FILE, RX_F_BODY_LITERAL, RX_BODY_LITERAL)):
            continue
        return True
    return False


def mcp_reads_comments(name, tool_input, number):
    """True when this MCP tool_use is a READ_ISSUE_COMMENTS call for
    `number` -- tool-mappings.yml's `mcp__github__issue_read` with
    `method: get_comments`, or a Cursor-mapped name ending in `issue_read`."""
    if not isinstance(name, str) or not name:
        return False
    if name != "mcp__github__issue_read" and not name.endswith("issue_read"):
        return False
    if not isinstance(tool_input, dict):
        return False
    method = tool_input.get("method")
    if not (isinstance(method, str) and method.lower() == "get_comments"):
        return False
    try:
        blob = json.dumps(tool_input)
    except (TypeError, ValueError):
        blob = str(tool_input)
    num = re.escape(number)
    if re.search(rf"/issues/{num}\b", blob):
        return True
    return bool(re.search(
        rf'"(?:issue_number|issueNumber|number)"\s*:\s*{num}\b', blob))


def transcript_has_comments_read(transcript_path, number):
    """True when some earlier transcript command read issue `number`'s
    comments. Returns True (discharged, silent) on any read failure --
    fail open, matching every sibling hook's own convention."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return True
    if _tool_uses is None or _payload_commands is None:
        return True
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                for name, payload in _tool_uses(entry):
                    if mcp_reads_comments(name, payload, number):
                        return True
                    for text in _payload_commands(payload):
                        if command_reads_comments(text, number):
                            return True
    except OSError:
        return True
    return False


NOTE = """\
No read of issue #{number}'s COMMENTS appears earlier in this session.

Measured on Lacaedemon/sparta#1544 (2026-09-18): a session posted a claim \
after reading only the issue's BODY. The body posed a diagnostic question; \
the issue's comments -- two above the one that got posted -- recorded that \
the diagnosis had already been done and merged, and that the residual had \
been escalated elsewhere. The claim was wasted, so was the draft PR it \
opened, and the correction landed in public.

One command settles it before you claim:

    gh issue view {number} --comments

(or `glab issue view {number} --comments` / \
`gh api repos/<owner>/<repo>/issues/{number}/comments`)

If you have already read the comments another way, carry on --- this is a \
reminder, not a refusal.
"""

UNREADABLE_NOTE = """\
This posts a claim-shaped comment on issue #{number} whose body this check \
cannot read (it comes from a file not yet on disk, from stdin, or from a \
variable), and no read of that issue's COMMENTS appears earlier in this \
session.

Measured on Lacaedemon/sparta#1544 (2026-09-18): a claim posted after \
reading only the issue's body missed a diagnosis and an escalation already \
recorded in the comments. If this comment is a claim, read the comments \
first:

    gh issue view {number} --comments

If you have already read the comments another way, carry on --- this is a \
reminder, not a refusal.
"""


def _emit(note):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": note,
        }
    }))


def _read_payload() -> tuple[dict, bool]:
    """Parse payload from sys.argv (--dry-run / --simulate) or sys.stdin."""
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
    except Exception as exc:
        print(f"warn-claim-without-comments-read: unreadable hook input ({exc})",
              file=sys.stderr)
        return {}, is_dry_run


def main():
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0
    if not isinstance(payload, dict):
        return 0  # fail open: the harness always sends an object

    tool_name = payload.get("tool_name")
    if tool_name not in BASH_TOOL_NAMES:
        return 0

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0

    command = (tool_input.get("command")
               or tool_input.get("cmd")
               or tool_input.get("CommandLine")
               or "")
    if not isinstance(command, str) or not command.strip():
        return 0

    cwd = payload.get("cwd") or os.getcwd()
    transcript = payload.get("transcript_path") or ""

    try:
        notes = []
        for number, kind, text, end in find_claim_targets(command):
            rest = _command_rest(text, end) if _command_rest else text[end:]

            if kind == "gh" and extract_body_text is not None:
                body = extract_body_text(rest, cwd)
            elif kind == "glab":
                body = extract_glab_note_body(rest, cwd)
            else:
                body = None

            if body is not None and not CLAIM_CUE.search(body):
                continue  # readable and not claim-shaped: not this hook's concern

            if transcript_has_comments_read(transcript, number):
                continue

            template = NOTE if body is not None else UNREADABLE_NOTE
            notes.append(template.format(number=number))

        if notes:
            _emit("\n\n".join(notes))
        return 0
    except Exception as exc:  # fail open on any parse trouble
        print(f"warn-claim-without-comments-read: could not evaluate ({exc})",
              file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
