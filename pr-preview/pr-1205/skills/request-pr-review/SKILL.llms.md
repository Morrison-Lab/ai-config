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

Back to top
