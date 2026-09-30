# Only work PRs scoped to the user or Actions app

Before pushing to, editing, commenting on, reviewing, resolving threads on,
dispatching a paid review of, or merging any PR, resolve the invoking user
and read the PR's author and assignees.

## Scope test

Proceed only when:
1. The author or one of the assignees is that user (or an alias listed in `memories/reviewing-prs.md`).
2. The user explicitly asked for work on that PR by name (or through an explicit `chores` call on Dependabot/Renovate).
3. The author is the GitHub Actions app (`github-actions`).

A mention such as "do not touch" followed by a PR number is not a request, a
claim comment confers no scope, and a sweep skill's "every open PR" means
every PR that passes this test.

## Exclusion veto

An explicit exclusion ("do not touch" followed by a PR number) is a veto: it
removes that PR before any positive arm is evaluated, the user's own PRs and
the Actions app's included, and every sweep carries the exclusion list into
each recheck and each delegated scan.

## Review-only runs and structured review data

A review-only run that CI or a skill invocation dispatched naming the target
PR (an `@claude review`, a `claude-code-review.yml` run) is an explicit
request, whoever authored the PR; it reviews and stops there.
Every review you post carries both representations of its verdict, whoever
asked for it and whether or not anything dispatched it: the human-readable
Markdown report, and the machine-readable `review-data` JSON payload, per
[`adversarial-self-review.md`](adversarial-self-review.md)'s "Structured review data" section.

## Fail closed

An out-of-scope PR is reported to the user and left untouched.
When no identity operation is available, fail closed the way `ardia` does:
leave the author and assignee arms unevaluated, act only on PRs the user
explicitly asked for or the Actions app authored, and say so in the report.
See [`memories/reviewing-prs.md`](../../memories/reviewing-prs.md) for full provenance and `skills/ardia/SKILL.md` step 1 for reference implementation.

- **Do:** verify author, assignees, or explicit user requests before interacting with any PR.
- **Do:** treat "do not touch" as an absolute exclusion veto overriding all other positive matches.
- **Don't:** interact with out-of-scope PRs or infer scope from claim comments.
