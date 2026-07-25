When an agent claims an issue it's about to work — in `gi`, `gii`, `gip`, or
`st` — open the PR **immediately**, before writing any code, and keep it a
**draft** until the implementation lands. Don't wait until the work is done to
open it.

**Why up front.** The claim comment on the issue is easy to miss, and it isn't
what other sessions check. The authoritative in-flight signal is the issue's
cross-referenced **open PRs** — the check `gi` runs before grabbing an issue.
Until a PR exists, a parallel issues-sweep can grab the same issue and build a
duplicate. An open PR closes that window: it shows in `gh pr list` and the
issue's timeline, and links the issue via `Closes #N`. An open PR is the
clearest "someone is working this" signal there is — stronger than a comment.
This is the strong form of the "open and link the PR promptly" note in
[`claim-pr`](claim-pr.md).

**Mechanics.** Branch, then open the PR against an empty commit:

```bash
git fetch origin main -q
git checkout -b <type>/<slug> origin/main
git commit --allow-empty -m "start: <issue title> (closes #<N>)"
git push -u origin HEAD
gh pr create --draft --title "<title>" --body "Closes #<N>

WIP — opened up front to claim the issue; implementing now."
```

The empty commit gives the branch a diff so the PR can open with no code yet.
In a remote/web session where `gh` is absent, push the empty commit and open
the PR with the GitHub MCP tools instead (`mcp__github__create_pull_request`
with `draft: true`).

**Draft, not ready-for-review — deliberately.** A draft doesn't trigger the
`@claude` review bot, so no review round is spent on an empty or half-finished
diff. Implement on top, pushing commits to the same PR; when the change is
complete and the repo's checks pass, mark the PR **ready for review**
(`gh pr ready <N>`, or `mcp__github__update_pull_request` with `draft: false`).
Marking it ready is what kicks off ARDI.

**Don't mark ready within seconds of the final push — the two review runs race
and the WRONG one can get cancelled.** On repos whose review workflow runs on
`pull_request` (`synchronize`, `ready_for_review`) with `concurrency:
cancel-in-progress`, a push followed immediately by `gh pr ready` fires two
runs a second apart: the ready-event run (recorded against the pre-push head)
and the push's synchronize run (recorded against the new head). The
cancellation can land on the **newer** run, leaving the current head with a
cancelled review job and a red require-review check — while the surviving
older run can still post a genuine, current verdict: a reviewer that fetches
the PR's diff at review time (sparta's does, via `gh pr diff` per its own run
transcript) sees the pushed code even though the run is nominally tied to the
pre-push head. Read the posted review and confirm it actually discusses the
current head's changes before trusting it. If this happens, don't push or
re-mention: `gh run rerun <cancelled-run-id>` re-reviews the same head and
turns the head's own checks green. Prevention: push the implementation first,
wait until the synchronize-triggered review run appears in GitHub Actions,
then mark ready as its own later step.
(Hit on `Lacaedemon/sparta#898`, 2026-07-15.)

**Check whether the race can even arise before paying for that wait --- on
many repos it cannot, and the check is one field.**
The race needs *two live runs*.
But the paragraph above sits in tension with this fragment's own
premise that "a draft doesn't trigger the `@claude` review bot": where that
holds, the push's synchronize run **skips** rather than running, so there is
nothing in flight for the `ready_for_review` run to cancel.
Which way a given repo behaves is visible directly --- read the review job's
conclusion on the push's own run before marking ready:

- `skipped` -> no live run, mark ready immediately, no wait needed.
- `in_progress`/`queued` -> the sparta case; wait for it to finish first.

Read it with `gh pr checks <N>`, or `pull_request_read` `get_check_runs` in a
session without `gh` (see [`tool-mappings.md`](../../tool-mappings.md)).
Mind the casing split [`fully-clean`](fully-clean.md) warns about: REST
returns lowercase `status`/`conclusion` (`completed`, `skipped`), while
`gh pr checks`/GraphQL return uppercase `state` values.

Don't generalize from either repo. sparta#898 is real, and so is the opposite;
the deciding factor is whether that repo's review workflow gates on
`github.event.pull_request.draft`, which is a property of the workflow, not
something to assume. (d-morrison/altdoc#55, 2026-07-25: the draft's
synchronize-triggered `review / claude-review` reported `skipped`, so marking
ready seconds after the push was safe and the subsequent `ready_for_review`
run posted a normal verdict.)

So the per-issue order becomes: claim → branch → **open the draft PR now** →
implement → mark ready-for-review → ARDI.

**Working several issues in one session? Verify you actually switched branches
before writing the second issue's code.** The `git checkout -b <type>/<slug>
origin/main` you ran for issue 1 doesn't carry over to issue 2 --- you have to
run it again with a new branch name for each new issue. Forgetting leaves the
working tree on issue 1's branch, so issue 2's edits land in the same
commit/PR as issue 1's --- silently, since nothing errors (there's no reused
branch name here to trigger `git checkout -b`'s own "already exists" error).
Run `git branch --show-current` immediately
before the first edit for every new issue, not just the first one in the
session, and confirm it matches the branch you just created for *this* issue.
(ucdavis/bcs `gia` session, 2026-07-06: SLURM-hardening changes for issue #286
were written while still on issue #281's `chore/renv-explicit-snapshot`
branch — caught before pushing, but only by re-checking `git status`/`git
diff --stat` against expectations, not because anything failed.)
