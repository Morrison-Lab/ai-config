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

# Reviewer-request CLI/MCP forms that are inherently mutating: no separate
# POST check is needed for these. Verified against `gh --help`:
# `gh pr create --reviewer` and `gh pr edit --add-reviewer` exist;
# `gh pr review --request` does NOT (`gh pr review` has only
# --approve/--comment/--request-changes), so it is deliberately absent.
RX_REQ_CLI = re.compile(
    r"request_copilot_review"
    r"|gh\s+pr\s+edit[^|;&]*--add-reviewer"
    r"|gh\s+pr\s+create[^|;&]*--reviewer\b",
    re.I,
)
# The short reviewer flag is `-r`; the repo flag is `-R`. They differ only by
# case, so this one alternative must be case-SENSITIVE -- matching it under
# re.I would read `gh pr create -R owner/repo` as a reviewer request.
RX_REQ_SHORT = re.compile(r"gh\s+pr\s+create[^|;&]*\s-r\s")
# A mutating HTTP method. The bare `requested_reviewers` endpoint is also read
# via GET (to CHECK who is requested -- the hook's own recovery text suggests a
# verification call), and a GET must NOT discharge the obligation.
RX_POST = re.compile(r"-X\s*['\"]?POST|--method\s+['\"]?POST", re.I)


def is_request(cmd):
    """True when a shell command actually REQUESTS a reviewer (not a read)."""
    if RX_REQ_CLI.search(cmd) or RX_REQ_SHORT.search(cmd):
        return True
    return "requested_reviewers" in cmd and bool(RX_POST.search(cmd))


# A gh action must be an actual command word, not a string quoted inside a
# DIFFERENT command's argument. This repo's own docs and this hook's own
# recovery text are full of literal `gh pr create` / `requested_reviewers -X
# POST` examples, so a `gh pr comment --body "... gh pr create ..."` would
# otherwise forge an obligation, and a `--body "... requested_reviewers -X
# POST ..."` would silently DISCHARGE a real one -- the exact false negative
# this hook exists to catch (the README.md:265-271 heredoc trap, one layer in
# from the non-shell-tool case). So blank the CONTENTS of heredoc bodies and
# quoted arguments before matching. A gh invocation is normally the leading
# word of its command, before any quote, so real opens/requests survive;
# over-blanking only ever drops a real match (a missed obligation -- the
# fail-open direction), never forges or discharges one.
RX_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1.*?\n[ \t]*\2\b", re.S)


def _scrub(cmd):
    cmd = RX_HEREDOC.sub("<<", cmd)              # drop heredoc bodies
    cmd = re.sub(r'"(?:[^"\\]|\\.)*"', '""', cmd)  # blank "..." contents
    cmd = re.sub(r"'[^']*'", "''", cmd)          # blank '...' contents
    return cmd


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
                    failed = bool(b.get("is_error")) or bool(
                        RX_FAILED.search(body))
                    rnum, rrepo = result_ident(body)
                    # Resolve the open that produced this result.
                    keep = []
                    for ob in obligations:
                        if ob["tid"] != rid:
                            keep.append(ob)
                            continue
                        if failed:
                            continue  # a failed open opened no PR
                        if ob["num"] is None and rnum:
                            ob["num"] = rnum
                        if ob["repo"] is None and rrepo:
                            ob["repo"] = rrepo
                        if ob["self"]:
                            continue  # create --reviewer already requested
                        keep.append(ob)
                    obligations[:] = keep
                    # Discharge the reviewer request that produced this result.
                    if rid in pending:
                        rnum2, rrepo2 = pending.pop(rid)
                        if not failed:
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
                        pending[tid] = (num, repo)
                    continue
                if name in REQ_TOOLS:
                    pending[tid] = input_ident(inp)
                    continue
                if name not in SHELL_TOOLS:
                    continue  # never text-match a non-shell tool

                cmd = _scrub(inp.get("command") or "")
                num, repo = cmd_ident(cmd)
                requested = is_request(cmd)
                opened = bool(RX_OPEN.search(cmd)) and not RX_DRAFT.search(cmd)
                # Draft is checked first: `gh pr ready --undo` matches RX_OPEN
                # too, and it is the draft action that decides.
                if RX_DRAFT.search(cmd):
                    _clear(obligations, num, repo)
                elif opened:
                    obligations.append({"num": num, "repo": repo, "tid": tid,
                                        "self": requested})
                # A create --reviewer both opens and requests; its `self` flag
                # discharges it on the create's own result, so it is not also a
                # separate pending request here.
                if requested and not opened:
                    pending[tid] = (num, repo)
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
