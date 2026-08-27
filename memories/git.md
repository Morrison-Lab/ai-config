# Git

Branch and remote-branch lifecycle (push, rename, delete, retarget,
recover, prune): [`git-branches.md`](git-branches.md).
Diff-range selection, diff-scoped check pitfalls, and pathspec/glob/ref
pattern matching: [`git-diffing.md`](git-diffing.md).
Stash-specific behavior: [`git-stash.md`](git-stash.md).
Tag management: [`git-tags.md`](git-tags.md).
Worktree-specific behavior: [`git-worktrees.md`](git-worktrees.md).

## Git branches

See [`git-branches.md`](git-branches.md) for branch and remote-branch
lifecycle: `gh pr merge --delete-branch` orphaning a stacked PR, a
head-branch rename closing its own PR, rebuilding a stacked PR across a
squash-merge, pushing a stray branch instead of HEAD, the remote-session
push-proxy deletion no-op / HTTP 403, pruning a `[gone]` local branch
safely, recovering a closed PR's branch from `refs/pull/N/head`,
uncommitted leftovers on a merged branch as a rejected direction rather
than unfinished work, and an orphaned `refs/remotes/<ns>/*` namespace.

## Git diffing

See [`git-diffing.md`](git-diffing.md) for diff-range selection
(`..` vs `...` vs the working tree), diff-scoped check pitfalls
(no-op-ing on an uncommitted diff, blindness to untracked files, an
untracked copy shadowing a tracked script), `git rev-parse <ref>:<path>`
echoing its own input on a missing path, and the pathspec-vs-glob /
`for-each-ref`-vs-`ls-files` matcher mismatches.

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
  (Verified on git 2.x;
a review bot suggested the broken form on Morrison-Lab/gha#58.)

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
