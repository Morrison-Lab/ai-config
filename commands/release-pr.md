---
description: Release a previously-claimed PR so other agents (the @claude bot, other CLI sessions) know they can pick it up again. Requires the GitHub MCP server — reads and posts comments via mcp__github__* tools (unlike /claim-pr, which uses only gh).
allowed-tools:
  - Bash
  - mcp__github__add_issue_comment
  - mcp__github__pull_request_read
---

Counterpart to `/claim-pr`.
Post a single, recognisable "claim released" comment so other agents and sessions know the PR is free for the next person.

## Arguments

- `pr_number` (required) — the PR number, e.g. `860`.
- `lane` (optional, default `Claude Code CLI (local session)`) — who's releasing. Should match the lane used in the original `/claim-pr` so the release is unambiguous.
- `summary` (optional) — one short phrase describing what landed during the claim window, e.g. `merge conflicts resolved`, `addressed review findings`, `pushed reframe`.

If only one positional arg is given, treat it as `pr_number`.

## What to do

1. Resolve the current repository's `<owner>` and `<repo>` as separate values — this command is repo-agnostic, so don't hardcode them:

    ```bash
    owner=$(gh repo view --json owner -q .owner.login)
    repo=$(gh repo view --json name -q .name)
    ```

    Use that `<owner>`/`<repo>` pair for every GitHub call below.

2. Sanity-check there's an actually-open claim to release:

    Call `mcp__github__pull_request_read(method = "get_comments", owner = <owner>, repo = <repo>, pullNumber = <pr_number>)`. Walk the last ~10 comments and confirm:

    - the most recent claim/release exchange is an unmatched claim that hasn't yet been followed by a release.
      **Match the two-word invariant `hold off` (case-insensitively), never a full sentence** --- the PR claim reads `please hold off on pushing to this branch until I'm done` while the issue claim reads `please hold off until I'm done`, so neither sentence is a substring of the other and a matcher keyed on either one misses the other.
      **Also match the pre-2026-08-24 invariant `paws off`**: claims posted before that date are still live on open PRs, since a claim expires on activity rather than on age, and a matcher narrowed to the new wording returns nothing on them --- indistinguishable from no claim at all.
      So the claim test is `test("hold off|paws off"; "i")`.
      Treat **any** of these as a release marker --- four the corpus posts today plus one retired form still sitting on open PRs, and enumerating only this command's own is what makes it post a stray release over somebody else's completed handover:
        - this command's `… done --- claim released.`
        - its pre-2026-08-24 form `… done --- paws off released.`
        - `claim-pr`'s `Done with my local session --- unclaiming.`
        - `ardi`'s on-clean unclaim, `Done --- PR is free.`
        - `post-merge`'s conflict unclaim, `Conflict resolved --- branch is now mergeable. …`

      Derive that list rather than trusting this one, since a skill may add a sixth: `grep -rn "unclaim\|released\|PR is free\|now mergeable" skills/ commands/`.
    - and that claim's `lane` matches the lane we're releasing.

    If the most recent signal is already a release, or the claim was by a different lane, stop and tell the user — don't post a stray release that misrepresents who was holding the PR.

3. Compose the comment body, exactly in this shape so other agents recognise it:

    ```
    <lane> done --- claim released.

    _Posted by Claude Code (AI agent) --- not written by a human._
    ```

    If `summary` is provided, append it in parentheses on the first line:

    ```
    <lane> done --- claim released. (<summary>)

    _Posted by Claude Code (AI agent) --- not written by a human._
    ```

    The trailing marker is required on every agent-posted comment, and is deliberately emoji-free --- see [`disclose-agent-authorship`](../shared/workflow/disclose-agent-authorship.md).

4. Post the comment:

    `mcp__github__add_issue_comment(owner = <owner>, repo = <repo>, issue_number = <pr_number>, body = <body>)`.

5. Reply with one short confirmation including the PR's URL — no further PR comment, no further work on the branch.

## Don't

- Don't push commits, open subagents, or modify files. Releasing is a no-op except for the comment.
- Don't release a claim that isn't yours unless the user explicitly tells you to (e.g. "the @claude bot crashed mid-claim, release it").
- Don't add or remove labels; the comment is the entire interface.
