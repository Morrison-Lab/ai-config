# Mention and sender gates of the `@claude` bot workflows

Satellite of [`claude-bot-workflows.md`](claude-bot-workflows.md),
split at the 1200-line gate (ai-config#1228).
The sections below moved verbatim; the parent keeps the bot's run behaviour.
[`mention-triggers.md`](mention-triggers.md) covers why the mention rule kept recurring.

## The bot-sender gate is on the actor, so commenting is not a way around it

This repo's review workflows skip when the event's **actor** is a bot, and that
gate is keyed on the actor rather than on the event type.
Measured 2026-09-17/18 from a Claude Code project thread, whose GitHub token is
the `claude[bot]` App identity:

- A **push** from the thread runs `claude-review.yml` on `pull_request`, and
  every `review /` job skips, `require-clean-verdict` included.
  GitHub counts a skipped required check as satisfied, so the PR reads
  `mergeable_state: clean` while carrying no verdict at all.
  Tracked as ai-config#3743.
- An **`@claude review` comment** from the same identity fires
  `claude-bot.yml` on `issue_comment` and skips as well.
  In run `35311218322` the `claude / mention-filter` job itself skipped, ahead
  of the `claude / claude` job, so the gate rejects the event before any agent
  starts.
  `GET actions/runs?event=issue_comment` reports `actor=claude[bot]` and
  `triggering_actor=claude[bot]` on every such run.
- That one comment skipped **Antigravity Code Review** and **Jules PR Review**
  in the same second, so this is not one reviewer's own gate.

A comment from a bot identity therefore never reaches the agent.
The `workflow_dispatch` fallback is a separate story, and a coarse reading of
it is wrong in both directions.
Three dispatches were observed on 2026-09-18 between 05:43 and 05:53.
The actor column is the one that explains them, and the first reading of this
table omitted it:

| run | actor | bound ref | outcome |
| --- | --- | --- | --- |
| `35311949751` | `github-actions[bot]` | `d36a6a62`, PR #3762's own head | all seven `review /` jobs succeeded; posted a real verdict |
| `35312346178` | `claude[bot]` | `aa32a3c1`, `main` | `claude-review` short-circuited; posted the gha#543 caution **onto #3762** |
| `35312509759` | `claude[bot]` | `26fd21fb`, PR #3763's own head | short-circuited too, with the right ref |

So binding to the wrong ref (gha#285) and the action refusing the actor are
**two independent failures**, and the second is not luck.
**A dispatch meets a second, different gate.**

The job `if:` in `Morrison-Lab/gha`'s `claude-code-review.yml` opens
`github.event_name == 'workflow_dispatch' ||`, so a dispatch is *exempt* from
the `github.event.sender.type != 'Bot'` test that filters the automatic
`pull_request` path.
It then reaches `anthropics/claude-code-action`, which applies its own
`allowed_bots` check, and gha's `allowed-bots` input defaults to
`github-actions[bot]` --- chosen because that is the actor `gh workflow run`
uses when `claude.yml` re-dispatches a review, and stated in that input's own
`description:` block.
A thread's dispatch carries `actor=claude[bot]`, which is not on that list, so
the action stands down without reviewing.

The correlation holds across every `workflow_dispatch` run of
**`Morrison-Lab/ai-config`'s** `claude-review.yml` visible on 2026-09-17/18,
but it is a correlation with the `claude-review` **job**, not with the run's
conclusion.
All four `claude[bot]` dispatches (`35312509759`, `35312346178`,
`35268075963`, `35267489584`) concluded `failure` with that job short-circuited.
Of the ten `github-actions[bot]` dispatches in the same window as of
2026-09-19T19:22Z, three concluded `failure` and one `cancelled`.
Those four are not counter-examples, and reading them as counter-examples is
the trap: on `35317602132`, the one read job-by-job, `claude-review` and
`require-review` both succeeded and only `require-clean-verdict` failed, which
is the action reviewing and returning a verdict of "not clean".
A run conclusion aggregates the gate jobs downstream of the review, so it
answers "is this PR clean" rather than "did the reviewer run".

**Name the repository whenever you write a run id down.**
Every id above belongs to `ai-config`, the *caller*, while the reusable
`claude-code-review.yml` this section mostly discusses lives in `gha` --- so a
reader carrying that repo forward looks them up in the wrong one, and a run id
is scoped to its repository.
The wrong repo returns a plain `404`, which reads as "this id was invented"
rather than "you are asking the wrong repository":
a reviewer of this paragraph 404'd on all seven and reported them fabricated.

- **Do:** read `claude-review`'s own conclusion when the question is whether
  the action was let in at all.
- **Do:** write the owner and repo beside a run id, in a passage that names
  more than one repository.
- **Don't:** count a `failure` run conclusion as an actor rejection;
  a real review with findings produces the same colour.
- **Don't:** read a `404` on a run id as evidence the id is wrong until you
  have confirmed which repository it belongs to.

**Settle it from the run list, not from the job log.**
A check run carries no actor, so this is one of the cases that genuinely needs
`list_workflow_runs`, whose spill-file remedy
[`github-mcp-tools`](github-mcp-tools.md) already carries.

- **Do:** read a short-circuited dispatch as an `allowed_bots` rejection until
  the run's actor says otherwise.
- **Don't:** pass `allowed-bots: claude[bot]` to make thread dispatches work.
  That input's description says to widen it only when the automatic gate has
  already been loosened, and widening it here would admit bot-authored pushes
  to review themselves.

Two consequences worth holding on to.
A dispatch bound to `main` attaches its red check runs to `main`, so the PR it
posted a caution onto still reads green on its own head --- the caution and
the check state disagree by construction, and only the caution is about that
PR.
And the caution's wording, "this PR has **not** been reviewed", is a claim
about *its own run*, not about the PR: an earlier run on the same head may
already have posted a verdict, as happened on #3762.

- **Do:** have a human push, or post `@claude review`, from their own account.
  A User-actor event passes the filter.
- **Do:** ask them for a **base sync** specifically, when the choice is yours
  to shape.
  Merging `main` into the branch is a push, so it starts the review by itself
  with no comment to write, and they can do it from the PR page's own
  "Update branch" button without a checkout --- which makes it the cheapest
  thing a blocked session can ask a human for.
  Measured 2026-09-18 on ai-config#3737.
- **Don't:** read "a comment fires a different event" as implying it meets a
  different gate.
  The event differs; the actor does not.
- **Don't:** spend one comment per PR re-measuring this.
  A single run's `mention-filter` conclusion settles it for the whole repo.
