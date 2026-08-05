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
- **`raw.githubusercontent.com` FOLLOWS repository-rename redirects, so a `200` under the OLD owner proves nothing — only a `200` under the NEW owner is decisive.** To test whether a repo has moved, probe the *new* name and treat `404` there as "did not move". Run a known-moved repo as a control first, or the probe silently answers backwards: `d-morrison/gha` still returned `200` on `raw.githubusercontent.com` well after it became `Morrison-Lab/gha`, so an old-name probe reports every repo as "not moved". The REST API is not a substitute — behind an agent proxy `api.github.com/repos/<o>/<r>` can return `403` for every repo regardless of existence, which answers nothing in either direction. This matters before any blanket owner rewrite: probing all nine `d-morrison/*` references in ucdavis/bcs under the new owner showed only `gha` and `ai-config` had moved, so a find-and-replace would have broken `macros`, `altdoc`, `snapr`, `stats-allowlist`, `diffviewer`, `equation-anchors`, and `rme`. Note the bare `d-morrison` *username* (a `reviewer:` input, author metadata) is unaffected by a repo/org rename and must not be swept along. The Actions-side consequences of the same rename are in `github-actions.md` ("A repo/org rename breaks Actions `uses:` refs"). (2026-07-28.)
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
  - Prefer match-boundary splitting over lookahead section delimiters (see "## Markdown PR Review Parsing & Regex Match-Boundary Splitting

- **Avoid lookahead regexes across markdown finding bodies containing code blocks.**
  Single-line comments in code blocks (`# comment` in Python, Bash, R, Ruby, YAML) start with `# `.
  A lookahead like `\n\#{1,6}[ \t]+` for section headers then treats those code comments as markdown headings, cutting a code-block suggestion off mid-snippet.
  (Morrison-Lab/gha#412, 2026-08-05).
- **Line-anchor the fence pattern when masking code blocks.**
  Mask fenced blocks before location matching with a line-anchored fence (`^[ \t]{0,3}```...`) under `re.MULTILINE`, and match each block's opening and closing fence as a balanced pair.
  Do not span blocks with a single `re.DOTALL` match: an unclosed fence then swallows everything up to a *later* block's closing fence, masking the valid location headers in between.
  (Morrison-Lab/gha#412, 2026-08-05).
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
