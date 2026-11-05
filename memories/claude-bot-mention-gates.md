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

## A comment a workflow *posts* is a mention-trigger surface, not just output

`claude-bot.yml` gates on `contains(github.event.comment.body, '@claude')`, a
plain substring test with no notion of Markdown.
The known consequence is that a human quoting the mention while writing *about*
the bot dispatches a run (#682 -> #683, and gha#342's stripper is the fix
upstream).
The consequence that is easy to miss: **your own workflows post comments too**,
and that gate does not care who wrote the body.

So a step that helpfully points a reader at the other reviewer ---
`Review it with @claude review instead` --- makes every one of its own comments
dispatch an agent run.
Nothing about writing it feels like triggering anything, because the mention is
being *documented* rather than issued, and it is being written into a workflow
file rather than into a comment box.
It becomes a comment only at runtime.

This is worse than the human-quoting case in two ways.
It fires on a code path taken automatically, so it repeats for every occurrence
rather than once per careless comment.
And it usually sits in an error or fallback path, which is exactly where nobody
watches closely and where the spurious run is least wanted.

The check is cheap: grep any workflow that posts a comment for every bot
mention it can emit, and confirm each one is either wanted or defanged.
Prefer rewording over cleverness --- naming the reviewer without the `@` is
both safe and usually more accurate, since an automatic reviewer needs no
request at all.

- **Do:** treat a `-f body=` / `gh pr comment` payload in a workflow as
  trigger-carrying text, and grep it for mentions before shipping.
- **Do:** name a bot without its `@` when the point is to tell a human which
  reviewer covers them.
- **Don't:** rely on backticks or a code span to defang a mention in a body
  your workflow posts --- the gate reads the raw string.

(Morrison-Lab/ai-config#857, 2026-07-30: an on-demand Jules trigger grew a
fork-skip comment ending "Review it with `@claude review` instead."
Caught in self-review before the first push; every fork skip would have
dispatched an agent run, on the exact substring gate this file already
documents for the human case.)

**gha#342's stripper does not close the human case, because a mention can be
quoted with no markup around it at all.**
That fix strips blockquote lines, fenced code blocks, indented code blocks,
and inline code spans before matching, so *upstream* it catches a mention
someone wrapped in backticks or quoted as a block.
It cannot catch one sitting in ordinary prose, and a rule cited by its own
title is exactly that, since quotation marks are not markup.

**The pin used to be the first reason this repo did not have the stripper.**
`claude-bot.yml` called `claude.yml@v1` until #1000; #998 had already moved
`claude-review.yml` to `@v2`. Check by content, not tag date: `v1` is frozen
and is not an ancestor of the fix (`detect-bot-mention` count is 0 at `v1`
and 1 at `v2`). A backticked mention on this repo now reaches the stripper.

The remaining reason holds after the pin moved.
`claude.yml@v2`'s own job-level `if:` still tests the raw body with
`contains()`, because a GitHub expression cannot strip Markdown, so the job
starts and the runner spins up regardless.
What the stripper buys is the billed agent run and the review re-dispatch, not
silence.
So a code span is the wrong thing to trust under either pin, which is what the
Do bullet below is about.

This corpus makes the bare case the common one rather than a rare one, because
four of its headings carry the mention with no markup at all:

```bash
grep -rn '^#\{1,6\} .*@claude' --include=*.md . | grep -v '`@claude'
```

Read that `grep -v` as isolating the bare subset, not as clearing what it
drops.
It filters out three further headings whose mention is backticked, and at
`@v1` those are no safer than the four it keeps.

One of the four is `CLAUDE.md`'s "Do the review yourself when the @claude
workflow doesn't produce a verdict", which is self-defeating in a specific
way: the rule you reach for *because* the reviewer failed cannot be named in a
comment without spending a real agent run.

So cite such a rule by section without reproducing its title verbatim, or
defang the mention when the title has to be quoted.
Neither backticks nor gha#342 will do it for you.

- **Do:** reword a quoted rule title that carries the mention, rather than
  trusting a code span to neutralize it.
- **Do:** read the caller's own pin before reasoning about the stripper at
  all, since `@v1` does not carry it.
- **Don't:** read gha#342 as closing the quoting hole in general --- upstream
  it closes the markup-quoted half only, and at `@v1` it is not in play at
  all.

(`Morrison-Lab/ai-config#986`, 2026-07-31: a self-review comment named that
rule in a parenthetical, mention bare, and workflow run 30664135897 was
created five seconds later.
That run is the one whose `Prompt is too long` comment finally explained the
afternoon's failures, so an accidental dispatch is the only reason the answer
existed at all --- which is luck, and not a reason to leave the hole open.)
