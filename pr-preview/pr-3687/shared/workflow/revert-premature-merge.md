# Revert Premature or Defective Merges Immediately and Continue on the Original PR Branch

When a Pull Request is prematurely or incorrectly merged
(e.g. merged before external review completion, merged over open findings, or merged without authorization):

## Immediate Revert Protocol

1. **Open a revert PR on `main` immediately**:
   Open a revert branch from `origin/main`,
   run `git revert <merge-commit>`,
   push,
   and drive the revert PR to a clean approved verdict and green CI before merging under `/mwc` / `/maw`, or request explicit user merge authorization.
   Never leave a defective or unapproved merge on the default branch while troubleshooting.

2. **Return to the original PR branch**:
   Switch directly to the original feature branch (`git checkout <original-branch>`).
   Never abandon the original branch to spin off untracked ad-hoc fix branches.

3. **Incorporate upstream and restore feature commits**:
   Because `main` now carries the revert commit that undone the feature diff,
   a plain merge of `main` into the original branch would erase the feature changes (the classic Git revert-of-a-merge trap).
   To preserve the feature diff and incorporate upstream history:
   merge `origin/main` and immediately revert the revert commit on the branch (`git revert <revert-commit-sha>`),
   or rebase the feature commits onto `origin/main` (`git rebase origin/main`).

4. **Address all review findings**:
   Fix every review finding and CI issue that was missed in the initial merge round.
   Validate tests, formatting, links, and manifests locally.

5. **Push and continue under ARDI**:
   Push to the original branch (`git push origin <original-branch>`).
   Because GitHub platform mechanics permanently lock merged PRs in state `MERGED`,
   open the continuation PR referencing the original PR number,
   request external AI review (`@claude review`),
   and drive the PR to a clean approved verdict before taking any merge action.

- **Do:** revert the merge on `main` immediately, return to the original branch, restore the feature diff by reverting the revert or rebasing onto `main`, address all findings, and drive the continuation PR to clean.
- **Don't:** leave an incorrect merge sitting on `main` while working on fixes, and don't create arbitrary new branches when the original PR branch is the canonical place of work.

## A revert is the default, not the rule: ask what the revert restores

Step 1 above reverts immediately, and that is right whenever the merge's
**content** is the defect.
One recognizable case inverts it, and it is common enough on a hardening branch
to need naming: a merge that lands over open findings while its diff also
closes a defect that exists on `main`.
Reverting then re-opens that defect in order to remove the findings, which is a
net loss whenever the defect is the worse of the two.

The deciding question is about the base rather than about the merge:
**what does `main` do without this commit?**

- Reverting leaves `main` merely missing a feature --- revert.
  That is step 1's case, and it stays the default.
- Reverting leaves `main` actively broken --- a hole the merge closed, a fix
  that later work already assumes --- fix forward instead.

"It was merged over open findings" cannot decide this, which is the trap:
it describes how the commit arrived and says nothing about what it contains,
and it is exactly the sentence that makes an immediate revert feel mandatory.

**A fix-forward is not the lighter option, and what makes it legitimate is the
re-filing.**
The findings were raised against a branch that is no longer a reviewable unit,
so nothing carries them once GitHub locks the PR at `MERGED`.
Writing them into an issue against `main` is what stops a fix-forward becoming
the silent loss this protocol exists to prevent.
File that issue before opening the fix PR, per
[`issue-first`](issue-first.md), and have the fix PR close it.

The issue-reopening rule in [`revert-merge`](revert-merge.md) does not apply on
this path and should not be performed as though it did: nothing was reverted,
so the original issue is still genuinely closed by work still on `main`.

- **Do:** name the state `main` returns to, before choosing.
- **Do:** fix forward where the revert would restore a defect worse than the
  open findings, and re-file every open finding as an issue against `main` in
  the same turn.
- **Do:** keep the immediate revert as the default whenever the merged content
  is itself the defect.
- **Don't:** revert on the strength of "merged over open findings" alone ---
  that is a fact about the process, and the decision turns on the content.
- **Don't:** fix forward without filing;
  a finding on `main` with no branch, no PR, and no reviewer is dropped rather
  than deferred.

(Measured 2026-09-15 on
[ai-config#3635](https://github.com/Morrison-Lab/ai-config/pull/3635), merged as
`322ae8a7` while its pre-merge adversarial gate had returned **NOT_CLEAN with 7
findings** six minutes earlier.
Reverting would have restored two executing bypasses of
`hooks/no-unauthorized-merge.py` that the diff closed --- both `bash -n` clean,
and both reproduced running a real `gh pr merge` against a stub while the hook
returned `allow`.
The same gate reported no executing bypass remaining at that head, across
29,813 differential strings and 5,034 constructed executing shapes, and every
one of the seven findings was a documentation or coverage defect.
So the revert was the strictly worse action, and
[#3681](https://github.com/Morrison-Lab/ai-config/issues/3681) ->
[#3682](https://github.com/Morrison-Lab/ai-config/pull/3682) closed all seven on
`main` instead.)
