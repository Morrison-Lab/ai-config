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

# The quoted value of a free-text payload flag. Used only for cmd_ident's
# identity on a REAL open/draft command (`gh pr ready N`, `-R o/r`), so a
# `--body` mentioning a `pulls/N` path cannot forge a draft-clear target.
RX_PAYLOAD = re.compile(
    r"((?:--body|--title|--notes|--message|-b|-t|-m)[=\s]+)"
    r"(\"(?:[^\"\\]|\\.)*\"|'[^']*')"
)


def _scrub_payload(cmd):
    """Blank heredoc bodies and free-text payload-flag values only."""
    cmd = RX_HEREDOC.sub("<<", cmd)
    return RX_PAYLOAD.sub(lambda m: m.group(1) + '""', cmd)


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

# Shell control operators that separate one simple command from the next.
_SHELL_OPS = set("();<>|&")


def _simple_commands(cmd):
    """Split a shell command into simple-command argv lists; None on error.

    Line-continuations are joined and heredoc bodies blanked first, so shlex
    neither chokes on a heredoc body nor mis-splits a `\\`-continued request
    (like the hook's own recovery command) into two commands.
    """
    cmd = re.sub(r"\\\r?\n", " ", cmd)   # join `\`-continued lines
    cmd = RX_HEREDOC.sub("<<", cmd)       # drop heredoc bodies
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        return None                       # unbalanced quotes, etc.
    cmds, cur = [], []
    for t in toks:
        if t and set(t) <= _SHELL_OPS:    # an operator token (||, |, ;, <<<)
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
    """(is_request, num, repo, api) for one simple command's argv.

    Identity comes from the request command ITSELF -- the `gh api` URL, or the
    `gh pr edit` number/`-R` -- so a different PR path echoed earlier in the
    line cannot misdirect the discharge. `-r` (reviewer) differs from `-R`
    (repo) only by case, and argv tokens are matched case-sensitively, so the
    two never collide.

    `api` is True only for the `gh api`/`curl`/`wget` POST form, whose failure
    is a clean 4xx-shaped body (RX_REQ_FAILED) readable regardless of where the
    command sits in a chain. The CLI forms (`--add-reviewer`, `--reviewer`) go
    through GraphQL, whose errors need not carry a 4xx status, so their failure
    is caught by the harness `is_error` exit status instead -- see the discharge
    in scan() for why that distinction decides which signal to trust.
    """
    if not argv:
        return False, None, None, False
    a0 = argv[0]
    if a0 == "gh" and len(argv) >= 3 and argv[1] == "pr":
        sub, rest = argv[2], argv[3:]
        if sub == "create" and _has_flag(rest, "--reviewer", "-r"):
            return True, None, None, False  # a create's number is in its result
        if sub == "edit" and _has_flag(rest, "--add-reviewer"):
            num, repo = _verb_ident(argv)
            return True, num, repo, False
    # `gh api`/`curl`/`wget` hitting the requested_reviewers endpoint with a
    # POST. The same endpoint is read via GET (to CHECK who is requested), and
    # a GET must NOT discharge, which is why the method is required.
    api = (a0 == "gh" and len(argv) >= 2 and argv[1] == "api") \
        or a0 in ("curl", "wget")
    if api:
        url = next((t for t in argv if "requested_reviewers" in t), None)
        if url and _post_method(argv):
            num, repo = _url_ident(url)
            return True, num, repo, True
    return False, None, None, False


def request_ident(cmd):
    """(is_request, num, repo, api): does `cmd` genuinely request a reviewer?"""
    cmds = _simple_commands(cmd)
    if cmds is None:
        return False, None, None, False
    for argv in cmds:
        ok, num, repo, api = _argv_request(argv)
        if ok:
            return True, num, repo, api
    return False, None, None, False


# Tools whose input is a SHELL COMMAND. Matching CLI patterns against any
# other tool's serialized input is the documentation/heredoc false positive
# README.md:265-271 warns about -- self-demonstrating here, since these very
# hook files contain the strings `gh pr create` and `requested_reviewers`.
SHELL_TOOLS = {"Bash", "bash", "run_command"}

# Structured PR tools, matched on the tool NAME with arguments read as fields.
OPEN_TOOLS = {"create_pull_request", "mcp__github__create_pull_request"}
EDIT_TOOLS = {"update_pull_request", "mcp__github__update_pull_request"}
REQ_TOOLS = {"request_copilot_review", "mcp__github__request_copilot_review"}

# A PR number plus owner/repo carried by a shell command: an API path
# (`repos/o/r/pulls/1038`), a CLI verb (`gh pr ready 1038`), or a `-R o/r`
# flag. `gh pr create` carries NEITHER -- its number is learned from the
# result -- which is the whole reason opens are keyed from their result.
RX_CMD_API = re.compile(r"repos/([\w.-]+)/([\w.-]+)/pulls?/(\d+)", re.I)
RX_CMD_VERB = re.compile(
    r"\bpr\s+(?:ready|edit|view|comment|review|merge|close|diff|checks)\s+#?(\d+)",
    re.I,
)
RX_CMD_REPO = re.compile(r"(?:-R|--repo)[=\s]+([\w.-]+/[\w.-]+)", re.I)

# A PR identity carried by a tool RESULT: the PR URL (owner/repo/number) or a
# bare `"number"` field.
RX_RES_URL = re.compile(r"github\.com/([\w.-]+)/([\w.-]+)/pull/(\d+)", re.I)
RX_RES_API = re.compile(r"repos/([\w.-]+)/([\w.-]+)/pulls?/(\d+)", re.I)
RX_RES_NUM = re.compile(r"\\?\"number\\?\"\s*:\s*(\d+)")

# A tool result that reports failure. Kept specific: a bare 4xx substring
# matches PR numbers like 422 or a `/pull/430` URL, so failure is keyed on an
# HTTP-status shape or an explicit error word, plus the harness `is_error`
# flag when present.
RX_FAILED = re.compile(
    r"\"status\"\s*:\s*4\d\d|HTTP\s+4\d\d|\berror\b|\bfailed\b"
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
RX_REQ_FAILED = re.compile(
    r"\"status\"\s*:\s*4\d\d|HTTP\s+4\d\d|cannot be requested",
    re.I,
)


def cmd_ident(cmd):
    """(num, repo) from a shell command; each None when absent."""
    repo = None
    m = RX_CMD_REPO.search(cmd)
    if m:
        repo = m.group(1)
    m = RX_CMD_API.search(cmd)
    if m:
        return m.group(3), f"{m.group(1)}/{m.group(2)}"
    m = RX_CMD_VERB.search(cmd)
    if m:
        return m.group(1), repo
    return None, repo


def input_ident(inp):
    """(num, repo) from a structured tool's input fields."""
    num = inp.get("pullNumber") or inp.get("pull_number")
    num = str(num) if num is not None else None
    owner, rp = inp.get("owner"), inp.get("repo")
    repo = f"{owner}/{rp}" if owner and rp else None
    return num, repo


def result_ident(body):
    """(num, repo) parsed from a tool_result body string."""
    m = RX_RES_URL.search(body) or RX_RES_API.search(body)
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
    pending = {}  # tool_use_id -> (num, repo) for reviewer requests
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
                        # single Bash call can chain a create with a trailing
                        # request (`gh pr create ... && gh api ...
                        # requested_reviewers -X POST`, or `gh pr create
                        # --reviewer` whose reviewer step 422s). A failure there
                        # must not be read as the create failing:
                        #   * failed AND no PR identity resolved -> the open
                        #     itself failed, no PR exists, so drop it.
                        #   * failed BUT a PR URL/number is present -> the create
                        #     SUCCEEDED and the trailing request is what failed;
                        #     the PR is real and unreviewed, so keep tracking it.
                        if failed and rnum is None:
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
                    # Discharge the reviewer request that produced this result,
                    # gated on the REQUEST's own outcome -- never the broad
                    # `failed` flag, which an unrelated chained command's
                    # `error`/`not found` shell noise would trip.
                    #
                    # `err` (is_error) is the exit status of the WHOLE Bash call,
                    # i.e. the LAST simple command, so it is trustworthy for the
                    # request ONLY when nothing runs after it. For the `gh api`
                    # POST form (api=True) that is not safe to assume -- the hook
                    # even suggests chaining a verify step after the POST -- but
                    # that form fails with a clean 4xx-shaped body, so
                    # RX_REQ_FAILED alone decides it, ordering-independent, and
                    # `err` is dropped. The CLI/structured forms (api=False) can
                    # fail without a 4xx body (a GraphQL error, an MCP failure),
                    # so `err` is kept -- reliable for the atomic structured
                    # tools, and only over-blocking (the safe direction) in the
                    # rare case a CLI request is chained ahead of another command.
                    if rid in pending:
                        rnum2, rrepo2, api2 = pending.pop(rid)
                        req_failed = bool(RX_REQ_FAILED.search(body)) \
                            or (err and not api2)
                        if not req_failed:
                            _clear(obligations, rnum2 or rnum, rrepo2 or rrepo)
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
                        _clear(obligations, num, repo)
                    elif inp.get("draft") is False:
                        obligations.append({"num": num, "repo": repo,
                                            "tid": tid,
                                            "self": bool(inp.get("reviewers"))})
                    if inp.get("reviewers"):
                        # A structured tool call is atomic -- one tool_use, one
                        # result -- so is_error reflects THIS request, with no
                        # chained command to poison it. api=False -> trust err.
                        pending[tid] = (num, repo, False)
                    continue
                if name in REQ_TOOLS:
                    rn, rr = input_ident(inp)
                    pending[tid] = (rn, rr, False)  # atomic; trust err
                    continue
                if name not in SHELL_TOOLS:
                    continue  # never text-match a non-shell tool

                cmd_raw = inp.get("command") or ""
                # Open/draft detection blanks EVERY quote (leading-word checks,
                # never quoted); open/draft IDENTITY reads the payload-scrubbed
                # string, so a `--body` mentioning a `pulls/N` path cannot forge
                # a draft-clear target on a real open/draft command.
                cmd_open = _scrub_all(cmd_raw)
                num, repo = cmd_ident(_scrub_payload(cmd_raw))
                draft = bool(RX_DRAFT.search(cmd_open))
                opened = bool(RX_OPEN.search(cmd_open)) and not draft
                # Request detection is STRUCTURAL (per simple command), so an
                # example request quoted in a body/echo/heredoc/herestring
                # never forges or discharges an obligation. Its identity comes
                # from the request command itself.
                requested, rnum, rrepo, rapi = request_ident(cmd_raw)
                # Draft is checked first: `gh pr ready --undo` matches RX_OPEN
                # too, and it is the draft action that decides.
                if draft:
                    _clear(obligations, num, repo)
                elif opened:
                    obligations.append({"num": num, "repo": repo, "tid": tid,
                                        "self": requested})
                # A create --reviewer both opens and requests; its `self` flag
                # discharges it on the create's own result, so it is not also a
                # separate pending request here.
                if requested and not opened:
                    pending[tid] = (rnum or num, rrepo or repo, rapi)
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
