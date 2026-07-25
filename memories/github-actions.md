# GitHub Actions & the @claude bot workflows

## Re-triggering the @claude PR *review* (d-morrison Quarto / R-pkg repos, e.g. `psw`)
- Filenames below are those in the **content/package repos** (verified in
  `d-morrison/psw`): the review workflow is `.github/workflows/claude-code-review.yml`
  and the comment-triggered agent workflow is `.github/workflows/claude.yml`.
  (ai-config's *own* bot uses different names — `claude-review.yml` /
  `claude-bot.yml` — so don't infer these from *this* repo's `.github/workflows/`.)
- **`d-morrison/gha` itself (the shared workflow repo) is different:** the
  reusable workflow is `claude-code-review.yml` (no `workflow_dispatch`), and the
  dogfooding caller stub with `workflow_dispatch` is `claude-review.yml`. So to
  dispatch a review in `gha`:
  `gh workflow run claude-review.yml -f pr_number=<N>` (not `claude-code-review.yml`).
- The review workflow (which calls `d-morrison/gha`'s reusable review workflow)
  is **not** comment-triggered. It runs on `pull_request` (`types: [opened,
  synchronize, ready_for_review, reopened]`) and on `workflow_dispatch` (input
  `pr_number`). Posting an `@claude review` *comment* drives the separate agent
  workflow `claude.yml` (which then re-dispatches a review after it pushes) — it
  does not directly fire the review workflow.
- A new push (`synchronize`) auto-fires a fresh review — the normal path during
  an iterate loop.
- To force a fresh review on an existing PR **without a new commit**:
  - **workflow_dispatch** (preferred — no extra PR timeline noise). Same
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
    review. Works reliably, but clutters the timeline with close/reopen events;
    prefer workflow_dispatch unless dispatch isn't available.
- **A successful `workflow_dispatch` review does not clear the PR's required
  `pull_request`-triggered check.** The dispatched run's check-runs attach to
  the **dispatch ref's SHA** (typically `main`, the default branch used to
  invoke it), not the PR's actual head SHA — even though the run reviews and
  comments on the right PR (it takes `pr_number` as an input and reads that
  PR's diff). So after a stub/failed `pull_request`-triggered review (see
  `mcp__github__actions_run_trigger` 403 below), posting `@claude review` or
  `/review` gets you a fresh, real verdict in the PR thread, but
  `review / claude-review` and any gate job on the PR's head SHA (checked via
  `get_check_runs`, not `get_status` — see below) stay red. Since reruns 403 in
  these sessions, the only way to get a fresh **gating** run is to push a new
  commit (an empty `git commit --allow-empty` is fine) so a real `pull_request`
  `synchronize` event fires against the actual head SHA. (Hit twice in one
  session on gha#176: two consecutive genuine — not raced — stub reviews on the
  pinned dogfooding checker, each requiring an empty retrigger commit after the
  dispatched `/review` came back clean.)
  - **The empty retrigger commit must be pushed by a HUMAN actor — a
    bot-pushed one is silently skipped.** `claude-code-review.yml` (and the
    review-triggering workflows generally) gate on a bot-actor `if:` filter
    (e.g. `github.actor != 'github-actions[bot]'` / not a `[bot]` login), so a
    `synchronize` event fired by a bot-authored push — e.g. the `@claude`
    agent itself doing `git commit --allow-empty` on the PR — is *filtered
    out* and never starts the gating `claude-review` run. The check stays red
    with no new run at all (not even a stub), which reads like nothing
    happened. Push the empty commit from a human actor (your own session's
    push) to get the gating run to fire. So when you ask the `@claude` agent
    to "retrigger the review," it can't self-serve this: its own empty commit
    is skipped, and it separately 403s on `rerun_failed_jobs` (below) — a
    human-actor push is the only lever left. (serocalculator#564, 2026-07-20:
    the agent's bot-pushed empty commit didn't fire the review; a
    human-actor empty commit did.)
  - **Root-caused and fixed at the source in gha#286 (issue gha#285):** the
    misattribution isn't inherent to `workflow_dispatch` -- it's that `gh
    workflow run <file> -f pr_number=<N>` with no `--ref` implicitly
    dispatches against the repo's default branch. `claude.yml`'s and
    `claude-review.yml`'s own dispatch calls now pass `--ref <PR-branch>`
    explicitly, so a re-dispatched review's check-runs attach to the PR's
    actual head commit and DO supersede a stale/cancelled `pull_request`-
    triggered run. Once a repo's `@v2` pin picks this fix up (check
    `slide-major-tag` has run since gha#286 merged), the empty-retrigger-
    commit workaround above should no longer be necessary for a plain
    `@claude review`/`/review` dispatch -- verify the fix landed before
    reaching for the workaround on a repo that might already have it.
- **A distinct stub-review signature: `is_error: false`, real `num_turns`/cost,
  but `permission_denials_count: 1` and no `Verdict` line.** (`permission_denials_count`
  is a field in the Claude Code SDK's runtime execution-output JSON, not
  anything in this repo's own files — if a future SDK version renames it,
  look for an equivalent counter in that JSON rather than assuming the
  signature vanished.) Not the
  quota-exhaustion case (`total_cost_usd==0 && num_turns==1`) and not a raced
  cancellation (`conclusion: cancelled`) — the SDK call itself ran several
  turns and cost real money, but a denied tool call mid-run derailed it before
  it wrote a verdict. Reproduced 3× identically on the same PR/diff (gha#180)
  across both push-triggered and dispatched reruns — not random flakiness once
  it starts recurring on a given diff. **Root-caused and fixed in gha#185/#187:**
  agent mode's default `allowedTools` has no `WebFetch`/`WebSearch`, but the
  review prompt's own fact-checking instructions can still lead the agent to
  attempt one, and on denial it sometimes stopped instead of finishing. The
  fix is prompt-only — tell the reviewer up front that network-fetch tools
  aren't available (so it doesn't try) and that a denied tool call is never a
  reason to stop early — rather than widening `allowedTools`, since granting
  broad `WebFetch` to a review-only job with secrets access raises its own
  prompt-injection/exfiltration question for a workflow shared across
  potentially-private consumer repos. That tradeoff (a domain-scoped
  `WebFetch(domain:...)` allowlist to let the reviewer live-fact-check
  external sources, matching `gha`'s own `CLAUDE.md` "Fact-check prose
  against domain knowledge and external sources" review guideline) is left
  as an open decision in gha#189, not decided unilaterally.
  - **The stub can recur across *unrelated* PRs in the same session/window,
    not just repeatedly on one diff — treat a cluster as a
    session/service-level condition, not N independent diff bugs.** When two
    different PRs in different repos both stub within the same span
    (serocalculator#564 and gha#276, 2026-07-20, both stubbed in the same
    session), don't burn a re-trigger round on each hoping the *diff* is at
    fault: post the self-review (per `CLAUDE.md`'s "Do the review yourself
    when the @claude workflow doesn't produce a verdict"), hand the required
    `require-review` check to the human, and stop re-triggering after one
    round. Both the app token and the `@claude` agent 403 on
    `rerun_failed_jobs` (below), so neither you nor the agent can force a
    fresh gating run without a human-actor push — which the human is doing
    anyway when they decide to merge past the stubbed check.
- **Diagnosing which tool call was denied requires the reusable workflow's
  `show-full-output` input turned on for a re-run — the job log alone won't
  show it.** Same underlying hidden-output behavior as the
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
  does not match `example.evil.com`). Confirmed against the official docs:
  <https://code.claude.com/docs/en/permissions> (WebFetch section). Same
  bracketed-scope pattern as `Bash(git commit:*)`. Useful for granting
  narrow, exfiltration-bounded fetch access instead of unrestricted
  `WebFetch` or none at all.

## YAML authoring (GitHub Actions / workflow files)
- **Regex values with backslashes: prefer single-quoted YAML, but document both forms
  correctly.** YAML double-quoted scalars process escapes, so you must double each
  backslash there (e.g. `"foo\\.bar"` for a single literal backslash before `.`).
  Single-quoted scalars preserve backslashes as-is (e.g. `'foo\.bar'` for that same
  single backslash), which is usually easier to reason about in workflow templates.
  This applies to `branches-or-tags-to-list` / regex inputs in reusable-workflow YAML.
  (d-morrison/altdoc#30.)

## @claude CI action (d-morrison/gha `claude.yml`)
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
  d-morrison/gha#39.
- If a repo pins an **older** gha tag (pre-fix), the workaround still applies. The
  symptom was `claude[bot]` "auto-commit residual @claude session changes" commits
  that reverted only config paths. Restore the section
  (`git checkout <my-commit> -- CLAUDE.md`, commit), then before merging verify with
  `git diff origin/main -- CLAUDE.md` being **non-empty** (an empty diff means the
  payload was silently reverted to main), and merge promptly.
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
  not a real parallel-session conflict. (Hit on d-morrison/gha#225: the self-review
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
    Observed 2026-06 on sparta#207 (consuming `d-morrison/gha@v1`) AND in `dem-extra1/gha`'s
    own `claude-code-review.yml`: the guard still `exit 1`d on `is_error=true` (RED check, no
    `[!WARNING]` comment) — gha#102's exit-0 behavior was not yet on the consumed `@v1` pin
    there. Read the actual guard code on the pin you consume rather than trusting this note.
    Note OAuth/subscription auth (`CLAUDE_CODE_OAUTH_TOKEN`) shows `total_cost_usd=0`
    regardless, because it isn't metered per-call — so cost=0 + 1 turn + immediate `is_error`
    points to a **subscription usage-limit**, not only API credits; confirm via the Anthropic
    Console usage for that account.
  - **Intermittent upstream bug** (`total_cost_usd > 0`, `duration_ms` ~192 s): the
    `claude-code-action` completes a real review but exits with `is_error=true` anyway.
    The guard step fails the check ❌. The prior clean review on the same diff is still
    valid. Fix: push a trivial commit to trigger a fresh review. Observed on gha#92 run
    #28034977099.
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
  `d-morrison/gha@v1` may not carry it yet, so check the tag. You CANNOT side-channel the
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
  every consumer calls `uses: d-morrison/gha/.github/workflows/claude-code-review.yml@v1`;
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

## d-morrison/gha reusable workflows
Check `d-morrison/gha` before writing bespoke CI — it has reusable workflows for
common patterns.

- **`quarto-publish.yml`** — sets up Quarto, renders, and deploys the site.
  Caller stub is ~12 lines. See `examples/quarto-publish.yml` in the gha repo.
  **`@v1` vs `@v2` differ in HOW they deploy, and the two are mutually exclusive
  at the repo-Pages-source level:**
  - **`@v1`** deploys via the Pages **artifact** (`actions/upload-pages-artifact`
    + `actions/deploy-pages`). Repo setup: Settings → Pages → Source = **"GitHub
    Actions"**. No `gh-pages` branch served.
  - **`@v2`** (gha#118) deploys to the **`gh-pages` branch** (`JamesIves/github-pages-deploy-action`,
    `clean-exclude: pr-preview/`, plus a `.nojekyll`). Repo setup: Settings → Pages
    → Source = **"Deploy from a branch", `gh-pages` / `(root)`**. Caller grants
    `contents: write` (not `pages:write` + `id-token:write`), **even with
    `deploy: false`** (see the reusable-workflow permission rule below).
  - **WHY the switch:** the gha PR-preview family (`preview-deploy`,
    `cleanup-pr-previews`) pushes previews to the `gh-pages` branch. A repo serves
    Pages from **one** source, so Actions-artifact publish + branch-based previews
    can't coexist — under Actions-source Pages, every `…/pr-preview/pr-N/` link
    404s. `rossjrw/pr-preview-action` REQUIRES branch-based Pages. So a repo that
    wants both a main site AND PR previews must use `@v2` + branch Pages.
  - **Branch-served Quarto needs `.nojekyll`** at the gh-pages root, or Jekyll
    strips Quarto's `_`-prefixed asset dirs. `quarto publish gh-pages` adds it
    automatically; `JamesIves` does not, so `@v2` touches one in before deploy.
  - **The repo's Pages *source* is a manual setting** — not changeable via the
    MCP tools or (in scoped sessions) the API. Hand the flip to the user, and
    order it safely: deploy to `gh-pages` FIRST (populates root; live site keeps
    serving the old artifact), THEN flip the source, or the root 404s in between.
- **`lint-changed-lines.yml@v2`** (gha#276) — runs `lintr` on changed R files but
  filters the reported lints down to only the lines a PR **adds or modifies**,
  so a repo can adopt or tighten a lint rule *incrementally*: new and edited
  code must comply while untouched legacy code is left alone. This is the
  answer to "a linter version bump (e.g. lintr 3.4.0's `indentation_linter`
  now matching the current tidyverse single-indent style) flags the whole
  repo" — don't disable the linter or reformat everything at once; adopt via
  this workflow and let the rule migrate file-by-file as code is touched.
  Caller stub is ~8 lines (`uses: d-morrison/gha/.github/workflows/lint-changed-lines.yml@v2`).
  Implementation detail worth knowing when debugging false negatives: the
  reusable workflow checks out `github.event.pull_request.head.sha` (NOT the
  default `refs/pull/N/merge` ref) so on-disk line numbers match the
  head-relative line numbers in the GitHub "list PR files" `patch` field.
  serocalculator#564 is the first consumer.
- **Convention:** ai-config (and d-morrison repos generally) call `d-morrison/gha`
  reusable workflows with `@v1` (not a SHA-pinned ref). SHA-pinning is the pattern
  for third-party actions only.
- **gha's major tag slides ONLY on a manual `workflow_dispatch`, NOT on every
  merge to main** (`slide-major-tag.yml`; `on: workflow_dispatch:` only, gated
  `if: github.ref == 'refs/heads/main'`). It re-points the major derived from
  the latest `vX.Y.Z` tag to HEAD when dispatched. So merging a fix or a new
  capability to `main` does **not** roll it out to `@v1`/`@v2` consumers on its
  own — the tag stays put until someone runs the workflow. This is deliberate
  (the workflow's own header comment: "the slide is a deliberate manual step,
  not an automatic reaction to every push" — merge, optionally canary a
  consumer at `@main`, then dispatch once confident). Practical consequence:
  after merging a PR that adds/fixes a capability, a consumer PR that calls it
  at `@v2` keeps running the **pre-merge** tagged version until the human
  dispatches the slide — the same "can't self-verify before merge" bootstrapping
  gap gha's own `CLAUDE.md` describes, but persisting *after* merge too until
  the dispatch. (serocalculator#564 called gha's new `lint-changed-lines.yml@v2`
  right after gha#276 merged; it only picked up the real capability once the
  user manually dispatched `slide-major-tag`.)
  Because the slide is manual, a **breaking** change merging to main does NOT
  silently slide `v1` onto it — but when you DO dispatch after a breaking
  change, guard it with TWO tag moves so the slide doesn't break `v1`:
  (1) force `v1` back to the last non-breaking commit
  (`git tag -f v1 <sha>; git push --force origin refs/tags/v1`), and
  (2) create `v2.0.0` + `v2` at HEAD. Once `v2.0.0` exists it's the latest
  semver, so the slide moves `v2` thereafter and `v1` stays frozen. There is NO
  MCP tool to create tags/releases — use `git` (but see the 403 caveat below).
  Notify registered consumers in `REVDEPS.md` (e.g. `Lacaedemon/sparta`).
- **`@v1` can trail `main` in practice —
  verify against the TAGGED file, not `main` or `examples/`.** Observed:
  `main`'s `claude.yml` / `claude-code-review.yml` both declare an
  `ANTHROPIC_API_KEY` secret in their `workflow_call: secrets:` block, and
  `examples/claude.yml` / `examples/claude-code-review.yml` (also on `main`)
  show passing it — but the `@v1` tag's copy of both reusable workflows only
  declares `CLAUDE_CODE_OAUTH_TOKEN`, `SUBMODULES_TOKEN`, and (for `claude.yml`)
  `WORKFLOW_TOKEN`. A caller that copies the example verbatim and pins `@v1`
  gets a `startup_failure`: `Invalid secret, ANTHROPIC_API_KEY is not defined
  in the referenced workflow.` Before trusting an `examples/` template (or
  `main`'s workflow file) for a `secrets:`/`with:` block passed to an `@v1`
  call, fetch the actual `@v1`-tagged file
  (`mcp__github__get_file_contents` with `ref: refs/tags/v1`, or
  `git show v1:.github/workflows/<file>`) and diff its `workflow_call:`
  section against what you're about to pass. Filed as gha#179; worked around
  in `d-morrison/altdoc`#14 by omitting `ANTHROPIC_API_KEY` until `@v1` catches
  up.
- **A `workflow_call` reusable-workflow ref (`@v1`/`@v2`) resolves ONCE, at the
  run's original creation time, and stays pinned to that SHA across every
  re-run of that same run — even after the tag has since moved to a fix.** So
  if a consumer PR's `claude-code-review.yml` run first ran while `@v2` still
  pointed at a broken gha commit, re-running that same run (whether via the
  Actions UI "Re-run failed jobs" or a bot re-dispatch that happens to target
  the existing run rather than creating a new one) reproduces the identical
  pre-fix failure forever, no matter how many times you retry or how long ago
  the tag was fixed. **Diagnose by checking `run_attempt`** (> 1 means this is
  a re-run, not a fresh dispatch) **and `created_at`** (`mcp__github__actions_get`,
  `method: get_workflow_run` — compare against when the fix landed), then read
  `referenced_workflows[].sha` in the same response — it shows the ACTUAL
  resolved commit for that run, which you can diff against the tag's current
  `get_tag` SHA to confirm staleness. **Only a
  genuinely NEW run (a new `run_id`) re-resolves the tag fresh** — a new commit
  (`pull_request: synchronize`) is the reliable trigger; an `@claude review`
  comment sometimes causes the bot to re-run the existing stale run instead of
  dispatching a new one (observed on UCD-SERG/serodynamics#193 — a direct
  `workflow_dispatch` via `actions_run_trigger` would have sidestepped this,
  but that call 403s in these sessions too, per the note above).
- **`check-non-standard-chars` (the `chars` selftest job) scans only `.qmd` and
  `.R` files.** Em dashes / smart quotes in workflow YAML comments, README, or
  example stubs pass; the SAME character in a `.qmd` fails CI (`U+2014` etc.).
  When editing gha docs, keep `.qmd` ASCII (`-`/`;`, not `—`).
- **403 caveat — scoped sessions can push ONLY the assigned branch; tag pushes
  are denied.** In remote/web sessions the proxy rejects any ref that isn't the
  harness-assigned branch with `HTTP 403` — including `refs/tags/*`. **`git push
  --dry-run` gives a FALSE POSITIVE here** (it prints `* [new tag] …` because the
  negotiation succeeds, but the real push 403s on the ref update). So you cannot
  cut tags from such a session — hand the exact `git tag` + `git push` commands to
  the user instead. Don't retry the 403 (policy denial, not transient).
- **A session can be fully READ-ONLY on a repo — even the harness-assigned
  branch can be unwritable.** Beyond the tag-push case above, some sessions
  403 on every write path to a given repo: `git push` to the assigned branch
  itself (not just other branches — and `git ls-remote` may show the assigned
  branch doesn't even exist on the remote yet, so the push 403s trying to
  create it), plus every GitHub MCP write tool — `push_files`/branch creation,
  `create_or_update_file` (contents API), and `add_issue_comment` — all
  returning `403 Resource not accessible by integration`. Confirm this
  conclusively by testing 2-3 *distinct* write endpoints (not just retrying the
  same one) before concluding read-only, since a single 403 could be a
  branch-scope issue (the case above) rather than a repo-wide one. Once
  confirmed: don't keep retrying — package the diff as a patch
  (`git format-patch`) and hand it to the user via `SendUserFile` instead of a
  pasted diff, so it's directly `git am`-able. Because you can't push, watch
  for the user (or another session) to land an independently-derived fix
  rather than your literal patch — re-verify the actual merged diff before
  reporting status rather than assuming your patch was applied as-is. (Hit on
  ucdavis/fxtas#156: diagnosed a CI-breaking dependency issue, delivered the
  fix as two patch files since every write 403'd; the user filed their own
  issue/PR with a different fix for the same root cause and merged that
  instead.)
- **Input-forwarding checklist when adding an input to a gha composite action.**
  Adding a new `inputs:` entry to `<name>/action.yml` requires four coordinated updates:
  1. Expose it in the wrapping reusable workflow (`.github/workflows/<name>.yml`) under
     `on: workflow_call: inputs:`.
  2. Forward it in the reusable workflow's `uses: d-morrison/gha/<name>@v1` step's
     `with:` block.
  3. Update `examples/<name>.yml` (the caller stub) if the input is consumer-visible.
  4. Update the README table row for `<name>.yml` to list the new input under "Key inputs".
  Missing any of these leaves the input wired only partway — consumers can't pass it
  through the reusable workflow even though it exists in the composite. (Caught by
  Copilot on gha#92: `fail-if-empty` was in the composite but not in README or examples;
  a separate pre-existing gap — the `fail` input — was filed as gha#93.)
- **Reusable workflow input descriptions say "workflow run", not "action."** A
  `workflow_call` wrapper is not a composite action — `inputs:` descriptions should say
  "Fail the workflow run …" not "Fail the action …". When copying an input description
  from `action.yml` into the wrapping `workflow_call` file, update "action" → "workflow
  run". (Fixed in gha#92: `fail-if-empty` description in `check-links.yml`.)
- **GitHub Actions job conclusions: no "skipped" from a running job.** A job that has
  started can only conclude `success` or `failure` — never `skipped`. The only way to get
  the gray skip icon on a check is a false `if:` on an *unstarted* job. Pattern for
  infrastructure conditions (quota exhaustion, pre-flight failures): have the main job
  succeed (exit 0) and set an output flag, then add a second gate job whose `if:` is
  false when the flag is set. The gate job is what consumers watch in branch protection;
  it shows skipped (gray) on infra conditions and success on clean reviews. See gha#104
  for the `require-review` job implementation.
- **`mcp__github__get_job_logs` usage.** Two calling modes — use the right one:
  - Single job: pass `job_id` (number) + `return_content: true`. Do NOT pass `run_id` alongside. Without `return_content: true` the tool returns only a `logs_url` download link and `"Job logs are available for download"` — no actual log text.
  - All failed jobs in a run: pass `run_id` (number) + `failed_only: true` + `return_content: true`. Do NOT pass `job_id`.
  The tool's error message ("job_id is required when failed_only is false") is misleading when you pass `failed_only: true` with `run_id`; the issue is actually conflicting parameters.
- **A small `tail_lines` on `get_job_logs` can silently miss the real failure** when
  the log contains a few enormous single-line entries (e.g. a base64-encoded
  spinner GIF/PNG being curled and embedded in a PR comment) — the tool's "line"
  budget gets consumed by those giant lines before reaching earlier real steps, so
  `tail_lines: 60`/`120`/`300` can return only post-failure cleanup/reviewer-restore
  steps with no trace of the actual error. Escalate `tail_lines` (e.g. to 2000) and,
  once the result exceeds the token cap and gets saved to a file, grep/slice that
  file with `python3` (byte-offset search, not line-based) rather than trusting a
  small default tail. Cross-check with `mcp__github__actions_get`
  (`method: "get_workflow_job"` — confirmed in the live schema alongside
  `get_workflow_run`) for the per-step `conclusion` breakdown to know which step
  actually failed and roughly where in the log to look. (ai-config#403.)
- **`get_job_logs` hard-caps the returned content at 5,000 lines regardless of
  `tail_lines`** — a `tail_lines: 100000` request on a 14,503-line job log still
  returns only the last 5,000 lines. The result's `original_length` field
  reports the full line count, so compute the offset: returned line `i`
  (0-based) is full-log line `original_length - 5000 + i + 1`. There's no way
  to fetch the head through this tool, and the REST fallback
  (`/actions/jobs/{id}/logs`) needs `api.github.com`, which the agent proxy
  blocks in these sessions. A GitHub UI deep link `#step:N:L` means line `L`
  counted *within step N* (step N's first log line is 1), so locating it in
  the tail needs the step's start line — estimable from the earlier steps'
  typical output volume when the head is unfetchable, and worth
  cross-checking against whether a plausible warning/error actually sits at
  the computed spot. (rme#1047: located a docx TeX-math warning this way at
  `#step:10:8366` of a truncated publish log.)
- **`claude-review` failing with "Skipping action due to workflow validation…
  must have identical content to the default branch" is NOT always the
  documented self-mod-skip or stale-`@v1`-tag drift.** Before assuming either,
  verify: diff the PR branch's own workflow files against current `origin/main`
  (`git diff origin/<branch> origin/main -- .github/workflows/`) — if that's
  empty, the branch has zero drift and neither known cause applies. The actual
  failure can be a one-off transient GitHub API error unrelated to workflow
  content at all, e.g. a `502` "Unicorn" error page from
  `GET /repos/.../collaborators/<actor>/permission` during the action's
  actor-permission check — visible only by reading the full job log (see the
  `tail_lines` note above), not from the top-level check-run message. Re-running
  (push a commit, since `actions:write` is usually unavailable — see above)
  clears a transient 502 with no code change needed. (ai-config#403.)
- **`update-snapshots.yml@v1`** — regenerates testthat snapshots, commits, and pushes.
  Supports `workflow_dispatch`, `/update-snapshots` PR comment (`pr-mode: true`), and
  auto-update before R-CMD-check (`ref: github.head_ref`). Pass system deps via
  `apt-packages`. Added in gha#103; bcs#226 is the reference caller.

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

## GitHub Actions workflow authoring gotchas

- **A bare `devtools::test()` in a gating CI step never fails the job.**
  `devtools::test()`'s signature sets `stop_on_failure = FALSE` and forwards
  it to `testthat::test_local()` — overriding `test_local()`'s own `TRUE`
  default (verified in `r-lib/devtools` `R/test.R`) — so under
  `shell: Rscript {0}` the step exits 0 even when tests fail. Pass
  `stop_on_failure = TRUE` explicitly in any step whose purpose is to gate.
  (gha#272: `update-snapshots.yml`'s post-`snapshot_accept()` verification
  re-run shipped this way for the capability's whole released life — a
  still-failing suite exited 0 and the broken snapshots were committed and
  pushed anyway; surfaced only when the new reference page's description of
  the gate was fact-checked against the implementation in review.)
- **`GITHUB_TOKEN`-driven pushes create no workflow runs — except on PRs,
  where the runs now appear in an approval-required state instead of not at
  all.** The long-standing no-retrigger rule has a github.com-live exception
  for `pull_request` `opened`/`synchronize`/`reopened`: when a workflow's
  `GITHUB_TOKEN` creates or updates a PR, the resulting runs are created
  approval-required, and a write-access user starts them via "Approve
  workflows to run" in the PR merge box. A `GITHUB_TOKEN` push to a plain
  branch still triggers nothing. (Verified via the `github/docs` source:
  `data/reusables/actions/actions-do-not-trigger-workflows.md`, gated by
  `data/features/actions-github-token-pull-request-approval.yml` with
  `fpt: '*'` and `ghec: '*'` (GHES commented out). Used on gha#272's
  update-snapshots reference page.)
- **Local composite refs (`./`) in reusable workflows resolve relative to the HOST repo.**
  A `workflow_call` reusable workflow living in gha cannot call `./path/to/composite` from
  a CALLER's repo — `./` always resolves to gha itself. Workaround: pass the data the
  composite would have consumed as a plain input (e.g. an `apt-packages` string). Learned
  while extracting `update-snapshots` (gha#103): bcs's `install-system-deps` composite
  couldn't be called; the package list was passed as a string input instead.
- **The inverse gotcha: `actions/checkout` (no explicit `repository:`) inside a
  `workflow_call` reusable workflow checks out the CALLER's repo, not the reusable
  workflow's own.** A `run:` step that then references a script by a
  `GITHUB_WORKSPACE`-relative path (e.g.
  `bash "${GITHUB_WORKSPACE}/.github/workflows/scripts/foo.sh"`) silently assumes the
  checked-out tree is the reusable workflow's own repo — true only when a repo calls its
  own workflow (dogfooding), false for every other consumer, which gets
  `No such file or directory`. A step inside `claude-code-review.yml` (the CALLEE) read
  `${{ github.workflow_ref }}` and it evaluated to
  `d-morrison/gha/.github/workflows/claude-review.yml@refs/pull/191/merge` — the
  CALLER's stub file (`claude-review.yml`), not the callee's own
  (`claude-code-review.yml`) — confirmed straight from the job's log output (gha#191,
  run 28628848306, job 84901231352, the `selfmod` step's `WORKFLOW_REF` env dump). This
  contradicts a naive reading of GitHub's docs (which describe `workflow_ref` simply as
  "the ref path to the [running] workflow" without spelling out the reusable-workflow
  case), so trust the log evidence over the doc summary if they seem to disagree.
  (d-morrison/gha#190/#191: `claude-code-review.yml`'s fail-check guard broke
  for every consumer after its logic was extracted from inline shell into a standalone
  script, landing right after the last known-good run.)
  **`github.job_workflow_ref` is NOT a reliable fix for this — correcting an earlier
  entry here that claimed otherwise.** #191's fix resolved the callee's own repo/ref via
  `github.job_workflow_ref`, parsed it, and checked that ref out into a side directory
  before running the script; at the time this looked "empirically verified" because the
  CI job went green afterward. It wasn't: on real consumer runs (a genuinely fresh
  `pull_request: reopened` event on a cross-repo consumer, well after the tag moved to
  the fix commit) `github.job_workflow_ref` evaluated to an **empty string** at that call
  site, crashing the step with a bare `usage: ...` error (gha#196). The earlier "green CI
  = confirmed working" inference was wrong — the green run just hadn't exercised the
  cross-repo path yet. A second, independent investigation (gha#194, a same-repo
  dogfooding failure on `d-morrison/gha` reviewing its own PR) found a documented
  explanation: per [github/community discussions #31054](https://github.com/orgs/community/discussions/31054)
  and [github/community discussions #45342](https://github.com/orgs/community/discussions/45342),
  `github.job_workflow_ref` is a **known no-op for a SAME-repository**
  reusable-workflow call — it only reliably populates for a genuine cross-repo
  `owner/repo/...@ref` call. That explains the same-repo dogfooding failure cleanly, but
  doesn't fully explain gha#196's original *cross-repo* failure (`Lacaedemon/sparta`
  calling `d-morrison/gha`) — so treat "populates correctly for cross-repo, no-op for
  same-repo" as the documented claim, not as fully reconciled with every observed
  failure; don't re-litigate it, just don't rely on the value being non-empty in ANY
  case. **The robust fix:** don't resolve-and-checkout at all — move the logic into a
  composite action and reference its own files via `${{ github.action_path }}`. A
  composite action's own files are always reachable through `github.action_path`
  regardless of how the calling reusable workflow was invoked (`workflow_call`, a
  re-dispatched `workflow_dispatch`, automatic `pull_request`, same-repo or cross-repo),
  with no conditional branching on `job_workflow_ref` needed. (d-morrison/gha#197,
  `.github/actions/run-review-guard/`.)
- **A fix that's only unit-tested against the extracted logic in isolation, never against
  the actual `uses:` invocation, can ship a broken integration point undetected.** #191's
  own test (`parse-workflow-ref/tests/run-tests.sh`) fed hardcoded ref strings straight to
  the sed-parsing script and proved the parsing logic correct — but never exercised
  whether GitHub actually populates `github.job_workflow_ref` with a non-empty value at
  the real call site, so the regression above (gha#196) shipped and went undetected until
  a live consumer run hit it. The fix (gha#197) closed this gap by adding a selftest step
  that invokes the new composite action itself via a real `uses: ./.github/actions/<name>`
  step against a canned fixture — the same category of gap `sync-with-main.md`'s "derived
  artifacts" and "extracted copy" entries describe, but for a composite action's runtime
  resolution specifically rather than a checked-out script's content.
- **A nested `uses: ./...` composite-action reference INSIDE another composite action
  resolves against `$GITHUB_WORKSPACE` (the top-level workflow's own checkout), not
  against the repo the enclosing composite was itself fetched from -- a distinct failure
  mode from the `job_workflow_ref` case just above, but the same underlying lesson.**
  Confirmed via [`actions/runner#1348`](https://github.com/actions/runner/issues/1348)
  ("Local composite actions always relative to top level repository"). Extracting a new
  shared composite (e.g. a base-URL-derivation helper) and having two sibling composites
  reach it via a local `uses: ./.github/actions/<new-composite>` step looks correct and
  even passes selftest when the selftest job happens to check out the same repo the
  composite lives in (masking the bug) -- but breaks for every real consumer, whose own
  checkout doesn't contain that path. I stated the opposite claim confidently in a code
  comment ("a same-repo local path resolves against the repository this action was
  fetched from") before a later review round caught it -- a wrong belief stated as fact,
  not just a missed check. **Fix: reach the sibling composite's script directly via
  `${{ github.action_path }}/../other-composite/script.py`, never via a nested `uses:`**
  -- `github.action_path` is correct regardless of caller context, the same principle
  #197 (above) established for `job_workflow_ref`. (d-morrison/gha#284, rounds 1-3 fixed
  other genuine bugs first; this one wasn't caught until round 4.)
- **An unrelated open PR can independently patch the same root cause as an incidental,
  second commit — without ever linking the issue — surfacing only as a merge conflict
  after your own fix lands.** `post-merge`'s cascade-conflict-scan step (1.5) is what
  catches this, not `check-history` or issue cross-referencing: neither would have
  flagged it, since the other PR (gha#194, primarily a `gh`-subcommand-allowlist fix)
  never mentioned or linked the job_workflow_ref issue it happened to also patch as a
  bundled "second, unrelated fix" commit. When resolving the resulting conflict, prefer
  the more general/robust fix over a narrower band-aid patching the same symptom (here:
  keep the composite-action fix, drop the other PR's `if: job_workflow_ref != ''`
  same-repo-only conditional and its now-inaccurate changelog fragment describing a fix
  that no longer ships) — and explain the resolution and why in a PR comment, since it's
  discarding another author's already-committed work.
- **`secrets: inherit` is NOT needed when the reusable workflow only uses `github.token`.**
  `github.token` auto-injects the caller's token via `permissions:` — not via `secrets:`.
  `secrets: inherit` is only needed for named secrets (`secrets.MY_PAT`, etc.). Automated
  reviewers (claude-bot, Copilot) routinely flag this as a false positive — rebut it by
  confirming the callee has no `secrets:` inputs.
- **A reusable workflow's job permissions are checked against the caller's grant at
  graph-build time — `if:`-skipped jobs are NOT exempt.** A called workflow's job that
  declares `permissions: contents: write` makes the WHOLE call fail with
  `startup_failure` (instant, <1s, no jobs created) if the caller grants only
  `contents: read` — even when that job has `if: inputs.deploy` evaluating false and
  never runs. Consequence: you canNOT offer a "deploy: false ⇒ caller needs only read"
  optimization in a reusable workflow whose deploy job statically requests write; the
  caller must grant write regardless. Keep the read-only work in a separate
  `contents: read` build job (it downscopes its own token), but the caller still grants
  the union (write). Cost me two red CI rounds on gha#118. To debug a `startup_failure`
  with `total_jobs: 0`: it's a graph/permission/parse error, not a runtime one — check
  the called workflow's permission ceilings first.
- **An OMITTED key in a caller's explicit `permissions:` block defaults to `none`, not
  "inherit" — so the caller must enumerate EVERY permission the callee's jobs request.**
  Same `startup_failure` failure mode as above, but the trap is silence: gha's
  `claude-code-review.yml@v1` job requests `actions: read` (for the `github_ci` MCP
  server), and ai-config's caller granted `contents`/`pull-requests`/`issues`/`id-token`
  but never listed `actions` — which then defaulted to `none`, so every review run died
  at `startup_failure` (`The nested job is requesting actions: read, but is only allowed
  actions: none`) and no review ever posted. When wiring a caller stub for a gha reusable
  workflow, copy the `permissions:` block from the matching `examples/<name>.yml` verbatim
  rather than hand-picking keys, and re-diff against it when the stub drifts. (ai-config#224.)
- **Detached HEAD on `pull_request` events.** `actions/checkout` without an explicit `ref`
  on a PR event checks out a synthetic merge commit in detached HEAD — `git push` then
  fails. Fix: pass `ref: ${{ github.head_ref }}` so the branch name is checked out, not the
  merge commit SHA. Required for any reusable workflow that needs to `git push` from a PR
  caller.
- **`always()` + optional upstream job needs an explicit result guard.** The pattern
  `if: ${{ always() && !cancelled() && needs.X.result == 'success' }}` keeps the job
  running when X is *skipped* (non-PR events), but also lets it run when X *fails* —
  causing noise from a job that depended on work that didn't land. Full guard:
  `(needs.X.result == 'success' || needs.X.result == 'skipped')`. (Fixed in bcs#226.)
- **The same `always()` gap exists one level down: a STEP gated `if: always()` that
  reads `env: FOO: ${{ steps.earlier.outputs.bar }}` still runs -- with `FOO` empty --
  if `earlier` failed, not just when an upstream JOB failed.** `always()` on a step
  means "run regardless of prior step outcome," so an earlier step's failure to
  write its output (script errored before the `>> "$GITHUB_OUTPUT"` line) silently
  hands the later step an empty string, not a skip. If that empty value feeds a
  command with real effects (a `--ref ""` on `gh workflow run`, a `--branch ""` on
  some other CLI), the failure mode ranges from a confusing CLI error to a
  misdirected action, not a clean no-op. Guard explicitly: `if [ -z "$FOO" ]; then
  echo "::warning::..."; else <the real command>; fi` -- don't assume the value is
  always populated just because the step that sets it "should" have run first.
  (gha#286, Copilot review finding: three `always()`-gated steps in `claude.yml`
  read `PR_BRANCH: ${{ steps.pr_checkout.outputs.branch }}` for a `gh workflow run
  --ref "$PR_BRANCH"` call, unguarded against `pr_checkout` having failed.)
- **Canonical GitHub privacy-safe noreply email is `<numeric-id>+<username>@users.noreply.github.com`.**
  The bare `<username>@users.noreply.github.com` is not privacy-safe and can match a real inbox.
  For `issue_comment` events, the actor's numeric ID is in `github.event.comment.user.id`:
  `committer-email: ${{ github.event.comment.user.id }}+${{ github.actor }}@users.noreply.github.com`.
- **Both bcs PR gates have a label bypass for non-user-visible changes.** `version-check`
  (`version-check.yaml`, derived from RMI-PACTA's R-semver-check) does a pure version
  comparison and fails if the PR branch version ≤ main's, **but** it skips when the
  `no version increment` label is present. The changelog check (`news.yaml` ->
  gha `check-news.yml`) skips with the `no changelog` label. Both workflows trigger on
  `labeled`/`unlabeled`, so adding the labels re-runs and clears them with no push. For a
  CI-only / workflow-only PR (no user-visible R-package change), apply **both** labels
  rather than bumping `DESCRIPTION` and editing `NEWS.md`. (Verified on ucdavis/bcs#236 —
  corrects an earlier note that claimed `version-check` had no bypass.)
- **bcs `docs` build (altdoc) EXECUTES the rendered man-page examples.** altdoc
  renders each `man/*.Rd` to a `man/*.qmd` and runs the example chunk, so
  `@examplesIf FALSE` does NOT protect an example — the code still runs and a
  data-dependent call fails the `docs` job (`object 'pt_a' not found`). For any
  example that needs the protected/real cohort, use `\dontrun{}` (altdoc renders
  it without evaluating), matching the existing convention (e.g.
  `R/calc_ip_weights.R`). Runnable examples with self-contained synthetic data
  are fine and do execute. (Hit on ucdavis/bcs#238.)
- **altdoc's `$ALTDOC_MAN_BLOCK` sidebar placeholder has no pkgdown-style
  `reference:` grouping and no internal-topic exclusion --- it flat-lists
  every `man/*.Rd` file under one ungrouped "Reference" section, internal
  topics (`@keywords internal`) included.** Confirmed by reading
  `d-morrison/altdoc`'s `R/settings_quarto_website.R`,
  `.sidebar_vignettes_quarto_website()` (despite the vignettes-only-sounding
  name, this one function handles both the `$ALTDOC_VIGNETTE_BLOCK` and
  `$ALTDOC_MAN_BLOCK` placeholders): it globs `man/*.qmd` under the
  render output and turns the whole list into `section: Reference` with no
  filtering or title-based grouping, unlike pkgdown's `reference:` block in
  `_pkgdown.yml`. To reproduce a pkgdown-style grouped index/sidebar (with
  internal topics hidden) on an altdoc site today, hand-author the grouping
  directly in the consuming repo's `altdoc/quarto_website.yml` --- replace
  the `$ALTDOC_MAN_BLOCK` placeholder with explicit `section:`/`contents:`
  entries pointing at `man/<topic>.qmd` (the same file-path convention the
  navbar's "Documentation" entry already uses for
  `man/serocalculator-package.qmd`), and simply omit any `.Rd` topic marked
  `\keyword{internal}`. When migrating from an old pkgdown site, its retired
  `_pkgdown.yml` (recoverable from git history even after deletion) is
  usually still an accurate source for the grouping and titles to reproduce.
  (`UCD-SERG/serocalculator#575`.)
- **`NEWS.md` section headers need a blank line before them.** A bullet that ends
  immediately before a `## Next-section` heading (no blank line) can cause
  `utils::news()` to misparse adjacent sections. Always leave one blank line
  between the last bullet of a section and the next `##` heading. (bcs#275:
  `## Internal` bullet → `## Tests` with no blank line; bot caught it.)
- **`merge_group:` trigger — guard PR-context workflows at the job level.**
  When adding `merge_group:` to a workflow's `on:` block so the GitHub merge
  queue fires CI checks, any job that uses `github.event.pull_request.*`
  context needs `if: github.event_name == 'pull_request'` at the job level —
  otherwise the job errors on merge-group commits where that context is absent.
  A job with a false `if:` counts as skipped (passing) for branch-protection
  purposes. Also update matrix-selection shell conditions that branch on
  `pull_request` to cover `merge_group` too (use release-only matrix for both).
  Affected jobs in bcs: `version-check`, `news`, `lint-changed-files`, and the
  `R-CMD-check` matrix selector. (bcs#275.)
- **bcs `test-coverage` (codecov) is NOT a required check.** A coverage drop
  leaves the PR `mergeable_state: unstable` (not `blocked`) and does not block
  the merge — `docs`, `version-check`, the R-CMD-check matrix, lint, and
  spellcheck are the required ones. So a PR that adds integration code only
  exercisable against protected data (which inherently lowers coverage) can
  still merge once the required checks are green. (Verified merging #238.)
- **During a long review, re-bump `DESCRIPTION` after every `main` merge.**
  `version-check` compares the PR version to *current* main; if main advances
  (another PR bumps `0.0.0.905x`) and you merge main in, the PR's version is no
  longer strictly greater and version-check flips to failing even though it
  passed before. Bump again (e.g. `9057` -> `9058`). (Hit on #238 after main
  moved to 9057.)
- **bcs object-name lint (`.lintr.R` custom `snake_case_ACROs1` rex regex)**
  rejected study/protocol codes like `ab507bs` (a lowercase segment with letters
  *after* digits) until the lowercase branch was widened to
  `some_of(lower), zero_or_more(one_of(lower, digit))`. As of #238 such
  alphanumeric codes are valid name components; before that they failed
  `lint-changed-files` with `object_name_linter`.
- **Sync vignette captions with R-source axis labels after a label fix.**
  A `plot_*()` function's y-axis label and its vignette figure caption often
  carry the same phrase. Changing the axis label in the R source without
  updating the caption leaves a stale inconsistency that the next review round
  will catch. After fixing an axis label, grep the vignette:
  `grep -r "old phrase" vignettes/` to find and update matching captions.
  (bcs#253 round 3.)
- **Check the column's scale before writing an axis label.**
  A `prep_*()` column computed as `mean(...) * 100` is a 0–100 percentage;
  the axis label must say `%`, not `"Probability of …"` (which implies 0–1).
  Inspect the prep function's body or roxygen `@returns` to confirm the scale.
  (bcs#253: `pct_annual` was 0–100, not 0–1 — label was wrong.)
- **Use `geom_point() + geom_errorbar()` for data with a meaningful non-zero minimum.**
  `geom_col()` draws bars from 0; for enrollment-age data (40–70+) this wastes
  most of the chart area and makes ±SD intervals visually tiny. Use
  `geom_point(size = 3) + geom_errorbar(...)` when 0 is not a meaningful
  reference point. (bcs#253: `plot_results_baseline` switch from `geom_col`.)
- **Use `helper-*.R` for shared testthat setup.**
  testthat 3 auto-sources `tests/testthat/helper-*.R` before any tests run.
  Put shared setup (e.g. `make_pt_data()`) in a `helper-*.R` rather than
  repeating it across test files. One test file per source file is the bcs
  convention — `test-plot_fn.R` for `R/plot_fn.R`. (bcs#253.)
- **A push can trigger ZERO check-runs on a `pull_request`-triggered workflow — not a
  quota skip, not an error, just total silence.** Symptom: `gh pr checks <N>` shows
  stale/old results or "no checks reported"; `gh api repos/<o>/<r>/commits/<sha>/check-runs`
  (the new commit's SHA) returns an **empty** `check_runs` array — confirms literally
  nothing was dispatched for that push, distinct from a job that ran and failed/skipped.
  `gh run list --branch <branch>` likewise shows no new run after the push timestamp.
  This hit on an otherwise-healthy repo (sparta) mid-ARDI: a normal `git push` to an
  open PR's branch produced no CI activity for 15+ minutes. Recovery — manually dispatch
  every required workflow rather than waiting longer or re-pushing (a re-push doesn't
  reliably fix it either): for any `workflow_dispatch`-enabled workflow keyed off the
  branch, `gh workflow run <file>.yml --ref <branch>`; for a PR-number-keyed review
  workflow (e.g. `claude-code-review.yml` with a `pr_number` input — see the
  `workflow_dispatch` re-trigger pattern above), `gh workflow run <file>.yml -f
  pr_number=<N>`. Poll the dispatched run's own ID (`gh run view <id> --json
  status,conclusion`), not the (still-empty) push-event check list. If a workflow has
  no `workflow_dispatch` trigger, that one specific check stays stuck — note it and ask
  the user rather than silently treating the PR as green without it.
- **`workflow_call` input `default:` must be a static literal — it cannot reference
  `${{ ... }}` expressions.** A reusable workflow's `inputs.<name>.default` is parsed
  before any context is available, so an input can't default straight to
  `${{ github.event_name == 'pull_request' && ... }}` (or any other expression) to
  mirror an existing composite/job heuristic. Use a sentinel default instead (e.g.
  `'auto'`) and resolve the real expression where the input is consumed (a `with:`/`env:`
  value or a step), treating `'auto'` as "apply the heuristic" while `'true'`/`'false'`
  are explicit overrides. (gha#148: `test-coverage.yml`'s `fail-ci-if-error` input.)

## claude-code-action: tag mode vs agent mode and git write tools

- **Tag mode (`track_progress: true`) hardcodes git write tools into `ALLOWED_TOOLS`
  regardless of `--disallowedTools`.** The action's TypeScript sets the `ALLOWED_TOOLS`
  env var at runtime, injecting `Bash(git add:*)`, `Bash(git commit:*)`,
  `Bash(git rm:*)`, and `git-push.sh`. The `--disallowedTools` CLI flag cannot
  override an env var set by the same process. Evidence: `d-morrison/gha` PR #134,
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
  — enough to confirm a stub occurred, not why. The workflow separately uploads
  the full turn-by-turn transcript as a `claude-review-execution-<run>-<attempt>.zip`
  artifact (the name is defined by `d-morrison/gha`'s reusable workflow, not a
  Claude Code convention — a future rename there invalidates this; confirm via
  `gh api repos/<owner>/<repo>/actions/runs/<run_id>/artifacts` rather than
  assuming the name, then `curl -H "Authorization: token $(gh auth token)"
  .../artifacts/<id>/zip` to fetch). It's a single pretty-printed JSON array of
  Claude Code SDK message objects, not NDJSON — each element has a top-level
  `type` (`"system"`/`"assistant"`/`"user"`/`"result"`) and, for `"assistant"`
  elements, a `message.content` array of blocks (`{"type":"tool_use", "name":
  ..., ...}`, `{"type":"text", "text": ...}`, etc.) — parse with
  `jq '.[] | select(.type=="assistant") | .message.content[]? | select(.type=="tool_use") | .name'`
  for a tool-use histogram, or pull `is_error==true` tool_results for the actual
  denial messages. This is how a "stub review" traced back to the model
  fanning its own review out across background `Agent` calls and ending its turn
  on "waiting for background agents" — a mechanism the summary object alone
  can't show (`d-morrison/gha#185`, `Lacaedemon/sparta` PR #615, 2026-07-03).
- **A `claude-code-review` false-positive "stub" is also possible on a review that actually completed and posted a real, correctly-formatted verdict — distinct from the gha#185 background-agent-fanout pattern above.** `check-review-execution.sh`'s stub-detector scans only `type=="text"` content blocks for a line matching `^[[:space:]>*_#-]*verdict\b` (grep, anchored to line-start) — it does not look inside `tool_use` block arguments. If the agent's final free-text message merely *narrates* what it posted ("Posted the inline finding and a summary comment ending in `### Verdict: Ready for merge`.") rather than repeating the verdict as its own standalone line, the word "verdict" only appears mid-sentence, so the anchored regex correctly does *not* match it — even though the actual GitHub comment (posted via a tool call earlier in the same transcript) has a perfectly-formed `### Verdict` heading. This false stub classification then triggers an unnecessary retry, and if THAT retry genuinely stubs (e.g. the gha#185 pattern), the overall check reports `failure` on a PR that already had a valid, complete review. Diagnose by downloading both attempts' execution-transcript artifacts (see the note above) and checking attempt 1's own posted PR comment directly, not just its final "result" text. Filed with full evidence as `d-morrison/gha#218` (`Lacaedemon/sparta` PR #615, 2026-07-03) rather than reopening #185, since the mechanism (a scanning gap, not a fanout-and-never-resume) is distinct.
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

## Changelog section ordering in d-morrison/gha

- **The established order in `CHANGELOG.md` is: Added → Changed → Fixed → Security.**
  Match this when adding new `## [Unreleased]` entries or when resolving merge
  conflicts in the changelog. Caught in gha#134 review (Fixed appeared before Changed).

## gha claude-code-review — self-modification skip guard (not a stub)

A PR that **edits `.github/workflows/claude-code-review.yml` itself** gets a
fast (~9s) green `review / claude-review` job that posts **no review**: the
reusable workflow detects the self-edit and deliberately skips
("PR #N edits .github/workflows/claude-code-review.yml — skipping self-review
(the action 401s on workflow validation until merged; it runs after merge)"),
and `require-review` tolerates the skip. Don't treat this as a stub review or
re-trigger it — read the job log for the `::notice::` line to confirm, post a
manual self-review with a verdict instead (per the do-the-review-yourself
rule), and note the first genuine end-to-end run happens on the next PR after
merge. (ucdavis/win#75, 2026-07-16 — the migration PR itself could never be
bot-reviewed; win#69's post-merge sync then ran the migrated workflow live and
it worked, including `check-latex-macros` and the cost report.)
