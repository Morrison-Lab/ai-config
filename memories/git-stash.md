# Git stash

Stash-specific behavior: what `stash`/`pop` does to a stack shared by the
whole repository, and how to verify a stash before dropping it.
Split out of [`git.md`](git.md) (ai-config#694 pattern) at the 1200-line gate.

## `git stash` on an already-clean tree saves nothing, so a later `pop` restores someone else's work

The stash is a **stack owned by the repository**, not a slot owned by the
branch or the session.
So `stash`-then-`pop` is a round trip only when the `stash` half actually
pushed an entry, and on an already-clean working tree it does not.
`git stash push` prints `No local changes to save`, exits **0**, and leaves
the stack exactly as it found it.
Plain `git stash` behaves identically.
(Measured on git 2.34.1.)

The `pop` is where that turns destructive.
It takes whatever sits at `stash@{0}`, which on a stack this session never
pushed to is another branch's or another session's leftover work.
Neither command's output names the branch an entry came from, so the two
halves read as a matched pair whether or not they are one.

The idiom that produces it is "stash, measure a baseline, pop", and it
survives the first run.
It breaks on a **later** run, once the work has been committed in between, so
the tree the second `stash` meets is clean.
Nothing about that run looks different from the one before it.

**A conflicted pop is the lucky outcome, not the bad one.**
`git stash pop` keeps the entry when the merge conflicts, so a foreign stash
that collides announces itself and stays recoverable for its owner.
A foreign stash that applies **cleanly** is consumed and dropped, which is the
silent version of the same event.

- **Do:** answer a baseline question with a detached worktree
  (`git worktree add --detach /tmp/wt <ref>`) or `git show <ref>:<path>`,
  which touch neither the working tree nor the stash stack.
- **Do:** read `git stash push`'s own output when you do stash, since
  `No local changes to save` is the only thing distinguishing "my work is on
  the stack" from "someone else's is on top".
- **Do:** record the ref deterministically rather than reading a message ---
  `git rev-parse stash@{0}` before and after the push, and treat an unchanged
  value as proof nothing was saved.
- **Don't:** treat `stash` and `pop` as a matched pair because you wrote them
  together; only the stack decides what comes back.
- **Don't:** read a silent, successful `pop` as evidence it restored your own
  work.

**Recovery, when a pop has already brought in a foreign stash.**
Check `git status` and `git stash list` first, and confirm your own work is
already committed --- that is the whole precondition, and it is exactly what
the second run of the idiom guarantees.
Then `git reset --hard HEAD` restores your tree and leaves the retained stash
entry intact for whoever owns it.
Where your own work is **not** committed, that reset destroys it too, which is
why the precondition is a check to run rather than an assumption to carry.

The principle behind the first bullet is already recorded in
[`fail-fast`](../shared/principles/fail-fast.md)'s "A read-only question does
not license a state-mutating answer": a diagnostic must write nothing outside
a scratch path.
That section reaches the tree-mutating half of the composition; this entry is
the half about the **stash stack**, which is global state a scratch path does
not protect either.

(Measured 2026-08-12 in the `ai-config` clone at
`/home/<user>/Projects/ai-config`.
A "stash, measure, pop" idiom was run twice while the tree's own work was
committed in between, so the second `stash` saved nothing and the `pop` drew
`stash@{0}` --- `On 2026-07-29-branch-sweep-learnings: leftover uncommitted
from #900 branch (ardia draft + reverse literal edits)`, pushed 2026-08-02 and
touching `skills/ardia/SKILL.md`, `skills/clean-branches/SKILL.md`,
`skills/clean-worktrees/SKILL.md`, and `skills/post-merge/SKILL.md`.
The result was a conflicted `UU skills/ardia/SKILL.md` plus three unrelated
modified skill files.
Because the pop conflicted, the entry was retained and still reads as
`stash@{0}` today, so nothing was lost.)

## Verify supersession line-by-line, tag before dropping

- Before dropping a stash as "already landed", verify against `origin/main`,
  not by eyeball: extract the stash's added lines
  (`git stash show -p 'stash@{0}' | grep '^+[^+]'` --- the `[^+]` keeps the
  `+++ b/<path>` diff headers out of the set, where they'd read as spurious
  "missing from main" lines) and `grep -F` each one in
  main's version of the file; for files the stash *creates*, check
  `git cat-file -e origin/main:<path>`.
  A line that matches on topic but not verbatim usually means main carries
  the **improved** review-cycle revision
  --- read both and confirm main's is a superset before calling it superseded.
- **Whole-diff `git apply -R --check` is not that verification, and it fails
  in the direction that looks safe.**
  Reverse-applying a stash's diff against a clean checkout of `origin/main`
  reads like an exact supersession test, and it is one only while the
  surrounding lines have not moved.
  `git apply` matches whole hunks with context, so any unrelated edit to the
  same file since the stash was taken fails the hunk, and one failed hunk
  fails the file.
  The verdict comes back "not present on main" for content that is entirely
  present.
  Measured 2026-09-09 over this repo's 13-entry stash stack: the whole-diff
  check reported ABSENT for 12 of 13, including one entry whose added lines
  were 95% already on `main` and another at 100%.
  The per-line check in the bullet above scored those two correctly.
  That stack was dropped in the same sweep, so the figures are not
  re-derivable from `git stash list`;
  the entries survive as the local tags `backup/stash-2026-09-09-s0` through
  `-s12`, which is what makes the measurement auditable at all.
  Local tags are not pushed, so a clone other than that machine's cannot
  check it --- read the numbers as a recorded observation rather than as a
  standing claim about anything a fresh checkout can reproduce.
  - **Do:** index every line of every tracked file once
    (`git ls-files`, read each, build a set of stripped lines), then score
    each stash's added lines against that set --- one pass answers the whole
    stack, where a per-line `git grep` costs a subprocess per line and times
    out.
  - **Do:** read a partial score as a prompt to open the diff, since the
    residue is the whole question --- drop a stale count or a debugging edit,
    and recover an unlanded feature onto a branch before dropping its stash.
  - **Don't:** treat a whole-diff reverse-apply failure as evidence the
    content is unlanded.
  - **Don't:** treat a high percentage as landed without reading the
    remainder; the 5% that missed is where the unrecorded learning lives.
- `git stash show -p` **omits the untracked-files component.**
  Check `git show 'stash@{0}^3'`
  (that parent exists only if the stash was made with `-u`)
  before judging supersession.
- `git stash drop` is irreversible, and Claude Code's auto-mode classifier
  blocks it for exactly that reason --- sometimes even after a general "do the
  cleanup" go-ahead, when the stash is large.
  Don't fight it: run `git tag backup/stash-<topic> 'stash@{0}'` first.
  The stash commit stays reachable,
  the drop becomes genuinely reversible
  (recover with `git stash apply backup/stash-<topic>`),
  and the retried drop passes.
  Tell the user the tag exists;
  remove it with `git tag -d backup/stash-<topic>` once confident.

## A stash of somebody else's work rots when the base moves under it

The two sections above are about a stash that was **wrong when taken** --- one that saved nothing, or one dropped without checking what it held.
This is the stash that was *right* when taken and decayed while it sat.

Measured 2026-09-23 on `Morrison-Lab/mlg`.
A session found one uncommitted file in the user's checkout, stashed it to cut a clean branch, and got on with its own work.
Roughly two hours later that branch merged, and restoring the stash failed: an unrelated PR had rewritten the same file in the meantime (223 lines changed), so `git stash apply` left `UU` and a conflict in a file the session had never intended to touch.

The stash itself was fine.
What broke it was holding it across a base change --- and a stash is the one piece of git state that carries no branch, no upstream, and no record of what it was taken against beyond a one-line `WIP on <branch>: <subject>` label.
Nothing warns you, because from git's point of view nothing happened.

It is worse than losing your own work, for two reasons.
The user did not ask for their file to be moved, so they have no reason to be watching for it.
And the session that stashed it is the only thing that knows it exists --- `git status` on a dirty-turned-clean tree looks exactly like a tree that was always clean, which is the same indistinguishability the first section above describes from the other direction.

**Recovery, when it has already happened.**
Do not `pop`, which drops the stash on success and can leave you mid-conflict with it half-consumed.
`git stash show -p stash@{0}` first and read what it actually holds --- in the measured case a single line setting a Google Form id, which was then applied by hand onto the rewritten file in seconds.
`git stash apply` only after you know the change is small enough to re-derive if it conflicts, and reset the unmerged path (`git reset HEAD <path>` then `git checkout -- <path>`) rather than `git checkout --` alone, which refuses on an unmerged path.
Drop the stash only once the change is verifiably back in the tree.

- **Do:** restore a stash of somebody else's work in the same turn you took it, or commit their change to a branch of its own instead of stashing it.
- **Do:** read `git stash show -p` before applying a stash you have held across any merge or pull.
- **Do:** say in your reply that you stashed something of theirs, so the debt is visible to someone other than you.
- **Don't:** stash a dirty file to clear the way for your own branch and leave it stashed while you work --- the base moves, and the conflict lands in a file you had no business touching.
- **Don't:** `git stash pop` a stash held across a base change; `apply`, verify, then drop.
