---
name: split-concerns
description: "Split multi-concern PRs."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# split-concerns

When a set of changes addresses multiple independent concerns, split them
into separate MRs/PRs rather than bundling everything together.

## When this fires

- You're about to commit changes that touch unrelated subsystems
- A reviewer flags "this MR does too many things"
- You notice your commit message needs "and" more than once
- The diff is large and contains logically separable chunks
- One part of the change is controversial but another is straightforward

## What counts as "independent concerns"

Two changes are independent if:
- They could be merged in either order without conflict
- They solve different problems / close different issues
- A revert of one wouldn't affect the other
- They'd have different reviewers in an ideal world

Examples:
- Bug fix + unrelated refactor → split
- Feature + the test for that feature → keep together
- CI template fix + documentation update for that fix → keep together
- CI template fix + unrelated linter config change → split
- CI/workflow change (`.github/workflows/`) + heavy simulation/validation dataset artifacts (`inst/extdata/*.rds`, `*.parquet`, `*.RData`) → split
- CI/workflow change (`.github/workflows/`) + HPC job array updates → split
- Heavy simulation/validation dataset artifacts (`inst/extdata/*.rds`, `*.parquet`, `*.RData`) + HPC job array updates → split
- Dependency update + code that uses the new dependency → keep together

## Process

1. **Identify the concerns** — list each logically independent change
2. **Assess dependencies** — can they be merged independently?
3. **Propose the split** to the user:
   ```
   This MR addresses 3 independent concerns:
   1. Fix the review job trigger (closes #32)
   2. Update stage naming convention
   3. Add shellcheck to CI

   Want me to split these into separate MRs? They can merge independently
   and won't block each other during review.
   ```
4. **If approved**, create the branches:
   - Start each from `main` (not from each other)
   - Cherry-pick or recreate the relevant commits on each branch
   - Open separate MRs with focused descriptions
   - Cross-reference them ("Related: #25, #26")

## Benefits to communicate

- **Faster review** — smaller diffs are easier to review thoroughly
- **Independent timelines** — a simple fix can merge while a complex change
  is still being discussed
- **Cleaner history** — each merge commit tells one story
- **Lower risk** — if one change causes a regression, the revert is surgical
- **Better CI signal** — failures are attributable to a specific change

## When NOT to split

- Changes are tightly coupled (splitting would break one or both)
- The total diff is small (<50 lines) and splitting adds more overhead than value
- User explicitly says "keep it in one MR"
- The concerns share significant context that would be lost if separated

## When unsure how finely to split, split finer

When the split could reasonably go either way,
take the finer one.
A split that turns out too fine costs bookkeeping:
one more PR to open,
and sometimes a temporary gap between the PRs,
such as a link to content that the later PR has not yet added,
which stays broken until that PR lands.
A split that is too coarse gives up the "Benefits to communicate" above,
most visibly faster review and independent timelines.

- **Do:** pick the finer split when both are defensible,
  and accept a temporary gap that a later PR closes.
- **Don't:** settle on the coarser split just because it means fewer PRs to manage.
- **Don't:** stretch the judgment items in "When NOT to split" above into tiebreakers.
  The small-diff item applies to a diff that really is under 50 lines,
  and the shared-context item only when a reviewer of one PR
  could not follow it without reading the other's diff.
  Context that a cross-reference ("Related: #N") carries is not lost.

(Directive from the user, 2026-09-25:
"when uncertain, err on the side of more decomposition",
said about splitting a large lecture-notes consolidation into PRs.)
