# Local tools & CLIs

## Copilot tool availability can change mid-session

- Honor `tools_changed_notice` events literally. If a notice says a tool is no
  longer available (e.g., `create`, `edit`), switch immediately to still-listed
  alternatives (typically `apply_patch` + `view` + `bash`) instead of retrying
  the removed tool.
- For UMS/maintenance passes this matters because stale muscle memory ("use
  create/edit") can fail repeatedly after the tool list changes.

## Operational checklist pattern for write actions

- **Preflight gate:** verify target branch/repo and whether the action should update an existing PR versus create a new one.
- **Safe command form:** when content includes markdown/backticks, write to a temp file and pass `--body-file` or `-F "body=@<file>"`; avoid inline double-quoted body args.
- **Postcondition gate:** after push/post/create, query GitHub state in the intended base repo (for PRs, include both repo and head owner) and confirm the intended object actually exists/updated. `gh pr list --head <owner>:<branch>` silently returns empty for an owner-qualified head even when a matching PR exists — verified directly against a real open PR (`gh pr list --head d-morrison:ums-pr635-lessons` returned `[]`; the bare `--head ums-pr635-lessons` found it). Use the REST API instead, with the branch passed as a `-f` GET field rather than interpolated into the raw URL — a branch name containing `#`, `&`, or `+` breaks a hand-built query string but is passed through correctly as a field: `gh api --method GET "repos/<upstream-owner>/<repo>/pulls" -f "head=<head-owner>:<branch>" -f "state=open" --jq '.[] | {number, url, state}'`.
- **Failure signature:** stderr like `command not found` during a `gh`/`glab ... --body` call can mean two different things — check which first, probing whichever CLI actually failed (`which gh` or `which glab`, not always `gh`): if `gh` itself is unavailable (expected in remote/web sessions), fall back to the mapped MCP tool instead of retrying the CLI — `tool-mappings.yml` has no `glab` operations, so a missing `glab` has no MCP fallback; hand off or block instead. If the CLI that failed is present, the likely cause is shell-expanded backticks mangling the body — re-run using a file-backed body.

## gh (GitHub CLI)
- `gh` opens a pager (alternate buffer) that hangs the agent terminal.
- Always disable it: pipe `| cat` or set `GH_PAGER=cat` (e.g. `gh pr view 116 | cat`).
- `gh --no-pager` is not a supported flag and will error; use `GH_PAGER=cat` or `| cat` instead.
- **Rate limit is shared (5000/hr) and split GraphQL vs REST.** All tools/sessions/agents share the one user's 5000/hr; **GraphQL has its own, smaller pool that exhausts first** — `gh pr checks`, `gh pr view --json comments`, `gh pr list --json` use GraphQL. When GraphQL is spent, get the same data via REST (still has budget): `gh api repos/<o>/<r>/pulls/<n>`, `.../commits/<sha>/check-runs`, `.../issues/<n>/comments`. `gh api rate_limit --jq .resources` is **free** (doesn't count) — check `core` vs `graphql` remaining/reset before retrying. Don't tight-poll; use a background watcher with `sleep` (parallel sessions drain the shared pool fast).
- **The @claude review bot's author name differs by API:** its comment author is `claude[bot]` in REST (`.user.login`) but `claude` in GraphQL (`.author.login`). A watcher filtering REST comments for `.user.login == "claude"` silently finds nothing — use `"claude[bot]"`.
- **A third variant: on `d-morrison/gha` itself, the review comment posts as `github-actions[bot]`, not `claude`/`claude[bot]`.** Filtering `.user.login == "claude"` (or `"claude[bot]"`) there returns nothing even though a real, complete review was posted — the workflow's own `gather-context` job comment even says "REST author login is `claude[bot]`", which doesn't match what the bot actually posts under in that repo. Don't conclude "no review yet" from an empty filter on one login string: if it comes back empty, list all comment authors (`gh api repos/<o>/<r>/issues/<N>/comments --jq '.[] | .user.login'`) and check the body for the `**Claude finished` marker regardless of which login posted it. (gha#278, 2026-07-21: `select(.author.login == "claude")` and `select(.user.login | test("claude"))` both came up empty; the actual review comments were under `github-actions[bot]`.)
- **Polling for the bot's verdict: match `Claude finished`, don't exclude a placeholder.** While a run is underway, the bot's comment holds an in-progress placeholder whose wording *varies between runs* ("### Review in progress …", "Claude Code is working…"), so a watcher that exits when comments exist, or when one known placeholder phrase disappears, fires early on the next differently-worded placeholder. Completed runs (review and agent alike) start the body with `**Claude finished`. **Filter on that body marker, not on an author login** --- the login itself varies by repo (see the `github-actions[bot]` variant in the bullet above), so a login-only filter can come up empty even once a review has posted.
  - **When re-triggering a run on a thread that already has a completed `**Claude finished` comment from an earlier run, also scope the filter to comments newer than a baseline ID captured before the trigger** --- otherwise the poll matches the *prior* run's already-finished comment immediately and never actually waits for the new one. **`gh api`'s own `--jq` flag has no way to inject a variable (no `--argjson`) and only fetches the first REST page (30 comments) unless told to paginate, and `--paginate`'s `--slurp` companion flag is rejected outright when combined with `--jq`** --- pipe the raw paginated output into standalone `jq -s` instead, which supports both. **Enable `pipefail` in each shell process that runs one of these pipelines** so an upstream `gh api` failure does not get masked by a successful downstream `jq`:
    ```bash
    set -o pipefail
    BASELINE=$(gh api repos/<o>/<r>/issues/<N>/comments --paginate | jq -s '[.[][] | .id] | max // 0')
    # ... trigger the new run ...
    set -o pipefail
    gh api repos/<o>/<r>/issues/<N>/comments --paginate | jq -s --argjson baseline "$BASELINE" \
      '[.[][] | select(.id > $baseline and (.body | startswith("**Claude finished")))] | last | .body'
    ```
    When polling for the *first* run on a fresh thread (no prior completed comment to collide with), the simpler unscoped form still needs `--paginate` for the same >30-comment reason (a REST issue-comments page is oldest-first, so page 1 alone can miss the newest comment entirely once a thread grows past one page): `gh api repos/<o>/<r>/issues/<N>/comments --paginate | jq -s '[.[][] | select(.body | startswith("**Claude finished"))] | last | .body'`. (Cost two wasted watch rounds on ai-config#357 before keying on the marker; the login-filtered version of this command was flagged as stale by review on ai-config#636; the unscoped-across-reruns version was flagged by a follow-up review on ai-config#637 and confirmed concretely on gha#278, whose thread holds two separate `**Claude finished` comments, one per run; and the `gh api --jq --argjson`/pagination gaps in *that* fix were themselves flagged by a still-later review on the same PR, caught only after #637 had already merged.)
- **A reply posted via `gh pr comment`/`gh api` from within a session shows up under the *human user's own* GitHub account, not a bot identity — don't mistake it for an independent human review when auditing a PR's review state.** `gh` authenticates as whatever account is logged in locally (often the user's own, e.g. seen as `dem-extra1` on `Lacaedemon/sparta`), so when an agent (or a dispatched subagent) replies to an inline review comment on the user's behalf, `gh api repos/<o>/<r>/pulls/<N>/reviews` lists it as a `COMMENTED` review authored by the user — indistinguishable at a glance from the user genuinely opening the PR in a browser and typing a reply themselves. Before treating an unexpected review entry as a signal that the human intervened, check whether its body/inline-comment content reads like the agent's own scripted reply (referencing a specific commit SHA, restating verification numbers) rather than free-form human commentary — if so, it's the session's own tooling, not new human input.
- **`gh pr view --json` does not accept `merged` as a field.** Use `state` (returns `"MERGED"`) and `mergedAt` (ISO timestamp, null if not merged) to check merge status. Example: `gh pr view <N> --json state,mergedAt`.
- **`gh pr edit` exits 1 on repos with Projects Classic — use `gh api` to update PR body.** `gh pr edit <N> --body "..."` / `--body-file <f>` returns exit code 1 with a GraphQL deprecation warning (`Projects (classic) is being deprecated…`). Sometimes the edit lands anyway; **sometimes it does not apply at all** (seen on sparta 2026-06-30: three `gh pr edit --body-file` attempts left the body unchanged with the `SHA_PLACEHOLDER` still in place). Either way, don't trust it — verify with `gh api repos/<o>/<r>/pulls/<N> --jq .body`, and just use the REST PATCH directly, which always exits 0 and applies: `gh api -X PATCH repos/<o>/<r>/pulls/<N> -f body="..."`. For a multi-line body, read it from a file with `-F body=@<path>` (capital `-F` to pull the field value from the file) rather than cramming it into `-f body="..."`.
- **PR description image embeds: use `raw.githubusercontent.com`, not `github.com/.../raw/...`.** Embedding a committed file in a PR body with `![](https://github.com/<owner>/<repo>/raw/<sha>/<path>)` may not render — the reviewer will flag it. The correct raw-content domain is `https://raw.githubusercontent.com/<owner>/<repo>/<sha>/<path>`. Reference the full commit SHA so the image keeps rendering after the branch is deleted on merge.
- **Download a user-pasted PR screenshot with `curl -L`.** When a user pastes an image into a GitHub PR comment, the file lives at `https://github.com/user-attachments/assets/<uuid>` and is publicly downloadable: `curl -L -o <dest>.png "https://github.com/user-attachments/assets/<uuid>"`. Retrieve the URL from the comment body via `gh api repos/<o>/<r>/issues/comments/<comment_id> --jq .body`.
- **Linking a GitHub sub-issue needs an integer DB id, not the number.** `POST /repos/<o>/<r>/issues/<parent>/sub_issues` takes `sub_issue_id` = the child's **database id** (`gh api repos/<o>/<r>/issues/<child> --jq .id`), *not* its issue number. Pass it with `-F` (typed, integer), never `-f` (string) — `-f sub_issue_id=…` fails with `422 Invalid property /sub_issue_id: "…" is not of type integer`. Full call: `gh api repos/<o>/<r>/issues/<parent>/sub_issues -F sub_issue_id=<child_db_id>`. Verify with `gh api .../issues/<parent>/sub_issues --jq '.[] | "#\(.number) \(.title)"'`.
- **Backticks in a double-quoted `-m` / `--body` string get command-substituted by the shell.** In the Bash tool, `` git commit -m "... `origin` ..." `` or `` gh pr comment --body "use `foo`" `` makes the shell run `` `origin` ``/`` `foo` `` as a command and splice the (usually empty/erroring) output into the message — silently mangling it (seen on sparta 2026-06-30: a commit body's `` `origin` `` and `` `killer` `` vanished, with `origin: command not found` in stderr). For any message/body containing backticks, use a single-quoted **heredoc** (`` -m "$(cat <<'EOF' … EOF)" `` — the quoted `'EOF'` disables all expansion) or a `--body-file`, never a bare double-quoted string. (Same root cause as ARD inline reply bodies too; use `-F body=@<file>` for `gh api .../pulls/<N>/comments`/`glab api .../notes` so backticks in Markdown never get shell-expanded.)
- **GitHub review inline comments are on a different API endpoint than top-level PR comments.** The top-level comment-view endpoint (`` `gh pr view <N> --json comments` `` or `gh api repos/<o>/<r>/issues/<N>/comments`) captures PR-level comments and bot-posted review overview summaries, but **not inline comments from formal reviews** (line-by-line inline findings). When a user links a specific review ID (e.g. `#pullrequestreview-4761444085`), fetch both the review overview and its inline comments separately: `gh api repos/<o>/<r>/pulls/<N>/reviews/<review-id> --jq '{state, body}'` for the overview, then `gh api repos/<o>/<r>/pulls/<N>/comments --jq '.[] | select(.pull_request_review_id == <review-id>) | {line: .line, body: .body}'` to get the inline findings. A review's overview body can be generic ("I reviewed the code") with all the actual findings in inline comments on specific lines — reading only the overview misses the findings. (Encountered on ai-config#647 review 4761444085: the overview body was generic, but the specific finding was in an inline comment on CLAUDE.md line 324.)
- **Finding the PR(s) linked to an issue from the CLI: use the REST timeline endpoint, not `gh issue view --json`.** `gh issue view --json` has no `timelineItems` field (that exists only on `gh pr view --json`), so `gh issue view <N> --json timelineItems` errors — and a `2>/dev/null` swallows the error so the check silently returns nothing and *looks* like it passed. Query the timeline instead, with three gotchas: (1) in a `cross-referenced` event, `source.type` is always `"issue"`, so a PR is one whose `source.issue.pull_request` is non-null (`source.type == "pull_request"` never matches); (2) `--paginate` is required, or `gh api` returns only the first 30 events and silently misses a later cross-reference; (3) filter `source.issue.state` if you only want open PRs. Full call: `gh api --paginate repos/<o>/<r>/issues/<N>/timeline --jq '.[] | select(.event == "cross-referenced") | .source.issue | select(.pull_request != null) | select(.state == "open") | "#\(.number) \(.title)"'`. (Learned over three review rounds on #287.)

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

## gh — stale remote URL causes cryptic `gh pr create` failure
- `gh pr create` fails with `Head sha can't be blank, Base sha can't be blank, No commits between <owner>:main and <other-owner>:<branch>` when `origin` points to an **old repo URL** (e.g. after a GitHub repo transfer/rename).
- Fix: `git remote set-url origin https://github.com/<new-owner>/<repo>.git` and re-push the branch before creating the PR.
- Diagnosis: `git remote -v` shows the stale URL; `gh repo view --json nameWithOwner` shows where `gh` thinks the canonical repo is.

## GitHub MCP tools (Claude Code remote/web sessions)
- In remote/web sessions the authenticated GitHub identity is the repo owner
  (`d-morrison`), so requesting `d-morrison` as a PR reviewer fails with
  `422 Review cannot be requested from pull request author`. Harmless — the PR
  is still created; the reviewer just isn't added. Don't treat the 422 as a
  failure to retry (it's expected per the standing request-pr-review rule when
  the author == the requested reviewer).
- `gh` is NOT available in these sessions — use the `mcp__github__*` tools for
  all GitHub interactions (PRs, issues, comments, reviews). CI status is always
  available via `mcp__github__pull_request_read` (`get_check_runs` / `get_status`)
  and the `mcp__github__actions_*` tools. Some environments may *also* expose a
  separate `github_ci` MCP server (`mcp__github_ci__*`, e.g. `get_ci_status`),
  which can connect asynchronously after session start. Don't conclude a tool is
  absent from one check — `ToolSearch` for what you need before deciding it's
  missing (and don't assume the `github_ci` server is present either).
- **`mcp__github__actions_run_trigger` can't re-run CI jobs in these sessions —
  it 403s.** `method: rerun_failed_jobs` (and `rerun_workflow_run`) returns
  `403 Resource not accessible by integration`: the integration token lacks the
  `actions: write` the re-run API needs. So a flaky CI failure can't be re-kicked
  via MCP — **push a commit to re-trigger the whole workflow** (the normal path
  during an iterate loop anyway), or ask the user to click Re-run. (Hit
  re-running a flaky `link-checker` timeout on a lab-manual PR.) **`method:
  run_workflow` (a fresh `workflow_dispatch`, not a rerun) 403s the same way** —
  the token lacks `actions: write` for dispatch too, not just for reruns, so
  don't expect a direct-dispatch workaround to succeed where rerun failed
  (confirmed on UCD-SERG/serodynamics#193, and again on `d-morrison/rme#1017`
  trying to dispatch `publish.yml` — same `403 Resource not accessible by
  integration`). Prefer folding
  the retry into a real, already-pending fix (e.g. a reviewer's requested
  wording tweak) over pushing a bare `--allow-empty` commit — same retrigger,
  no throwaway commit in history. Only use an empty commit when no real fix is
  pending. (ai-config#403.) **When the failing workflow only triggers on
  `push: main` / `workflow_dispatch` (no `pull_request` trigger), there's no
  "push a commit to re-trigger" fallback either** — nothing exercises the
  actual failing job pre-merge. Ask the user to dispatch it manually from the
  Actions UI (share the exact workflow filename + branch), and get their
  explicit go-ahead first if the workflow has a real side effect (e.g. a
  gh-pages deploy step not gated to `main`) — dispatching isn't just a status
  check in that case, it's a live action.
- **Comments/replies you post via the GitHub MCP tools echo back into the
  session's `<github-webhook-activity>` events under the human account's
  identity, not a bot identity.** `add_reply_to_pull_request_comment` and
  `add_issue_comment` authenticate as the human who owns the session (e.g.
  `d-morrison`), so a webhook event for your own just-posted reply shows
  `Author: d-morrison` (or whichever human), never a recognizable bot name
  like `claude[bot]`. Don't use the author field to decide "is this my own
  echo, skip it" — match the event's body text (and timing) against what
  you just posted instead. This is easy to get wrong at a glance since a
  same-author event looks exactly like a genuine human reply demanding a
  response. (Hit repeatedly on `UCD-SERG/serocalculator#503`, 2026-07-24:
  several `add_reply_to_pull_request_comment` calls immediately produced a
  webhook event attributed to `d-morrison` quoting the reply verbatim ---
  each one a self-echo, not a new human comment, confirmed by matching the
  body text before deciding to skip.)
- **A sustained run of `503` responses across every endpoint (not just PR
  reads) is a GitHub-side outage, not a per-call glitch — confirm with the
  cheapest possible probe, then stop retrying and back off.** When
  `pull_request_read`/`list_pull_requests` both 503, don't keep hammering the
  same call — call `mcp__github__get_me` (no arguments, smallest possible
  request) once: if that 503s too, it's a broad outage rather than something
  scoped to one repo, PR, or endpoint, and no amount of retrying the original
  call will help. Report the outage plainly, use whatever was last confirmed
  before it started, and re-check later rather than looping. (ai-config#583/
  #585 session, 2026-07-16: `pull_request_read`, `list_pull_requests`, and
  `get_me` all 503'd for roughly an hour across several separate check-ins;
  confirmed via `get_me` that it wasn't scoped to the two PRs being watched.)
- `mcp__github__pull_request_read` `method:` enum: `get` · `get_diff` (PR
  unified diff — equivalent to `gh pr diff`) · `get_status` · `get_files` ·
  `get_commits` · `get_review_comments` · `get_reviews` · `get_comments` ·
  `get_check_runs`.
- **`mcp__github__request_copilot_review` is a real, separate tool** (not a
  `pull_request_read` method) -- requests a Copilot code review on a PR,
  equivalent to `gh api .../requested_reviewers -X POST -f
  "reviewers[]=copilot-pull-request-reviewer[bot]"`. Verified directly
  against `github/github-mcp-server`'s own source
  (`pkg/github/copilot.go`'s `RequestCopilotReview`), registered in the
  **default** toolset (`pkg/github/tools.go`), not behind an opt-in flag --
  don't assume a tool is a hallucination just because it's absent from this
  file, which is a running collection of quirks encountered, not an
  exhaustive registry.
- **`get_status` can return "pending / 0 checks" even after CI has finished.**
  Use `get_check_runs` for the authoritative CI state — it returns the real
  job conclusions (`success`, `failure`, `skipped`). `get_status` aggregates
  across check suites and can lag or show a stale "pending" when all runs have
  actually completed; `get_status` is unreliable for CI state.
  (Hit during the ai-config #275 GII session — `get_status` showed
  `total_count: 0` / `pending` while `get_check_runs` correctly showed all 5
  checks `success`.)
  **Given this, don't call `get_status` at all when checking CI state** —
  go straight to `get_check_runs`; calling both in parallel "to be safe"
  just spends a call on a field you already know not to trust. (Repeated
  on `Lacaedemon/sparta` PR #780, 2026-07-12: called both in parallel to
  confirm a canceled-review race, when `get_check_runs` alone — or, when
  the incoming webhook event already names the failing commit's SHA, a
  single `pull_request_read` `get` compared against that SHA — would have
  settled it in one call. See
  [`efficient-pr-babysitting`](../shared/workflow/efficient-pr-babysitting.md).)
- **`gh pr view --json checks` is not a valid field.** When you need the
  combined status/check rollup from `gh pr view`, ask for `statusCheckRollup`
  instead; when you need the actual CI conclusions, use `gh pr checks` or the
  REST check-runs endpoint.
- **`mcp__github__push_files` strips executable bits** — files pushed via this
  tool always land with mode `100644`, regardless of their original mode. Scripts
  that were `100755` become non-executable. This is harmless when the workflow
  invokes them via `bash <script>` (not directly), but creates cosmetic
  inconsistency with sibling scripts. Workaround: fix the bit locally after
  merge with `chmod +x <script> && git add <script> && git commit -m "Restore executable bit"`. Track the deferred fix as a
  follow-up issue; don't block the PR on it. (Hit on `ucdavis/rampp#130` —
  both `reassign-reviewers.sh` and `stash-reviewers.sh` lost `100755`; tracked
  as `ucdavis/rampp#131`.)
- **When rewriting a file's full content via `push_files`, read the current
  file first and diff mentally.** Constructing the content from memory risks
  introducing typos or omitting lines — e.g. accidentally re-adding a
  previously-removed entry (`estiamnd` was re-introduced into `inst/WORDLIST`
  after being removed, requiring a correction commit). Always use
  `get_file_contents` to get the exact current content, then make the minimal
  targeted change before pushing.
- `mcp__github__pull_request_read` parameter names are **camelCase** — use
  `pullNumber`, NOT `pull_number`. Snake_case fails silently or errors.
- `mcp__github__add_issue_comment` parameter is **`issue_number`** (snake_case),
  NOT `issueNumber`. This is the opposite of `pull_request_read`. Reload the
  tool schema when unsure rather than guessing.
- **`mcp__github__issue_write` with `method: "update"` and a `body` param
  REPLACES the entire issue body -- it is not a way to post a comment.**
  Passing a short claim string like "Working on this" as `body` silently
  overwrites the full issue description with that one line; the call
  succeeds with no warning, since `update` genuinely means "set these
  fields," not "append." To post a comment, use
  `mcp__github__add_issue_comment` instead -- never pass `body` to
  `issue_write update` unless the actual intent is to edit/replace the
  issue's description. The tool's own result echoes back the (now-wrong)
  body, so the mistake is visible immediately if you check the response;
  fix it with a follow-up `issue_write update` call restoring the original
  text (keep a copy of the issue's existing body before editing it, since
  the tool's response only echoes the new state, not the prior one --
  or re-fetch it with `issue_read` `get` if you didn't), then post the
  actual comment via `add_issue_comment`. (Hit claiming
  `UCD-SERG/serocalculator#571` per the `claim-pr` convention: intended
  `add_issue_comment` but called `issue_write update` with just the claim
  text as `body`, clobbering the freshly-filed issue description --- caught
  immediately from the echoed response and fixed with a restore-then-comment
  pair of calls.)
- **`mcp__github__create_or_update_file`'s `content` param is raw plain text,
  not base64** — despite the GitHub REST API's own `PUT /repos/.../contents/`
  endpoint taking base64, this MCP tool does the encoding for you. Passing an
  already-encoded (or garbled-looking) string writes that literal string as the
  file body — it does not decode it first, and the call still reports success,
  so there's no error to catch the mistake. **Verify the write**: the response's
  `content.size` should roughly match the source text's byte length; a
  suspiciously small `size` (e.g. 113 bytes for a file that should be ~2700)
  means the wrong content shipped. Fix immediately with a follow-up
  `create_or_update_file` call using the new `sha` from the bad commit — don't
  leave a broken file on the branch waiting for the next review round to catch
  it. (Hit on lab-manual#376: an editing slip sent a truncated placeholder
  instead of the real fragment text; caught by checking the returned `size`.)
- **Issue *writes* 404 while *reads* succeed → the issue was transferred to
  another repo, not a permissions gap.** If `mcp__github__add_issue_comment` /
  `issue_write` to `owner/repo#<N>` fail (`404 Not Found`, or `Could not resolve
  to an Issue with the number of <N>`) but `issue_read` (`get`) on the *same*
  number succeeds and PR-comment writes work, suspect a **GitHub issue
  transfer**. A transfer redirects the old number for *reads* — `issue_read`
  silently follows the redirect and returns the issue at its NEW home, so check
  the returned `html_url`/`number` (they show a different repo/number). Writes to
  the old `owner/repo/issues/<N>` 404 because the issue no longer lives there.
  Fix: re-read to get the new repo + number, then comment/close *there*. Don't
  misdiagnose it as a missing `Issues:write` token scope. (Caught closing
  `gha#75`, transferred to `rme#941`.)
- **A pinned upstream commit SHA that 404s on the GitHub API can mean the
  whole repo moved orgs, not just a stale/rewritten pin.** `renv::restore()`
  (or any tool resolving a `Remotes:`-style GitHub pin) failing with a plain
  network-looking error (curl "error code 22" wrapping an HTTP error) on a
  commit-metadata fetch is easy to read as "transient" or "just re-pin to
  latest `main`." Before assuming that, check whether the source repo itself
  still exists at that path: fetch its `github.com` root page (not
  `api.github.com`, which a sandbox proxy may block for out-of-scope repos —
  use `WebFetch` on the plain `github.com/<owner>/<repo>` URL instead) and
  look for a "this repo has moved to `<new-owner>/<repo>`" redirect notice —
  some orgs (e.g. `insightsengineering`) replace a migrated repo's content
  entirely with a redirect stub and drop its git history, which orphans every
  previously-pinned commit SHA outright (a real 404, not a rate limit or
  blip). Fix by repointing the `Remotes:`/lockfile entry at the NEW org and a
  current commit there, not by re-snapshotting blindly (see the
  `renv::snapshot()` destructive-mistake entry below for why not) or assuming
  a simple re-pin to the old repo's `main` will work.
  (`d-morrison/rme#1017`: `insightsengineering/cards` had moved to
  `pharmaverse/cards`; the old repo was reduced to a redirect-only stub with
  history removed, orphaning the pinned SHA.)
- **WebFetch summarizes rendered page text through a small model, which can
  garble a long hex string (e.g. a 40-char git SHA) even when the source page
  is fetched correctly.** Don't trust a SHA read back from prose/rendered
  text alone — cross-check by asking WebFetch specifically for an anchor
  `href` containing the SHA as a URL path segment (e.g.
  `/owner/repo/commit/<sha>`), which is far less prone to transcription
  errors than reading digits out of rendered commit-page text, and repeat the
  fetch 2-3× to confirm the same value comes back consistently before using
  it in a commit/config change. (`d-morrison/rme#1017`: eyeballing a
  WebFetch-rendered SHA left doubt about its exact length at a glance; an
  href-based cross-check against the commit permalink URL, repeated across
  three independent fetches, confirmed the same 40-char value each time
  before it was used in the fix.)
- **In a fresh web/remote container, local `origin/*` refs can be stale or
  phantom — verify true remote state via MCP, not local refs.** The clone's
  `remotes/origin/main` may lag the real default branch by already-merged
  commits, and the harness-assigned `claude/<id>` branch can appear under
  `git branch -a` as `remotes/origin/claude/<id>` while not existing on the real
  remote (`get_file_contents` with `ref: refs/heads/claude/<id>` returns 404).
  `git fetch origin` (all refs) can also exceed the 2-min Bash limit on large
  repos with submodules (rme). To read the real default-branch HEAD cheaply,
  `get_file_contents` any file with no `ref` (= default branch) — the returned
  resource path embeds the live commit SHA. Fetch the single branch you need
  (`git fetch origin main`) and branch off that, so you don't build on a
  stale/polluted base.
- `mcp__github__pull_request_review_write` with `method: resolve_thread`
  requires **only `threadId`** (node ID, e.g. `PRRT_kwDO...`); `owner`,
  `repo`, and `pullNumber` are ignored for that method. Thread node IDs come
  from `get_review_comments`.
- **`mergeable_state` glossary — `unstable` is NOT a merge conflict.** GitHub's
  `pull_request_read` `get` returns `mergeable_state` alongside `mergeable`;
  the common values: `clean` (mergeable, all checks passing), `unstable`
  (mergeable, but some check is pending/failing — not blocking), `dirty` (real
  merge conflicts — this is the one that needs `git merge origin/main` +
  conflict resolution), `blocked` (a required check hasn't passed),
  `behind` (branch protection requires an update first). Only `dirty` means
  conflicts; `unstable` just means "wait for CI" and needs no merge action.
  (ai-config#373: `mergeable_state: unstable` right after a push was CI still
  running, not a conflict signal.)
- **`gh pr merge` can return "Head branch is out of date" even after syncing; verify with SHAs before looping, and re-establish fully-clean before retrying.** When this error repeats, first read the PR's actual base branch (`gh pr view <N> --json baseRefName -q .baseRefName`) — do **not** assume `main`; stacked and release PRs target a different base — then fetch and merge that base into the branch. Merging the base creates a new head SHA, which invalidates the CI/review "fully clean" snapshot that authorized the original merge attempt (a repo that doesn't make every workflow/review a required branch-protection check can otherwise merge an unreviewed/untested new head) — re-run the `fully-clean.md` check against the new SHA before retrying the merge, not just the merge command itself. If it still fails, don't compare against `origin` blindly: for a cross-fork PR, `origin` is the *base* repo, not necessarily where the head branch lives, so `git ls-remote origin refs/heads/<branch>` can silently read a missing ref or an unrelated same-named branch in the base repo. Get the actual head repo and ref from the PR API first (`gh pr view <N> --json headRepositoryOwner,headRepository,headRefName`), query *that* repo's ref (`gh api repos/<head-owner>/<head-repo>/git/refs/heads/<head-ref> --jq .object.sha` — verified this endpoint works), and compare it against the PR API's own `.head.sha` (`gh api repos/<o>/<r>/pulls/<N> --jq .head.sha`); the PR object can lag the branch ref briefly, so **wait** until the two SHAs agree rather than retrying. If branch protection still blocks the merge, only use `gh pr merge --admin` when the user has **separately and explicitly** authorized the bypass itself — ordinary merge authorization does **not** cover it (see `preferences.md`) — otherwise stop and surface it as a blocker.
- Webhook PR-activity events cover comments/reviews/CI *failures* but NOT CI
  *success*, new pushes, or merge-conflict transitions — don't rely on events
  alone to know a PR went green or merged; re-check explicitly.
- **A CI-failure webhook event's `HeadSHA` can be stale — compare it against
  the PR's actual current head before investigating.** Pushing a fix-up commit
  right after a bad one (e.g. correcting an encoding mistake seconds later)
  produces a cascade of failure events for every check on the now-superseded
  commit, arriving over the next several minutes as each job finishes. Check
  the event's `HeadSHA` field against the PR's live head (`pull_request_read`
  `get`, `.head.sha`) — if it doesn't match, the event is about a commit no
  one will ever see the result of; skip it with a one-line "stale, superseded"
  note instead of re-diagnosing content you've already fixed. (Hit on
  UCD-SERG/serodynamics#193: an accidental double-base64-encoded push
  triggered ~10 failure events across the whole CI matrix, all for the
  immediately-superseded commit.)
- **Self-wake to re-check CI in remote/web sessions.** Webhooks don't deliver CI
  *success*, new pushes, or merge transitions, so re-check on a timer. Prefer
  `CronCreate` (a harness scheduling tool, not an MCP tool): schedule a one-shot
  (`recurring: false`) or recurring (`recurring: true`) job whose prompt re-polls
  `mcp__github__pull_request_read` (`get_check_runs`) and acts on the result; it
  fires at wall-clock time without holding a background process. (Used to watch
  both PRs' merge transitions while migrating rme's preview workflows to the gha
  reusable family.) Fallback when `CronCreate` isn't available: arm a one-shot
  `Monitor` with `sleep <N>; echo recheck` and re-poll when it fires — the
  `Monitor` can't reach the GitHub API itself (no `gh`; the only git remote is a
  git-only proxy), so it's purely a timer, and foreground Bash `sleep` is
  blocked, which is why the background `Monitor` is the workable one. There is no
  `send_later` tool. Re-arm until the build goes green. Learned driving rme#929.
- **`mcp__Claude_Code_Remote__send_later` can become unavailable mid-session,
  not just absent from the start** (contrast the rme case above, where it was
  never present). Observed failure sequence: first a few transient "Tool
  permission stream closed before response received" errors (retrying the
  identical call sometimes still worked), then a hard "Error: No such tool
  available: mcp__Claude_Code_Remote__send_later" that no retry cleared.
  Fallback to `CronCreate` with `recurring: false`, pinned to a specific
  near-future cron time (compute it with `date`, since `CronCreate` takes an
  absolute cron expression, not a relative "N minutes from now" delay).
  **`CronCreate` jobs are session-only** — they die with the session, unlike
  `send_later`'s durable server-side triggers — so this is a degraded
  substitute, not an equivalent; say so rather than treating it as a full
  replacement. (gha#193 PR-babysitting session, 2026-07-03.)
- **`add_repo` refuses a cross-owner add once the session already has a repo from a
  different owner** ("cross-tier adds are not supported in v1: requested `<owner>/<repo>`
  but session already has repos from owner(s) `[...]`") — it does NOT fall back to a
  read-only or degraded mode, so a session scoped to e.g. `d-morrison/*` repos cannot add
  a `UCD-SERG/*` repo (or vice versa) no matter how the request is phrased. When a task
  needs to read a PR/issue in such an out-of-scope repo, don't stop at the `add_repo`
  failure or a raw `api.github.com` 403 (a plain `WebFetch` GET to
  `api.github.com/repos/.../issues/comments/<id>` for a public repo 403'd with no body —
  exact cause unconfirmed; `WebFetch` isn't threaded through the GitHub MCP session's own
  auth, so this isn't necessarily the same failure mode as a scoped/cross-owner API call,
  and GitHub's REST API does generally allow unauthenticated reads of public repos at a
  lower rate limit, so don't over-generalize from this one data point) — try `WebFetch`
  on the **rendered** `https://github.com/<owner>/<repo>/pull/<N>`
  (or `/issues/<N>`) page instead. For a public repo this reliably returns the PR/issue
  title, state, and recent comment/review content (works even for reading a *specific*
  comment by its anchor), succeeding where both the MCP tool and the JSON API failed.
  (Used to read UCD-SERG/serodynamics#193's `@claude`-bot comment from a
  `d-morrison/gha`-scoped session, which surfaced the root cause fixed in gha#191.)
- **`add_repo` (and likely other approval-gated MCP tools) can fail repeatedly
  and silently under auto-mode, with no useful error.** In auto mode, a call
  that needs an interactive permission-dialog approval has no human present to
  click it, so it errors `Streamable HTTP error: Error POSTing to endpoint:
  MCP tool call requires approval` — identical on every retry, giving no
  signal that the real blocker is "no one is watching to approve this."
  Retrying the same call in auto mode doesn't help. The fix is to have the
  user switch to a non-auto permission mode (e.g. accept-edits) so there's
  someone to grant it, then retry once — it then either succeeds outright or
  fails with a real, actionable error (e.g. `add_repo`'s cross-tier-owner
  refusal, above). Don't burn more than one or two identical retries in auto
  mode before flagging this to the user. (gha#204 session, 2026-07-03: `rme`
  succeeded immediately after the user switched modes; `epi204`/`epi202` then
  failed with the real cross-tier error instead.)
- `d-morrison/gha`'s `CLAUDE.md` carries its own `gh`->MCP substitution table
  (the "GitHub access in remote / web sessions" section), scoped to that repo.
  `d-morrison/ai-config` has its own cross-model registry at
  [`tool-mappings.md`](../tool-mappings.md) (generated from `tool-mappings.yml`),
  which ai-config skills can point to directly — see `CLAUDE.md`'s "Skills that
  call gh/glab" section. When a skill or doc in a **different** repo (one with
  neither table) tells a reader to "use the GitHub MCP tools," name the tools by
  example (`mcp__github__add_issue_comment`, `mcp__github__create_pull_request`,
  `mcp__github__search_pull_requests`) rather than pointing at a `CLAUDE.md`
  mapping table that repo doesn't have — that cross-reference resolves only
  where the table actually lives. (Caught in ai-config#137 review: the gip
  skill referenced a table ai-config didn't have at the time; ai-config#327
  later added `tool-mappings.md` to close that gap.)

## GII (Grab Issues Iteratively) — startup cleanup sweep

When starting a GII loop, do a cleanup pass before diving into ARDI:

1. **List all open PRs** with `mcp__github__list_pull_requests`. Look for
   stale bot-opened PRs that target the same issues as the queue.
2. **Close empty PRs** — bot-opened branches with no commits (e.g. a `@claude`
   task run that posted a comment but never pushed code). Check `get_commits`
   on each PR before closing.
3. **Identify the canonical PR** for each in-flight issue. Superseded drafts
   should be closed with a note pointing to the canonical one.
4. **Collapse stacked changes** — if two open PRs address the same issue or
   have a causal dependency (one builds on the other), merge one branch into
   the other before starting ARDI, so the reviewer evaluates the combined diff.

Skipping this sweep leads to confusion: multiple PRs for the same issue,
closed-issue references in multiple PR bodies, and stacking conflicts mid-ARDI.
(Learned from the ai-config #275 / #272 / #265 / #266 cleanup pass.)

## Git tags (force-move / slide)
- To move a tag to a new commit: `git tag -d <tag> && git tag <tag> <target> && git push origin :refs/tags/<tag> && git push origin <tag>`
- Can't use `git push --force origin <tag>` on some GitLab instances (protected tags). The delete+recreate pattern always works.
- `git fetch --tags` silently refuses to update a local tag that already exists if the remote moved it. Use `git fetch --tags --force` to get the latest remote tag positions. Without `--force`, you'll see stale local tags and draw wrong conclusions about what the tag includes.

## Git — bump a submodule pin without initializing it
- To advance a submodule pointer when the submodule isn't checked out (common in
  a remote/web session, where the configured submodule URL may be unreachable
  from the sandbox), update the gitlink directly in the index:
  `git update-index --cacheinfo 160000,<full-sha>,<path>`, then commit and push.
  Clones and CI resolve the new SHA from the submodule's own remote.
- The `<full-sha>` must already exist on the submodule's remote, so push or merge
  it there first or clones can't resolve the pin.
- `git diff --cached --submodule=log` reports the change as `Submodule <path>
  <old>...<new> (commits not present)`. The "commits not present" note just means
  the submodule isn't checked out locally; it is not an error.
- This is the manual form of what lab-manual's `bump-ai-config.yml` and gha's
  `bump-submodule` workflows do automatically. Use it for a one-off bump (e.g.
  lab-manual#338 picked up an ai-config reprexes fix this way).
- **Verify additive-only before bumping**, especially when the bump PR itself
  won't adopt the new content: `git -C <submodule> diff <old-sha>..<new-sha> --
  <file>` and confirm no `^-` lines (removed/changed) — only `^+` additions.
  An additive-only diff means the bump can't break any existing render/usage,
  which is worth stating explicitly in the bump PR body as the safety argument.
- **Bump-then-adopt sequencing when the consumer isn't on `main` yet.** If a
  submodule bump adds macros/content meant for files that only exist on an
  *unmerged* content PR branch (not yet on `main`), the bump itself must still
  be scoped to a `main`-based branch — you can't adopt the new macros in the
  same PR, because those consuming files aren't there to edit. Split into two
  PRs: (1) the bump alone (safe, additive, mergeable now), and (2) an adoption
  follow-up filed as a tracked issue, scoped to run **after** the content PR
  merges and those files land on `main`. Don't try to do both in one PR just
  because they're conceptually related — the file-existence dependency forces
  the split. (rme #976 bumped `latex-macros`; the `\ppi`/`\opi` adoption in the
  marginal-risk content was deferred to #977 because those `.qmd` files were
  still only on the unmerged #706.)

## Git — scanning for parallel/in-flight work
- A remote-only scan (`git branch -r`) **misses** work a parallel CLI session is
  building in an **unpushed local worktree** — the branch exists only locally
  until that session pushes. Hit PR #67: a sibling skill was caught by a stray
  system-reminder, not the scan.
- To find all in-flight work before starting (skill-builder Step 0, deconflict,
  scout-peers, etc.), run two scans: `git branch -a` for local + remote refs
  (catches committed-but-unpushed local branches), and the `git worktree list`
  working trees for *untracked* files that never reached any ref
  (`git -C <wt> ls-files --others --exclude-standard -- 'skills/'`).

## Git — looking up a PR's branch name
- `git branch -r` lists **all** remote branches — useless for finding a specific PR's branch: it has no way to filter by PR number. Don't suggest it as a fallback.
- Targeted lookup: `gh pr view <N> --json headRefName -q .headRefName` in CLI sessions;
  `mcp__github__pull_request_read` with `method: get` in remote/web sessions.
- Flagged on ai-config#186: the first draft of the harness-override instruction included
  `git branch -r` as the fallback; reviewer (claude-review bot) caught it.

## Git branch create/reset (`git switch -C`)
- `git switch -C "$BRANCH"` is already safe against flag-shaped branch names: `$BRANCH` is the argument *to* `-C`, so a value like `--weird` fails cleanly as `fatal: '--weird' is not a valid branch name` rather than being parsed as an option.
- Do NOT "harden" it to `git switch -C -- "$BRANCH"` — that form is **broken**: the `--` is consumed as the branch name (the required argument to `-C`), so `$BRANCH` is parsed as the start-point instead and the command fails without creating the branch. (Verified on git 2.x; a review bot suggested the broken form on d-morrison/gha#58.)

## Git — `gh pr merge --delete-branch` can orphan a stacked PR instead of retargeting it
- GitHub's docs promise automatic retargeting: "If you delete a head branch
  after its pull request has been merged, GitHub checks for any open pull
  requests in the same repository that specify the deleted branch as their
  base branch. GitHub automatically updates any such pull requests, changing
  their base branch to the merged pull request's base branch."
- In practice (Lacaedemon/sparta, 2026-07-01), `gh pr merge <N> --squash
  --delete-branch` did NOT retarget a stacked PR onto the new base — it
  auto-**closed** the stacked PR instead. Root cause unconfirmed (possibly a
  timing/API-path difference between `gh`'s post-merge branch deletion and the
  web UI's "Delete branch" button the docs describe) — but the failure mode is
  reproducible enough to plan around regardless of cause.
- **Before running `gh pr merge <N> --delete-branch`**, check whether another
  open PR uses that branch as its base: `gh pr list --base <branch-name>`. If
  one does, omit `--delete-branch` (merge without it, or delete manually
  afterward once you've confirmed the stacked PR retargeted cleanly).
- **Recovery when it happens anyway:** the *head* branch of the closed PR
  usually still exists (only the deleted *base* branch is gone) —
  `gh pr reopen` fails once the base is gone, so instead open a **new** PR
  from that same head branch targeting `main` (or whatever the new
  grandparent base is), note in the body that it supersedes the closed PR
  number with identical commits, and comment on the closed PR linking the
  replacement.
- **When run from a worktree/checkout that's currently on the branch being
  merged, `gh pr merge --delete-branch` also switches that checkout to the
  default branch and fast-forwards it, and deletes the now-merged local
  branch** — a normal, convenient side effect, not a bug. Don't follow it
  with the usual post-merge `git checkout main && git pull && git branch -d
  <branch>` sequence on autopilot: the checkout is already on `main` and
  up to date, and `git branch -d <branch>` errors `branch '<branch>' not
  found` since `gh` already deleted it. Check `git branch --show-current`
  first before running any of those.

## Git — renaming an open PR's *head* branch can close the PR (no reopen)

`gh api -X POST repos/{owner}/{repo}/branches/{branch}/rename` (or the web UI
"Rename branch") on a branch that is the **head** of an open PR **can close**
that PR. GitHub's documented behavior is to auto-update a PR's head ref when its
branch is renamed and keep the PR open, but this has been observed to fail: the
PR closed and could not be reopened — `gh pr reopen` returns `GraphQL: Could not
open the pull request. (reopenPullRequest)`. Whether that's an edge case
(timing, an older API, an Enterprise instance) or the head ref not surviving the
rename, treat a head-branch rename as something that **may** close the PR.

Branch-rename **does** reliably retarget PRs whose **base** is the renamed
branch; the head-branch case is the risky one.

**How to apply:** don't rename a branch backing an open PR just to fix a
misleading name. Live with the name (explain it in the PR body), or accept
you'll open a replacement PR — rename, immediately open a new PR from the new
branch, say "Supersedes #N", and comment on the closed PR pointing forward.
(Hit on `ucdavis/bcs` 2026-07-09: renaming `fix/msm-competing-risks-324` to a
name that no longer asserted a refuted diagnosis closed PR #326, replaced
by #328.)

## Git — `worktree add` does not cd into the new worktree
- `git worktree add <path> <ref>` creates the worktree at `<path>` but leaves the
  shell in the **original** checkout. Subsequent bare git commands (`git checkout`,
  `git merge`, etc.) run against the original checkout, not the new worktree.
- Always follow `git worktree add <path> …` with `cd <path>` before any further
  git work inside that worktree.
- When creating a worktree to fix a **conflict caused by a squash-merge on main**,
  `git fetch origin main <branch>` (both refs) **before** `git worktree add` so
  the squash commit is present when you merge. Fetching only the PR branch leaves
  origin/main stale and the merge won't pick up the commit that caused the conflict.

## Git — removing a worktree that contains a submodule
- `git worktree remove <path>` **fails** on a worktree that has an initialized
  submodule: `fatal: working trees containing submodules cannot be moved or
  removed`. Many repos with a vendored `.ai-config` submodule hit this after a
  feature branch merges.
- Fix: `git worktree remove --force <path>` removes it cleanly. (Plain `--force`
  is enough; the submodule warning is the only blocker.) If the dir somehow
  lingers, `rm -rf <path> && git worktree prune` finishes the cleanup.
- The branch can't be deleted while the worktree still references it
  (`error: cannot delete branch '…' used by worktree at '…'`), so remove the
  worktree **first**, then `git branch -D <branch>`.

## Git (Windows) — `worktree remove` on your own cwd partially fails, leaving an orphaned unregistered directory that silently falls through to the parent repo
- `git worktree remove <path>` on a `<path>` that is the **current process's cwd**
  fails on Windows with `error: failed to delete '<path>': Permission denied` —
  Windows won't let you delete a directory a running process has open as its
  working directory. That failure is not clean/atomic: git had already
  unregistered the worktree (removed it from `git worktree list` and deleted
  the checked-out files) before the final `rmdir` step failed, so the
  directory is left **empty and unregistered** rather than restored to its
  prior working state.
- **The dangerous part:** an empty, unregistered directory nested under the
  main repo (e.g. `.claude/worktrees/<name>/`) is not an error state as far as
  git commands are concerned — `git status`/`git log`/`git pull` etc. run from
  inside it just walk up to the parent directory, find `../../.git` there, and
  silently operate on the **main repo's checkout and branch** instead of
  erroring. Nothing points out that you're no longer in an isolated worktree;
  a `git pull --ff-only` there quietly fast-forwards the main checkout instead
  of failing.
- **Detect it** with `git rev-parse --show-toplevel` (or `--git-dir`) — if the
  path it prints is the **parent** repo rather than the worktree path itself,
  you've hit this. `git worktree list` run from the parent repo also won't
  list the directory. (Same failure signature as a worktree that was simply
  never registered in the first place, e.g. because a harness only prepared
  the directory but never actually ran `git worktree add` — check this first
  before assuming any work was corrupted.)
- **Fix** by re-registering in place: `git -C <parent-repo> worktree add
  <same-path> [-b <branch>] <base-ref>` — safe to run even though the
  directory already exists, as long as it's empty (which it will be, since
  the failed removal already deleted its contents).
- Avoid triggering this at all: don't call `git worktree remove` on a path
  that's your own cwd. `cd` out to the parent repo (or a sibling worktree)
  first, *then* remove.

## Git — `checkout -B` in a linked worktree silently bypasses the already-checked-out guard
- Plain `git checkout main` in a linked worktree correctly refuses when `main`
  is checked out in the primary (or any other) worktree: `fatal: 'main' is
  already used by worktree at …`. `git checkout -B main origin/main` does
  **not** refuse — the reset-and-checkout form re-points the shared branch ref
  and checks it out in the current worktree anyway, leaving **two** worktrees
  both claiming `[main]` in `git worktree list`.
- The damage lands one command later: a `git pull` in the second worktree moves
  the shared ref out from under the first worktree's working tree — HEAD
  advances while that worktree's index and files stay at the old commit, so
  `git status` there shows index-vs-HEAD as phantom **staged** diffs, with no
  error anywhere. In the primary worktree this reads as the just-merged PR's
  changes staged in reverse, as if about to commit a full revert of it.
- The scripted fallback is how it happens in practice:
  `git checkout -q main 2>/dev/null || git checkout -qB main origin/main` —
  the plain form refuses (silenced by `-q`/`2>/dev/null`), the fallback
  "succeeds".
- **Recovery:** move the offending worktree onto a new branch
  (`git switch -c <next-branch>` — frees the ref), then in the other worktree
  restore **only** the phantom-diff files
  (`git restore --staged --worktree <files>`) — not a blanket `reset --hard`,
  which clobbers unrelated local state (e.g. a dirty submodule pointer).
- **Prevention:** in a session/linked worktree, never "return to main" after a
  merge — branch the next task directly off the remote
  (`git switch -c <branch> origin/main`) and leave `main` itself to the
  primary checkout. To advance the local `main` ref without checking it out
  (CLAUDE.md § "Keep ai-config and repo checkouts fresh" recommends this when
  a single checkout sits on a feature branch), `git branch -f main
  origin/main` is the safe form to *attempt* — not because the guard never
  fires, but because it **fails closed**: when any worktree holds `main` it
  hard-refuses (`fatal: cannot force update the branch 'main' checked out
  at …`, verified empirically) instead of silently double-checking-out the
  way `checkout -B` does; in that multi-worktree case, leave updating `main`
  to the worktree that holds it. (Hit on `Lacaedemon/sparta`, 2026-07-16: a
  post-merge tidy ran the fallback form inside a session worktree; the
  primary showed nine phantom staged reversals of the just-merged PR until
  restored.)

## Git — if a target branch is already checked out in another worktree, push by refspec instead of switching
- Attempting to `checkout` a branch already active elsewhere fails with
  `fatal: '<branch>' is already used by worktree at ...`.
- When you need to land your current commit on that branch (for example, to
  update an existing PR branch), avoid switching branches: push your current
  HEAD directly to the target remote branch with
  `git push "<remote>" HEAD:"<target-branch>"`. Note that this pushes **all commits
  reachable from HEAD**, not just your latest one; before pushing, verify the
  outgoing range is safe — the target branch should be an ancestor of HEAD
  (`git merge-base --is-ancestor "<target-branch-tip>" HEAD`), and there should be
  no unrelated commits between them — to avoid advancing the PR branch beyond
  what you intended. Don't hard-code `origin` without
  checking: in a fork/multi-remote setup, `origin` may be your own fork while
  the existing PR's head branch lives on a different remote (e.g.
  `upstream`), so pushing to `origin` silently creates/advances a same-named
  branch there instead of updating the intended PR. Confirm which remote
  actually owns the PR's head (`git remote -v`, or match the PR's
  `head.repo` from `gh pr view "<N>" --json headRepositoryOwner,headRepository`)
  before picking the refspec's remote.
- This avoids clobber-prone workarounds (`checkout -B`) and avoids opening a
  new sibling PR by mistake.

## Git — `merge --continue` takes no arguments
- `git merge --continue --no-edit` fails with `fatal: --continue expects no arguments`.
- After resolving conflicts and staging (`git add <files>`), use `git merge --continue` alone.
- In a non-interactive (headless) session git uses the auto-generated merge commit message without prompting — no editor opens.

## Git merge — uncommitted edits to an untouched file silently ride along, uncommitted, through repeated merges
- `git merge <branch>` only refuses when the incoming branch's commits touch a
  file you also have uncommitted changes to. If the incoming commits don't
  touch that file, the merge succeeds and your uncommitted edit is left
  exactly as it was --- still uncommitted, sitting on top of the new merge
  commit. Repeat the pattern (merge again while the edit is still
  uncommitted, e.g. reconciling with a remote branch another actor pushed to)
  and it survives through multiple merge commits without ever landing in one.
- This is easy to miss because `grep`/`cat` against the **working tree** shows
  the fix is present, creating false confidence that it's committed. Verify
  against the actual commit instead: `git show HEAD:<path>` (or `git status
  --short` for a stray `M`), not a plain file read, before pushing and
  declaring a review finding addressed.
- Fix: commit the edit (`git add <path> && git commit`) as its own step
  **before** merging anything else in, not after. (Hit on ai-config#461: a
  one-line prose fix sat uncommitted through two merge commits — one merging
  `origin/main` in, one reconciling with a bot's competing push to the same
  branch — so what got pushed both times still had the pre-fix text, and a
  review correctly re-flagged it as unaddressed after an incorrect "addressed"
  reply.)

## Git stash — verify supersession line-by-line, tag before dropping
- Before dropping a stash as "already landed", verify against `origin/main`,
  not by eyeball: extract the stash's added lines
  (`git stash show -p 'stash@{0}' | grep '^+[^+]'` — the `[^+]` keeps the
  `+++ b/<path>` diff headers out of the set, where they'd read as spurious
  "missing from main" lines) and `grep -F` each one in
  main's version of the file; for files the stash *creates*, check
  `git cat-file -e origin/main:<path>`. A line that matches on topic but not
  verbatim usually means main carries the **improved** review-cycle revision —
  read both and confirm main's is a superset before calling it superseded.
- `git stash show -p` **omits the untracked-files component.** Check
  `git show 'stash@{0}^3'` (that parent exists only if the stash was made with
  `-u`) before judging supersession.
- `git stash drop` is irreversible, and Claude Code's auto-mode classifier
  blocks it for exactly that reason — sometimes even after a general "do the
  cleanup" go-ahead, when the stash is large. Don't fight it: run
  `git tag backup/stash-<topic> 'stash@{0}'` first. The stash commit stays
  reachable, the drop becomes genuinely reversible (recover with
  `git stash apply backup/stash-<topic>`), and the retried drop passes. Tell
  the user the tag exists; remove it with `git tag -d backup/stash-<topic>`
  once confident.

## GitLab Discussions API (inline diff comments)
- Endpoint: `POST /projects/:id/merge_requests/:iid/discussions`
- For inline comments, include `position` object: `position_type: "text"`, `base_sha`, `head_sha`, `start_sha`, `new_path`, `old_path`, `new_line`
- Get SHAs from MR Versions API: `GET /projects/:id/merge_requests/:iid/versions` → `[0].base_commit_sha`, `[0].head_commit_sha`, `[0].start_commit_sha`
- If the position is rejected (e.g., line not in diff), the API returns 400 — handle gracefully

## glab (GitLab CLI)
- Installed via Homebrew (macOS) or system package manager — verify with `which glab`.
- Authenticated on your GitLab instance — run `glab auth status` to verify host and username
- Use for MR comments, pipeline checks, CI job logs, etc.
- `glab issue list --opened` is deprecated — `--opened` is the default when `--closed` is not used. Just use `glab issue list` (no flag needed).
- No `GITLAB_TOKEN` env var — glab uses its own config at `~/Library/Application Support/glab-cli/config.yml`
- Key commands:
  - `glab ci list` — list pipelines
  - `glab ci get --pipeline-id <ID>` — view pipeline details (non-interactive)
  - `glab ci create --branch <branch>` — trigger a NEW pipeline (picks up upstream template changes)
  - `glab ci retry --branch <branch>` — retries the EXISTING pipeline (does NOT pick up template changes)
  - `glab ci view <id>` — requires TTY; use `glab ci get` or `glab api .../trace` instead
  - `glab api "/projects/<ID>/jobs/<JOB_ID>/trace"` — get job log non-interactively
  - `glab mr note create <MR_IID> --message "..."` — post MR comment
  - `glab mr list` — list merge requests
  - `glab mr view <MR_IID>` — view MR details
- GitLab CI job token allowlist:
  - When repo A's CI job needs API access to repo B, repo B must add A to its allowlist
  - `glab api --method POST "/projects/<TARGET_ID>/job_token_scope/allowlist" -f "target_project_id=<SOURCE_ID>"`
  - `include:` (for CI templates) works independently of the API allowlist
  - Check existing: `glab api "/projects/<ID>/job_token_scope/allowlist"`

## Julia in Claude Code cloud / web sessions
- To install Julia, prefer downloading the official binary tarball from
  `julialang-s3.julialang.org` via `curl` (system CA store) over `juliaup`:
  juliaup's rustls HTTP client rejects TLS-intercepting proxies common in cloud
  environments, so it can fail even when the host is allowlisted. Prebuilt Linux
  Julia binaries live ONLY on `julialang-s3.julialang.org` — the
  `JuliaLang/julia` GitHub releases attach source tarballs only. `Pkg`
  operations need `pkg.julialang.org` allowlisted too.
- Reference implementation: `references/cloud-setup/cloud-setup.sh` in ai-config
  (curl+tarball, `$SUDO`-aware, best-effort/non-fatal).
- Layering: the build-time **Setup script** is the right place for slow,
  repo-independent toolchain installs (R, Julia, Quarto); the **SessionStart
  hook** is for repo-dependent per-session work (`renv::restore`,
  `Pkg.instantiate`). BUT the build-time Setup script can't be committed to a
  repo (it's pasted into the web UI), so a SessionStart hook is the only
  in-repo lever to auto-install a toolchain for *that repo's own* sessions.

## R / Quarto (rme etc.) in Claude Code cloud / web sessions
- The renv library is NOT provisioned at session start (`requireNamespace`
  returns FALSE for lintr/spelling/rmarkdown). `renv::restore()` from the
  lockfile's CRAN *source* repo is slow. Instead install only what a given
  chapter needs, from BINARY repos:
  - CRAN pkgs → P3M binaries:
    `options(repos = c(P3M = "https://packagemanager.posit.co/cran/__linux__/noble/latest"))`
    then `install.packages(...)` (installs into the active renv library; fast).
  - To restore the WHOLE lockfile (when you don't know which pkgs a render
    pulls in), point renv itself at P3M binaries instead of hand-picking:
    `Sys.setenv(RENV_CONFIG_PPM_ENABLED = "TRUE")` (or
    `options(renv.config.ppm.enabled = TRUE)`) + P3M `repos`, then
    `renv::restore(prompt = FALSE)`. Observed on rme: ~264 pkgs in ~5 min
    (mostly cache-linked binaries; a few like glmmTMB still build from source).
    A plain source-repo `renv::restore()` times out — enabling P3M is what
    makes the full restore feasible. knitr/rmarkdown must be present for
    `quarto render` to even start the knitr engine (`--no-execute` does NOT
    skip the engine check), so a full restore is the surest path when an edit
    needs a real render.
  - **This isn't rme-specific — check any R-package repo's own CI YAML for a
    `RENV_CONFIG_REPOS_OVERRIDE` / RSPM env var before running
    `renv::restore()` interactively, and set the same one yourself.** The CI
    workflow's `env:` block does NOT propagate to a bare `Rscript -e
    'renv::restore(...)'` you launch by hand — it's just an unset env var in
    your session — so skipping this replicates the "plain source-repo restore
    times out" trap even on a repo whose own CI already solved it. Confirmed on
    ucdavis/bcs: an interactive `renv::restore(prompt = FALSE)` with no P3M
    override spent 40+ minutes compiling `arrow` from source alone (out of
    267 packages), when `R-CMD-check.yaml`'s own
    `RENV_CONFIG_REPOS_OVERRIDE: https://packagemanager.posit.co/cran/__linux__/noble/latest`
    was sitting right there in the workflow file the whole time.
  - d-morrison GitHub-only pkgs → r-universe `https://d-morrison.r-universe.dev`
    has `dobson`, `regress3d` (and more), but NOT `rmb` — and `rmb`'s standard
    install channels (tarball/clone via `github.com`/`codeload`, plus
    `api.github.com` for renv/pak) are proxy-blocked when the repo isn't in
    session scope. That no longer blocks renders of chapters that do
    `rmb::hers` / `library(rmb)`: see the "Scope-blocked GitHub repo, but you
    only need its *datasets*" bullet in this file for the data-only rebuild
    from `raw.githubusercontent.com` (which stays reachable).
  - `igraph` needs system lib `libglpk.so.40` → `apt-get install -y libglpk40`
    (you're root in these containers). Needed to run `data-raw/callout-graph.R`.
  - The install routes through **pak** (renv's pak backend), which is ATOMIC:
    if ONE requested pkg is unavailable (e.g. rmb), the WHOLE transaction rolls
    back and nothing installs — drop the unavailable pkg and retry. (Holds for
    `pak::pkg_install()`, and for `install.packages()` while renv's pak backend
    is active; base `install.packages()` on its own is NOT atomic.)
  - The **`renv` autoloader can shadow a system-library install.** If you
    `install.packages()` a Suggests-only tool (e.g. `lintr`, `spelling`) into the
    *default* libPaths rather than the active renv library, `Rscript` run from the
    repo root STILL fails with "no package called 'lintr'" — the project
    `.Rprofile` autoloader resets `.libPaths()` to the renv library on startup.
    Either install into the renv library (the P3M path above), or run the one-off
    with the autoloader off:
    `RENV_CONFIG_AUTOLOADER_ENABLED=FALSE Rscript -e 'lintr::lint("path/to/file.qmd")'`.
    (Used to lint the changed files for rme #873 when lintr wasn't in the renv lib.)
- **When the container's R is a brand-new release P3M hasn't built binaries for
  yet** (e.g. R 4.6.1 in mid-2026), `install.packages()` from P3M silently falls
  back to **source**, and heavy pkgs (DT → sass, etc.) fail or time out — so a
  full HTML `quarto render` (needs knitr/DT/rmarkdown) isn't feasible locally.
  Two mitigations: (1) replicate just the **build-breaking check in base R**
  (e.g. a Quarto page's `stop()`-on-missing-data guard) — base R needs no
  install; (2) `quarto install tinytex` **does** work, so validate the LaTeX/PDF
  paths locally with lualatex (`quarto render <f>.qmd --to pdf`) even when the
  HTML render is blocked. Let CI do the authoritative HTML render. (macros#71:
  DT/knitr uninstallable, but a base-R interpretation-completeness check + a
  lualatex PDF render of the new macros validated the change before push.)
  **Before accepting "uninstallable," try `install.packages()` straight from a
  source CRAN mirror** (`options(repos = c(CRAN = "https://cloud.r-project.org"));
  install.packages(c("knitr", "rmarkdown", "DT"))`, no P3M) — it builds sass/DT
  etc. from source and can succeed in a few minutes even when P3M's binary
  fallback fails, unlocking the full local HTML render instead of falling back
  to the base-R/PDF-only mitigations above. Why CRAN-direct can succeed where
  P3M's source fallback doesn't isn't confirmed — both ultimately build the same
  source tarball, so the difference is more likely P3M's build sandbox (timeout
  or resource limits) than a real incompatibility; note the actual mechanism
  here if a future session pins it down. (macros#74: same class of container,
  but a plain-CRAN source install of knitr/rmarkdown/DT succeeded, letting all
  three of `CONTRIBUTING.md`'s documented renders — both PDF demos and the full
  HTML site — run locally before push.)
- **A fresh `git worktree` gets its own renv library cache, keyed by the
  worktree's absolute path** (`/root/.cache/R/renv/library/<repo>-<worktree-dirname>-<hash>/...`),
  separate from the main checkout's already-populated cache. Its own
  `renv::restore()` can fail to bootstrap for the same reasons as a fresh
  session — a renamed GitHub repo in `Remotes:`, P3M binaries not yet built
  for a brand-new R release (see the bullets above and below), or renv's own
  live GitHub-API resolution of `Remotes:` (unset `RENV_CONFIG_INSTALL_REMOTES`
  defaults to `TRUE`, so `renv::restore()`/activation hits `api.github.com`
  even though the actual package versions installed come entirely from
  `renv.lock`'s pinned SHAs; set `RENV_CONFIG_INSTALL_REMOTES=false` to skip
  that network dependency) — so `quarto render` inside the worktree errors
  with "the knitr package is not available" even though the SAME package is
  installed and working in the main checkout. **Don't force the local render
  through this** — push, let CI's `build`/`quarto render` job do the real
  render (it already has the right env vars and a working cache), then verify
  the rendered output by fetching the PR-preview HTML straight from the
  `gh-pages` branch: `mcp__github__get_file_contents` with
  `path: pr-preview/pr-<N>/<chapter>.html`, `ref: refs/heads/gh-pages` returned
  the file, in one observed session, **base64-decoded already** (not raw
  base64) as a `[{type,text}, {type,text}]` array with the actual HTML in the
  second element — write it to a scratch file (Python `json.load` + write
  `data[1]['text']`) and `grep`/`Read` it to confirm cross-refs resolved (no
  literal `?@id` or `**id?**` text), computed values match your derivation,
  and new callout/div structure rendered as intended. This exact array shape
  is an observed harness behavior, not a documented contract — if
  `data[1]['text']` is missing or isn't HTML, `cat`/`head` the saved file to
  see its actual structure (try `data[0]['text']` next) rather than assuming
  the recipe is wrong. This is strictly more reliable than fighting the
  worktree's renv bootstrap, and it's what actually caught a real structural
  bug — a stray `---` left next to a `{{< slidebreak >}}` rendering a
  spurious `<hr>` in every non-`revealjs` Quarto profile, invisible from
  reading the `.qmd` source alone — that a purely-local read wouldn't have
  surfaced. (`d-morrison/rme#1009`, several rounds: a background
  `renv::restore()` in `/tmp/rme-<issue>-worktree` sat at "renv installed,
  nothing else" after the worktree was removed and re-created at the same
  path — verified the actual chapter content instead via this gh-pages
  fetch, twice, once per structural fix.)
- **A `renv::restore()` failure downloading `https://api.github.com/repos/<owner>/<repo>/...`
  with `error code 22` can mean the GitHub-pinned `Remotes:` package was
  renamed/transferred, not a transient network blip.** `insightsengineering/cardx`
  moved to `pharmaverse/cardx`; GitHub's rename redirect doesn't reliably resolve
  for the specific REST endpoints `renv::restore()` hits, so every restore under
  the old owner fails identically and repeatedly — check actual job logs each
  time rather than assuming "the same infra flakiness as before" (a failure that
  looks recurring can still be worth re-diagnosing once; this one turned out to
  have a real, fixable root cause). `RENV_CONFIG_INSTALL_REMOTES=false` (see the
  worktree bullet above) sidesteps it entirely, since the actual installed
  versions come from `renv.lock`'s pinned SHAs regardless of where `Remotes:`
  points. (`d-morrison/rme#772`, tracked in `d-morrison/rme#994` and `d-morrison/rme#996`, fixed centrally in
  `d-morrison/gha#241`.)
- **R in these containers defaults to the `C` locale**, so
  `read.delim(..., fileEncoding="UTF-8")` (or any read) of a file with multibyte
  chars (π, μ, ℓ, …) **silently truncates at the first non-ASCII byte**, emitting
  only an `invalid input found on input connection` warning — you get a few rows,
  not all, and a completeness check then reports bogus "missing" rows. Run R with
  `LANG=C.UTF-8 LC_ALL=C.UTF-8 Rscript …` to read UTF-8 data files correctly.
  (CI runners are UTF-8, so this bites only locally.)
- **renv activation failure when a GitHub remote is blocked**: if `DESCRIPTION`
  lists a GitHub `Remotes:` entry for a repo the session's git proxy hasn't
  scoped in, renv activation (via `.Rprofile`) aborts on startup — every
  subsequent `R` call errors before loading any package (e.g. bcs's
  `d-morrison/altdoc@recursive-qmd-search`: a plain `curl` to
  `api.github.com/repos/d-morrison/altdoc/...` 403'd with `"GitHub access to
  this repository is not enabled for this session. Use add_repo to request
  access."` — this is the *session repo-scope* check, not a general network
  block; the same 403 hits `renv`/`pak`'s own `api.github.com` calls even
  though they never go through an MCP tool).
  Quick bypass (when you just need *a* working R session, not to fix the
  remote): `R --no-save --no-restore --no-site-file --no-init-file` skips
  `.Rprofile` entirely; install needed packages from P3M into the user
  library and proceed.
  **Real fix, when the remote itself is wrong or you need the full
  dependency tree:** call `add_repo` for the blocked owner/repo — this
  unblocks the proxy's direct HTTPS access (curl, `renv::restore()`,
  `pak`), not just the GitHub MCP tools, so **no local clone is needed**
  just to resolve dependencies (ignore `add_repo`'s "clone it now"
  instructions unless you actually need the repo's file contents). Then
  check whether the pinned non-default branch has already merged into the
  remote repo's default branch — `curl .../compare/main...<branch>` and
  read `ahead_by`/`behind_by`; `behind_by: N, ahead_by: 0` means the branch
  is a fully-merged, stale ref — and if so, repoint `Remotes:` at the
  default branch instead of leaving DESCRIPTION pinned to dead history.
  **Grep the whole repo for other hardcoded copies of the same remote
  spec** before considering the fix complete — a CI workflow's
  `extra-packages:` list can duplicate the exact same `owner/repo@branch`
  string outside DESCRIPTION, and fixing only DESCRIPTION leaves pak's
  dependency solver seeing two conflicting specs for the same package
  (`Conflicts with <old-spec>`). If nothing else needs that duplicate
  pin (e.g. `r-lib/actions/setup-r-dependencies`'s `needs: check` /
  `local::.` already resolves the package from DESCRIPTION's own
  `Remotes:`), just delete the redundant `extra-packages` line rather than
  updating it in two places. (ucdavis/bcs#310, 2026-07-06: this exact
  chain — `add_repo` unblock, `compare` showing the branch fully merged,
  then two more hardcoded copies of the same stale ref found in
  `docs.yaml` and `copilot-setup-steps.yml`.)
- **When a consumer repo pins a dependency to an upstream *feature branch*
  (not a tag/default branch) and the consumer's CI is failing because of a bug
  *in* that dependency, the fix must land ON that pinned branch --- open a PR
  into it, don't just fix the consumer.** The consumer's CI reinstalls the
  branch's tip on the next run (pak/`setup-r-dependencies` resolves
  `owner/repo@branch` to its current SHA at install time), so once the upstream
  fix merges into the pinned branch, re-triggering the consumer's failing job
  picks it up with no change to the consumer at all. Corollary: a stale feature
  branch can fail its *own* repo's newer CI (e.g. a `jarl-check` on
  pre-existing `unused_function` warnings) purely from being behind `main` ---
  don't debug those as new defects; catch the branch up to `main`'s
  already-clean state (mirror what `main` already did: add the `jarl.toml`,
  remove the dead functions `main` removed). Verify main's tree with
  `git show origin/main:<file>` reads rather than a shallow-clone range diff
  (see below). (UCD-SERG/serocalculator#503 pinned
  `d-morrison/altdoc@recursive-qmd-search`; fixing the consumer's docs build
  required altdoc PR #27 into that branch, and altdoc PR #28 caught the branch
  up to main's jarl-clean state, 2026-07.)
- **Scope-blocked GitHub repo, but you only need its *datasets* (an R data
  package like `rmb`): rebuild a minimal data-only package from
  `raw.githubusercontent.com`.** The proxy's repo-scope check blocks
  `github.com`/`codeload.github.com` tarball downloads and `git clone` for
  out-of-scope repos (the same 403 as the renv bullet above), and `add_repo`
  needs an explicit user request — but `raw.githubusercontent.com` serves the
  same repo's files fine. When the consuming render/tests only use
  `pkg::dataset` objects (grep for `pkg::` to enumerate them), fetch
  `DESCRIPTION` plus just the needed `data/*.rda` files at the lockfile's
  pinned `RemoteSha`, write a stub comment-only `NAMESPACE`, and
  `R CMD INSTALL` the result: `LazyData: true` makes `pkg::dataset` resolve
  via lazydata with no exports and no `R/` sources needed. Don't copy the
  real `NAMESPACE` — its `export()` lines reference functions whose `R/`
  sources you didn't fetch, and the install fails on the missing objects.
  (rme#1047/#1048: unblocked `quarto render` of a chapter needing
  `rmb::hers` after the tarball 403'd; the older installed `rmb` predated
  the dataset.)
- **A stale `00LOCK-*` directory silently blocks every subsequent
  `install.packages()` call**, left behind when an earlier install was
  interrupted (killed mid-run, or two `install.packages()` calls racing —
  e.g. a foregrounded retry while an earlier `nohup`'d background install was
  still holding the lock). Under `quiet = TRUE` the only symptom is
  `installation of package 'X' had non-zero exit status` for every package in
  the call, with no hint why — rerun once without `quiet` to see the real
  `ERROR: failed to lock directory '.../site-library' for modifying` line.
  Fix: `rm -rf` the lock directory shown in that error output — typically
  `/usr/local/lib/R/site-library/00LOCK-*` in these containers, but confirm
  the path from the error rather than assuming it (an renv project or a
  user-library session uses a different one) — then retry; packages
  installed before the interruption are still there; only the retry was
  blocked. (ucdavis/ettbc#32: cost real time before diagnosing, since most of
  a large dependency tree had actually installed fine and only the lock
  blocked the last few packages.)
- **To check whether a CRAN package is archived, query the PPM JSON API, not
  WebFetch against the CRAN HTML page — and check `is_archived`, NOT
  `tran_archive`.**
  `curl -s https://packagemanager.posit.co/__api__/repos/cran/packages/<pkg>`
  returns a top-level boolean `"is_archived": true|false` — that's the
  authoritative field. `tran_archive` is a decoy: it's present in the same
  response but stays `null` even for a package that **is** archived (verified
  directly — `pryr`'s response has `"tran_archive": null` alongside
  `"is_archived": true`), so checking it gives a false "not archived" on every
  query. Confirmed by curling both packages live: `pryr` and `veccompare` each
  return `"is_archived": true`. WebFetch summarizing
  `cran.r-project.org/package=<pkg>` can also return confident-sounding but
  unverified specifics (an "Archival Date" / "Reason" framing CRAN's actual
  archived-package page doesn't present that way) — cross-check against the
  PPM API's `is_archived` field before citing a date or reason as fact.
  (Surfaced on ucdavis/fxtas#157: pak failed to resolve `pryr` +
  `veccompare` from the PPM snapshot; the repo owner verified via this
  endpoint before concluding they were genuinely archived.)
- **`snapr` is not on CRAN or P3M**: install from the GitHub tarball.
  `curl -L https://codeload.github.com/d-morrison/snapr/tar.gz/refs/heads/main -o /tmp/snapr.tar.gz`
  then in R, install `readr` first (a direct `snapr` `Imports:` dependency):
  `install.packages("readr")`, then
  `install.packages("/tmp/snapr.tar.gz", repos=NULL, type="source")`.
  `snapr::expect_snapshot_data()` silently skips snapshot generation/comparison when
  `NOT_CRAN` is unset (respects the standard CRAN-skip convention):
  `NOT_CRAN=true Rscript -e 'devtools::test()'`.
- The `latex-macros` submodule (d-morrison/macros) is uninitialized on a fresh
  clone → `git submodule update --init latex-macros` before any render, else
  `{{< include latex-macros/macros.qmd >}}` fails for every chapter.
- More generally, when Quarto errors with `Include directive failed` / `could
  not find file ...` and the missing path is under a submodule directory,
  check `git submodule status` first and initialize/update that submodule in
  the current worktree before debugging include paths (`git submodule update
  --init <path>`). (Observed in UCD-SERG/serocalculator, 2026-07-22: missing
  `../macros/macros.qmd` was from an uninitialized `macros` submodule, not a
  bad include expression.)
- In a Quarto **project** (observed on rme), `{{< include >}}` paths for files
  rendered via a root wrapper resolved from the PROJECT ROOT *in practice* —
  even for *nested* includes inside subfiles (a `{{< include _root.qmd >}}`
  inside `_subdir/nested.qmd`, rendered via a root wrapper, picked up `_root.qmd`
  from the project root, not from `_subdir/`). This is contrary to the Quarto
  docs' single-document rule ("relative to the file containing the include").
  One observation can't rule out a confound, and behavior may differ across
  Quarto versions or project configs — so test; don't assume *either* rule holds
  without checking. To verify touched subfiles when the full
  chapter needs an unavailable pkg (rmb): write a minimal wrapper `.qmd` AT THE
  REPO ROOT that includes `latex-macros/macros.qmd` + the subfiles, loading data
  manually
  (`hers <- haven::read_dta(here::here("inst/extdata/hersdata.dta"))`). This
  checks LaTeX/markdown/cross-refs for edits that don't touch R chunks without
  provisioning the whole dep tree. Grep the rendered HTML for `?@` / `>??<` to
  catch broken cross-refs.
- **Asset paths in `{{< include >}}`-ed fragments resolve against the
  master/including file's directory** in the outputs that matter (observed on
  wai, Quarto 1.9.38, `type: website`; distinct from *include-path*
  resolution in the bullet above --- that one is about where a nested
  `{{< include >}}` directive finds its target file, this one is about where
  a relative image/asset path inside a fragment resolves at render time): the rendered master HTML page emits
  the `img src` as written, relative to the master page's output location,
  and the lualatex PDF pass compiles from the master file's directory. So an
  image referenced as `assets/images/x.png` inside
  `chapters/ai-tools/fragment.qmd`, included by `chapters/master.qmd`, must
  live at `chapters/assets/images/x.png` — project root and fragment-dir
  placements both fail (HTML silently as a placeholder; PDF hard with
  lualatex `file not found`). Verify empirically: check where `quarto render`
  copies the asset under `_site/`, and read the failing `.log`'s own path
  (`chapters/master.log` ⇒ compile cwd was `chapters/`). Related trap that
  let a wrong fix merge green: wai's PR `preview` job renders HTML only,
  while `publish.yml` on main renders all formats — the PR's checks never
  exercised the PDF pass, so main stayed red after merge. Identify which CI
  job actually runs the failing format before trusting a green PR.
  (wai#13 → #15 → #16, 2026-07-16.)
- Chapters that `{{< include r-config.qmd >}}` pull the full ~40-pkg set
  (dobson, survminer, gtsummary, …); chapters that only include macros.qmd are
  light (math-prereqs needs just plotly).
- **A sandbox with no R at all: `apt-get install r-cran-*` binaries can be ABI-
  incompatible with the installed R version.** A fresh container with R 4.6.1
  and no packages hit pervasive `undefined symbol: SETLENGTH` / `SET_FORMALS` /
  `R_nchar` / `SET_GROWABLE_BIT` errors across dplyr, vctrs, fansi, tibble,
  testthat, pkgload, roxygen2, readr, and their transitive deps — apt's
  prebuilt `r-cran-*` .debs were built against a different R ABI than the one
  actually installed. Fix: reinstall every affected package from source,
  `install.packages(pkgs, type = "source")`, resolving each new transitive
  failure iteratively (plus any system libs a source build needs, e.g.
  `libudunits2-dev` for the `units` package's C bindings). Slow but gets a
  real, verifiable R toolchain instead of guessing at doc/roxygen output.
  (serocalculator PR-393-extraction session, 2026-07-08.)
- **`testthat::test_dir()` run without every snapshot-consuming package
  installed can DELETE committed snapshot files.** testthat's own end-of-run
  "Deleting unused snapshots" cleanup treats any snapshot it didn't see
  exercised (e.g. an `expect_snapshot_file()` an `svglite`/`vdiffr`-dependent
  test skipped because `vdiffr` wasn't installed in a stripped-down sandbox)
  as orphaned and removes it from `tests/testthat/_snaps/` — silently, with no
  confirmation prompt. Caught only via `git status --short` before staging
  anything (21 legitimate `.svg` snapshots had vanished from the working
  tree); restored with `git checkout -- <paths>`. Prefer
  `testthat::test_file()` on individual files in this kind of sandbox — it
  doesn't run the whole-suite cleanup pass — and always `git status` before
  committing after any `test_dir()` run.
- **`if (cond) "name" = value` inside `c(...)` is parsed as an assignment
  expression, not a named `c()` element.** R's argument-tag recognition
  requires the tag to be the direct head of the argument passed to `c()` — a
  bare `"name" = value` — not one produced by evaluating a nested `if()`
  expression. `c("a", if (cond) "name" = value)` silently creates/evaluates a
  local variable named `name` and splices in the *unnamed* string `value`
  instead of a `name = value` pair, with no warning or error. This breaks a
  `dplyr::*_join(by = c(...))` call the moment the conditional branch fires
  (a "Join columns in x must be present in the data" error, since the
  intended named join key was silently dropped). Fix: wrap the whole
  conditional element in its own `c()` — `c("a", if (cond) c("name" = value))`
  — so the name attaches to the inner `c()` call's result, which is what gets
  spliced into the outer one. Verify with a direct R repro
  (`names(c("a", if (TRUE) "name" = "value"))` vs the wrapped form) before
  trusting either reading. (serocalculator#552 review round 1: found in
  `sim_pop_data_2()`'s `left_join(by = ...)`.)
- **`rngtools::RNGseq(n, seed)` returns an unwrapped single state vector
  (not a list-of-one) when `n == 1`**, unlike `n > 1` which returns a proper
  `list` of 7-integer L'Ecuyer-CMRG state vectors. Code that assumes a list
  regardless of `n` — e.g. `rngtools::RNGseq(n, seed) |> array(dim = c(1,1,1),
  ...)` — silently truncates the 7-integer vector to its first element when
  `array()` reshapes it, corrupting the RNG state fed to `rngtools::setRNG()`
  downstream. Symptom: genuinely non-reproducible results (different values
  across separate R sessions with the identical seed) specifically when a
  parallel/foreach-driven simulation call reduces to a single
  lambda/sample_size/cluster (or equivalent single-task) combination — every
  other combination stays reproducible, which makes this easy to miss until
  someone writes a test for exactly the single-task case. Diagnose by
  comparing `class(rngtools::RNGseq(1, seed))` (`"integer"`) against
  `class(rngtools::RNGseq(2, seed))` (`"list"`), and by checking
  `array(rngtools::RNGseq(1, seed), dim = c(1,1,1))` for silent truncation.
  Workaround at the call site: avoid the single-task case (e.g. bump a
  `nclus`-style parameter to 2+) until the root function is fixed to
  `list()`-wrap the `n == 1` case explicitly. (serocalculator#554, found
  while adding test coverage for `sim_pop_data_multi()`'s `sim_function`
  dispatch parameter — the natural minimal test used a single lambda/
  sample_size/`nclus = 1`, which happened to hit exactly this bug.)
- **Provisioning packages already tracked in `renv.lock` but missing from the
  library (an incomplete restore, not a new-package addition) hits the same
  `Remotes:`-resolution failure documented below** ("renv.lock — adding a
  package…") — `install.packages()`/`renv::install()` both route through
  renv/pak and abort the whole call if any `Remotes:` entry can't be resolved
  (blocked `api.github.com`), even for unrelated CRAN packages. For this
  simpler case (no lockfile edit needed, just get already-tracked packages
  installed), bypass `.Rprofile` entirely instead of hand-editing the
  lockfile: `Rscript --no-init-file -e '.libPaths("<renv-project-lib-path>");
  options(repos=c(CRAN="https://cloud.r-project.org")); install.packages(c(...))'`.
  (Try the P3M binary-repo approach above first; reach for this bypass only
  if that's also unavailable.)
- **Don't pass `dependencies=TRUE` when filling small gaps in an existing renv
  library.** It recurses into `Suggests` too, not just `Depends`/`Imports`, and
  can drag in huge unrelated compiled packages (hit `OpenMx`, `rsvg`, `Rfast` —
  Suggests-of-Suggests of `parameters`/`broom.helpers`) that add 30+ minutes of
  compilation and aren't needed to render. Use `dependencies=NA` (the default:
  `Depends`+`Imports`+`LinkingTo` only) — it's what's actually needed to
  `library()` and render, and installs in a fraction of the time.
- To find exactly which packages are missing (including transitively, without
  over-installing): `tools::package_dependencies(top_pkgs, db=available.packages(),
  which=c("Depends","Imports","LinkingTo"), recursive=TRUE)`, then filter with
  `requireNamespace(..., quietly=TRUE)` against the **full** `.libPaths()`
  search (not `installed.packages(lib.loc=<one dir>)`, which misses base/recommended
  packages and anything already installed in a different lib on the path and
  falsely reports them as missing).

## renv.lock — adding a package that's only referenced via another package's Suggests

Using a function that requires an **optional** dependency of an already-locked
package (e.g. `lintr::cyclocomp_linter()`, which needs the `cyclocomp` package —
listed only inside `lintr`'s own embedded `Suggests` metadata in `renv.lock`,
never as its own top-level `Packages` entry) breaks CI silently: `renv::status()`
looks clean beforehand, but `renv::restore()` never installs it, and the first
run that actually calls the function errors at runtime (for `cyclocomp_linter()`:
"disabled due to lack of the cyclocomp package"). Before relying on a new
function that pulls in an optional dep like this, check with
`jsonlite::fromJSON("renv.lock")$Packages` (or grep the lockfile) that the
package has its own top-level entry — its name appearing SOMEWHERE in the file
(inside another package's `Suggests` list) is not sufficient.

**Fixing it: do NOT run `renv::snapshot()` (even scoped via `packages = c(...)`)
in an environment that can't fully restore the lockfile's existing package set.**
`renv::snapshot(packages = "cyclocomp")` in a sandboxed/offline container pruned
~4000 unrelated lines from a real `renv.lock` (every package not physically
installed in the local renv library got dropped) and mangled Unicode author
names into octal-escaped bytes in surviving entries — collateral damage far
outside the intended one-package addition. `renv::install()` has the same
blast radius: it tries to resolve the WHOLE project's `Remotes:` field (e.g. a
GitHub pin like `rstudio/bookdown`), which fails outright if GitHub API access
is blocked, even though the failure has nothing to do with the CRAN package
being installed. **`install.packages()` hits the identical failure while renv
is active**, because renv's autoloader shims `install.packages()` to route
through `renv::install()` internally (confirmed by the traceback: a plain
`install.packages("cyclocomp")` call showed `renv::install("cyclocomp")` as
a parent frame) — so avoid both, not just the namespaced call.

**A second, more severe occurrence: a full, unscoped `renv::snapshot()` (no
`packages =` arg) in a Claude Code Bash sandbox that had NO project R packages
installed at all (only base R) truncated a real `renv.lock` from ~300 package
entries down to ~6 base-R packages** — not a partial prune, essentially the
whole lockfile. The mistake was made trying to "refresh" a lockfile that
looked stale (a pinned GitHub remote's commit SHA 404'd); running
`renv::snapshot()` felt like the obvious fix but, per the rule above, is
never safe unless the environment can actually restore the full existing
package set first. It went unnoticed at push time (the diff just looked like
"a smaller lockfile") and was only caught because a *downstream* CI job
(`lint-changed-files`) failed on a missing `gh` R package that the lockfile
no longer had — prompting a diff review that revealed the near-total
truncation. **Before trusting any regenerated lockfile, diff old-vs-new
package *counts*** (e.g. `jq -r '.Packages|keys[]' old.json | sort >
/tmp/old.txt`, same for `new.json`, then `comm -23 /tmp/old.txt
/tmp/new.txt` to list dropped packages) and treat a dramatic shrink as a red
flag requiring revert, not a "cleanup." (`d-morrison/rme#1017`: reverted via `git revert`, then fixed the
actual root cause — see the repo-move 404 entry above — with a minimal
hand-edit instead.)

The safe fix is a **surgical hand-edit of the lockfile JSON**: install the
missing package locally just to read its DESCRIPTION metadata (e.g.
`install.packages("cyclocomp", lib = <renv project lib>)`,
`packageDescription("cyclocomp")`), then copy the exact field style of a
neighboring `Packages` entry (`Package`, `Version`, `Source: "Repository"`,
`Title`, `Authors@R`, `Description`, `License`, `URL`, `BugReports`,
`Imports`/`Suggests` as arrays, `NeedsCompilation`, `Author`, `Maintainer`,
`Repository: "CRAN"`) and insert it alphabetically with the Edit tool. Verify
with `jsonlite::fromJSON("renv.lock")` that it still parses and
`git diff --stat renv.lock` shows only the intended additive lines — a diff in
the thousands means the wrong approach was used; `git checkout -- renv.lock`
and redo it by hand. (UCD-SERG/lab-manual#381: `lint-project` failed on
`cyclocomp_linter is disabled due to lack of the cyclocomp package`; the
snapshot approach was tried first and reverted before the hand-edit.)

## lintr — no built-in function-length (line-count) linter; custom-linter pattern

`{lintr}` has no built-in linter that flags functions by raw line count — it's
a long-standing unimplemented upstream feature request
([r-lib/lintr#361](https://github.com/r-lib/lintr/issues/361)). The closest
built-in is `lintr::cyclocomp_linter()`, which flags branching/decision
complexity (via `{cyclocomp}`), not line count — a reasonable proxy but not
the same metric. When a repo wants an actual `<N`-lines heuristic enforced,
write a custom linter.

Working pattern (verified against lintr 3.3.0):

```r
function_length_linter <- function(length_limit = 150L) {
  xpath <- "//FUNCTION/parent::expr | //OP-LAMBDA/parent::expr"

  lintr::Linter(linter_level = "expression", function(source_expression) {
    if (!lintr::is_lint_level(source_expression, "expression")) {
      return(list())
    }
    xml <- source_expression$xml_parsed_content
    fun_defs <- xml2::xml_find_all(xml, xpath)
    n_lines <- as.integer(xml2::xml_attr(fun_defs, "line2")) -
      as.integer(xml2::xml_attr(fun_defs, "line1")) + 1L
    lintr::xml_nodes_to_lints(
      fun_defs[n_lines > length_limit],
      source_expression = source_expression,
      lint_message = sprintf("Function spans more than %d lines.", length_limit),
      type = "warning"
    )
  })
}
```

The XPath `//FUNCTION/parent::expr | //OP-LAMBDA/parent::expr` catches both
`function(...)` and `\(...)` lambda syntax; `line1`/`line2` are XML attributes
from `xmlparsedata` on the matched node, so line span is `line2 - line1 + 1`.
`linter_level = "expression"` + the `is_lint_level()` guard is `lintr`'s own
documented pattern (see `vignette("creating_linters", package = "lintr")`).
Needs `lintr (>= 3.1.2)` for the `linter_level` argument. (Landed as
`lms::function_length_linter()` in UCD-SERG/lab-manual#381.)

## air (R formatter) vs lintr's `indentation_linter` — keep `indent-width` aligned

- `air`'s `air.toml` `[format]` table has a configurable `indent-width`
  (default 2). Air indents a multi-line function *definition*'s arguments by a
  *single* level (one `indent-width`), NOT the styler/tidyverse-style-guide
  "double indent". lintr's default `indentation_linter` also expects a single
  2-space indent there. So air's default output and lintr agree at 2 --- but a
  repo that sets `air.toml` `indent-width = 4` (as `d-morrison/altdoc` does)
  will have air-formatted signatures that a *different* repo's lintr (default
  2) rejects.
- **Practical failure:** old styler-formatted code (4-space double-indent
  function signatures) sitting in a repo whose `.lintr` uses
  `lintr::linters_with_defaults()` passes CI only until a PR *touches* that
  file --- `lint-changed-files` then flags `[indentation_linter] Indentation
  should be 2 spaces but is 4 spaces`. Fix by reformatting the signature to a
  single 2-space indent (de-indent the arg block by 2), and set/confirm
  `air.toml` `indent-width = 2` so a future `air format` keeps it lintr-clean.
  (Only the *first* mis-indented line of a block is reported; de-indent the
  whole signature block, not just the flagged line, or the next line flags on
  the next run.) (UCD-SERG/serocalculator#503, 2026-07.)
- **A `lint-changed-files`-style workflow that calls `gh::gh()` (or any
  GitHub API) to list the PR's changed files can flake with `403 API rate
  limit exceeded for <IP>` when it runs *unauthenticated*.** The R `gh`
  package reads its token from `GITHUB_PAT` then `GITHUB_TOKEN`; if the
  workflow sets `env: GITHUB_PAT: ${{ secrets.GITHUB_PAT }}` and that custom
  secret isn't configured in the repo, the value is empty and the call runs
  anonymously (low shared-IP rate limit). Fix:
  `GITHUB_PAT: ${{ secrets.GITHUB_PAT || secrets.GITHUB_TOKEN }}` --- falls
  back to the always-present built-in token (`permissions: read-all` already
  covers the read). It's a flake (passes most runs), so a red
  `lint-changed-files` with no R lint output and a `gh_error`/`rate limit`
  traceback is this, not a code problem. (UCD-SERG/serocalculator#503, 2026-07.)

## jarl (Just Another R Linter) — `jarl.toml` fields lag the published docs
- `jarl` (`etiennebacher/jarl`, installed via `etiennebacher/setup-jarl@vX` in
  CI) is a fast Rust-based R linter, a sibling to `{flir}` by the same author
  (both are `etiennebacher` projects; `{air}`, the R formatter jarl builds on,
  is a separate Posit project by Davis Vaughan and Lionel Henry, not the same
  author). Its `unused_function` rule flags any function jarl's static analysis
  can't find a call site for — including functions in **fixture/test-data R
  packages** (e.g. a `tests/testthat/examples/testpkg.*/R/*.R` tree copied and
  rendered as test input), which are genuine false positives: nothing in the
  outer package is ever meant to "call" fixture content.
- **The `jarl.toml` config schema in the repo's `CHANGELOG.md`/docs can
  describe a feature not yet in the released version CI actually installs.**
  `[lint.per-file-ignores]` (scope a rule to specific files/globs) appears in
  jarl's `CHANGELOG.md` on `main`, but `jarl check` itself is the source of
  truth for what the *installed* version accepts — it errors immediately with
  `Invalid configuration ... Unknown field 'per-file-ignores' in '[lint]'.
  Expected one of: select, extend-select, ignore, fixable, unfixable, exclude,
  default-exclude, include, check-roxygen, fix-roxygen` when the field isn't
  supported yet (hit against jarl 0.5.0 via `setup-jarl@v0.1.0`, no version
  pin -> latest). The error message's "Expected one of" list is authoritative;
  don't trust changelog/docs-site prose for what a *pinned or auto-latest* CI
  install actually accepts, since "on `main`" doc content can be ahead of the
  latest tagged release.
- **Fallback when the wanted field isn't supported: `[lint] exclude = ["<dir>/"]`**
  (full path/glob exclusion — coarser than `per-file-ignores`, silences ALL
  jarl rules for that directory, not just the one false-positive rule) rather
  than editing fixture file content to appease the linter (fixture bytes often
  feed snapshot/rendering tests, so editing them risks unrelated test
  breakage). File a follow-up issue to narrow `exclude` to `per-file-ignores`
  once the installed jarl version supports it. (`d-morrison/altdoc#18`, #19.)
- **There is no `.jarlignore` file — jarl has never supported one.** Don't
  assume jarl follows the `.gitignore`/`.eslintignore`-style convention of a
  dotfile-per-tool; its only exclusion mechanism is `jarl.toml`'s `[lint]`
  table (`exclude` / `per-file-ignores`, above). A `.jarlignore` file is
  silently inert — `jarl check` never reads it, so violations inside the
  "excluded" paths still fire, and no error or warning flags the unsupported
  config. This is easy to miss because CI can still look green: pairing the
  fake `.jarlignore` with `continue-on-error: true` on the lint step (to
  paper over the failures it doesn't actually suppress) hides the breakage
  entirely, and a bot review can approve the change on the false premise that
  `.jarlignore` works, since nothing about the diff itself is wrong-looking.
  Verify a suppression file is real by checking the tool's own config-file
  reference (or just removing `continue-on-error` and running the check) —
  not by pattern-matching on other tools' ignore-file conventions.
  (`d-morrison/altdoc#7`: `continue-on-error: true` masked a `.jarlignore`
  that did nothing; removing the flag immediately reproduced the
  `unused_function` failure it was supposed to prevent.)

## R-package PR CI gates (d-morrison / UCD-SERG R packages, e.g. `bcs`)
- These repos gate PRs on a **changelog check** (`news.yaml` / "Check Changelog
  Action") and a **version-check**. A user-visible PR needs **both** a
  `NEWS.md` entry under `# <pkg> (development version)` **and** a `DESCRIPTION`
  `Version:` dev-bump (e.g. `0.0.0.9053` → `.9054`), or CI fails. Add them up
  front rather than waiting for the red check. (Observed on ucdavis/bcs#223.)
  For a **non-user-visible** PR (CI/workflow-only), skip both with the
  `no changelog` + `no version increment` labels instead — see the label-bypass
  note below.
- The **Spellcheck** job (`spelling::spell_check_package()`) fails on any word
  not in `inst/WORDLIST`. For one-off non-dictionary words in NEWS/prose, prefer
  rewording (e.g. "uncaptioned" → "without captions") over polluting WORDLIST;
  add to WORDLIST only for real domain terms you'll reuse.
  - **When the offending token is a code identifier or a literal log/warning
    message** (e.g. quoting `non-integer #successes in a binomial glm!` in a
    NEWS entry, which tripped on `glm`), wrap it in backticks as inline code
    instead — the spellcheck parses markdown and skips code spans, and
    backticking a `pkg::fn()`/identifier/message is the correct markdown style
    anyway. Cleaner than both rewording and a WORDLIST add. (ucdavis/ettbc#30.)
  - **Cross-repo issue refs and bare domain names are spellable-token sources
    too, not just code identifiers.** The checker splits on punctuation, so an
    unbackticked `d-morrison/altdoc#26` flags `morrison`, and `rdrr.io` flags
    both `rdrr` and `io`. Backtick them (existing NEWS entries already backtick
    cross-repo refs, so this matches convention), and reword genuinely-prose
    words instead of listing them (`undiscoverable` → "cannot discover").
    (ucdavis/bcs#375: four tokens flagged from one NEWS entry, fixed with zero
    WORDLIST additions.)
- **Regenerating `man/*.Rd`: run `devtools::document()` (or
  `roxygen2::roxygenise()`) --- never hand-edit the `.Rd`.** A `docs-check` /
  `R-check-docs` job runs `roxygenize()` then `git diff --exit-code man/`, so a
  roxygen edit with a stale `man/*.Rd` fails; the fix is to regenerate, not to
  hand-write the `.Rd`. **If the toolchain looks missing** (a bare-R cloud/web
  sandbox with no `devtools`/`roxygen2`), install it ---
  `install.packages("roxygen2")` plus the package's own `Imports` so
  `pkgload::load_all()` can load it --- and run `roxygen2::roxygenise()`
  (`devtools::document()` if `devtools` is also installed). Treat "no R
  toolchain" as a resource to obtain (growth-mindset), not a reason to edit
  `.Rd` by hand. (Corrected 2026-07-20: on serocalculator#562 I hand-edited two
  `.Rd` files instead of installing roxygen2 and running `document()`; the
  user's rule is to run the generator.)
- **Hand-editing `.Rd` is a genuine last resort, only when installing the
  toolchain truly fails** (offline / locked-down sandbox). If forced to it, keep
  the edit safe: roxygen copies `@format`/`@param`/`@return` prose verbatim into
  the `.Rd` and `roxygenize()` is deterministic, so a **same-length word swap**
  (e.g. `biannual`->`biennial`) reproduces exactly what `document()` would
  generate. For a larger edit, first verify the transform empirically --- diff an
  existing `\item{}` block's roxygen source (stripped of its `#'` prefix) against
  its rendered `.Rd` lines; roxygen with `markdown = TRUE` preserves line breaks
  and converts `` `x` `` to `\code{x}` (and `**bold**` to `\strong{}`, `[text](url)`
  to `\href{}{}`) --- then validate your hand-edit with a scripted
  transform-and-diff (`` perl -pe 's/`([^`]+)`/\\code{$1}/g' `` piped to `diff`
  against the `.Rd`). Watch `@inheritParams`/`@inherit`: editing one function's
  roxygen also changes every inheriting function's `.Rd`, so grep `man/` for the
  changed sentence. (bcs#225; serocalculator#562 --- but prefer installing the
  toolchain over all of this.)
- **Codoc mismatch with escaped-dot defaults: limit the lesson to the observed case.**
  In d-morrison/altdoc#30, changing the default regex from an escaped dot (`\\.`) to
  a bracket expression (`[.]`) resolved an `R CMD check` codoc mismatch for
  `setup_github_actions()`. Keep this note scoped to that concrete escaped-dot case;
  avoid generalizing to other escape sequences without direct evidence.
  (d-morrison/altdoc#30, 2026-07-22.)
- **Internal helper functions as default argument values appear literally in `.Rd` usage
  blocks.** If you write `foo = .helper_default()` as a parameter default, the roxygen
  `\usage{}` section shows `.helper_default()` verbatim — which is confusing to users
  copy-pasting the signature. Inline the literal value directly in the function
  signature instead. (d-morrison/altdoc#30.)

## YAML authoring (GitHub Actions / workflow files)
- **Regex values with backslashes: prefer single-quoted YAML, but document both forms
  correctly.** YAML double-quoted scalars process escapes, so you must double each
  backslash there (e.g. `"foo\\.bar"` for a single literal backslash before `.`).
  Single-quoted scalars preserve backslashes as-is (e.g. `'foo\.bar'` for that same
  single backslash), which is usually easier to reason about in workflow templates.
  This applies to `branches-or-tags-to-list` / regex inputs in reusable-workflow YAML.
  (d-morrison/altdoc#30.)

## GitHub access from bash in remote/web sessions
- The git proxy proxies ONLY git operations — there is no `gh`/`glab` and no
  GitHub REST API reachable from a Bash/Monitor script. Use `mcp__github__*`
  tools for any API need.
- **The proxy allows branch creation/push but BLOCKS branch deletion.** Pushing a
  *new* branch (even one other than the harness-assigned `claude/...`) works, but a
  delete push — `git push origin --delete <b>` or `git push origin :<b>` — is rejected.
  Observed verbatim: "send-pack: unexpected disconnect" / "remote end hung up", then a
  misleading "Everything up-to-date" (the proxy returns that no-op message instead of a
  normal `failed to push some refs` error), but the command still exits non-zero. So a
  throwaway branch (e.g. a push-capability probe) can't be cleaned up from the session;
  delete it via the GitHub UI/API, or just leave it if it's identical to `main` and has
  no PR. (Seen on ai-config, 2026-06-28.)
- **GitHub Pages sites (`<owner>.github.io`, incl. `rossjrw/pr-preview-action`
  PR-preview links) are policy-blocked in at least some sandboxes** — both
  WebFetch and a direct `curl`/CONNECT through the agent proxy get a `403`
  (`gateway answered 403 to CONNECT (policy denial)`, confirmed via
  `curl -sS "$HTTPS_PROXY/__agentproxy/status"`). Don't retry or assume it's
  transient — treat it the same as an unavailable preview and fall back to
  rendering the chapter locally (rme's own CLAUDE.md already names this
  fallback for "no preview has deployed yet"; it also applies when the
  preview exists but the sandbox can't reach it).
- Consequence: you CANNOT poll PR review/CI state from a background Monitor.
  Rely on `mcp__github__subscribe_pr_activity`, which delivers review comments
  and CI *failures* — but NOT CI success, new pushes, or merge-conflict
  transitions. A self-check-in scheduler may be absent: rme's instructions
  reference `send_later` (from the `claude-code-remote` MCP server), and the
  harness may expose its own (e.g. `ScheduleWakeup`) — but in this remote rme
  session ToolSearch surfaced neither, so you can't arm the safety re-poll the
  watch-guidance suggests. Say so rather than implying it's armed.
- rme runs TWO review workflows per push: `claude-code-review.yml` (sticky
  comment, gives the "ready to merge" verdict) and `claude.yml` agent post-step
  (separate findings). They can DISAGREE — one says clean while the other finds
  nits. Reconcile BOTH before calling a PR clean; the agent post-step tends to
  drip 1–2 pre-existing cosmetic nits per round (asymptotic).

## WebFetch 403 on a rendered docs site -> raw.githubusercontent.com; WebSearch to find the exact source path
- A GitHub-Pages/Quarto-rendered docs site (e.g. `jarl.etiennebacher.com`,
  `ucd-serg.github.io/lab-manual/...`) can reject `WebFetch` outright (403 —
  likely anti-scraping), even though the plain-text/markdown **source** it was
  built from is a public file in a public repo and fetches fine via
  `https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>`. This
  isn't `d-morrison/gha`-specific (that repo's own `CLAUDE.md` documents it
  for the lab manual) — it generalizes to any Quarto/Docusaurus-style site,
  including third-party tool docs with no relation to our own repos.
- **When the exact source path isn't obvious** (unlike the lab-manual case
  where `foo.html` predictably maps to `foo.qmd`), guessing candidate paths
  one `curl -o /dev/null -w "%{http_code}"` at a time is slow and often wrong.
  `WebSearch` for `<repo-or-tool-name> <topic> site:github.com` (or just
  `<tool> <config-file> github`) surfaces the actual repo file path (e.g.
  `jarl/docs/reference/config-file.md`) from its indexed GitHub listing —
  faster than blind guessing, and the found path fetches cleanly via
  `raw.githubusercontent.com` immediately after. (Confirmed on jarl's docs
  site: `jarl.etiennebacher.com/reference/config-file` 403'd, but
  `WebSearch` surfaced `docs/reference/config-file.md` as the underlying
  file, which raw-fetched with the full field-by-field config reference.)
- **`docs.github.com` itself can be blocked outright by a remote session's
  network policy** (proxy 403 on every page, and `api.github.com` too —
  both at the curl/WebFetch level; the GitHub MCP tools route through
  their own server and keep working), not
  just anti-scraping — but `raw.githubusercontent.com` stays reachable, and
  GitHub's docs are built from the public `github/docs` repo. Verify a docs
  claim or URL against that source instead: page content lives under
  `content/<area>/.../<slug>.md`, but live-URL paths do NOT map 1:1 to
  source paths (the docs get reorganized; e.g.
  `/billing/managing-billing-for-your-products/...` now lives at
  `content/billing/concepts/product-billing/github-actions.md`). If a page
  was moved, its frontmatter carries a `redirect_from:` list — an old URL
  appearing there means it still works for readers via redirect — and
  shared text is factored into `data/reusables/<area>/<name>.md` includes,
  so grep for a `{% data reusables.<area>.<name> %}` tag and fetch that
  file when a section's body looks like one include line. Version-gated
  (`{% ifversion <flag> %}`) passages resolve via `data/features/<flag>.yml`:
  its `versions:` block (e.g. `fpt: '*'`) says which plans the gated text
  applies to: `fpt` = Free/Pro/Team on github.com, `ghec` = GitHub Enterprise
  Cloud (also github.com-hosted), `ghes` = GitHub Enterprise Server
  (self-hosted). (Used on
  ai-config#601 to verify the GitHub Actions billing and `jobs.<job_id>.if`
  citations offline, and on gha#272 to confirm the approval-required
  `pull_request`-runs exception applies to github.com.)

## Claude Code on the web: CI monitoring toggles have no default setting
- The per-PR "CI monitoring" panel (web session sidebar) shows two toggles,
  **Auto-fix CI & address comments** and **Auto-merge when ready**. There is
  **no account-, org-, repo-, or environment-level setting to default these on**
  — confirmed against https://code.claude.com/docs/en/claude-code-on-the-web.
  Each new PR/session starts with both off and they must be toggled manually.
- Closest workaround: run `/autofix-pr` from the CLI on a PR's branch — it
  spawns a web session with **Auto-fix CI & address comments** already on for
  that PR. There's no CLI shortcut for **Auto-merge when ready**; that one
  always needs a manual toggle. A true default would require a feature
  request via `/feedback`.

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

## AskUserQuestion (Claude Code harness tool)
- Each entry in `questions[]` **requires a `question` field** (the full question
  text) — `header` + `options` alone fail with `InputValidationError: required
  parameter questions[0].question is missing`. Easy to omit when you build the
  call from options first; include the `question` string every time.
- **`Tool permission request failed: Error: Tool permission stream closed before
  response received`** is a **transient** harness glitch, not a user denial —
  **retry the same call.** Hit AskUserQuestion twice and `ExitPlanMode` twice in
  one web session; every retry went through. Applies to any permission-gated
  harness tool (AskUserQuestion, ExitPlanMode, …), so don't abandon the
  interactive flow or fall back to a workaround on the first failure. (A genuine
  denial reads differently — the user declining the specific action.)
  **But don't retry indefinitely if it keeps failing.** In a different web
  session, the same error hit AskUserQuestion twice in a row with no successful
  retry in between. Rather than looping a third time, asking the same question
  in plain chat text worked fine and got an answer. One or two retries is
  reasonable; past that, fall back to a plain-text question rather than
  blocking the turn on a tool that isn't recovering. (ai-config#493 fix-up
  session, 2026-07-05.)

## Bash tool runs under zsh — avoid bash-isms & reserved variable names
- The Bash tool's shell is zsh-initialized, where some names are **read-only
  special variables**: `status`, `path`, `pipestatus`, `argv`, `options`, `?`.
  Assigning to them (e.g. `status=$(...)` in a poll loop) fails with
  `read-only variable: status` and aborts the command.
- Use neutral names instead — `st`, `rc`, `out`, `p`. Bit a `gh run view`
  status-poll loop once; renaming `status`→`st` fixed it.
- **No bash-only builtins.** `mapfile`/`readarray` are undefined in zsh —
  `mapfile -t arr < <(cmd)` fails with `command not found: mapfile`. Iterate the
  glob/list directly instead, e.g. `for d in skills/*/; do s=$(basename "$d");
  …; done`, rather than slurping into an array first. This matters double for
  **skill command blocks**: the user's local shell is zsh too, so a command
  block I write into a skill gets run under zsh — keep it bash/zsh-portable.
  (A `mapfile` loop in the link-skills draft failed this way; PR #71.)

## Skill command blocks — resolve the ai-config repo root with the per-skill symlink
- To `cd` to the repo root from inside a skill, use the **per-skill** form
  `git -C ~/.claude/skills/<this-skill> rev-parse --show-toplevel`, never the
  bare-parent `git -C ~/.claude/skills rev-parse --show-toplevel`. `bootstrap.sh`
  may symlink skills
  *per-child* into a real `~/.claude/skills` directory, so the parent isn't a
  symlink into the repo and `git -C` there fails with "not a git repository".
  The `@claude` reviewer enforces the per-skill form on new skills (it flagged
  the bare-parent form on PR #71); `skill-builder` and `ums` already use it.
- Issue #36 originally proposed the bare-parent `git -C ~/.claude/skills
  rev-parse --show-toplevel` — but that example is the unreliable one (it can
  error with "not a git repository", not a security risk). #36 was closed by
  PR #110, which standardized on the **per-skill** form for `record-learnings`
  and `memorize`; PR #109 swept the last straggler #110 missed (`find-overlap`).
- **Worktree caveat:** the resolved toplevel is the **MAIN** checkout, often on
  another session's branch — don't author files there. Work in your own
  worktree's `skills/<name>/` dir (full rationale in `skill-builder`'s Ship-it
  caveat).
- **Use `<angle-bracket>` placeholders in command blocks — never bare ALLCAPS.**
  `PATH`, `URL`, `TARGET`, etc. look like shell env vars: bare `PATH` looks like
  the `$PATH` env var, and `path` is a zsh special that mirrors `$PATH`. A reader
  who copies the command without substituting the placeholder runs something wrong.
  Use `<path>`, `<url>`, `<target>` instead. (PR #99 fixed `test -e PATH` →
  `test -e <path>` and `curl … URL` → `curl … <url>` in purge-hallucinations.)
- **A trailing `# TOKEN` annotation on a `\`-continued line swallows the
  continuation.** When annotating a command with an inline marker comment
  (e.g. the `tool-mappings.yml` abstract-operation-token pilot, #195/#415),
  putting `# TOKEN` on a line that ends in a line-continuation `\` breaks the
  command: bash's `#` starts a comment that runs to the end of the line,
  consuming the `\` along with it, so the next line's flags are no longer
  part of the same command. Put the annotation on the **last** line of a
  multi-line command (after the final flag/filter), never on an intermediate
  `\`-continued line. The `@claude` reviewer caught this on PR #415's first
  pass (`skills/ardi/SKILL.md`'s `gh pr list \` / `--jq ...` block) — worth
  checking for on every subsequent skill in #416's token-rollout.
- **Verify a brand-new `tool-mappings.yml` `github_mcp` tool name with
  `ToolSearch` before adding the operation, not after.** When #416's
  token-rollout needs a new operation whose GitHub MCP form hasn't been used
  in this repo yet, the tool name is easy to *guess* correctly by pattern
  (e.g. `mcp__github__search_issues` from the existing
  `mcp__github__search_pull_requests`) but still worth confirming live —
  `ToolSearch({query: "select:mcp__github__<name>"})` returns the real schema
  if it exists, or no match if it doesn't. Doing this before adding the row
  avoids a review round-trip flagging the name as unverified (batch 2, PR
  #419): the reviewer couldn't confirm the tool from a static read and had to
  ask for a live check, which a rebuttal citing the schema then resolved
  anyway. Front-load that ToolSearch call and note in the row's PR
  description (or commit message) that it was verified, so the review can
  skip straight past it.
- **`PUSH` was an imperfect fit for remote ref/tag *deletion* — resolved.**
  Flagged as a non-blocking observation by the `@claude` reviewer on batch 3
  (PR #423, `skills/slide-tag/SKILL.md` and `skills/ts/SKILL.md`'s
  `git push origin :refs/tags/<tag>`): the registry's `PUSH` operation is
  documented as "push commits to a branch," and a colon-prefix ref-delete
  pushes nothing and isn't a branch. Initially left as `PUSH` (two instances,
  not the rollout's main surface) with a note to revisit if the pattern
  recurred. It did, a third time, in batch 4 (`clean-branches`'s
  `git push origin --delete <branch>`) — past the self-set threshold — so
  batch 4 added a dedicated `DELETE_REF` operation to `tool-mappings.yml` and
  retro-fitted all three sites (including the two already-merged ones) from
  `PUSH` to `DELETE_REF`.

## ai-config memory file structure
- Memory files (`memories/*.md`) **may** carry YAML frontmatter (`name`,
  `description`, `metadata`) — while older ones
  start directly with a `#` heading. Don't assume either form: `grep -rn "^name:"
  memories/` finds the frontmatter'd files, and a file without it is still valid.
  Preserve whatever frontmatter a file already has rather than stripping it.
- `[[link]]` cross-links in skills and memories resolve to **skill directories**
  (`skills/<target>/`), not to named entries in memory files. To verify a
  `[[target]]` link: `ls skills/<target>/`. If no skill dir exists, fall back to
  searching memory headings: `grep -rn "^# .*<target>" memories/`.
- System skills (e.g. `claude-api`) may be globally available but have no local
  `skills/<name>/` directory. An absent local dir means ❓ Unverifiable, not
  ❌ Fabricated — check the session's available-skills list before classifying.

## Quarto HTML sites (build & layout gotchas)
Hit while adding a mobile within-chapter TOC to `d-morrison/rme` (#929); apply to
any Quarto website (rme, psw, qwt, …).
- **Single-file `quarto render <file>.qmd` serves cached compiled theme CSS.**
  Edits to `custom.scss` / theme SCSS may NOT appear in the output — Quarto reuses
  the cached sass bundle. The tell: the
  `_site/site_libs/bootstrap/bootstrap-*.min.css` content hash stays identical
  across renders. Force a recompile by clearing the sass cache and the stale libs
  first: `rm -rf ~/.cache/quarto/sass _site/site_libs`, then re-render. (A
  "verified" CSS rule was actually stale until I cleared this.)
- **The within-chapter "On this page" TOC is hidden on mobile with no built-in
  replacement.** Quarto's bootstrap hides `#quarto-margin-sidebar` below the `md`
  breakpoint (`@media (max-width: 767.98px)` in `_bootstrap-rules.scss`). There is
  no `toc:` option to re-enable it; the `quarto-toc-toggle` "convert TOC to a
  floating menu" in `quarto.js` is an overlap-avoidance feature for wide screens,
  not a mobile feature (on a phone the margin sidebar is already `display:none`,
  so it never fires).
- **A cloned within-chapter TOC must NOT carry `role="doc-toc"`.** Quarto's mobile
  CSS includes a bare `nav[role=doc-toc] { display: none }` (inside the `md` media
  query), so any clone with that role stays hidden even when you mean to show it.
  Use a plain `<nav aria-label="…">` instead.
- **Navbar headroom = reveal-on-scroll-up.** Quarto attaches Headroom to
  `#quarto-header`; on scroll it toggles `sidebar-unpinned` on the header AND on
  every `.sidebar` / `.headroom-target` element (see `quarto-nav.js`). To make a
  custom element hide-on-scroll-down / reappear-on-scroll-up in step with the
  navbar, place it inside `#quarto-header` (it inherits the header's transform) or
  give it `.headroom-target`. (Used to put a "Contents" TOC button in the navbar.)
- **`quarto render` auto-modifies `.gitignore`.** On first render, Quarto appends
  `/.quarto/` and `**/*.quarto_ipynb` to `.gitignore`. If `.quarto/` is already
  present, `/.quarto/` is redundant (the unanchored form already covers the root).
  Remove `/.quarto/` only when `.quarto/` is already present; keep `**/*.quarto_ipynb`.
- **Manuscript projects do NOT support `repo-url` / `repo-actions` natively.**
  `book` and `website` inherit `base-website` schema (which includes these keys);
  `manuscript-schema` is `closed: true` with no `super`, so the keys are silently
  ignored even when placed under `website:` or `format: html:` in `_quarto.yml`.
  Workaround: a Lua filter that reads those keys from metadata and injects the links
  via inline JS — see `d-morrison/qmt/_repo-links.lua` for a full implementation.
  Upstream issue: quarto-dev/quarto-cli#14627.
- **In Quarto Lua filters, use `quarto.doc.input_file` (not `PANDOC_STATE.input_files[1]`)
  to get the real source path.** Quarto preprocesses `.qmd` files into temp files before
  passing them to Pandoc; `PANDOC_STATE.input_files[1]` gives the temp path, not the
  original `.qmd`. `quarto.doc.input_file` reads the `quarto-source` param and returns
  the real path. To compute the repo-relative path: strip `os.getenv("QUARTO_PROJECT_DIR")`
  from the front (`abs_input:sub(#project_root + 2)`). (Learned while writing `_repo-links.lua`
  for d-morrison/qmt.)
- **A plain project-wide `quarto render` (no `--to`) DOES render every format a
  document's own front matter lists** — even formats the project's `_quarto.yml`
  doesn't configure. Verified from a clean state (`rm -rf _site .quarto` first,
  no priming single-file renders) on `d-morrison/macros`: `_quarto.yml` there
  configures only `format: html:`, yet a bare `quarto render` still produced
  `.pdf`, `.docx`, and reveal.js `.html` output for every doc whose own front
  matter lists those formats — the project config sets the *default* for docs
  with no local `format:` override, it doesn't cap docs that declare their own.
  So a CI step that just runs `quarto render` **likely already exercises** the
  PDF/other-format renders a `CONTRIBUTING.md` separately documents as
  `quarto render <doc>.qmd --to pdf` — don't assume a bare project render is
  HTML-only without checking. (Corrected in ai-config#408 after re-verifying
  from a clean state; the empirical result contradicted both an earlier claim
  logged here and a reviewer's proposed replacement.) The durable lesson
  survives: don't write "CI covers this" in a PR description from assumption —
  verify what CI *actually* does before asserting either that it does or
  doesn't cover a given check.
- **Custom Quarto shortcode Lua files belong under YAML `shortcodes:`, not
  `filters:`.** A Lua file that returns a shortcode table (for example
  `return { ['slidebreak'] = slidebreak }`) does **not** register that
  shortcode when listed under `filters:`; Quarto treats it as a Pandoc filter,
  leaves `{{< slidebreak >}}` literal in rendered HTML, and warns
  `Shortcode 'slidebreak' not found`. Put the path under front-matter or
  project metadata `shortcodes:` instead (e.g.
  `shortcodes: [../_extensions/d-morrison/slidebreak/slidebreak.lua]`), even
  when the file lives inside `_extensions/`. (Observed directly in
  UCD-SERG/serocalculator, 2026-07-22: switching the same Lua path from
  `filters:` to `shortcodes:` made the shortcode render and removed the
  warning in a standalone `quarto render` smoke test.)
- **Large site renders crash Deno's default 8 GB V8 heap — deterministically,
  not flakily.** Quarto's launcher script hardcodes
  `--max-old-space-size=8192,--max-heap-size=8192` and *prepends* those
  defaults before any user-supplied `$QUARTO_DENO_V8_OPTIONS` inside one
  `--v8-flags=` argument; V8 lets the last occurrence of a flag win, so
  setting `QUARTO_DENO_V8_OPTIONS=--max-old-space-size=12288,--max-heap-size=12288`
  in the environment is the supported override. The crash signature: all
  chapters render fine individually, then `Fatal JavaScript out of memory:
  Ineffective mark-compacts near heap limit` late in the ~35-40-file site
  render (cumulative heap, worst in finalization/search-indexing), exit code
  133 — SIGTRAP, not the SIGABRT (134) a classic `abort()` would give:
  V8's fatal-error handler dies on a trap instruction, and the launcher's
  own log line confirms it (`Trace/breakpoint trap (core dumped)` followed
  by `Process completed with exit code 133`, observed identically in both
  failing runs). Reproducible on every re-run. Fixed fleet-wide in gha#263 (the
  `preview`/`quarto-publish` composites export the 12 GB override; standard
  runners have 16 GB). To validate a heap-flag change without a 20-minute
  render: run Quarto's own bundled deno
  (`/opt/quarto/bin/tools/x86_64/deno eval` with the launcher-composed flag
  string) against a >8 GB JS-heap allocation loop — crashes under the
  default string, survives with the override appended, minutes instead of
  hours. (rme #1040/#1042, 2026-07-17: four identical CI OOMs across two
  PRs; not a Quarto version change — v1.9.38 predated both green and red
  runs.)

## renv — each git worktree gets its own (empty) project library

renv keys the project library path on the project directory name, so a
fresh `git worktree` of an renv project starts with an EMPTY library even
though the main checkout's is fully restored — the first render fails with
"package not available" (rmarkdown, etc.). In the Claude Code cloud
containers this lands at `~/.cache/R/renv/library/<dirname>-<hash>/…`
(renv 1.2.2, with NO `RENV_PATHS_*` env vars set — verified); the exact
root is version/config-dependent, so locate it portably with
`Rscript -e 'renv::paths$library()'` from each checkout rather than
assuming the pattern. Fastest fix when the worktree is same-machine and
same-lockfile: symlink the worktree's hashed library dir to the main
checkout's (`ln -s <main-lib-parent> <wt-lib-parent>` after removing the
empty one) instead of re-running `renv::restore()`. Note `RENV_PATHS_LIBRARY`
did NOT take effect for this (renv still bootstrapped its own path); the
symlink did. Also: renv intercepts `install.packages` and resolves ALL of
`DESCRIPTION`'s GitHub remotes first — in a proxy-restricted session that
403s on out-of-scope `api.github.com` calls, even a plain CRAN install
fails; bypass with `R_PROFILE_USER=/dev/null Rscript -e
'.libPaths("<lib>"); install.packages(...)'`. That bypass works even from
inside the project directory — R's user-profile search checks the CURRENT
directory for `.Rprofile` before the home directory (see `?Startup`), so
the project `.Rprofile` occupies the user-profile slot and
`R_PROFILE_USER` overrides it (verified empirically: renv unloaded with
the override, loaded without). `Rscript --no-init-file` is an equivalent
alternative. (rme OOM investigation, 2026-07-17.)

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
- **`mcp__github__actions_list` / `list_workflow_runs` returns HUGE objects**
  (full repo metadata embedded per run, ~30-60KB even at `per_page: 1`), which
  blows the tool-output cap and gets saved to a file. To read a run's
  status/conclusion cheaply, prefer `actions_get` (`get_workflow_run`, single
  object) or parse the saved file with `python3 -c "json.load(...)"`; don't keep
  re-listing.
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

## markdownlint / markdownlint-cli2
- **MD060/table-column-style is a real rule, present in `markdownlint-cli2@0.22.1`**
  (added in a recent markdownlint version; the `@claude` reviewer's rule list is
  outdated — it claims rules "top out at MD058", but `MD060/table-column-style` is a
  distinct real rule).
  Under default config it fires ~330 times on the ai-config corpus (2026-06 snapshot;
  count grows as files are added; every table with compact pipe style).
  Reproduction (move aside `.markdownlint-cli2.jsonc` first):
  `npx markdownlint-cli2@0.22.1 "**/*.md" "!codex-skills/**"`. The disable in
  `.markdownlint-cli2.jsonc` is load-bearing; do not remove it on the reviewer's say-so
  — rebut with the reproduction command. (Hit on ai-config#267.)
- **Introducing markdownlint to a legacy corpus — baseline strategy.** Run with all
  defaults first (no config): collect the full violation list. Disable every failing rule
  to achieve a green baseline with zero corpus churn. Re-enable rules incrementally after
  targeted fix passes. This prevents flooding CI with hundreds of pre-existing violations.

## Custom subagents (`.claude/agents/*.md`) — Bash is a write-access loophole

The `tools:` frontmatter field (comma-separated, e.g. `tools: Bash, Read,
Grep, Glob`) is the correct, harness-enforced way to restrict a custom
subagent — confirmed against the real docs
(<https://code.claude.com/docs/en/sub-agents>). But blocking `Edit` and
`Write` does **not** make an agent read-only if it still has `Bash`: shell
commands (`sed -i`, `echo >`, `git commit`, `renv::update()` without
`check = TRUE`) write to the filesystem regardless of which Claude tools are
in the allowlist. Only an agent with *no* `Bash` (e.g. `WebSearch, WebFetch,
Read, Grep, Glob`) gets a genuine harness-enforced read-only guarantee.
When an agent needs `Bash` for read-only shell checks (`grep`, `gh api`,
`git status`), describe the isolation honestly as "no Edit/Write tool use;
avoiding write-capable shell commands is instruction-level discipline" —
don't claim an unconditional "nothing can be modified" guarantee. (Caught
across three review rounds on ai-config#341, `hallucination-detector` and
`dependency-auditor`.)

## Office Open XML (.docx / .xlsx) — editing committed content
- `.docx`/`.xlsx` are zip archives. To strip or edit content (e.g. remove a sensitive
  link from a committed Word doc): `unzip` the file, edit `word/document.xml` for body
  text, and edit `word/_rels/document.xml.rels` for hyperlink **targets** — a clickable
  URL's address lives in the `.rels` `Target`, not just the visible `<w:t>` text, so
  delete both the `<w:hyperlink r:id="rIdN">...</w:hyperlink>` element and its matching
  `<Relationship Id="rIdN" ... Target="...">` to remove link and address.
- Re-zip from the extracted dir: `zip -r -X out.docx '[Content_Types].xml' _rels docProps word`
  (plus `customXml` if present). Verify with `unzip -t out.docx` and re-extract + grep to
  confirm the removed strings are gone before committing. (Done on ucdavis/bcs#237 to strip
  an internal SharePoint URL and a server reference from a to-do doc.)

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

## ScheduleWakeup is scoped to `/loop` dynamic mode --- use `send_later` for ad-hoc waits

`ScheduleWakeup` requires a `prompt` param and is meant to re-arm a `/loop`
session's next firing (its own docs say to pass the same `/loop` input back,
or the `<<autonomous-loop-dynamic>>` sentinel). Calling it outside a `/loop`
context --- e.g. to arm a plain "check back on this PR in 5 minutes" wait ---
throws `InputValidationError: prompt is missing`, since there's no `/loop`
input to hand it. Use `mcp__Claude_Code_Remote__send_later` (or the harness's
plain wakeup tool, if present) for a one-off self check-in instead; reserve
`ScheduleWakeup` for actual `/loop` iterations. See `send_later` mid-session
availability above for the fallback (`CronCreate`) if it disappears.
(ai-config#455/gha#216, 2026-07-03.)

**Correction: the validation error is about a missing `prompt`, not about
being outside `/loop` per se.** In a remote/web session, calling
`ScheduleWakeup` with an explicit, self-written `prompt` string (not the
`/loop` sentinel) for a plain ad-hoc check-in did **not** throw
`InputValidationError` --- it accepted the call, returned a confirmed clock
time, and the wakeup fired as scheduled. This is a workable fallback when
`send_later` itself is unavailable or repeatedly failing (e.g. an MCP server
mid-reconnect) --- supply your own full prompt text rather than assuming the
tool rejects non-`/loop` calls outright. (ai-config#583/#585 session,
2026-07-16: `mcp__Claude_Code_Remote__send_later` failed three times in a row
with "Tool permission stream closed before response received"; `ScheduleWakeup`
with a custom prompt worked immediately both times it was tried as a fallback.)

## In a plain local Claude Code session, `ScheduleWakeup` can accept an ad-hoc call but silently fail to fire

This is a DIFFERENT harness/observation from the entry above (that one is the `Claude Code Remote`
MCP server's `ScheduleWakeup`; the "rejects non-`/loop` calls with a validation error" characterization
was corrected by the block above it --- the error is about a missing `prompt`, not the non-`/loop`
context, and a supplied `prompt` works fine there).
In a plain local Claude Code CLI session, `ScheduleWakeup` accepted an arbitrary one-off
`{delaySeconds, prompt, reason}` call with no error and returned a confirmed clock time (e.g.
"Next wakeup scheduled for 08:27:00") -- but the scheduled re-invocation never actually fired.
Observed twice in a row in the same session: the user had to send a message directly each time
before work resumed, well past the confirmed time. Root cause unconfirmed from inside the
conversation (no introspection into harness wakeup-delivery internals) -- plausible candidates are
a genuine at-least-once delivery gap for ad-hoc (non-`/loop`) wakeups in this session type, or the
pending wakeup being silently superseded/dropped when a real user message arrives first rather than
double-delivering. Either way: don't treat a confirmed `ScheduleWakeup` result as a guarantee of
resumption in a plain local session -- prefer a `Monitor`/background-Bash wait (which reports back
via the harness's own task-completion notification, not a separately-scheduled wakeup) when the
condition being waited on is itself observable via a command, and treat `ScheduleWakeup` as
best-effort. (Sparta gii-ffdb93 session, 2026-07-14.)

## Monitor scripts: don't pipe a `grep -q` into another `grep` -- `-q` suppresses stdout too

`grep -q` is silent by design -- it exits 0/1 and prints nothing, even on a match (unlike `-l`,
which prints the matched filename, or `-c`, which prints a count -- only `-q` produces zero
stdout). Piping its (empty) stdout into a second `grep -qi "..."` therefore ALWAYS sees an empty
input and ALWAYS fails to match, regardless of the actual content -- e.g.
`gh pr checks N | grep -qv "pending" | grep -qi "^check-name.*(pass|fail)"` silently never fires,
looping until the `Monitor` call's own timeout kills it, with no error to signal the mistake (the
loop just runs quietly and "times out" looking like slow CI rather than a broken filter). Test the
condition directly against the ORIGINAL command's output instead of chaining greps:
`line=$(gh pr checks N | grep "^check-name"); ! echo "$line" | grep -qi pending && echo "$line"`.
More generally: before arming a `Monitor` loop, mentally trace what each pipe stage's STDOUT
actually contains -- a `-q` flag upstream of a later stage that reads stdout (or `-l`/`-c`
replacing the original content with just a filename or count) is
the tell. (Sparta gii-ffdb93 session, 2026-07-14: caught only by comparing the monitor's silence
against a manual `gh pr checks` call showing the check had already resolved.)

## Evergreen-conditional citation phrasing can still regress in adjacent prose

`shared/workflow/challenge-ambiguous-terminology.md`'s "cross-repo citations
have a merge-order trap" note prescribes evergreen-conditional phrasing
("proposed in `<repo>#<PR>` --- once merged, the fragment lives at `<path>`
there") specifically so a citation never needs a follow-up edit. That
phrasing held up correctly once applied --- but while writing the *PR
description* for the companion PR, a draft sentence ("once this merges, that
citation should be tightened to the standard present-tense form") reintroduced
the same future-edit-fragility anti-pattern the citation fix had just avoided,
one level up. Caught before pushing by re-reading against the fragment's own
"never needs editing" design intent, not by a reviewer. When writing about an
evergreen-conditional citation elsewhere (a PR description, a commit message),
don't promise a future tightening --- the whole point of that phrasing is that
none is needed. (ai-config#455, 2026-07-03.)

## Wiring ai-config skills/memories into a consumer repo's `claude` bots

`bootstrap.sh` only reaches local CLI sessions --- a consumer repo's
`claude`/`claude-code-review` bots (running via `d-morrison/gha`'s reusable
workflows and `anthropics/claude-code-action`) get nothing from it. The
pattern that worked, with no workflow changes needed, on `d-morrison/rme#982`
and `ucdavis/epi204#360`:

1. `git submodule add https://github.com/d-morrison/ai-config.git .ai-config`
   in the consumer repo.
2. Replace any hand-copied `.claude/skills/<name>/SKILL.md` (these drift ---
   confirmed via `diff` against ai-config's canonical copy before removing)
   with a **committed symlink** `.claude/skills -> ../.ai-config/skills`, so
   all of ai-config's skills become discoverable, not just the one that was
   hand-copied. `.claude/commands/` was left as-is in both repos --- those
   were genuinely project-specific, not ai-config duplicates.
3. Check `.gitignore` for a blanket `.claude/*` ignore (rme had one, with an
   existing `!.claude/commands` exception already carved out for the same
   reason). If it's there, add `!.claude/skills` alongside it, or `git add`
   silently skips the new symlink as ignored. If `.claude/skills/` was
   already tracked as a real directory, also run
   `git rm -r --cached .claude/skills` first, to clear it from the index
   before the symlink can be staged in its place.
4. Confirm `checkout-submodules: true` (or an unconditional
   `git submodule update --init --recursive`, as in rme's bespoke `claude.yml`)
   is already set on both bot workflows --- both repos already had it, so no
   workflow edit was needed.

The committed symlink survives `claude-code-action`'s `restoreConfigFromBase`
(which wipes/restores `.claude/` from the base branch on PR-triggered runs)
because it's part of that committed base --- this is the same technique
ai-config's own repo already uses for its own `@claude` bot. `memories/` and
`shared/` get no equivalent auto-load mechanism (Claude Code doesn't scan a
project memories folder the way it does skills), so they're just readable
on disk, not injected into context automatically --- unless the consumer's
own `CLAUDE.md` explicitly pulls specific files in with Claude Code's
`@path` include syntax, e.g. `@.ai-config/memories/tools.md` or
`@.ai-config/shared/workflow/ardi.md` (the path is `.ai-config/`-prefixed
in a consumer repo, unlike ai-config's own `@claude` bot, which resolves
`@shared/...` straight from the repo root --- see this repo's own
`README.md`, "Shared content (`shared/`)").

Two caveats a reviewer raised are worth pre-empting rather than leaving as
open questions.

A pinned submodule SHA that isn't `ai-config`'s current tip is still
fetchable with `git fetch --depth 1 origin <sha>` --- GitHub's shallow-clone
protocol supports fetching any reachable commit, not just branch tips.

**A `--depth 1` shallow clone gives a bogus merge-base, so a `git log A..B`
/ `git diff A..B` range against another branch shows the *entire* repo as
added.** In a shallow clone the histories of two branches share no common
ancestor git can see (it's truncated), so `origin/main` and a feature branch
appear fully disjoint --- `git log <branch>..origin/main --stat` reports
hundreds of files / thousands of insertions that aren't real, and a real
`git merge origin/main` produces spurious mass conflicts. Don't run
merge/diff-vs-main operations on a shallow clone. What *is* reliable on a
shallow clone: single-tree reads (`git show origin/main:<file>`,
`git cat-file`) --- they read the fetched tip's tree directly, no merge-base
needed. `git fetch --depth N origin <branch>` deepens enough history to make
a real merge-base available if you must merge. (Hit resolving
UCD-SERG/serocalculator#503's altdoc chain, 2026-07: a `--depth 1` altdoc
clone made `recursive-qmd-search..origin/main` show 272 files / 14k
insertions, all an artifact; the `git show origin/main:R/utils.R` tree reads
in the same session were accurate.)

A fine-grained `SUBMODULES_TOKEN` scoped to a private submodule (e.g. rme's
`latex-macros`) also authenticates a newly-added *public* submodule, since
public repos need no authentication --- confirmed empirically by the PR's
own `claude-review` check (which runs with submodule checkout on) completing
successfully. (rme#982, epi204#359/#360, 2026-07-04.)

## Windows/Git Bash: `core.fileMode=false` silently blocks executable-bit fixes

On a Windows checkout with `core.fileMode=false` (common, since NTFS has no
native Unix execute bit), a plain `chmod +x <file>` followed by `git add`
does **not** register a mode change with git at all — `git diff --stat` shows
nothing, and the file stays `100644` in the index/next commit, even though the
filesystem-level chmod itself succeeded. Fix by writing directly to the index
instead of relying on the stat-based diff: `git update-index --chmod=+x
<file>`, then verify with `git ls-files -s <file>` (should read `100755`) or
`git diff --cached` (shows `old mode 100644` / `new mode 100755` headers).

**Why this matters beyond the mechanic:** a missing executable bit on a script
a CI workflow invokes *directly* (not via `bash script.sh`) fails at runtime
with `Permission denied` / exit 126 — a failure mode invisible to a normal
content-diff code review, since reviewing a diff shows added/changed lines,
not file-mode metadata. This let a broken script merge to `main` via a
reviewed, "Ready for merge" PR (`d-morrison/gha`-reviewed
`Lacaedemon/sparta` PR #634, 2026-07-03) and then break the `demo` CI job on
every *other* open PR that subsequently merged `main` in. When a PR adds a new
executable script (a `tools/ci/*.sh` invoked directly, not sourced), verify
its committed mode explicitly (`git ls-tree HEAD -- <path>`, compare against
an existing sibling script) rather than trusting the code review alone to
catch it.

## Two worktrees on the same branch name silently move a shared ref, not a conflict error

Git *should* refuse `git checkout -B <branch>` (or checking that branch out)
when another worktree already has it checked out — but in practice, creating
a second worktree for a branch name a leftover worktree from earlier in the
same session still holds (e.g. via `git worktree add <path> origin/<branch>`
then `git checkout -B <branch>` inside it) can succeed without error and
silently repoint the shared branch ref out from under the first worktree.
That worktree's `git status` then shows a wall of spurious modified/deleted
files — not real data loss, just its checked-out files diffing against the
ref's new (moved) tip while its own index/working tree still reflect the old
one. Confirm via that worktree's own reflog (`git -C <path> reflog show
HEAD`) that its real last commit is still there and reachable — check with
`git merge-base --is-ancestor <that-commit> <new-ref-tip>` — before concluding
anything, but treat any push made under this collision as suspect until
verified, since it may have been built from a different, wrong base than
intended. **Prevention:** always `git worktree list | grep <branch>` before
creating a new worktree for a PR branch, especially one worked earlier in the
same session (a `wave-N-*`-style dispatch worktree is exactly the kind that
lingers). If one already exists, reuse it (`git fetch` +
`git reset --hard origin/<branch>`) instead of adding a second one on the same
name — or use a distinct local branch name if reuse isn't feasible.
(`Lacaedemon/sparta` PR #626, 2026-07-03 — recovered with no data loss, but
required a `--force-with-lease` push to fix and explicit user sign-off given
the ref-mutation risk.)

**On Windows, `~/.claude`'s real-copy consumer directories can drift far more than a quick glance suggests — check the whole corpus, not just `CLAUDE.md`.** CLAUDE.md's own "Keep ai-config and repo checkouts fresh" step 2 already says a `git pull` on the ai-config checkout doesn't propagate to `~/.claude/{skills,shared,commands,memories}` on Windows (real copies, not symlinks). In practice the drift found there can be large even in an actively-used setup: one check found `CLAUDE.md` itself missing ~10 sections, `skills/` with 56 of ~90 files differing (plus 6 new skills never copied over), `shared/` with 5 differing/missing fragments, and `memories/` with 3 of 4 files differing — accumulated silently because the per-session refresh habit checks `CLAUDE.md` (loaded every turn, so staleness there is visible) but not the other three directories (loaded on-demand, so staleness there is invisible until a skill/memory is actually needed and reads wrong). Before trusting a sync is complete, `diff -rq` (or `cp -r` unconditionally, after checking for genuine un-upstreamed local edits per the existing before-overwriting caution) all four directories, not just the one that happens to render in every prompt. (`Lacaedemon/sparta`, 2026-07-04.)

## Windows Git Bash: MSYS path conversion mangles a colon-refspec that contains a slash

Git Bash's MSYS layer auto-converts POSIX-looking arguments into Windows paths,
and the heuristic fires on *any* argument containing a `/` — including a git
refspec like `origin/main:.ai-config` (checking a submodule pin as recorded on
a branch other than the one currently checked out). The `/` inside
`origin/main` flips the heuristic on for the whole argument, and it mangles the
colon too: `origin/main:.ai-config` silently becomes `origin\main;.ai-config`,
then fails with `fatal: ambiguous argument ... unknown revision or path not in
the working tree`. A colon-refspec with no `/` before the colon
(`HEAD:.ai-config`, `some-tag:.ai-config`) is unaffected — the heuristic keys
on the slash, not the colon. Fix: prefix just that one command with
`MSYS_NO_PATHCONV=1` rather than disabling path conversion shell-wide, e.g.
`MSYS_NO_PATHCONV=1 git rev-parse "origin/main:.ai-config"`. (Hit checking
whether `Lacaedemon/sparta`'s vendored `.ai-config` submodule pin was actually
stale on `origin/main`, vs. only stale on the current feature-branch worktree
— see the `CLAUDE.md` "Keep ai-config and repo checkouts fresh" step 4 update
this same session added. `Lacaedemon/sparta`, 2026-07-04.)

## Bash tool cwd persists across calls — an easy trap when juggling sibling repo checkouts

The Bash tool's working directory carries over from one tool call to the
next within a session (per its own tool description), not just within a
single multi-line script. When a task touches several sibling repo
checkouts in the same session (e.g. `rme`, `epi204`, and their shared
`macros` submodule, each at its own path), a command issued without an
explicit `cd` silently runs wherever the *previous* call left off — not in
the repo the command's own text implies. This produced several
wrong-directory mistakes in one session: a `git log --oneline -1` meant for
`epi204/macros` instead reported `epi204`'s own root HEAD, and a `git push`
meant for `epi204` silently ran again in `rme` and printed
"Everything up-to-date" (which reads like a real, if uninteresting, result —
not an obvious error — so the mistake wasn't visually distinct from success).
When issuing single-line Bash calls across multiple repo checkouts in the
same session, either prefix every command with an explicit `cd
/path/to/repo &&`, or use `git -C /path/to/repo <command>` for read-only
checks — don't rely on remembering which directory the last call left you
in. (Session sliding the `macros` submodule pin in `d-morrison/rme` and
`ucdavis/epi204`, 2026-07-04.)

## Working several PRs in one session shares ONE working tree — commit before switching branches

Without explicit worktree isolation, `git checkout <other-branch>` in the
same session reuses the single physical working directory — there's no
per-branch sandbox. Writing a new file (e.g. a new skill's `SKILL.md`) and
then switching to a different branch *before committing* leaves that file
sitting in the working tree as an **untracked** file; git doesn't error or
warn, since nothing conflicts. If a later branch's cleanup step does
`rm -rf` on what looks like a stray generated artifact from a previous
context, it can silently delete that still-uncommitted work with no
recovery path (unlike a committed file, which survives in git history
regardless of which branch is checked out). When working multiple
issues/PRs in one session on a harness with a single shared working tree,
commit each new file immediately after writing it — before running any
cleanup command or switching to the next branch — rather than batching
several files' worth of edits before the first commit. (`ai-config` `gia`
session, 2026-07-06: a freshly-written `skills/checkpoint/SKILL.md` was
lost this way when a same-session cleanup `rm -rf` on a different branch's
leaked untracked directory swept it up too; recovered by rewriting the file
from the still-visible conversation content, but a git-invisible loss like
this can go unnoticed without that fallback.)

## Regenerate derived files BEFORE the final `git add`, not after

A generator script (e.g. `scripts/sync-codex-skill-wrappers.py`, which
rewrites every file under `codex-skills/` from `tool-mappings.yml`) can
legitimately need to run more than once in a work session — once early,
then again after a late-session `git merge origin/main` pulls in changes
the generator's inputs depend on. If the sequence is `git add <file>` →
run the generator → `git commit` (without re-running `git add` on what the
generator just rewrote), the commit omits the regenerated content even
though the working tree still has the regenerated content — a `git status`
*after* the commit would show the codex-skills files as unstaged
modifications, but a developer who only checked `git diff --staged` or
`git status` right after the earlier partial `git add` (and didn't look
again after running the generator) would miss them. This surfaces later
as a CI `validate` failure ("Codex skill wrappers are out of sync") on a
commit that looks, from its own diff, like it shouldn't have touched
`codex-skills/` at all. Always run the generator immediately before the
final `git add -A` (or explicit paths covering its output directory), not
between an earlier partial `git add` and the commit. (`ai-config` `gia`
session, 2026-07-06: this exact ordering, done on two sibling PR branches
right after merging `main` in, produced a `validate` failure on one of them
that had to be fixed with a follow-up commit.)
## Workflow `agent()` — schema validates shape, not substance

A `Workflow`-tool agent can pass its `schema` validation while returning
content that's substantively worthless — schema validation only checks
shape (does the JSON have the right fields/types), never substance (is
the content real analysis or a placeholder).
Don't trust a synthesis-stage `agent()` result at face value just because
it validated — skim the actual content before building on it, the same as
any other agent's report. If it looks wrong or too trivial for the input
it was given, read `<transcriptDir>/journal.jsonl` (each earlier agent's
real return value is recorded there — a directly-observed path from the
transcript directory during the incident below, and the primary artifact
per the Workflow tool's own spec; `agent-<id>.jsonl` files are that spec's
documented fallback for when no journal is available, not a competing
name for the same file) and redo the synthesis by hand from those results
rather than trusting the degenerate output.
(Learned on `ai-config#554`, 2026-07-14: a Design-phase agent, handed
genuine, detailed findings from four parallel survey agents, returned
`{"summary":"test","changes":[{"gap":"test",...}]}` — a literal
placeholder that still matched the schema. Caught before treating it as
"no changes needed"; the actual gap analysis and PR content were
synthesized by hand from the survey agents' real `journal.jsonl` results
instead. This is also why `shared/workflow/when-to-orchestrate.md` now
carries a "schema checks shape, not substance" reminder in its
model/effort-routing section — this incident is the concrete case behind
that addition.)

## Edit two-step move — delete-only silently drops content

Relocating a block of text with `Edit` (an `old_string` that spans the
block plus its surroundings, a `new_string` that omits the block,
intending to re-insert it via a *second*, separate `Edit` at the new
location) silently drops the content if that second `Edit` never actually
gets issued — the diff then shows a pure deletion, and nothing errors to
flag the gap.
This is a different failure from the "restoring/reconstructing a full
file's content" bullet in `preferences.md` (that one is about transcription
fidelity — accidentally omitting, altering, or inventing content while
intending a faithful reproduction from memory); here the exact right
content is known throughout, but a two-step move degrades to a one-step
delete when the second step is skipped. The same fix applies either way —
diff the result against the base branch — but check specifically that the
moved content is **present** at its new location, not just that the old
location no longer has it.
(Learned on `ai-config#554`, 2026-07-14: a fix instructed as "move this
3-line bullet to after paragraph Y" was executed as delete-the-bullet
only, leaving the file's net diff against `origin/main` empty for that
bullet entirely. Caught by a bot review reading the actual diff, then
independently reconfirmed with `git diff origin/main -- <path>` before
trusting the follow-up fix.)

## `codex exec`: the auto-mode classifier denies `--sandbox danger-full-access`

Claude Code's auto-mode permission classifier **denies** a `codex exec` invoked
with `--sandbox danger-full-access` (reason: "[Create Unsafe Agents] ... runs an
autonomous agent with sandbox isolation and approval gates disabled", plus
"[Safety Bypass Flag]"). A user grant to *use* codex — even a standing one, e.g.
"use codex whenever examining the actual data" — does **not** extend to running
it with the sandbox disabled; that's a separate permission the user never named.

Use `--sandbox workspace-write` instead. It reads/writes inside the repo and
runs local interpreters, which covers essentially every delegation case
(inspecting a large data file, running an `Rscript`/`python` analysis, drafting
into a scratch file). Don't reach for full-access as the reflex — reach for it
never, and re-scope the task if it seems to need it.

`--sandbox read-only` also exists but blocks writing the temp script most
analysis delegations need, so `workspace-write` is the practical default.

## `codex` is NOT a read-only tool — `-s read-only` still executes commands

`codex exec -s <mode>` (long form `--sandbox`) takes `read-only`,
`workspace-write`, or `danger-full-access`. "Read-only" is a sandbox flag you
choose, not a property of codex — so don't treat codex as a read/analyze-only
delegate:

- **codex can write and execute.** `-s workspace-write` lets it create files and
  run builds, so it can take execution-heavy implementation work, not just
  reading and analysis.
- **Even `-s read-only` runs model-generated shell commands** — the mode
  restricts *filesystem writes*, not command execution. A `-s read-only` codex
  can still invoke `Rscript`, run a test, and read the result; it just can't
  modify files. (This is why the `workspace-write` default in the section above
  matters for *writing* a temp script, not for running one.)

So when deciding whether codex can take a task, ask what sandbox mode it needs,
not whether codex "can write." (Corrected on `ucdavis/bcs`, 2026-07-09:
over-generalized a "`-s read-only` for read/analyze" default into a capability
limit when asked why a delegation wasn't happening.)

## `codex` can report "logged in" while every `codex exec` fails on auth

`codex login status` prints "Logged in using ChatGPT" and yet `codex exec` dies
with:

> Your access token could not be refreshed because your refresh token was
> already used.

The status check reads the stored credential; it does not exercise the refresh.
So a stale/consumed refresh token looks healthy right up until you actually run
something. Re-running `codex exec` just reproduces it — this does not
self-resolve.

Fix: a **full re-login**, which is interactive and therefore the user's to run:

```
codex logout && codex login
```

Ask the user to run it with the `! ` prefix so the output lands in the session.
Verify with a real round-trip (`codex exec --skip-git-repo-check "Reply with
exactly: CODEX_OK"`), **not** with `codex login status` — which is what misled
you in the first place. (Hit on `ucdavis/bcs`, 2026-07-13: the auth failure
blocked a data-examination step for an entire session under the user's standing
"use codex whenever examining the actual data" rule, until they reset it.)

## Stacked PRs across a squash-merge: rebuild via cherry-pick, and verify force-pushes actually landed

Two git/GitHub behaviors that compose on stacked PRs (learned on
Lacaedemon/sparta #883→#884, 2026-07-15):

- When the base PR of a stack merges (with branch auto-delete), GitHub
  auto-retargets the stacked PR to the new base — no manual retarget needed,
  and a manual `gh api ... -f base=main` after the fact 422s (something to
  the effect of "already exists") precisely because it already happened.
  But if the base was **squash-merged**, the stacked branch still carries
  the base's original commits, which are no longer ancestors of main —
  `git merge origin/main` conflicts on the very content that already landed.
  Rebuild instead:
  `git checkout -B <branch> origin/main && git cherry-pick <own-commits...>
  && git push --force-with-lease`.
- **A rejected `git push --force-with-lease` is easy to miss in a compound
  command** — after `checkout -B`, the remote-tracking ref can be stale, the
  push's rejection prints to stderr but scrolls past in long output, and the
  PR keeps serving the old head (showing merge conflicts that look
  unexplainable). Verify a force-push actually landed by re-reading the PR
  head (`gh pr view N --json headRefOid`) and comparing to the local SHA —
  then `git fetch` + retry the push if it didn't. Don't diagnose PR state
  until the head matches.

## Personal machine setup (shiva cluster — not shared in project repos)

Personal, machine-specific tooling on the user's shiva login node (UCD PHS HPC),
deliberately NOT documented in shared project repos — collaborators don't have
these.

- **GitHub PAT stored encrypted, never as plaintext.** The user won't keep auth
  credentials as plaintext on this shared cluster (no keyring daemon available,
  no sudo to install one).
  - **At rest:** `~/.gh-token.gpg` (GPG symmetric, AES256, mode 600), created via
    `~/.local/bin/encrypt-gh-token.sh`.
  - **Unlock for a session:** `gh-unlock` (a zsh function) decrypts and exports
    `GH_TOKEN`; `gh-lock` clears it. `gh` then picks `GH_TOKEN` up from the env.
  - **Never run `gh auth login`** — it re-writes plaintext to
    `~/.config/gh/hosts.yml`. If asked to authenticate `gh` on this machine,
    remind the user to run `gh-unlock` instead.
  - **Git-over-HTTPS fallback** when `gh-unlock` can't run (an expired gpg-agent
    passphrase cache needs an interactive pinentry a non-interactive Bash tool
    can't supply): if `gh auth status` already shows a token from `hosts.yml`,
    route git through gh's credential helper inline —
    `git -c credential.helper='!gh auth git-credential' fetch/push ...` — putting
    the `-c` directly on the git command (don't pass it via a shell variable; zsh
    mangles the quoting).
  - SLURM jobs don't need the PAT; it's only for interactive `gh` / Claude Code.
- **`claude-alloc` / `codex-alloc` run agent sessions in a SLURM slice**, never
  compute on the login node directly (`claude-alloc` = Claude Code, `codex-alloc`
  = Codex CLI). Both wrap `~/bin/tui-alloc` (`~/bin` is on PATH via `~/.zshrc`).
  - Defaults: 8 hwthreads (4 physical cores), `--mem=32G`, `--time=12:00:00`,
    `--exclude=c1` (the GPU node). Override per-launch with `ALLOC_CPUS`,
    `ALLOC_MEM`, `ALLOC_TIME`.
  - **Always set `--mem`** (the launchers do): the `normal` partition uses
    `CR_CORE_MEMORY` with `DefMemPerNode=UNLIMITED`, so omitting `--mem` grabs the
    node's whole ~772G and locks everyone else out.
  - **Name the conda env for bcs work:** `ALLOC_CONDA_ENV=bcs claude-alloc`. A
    `chpwd` hook sets it automatically inside `~/Projects/bcs*` checkouts. The
    launchers are otherwise project-agnostic — they only read `ALLOC_CONDA_ENV`.
  - **Exit takes two steps** (salloc -> srun --pty zsh -> agent): quit the agent
    (`/exit`) to drop to the allocation shell (slice still held), then `exit` the
    shell to release the slice. Force-release with `scancel $SLURM_JOB_ID`; check
    for a forgotten slice with `squeue -u $USER` (job name `claude`/`codex`).
  - Full usage/exit doc: `~/.config/tui-alloc/README.md`.

## quarto-actions/setup with tinytex — two shared-runner failure signatures (win, 2026-07)

- **`ERROR: Unable to determine latest release for rstudio/tinytex-releases / 403 - Forbidden`**
  during "Set up Quarto": `quarto install tinytex`'s latest-release lookup is an
  unauthenticated GitHub API call, and shared runners intermittently rate-limit it.
  Fix: `env: GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` (or `${{ github.token }}`) on the
  setup step. gha's `preview` composite already does this; `quarto-publish` gap filed
  as gha#270. (Broke ucdavis/win's preview/publish repeatedly; fixed in win PR #69.)
- **`renv::restore()` fails compiling `curl` ("libcurl was not found")** on
  current ubuntu runner images: the R build libs are no longer preinstalled, so any
  renv repo needs an explicit apt step. Working set for a typical
  curl/openssl/xml2/gert/V8/igraph/ragg/textshaping lockfile:
  `libcurl4-openssl-dev libssl-dev libxml2-dev libgit2-dev libnode-dev libglpk-dev
  libfontconfig1-dev libfreetype6-dev libharfbuzz-dev libfribidi-dev libpng-dev
  libtiff5-dev libjpeg-dev` (gha's `preview` reusable workflow's default
  `apt-packages` list is the fuller reference).
- Diagnostic order matters: the TinyTeX 403 masks the renv gap — fixing the first
  failure surfaces the second on the next run, so read each new failed run's log
  fresh instead of assuming the prior diagnosis still applies.

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

## WORDLIST alphabetization — Copilot vs claude reviewer collation conflict

`spelling`-package WORDLISTs sort in **two case-grouped blocks**
(uppercase-leading then lowercase-leading), each **case-insensitively** sorted
within the block — the order `spelling::update_wordlist()` emits under a UTF-8
locale. The claude reviewer enforces that order; Copilot sometimes flags the
same lines wanting ASCII/byte order (e.g. claiming `PP` must precede
`Positivity`). Don't flip-flop between the two: keep the case-insensitive
convention, verify each block **separately** with `sort -f -c`
(e.g. `grep '^[A-Z]' inst/WORDLIST | sort -f -c` for the uppercase block —
a whole-file `sort -f -c` false-fails at the block boundary even when the
file is correctly formatted), and rebut Copilot citing the
tool's own emitted order — the rebuttal stuck (Copilot dropped it on
subsequent rounds; ucdavis/win#69, 2026-07-16).

## Remote-session push proxy: branch DELETION silently no-ops

The Claude Code web/remote push proxy accepts branch pushes but silently
refuses branch deletions: `git push origin --delete <branch>` (and the
`:refs/heads/<branch>` refspec form) reports `Everything up-to-date` (or
`fatal: the remote end hung up unexpectedly` followed by up-to-date) while
`git ls-remote` confirms the remote branch still exists. There is no error
that says "deletion not allowed" — the success-looking output is the trap.
Verify with `git ls-remote --heads origin <branch>` after any deletion
attempt, and when it survives, hand the deletion to the user (GitHub UI
Branches page) instead of retrying. (ucdavis/rampp, 2026-07-17: deleting the
orphaned `claude/split-survival` stack branch per its tracking issue no-op'd
twice; delegated to d-morrison in the issue-close comment.)

## Stacked-PR series: a closed base PR strands the whole downstream stack silently

When PRs are stacked A <- B <- C and the PR for A is closed unmerged (even
accidentally — check `closed_by`/`closed_at` via the API rather than
inferring a mechanism), B and C keep "working": their reviews run, they go
clean, and they MERGE — but into A's head branch, which no longer has any
open PR to main. Nothing errors; the reviewed content is simply stranded on
an orphaned branch. Detection: (1) closed-unmerged PRs whose head branches
still exist with commits not on main (`git rev-list --count
origin/main..origin/<branch>`), (2) branches with substantial unmerged
content and no PR at all (never-PR'd forgotten work is found the same way).
Recovery that worked well: **re-cut the stranded reviewed content from the
stack's tip** (it embodies every review round's refinements — taking the
older pre-review copies from elsewhere re-litigates settled findings), layer
any later improvements from other branches on top, and verify per function
that the re-cut supersedes the stranded branch before deleting it
(`git grep -E '^[\w.]+ <- function'` on both refs, set-difference the
names). Also verify the close reason from the API record: the earlier
"auto-closed when its base branch was deleted" explanation was disproven by
`closed_at` predating the base's merge by 8 days — `closed_by: <user>` with
no comment was the actual record. (ucdavis/rampp #127 closed 2026-07-05;
PRs #128/#129 merged into the orphaned `claude/split-survival`; re-cut
as #136–#138, 2026-07-16..17.)

## CI failure on untouched files: diff the installed-package line between last-green and first-red logs

When a CI job fails on files the PR never touched, suspect toolchain drift
and make the version comparison the FIRST diagnostic: fetch the last
passing run's job log and the failing run's, and grep each for the suspect
package's sessioninfo line. A dev-tracking install (`extra-packages:
r-lib/lintr` in r-lib/actions) makes this a recurring class, and the log
line pins it exactly. Two 2026-07 instances in ucdavis/rampp: (1) `lint`
red on 31 untouched files — `lintr 3.3.0.9000 Github(@4579471)` green on
07-13 vs `3.4.0.9000 Github(@178882f)` red on 07-16 (lintr 3.4.0 dropped
double-indent formals, r-lib/lintr#2830); fixed by restyling, since the new
style is valid under both versions. (2) `macos-latest` R CMD check red
repo-wide — flextable 0.10.0 hit CRAN with no macOS binary yet, forcing a
source build that needs XQuartz libs the runner lacks; self-healed when the
binary appeared ~7h later, so the right move was retry-later
(`rerun_failed_jobs`), not a code change.

## Fact-check code comments' factual claims — a false one can survive many review rounds

A code comment asserting a checkable fact ("grepl() returns NA for NA
input") is prose the review bots tend to accept as given, especially when
it justifies adjacent defensive code: this one survived ~10 independent
review passes across two PRs before being caught — and only because a
WRONG Copilot finding on a third PR prompted an empirical check
(`grepl("a", NA)` is FALSE; it's `sub()`/`gsub()` that propagate NA — and
the guard it justified was load-bearing for a different reason:
`NA != ""` yields NA). Verified empirically in R 4.6.1
(`grepl("a", NA)` → FALSE; `sub("a", "b", NA)` → NA;
`gsub("a", "b", NA)` → NA; `NA != ""` → NA), and by `?grep` itself:
"Both 'grep' and 'grepl' take missing values in 'x' as not matching a
non-missing 'pattern'." When writing or reviewing a comment that states a
language/library behavior, run the one-liner that checks it instead of
trusting plausibility; when a reviewer finding is wrong, check whether the
code's own documentation made the same wrong claim — the finding often
mirrors prose it read in-context. This same claim was later re-disputed
by a reviewer citing a doc line that does not exist in `?grep` — a
reminder that the empirical one-liner outranks any quoted documentation,
including a reviewer's. (ucdavis/rampp #138/#111, 2026-07-17;
re-verified on ai-config#611, 2026-07-18.)

## Resuming a subagent mid-run tends to restart its long check, not resume it — verify the process directly before nudging it again

When a background subagent pauses its own turn while a long-running local
check (a full test/coverage suite, a build) is still executing in the
background, sending it a follow-up message to "check the result" does NOT
reliably make it poll the existing run — in practice it tends to just
launch a FRESH invocation of the same check and wait on that one instead,
discarding the earlier run's progress. This repeated three times in a row
in one session (each resume costing ~4-6 minutes of the agent's own
reasoning plus a full ~15-20 minute check re-run) before switching
strategy. The subagent isn't lying about "waiting for the background run"
— it genuinely doesn't have a reliable way to reattach to a shell command
it started in an earlier turn, so a fresh nudge reads as "go check" and it
takes the simplest interpretation: run it again.

**Fix: verify the actual process state yourself before resuming, and when
you do resume, hand the agent unambiguous evidence so it doesn't restart
anything.** From the orchestrating session (not the subagent), check for a
live process directly (`tasklist | grep -i <binary>` in Git Bash/Cygwin,
`findstr /I <binary>` in native Windows CMD, `Get-Process -Name "..."` for
start-time/age via PowerShell, or `pgrep`/`ps` elsewhere) and wait on it
directly (`Wait-Process -Id <pid> -Timeout <seconds>` on Windows, or a bash
poll loop) rather than just re-pinging the
subagent and hoping. Once the process has genuinely exited (confirm via a
fresh process check, not just elapsed time), resume the subagent with the
specific evidence in hand ("I've confirmed no such process is running as
of `<timestamp>`; the run already finished — do NOT start a new one, read
its output and report") — this stops the same restart loop from recurring
on the next resume. This is strictly better than either blindly trusting
"still waiting" messages (which can repeat indefinitely) or arbitrarily
capping the number of resumes (which risks cutting off a genuinely
long-running check before it finishes).

This generalizes beyond any one tool: the same pattern applies to any
subagent orchestration where a delegated agent's own background command
outlives its turn — verify state from the outside, don't just ask again.
(Sparta `gii-mwc` session, 2026-07-19: hit on two independent subagents in
the same session, one implementing a casualty-reflow feature and one a
maneuver feature, each running the project's own `tools/check.sh` full
suite — direct process verification via PowerShell resolved both.)

## A diff-scoped local check silently no-ops on an empty/uncommitted diff — commit before running it, not after

A repo's own pre-push check script can include steps that gate on `git diff
<merge-base> HEAD` (a comment-citation scanner, a units-convention linter, a
patch-coverage calculator) rather than the raw working tree. If you run such
a script against **uncommitted** changes — reasoning "let me verify before I
commit" — the diff-scoped steps compare HEAD against itself (or whatever the
last commit was), see no changes, and silently report a clean pass ("no
GDScript changes in this diff") without having examined your actual edits at
all. Only the disk-based steps in the same invocation (a plain test run, a
character-encoding scan of the working tree) give real signal; the
diff-scoped ones are pure no-ops that LOOK identical to a genuine clean
result in the printed summary.

This cost one delegated subagent roughly two hours and most of a million
tokens in one session: it wrote a real, working feature, then spent that
time re-running the full check suite (each pass ~15-20 minutes) against its
own uncommitted working tree, never noticing that three of the five
requested checks were quietly checking nothing. The fix, once diagnosed,
was mechanical — commit first, then re-run the checks against a real diff —
but the diagnosis itself only happened after the orchestrating session
noticed a suspicious mismatch (two full turns and heavy token spend, yet
`git log`/`git status` showed no commits and no uncommitted changes) and
asked the agent directly why there was no visible progress.

**How to apply:** before trusting a "PASS" from any check step whose own
description implies it scopes to a diff (a comment scanner, a
units-convention check, coverage-of-new-lines), confirm there IS a
non-empty diff for it to have scanned — commit (even a rough, uncommitted-
but-final draft) before the verification pass, not after. When briefing a
subagent to implement-and-verify a feature, say so explicitly: "commit your
changes before running the diff-scoped checks (comments/units/patch_coverage
in this repo's `tools/check.sh`), not after — they silently no-op against
an empty diff." And when an orchestrating session sees a subagent burn
much more wall-clock/tokens than its own diff would justify, checking
`git log`/`git status` directly is a fast, decisive way to catch this class
of problem rather than trusting the subagent's own narration that it's
"still verifying." (Sparta `gii-mwc` session, 2026-07-19, `tools/check.sh`'s
`comments`/`units`/`patch_coverage` steps.)

## Rex + base regex engines in R

- `rex::rex()` patterns often emit PCRE constructs; do not pass those directly to APIs that use POSIX regex defaults (for example `list.files(pattern = ...)`). List/filter in two steps and match with `grepl(..., perl = TRUE)` (and similarly `gregexpr`/`gsub` with `perl = TRUE`) when using rex-built patterns.
- `rex` shortcut symbols (`any_spaces`, `spaces`, `capture`, etc.) are not exported as `rex::name`; either keep them unqualified within `rex::rex(...)` and register shortcuts for R CMD check, or build explicit fragments with exported APIs (`rex::regex`, `rex::escape`) so static analysis does not depend on shortcut registration side effects.

## Windows Git Bash: `python`/`python3` may resolve to the Store stub; use `py`

On at least one Windows setup, `python` and `python3` both resolve on
`PATH` inside the Git Bash tool, but only to the Windows Store
install-shortcut stub. They print `Python was not found; run without
arguments to install from the Microsoft Store, or disable this shortcut
from Settings > Apps > Advanced app settings > App execution aliases`
instead of running the script, with a nonzero exit code. The `py` launcher
(the standard Windows Python launcher, installed alongside python.org
Python) works fine and should be the first thing tried when `python3 -c
"..."` fails with that specific message — don't waste a retry loop guessing
at other causes. When scripting a small one-off transform inline (e.g. a
Bash tool call doing a targeted string replacement Edit's exact-match
failed on), resolve which launcher actually works before using it, rather
than relying on the combined exit status of `A || B` (which tells you
*something* succeeded, not *which side*): probe each candidate
non-mutating and stop if neither works, rather than assuming the last one
must be fine. Use `if`/`elif`, not a `||`-chained subshell assignment
(`(cmd && VAR=x) || ...` looks like it works but the subshell's `VAR=x`
never reaches the parent shell — verified this by testing both forms
before publishing this note) —
```sh
if python3 -c "pass" >/dev/null 2>&1; then PY=python3
elif py -c "pass" >/dev/null 2>&1; then PY=py
else echo "no working python launcher found"; exit 1
fi
```
— then invoke `$PY` for the real transform. This both avoids risking a
second, possibly destructive run of a real script under a bare `||`
fallback, and fails loudly instead of proceeding with an unverified
command if neither launcher actually works. (ai-config#635,
2026-07-22/23: hit repeatedly running `scripts/validate-skills.py`, and
again scripting a one-off text replacement after an `Edit` tool call's
`old_string` failed to match despite `grep` showing byte-identical content
in the file.)
