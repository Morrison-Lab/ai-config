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
