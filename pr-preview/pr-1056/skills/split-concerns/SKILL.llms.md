# split-concerns

When a set of changes addresses multiple independent concerns, split them into separate MRs/PRs rather than bundling everything together.

## When this fires

- You’re about to commit changes that touch unrelated subsystems
- A reviewer flags “this MR does too many things”
- You notice your commit message needs “and” more than once
- The diff is large and contains logically separable chunks
- One part of the change is controversial but another is straightforward

## What counts as “independent concerns”

Two changes are independent if: - They could be merged in either order without conflict - They solve different problems / close different issues - A revert of one wouldn’t affect the other - They’d have different reviewers in an ideal world

Examples: - Bug fix + unrelated refactor → split - Feature + the test for that feature → keep together - CI template fix + documentation update for that fix → keep together - CI template fix + unrelated linter config change → split - Dependency update + code that uses the new dependency → keep together

## Process

1.  **Identify the concerns** — list each logically independent change

2.  **Assess dependencies** — can they be merged independently?

3.  **Propose the split** to the user:

        This MR addresses 3 independent concerns:
        1. Fix the review job trigger (closes #32)
        2. Update stage naming convention
        3. Add shellcheck to CI

        Want me to split these into separate MRs? They can merge independently
        and won't block each other during review.

4.  **If approved**, create the branches:

    - Start each from `main` (not from each other)
    - Cherry-pick or recreate the relevant commits on each branch
    - Open separate MRs with focused descriptions
    - Cross-reference them (“Related: \#25, \#26”)

## Benefits to communicate

- **Faster review** — smaller diffs are easier to review thoroughly
- **Independent timelines** — a simple fix can merge while a complex change is still being discussed
- **Cleaner history** — each merge commit tells one story
- **Lower risk** — if one change causes a regression, the revert is surgical
- **Better CI signal** — failures are attributable to a specific change

## When NOT to split

- Changes are tightly coupled (splitting would break one or both)
- The total diff is small (\<50 lines) and splitting adds more overhead than value
- User explicitly says “keep it in one MR”
- The concerns share significant context that would be lost if separated

Back to top
