---
name: claude-agent-workflow
description: "Add or update claude.yml workflow."
user-invocable: true
allowed-tools:
  - Read
  - Edit
  - Write
  - Bash
---

# claude-agent-workflow

Sets up or edits the `@claude` agent GitHub Actions workflow (`.github/workflows/claude.yml` or `.github/workflows/claude-bot.yml`),
which delegates to the reusable [`claude.yml`](https://github.com/Morrison-Lab/gha/blob/v2/.github/workflows/claude.yml) workflow from `Morrison-Lab/gha`.
For the read-only **PR review** workflow,
use [`claude-review-workflow`](../claude-review-workflow/SKILL.md).

Path: `.github/workflows/claude.yml` (or `.github/workflows/claude-bot.yml`)

## Standard caller stub

```yaml
name: Claude Code

on:
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]
  # `opened` is safe: the callee's mention-filter runs detect-bot-mention on
  # issue body and title and stands down on a quoted mention (gha#554).
  # `assigned` fires only when the issue body or title also mentions the bot
  # and the issue author is trusted -- or add a dispatch-on-assignee clause
  # below AND pass the dispatch-on-assignee input (see gha examples/claude.yml).
  issues:
    types: [opened, assigned]
  pull_request_review:
    types: [submitted]

jobs:
  claude:
    # Caller-side trusted-author gate, copied from gha examples/claude.yml at
    # the pinned tag: an untrusted mention never invokes a workflow that holds
    # write permissions and secrets. Re-diff against the example on every bump.
    if: |
      (github.event_name == 'issue_comment' && contains(github.event.comment.body, '@claude') && contains(fromJSON('["OWNER","MEMBER","COLLABORATOR"]'), github.event.comment.author_association)) ||
      (github.event_name == 'pull_request_review_comment' && contains(github.event.comment.body, '@claude') && contains(fromJSON('["OWNER","MEMBER","COLLABORATOR"]'), github.event.comment.author_association)) ||
      (github.event_name == 'pull_request_review' && contains(github.event.review.body, '@claude') && contains(fromJSON('["OWNER","MEMBER","COLLABORATOR"]'), github.event.review.author_association)) ||
      (github.event_name == 'issues' && (contains(github.event.issue.body, '@claude') || contains(github.event.issue.title, '@claude')) && contains(fromJSON('["OWNER","MEMBER","COLLABORATOR"]'), github.event.issue.author_association))
    permissions:
      contents: write
      pull-requests: write
      issues: write
      id-token: write
      actions: write
    uses: Morrison-Lab/gha/.github/workflows/claude.yml@v2
    secrets: inherit
    with:
      setup-r: false
      eager-pr: true
      review-workflow-file: claude-review.yml
```

## Load-bearing pieces (managed by `Morrison-Lab/gha`)

By delegating to `Morrison-Lab/gha/.github/workflows/claude.yml@v2`,
the consumer repo automatically inherits:

1. **Bot-actor filtering**: Evaluates mention triggers (`@claude`) on comments, reviews, and assigned issues while filtering out bot-generated loops.
2. **Concurrency serialization**: Per-issue/PR concurrency with `cancel-in-progress: false` to avoid clobbering concurrent in-flight agent pushes.
3. **Late-comment polling**: Scans for comments arriving during execution so long-running sessions drain multi-comment bursts.
4. **Post-push review triggering**: Captures head SHAs before and after execution;
   if changes were pushed, automatically requests review and dispatches the review workflow.
5. **Tool permission sandboxing**: Restricts allowed CLI tools (`gh` read commands, `git`, build tools) and enforces secure WebFetch domain allowlisting.
6. **Threaded inline replies**: Automatically posts responses as threaded inline replies when triggered by pull request review comments.
7. **Environment and secret propagation**: Handles private submodules (`SUBMODULES_TOKEN`) and optional domain tokens (`EPI202_TOKEN`).

## Inputs and customization

- `setup-r`: Initialize R toolchain and renv package cache (`true` for R packages / Quarto R repos).
- `eager-pr`: Open a draft PR up front when claiming an issue (`true` by default).
- `review-workflow-file`: Name of the companion review workflow file (e.g. `claude-review.yml` or `claude-code-review.yml`).
- `use-ai-config`: Automatically load `ai-config` agent instructions (defaults to `true`, set `false` for `Morrison-Lab/ai-config` itself).
- `apt-packages` / `pip-packages`: Additional build or analysis packages.

## Setting up in a new repo

1. Confirm `CLAUDE_CODE_OAUTH_TOKEN` secret exists in repo/org secrets (`gh secret list`).
2. Add the caller stub at `.github/workflows/claude.yml`.
   Diff it against gha's `examples/claude.yml` at the tag you pin, not against another consumer's caller:
   see [`gha-reusable-workflows.md`](../../memories/gha-reusable-workflows.md)'s "Template propagation hazard".
3. Ensure required permissions (`contents: write`, `pull-requests: write`, `issues: write`, `id-token: write`, `actions: write`) are declared on the caller job.
4. Configure appropriate inputs (`setup-r`, `review-workflow-file`, etc.).

## Relationship to other skills

- [`claude-review-workflow`](../claude-review-workflow/SKILL.md) — Companion skill for the automated PR review workflow.
- [`upgrade-to-gha`](../../shared/workflow/upgrade-to-gha.md) — Migration guidelines for upgrading standalone workflows to `Morrison-Lab/gha`.
- [`config-ai`](../config-ai/SKILL.md) — Router for AI workflow capability requests.
