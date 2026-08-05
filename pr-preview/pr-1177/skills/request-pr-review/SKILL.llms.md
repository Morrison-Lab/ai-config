# request-pr-review

After creating any PR, request `d-morrison` as a reviewer. The user said “you should always request my review after creating PRs” on 2026-05-15 — without an explicit review request, the PR sits in their inbox without notification.

## When to run

- Immediately after `gh pr create` succeeds, in the same response.
- When the user asks you to “request review” on an existing PR.

## Command

`EDIT_PR` (abstract operation token; resolve to your model’s tool via [`tool-mappings.md`](../../tool-mappings.md) — the GitHub MCP form is `mcp__github__update_pull_request` with `reviewers: ["d-morrison"]`):

``` sh
gh api -X POST repos/<owner>/<repo>/pulls/<num>/requested_reviewers \
  -f "reviewers[]=d-morrison"
```

You can get `<owner>/<repo>` from `gh repo view --json nameWithOwner -q .nameWithOwner` and `<num>` from the PR URL returned by `gh pr create`.

## Edge cases

- **PR author is d-morrison.** GitHub returns HTTP 422 with `"Review cannot be requested from pull request author"`. Surface this explicitly to the user — don’t silently swallow the error. They can self-assign via the UI if needed, but the review request can’t go through the API.

- **Other reviewers already requested.** The endpoint adds to the existing list rather than replacing it, so this is safe to run alongside pre-configured CODEOWNERS or workflow-added reviewers.

## Scope

Applies by default to all GitHub repos. If the user tells you a specific repo shouldn’t auto-request d-morrison, honor that override per-repo via a project-level memory.

### Exception: `Morrison-Lab/ai-config`

Never request `d-morrison` as a reviewer on a PR in this repo.

The exception is repo-scoped, not rule-wide. Requesting `d-morrison` in every other repo stays correct and unchanged, on PR creation and on deadlock alike. Within this repo it covers every path that would reach a request: the standing post-`gh pr create` request above, the ship step of any skill whose own PR lands in ai-config, and the deadlock escalation below.

A skill that routes its request through this skill inherits the exception automatically, so nothing had to change in `ard`, `ardi`, `merge-it`, or `st` — each is cross-repo, and each defers here. What did change is the skills that hardcoded the request while always shipping to ai-config; their ship step now requests nobody. Derive that set rather than trusting a list, since it grows. This lists every site that names `d-morrison` as a reviewer; a site is covered whenever its PR lands in ai-config:

``` sh
git grep -nE 'add-reviewer d-morrison|request `d-morrison`' -- skills/
```

**A review deadlock on an ai-config PR escalates to the user in chat, not to a review request.** Escalation is not retired here, only re-routed: its purpose was always that a human decides, and that is unchanged. Post a boxed `🛑 BLOCKER` (per `CLAUDE.md`’s chat-output-tagging convention) naming the PR, the single disputed item, and both sides of the exchange, then stop iterating that item and wait for the user’s call.

- **Do:** open an ai-config PR with no human reviewer requested.
- **Do:** take an ai-config deadlock to the user in chat as a boxed `🛑 BLOCKER`, and keep requesting `d-morrison` for a deadlock in any other repo.
- **Don’t:** run `gh pr edit --add-reviewer d-morrison`, or POST to `requested_reviewers` with that login, against an ai-config PR — not on creation, and not as a deadlock escalation.
- **Don’t:** read this as ending escalation on ai-config; an unresolved deadlock still needs a human, and chat is now where it goes.

(Directive from the user, 2026-08-05, verbatim: “cai: stop requesting reviews from d-morrison in this repo”. No reason was given, and none is recorded here.)

Back to top
