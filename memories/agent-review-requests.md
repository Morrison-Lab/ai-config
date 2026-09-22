# Requesting a Claude review from an agent session

Split out of [`github-actions.md`](github-actions.md) at the 1250-line gate.
For what the reusable review workflow does once dispatched --- including how it
triggers, stashes and restores requested reviewers, and posts its reply ---
see [`claude-review-dispatch.md`](claude-review-dispatch.md).

## How an agent session requests a review: a `/review` comment, never a dispatch

An agent session -- a Claude Code remote/web session, a thread session, or one
of their subagents -- cannot reach the Claude reviewer the way a person does,
and the two gates that stop it fail in different, quiet ways.

The **automatic** `pull_request` path is gated on
`github.event.sender.type != 'Bot'` inside the reusable workflow, and such a
session pushes under the harness's App identity, so every `review /` job skips.
A skipped job counts as passing for branch protection, so the PR then reads
`mergeable_state: clean` while carrying no verdict at all
([ai-config#3743](https://github.com/Morrison-Lab/ai-config/issues/3743)).

The **direct `workflow_dispatch`** path looks like the obvious bypass, and it
is half right: the reusable workflow's `if:` admits `workflow_dispatch`
unconditionally, so the run does start.
`claude-code-action` then rejects the triggering actor, because the caller
passes `allowed-bots: github-actions[bot]` and the dispatching session is
`claude[bot]`.

The tell is a run that concludes `failure` having spent nothing.
Measured 2026-09-18 on this repo, every dispatched run with
`triggering_actor: claude[bot]` -- all four this repo has ever had:
[35267489584](https://github.com/Morrison-Lab/ai-config/actions/runs/35267489584),
[35268075963](https://github.com/Morrison-Lab/ai-config/actions/runs/35268075963),
[35312346178](https://github.com/Morrison-Lab/ai-config/actions/runs/35312346178)
and
[35312509759](https://github.com/Morrison-Lab/ai-config/actions/runs/35312509759)
-- packed `failure-kind: short-circuit`, `attempts: 1`,
`total-cost-usd: 0.0000`, with the "Run Claude Code Review" step lasting 35ms
and skipping its own Bun install.
The four dispatched runs with `triggering_actor: github-actions[bot]` checked
in the same window --
[35311949751](https://github.com/Morrison-Lab/ai-config/actions/runs/35311949751),
[35312775441](https://github.com/Morrison-Lab/ai-config/actions/runs/35312775441),
[35312827292](https://github.com/Morrison-Lab/ai-config/actions/runs/35312827292)
and
[35312866850](https://github.com/Morrison-Lab/ai-config/actions/runs/35312866850)
-- produced a real review.
`SELF_MOD` was `false` on each failure, so this is not the gha#598
workflow-restore path, and the cost of zero rules out the mid-run quota skip.
Derive that population rather than recalling it: `actions_list`
`list_workflow_runs` on `claude-review.yml`, filtered to
`event: workflow_dispatch`, read for `triggering_actor.login`.

That reading is easy to get wrong in a specific way worth naming: a
short-circuit is also the signature of gha#368, an intermittent no-verdict
crash, so the first diagnosis of these runs was "the dispatch bypass is
unreliable" and the remedy inferred from it was to retry.
Retrying reproduces it exactly, because the discriminator is the **actor**
rather than the attempt --- 4 of 4 one way, 4 of 4 the other.
Read the actor before reading the failure kind.

**So request a review by posting a comment whose first token is `/review`.**
`.github/workflows/claude-review.yml`'s `dispatch-on-comment` job answers it
(see [`claude-review-dispatch.md`](claude-review-dispatch.md) for how the
workflow handles the dispatch once started):
it looks the PR's head branch up over the API, dispatches with `--ref` so the
check-runs land on the PR's own head rather than the default branch
(gha#285), omits `--ref` for a fork or a workflow-editing PR (gha#289,
gha#598), and acknowledges with a link to the dispatch run.
Because that dispatch is issued under `GITHUB_TOKEN`, the triggering actor is
`github-actions[bot]`, which `allowed-bots` already admits --- so the comment
route fixes both gates at once rather than widening either.

The command is a slash command and not an `@claude` mention on purpose: any
`@claude` substring also wakes `claude-bot.yml`'s agent, which is a far more
expensive thing to start by accident, and would let a review summon an agent.
Nothing the review path posts begins with `/review`, so it cannot re-enter
itself.

- **Do:** post `/review` (optionally with text after it) as a PR comment, and
  read the acknowledgement's link to find the dispatch run.
- **Do:** check a dispatched run's `triggering_actor` before diagnosing a
  zero-cost short-circuit as a flake.
- **Don't:** dispatch `claude-review.yml` directly from an agent session ---
  the run starts, costs nothing, and fails.
- **Don't:** reach for an `@claude review` comment instead; the mention filter
  skips a bot sender before any agent starts, and if it ever stopped doing so
  it would start an agent rather than a review.

## Measured end to end, and the one row that reads like a failure

The `/review` route above was written from the workflow's own source.
Measured from a thread session on 2026-09-21, that route works:
a bare `/review` comment posted by `claude[bot]` on
[ai-config#3852](https://github.com/Morrison-Lab/ai-config/pull/3852)
at head `6b318903` produced
[run 35689771719](https://github.com/Morrison-Lab/ai-config/actions/runs/35689771719),
in which all six `review /` jobs concluded `success` ---
`require-review` and `require-clean-verdict` among them ---
and `scripts/check-pr-fully-clean.py` then exited 0 on that same head.
The automatic `pull_request` run on that identical head under four minutes
earlier,
[run 35689529308](https://github.com/Morrison-Lab/ai-config/actions/runs/35689529308),
skipped all six.
So the two paths were compared against one commit rather than across two.

Derive both halves from one query rather than reading either run's page:

```bash
curl -sS -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/<owner>/<repo>/commits/<sha>/check-runs?per_page=100" \
  | jq -r '.check_runs[] | select(.name | startswith("review /"))
           | [.name, .conclusion, .details_url] | @tsv'
```

Both runs survive that query, because the default `latest` filter dedupes
within a check suite and these are two suites --- measured on `6b318903`,
`filter=latest` and `filter=all` each returned the same twelve rows.
The cost of the dispatched run, $0.6517, is not in that output;
that figure comes from the review comment's own `total_cost_usd`.

**The dispatched run's own `dispatch-on-comment` job reads `skipped`, and
that row is not evidence the route failed.**
That job's `if:` requires `github.event_name == 'issue_comment'`, while the
run that job dispatched carries `workflow_dispatch` --- so the job is by
construction inapplicable to the very run it started.
The trap is that this row sits at the top of the job list, above the six that
matter, and `skipped` is exactly the word this page teaches a reader to
distrust on the automatic path.
Reading that row as the same signal inverts the conclusion: the one route that
does produce a verdict gets abandoned for the reason the other one fails.

The routing mechanism that makes `/review` work is written down in the
workflow itself, in `.github/workflows/claude-review.yml`'s header on `main`.
The skipped-row consequence is not narrated there;
it follows only from `dispatch-on-comment`'s own `if:` read against the
triggering event.
So read that condition rather than inferring the mechanism from the event
sequence, which is the same trap
[`claude-review-dispatch.md`](claude-review-dispatch.md) records for the
reviewer's stash-and-restore of requested reviewers.

- **Do:** read the six `review /` jobs on the dispatched run, and ignore the
  `dispatch-on-comment` row there.
- **Do:** confirm a route's verdict by scoring the head with
  `scripts/check-pr-fully-clean.py`, not by reading job rows alone.
- **Don't:** read `dispatch-on-comment: skipped` on a dispatched run as the
  bot-sender skip this page's first section describes.
  That skip is a sender-type gate on the automatic path, whereas the skipped
  `dispatch-on-comment` row is an event-type mismatch, and that row appears on
  every successful dispatch.
- **Don't:** conclude the comment route is unavailable to an agent session ---
  the comment route is the one path measured to produce a verdict from
  `claude[bot]`.
