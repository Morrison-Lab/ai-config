# Verify CI on the merge commit, not only on the PR

A PR's own CI is not the whole story once it merges.
A repo can run a workflow on `push` that it never runs on `pull_request` ---
a full or PDF render, a deploy, a publish step ---
so a PR-preview workflow can stay narrower than what actually ships.
`fully-clean.md`'s criteria are scoped to the PR's own head;
nothing in them looks at the commit the merge produces on the base branch.

**The required state is that every workflow run triggered on the merge
commit itself concluded successfully.**
Not "looked at the Actions tab", not "the PR was green", not "no notification arrived" ---
each of those is a proxy a merge can satisfy while the actual push-triggered run is still queued, still running, or already red.
Per [`no-gameable-rules`](../principles/no-gameable-rules.md),
key the check to the run's own conclusion on that SHA, not to whether anyone looked at a page.

**A merge made under an `mwc` grant is covered the same way.**
The grant authorizes not asking before merging a fully-clean PR;
it says nothing about the state of `main` after the merge lands, and does not exempt this check.
The merge is not done until the push-triggered runs on that commit are green too.

**If a push-triggered run on the merge commit is red, fixing it is top
priority**, per [`fixing-mistakes-is-top-priority`](fixing-mistakes-is-top-priority.md) ---
not a follow-up issue to file and move past while `main` stays broken.

The check has to be armed or awaited, not remembered:

- **Wait for the runs and read them**, with
  [`scripts/check-merge-commit-ci.py`](../../scripts/check-merge-commit-ci.py)
  `-R <owner>/<repo> --sha <merge-sha>` ---
  exit 0 is clean, exit 1 is not-clean (a run failed or is still in progress),
  and exit 3 means no workflow runs are attached to that SHA yet.
  Retry on exit 3 rather than reading it as clean:
  a repo with push-triggered workflows can take a few seconds to register them,
  and an absent run is not the same as a successful one.
- **Schedule a check-in** when the runs will not finish quickly (a render, a deploy),
  rather than reporting the merge done and moving on.
  This is the same obligation [`AGENTS.md`](../../AGENTS.md)'s
  "Resume every non-clean pause" already states in general,
  applied to the specific moment right after a merge.

- **Do:** after every merge, run the instrument above against the merge
  commit and read its exit code before reporting the merge done.
- **Do:** if a push-triggered workflow is still running, schedule a
  check-in (or actively poll) rather than treating "merged" as "finished".
- **Do:** treat a red run on the merge commit as top priority, fixed before
  anything else, whether or not the merging session is the one that finds
  it.
- **Do:** treat this as covered by an `mwc` grant to merge, not exempted by
  it --- the grant authorizes the merge decision, not skipping what happens
  after.
- **Don't:** report a merge done because the PR's own CI was green; a
  push-only workflow (a full render, a PDF build, a deploy) never ran there
  at all, so a green PR check says nothing about it.
- **Don't:** read "no runs found yet" (exit 3) as a clean verdict --- it
  means the check has not registered, not that there is nothing to check.
- **Don't:** move on to other work while a push-triggered workflow is still
  queued or running on the merge commit, with no scheduled check-in armed.

(User directive, 2026-09-28: "cai: after merging a PR into main, always make
sure CI passed on the merge commit."
Incident: an agent merged several `Morrison-Lab/mds` PRs whose PR-level CI was green.
`publish.yml`, the workflow that runs on push to `main`, renders every format including PDF;
`preview.yml` renders HTML only, so nothing on the PR could see a PDF-only failure.
The merge commit's `publish.yml` run failed with a lualatex "Extra }, or forgotten $" error ---
a theorem-type div's `####` title contained `$[0, 1]$`,
and Quarto emits that title as `\begin{example}[...]`'s optional argument, so the `]` closed it early
(https://github.com/Morrison-Lab/mds/actions/runs/36405007145/job/108871519751,
fixed in [Morrison-Lab/mds#19](https://github.com/Morrison-Lab/mds/pull/19)).
The agent reported the merges done and moved on,
and found the red `main` only after the user pointed at the failing job.)
