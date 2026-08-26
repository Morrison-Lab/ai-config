# Repository transfers (GitHub)

What moving a repository between owners does, and does not, carry with it.
Split out of [`github.md`](github.md) (ai-config#694 pattern) at the
1200-line gate.

## A repository transfer does NOT carry Actions secrets, so every secret-dependent workflow silently stops working

The sections around this one are about **links** breaking on a transfer --- a
redirect that covers `pull` and not `issues`, a `uses:` ref that stops
resolving, an `origin` still naming the old owner.
Each of those announces itself: a 404, a red check, a rejected push.

Secrets break differently, and worse.
They do not move with the repository, so a workflow that authenticated fine
last week now runs with an empty credential --- and a workflow whose secret is
declared `required: false` (the usual shape, so fork PRs skip cleanly rather
than hard-failing at the call gate) does not fail at all.
It skips.

So the failure presents as a review bot that is configured, referenced in
`.github/workflows/`, and simply never says anything.
Nobody reads a missing comment as a symptom, which is why this can sit for
months: the repo looks reviewed-by-default and is not.

One call settles it, and it is worth running on **any** repo whose ownership
has changed, not only when something looks wrong:

```bash
gh api repos/<owner>/<repo>/actions/secrets --jq '{n: .total_count, names: [.secrets[].name]}'
```

`{"n": 0, "names": []}` on a repo whose workflows reference secrets is the
whole diagnosis.

Two follow-ons worth knowing before you go looking for a cause.

**Restoring the secret does not prove the workflow works.**
Adding it back is necessary and not sufficient, and treating the two as the
same thing is how a second, unrelated fault stays hidden behind the first ---
so re-run the workflow and read the run's conclusion rather than the secret
list.

**A missing secret is not a `startup_failure`.**
Because the callee declares it `required: false`, an absent secret cannot fail
the call gate, so a `startup_failure` on a secret-passing workflow is always
something else and the secret is a red herring.
Establish that empirically where you can: adding the secret and re-dispatching
is a genuine negative control, since it moves exactly one variable.

- **Do:** query `actions/secrets` as a routine step whenever a repo's owner has
  changed, before diagnosing anything downstream.
- **Do:** re-run a secret-dependent workflow after restoring a secret, and read
  its conclusion.
- **Don't:** read a quiet review bot as "no findings" --- on a transferred repo
  it is more likely to be "no credential".
- **Don't:** attribute a `startup_failure` to a missing secret without checking
  whether the callee declares it `required: false`.

(`ucdavis/mic.sim`, 2026-08-06, transferred from `ajmichaelucd/mic.sim`:
`actions/secrets` reported `total_count: 0`, and `Claude Code Review` had
concluded `skipped` on all ten of its prior runs, having never once posted a
review.
Once `CLAUDE_CODE_OAUTH_TOKEN` was restored the workflow still ended in
`startup_failure`, which is what proved the secret was never that failure's
cause; filed as ucdavis/mic.sim#50.
The same transfer also left five stale `ajmichaelucd` URLs across `DESCRIPTION`,
`_pkgdown.yml`, and `README.md`, one of which disagreed with the live Pages URL
reported by `gh api repos/<o>/<r>/pages` --- ucdavis/mic.sim#51.)

## A repository transfer redirects `pull` paths but NOT `issues` paths

When a repo moves between owners (`d-morrison/gha` -> `Morrison-Lab/gha`),
GitHub's redirect does not cover every path shape, and the split is not
documented anywhere obvious.
Measured directly after one such move:

| Old-owner URL | Result |
| --- | --- |
| `.../gha` (repo root) | 301 -> new owner |
| `.../gha/tree/main/examples` | 301 -> new owner |
| `.../gha/blob/main/README.md` | 301 -> new owner |
| `.../gha/pull/34` | 301 -> new owner |
| `.../gha/issues/325` | **404** |

The issues themselves are fine --- the same numbers return 200 under the new
owner.
Only the redirect is missing, so every prose link of the form
`https://github.com/<old-owner>/<repo>/issues/N` becomes a hard 404 the
moment the transfer completes.

Two consequences worth knowing before diagnosing this:

- **A link checker goes red repo-wide, on `main`, with no diff to blame.**
  lychee's usual config accepts 301, so the redirecting links pass and only
  the issue links fail.
  Every open PR inherits the failure, which invites blaming whichever PR you
  happen to be looking at.
  Confirm by checking whether the failing files appear in the PR's own
  changed-file list at all: a file the diff never touched cannot be the
  cause.
  An identical count of old-owner links on `main` and on the branch
  corroborates it.
- **Do not infer that the issues were lost.**
  A 404 on the old owner says nothing about the new one.
  Request the new-owner URL before concluding anything; the fix is usually a
  plain rewrite rather than recreating or remapping anything.
  (This exact inference was made, published in a review, and had to be
  retracted --- gha#351, 2026-07-28.)

The `uses:`-resolution half of the same transfer is covered in
`github-actions.md` ("A repo/org rename breaks Actions `uses:` refs"),
including the trap that a tag can resolve while its own contents still name
the old owner.
One diagnostic belongs here because it generalizes beyond Actions: a run
started shortly before a cutover can still succeed, so two attempts of the
*same run* can disagree --- the cheapest available proof that a cause is
environmental rather than in the diff.

## `gh pr create` fails on a transferred repo whose `origin` still names the old owner

The section above covers which paths a transfer redirects.
This is a case where the redirect holds for `git` and not for `gh`: a checkout
whose `origin` URL still carries the old owner pushes fine and then cannot open
a PR.

`git push`'s *exit status* is therefore useless as a control, because it
succeeds.
Git follows GitHub's transfer redirect, so the branch really does land on the
new repo.
The push *output* is not useless, though: pushing to the stale remote prints a
`remote: This repository moved. Please use the new location: <new-url>` notice
that names the canonical owner, so it is the earliest tell that `origin` is
stale --- read it rather than the exit status.
Miss that notice and the failure arrives only at PR creation:

```
GraphQL: Head sha can't be blank, Base sha can't be blank, Head repository
can't be blank, No commits between Morrison-Lab:main and
the repository owner:docs/customization-surface, Head ref must be a branch, not all refs
are readable (createPullRequest)
```

Read that error's owner names, not its most legible clause.
"No commits between `<base>` and `<head>`" describes a base-versus-head
relationship, which sends you to check whether the push landed any commits ---
the one thing that is definitely fine here.
The actual finding is that the two sides carry **different owners**:
`Morrison-Lab` for the base, which followed the transfer redirect, and
`the repository owner` for the head, which tracked the stale `origin` URL.
Five of that message's six clauses are downstream noise from the head repo not
resolving.

Pass the repo explicitly, with an explicit head and base:

```bash
gh pr create -R Morrison-Lab/wai --head <branch> --base main --title ... --body ...
```

Repointing `origin` at the new owner is the durable fix and was not tested
here; `-R` unblocks the PR without mutating a checkout other sessions may be
using.

- **Do:** compare the two owner names inside a `No commits between` error
  before concluding anything about commits.
- **Do:** pass `-R <new-owner>/<repo>` with explicit `--head` and `--base` when
  the remote still names the old owner.
- **Do:** read `git push`'s output, not only its exit status: a `remote: This
  repository moved` notice names the canonical owner and catches the stale
  remote a step before `gh pr create` does.
- **Don't:** read a successful `git push` as evidence that `gh` resolves the
  same repo --- git follows the transfer redirect here and `gh pr create` does
  not.
- **Don't:** re-push, re-commit, or rebuild the branch in response to `No
  commits between`; the commits are there, under a repository name `gh` is not
  looking at.

(`Morrison-Lab/wai`, 2026-08-04: `git remote get-url origin` returned
`https://github.com/Morrison-Lab/wai`, while `gh api repos/Morrison-Lab/wai`
reported `Morrison-Lab/wai` and `gh api repos/Morrison-Lab/wai` returned that
same `full_name`, confirming the redirect.
The push succeeded --- with a `remote: This repository moved` notice naming
`https://github.com/Morrison-Lab/wai.git` as the new location --- `gh pr create`
failed with the message above, and the `-R` form worked.
The same repo recurred at PR #41 on 2026-08-05, with the identical push
notice.)

## An ISSUE transfers only within one owner, so a cross-owner move is a hand copy

Everything above is about transferring a **repository**.
An issue is the other thing people say "transfer" about, and it obeys a
constraint the repository case does not: GitHub transfers an issue only
between repositories owned by the **same** user or organization.
So `d-morrison/<repo>` to `Morrison-Lab/<repo>` is not a transfer at all, and
the two interfaces refuse it differently.
`gh issue transfer` takes the destination as a positional argument and errors
on it.
The web UI has a repository picker, and the destination simply does not appear
in it --- which reads as the repo being missing rather than as the operation
being unavailable, and is the likelier of the two to be misdiagnosed as a
permissions problem.

That matters because the two owners here are one person's account and that
person's org, so the move feels internal.
It is not, and no permission level changes it.

The hand copy is the whole remedy, and it has three parts, none optional:

1. **File fresh in the destination**, carrying the original text rather than a
   summary --- a pointer plus a paraphrase loses exactly the specifics a
   transfer would have preserved.
2. **Re-verify the original's claims against the destination repo** while
   copying.
   An issue filed from another repo's session cites line numbers and file
   contents it could not read.
   Those drift, and the copy is the moment to check them rather than to
   propagate them.
3. **Link both ways and close the original as transferred**, so the source
   repo's tracker does not keep a live duplicate.

- **Do:** treat a cross-owner "transfer" request as file-fresh-and-close, and
  say in the new issue that it was hand-transferred and from where.
- **Do:** re-derive any file/line claim the original made, since the original
  session could not read the destination repo.
- **Don't:** read a missing destination in the transfer picker as a
  permissions problem --- same-owner is a hard constraint of the feature.
- **Don't:** leave the source issue open once the copy exists.

(`d-morrison/rme#1083` to `Morrison-Lab/ai-config#1709`, 2026-08-19.
The original was filed in `rme` precisely because that session's write access
was scoped there, with the body opening "Filed here for transfer to
`Morrison-Lab/ai-config`" --- a transfer that was never available.)
