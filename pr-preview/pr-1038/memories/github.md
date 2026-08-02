# GitHub & GitLab CLIs and APIs

The GitHub MCP tool surface used in remote/web sessions lives in
[`github-mcp-tools.md`](github-mcp-tools.md).

## Operational checklist pattern for write actions

- **Preflight gate:** verify target branch/repo and whether the action should update an existing PR versus create a new one.
- **Safe command form:** when content includes markdown/backticks, write to a temp file and pass `--body-file` or `-F "body=@<file>"`; avoid inline double-quoted body args.
- **Postcondition gate:** after push/post/create, query GitHub state in the intended base repo (for PRs, include both repo and head owner) and confirm the intended object actually exists/updated. `gh pr list --head <owner>:<branch>` silently returns empty for an owner-qualified head even when a matching PR exists — verified directly against a real open PR (`gh pr list --head d-morrison:ums-pr635-lessons` returned `[]`; the bare `--head ums-pr635-lessons` found it). Use the REST API instead, with the branch passed as a `-f` GET field rather than interpolated into the raw URL — a branch name containing `#`, `&`, or `+` breaks a hand-built query string but is passed through correctly as a field: `gh api --method GET "repos/<upstream-owner>/<repo>/pulls" -f "head=<head-owner>:<branch>" -f "state=open" --jq '.[] | {number, url, state}'`.
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
  `d-morrison` is a `User`, so it would have 404'd on the first owner in the list.
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
  Note `statusCheckRollup.contexts` needs inline fragments, since a
  `CheckRun` and a legacy `StatusContext` carry different fields
  (`name`/`status`/`conclusion` versus `context`/`state`).
  (Morrison-Lab/ai-config#816, 2026-07-29: `core` returned `403` mid-round
  with `graphql` at 4922/5000; the round's reply, thread-resolve, ARD
  summary, and clean-state verification all went through GraphQL, and
  `core` reset 11 minutes later.)
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
- **A reply posted via `gh pr comment`/`gh api` from within a session shows up under the *human user's own* GitHub account, not a bot identity — don't mistake it for an independent human review when auditing a PR's review state.** `gh` authenticates as whatever account is logged in locally (often the user's own, e.g. seen as `dem-extra1` on `Lacaedemon/sparta`), so when an agent (or a dispatched subagent) replies to an inline review comment on the user's behalf, `gh api repos/<o>/<r>/pulls/<N>/reviews` lists it as a `COMMENTED` review authored by the user — indistinguishable at a glance from the user genuinely opening the PR in a browser and typing a reply themselves.
  Before treating an unexpected review entry as a signal that the human intervened, check whether its body/inline-comment content reads like the agent's own scripted reply (referencing a specific commit SHA, restating verification numbers) rather than free-form human commentary — if so, it's the session's own tooling, not new human input.
  **The same ambiguity runs the other way, and there it arrives as a positive claim rather than an inference you might draw.** An automated reviewer reading the PR's own history sees that same bot-account commit and can describe it *in its review body* as the work of a human, e.g. "that finding was confirmed and fixed by a human reviewer (`dem-extra1`) in commit `<sha>`", stating as fact something no API field asserts.
  That is worse than the inference case above, because the claim is now published prose a later reader inherits, and "a human already verified this" is precisely the sentence that stops the next person checking.
  Correct it in the thread when you see it, naming which account is actually a session identity; don't let it stand just because the surrounding verdict was clean. (`ucdavis/bcs#532`, 2026-07-31: a `claude-review` pass reported a fix as human-confirmed when `dem-extra1` was the Claude session that made it, and no human had touched the PR at that point.)
- **`gh pr view --json` does not accept `merged` as a field.** Use `state` (returns `"MERGED"`) and `mergedAt` (ISO timestamp, null if not merged) to check merge status. Example: `gh pr view <N> --json state,mergedAt`.
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
- **`raw.githubusercontent.com` FOLLOWS repository-rename redirects, so a `200` under the OLD owner proves nothing — only a `200` under the NEW owner is decisive.** To test whether a repo has moved, probe the *new* name and treat `404` there as "did not move". Run a known-moved repo as a control first, or the probe silently answers backwards: `d-morrison/gha` still returned `200` on `raw.githubusercontent.com` well after it became `Morrison-Lab/gha`, so an old-name probe reports every repo as "not moved". The REST API is not a substitute — behind an agent proxy `api.github.com/repos/<o>/<r>` can return `403` for every repo regardless of existence, which answers nothing in either direction. This matters before any blanket owner rewrite: probing all nine `d-morrison/*` references in ucdavis/bcs under the new owner showed only `gha` and `ai-config` had moved, so a find-and-replace would have broken `macros`, `altdoc`, `snapr`, `stats-allowlist`, `diffviewer`, `equation-anchors`, and `rme`. Note the bare `d-morrison` *username* (a `reviewer:` input, author metadata) is unaffected by a repo/org rename and must not be swept along. The Actions-side consequences of the same rename are in `github-actions.md` ("A repo/org rename breaks Actions `uses:` refs"). (2026-07-28.)
- **Download a user-pasted PR screenshot with `curl -L`.** When a user pastes an image into a GitHub PR comment, the file lives at `https://github.com/user-attachments/assets/<uuid>` and is publicly downloadable: `curl -L -o <dest>.png "https://github.com/user-attachments/assets/<uuid>"`. Retrieve the URL from the comment body via `gh api repos/<o>/<r>/issues/comments/<comment_id> --jq .body`.
- **Linking a GitHub sub-issue needs an integer DB id, not the number.** `POST /repos/<o>/<r>/issues/<parent>/sub_issues` takes `sub_issue_id` = the child's **database id** (`gh api repos/<o>/<r>/issues/<child> --jq .id`), *not* its issue number. Pass it with `-F` (typed, integer), never `-f` (string) — `-f sub_issue_id=…` fails with `422 Invalid property /sub_issue_id: "…" is not of type integer`. Full call: `gh api repos/<o>/<r>/issues/<parent>/sub_issues -F sub_issue_id=<child_db_id>`. Verify with `gh api .../issues/<parent>/sub_issues --jq '.[] | "#\(.number) \(.title)"'`.
- **Backticks in a double-quoted `-m` / `--body` string get command-substituted by the shell.** In the Bash tool, `` git commit -m "... `origin` ..." `` or `` gh pr comment --body "use `foo`" `` makes the shell run `` `origin` ``/`` `foo` `` as a command and splice the (usually empty/erroring) output into the message — silently mangling it (seen on sparta 2026-06-30: a commit body's `` `origin` `` and `` `killer` `` vanished, with `origin: command not found` in stderr). For any message/body containing backticks, use a single-quoted **heredoc** (`` -m "$(cat <<'EOF' … EOF)" `` — the quoted `'EOF'` disables all expansion) or a `--body-file`, never a bare double-quoted string. (Same root cause as ARD inline reply bodies too; use `-F body=@<file>` for `gh api .../pulls/<N>/comments`/`glab api .../notes` so backticks in Markdown never get shell-expanded.)
- **GitHub review inline comments are on a different API endpoint than top-level PR comments.** The top-level comment-view endpoint (`` `gh pr view <N> --json comments` `` or `gh api repos/<o>/<r>/issues/<N>/comments`) captures PR-level comments and bot-posted review overview summaries, but **not inline comments from formal reviews** (line-by-line inline findings). When a user links a specific review ID (e.g. `#pullrequestreview-4761444085`), fetch both the review overview and its inline comments separately: `gh api repos/<o>/<r>/pulls/<N>/reviews/<review-id> --jq '{state, body}'` for the overview, then `gh api repos/<o>/<r>/pulls/<N>/comments --jq '.[] | select(.pull_request_review_id == <review-id>) | {line: .line, body: .body}'` to get the inline findings. A review's overview body can be generic ("I reviewed the code") with all the actual findings in inline comments on specific lines — reading only the overview misses the findings. (Encountered on ai-config#647 review 4761444085: the overview body was generic, but the specific finding was in an inline comment on CLAUDE.md line 324.)

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

  **The reviewer-request API is not the surface to check, and a `422` reported for it did not reproduce.**
  `POST /repos/<o>/<r>/pulls/<N>/requested_reviewers` with `reviewers[]=copilot-pull-request-reviewer[bot]` returned **201**, and the plain `Copilot` and `copilot` logins were accepted the same way.
  So the login spelling is not what decides the outcome, and a `422` seen elsewhere is likelier to be about whether Copilot review is enabled for that repo at all -- untested here, since bcs has it enabled.
  The 201 body lists Copilot under `requested_reviewers`, but an immediate `GET .../requested_reviewers` returns `{"users":[],"teams":[]}` and `gh pr view --json reviewRequests` returns `[]`.
  Neither surface therefore answers "was Copilot asked to review this", in either direction.
  (Probed on `ucdavis/bcs#479`, 2026-07-30.)

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

## gh — stale remote URL causes cryptic `gh pr create` failure
- `gh pr create` fails with `Head sha can't be blank, Base sha can't be blank, No commits between <owner>:main and <other-owner>:<branch>` when `origin` points to an **old repo URL** (e.g. after a GitHub repo transfer/rename).
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
  was the `d-morrison` -> `Morrison-Lab` transfer being fixed at the time
  (`gha`; the other repo in that transfer had already been corrected by hand
  before the sweep ran, so it was no longer stale).
  The rest came from three unrelated events: two repos moved out of
  `UCD-SERG` to `d-morrison` (`qbt`, `qwt`), one moved from `UCD-IDDRC` to
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
  - **For a repo outside the scope, `mcp__github__*` is not a fallback either
    --- but git operations are.**
    The scope limits the MCP tools to the same repo list, so switching to them
    does not get around a `403`.
    `git ls-remote https://github.com/<owner>/<repo>` works against any public
    repo whatever the scope is, because it is a git operation and the proxy
    passes those through unchanged.
    That answers every ref question the REST API would have --- which tags and
    branches exist, and which shas they point at --- and that is usually the
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

## A repository transfer redirects `pull` paths but NOT `issues` paths

When a repo moves between owners (`d-morrison/gha` -> `Morrison-Lab/gha`),
GitHub's redirect does not cover every path shape, and the split is not
documented anywhere obvious.
Measured directly after one such move:

| Old-owner URL | Result |
| --- | --- |
| `.../gha` (repo root) | 301 -> new owner |
| `.../gha/tree/main/examples` | 301 -> new owner |
| `.../gha/blob/main/README.md` | 301 -> new owner |
| `.../gha/pull/34` | 301 -> new owner |
| `.../gha/issues/325` | **404** |

The issues themselves are fine --- the same numbers return 200 under the new
owner.
Only the redirect is missing, so every prose link of the form
`https://github.com/<old-owner>/<repo>/issues/N` becomes a hard 404 the
moment the transfer completes.

Two consequences worth knowing before diagnosing this:

- **A link checker goes red repo-wide, on `main`, with no diff to blame.**
  lychee's usual config accepts 301, so the redirecting links pass and only
  the issue links fail.
  Every open PR inherits the failure, which invites blaming whichever PR you
  happen to be looking at.
  Confirm by checking whether the failing files appear in the PR's own
  changed-file list at all: a file the diff never touched cannot be the
  cause.
  An identical count of old-owner links on `main` and on the branch
  corroborates it.
- **Do not infer that the issues were lost.**
  A 404 on the old owner says nothing about the new one.
  Request the new-owner URL before concluding anything; the fix is usually a
  plain rewrite rather than recreating or remapping anything.
  (This exact inference was made, published in a review, and had to be
  retracted --- gha#351, 2026-07-28.)

`uses:` resolution is a separate question from link resolution and behaves
differently again: Actions stopped resolving
`uses: <old-owner>/<repo>/.github/workflows/x.yml@v2` after the same
transfer, failing affected runs with `startup_failure` and **zero jobs**.
Note that a run started shortly before the cutover can still succeed, so two
attempts of the *same run* can disagree --- which is the cheapest available
proof that the cause is environmental rather than in the diff.

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
