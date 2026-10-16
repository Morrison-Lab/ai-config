# Always refactor before modifying substance

Always refactor before modifying substance,
and do the modifications in a separate PR stacked on top of the refactor PR,
so it is easier to see what is actually changing.

Never bundle structural refactoring (extracting helpers,
moving code,
renaming symbols,
reorganizing modules)
and substantive modifications (changing logic,
fixing bugs,
altering behavior,
adding features)
into the same pull request.

## The problem with commingling

When a PR mixes structural reorganization with behavioral changes:

- **Reviewability collapses**:
  reviewers cannot easily distinguish behavior-preserving movements from behavioral alterations.
- **Regressions hide**:
  subtle logic bugs and off-by-one errors easily slip past notice inside large diffs of moved or reformatted lines.
- **Reversion is painful**:
  if the substantive change causes an issue in production,
  reverting it also discards the clean structural improvement.
- **Review velocity stalls**:
  an uncontroversial refactor cannot land while the substantive change is still being debated or revised.

This operationalizes Kent Beck's classic maxim:
"Make the change easy, then make the easy change."

## The two-PR stacked workflow

When a substantive change requires or benefits from structural refactoring:

1. **PR 1 (Base --- pure refactor)**:
   Create a dedicated branch off `main` for the refactoring.
   This PR must be strictly behavior-preserving:
   zero logic changes,
   zero output differences,
   and all existing test suites must pass without changing expected results.
   Open this PR against `main`.
2. **PR 2 (Stacked --- substantive modification)**:
   Branch off the tip of PR 1's branch using [`stack-prs`](../../skills/stack-prs/SKILL.md).
   Point the PR base to PR 1's branch rather than `main`.
   Implement the substantive change,
   its new tests,
   and any updated expectations here.
   The diff on PR 2 against PR 1 will be small,
   sharp,
   and focused exclusively on the substantive modification.

Lead the substantive PR's description with the merge-order alert prescribed by [`surface-merge-order`](../workflow/surface-merge-order.md) and [`stack-prs`](../../skills/stack-prs/SKILL.md):

```markdown
> [!IMPORTANT]
> Merge #<base-N> first --- this PR is stacked on its branch.

Stacked on #<base-N>.
```

## Do and Don't

- **Do:** split work into a pure behavior-preserving refactor PR and a separate substantive modification PR stacked on top of it.
- **Do:** verify that the base refactoring PR introduces zero behavioral change and passes all existing tests untouched.
- **Do:** point the substantive PR's base to the refactor branch using [`stack-prs`](../../skills/stack-prs/SKILL.md) so its diff shows only the substantive modification.
- **Do:** format PR merge-order notices using the established `> [!IMPORTANT]` alert and `Stacked on #<base-N>` convention per [`surface-merge-order`](../workflow/surface-merge-order.md) and [`stack-prs`](../../skills/stack-prs/SKILL.md).
- **Don't:** commingle structural refactoring and substantive modifications in a single commit or PR.
- **Don't:** sneak logic or behavioral fixes into a "refactoring" PR;
  keep the refactor strictly behavior-preserving.
- **Don't:** settle for a large, noisy diff where behavioral alterations hide among moved or reformatted lines.
- **Don't:** invent ad-hoc cross-reference phrasing when standardized stacking conventions already exist.

(2026-10-07, Morrison-Lab/ai-config#4339:
directive from Douglas Ezra Morrison:
"always refactor before modifying substance and do the modifications in a separate PR stacked on top of the refactor PR, so it's easier to see what's actually changing.")
