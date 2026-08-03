#!/usr/bin/env python3
"""Stop-hook guard: catch opening a PR without requesting a reviewer.

Opening a PR auto-triggers the repo's *own* review workflow, so review
genuinely is in motion -- for that half. It does NOT summon Copilot, which
reviews only when explicitly requested. The auto-triggered half running is
exactly what disguises the missing half: the PR shows review-shaped activity
in its checks while no reviewer has read the diff.

That matters more here than in most repos, because `claude-review` on this
repo's own PRs has failed on every run that actually attempted a review this
session (ai-config#897). Whatever the cause -- #897 calls prompt overflow only
the leading hypothesis, states the literal error is unconfirmed, and reports
15 successful runs on six other branches -- the observed effect stands on its
own: when it fails, Copilot is the only working reviewer, so a PR opened
without an explicit request gets no review at all.

The condition is exactly decidable from the transcript, which is why this is
a hook rather than a rule to remember:

    a PR was created or marked ready this session
    AND no reviewer request came after it

Correlation is by tool_use identity, not by position or by a scalar
timestamp. Three facts make that necessary, each an independently-reproduced
bug in the position/timestamp model this replaces:

  * A `gh pr create` command cannot carry its own PR number -- the number
    only appears in the command's RESULT. So the open is keyed from its
    result (URL or `number` field), by tool_use id, not from the command.
  * A reviewer request is discharged only by ITS OWN successful result,
    matched by tool_use id -- not by the first result in a batch, which may
    belong to an unrelated tool.
  * A read of the `requested_reviewers` endpoint (a GET) is not a request;
    only a mutating POST (or a `--reviewer`/`--add-reviewer`/
    `request_copilot_review` form) discharges the obligation.

Obligations carry owner/repo when the transcript provides it, so the same PR
number in two repositories is two obligations, not one.

Fails OPEN on any parse trouble, and fires at most once per distinct message
per transcript, so it cannot wedge a session.
"""
import hashlib
import json
import os
import re
import shlex
import sys
import tempfile

# Opening a PR, or taking a draft out of draft, via the CLI. The structured
# harness/MCP tools are matched by NAME below, not by this pattern -- a
# command string never contains `create_pull_request`, but a doc that quotes
# it would, which is the heredoc false positive README.md:265-271 warns about.
RX_OPEN = re.compile(r"gh\s+pr\s+(?:create|ready)\b", re.I)

# Marking a PR draft is a deliberate reason NOT to request review yet: a draft
# does not trigger the review bot, per shared/workflow/pr-on-claim.md. Only a
# *later* ready/create re-arms the guard.  `gh pr ready --undo` converts a
# ready PR BACK to draft, so it counts as a draft action even though it also
# matches RX_OPEN -- the draft branch is checked first below.
RX_DRAFT = re.compile(
    r"\"?draft\"?\s*[:=]\s*true|--draft\b|gh\s+pr\s+ready[^|;&]*--undo",
    re.I,
)

# A gh action must be an actual command word, not a string quoted inside a
# DIFFERENT command's argument. This repo's own docs and this hook's own
# recovery text are full of literal `gh pr create` / `requested_reviewers -X
# POST` examples, so a `gh pr comment --body "... gh pr create ..."` would
# otherwise forge an obligation, and a `--body "... requested_reviewers -X
# POST ..."` would silently DISCHARGE a real one -- the exact false negative
# this hook exists to catch (the README.md:265-271 heredoc trap, one layer in
# from the non-shell-tool case).
#
# Open/draft detection and request detection defend against that differently,
# because they key on structurally different things:
#
#   * RX_OPEN/RX_DRAFT key on `gh pr create`/`ready`, always a LEADING command
#     word, never legitimately inside quotes. So for them every quoted span is
#     blanked (`_scrub_all`) before matching -- that neutralises an example
#     create quoted in a `--body` AND a bare `echo "gh pr create"`, with no
#     risk to a real open, whose command word is never quoted.
#   * Request detection keys on `requested_reviewers`/`-X POST`, which are the
#     STRUCTURAL argv of the hook's OWN recovery command
#     (`gh api "repos/o/r/pulls/N/requested_reviewers" -X POST`) -- double-
#     quoting a `gh api` URL is standard shell, so blanking every quote there
#     erases a genuine request and the hook nags forever after the user does
#     exactly what it asked (round 4's regression). But those same tokens also
#     appear inside ordinary string arguments -- `echo "... -X POST"`, a
#     `gh pr comment` body, a heredoc/herestring -- where they are NOT a
#     request. Blanking only known payload flags (round 5) missed every other
#     embedding mechanism. So request detection instead PARSES the command into
#     simple commands and inspects each one's argv (`request_ident`), matching
#     the request tokens only when they are the argv of an actual `gh api`/
#     `gh pr edit`/`gh pr create` invocation -- never the value of a string
#     argument. That closes the class rather than the next instance of it.
#
# Over-blanking (open/draft) only ever DROPS a match -- a missed obligation,
# the fail-open direction -- never forges or discharges one. Request parsing
# fails toward NOT-a-request (a shlex error or unrecognised form leaves the
# obligation outstanding and the hook warns), so it never silently discharges.
RX_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1.*?\n[ \t]*\2\b", re.S)


def _scrub_all(cmd):
    """Blank heredoc bodies and EVERY quoted span (safe for RX_OPEN only)."""
    cmd = RX_HEREDOC.sub("<<", cmd)
    cmd = re.sub(r'"(?:[^"\\]|\\.)*"', '""', cmd)
    cmd = re.sub(r"'[^']*'", "''", cmd)
    return cmd


# --- Structural reviewer-request detection --------------------------------
# `requested_reviewers`/`-X POST`/`--add-reviewer` are matched against the
# argv of parsed simple commands, never as substrings of the raw string, so an
# example request embedded in any string argument (echo, a comment body, a
# heredoc or herestring) is never mistaken for a real request. Verified
# against `gh --help`: `gh pr create --reviewer` and `gh pr edit
# --add-reviewer` exist; `gh pr review --request` does NOT (review has only
# --approve/--comment/--request-changes), so it is deliberately absent.

# Shell CONTROL operators that separate one simple command from the next:
# `;`, `&`/`&&`, `|`/`||`, `(`, `)` -- and a newline, handled below. Redirection
# operators (`<`, `>`, `>>`, `2>&1`) are deliberately EXCLUDED: a redirect
# attaches to the command it decorates rather than terminating it, so treating
# `>` as a separator split a genuinely-sole request with a trailing `> /dev/null`
# into two "commands", flipped its `last` flag to False, and left it permanently
# undischargeable (a severe over-warn). A `>`/`<` token now falls through into
# the current command's argv, where the request/draft detectors ignore it.
_SHELL_OPS = set("();|&")


def _simple_commands(cmd):
    """Split a shell command into simple-command argv lists; None on error.

    Line-continuations are joined and heredoc bodies blanked first, so shlex
    neither chokes on a heredoc body nor mis-splits a `\\`-continued request
    (like the hook's own recovery command) into two commands.

    An unescaped newline is a genuine command separator, but shlex treats it as
    whitespace and silently drops it -- which merged two commands on two lines
    into one, making a trailing command's exit status masquerade as the
    request's own `last` outcome and SILENTLY DISCHARGE a failed request (the
    dangerous direction). Multi-line Bash is the ordinary shape agents emit, so
    remaining newlines are converted to `;`. A newline INSIDE a quoted string
    becomes a `;` inside that quote -- a literal character in one token, not a
    separator -- so a multi-line `--body` is not split (and its contents are
    never argv the detectors read anyway).
    """
    cmd = re.sub(r"\\\r?\n", " ", cmd)   # join `\`-continued lines
    cmd = RX_HEREDOC.sub("<<", cmd)       # drop heredoc bodies
    cmd = cmd.replace("\n", ";")          # unquoted newline -> separator
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        return None                       # unbalanced quotes, etc.
    cmds, cur = [], []
    for t in toks:
        if t and set(t) <= _SHELL_OPS:    # a control-operator token (||, |, ;, &)
            if cur:
                cmds.append(cur)
                cur = []
        else:
            cur.append(t)
    if cur:
        cmds.append(cur)
    return cmds


def _has_flag(argv, *flags):
    """True if argv contains any of `flags`, as a bare token or `flag=value`."""
    for a in argv:
        if a in flags or any(a.startswith(f + "=") for f in flags):
            return True
    return False


def _post_method(argv):
    """True if argv sets the HTTP method to POST (a mutating request)."""
    for i, a in enumerate(argv):
        au = a.upper()
        if au in ("-X", "--METHOD") and i + 1 < len(argv) \
                and argv[i + 1].upper() == "POST":
            return True
        if au == "-XPOST":
            return True
        if au.startswith("--METHOD=") and au.split("=", 1)[1] == "POST":
            return True
    return False


def _url_ident(url):
    """(num, repo) from a `repos/o/r/pulls/N/...` token; RX_CMD_API is below."""
    m = RX_CMD_API.search(url)
    if m:
        return m.group(3), f"{m.group(1)}/{m.group(2)}"
    return None, None


def _verb_ident(argv):
    """(num, repo) from a `gh pr edit <N> ... -R o/r` argv."""
    num = argv[3].lstrip("#") if len(argv) >= 4 \
        and argv[3].lstrip("#").isdigit() else None
    repo = None
    for i, a in enumerate(argv):
        if a in ("-R", "--repo") and i + 1 < len(argv):
            repo = argv[i + 1]
        elif a.startswith("--repo="):
            repo = a.split("=", 1)[1]
    return num, repo


def _argv_request(argv):
    """(is_request, num, repo) for one simple command's argv.

    Identity comes from the request command ITSELF -- the `gh api` URL, or the
    `gh pr edit` number/`-R` -- so a different PR path echoed earlier in the
    line cannot misdirect the discharge. `-r` (reviewer) differs from `-R`
    (repo) only by case, and argv tokens are matched case-sensitively, so the
    two never collide.
    """
    if not argv:
        return False, None, None
    a0 = argv[0]
    if a0 == "gh" and len(argv) >= 3 and argv[1] == "pr":
        sub, rest = argv[2], argv[3:]
        if sub == "create" and _has_flag(rest, "--reviewer", "-r"):
            return True, None, None       # a create's number is in its result
        if sub == "edit" and _has_flag(rest, "--add-reviewer"):
            num, repo = _verb_ident(argv)
            return True, num, repo
    # `gh api`/`curl`/`wget` hitting the requested_reviewers endpoint with a
    # POST. The same endpoint is read via GET (to CHECK who is requested), and
    # a GET must NOT discharge, which is why the method is required.
    api = (a0 == "gh" and len(argv) >= 2 and argv[1] == "api") \
        or a0 in ("curl", "wget")
    if api:
        url = next((t for t in argv if "requested_reviewers" in t), None)
        if url and _post_method(argv):
            num, repo = _url_ident(url)
            return True, num, repo
    return False, None, None


def request_ident(cmd):
    """(is_request, num, repo, last): does `cmd` genuinely request a reviewer?

    `last` is True when the matched request is the LAST simple command in the
    chain. That is exactly when the harness `is_error` exit status (which
    reflects the WHOLE call, i.e. its last command) is authoritative for the
    request's own outcome -- so the discharge can trust `err` only then. A
    request chained AHEAD of other commands has an is_error that belongs to a
    later command, so the discharge treats it as ambiguous and does not fire.
    """
    cmds = _simple_commands(cmd)
    if cmds is None:
        return False, None, None, False
    for i, argv in enumerate(cmds):
        ok, num, repo = _argv_request(argv)
        if ok:
            return True, num, repo, (i == len(cmds) - 1)
    return False, None, None, False


def _argv_draft(argv):
    """(is_draft, num, repo) for one simple command's argv: a draft transition.

    Structural and gh-SCOPED, exactly like _argv_request: a `--draft` token
    counts as a draft action ONLY as the flag of an actual `gh` invocation of
    the right shape -- never as a bare token in an UNRELATED command (a `--body`
    value, a different subcommand's argument). Without that scope, a failed
    `gh pr ready --undo` chained ahead of an unrelated command whose argv merely
    CONTAINS a `--draft`/`draft=true` token (`... ; gh pr comment N --body
    "draft=true"`, or a follow-up `gh pr create --draft`) is misread as the
    transition being last, silently discharging a still-ready PR -- the exact
    silent-discharge class every prior round blocked.

    Only the two shell forms that genuinely change draft state are matched:
    `gh pr ready [<N>] --undo` (ready -> draft) and `gh pr create --draft` (a
    new draft). A `gh api ... -f draft=true` is deliberately NOT matched: the
    REST `PATCH /pulls/{n}` endpoint does not accept `draft` (title/body/state/
    base/maintainer_can_modify only), so such a call does NOT convert a PR to
    draft -- treating it as one would discharge the obligation on a no-op
    success, silently clearing a still-ready PR. A real toggle is GraphQL
    (convert/markReady), which `gh pr ready` wraps and which this matches above.

    Identity comes from the draft command ITSELF, so a decoy PR verb elsewhere
    in the line (`gh pr comment 42 ... ; gh pr ready 1038 --undo`) cannot
    misdirect the clear onto the wrong PR.
    """
    if not argv or argv[0] != "gh":
        return False, None, None
    # `gh pr ready [<N>] --undo` converts a ready PR BACK to draft.
    if len(argv) >= 3 and argv[1] == "pr" and argv[2] == "ready" \
            and _has_flag(argv[3:], "--undo"):
        num, repo = _verb_ident(argv)
        return True, num, repo
    # `gh pr create --draft` opens a NEW draft PR (a draft action for ordering);
    # like any create, its number is in the result, not the command.
    if len(argv) >= 3 and argv[1] == "pr" and argv[2] == "create" \
            and _has_flag(argv[3:], "--draft"):
        return True, None, None
    return False, None, None


def draft_ident(cmd):
    """(is_draft, num, repo, last): does `cmd` perform a draft transition, and
    is that transition the LAST simple command?

    Mirrors request_ident exactly: it locates the draft action STRUCTURALLY (the
    first simple command that is a gh draft invocation) and reports whether THAT
    command is last -- which is exactly when the harness is_error (the whole
    call's exit status) is authoritative for the transition's own outcome. A
    draft action chained AHEAD of another command has an is_error belonging to a
    later command, so the discharge treats it as AMBIGUOUS and keeps the PR
    tracked (the safe over-warn direction). Fails toward not-a-draft on a parse
    error, so it never fabricates a clear.
    """
    cmds = _simple_commands(cmd)
    if cmds is None:
        return False, None, None, False
    for i, argv in enumerate(cmds):
        ok, num, repo = _argv_draft(argv)
        if ok:
            return True, num, repo, (i == len(cmds) - 1)
    return False, None, None, False


def _argv_open(argv):
    """(is_open, num, repo) for one simple command's argv: a create/ready open.

    Structural and gh-SCOPED, exactly like _argv_draft/_argv_request. Identity
    comes from the open command ITSELF, so a decoy PR verb earlier in a chained
    command (`gh pr view 42 && gh pr ready`) cannot misattribute the obligation's
    number. A `gh pr create`'s number is never in the command -- it comes from
    the result -- so num is None for create; a `gh pr ready [<N>]` carries a
    number only when one is given explicitly (a bare `gh pr ready` yields None,
    backfilled from the ready command's own `owner/repo#N` result).
    """
    if not argv or argv[0] != "gh" or len(argv) < 3 or argv[1] != "pr":
        return False, None, None
    if argv[2] == "create":
        _, repo = _verb_ident(argv)
        return True, None, repo          # a create's number is in its result
    if argv[2] == "ready":
        num, repo = _verb_ident(argv)
        return True, num, repo
    return False, None, None


def open_ident(cmd):
    """(num, repo) from the actual `gh pr create`/`gh pr ready` simple command.

    Mirrors draft_ident/request_ident: the OPEN identity is located
    structurally from the create/ready command, never from the whole raw string.
    A whole-string search (the old cmd_ident) matched a decoy PR number from an
    unrelated verb chained ahead (`gh pr checks 1029 && gh pr ready`), mislabeled
    the obligation, and let a later unrelated request for that decoy PR silently
    discharge the real one. Returns (None, None) when no open command carries a
    number -- the bare `gh pr ready` case -- so the number backfills from the
    open's own result instead. Fails toward no-identity on a parse error.
    """
    cmds = _simple_commands(cmd)
    if cmds is None:
        return None, None
    for argv in cmds:
        ok, num, repo = _argv_open(argv)
        if ok:
            return num, repo
    return None, None


# Tools whose input is a SHELL COMMAND. Matching CLI patterns against any
# other tool's serialized input is the documentation/heredoc false positive
# README.md:265-271 warns about -- self-demonstrating here, since these very
# hook files contain the strings `gh pr create` and `requested_reviewers`.
SHELL_TOOLS = {"Bash", "bash", "run_command"}

# Structured PR tools, matched on the tool NAME with arguments read as fields.
OPEN_TOOLS = {"create_pull_request", "mcp__github__create_pull_request"}
EDIT_TOOLS = {"update_pull_request", "mcp__github__update_pull_request"}
REQ_TOOLS = {"request_copilot_review", "mcp__github__request_copilot_review"}

# A PR API path (`repos/o/r/pulls/1038`) inside a shell command, used by
# _url_ident to read identity from a request command's own `gh api` URL. Open,
# draft, and request identity are all resolved STRUCTURALLY from the specific
# simple command (open_ident/draft_ident/request_ident), never from a
# whole-string scan -- a decoy PR number chained ahead would otherwise mislabel
# the obligation (see open_ident).
RX_CMD_API = re.compile(r"repos/([\w.-]+)/([\w.-]+)/pulls?/(\d+)", re.I)

# A PR identity carried by a tool RESULT: the PR URL (owner/repo/number), gh's
# `Pull request owner/repo#N` success line, or a bare `"number"` field.
RX_RES_URL = re.compile(r"github\.com/([\w.-]+)/([\w.-]+)/pull/(\d+)", re.I)
RX_RES_API = re.compile(r"repos/([\w.-]+)/([\w.-]+)/pulls?/(\d+)", re.I)
# `gh pr ready`/`gh pr create` print `... Pull request owner/repo#N ...` (e.g.
# `Pull request o/r#42 is marked as "ready for review"`). A BARE `gh pr ready`
# (no number -- the ordinary way to ready the current branch's PR) carries no
# number in the command, so open_ident yields None and the obligation is
# appended with num=None. Without recognizing this result shape the number never
# backfills, and _clear() (which refuses to touch a num=None obligation) can
# never discharge it -- a bare `gh pr ready` would then block every message for
# the rest of the session, contradicting the "cannot wedge a session" invariant.
RX_RES_HASH = re.compile(r"[Pp]ull [Rr]equest\s+([\w.-]+)/([\w.-]+)#(\d+)")
RX_RES_NUM = re.compile(r"\\?\"number\\?\"\s*:\s*(\d+)")

# A tool result that reports failure. Kept specific: a bare 4xx substring
# matches PR numbers like 422 or a `/pull/430` URL, so failure is keyed on an
# HTTP-status shape or an explicit error word, plus the harness `is_error`
# flag when present.
RX_FAILED = re.compile(
    r"\\?\"status\\?\"\s*:\s*4\d\d|HTTP\s+4\d\d|\berror\b|\bfailed\b"
    r"|cannot be requested|not found",
    re.I,
)

# A request discharge must NOT be blocked by an UNRELATED command's failure
# text chained into the same Bash call (`some_check; gh api ... POST`, or
# `<request> || echo done`). RX_FAILED above matches generic `error`/`failed`/
# `not found` -- ordinary shell noise -- so a successful request sharing a
# result body with such text would nag forever. The discharge therefore keys
# on this NARROWER signal: an actual API-failure SHAPE (a 4xx status or GitHub's
# "cannot be requested"), plus the tool call's own is_error exit status. A
# genuinely failed `gh api`/`gh pr edit` request exits non-zero (is_error) or
# returns a 4xx, so this still catches every real failure without firing on a
# neighbouring command's stderr.
# The `\\?\"` before/after `status` tolerates the escaped-quote shape a string
# tool-result body takes once `json.dumps()` wraps it (`\"status\":422`), as
# well as an unescaped `"status":422`; without it this 4xx alternative was dead
# for the ordinary string-content case and only `HTTP 4\d\d`/`is_error` caught a
# failure. Mirrors RX_RES_NUM's `\\?\"` handling.
RX_REQ_FAILED = re.compile(
    r"\\?\"status\\?\"\s*:\s*4\d\d|HTTP\s+4\d\d|cannot be requested",
    re.I,
)


def input_ident(inp):
    """(num, repo) from a structured tool's input fields."""
    num = inp.get("pullNumber") or inp.get("pull_number")
    num = str(num) if num is not None else None
    owner, rp = inp.get("owner"), inp.get("repo")
    repo = f"{owner}/{rp}" if owner and rp else None
    return num, repo


def result_ident(body):
    """(num, repo) parsed from a tool_result body string."""
    m = RX_RES_URL.search(body) or RX_RES_API.search(body) \
        or RX_RES_HASH.search(body)
    if m:
        return m.group(3), f"{m.group(1)}/{m.group(2)}"
    m = RX_RES_NUM.search(body)
    if m:
        return m.group(1), None
    return None, None


def _repo_ok(a, b):
    return a is None or b is None or a == b


def _clear(obligations, num, repo):
    """Remove the best obligation a (num, repo) discharges, if any.

    Matches on PR number, preferring an exact owner/repo match over one where
    a side's repo is unknown. It deliberately does NOT clear an obligation
    whose own number is still unresolved: that would let a request for one PR
    silently discharge a different, unidentified one. A create's number is read
    from its result before any request could target it, so a resolved
    obligation is the normal state, and an unresolved one means a genuinely
    unparseable result -- which stays outstanding rather than being cleared by
    an unrelated request.
    """
    best, best_rank = None, 99
    for idx, ob in enumerate(obligations):
        if ob["num"] is not None and num is not None and ob["num"] == num \
                and _repo_ok(ob["repo"], repo):
            rank = 0 if (ob["repo"] and repo) else 1
            if rank < best_rank:
                best, best_rank = idx, rank
    if best is not None:
        obligations.pop(best)


def scan(path):
    """Return (obligations, text).

    `obligations` is a list of {"num", "repo", "tid", "self"} records, one per
    non-draft PR opened whose reviewer request has not been discharged.
    Tracked as a list (not a scalar timestamp or a number-keyed dict) so that
    two PRs, or the same number in two repositories, are two obligations.
    """
    obligations = []
    pending = {}        # tool_use_id -> (num, repo) for reviewer requests
    pending_clear = {}  # tool_use_id -> (num, repo) for draft transitions
    text = ""
    with open(path, errors="ignore") as fh:
        for line in fh:
            try:
                m = json.loads(line)
            except Exception:
                continue
            blocks = (m.get("message") or {}).get("content") or []
            if not isinstance(blocks, list):
                continue
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                kind = b.get("type")

                if kind == "tool_result":
                    rid = b.get("tool_use_id")
                    body = json.dumps(b.get("content") or "")
                    err = bool(b.get("is_error"))
                    failed = err or bool(RX_FAILED.search(body))
                    rnum, rrepo = result_ident(body)
                    # Resolve the open that produced this result.
                    keep = []
                    for ob in obligations:
                        if ob["tid"] != rid:
                            keep.append(ob)
                            continue
                        # `failed` is one flag over the WHOLE result body, but a
                        # single call can pair opening a PR with requesting a
                        # reviewer (`gh pr create --reviewer` whose reviewer step
                        # 422s, or `update_pull_request(draft=False,
                        # reviewers=[...])` whose reviewer-add fails). A failure
                        # there must not be read as the PR never existing:
                        #   * failed, NOT a self create+reviewers obligation, AND
                        #     the PR's identity is STILL unknown (never in the
                        #     input, not in this result) -> the open itself is what
                        #     failed, no PR exists to track, so drop it. This is a
                        #     plain `create_pull_request`/`gh pr create`, whose
                        #     number is only ever learned from the result -- a
                        #     create that failed without yielding a number yielded
                        #     no PR.
                        #   * failed BUT the PR's identity is known -- resolved
                        #     here (a URL/number in the result) OR already known
                        #     from the input (`update_pull_request`'s
                        #     `pull_number`, populated at append time) -> the PR
                        #     is real and its reviewer step is what failed, so
                        #     keep tracking it and let the `self` check below hold
                        #     it outstanding. Dropping a known-identity obligation
                        #     on a bare `{"status":422}` body (no number echoed --
                        #     the ordinary error shape) would silently clear a PR
                        #     that was genuinely marked ready with no reviewer.
                        #   * failed AND self (a create+reviewers: `gh pr create
                        #     --reviewer`, `create_pull_request(reviewers=[...])`)
                        #     -> its number is NEVER known at append time, so a
                        #     numberless failure body cannot distinguish "the
                        #     create failed, no PR" from "the PR was created and
                        #     only the reviewer step failed". Dropping would
                        #     silently discharge a genuinely-created, unreviewed
                        #     PR (the dangerous direction), so it is NOT dropped
                        #     here: it falls through to the `self` check below and
                        #     stays outstanding. The cost is a rare unclearable
                        #     (num-None) obligation when the create truly failed --
                        #     a safe over-warn, per shared/principles/fail-fast.md,
                        #     chosen over a silent discharge.
                        if failed and rnum is None and ob["num"] is None \
                                and not ob["self"]:
                            continue
                        if ob["num"] is None and rnum:
                            ob["num"] = rnum
                        if ob["repo"] is None and rrepo:
                            ob["repo"] = rrepo
                        # A create --reviewer (self) discharges only when its
                        # result did NOT fail: a reviewer request that 422'd on
                        # an otherwise-created PR leaves the PR unreviewed, so
                        # the obligation must stay outstanding.
                        if ob["self"] and not failed:
                            continue
                        keep.append(ob)
                    obligations[:] = keep
                    # Discharge the reviewer request that produced this result.
                    # A discharge is the DANGEROUS action -- it asserts the PR
                    # got its reviewer -- so it fires only on POSITIVE evidence
                    # the request itself succeeded, never merely on the absence
                    # of failure text.
                    #
                    # The one reliable success signal is the harness `is_error`
                    # exit status, but it is the exit status of the WHOLE Bash
                    # call -- its LAST simple command -- so it is authoritative
                    # for the request ONLY when the request is that last command
                    # (`last`), or when the call is a single structured tool
                    # (atomic, recorded with last=True). A request chained AHEAD
                    # of anything else has an is_error belonging to a later
                    # command, and no other signal recovers the request's own
                    # outcome from the one combined result blob -- RX_REQ_FAILED
                    # catches a 4xx body but not a network error, a timeout, a
                    # 5xx, or a GraphQL/auth failure. Such a call is therefore
                    # AMBIGUOUS, and the guard fails toward NOT discharging (it
                    # keeps blocking -- the safe over-warn direction) rather than
                    # risk silently clearing a genuinely-failed request.
                    #
                    # So discharge only a last/atomic request whose own result
                    # neither errored nor carries a 4xx failure body.
                    if rid in pending:
                        rnum2, rrepo2, last2 = pending.pop(rid)
                        req_failed = (not last2) or err \
                            or bool(RX_REQ_FAILED.search(body))
                        if not req_failed:
                            _clear(obligations, rnum2 or rnum, rrepo2 or rrepo)
                    # A deferred draft transition clears its PR only on POSITIVE
                    # evidence the transition itself succeeded -- a clear is the
                    # DANGEROUS action (it asserts the PR is now a draft and
                    # needs no reviewer), so it obeys the same fail-safe rule the
                    # reviewer-request discharge above does.
                    #
                    # `is_error`/`failed` is the WHOLE call's exit status, so it
                    # is authoritative for the transition ONLY when the draft
                    # action is the last simple command (`clast`) or an atomic
                    # structured tool. A `gh pr ready --undo` that genuinely
                    # fails but is chained AHEAD of a succeeding command (e.g.
                    # `... --undo; echo done`, or `... --undo || true`) has an
                    # is_error belonging to that later command -- so such a call
                    # is AMBIGUOUS and must NOT discharge (keep the PR tracked --
                    # the safe over-warn direction), never silently clear a
                    # still-ready, unreviewed PR.
                    #
                    # For the last/atomic case the BROAD `failed` (not the
                    # narrower RX_REQ_FAILED the request side uses) is
                    # deliberate: for a clear, over-warning is the SAFE direction,
                    # so a broader failure signal is strictly safer here -- per
                    # shared/principles/fail-fast.md, prefer keeping the over-warn
                    # rather than narrowing it to cut nags.
                    if rid in pending_clear:
                        cnum, crepo, clast = pending_clear.pop(rid)
                        clear_failed = (not clast) or failed
                        if not clear_failed:
                            _clear(obligations, cnum, crepo)
                    continue

                if kind != "tool_use":
                    if kind == "text" and m.get("type") == "assistant":
                        if b.get("text", "").strip():
                            text = b["text"]
                    continue

                name = b.get("name") or ""
                tid = b.get("id")
                inp = b.get("input")
                if not isinstance(inp, dict):
                    inp = {}

                if name in OPEN_TOOLS:
                    if not inp.get("draft"):
                        num, repo = input_ident(inp)
                        obligations.append({"num": num, "repo": repo,
                                            "tid": tid,
                                            "self": bool(inp.get("reviewers"))})
                    continue
                if name in EDIT_TOOLS:
                    num, repo = input_ident(inp)
                    if inp.get("draft") is True:
                        # Converting a ready PR back to draft defers review, but
                        # only if it SUCCEEDS. Clearing at tool_use time would
                        # forget a still-ready PR when the transition fails, so
                        # defer the clear to this call's own non-failed result.
                        # A structured tool is atomic -- one tool_use, one result
                        # -- so is_error reflects THIS transition: last=True.
                        pending_clear[tid] = (num, repo, True)
                    elif inp.get("draft") is False:
                        obligations.append({"num": num, "repo": repo,
                                            "tid": tid,
                                            "self": bool(inp.get("reviewers"))})
                    if inp.get("reviewers") and inp.get("draft") is not False:
                        # A structured tool call is atomic -- one tool_use, one
                        # result -- so is_error reflects THIS request, with no
                        # chained command to poison it: last=True -> trust err.
                        #
                        # But NOT when draft is False: that branch already
                        # appended a `self` obligation, whose discharge/keep is
                        # decided in the obligations loop by the BROAD `failed`
                        # (success -> discharge via the `self and not failed`
                        # drop; failure -> keep). Also registering `pending[tid]`
                        # here would add a SECOND discharge path for the same
                        # tid, keyed on the NARROWER RX_REQ_FAILED, that runs
                        # AFTER the obligations loop and `_clear()`s the very
                        # obligation the broad check just kept -- so a
                        # reviewer-add failing with plain-language text
                        # ("failed"/"error"/"not found") and no 4xx/HTTP shape,
                        # with is_error unset, would silently discharge a
                        # genuinely-unreviewed PR. The self-obligation path is
                        # sufficient and fail-safe on its own; the pending path
                        # is reserved for a reviewer-add with NO draft:false
                        # transition (a request against an already-ready PR).
                        pending[tid] = (num, repo, True)
                    continue
                if name in REQ_TOOLS:
                    rn, rr = input_ident(inp)
                    pending[tid] = (rn, rr, True)  # atomic; is_error is trusted
                    continue
                if name not in SHELL_TOOLS:
                    continue  # never text-match a non-shell tool

                cmd_raw = inp.get("command") or ""
                # DETECTION (is this an open/draft?) blanks EVERY quote, since
                # `gh pr create`/`ready` is always a leading command word and a
                # quoted example must not forge an obligation. IDENTITY (which
                # PR) is resolved STRUCTURALLY from the specific simple command
                # by open_ident/draft_ident/request_ident -- never a whole-string
                # scan, which matched a decoy PR number chained ahead
                # (`gh pr view 42 && gh pr ready`) and mislabeled the obligation.
                cmd_open = _scrub_all(cmd_raw)
                draft = bool(RX_DRAFT.search(cmd_open))
                opened = bool(RX_OPEN.search(cmd_open)) and not draft
                onum, orepo = open_ident(cmd_raw)
                requested, rnum, rrepo, rlast = request_ident(cmd_raw)
                _dok, dnum, drepo, dlast = draft_ident(cmd_raw)
                # Draft is checked first: `gh pr ready --undo` matches RX_OPEN
                # too, and it is the draft action that decides. The clear is
                # deferred to the command's own non-failed result: a `gh pr
                # ready --undo` that fails leaves the PR ready, so clearing at
                # tool_use time would silently forget it.
                if draft:
                    # Identity and `last` come from the draft command ITSELF
                    # (draft_ident): a decoy PR verb earlier in the line cannot
                    # misdirect the clear onto the wrong PR, and a draft chained
                    # AHEAD of another command is seen as not-last (dlast=False),
                    # so the clear is withheld (is_error ambiguous). A draft form
                    # draft_ident does not resolve leaves dnum=None/dlast=False,
                    # which never clears -- the safe over-warn direction.
                    pending_clear[tid] = (dnum, drepo, dlast)
                elif opened:
                    obligations.append({"num": onum, "repo": orepo, "tid": tid,
                                        "self": requested})
                # A create --reviewer both opens and requests; its `self` flag
                # discharges it on the create's own result, so it is not also a
                # separate pending request here.
                if requested and not opened:
                    pending[tid] = (rnum, rrepo, rlast)
    return obligations, text


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        transcript = payload.get("transcript_path") or ""
        obligations, text = scan(transcript)
    except Exception:
        return 0  # fail open

    if not text or not obligations:
        return 0

    named = sorted({o["num"] for o in obligations if o["num"]}, key=int)
    which = ", ".join("#" + n for n in named) if named else "a PR"

    # Sentinel scoped to this transcript AND this message, so a later session
    # ending with the same recap text does not silently skip the guard.
    key = hashlib.sha256(
        (transcript + "\0" + text + "\0" + which).encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-unreviewed-pr-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    print(json.dumps({
        "decision": "block",
        "reason": (
            f"You opened or readied {which} in this session and no SUCCESSFUL "
            "reviewer request follows for it.\n\n"
            "Opening a PR auto-triggers the repo's own review workflow but "
            "does NOT summon Copilot, which reviews only when explicitly "
            "requested. The auto-triggered half is what disguises this: the "
            "PR shows review-shaped activity while nothing has read the "
            "diff.\n\n"
            "Request it now, in this same message. Quote every placeholder -- "
            "an unquoted `<` is a shell redirect:\n\n"
            "    gh api \"repos/<owner>/<repo>/pulls/<N>/requested_reviewers\" "
            "\\\n      -X POST -f "
            "'reviewers[]=copilot-pull-request-reviewer[bot]'\n\n"
            "Then verify a review actually lands at the current head -- the "
            "request itself can 422, and a pending request can vanish from "
            "both `reviewRequests` and the GET endpoint (see "
            "memories/github.md):\n\n"
            "    gh pr view \"<N>\" --json reviews \\\n"
            "      --jq '[.reviews[] | select(.author.login | "
            "startswith(\"copilot\"))] | length'\n\n"
            "If the PR is deliberately a DRAFT, that is a legitimate reason to "
            "defer -- a draft does not trigger the review bot (see "
            "shared/workflow/pr-on-claim.md). Say so explicitly.\n\n"
            "Writing \"review owed\" into a recap does not discharge this."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
