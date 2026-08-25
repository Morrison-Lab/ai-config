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

3. **Sync `main` on the original branch**:
   Merge `origin/main` into the original branch (`git merge origin/main`) to incorporate upstream history;
   the branch's feature commits remain intact for iteration.

4. **Address all review findings**:
   Fix every review finding and CI issue that was missed in the initial merge round.
   Validate tests, formatting, links, and manifests locally.

5. **Push and continue under ARDI**:
   Push to the original branch (`git push origin <original-branch>`).
   Because GitHub platform mechanics permanently lock merged PRs in state `MERGED`,
   open the continuation PR referencing the original PR number,
   request external AI review (`@claude review`),
   and drive the PR to a clean approved verdict before taking any merge action.

- **Do:** revert the merge on `main` immediately, return to the original branch, sync `main`, address all findings, and drive the continuation PR to clean.
- **Don't:** leave an incorrect merge sitting on `main` while working on fixes, and don't create arbitrary new branches when the original PR branch is the canonical place of work.
