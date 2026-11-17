# Confirm a clone is complete before reading history from it

A shallow clone answers history questions wrongly and exits 0.
Its cut-off commits, listed in `<common-dir>/shallow`, look parentless, so a walk that reaches one stops there.
`git merge-base` then names no base, `git rev-list --count A..B` counts commits both branches share, `git log --reverse` names a "first commit" that is only the cut-off, and a cut-off commit's diff shows it adding every file.
On 2026-11-11 a cloud session audited Morrison-Lab/lds's branches from a shallow clone, concluded that 23 branches shared no history with `main`, and recommended deleting 41 of them.
Twelve held work found on no other branch, and Ezra stopped the deletion seconds before it ran ([ai-config#5323](https://github.com/Morrison-Lab/ai-config/issues/5323)).

Every decision drawn from a history read is only as sound as the clone it was read from.
The decision most at risk is a deletion, because the clone's error points the same way as the deletion: the work looks unmerged, orphaned, or already in `main`, and a deleted ref cannot be read back to check.

- **Do:** run `git rev-parse --is-shallow-repository` before any comparison, ancestry, count, first-commit, or "is this merged" read, and `git fetch --unshallow origin` when it prints `true`.
- **Do:** re-derive a report's history claims from the full clone before acting on any recommendation it makes, above all a deletion.
- **Don't:** delete or force-push a remote ref on the strength of a read taken in a clone you never confirmed was complete.
- **Don't:** read a clean exit, a real SHA or a real date as evidence that the answer is right: the clone gives all three for a wrong answer.

[`memories/git.md`](../../memories/git.md#in-a-shallow-clone-git-log--s---follow-and-blame-report-a-graft-as-the-introduction) records the related failure modes, `blame` among them, which no check covers.

## The other two layers

- **The check:** `hooks/no-history-compare-in-shallow-clone.py` refuses, in a shallow repository, each read whose walk reaches a cut-off commit, and every push that can delete a remote ref.
  `ALLOW_SHALLOW_HISTORY=1` overrides one command.
- **The reviewer:** [`adversarial-reviewer`](../../.claude/agents/adversarial-reviewer.md#history-read-from-a-shallow-clone) looks for a deletion or a history claim that rests on a clone never confirmed complete.
