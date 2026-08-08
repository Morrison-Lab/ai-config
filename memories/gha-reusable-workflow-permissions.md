# Two consumer-side gotchas when calling `Morrison-Lab/gha`'s Claude workflows

`github-actions.md`'s "d-morrison/gha reusable workflows" section is where
this belongs topically, but that file sits at the 1200-line size gate with
zero headroom (`scripts/check-memory-file-size.py`), so this is a satellite
file for two new findings rather than an addition there -- the same reason
[`github-mcp-tools.md`](github-mcp-tools.md) split out of
[`github.md`](github.md). Both were hit migrating a hand-rolled
`claude.yml`/`claude-code-review.yml` in a consumer repo to thin callers of
`Morrison-Lab/gha`'s reusable versions (`d-morrison/qwt#135`).

## A permissions mismatch against a nested job fails with ZERO jobs and ZERO check runs

A `uses: <owner>/<repo>/.github/workflows/<file>.yml@<ref>` caller must grant,
at the calling job's `permissions:` block, everything every job **inside**
the called workflow requests -- not just what the top-level docs mention in
passing. Getting one wrong (`issues: read` where the nested job needs
`issues: write`, say) produces:

```
Invalid workflow file: .github/workflows/<caller>.yml#L37
The workflow is not valid. ... Error calling workflow '<owner>/<repo>/.github/workflows/<file>.yml@<ref>'.
The nested job '<job-id>' is requesting 'issues: write', but is only allowed 'issues: read'.
```

as a `startup_failure` conclusion with **zero jobs recorded** --
`gh api repos/<owner>/<repo>/actions/runs/<id>/jobs` returns
`{"jobs":[],"total_count":0}`. That is the same shape
[`fully-clean.md`](fully-clean.md) already documents for
`action_required`-blocked runs: a workflow run that fails before any job
starts produces no check run at all, so `gh pr checks` shows nothing wrong
and the failure is invisible to any check-runs-only poll.

The error text names the exact fix (which permission, which value), but
nothing surfaces it except opening the run in a browser -- `gh run view`
prints only `This run likely failed because of a workflow file issue`, with
no detail, and the REST API has no endpoint for it since there's no check
run to attach an annotation to. Fetch the rendered Actions run page and grep
its `Annotations` section (`get_page_text` in a browser tool, or scrape the
HTML) when a `pull_request`-triggered run of a reusable-workflow caller
completes with `startup_failure` and an empty `jobs` array.

Before trusting a hand-transcribed `permissions:` block against an example
caller, diff it line-by-line rather than eyeballing it -- a one-word slip
(`read` for `write`) parses as valid YAML, passes `actionlint` (it doesn't
resolve remote reusable-workflow schemas), and only fails at real dispatch
time, against the live PR, invisibly.

- **Do:** grant, in the caller's `permissions:` block, the union of every
  permission any job inside the called workflow requests -- read the called
  workflow's own source rather than inferring from its `secrets:`/`inputs:`
  contract or an example that might be stale.
- **Do:** check a reusable-workflow caller's actual run (not just `gh pr
  checks`) after the first push, since a `startup_failure` with zero jobs is
  invisible to a check-runs-only view.
- **Don't:** trust a hand-copied `permissions:` block without diffing it
  against the example byte-for-byte -- a single wrong verb parses fine and
  fails silently until a real `pull_request` event fires it.

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
