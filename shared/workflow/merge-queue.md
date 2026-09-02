# GitHub Merge Queue

A GitHub merge queue eliminates the O(N^2) review and CI churn that occurs when landing multiple pull requests under strict branch protection.
By decoupling merge serialization from individual PR branch updates,
speculative merge testing validates ready PRs against moving base branches at O(N) cost.

Worked-example case records and empirical measurements live in [`batch-merge-and-resolve.cases.md`](batch-merge-and-resolve.cases.md) and [`../../memories/gh-cli.md`](../../memories/gh-cli.md).

## The quadratic cost of strict branch protection

When a repository enables strict branch protection (`required_status_checks.strict: true` or "Require branches to be up to date before merging"),
a pull request cannot merge unless its head commit incorporates the latest tip of the base branch (`main`).
When N independent PRs are simultaneously approved and ready to merge:

1. PR 1 merges into `main`.
2. The base branch advances, immediately flipping the remaining N - 1 PRs to `mergeStateStatus: BEHIND`.
3. Each of the N - 1 PRs must sync with `main` (via `gh pr update-branch` or merge/rebase).
4. Updating each branch creates a new commit, triggering full CI test suites and automated AI review workflows (such as `claude-code-review`).
5. PR 2 finishes re-testing and merges into `main`.
6. The base advances again, invalidating PRs 3 through N and requiring N - 2 more re-syncs and review rounds.

This cycle repeats until all N PRs land.
Landing N simultaneously ready PRs requires:

$$\sum_{k=1}^{N-1} k = \frac{N(N-1)}{2} = \mathcal{O}(N^2)$$

review rounds and serial CI execution cycles.

### The nature of the churn

As detailed in [`batch-merge-and-resolve.md`](batch-merge-and-resolve.md),
a `DIRTY` or `BEHIND` status caused by base advancement is staleness rather than a defect.
None of the N PRs carry flawed code or merge conflicts.
The churn is purely structural:
the requirement to test each PR against `main` before merge forces repeated, redundant re-validation on every intermediate base advance.

Each re-triggered review round consumes both billable LLM tokens and serial wall-clock time.
On repositories where CI and automated review take several minutes per round,
clearing a queue of 5 ready PRs costs 10 extra review rounds and substantial serial latency.

## How merge queues eliminate quadratic churn

A GitHub merge queue solves this bottleneck by managing speculative merge trees on the forge side.

```text
                    +--- PR 1 (tested against main) ------------------> Merged to main
                    |
main ---> Queue ----+--- PR 2 (speculatively tested against main + PR 1) --> Merged to main
                    |
                    +--- PR 3 (speculatively tested against main + PR 1 + PR 2) --> Merged to main
```

1. **Queue entry:** When a PR passes review and required pre-merge checks, it is added to the merge queue (`gh pr merge <PR>` or `gh pr merge --auto` --- the `gh` CLI automatically detects that the base branch requires a merge queue and submits the PR to the queue).
2. **Speculative branches:** GitHub creates temporary merge branches (e.g. `gh-readonly-queue/main/pr-...`) that speculatively merge queued PRs in sequence.
3. **Single CI pass:** Required checks run on the speculative merge commit rather than requiring developers or bots to update individual feature branches.
4. **Fast-forward merge:** When checks on a speculative commit pass, GitHub updates `main` directly.
   Sibling PRs already queued behind it continue running against their speculative trees without being marked `BEHIND` or re-triggering feature-branch reviews.

The total review and CI cost drops from O(N^2) to O(N) individual runs.
When merge queue batching is enabled (grouping multiple PRs into a single speculative merge commit),
cost drops further to O(N / K) where K is the batch size.

### Speculative failure isolation

If a PR in the queue fails CI (or introduces a semantic incompatibility with an earlier queued PR),
GitHub automatically evicts the failing PR from the queue.
It then reconstructs the speculative branches for subsequent PRs without the failed entry and re-runs checks automatically.
Healthy PRs land without manual rebase or re-sync interventions.

## Repository configuration

Merge queues are configured via repository rulesets or branch protection rules on `main`.

### Ruleset configuration

In repository settings under **Rulesets** -> **Rules** -> **Require merge queue**:

- **Merge method:** Select `SQUASH` (or `MERGE` / `REBASE` depending on repo convention).
- **Grouping strategy:**
  - `ALLGREEN`: All PRs in a speculative batch must pass CI before merging together.
  - `HEADGREEN`: PRs merge individually as soon as their speculative prefix passes.
- **Batch size:** Configure `min_entries_to_merge` (minimum PRs before testing a batch, typically 1) and `max_entries_to_merge` (maximum batch size, e.g. 5).
- **Check response timeout:** Maximum time allowed for CI to complete before timing out a queued entry (e.g. 60 minutes).

### Workflow event trigger

Workflows containing required status checks must listen for the `merge_group` event in addition to `pull_request` and `push`.
Without `merge_group`, GitHub Actions will not run checks on speculative queue branches, causing queued PRs to hang indefinitely until timeout.
The queue blocks only on required checks, so a clean-gate check that is not required, or is `pull_request`-only, neither runs on the speculative branch nor holds the merge.
Before the queue replaces the manual update, every check in the clean gate has to be required (or aggregated behind a required one) and has to execute on `merge_group`, per [`fully-clean`](fully-clean.md)'s merge-gate section.

```yaml
name: CI

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]
  merge_group:
    types: [checks_requested]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run test suite
        run: make test
```

## Comparison with alternatives

| Strategy | CI / Review Cost | Conflict / Regression Risk | Developer & Harness Effort |
|---|---|---|---|
| **Strict branch protection without queue** | O(N^2) | Low (always tested against latest base) | High (serial `update-branch` chasing) |
| **Non-strict branch protection (`strict: false`)** | O(N) | Medium (disjoint changes merge cleanly, but semantic conflicts reach `main`) | Low (immediate merge on approval) |
| **Manual batch trains (integration branch)** | O(N) | Low (tested together on train branch) | High (manual branch coordination and cherry-picking) |
| **GitHub Merge Queue** | O(N) or O(N / K) | Low (speculative merge testing guarantees clean `main`) | Minimal (automated queue handoff) |

- **Do:** enable `merge_group` event triggers on all workflows that provide required status checks.
- **Do:** use merge queues to automate pre-merge speculative testing when landing multiple PRs in parallel.
- **Do:** treat base-advance staleness on queued PRs as a platform queue concern rather than an immediate need for manual branch re-syncing.
- **Don't:** run manual `gh pr update-branch` loops on simultaneously ready PRs when a merge queue is active.
- **Don't:** omit the `merge_group` trigger from CI workflows when enabling merge queue rulesets.
