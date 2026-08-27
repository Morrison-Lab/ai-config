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
