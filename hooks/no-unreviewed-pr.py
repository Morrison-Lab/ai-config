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

Fails OPEN on any parse trouble, and fires at most once per distinct message,
so it cannot wedge a session.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

# Opening a PR, or taking a draft out of draft. `create_pull_request` is the
# harness tool; `gh pr create` and `gh pr ready` are the CLI forms.
RX_OPEN = re.compile(
    r"gh\s+pr\s+ready|gh\s+pr\s+create|"
    r"create_pull_request|update_pull_request",
    re.I,
)

# Requesting a reviewer. Covers the REST endpoint, the CLI flag, and the MCP
# tool. `requested_reviewers` is the stable token across all three.
# Verified against `gh --help`: `gh pr create --reviewer` and
# `gh pr edit --add-reviewer` exist; `gh pr review --request` does NOT
# (`gh pr review` has only --approve/--comment/--request-changes, and
# `--request` is rejected as an unknown flag). Matching it would let a
# command that FAILS look like a successful request.
RX_REQUEST = re.compile(
    r"requested_reviewers|request_copilot_review|"
    r"gh\s+pr\s+edit[^|;&]*--add-reviewer|"
    r"gh\s+pr\s+create[^|;&]*(?:--reviewer|-r\s)",
    re.I,
)

# Marking a PR draft is a deliberate reason NOT to request review yet: a draft
# does not trigger the review bot, per shared/workflow/pr-on-claim.md. Only a
# *later* ready/create should re-arm this guard, which the index compare below
# handles naturally.
RX_DRAFT = re.compile(
    r"\"?draft\"?\s*[:=]\s*true|--draft\b|gh\s+pr\s+ready[^|;&]*--undo",
    re.I,
)


# Tools whose input is a SHELL COMMAND. Matching CLI patterns against any
# other tool's serialized input is the documentation/heredoc false positive
# README.md:265-271 warns about -- and it is self-demonstrating here, since
# these very hook files contain the strings `gh pr create` and
# `requested_reviewers` in their prose.
SHELL_TOOLS = {"Bash", "bash", "run_command"}

# Structured PR tools. Matched on the tool NAME, with their arguments read as
# fields rather than as text.
OPEN_TOOLS = {"create_pull_request", "mcp__github__create_pull_request"}
EDIT_TOOLS = {"update_pull_request", "mcp__github__update_pull_request"}
REQ_TOOLS = {"request_copilot_review", "mcp__github__request_copilot_review"}

# Three shapes carry a PR number: an API path (`pulls/1038`), a CLI verb
# (`gh pr ready 1038`), and a structured field (`pull_number: 1038`).
# Missing the CLI-verb form made `gh pr ready <N> --undo` resolve to a
# different key than the `create` that opened it, so the draft carve-out
# silently failed to clear the obligation it was meant to.
RX_PR_NUM = re.compile(
    r"pulls?[/\s#]+(\d+)"
    r"|\bpr\s+(?:ready|edit|view|comment|review|merge|close)\s+#?(\d+)"
    r"|\bpull_?number\D{0,3}(\d+)",
    re.I,
)
# A tool result that reports failure. A 422 -- documented when the PR author
# is the requested reviewer -- must NOT discharge the obligation.
RX_FAILED = re.compile(r"\b4\d\d\b|\berror\b|\bfail", re.I)


def pr_key(blob):
    """PR number mentioned, or '*' when none is identifiable."""
    m = RX_PR_NUM.search(blob)
    if m:
        return next(g for g in m.groups() if g)
    return "*"


def scan(path):
    """Return (open_prs, text).

    `open_prs` maps PR key -> True when an obligation is outstanding. Tracked
    PER PR rather than as scalar timestamps: with scalars, opening A then B
    and requesting review only for B silently forgets A -- which is exactly
    the two-PR failure this hook exists to catch.
    """
    open_prs = {}
    text = ""
    pending = []  # (index, key) request attempts awaiting their result
    with open(path, errors="ignore") as fh:
        for i, line in enumerate(fh):
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
                    # Only a SUCCESSFUL request discharges. A 422 still
                    # produces a tool_use, so trusting the attempt alone lets
                    # the session stop with no reviewer attached.
                    body = json.dumps(b.get("content") or "")
                    for _, key in pending:
                        if not RX_FAILED.search(body):
                            open_prs.pop(key, None)
                            if key == "*":
                                open_prs.clear()
                    pending = []
                    continue

                if kind == "tool_use":
                    name = b.get("name") or ""
                    inp = b.get("input") or {}
                    blob = json.dumps(inp)

                    if name in OPEN_TOOLS:
                        if not inp.get("draft"):
                            open_prs[pr_key(blob)] = True
                        continue
                    if name in EDIT_TOOLS:
                        key = pr_key(blob)
                        if inp.get("draft") is True:
                            open_prs.pop(key, None)
                        elif inp.get("draft") is False:
                            open_prs[key] = True
                        if inp.get("reviewers"):
                            pending.append((i, key))
                        continue
                    if name in REQ_TOOLS:
                        pending.append((i, pr_key(blob)))
                        continue
                    if name not in SHELL_TOOLS:
                        continue  # never text-match a non-shell tool

                    cmd = inp.get("command") or ""
                    key = pr_key(cmd)
                    # RX_DRAFT is checked FIRST, via if/elif, and its own
                    # pattern already matches `gh pr ready ... --undo` -- so
                    # RX_OPEN needs no separate `--undo` exclusion. That
                    # exclusion was tried and found dead: the mutation test
                    # that removed it did not fail, because this ordering
                    # already wins regardless of what RX_OPEN also matches.
                    if RX_DRAFT.search(cmd):
                        open_prs.pop(key, None)
                    elif RX_OPEN.search(cmd):
                        open_prs[key] = True
                    if RX_REQUEST.search(cmd):
                        pending.append((i, key))

                elif kind == "text" and m.get("type") == "assistant":
                    if b.get("text", "").strip():
                        text = b["text"]
    return open_prs, text


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        open_prs, text = scan(payload.get("transcript_path") or "")
    except Exception:
        return 0  # fail open

    if not text or not open_prs:
        return 0

    named = sorted(k for k in open_prs if k != "*")
    which = ", ".join("#" + k for k in named) if named else "a PR"

    key = hashlib.sha256((text + which).encode()).hexdigest()[:16]
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
