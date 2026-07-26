# GitHub & GitLab CLIs and APIs

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
  it 403s.** `method: rerun_failed_jobs` (and `rerun_workflow_run`, and
  `cancel_workflow_run` -- the whole `actions: write` family, so you can neither
  restart a run nor stop one) returns
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
  echo, skip it." This is easy to get wrong at a glance since a same-author
  event looks exactly like a genuine human reply demanding a response.
  **Check for the Claude Code attribution footer instead of fuzzy-matching
  body text/timing** --- every comment posted from these sessions ends with
  `_Generated by [Claude Code](https://claude.ai/code)_` per the system
  prompt's attribution-footer requirement, so a webhook event whose body
  ends with that footer is mechanically, unambiguously your own post
  (a genuine human reply won't carry it) --- a much sharper signal than
  eyeballing whether the wording looks familiar. (Hit repeatedly on
  `UCD-SERG/serocalculator#503`, 2026-07-24: several
  `add_reply_to_pull_request_comment` calls immediately produced a webhook
  event attributed to `d-morrison` quoting the reply verbatim --- each one
  a self-echo, not a new human comment, confirmed each time by re-reading
  the body rather than checking for the footer directly.)
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
- **`request_copilot_review` returns success even when Copilot's quota is
  exhausted -- the refusal arrives later, as a posted review.**
  The tool reports no error and no output whether or not Copilot will
  actually review; what comes back minutes later is a `COMMENTED` review
  whose entire body is *"Copilot was unable to review this pull request
  because the user who requested the review has reached their quota
  limit"*.
  So a clean return is **not** evidence the quota is back, and neither is
  the absence of an error --- only the posted review body settles it.
  Two further specifics:
  - The quota is **per requesting user**, not per repo or per PR, so every
    request from the same account keeps refusing until it resets, however
    many different PRs it's spread across.
  - **Latency is a weak tell, and an untested one.**
    Every refusal came back within roughly a minute of the request.
    A later request was still pending when last checked about ten minutes
    in, which is the only reason to suspect a long-pending request may be
    a real review rather than a slow refusal -- but its outcome was never
    observed, because the PR merged first.
    So treat a long wait as weak grounds for holding off on re-requesting,
    not as evidence a review is coming, and read the posted review either
    way.
  Copilot and the `@claude` reviewer fail **independently**: Copilot can be
  quota-dead while `claude-review` posts genuine verdicts at the same head,
  so a Copilot refusal is never a reason to stop checking the other one.
  (`ucdavis/rampp#111`, 2026-07-24/25: three refusals across two heads while
  `claude-review` reviewed both normally, and Copilot itself had worked on
  the same PR two days earlier.)
- **A branch ruleset can block Copilot from pushing a fix while leaving my
  own push to the same branch unaffected.**
  When Copilot reports it prepared a change but could not apply it ---
  e.g. *"Cannot update this protected ref"* --- don't infer the branch is
  write-protected for this session too: try the push.
  The corollary matters more for review triage: a Copilot-identified issue
  still sitting unfixed may be unfixed because its push was rejected,
  **not** because the fix was wrong, disputed, or deliberately dropped.
  Re-check such a finding on its own merits rather than reading "Copilot
  left it alone" as a signal it was already settled.
  (`ucdavis/rampp#111`: Copilot had prepared the `DESCRIPTION` version bump
  that `version-check` was failing on and was rejected with that error; the
  identical fix pushed fine from this session as `0c72d81`.)
- **`get_status` can return "pending / 0 checks" even after CI has finished.**
  Use `get_check_runs` for the real job conclusions (`success`, `failure`,
  `skipped`) --- but see the bullet below: it is the more reliable of the two,
  not an authoritative source.
  `get_status` aggregates
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
- **`get_check_runs` is the better of the two, but it is not authoritative:
  it can report a job as `in_progress` minutes after that job finished.**
  The entry above says to prefer it over `get_status`, which still holds ---
  but read that as "less stale", not "correct".
  `actions_get` `get_workflow_job` on the same job id returns the true
  `status`/`conclusion`, and the two disagree often enough to matter.
  The cross-check is cheap and decides it exactly, so run it rather than
  reasoning about how long the job "should" have taken.
  It is worth running in **both** directions.
  Concluding "still running" from a stale `in_progress` only wastes a wait;
  the dangerous inverse is a
  rollup that has not yet caught up with a job that has since failed, which
  is why the cross-check belongs in the declare-clean sweep
  ([`fully-clean`](../shared/workflow/fully-clean.md) criterion 1) and not
  only when something looks slow.
  Do not over-correct, either: on the same PR minutes later, an
  `in_progress` R-CMD-check was genuinely still running, and the runs
  endpoint confirmed it.
  The endpoint is unreliable, not wrong.
  (`d-morrison/altdoc#61`, 2026-07-25: three instances in one afternoon ---
  `test-coverage`, `docs-check` (completed `21:12:56`, still reported
  `in_progress` after), and one true negative.)
- **`mcp__github__actions_list` (`list_workflow_runs`) returns a full repository
  object per run -- budget accordingly, and prefer a cheaper call.** Each run in
  the response carries `repository`, `head_repository`, `actor`, and
  `triggering_actor` in full, so even `per_page: 1` runs ~30-60KB and a
  `per_page: 3` call costs several thousand tokens; a large enough response
  blows the tool-output cap and gets spilled to a file instead of returned.
  When the question is "did CI/the review run, and how did it end",
  `pull_request_read` `get_check_runs` answers it for a fraction of that, and
  `actions_get` `get_workflow_run` (a single run by ID) is the right call when
  you need one run's event/trigger/conclusion. Reserve `list_workflow_runs` for
  when you genuinely need to enumerate runs the check-runs view can't see -- the
  `action_required`/zero-job case in
  [`fully-clean`](../shared/workflow/fully-clean.md) -- and when a call has
  already spilled to a file, parse that file
  (`python3 -c "json.load(...)"`) rather than re-listing.
  (ai-config#687, 2026-07-24:
  a two-run `list_workflow_runs` call to check whether a draft PR's review had
  fired cost ~6k tokens; `get_check_runs` gave the same answer.)
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
- **Read a commit SHA back from git before citing it in a comment; never
  write one from memory.** The bullet above covers a SHA *garbled in
  transit* by WebFetch; this is the adjacent failure of never having looked
  it up at all. A PR reply that names "the commit that fixed this" is a
  checkable reference, and an invented one sends every later reader to
  nothing. `git rev-parse --short HEAD` immediately after the push costs one
  call. Correct a wrong one on the thread promptly rather than at leisure:
  an automated reviewer gathers comments when its run starts, so a
  fabricated SHA left standing gets copied into the reviewer's own verdict
  and becomes a second durable artifact to chase. (ai-config#696: a reply
  cited `0d2ec06`, which existed nowhere on the branch -- the real commit
  was `30ac111` -- and the `@claude` reviewer quoted `0d2ec06` back in its
  next review before the correction landed.)
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
- **The MCP write tools silently drop `<https://...>` angle-bracket autolinks
  from PR and issue bodies.** A body posted through `create_pull_request`,
  `update_pull_request`, or `issue_write` comes back with the whole
  `<...>` span gone, leaving a double space where the URL was --
  "pointed readers at&nbsp;&nbsp;for the in-development documentation."
  Presumably the angle brackets are treated as an HTML tag and stripped
  somewhere in the write path; whatever the mechanism, the URL never reaches
  GitHub. It is silent (the call succeeds) and easy to miss, because nothing
  in the tool result flags it and the sentence still reads as a sentence.
  Especially costly when the URL *is* the subject -- a PR about a broken link
  losing exactly that link.
  **Backticks do NOT protect it.** The sanitizer runs over the raw body
  string with no regard for Markdown context, so an angle-bracket span inside
  a code span is stripped exactly like a bare one, leaving an empty pair of
  backticks. This is the same formatting-blind-substring failure mode as the
  bot-mention gate in `memories/github-actions.md` -- a pass that inspects
  raw text while the author reasons in rendered Markdown.
  **Write the URL with no angle brackets at all**: a `[text](url)` link, or
  the bare `https://...` (GitHub auto-links it in a PR body anyway). Then
  re-read the stored body after posting when a URL matters -- the call
  succeeds either way, so the tool result never tells you.
  Note this is a quirk of the MCP write path, not of GitHub or of Markdown
  files: angle-bracket autolinks in a committed `README.md` render fine and
  should be left alone.
  (`UCD-SERG/serocalculator#605` and its issue #604, 2026-07-25: both bodies
  lost the same URL this way. The backticked-is-safe assumption was then
  disproved by this very bullet's own PR, `ai-config#724`, whose description
  lost an angle-bracket span from inside a code span in the heading that
  introduced this entry.)
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

## GitHub access from bash in remote/web sessions
- The git proxy proxies ONLY git operations — there is no `gh`/`glab` and no
  GitHub REST API reachable from a Bash/Monitor script. Use `mcp__github__*`
  tools for any API need.
  - **For a repo outside the session's GitHub scope, `mcp__github__*` is not a
    fallback either — but git operations still are.**
    The proxy answers `403` for an out-of-scope repo with a body that names the
    scope as the reason, rather than a generic denial:
    ```
    $ curl -sS https://api.github.com/repos/actions/checkout
    {"message":"GitHub access to this repository is not enabled for this
     session. Use add_repo to request access. ..."}
    ```
    The session's own repo-scope rule limits the MCP tools to that same list,
    so switching to them is not a way around it.
    But `git ls-remote https://github.com/<owner>/<repo>` works against any
    public repo whatever the scope is, because it is a git operation and the
    proxy passes those through unchanged.
    That answers every ref question the REST API would have — which tags and
    branches exist, and which shas they point at — and that is usually the
    whole reason an out-of-scope repo came up.
    So the ladder is: MCP tools, then `add_repo` if the repo genuinely needs
    API or write access, then `git ls-remote` for anything that is only a ref
    lookup.
    See [`git.md`](git.md)'s "Resolving a tag to a COMMIT sha" for the exact
    refspec form to ask for.
    (d-morrison/altdoc#65, 2026-07-26: SHA-pinning seven third-party actions
    needed tag shas from `actions/`, `r-lib/`, `r-hub/`, `quarto-dev/`, and
    `JamesIves/`, none of them in session scope, and `add_repo` would have been
    five pointless scope grants for five ref lookups.)
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
  - **But try the `gh-pages` branch first --- the deployed HTML is usually
    readable through the authenticated MCP tools even when the served site
    isn't.** `rossjrw/pr-preview-action` commits each build to `gh-pages`
    under `pr-preview/pr-<N>/`, so
    `mcp__github__get_file_contents` with `ref: refs/heads/gh-pages` and
    `path: pr-preview/pr-<N>/<page>.html` returns the exact bytes the blocked
    URL would have served. That reaches the *real rendered artifact*, which a
    local re-render only approximates, and it needs no Quarto toolchain.
    Large pages exceed the tool's token cap and get spilled to a file --- grep
    that file rather than reading it whole, and diff byte counts across two
    fetches to confirm you're looking at a genuinely new build rather than an
    unchanged one. Check the branch's own commit log
    (`mcp__github__list_commits` with `sha: gh-pages` --- the `LIST_COMMITS`
    operation in [`tool-mappings.md`](../tool-mappings.md), verified by use in
    the session below) to see which build is actually deployed before drawing
    conclusions; a preview comment's timestamp can precede the deploy of the
    commit you care about.
    (`UCD-SERG/serocalculator#392`, 2026-07-25: used this to verify six new
    topics appeared in a rendered altdoc sidebar, counting occurrences
    before and after the fix, after both `curl` and `WebFetch` 403'd.)
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

## A CI failure caused by a documented-but-wrong convention may already have an upstream fix -- check before re-patching the symptom

When a consumer repo's CI fails because a *documented* convention (a skip
label, a config key) doesn't actually work as described, the first instinct
is to fix the local documentation to match the tool's real behavior. Check
first whether a **shared/reusable workflow this repo depends on** already
fixed the actual root cause in a newer version than the one pinned -- the
consumer's stale pin, not the doc wording, may be the real bug.

Concretely: `UCD-SERG/serocalculator`'s docs said a PR could skip its
`news.yaml` changelog check with a `no-changelog` (hyphen) label, but
applying that label didn't work -- the wrapped `UCD-SERG/changelog-check-action`
hardcodes checking for `no changelog` (space), a different string. The first
fix redocumented the label as `no changelog` (space) everywhere -- technically
unblocked the PR, but was wrong: it was really the shared
`d-morrison/gha` `check-news.yml` reusable workflow, pinned to the repo's
frozen `@v1` tag, that was stale. A newer version (`@v2`) already had a
configurable `no-changelog-label` input, added specifically for this
convention by an earlier, already-closed upstream issue (gha#143). The
wrapper doesn't pass the label through to the action (which still
unconditionally hardcodes `no changelog`, space) -- instead its own job
carries a job-level `if:` that skips the whole job, action included,
whenever the configured label is present, so the hardcoded check inside
the action never runs at all for a PR carrying it. Confirmed by diffing
the reusable workflow's file content at the two tags
directly (`git show <tag>:<path>` / a raw fetch per tag), not by trusting a
versioning doc's blanket claim. The correct fix was reverting the
re-documented label and bumping the stale `@v1` pin to `@v2`, which restored
the originally-documented (and originally correct) hyphenated label.

**Tell:** a review flags "this looks like the fix for an issue that's already
closed" or the bug's exact symptom appears in a shared workflow's own inline
comments/changelog. Before accepting a symptom-level fix (redocumenting
behavior to match what's observed), check the shared/reusable component's
own issue tracker and version history for a fix already covering this exact
case, and check whether the consumer is pinned to a version that predates it.

**A second-order lesson from the same investigation:** a package/repo's own
versioning docs claiming a component is "audited, unchanged since the freeze"
can itself be stale -- the audit can predate a later fix to that exact
component. Verify the claim against the two tags' actual file content rather
than trusting the doc; if wrong, fix it too (not just the one broken
reference that surfaced the problem) via a repo-wide grep, since the same
claim is often restated in multiple docs/pages.

**A third, narrower lesson: an unassembled `changelog.d/`-style fragment is a
pending draft, not published history -- don't treat it as immutable.** A
fragment already merged to `main` but not yet collated into `CHANGELOG.md` by
the release script can assert the exact stale claim being corrected. Fix it
in place like any other stale doc; leaving it risks a self-contradictory
`CHANGELOG.md` once both fragments are assembled together. A review caught
this only because it explicitly checked fragments outside the current PR's
diff -- don't assume a `changelog.d/` file is out of scope just because this
PR didn't author it.

(`UCD-SERG/serocalculator#593` / `d-morrison/gha#304`/`#143`, 2026-07-25: the
label-name fix round-tripped through a wrong "redocument the label" patch
before the actual `@v1`→`@v2` pin bump was found; `gha#304`'s own review then
caught two more stale `@v1` references in sibling docs pages and the
contradicting pending changelog fragment, all in the same repo-wide sweep.)
