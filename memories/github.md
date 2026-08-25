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

The `gh` (GitHub CLI) tool surface lives in [`gh-cli.md`](gh-cli.md).
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

(Measured 2026-08-23 on Morrison-Lab/ai-config#1976, gh in a local Windows
session; the REST PATCH succeeded immediately on the same body file.)

## `gh pr update-branch` creates a merge commit and triggers CI

When a PR is out of date with the base branch,
`gh pr update-branch <PR>` is a convenient way to merge the base branch into the PR.
It avoids manually checking it out and running git merge or rebase.

However, note that this action creates a new merge commit on the PR branch.
This will trigger any CI pipelines or automated review workflows that run on push.
You must wait for those new runs to pass before the PR is fully clean again.

(Measured 2026-08-25 via `gh pr update-branch --help`)
