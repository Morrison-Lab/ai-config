# Admitting site vs branching site

When enabling a new condition, trigger, or input case,
that condition must be handled at two distinct sites that must agree:

1. **The admitting site:**
   the guard, rule, or filter that decides whether the code **runs** for that case.
2. **The branching site:**
   the downstream execution logic that decides what the code **does** once it runs.

Fixing only the admitting site makes the code execute for the new case,
but leaves the downstream execution logic branching on variables or assumptions
that are invalid, empty, or defaulted for that case.
This creates a false sense of completion:
the diff mentions the condition,
the admitting rule matches the finding's wording,
and CI runs green,
while the actual execution path silently does the wrong thing.

## Why half-fixes survive self-review

A half-fix at the admitting site is peculiarly resistant to casual self-review:

- **The finding names the admitting condition:**
  A review comment or issue typically says "Job X does not run on tags"
  or "Feature Y ignores webhook events".
  The wording directs attention to the admission gate.
- **The diff matches the finding:**
  Adding the admitting rule (e.g. `- if: $CI_COMMIT_TAG`) matches the requested change.
  Reviewing the diff shows the named concept present and accounted for.
- **The branching site never names the new condition:**
  The downstream code that needs changing is the site that *does not* mention the new condition.
  Searching the codebase for the named concept finds only the admitting site you just edited.
- **The branching variable goes silently empty:**
  The downstream code often tests an alternative variable that becomes empty or unset
  under the new condition (e.g. `CI_COMMIT_BRANCH` is empty on a tag pipeline).
  The condition `"${CI_COMMIT_BRANCH}" = "main"` evaluates to false,
  silently routing the new case down an unintended fallback path (such as a diff against an unrelated branch).
- **Shallow tests pass:**
  Text-matching tests or configuration linters only verify that the admitting rule exists in the manifest.
  Because CI rarely triggers the newly admitted condition during the PR itself,
  the defect survives until an external reviewer flags it or production fails.

## The two-site check

Whenever handling a new case, mode, or input trigger, ask two separate questions:

1. **Admission:** Does the case now reach the code?
2. **Branching:** Does the code branch and execute correctly once it arrives?

To find the branching site, do not search for the new condition.
Search instead for the variables and flags that the code tests *instead of* the new condition ---
specifically properties that become empty, unset, or defaulted when the new case is active.

## Testing requirements

Text-matching tests cannot detect an admitting-vs-branching divergence.
A test asserting that `- if: $CI_COMMIT_TAG` appears in a configuration file
proves only that the admitting site was edited.

To verify the branching site:

- **Execute against real fixtures:**
  Extract or invoke the actual execution logic against simulated environments
  for every admitted case (e.g. branch pipelines, tag pipelines, default branch, merge requests).
- **Verify mutation failure:**
  Verify that the test suite fails when the branching site is in the half-fixed state.
  If the test passes when the branching site is untouched, the test is not verifying behaviour.

## Related rules

- [`fail-fast.md`](fail-fast.md):
  A guard keyed on an empty variable should fail loudly rather than silently taking an invalid fallback.
- [`algorithmatize-checks.md`](../workflow/algorithmatize-checks.md):
  Extract execution scripts into testable units rather than embedding untestable multi-line shell blocks in CI templates.
- Pattern 35 in [`mistake-patterns.md`](../../memories/mistake-patterns.md):
  The recurring failure record for admitting-vs-branching half-fixes.

## Do / Don't

- **Do:** audit every downstream execution branch whenever adding or modifying an admission rule.
- **Do:** search for variables that become empty or default in the new case to locate downstream branching sites.
- **Do:** test the actual execution script against concrete fixtures representing each admitted state.
- **Don't:** assume a fix is complete because the diff adds the admitting rule named in the issue.
- **Don't:** rely on text-matching or YAML-presence tests to verify multi-site behavioural fixes.
