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
- **A reply posted via `gh pr comment`/`gh api` from within a session shows up under the *human user's own* GitHub account, not a bot identity — don't mistake it for an independent human review when auditing a PR's review state.** `gh` authenticates as whatever account is logged in locally (often the user's own, e.g. seen as `dem-extra1` on `Lacaedemon/sparta`), so when an agent (or a dispatched subagent) replies to an inline review comment on the user's behalf, `gh api repos/<o>/<r>/pulls/<N>/reviews` lists it as a `COMMENTED` review authored by the user — indistinguishable at a glance from the user genuinely opening the PR in a browser and typing a reply themselves. Before treating an unexpected review entry as a signal that the human intervened, check whether its body/inline-comment content reads like the agent's own scripted reply (referencing a specific commit SHA, restating verification numbers) rather than free-form human commentary — if so, it's the session's own tooling, not new human input.
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
- **An angle-bracket placeholder can vanish from a PR or issue body posted
  through these tools, and no markdown construct protects it.**
  A PR body written with `` `git ls-remote https://github.com/<owner>/<repo>` ``
  came back from the API as `git ls-remote https://github.com//`, with both
  placeholders gone.
  **No markdown construct protects them.**
  A controlled test posted the same string four ways in one body --- plain
  prose, an inline code span, an indented code block, and a fenced code block
  --- and all four came back stripped, so the removal happens to the raw body
  text and never reaches markdown parsing.
  The instinct that backticks make text literal is therefore wrong twice over
  here: neither the span nor the fence helps.
  What is lost is the *stored* body, not one rendering of it, so re-reading or
  re-rendering will not bring it back.
  The blast radius is narrower than it first looks, and worth knowing precisely:
  only text sent as a body through the API is affected.
  A `<placeholder>` inside a file committed in the same PR is untouched, so a
  memory entry documenting a command survives while the PR description quoting
  that same command does not.
  Write placeholders in a body without brackets --- `OWNER/REPO`, `PATH`, `N`
  --- and re-read the body after posting whenever the exact text matters.
  This is the "Postcondition gate" bullet at the top of this file made concrete:
  nothing errors, the object is created exactly as asked, and only reading the
  stored result back shows the content is not what was sent.
  (ai-config#734, 2026-07-26: caught only because the mangled URL happened to be
  re-read during an unrelated check.)
  **A later observation narrows what "angle-bracket" means here, and its
  mechanism is unconfirmed.**
  A PR body posted through `create_pull_request` on 2026-07-31 came back
  missing `<branch>`, `<gha-checkout>`, and `<base>`, leaving a documented
  command with no path and a `git reset --hard origin/` with no branch --- so
  the stored body carried instructions a reader would run and get wrong.
  Two contrasts stop that from reducing to "angle brackets are stripped".
  In the same body `<=` survived, stored as the escaped entity `&lt;=`, so
  only tag-shaped tokens went.
  And `<branch>` survived intact in a PR comment posted through
  `add_issue_comment` in the same session (ai-config#965), inside backticks in
  a blockquote, so the two write surfaces did not behave alike.
  Which layer strips --- the MCP tool, GitHub's sanitizer, or the two
  composed --- was not established, so read this as an observed effect rather
  than as a mechanism, and do not generalize either surface's behaviour to the
  other.
  The mitigation is unchanged and cheap: spell a placeholder in caps
  (`BRANCH`, `GHA-CHECKOUT`, `BASE`) in any body, where nothing can read it as
  a tag.
  Files in the diff were unaffected, as above --- the angle-bracket form
  inside a fenced code block is correct there and should stay.
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
- **`issue_write`'s `labels` REPLACES the issue's whole label set, and a name
  that does not exist yet is silently CREATED rather than rejected.** Two
  independent surprises in one parameter, pulling in opposite directions.
  The replace semantics come from the underlying REST "update an issue"
  endpoint, so passing `["needs-data"]` to an issue already carrying
  `["bug","tech-debt"]` drops both, with no warning and nothing in the
  response to notice --- always pass the **union** of existing plus new.
  Read the current labels first; `list_issues` already returns them, so a
  bulk pass needs no extra call per issue.
  The auto-creation runs the other way: it means a typo becomes a real label
  rather than an error, so a misspelling silently splits a set in two.
  Confirmed on `ucdavis/bcs`, 2026-07-29: applying `needs-data` to an issue
  in a repo that had no such label created it, and `get_label` then returned
  it with the default grey `#ededed` and an empty description.
  **Nothing in the MCP tool set can set a label's color or description** ---
  there is only `get_label` (`GET_LABEL` in
  [`tool-mappings.md`](../tool-mappings.md)), no create/update --- so a label
  born this way stays grey and undescribed until a human with **write**
  access fixes it, or a workflow with `issues: write` does it via `gh api`.
  Write, not admin: the Labels REST API's create/update endpoints need push
  access, while admin governs repository settings, branch protection, and
  webhooks.
  Note that the Triage role can *apply* an existing label but cannot create
  or edit one, so it is not sufficient here.
  Say so when handing off, rather than leaving someone to wonder why the new
  labels look unstyled.
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
  from `get_review_comments` --- **fetch them, never reconstruct one.** They
  are opaque base64, so a plausible-looking id assembled from a remembered
  prefix plus the suffix of a *different* thread fails with "Could not
  resolve to a node with the global id"; that error means the id was
  invented, not that the thread is gone.
  On a PR with many threads, the
  temptation is to skip a re-fetch because the list was read a few calls
  ago --- but a new review round appends threads, so the ones you need are
  exactly the ones not in that earlier read.
  When only the newest threads
  are wanted, `get_review_comments` takes an `after` cursor: pass the
  `endCursor` from the previous listing and get just what has appeared
  since, rather than re-fetching every thread.
  **`page` does not do this for this method**, so `page: 2` returns the
  first page again.
  The tool's own schema is the authority, not the REST
  endpoint [`tool-mappings.md`](../tool-mappings.md) lists as the `gh`
  equivalent: `after` is documented as "used only by the
  `get_review_comments` method", and that method's own description says
  "use cursor-based pagination (`perPage`, `after`)", while `page` is a
  generic parameter shared with the REST-backed methods on the same tool.
  The `PRRT_`-prefixed thread ids corroborate it --- those are GraphQL
  global node ids, which the REST comments endpoint does not return.
  So one `pull_request_read` tool spans both pagination models depending
  on `method`; don't generalize either one across it.
  (Guessed twice in one `d-morrison/altdoc#78` session, 2026-07-27,
  costing two failed calls before fetching properly.)
- **A repository transfer breaks `mcp__github__resolve_review_thread`
  specifically, and neither owner spelling works.**
  The standing advice for a transferred repo --- keep using whichever owner
  the session was scoped with, since the API follows the transfer redirect
  server-side --- holds for every call that names the repo by `owner`/`repo`
  **strings**.
  It does not hold for this tool, whose `threadId` is a GraphQL node ID that
  already encodes the post-transfer repo, so the declared owner and the node
  have to agree.
  Measured on `Morrison-Lab/ai-config` (transferred from `d-morrison`),
  2026-07-31, against PR #975 --- two different gates, one per spelling:
  - `owner: d-morrison` --- `Access denied: review thread
    PRRT_kwDOShagnM6VdO1_ does not belong to the declared repo
    "d-morrison/ai-config".`
  - `owner: Morrison-Lab` --- `Access denied: repository
    "morrison-lab/ai-config" is not configured for this session.
    Allowed repositories: d-morrison/gha, d-morrison/workflows,
    d-morrison/ai-config, d-morrison/rpt, d-morrison/qwt, d-morrison/qbt`

  The second is the session's own repo-scope list, which is fixed at session
  start, and `add_repo` refuses a cross-owner add --- so this is **not
  transient**, and re-testing it each polling round buys nothing.
  Every other tool used in that session worked normally under
  `owner: d-morrison`: `pull_request_read` (every method),
  `add_issue_comment`, `add_reply_to_pull_request_comment`,
  `update_pull_request`, `request_copilot_review`, and
  `subscribe_pr_activity`.
  So the split is between string-addressed and node-addressed calls, not
  between read and write.

  The consequence is worth stating plainly, because it is easy to mistake for
  work left undone.
  [`fully-clean`](../shared/workflow/fully-clean.md) makes "every inline
  review thread is resolved" a criterion for calling a PR clean, so in a
  transferred-repo session that criterion is **structurally unreachable**:
  every finding can be Addressed and replied to, and the PR still cannot be
  reported fully clean from this session.
  Resolve the threads from the GitHub UI, or from a session scoped to the new
  owner.

  One untested alternative, recorded so the next session tries it before the
  UI.
  `pull_request_review_write` with `method: resolve_thread` is a separate tool
  whose own schema says the `owner`, `repo`, and `pullNumber` it still
  requires "are not used for this method", so passing the session's own owner
  should clear the scope gate and then be ignored.
  That is an inference from the tool descriptions rather than a measurement,
  so treat it as one call worth spending, not as a known route.

  - **Do:** resolve the threads in the GitHub UI, or from a session scoped to
    the new owner, once this failure appears.
  - **Do:** say in the status report that the findings are addressed and
    replied to but the fully-clean criterion cannot be met from this session,
    naming the tool.
  - **Don't:** re-test the call each polling round --- the scope list is fixed
    at session start and `add_repo` cannot widen it.
  - **Don't:** report the PR fully clean because every finding was addressed;
    unresolved threads fail that criterion whatever the reason.
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
  **It is degraded in a sharper way than "dies with the session" suggests:**
  a `CronCreate` job can vanish from the store *before its fire time*, with
  no error and nothing to surface the loss.
  See the `CronCreate`-silent-loss entry in
  [`claude-code.md`](claude-code.md) for the observations and the
  `CronList` re-verification habit that catches it.
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
  bot-mention gate in `memories/claude-bot-workflows.md` -- a pass that inspects
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
