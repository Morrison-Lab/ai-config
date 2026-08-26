# Git

## Git tags

See [`git-tags.md`](git-tags.md) for tag management (force-moving/sliding tags and resolving tags to commit SHAs).

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
- Do NOT "harden" it to `git switch -C -- "$BRANCH"` — that form is **broken**:
  the `--` is consumed as the branch name (the required argument to `-C`), so `$BRANCH` is parsed as the start-point instead and the command fails without creating the branch.
  (Verified on git 2.x; a review bot suggested the broken form on Morrison-Lab/gha#58.)

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
- **Both halves of that mitigation are narrower than they read: the trigger is
  wrong, and the remedy does not work in a repo that auto-deletes.**
  The check
  is gated on `--delete-branch`, so a plain squash merge fires none of it and
  orphans the dependent anyway --- the merge base stays put, and the dependent
  re-shows the merged content as a conflict.
  And omitting the flag buys nothing
  where the repo deletes merged head branches on its own, since the branch goes
  away whatever you passed (measured on `Morrison-Lab/ai-config`, 2026-08-16:
  five of five recently merged head branches were absent from `git ls-remote
  --heads origin`, the sixth surviving only because an open PR still used it).
  So run the base query before **any** merge.
  [`shared/workflow/batch-merge-and-resolve.md`](../shared/workflow/batch-merge-and-resolve.md)'s
  "A stacked PR is the one conflict that intersection cannot attribute" section
  carries the derivation and the attribution rule.
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
- (`Morrison-Lab/altdoc#61`, 2026-07-25: a `NEWS.md` conflict was resolved in the
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
reviewed, "Ready for merge" PR (`Morrison-Lab/gha`-reviewed
`Lacaedemon/sparta` PR #634, 2026-07-03) and then break the `demo` CI job on
every *other* open PR that subsequently merged `main` in. When a PR adds a new
executable script (a `tools/ci/*.sh` invoked directly, not sourced), verify
its committed mode explicitly (`git ls-tree HEAD -- <path>`, compare against
an existing sibling script) rather than trusting the code review alone to
catch it.

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

## `git checkout <branch> 2>/dev/null; <next>` silently continues on the wrong branch

`git checkout` is a **state-changing** command whose only report of failure is
its stderr and its exit status.
Redirect the first and separate with `;` rather than `&&`, and both signals are
discarded:

```bash
git checkout main -q 2>/dev/null; git pull --ff-only -q     # WRONG
```

When the checkout fails --- most commonly because another session left
uncommitted changes that would be overwritten --- nothing is printed, nothing
stops, and every subsequent command in the session runs against whatever branch
was already checked out.
The failure mode is not a wrong read but a wrong **write**: later edits, and
potentially a commit, land on somebody else's branch.

Two things make this worse than an ordinary swallowed error.
The `-q` flag suppresses the success message too, so the silent-failure case
and the silent-success case produce byte-identical output --- which is
[`fail-fast`](../shared/principles/fail-fast.md)'s pass-path-equals-failure-path
shape exactly.
And the natural next command is often `git pull`, which succeeds on the wrong
branch and prints something reassuring.

```bash
git checkout main -q && git pull --ff-only -q               # RIGHT
```

- **Do:** join a checkout to what follows with `&&`, so a failed checkout stops
  the sequence.
- **Do:** let `git checkout`'s stderr through; its message names the blocking
  file directly.
- **Do:** re-read `git rev-parse --abbrev-ref HEAD` before editing, when a
  checkout was not verified.
- **Don't:** redirect stderr on any state-changing git command --- the
  distinction from a read-only one is that a swallowed failure here leaves you
  writing to the wrong place.
- **Don't:** rely on `-q` plus a `;` chain and assume a later command's success
  says anything about the checkout.

(Morrison-Lab/ai-config, 2026-08-19: a session ran the WRONG form above against
the shared primary checkout, which another session had left on
`fix/quote-yaml-placeholders` with uncommitted work.
The checkout failed with `Your local changes ... would be overwritten`, the
redirect hid it, and a 49-line memory edit was written to that session's
working tree.
It was caught only when a later `git checkout -b` printed `Aborting` with
stderr unredirected, and reverted with `git checkout -- <file>` after
confirming the diff was a single hunk containing nothing of theirs.
The standing rule against touching the primary checkout from a worktree
session is in [`preferences.md`](preferences.md); this entry is about why the
violation produced no error message.)

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

## `git commit -m "..."` runs backtick spans as shell commands

A commit message passed through a double-quoted `-m` goes through the shell
first, so any backtick span inside it is command substitution: the shell
*runs* the backticked text and drops it from the message.
``git commit -m "fix the `slast` guard"`` commits `fix the  guard` --- the
`slast` span is gone, and whatever running `slast` printed (usually nothing,
often an error to stderr) is spliced in where it stood.
Nothing errors on the commit itself, and the corrupted message is what lands in
history.

This is the bash counterpart of `CLAUDE.md`'s "PowerShell CLI Command Safety"
backtick warning, by a different mechanism: PowerShell treats the backtick as
an escape character, bash treats it as command substitution.
The remedy is the same either way.
Use `git commit -F <file>` with a body file, or a single-quoted `-m '...'`,
whenever the message carries backticks --- Markdown code spans, identifiers,
paths.
(Morrison-Lab/ai-config#1042, 2026-08-03: a `-m` commit message lost its
backtick spans this way; the message landed at `97bf7d4` with the spans
executed and deleted.)

## `gh pr comment` / `gh api ... -f body="..."` run backtick spans too

The identical bash mechanism corrupts any `gh` command that takes a body
through a double-quoted argument, not just `git commit -m`.
`gh pr comment <N> --body "..."`, `gh issue comment`, and
`gh api .../comments -f body="..."` / `.../replies -f body="..."` pass the body
through the shell first, so a backtick span is command substitution: the shell
runs the backticked text and splices its output (usually nothing) where the
span stood, and the corrupted comment lands on someone else's thread reading as
though you wrote it that way.

The remedy is `CLAUDE.md`'s "Use body files" rule, extended past PR
descriptions and past PowerShell: write the body to a file and pass
`--body-file <file>` (`gh pr comment`, `gh issue comment`) or `-F body=@<file>`
(`gh api`), for comment and review-reply bodies too, in any shell.

- **Do:** pass a backtick-carrying comment or review-reply body through
  `--body-file` / `-F body=@<file>`, exactly as for a PR description.
- **Don't:** inline a double-quoted `--body "..."` / `-f body="..."` that
  contains a code span or identifier --- bash runs it as a command and drops it.

(Morrison-Lab/gha#425, 2026-08-05: a `gh api .../replies -f body="..."` review
reply carried a `ms.` code span; the posted comment ran that span as a command
and dropped it, so the thread lost the identifier entirely.)

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
- **`stale info` after `checkout -B` usually means the remote branch was
  DELETED, not moved -- and then a plain push is the correct fix, not a bigger
  hammer.**
  The bullet above says the remote-tracking ref can be stale; this is the
  specific cause that recurs on this repo's normal flow, since a squash-merge
  with auto-delete-on-merge removes the branch while your ref still names its
  old tip.
  `--force-with-lease` then fails for a reason that reads alarmingly like a
  race with another session:

  ```
  ! [rejected]  HEAD -> claude/... (stale info)
  ```

  The lease is unsatisfiable rather than violated, because the ref it names no
  longer exists.
  So the reflex it invites -- reach for `--force`, or assume someone else
  pushed -- is wrong in both directions: `--force` is unnecessary, and there is
  nothing to race.
  Settle which case it is before pushing anything:

  ```sh
  git ls-remote --heads origin <branch>   # empty output = deleted
  ```

  Empty means the next push *creates* the branch, so it can destroy nothing and
  needs no lease at all.
  `git fetch --prune` followed by a retry works for the same reason, and is
  worth preferring when you want the remote-tracking ref corrected too.
  Non-empty means a real concurrent session pushed to the remote branch; settle
  claims and inspect commits before forcing.

  - **Do:** run `git ls-remote --heads origin <branch>` when a lease push
    reports `stale info`, and plain-push (or `git fetch --prune` + push) when it comes back empty.
  - **Don't:** escalate to `--force`, or suspect a parallel session, before
    checking whether the branch still exists.

  (Morrison-Lab/ai-config#857 -> #872, 2026-07-30: #857 squash-merged and its
  head branch was auto-deleted.
  Restarting the same harness-assigned branch name from the new `main` and
  pushing the follow-up work produced `stale info`; `ls-remote` returned
  nothing, and the plain push reported `* [new branch]`.)

## `git push origin <name>` pushes the LOCAL BRANCH of that name, not HEAD

`git push origin <refspec>` takes a *ref*, not a label for "what I am working
on".
So in a checkout that has both the PR's branch checked out and a leftover
local branch named after something else --- the harness-assigned
`claude/...` name, say --- running `git push -u origin claude/...` pushes
**that other branch**, wherever it happens to point, and leaves the current
work unpushed.

The failure is quiet in the direction that matters.
The push succeeds, `git log` still shows the commits, and the only complaint
is from whatever check later notices the PR did not move.
The `-u` compounds it by repointing the *other* branch's upstream, so a
subsequent bare `git push` is now aimed somewhere new.

The tell is `* [new branch]` in the push output, and this is a **second
cause** for that line, distinct from the one in `CLAUDE.md`'s "Use the
existing PR branch" section.
There it means the remote branch was deleted underneath you, which on a PR
branch means the PR merged.
Here it means the ref you named had no remote counterpart because it was
never the branch you were working on.
Both warrant stopping, and they are told apart by which name is on the line:
if it is not the branch you have been pushing all along, you pushed the
wrong ref.

Recovery is cheap when caught immediately --- push the real branch, then
clean up the stray remote ref (`git merge-base --is-ancestor <stray-tip>
origin/main` first, to confirm it carries nothing unmerged; note that
deletion no-ops under the remote push proxy, per the section below).

- **Do:** push with no refspec (`git push`) once upstream is set, or name the
  branch you confirmed with `git branch --show-current`.
- **Do:** read the push output for `* [new branch]` versus a `SHA..SHA`
  range, and stop on the former.
- **Don't:** paste a branch name from the harness's instructions into
  `git push` without checking it is the branch you are on.
- **Don't:** read a zero exit status as evidence the right commits went out.

(Morrison-Lab/gha#357, 2026-07-29: `git push -u origin
claude/gha-pr-357-review-of6k4h` while on `add-gemini-and-ai-review-workflows`
created a stray remote branch at an already-merged commit and pushed none of
the round's four commits.
Caught by the `* [new branch]` line, since the PR branch had been pushed
several times already.)

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
twice; delegated to the repository owner in the issue-close comment.)

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

**Green on the push event is not green on the pull_request event, for a diff-scoped checker --- the two triggers diff different bases.**
Same commit, ai-config#2074, 2026-08-24: the push-event `new-line-breaks / check-new-line-breaks` run passed on three consecutive heads while the pull_request-event run failed each time, because that run diffs lines added since the merge-base, which is the set the PR is actually judged on.
Judge a branch by its pull_request-event runs.
A green push-event run of the same check name proves nothing about the PR verdict.

## Picking the diff range: `..` vs `...` vs the working tree

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

**A reviewer can make this mistake against your PR, and the finding it
produces is far more convincing than the self-check version above.**
The cases above are you misreading your own diff, where the fix is just to
rerun the command.
Here someone else runs `git diff --stat origin/main HEAD` and reports, in
detail, that your branch deletes files you never touched.
Three things make it hard to dismiss.
It arrives itemized, as a table of real paths with real line counts, because
every one of those files genuinely does differ between the two tips.
It is internally consistent, so a count or an index that moved in the same
upstream commit corroborates the "deletions" and reads as deliberate intent.
And it invites a destructive repair: reverting those files from your branch
would actually revert whatever merged to `main` while your PR was open.

Check the base before believing the finding, and answer with the merge-base
diff rather than by arguing.
GitHub's own Changed Files panel is the tell, since it always diffs the merge
base, so a reviewer's file list that disagrees with the panel is a diff-range
artifact until shown otherwise rather than a defect in your branch.
Merging `main` in makes the two agree, which lets the rebuttal end with the
reviewer's own command reproducing the panel's numbers.
(ai-config#765, 2026-07-28: a review reported 20 changed files and 822
deletions against a 7-file PR, listed three skills, three Codex wrappers, a
shared fragment and four memory files as deleted, and asked whether to revert
them.
All of it was four commits that reached `main` after the branch was cut.
`skills.qmd`'s count reading `171+` against main's `175+` was the
corroborating detail, and it had moved in the same commit that added the
skills.
The next review round retracted the finding once `main` was merged in.)

## A `git diff` self-check is blind to untracked files, whatever range you pick

The section above chooses between `..`, `...`, and the bare worktree form.
None of the three sees a file git is not tracking yet.
So a self-check driven by `git diff` skips a PR's brand-new file entirely, and a new file is usually the one carrying the most unreviewed added lines.
`git add -N <path>` (or a plain `git add`) is what makes it visible;
`git status --short` marks with `??` exactly what a diff-based check is currently ignoring.

The failure runs in the direction that reads as a pass, so print a count of what the check examined rather than only its hits, per [`fail-fast`](../shared/principles/fail-fast.md)'s by-hand-check rule.
A scan reporting `0 banned-punctuation hits` looks identical whether it read the whole diff or nothing at all.
(ai-config#760, 2026-07-28: a pre-push scan for banned punctuation and multi-sentence lines printed `examined 11 added lines, 0 hits` on a PR whose new fragment ran to 85 lines.
The count was the only thing that gave it away;
staging first and re-running scanned all 85.)

## An untracked copy sitting where a tracked file lives on another branch runs instead of it

The entry above is about a check that cannot **see** an untracked file.
This is the inverse and the worse half: an untracked file you cannot help but
**run**.
A scratch copy of a script, left at the same relative path as the tracked
version that lives on some other branch, is what `./scripts/<name>.sh`
resolves to.
The inputs are fine, the invocation is right, and the binary is wrong.

Nothing at the call site distinguishes them.
Same path, same name, executable, plausible output.
`git status --short` marks it `??`, but an untracked file among a working
tree's other untracked files is unremarkable, and the checkout around it is
fresh --- which is what makes this harder to spot than an ordinary stale
checkout, where at least everything is stale together.

The failure is also **self-confirming**, not merely silent.
A stale copy's already-fixed bug presents as a genuine finding, so the wrong
binary generates apparently productive work: a diagnosis, a fix, a test.
A wrong *artifact* would eventually contradict something; this produces a
correct fix to a problem that no longer exists, and every step after the first
looks like progress.

One command settles it before you trust any behaviour you observed:

```bash
git ls-files --error-unmatch scripts/<name>.sh    # exit 0 = tracked here
```

Non-zero on a path you expected to be tracked is the tell.
Then ask the second question, which the first does not answer: **is this branch
the one that owns the file?**
A path untracked on `main` and tracked on a feature branch is exactly the
shape, so check the owning PR's copy before concluding anything about the
script's behaviour --- and diff the two rather than assuming yours is behind
only where you noticed.

`ucdavis/bcs`'s own `CLAUDE.md` already leans on this command for a different
purpose (deciding whether a path under `inst/extdata/` is restricted data), so
it is a cheap habit with two payoffs rather than a new one.

- **Do:** run `git ls-files --error-unmatch <path>` before treating a script's
  behaviour as the artifact's behaviour.
- **Do:** compare against the copy on the branch that owns the file, and read
  its version before writing a fix.
- **Don't:** read a fresh checkout as evidence that every file in it is the
  tracked one.
- **Don't:** trust a bug you found by running a script until you have confirmed
  which copy ran --- an already-fixed bug reads exactly like a new one.

(`ucdavis/bcs#530`, 2026-07-31: `scripts/resolve-version-conflict.sh` lives on
that PR's branch, and an untracked copy of an earlier revision sat at the same
path in the main checkout, where `git status` showed it as `??`.
Running it exercised the stale copy, whose final "still unmerged elsewhere"
guard counted the file it had just resolved --- it never staged it --- so it
exited 1 on its own success path.
That bug was diagnosed correctly, fixed, and tested in both directions, all of
it redundant: #530's copy already fixed it, and additionally guards on
`git rev-parse --is-inside-work-tree`, where the independently-written fix would
have aborted under `set -e` outside a work tree.
Running the same three-case fixture against #530's copy gave exit 0 on the
handled case, exit 1 naming the genuine second conflict, and exit 0 outside a
work tree.)

## A pattern resolved by `git ls-files` is a pathspec, not a shell glob -- `*.md` is recursive and `**/*.md` drops root-level files

Any tool that selects files by handing a pattern to `git ls-files -- <pattern>`
takes a **git pathspec**, and git's pathspec matching differs from shell and
globby matching in one load-bearing way: `*` matches `/` too.

The consequences invert the usual intuition:

- `*.md` matches at **any depth**, root-level files included.
  It is already recursive.
- `**/*.md` requires **at least one `/`**, so it matches nothing at the repo
  root.

Measured on `ucdavis/bcs`:

```console
$ git ls-files -- '*.md' | wc -l
28
$ git ls-files -- '**/*.md' | wc -l
23
$ git ls-files -- '**/*.md' | grep -v /     # any root-level hits?
```

The third command prints nothing at all: `**/*.md` matches no root-level file.
The five it loses are `NEWS.md`, `README.md`, `CLAUDE.md`, `AGENTS.md`, and
`LICENSE.md` -- in most repos, the ones that matter most.

**Why this is worth a section rather than a footnote: the wrong form fails
silently.** `*.md` reads as non-recursive to anyone carrying shell intuition,
so "correcting" it to `**/*.md` looks like a straightforward fix.
Nothing turns red when it lands.
The linter still runs, still reports success, and still prints a file count --
just a smaller one -- so the repo's most important files stop being checked
with no signal that anything changed.

**The rule is "know which matcher you are feeding", not "never write
`**/*.md`".**
The same pattern behaves oppositely in the two engines, so a blanket ban would
break the globby-based configs it does not apply to.
Two files, one at the root and one nested, in the same repo:

```console
$ npx markdownlint-cli2 '**/*.md'      # globby
Linting: 2 file(s)

$ git ls-files -- '**/*.md'            # git pathspec
sub/nested.md

$ git ls-files -- '*.md'               # git pathspec
root.md
sub/nested.md
```

Globby's `**/*.md` finds both files; the identical pathspec finds only the
nested one, and `*.md` is the pathspec that matches what globby matched.

This corpus relies on both conventions at once, correctly: its own
`.markdownlint-cli2.jsonc` sets `"globs": ["**/*.md"]`, which is right because
`markdownlint-cli2` resolves globs with globby, while a gha workflow input
consumed by `git ls-files` needs `*.md` for the same coverage.

**Settle it by measuring, not by reasoning about glob semantics.**
Both forms through `git ls-files`, compare the counts, and look specifically
for root-level hits with `grep -v /`.
One command decides it, which is the
[`algorithmatize-checks`](../shared/workflow/algorithmatize-checks.md) rule
applied to a question that otherwise invites a confident wrong answer.

This is not specific to one repo.
`Morrison-Lab/gha`'s `lint-markdown` and `lint-yaml` both resolve their `globs`
input this way (`_pathspec.mjs` / `_pathspec.py`, `trackedFiles()`) and
document it as "git pathspecs ... recursive by default", so every consuming
repo inherits the same trap.

(`ucdavis/bcs#445`, 2026-07-27: a review of the PR wiring `lint-markdown`
suggested changing `globs: '*.md'` to `'**/*.md'` "for recursive matching",
reasoning correctly from globby semantics and incorrectly assuming they
applied here.
Running both forms before replying is what caught it; applying the suggestion
would have silently un-gated all five root-level files, including the
`NEWS.md` whose merge-splice defect motivated the PR.)

## Citing evidence that lives in a PR's own superseded commits

When durable guidance (a `CLAUDE.md` rule, a memory entry, a doc) cites a real
incident as its worked example, ask where a later reader would go to check it.
An incident that happened on an **earlier commit of the very PR adding the
guidance** is the hard case: it is real, and it is invisible to every obvious
probe.

A reviewer checking `git show HEAD:<file>` finds nothing, because the later
commit fixed the thing away.
A reviewer checking the *linked prior PR* -- the one the guidance is about --
finds nothing either, because the incident was never there.
Both probes are reasonable, and both come back empty, so a true claim reads as
fabricated.

Cite the SHA, so the claim is reachable rather than merely true.
Naming the commit (and, where it exists, the CI job id) converts an
unverifiable anecdote into something a reader can run `git show` against.

**Whether that citation survives the merge depends on the repo's merge
strategy, so check it before relying on a branch SHA.**
A repo that creates real merge commits keeps the PR's individual commits as
ancestors of `main`, so the short SHA stays reachable forever.
A repo that **squash-merges** does not: the branch commits never become
ancestors, and a cited SHA goes dead the moment the branch is deleted.
**And you cannot read a repo's strategy off one merge, so never cite a branch
SHA on the strength of what the last PR looked like.**
GitHub lets a repository enable merge, squash, and rebase simultaneously, so
the strategy is chosen per pull request by whoever clicks the button.
`ucdavis/bcs` demonstrates it inside one afternoon:

```
$ for c in b8ee355 2daed4c eead1e0; do git show -s --format='%p %s' $c; done
9787b57                  docs: record the Spellcheck house-style rule (#456)   <- 1 parent, squashed
eead1e0 52d28e8          Merge pull request #453 from ucdavis/fix/repoint...   <- 2 parents, merged
c10ed45                  fix: exclude artifact outputs from provenance (#449)  <- 1 parent, squashed
```

So the safe default is to cite what survives **every** strategy: the PR or
issue number, a permalink to the file at a merged commit, or the CI job URL.
Reach for a branch SHA only when the merge has already happened and you have
checked that specific commit with `git merge-base --is-ancestor`.

That is not a hypothetical.
This entry originally cited `082f369` as a still-reachable example, on the
strength of #453 having merged as a merge commit --- and #456 then
squash-merged, so `git merge-base --is-ancestor 082f369 origin/main` returns
false and the citation died within the hour.
`Morrison-Lab/ai-config` squashed #795 the same way: ancestry false for both
commits, though the *content* was present on `main`.

That same asymmetry is why a post-merge check should verify **content** rather
than ancestry in a squash repo --- `git show origin/main:<path> | grep` answers
the question ancestry cannot.

(ucdavis/bcs#456, 2026-07-28: a review called a `wordlist NEWS.md:3` spellcheck
failure "fabricated rather than drawn from a real incident".
It had happened two commits earlier on that same PR, at `082f369`, and had
already been reworded away.
Rebutted with the commit and the job log, then addressed by naming the SHA in
the guidance itself --- which ucdavis/bcs#457 had to undo an hour later, once
PR #456 squash-merged and that SHA stopped resolving.)

## Cleaning up a branch deleted on `origin` is two mechanisms, and only one is a config

"Prune branches once they are deleted on `origin`" sounds like one setting.
It is two, they live in different places, and only the first is a git config.

**Half 1 --- the remote-tracking ref.**
`fetch.prune=true` (or the per-remote `remote.origin.prune=true`) drops
`refs/remotes/origin/<name>` once that branch is gone upstream, on an
**unscoped** fetch.
A scoped one (`git fetch origin main --prune`) prunes nothing outside its own
refspec, config or no config, so it leaves the ref resolving --- see
[`keep-checkouts-fresh`](../shared/workflow/keep-checkouts-fresh.md).
It never touches a local branch.
Verified on git 2.34.1 (2026-07-29), deleting `feat` from a second clone:

```
=== after fetch.prune=true ===
remote-tracking refs:   origin/master       <- origin/feat pruned
LOCAL branches:         feat  * master      <- feat untouched
```

**Half 2 --- the local branch whose upstream is now `[gone]`.**
Git has no config for this at all, so no setting will ever do it.
It is a procedure, owned by
[`clean-branches`](../skills/clean-branches/SKILL.md) step 8b: find the
`[gone]` branches, confirm the PR actually merged, then delete.
Keep it confirmation-gated --- it is the half that can destroy work.

### Without half 1, half 2 reports a false clean rather than an error

The `[gone]` marker is produced **by pruning**, not by the branch being deleted
upstream.
Until a prune runs, `%(upstream:track)` is empty for exactly the branches the
sweep exists to find, so a `grep '\[gone\]'` matches nothing and the sweep
reports there is nothing to clean:

```
=== plain fetch, no prune ===
feat | origin/feat | track=
=== after fetch.prune=true ===
feat | origin/feat | track=[gone]
```

That is the shape [`fail-fast`](../shared/principles/fail-fast.md) warns about:
the "nothing found" path and the "never ran" path print the same thing.
So a sweep has to *establish* that a prune happened rather than assume it.
Running `git fetch --prune` inside the step is what keeps the config a
convenience rather than a silent prerequisite.

### In a squash-merge repo, local ancestry cannot be the safety signal

The safety rule is "never delete a branch carrying unique local commits", and
the obvious instruments for it all give the wrong answer where the repo
squash-merges.
Verified against a branch whose work had demonstrably landed on `main`:

```
ahead: 1   behind: 1
is feat an ancestor of master?      NO
git branch --merged origin/master   ->  * master        (feat absent)
git branch -d feat                  ->  error: The branch 'feat' is not fully merged.
```

Every one of those says "unmerged" about a branch that merged.
Once the upstream ref itself has been pruned there is no upstream left to
compare against, so `-d` falls back to `HEAD` and refuses.
Read that refusal as *unproven*, not as *unique local work* --- which is why
step 8b confirms the merge through the PR and only then reaches for `-D`.

So the authoritative landed-signal is the PR's own merge state, and the
content check that survives a squash (`git show origin/main:<path>`), not
local ancestry.
`ucdavis/bcs` and `Morrison-Lab/ai-config` both squash-merge.

- **Do:** set `fetch.prune` for the remote-tracking half, and treat the
  local-branch half as a reviewed sweep rather than something a config does.
- **Do:** decide "did this land?" from the PR, in any repo that squash-merges.
- **Don't:** read a `[gone]` sweep that found nothing as a clean result until
  you know a prune actually ran.
- **Don't:** treat `git branch -d` refusing, a non-zero ahead-count, or absence
  from `git branch --merged` as evidence a branch still holds unpushed work.

## `git rev-parse <ref>:<path>` writes its own input to stdout when the path is absent

`git rev-parse` resolves `<ref>:<path>` to a blob SHA.
When that path does not exist in that ref it fails **and still writes to stdout** -- the literal input string, unchanged.
Verified on git 2.34.1, 2026-07-30:

```console
$ git rev-parse origin/main:not/a/real/path; echo "rc=$?"
fatal: path 'not/a/real/path' does not exist in 'origin/main'
origin/main:not/a/real/path
rc=128
$ git rev-parse origin/main:README.md; echo "rc=$?"
939ce89cb74324b1c783fe726a20a1d2b4d9b06b
rc=0
```

The two lines go to different streams, so a capture keeps the echoed input whichever way stderr is handled:

```console
$ out=$(git rev-parse origin/main:not/a/real/path 2>/dev/null); echo "[$out]"
[origin/main:not/a/real/path]
```

A capture that merges stderr with `2>&1`, or that ignores the exit status, therefore comes back non-empty with a value that reads as an ordinary answer.
It is also unequal to every real SHA, which is what makes it worse than an empty result.
A "does this path differ between two refs" check compares two such strings, finds them unequal, and reports **differs** when the true answer was **absent from one side**.
That is the by-hand-check shape [`fail-fast`](../shared/principles/fail-fast.md) describes, where the failure path and the pass path print the same kind of thing.

Test the exit status, or use `git cat-file -e "$ref:$path"`, which writes nothing to stdout at all:

```console
$ out=$(git cat-file -e origin/main:not/a/real/path 2>/dev/null); echo "rc=$? out=[$out]"
rc=128 out=[]
```

- **Do:** read `rc` from `git rev-parse <ref>:<path>`, or switch to `git cat-file -e` when only existence is in question.
- **Do:** treat an output that is not SHA-shaped as "the path was absent" rather than as a difference.
- **Don't:** pipe `git rev-parse <ref>:<path>` through `2>&1` into a comparison.
- **Don't:** compare two `git rev-parse <ref>:<path>` outputs for equality without first establishing that both resolved -- two absent paths echo two different strings, which reads as a difference.

(2026-07-30, a `ucdavis/bcs` branch sweep: a per-path comparison built this way reported that a branch was about to destroy another session's work, and that went out as a blocker.
The paths were absent on one side rather than different, and a real set-difference over the two file lists showed the branch was safe.)

## A hook that names a branch but not a repo may be pointing at a different checkout

A multi-repo session assigns the **same** harness branch name in every
repo it has cloned, so a pre-commit/stop hook reporting
"commit(s) on branch `claude/<slug>`" does not tell you which working tree
it looked at.
It can easily be a repo you only ever *read* from -- and whose branch is
just tracking `main`.

The failure mode is that the remediation the hook suggests is destructive
in that case.
A hook flagging commits as Unverified (committer not
`noreply@anthropic.com`) will suggest
`git rebase --exec "git commit --amend --no-edit --reset-author"`.
Run against a checkout carrying only upstream history, that rewrites
commits nobody in the session authored and **reattributes the repo owner's
own commits to Claude**, for a branch with nothing to push.

Decide it mechanically before touching anything:

```bash
git remote get-url origin              # which repo is this actually?
git merge-base --is-ancestor HEAD origin/main; case $? in
  0) echo "pure upstream history -- nothing local to lose" ;;
  1) echo "HAS local commits -- do not rewrite" ;;
  *) echo "check failed (bad ref?) -- do not rewrite" ;;
esac
git show -s --format='%an <%ae> | %cn <%ce>' <flagged-sha>
```

Two details in that block are deliberate, and both are easy to "helpfully"
undo.

There is **one** liveness check rather than two.
An empty `origin/main..HEAD` range is the same fact as `--is-ancestor`
succeeding, so running both confirms one thing twice rather than two things
once --- see `CLAUDE.md`'s "Run `wrap-up`'s state sweep" section, which
states that rule for the branch-deletion case.

And the exit status is read with a three-arm `case` rather than
`&& echo ... || echo ...`.
`--is-ancestor` exits 2 or higher when a ref has been pruned away, and `&&`
fails on any non-zero status, so the two-arm form reports a confident
"no local work" for a check that never ran --- the
[`fail-fast`](../shared/principles/fail-fast.md) shape where the failure
path and the pass path print the same thing.

A branch that is an **ancestor** of `origin/main` has no local work on it
by definition, so anything flagged there is upstream history and the hook
is a false positive.
Check the author too: an upstream squash-merge commit is typically authored
by the repo owner and committed by `noreply@github.com`, which is exactly
the shape a committer-email check flags.

The root cause is worth fixing rather than re-diagnosing: a non-working
checkout should sit on `main`, not a leftover harness-named branch.
`CLAUDE.md`'s "Keep ai-config and repo checkouts fresh" rule already asks
for this for the ai-config clone specifically; the hook noise is a second
reason it matters.

(2026-07-28: a stop hook flagged 17 "Unverified" commits on
`claude/gha-workflows-review-84aqlu`.
The session's actual work was in `gha`, whose two commits were correctly
`Claude <noreply@anthropic.com>` as both author and committer.
The flagged commits were in the **ai-config** checkout, pulled in minutes
earlier by a routine `git pull --ff-only`, authored by the repo owner.
`git merge-base --is-ancestor HEAD origin/main` returned true, settling it
in one command.)

## A ref pattern is not a pathspec: `*` does NOT cross a slash in `for-each-ref`, but DOES in `ls-files`

The section above establishes that a **pathspec** `*` matches `/` too.
Git's other pattern matcher does the opposite, with identical syntax, so the
intuition you just built is wrong one command over.

`git for-each-ref <pattern>` (and `git branch --list`, and a refspec's left
side) matches with `fnmatch` under `FNM_PATHNAME`, where `*` stops at a slash.
So `refs/remotes/origin/*` matches `origin/main` and misses
`origin/feat/anything`.

Measured together on git 2.34.1, in one repo, same syntax:

```bash
git for-each-ref --format='%(refname:short)' 'refs/remotes/origin/*'    # 8
git for-each-ref --format='%(refname:short)' 'refs/remotes/origin/**'   # 18
git ls-files -- 'skills/*'                                              # 180
git ls-files -- 'skills/**'                                             # 180
```

The ref matcher halves the result; the pathspec matcher cannot tell the two
patterns apart.

**The failure direction is a silent false all-clear, and it is biased toward
the refs that matter.**
Slash-named branches are exactly the conventional ones -- `feat/`, `fix/`,
`docs/`, `claude/` -- so a sweep keyed on the single star quietly omits every
branch anyone named properly, including the ones carrying open PRs, while
reporting a clean run over whatever is left.
Nothing errors and the count looks plausible.

Use `**` for ref patterns, or `git branch -r` / `git branch --list`, which
enumerate without a pattern.
And per [[algorithmatize-checks]], give any ref sweep a control: check that a
known slash-named branch appears in its output before trusting a total.

- **Do:** use `refs/remotes/origin/**` when you mean every remote branch.
- **Do:** confirm a known nested ref is in the result before quoting a count.
- **Don't:** carry pathspec intuition into `for-each-ref` -- the two matchers
  disagree on the one character that decides it.
- **Don't:** read a smaller-than-expected ref count as "this repo is tidy".

(2026-08-02, a `clean-branches` sweep on `Morrison-Lab/ai-config`: the single
star reported 17 of 34 `origin/**` refs and hid all five open PRs' branches.
Caught only because the open-PR column came back empty against a known count of
five.)

## GitHub keeps `refs/pull/N/head` forever, so deleting a closed PR's branch loses nothing

Deleting the head branch of a **closed, unmerged** PR feels lossy, since the
commits are on no branch afterwards and `main` never absorbed them.
It is not.
GitHub retains the PR's own head ref permanently, and it still resolves after
the branch is gone.

Check before deleting, and recover afterwards:

```bash
git ls-remote origin 'refs/pull/669/head'          # still resolves post-deletion
git fetch origin refs/pull/669/head
git checkout -b recover/669 FETCH_HEAD
```

Verify rather than assume, since it is one call: `git ls-remote`'s SHA should
equal the branch tip you are about to delete.
Measured across six closed PRs on `Morrison-Lab/ai-config`
(#305, #306, #430, #553, #610, #669):
every `refs/pull/N/head` resolved and matched its branch tip exactly.

Two consequences worth carrying:

- A closed PR's branch is safe to delete, so the real deliverable is a tracking
  issue recording *what* was unlanded and the recovery command -- not keeping
  the ref.
- These refs are **not** fetched by the default refspec
  (`+refs/heads/*:refs/remotes/origin/*`), so they cost nothing until asked for.

- **Do:** cite the `refs/pull/N/head` recovery command in the issue that
  records the unlanded work.
- **Don't:** hold a dead branch open as the backup copy -- GitHub already is
  one.

## An orphaned `refs/remotes/<ns>/*` namespace inflates every branch count

A one-off `git fetch origin '+refs/pull/*/head:refs/remotes/pr/*'` writes refs
that **no configured refspec matches**.
Nothing updates them, `--prune` never touches them (it prunes only what a
refspec covers), and they persist indefinitely.

They are counted by `git branch -r`, so a repo can report hundreds of "remote
branches" that are neither remote nor branches.

```bash
git config --get-all remote.origin.fetch      # what is actually tracked
git for-each-ref --format='%(refname)' | grep -v '^refs/remotes/origin/'   # what is not
git for-each-ref --format='delete %(refname)' refs/remotes/pr/ | git update-ref --stdin
```

Before sweeping branches, separate the tracked namespace from stray ones ---
otherwise the sweep's scope is wrong from the first command.

(2026-08-02: `git branch -r` reported 741 on `Morrison-Lab/ai-config`, of which
709 were orphaned `refs/remotes/pr/*` from an earlier PR-head fetch and only 31
were real branches.
Deleting them took the repo from ~800 refs to 49.)

## Uncommitted leftovers on a merged branch can be a REJECTED direction, not unfinished work

Finding staged or unstaged edits on a branch whose PR already merged reads as
"work someone did not finish", and the reflex is to complete and land it.
Check the opposite hypothesis first, because the working tree records only that
an edit was *made*, never that it was *kept*.

Two shapes seen together on one branch:

- **A stale base.** The edits were written against an older `main`, so applying
  them now silently reverts whatever landed in between.
- **A rejected direction.** The edits contradict what the merged PR concluded,
  because they predate its final review round.

The second is the dangerous one: it looks like unfinished work and is actually
a bug someone already fixed correctly.

So before completing leftover work, check the branch's PR state, then verify
the edit's own claim independently rather than inferring intent from its
presence.

- **Do:** run the leftover edit's central claim as an experiment before landing
  it.
- **Do:** diff each leftover file against current `main`, not against the
  branch tip, to separate genuinely new content from stale-base reverts.
- **Don't:** treat an uncommitted edit as an unfinished intention -- it may be
  a draft the review already overruled.

(2026-08-02, after `Morrison-Lab/ai-config#900` merged: three staged files
proposed *unquoting* git's `branch -d` warning literal.
Reproducing the command showed git prints the quoted form with a trailing
period, which is what `main` already had -- so the leftovers would have
reintroduced the exact defect that PR's final round fixed.
A fourth, unstaged file held genuinely new content plus a stale-base reversion
of a taxonomy that had landed meanwhile; only the new half was carried forward,
as #1054.)

## Git --- deleting a remote branch returns HTTP 403 in a remote/web session

`git push origin --delete <branch>` (and its `:refs/heads/<branch>` spelling)
is refused by the agent proxy from a Claude Code remote/web session:
`error: RPC failed; HTTP 403`, then `fatal: the remote end hung up`.
It is a policy answer rather than a transient one, so the retry-with-backoff
path does not apply --- retrying reproduces the identical 403.

The failure also prints a trailing `Everything up-to-date`, which reads as
success once the error line scrolls away.

- **Do:** delete a remote branch through the forge API or UI here, and confirm
  with `git ls-remote origin refs/heads/<branch>`.
- **Do:** leave the branch and say so when neither is available; its closed PR
  is the record of why it exists.
- **Don't:** retry the delete with backoff.
- **Don't:** read `Everything up-to-date` as the delete having succeeded.

(Measured 2026-08-22;
[ai-config#1999](https://github.com/Morrison-Lab/ai-config/issues/1999).)
