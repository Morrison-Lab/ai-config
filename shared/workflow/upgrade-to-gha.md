`Morrison-Lab/gha` is the lab's repository of reusable GitHub Actions workflows.
A consumer repo calls one with a small stub rather than carrying its own copy:

```yaml
jobs:
  check:
    uses: Morrison-Lab/gha/.github/workflows/check-bibliography-dois.yml@v2
```

When a repo you are working in hand-maintains a workflow gha already provides, migrate it.
The upgrade is the deliverable, not the observation.

[`dont-reinvent-wheel`](../principles/dont-reinvent-wheel.md) is the parent principle and supplies the detection tell this rule reuses; what it does not supply is a trigger for the unprompted case, which is what follows.

## Why this needs its own trigger

Three rules already point at gha, and each waits for a different event:

- [`dont-reinvent-wheel`](../principles/dont-reinvent-wheel.md)'s "A stale, un-migrated local copy is the least reliable place to fix a bug" fires when you are **about to patch a bug** in a workflow file.
- The same fragment's "Close the loop once the port lands" fires when **gha has just gained** a capability a consumer already had locally.
- [`gha-reusable-workflows.md`](../../memories/gha-reusable-workflows.md) opens with "Check `d-morrison/gha` before writing bespoke CI", which fires when you are **about to write new CI**.

None of the three reaches the commonest case.
You are in the repo for an unrelated reason, its `.github/workflows/` already carries a hand-maintained copy of something gha ships, and nothing is broken today.
No bug prompts the first, no port prompts the second, and you are writing no CI at all, so the third stays silent too.

The duplicate is therefore never noticed, and the incentive runs backwards: the longer a standalone workflow has sat there, the more fixes gha has absorbed that it has not, and the more ordinary it looks for having been there so long.

## What makes a repo a candidate

"Would benefit" is a judgment, so name which of these you found:

- **Duplication.**
  A workflow file in the repo does what a gha reusable workflow does.
  Derive the inventory rather than recalling it: `gh api repos/Morrison-Lab/gha/contents/.github/workflows --jq '.[].name'`, then read the README's "Available reusable workflows" table for what each one covers.
- **Drift.**
  The local copy was a port from gha, or gha was a port from it, and the two have since diverged.
  A drift claim is relational, so name both artifacts and read both, per [`verify-the-right-artifact`](verify-the-right-artifact.md).
  Reading the canonical version's own comments is usually faster than diffing, since a mature reusable workflow records its incident history in its source.
- **Missing fixes.**
  The local copy predates fixes gha carries.
  This is the invisible one: the workflow passes, so nothing reports the fixes it never received.
- **A partially migrated repo.**
  Other files in the same directory already `uses: Morrison-Lab/gha/...`, and some do not.
  This is `dont-reinvent-wheel`'s structural tell, and it is the strongest single signal, because the standalone files are precisely the ones nobody revisited when the shared version absorbed their capability.

## What makes a repo not a candidate

The boundary matters as much as the trigger, because a migration that drops behaviour is worse than the duplication it removed.

- **Genuinely repo-specific logic gha does not model.**
  Compare the local workflow's inputs and steps against the reusable workflow's `workflow_call` block before concluding the two are equivalent.
  Where gha covers most of it and misses one input, the fix is a PR to gha adding that input, rather than a migration that silently drops it --- gha is a repo we administrate, so its limit is self-imposed rather than external (see [`dont-reinvent-wheel`](../principles/dont-reinvent-wheel.md), "A constraint your own change authored is not evidence against an upstream", and [`upstream-issues`](upstream-issues.md) for the etiquette).
- **A repo deliberately pinned off gha.**
  A comment, an issue, or a prior decision saying so is a decision, not an oversight.
  Re-argue it explicitly if you disagree; do not migrate around it, per [`incidents-dont-repeal-decisions`](incidents-dont-repeal-decisions.md).
- **A repo outside the owners gha serves.**
  The gha README names `d-morrison`, `ucdavis`, `UCD-SERG`, `UCLA-PHP`, and `UCD-IDDRC`, and the gha repo is public so any of them can reference it.
  A repo outside those owners is a question for its maintainer rather than a migration to perform.

## The migration is its own change

A repo you entered for an unrelated reason is not a licence to reshape its CI inside that task.
[`restructure-for-efficiency`](restructure-for-efficiency.md) draws the same line for token cost: the change belongs in its own issue or PR, where someone can disagree with it.
So file the issue per [`issue-first`](issue-first.md) and migrate under it, rather than folding the upgrade into whatever brought you there.

Filing is not gated on approval, per [`report-mistakes-proactively`](report-mistakes-proactively.md), so a candidate you cannot migrate this session still becomes a tracked issue naming which condition you found.

## Pin per capability, not uniformly

`@v1` was frozen at the pre-`2.0.0` snapshot, so the recommended major tag varies by workflow rather than defaulting to one answer.
Most capabilities want `@v2`; a few remain current at `@v1`.
Read gha's README "Versioning" section for the current split rather than copying a tag from a neighbouring caller, and never reference `@main` from a consumer.

## Read the migration hazards before writing the stub

A stub that resolves is not yet a stub that runs, and two consumer-side traps are specific to migration rather than to gha in general.
[`gha-reusable-workflow-permissions.md`](../../memories/gha-reusable-workflow-permissions.md) carries both in full:

- **An under-granted permission fails the whole call with `startup_failure` and zero jobs**, which `gh run view`, the REST jobs endpoint, and `gh pr checks` all report as nothing at all.
  The error text naming the job and permission exists only in the rendered Actions run page's Annotations panel.
  A called reusable workflow cannot hold more `GITHUB_TOKEN` permission than the caller grants, and most repos default to read-only, so copy the `permissions:` block from the matching `examples/<name>.yml`.
- **Carrying the old workflow's `concurrency:` group across deadlocks the run.**
  Preserving an existing per-PR dedup group is the natural thing to write during a migration, and where the reusable workflow already declares an identically-named group on a nested job, GitHub cancels the run outright every time.
  The reusable workflow supplies that dedup itself, so the caller needs no block.

Fetch the workflow file at the tag you are pinning and read its `workflow_call: secrets:` block too, rather than copying an `examples/` stub; [`gha-reusable-workflows.md`](../../memories/gha-reusable-workflows.md) records the two disagreeing.

## A migration PR that touches the review caller cannot be bot-reviewed

Where the workflow being migrated is `claude-code-review.yml` itself, the reusable workflow detects the self-edit and deliberately skips, posting no review, and the review gate tolerates the skip.
That is the guard working, not a stub and not a defect, so re-dispatching the review reproduces it.

The agent workflow (`claude.yml`) carries no equivalent guard, so a deliberate mention comment still yields a genuine external verdict at the current head --- which is what [`fully-clean`](fully-clean.md)'s criterion 2 wants, and what a self-review cannot supply.
Take that route rather than reporting the PR ready on a self-review alone.

- **Do:** name the specific candidate condition you found --- duplication, drift, missing fixes, or a partially migrated directory --- and migrate the workflow rather than reporting it.
- **Do:** derive gha's inventory from its own contents listing, and take each capability's tag from the README's Versioning section.
- **Do:** compare the local workflow's inputs against the reusable workflow's `workflow_call` block, and send a PR to gha for whatever it does not yet model.
- **Do:** file the migration as its own issue and PR, so the upgrade is reviewable separately from whatever brought you to the repo.
- **Do:** get the external verdict from the agent bot when the review workflow's self-edit guard skips the migration PR.
- **Don't:** report a hand-rolled duplicate as an observation and move on --- that is the failure this rule names, and it reads as diligence.
- **Don't:** migrate a workflow carrying repo-specific logic gha does not model, or one a prior decision deliberately kept local.
- **Don't:** copy a `@v2` or `@v1` tag from a neighbouring caller; the recommended tag is per-capability.
- **Don't:** carry the old workflow's `permissions:` or `concurrency:` blocks across unexamined.
- **Don't:** re-dispatch a review the self-edit guard skipped, or read that skip as a defect in the PR.

(Directive from the user, 2026-08-24: "cai: if a repo isn't using gha and would benefit, upgrade it".
Filed as [ai-config#2126](https://github.com/Morrison-Lab/ai-config/issues/2126).
Measured the same day: `AGENTS.md` mentioned `gha` zero times before this rule, so the cross-agent contract carried no gha guidance at all, and the three triggers named above were the corpus's complete coverage of when to reach for it. ai-config is itself a consumer, calling gha for `quarto-publish`, the PR-preview family, `claude-code-review`, `claude`, `sync-shared-fragments`, `check-new-line-breaks`, and `lint-qmd`.
`ucdavis/win#75`, 2026-07-16, is the worked migration: the PR converting that repo's hand-rolled review workflow to a gha caller could never itself be bot-reviewed, and win#69's post-merge sync then ran the migrated workflow live.)
