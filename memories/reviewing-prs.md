# Reviewing someone else's PR

Satellite of [`preferences.md`](preferences.md).
`preferences.md` is at the 1200-line gate,
so new review-scope lessons land here rather than as appends there.

Source: [UCD-SERG/shigella#31](https://github.com/UCD-SERG/shigella/pull/31), 2026-08-25.

## Do not withhold findings in notes

When *you* are the reviewer posting on a PR,
post every finding already in hand.
If a remainder surfaces after the first comment,
post it immediately.
Do not leave it in session notes
and wait to be asked whether it landed.

This is not the automated-reviewer prompt rule in
[`preferences.md`](preferences.md)
("Demand a single, exhaustive review pass", gha#412),
which forbids staggering *prompted* feedback across rounds.
A follow-up here is a completeness correction,
not a planned second round.

shigella#31, 2026-08-25:
mechanical and math/content reviews went up.
Leftover nits stayed in notes until the user asked
"did you post all that?" then "yes".

## Leftover-artifact findings

Read what the PR is for before posting leftover-artifact findings.
Do not criticize a PR for delivering the artifact its title and body name.
If the PR is landing a dissertation,
"the chapter files still read as a dissertation" is not a finding.
The same applies to any "this still looks like X" comment when X is the change.

shigella#31: posted leftover dissertation framing as section 5 of a
mechanical review.
The user had it withdrawn because this PR *is* the dissertation.

## Owner scope vs the author's mechanical box

When reviewing a manuscript or dissertation for the owner,
his scope expansions win over the author's requested mechanical box.
Cross-refs, numbers vs CSVs, and citations are the floor, not the ceiling,
once he asks to also check math, modeling logic, or scientific claims.
Factual errors stay in scope even when prose style does not
(a submitted manuscript can still be wrong).
An author's "not up for modeling-logic revision" does not bind the owner.

shigella#31: the author asked for a mechanical pass.
The owner then asked to check math, Stan/R runners, and content.

## Review-only is not working the PR

Posting a review as comments is not working the PR.
A request to review and leave findings, with no request to edit, is
review-only:
do not start ARDI, do not push fixes, and do not merge.
Leave the findings and stop unless asked to iterate.
A later request to iterate is a driving request.
"Watch and ARDI every PR you touch" applies when you are driving the
branch, not when you were asked only to read it.
See also [`shared/workflow/ardi.md`](../shared/workflow/ardi.md).
