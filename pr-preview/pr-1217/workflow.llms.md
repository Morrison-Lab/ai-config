# Workflow guide

This page covers the key workflow conventions baked into the skills and `CLAUDE.md` instructions in this repo.

## Issue-first

Before branching, editing, or opening a PR, make sure a tracking issue exists. Search first; if no open issue covers the task, file one:

``` sh
gh issue create --title "..." --body "..."
```

The issue is the durable record of intent and scope. It lets the PR auto-close it via `Closes #N` and keeps the work discoverable if the PR stalls.

The [`start-task`](skills/start-task/SKILL.llms.md) skill (`/st`) runs this pattern end-to-end: search for an existing issue, file one if needed, branch, implement, open PR, and iterate to clean.

## Claim a PR before working on it

Before fetching a branch, editing files, or triggering a review loop, post a brief comment so other people and bots know not to start a conflicting session:

``` sh
gh pr comment <N> --body "Working on this --- paws off until I'm done."
```

After the session ends (PR merged, paused, or closed), follow up with a closing comment so the PR is unclaimed for the next person.

Skip the claim step if the most recent comment already claims it. Read-only inspection (checking status, explaining a diff) doesn’t need a claim.

The [`claim-pr`](skills/claim-pr/SKILL.llms.md) skill handles the exact wording and tracks when to unclaim.

## The ARDI loop

ARDI stands for **Address, Rebut, Defer, Iterate**. It’s the review loop that drives a PR to a clean verdict.

For every flagged item in a review, do exactly one of:

1.  **Address** — fix it in this PR (the default path; most nits are 1–3 line changes).
2.  **Rebut** — explain why the finding is wrong or doesn’t apply. Post the rebuttal in the PR and wait for the reviewer’s response. A rebuttal that doesn’t convince the reviewer does *not* close the item.
3.  **Defer** — file a follow-up issue and reference it in the PR. Use only when the fix expands scope (new feature, separate concern) or the requester said the PR shouldn’t grow.

After handling every item, push the fixes, post an ARD summary comment, and re-request review. Repeat until the latest review has zero flagged items under any heading.

The [`ardi`](skills/ardi/SKILL.llms.md) skill (`/ardi`) runs this full loop automatically. Aliases: `dc`, `drive`, `clean`, `iterate`.

### What “fully clean” means

A PR is fully clean when:

1.  All CI workflows and check runs are green and completed – not just the required checks, and not just the review job.
2.  The latest review has no flagged items — no nits, no “consider”, no “minor observation”. The reviewer’s “Not a blocker” label is not a pass; fix it or defer it.
3.  That review is a genuine posted verdict at the current head commit, from an external reviewer whenever one is reachable. Self-review is only the fallback for when no working external reviewer is available – never a substitute once one is – and availability gets re-checked right before declaring clean, not assumed from an earlier round.

At fully clean, every inline review thread is resolved. The only open conversation is the final all-clear exchange.

See [`shared/workflow/fully-clean.md`](https://github.com/d-morrison/ai-config/blob/main/shared/workflow/fully-clean.md) for the full definition this page summarizes.

**Deadlock:** if you and the reviewer can’t reach consensus after a rebuttal exchange, escalate to a human reviewer (`gh pr edit <N> --add-reviewer d-morrison`) rather than looping.

## Keep branches synced with main

Before pushing fixes or triggering a fresh review, merge `main` into the PR branch:

``` sh
git fetch origin main
git log --oneline ..origin/main | head    # any output? main is ahead
git merge origin/main
```

Don’t rebase or squash-rewrite a published PR branch unless explicitly asked — a merge commit matches GitHub’s “Update branch” button and preserves PR history.

The [`sync-pr-branch`](skills/sync-pr-branch/SKILL.llms.md) skill (`/sync`) does this automatically.

## Tracking upstream issues

When you find a bug in a dependency or external repo:

1.  Open a PR in the upstream repo if you have a fix ready.
2.  File an issue in the upstream repo if you have tracker access but no fix.
3.  File an issue in your own repo and ask the user to transfer it via GitHub’s *Transfer issue* feature.

In all cases, link the upstream issue or PR in your current PR so the root cause is tracked.

The [`send-upstream`](skills/send-upstream/SKILL.llms.md) skill (`/sup`) handles steps 1–2.

## Updating memories and skills

After a PR merges (or at the end of any significant session), run UMS to capture what you learned:

``` text
/ums
```

UMS reviews recent context for recurring review findings, corrections, and guidance, then writes or updates the relevant memory and skill files. A merge is the natural checkpoint to bank lessons before context is lost.

The [`merge-it`](skills/merge-it/SKILL.llms.md) skill chains `merge-it` → [`post-merge`](skills/post-merge/SKILL.llms.md) → [`ums`](skills/ums/SKILL.llms.md) automatically when you say “merge it”.

## Queue keywords

Several bare keywords (no `/` prefix) trigger skill semantics:

| Keyword | Skill | What it does |
|----|----|----|
| `also` | `/also` | Append a task to the current queue |
| `first` | `/first` | Prepend a task (do it before anything else) |
| `next` | `/next` | Queue a task for after the current one |
| `before` | `/before` | Insert a task before a named step |
| `and` | `/and` | Add a step to the current task |
| `remember` / `always` | `/memorize` | Save a fact or preference to memory |

Back to top
