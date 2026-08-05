---
name: request-pr-review
description: Request d-morrison as reviewer after creating a GitHub PR. Run immediately after `gh pr create` succeeds, in the same response. Standing rule across all repos except `Lacaedemon/sparta`, which never requests d-morrison (see Scope).
user-invocable: true
allowed-tools:
  - Bash(gh api *)
  - Bash(gh pr *)
---

# request-pr-review

After creating any PR, request `d-morrison` as a reviewer. The user said
"you should always request my review after creating PRs" on 2026-05-15 —
without an explicit review request, the PR sits in their inbox without
notification.

## When to run

- Immediately after `gh pr create` succeeds, in the same response.
- When the user asks you to "request review" on an existing PR.

## Command

`EDIT_PR` (abstract operation token; resolve to your model's tool via
[`tool-mappings.md`](../../tool-mappings.md) — the GitHub MCP form is
`mcp__github__update_pull_request` with `reviewers: ["d-morrison"]`):

```sh
gh api -X POST repos/<owner>/<repo>/pulls/<num>/requested_reviewers \
  -f "reviewers[]=d-morrison"
```

You can get `<owner>/<repo>` from `gh repo view --json nameWithOwner -q .nameWithOwner`
and `<num>` from the PR URL returned by `gh pr create`.

## Edge cases

- **PR author is d-morrison.** GitHub returns HTTP 422 with
  `"Review cannot be requested from pull request author"`. Surface this
  explicitly to the user — don't silently swallow the error. They can
  self-assign via the UI if needed, but the review request can't go through
  the API.

- **Other reviewers already requested.** The endpoint adds to the existing
  list rather than replacing it, so this is safe to run alongside
  pre-configured CODEOWNERS or workflow-added reviewers.

## Scope

Applies by default to all GitHub repos. If the user tells you a specific
repo shouldn't auto-request d-morrison, honor that override per-repo via a
project-level memory.

### Exception: `Lacaedemon/sparta`

Never request `d-morrison` as a reviewer on a PR in sparta.

The exception is repo-scoped, not rule-wide.
Requesting `d-morrison` everywhere else stays correct and unchanged, on PR
creation and on deadlock alike, and that includes `Morrison-Lab/ai-config`,
which is emphatically not covered.
Within sparta the exception covers every path that would reach a request: the
standing post-`gh pr create` request above, and the deadlock escalation below.

A skill that routes its request through this skill inherits the exception
automatically, so `ard`, `ardi`, `merge-it`, and `st` need no edit.
Each is cross-repo, and each defers here.

**A review deadlock on a sparta PR escalates to the user in chat, not to a
review request.**
Escalation is re-routed, not retired: its purpose was always that a human
decides, and that is unchanged.
Post a boxed `BLOCKER` (per `CLAUDE.md`'s chat-output-tagging convention)
naming the PR, the single disputed item, and both sides of the exchange, then
stop iterating that item and wait for the user's call.

- **Do:** open a sparta PR with no human reviewer requested, and keep
  requesting `d-morrison` on every other repo's PRs, ai-config's included.
- **Do:** take a sparta deadlock to the user in chat as a boxed `BLOCKER`.
- **Don't:** run `gh pr edit --add-reviewer d-morrison`, or POST to
  `requested_reviewers` with that login, against a sparta PR.
  Not on creation, and not as a deadlock escalation.
- **Don't:** read this as ending escalation on sparta.
  An unresolved deadlock still needs a human, and chat is now where it goes.

(Directive from the user, 2026-08-05: "cai: stop requesting reviews from
d-morrison in this repo", then, correcting the scope shortly after, "cai: stop
requesting reviews from d-morrison in sparta, not in ai-config".
The first reading took "this repo" to mean ai-config, since that was where the
PRs under discussion sat, and shipped the exception pointed at the wrong repo
in ai-config#1177 --- which also reverted the reviewer request in six skills
that ship to ai-config and should have kept it.
Recorded because the near-miss is the transferable part: "this repo" resolves
against the repo the *work* is about, which need not be the repo whose PRs
happen to be in front of you.
When a repo-scoped directive arrives during cross-repo work, name the repo
back explicitly before encoding it.
No reason for the rule was given, and none is invented here.)
