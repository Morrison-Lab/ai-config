---
name: claude-review-workflow
description: "Add or update claude-review workflow."
user-invocable: true
allowed-tools:
  - Read
  - Edit
  - Write
  - Bash
---

# claude-review-workflow

Sets up or edits the Claude PR **review** workflow (`.github/workflows/claude-code-review.yml` or `.github/workflows/claude-review.yml`),
which delegates to the reusable [`claude-code-review.yml`](https://github.com/Morrison-Lab/gha/blob/v2/.github/workflows/claude-code-review.yml) workflow from `Morrison-Lab/gha`.
For the **agent** workflow that edits files in response to `@claude` mentions,
use [`claude-agent-workflow`](../claude-agent-workflow/SKILL.md).

Path: `.github/workflows/claude-code-review.yml` (or `.github/workflows/claude-review.yml`)

## Standard caller stub

```yaml
name: Claude Code Review

on:
  pull_request:
    types: [opened, synchronize, ready_for_review, reopened]
  workflow_dispatch:
    inputs:
      pr_number:
        description: 'Pull request number to review'
        required: true
        type: string

jobs:
  gather-context:
    runs-on: ubuntu-latest
    permissions:
      issues: read
    outputs:
      prior-reviews: ${{ steps.fetch.outputs.prior-reviews }}
    steps:
      - id: fetch
        env:
          GH_TOKEN: ${{ github.token }}
          PR_NUMBER: ${{ github.event.pull_request.number || inputs.pr_number }}
          REPO: ${{ github.repository }}
        run: |
          REVIEWS=$(gh api "repos/${REPO}/issues/${PR_NUMBER}/comments" \
            --jq '[.[] | select(.user.login == "claude[bot]")] | .[-3:] |
                  .[] | "=== Review posted \(.created_at) ===\n\(.body)\n"' \
            2>/dev/null | head -c 12000 || true)
          {
            echo 'prior-reviews<<__REVIEWS_EOF__'
            echo "$REVIEWS"
            echo '__REVIEWS_EOF__'
          } >> "$GITHUB_OUTPUT"

  review:
    needs: gather-context
    permissions:
      contents: read
      pull-requests: write
      issues: write
      id-token: write
      actions: read
    uses: Morrison-Lab/gha/.github/workflows/claude-code-review.yml@v2
    secrets: inherit
    with:
      pr-number: ${{ github.event.pull_request.number || inputs.pr_number }}
```

## Load-bearing pieces (managed by `Morrison-Lab/gha`)

By delegating to `Morrison-Lab/gha/.github/workflows/claude-code-review.yml@v2`,
the consumer repo automatically inherits:

1. **History preservation**: Fresh review comment posted per run without deleting prior review history.
2. **Inline comment prompt**: Pushes review findings toward line-anchored comments via `mcp__github_inline_comment__create_inline_comment`.
3. **Dispatch and event-gating**: Handles both `pull_request` and `workflow_dispatch` triggers, with branch-anchored dispatch resolution.
4. **Draft and fork guards**: Skips unready drafts, Dependabot PRs, and tokenless fork PRs while executing dispatched runs.
5. **Concurrency & self-cancellation safety**: Concurrency group keyed per PR with `cancel-in-progress: true`.
6. **Package customization**: Supports `apt-packages` and `pip-packages` (e.g. `maxima`, `sympy`) for CAS-driven mathematical verification when needed.
7. **Prompt extensions**: Custom repo-level instructions passed via `prompt-addendum`.

## Inputs and customization

- `pr-number`: Required PR number passed from caller.
- `prompt-addendum`: Repo-specific review instructions (e.g. Quarto/R checks, domain invariants).
- `apt-packages` / `pip-packages`: Optional system/Python packages for verification (e.g. CAS engines).
- `setup-r`: Set `true` if R packages or renv environment need initialization during review.

## Setting up in a new repo

1. Confirm `CLAUDE_CODE_OAUTH_TOKEN` secret exists in repo/org secrets (`gh secret list`).
2. Add the caller stub at `.github/workflows/claude-code-review.yml`.
3. Ensure required permissions (`contents: read`, `pull-requests: write`, `issues: write`, `id-token: write`, `actions: read`) are declared on the caller job.
4. Pass any project-specific guidance via `prompt-addendum`.

## Relationship to other skills

- [`claude-agent-workflow`](../claude-agent-workflow/SKILL.md) — Companion skill for the interactive editing agent workflow.
- [`upgrade-to-gha`](../../shared/workflow/upgrade-to-gha.md) — Migration guidelines for upgrading standalone workflows to `Morrison-Lab/gha`.
- [`config-ai`](../config-ai/SKILL.md) — Router for AI workflow capability requests.
