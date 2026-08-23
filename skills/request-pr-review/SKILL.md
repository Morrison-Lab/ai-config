---
name: request-pr-review
description: "Request human review on PR."
user-invocable: true
allowed-tools:
  - Bash(gh api *)
  - Bash(gh pr *)
---

# request-pr-review

After AI review produces a clean verdict or upon a review deadlock, request a human reviewer.

## When to run

- After completing code pushes for the round AND after the AI review produces a clean/approved verdict (or upon a review deadlock), per [`copilot-review-before-human.md`](../../shared/vendored/copilot-review-before-human.md).
- When the user asks you to "request review" on an existing PR.

## Command

`EDIT_PR` (abstract operation token; resolve to your model's tool via
[`tool-mappings.md`](../../tool-mappings.md)):

```sh
gh api -X POST repos/<owner>/<repo>/pulls/<num>/requested_reviewers \
  -f "reviewers[]=<reviewer>"
```

You can get `<owner>/<repo>` from `gh repo view --json nameWithOwner -q .nameWithOwner`
and `<num>` from the PR URL returned by `gh pr create`.
`<reviewer>` is the repository's configured human reviewer or CODEOWNERS entry for the repository.

## Edge cases

- **PR author is the requested reviewer.** GitHub returns HTTP 422 with
  `"Review cannot be requested from pull request author"`. Surface this
  explicitly to the user — don't silently swallow the error.

- **Prefer this REST POST over `gh pr edit --add-reviewer`.**
  The CLI form exits 0 with no error when the reviewer is the PR author and
  attaches nobody, so the 422 above is invisible on that path
  (measured on Morrison-Lab/wai#93, 2026-08-22).
  When the target `<reviewer>` is the author (`<reviewer>` matches `.author.login`),
  skip the request entirely --- human review cannot be requested from the author.
  Report that the PR awaits that person's own review.

- **Other reviewers already requested.** The endpoint adds to the existing
  list rather than replacing it, so this is safe to run alongside
  pre-configured CODEOWNERS or workflow-added reviewers.

## Scope

Applies by default to all GitHub repos. If the user tells you a specific
repo shouldn't auto-request human review, honor that override per-repo via a
project-level memory.

### Exception: `Lacaedemon/sparta`

Never request a human reviewer on a PR in sparta.

The exception is repo-scoped, not rule-wide.
Requesting a human reviewer on other repos applies after AI review passes or on deadlock.
Within sparta the exception covers every path that would reach a request: the
post-AI-review request above, and the deadlock escalation below.

A skill inherits this exception only where it actually routes through here.
`st` does, citing this skill by name and nothing else.
`ard`, `ardi`, and `merge-it` carried the command guard inline.

The general rule is that **a raw command inherits nothing**;
only a reference to this skill does.
So when adding a repo exception here, grep for the raw command as well as for this skill's name:

```sh
git grep -nE 'add-reviewer|requested_reviewers' -- skills/
```

Both literal forms are matched: the `gh pr edit <N> --add-reviewer <reviewer>` command, and the workflow `gh api ... requested_reviewers -f "reviewers[]=<reviewer>"` form.
Then judge each hit rather than editing all of them.

**A review deadlock on a sparta PR escalates to the user in chat, not to a
review request.**
Escalation is re-routed, not retired: its purpose was always that a human
decides, and that is unchanged.
Post a boxed `BLOCKER` (per `CLAUDE.md`'s chat-output-tagging convention)
naming the PR, the single disputed item, and both sides of the exchange, then
stop iterating that item and wait for the user's call.

- **Do:** open a sparta PR with no human reviewer requested, and request human review on other repos after AI review is clean or on deadlock.
- **Do:** take a sparta deadlock to the user in chat as a boxed `BLOCKER`.
- **Don't:** run `gh pr edit --add-reviewer`, or POST to `requested_reviewers`, against a sparta PR.
- **Don't:** read this as ending escalation on sparta.
  An unresolved deadlock still needs a human, and chat is now where it goes.
