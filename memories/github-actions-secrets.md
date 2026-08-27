# GitHub Actions secret scoping, and proving a credential works

Scoping and verification of Actions secrets,
as distinct from workflow authoring (`github-actions.md`)
and outage diagnosis (`github-actions-outages.md`).

Measured 2026-08-26 while migrating `CLAUDE_CODE_OAUTH_TOKEN`
from eight per-repo copies to a single org secret on `Morrison-Lab`
([ai-config#2360](https://github.com/Morrison-Lab/ai-config/issues/2360)).

## A repo-level secret shadows an org-level one, so a migration is inert until the copies are deleted

GitHub's secrets reference states it directly:

> If a secret with the same name exists at multiple levels, the secret at the
> lowest level takes precedence.
> For example, if an organization-level secret has the same name as a
> repository-level secret, then the repository-level secret takes precedence.
> Similarly, if an organization, repository, and environment all have a secret
> with the same name, the environment-level secret takes precedence.

Two consequences follow,
and the second is the one that costs a wasted verification round.

Installing the org secret **changes nothing** while the repo copies exist.
A later rotation of the org secret would silently no-op
on every repo that still has one.
The deletions are what make the org secret live.

And the org secret **cannot be verified** on any repo that still carries a copy,
because a green run there exercised the copy.
Verification needs a repo with no copy.
Where every candidate carries one,
that means deleting one first
and accepting that the deleted value is unrecoverable.

- **Do:** delete the repo copies as part of the migration,
  not as tidy-up afterwards.
- **Do:** pick the quietest repo as the canary when no copy-free repo exists,
  and check its open-PR count and last push before choosing.
- **Don't:** report an org secret as in effect
  while any repo-level copy of that name survives.
- **Don't:** verify on a repo that still has its own copy ---
  the result is about the copy.

## The org form defaults to `--visibility private`

From `gh help secret set`:

```
-v, --visibility string   Set visibility for an organization secret:
                          {all|private|selected} (default "private")
```

An org secret created without an explicit visibility lands at `private`,
and reaches only private repos.
It fails quietly toward the narrower scope,
and nothing about the resulting secret looks wrong in a listing.

`Morrison-Lab`'s `GEMINI_API_KEY` is the worked example.
At the time of the migration it sat at `private`
while its four siblings sat at `all`,
and the only private repo in the org did not use it,
so the secret reached nothing
([ai-config#2361](https://github.com/Morrison-Lab/ai-config/issues/2361)).

The plan gate is separate,
and applies to the **reader** rather than the writer:
"Organization-level secrets and variables are not accessible by private
repositories for GitHub Free."
`Morrison-Lab` is on `team`,
so private repos are reachable there.

- **Do:** pass visibility explicitly on every org-secret write.
- **Don't:** read a successfully created org secret as correctly scoped.

## The web UI's list page is the receipt, not the form

A secret written through the org settings UI can silently fail to land.
The first attempt on 2026-08-26 did not reach GitHub at all.
The org list still showed five rows afterwards,
confirmed independently by the REST API
and by a screenshot of the settings page.

Nothing reported an error.
The failure is only visible as an absence.

- **Do:** confirm the new row appears in the list before navigating away.
- **Don't:** treat "I filled in the form" as the write having happened.

## Proving a credential works: the execution result, not the conclusion and not the artifact

The sharpest finding,
and the one that generalizes past secrets.

The canary run (a dispatched review on `Morrison-Lab/qmt`, the migration's
canary repo) went green and posted **no** review comment.
Two natural checks were each available,
and each would have been wrong:

- The **job conclusion** said `success`.
  But a run can pass without ever exercising the credential ---
  an early bail, a skipped step,
  or a guard step that concludes the run is fine.
  So `success` is compatible with the token never being used.
- The **expected artifact** was absent, since no comment appeared.
  But a reviewer legitimately produces nothing when there is nothing to say,
  and this target was an already-merged PR.
  So the absence is compatible with the token working perfectly.

The two surfaces disagreed, and neither could settle it.
What settled it was the action's own execution result in the job log:

```json
{ "type": "result", "subtype": "success", "is_error": false,
  "duration_ms": 30774, "num_turns": 2,
  "total_cost_usd": 0.1099753, "permission_denials_count": 0 }
```

Real turns and real spend.
A credential that failed to authenticate cannot produce a non-zero
`total_cost_usd`,
so that field is the discriminator and the conclusion is not.
The inference needs one precondition, restated here because this is where it
gets applied: non-zero cost proves *some* credential authenticated, so it
identifies **the** credential under test only when the run had exactly one
available --- no surviving repo-level copy, and no sibling credential (an
`ANTHROPIC_API_KEY`, say) the workflow could fall back to.
The canary satisfied it: `Morrison-Lab/qmt` had zero repository secrets,
verified.

This is the shape
[`verify-the-right-artifact`](../shared/workflow/verify-the-right-artifact.md)
names as "one half of a mechanism for the whole".
The job ran,
and whether the token was used is a different question
from whether the job succeeded.

- **Do:** read `is_error`, `num_turns`, and `total_cost_usd`
  out of the execution result
  when the claim under test is "this credential works".
- **Do:** ask what would have to be true for the credential to be **broken**,
  and whether the surface in hand could show it.
- **Don't:** read a green job conclusion as evidence a secret authenticated.
- **Don't:** read a missing artifact as evidence it did not ---
  a reviewer producing nothing is a normal outcome.

## Changing a secret's scope breaks tooling keyed on the old topology

`scripts/rotate-claude-token.py` discovers targets
by asking each repo whether it carries the secret,
keeping only those that do.
After the migration no repo does,
so the sweep returns zero targets and prints `Nothing to rotate` ---
which is also its correct output when there is genuinely nothing to do.

Pass path equals failure path,
per [`fail-fast`](../shared/principles/fail-fast.md),
in the dangerous direction:
the next expiry would be invisible to the one tool built to fix it.

Tracked as [ai-config#2371](https://github.com/Morrison-Lab/ai-config/issues/2371).

- **Do:** sweep for tooling keyed on a topology you are about to change,
  in the same pass that changes it.
- **Don't:** leave a discovery step
  whose empty result is indistinguishable from its healthy one.

## `require-gh-repo-flag.py` blocks the bare org-secret write

The local guard discharges only on `-R`/`--repo`,
but an org secret is addressed with `-o/--org`,
so the natural spelling of an org-secret write is refused,
and the block message steers toward `-R`,
which is the wrong flag for the org form.

The workaround is stated here because the first draft of this file got it
wrong, and an adversarial review round refuted the error by executing both
halves (PR #2373): `gh` ignores an inherited `-R` when `-o` is present,
so adding a redundant `-R <owner>/<repo>` **discharges the guard and still
writes the org secret** --- verified with `--no-store`,
which encrypted against the org public key
even when the `-R` value named a nonexistent repository.
The false belief worth recording alongside the fact:
"the hint would cause a wrong-target write" reads as obviously true from the
guard's message and is refuted by one probe of the tool itself,
which is [`self-review-fallback`](../shared/workflow/self-review-fallback.md)'s
check-the-tool's-own-documentation rule in miniature.

Two real defects remain in the guard.
The discharge-on-`-R` behaviour above means the guard is satisfied by an
**inert** flag, which is a proxy for "target named" rather than the thing
itself; widening the discharge to `-o`/`--org` and `-u`/`--user` is the fix.
And it matches command text inside a heredoc,
so writing *about* the pattern trips it too
(measured while filing the tracking issue).

Tracked as [ai-config#2367](https://github.com/Morrison-Lab/ai-config/issues/2367).
The pipe split in the guard is real but not the blocker it first appears:
a piped stdin write carrying an explicit target passes,
and the org form was blocked by the missing `-R` with or without a pipe.

## Keeping a token out of an agent's context

Actions secrets are write-only over the API:
no endpoint returns the value.
The org-scoped `secrets/<NAME>` returns `name`, `visibility`,
`created_at`, and `updated_at`;
the repo-scoped one returns no `visibility` at all.
So an agent can verify a secret's configuration
and prove it authenticates,
without ever being able to read it.

The transfer is the only exposed moment,
and the web UI removes it entirely.
Where a CLI is wanted,
the value belongs on stdin rather than in `argv`.

- **Do:** run a token-printing command in a separate terminal,
  never through a session-visible shell.
- **Don't:** paste a token into a chat,
  or into a command line an agent reads.
