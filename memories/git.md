# Git

## Git tags (force-move / slide)
- To move a tag to a new commit: `git tag -d <tag> && git tag <tag> <target> && git push origin :refs/tags/<tag> && git push origin <tag>`
- Can't use `git push --force origin <tag>` on some GitLab instances (protected tags). The delete+recreate pattern always works.
- `git fetch --tags` silently refuses to update a local tag that already exists if the remote moved it. Use `git fetch --tags --force` to get the latest remote tag positions. Without `--force`, you'll see stale local tags and draw wrong conclusions about what the tag includes.

## Resolving a tag to a COMMIT sha (e.g. to SHA-pin a GitHub Action)

- **`git ls-remote --refs` is the wrong tool for this, and fails silently.**
  The `--refs` flag filters out *peeled* (`^{}`) entries.
  For a **lightweight** tag that is harmless --- the one line printed is the
  commit.
  For an **annotated** tag, the only line left is the **tag object's** sha,
  and nothing in the output says so.
  Pin that and GitHub Actions rejects it (`uses:` needs a commit), or worse,
  a tool silently resolves something you did not intend.
- Ask for **both exact refspecs**, and take the `^{}` line when there is one:
  ```bash
  git ls-remote https://github.com/<owner>/<repo> 'refs/tags/<tag>' 'refs/tags/<tag>^{}'
  # lightweight -> one line:  <commit-sha>  refs/tags/<tag>
  # annotated   -> two lines: <tag-obj-sha> refs/tags/<tag>
  #                           <commit-sha>  refs/tags/<tag>^{}   <- the one you want
  ```
  Don't reach for a `'refs/tags/<tag>*'` glob instead: `*` matches any suffix,
  so looking up `v0.0.1` in a repo that also has `v0.0.10`--`v0.0.18` returns
  nine unrelated tags and the two-line rule above stops meaning anything.
  The exact pair has no such failure mode --- a tag name and its own peeled
  form are the only two refs it can ever match.
- Real demonstration of the gap, on `git/git`'s annotated `v2.9.5`:
  ```
  $ git ls-remote https://github.com/git/git 'refs/tags/v2.9.5' 'refs/tags/v2.9.5^{}'
  dcba104ffdcf2f27bc5058d8321e7a6c2fe8f27e  refs/tags/v2.9.5
  4d4165b80d6b91a255e2847583bd4df98b5d54e1  refs/tags/v2.9.5^{}

  $ git ls-remote --refs https://github.com/git/git 'refs/tags/v2.9.5'
  dcba104ffdcf2f27bc5058d8321e7a6c2fe8f27e  refs/tags/v2.9.5
  ```
  `--refs` returns `dcba104` --- the **tag object** --- as its only line, with
  nothing marking it as such.
  The commit is `4d4165b`.
- **Don't infer the object type from the ref listing --- ask git.** Fetch the
  object into a throwaway repo and check it directly, which works even when
  `gh` is absent and `api.github.com` is blocked by a sandbox proxy:
  ```bash
  cd "$(mktemp -d)" && git init -q .
  git remote add o https://github.com/<owner>/<repo>
  git fetch -q --depth 1 o <sha>
  git cat-file -t <sha>          # want: commit   (a `tag` here means you peeled wrong)
  ```
- **The commit sha is only half of a pin --- the trailing version comment is a
  claim too, and the tag you looked up does not tell you what to write.**
  Pinning `actions/checkout@v4` and commenting `# v4` restates the input and
  tells a reader nothing.
  The comment earns its place by naming the release the pin actually sits on,
  which means finding every tag that points at the same commit:
  ```bash
  git ls-remote --tags https://github.com/<owner>/<repo> |
    awk -v s="<commit-sha>" '$1==s {sub(/\^[{][}]$/,"",$2); print $2}'
  ```
  The major tag, any minor alias, and the exact release all come back together,
  so the most specific one is visible rather than guessed at.
  Two details in that one-liner, both load-bearing.
  The `sub()` is needed because an **annotated** tag's line matching the commit
  is the peeled one, so `$2` arrives as `refs/tags/v2.9.5^{}` and reading the
  version straight off it writes a comment with a `^{}` glued to the end.
  And the suffix has to be matched as `\^[{][}]` rather than `\^{}`: mawk,
  which is `awk` on Debian and Ubuntu, parses a bare `{}` as an interval
  expression and dies with `regular expression compile failed (bad interval
  expression)` --- bracketing each brace makes it a literal in every awk.
  Guessing is the failure worth naming: a version comment is a factual claim
  sitting next to an opaque sha, so a wrong one is both undetectable at a
  glance and exactly what a later reader will trust.
  (d-morrison/altdoc#65, 2026-07-26: `quarto-dev/quarto-actions@v2` resolved to
  a commit carrying `v2`, `v2.2`, and `v2.2.0` --- only `# v2.2.0` was worth
  writing, and no amount of reasoning about the `@v2` in the workflow would
  have produced it.)
- This is an [`algorithmatize-checks`](../shared/workflow/algorithmatize-checks.md)
  case: two commands decide it exactly, so never write a pin from recollection
  or from a ref listing you did not check the peel state of.
  (d-morrison/altdoc#57, 2026-07-25: SHA-pinning `etiennebacher/setup-jarl`.
  The tag was lightweight so `--refs` happened to give the right answer --- the
  trap only bites on annotated tags, which is exactly why it is worth checking
  every time rather than when something looks off.)

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
- **The same suppression bites outside worktrees, on ref manipulation
  generally: never `2>/dev/null` a git command that moves a branch ref.**
  `git branch -f main origin/main` is the right way to realign `main` when
  it is *not* checked out (per `CLAUDE.md`'s "Keep ai-config and repo
  checkouts fresh"), but git refuses it outright when `main` **is** the
  current branch ("cannot force update the branch checked out at ...").
  That refusal is the signal; a `2>/dev/null` on it, or burying it mid-chain
  in a `;`-separated compound whose later commands still succeed, throws the
  signal away and leaves you on a stale base with everything reporting
  success.
  The staleness then surfaces somewhere unrelated and much later:
  a diff-scoped CI check reporting a phantom hit in a file you never
  touched, because the base ref, not the file, was wrong.
  Run ref-moving commands unsuppressed and read their output;
  when `main` is checked out,
  use `git pull --ff-only` (or `git checkout --detach` first) instead of
  `git branch -f`. (ai-config#691: `git branch -f main origin/main` was
  refused this way while `main` was checked out -- the error suppressed, the
  ref left untouched -- leaving the branch two commits
  behind; caught only when `scripts/check-new-line-breaks.py` flagged a line
  in `memories/tools.md` that the working tree did not contain.)
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

## Git merge --- editing away the conflict markers is not resolving the conflict
- Rewriting a conflicted file to remove `<<<<<<<`/`=======`/`>>>>>>>` leaves it
  at `UU` in `git status` until you `git add` it.
  The merge stays in progress, and a `git commit` that names other paths, or a
  later `git status` glanced at for a different reason, will not necessarily
  make that obvious.
- Grepping the tree for leftover conflict markers is therefore **not** a check
  that the merge is done: the markers being gone is exactly the state this
  failure mode produces.
  `git status --short | grep '^UU'` (or `git diff --name-only --diff-filter=U`)
  is the check that actually decides it.
- A test run started at this point is still **valid** --- `git add` does not
  change working-tree content, so the suite reads the correctly-resolved file.
  Don't discard a run's results on this basis; the problem is with the commit,
  not the run.
- (`d-morrison/altdoc#61`, 2026-07-25: a `NEWS.md` conflict was resolved in the
  editor and left unstaged; caught only because `git status` was checked for an
  unrelated reason before pushing.)

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

**This is not only a subagent-scale failure --- it bites a single session
running one check by hand, and the ai-config corpus's own
`check-new-line-breaks` is one of these.**
Its script runs `git diff --unified=0 <base_ref>...HEAD`, so a working tree
full of uncommitted edits is invisible to it: on `main` with changes not yet
committed, `HEAD` *is* `origin/main`, the diff is empty, and it prints
`No lines missing semantic breaks.`
That message is indistinguishable from a genuine pass, and it is especially
seductive here because the check is *also* advisory (it warns and exits 0 ---
see [`semantic-line-breaks`](../shared/writing/semantic-line-breaks.md)), so
neither its exit code nor its output gives the game away.
The habit that actually works: `git checkout -b`, `git add`, `git commit`,
**then** run the diff-scoped checks, and only then push.
(ai-config#730 and #732, 2026-07-25, in the same session: both ran the check
against an uncommitted tree, both got a false clean, and both had the real
violations found afterward --- #730's by the check itself once the first
commit existed, #732's by a reviewer.
The second time is what makes this worth recording, since the entry above
already existed and was not applied.)

## Picking the diff range when self-checking a PR: `..` vs `...` vs the working tree

Three forms answer three different questions, and reaching for the wrong one
produces a confident, wrong read of your own PR.

- `git diff origin/main..HEAD` (two dots) compares the two **tips**.
  When your branch is behind `main`, main's newer commits show up as
  **deletions** -- files your PR never touched look removed by it.
- `git diff origin/main...HEAD` (three dots) compares against the **merge
  base**, which is the PR's actual diff and what GitHub shows.
  Use this to reason about what the PR changes.
- `git diff origin/main` (no second ref) compares the **working tree**, so it
  includes uncommitted edits; both `..` and `...` see only committed work.

Both mistakes hit the same session (gha#318, 2026-07-26).
The two-dot form made #317's changelog fragment -- merged to `main` after the
branch was cut -- appear deleted by the PR, and it was nearly reported to the
user as a finding before `...` showed the real four-file diff.
Later, a non-ASCII/em-dash self-check run as `git diff origin/main...HEAD |
grep` printed clean while the em-dashes sat uncommitted in the working tree;
`git diff origin/main` found them immediately.

That second failure is the by-hand instance of the diff-scoped-no-op section
above, with a second fix available: when the edits are deliberately still
uncommitted, use the worktree-comparing `git diff origin/main` rather than
committing first just to make a check see them.
After you merge `main` into the branch, the merge base becomes `origin/main`
and all three forms agree on committed content -- which is exactly when it is
easiest to stop thinking about the distinction and get bitten by the next
stale-branch case.
