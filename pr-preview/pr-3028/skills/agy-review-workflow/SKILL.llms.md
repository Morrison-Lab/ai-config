# agy-review-workflow

> \[!IMPORTANT\] **This workflow’s *API-dispatch* status is unverified since 2026-08-20.** That date’s dispatched run ended `request failed (code 429): Your prepayment credits are depleted` / `Execution failed: model unreachable`, and nobody has re-tested this specific `antigravity-review.yml` / `antigravity-code-review.yml` dispatch path since. Don’t assume it works, and don’t assume it is still broken — probe it before relying on it, and update this banner with what you find. **This is a separate claim from the `agy` CLI**, which is confirmed working on Windows as of 2026-09-02 via a direct local install (see `memories/delegation.md`’s IMPORTANT banner and its “agy on Windows” section, pointed to from `memories/preferences.md`) — that CLI route does not go through this workflow file at all, so its recovery says nothing about whether the API dispatch here still 429s. Until someone re-runs this workflow and reports a result, prefer [`delegate-to-codex`](../../skills/delegate-to-codex/SKILL.llms.md) or a direct `agy --print` CLI dispatch (per `memories/delegation.md`) for a cross-vendor second opinion. Copilot stays requestable on the PR where the org’s licensing reaches it. Tracked as ai-config#1776.

Sets up or edits the Google Antigravity PR **review, security audit, and test generation** workflow ([antigravity-review.yml](../../.github/workflows/antigravity-review.yml)), which invokes the reusable [antigravity-code-review.yml](https://github.com/Morrison-Lab/gha/blob/v2/.github/workflows/antigravity-code-review.yml) workflow from `Morrison-Lab/gha`.

Path: [.github/workflows/antigravity-review.yml](../../.github/workflows/antigravity-review.yml)

## Load-bearing pieces (don’t “simplify” away)

### 1. Delegation to `Morrison-Lab/gha` reusable workflow

``` yaml
jobs:
  review:
    uses: Morrison-Lab/gha/.github/workflows/antigravity-code-review.yml@v2
```

The workflow delegates execution to `Morrison-Lab/gha`’s reusable workflow, which executes `Morrison-Lab/gha/antigravity-review@v2`. This ensures updates, safety checks, and runner handling in `gha` are automatically shared across repos.

### 2. Required permissions

``` yaml
permissions:
  contents: read
  pull-requests: write
  issues: write
  id-token: write
  actions: read
```

- `contents: read`: Allows reading repository code and diffs.
- `pull-requests: write`: Grants permission to post review comments and verdicts on PRs.
- `issues: write`: Allows writing issue comments where required.
- `id-token: write`: Enables OIDC authentication where required.
- `actions: read`: Lets automated review agents inspect CI run status.

### 3. Concurrency management

``` yaml
concurrency:
  group: antigravity-review-${{ github.event.pull_request.number || inputs.pr_number || github.ref }}
  cancel-in-progress: true
```

`cancel-in-progress: true` cancels superseded runs on rapid sequential pushes, preventing API quota waste and review comment race conditions.

### 4. Secret propagation (`GEMINI_API_KEY`)

``` yaml
secrets:
  GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
```

Antigravity uses the Gemini API. Ensure the target repo has `GEMINI_API_KEY` defined in repository or organization secrets (`gh secret list`).

### 5. Operational modes

Supported operational modes passed via `inputs.mode`: - `code-review` (default): Performs an automated PR code review. - `security-audit`: Runs targeted security inspection on modified code. - `test-generation`: Generates suggested test cases for changed files.

### 6. Event-gated trigger policy

``` yaml
with:
  trigger-policy: ${{ github.event_name == 'pull_request' && 'on-push' || 'on-request' }}
```

- `on-push`: Automatically reviews PR updates on `pull_request` events (`opened`, `synchronize`, `ready_for_review`, `reopened`).
- `on-request`: Restricts review to manual execution via `workflow_dispatch`.

### 7. Fork & Dependabot safeguards

The underlying action (`Morrison-Lab/gha/antigravity-review@v2`) enforces guards so draft PRs, cross-repository (fork) PRs, and `dependabot[bot]` runs do not leak secrets or execute untrusted code.

## Setting up in a new repo

1.  Confirm `GEMINI_API_KEY` secret exists (`gh secret list`).
2.  Write `.github/workflows/antigravity-review.yml` using the template below.
3.  Push to `main` or open a PR to enable automated reviews.

### Canonical Workflow Template

``` yaml
# Active caller for Morrison-Lab/gha's reusable Antigravity PR review workflow.
name: Antigravity Code Review

on:
  pull_request:
    types: [opened, synchronize, ready_for_review, reopened]

  workflow_dispatch:
    inputs:
      pr_number:
        description: 'Pull request number to review'
        required: true
        type: string
      mode:
        description: 'Operational mode: code-review, security-audit, or test-generation'
        required: false
        default: 'code-review'
        type: choice
        options:
          - code-review
          - security-audit
          - test-generation

concurrency:
  group: antigravity-review-${{ github.event.pull_request.number || inputs.pr_number || github.ref }}
  cancel-in-progress: true

jobs:
  review:
    permissions:
      contents: read
      pull-requests: write
      issues: write
      id-token: write
      actions: read
    uses: Morrison-Lab/gha/.github/workflows/antigravity-code-review.yml@v2
    with:
      mode: ${{ inputs.mode || 'code-review' }}
      pr-number: ${{ github.event.pull_request.number || inputs.pr_number || '' }}
      model: ''
      trigger-policy: ${{ github.event_name == 'pull_request' && 'on-push' || 'on-request' }}
    secrets:
      GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
```

## Relationship to other skills

- **`claude-review-workflow`** – sets up the Claude Code PR review workflow (`claude-code-review.yml`).
- **`claude-agent-workflow`** – sets up the Claude Code agent workflow (`claude.yml`).
- **`config-ai`** – routes AI capability and bot workflow requests to the appropriate skill.

Back to top
