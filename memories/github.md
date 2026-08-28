# GitHub PR/issue queue management

The `gh` CLI itself: [`gh-cli.md`](gh-cli.md).
Remote/web MCP tools: [`github-mcp-tools.md`](github-mcp-tools.md).
Remote/web bash access:
[`github-remote-sessions.md`](github-remote-sessions.md).
Owner transfers: [`github-repo-transfers.md`](github-repo-transfers.md).
Closing-keyword parser traps:
[`github-closing-keywords.md`](github-closing-keywords.md).
GitLab CLI and Discussions API: [`gitlab.md`](gitlab.md).
Consumer-side CI, App installs, and moving-tag pins:
[`github-consumer-ci.md`](github-consumer-ci.md).

## Operational checklist pattern for write actions

- **Preflight gate:** verify target branch/repo and whether the action should update an existing PR versus create a new one.
- **Safe command form:** when content includes markdown/backticks, write to a temp file and pass `--body-file` or `-F "body=@<file>"`; avoid inline double-quoted body args.
- **Postcondition gate:** after push/post/create, query GitHub state in the intended base repo (for PRs, include both repo and head owner) and confirm the intended object actually exists/updated. `gh pr list --head <owner>:<branch>` silently returns empty for an owner-qualified head even when a matching PR exists — verified directly against a real open PR (`gh pr list --head the repository owner:ums-pr635-lessons` returned `[]`; the bare `--head ums-pr635-lessons` found it). Use the REST API instead, with the branch passed as a `-f` GET field rather than interpolated into the raw URL — a branch name containing `#`, `&`, or `+` breaks a hand-built query string but is passed through correctly as a field: `gh api --method GET "repos/<upstream-owner>/<repo>/pulls" -f "head=<head-owner>:<branch>" -f "state=open" --jq '.[] | {number, url, state}'`.
- **Failure signature:** stderr like `command not found` during a `gh`/`glab ... --body` call can mean two different things — check which first, probing whichever CLI actually failed (`which gh` or `which glab`, not always `gh`): if `gh` itself is unavailable (expected in remote/web sessions), fall back to the mapped MCP tool instead of retrying the CLI — `tool-mappings.yml` has no `glab` operations, so a missing `glab` has no MCP fallback; hand off or block instead. If the CLI that failed is present, the likely cause is shell-expanded backticks mangling the body — re-run using a file-backed body.

## gh (GitHub CLI)

Moved to [`gh-cli.md`](gh-cli.md).

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

Moved to [`gitlab.md`](gitlab.md) with the `glab` section.

## glab (GitLab CLI)

Moved to [`gitlab.md`](gitlab.md) with the Discussions API section.

## GitHub access from bash in remote/web sessions

Moved to [`github-remote-sessions.md`](github-remote-sessions.md).
Kept here as a heading stub so inbound citations of this title still resolve.

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

Moved to [`github-consumer-ci.md`](github-consumer-ci.md).

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

Moved to [`claude-bot-workflows.md`](claude-bot-workflows.md),
which owns `claude-code-action` runtime behaviour.

## Verify GitHub App installation per repository

Moved to [`github-consumer-ci.md`](github-consumer-ci.md).
Kept here as a heading stub so inbound citations of this title still resolve.

## A moving upstream tag can turn a consumer's default branch red with no local change

Moved to [`github-consumer-ci.md`](github-consumer-ci.md).
Kept here as a heading stub so inbound citations of this title still resolve.

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

## `gh pr merge` "not up to date with the base branch" does not fire consistently on an equally-stale PR

Observed 2026-08-27 (PT) on Morrison-Lab/ai-config: `gh pr merge` refused PR #2470 with "not up to date with the base branch" after `main` had advanced by several merges past its branch point, but succeeded minutes later on PR #2480, which was also behind `main` by one freshly-merged commit.
Updating #2470's branch via `gh api -X PUT repos/<owner>/<repo>/pulls/<N>/update-branch` and getting one clean re-review cleared the block.

The discriminator between the two cases is not established --- do not assume "several commits behind" is the trigger, since #2480 also merged while behind.
It may be required-check staleness (a status check keyed to an older base SHA) rather than a strict branch-parity requirement, but this is unverified.
[`gh-cli.md`](gh-cli.md)'s "Strict branch protection makes a clean PR queue merge serially" section, measured the same day in this same repo, is a plausible but unconfirmed explanation: under `required_status_checks.strict: true`, only whichever PR is next in the merge queue --- freshly updated against the current base --- merges immediately, while every other PR reads `BEHIND` again before its own turn even at a comparably small remove.
That would fit #2480 succeeding (next in queue, just updated) against #2470 refusing (not yet updated) without needing a second mechanism, but this session did not verify the actual update order or confirm strict mode was the active setting, so it stays a candidate explanation rather than an established one.

- **Do:** when `gh pr merge` refuses with "not up to date with the base branch," update the branch via the `update-branch` REST endpoint and get one fresh clean review before retrying, per `gh-cli.md`'s serial-queue section.
- **Don't:** assume every PR behind `main` by any amount will hit this refusal --- it did not reproduce on a comparably stale PR the same day.
- **Don't:** assume the queue-ordering explanation above is confirmed --- it fits the observation but was not independently verified.
