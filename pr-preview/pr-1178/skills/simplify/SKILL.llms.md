# simplify

After any change that narrows the invocation context (e.g., a job now only runs under branch pipelines, a function is only called from one site, a config option is removed), sweep for dead code that the change made unreachable.

## When this fires

- Automatically after any refactor that changes how code is invoked
- When asked to “simplify”, “clean up”, “prune dead code”
- During review when spotting unreachable paths
- After removing a feature flag or configuration option

## What to look for

1.  **Dead branches** — `if` conditions that can never be true given the new invocation context. Example: checking for `merge_request_event` when the job only runs on branch pipelines.

2.  **Unnecessary fallbacks** — `${VAR:-fallback}` where `VAR` is always set in the current context. Simplify to just `$VAR`.

3.  **Redundant guards** — checks that duplicate a constraint already enforced by the caller (e.g., a rule in the CI template already ensures an MR exists, so the script’s “no MR found” check is belt-and-suspenders — keep it for defense-in-depth, but remove the *comment* claiming it’s the primary gate).

4.  **Vestigial comments** — comments describing behavior that no longer applies. Stale comments are worse than no comments.

5.  **Collapsed conditionals** — an `if/else` where one branch is now unreachable can be collapsed to just the reachable branch.

6.  **Unused variables** — assignments whose values are never read downstream.

## Decision criteria

| Situation | Action |
|----|----|
| Code is unreachable AND no consumer could reach it | Remove |
| Code is unreachable under shipped config but a consumer *could* override | Keep with a comment explaining why |
| Fallback value is never used but adds clarity | Keep (readability \> minimalism) |
| Comment describes removed behavior | Remove or rewrite |
| Defense-in-depth guard (redundant but safe) | Keep the guard, update the comment |

## Process

1.  Identify the narrowed context (what changed about how this code is called)
2.  Trace each conditional/fallback to determine if it’s still reachable
3.  For each dead path: remove it or document why it’s retained
4.  Run syntax checks / tests after pruning
5.  Note the simplification in the commit message (e.g., “remove unreachable merge_request_event path — job now only runs on branch pipelines”)

## Principle

> The best code is code that doesn’t exist. Every line is a liability — it must be read, understood, maintained, and tested. Remove what you can; document what you keep.

## Relationship to other skills

- **`shared/workflow/challenge-unnecessary-complexity.md`** — the standing review-time counterpart. This skill only prunes *dead* code made unreachable by a narrowed invocation context, triggered after a specific refactor; the fragment is the broader “flag complexity in otherwise-correct, reachable content” rule folded into every review pass (prose and math too, not just code). Run this skill when code just became unreachable; the fragment’s check applies continuously, to code that is fully reachable but more complex than it needs to be.
- **`tidy`** — the broader on-demand code audit (5 axes, one of which is “Simplify”); this skill is narrower and specifically about dead-code removal after a context change.

Back to top
