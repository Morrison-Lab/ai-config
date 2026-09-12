# Two consumer-side gotchas when calling `Morrison-Lab/gha`'s Claude workflows

[`gha-reusable-workflows.md`](gha-reusable-workflows.md) is where this belongs
topically; this stays a separate satellite file for two consumer-side
findings rather than a merge into that file.
Both were hit migrating a hand-rolled
`claude.yml`/`claude-code-review.yml` in a consumer repo to thin callers of
`Morrison-Lab/gha`'s reusable versions (`Morrison-Lab/qwt#135`).

## A permissions-mismatch startup_failure is invisible outside a browser

`github-actions.md`'s "GitHub Actions workflow authoring gotchas" section
already covers the mechanism and the remedy for a caller under-granting a
permission a nested job requests: the graph-build-time check that fails the
whole call with `startup_failure` and zero jobs created even when the
under-permissioned job is `if:`-skipped, and the sibling trap where an
**omitted** key in an explicit `permissions:` block defaults to `none`
rather than inheriting anything -- both ending in the same "copy the
`permissions:` block from the matching `examples/<name>.yml` verbatim"
remedy this file would otherwise just repeat. Hit the identical shape again
migrating `Morrison-Lab/qwt`'s `claude-code-review.yml` caller (`issues: read`
where the nested `claude-review` job needs `issues: write`; `Morrison-Lab/qwt#135`),
and confirmed a gap that section doesn't cover: **how you actually see the
error.**

`gh run view` prints only `This run likely failed because of a workflow file
issue`, with no detail. The REST API has no endpoint for it either --
`gh api repos/<owner>/<repo>/actions/runs/<id>/jobs` returns
`{"jobs":[],"total_count":0}`, and there's no check run to attach an
annotation to, so nothing shows up in `gh pr checks` (the same shape
[`fully-clean`](../shared/workflow/fully-clean.md) documents for
`action_required`-blocked runs). The actual error text -- naming the exact
job, permission, and value -- only exists in the rendered Actions run page's
`Annotations` panel. Fetch it there (`get_page_text` in a browser tool, or
scrape the HTML) when a `pull_request`-triggered reusable-workflow caller
completes with `startup_failure` and an empty `jobs` array.

- **Do:** read the rendered Actions run page's `Annotations` panel when a
  reusable-workflow caller fails with `startup_failure` and zero jobs --
  `gh run view` and the REST API surface nothing.
- **Do:** see `github-actions.md`'s "GitHub Actions workflow authoring
  gotchas" for the permission-grant mechanism and remedy; this only adds
  where to find the error text once you've hit it.
- **Confirmed again, different repo, different permission**:
  `Morrison-Lab/psw`'s `claude-code-review.yml` caller granted `contents`,
  `pull-requests`, `issues`, `id-token` but omitted `actions`, while the
  callee's `claude-review` job requests `actions: read` (to let
  `claude-code-action` install its `github_ci` MCP server). Same
  `startup_failure`, zero jobs, nothing in `pull_request_read`
  `get_check_runs` or `get_job_logs`. `WebFetch` on the run's `html_url`
  reliably surfaced the Annotations text verbatim -- "The nested job
  'claude-review' is requesting 'actions: read', but is only allowed
  'actions: none'." -- confirming this isn't `Morrison-Lab/qwt`-specific and
  that a plain `WebFetch` (not just a dedicated `get_page_text` browser
  tool) is sufficient to read it. (Morrison-Lab/psw#43/#44, 2026-08-10.)
  This exact `actions: read` gap -- same four granted permissions, same
  `startup_failure`/zero-jobs shape -- had already happened once before,
  in `ai-config` itself rather than a downstream consumer
  ([`github-actions.md`](github-actions.md), ai-config#224).
  So this is the third occurrence, not the second, and "not
  `Morrison-Lab/qwt`-specific" above undersells it -- the gap recurs
  independently of which repo is calling `Morrison-Lab/gha`, ai-config's
  own repo included.

## A mention-triggered caller's startup_failure is invisible to everything, not just to the CLI

The section above answers "how do I read this error".
This answers the prior question nobody asks, because on every case recorded above somebody was already looking: a red check on a PR sent them there.

A `startup_failure` creates zero jobs and therefore zero check runs.
On a `pull_request`-triggered caller that still surfaces, since the PR's check list is short one expected entry and the run sits at the top of `gh run list`.
On a caller triggered by `issue_comment`, `issues`, `pull_request_review`, or `pull_request_review_comment` --- which is every `claude.yml` stub --- it surfaces nowhere.
There is no PR to be short an entry, no check run to go red, and no notification.
The agent simply never answers, which is indistinguishable from quota, from a trusted-author gate declining, or from nobody having mentioned it.

Measured 2026-08-27 on `UCD-SERG/shigella`: nine consecutive `Claude Code` runs concluded `startup_failure` between 2026-08-24 11:42 and 2026-08-27 18:20 Pacific, and the first anyone knew of it was a run URL pasted into a session by hand.
The cause was the `ANTHROPIC_API_KEY`-at-`@v1` secret mismatch [`gha-reusable-workflows.md`](gha-reusable-workflows.md) already records --- so the corpus could diagnose it in one read, and nothing in the corpus was going to make anyone look.

Worse, the interim change read as a fix.
The consumer repointed both callers from `d-morrison/gha` to `Morrison-Lab/gha` during those three days, which is a real improvement and left the tag pin untouched, so the tenth failure looked exactly like the first.

The check is one command, and it belongs immediately after merging any PR that touches a mention-triggered caller:

```bash
gh run list -R <owner>/<repo> --workflow claude.yml --limit 5 \
  --json databaseId,conclusion,createdAt \
  --jq '.[] | "\(.databaseId) \(.conclusion) \(.createdAt)"'
```

A column of `startup_failure` is the whole diagnosis.
Diff the caller's `secrets:` and `with:` keys against the callee **at the pinned tag** from there --- cheaper than the Annotations-panel route above, and sufficient for the secret and input cases.

- **Do:** list the workflow's own recent runs after merging a change to a mention-triggered caller, since no check list will report it.
- **Do:** read a silent agent as a possible `startup_failure` rather than as quota or a gate.
- **Don't:** treat repointing an owner, sliding a tag, or any other improvement to the caller as evidence the caller now starts --- only a green run is.
- **Don't:** expect `gh pr checks`, a PR's check list, or a notification to carry this;
  all three are structurally blind to it.

(Tracked as [ai-config#2473](https://github.com/Morrison-Lab/ai-config/issues/2473).)

## A caller-level `concurrency:` group with the same name as a nested job's own group deadlocks the run

[`github-actions.md`](github-actions.md)'s "A caller with no `concurrency:`
block can still have its runs cancelled" documents one direction: a caller
with **no** `concurrency:` block still gets cancelled, because
`Morrison-Lab/gha/.github/workflows/claude-code-review.yml`'s own
`claude-review` job declares

```yaml
concurrency:
  group: claude-review-${{ github.event.pull_request.number || inputs.pr-number }}
  cancel-in-progress: true
```

internally.
The mirror direction is worse.
A caller that declares its **own** top-level `concurrency:` block using that
**same** group name -- the natural thing to write when migrating a
hand-rolled workflow that already had its own per-PR dedup, since it looks
like the obvious way to express "serialize per PR" -- doesn't merely race
against the nested job's group.
GitHub Actions detects it as a deadlock between the top-level workflow and
the nested job, and cancels the run outright, every time, before it does
anything:

```
Canceling since a deadlock was detected for concurrency group: 'claude-review-<pr>'
between a top level workflow and 'review / claude-review'
```

Nothing in `examples/claude-code-review.yml` or the README warns against
this -- the example simply has no caller-level `concurrency:` block at all,
so there's nothing to contradict. The trap is specifically for anyone
preserving an *existing* per-PR concurrency group during a migration to the
reusable workflow, since the reusable workflow already provides that dedup
internally and a caller-level block is never needed for it. Filed as
[Morrison-Lab/gha#437](https://github.com/Morrison-Lab/gha/issues/437) to
get a warning added to the example/README.

- **Do:** omit any caller-level `concurrency:` block when calling
  `claude-code-review.yml` -- the nested `claude-review` job already
  serializes per PR.
- **Do:** read the called workflow's own job-level `concurrency:` blocks
  before adding one at the caller level for "the same" purpose.
- **Don't:** assume a caller-level concurrency group used to preserve old
  standalone-workflow behavior is safe just because it matches the old
  group-name pattern -- if the reusable workflow already declares an
  identically-named group on a nested job, this deadlocks rather than merely
  racing.

## A missing review is not a pending one; redispatch posts a comment but does not make the PR mergeable

Fourth occurrence of the same permission-mismatch class this file already
tracks,
now `checks: read` rather than `actions:` or `issues:`.
Every `claude-review` run in `Morrison-Lab/ai-config` ended `startup_failure`
from 2026-09-06T06:50Z:
gha's reusable review job needed `checks: read`,
which the caller had not granted,
and a called job may not request more than its caller grants --
so the call broke at parse time
(ai-config#3303, Morrison-Lab/gha#830, fixed by `checks: read` in #3313).

A `startup_failure` creates zero jobs and zero check runs,
so an affected PR's checks read all-green with simply no review comment,
and `check-pr-fully-clean.py` correctly reports "No automated review comments
or reviews found" --
which reads as "not yet reviewed" and is actually "the review workflow
cannot start."
When a PR shows green checks and no review for longer than one normal
review round,
check `gh run list --workflow=<review>.yml --json conclusion` for
`startup_failure` rather than continuing to wait.
This half held up under later measurement and is unchanged.

**Corrected belief, from ai-config#3305.**
An earlier version of this entry claimed that redispatching
`claude-review.yml` via `workflow_dispatch` "heals every open PR," on the
strength of `workflow_dispatch` always running the workflow file from the
default branch.
That premise is true and the conclusion drawn from it was wrong --
the two were never the same claim.

- **Was believed:** redispatch makes the PR fully mergeable, because it runs
  the fixed caller and produces a clean review.
- **Measured instead:** redispatch runs the fixed caller and DOES post a
  review comment, so `check-pr-fully-clean.py` correctly goes green on the
  strength of that comment -- but the run executes in the *default branch's*
  context, so its check runs attach to `main`'s SHA, not the PR head.
  The repo's required check (`review / require-review`) therefore never
  appears on the PR, and `gh pr merge` still fails with "the base branch
  policy prohibits the merge" while the fully-clean instrument reports
  clean.
  A green `check-pr-fully-clean.py` and an unmergeable PR are consistent
  states here, because the two read different things: a comment, versus a
  check run tied to a specific SHA.

**A second belief in the same entry was asserted mid-session, before being
tested, and was also wrong.**
The claim was that a `pull_request` event uses the merge ref
(`refs/pull/N/merge`) and so needs no branch sync to pick up a base-branch
fix.
Measured the same day, on branches that both still lacked the `checks: read`
fix (`git show origin/<branch>:.github/workflows/claude-review.yml | grep -c
"checks: read"` returned 0 for both, so branch content was not the
variable):

- #3305 closed-and-reopened (a `reopened` event, head SHA unchanged) ->
  `startup_failure`.
- #3312 after a push -> `success`.

What differed was that a push refreshes `refs/pull/N/merge` against the
current base; a bare reopen does not.

- **Do:** read a PR with green checks and no review as a possible
  `startup_failure`, and check `gh run list --workflow=<review>.yml` before
  waiting longer.
- **Do:** treat a redispatch's clean `check-pr-fully-clean.py` verdict as a
  comment having landed, not as the PR being mergeable -- check for the
  `review / require-review` check run on the PR head before attempting
  merge.
- **Do:** to get both a working review AND the required check run onto a
  stalled PR head, push to the branch (a `main` merge is the natural push);
  closing and reopening the PR does not refresh the merge ref and leaves
  `startup_failure` in place.
- **Don't:** read "No automated review comments or reviews found" from
  `check-pr-fully-clean.py` as proof the review is merely pending -- confirm
  the workflow actually started.
- **Don't:** assume `workflow_dispatch`'s default-branch behavior extends to
  making the PR mergeable, or that a `pull_request` event's merge-ref
  semantics substitute for an actual push -- both were asserted here
  without being measured first, and both were wrong.

## Slide-tag callee permissions gate (gha#836)

`slide-major-tag.yml` gates sliding major tags on `audit_callee_permissions.py`.
Before advancing a floating tag (e.g. `v2`), the script compares all reusable workflows
(`on: workflow_call`) between the base tag and the head commit.

It rejects:
- Added permission keys on any job or workflow level.
- Widened permission values (`read` -> `write`, or dict -> `write-all`).
- Jobs gaining a `permissions:` block where none existed.
- Jobs dropping a `permissions:` block (reverting to unconstrained inheritance).

It permits:
- Narrowed values (`write` -> `read`, `read` -> `none`).
- Dropped permission keys.
- Brand-new reusable workflows (no existing callers pinned to the base tag).
- Comment edits and key reorderings (parsed YAML per-job set comparison).
