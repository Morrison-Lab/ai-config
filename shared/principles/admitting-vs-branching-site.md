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

## A predicate shared by several branches: widening it can steal a case from a stricter sibling

The two-site frame above assumes one admission gate feeding one execution path.
A related but distinct shape recurs in authorization code with several branches in one `if`/`elif` chain, each meant to be authoritative for a different kind of input, where the same downstream predicate (a persona-name lookup, a type matcher) is consulted from more than one arm.
Widening that predicate to admit a new case for the arm you are fixing can make an **earlier** arm match inputs it was never meant to see, silently routing them away from a **later**, stricter arm that was the actual authority for them.
The widened arm is not wrong about the case it was built for;
it now also wins ties it should have lost.

Nothing about this shows up in a diff review of the arm you touched, because that branch continues to behave correctly on its own inputs.
What breaks is a sibling branch elsewhere in the chain, and the failure is silence rather than an error: the sibling's stricter check simply never runs for the stolen input.

(`Morrison-Lab/ai-config#3707` / `#3742`, commits `dd10dca4` and `6ed58075`, 2026-09-17.
`hooks/no-push-without-self-review.py` widened the persona-key set a lookup function reads, to recognize a Codex reviewer dispatch keyed on `agent` or `persona`.
That same lookup is consulted from a branch that ran before the branch carrying the guard's real, stricter provenance check for task-output-tool calls -- a `task_id`-membership test against IDs the guard itself recorded as reviewer dispatches.
Because the persona check now matched more inputs, a task-output call merely *labelled* with a reviewer persona was parsed as a genuine reviewer report: dispatch an unrelated persona in the background, capture its task id, then call the task-output tool with that id plus a `persona` key naming the reviewer and a well-formed clean report -- authorized, with no review having happened.
The hole pre-dated the widening (it reproduced on `origin/main` via a persona key already in the narrower set);
the widening spread it to two more keys.
The fix reorders the chain so the stricter, task-id-gated branch is tested first and is exhaustive for its own input class, so a persona label on that call can never reach the looser branch at all.
Twelve regression cases pin the ordering; reverting it fails all twelve.)

- **Do:** before widening a predicate, list every branch that consults it, not only the one the finding named -- a persona/name/type matcher reused across an `if`/`elif` chain gates more than the arm you are editing.
- **Do:** where two branches can both match the same input, make the stricter, more-authoritative branch's condition run first and exhaustive for its own input class, so a looser sibling can never reach it.
- **Do:** mutation-test a branch ordering the same way any other guard condition is tested -- revert the order and confirm the regression case fails.
- **Don't:** reason about a widened predicate's safety from the arm it was written for;
  ask what else in the same chain reads it.
- **Don't:** assume a hole that appeared alongside a widening was caused by it -- check whether the base branch already reproduces it, since the fix differs (reorder vs. narrow) depending on which is true.

## Related rules

- [`fail-fast.md`](fail-fast.md):
  A guard keyed on an empty variable should fail loudly rather than silently taking an invalid fallback.
- [`algorithmatize-checks.md`](../workflow/algorithmatize-checks.md):
  Extract execution scripts into testable units rather than embedding untestable multi-line shell blocks in CI templates.
- Pattern 35 in [`mistake-patterns.md`](../../memories/mistake-patterns.md):
  The recurring failure record for admitting-vs-branching half-fixes.
- [`fixtures-are-not-evidence.md`](../workflow/fixtures-are-not-evidence.md): Every row testing the widened predicate supplied its old key for free and so could not exercise the new ones.

## Do / Don't

- **Do:** audit every downstream execution branch whenever adding or modifying an admission rule.
- **Do:** search for variables that become empty or default in the new case to locate downstream branching sites.
- **Do:** test the actual execution script against concrete fixtures representing each admitted state.
- **Don't:** assume a fix is complete because the diff adds the admitting rule named in the issue.
- **Don't:** rely on text-matching or YAML-presence tests to verify multi-site behavioural fixes.
