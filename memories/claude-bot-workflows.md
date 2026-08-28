# The `@claude` bot workflows (`Morrison-Lab/gha`)

The bot's own behaviour: what a run does, how it fails, and how to recover.
Split out of [`github-actions.md`](github-actions.md), which keeps the
generic Actions-authoring material.

Triggering a review, and what becomes of the reply it writes, live in
[`claude-review-dispatch.md`](claude-review-dispatch.md).

## @claude CI action (Morrison-Lab/gha `claude.yml`)
- The reusable `claude.yml@v1` agent workflow restores config files (`CLAUDE.md`,
  `.claude/**`) to `origin/main` during its run (`restoreConfigFromBase`), so a
  PR can't rewrite the reviewer's own instructions. With `eager-pr: true` +
  `contents: write`, the **residual auto-commit step** historically then committed
  that reset onto the PR branch as `claude[bot]` "chore: auto-commit residual
  @claude session changes" — **deleting the PR's own `CLAUDE.md` edits**.
  `memories/**` and `skills/**` were untouched; only the restored-config paths
  were affected.
- **FIXED in gha `v1` (≈2026-06-20):** the residual sweep now force-reverts the
  protected config paths (incl. `CLAUDE.md`, `.claude`, `.mcp.json`, `.gitmodules`,
  `.husky`) back to **PR-tip (HEAD)** before `git add -A`, so it no longer commits
  the reset. A follow-up commit (`78fe7bc`, "honor PR deletions of config files in
  the residual sweep") prevents the sweep from reverting legitimate config-file
  deletions in the PR.
  Verified on ai-config#41: once the fix landed, the gut stopped recurring (the
  config-edit payload stayed on the branch across later bot runs). Was tracked as
  Morrison-Lab/gha#39.
- If a repo pins an **older** gha tag (pre-fix), the workaround still applies. The
  symptom was `claude[bot]` "auto-commit residual @claude session changes" commits
  that reverted only config paths. Restore the section
  (`git checkout <my-commit> -- CLAUDE.md`, commit), then before merging verify with
  `git diff origin/main -- CLAUDE.md` being **non-empty** (an empty diff means the
  payload was silently reverted to main), and merge promptly.
- **The bot-resolves-version-to-`==main` failure mode below is obsolete once a
  repo adopts `Morrison-Lab/gha`'s new `bump-dev-version`/`version-check`
  capabilities (gha#390, tracking gha#388).** Once a repo migrates, PRs never
  carry a `DESCRIPTION` version bump at all, so there is no version line left
  for a bot merge to resolve one way or the other, and this whole bullet's
  "re-check versions after a bot merge" step no longer applies there. Not
  deleted here since most repos haven't migrated yet --- check whether the repo
  in front of you has before following this recovery step.
- **The `@claude` agent can push a `main`-merge commit to your PR branch — not just
  comment.** Triggered by PR activity, the `claude.yml` agent may merge `origin/main`
  into the branch and push it (e.g. `claude[bot]` "Merge branch 'main' into <branch>").
  **The same collision happens with a human's push, too** — e.g. the repo owner
  clicking GitHub's "Update branch" button while you're mid-session on the same PR
  produces an identical merge-main commit (authored by the human, committed by
  `GitHub`) and the identical rejection; the recovery is the same regardless of who
  pushed it. Two consequences: (1) your in-flight local push is rejected ("fetch
  first" / RPC `HTTP 403` from the git backend — a non-fast-forward, **not** a
  policy denial); (2) **bot-push only** — the `@claude` agent may resolve a
  `DESCRIPTION` version conflict to `== main` when it merges, which then fails
  `version-check`; a human's "Update branch" click doesn't do this — GitHub blocks
  the merge on conflict instead of silently resolving it, so re-check versions only
  applies after a bot merge. Recovery (either case): stash any uncommitted work
  first (`git stash` — `reset --hard` discards it), then `git fetch origin <branch>`,
  `git reset --hard origin/<branch>` onto the remote's merge commit (build on it —
  don't force-push a competing parallel merge of your own), then re-bump the version
  above main if needed and push.
  (Hit on bcs#255: the bot pushed `4807f0c` and resolved the version to `.9062` == main,
  failing version-check until I bumped to `.9063` on top.)
- **Cherry-pick recovery when the bot and your session both merge main.** If the `@claude` agent pushes a merge-main commit to the PR branch while you have unpushed commits, your push will be rejected ("fetch first"). Don't open a competing parallel merge — cherry-pick instead: (1) note the SHA of your local fix commit(s), (2) `git reset --hard origin/<branch>` to build on the bot's merge, (3) `git cherry-pick <sha>`, (4) push. This lands your fix cleanly on top without creating a divergent history.
- **The `@claude` agent can run a parallel session that posts a phantom commit SHA.**
  While you ARDI a PR (pushing fixes + posting reply comments), the activity can trigger
  the `claude.yml` agent to spin up its own run that attempts the *same* fixes, fails to
  push (it collides with your pushes), then posts review comments crediting a commit SHA
  that **never reached the remote** (e.g. it posts "Addressed in `a841fc7`", but that SHA
  was never pushed and isn't on the remote). The fixes are really there via *your* pushed commit; the cited SHA
  is a phantom. Don't chase it: verify the real branch head with `git ls-remote origin
  <branch>` (or `git rev-parse HEAD` vs `origin/<branch>`), and if the cited SHA fails
  `git cat-file -t <sha>` it never existed. Post a one-line clarification on the PR so the
  phantom doesn't confuse later readers, and keep going. (Hit on ai-config#254.)
- **A self-review's own prose can false-positive-trigger the `@claude` agent via
  substring match.** `claude.yml`'s comment dispatcher matches any occurrence of the
  literal substring `@claude` in a new PR comment, not just a genuine mention. A manual
  self-review that refers to the failed job by name (e.g. "the `@claude` review job
  failed with a hard SDK error") satisfies that match and spins up an unrelated agent
  run. That run isn't wasted, though: it re-reads the whole thread, finds no new
  directed request, but still runs a general review pass — and in one observed case
  that was enough to independently catch and fix a real stale-doc bug (a `CLAUDE.md`
  line no longer matching the PR's own diff), committing the fix under the same GitHub
  identity a human session posts under.
  From outside, this looks exactly like a second human/session claiming the same PR (a
  duplicate "Working on this" comment, an unexplained new commit) even though only one
  person was ever working it. Before treating that as a collision worth investigating,
  check the commit author: `Claude <noreply@anthropic.com>` committing without a
  matching claim from an actual second session is this false-positive-trigger pattern,
  not a real parallel-session conflict. (Hit on Morrison-Lab/gha#225: the self-review
  comment's own reference to the failed `@claude` review job triggered a real agent
  run, which found and fixed a stale `CLAUDE.md` trigger-type claim before the PR
  merged.)
  Prevention: in PR status/report comments, don't write the literal string
  `@claude` unless you want a run — say "the Claude review" / "the Claude
  bot" instead. Each accidental mention dispatches a full agent workflow run
  (API spend) even when the comment asks for nothing. (Second instance on
  ucdavis/rampp#111, 2026-07-18: a ready-for-merge report quoting "latest
  @claude verdict" dispatched a run, which correctly no-op'd with a status
  recap.)
  (Third instance on UCD-SERG/lab-manual#441, 2026-07-24: a status comment
  reporting "the `@claude` review verdict is clean" dispatched a run against
  `main`'s HEAD rather than the PR branch (the `gha#285`/`gha#286`
  `workflow_dispatch`-without-`--ref` pattern documented under "@claude CI
  action" below), even though the PR's own review had already gone clean.
  It self-resolved with an "Acknowledge @claude mention" no-op rather than
  making any change, but still cost a wasted agent run.)
  **The vector is not limited to comments: an issue's own body or title
  matches too, via the `issues` trigger.** `claude.yml`'s job gate for the
  `issues` event checks `contains(github.event.issue.body, ...)` /
  `contains(..., .title, ...)` with the same formatting-blind substring match,
  so **filing** an issue that merely discusses the bot dispatches a full agent
  run -- the worst case of the four, because an issue is the artifact most
  likely to *describe* the bot rather than address it, and because
  `eager-pr: true` makes that run open a branch and a draft PR before doing
  any work. Prevention on the caller side: don't list `opened` in the
  `issues:` trigger types. `ai-config`'s `claude-bot.yml` now uses
  `types: [assigned]` for exactly this reason (#686/#687) -- the agent runs
  only when deliberately summoned. Note the gate treats `assigned` the same
  way, so bare assignment is not itself sufficient; the issue text must still
  contain the mention. (Fourth instance, ai-config#682 -> #683, 2026-07-24: an
  issue proposing a markdown line-length check said "like the `@claude`
  reviewer already can" inside a code span; the run opened #683, worked ~8
  minutes, then died at the push step on the `WORKFLOW_TOKEN` gap, losing the
  work.)
  **Once fired, a remote/web session cannot call it back -- so prevention is
  the only control.** `cancel_workflow_run` 403s exactly like
  `rerun_failed_jobs` does (see `memories/github-mcp-tools.md`), and no MCP tool edits
  an existing comment, so the mention can't be defused after the fact either.
  Editing would not help regardless: the caller stubs trigger on
  `issue_comment: [created]`, so an already-fired comment cannot re-fire, and
  a later edit changes nothing. Don't spend retries discovering this. (Fifth
  instance, `UCD-SERG/serocalculator#605`, 2026-07-25: a comment reporting a
  CI blocker said "another `@claude` review (about $1.24)" -- backticked and
  purely descriptive -- and spawned a $0.43 run that correctly no-op'd.
  Both a cancel attempt and a search for a comment-edit tool came up empty.)
- **Dispatched reviews now post a PR comment (gha#89, now in `v1`).** Before this fix,
  `workflow_dispatch` runs wrote output to the step summary only —
  `github.event.pull_request.number` is null for dispatch events, so the action's
  internal post-step failed silently, and the old-comment collapse step then minimized
  all prior review comments, leaving the PR thread silent. Fixed by a "Post review
  comment for dispatched run" step that reads the last assistant text from the execution
  file and posts it via `gh issue comment`. When the review finds no new issues, Claude
  is prompted to link the most recent prior `claude[bot]` review comment and state it
  still stands. Execution file extraction (for debugging):
  ```
  jq -r '[.[] | select(.type == "assistant") | .message.content[]? | select(.type == "text") | .text] | last // ""' \
    "${RUNNER_TEMP}/claude-execution-output.json"
  ```
- **Dispatched review quoting bug (gha#90, not yet fixed).** When the review body
  contains backtick-quoted text (e.g. `` `@v1` ``), the "Post review comment for
  dispatched run" step fails with `unexpected EOF while looking for matching '"'` — the
  backticks are interpreted as shell command substitution. The review itself still
  completes: look for `Claude review completed cleanly (subtype=success)` in the step
  logs to confirm. The PR comment simply isn't posted. Workaround: push a trivial
  commit to trigger the push-based review instead of dispatching again.
- **Self-mod skip in `claude-code-review.yml` (added in gha#70, now in `v1`).** The
  workflow skips when the PR modifies `.claude/**` paths or the
  review workflow file itself (derived from `github.workflow_ref`). CI completes in
  ~48 s without posting a verdict comment. This prevents 401 errors from the
  App-token exchange during workflow validation of a not-yet-merged workflow file
  (source: gha#70 PR body). Not a CI failure — check the job logs for the skip message.
  **The self-mod skip is NOT the same signal as the quota-skip (gha#104) — the
  `require-review` gate job does not catch it.** `require-review`'s `if:` only
  goes gray when `claude-review`'s result is literally `skipped` or
  `quota_exhausted=true`; a self-mod skip leaves individual *steps* conditioned
  off (`steps.selfmod.outputs.self_mod != 'true'`) but the `claude-review` JOB
  itself still reports `success`, so `require-review` passes trivially and the
  PR shows all-green with no review having actually run. Don't read "CI green,
  no `@claude` comment" as "review ran clean" on a PR that touches
  `claude-code-review.yml` — check the `claude-review` job log for the
  `self_mod=true` notice, and do a manual review in its place (same playbook as
  the quota-skip case below). (d-morrison/altdoc#14.)
- **`grep -qxF` for literal fixed-string line matching in workflow files.** Flags: `-q`
  = quiet, `-x` = full-line match, `-F` = treat pattern as a fixed string (not a
  regex). Omitting `-F` makes `.` in file paths (e.g.
  `.github/workflows/claude-code-review.yml`) act as a regex wildcard, so the selfmod
  check would match any file with a similar path structure. Use `-qxF` whenever
  comparing file paths literally. The `selfmod` step in `claude-code-review.yml` uses
  `grep -qxF` for this reason.
- **`is_error=true, subtype=success` in review execution output — two distinct causes:**
  - **Quota/auth exhaustion** (`total_cost_usd=0`, `num_turns=1`, `duration_ms` < 2000):
    the API rejected the request before Claude did any work. Fixed in gha#102 (`@v1`):
    the guard step exits 0 and posts a `[!WARNING]` PR comment naming `CLAUDE_CODE_OAUTH_TOKEN`
    as the account whose quota is exhausted. Further fixed in gha#104: a second `require-review`
    gate job (whose `if:` is false when `quota_exhausted=true`) shows as the gray **skipped**
    icon rather than a misleading green checkmark. Consumers should add `require-review` (e.g.
    `review / require-review`) to their branch protection required-checks.
    Fix: wait for quota reset (or auth fix), then re-trigger. No need to push a commit.
    ⚠️ **Verify the consumed guard actually warns — don't assume the fix is live.**
    Observed 2026-06 on sparta#207 (consuming `Morrison-Lab/gha@v1`) AND in `dem-extra1/gha`'s
    own `claude-code-review.yml`: the guard still `exit 1`d on `is_error=true` (RED check, no
    `[!WARNING]` comment) — gha#102's exit-0 behavior was not yet on the consumed `@v1` pin
    there. Read the actual guard code on the pin you consume rather than trusting this note.
    Note OAuth/subscription auth (`CLAUDE_CODE_OAUTH_TOKEN`) shows `total_cost_usd=0`
    regardless, because it isn't metered per-call — so cost=0 + 1 turn + immediate `is_error`
    points to a **subscription usage-limit**, not only API credits; confirm via the Anthropic
    Console usage for that account.
    ⚠️ **That signature is necessary for a usage-limit and not sufficient for one**, which is
    why this bullet is headed "Quota/auth" rather than "Quota": an expired or invalid token
    dies at the same model call, having done the same zero billable work, so the result object
    is indistinguishable on every field the guard reads.
    The test that settles it is a **before/after on this repo alone**: rewrite its
    `CLAUDE_CODE_OAUTH_TOKEN` from a known account, change nothing else, and re-run.
    A run that then reaches the model proves the credential was the fault, because it is the
    only variable that moved.
    A **cross-repo** success (the same reviewer working on a different repo at the same time)
    proves only that the **service** is up --- not that the account has quota, because
    `rotate-claude-token.py`'s docstring records that each repo's secret is minted by whichever
    account the local CLI happened to be logged into, and that a mix provisioned across several
    sittings "cannot be untangled after the fact".
    Use
    `gh api repos/<owner>/<repo>/actions/secrets --jq '.secrets[] | "\(.name) \(.updated_at)"'`
    to pick which repo to rewrite --- a token written long before a working repo's is a rotation
    that plausibly missed it --- but treat that as triage, not evidence.
    See [`review-verdict-pitfalls`](../shared/workflow/review-verdict-pitfalls.md) for the full statement.
  - **Intermittent upstream bug** (`total_cost_usd > 0`, `duration_ms` ~192 s): the
    `claude-code-action` completes a real review but exits with `is_error=true` anyway.
    The guard step fails the check ❌. The prior clean review on the same diff is still
    valid.
    Fix: **re-run the failed job first** (`gh run rerun <id> --failed`).
    `gh run rerun --help` documents that flag as "Rerun only failed jobs, including
    dependencies", so it re-runs the review job and whatever it depends on rather
    than the whole workflow (verified against `gh` 2.96.0, 2026-07-30).
    A trivial commit is not needed, and it costs a commit plus a full CI round for
    a defect that is not in the diff.
    The no-op re-run is also the better evidence, because nothing changed between
    the two attempts.
    A pass therefore proves the failure was transient by construction, which is the
    negative control `shared/workflow/review-verdict-pitfalls.md`'s eighth case prizes.
    A push cannot show that, since it changes the code.
    Fall back to a trivial commit only if the re-run fails too.
    Observed on gha#92 run #28034977099.
    The re-run path was verified on Morrison-Lab/ai-config#922, 2026-07-30, where
    the run reported `is_error=true` with `subtype=success`, `num_turns=7`,
    `duration_ms=118719`, `total_cost_usd=1.10`, and no permission denials, having
    posted a full `Ready for merge` verdict.
    The re-run on the same commit passed.
- **A review job with `conclusion: success` but NO posted comment is NOT
  automatically "unreviewed."** It is either (a) a quota/auth skip (see above:
  `total_cost_usd=0`, `num_turns=1`) or (b) a genuinely **clean review that found
  nothing to flag**. Tell them apart from the job log: a clean review shows a
  full agent run (`"subtype":"success"`, `"is_error":false`, high `num_turns`,
  `total_cost_usd` > 0) followed by `No buffered inline comments` in the
  post-comments step — the bot reviewed and posted nothing because it had nothing
  to say. Don't treat that as a missing review or re-trigger it. (macros#71:
  `claude-review` ran 21 turns at $0.88 and buffered 0 comments = clean.)
- **Reading the hidden error behind a failed `claude-code-review`.** The action prints
  `Running Claude Code via SDK (full output hidden for security)…` and suppresses the real
  API error. The reusable `claude-code-review.yml` now accepts a **`show-full-output`** input
  (default false; added in dem-extra1/gha#1) that passes through to the action's
  `show_full_output` — flip it to print the raw error in the job log. The live consumer pin
  `Morrison-Lab/gha@v1` may not carry it yet, so check the tag.
  You CANNOT side-channel the
  error from a throwaway workflow on a feature branch: `claude-code-action` rejects `push`
  events (`Unsupported event type: push`) and refuses to run unless the workflow file is
  byte-identical to the default-branch copy (`Workflow validation failed … must … match the
  default branch`) — both are deliberate guards, so a diagnostic workflow only works once
  it's on `main`.
- **`review / claude-review` fails with "no '### Verdict' heading" (gha#173,
  closed/fixed) — a DIFFERENT failure than the `is_error=true` cases above.**
  Symptom: the job's SDK run reports `is_error: false` / `subtype: success` (it
  genuinely completed, no crash), but a guard step (`run-review-guard`) still
  fails the job because the review's final message never emitted the mandated
  `### Verdict` heading or `Verdict:` line — the review agent silently
  stubbed. `review / require-review` then fails too, since it gates on this
  job. **This is the fix, not a bug**: gha#173 replaced an earlier
  silent-green-stub failure mode with a loud one, so don't read the red check
  as a content problem in your diff — check the job log
  (`mcp__github__get_job_logs`) for this exact error string before assuming
  otherwise. gha#173's primary contribution is that `run-review-guard` step
  itself, not a proven root cause for *why* the agent stubs — its issue body
  only *observed* (hedged, not traced) that `workflow_dispatch` re-triggers
  succeeded more reliably than another push in the incidents it cites, and
  don't read that as push-trigger-*specific*: the separate gha#185/#187
  root-cause investigation later found the underlying stall reproduces across
  **both** push-triggered and dispatched reruns on the same PR/diff (gha#180)
  — so `workflow_dispatch` is a practically-useful re-trigger, not a guaranteed
  fix tied to the push/dispatch distinction. If the API returns
  `403 Resource not accessible by integration` on
  `rerun_failed_jobs`/`run_workflow` (no Actions-write permission in the
  session), you can't self-trigger the dispatch — surface it to the user with
  the fix path rather than guessing at a comment-based re-trigger. In practice,
  the very next push-triggered review after the failure has also gone through
  cleanly both times it recurred (rme#706, #976) — so a subsequent normal
  push can clear it too; try `workflow_dispatch` if you have the permission
  and a normal push isn't an option (e.g. no new commit to make).
- **A bot-sender push never triggers the ai-config review workflow ---
  every `review /` job skips,
  and the run still reads `completed/success`.**
  Measured 2026-08-27 on ai-config#2340:
  four pushes by the Cursor cloud agent
  each produced a "Claude Code Review" run
  whose `gather-context` succeeded
  and whose `review / *` jobs all skipped,
  because the callee (`Morrison-Lab/gha/claude-code-review.yml@v2`)
  gates its jobs on `github.event.sender.type != 'Bot'`
  (drafts and fork heads are filtered by the same `if:`).
  Nothing in the PR announces it:
  the head sits "unreviewed" while the runs list looks green.
  The same `if:` admits `workflow_dispatch` at the job level,
  so on a same-repo, non-Dependabot PR the fix is one dispatch:
  `gh workflow run claude-review.yml -R Morrison-Lab/ai-config -f pr_number=<N>`
  --- which produced a real verdict on the same head
  the push-triggered runs had skipped.
  (A dispatched run still passes through the callee's `dispatch-guard` step,
  which blocks fork and Dependabot PRs precisely because
  dispatch bypasses the payload gate.)
  - **Do:** on a PR whose recent heads were pushed by a bot
    (Cursor, @claude's own sync),
    read the review run's *job* conclusions
    before concluding a review ran;
    dispatch `claude-review.yml` for the head.
  - **Don't:** read a green "Claude Code Review" run on a bot-pushed head
    as a review having happened --- `success` there is the skip path.
- **Write accurate `workflow_dispatch` comments when adapting the upstream
  `claude-code-review.yml` template.** The upstream template says "workflow_dispatch is
  fired by claude.yml" — but that's only true when the repo's `claude.yml` actually
  dispatches the review workflow. In repos where `claude.yml` runs `claude-code-action`
  directly (e.g. qbt), that comment is wrong. When adapting the template, check whether
  the local `claude.yml` dispatches `claude-code-review.yml`; if not, rewrite the
  comment to say "workflow_dispatch is a manual re-review from the Actions UI" rather
  than citing `claude.yml`. The `PR_NUMBER` env comment (was "when claude.yml triggered
  us") should become "when a manual re-review is triggered." Fixed in rpt#153 and qbt#43.
- **`@claude review` produced no review? Trace the whole dispatch chain — the
  failure is usually in the *dispatched* review run, not the agent run.** An
  `@claude review` *comment* fires the agent workflow `claude.yml` (issue_comment),
  which **succeeds** and then, in a later step (a regular step after the Claude run —
  not an Actions post-step), re-dispatches `claude-code-review.yml` via
  `gh workflow run` (workflow_dispatch). So a green `claude.yml` run with no review
  comment means the review died in the separately-dispatched run. Find it:
  `actions_list` the runs of `claude-code-review.yml` filtered to
  `event=workflow_dispatch` around the comment time, then read that run's failed
  job logs. Don't stop at the agent run's green checkmark. (Diagnosed on rme#706:
  agent run 28256515868 was green; the dispatched review run 28257175025 had failed.)
- **`allowed_bots` actor gate: dispatched reviews fail in ~6 s with "Workflow
  initiated by non-human actor: github-actions (type: Bot)".** `anthropics/claude-code-action`
  has its **own** actor gate, separate from the workflow's job-level `if:`. Because
  `claude.yml` re-dispatches as `github-actions[bot]`, the action aborts
  ("Add bot to allowed_bots list or use '*'") unless the action step sets
  `allowed_bots: "github-actions[bot]"` in its `with:` (underscore — the action's
  own input name; the gha reusable exposes this as `allowed-bots` with a hyphen
  and maps it through). A job `if:` that permits
  `workflow_dispatch` is **not** enough — the run passes the `if:` then dies one layer
  deeper in the action. The canonical gha reusable `claude-code-review.yml` already
  sets this (via its `allowed-bots` input, default `github-actions[bot]`); a
  standalone copy must add it. Fixed for rme in #945.
- **Consumer repos may carry a standalone `claude-code-review.yml` that has drifted
  from the gha reusable one — check gha first when debugging CI/infra bugs.** Not
  every consumer calls `uses: Morrison-Lab/gha/.github/workflows/claude-code-review.yml@v1`;
  some (rme, pre-#948) kept a hand-maintained fork that missed fixes gha already
  had — that drift is how the `allowed_bots` bug reached rme. When debugging a
  CI/infra bug in a consumer repo, compare against the canonical gha `@v1` version;
  the fix often already exists there. Preferred remedy: migrate the standalone file
  to a thin reusable-workflow caller (gha ships example caller stubs in `examples/`)
  so it can't drift again. Keep the workflow filename and the `pr_number`
  workflow_dispatch input so `claude.yml`'s
  `gh workflow run claude-code-review.yml -f pr_number=<N>` still works, mapping it
  to the reusable's `pr-number` input; set `checkout-submodules: true` if the repo
  has submodules the reviewer must read (e.g. rme's `latex-macros`). Done for rme
  in #948.
- **The `@claude` reviewer may re-raise a finding that was previously rebutted and
  its thread resolved, if a new commit triggers a fresh review cycle.** Each review
  run re-reads the diff from scratch; a rebuttal reply in the thread does not persist
  into the next run's context. Keep the rebuttal text ready to post again. (Hit
  repeatedly on ai-config#267 with the MD060/table-column-style finding.)
- **The agent can commit the right fix and still fail to push it, when the diff
  touches `.github/workflows/*.yml` -- "refusing to allow a GitHub App to create
  or update workflow ... without `workflows` permission".** `claude.yml`'s
  `PUSH_TOKEN` (`secrets.WORKFLOW_TOKEN || secrets.GITHUB_TOKEN`) needs an
  explicit `workflows` OAuth scope to push a commit that edits a workflow file;
  a plain `GITHUB_TOKEN`/GitHub App token doesn't have it, and even a
  configured `WORKFLOW_TOKEN` secret can be unset/not wired for a given
  trigger path. The job reports `conclusion: failure` on its "Push branch and
  finalize PR" step (`get_job_logs` with `failed_only: true` shows the exact
  rejection), and the draft PR is left with only its empty seed commit -- the
  correct fix exists only in that ephemeral run's checkout, never landed.
  A session with a broader-scoped push (e.g. Claude Code on the web) doesn't
  hit this, so the recovery is: read the failed job's logs for the actual
  diagnosis, fetch the PR's real head branch (`pull_request_read`'s
  `head.ref`, not the harness-assigned fallback branch -- see "Use the
  existing PR branch" in `CLAUDE.md`), re-implement the same fix from that
  session's own checkout, and push directly. (gha#286, fixing gha#285: the
  agent's own commit correctly added `--ref` to every `gh workflow run`
  dispatch call, including in `.github/workflows/claude-review.yml`, but the
  push to `claude/issue-285-...` 403'd on exactly that file; re-implemented
  and pushed from the Claude Code web session instead.)

  **The run does not merely lose the work quietly -- a later post-step posts a
  comment claiming the fix shipped.**
  The push step exits 1, but the "Post Claude's response if no code was
  committed" step is not gated on it, so the PR thread gains an affirmative
  "Applied both fixes from the prior review: 1. ... 2. ..." for a commit that
  is not on the branch.
  That is worse than silence: the next reader, human or reviewer bot, has no
  reason to doubt a state claim and no cheap way to check it, which is the
  failure [`ardi`](../shared/workflow/ardi.md) names from the author's side,
  arriving here from someone else's run.
  So when a PR comment says a fix was applied and the diff does not show it,
  do not assume you are looking at a stale page.
  Two commands decide it: compare the PR's `head.sha` against what the claim
  implies, and read the linked run's own job list for a failed **Push** step.
  Do not re-derive the fix from the comment's prose either -- read the failed
  run's log, since the comment can describe a fix that was itself partly wrong
  (here it claimed to swap `statuses: write` for `issues: write`, and both
  halves of that were incorrect).
  Filed as `Morrison-Lab/gha#360`.
  (`Morrison-Lab/ai-config#805`, 2026-07-29, run 30435574496: the consumer-repo
  instance -- `gha` set its own `WORKFLOW_TOKEN` after gha#292, but
  `ai-config` never had one, so `secrets: inherit` had nothing to inherit,
  tracked as `Morrison-Lab/ai-config#807`.
  Note the secret is optional by design, so its absence is invisible in every
  new consumer repo until the first workflow-touching push.)

- **A dispute about which `permissions:` key an action needs is decided by the
  run log, not by reasoning about which REST endpoint it calls.** Every job
  prints the granted set near the top of "Set up job":

  ```text
  ##[group]GITHUB_TOKEN Permissions
  Contents: read
  Metadata: read
  PullRequests: write
  Statuses: write
  ##[endgroup]
  ```

  Pair that with evidence the disputed call actually succeeded -- for a
  comment-posting action, the comment's own `created_at` (never `updated_at`) from
  `gh api repos/{o}/{r}/issues/{n}/comments`, matched against the run's step
  timestamps -- and a green run under the disputed permission set is
  conclusive.
  This is the [`algorithmatize-checks`](../shared/workflow/algorithmatize-checks.md)
  rule applied to a review argument: two log excerpts settle it exactly, so
  never trade citations about endpoint semantics instead.

  The specific claim worth knowing, since it is the one that keeps coming up:
  `POST /repos/{o}/{r}/issues/{n}/comments` is shared by issues and pull
  requests, and the required permission follows **which** it is called on --
  `pull-requests: write` authorizes it against a PR number, while
  `issues: write` is needed only against an issue number.
  A `pull_request`-triggered workflow that only ever comments on PRs therefore
  does not need `issues: write`, and adding it is an unused widening.
  (`Morrison-Lab/ai-config#805`: a reviewer raised this, was rebutted, re-raised
  it in a fresh thread with a one-click `suggestion` block, and retracted it in
  the next round once shown a run that had already posted and edited the
  comment under `PullRequests: write` alone.
  The first of its two suggestion blocks also silently dropped the
  `statuses: write` that the reviewer had retracted moments earlier -- another
  instance of the standing rule that a suggestion block's literal is a claim to
  verify, not text to accept.)

## Disabling the @claude agent in a gha-consumer repo

- **Commenting out the triggers is not enough; the job also needs
  `if: false`.**
  The reusable `claude.yml` **runs unattended on `workflow_dispatch`** -- its
  gate exempts that event (and `schedule`) deliberately, on the reasoning that
  dispatching already requires Actions write access.
  And you cannot simply delete the `on:` block, because GitHub rejects a
  workflow file with no trigger at all, so some placeholder has to remain.
  Leave `workflow_dispatch:` as that placeholder and put `if: false` on the job.
  Either mechanism alone leaves the agent runnable by anyone who can press
  "Run workflow".
- **Check the review stub's own triggers BEFORE disabling the agent -- you may
  be removing the only path that starts a review.**
  `claude.yml` is what dispatches a review on an `@claude review` mention, so in
  a repo whose automatic `pull_request` review is already off, turning off the
  agent leaves no review path whatsoever.
  The fix is the `/review` path from
  [gha's example stub](https://github.com/Morrison-Lab/gha/blob/v2/examples/claude-code-review.yml):
  an `issue_comment` trigger plus a `dispatch-on-comment` job gated on
  OWNER/MEMBER/COLLABORATOR that re-enters the existing `workflow_dispatch`
  path.
  A slash command rather than a mention, on purpose -- any `@claude` would wake
  the workflow you just disabled.
- **Turning off the `pull_request` review trigger can block every PR in the
  repo.**
  If `review / require-review` (or `review / claude-review`) is a **required
  status check** in branch protection, it stops reporting entirely and PRs sit
  waiting for a status that never arrives.
  Nothing in the diff reveals this -- branch protection is not in the repo -- so
  state it as a merge precondition for a human to confirm rather than assuming
  either way.
- **A `/review` dispatch should pass `--ref <pr-head-branch>`.**
  Without it `workflow_dispatch` falls back to the default branch and the review
  check-run lands on the wrong commit.
  Fork PRs are the exception: their head branch does not exist in the base repo,
  so `--ref` cannot resolve and the dispatch has to fall back to no `--ref`.
  Older copies of the `dispatch-on-comment` job in consumer repos predate this
  and still need it backported -- it matters most once `/review` is the *only*
  path that ever produces a review check-run.
- (2026-07-31, `UCD-SERG/serodynamics#282` + `UCD-SERG/serocalculator#627`:
  agent disabled in both.
  serodynamics needed the `/review` path built, having relied entirely on the
  mention; serocalculator already had it and needed the
  `pull_request` trigger removed plus the `--ref` backport.)

## GitHub Actions — gathering prior review context in reusable workflows

When a reusable workflow needs to fetch prior `claude[bot]` review comments for
deduplication, two API endpoints carry different content:

- **`/repos/{owner}/{repo}/issues/{n}/comments`** — top-level PR comments
  (summary/tracking verdicts). Filter to review comments with
  `select(.user.login == "claude[bot]" and (.body | test("### Code Review")))`.
  This pattern discriminates review summaries from `@claude` task-handler responses
  (which also post as `claude[bot]` but use "Claude finished…" / "Claude Code is
  working…" headers, not the "### Code Review" heading the review workflow uses).
  The ai-config `claude-review.yml` (#275) omits this content filter — it was
  accepted, but task-handler responses can appear in the `prior-reviews` context.
- **`/repos/{owner}/{repo}/pulls/{n}/comments`** — inline review findings posted
  via the review API. These are already `claude[bot]`-only (the `@claude` task
  handler posts to `/issues/`, not `/pulls/`), so no content filter is needed.
  Fetch the most recent ~30, map to `"=== Inline finding on {path}:{line} ===\n{body}"`.

Combine both (inline first, summary last) and cap at ~12000 chars with `head -c`.
Require `pull-requests: read` permission in the job that fetches inline comments.

**`GITHUB_OUTPUT` multiline heredoc — always use a random delimiter.**
A static delimiter like `__EOF__` collides with content in prior review comments
(e.g. a review suggestion showing a shell heredoc). Use:
```bash
DELIMITER="eof_$(openssl rand -hex 8)"
{
  echo "my-output<<${DELIMITER}"
  printf '%s\n' "$VALUE"
  echo "${DELIMITER}"
} >> "$GITHUB_OUTPUT"
```
The ai-config `claude-review.yml` (merged in #275) uses a static
`__REVIEWS_EOF__` delimiter instead — accepted by design but is a known
divergence from this best practice.

**`needs.X.result != 'cancelled'` vs `== 'success'`** — when the dependency job
is non-critical (acceptable to proceed without its output), use
`!= 'cancelled'` in the dependent job's `if:` so genuine failures fall through
rather than blocking. When the dependency is truly required, use `== 'success'`
(not `!= 'failure'` — that still runs when the dep was cancelled, which usually
means its output was never produced). (gha#133: `gather-context` failure should
not block `claude-review`.)

## claude-code-action: tag mode vs agent mode and git write tools

- **Tag mode (`track_progress: true`) hardcodes git write tools into `ALLOWED_TOOLS`
  regardless of `--disallowedTools`.** The action's TypeScript sets the `ALLOWED_TOOLS`
  env var at runtime, injecting `Bash(git add:*)`, `Bash(git commit:*)`,
  `Bash(git rm:*)`, and `git-push.sh`. The `--disallowedTools` CLI flag cannot
  override an env var set by the same process.
  Evidence: `Morrison-Lab/gha` PR #134,
  where a supposedly read-only `claude-code-review` run pushed commit `02af72b` to
  UCD-SERG/serodynamics PR #175. Upstream fix tracked in
  `anthropics/claude-code-action#1415` (draft PR #1433).
- **Agent mode (`track_progress: false`) builds `ALLOWED_TOOLS` solely from
  `claude_args` — no git write tools are injected.** This is the safe default for
  a read-only reviewer. Trade-off: no live tracking comment, no inline-comment tool
  (the inline-comment tool is only initialized in tag mode per `claude-code-action#635`);
  reviews post as top-level PR comments instead.
- **`inputs.dot-notation` vs `inputs['bracket-notation']` in GitHub Actions `if:`.**
  Both work, but use dot notation (`inputs.track-progress`) for consistency — bracket
  notation looks non-idiomatic next to the dot notation used everywhere else in the
  same workflow. Caught in gha#134 review.
- **A `claude-code-review`-style job that fails with "no verdict written" but `is_error: false` and real cost/turns can be root-caused by downloading the uploaded execution-transcript artifact, not just reading the summary `result` object.**
  The `Run Claude Code Review` step's own JSON output only shows the final SDK
  summary (`is_error`, `num_turns`, `total_cost_usd`, `permission_denials_count`)
  — enough to confirm a stub occurred, not why.
  The workflow separately uploads the full turn-by-turn transcript as a
  `claude-review-execution-<run-id>-<run-attempt>-<attempt-label>` artifact
  (no `.zip` suffix — that's not part of the artifact's own `name`, and
  `gh run download -n <name>` auto-unzips; the name is defined by
  `Morrison-Lab/gha`'s reusable workflow, not a Claude Code convention — a
  future rename there invalidates this pattern, so confirm via
  `gh api repos/<owner>/<repo>/actions/runs/<run_id>/artifacts` rather than
  assuming it).
  `<run-attempt>` is `github.run_attempt` — the *workflow rerun* count,
  almost always `1` — while `<attempt-label>` (`attempt1`/`attempt2`) is the
  *review's own* stub-retry count.
  The two are easy to conflate: targeting a specific review attempt means
  changing `attempt-label`, not `run-attempt` --- for example,
  `attempt2` of a review that never got manually rerun is still
  `claude-review-execution-<run-id>-1-attempt2`, not `...-2-attempt2`.
  Fetch it with
  `gh run download <run-id> --repo <owner>/<repo> -n <name> -D <dir>`,
  rather than a manual `curl`.
  It's a single pretty-printed JSON array of
  Claude Code SDK message objects, not NDJSON — each element has a top-level
  `type` (`"system"`/`"assistant"`/`"user"`/`"result"`) and, for `"assistant"`
  elements, a `message.content` array of blocks (`{"type":"tool_use", "name":
  ..., ...}`, `{"type":"text", "text": ...}`, etc.) — parse with
  `jq '.[] | select(.type=="assistant") | .message.content[]? | select(.type=="tool_use") | .name'`
  for a tool-use histogram, or pull `is_error==true` tool_results for the actual
  denial messages. This is how a "stub review" traced back to the model
  fanning its own review out across background `Agent` calls and ending its turn
  on "waiting for background agents" — a mechanism the summary object alone
  can't show (`Morrison-Lab/gha#185`, `Lacaedemon/sparta` PR #615, 2026-07-03).
  A second, usually simpler route to the same detail is a re-run with the
  reusable workflow's `show-full-output` input turned on, which surfaces
  denied tool calls directly in the job log — see
  [`claude-review-dispatch.md`](claude-review-dispatch.md)'s
  "Diagnosing which tool call was denied" note.
  Reach for the artifact download instead when a re-run isn't an option
  (the failure needs diagnosing from the run that already happened,
  not a fresh one), or when `show-full-output` itself is unavailable.
  A specific mechanism found this way: `permission_denials_count: 33`,
  no verdict, on a `claude-review` run reviewing a large PR diff
  (21 files, 700+ lines) in `ucdavis/win#78`.
  The artifact showed the reviewer looping roughly 15 times trying to save
  the diff to a file so it could be grepped/counted in chunks — every
  attempt denied, either because chaining an allowlisted `gh pr diff`
  command with `;`/`&&`/a redirect makes the whole compound command require
  approval even though the allowed part matches exactly, or because writing
  anywhere outside a very narrow "allowed working directory" is a hard
  block rather than a promptable permission — including `/tmp` and even a
  freshly `mkdir`-created subdirectory of the repo checkout being reviewed.
  Filed with the full transcript as `Morrison-Lab/gha#541`
  (2026-08-20).
  A related case, `Morrison-Lab/gha#370`, hit a comparably high
  `permission_denials_count: 32` on a different repo but couldn't confirm
  the mechanism because that session's egress proxy blocked the artifact
  download from `productionresultssa5.blob.core.windows.net` — worth
  retrying from a session without that restriction before assuming the
  artifact is unreachable.
- **`permission_denials_count` is per-attempt (per job), not per-PR.**
  See [`self-review-fallback.md`](../shared/workflow/self-review-fallback.md)'s
  "High-denial stub (gha#198)" for the full treatment, measured examples,
  and the do/don't bullets.
  The one addition: when citing a count, name the job id, not just the PR,
  because different attempts on the same PR can carry materially different
  counts. (2026-08-20.)
- **A `claude-code-review` false-positive "stub" is also possible on a review that actually completed and posted a real, correctly-formatted verdict — distinct from the gha#185 background-agent-fanout pattern above.**
  `check-review-execution.sh`'s stub-detector scans only `type=="text"` content blocks for a line matching `^[[:space:]>*_#-]*verdict\b` (grep, anchored to line-start) — it does not look inside `tool_use` block arguments.
  If the agent's final free-text message merely *narrates* what it posted ("Posted the inline finding and a summary comment ending in `### Verdict: Ready for merge`.") rather than repeating the verdict as its own standalone line, the word "verdict" only appears mid-sentence, so the anchored regex correctly does *not* match it — even though the actual GitHub comment (posted via a tool call earlier in the same transcript) has a perfectly-formed `### Verdict` heading.
  This false stub classification then triggers an unnecessary retry, and if THAT retry genuinely stubs (e.g. the gha#185 pattern), the overall check reports `failure` on a PR that already had a valid, complete review.
  Diagnose by downloading both attempts' execution-transcript artifacts (see the note above) and checking attempt 1's own posted PR comment directly, not just its final "result" text.
  Filed with full evidence as `Morrison-Lab/gha#218` (`Lacaedemon/sparta` PR #615, 2026-07-03) rather than reopening #185, since the mechanism (a scanning gap, not a fanout-and-never-resume) is distinct.
- **Both bullets above presuppose `@v2`: at `@v1` the execution artifact is
  never produced at all, so its absence is not an access problem.**
  `claude-code-review.yml@v1` has no `Resolve and upload execution file path`
  step, while `@v2` has two of them (one per attempt), so a run pinned at
  `@v1` uploads nothing and every route to the artifact fails identically ---
  which reads as a credentials or proxy problem and is not.
  Confirm the producing step ran before diagnosing the fetch; see
  [`debugging.md`](debugging.md)'s "An artifact you cannot retrieve may never
  have been produced" for the general form and the one-call check. (2026-07-31.)
- **`is_error` is the field that says whether the run failed.
  `subtype` is not, and the two can look contradictory in the same object.**
  A stub review reports `is_error: false` alongside real turns and cost: it
  ran, and never stated a verdict.
  A genuine failure reports `is_error: true`, and can carry
  `subtype: "success"` beside it.
  That is not a contradiction --- `subtype` describes how the SDK turn
  terminated, not whether the job did its job.
  So read `is_error` for the verdict and treat `subtype` as narration.
  (2026-07-31.)
- **The *agent* workflow reports an API-level error by posting it as a plain
  PR comment, and its job still concludes `success`.**
  When `claude.yml`'s `Run Claude Code` step ends without committing anything,
  the later `Post Claude's response if no code was committed` step publishes
  whatever the run produced --- including a bare API error such as
  `Prompt is too long`, under a footer naming the step and linking the run.
  Every step conclusion stays `success` or `skipped`, so the run is green and
  no check, artifact, or log records a failure anywhere.
  Read the thread rather than the run when an agent invocation appears to have
  done nothing; see [`debugging.md`](debugging.md)'s
  "Read the failure's own output" for the general form.
  (`Morrison-Lab/ai-config#986`, run 30664135897, 2026-07-31.)
- **`gh pr checks <N>` can return a momentarily-stale check entry right after a
  state-changing trigger (close/reopen, a push, `gh run rerun`).** Querying
  immediately after triggering can show the check that was current a few
  seconds ago — including a red/failed one from a run that already finished
  hours earlier — rather than the freshly-queued run. Don't trust a `gh pr
  checks` read taken within seconds of triggering; instead look up the actual
  newest run for the branch and watch that specific run id:
  `gh run list --workflow "<name>" --json databaseId,createdAt,headBranch --jq
  'map(select(.headBranch=="<branch>")) | sort_by(.createdAt) | last | .databaseId'`,
  then poll `gh run view <id> --json status,conclusion` directly. A poll loop
  built on `gh pr checks`'s live state must also treat every non-`"completed"`
  status (`queued`, `in_progress`, and any value not explicitly enumerated) as
  still-running rather than allow-listing only `PENDING`/`IN_PROGRESS` —
  `QUEUED` slipping through an allow-list caused a premature "settled" false
  positive in one session (`Lacaedemon/sparta`, 2026-07-03).
- **A check's wall-clock duration is not its runtime — compare `started_at`
  against the first line of its own log before diagnosing a "hung" job.** A
  check run's `started_at` is set when the check is **queued**, before a runner
  picks it up -- distinct from `created_at`, which the Check Runs API reports
  separately -- so a starved runner makes an ordinary job look stuck for an
  hour. In ucdavis/bcs#453 a
  `Spellcheck` job showed `started_at` 19:29 with no completion by 20:05,
  against a 3-minute norm; its log's first timestamp was 20:33, and it then ran
  in 3m14s and failed on a real finding. The duration was queue starvation and
  the failure was unrelated — so "this has been running for 36 minutes" is a
  reason to read the log's own timestamps, not a diagnosis (2026-07-28).

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

## `CLAUDE_CODE_OAUTH_TOKEN` carries no recoverable account identity

Which Claude account minted a repo's `CLAUDE_CODE_OAUTH_TOKEN` is not
recorded anywhere, and cannot be recovered after provisioning.
Worth knowing before spending a session trying, because several surfaces
look like they should answer it and none does.

- **The secrets API returns metadata only.**
  `GET /repos/{owner}/{repo}/actions/secrets` gives `name`, `created_at`, and
  `updated_at`.
  Values are write-only by design.
- **The run logs mask it.**
  `claude-code-action` prints `CLAUDE_CODE_OAUTH_TOKEN: ***` and
  `"claude_code_oauth_token": "***"`, and the neighbouring
  `anthropic_organization_id` / `anthropic_service_account_id` fields are
  empty strings on a subscription token.
  Nothing in the log names an account, an email, or an org.
- **`total_cost_usd` is not an identity signal.**
  It reports a real figure on a subscription token
  (`4.352437800000001` on one ai-config review run), so it distinguishes a
  run that did work from one that died early -- not one account from another.

Two consequences.
Behavioural inference is the only route, and it is weak: a repo whose review
job completed real work has a token with quota, which says nothing about
whose.
Do not build an account attribution on "this succeeded after the other
account ran out"; that premise is usually itself unverified, and the local
usage chart (`/status` -> Stats) can refute it outright.

The provisioning path explains why the estate ends up mixed.
`/install-github-app` mints from **whichever account the local CLI is logged
into at that moment**, with no account picker and no confirmation naming it,
and `claude setup-token` behaves the same way.
So a repo-by-repo rollout across several sittings records nothing about which
account each sitting used.

`scripts/rotate-claude-token.py` (ai-config#952) is the remedy rather than the
diagnosis: set every repo from one known account so the question stops
mattering.

(2026-07-30: a sweep of 324 admin repos found 35 carrying the secret and zero
org-level Claude secrets, provisioned in three batches between 2026-05-09 and
2026-07-14.
Attribution proved unrecoverable by any of the three surfaces above.)

## `pull_request_target` is rejected by the App-token exchange

Anthropic's `github-app-token-exchange` endpoint rejects OIDC tokens minted for
`pull_request_target` events, with
`App token exchange failed: 401 Unauthorized - Invalid OIDC token`.
The job dies in about 25 seconds, before the model is reached.

The trap is that the action's **own** side supports the event.
claude-code-action#347, "Can't use action in workflow triggered by
`pull_request_target`", is closed as completed, and `docs/security.md` carries a
section on using the action with that trigger --- so the workflow reads as both
correct and documented.
Only the server side refuses it.
(Issue #713's body credits the support to "PR #759".
That number is an unrelated open bug report in the same repo, so cite #347
instead of repeating it.)
Tracked as
[anthropics/claude-code-action#713](https://github.com/anthropics/claude-code-action/issues/713),
open since 2025-12-02, whose stated workaround is to use `pull_request`.

So `pull_request_target` is not an available fix for fork PRs, whatever else
recommends it.
Nor would it be sufficient if the exchange worked: the action still refuses to run
for a contributor without write access unless `allowed_non_write_users` is set,
which `docs/security.md` documents as a significant security risk.
Read a proposal to switch a review workflow to this trigger as a regression, and
leave a comment in the workflow naming the upstream issue so it does not get
re-applied.

Three messages arrive at that same exchange step, and only the first two are
401s.
The message is what separates them:

- `Invalid OIDC token` --- the trigger event, this entry.
- `User does not have write access on this repository` --- the triggering actor is
  not a collaborator, e.g. the Copilot coding agent
  (`UCD-SERG/ucd-serg.github.io#84`).
- `Workflow validation failed ... identical content to the version on the
  repository's default branch` --- usually the self-mod skip when the action exits
  0, but it can also be a red stale-branch block.
  The green form means a PR edited the review workflow and the action deliberately
  skipped itself.
  The red form can appear on a PR that edits no workflows at all, when the branch
  is behind a `main` commit that changed `.github/workflows/`.
  **Do:** compare `.github/workflows/` against `origin/main` and merge `main`
  before rerunning when this message appears on a non-workflow PR.
  **Don't:** treat the message's "new repository" / "workflow changes" text as
  exhaustive, or spend `rerun_failed_jobs` before bringing the branch current.
  See the self-mod skip section in [`claude-review-dispatch.md`](claude-review-dispatch.md)
  for gha's own guard against the green form,
  and `review-verdict-pitfalls.md` for the stale-branch red form.

(Morrison-Lab/ai-config#981, 2026-07-31/2026-08-01: a non-workflow PR
was 30 commits behind `main` after #998 changed `claude-review.yml`.
Its `claude-review` attempt 2 failed in 16 seconds with this validation text and
`Error is not retryable, giving up immediately`; merging `origin/main` was the
whole fix.
Morrison-Lab/ai-config#994's earlier 5m26s stub looked similar in the queue, but
it ran before #998 merged and was a different bug.)

This is a fourth distinct cause in the short-duration band that
[`review-verdict-pitfalls`](../shared/workflow/review-verdict-pitfalls.md) already
records three for, under "That duration signature does not run backwards".
Three of the four run 25 seconds or less, and none of them is about credentials,
which is that section's point: a short run corroborates a credential hypothesis
you already hold on other grounds, and never produces one.

Three of the four are on `UCD-SERG/ucd-serg.github.io` and one is on
`Morrison-Lab/qwt`, so the band is the thing they share rather than the repo.
Saying otherwise would be the grouping-by-symptom overreach that same section
warns about, in the entry invoking its authority.

(`UCD-SERG/ucd-serg.github.io`, 2026-07-31: PR #83 switched the review workflow to
`pull_request_target`, and all five subsequent runs failed this way while the two
`pull_request` runs immediately before it succeeded.
Reverted in #89, tracked as #88.
The revert PR's own two runs are the cleanest demonstration available, because the
trigger is the only variable between them.
Run 30680266779 (`pull_request_target`) was rejected at the token with
`401 Invalid OIDC token`.
Run 30680266785 (`pull_request`) had its token *accepted* and got as far as
workflow validation, where it skipped and exited 0 --- so its check reads
`success` while the action never reviewed anything.
Same repo, same secret, 15 seconds apart.

That second run is also a worked example of the self-mod skip section, now in
[`claude-review-dispatch.md`](claude-review-dispatch.md), and of how it
misleads a careful reader.
Round 2 of this PR's own review read that `success` conclusion and reported the
sentence describing it as a fabricated claim, on the reasoning that a run which
succeeded cannot have stopped early.
It can, and this one did: the log carries
`Skipping action due to workflow validation` and `Exiting due to workflow
validation skip`.
Read the log rather than the conclusion, on any job whose action can exit 0
without doing its work.)

A further failure state, and the only one that leaves no message at that step at
all: the run reaches the model, produces a review, and is **denied when it tries to
post it**.

`pull-requests: read` in the workflow's `permissions:` block is enough to cause
this.
The action's app token covers its own bookkeeping, but the review is posted by
Claude's tool calls running under `GITHUB_TOKEN`, so a read-only token loses the
review after paying for it.
The tell sits in the execution output rather than in any error:
`"permission_denials_count": 8` alongside `is_error: false`.

That makes **two** green-but-no-review states on this workflow: denied at posting,
and skipped at workflow validation.
The two 401s above are red, so they announce themselves; these two do not, which is
what makes them worth enumerating separately from the messages.
Only the log tells them apart.

But the question that settles both at once is not about any mechanism.
**Ask whether a `claude`-authored comment exists on the PR**, which is one query,
rather than reasoning about which token ought to be able to post.

- **Do:** grant `pull-requests: write` to a review workflow on the `pull_request`
  trigger.
  GitHub forces a read-only `GITHUB_TOKEN` on fork PRs regardless, so this widens
  nothing for untrusted contributors.
- **Don't:** infer from a green check, or from an argument about token scopes, that
  a review was posted.

(`UCD-SERG/ucd-serg.github.io`, 2026-08-01: `pull-requests: read` had been in that
workflow since its first commit, and `claude` had **never** posted a review comment
on the repository --- PRs #78, #79, #80, and #86 all ran green with zero.
It surfaced only because #89 restored `read` while asserting it was safe on the
grounds that "the action posts with its own app token".
Two Copilot reviews on that PR restated the premise without objection.
Fixed in #91.
A single query for a `claude` comment on any earlier PR would have caught it at any
point in the preceding month.)

## `claude-code-action`'s `Task`/`Agent` tool is not gated behind `--allowedTools`

Split out of [`github.md`](github.md) (ai-config#2267 / #694 pattern).

`claude --allowedTools` is documented as "Comma or space-separated list
of tool names to allow" -- read naturally, that implies anything not
listed gets denied in unattended CI, where nobody can approve a
permission prompt.
**Verified false for `Task`**: `claude -p "..." --allowedTools
"Bash(echo hi:*)"` (deliberately excluding `Task`) let a real `Task`
subagent call through with `permission_denials: []`, identical to
running with `Task` explicitly listed.
Confirmed on the raw CLI directly, not inferred from
`claude-code-action`'s own wrapping behavior.

So a `claude-code-action` review job that stubs -- real turns and cost
logged, `is_error: false`, but no verdict ever posted -- is **not**
explained by "the plugin's `Task` calls were denied" just because `Task`
is absent from the job's `claude_args --allowedTools`.
Look for a different denied tool instead.
`Morrison-Lab/gha`'s `run-claude-review-attempt` composite action
documents the actual repeat offender at length: the
`code-review@claude-code-plugins` command's own declared `allowed-tools`
frontmatter names `Bash(gh pr list:*)`, `Bash(gh issue view:*)`,
`Bash(gh issue list:*)`, and `Bash(gh search:*)` alongside
`view`/`diff`/`comment` -- omit any of those and the plugin's 4 parallel
sub-agents rack up denials across their fan-out.

(Morrison-Lab/wai#49/#50, 2026-08-08: diagnosed a stub review as a
missing `Task` grant, patched it, then verified empirically that the
patch was a no-op.
The real fix was migrating to gha's canonical reusable workflow, which
grants the plugin's actual declared tool list and -- more robustly --
denies `gh pr comment` to the agent entirely, having the workflow post
the review from the agent's final message instead.
See [`dont-reinvent-wheel.md`](../shared/principles/dont-reinvent-wheel.md)'s
"A stale, un-migrated local copy is the least reliable place to fix a
bug" for the broader lesson.)
