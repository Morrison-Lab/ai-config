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

## Only work PRs I opened, am assigned to, or asked for by name, or the Actions app authored

Work only on pull requests opened by me (`d-morrison` or `dem-extra1`),
assigned to me,
explicitly asked for by name in the request,
or authored by the GitHub Actions app
(app slug `github-actions`,
which the APIs surface as `github-actions[bot]`, bare `github-actions`, or `app/github-actions`
--- a submodule bump, an automated sync PR).
A PR opened by another lab member, or by any other bot,
is not mine to drive unless it is assigned to me or I explicitly asked for it
--- however clean, stale, or easy it looks,
and however a sweep skill words its scope.

The user stated the **Do** side, in two steps: first the author/assignee test, then (same day) that workflow-opened PRs such as a submodule bump are fine.
The **Don't** side is inferred from the near-miss that prompted it, and is what makes the rule checkable.
The named-in-request arm came from neither directive: it is carried over from `ardia`'s former "unless told to" bullet, which this rule replaced.
The narrowing of "workflow-opened" to the `github-actions[bot]` login is also inferred: the example given was a `bump-submodule.yml` PR, and Dependabot and Copilot PRs post under their own logins and were not named.
That login match covers a workflow that opens its PR with `GITHUB_TOKEN`;
`gha`'s reusable sync workflows (`bump-submodule.yml`, `bump-dev-version.yml`, `sync-shared-fragments.yml`, `sync-upstream.yml`, read at `Morrison-Lab/gha` `82f3c36` on 2026-09-01) hand `open-sync-pr` `${{ secrets.WORKFLOW_TOKEN || github.token }}`, so when the repo sets that secret the PR posts under that token's identity: the PAT holder's own login, or an App's `<slug>[bot]`.
The rule therefore narrows the directive's "workflow-opened" on purpose, because provenance is not observable from the API: the arm is an author test on the `github-actions` app, not a provenance test, and such a PR is in scope through the author arm when the PAT is mine, and needs an assignment or naming under an App token or another member's PAT, however it was opened.

- **Do:** treat `d-morrison` and `dem-extra1` as one person --- this corpus's owner --- when either is the invoking user (`preferences.md`'s `## Git author mapping` entry records the same two-account split, with the owner written as "the repository owner").
  They are written as literals here on purpose: `preferences.md`'s "Never hardcode usernames" rule exempts values that must resolve to a real account, and an `author.login` match is exactly that.
  A skill must still resolve the invoking user dynamically and only *add* these aliases, so another lab member running the vendored corpus filters on their own identity, not on these two.
- **Do:** before touching any PR, resolve who you are running as, read the PR's author and assignees (`author.login` / `assignees[].login` from `gh --json`, `user.login` / `assignees[].login` from REST, `user.login` plus bare login strings in `assignees` from the MCP tools --- `mcp__github__list_pull_requests` and `pull_request_read` returned `"assignees": ["d-morrison"]` on 2026-09-01, and the list tool omits the key on an unassigned PR --- and `author.username` / `assignees[].username` from GitLab), and proceed only when the author is you (or one of those aliases) or the GitHub Actions app (`github-actions`, in whichever form the source returns it), you or one of those aliases is among the assignees, or the user explicitly asked for work on that PR.
  A mention is not a request: "do not touch [#284](https://github.com/UCD-SERG/serodynamics/pull/284)" names [#284](https://github.com/UCD-SERG/serodynamics/pull/284) and excludes it, and a link given as context authorizes nothing.
  An explicit exclusion is the opposite of a request: it is a veto checked before every positive arm, so a PR I authored, am assigned to, or the Actions app opened is still left untouched when the request says not to touch it, and the exclusion list travels with the sweep into every recheck and every delegated scan (`skills/chores/SKILL.md`'s `PR_SCOPE_EXCLUDED` is the executable form).
  Match the app slug `github-actions` in whichever form the source returns it (forms measured 2026-09-01 against `cli/cli` trunk and the REST API;
  re-check if a tool's output format changes): the REST API and the MCP tools suffix it (`github-actions[bot]`), GraphQL and `scripts/pr-sweep.py` return it bare (`github-actions`), and `gh pr list --json author` prefixes it (`app/github-actions`, with `is_bot: true`).
- **Do:** on a sweep (`ardia`, `gia`, `ardiaei`, `gmd`), filter the PR list by that test first, and say in the report which PRs were excluded and why.
- **Do (inferred):** when no identity operation is available (no `gh`, no `mcp__github__get_me`, no `glab`), fail closed:
  leave the author and assignee arms unevaluated, keep only the PRs the user explicitly asked for or the Actions app authored, and say so in the report.
  `skills/ardia/SKILL.md` step 1 and `AGENTS.md` state the same fallback.
- **Don't:** push commits to, rewrite the title or body of, comment on, review, dispatch a paid review on, resolve threads on, or merge a PR that fails the test.
  A review-only run that CI or a skill invocation dispatched naming the PR (an `@claude review`, a `claude-code-review.yml` run) satisfies the explicit-request arm for that review whoever the author is, and stops at the review per "Review-only is not working the PR" above.
- **Don't:** read a skill's "drive every open PR" as a scope grant that overrides this --- "every" means every PR that is mine.
- **Don't:** treat a PR from a bot other than the GitHub Actions app (a Dependabot PR, a Copilot-agent PR, a PR another App's token opened) as mine by default;
  such a PR needs an assignment or an explicit request like any other.
  An explicit `chores` invocation names the Dependabot/Renovate population, which is the named-in-request arm.
- **Don't:** stand down from a PR the `github-actions` app authored on the ground that a bot opened it --- that is the over-correction the second directive reversed.

The near-miss looks like diligence from the inside, which is why the rule needs the explicit Don'ts.
On `UCD-SERG/serodynamics`, 2026-09-01, a `gia` sweep pushed commits to [#284](https://github.com/UCD-SERG/serodynamics/pull/284), [#292](https://github.com/UCD-SERG/serodynamics/pull/292), [#298](https://github.com/UCD-SERG/serodynamics/pull/298) and [#311](https://github.com/UCD-SERG/serodynamics/pull/311) and dispatched a review on [#310](https://github.com/UCD-SERG/serodynamics/pull/310) --- four authored by other lab members, one ([#292](https://github.com/UCD-SERG/serodynamics/pull/292)) by `github-actions[bot]`, none assigned to me --- and drove all of them to a clean verdict before the correction arrived.
The session then stood down from all five, and the user reversed that for the workflow-opened one, [#292](https://github.com/UCD-SERG/serodynamics/pull/292), which was fine to drive.
So the population error was the four human-authored PRs, and the over-correction was the fifth.
Every individual action was a correct ARDI step.
The error was the population, decided by reading "every open PR" in the skill rather than by asking whose PRs they were.
Each of those threads got one disclosure comment naming the commits (or, on [#310](https://github.com/UCD-SERG/serodynamics/pull/310), the dispatched review), so the authors can keep or revert them.

The issue carve-out is inferred too: nothing in either directive mentioned issues.
An issue on a repo I own is different from a PR on it:
filing, triaging, and commenting on issues is fine,
and an issue someone else's open PR already fixes is left to that PR (not grabbed, and that PR not driven either).

## Inspect every restatement of a rule in one pass

When a reviewer's finding adds an arm, a veto, or a recheck to one
restatement of a rule, the same gap may be open at any other restatement,
and the reviewer finds those one round at a time.
[Morrison-Lab/ai-config#2913](https://github.com/Morrison-Lab/ai-config/pull/2913) (2026-09-01) spent Copilot rounds thirty-two
through thirty-five landing one exclusion veto and one pre-write recheck
site by site (files per commit from `git show --stat`): `chores` plus the
`scripts/validate-skills.py` allowlist entry for its new input
(`28c20e5`), `chores` again for the recheck's step range (`988b545`),
then `AGENTS.md`, `ardia`, `post-merge`, and this file (`3b32086`), then
`memories/github.md` and `chores` a third time for the recheck's inputs
(`ab89045`).
A corpus grep for the rule's vocabulary after round thirty-two, with each
hit read against the widened rule, reaches most of those sites.
Measured 2026-09-01 against the `28c20e5` tree:

```bash
git grep -n -i -e "not a request" -e "reapply the" -e "before each write" \
  -e "before the mutations" -e "explicitly authorized" 28c20e5 -- '*.md'
```

returns `AGENTS.md:571`, `memories/reviewing-prs.md:94`,
`skills/ardia/SKILL.md:45` and `:47`, `skills/chores/SKILL.md:46` and
`:132-133`, `memories/github.md:73`, and `skills/post-merge/SKILL.md:285`,
plus three unrelated hits (`hooks.md`, `report-mistakes-proactively.md`,
`math-derivation-steps.md`) that reading against the rule discards.
That is every file rounds thirty-three through thirty-five changed.
The `post-merge` hit at line 285 is the scanner's own filter, where the
phrase sits on one line.
The scanner brief a few paragraphs above it restates the same rule with
the phrase wrapped across a line break, `explicitly` ending line 231 and
`authorized` starting line 232
(`git show 28c20e5:skills/post-merge/SKILL.md | sed -n 231,232p`), so the
grep reaches that file through the filter and not through the brief.
A wrapped phrase needs a second pattern or a read of the surrounding
section, which is one more reason the sweep inspects each hit's file
rather than only the matching line.
Round thirty-six was a different gap (a live-claim check in
`check-history`, distinct from scope), so it is not an instance of this
lesson and a restatement sweep would not have caught it.

A sweep inspects; it does not rewrite.
Some restatements are already correct, and some are deliberately narrower
(`ardia`'s recheck reads author and assignees only, because its predicate
has no title or label arm), so each hit is read against the new scope and
changed only when it carries the gap, per
[`address-every-comment`](../shared/workflow/address-every-comment.md)'s
broadening-fix section.

A "reapply the test before each write" sentence has two populations to
enumerate, and recalling either one misses members: the write actions per
step (read every mutating command or API call off the procedure itself,
`gh pr close`, `comment`, `merge`, `edit`, `ready`, `review`, a thread
resolution, a push, an API mutation, rather than a fixed verb list) and
the predicate's mutable inputs (read them off the filter itself: `chores`
reads title and labels, not only author and assignees).

- **Do:** find every restatement of the rule the finding touched by
  three routes, since a phrase grep matches strings and a restatement can
  use other words
  ([`grep-is-not-coverage`](../shared/workflow/grep-is-not-coverage.md)):
  the phrase grep, a grep for the mechanism's stable terms (the input
  names, the arm names, the write verbs), and a topic-and-filename pass
  over every skill, fragment, and memory that lists PRs or mutates PR
  state (push, comment, review, resolve a thread, edit title, body, or
  metadata, mark ready, close, merge).
  Read each candidate against the widened rule, fix the ones that carry
  the gap, and say in the ARD reply which candidates were inspected and
  which changed, never that the grep enumerated the concept.
- **Do:** derive both populations for a before-each-write sentence from
  the file, and name them in it.
- **Don't:** fix the one site the finding quoted and wait for the next
  round to name the next one.
- **Don't:** rewrite a restatement that is correct or deliberately
  narrower just because the grep returned it.

## Search the issue thread before rebutting "no source exists"

A reviewer asked for a permalink to the post a chapter summarized.
The rebuttal said none existed, because the issue *body* carried only a
paraphrase.
The permalink sat in a comment on that same issue, and the rebuttal was a
false state claim (wai#184 / wai#98, 2026-09-01).

An issue is its body plus its comments, and the body is the part that
gets read.
Before asserting that a source, a link, or a decision is absent, query the
comments too:
`gh api repos/<owner>/<repo>/issues/<N>/comments --paginate`, or
`issue_read` with `method: get_comments` in a remote session.
Then cite the found comment by URL.

- **Do:** run the comments query and quote what it returned before writing
  "no permalink exists".
- **Don't:** rebut an absence finding from the issue body alone.
