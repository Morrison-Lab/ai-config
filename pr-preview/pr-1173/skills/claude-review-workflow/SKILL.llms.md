# claude-review-workflow

Sets up or edits the Claude PR **review** workflow (`claude-code-review.yml`), which runs the upstream `code-review@claude-code-plugins` plugin on a PR. For the **agent** workflow that edits files in response to `@claude` mentions, use \[\[claude-agent-workflow\]\].

Path: `.github/workflows/claude-code-review.yml`

## Load-bearing pieces (don’t “simplify” away)

### 1. Fresh comment per run — do NOT delete prior reviews

Each run posts a **new** review comment and leaves earlier ones in place, so the PR keeps a visible review history rather than a rolling sticky.

**Do not add a “delete previous Claude sticky comment” pre-step.** An older version of this skill recommended exactly that; it was wrong and is rejected — deleting prior reviews erases history and the delete-then-repost churns notifications. (If you find such a step in a repo, remove it.) The canonical workflows (qwt, rme) explicitly leave priors in place.

### 2. Encourage inline comments

The action already makes inline review comments possible — `permissions: pull-requests: write`, and the inline tool available either by allowlisting `mcp__github_inline_comment__create_inline_comment` (qwt) or via the default toolset when you only use `--disallowedTools` (rme). But the `code-review:code-review` plugin **defaults to a single top-level summary** with prose line-references, so you have to *push* it toward real inline comments in the prompt:

    **Post line-specific findings as inline review comments** anchored to the
    relevant line(s) — use the inline-comment tool, not a prose list in the
    summary. Reserve the top-level summary comment for a brief overall verdict
    plus any finding not tied to a specific line; don't restate each inline
    comment there.

Caveat: the plugin drives much of the behavior, so prompt-strengthening only *partly* moves it — verify on a live PR and iterate the wording. (Added in qwt#93 / rme#833.)

**Pitfall — duplicate `with:` block.** When a workflow file has a commented-out `# with:` template block *below* the active `with:` block, do **not** uncomment it as a second `with:` key. YAML duplicate keys cause the second to silently override the first, dropping `pr-number` on `workflow_dispatch` runs. Instead, add `prompt-addendum` as a new key *inside* the existing `with:` block:

``` yaml
    with:
      pr-number: ${{ inputs.pr_number }}
      prompt-addendum: |
        ...
```

### 3. Event-gated `track_progress`

``` yaml
track_progress: ${{ github.event_name == 'pull_request' && 'true' || 'false' }}
```

`track_progress: true` forces tag mode, which guarantees a tracking comment even when the plugin scores the PR below its post threshold (≥80). **But the action rejects `track_progress` for `workflow_dispatch`** and fails the whole step — and `claude.yml` dispatches this workflow via `workflow_dispatch`. So gate it on `event_name`: tag mode for `pull_request`, agent mode for dispatched runs (which may then be silent on small/mechanical PRs — acceptable vs. the dispatch path failing outright). See d-morrison/rme#818, \#801.

### 4. `workflow_dispatch` path with `pr_number` input

``` yaml
on:
  workflow_dispatch:
    inputs:
      pr_number: { description: 'Pull request number to review', required: true, type: number }
```

`claude.yml` dispatches a fresh review after an `@claude` run pushes commits or on an `@claude review` comment. `GITHUB_TOKEN`-driven pushes don’t fire `synchronize`, so this explicit dispatch path is required, and the job must resolve `PR_NUMBER` from `github.event.pull_request.number || inputs.pr_number`.

### 5. Skip drafts / Dependabot / forks — except dispatched runs

The `if:` runs `workflow_dispatch` unconditionally (so a review fires on the draft PR claude.yml opens for an issue trigger), otherwise skips drafts, `dependabot[bot]`, and fork PRs (forks can’t read `CLAUDE_CODE_OAUTH_TOKEN`, so the run would fail with a noisy red check).

### 6. Concurrency

``` yaml
concurrency:
  group: claude-review-${{ github.event.pull_request.number || inputs.pr_number }}
  cancel-in-progress: true
```

`cancel-in-progress: true` is safe here **only because this workflow is read-only** (its tools grant no git push/commit, so it never pushes a fix and can’t self-cancel). A review workflow that can push fixes must guard against cancelling its own triggered run — see d-morrison/rme#817.

### 7. Optional: install a computer algebra system when math verification would help

`apt-packages` / `pip-packages` inputs on `claude-code-review.yml` mirror the inputs `claude.yml` already had (both empty by default) and let a repo’s review job install system/pip packages before the review runs — most usefully a CAS (`apt-packages: maxima`, `pip-packages: sympy`) so the reviewer’s Bash tool can symbolically check a derivation instead of eyeballing the algebra. Set these only for repos with substantial math-heavy prose (e.g. rme’s textbook chapters); most repos need neither. Pair with a `prompt-addendum` telling the reviewer to actually use the installed CAS for derivations/proofs, and — when the repo has a PR-preview deploy — to check any computed value or figure the prose describes against the rendered output rather than trusting the prose’s own description (see `d-morrison/ai-config`’s `shared/writing/fact-check-prose.md` and the `fact-check-prose` skill for the full policy this operationalizes).

## Setting up in a new repo

1.  Confirm `CLAUDE_CODE_OAUTH_TOKEN` secret exists (`gh secret list`).
2.  Write the workflow with the pieces above. Keep the read-only tool posture (`--disallowedTools` for git writes, or an allowlist without them).
3.  Add a repo-specific addendum to the prompt (Quarto/R checks, etc.) if the project warrants it — see qwt’s review workflow for an example.

## Relationship to other skills

- **`claude-agent-workflow`** — the companion skill for the agent workflow that edits files in response to `@claude` mentions; see the top of this file.
- **`config-ai`** — the broader router: when a request is “change how the `@claude` bot behaves when invoked,” not “add something consumers’ CI can call,” `config-ai` hands off to this skill (or `claude-agent-workflow`) rather than `skill-builder`/`agent-builder`.

Back to top
