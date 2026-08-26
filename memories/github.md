# GitHub & GitLab CLIs and APIs

The GitHub MCP tool surface used in remote/web sessions lives in
[`github-mcp-tools.md`](github-mcp-tools.md).
What a repository transfer between owners carries, and silently does not, lives
in [`github-repo-transfers.md`](github-repo-transfers.md).

## Operational checklist pattern for write actions

- **Preflight gate:** verify target branch/repo and whether the action should update an existing PR versus create a new one.
- **Safe command form:** when content includes markdown/backticks, write to a temp file and pass `--body-file` or `-F "body=@<file>"`; avoid inline double-quoted body args.
- **Postcondition gate:** after push/post/create, query GitHub state in the intended base repo (for PRs, include both repo and head owner) and confirm the intended object actually exists/updated. `gh pr list --head <owner>:<branch>` silently returns empty for an owner-qualified head even when a matching PR exists — verified directly against a real open PR (`gh pr list --head the repository owner:ums-pr635-lessons` returned `[]`; the bare `--head ums-pr635-lessons` found it). Use the REST API instead, with the branch passed as a `-f` GET field rather than interpolated into the raw URL — a branch name containing `#`, `&`, or `+` breaks a hand-built query string but is passed through correctly as a field: `gh api --method GET "repos/<upstream-owner>/<repo>/pulls" -f "head=<head-owner>:<branch>" -f "state=open" --jq '.[] | {number, url, state}'`.
- **Failure signature:** stderr like `command not found` during a `gh`/`glab ... --body` call can mean two different things — check which first, probing whichever CLI actually failed (`which gh` or `which glab`, not always `gh`): if `gh` itself is unavailable (expected in remote/web sessions), fall back to the mapped MCP tool instead of retrying the CLI — `tool-mappings.yml` has no `glab` operations, so a missing `glab` has no MCP fallback; hand off or block instead. If the CLI that failed is present, the likely cause is shell-expanded backticks mangling the body — re-run using a file-backed body.

## gh (GitHub CLI)
- `gh` opens a pager (alternate buffer) that hangs the agent terminal.
- Always disable it: pipe `| cat` or set `GH_PAGER=cat` (e.g. `gh pr view 116 | cat`).
- `gh --no-pager` is not a supported flag and will error; use `GH_PAGER=cat` or `| cat` instead.
- **`gh repo list <owner>` works for a user or an org; `gh api /orgs/<owner>/repos` only works for an org.**
  The REST endpoint returns 404 on a personal account, so it is not a drop-in replacement for `gh repo list` even though it offers `--paginate`.
  `gh api /users/<owner>/repos` is the personal-account counterpart, and `gh api /users/<owner> --jq .type` returns `User` or `Organization` when you need to branch.
  This matters when enumerating repos across a mixed owner list: substituting the `/orgs/` form to get pagination silently drops every user account in the list.
  (Morrison-Lab/ai-config#833, 2026-07-29: a review suggested exactly that substitution to fix a `--limit 1000` truncation.
  `the repository owner` is a `User`, so it would have 404'd on the first owner in the list.
  The truncation was real, and the fix was to detect the ceiling instead, in the census command under "`gh search code` is not a reliable way to enumerate consumers".)
- **Rate limit is shared (5000/hr) and split GraphQL vs REST.**
  All tools/sessions/agents share the one user's 5000/hr, and `core` (REST)
  and `graphql` are **separate pools**.
  `gh pr checks`, `gh pr view --json comments`, and `gh pr list --json` use
  GraphQL.
  When one pool is spent, get the same data through the other: REST as
  `gh api repos/<o>/<r>/pulls/<n>`, `.../commits/<sha>/check-runs`,
  `.../issues/<n>/comments`; GraphQL as `gh api graphql -f query=...`.
  `gh api rate_limit --jq .resources` is **free** and doesn't count against
  either pool, so check `core` vs `graphql` remaining/reset before retrying.
  Don't tight-poll; use a background watcher with `sleep`, since parallel
  sessions drain the shared pool fast.
  **Don't assume which pool empties first --- read `rate_limit` rather than
  predicting.**
  An earlier version of this entry said GraphQL exhausts first, generalized
  from one session.
  The reverse happens just as readily: a session doing mostly REST work
  (per-PR `gh api` reads, check-run polls) exhausts `core` while `graphql`
  sits nearly untouched.
  So the fallback direction is whichever the free call says it is, in either
  direction.
  **GraphQL can carry a whole ARDI round on its own**, which is what makes
  the REST-exhausted case survivable rather than merely diagnosable:
  `addPullRequestReviewThreadReply` for a threaded reply,
  `resolveReviewThread` to resolve it, `addComment` for a top-level summary,
  and `pullRequest{ headRefOid mergeable reviewThreads statusCheckRollup }`
  for the fully-clean sweep.
  Note `statusCheckRollup.contexts` needs inline fragments, since `CheckRun` and `StatusContext` carry different fields (`name`/`status`/`conclusion` versus `context`/`state`).
  `CheckRun.status` (`CheckStatusState`: `QUEUED`, `IN_PROGRESS`, `REQUESTED`, `WAITING`, `PENDING`, `COMPLETED` --- measured 2026-08-25) has non-terminal states like `REQUESTED` (pre-queue) and `WAITING` (protection/approvals).
  `StatusContext.state` (`StatusState`: `EXPECTED`, `PENDING`, `SUCCESS`, `FAILURE`, `ERROR` --- measured 2026-08-25) treats `EXPECTED` as non-terminal.
  Gating code must fail-closed: require `CheckRun.status === 'COMPLETED'` and `StatusContext.state` in terminal states (`SUCCESS`, `FAILURE`, `ERROR` --- or require `state === 'SUCCESS'` on every context for an all-green gate),
  treating any other status or state as still in progress rather than allow-listing expected pending values.
  (Morrison-Lab/ai-config#816, 2026-07-29: `core` returned `403` mid-round with `graphql` at 4922/5000 --- the round's reply, thread-resolve, ARD summary, and clean-state verification all went through GraphQL, and `core` reset 11 minutes later.)
- **A session's egress proxy can block GraphQL entirely, as a session-scoped
  policy rather than an account-level quota --- distinct from the rate-limit
  case above, and easy to conflate with it.**
  The symptom looks identical at first glance: `gh pr view --json ...` fails.
  The cause is not shared.
  `gh api rate_limit` reports a healthy `graphql` pool, and `gh auth status`
  plus a plain `gh api <rest-endpoint>` both report success, so the session
  reads as fully authenticated and REST-capable while every GraphQL call
  fails identically:
  ```
  HTTP 403: This GraphQL query is not enabled for this session --- only the
  pinned set of PR-review operations is served. Use REST via
  `gh api repos/{owner}/{repo}/...` instead.
  ```
  Confirmed not scoped to one query: a minimal hand-written
  `gh api graphql -f query='{ ... }'` against the same PR gets the identical
  403.
  This breaks `scripts/check-pr-fully-clean.py` at its very first call
  (`gh pr view --json ...` inside `get_pr_info()`), before anything
  repo-specific runs, and the healthy `gh auth status`/REST readings make it
  easy to misdiagnose as "something else is wrong" rather than "GraphQL is
  closed here."
  Route around it the same way as the rate-limit case: REST
  (`gh api repos/<o>/<r>/pulls/<n>` plus `.../commits` for the head SHA) or
  the GitHub MCP tools, which already implement `pull_request_read` over
  REST.
  (`Morrison-Lab/ai-config#1330`, 2026-08-10, comment: this session's proxy
  refused every GraphQL call while `gh api user`/`gh api repos/<o>/<r>` both
  returned 200 --- a second, distinct root cause for the same
  `check-pr-fully-clean.py` failure symptom already tracked in that issue.)

  **A third root cause reaches that same first call, and it is the most
  common one: `gh` is not installed at all.**
  The two causes above both assume a working `gh` whose *requests* are
  refused, so both are diagnosed by reading a status code.
  Here there is no request, and since #1462 (2026-08-14) no traceback:

  ```text
  `gh` is not installed or not on PATH.
  This script requires the GitHub CLI; -R cannot substitute for it.
  ```

  It exits **2**, never 1 --- 1 is this script's "not clean" code, so a missing
  binary would otherwise read as a verdict rather than an environment failure.
  `command -v gh` discriminates the three in one read, and it is worth
  running before diagnosing anything else about the script.

  What makes this worth recording rather than filing under "the CLI is
  missing" is **which** sessions it hits.
  This file's own "GitHub access from bash in remote/web sessions" section
  states that there is no `gh`/`glab` CLI in these sessions, so this is the
  norm for a whole class of session rather than a misconfiguration --- and two
  corpus rules name that script as the instrument for deciding a PR is ready:
  [`ardi`](../shared/workflow/ardi.md) requires it for the single-PR loop, and
  [`fully-clean`](../shared/workflow/fully-clean.md) opens by saying the two
  criteria are "verified via `python3 scripts/check-pr-fully-clean.py
  <pr-number>`".
  So a mandated check is simply unavailable, and nothing in either rule says
  what to do about that.

  Route around it the same way this bullet already prescribes: the GitHub MCP
  tools, verifying by hand against
  [`fully-clean`](../shared/workflow/fully-clean.md)'s own criteria ---
  select verdict candidates on the `**Claude finished` body marker rather
  than an author login, anchor on the **last** `### Verdict` heading, read
  Copilot's posted review body rather than its check colour, and paginate the
  check-runs endpoint.

  - **Do:** run `command -v gh` before diagnosing a `check-pr-fully-clean.py`
    failure, so a missing binary, a blocked GraphQL call, and a rate limit are
    separated in one read.
  - **Do:** report the script as **unavailable** in the status summary, naming
    the MCP checks run in its place, so a reader can tell a hand verification
    from an instrument's verdict.
  - **Don't:** read the script's absence as licence to skip criteria 1 and 2
    --- the criteria are the requirement, and the script is one way of
    reaching them.
  - **Don't:** report a PR clean without saying which instrument decided it;
    a hand check and a script run are different evidence and should not read
    alike.

  (`Morrison-Lab/ai-config#1403`, 2026-08-12: a remote session driving that
  PR's own check-in ran the script as instructed and got the traceback above.
  Every criterion was then verified through `pull_request_read` and
  `get_check_runs` instead, and the merge went ahead on that evidence --- but
  the summary had to say the instrument was unavailable rather than clean.)
- **The @claude review bot's author name differs by API:** its comment author is `claude[bot]` in REST (`.user.login`) but `claude` in GraphQL (`.author.login`). A watcher filtering REST comments for `.user.login == "claude"` silently finds nothing — use `"claude[bot]"`.
- **A third variant, and it is not one repo's quirk: the review comment can
  post as `github-actions[bot]` rather than `claude`/`claude[bot]`, and the
  same repo can do it on one round and not the next.**
  First recorded on `d-morrison/gha`; observed again on
  `Morrison-Lab/ai-config#1054` (2026-08-03), where round 2's verdict posted as
  `claude[bot]` at `02:12:52Z` and round 3's as `github-actions[bot]` at
  `03:04:19Z` --- so the login varied **between consecutive rounds of one PR**,
  and a login filter that had worked all session began silently returning the
  older comment.
  Note the failure differs by repo in a way that matters: where the login never
  matches, the filter returns **empty**, which at least looks wrong; where it
  matched earlier rounds, it returns a **stale but plausible** verdict, which
  does not.
  Filtering `.user.login == "claude"` (or `"claude[bot]"`) returns nothing on
  such a repo even though a real, complete review was posted --- the workflow's
  own `gather-context` job comment even says "REST author login is
  `claude[bot]`", which does not match what the bot actually posts under there.
  Don't conclude "no review yet" from an empty filter on one login string: if it
  comes back empty, list all comment authors
  (`gh api repos/<o>/<r>/issues/<N>/comments --jq '.[] | .user.login'`) and check
  the body for the `**Claude finished` marker regardless of which login posted
  it.
  (gha#278, 2026-07-21: `select(.author.login == "claude")` and
  `select(.user.login | test("claude"))` both came up empty; the actual review
  comments were under `github-actions[bot]`.)
- **Polling for the bot's verdict: match `Claude finished`, don't exclude a placeholder.** While a run is underway, the bot's comment holds an in-progress placeholder whose wording *varies between runs* ("### Review in progress …", "Claude Code is working…"), so a watcher that exits when comments exist, or when one known placeholder phrase disappears, fires early on the next differently-worded placeholder. Completed runs (review and agent alike) start the body with `**Claude finished`. **Filter on that body marker, not on an author login** --- the login itself varies by repo (see the `github-actions[bot]` variant in the bullet above), so a login-only filter can come up empty even once a review has posted.
  - **When re-triggering a run on a thread that already has a completed `**Claude finished` comment from an earlier run, also scope the filter to comments newer than a baseline ID captured before the trigger** --- otherwise the poll matches the *prior* run's already-finished comment immediately and never actually waits for the new one.
    **`gh api`'s own `--jq` flag has no way to inject a variable (neither `--arg` nor `--argjson`), and reaching for one fails in the shape of an empty result**: `gh` parses the unknown flag and its value as extra positionals, so `gh api <endpoint> --jq --arg h "$SHA" '<expr>'` exits 1 with an empty **stdout** and `accepts 1 arg(s), received 4` on **stderr** (measured on `gh` 2.92.0, 2026-08-13).
    Inside a `$(...)` whose stderr is not being watched --- a "reviews at the current head" query, say --- that reads as "no reviews exist" rather than as a broken command, which is why the remedy below is worth taking rather than retrying the flag.
    It **also only fetches the first REST page (30 comments) unless told to paginate, and `--paginate`'s `--slurp` companion flag is rejected outright when combined with `--jq`** --- pipe the raw paginated output into standalone `jq -s` instead, which supports both.
    **Enable `pipefail` in each shell process that runs one of these pipelines** so an upstream `gh api` failure does not get masked by a successful downstream `jq`:
    ```bash
    set -o pipefail
    BASELINE=$(gh api repos/<o>/<r>/issues/<N>/comments --paginate | jq -s '[.[][] | .id] | max // 0')
    # ... trigger the new run ...
    set -o pipefail
    gh api repos/<o>/<r>/issues/<N>/comments --paginate | jq -s --argjson baseline "$BASELINE" \
      '[.[][] | select(.id > $baseline and (.body | startswith("**Claude finished")))] | last | .body'
    ```
    When polling for the *first* run on a fresh thread (no prior completed comment to collide with), the simpler unscoped form still needs `--paginate` for the same >30-comment reason (a REST issue-comments page is oldest-first, so page 1 alone can miss the newest comment entirely once a thread grows past one page): `gh api repos/<o>/<r>/issues/<N>/comments --paginate | jq -s '[.[][] | select(.body | startswith("**Claude finished"))] | last | .body'`. (Cost two wasted watch rounds on ai-config#357 before keying on the marker; the login-filtered version of this command was flagged as stale by review on ai-config#636; the unscoped-across-reruns version was flagged by a follow-up review on ai-config#637 and confirmed concretely on gha#278, whose thread holds two separate `**Claude finished` comments, one per run; and the `gh api --jq --argjson`/pagination gaps in *that* fix were themselves flagged by a still-later review on the same PR, caught only after #637 had already merged.)
- **`jq empty` exits 0 on empty stdin: pair it with an emptiness check `[ -n "$out" ]` when validating JSON.**
  `printf "" | jq empty` exits `0`, so using `echo "$out" | jq empty` alone to validate API responses accepts an empty response body as valid JSON.
  For robust validation of API responses (e.g. `gh api`), check both non-emptiness and JSON validity: `[ -n "$out" ] && echo "$out" | jq empty 2>/dev/null`.
  That pair has no correct one-token shortcut, and the two obvious candidates both fail.
  `jq -e empty` exits `4` on *every* input, valid non-empty JSON included, because `-e` takes its status from the filter's last output value and `empty` is defined never to emit one.
  `jq -e .` does separate empty from valid input, but then rejects the legitimate `null`/`false` bodies `gh api` returns routinely.
  Also note `gh api ... --jq '<expr>'` returns raw unquoted strings for string scalar expressions (such as `.head.sha`), which are not valid JSON on their own and fail `jq empty`.
  Fetch the endpoint JSON first and parse with `jq -r` instead. (Learned on gha#518.)
- **A reply posted via `gh pr comment`/`gh api` from within a session shows up under the *human user's own* GitHub account, not a bot identity — don't mistake it for an independent human review when auditing a PR's review state.**
  `gh` authenticates as whatever account is logged in locally (often the user's own, e.g. seen as `dem-extra1` on `Lacaedemon/sparta`), so when an agent (or a dispatched subagent) replies to an inline review comment on the user's behalf, `gh api repos/<o>/<r>/pulls/<N>/reviews` lists it as a `COMMENTED` review authored by the user — indistinguishable at a glance from the user genuinely opening the PR in a browser and typing a reply themselves.
  **Since 2026-08-24 the fix is on the posting side:** every comment an agent posts carries a trailing `_Posted by Claude Code (AI agent) --- not written by a human._` marker, so the body says what the author field cannot.
  See [`disclose-agent-authorship`](../shared/workflow/disclose-agent-authorship.md).
  That makes agent-authored comments identifiable **going forward**.
  Comments posted before that date carry no marker, so this warning still governs when auditing older threads.
  Before treating an unexpected review entry as a signal that the human intervened, check whether its body/inline-comment content reads like the agent's own scripted reply (referencing a specific commit SHA, restating verification numbers) rather than free-form human commentary — if so, it's the session's own tooling, not new human input.
  **The same ambiguity runs the other way, and there it arrives as a positive claim rather than an inference you might draw.**
  An automated reviewer reading the PR's own history sees that same bot-account commit and can describe it *in its review body* as the work of a human, e.g. "that finding was confirmed and fixed by a human reviewer (`dem-extra1`) in commit `<sha>`", stating as fact something no API field asserts.
  That is worse than the inference case above, because the claim is now published prose a later reader inherits, and "a human already verified this" is precisely the sentence that stops the next person checking.
  Correct it in the thread when you see it, naming which account is actually a session identity; don't let it stand just because the surrounding verdict was clean. (`ucdavis/bcs#532`, 2026-07-31: a `claude-review` pass reported a fix as human-confirmed when `dem-extra1` was the Claude session that made it, and no human had touched the PR at that point.)
- **`gh pr view --json` does not accept `merged` as a field.** Use `state` (returns `"MERGED"`) and `mergedAt` (ISO timestamp, null if not merged) to check merge status. Example: `gh pr view <N> --json state,mergedAt`.
  Verified 2026-08-09: `gh pr view <N> --json merged` fails with `Unknown JSON field: "merged"` and prints the full valid field list (`gh` 2.96.0), which includes `state`, `mergedAt`, `mergedBy`, `mergeCommit`, `closed`, and `closedAt` --- no bare `merged`.
  That absence is specific to `gh --json`'s own field-name allowlist, not to the underlying data.
  REST's `GET /repos/{owner}/{repo}/pulls/{number}` and the GraphQL `PullRequest.merged` field each carry a genuine `merged` boolean, verified 2026-08-09 against `Morrison-Lab/wai#57`: `gh api repos/<o>/<r>/pulls/<N> --jq .merged` returns `true`, and `gh api graphql -f query='{repository(owner:"<o>",name:"<r>"){pullRequest(number:<N>){merged}}}'` returns `true` as well.
  The GitHub MCP tool's `pull_request_read` `get` method carries it too --- see [`github-mcp-tools.md`](github-mcp-tools.md)'s note that `list_pull_requests` reports `merged: false` for every PR while `pull_request_read` `get` reports it correctly.
  So the fix differs by surface.
  Under `gh --json`, read `state`/`mergedAt`; under REST or the MCP `get` method, the `merged` field itself already works.
  **Never compare that `mergedAt` against a git timestamp as strings --- convert both to epochs first.**
  Every GitHub API timestamp is UTC (`...Z`), while git's `%cI`/`%cd` render in the *machine's local zone*, so a lexicographic `<` between them compares clock faces from two different zones and silently answers wrong.
  It fails in the unsafe direction west of UTC: a commit made *after* the merge still sorts first.
  Verified directly --- `tip="2026-07-30T18:00:00-07:00"` is `2026-07-31T01:00:00Z`, two hours *later* than `merged="2026-07-30T23:00:00Z"`, and `[[ "$tip" < "$merged" ]]` returns true.
  Use `%ct` (epoch seconds) plus jq's `fromdateiso8601`, and an integer test:
  ```bash
  tip=$(git log -1 --format='%ct' "<branch>")
  merged=$(gh pr view <N> --json mergedAt --jq '.mergedAt|fromdateiso8601')
  [[ "$tip" -lt "$merged" ]] && echo "tip predates merge" || echo "tip AFTER merge"
  ```
  `fromdateiso8601` is available in the jq that `gh --jq` embeds, confirmed by `gh pr view <N> --json createdAt --jq '.createdAt|fromdateiso8601'` returning an integer.
  So this needs no external `jq` and no `date -d`, which is GNU-only and absent on macOS.
  (Morrison-Lab/ai-config#908, 2026-07-30: the `clean-worktrees` merged-PR guard shipped the string comparison.
  Review caught it, and the repro above confirmed the failure direction before the fix went in.)
- **A MERGED (or closed) PR reads exactly like a "GitHub sync delay" --- check `state` before theorizing about lag.**
  Its signature is three symptoms that each look like webhook/replication lag:
  `gh pr view --json headRefOid` stays frozen at the last-merged SHA (lagging the actual branch tip),
  `mergeable`/`mergeStateStatus` read `UNKNOWN`,
  and pushing new commits to the branch triggers NO new synchronize review.
  All three are the merged/closed steady state, not a transient delay.
  Don't attribute them to a lag: `gh pr view <N> --json state` (or `mergedAt`/`mergeCommit`) returns `MERGED` immediately and settles it in one call.
  Corollary: after a squash-merge that auto-deletes the head branch, a later push RE-CREATES the branch as an orphan,
  so the pushed commit is NOT on `main` --- verify with `git merge-base --is-ancestor <sha> origin/main`.
  - **Do:** when a PR's head looks stuck and pushes don't trigger reviews, read `state`/`mergedAt` first.
  - **Don't:** read a frozen `headRefOid` plus `UNKNOWN` mergeable plus no-new-review as a sync lag --- that is the merged state.
  (gha#400, 2026-08-03: the PR merged at 15:54 PT as squash `03a046a`,
  but work continued on it for over an hour --- live verification, two nit-fix commits, posting evidence, resolving threads ---
  all on an already-merged PR, because the frozen-head/`UNKNOWN`-mergeable/no-new-review state was read as a sync delay instead of `state: MERGED`;
  the nit-fix commit ended up orphaned, not on `main`.)
  - **Mis-tracking a merged PR as still-open does not only misreport status --- it SILENTLY suppresses the "flag a good moment to `/clear`" suggestion, on false data.**
    The "Flag good moments to `/clear` in long-running sessions" rule in the user `CLAUDE.md` says not to flag a stopping point while any PR you opened or pushed to is still unmerged --- so "I still have open PRs" is that rule's own suppression clause.
    A remembered "it is still open" therefore does two things at once: it misreports the PR's status, and it invisibly cancels the stopping-point flag the user would otherwise get.
    The suppression fires correctly on stale input, so nothing looks wrong --- the user simply never receives the suggestion and has to ask.
    - **Do:** after confirming a merge, or at any long-session lull, re-query `gh pr view <N> --json state` for every PR you opened before either raising OR suppressing a stopping-point suggestion.
    - **Don't:** let a remembered "it is still open" both misreport status and silently cancel the `/clear` flag --- recollection about merge-state is exactly what the `--json state` query exists to replace.
    (This session, 2026-08-03/04, gha#400/#401 + ai-config#1111: three PRs were described as "open follow-ups I'm watching" after all three had merged, and no stopping-point flag was raised until the user asked whether to compact or start a new session.)
- **`gh pr list --state merged` plus a low `--limit` can miss recent merges:**
  The list is ordered by PR list order, effectively number/creation, before your `--jq` filter runs.
  That means an old, low-numbered PR that merged recently can sit below a page of higher-numbered PRs and never reach the filter.
  The result looks scoped by time while silently excluding the very merge checkpoint you were polling for.
  Use a query whose filter matches the question, such as `gh search prs --repo <owner>/<repo> --merged-at ">=<date>"`, or query each PR of interest directly.
  If you use `gh pr list --state merged`, set `--limit` far beyond the expected count and report how many merged PRs the command examined, not only how many passed the `mergedAt` filter.
  - **Do:** use `gh search prs --repo <owner>/<repo> --merged-at ">=<date>"`, direct `gh pr view <N>`, or an intentionally over-wide list with an examined count when answering "what merged since T".
  - **Don't:** trust `gh pr list --state merged --limit N --json mergedAt --jq '.[] | select(.mergedAt > T)'` as a time-window query.
  (Morrison-Lab/ai-config#969, 2026-08-01: `gh pr list --state merged --limit 15 --json number,mergedAt` plus a `mergedAt > 2026-08-01T08:00:00Z` filter returned only #1019, merged at `09:03:13Z`, and missed #969, merged at `09:14:38Z`.
  Raw `--limit 6` output showed #1013 at `05:36Z` before #1012 at `05:45Z`, proving the page was not sorted by merge time.
  Raising the limit to 30 returned both #1019 and #969.)
- **`gh pr edit` exits 1 on repos with Projects Classic — use `gh api` to update PR body.** `gh pr edit <N> --body "..."` / `--body-file <f>` returns exit code 1 with a GraphQL deprecation warning (`Projects (classic) is being deprecated…`). Sometimes the edit lands anyway; **sometimes it does not apply at all** (seen on sparta 2026-06-30: three `gh pr edit --body-file` attempts left the body unchanged with the `SHA_PLACEHOLDER` still in place). Either way, don't trust it — verify with `gh api repos/<o>/<r>/pulls/<N> --jq .body`, and just use the REST PATCH directly, which always exits 0 and applies: `gh api -X PATCH repos/<o>/<r>/pulls/<N> -f body="..."`. For a multi-line body, read it from a file with `-F body=@<path>` (capital `-F` to pull the field value from the file) rather than cramming it into `-f body="..."`.
- **PR description image embeds: use `raw.githubusercontent.com`, not `github.com/.../raw/...`.** Embedding a committed file in a PR body with `![](https://github.com/<owner>/<repo>/raw/<sha>/<path>)` may not render — the reviewer will flag it. The correct raw-content domain is `https://raw.githubusercontent.com/<owner>/<repo>/<sha>/<path>`. Reference the full commit SHA so the image keeps rendering after the branch is deleted on merge.
- **`raw.githubusercontent.com` FOLLOWS repository-rename redirects, so a `200` under the OLD owner proves nothing — only a `200` under the NEW owner is decisive.** To test whether a repo has moved, probe the *new* name and treat `404` there as "did not move". Run a known-moved repo as a control first, or the probe silently answers backwards: `d-morrison/gha` still returned `200` on `raw.githubusercontent.com` well after it became `Morrison-Lab/gha`, so an old-name probe reports every repo as "not moved". The REST API is not a substitute — behind an agent proxy `api.github.com/repos/<o>/<r>` can return `403` for every repo regardless of existence, which answers nothing in either direction. This matters before any blanket owner rewrite: probing all nine `d-morrison/*` references in ucdavis/bcs under the new owner showed only `gha` and `ai-config` had moved, so a find-and-replace would have broken `macros`, `altdoc`, `snapr`, `stats-allowlist`, `diffviewer`, `equation-anchors`, and `rme`. Note the bare `the repository owner` *username* (a `reviewer:` input, author metadata) is unaffected by a repo/org rename and must not be swept along. The Actions-side consequences of the same rename are in `github-actions.md` ("A repo/org rename breaks Actions `uses:` refs"). (2026-07-28.)
- **Download a user-pasted PR screenshot with `curl -L`.** When a user pastes an image into a GitHub PR comment, the file lives at `https://github.com/user-attachments/assets/<uuid>` and is publicly downloadable: `curl -L -o <dest>.png "https://github.com/user-attachments/assets/<uuid>"`. Retrieve the URL from the comment body via `gh api repos/<o>/<r>/issues/comments/<comment_id> --jq .body`.
- **Linking a GitHub sub-issue needs an integer DB id, not the number.** `POST /repos/<o>/<r>/issues/<parent>/sub_issues` takes `sub_issue_id` = the child's **database id** (`gh api repos/<o>/<r>/issues/<child> --jq .id`), *not* its issue number. Pass it with `-F` (typed, integer), never `-f` (string) — `-f sub_issue_id=…` fails with `422 Invalid property /sub_issue_id: "…" is not of type integer`. Full call: `gh api repos/<o>/<r>/issues/<parent>/sub_issues -F sub_issue_id=<child_db_id>`. Verify with `gh api .../issues/<parent>/sub_issues --jq '.[] | "#\(.number) \(.title)"'`.
- **Backticks in a double-quoted `-m` / `--body` string get command-substituted by the shell.** In the Bash tool, `` git commit -m "... `origin` ..." `` or `` gh pr comment --body "use `foo`" `` makes the shell run `` `origin` ``/`` `foo` `` as a command and splice the (usually empty/erroring) output into the message — silently mangling it (seen on sparta 2026-06-30: a commit body's `` `origin` `` and `` `killer` `` vanished, with `origin: command not found` in stderr). For any message/body containing backticks, use a single-quoted **heredoc** (`` -m "$(cat <<'EOF' … EOF)" `` — the quoted `'EOF'` disables all expansion) or a `--body-file`, never a bare double-quoted string. (Same root cause as ARD inline reply bodies too; use `-F body=@<file>` for `gh api .../pulls/<N>/comments`/`glab api .../notes` so backticks in Markdown never get shell-expanded.)
- **GitHub review inline comments are on a different API endpoint than top-level PR comments.** The top-level comment-view endpoint (`` `gh pr view <N> --json comments` `` or `gh api repos/<o>/<r>/issues/<N>/comments`) captures PR-level comments and bot-posted review overview summaries, but **not inline comments from formal reviews** (line-by-line inline findings). When a user links a specific review ID (e.g. `#pullrequestreview-4761444085`), fetch both the review overview and its inline comments separately: `gh api repos/<o>/<r>/pulls/<N>/reviews/<review-id> --jq '{state, body}'` for the overview, then `gh api repos/<o>/<r>/pulls/<N>/comments --jq '.[] | select(.pull_request_review_id == <review-id>) | {line: .line, body: .body}'` to get the inline findings. A review's overview body can be generic ("I reviewed the code") with all the actual findings in inline comments on specific lines — reading only the overview misses the findings. (Encountered on ai-config#647 review 4761444085: the overview body was generic, but the specific finding was in an inline comment on CLAUDE.md line 324.)

- **Replying to an inline review comment and editing one are two routes on the same comment id, and the destructive one is the shorter path.**
  The bullets above are about *reading* inline comments.
  Writing back to one has a trap they do not cover, because both routes take the same `<id>` and only the surrounding path distinguishes them:

  ```bash
  # REPLY: adds a comment alongside theirs. Note the PR number.
  gh api -X POST repos/<o>/<r>/pulls/<N>/comments/<id>/replies -F body=@<file>

  # EDIT: OVERWRITES their comment. No PR number.
  gh api -X PATCH repos/<o>/<r>/pulls/comments/<id> -F body=@<file>
  ```

  The discriminator is whether the PR number is present, which is the least memorable difference the two could have had, and the id-only form is the one that reads as the tidier of the two.
  Both were confirmed against GitHub's own reference: `PATCH /repos/{owner}/{repo}/pulls/comments/{comment_id}` updates a review comment, while `POST /repos/{owner}/{repo}/pulls/{pull_number}/comments/{comment_id}/replies` creates a reply.
  The underlying rule is that collection-scoped routes carry the PR number while single-comment-by-id routes do not, and that split cuts across the read/write divide rather than along it.
  `GET .../pulls/<N>/comments` lists a PR's comments and `GET .../pulls/comments/<id>` fetches one, so the id-only shape is already familiar from reading before you ever write with it.

  GitHub documents a second reply form, and it carries the PR number too: `POST .../pulls/<N>/comments` with `-F in_reply_to=<id>`, which is what [`ard`](../skills/ard/SKILL.md)'s step 4b uses.
  Either reply form is fine, and the discriminator holds for both, which is the point: every route that adds a comment names the PR, and the one that overwrites an existing comment does not.

  Nothing warns you.
  On a repo where you have write access the `PATCH` returns success, and success is exactly what an overwrite looks like.
  The review-comment REST surface exposes no edit-history read either, so a restore cannot be diffed against the original.
  The only durable trace is that `updated_at` stops matching `created_at`, and the comments render as edited from then on.

  The transferable shape is not about `gh`.
  A comment id addresses an artifact belonging to someone else, so a verb that writes *to* that id writes over their work rather than adding alongside it.
  The id being correct is therefore no evidence that the verb is, which is what makes this survive the check you would actually run: you verify the id, it is right, and the call succeeds.

  Use [`REPLY_REVIEW_COMMENT`](../tool-mappings.md) rather than composing the path by hand.
  That row carried a non-runnable `gh api (reply to review comment)` placeholder until this entry was written, which is the specific reason the path got improvised in the first place.

  - **Do:** reply with the `/replies` route, and read the PR number's presence as the check that you are on it.
  - **Do:** resolve the operation through `tool-mappings.yml`'s token rather than reconstructing a URL from the read endpoint you just used.
  - **Don't:** reach for `PATCH` on `pulls/comments/<id>` or `issues/comments/<id>` to respond to someone; that edits their comment.
  - **Don't:** read a `200` as confirmation you added something, on any id-addressed route you did not intend to write to.

  (Morrison-Lab/ai-config#1151, 2026-08-05: replying to five `claude[bot]` review findings was attempted with `-X PATCH repos/<o>/<r>/pulls/comments/<id>`, once per id, and all five findings were replaced by the reply text before anything reported a problem.
  They were restored from copies already read, and the replies reposted on the `/replies` route.
  The five comments (`3717322685`, `3717323117`, `3717323586`, `3717324073`, `3717324556`) were created `01:33:18Z` to `01:33:57Z` and last updated `01:40:35Z` to `01:40:38Z`, so the overwrite and the restore both fall inside that 7-minute bracket and cannot be separated any more finely than that, which is the missing-edit-history residual in concrete form.
  The five replies, created `01:41:03Z` to `01:41:07Z`, still carry `updated_at == created_at`.
  The correct route was already written down in [`skills/claude-agent-workflow/SKILL.md`](../skills/claude-agent-workflow/SKILL.md), so this was a placement failure rather than a knowledge gap: the command existed in a skill about a CI workflow, and the registry a person replying to a review would actually consult had a placeholder.)

- **One review round can post several review objects, so filtering by a single `pull_request_review_id` silently drops findings.**
  The bullet above is right that inline comments need their own endpoint, and its `select(.pull_request_review_id == <review-id>)` filter is the correct way to drill into *one* review.
  It is the wrong way to answer "what did this round find", because the round and the review object are not the same unit.
  A reviewer can emit two review objects seconds apart, one finding in each, and a linked review URL names only one of them --- so the filter returns a strict subset and reads exactly like a complete answer.
  Nothing in the output announces the omission.

  Enumerate unfiltered instead, and let the **thread list** decide what is outstanding:

  ```bash
  # every inline comment, whatever review it belongs to
  gh api repos/<o>/<r>/pulls/<N>/comments --paginate \
    --jq '.[] | "review_id=\(.pull_request_review_id) \(.path):\(.line) [\(.user.login)] \(.body[0:90])"'

  # the authoritative outstanding-work list
  gh api graphql -f query='{ repository(owner:"<o>", name:"<r>") {
    pullRequest(number:<N>) { reviewThreads(first:100) {
      totalCount
      nodes { id isResolved path line comments(first:1){nodes{databaseId}} } } } } }'
  ```

  Select `totalCount` and page at `first:100`, the guard `skills/pr-status/SKILL.md` and `skills/pr-status-all/SKILL.md` already use: a `totalCount` above the number of `nodes` means the 100-thread cap was hit, so the list is itself a truncated subset and cannot confirm clean --- exactly the silent-subset failure this bullet is about, one query lower.
  The unresolved-thread count is the check worth trusting: it is per-thread rather than per-review, so it cannot be split across review objects.
  Keep the id filter for drilling into a specific review a human pointed at.
  Never use it to decide a round is complete.
  The same caveat applies wherever this filter still appears as a drill-down --- `skills/ardi/SKILL.md` and `skills/pr-status-all/SKILL.md`.
  `skills/post-merge/SKILL.md` was the one call site using it as a completeness check, and now reads the inline comments unfiltered instead.
  (UCD-SERG/lab-manual#452, 2026-08-04: `claude[bot]` posted review `4851937544` at `07:57:27Z` and `4851938388` at `07:57:34Z`, one finding each, and the linked review's own body was **empty** so both findings were inline-only.
  Filtering on the linked id found the Wayland finding and missed the "Windows" one, which surfaced only from the unresolved-thread count after the first had been resolved.)

- **`repos/{owner}/{repo}/issues/comments` -- without a number -- is repo-wide, not PR-scoped, and it fails by returning another PR's review.**
  The bullet above gives the correct form, `issues/<N>/comments`.
  Dropping the `<N>` produces a path that still looks PR-shaped and still returns well-formed review JSON, so `--paginate | last` hands back whichever comment is newest **anywhere in the repository**.
  On a repo with several PRs in flight that is routinely a review of a different PR.
  Nothing in the payload announces the mismatch: it is a genuine review with genuine findings, and a reader who asked for "the latest review on this PR" has every reason to accept it.
  The damage runs both ways -- the PR you are on gets reported as blocked by findings that are not its own, and you go looking for defects in files it never touches.
  Worse, the wrong query is **intermittently correct**: whenever the PR you care about happens to hold the newest comment in the repo, it returns the right answer, so the method can survive several rounds before it bites.
  Treat "this worked last time" as no evidence at all here.
  Prefer `gh pr view <N> --json comments`, which cannot be mis-scoped.
  (`ucdavis/bcs`, 2026-07-30: an agent driving #473 was handed #468's "Needs more work" verdict, with two HIGH findings about restricted-data handling, and was three sentences into treating them as #473's before the body's own `## Code Review: ucdavis/bcs#468` header caught it.
  The same query had been used for two earlier rounds and was right both times, by luck.)
- **Finding the PR(s) linked to an issue from the CLI: use the REST timeline endpoint, not `gh issue view --json`.** `gh issue view --json` has no `timelineItems` field (that exists only on `gh pr view --json`), so `gh issue view <N> --json timelineItems` errors — and a `2>/dev/null` swallows the error so the check silently returns nothing and *looks* like it passed. Query the timeline instead, with three gotchas: (1) in a `cross-referenced` event, `source.type` is always `"issue"`, so a PR is one whose `source.issue.pull_request` is non-null (`source.type == "pull_request"` never matches); (2) `--paginate` is required, or `gh api` returns only the first 30 events and silently misses a later cross-reference; (3) filter `source.issue.state` if you only want open PRs. Full call: `gh api --paginate repos/<o>/<r>/issues/<N>/timeline --jq '.[] | select(.event == "cross-referenced") | .source.issue | select(.pull_request != null) | select(.state == "open") | "#\(.number) \(.title)"'`. (Learned over three review rounds on #287.)
- **Whether `#N` is an issue or a PR is decided by the `pull_request` key, and `gh issue view` cannot decide it.**
  GitHub's REST API models every PR as an issue, so `gh issue view <N>` resolves a **PR** number too, returning its
  `state` (`MERGED`) as though it were an issue's --- a success there is evidence of nothing.
  Only `gh pr view <N>` discriminates, and it does so by *failing* on an issue
  (`Could not resolve to a PullRequest`), so the informative answer is an error rather than a value, which is easy to
  read as a broken command.
  One call answers it directly: `gh api repos/<o>/<r>/issues/<N> --jq '.pull_request != null'` --- `true` for a PR,
  `false` for an issue.
  Reach for it whenever two sources disagree about what `#N` is, rather than trusting whichever one resolved;
  per `metacognitive-monitoring.md`, a two-source disagreement is a prompt for a third check, not a finding.
  (Measured 2026-08-09 on `Morrison-Lab/ai-config`: `#1328` returns `false` and `#1334` returns `true`, while
  `gh issue view 1334` returns `{"number":1334,"state":"MERGED",...}` without complaint.
  Same key the timeline bullet above relies on.
  What it adds is that the plain `gh issue view` path answers for both kinds, and so distinguishes neither.)
- **`gh pr checks` does NOT say which checks are REQUIRED, and the legacy protection endpoint 404s on ruleset-gated repos — so the lazy check confirms the wrong answer.** `gh pr checks` reports check *state* only; required-ness is nowhere in its output. And `gh api repos/<o>/<r>/branches/<branch>/protection` returns `404 Branch not protected` on a repo that gates the branch with a **ruleset** rather than legacy branch protection, which reads as "nothing is required" and *confirms* the mistaken assumption. Query rulesets too, before any "ready to merge" or "that check doesn't gate us" claim:
  ```bash
  gh api "repos/<o>/<r>/rulesets" --jq '.[] | "\(.id) \(.name) \(.target) \(.enforcement)"'
  gh api "repos/<o>/<r>/rulesets/<id>" \
    --jq '.rules[] | select(.type=="required_status_checks")
          | .parameters.required_status_checks[].context'
  ```
  (ucdavis/bcs, 2026-07-26: a red `docs` check was twice reported non-required and a PR reported "ready" on that basis; `docs` is required under ruleset 11050897, so the merge was blocked the whole time and a queue-wide blocker was mislabeled a cosmetic flake. The legacy endpoint's 404 would have reinforced the error if consulted alone.)
  Note: the two commands above cover only **repo-level** rulesets. Org-level rulesets (`gh api "orgs/<org>/rulesets"`) can also gate branches in member repos and would still return "nothing required" with the repo queries alone; add that sweep when the repo belongs to an org.

  **Required checks are not the only thing a ruleset carries -- Copilot code review is turned on there too.**
  A `copilot_code_review` rule schedules Copilot itself, so nothing in the PR requests the review and no per-PR reviewer entry explains where it came from.
  Read it off the same endpoint:
  ```bash
  gh api "repos/<o>/<r>/rulesets/<id>" \
    --jq '.rules[] | select(.type=="copilot_code_review") | .parameters'
  ```
  On `ucdavis/bcs` (2026-07-30) ruleset `19248641`, scoped to `~DEFAULT_BRANCH`, returns `{"review_on_push":true,"review_draft_pull_requests":true}` -- which is why draft PRs there get Copilot reviews at all.
  Check this before concluding that a Copilot review was requested by a person, or that its absence means nobody asked.

- **GitHub PR Reviews REST API (`POST /repos/{owner}/{repo}/pulls/{number}/reviews`) Requirements & Fallbacks**:
  - `pull_number` MUST be an explicit integer in the URL path (e.g. `/pulls/412/reviews`), not `'current'` or branch names. Query `number` and `headRefOid` via `gh pr view --json number,headRefOid`.
  - Line numbers must be `>= 1` and `line >= start_line`. Normalize ranges with `min(start_line, end_line)` and `max(start_line, end_line)` to avoid `422 Unprocessable Entity` errors on inverted range inputs.
  - Multi-line inline review comments require `start_line` (start line), `line` (end line), and `start_side: "RIGHT"`.
  - Inline comments on files or lines outside active PR diff hunks return `422 Unprocessable Entity`; automatically catch `gh api` non-zero exit status and fall back to top-level issue comments (`gh pr comment`).
  - Prepend matched section headers (e.g. `#### 1. 🚨 Critical Issue`) to inline comment bodies so comments retain context and severity indicators on GitHub diff cards. (Morrison-Lab/gha#412, 2026-08-05).

- **Regex Parsing for Automated Agent Reports (`re.VERBOSE`)**:
  - Standardize on Python's built-in `re.compile` with `re.VERBOSE` (`re.X`) instead of third-party DSL wrappers (`humre`) or dual regex fallback paths. Dual regex definitions introduce implementation drift between local unit tests and CI runners.
  - Prefer match-boundary splitting over lookahead section delimiters.

- **Avoid lookahead regexes across markdown finding bodies containing code blocks.**
  Single-line comments in code blocks (`# comment` in Python, Bash, R, Ruby, YAML) start with `# `.
  A lookahead like `\n\#{1,6}[ \t]+` for section headers then treats those code comments as markdown headings, cutting a code-block suggestion off mid-snippet.
  (Morrison-Lab/gha#412, 2026-08-05).
- **Line-anchor the fence pattern when masking code blocks.**
  Mask fenced blocks before location matching with a line-anchored fence (`^[ \t]{0,3}```...`) under `re.MULTILINE`, and match each block's opening and closing fence as a balanced pair.
  Do not span blocks with a single `re.DOTALL` match: an unclosed fence then swallows everything up to a *later* block's closing fence, masking the valid location headers in between.
  (Morrison-Lab/gha#412, 2026-08-05).
  - **Second occurrence, in ai-config's own scripts rather than gha's review parser.**
    `` re.compile(r"```.*?```", re.S) `` pairs backtick *runs* wherever they fall instead of tracking fence open and close positionally, so a document whose runs are 4, 3, 4, 3, 3 masks the wrong spans.
    `scripts/check-links.py:22` and `scripts/check-pr-fully-clean.py:191-192` both carry it; `scripts/check-context-closure.py:200-240` is the same repo's correct positional implementation, so the fix is to reuse that rather than to re-derive one.
    Filed as [#1567](https://github.com/Morrison-Lab/ai-config/issues/1567).
    Read this as the class recurring rather than as a new lesson: the bullet above already states the rule, and
    [`fact-check-code-logic`](../shared/coding/fact-check-code-logic.md)'s "When one parser construct becomes tolerant of a condition, audit its siblings" says to sweep sibling constructs --- which here means sibling *scripts* sharing one repo, not only sibling regexes sharing one file.
    (2026-08-16.)
- **Use match-boundary splitting instead of single-pass lookaheads.**
  Collect every finding's location header (`**Location:** [file.ext:L10]`) into `matches`, then slice each body between consecutive matches.
  An interior body is `content[matches[i].end():matches[i+1].start()]`.
  The last match has no `matches[i+1]`, so its body runs to `content[matches[-1].end():]` (end of content) rather than indexing past the list.
  This eliminates catastrophic backtracking on nested code blocks and `#` code comments.
  (Morrison-Lab/gha#412, 2026-08-05).
- **Anchor a location match to its heading, not just the `Location:` line.**
  When intro text sits between a section heading (`#### 1. Critical Bug`) and its `Location:` tag, a regex keyed only on the immediate prefix of `Location:` misses the heading, and finding bodies then absorb the adjacent heading.
  Precompute each heading's start position preceding its location match and slice bodies from there.
  (Morrison-Lab/gha#412, 2026-08-05).
- **Strip backticks and leading slashes from location file paths.**
  LLMs sometimes wrap the path in backticks (e.g. ``**Location:** [`file.py`:L12]``) or prefix a leading `/` (`/src/main.py`).
  `POST /repos/{owner}/{repo}/pulls/{number}/reviews` rejects a leading-slash path with `HTTP 422` (`path cannot start with /`), and a stray backtick yields `HTTP 422: File path does not exist`.
  Normalize with ``.strip("'\"` ").lstrip("/")`` so the API gets a clean relative path.
  (Morrison-Lab/gha#412, 2026-08-05).
- **Resolve candidate instruction paths relative to `GITHUB_WORKSPACE`.**
  Relative lookups for root files (`CLAUDE.md`, `AGENTS.md`) depend on the working directory, so a script invoked from a subdirectory misses them.
  Use `os.path.join(os.environ.get("GITHUB_WORKSPACE", "."), rel_path)`, and `.lstrip("/")` the `rel_path` first: `os.path.join` discards the base whenever its second argument is absolute.
  (Morrison-Lab/gha#412, 2026-08-05).
- **Require double newlines `\n\s*\n` (or a compound section phrase) when truncating summary headers.**
  Trimming a summary on single newlines (`\n+#{1,6}`) or a bare keyword (`Recommendation`) can cut an inline comment body short when a finding contains a sub-heading like `### Recommendation`.
  Requiring `\n\s*\n`, or matching a compound phrase (`Overall Summary`, `General Recommendations`) with a negative lookahead, keeps such sub-headings intact.
  (Morrison-Lab/gha#413, 2026-08-05).

- **Shell Script Fail-Closed Safety in Workflows**:
  - Under `set -e`, use `if ! CMD; then` to safely handle non-zero exit status without `set +e`.
    Using `set +e` turns off `errexit` for subsequent pipeline steps (e.g., `jq`), risking failing open instead of closed on JSON parse errors.
    (Morrison-Lab/gha#412, 2026-08-05).

- **`gh pr edit --add-reviewer` silently no-ops when the requested reviewer is the PR's author, and the CLI reports success anyway.**
  GitHub forbids a review request aimed at a PR's author, and [`skills/request-pr-review/SKILL.md`](../skills/request-pr-review/SKILL.md)'s edge case records that the REST POST answers HTTP **422** --- but the `gh pr edit <N> --add-reviewer <login>` wrapper swallows it: exit 0, no error, no warning.
  Observed on `Morrison-Lab/wai#93`, 2026-08-22 --- the session requested `the repository owner` and the PR author was `the repository owner`.
  Two runs of `gh pr edit 93 --add-reviewer d-morrison` both exited clean, and `GET /repos/Morrison-Lab/wai/pulls/93/requested_reviewers` returned no users after each.
  Here the empty `requested_reviewers` list **is** decisive negative evidence: the request was refused at creation, not accepted-and-hidden.
  Consequence for the skill's own step: human review cannot be requested from a PR's author --- when the intended reviewer is the author, "request human review" degenerates to reporting the PR to that person in chat.

  - **Do:** compare the target reviewer login against `gh pr view --json author --jq .author.login` before requesting review, and skip the request when they match, saying the PR awaits that reviewer's own review.
  - **Don't:** read exit code 0 or the printed URL from `--add-reviewer` as proof a reviewer was attached --- use the REST POST, whose 422 is visible, or confirm with one `GET .../requested_reviewers`.

- **The reviewer-request API is not the surface to check, and a `422` reported for it did not reproduce.**
  `POST /repos/<o>/<r>/pulls/<N>/requested_reviewers` with `reviewers[]=copilot-pull-request-reviewer[bot]` returned **201**, and the plain `Copilot` and `copilot` logins were accepted the same way.
  So the login spelling is not what decides the outcome, and a `422` seen elsewhere is likelier to be about whether Copilot review is enabled for that repo at all -- untested here, since bcs has it enabled.
  The 201 body lists Copilot under `requested_reviewers`, but an immediate `GET .../requested_reviewers` returns `{"users":[],"teams":[]}` and `gh pr view --json reviewRequests` returns `[]`.
  Neither surface therefore answers "was Copilot asked to review this", in either direction.
  (Probed on `ucdavis/bcs#479`, 2026-07-30.)

  That disappearance is **not** explained by the `review_on_push: true` rule above, and [`shared/workflow/pr-on-claim.md`](../shared/workflow/pr-on-claim.md)'s "blocked-request test has a false positive" section owns the argument and the deriving queries.
  The short version: `Morrison-Lab/ai-config` reproduces the identical 201-then-empty signature while carrying no `copilot_code_review` rule at either scope, so an empty pending list is evidence neither that the request was blocked nor that a review is coming.
  Only the posted review **body** settles which of those happened.

  **Both outcomes were genuinely observed on the same repo the same day, so do not flatten this into "it returns 201".**
  One session ran the POST once and got `422`; another ran it three times, across all three login spellings, and got `201` every time.
  Neither session was lying, and the first one's real mistake was not the observation but the generalisation -- it turned a single failed attempt into a stated property of the repository, wrote that into a PR body as settled fact, and steered two later rounds with it.
  The second session's report then invited the mirror-image error, of treating `201` as the settled answer.

  The likeliest reconciliation, **untested**: GitHub answers `422` when the requested reviewer is already pending.
  The `review_on_push: true` rule above re-requests Copilot on **every push**, so there is a window after each push in which Copilot is already a pending reviewer and a manual request is a duplicate.
  That would make the response depend on *when* you ask rather than on how, and it fits both observations without either being wrong.
  It stays untested on purpose: probing consumes the per-user quota that is usually the actual reason Copilot is absent, so the experiment damages the thing it would explain.

  The operational advice does not depend on resolving it.
  Don't spend a call on this endpoint either way -- the ruleset already requests the review, and neither response tells you whether one is pending.

  **As of 2026-08-04, Copilot is quota-exhausted across Morrison-Lab and unavailable until September 2026, so do not request it at all until then.**
  The user stated this directly on 2026-08-04, in the words "copilot is unavailable until september" and "stop trying to get copilot reviews".
  Until then, skip both the `requested_reviewers` POST for `copilot-pull-request-reviewer[bot]` and the `request_copilot_review` MCP tool: either only produces a `COMMENTED` review whose whole body is *"Copilot was unable to review this pull request because the user who requested the review has reached their quota limit."*, which wastes a round and is not a verdict.
  This is a time-bounded override of two standing instructions that otherwise say to request Copilot every round: `shared/workflow/pr-on-claim.md`'s "Request the external reviewer in the same stride" and `shared/workflow/review-verdict-pitfalls.md`'s fifth case ("Keep re-requesting each round anyway").
  Until September 2026, rely on `claude-review` plus self-review, which is exactly the no-reachable-external-reviewer fallback that fifth case already describes.
  Re-verify Copilot's quota and re-enable the per-round request after September 2026, per `shared/writing/timestamp-volatile-claims.md`.
  **Re-measured 2026-08-06 with a wider denominator:** across `Morrison-Lab/ai-config`'s last 60 merged PRs, every Copilot review object carries a refusal body and **zero** are substantive (query in [`shared/workflow/pr-on-claim.md`](../shared/workflow/pr-on-claim.md), which also explains why the object count drifts between runs while the zero does not).
  Say *refusals* rather than *quota refusals* when reporting a count like this, because the body alone does not name a cause: the 2026-08-06 Actions incident listed "Copilot code review" among its affected components, so a refusal inside that window has two candidate explanations.
  `Morrison-Lab/ai-config#1223` owns that discrimination and carries the timestamp table --- read it rather than re-deriving.
  Applying its two discriminators to this wider set clears it: all 39 objects predate the incident's `created_at` of `2026-08-06T15:22:49Z` (latest is `09:14:23Z`), and all 39 carry the quota-specific wording "because the user who requested the review has reached" rather than a generic error.
  Every one also postdates the override rather than explaining why it was written --- `select(.submittedAt >= "2026-08-04")` returns 39 of 39, earliest `2026-08-04T04:38:12Z`.
  So requests are still being issued despite this override, and each one spends a request on a guaranteed non-verdict.
  That every one of those PRs merged on `claude-review` alone is the same practice slippage [`shared/workflow/flag-practice-slippage.md`](../shared/workflow/flag-practice-slippage.md) already records at eight PRs, met here at larger scale and still live; read that fragment for the argument rather than re-deriving it.
  A `no-unreviewed-pr.py` `Stop` hook (ai-config#1041) enforces the opposite instruction, and until 2026-08-19 it collided with this override on every turn the quota was out.
  It fired every turn a PR opened or readied this session sat awaiting review, demanding a Copilot request -- the one action this override forbids -- so a session honoring the override never satisfied it and the demand repeated each turn.
  One Morrison-Lab/gha session spent over a dozen turns in this loop before the collision was recognized.
  That loop persisted even though each request POST succeeded, because the hook discharges only on a reviewer-request that is the **last simple command in the call** (its exit status is then unambiguous), and every turn chained a verify `gh pr view` after the POST, leaving it non-last.
  Running the POST as its own last command would discharge the hook, but that is still the Copilot request the override forbids.
  So no discharge available to a session honoring the override was ever the right fix.
  The collision was in the hook's own demand rather than in how any session answered it.
  (Reproduced on Morrison-Lab/ai-config#1128, 2026-08-04.)

  **Superseded 2026-08-19 (ai-config#1709): the script now honors this override itself, and nothing needs unregistering.**
  `hooks/no-unreviewed-pr.py` carries `MORATORIUM_END = 2026-09-01`, matching the September 2026 expiry above, and returns before scanning while that date is still ahead --- so the collision is gone on every installation shape and the guard re-arms itself on the day the override names, with nobody having to remember.
  Keep the two in step: extending the moratorium here means editing that constant in the same PR, or the memory and the hook start disagreeing again.

  The remedy this paragraph used to give --- unregister it from `~/.claude/settings.json`'s `Stop` hooks --- covered only ONE installation shape, and it is worth recording why rather than just deleting it.
  Where ai-config is installed as a **plugin**, the registration lives in ai-config's own `hooks/hooks.json` under `${CLAUDE_PLUGIN_ROOT}`, so there is nothing in the user's settings to remove: the edit succeeds, changes no behaviour, and the hook keeps firing.
  A remedy that silently does nothing is worse than none, because it reads as applied.
  The plugin shape is now the common one --- `d-morrison/rme#1074` migrates off the `.ai-config` submodule, and `Morrison-Lab/gha`'s `run-claude-review-attempt` installs the plugin for every review run --- which is the general lesson: a fix aimed at a local registration has to name which installation shape it assumes.

  - **Do:** treat the hook's `MORATORIUM_END` as the switch, and move it and this memory together.
  - **Don't:** unregister the hook from `~/.claude/settings.json` to quiet it --- that does nothing on a plugin install, and nothing is needed on any install now.

  The general form of that lesson --- any hook suppression aimed at a registration is blind to one of the two installation shapes --- lives in [`shared/workflow/keep-checkouts-fresh.md`](../shared/workflow/keep-checkouts-fresh.md), beside the enabling-direction hazard it mirrors.

  **Restated and widened 2026-08-19: the moratorium covers ALL REPOS, not just Morrison-Lab.**
  The user said "stop requesting copilot reviews until september", then, asked about scope, "ALL REPOS".
  So the paragraph above should be read with `ucdavis/bcs` and every other repo inside it, not only the Morrison-Lab org the 2026-08-04 measurement happened to cover.
  The expiry is unchanged and deliberate: **September 2026**, after which re-verify the quota and re-enable the per-round request rather than letting the moratorium become permanent by default (`shared/writing/timestamp-volatile-claims.md`).

  The same session tried four `requested_reviewers` POSTs for `copilot-pull-request-reviewer[bot]` on `ucdavis/bcs` PRs #648, #649, and #650.
  Each was accepted with HTTP **200**, and each left zero Copilot reviews behind, the pending request absent from both `gh pr view --json reviewRequests` and the `GET .../requested_reviewers` endpoint.
  Re-verified 2026-08-20: all three PRs still carry zero Copilot reviews and no pending Copilot request.

  **Read that as weak evidence, not as the 201-then-empty signature above, and the reason is the status code.**
  `hooks/no-unreviewed-pr.py`'s `_argv_close` docstring records that GitHub accepts this POST on a **merged or closed** PR with HTTP **200** and adds nobody, which is a different outcome from the **201** the signature above is defined by.
  Two of the three PRs fit that reading: #648 was closed at `2026-08-20T01:33:34Z` and #649 merged at `01:40:47Z`, both plausibly before the POSTs.
  #650 was open throughout and remains open, so at least one of the four is not explained that way, but the per-POST timings were not recorded and cannot now be recovered.
  So this measurement does not establish that a Copilot request fails on a live PR outside Morrison-Lab.
  It is not what the moratorium rests on either --- the maintainer's directive is --- and it is kept here only so a later reader does not re-derive it as fresh support.
  A clean version of the experiment would POST once on a PR known to be open and record the status code beside the timestamp.

  **This outranks `hooks/no-unreviewed-pr.py`, which demands a Copilot request after every PR open, ready, or re-head.**
  That hook's docstring names two legitimate deferrals, a draft PR and a redaction PR.
  A standing maintainer directive is a third, and it wins: a user instruction outranks a skill or a hook.
  Say so in the PR or the recap when you defer on this ground, so the omission reads as a recorded deferral rather than as a missed step --- that is the whole reason to write it down, since silence and compliance look identical from outside.
  Unregistering the hook, per the paragraph above, remains the fix for the turn-by-turn nag while the moratorium is live.

  - **Do:** skip the `requested_reviewers` POST and `request_copilot_review` on every repo until September 2026, and state the directive as the reason when a PR ships without a Copilot request.
  - **Do:** rely on `claude-review` plus self-review meanwhile, which is the same no-reachable-external-reviewer fallback the paragraph above already cites --- `shared/workflow/review-verdict-pitfalls.md`'s fifth case.
    Withheld-by-policy is not literally unreachable, so the fit is by analogy rather than by definition.
    Say which one applies when reporting a PR's review state.
  - **Don't:** read `hooks/no-unreviewed-pr.py`'s demand, or `shared/workflow/pr-on-claim.md`'s "request the external reviewer in the same stride", as overriding a standing user directive.
  - **Don't:** treat an accepted POST (200 or 201) as evidence the moratorium is over --- all four 2026-08-19 requests were accepted and none produced a review.
  - **Don't:** let September 2026 pass without re-verifying.
    The expiry is part of the rule, not a footnote to it.

  **Recurrence 2026-08-21 (Morrison-Lab/gha#571), and the new failure is what happened AFTER the request, not the request itself.**
  Copilot was requested on that PR on 2026-08-20 despite this moratorium, which is the slippage already recorded above.
  What had not been recorded is the second half: the absence of a review was then investigated as an **open question**, and `Morrison-Lab/gha#575` was filed asking whether Copilot is licensed for the org --- a question the 2026-08-06 re-measurement above had already answered, with a wider denominator than the sweep that re-asked it.
  The issue was retracted and closed within the hour.
  Read that as the more expensive error of the two.
  A forbidden request wastes one call.
  Treating its predictable silence as a mystery spends a search sweep, a negative-control sweep, and a filed issue,
  and it publishes a tracker item asserting that Copilot is "one of two cross-vendor reviewers still in service" while a standing directive says it is not.
  The rule this violates is already in the corpus and is not Copilot-specific: [`shared/workflow/grep-is-not-coverage.md`](../shared/workflow/grep-is-not-coverage.md) governs asserting a gap from a search, and the gap here was in the memory file rather than in the repo.

  **The moratorium's mechanism is enforced against the HOOK and not against the session, which is why a self-initiated request still gets through.**
  `hooks/no-unreviewed-pr.py`'s `moratorium_active()` makes the guard return before scanning, so it stops **demanding** a Copilot request.
  Nothing anywhere refuses one a session decides to make on its own initiative.
  Standing down and forbidding are different operations, and the paragraphs above describe only the first --- so the fix for the turn-by-turn nag is complete while the directive itself has no enforcement at the moment of action.
  Tracked as `Morrison-Lab/ai-config#1877`.

  **`reviewed-by:copilot-pull-request-reviewer` is not a way to ask whether Copilot has engaged, and its zero is a trap.**
  Measured 2026-08-21: that qualifier returns `total_count: 0` for both `Morrison-Lab/gha` and `Morrison-Lab/ai-config`, while ai-config demonstrably holds the 39 Copilot review objects counted above.
  So refusal reviews are not indexed by it, and a zero there means neither "never requested" nor "never answered".
  The posted review **body** remains the only surface that discriminates, exactly as [`shared/workflow/pr-on-claim.cases.md`](../shared/workflow/pr-on-claim.cases.md) already says for the pending-request list.

  **Two negative controls are needed before reading anything into a zero from a `reviewed-by:` search, and they test different things.**
  The first is the ordinary one this corpus already requires of any sweep: does the detector run at all?
  `repo:Morrison-Lab/ai-config reviewed-by:the repository owner` returns `total_count: 273`, so the qualifier works.
  The second is specific to a search keyed on a **login**, and it is free: GitHub rejects a nonexistent one outright rather than returning zero.
  `reviewed-by:Copilot` fails with `422 Validation Failed ... The listed users cannot be searched either because the users do not exist or you do not have permission to view the users`, whereas `copilot-pull-request-reviewer` returned `0` with no `422`.
  A quiet zero therefore establishes that the login resolved, and a `422` establishes that it did not --- so the error channel is the negative control for the predicate, and running the search against a deliberately bogus value is the cheapest way to prove the value you care about was understood.
  Note what neither control can reach: both came back clean here, and the zero was still uninformative for the reason in the paragraph above.

  - **Do:** run a bogus-value search alongside a login-keyed one, so a `422` versus a quiet zero tells you whether the value resolved.
  - **Do:** re-read this section before investigating a missing Copilot review --- the answer for any date before September 2026 is already here.
  - **Don't:** treat a moratorium the hook honors as a moratorium the session is prevented from breaking.
    Only the nag is mechanized.
  - **Don't:** file an issue asking why Copilot did not review, or whether it is licensed, while the moratorium is live.
- **`gh pr checks` prints the literal word `fail` for a CANCELLED job, but only
  when its output is not a terminal --- which is always, for an agent.**
  A cancellation and a real failure are therefore the same word in the column
  most people read, and they want opposite responses: a re-run versus a
  debugging round.
  `gh` itself distinguishes them internally and then discards the distinction
  on the way out.
  In `cli/cli` v2.92.0 (the installed version, checked with `gh --version`),
  `pkg/cmd/pr/checks/aggregate.go` gives `CANCELLED` its own bucket, separate
  from `ERROR`/`FAILURE`/`TIMED_OUT`/`ACTION_REQUIRED`:
  ```go
  case "CANCELLED":
      item.Bucket = "cancel"
  ```
  `pkg/cmd/pr/checks/output.go` renders that bucket as a muted `-` in a TTY,
  identically to `skipping` --- and then, for the non-TTY table:
  ```go
  if o.Bucket == "cancel" {
      tp.AddField("fail")
  } else {
      tp.AddField(o.Bucket)
  }
  ```
  So a human at a terminal sees a cancellation as a dash, and a piped or
  captured run sees `fail`.
  Two consequences worth keeping apart.
  A human's report of what they saw and an agent's are not describing the same
  output, so "it's showing as failing" from one is not corroboration for the
  other.
  And the fix is one flag, not a heuristic: **`--json name,state,bucket`**
  preserves `bucket: "cancel"` and `state: "CANCELLED"` distinctly from `fail`,
  which decides it exactly rather than by inference
  ([`algorithmatize-checks`](../shared/workflow/algorithmatize-checks.md)).
  Duration is a decent corroborating tell --- a review job cancelled by a
  concurrency race dies in seconds where a real one takes minutes --- but take
  it from `completed_at` minus `started_at` on a completed run, never from
  `status`, per [`fully-clean`](../shared/workflow/fully-clean.md) criterion 1.
  Prefer the flag to the tell: the flag is exact and the duration is a prior.
  For the cause of these cancellations, and why the *gate* job then reports
  failure too, see the `cancel-in-progress` entries in
  [`memories/debugging.md`](debugging.md) and
  [`pr-on-claim`](../shared/workflow/pr-on-claim.md).
  (2026-07-31: a 6-second "failing" `review / claude-review` was read as a real
  failure and debugged as one; it was a concurrency cancellation, and needed
  only a re-run.
  Confirmed against a real cancelled run on Morrison-Lab/ai-config commit
  `7b006485`, whose `review / claude-review` check run carries
  `conclusion: cancelled` while its dependent `review / require-review` carries
  `conclusion: failure`.)
- **`gh run list -w "Workflow Name"` fails if multiple workflow files share the same `name:` field in their YAML.**
  The command exits 1 with `could not resolve to a unique workflow; found: workflow-a.yml workflow-b.yml`.
  This happens commonly when reusable workflows (like a review action) are called by multiple caller workflows, or when two different files just happen to use the same `name`.
  The fix is to query by the **exact filename** instead of the display name: `gh run list -w workflow-b.yml`.

## gh — stale remote URL causes cryptic `gh pr create` failure
- `gh pr create` fails with `Head sha can't be blank, Base sha can't be blank, No commits between <owner>:main and <other-owner>:<branch>` when `origin` points to an **old repo URL** (e.g. after a GitHub repo transfer/rename).
  The transfer-specific form of this failure, where `git` follows the redirect and `gh` does not, is in [`github-repo-transfers.md`](github-repo-transfers.md).
- Fix: `git remote set-url origin https://github.com/<new-owner>/<repo>.git` and re-push the branch before creating the PR.
- Diagnosis: `git remote -v` shows the stale URL; `gh repo view --json nameWithOwner` shows where `gh` thinks the canonical repo is.
- **`gh repo view <old-slug> --json nameWithOwner` is the whole detector, and it
  resolves the redirect for you** --- ask for the old name and read which name
  comes back.
  That makes the check a one-liner per repo, so run it over *every* local
  checkout rather than over the ones you happened to notice.
  Stale remotes accumulate from unrelated events --- an org transfer, a repo
  rename, a move between orgs --- so the set you know about is rarely the set
  that exists.
  (2026-07-29: a sweep of 118 local checkouts found 5 stale, and only **one**
  was the `the repository owner` -> `Morrison-Lab` transfer being fixed at the time
  (`gha`; the other repo in that transfer had already been corrected by hand
  before the sweep ran, so it was no longer stale).
  The rest came from three unrelated events: two repos moved out of
  `UCD-SERG` to `the repository owner` (`qbt`, `qwt`), one moved from `UCD-IDDRC` to
  `ucdavis` (`fxtas`), and one plain rename, `snapshot.data` -> `snapr`.
  So 1 + 2 + 1 + 1, which is the point --- four of the five had nothing to do
  with the move that prompted the sweep.)
- **Preserve the URL scheme when rewriting a remote.**
  A remote on SSH (`git@github.com:<owner>/<repo>.git`) rewritten to the
  `https://` form still works for public reads, so nothing fails immediately ---
  but it silently moves that repo's auth from your SSH key to whatever
  credential helper HTTPS uses, which surfaces later as an unexpected
  credential prompt or a push denial.
  Read the existing URL first and rebuild it in the same form.
  A scripted sweep is where this bites, since a single hard-coded
  `https://github.com/...` template rewrites every remote it touches into HTTPS
  regardless of what each one was.
  (Same sweep: 4 of the 5 were HTTPS and one, `snapr`, was SSH; the template
  converted it before the mismatch was spotted and reverted.)

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
- **`glab api` has no `--jq` flag**, unlike `gh api`: passing one errors with
  `Unknown flag: --jq`.
  Pipe the raw JSON to `jq` separately instead:
  `glab api "projects/<id>" | jq '.default_branch'`.
- **A self-hosted GitLab instance on an institutional internal network may
  only resolve while on that network's VPN.**
  A DNS failure (`NXDOMAIN` / `no such host`) for the GitLab hostname, with
  ordinary internet DNS resolving fine otherwise, points at needing the VPN
  rather than a broader outage or sandbox restriction: `nslookup <host>`
  before and after connecting confirms it.
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
- There is no `gh`/`glab` CLI in these sessions, so `mcp__github__*` is the
  normal path for anything the API would answer.
  - **The REST API itself is not necessarily unreachable from bash, though ---
    it can be scope-limited instead, so test rather than assume.**
    This entry asserted flatly that no REST API was reachable from a
    Bash/Monitor script until 2026-07-26, when a session found otherwise.
    A plain `curl` to `api.github.com` went through the agent proxy and
    answered normally for a repo in that session's GitHub scope:
    ```
    $ curl -sS -o /dev/null -w '%{http_code}\n' \
        https://api.github.com/repos/d-morrison/altdoc
    200
    ```
    For a repo outside the scope it returned `403`, with a body naming the
    scope as the reason rather than a generic denial:
    ```
    $ curl -sS https://api.github.com/repos/actions/checkout
    {"message":"GitHub access to this repository is not enabled for this
     session. Use add_repo to request access. ..."}
    ```
    Sandbox policy varies, so the older claim may well have been true of the
    environment it was written in --- which is the point: check the behavior
    in the sandbox you are actually in.
    The consequence bullet below, that a background Monitor cannot poll PR
    state, rests on the same assumption and deserves the same re-check before
    you rely on it either way.
  - **A repo the REST API refuses may still be reachable through
    `mcp__github__*` --- measure both surfaces rather than assuming one scope.**
    They shared a scope in the session that wrote this and did not in a later
    one; see [`github-mcp-tools.md`](github-mcp-tools.md)'s org-gate entry.
    `git ls-remote https://github.com/<owner>/<repo>` works against any public
    repo whatever the scope is, because it is a git operation and the proxy
    passes those through unchanged.
    That answers every ref question the REST API would have --- which tags and
    branches exist, and which shas they point at --- and that is usually the
    whole reason an out-of-scope repo came up.
    So the ladder is: MCP tools, then `add_repo` if the repo genuinely needs
    API or write access, then `git ls-remote` for anything that is only a ref
    lookup.
    See [`git-tags.md`](git-tags.md)'s "Resolving a tag to a COMMIT sha" for the exact
    refspec form to ask for.
    (d-morrison/altdoc#65, 2026-07-26: SHA-pinning seven third-party actions
    needed tag shas from `actions/`, `r-lib/`, `r-hub/`, `quarto-dev/`, and
    `JamesIves/`, none of them in session scope, and `add_repo` would have been
    five pointless scope grants for five ref lookups.)
  - **The `github.com` web host 403s on scope exactly as `api.github.com`
    does, so `curl -I https://github.com/<owner>/<repo>` answers nothing
    about whether the repo exists.**
    The bullet above covers the API host; the web host is the one reached for
    when the question is existence rather than data, and it is the likelier
    mistake because a `403` there reads as GitHub refusing rather than as the
    proxy refusing.
    Both hosts return the proxy's verdict on **session scope**, so a repo can
    be public, healthy, and 403 --- and the same probe returns 200 for a repo
    that is merely in scope, which makes the pair look like a real signal
    about the repos rather than about the allowlist.
    `git ls-remote` is the instrument, per the ladder above, and it
    discriminates every case.
    Measured 2026-08-09, from a session scoped to `Morrison-Lab/ai-config`
    and `Morrison-Lab/wai`:

    | repo | `curl -I` | `git ls-remote <url> HEAD` |
    |---|---|---|
    | `d-morrison/ai-config` | 403 | `7d843650...` |
    | `Morrison-Lab/ai-config` | 200 | `7d843650...` |
    | `d-morrison/macros` | 403 | `8ce5d0cf...` |
    | `Morrison-Lab/macros` | 403 | `fatal: could not read Username` |

    Read the `curl` column as a table of the allowlist and nothing else:
    the one 200 is `ai-config`, which is in scope.
    Two things the `ls-remote` column settles that no `curl` here could.
    An **identical HEAD under two owner spellings** proves a live rename
    redirect, which makes it the sharpest rename detector available --- better
    than the `raw.githubusercontent.com` probe in this file's own
    "`raw.githubusercontent.com` FOLLOWS repository-rename redirects" bullet,
    since that one has to be run under the *new* name with a known-moved
    control or it answers backwards, whereas comparing two shas needs no
    control at all.
    And `fatal: could not read Username for 'https://github.com'` is how an
    **absent or private** repo presents on an anonymous read: git falls back
    to asking for credentials rather than reporting a 404.
    Set `GIT_TERMINAL_PROMPT=0` so that case fails immediately instead of
    blocking on a prompt.
    Note the pair `d-morrison/macros` resolving while `Morrison-Lab/macros`
    does not --- the opposite direction from `ai-config`, which is why a
    blanket owner rewrite across both would break a working reference.
    (`Morrison-Lab/wai#54`, 2026-08-09: a `.gitmodules` still naming
    `d-morrison/ai-config` resolved only through the rename redirect, so
    nothing was visibly broken; `macros` was correctly left pointed at
    `the repository owner`.)
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
  drip 1-2 pre-existing cosmetic nits per round. That drip is a reason to keep
  iterating, never a reason to stop or to ask whether to stop --- see
  `skills/ardi/SKILL.md`, "Stopping conditions".

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

## `gh search code` is not a reliable way to enumerate consumers

When a shared repo moves or cuts a breaking release, the question is which
repos call it.
Code search is the obvious instrument and it is **incomplete**: it silently
omits repos whose content it has not indexed, and nothing in the response
says so.

Measured 2026-07-28, hunting callers of a renamed `d-morrison/gha` across ten
owners: an owner-scoped `gh search code '"d-morrison/gha" user:...'` returned
176 hits across 23 repos, and missed `d-morrison/altdoc`, a live consumer with
four workflow files calling it.
An exhaustive scan of all 947 non-archived repos found it immediately.

So treat code search as a fast first pass, never as the census.
The census enumerates repos and reads their workflow files:

```bash
LIMIT=1000
for o in <owners>; do
  # gh repo list works for users AND orgs; `gh api /orgs/$o/repos` 404s on a
  # user account, so don't substitute it just to get --paginate.
  n=$(gh repo list "$o" --limit "$LIMIT" --no-archived --json nameWithOwner \
        --jq '.[].nameWithOwner' | tee -a repos.txt | wc -l)
  [ "$n" -ge "$LIMIT" ] && echo "TRUNCATED: $o hit --limit $LIMIT; raise it" >&2
done

while read -r r; do
  echo "$r" >> scanned.txt          # before any early exit, per fail-fast
  files=$(gh api "/repos/$r/contents/.github/workflows" --jq '.[].path' 2>err.txt) || {
    # 404 = no workflows dir, expected. Anything else is an error, not a miss.
    grep -q '"status": "404"' err.txt || echo "ERROR: $r $(tr -d '\n' < err.txt)" >&2
    continue
  }
  for f in $files; do
    gh api "/repos/$r/contents/$f" -H "Accept: application/vnd.github.raw" \
      | grep -q "<old-owner>/<repo>" && echo "$r $f"
  done
done < repos.txt

echo "scanned $(wc -l < scanned.txt) of $(wc -l < repos.txt)"
```

Note what the error branch is for: a blanket `2>/dev/null` on those calls
swallows the 403 secondary-rate-limit failures the next section describes
alongside the 404s it is meant to hide, so a rate-limited run reports fewer
hits rather than an error.
That is the same false-all-clear
[`fail-fast`](../shared/principles/fail-fast.md) covers, arriving in the very
command written to prevent it.

Three things that scan still misses, so state them rather than claiming a
clean census:

- **Non-default branches.** It reads each repo's default branch only, so an
  open PR branch carrying the old reference is invisible.
  Those self-heal on the branch's next `main` sync when the branch does not
  itself touch the file, but they break the branch's CI until then.
- **Paths outside `.github/workflows/`.** A composite action under
  `.github/actions/*/action.yml` can carry its own `uses:`, and is missed by
  a workflows-only glob.
  Widen the path filter, or use the git-trees API to list every blob under
  `.github/` in one call per repo.
- **A local checkout is not evidence about the remote.**
  `d-morrison/methods.paper` had four gha-calling workflows on disk, all on an
  unmerged branch; the remote default branch had no `.github/workflows`
  directory at all.

## A secondary rate limit fires while `rate_limit` still reports headroom

`gh api /rate_limit` reporting `core: 4936/5000` does **not** mean the next
call will succeed.
GitHub enforces a separate concurrency/abuse limit, and at `xargs -P 12`
across a few thousand `contents` reads, `/repos/{owner}/{repo}` began
returning 403 `API rate limit exceeded for user ID <n>` while the
`rate_limit` endpoint went on reporting nearly the full core budget unspent.
The two counters are not the same counter, so the cheap check does not
predict the expensive one.

Two practical consequences:

- **Back off rather than retry.** Re-running the same fan-out at the same
  concurrency reproduced it immediately; the limit cleared on its own after
  roughly fifteen minutes.
  Lower the parallelism (`-P 3` completed the remainder without incident)
  rather than looping.
- **Log coverage, not just hits.** A per-repo scan that exits early on a 403
  records nothing for that repo, so the run reports fewer findings rather
  than an error.
  Print `scanned N of M` and diff the two lists, or a truncated sweep reads
  exactly like a clean one.
  (2026-07-28: a 947-repo scan reported 910 scanned; the 37-repo shortfall
  was the whole signal that anything had gone wrong.)

## `git push --mirror` into a freshly-created empty repo can pick the wrong default branch

Pushing multiple branches with `git push --mirror` into a GitHub repo that
was just created with `gh repo create` (no initial commit, so no branch is
yet the "real" default) can leave GitHub's `default_branch` pointing at an
arbitrary pushed branch instead of the source repo's actual default (e.g.
`main`).
Nothing errors; the mirror push reports every branch and tag landing
successfully, and the wrong default is silent until someone opens the repo.

Check and fix after any mirror push into a new repo:

```bash
gh api repos/<owner>/<repo> --jq '.default_branch'
gh api -X PATCH repos/<owner>/<repo> -f default_branch=main
```

(2026-08-06, mirroring an internal GitLab repo whose default branch was
`main`: the fresh GitHub repo came back with a `claude/issue-3-...`
feature branch as `default_branch` instead.)

## `claude-code-action`'s `Task`/`Agent` tool is not gated behind `--allowedTools`

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

## Verify GitHub App installation per repository

- **`gh api orgs/<org>/installations` answers this without a browser, in any org you own.**
  Measured 2026-08-21 under a classic PAT carrying `admin:org`: `Morrison-Lab` returned `claude`, `google-labs-jules`, and `cursor`.
  The `cursor` slug means the GitHub App is installed, not that Bugbot
  reviews PRs.
  Dashboard enablement, the Enterprise GHA queue, and the author-mismatch
  on `bugbot run` are in [`cursor-bugbot.md`](cursor-bugbot.md).

  ```bash
  gh api orgs/<org>/installations --jq '.installations[].app_slug'
  ```

- **A 404 from that endpoint is about the caller's org ROLE, not about token class.**
  GitHub documents that "the authenticated user must be an organization owner to use this endpoint"
  ([List app installations for an organization](https://docs.github.com/en/rest/orgs/orgs#list-app-installations-for-an-organization)).
  So the same PAT that answers for `Morrison-Lab` returned 404 for `ucdavis` on 2026-08-21, where we are not an owner --- the token was fine and the role was missing.
  Don't generalize that 404 into "a classic PAT cannot check installations";
  it is a per-org fact rather than a property of the credential.
  Note the response is a bare `404 Not Found` rather than a `403`, so nothing in it names the missing role --- which is why the 404 invites a token-shaped explanation it does not support.
- **The two endpoints that genuinely need App credentials are different endpoints, and neither explains the 404 above.**
  `GET /repos/<owner>/<repo>/installation` needs an app JWT, and `GET /user/installations` needs a GitHub App user access token
  ([GitHub App installation API](https://docs.github.com/en/rest/apps/installations)).
  Both are true and neither is the org endpoint, so neither is evidence about it.
- **Fall back to the browser for an org you don't own.**
  With repository-admin access, open `https://github.com/<owner>/<repo>/settings/installations` and read the **Installed GitHub Apps** list.
  This distinguishes an installed Claude app from a repository that merely has workflow files or secrets.
- Verified 2026-08-21 by that route: `ucdavis/bcs` listed **Claude**, developed by Anthropic, while `ucdavis/hac.it` listed only GitHub Learning Lab.

## A moving upstream tag can turn a consumer's default branch red with no local change

A consumer pinned to a moving major tag (`...@v2`) inherits every change the
tag's owner slides under it, so its default branch can go green-to-red between
two consecutive commits while nothing changed that the check even looks at.

Two cheap reads settle it before anyone's diff is opened.
Check whether the **default branch itself** is red rather than only the PR,
since that means the cause is not in any open branch; then intersect the red
commit's changed files with the flagged files, where an empty intersection
points at the moving pin upstream.

**A tail-limited log fetch truncates the beginning of the output**, so earlier
findings are absent and a complete checker looks partial.
Read the checker's own summary line, which usually states the true total.

- **Do:** read the default branch's status and intersect the red commit's
  changed files with the flagged files, before diagnosing anyone's diff.
- **Do:** compare a checker's stated total against the entries a fetch
  returned, and re-derive the affected set from its own extension list.
- **Don't:** read a green-to-red transition as evidence the red commit caused
  it --- a moving pin changes what runs without changing what it runs on.
- **Don't:** treat a tail-limited log read as the breakage's full scope.

(2026-08-15: a consumer pinning a shared `check-non-standard-chars` workflow
at `@v2` went red when that checker's banned-glyph set gained U+00D7.
The red commit changed only a demo JSON and one GDScript file --- no file the
checker scans and no workflow file.
The log itself was complete, opening `Found 19 non-standard character(s) in 4
file(s)` and listing all four; a `tail_lines`-capped fetch showed only the last
two, and that partial read was mistaken for the checker's own output.
An independent scan produced the right set anyway, so the fix was correct while
the reason given for it was not.)

## Diagnosing a stub/no-verdict `claude-code-review` run

Covered in [`claude-bot-workflows.md`](claude-bot-workflows.md)'s
"A `claude-code-review`-style job that fails with 'no verdict written'"
bullet, not here --- that file is scoped to the bot's own runtime behavior,
which is what this diagnostic technique is about.
Download and parse the run's `claude-review-execution-*` artifact
(exact naming, `jq` pattern, and a worked case are there) rather than
reading the job log's own summary line, which never shows which tool
call was actually denied.

## `gh pr edit` can fail on Projects-classic deprecation; PATCH the pulls REST endpoint instead

`gh pr edit <N> --body-file <f>` can fail outright with
`GraphQL: Projects (classic) is being deprecated ... (repository.pullRequest.projectCards)`
--- the command's GraphQL query requests `projectCards` whether or not the
edit involves projects, so the deprecation kills an ordinary body update.
The REST route performs the same edit without touching that surface:

```bash
gh api repos/<owner>/<repo>/pulls/<N> -X PATCH -F body=@<file>
```

`-F body=@<file>` keeps the body-file discipline (backtick-safe, no shell
interpolation), same as `--body-file` on the porcelain command.

- **Do:** fall back to the REST PATCH when `gh pr edit` errors on
  `projectCards`, rather than retrying or hand-editing on the web.
- **Don't:** read the error as a permissions or repo problem --- the failing
  field is one the edit never needed.

(Measured 2026-08-23 on Morrison-Lab/ai-config#1976, gh in a local Windows session;
the REST PATCH succeeded immediately on the same body file.)
