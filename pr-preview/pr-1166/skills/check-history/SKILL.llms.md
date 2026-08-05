# check-history

Before implementing changes for an issue or MR, review the repository’s merge history to understand what decisions were made previously and why.

## When this fires (automatically)

- Starting work on any issue that involves modifying existing code
- Before proposing changes to CI/CD templates, shared infrastructure, or configuration files
- When the change touches code that has been refactored in prior MRs

## First: is the issue already done or in progress?

Before reviewing past history, confirm the issue still needs a *new* PR. Two checks (skipping them wastes a whole issue-pick):

- **Already resolved on `main`?** An issue can go stale — fixed incidentally by a later change (e.g. a dependency bump). Re-read the issue body against current `main` before implementing.

  ``` bash
  gh issue view <N> --json state,title,body | cat   # VIEW_ISSUE — also: is it already closed?
  ```

- **Existing open PR for it?** Search open PRs for one that already addresses the issue, so you don’t open a second, parallel PR for the same work.

  ``` bash
  gh pr list --state open --json number,title,headRefName,body \
    --jq '.[] | select(((.body // "") | test("#<N>\\b")) or (.title | test("#<N>\\b"))) | "#\(.number) \(.title) [\(.headRefName)]"'   # LIST_PRS
  ```

- **On a long-lived or foundational issue, the issue text AND any design-doc status header can lag the code by several PRs.** A mature feature (a phased effort, or anything with a dedicated design doc) may be partly or mostly implemented even when the issue reads as unstarted. The work can land across sibling PRs that never updated this issue or that header. Before scoping *new* code, verify the **actual implementation state against the code**: read the key source files implementing the feature and the test files, not just the issue body. (Seen on sparta: issue \#164 / \#240 read as “phase 4b not done”, but the core feature was already fully implemented and tested across sibling PRs — nearly rebuilt already-completed work. The right move was to audit, correct the stale issue/doc status, and pick the genuine next slice.)

If an open PR already covers it, **drive that PR to clean** instead of re-implementing (ask before pushing to a branch you didn’t create). If `main` already satisfies the issue, stand it down and report — don’t open a no-op PR. When the issue is only *partly* done, don’t rebuild the done part: audit it, correct the stale issue/doc status, and scope only the genuine remaining slice.

## Procedure

0.  **Check the issue for an already-open PR.** Before writing any code, look at the issue itself for an open PR that already addresses it (one whose body says `Closes #<N>`). A parallel session — or an issues-sweep run on another machine — may already be on it; building anyway produces a duplicate PR.

    **GitHub:**

    ``` bash
    gh pr list --state open --limit 100 --json number,title,body \
      --jq '.[] | select((.body // "") | test("(Closes|Fixes|Resolves) #<N>\\b"; "i")) | "#\(.number) \(.title)"'   # LIST_PRS
    ```

    **GitLab:**

    ``` bash
    glab mr list --state opened --per-page=50 --output json 2>/dev/null \
      | jq -r '.[] | select((.description // "") | test("(Closes|Fixes|Resolves) #<N>\\b"; "i")) | "!\(.iid) \(.title)"'
    ```

    If an open PR already covers the issue, **review or extend it** instead of opening a competing one. This catches *in-flight* work; the merged/closed history below catches *settled* decisions.

1.  **List recent merged MRs** touching the same area:

    **GitHub:**

    ``` bash
    gh pr list --state merged --limit 20 --json number,title,headRefName | cat   # LIST_PRS
    ```

    **GitLab:**

    ``` bash
    glab mr list --merged --per-page=20 2>&1 | cat
    ```

2.  **Identify relevant MRs** — look for titles/branches that relate to the files or subsystem you’re about to modify.

3.  **Read their descriptions** for rationale:

    **GitHub:**

    ``` bash
    gh pr view <N> --json body --jq '.body' | cat   # VIEW_PR
    ```

    **GitLab:**

    ``` bash
    glab mr view <N> 2>&1 | cat
    ```

4.  **Check for contradictions** — if a prior MR/PR explicitly chose approach A and you’re about to implement approach B, understand *why* A was chosen. Common patterns:

    - MR/PR \#X switched to strategy A for performance → don’t blindly revert to B
    - MR/PR \#Y removed code as dead → verify it’s still dead before re-adding
    - MR/PR \#Z added a guard/check → understand what it prevents before removing

5.  **Document the relationship** in your commit message or MR/PR description:

    - “This resolves the incompatibility between \#X and \#Y”
    - “Supersedes the approach from \#Z because \[reason\]”
    - “Preserves the intent of \#X (no wasted resources) while also…”

## What to look for

- **Intentional trade-offs** documented in MR descriptions
- **Reverted MRs** — if something was tried and reverted, don’t repeat it without understanding why it failed
- **Sequential MRs** that built on each other — your change might break an assumption from a later MR
- **Closed (not merged) MRs** — rejected approaches that shouldn’t be retried

## Output

Report a brief summary to the user: - Which MRs are relevant to the current work - Any potential conflicts or trade-offs identified - Confirmation that the proposed approach is compatible with prior decisions

If a conflict is found, surface it before writing code — don’t implement first and discover the regression later.

Back to top
