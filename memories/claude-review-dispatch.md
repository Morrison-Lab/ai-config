# Dispatching an `@claude` review, and posting its reply

How a review run gets **triggered** in each repo family, and what happens to
the reply once it is written.
Satellite of [`claude-bot-workflows.md`](claude-bot-workflows.md), which owns
what a run does once it starts, split at the 1200-line gate.

## Re-triggering the @claude PR *review* (d-morrison Quarto / R-pkg repos, e.g. `psw`)
- Filenames below are those in the **content/package repos** (verified in
  `Morrison-Lab/psw`, moved there from `d-morrison/psw`): the review workflow
  is `.github/workflows/claude-code-review.yml`
  and the comment-triggered agent workflow is `.github/workflows/claude.yml`.
  (ai-config's *own* bot uses different names — `claude-review.yml` /
  `claude-bot.yml` — so don't infer these from *this* repo's `.github/workflows/`.)
- **`d-morrison/gha` itself (the shared workflow repo) is different:** the
  reusable workflow is `claude-code-review.yml` (no `workflow_dispatch`), and the
  dogfooding caller stub with `workflow_dispatch` is `claude-review.yml`.
  So to
  dispatch a review in `gha`:
  `gh workflow run claude-review.yml -f pr_number=<N>` (not `claude-code-review.yml`).
- The review workflow (which calls `d-morrison/gha`'s reusable review workflow)
  is **not** comment-triggered.
  It runs on `pull_request` (`types: [opened,
  synchronize, ready_for_review, reopened]`) and on `workflow_dispatch` (input
  `pr_number`).
  Posting an `@claude review` *comment* drives the separate agent
  workflow `claude.yml` (which then re-dispatches a review after it pushes) — it
  does not directly fire the review workflow.
- A new push (`synchronize`) auto-fires a fresh review --- the normal path during
  an iterate loop.
  A property of *those* repos, not a general one --- see "`ai-config` never
  auto-reviews a PR on push" at the end of this file.
- To force a fresh review on an existing PR **without a new commit**:
  - **workflow_dispatch** (preferred — no extra PR timeline noise).
    Same
    dispatch, three ways to send it:
    - **`gh`:** `gh workflow run claude-code-review.yml -f pr_number=<N>`
      (dispatches the workflow as defined on the **default branch** — `gh`
      defaults `--ref` to it).
    - **REST** (remote/web sessions, no `gh`):
      `POST /repos/<owner>/<repo>/actions/workflows/claude-code-review.yml/dispatches`
      with body `{"ref":"main","inputs":{"pr_number":"<N>"}}` (`"main"` = the
      repo's **default branch**; the `ref` must be a branch/tag that *contains*
      the workflow file, not the PR branch, unless you mean to dispatch a
      modified version).
    - **GitHub MCP:** your workflow-dispatch tool if available (e.g.
      `mcp__github__actions_run_trigger`).
  - **Close + reopen the PR** → fires the `reopened` event, which re-runs the
    review.
    Works reliably, but clutters the timeline with close/reopen events;
    prefer workflow_dispatch unless dispatch isn't available.
- **A successful `workflow_dispatch` review does not clear the PR's required
  `pull_request`-triggered check.**
  The dispatched run's check-runs attach to
  the **dispatch ref's SHA** (typically `main`, the default branch used to
  invoke it), not the PR's actual head SHA — even though the run reviews and
  comments on the right PR (it takes `pr_number` as an input and reads that
  PR's diff).
  So after a stub/failed `pull_request`-triggered review (see
  `mcp__github__actions_run_trigger` 403 below), posting `@claude review` or
  `/review` gets you a fresh, real verdict in the PR thread, but
  `review / claude-review` and any gate job on the PR's head SHA (checked via
  `get_check_runs`, not `get_status` — see below) stay red.
  Since reruns 403 in
  these sessions, the only way to get a fresh **gating** run is to push a new
  commit (an empty `git commit --allow-empty` is fine) so a real `pull_request`
  `synchronize` event fires against the actual head SHA. (Hit twice in one
  session on gha#176: two consecutive genuine — not raced — stub reviews on the
  pinned dogfooding checker, each requiring an empty retrigger commit after the
  dispatched `/review` came back clean.)
  - **The empty retrigger commit must be pushed by a HUMAN actor — a
    bot-pushed one is silently skipped.**
    `claude-code-review.yml` (and the
    review-triggering workflows generally) gate on a bot-actor `if:` filter
    (e.g. `github.actor != 'github-actions[bot]'` / not a `[bot]` login), so a
    `synchronize` event fired by a bot-authored push — e.g. the `@claude`
    agent itself doing `git commit --allow-empty` on the PR — is *filtered
    out* and never starts the gating `claude-review` run.
    The check stays red
    with no new run at all (not even a stub), which reads like nothing
    happened.
    Push the empty commit from a human actor (your own session's
    push) to get the gating run to fire.
    So when you ask the `@claude` agent
    to "retrigger the review," it can't self-serve this: its own empty commit
    is skipped, and it separately 403s on `rerun_failed_jobs` (below) — a
    human-actor push is the only lever left. (serocalculator#564, 2026-07-20:
    the agent's bot-pushed empty commit didn't fire the review; a
    human-actor empty commit did.)
  - **Root-caused and fixed at the source in gha#286 (issue gha#285):** the
    misattribution isn't inherent to `workflow_dispatch` -- it's that `gh
    workflow run <file> -f pr_number=<N>` with no `--ref` implicitly
    dispatches against the repo's default branch.
    `claude.yml`'s and
    `claude-review.yml`'s own dispatch calls now pass `--ref <PR-branch>`
    explicitly, so a re-dispatched review's check-runs attach to the PR's
    actual head commit and DO supersede a stale/cancelled `pull_request`-
    triggered run.
    Once a repo's `@v2` pin picks this fix up (check
    `slide-major-tag` has run since gha#286 merged), the empty-retrigger-
    commit workaround above should no longer be necessary for a plain
    `@claude review`/`/review` dispatch -- verify the fix landed before
    reaching for the workaround on a repo that might already have it.
- **Attribute a `workflow_dispatch`-triggered review run by its prompt or
  `pr-number` input, not its head branch.**
  A `claude-code-review` run dispatched with a `pr-number` input records
  `head_branch: <default-branch>` (the PR is an INPUT, not the run's head), so
  `gh run list` shows it as `Claude Code Review | head=main@<sha>` and two
  concurrent dispatched review runs on different PRs are indistinguishable by
  head, which defeats a `--headBranch`-filtered `gh run list` selection.
  To pin a dispatched run to its PR, read the run's own prompt (it embeds
  `/code-review ... /pull/NNNN`) or its `pr-number` input rather than its head
  branch.
  This is the same records-against-default-branch quirk
  `shared/workflow/fully-clean.md` documents for a `--commit`-filtered lookup,
  applied to a `--headBranch`-filtered one instead.
- **A stalled or hung `claude-review` job posts NO comment on the PR, so a
  stall leaves no PR-timeline breadcrumb.**
  Only the success path posts a `Claude finished review -- View run <url>`
  comment, so a run that hangs before reaching that step is invisible from the
  PR's own conversation and must be found through the run list
  (`gh run list --workflow`), not the PR timeline.
  The fix is tracked in Morrison-Lab/gha#424 (have the workflow post an early,
  PR-anchored comment linking the dispatched run so a stall is visible and the
  run is attributable up front).
- **A `claude-review` run's `updated_at` can freeze mid-run, so it is not a
  liveness signal.**
  A dispatched `Morrison-Lab/gha` `claude-review` run can sit
  `status: in_progress` with its run-object `updated_at` frozen for 10+ minutes
  while it is genuinely working --- a real review runs ~13 min, costs real money
  (~$28 for one three-sub-agent round), and only settles at the end.
  Reading `updated_at` (or wall-clock time since it) as a liveness/stall signal
  therefore produces a FALSE "stalled" conclusion.
  Judge liveness from the job LOG's own timestamps (first line to `Cleaning up
  orphan processes`) instead, per `shared/workflow/fully-clean.md`'s
  "`status` itself can be stale, so never infer a job's duration from it" rule
  --- this extends that rule from the check-run `status` field to the run-object
  `updated_at` field.
  (Morrison-Lab/ai-config#1194, 2026-08-06: run 31063429910 held
  `updated_at=2026-08-06T01:41:25Z` for ~13 min and was misread as stalled ---
  a false "stalled twice" claim was even published on Morrison-Lab/gha#362 and
  had to be corrected --- then posted a complete $28.31 "Needs minor changes"
  verdict from three parallel verify sub-agents.)
- **A distinct stub-review signature: `is_error: false`, real `num_turns`/cost,
  but `permission_denials_count: 1` and no `Verdict` line.** (`permission_denials_count`
  is a field in the Claude Code SDK's runtime execution-output JSON, not
  anything in this repo's own files — if a future SDK version renames it,
  look for an equivalent counter in that JSON rather than assuming the
  signature vanished.)
  Not the
  quota-exhaustion case (`total_cost_usd==0 && num_turns==1`) and not a raced
  cancellation (`conclusion: cancelled`) — the SDK call itself ran several
  turns and cost real money, but a denied tool call mid-run derailed it before
  it wrote a verdict.
  Reproduced 3× identically on the same PR/diff (gha#180)
  across both push-triggered and dispatched reruns — not random flakiness once
  it starts recurring on a given diff.
  **Root-caused and fixed in gha#185/#187:**
  agent mode's default `allowedTools` has no `WebFetch`/`WebSearch`, but the
  review prompt's own fact-checking instructions can still lead the agent to
  attempt one, and on denial it sometimes stopped instead of finishing.
  The
  fix is prompt-only — tell the reviewer up front that network-fetch tools
  aren't available (so it doesn't try) and that a denied tool call is never a
  reason to stop early — rather than widening `allowedTools`, since granting
  broad `WebFetch` to a review-only job with secrets access raises its own
  prompt-injection/exfiltration question for a workflow shared across
  potentially-private consumer repos.
  That tradeoff (a domain-scoped
  `WebFetch(domain:...)` allowlist to let the reviewer live-fact-check
  external sources, matching `gha`'s own `CLAUDE.md` "Fact-check prose
  against domain knowledge and external sources" review guideline) is left
  as an open decision in gha#189, not decided unilaterally.
  - **The stub can recur across *unrelated* PRs in the same session/window,
    not just repeatedly on one diff — treat a cluster as a
    session/service-level condition, not N independent diff bugs.**
    When two
    different PRs in different repos both stub within the same span
    (serocalculator#564 and gha#276, 2026-07-20, both stubbed in the same
    session), don't burn a re-trigger round on each hoping the *diff* is at
    fault: post the self-review (per `CLAUDE.md`'s "Do the review yourself
    when the @claude workflow doesn't produce a verdict"), hand the required
    `require-review` check to the human, and stop re-triggering after one
    round.
    Both the app token and the `@claude` agent 403 on
    `rerun_failed_jobs` (below), so neither you nor the agent can force a
    fresh gating run without a human-actor push — which the human is doing
    anyway when they decide to merge past the stubbed check.
- **Diagnosing which tool call was denied requires the reusable workflow's
  `show-full-output` input turned on for a re-run — the job log alone won't
  show it.**
  Same underlying hidden-output behavior as the
  `show-full-output`/`show_full_output` note below (see there for the
  input-vs-passthrough-parameter naming); worth restating here because it's
  the reason `permission_denials_count` in the final result confirms *that*
  something was denied but never *what* — the turn-by-turn tool-call detail
  is exactly what stays hidden without it.
- **Claude Code's tool-permission syntax scopes `WebFetch` by domain:**
  `WebFetch(domain:host)` (e.g. `WebFetch(domain:docs.anthropic.com)`), with
  wildcards like `WebFetch(domain:*.github.com)` (matches a subdomain at any
  depth, not the bare domain) or `WebFetch(domain:example.*)` (matches
  `example.org`, i.e. a wildcard segment can't cross a `.` — `example.*`
  does not match `example.evil.com`).
  Confirmed against the official docs:
  <https://code.claude.com/docs/en/permissions> (WebFetch section).
  Same
  bracketed-scope pattern as `Bash(git commit:*)`.
  Useful for granting
  narrow, exfiltration-bounded fetch access instead of unrestricted
  `WebFetch` or none at all.

## gha claude-code-review — self-modification skip guard (not a stub)

A PR that **edits `.github/workflows/claude-code-review.yml` itself** gets a
fast (~9s) green `review / claude-review` job that posts **no review**: the
reusable workflow detects the self-edit and deliberately skips
("PR #N edits .github/workflows/claude-code-review.yml — skipping self-review
(the action 401s on workflow validation until merged; it runs after merge)"),
and `require-review` tolerates the skip.
Don't treat this as a stub review or
re-trigger it — read the job log for the `::notice::` line to confirm, post a
manual self-review with a verdict instead (per the do-the-review-yourself
rule), and note the first genuine end-to-end run happens on the next PR after
merge. (ucdavis/win#75, 2026-07-16 — the migration PR itself could never be
bot-reviewed; win#69's post-merge sync then ran the migrated workflow live and
it worked, including `check-latex-macros` and the cost report.)

**A manual self-review is not the only remedy: the AGENT workflow
(`claude.yml`) carries no self-modification guard, so mentioning the bot in a
comment does produce a genuine external review of a PR that trips the
reviewer's guard.**
The guard lives in `claude-code-review.yml`, which gates on the caller's own
review-workflow path.
`claude.yml` is a separate reusable workflow with no equivalent check.
So on a guard-tripping PR, post the mention deliberately and let the agent
review it, which yields an actual external verdict at the current head.
[`fully-clean`](../shared/workflow/fully-clean.md)'s criterion 2 prefers an
external verdict whenever one is reachable, and a self-review cannot satisfy
it.

Two things to know before relying on it.
The mention is matched with `contains(github.event.comment.body, '@claude')`,
which has **no notion of code spans**, so writing the literal string inside
backticks or ordinary prose fires the workflow just the same.
That makes it easy to trigger a full agent run by accident while merely
*describing* the reviewer.
The agent's reply also arrives as a plain PR comment rather than a check run,
so it satisfies the review criterion without turning any check green, and
`claude-review` stays a skip either way.
(d-morrison/altdoc#71, 2026-07-27: a self-review comment that named the
reviewer woke the agent unintentionally, and it posted a substantive review of
the diff, checking `"${REF_ARGS[@]}"` expansion under `set -u`, the per-event
`author_association` fields, and `required: false` secret semantics, on a PR
whose `claude-review` job had skipped in 8 seconds.
Worth doing on purpose next time rather than by accident.)

**A third remedy, when the workflow edit is redundant with something already
merged: the guard keys on the PR's changed-FILE list, so a `main`-merge that
absorbs the edit clears it mid-PR.**
The "cannot clear before merge" note above is about the *same* diff, and it
holds — re-triggering never helps.
But when that workflow change lands on `main` via a different PR, merging
`main` back in resolves those lines and drops the file out of this PR's diff
entirely, so the next review run stops skipping and produces a real verdict.
Worth reaching for before writing a manual self-review, since it costs one
merge and yields an actual external verdict.
(ucdavis/bcs#450, 2026-07-28: its workflow-rename commit was superseded by
\#453; the `main`-merge shrank #450's diff back to its own five files and
re-enabled a genuine bot review that had been unobtainable for hours.)

## `ai-config` never auto-reviews a PR on push, and the absence is silent

Nothing here summons a reviewer when a PR is pushed: `validate` and `preview`
fire on a PR event, and no reviewer does.
So a PR reaches all-green CI, `mergeStateStatus: CLEAN`, and sits with zero
reviews forever, because nobody asked.

Derive it rather than recalling it; every row is one `on:` block that can change:

```bash
for f in .github/workflows/*.yml; do
  printf '%-32s ' "$(basename "$f")"
  sed -n '/^on:/,/^[a-z]/p' "$f" | grep -oE 'pull_request_review_comment|pull_request_review|pull_request|issue_comment|workflow_dispatch|schedule|issues|push' | sort -u | tr '\n' ' '
  echo
done
```

Every reviewer workflow, measured 2026-08-07:

| workflow | triggers |
| --- | --- |
| `claude-bot.yml` | `issue_comment`, `pull_request_review_comment`, `issues: assigned`, `pull_request_review` --- **no `pull_request` at all** |
| `claude-review.yml` | `workflow_dispatch` only, input `pr_number` |
| `antigravity-review.yml` | `issue_comment`, `workflow_dispatch` |
| `jules-review.yml` | `issue_comment`, gated on an `@jules` mention |

The remedy is one command:

```bash
gh workflow run claude-review.yml --repo Morrison-Lab/ai-config --ref <branch> -f pr_number=<N>
```

**The contrary expectation is written down, correctly, for other repos.**
This file's "Re-triggering the @claude PR *review*" section and
[`debugging.md`](debugging.md)'s ARDI polling bullet both say a push auto-fires
a review, and both are right about the content and package repos --- as is
`Lacaedemon/sparta`, which re-enabled its own trigger in sparta#1122.
So the question is not "does review fire on push" but "what does **this** repo
trigger on".

**The absence is silent and shaped like patience.**
Green checks plus no review is indistinguishable from a review still running,
so the natural response is to wait for something never scheduled.
[`fully-clean`](../shared/workflow/fully-clean.md)'s criterion 2 separates "no
findings" from "no verdict"; here nobody asked.
Copilot is no fallback either: `repos/Morrison-Lab/ai-config/rulesets` returns
one ruleset, `main`, carrying `deletion,non_fast_forward,pull_request` and no
`copilot_code_review` rule.

- **Do:** dispatch `claude-review.yml` explicitly after opening a PR here, and
  again after every push you want re-reviewed.
- **Do:** derive a repo's review triggers from its own `on:` blocks before
  concluding a review is late rather than absent.
- **Don't:** wait on an ai-config review you did not dispatch --- green checks
  plus an empty `reviews` array is the steady state, not a transient one.
- **Don't:** carry a sibling repo's auto-review behaviour across; the two look
  identical from the PR page.

(2026-08-06/07: PRs #1219 and #1224 each reached all-green CI with
`reviews: []` and stayed there until a review was dispatched by hand.
Reading the `on:` blocks directly corrected two rows a first-pass recollection
had wrong, neither of which changes the conclusion --- `antigravity-review.yml`
also carries `issue_comment`, and `jules-review.yml` is comment-triggered.)

## A workflow that posts the *last* assistant message loses the reply when a rule claims that slot

`claude.yml`'s reply step selects the final assistant turn out of the
execution file and posts it:

```jq
[.[] | select(type == "object" and .type == "assistant")] | last
| (.message.content // []) | map(select(.type == "text") | .text) | join("\n\n")
```

That is fine until the agent follows a corpus requiring its **last** message to
be a fixed marker --- ai-config's
`shared/workflow/flag-session-boundaries.md` and its `**Stopping Point**`
declaration.
Two rules then claim one slot, and the declaration wins every time by
construction, so the substantive answer is replaced by a one-line status
marker.

The loss is silent and unrecoverable: the run log does not carry the
conversation, and no execution-file artifact is published.
It is also self-concealing --- a stopping-point line reads like a completed
task, so nothing in the thread shows that an answer went missing.
Measured 2026-08-19 on `d-morrison/rme` after the ai-config plugin was
installed there (rme#1076): the pre-plugin reply ran 1182 characters, the three
post-plugin ones 233, 356 and 501, each beginning with the marker.
One run diagnosed the bug itself and had its diagnosis swallowed by it.

Two fixes, and both were needed.
Upstream, `flag-session-boundaries.md` now scopes the declaration to
interactive sessions and tells an agent whose last message a harness posts to
fold it into the substantive reply instead (ai-config#1711).
Consumer-side, [rme#1082](https://github.com/d-morrison/rme/pull/1082) made
the selection a **slice-and-join** from the last substantive message onward
rather than a pick.
That shape is the load-bearing part: any test for "is this message only a
declaration?" misjudges some message, and the two errors are not symmetric ---
over-including costs redundant text, visibly, while under-including costs the
answer, silently.
Joining the tail can only ever add text, so a misjudgement degrades into noise
instead of data loss.
The same eagerness applies to the marker test itself; an earlier revision
narrowed it to "single paragraph, or under 400 characters" for tidiness, which
made a long declaration test as substantive, become the slice start, and
exclude the real answer behind it --- reintroducing the exact loss.

- **Do:** slice from the last substantive message onward when a workflow posts
  an agent's reply, and keep any declaration test eager enough that refining it
  can only ever match *more* messages.
- **Do:** check what a consumer's reply step selects before installing a corpus
  that constrains the agent's final message.
- **Don't:** post a single picked message; a rule you do not control can occupy
  that slot.
- **Don't:** read a well-formed status line in a PR thread as evidence the
  reply arrived intact.

(Tracked as [rme#1081](https://github.com/d-morrison/rme/issues/1081).
The two rules are individually reasonable and collide only when composed,
which is the class of defect a memory catches and a code review of either side
alone does not.)
