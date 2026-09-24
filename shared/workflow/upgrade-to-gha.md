`Morrison-Lab/gha` is the lab's repository of reusable GitHub Actions workflows.
A consumer repo calls one with a small stub rather than carrying its own copy:

```yaml
jobs:
  check:
    uses: Morrison-Lab/gha/.github/workflows/check-bibliography-dois.yml@v2
```

When a repo you are working in hand-maintains a workflow gha already provides, migrate it.
The upgrade is the deliverable, not the observation.

[`dont-reinvent-wheel`](../principles/dont-reinvent-wheel.md) is the parent principle and supplies the detection tell this rule reuses.
What it does not supply is a trigger for the unprompted case, which is what follows.

## Why this needs its own trigger

Three rules already name a condition for reaching toward gha, and each waits for an event:

- [`dont-reinvent-wheel`](../principles/dont-reinvent-wheel.md)'s "A stale, un-migrated local copy is the least reliable place to fix a bug" fires when you are **about to patch a bug** in a workflow file.
- The same fragment's "Close the loop once the port lands" fires when **gha has just gained** a capability a consumer already had locally.
- [`gha-reusable-workflows.md`](../../memories/gha-reusable-workflows.md) opens with "Check `Morrison-Lab/gha` before writing bespoke CI", which fires when you are **about to write new CI**.

Those three are the migration-condition rules, not every mention of gha in the corpus.
Many more files mention gha without naming one --- `git grep -l gha <ref> -- '*.md' | wc -l` counts them at whatever ref you hand it --- and some route work toward gha for reasons that are not migration at all: [`config-ai`](../../skills/config-ai/SKILL.md)'s routing table picks gha as the home for a new shared capability, and [`convert-repo-format`](../../skills/convert-repo-format/SKILL.md) assumes a target template already calls it.
None of those decides whether an existing repo should migrate.

And none of the three reaches the commonest case.
You are in the repo for an unrelated reason, its `.github/workflows/` already carries a hand-maintained copy of something gha ships, and nothing is broken today.
No bug prompts the first, no port prompts the second, and you are writing no CI at all, so the third stays silent too.

The duplicate is therefore never noticed, and the incentive runs backwards: the longer a standalone workflow has sat there, the more fixes gha has absorbed that it has not, and the more ordinary it looks for having been there so long.

## What makes a repo a candidate

"Would benefit" is a judgment, so name which of these you found, and how you established it:

- **Duplication.**
  A workflow file in the repo does what a gha reusable workflow does.
  The README's "Available reusable workflows" table is the inventory: it lists the consumer-callable capabilities and what each covers.
  `gh api repos/Morrison-Lab/gha/contents/.github/workflows --jq '.[].name'` is a cross-check rather than the inventory, since it also returns gha's own caller stubs, its maintenance workflows, and a `scripts` directory.
- **Drift.**
  The local copy was a port from gha, or gha was a port from it, and the two have since diverged.
  A drift claim is relational, so name both artifacts and read both, per [`verify-the-right-artifact`](verify-the-right-artifact.md).
  Reading the canonical version's own comments is usually faster than diffing, since a mature reusable workflow records its incident history in its source.
- **Missing fixes.**
  The local copy predates fixes gha carries.
  This is the invisible one --- the workflow passes, so nothing reports the fixes it never received --- which means it needs a derivation rather than an impression: read gha's `CHANGELOG.md` and the capability's own commit history since the fork point, and name a specific fix the local copy lacks.
  A candidate you cannot name a missing fix for is not this condition.
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
  Re-argue it explicitly if you disagree.
  Do not migrate around it, per [`incidents-dont-repeal-decisions`](incidents-dont-repeal-decisions.md).
- **A repo we do not administrate.**
  The operative test is whether we can merge a PR to that repo, not whether its owner appears on a list.
  The gha README names `the repository owner`, `ucdavis`, `UCD-SERG`, `UCLA-PHP`, and `UCD-IDDRC` as the owners it is public for, and that sentence predates the `Morrison-Lab` org, so it omits the owner gha itself lives under along with `Morrison-Lab/ai-config`, `Morrison-Lab/wai`, and `Morrison-Lab/psw`, each a documented consumer.
  Read the list as evidence of reach rather than as an allowlist, and treat a repo outside our administration as a question for its maintainer rather than a migration to perform.

Both [`claude-review-workflow`](../../skills/claude-review-workflow/SKILL.md) and [`claude-agent-workflow`](../../skills/claude-agent-workflow/SKILL.md) author caller stubs delegating to `Morrison-Lab/gha/.github/workflows/claude-code-review.yml@v2` and `Morrison-Lab/gha/.github/workflows/claude.yml@v2` (reconciled under [ai-config#2133](https://github.com/Morrison-Lab/ai-config/issues/2133)).

## The migration is its own change

A repo you entered for an unrelated reason is not a licence to reshape its CI inside that task.
[`restructure-for-efficiency`](restructure-for-efficiency.md) draws the same line for token cost: the change belongs in its own issue or PR, where someone can disagree with it.
So file the issue per [`issue-first`](issue-first.md) and migrate under it, rather than folding the upgrade into whatever brought you there.

Filing is not gated on approval, per [`report-mistakes-proactively`](report-mistakes-proactively.md), so a candidate you cannot migrate this session still becomes a tracked issue naming which condition you found.

## Pin per capability, not uniformly

`@v1` was frozen at the pre-`2.0.0` snapshot, so the recommended major tag varies by workflow rather than defaulting to one answer.
Measured 2026-08-24: most capabilities want `@v2`, and three --- `summary`, `bump-submodule`, and `sync-shared-fragments` --- remain current at `@v1`.
That split moves as capabilities are added, so read gha's README "Versioning" section for the current one rather than copying a tag from a neighbouring caller, and never reference `@main` from a consumer.

## Read the migration hazards before writing the stub

A stub that resolves is not yet a stub that runs.
One precondition and two traps, the traps being specific to migration rather than to gha in general.
[`gha-reusable-workflow-permissions.md`](../../memories/gha-reusable-workflow-permissions.md) carries both traps in full.

- **A private consumer must be granted access first.** gha is public, so public repos can call its reusable workflows automatically.
  A private repo cannot until someone allows access under Settings, Actions, General, Access --- a human step, so establish it before the migration rather than after the first red run.
- **An under-granted permission fails the whole call with `startup_failure` and zero jobs.**
  `gh run view` prints only the generic `This run likely failed because of a workflow file issue`.
  The REST jobs endpoint returns an empty array, and `gh pr checks` shows nothing, because no check run exists to attach an annotation to.
  The text naming the job and the permission exists only in the rendered Actions run page's Annotations panel.
  A called reusable workflow cannot hold more `GITHUB_TOKEN` permission than the caller grants, and most repos default to read-only, so copy the `permissions:` block from the matching `examples/<name>.yml`.
- **Carrying the old workflow's `concurrency:` group across deadlocks the run.**
  Preserving an existing per-PR dedup group is the natural thing to write during a migration, and where the reusable workflow already declares an identically-named group on a nested job, GitHub cancels the run outright every time.
  The reusable workflow supplies that dedup itself, so the caller needs no block.

The `examples/` stub is authoritative for `permissions:` and not for `secrets:`: [`gha-reusable-workflows.md`](../../memories/gha-reusable-workflows.md) records an example passing a secret the tagged workflow does not declare, which fails the caller at startup.
So fetch the workflow file at the tag you are pinning and read its own `workflow_call: secrets:` block.

## A migration PR that touches the review caller may not be bot-reviewed

Where the workflow being migrated is `claude-code-review.yml` itself, the reusable workflow can detect the self-edit and deliberately skip, posting no review, and the review gate tolerates the skip.

Confirm that is what happened rather than assuming it, because the same missing review has other causes --- a stale tag, and at least one measured transient `502` during the action's actor-permission check.
The self-edit skip is a fast (roughly 9-second) **green** `review / claude-review` job, and the job log carries a `::notice::` line naming the file and the reason.
Read that line.
A red review check is a different case entirely and routes to [`self-review-fallback`](self-review-fallback.md).

Once confirmed, re-dispatching reproduces the skip, so take the other route: the agent workflow (`claude.yml`) carries no equivalent guard, and a comment mentioning the bot still yields a genuine external verdict at the current head --- which is what [`fully-clean`](fully-clean.md)'s criterion 2 wants and a self-review cannot supply.
Post that comment deliberately, and note that the trigger is a raw substring test with no notion of code spans, so write the bot's at-mention only when you intend to fire it (see [`mention-triggers.md`](../../memories/mention-triggers.md)).

- **Do:** name the specific candidate condition you found --- duplication, drift, missing fixes, or a partially migrated directory --- and migrate the workflow rather than reporting it.
- **Do:** take the inventory from gha's README table, and each capability's tag from its Versioning section.
- **Do:** compare the local workflow's inputs against the reusable workflow's `workflow_call` block, and send a PR to gha for whatever it does not yet model.
- **Do:** file the migration as its own issue and PR.
- **Do:** copy the caller's `permissions:` block from the matching `examples/<name>.yml`, and read `secrets:` from the workflow file at the tag you are pinning.
- **Do:** read the job log's `::notice::` line before concluding that a missing review on a migration PR was the self-edit guard, then get the verdict from the agent bot.
- **Don't:** report a hand-rolled duplicate as an observation and move on --- that is the failure this rule names, and it reads as diligence.
- **Don't:** migrate a workflow carrying repo-specific logic gha does not model, one a prior decision deliberately kept local, or one in a repo we cannot merge a PR to.
- **Don't:** derive the inventory from gha's workflow-directory listing alone.
  It also returns caller stubs and maintenance workflows that are not consumer-callable.
- **Don't:** copy a `@v2` or `@v1` tag from a neighbouring caller.
  The recommended tag is per-capability.
- **Don't:** carry the old workflow's `permissions:` or `concurrency:` blocks across unexamined --- grant what the example grants, and drop the concurrency block entirely.
- **Don't:** fold the migration into the PR for whatever brought you to the repo.
- **Don't:** re-dispatch a review the self-edit guard skipped, or read a confirmed skip as a defect in the PR.

(Directive from the user, 2026-08-24: "cai: if a repo isn't using gha and would benefit, upgrade it".
Filed as [ai-config#2126](https://github.com/Morrison-Lab/ai-config/issues/2126).
Measured 2026-08-24: `git show origin/main:AGENTS.md | grep -ci gha` returned 0, so the cross-agent contract carried no gha guidance before this rule.
The ai-config repo is itself a consumer --- `grep -rho 'gha/\.github/[a-z]*/[a-z-]*' .github/workflows/ | sort -u` returned nine reusable workflows and one composite action on the same date.
`ucdavis/win#75`, merged 2026-07-17, is the worked migration: the PR converting that repo's hand-rolled review workflow to a gha caller could never itself be bot-reviewed, and win#69 then ran the migrated workflow live.)

## A new repo's counterpart: CI ships in the first PR, not later

Everything above is about a repo that already exists and already has some CI, hand-rolled or otherwise.
It says nothing about a repo that has neither yet, and that gap is exactly what let `Morrison-Lab/mlr` get created with no `.github/workflows/` at all (2026-09-24).
No hand-maintained workflow existed to migrate, so `dont-reinvent-wheel`'s own detection tell --- a local copy of something gha already ships --- never fired, and the repo shipped with nothing catching a leaked secret, a malformed workflow, or a typo until someone thought to add it later.
"Later" is the failure mode this section names: a repo with real content and no CI accumulates exactly the defects CI exists to catch, for however long "later" takes.

So when creating a new repository, add CI in the same first PR that creates the repo's initial content, not as a follow-up once something is already there to break.
An empty repo with no workflows is not a clean slate;
it is a repo whose CI has not been written yet.

### The baseline set

Every new repo gets these gha-backed callers, whatever the repo's purpose, because none of them depends on the repo having any particular language or build system:

- `claude-review.yml` + `claude-bot.yml` --- the AI review and agent-dispatch pair, pinned per `claude-code-review.yml`'s and `claude.yml`'s own reference pages (`@v2` as of this writing;
  read gha's README Versioning section rather than copying that number).
- `check-secrets.yml` --- the gitleaks history scan.
- `check-junk-files.yml` --- tracked OS/editor detritus.
- `check-typos.yml` --- misspellings on the lines a PR adds.
- `lint-workflows.yml` --- actionlint plus zizmor over `.github/`, together with a `.github/zizmor.yml` accepting tag pins and a `.github/dependabot.yml` keeping those tags current (`Morrison-Lab/mln`'s copies of both are the pattern to start from).

### Add whatever fits the repo type on top of that

The baseline is deliberately generic.
A repo's actual content decides the rest: an R package wants `r-cmd-check.yml` and friends, a Quarto site wants `preview.yml`/`preview-deploy.yml`/`quarto-publish.yml`, and so on.
Take the inventory and the pin from gha's README table, exactly as the migration case above does --- this is not a separate lookup, only an earlier one.

"Any other appropriate sources" (the user's own phrase) means: where gha has no matching capability, reach for a well-maintained third-party action or `r-lib/actions` rather than hand-rolling one, pinned per the gha README's "Pinning third-party actions" subsection.
That subsection's SHA-pinning guidance applies to a third-party action exactly as it would if you were adding it to gha itself;
it does not relax because the action lives in a consumer repo instead.

### The fastest route is copying a sibling repo's callers

A sibling repo of the same shape almost certainly already has this worked out.
`Morrison-Lab/mln`'s `.github/` is a private-repo Quarto-site example carrying the whole baseline set plus `check-equation-renders.yml`, `check-new-line-breaks.yml`, `check-ai-tells.yml`, and the Quarto preview/publish chain;
a private R-package repo would instead start from `Morrison-Lab/gha`'s own `examples/` stubs or from `Morrison-Lab/qwt`/`rpt` template repos (see `Morrison-Lab/gha`'s own CLAUDE.md, "Test changes against a template repo").
Copy the caller stubs wholesale and then adapt only what is genuinely repo-specific --- the `claude-bot.yml` header comment naming the repo's own visibility posture, a `review-workflow-file:` value, any `install-quarto`/`setup-r` flags the new repo's content actually needs.
Do not copy blind: a caller file carries prose that describes the repo it came from, and leaving that prose unedited in the new repo is a smaller version of the same problem `check-the-renders.md` names for a stale claim about a different artifact.

- **Do:** add `.github/workflows/` in the repo's first PR, alongside its first real content, not in a later PR.
- **Do:** start from the baseline set (`claude-review` + `claude-bot`, `check-secrets`, `check-junk-files`, `check-typos`, `lint-workflows` with `zizmor.yml` and `dependabot.yml`), then add what the repo's type needs.
- **Do:** copy a sibling repo's callers as the fast path, and actually re-read the copied prose rather than leaving it describing the wrong repo.
- **Do:** reach for a well-maintained third-party action or `r-lib/actions`, SHA-pinned per gha's own third-party-pinning guidance, wherever gha itself has no capability.
- **Don't:** create a repo with no `.github/workflows/` at all and plan to add CI "later" --- that is the exact failure this section exists to name.
- **Don't:** treat the baseline set as optional scaffolding to skip for a small or private repo;
  `Morrison-Lab/mlr` was both, and shipped with no CI anyway.
- **Don't:** invent a bespoke workflow for something gha or a well-maintained third-party action already covers, even in a repo too new to have accumulated the migration-condition history the section above looks for.
- **Don't:** copy a sibling's caller stub and leave its repo-specific prose (visibility notes, `review-workflow-file:`, feature flags) pointed at the sibling instead of the new repo.

(Directive from the user, Ezra, 2026-09-24: "cai: let's set up CI workflows, using gha and any other appropriate sources, by default when starting new repos".
Filed as [ai-config#3978](https://github.com/Morrison-Lab/ai-config/issues/3978).
Originating case: `Morrison-Lab/mlr` was created with no CI at all.)
