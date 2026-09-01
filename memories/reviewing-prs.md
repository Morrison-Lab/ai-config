# Reviewing someone else's PR

Satellite of [`preferences.md`](preferences.md).
`preferences.md` hit the 1200-line gate when this file was split out
(measured ~1200 lines at the split; 1130 on `main` as of 2026-08-26),
so new review-scope lessons still land here rather than as appends there.

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
## Only work PRs I opened or am assigned to

Work only on pull requests opened by me (`d-morrison` or `dem-extra1`) or
assigned to me.
A PR opened by another lab member, or by a bot, is not mine to drive unless it
is assigned to me --- however clean, stale, or easy it looks, and however a
sweep skill words its scope.

The user stated the **Do** side; the **Don't** side is inferred from the
near-miss that prompted it, and is what makes the rule checkable.

- **Do:** before touching any PR, resolve who you are running as, read the
  PR's `author.login` and `assignees`, and proceed only when the author is
  you (or an alias below), you are among the assignees, or the user named
  the PR in the request.
- **Do:** treat `d-morrison` and `dem-extra1` as one person --- this
  corpus's owner --- when either is the invoking user.
  They are written as literals here on purpose: `preferences.md`'s
  "Never hardcode usernames" rule exempts values that must resolve to a
  real account, and an `author.login` match is exactly that.
  A skill must still resolve the invoking user dynamically and only *add*
  these aliases, so another lab member running the vendored corpus filters
  on their own identity, not on these two.
- **Do:** on a sweep (`ardia`, `gia`, `ardiaei`, `gmd`), filter the PR list by
  that test first, and say in the report which PRs were excluded and why.
- **Don't:** push commits to, rewrite the title or body of, dispatch a paid
  review on, or resolve threads on a PR that fails the test.
- **Don't:** read a skill's "drive every open PR" as a scope grant that
  overrides this --- "every" means every PR that is mine.
- **Don't:** treat a bot-opened PR (a submodule bump, a Dependabot PR) as
  mine by default; it needs the assignment like any other.

The near-miss looks like diligence from the inside, which is why it needs
the explicit Don'ts.
On `UCD-SERG/serodynamics`, 2026-09-01, a `gia` sweep pushed commits
to #284, #292, #298 and #311 and dispatched a review on #310 --- four
authored by other lab members, one by `github-actions[bot]`, none assigned
to me --- and drove all of them to a clean verdict before the correction
arrived.
Every individual action was a correct ARDI step.
The error was the population, decided by reading "every open PR" in the
skill rather than by asking whose PRs they were.
Each of those threads got one disclosure comment naming the commits, so the
authors can keep or revert them.

An issue on a repo I own is different from a PR on it: filing, triaging, and
commenting on issues is fine, and an issue someone else's open PR already
fixes is left to that PR (not grabbed, and that PR not driven either).
