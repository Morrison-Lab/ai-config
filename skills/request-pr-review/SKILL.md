---
name: request-pr-review
description: Request a human reviewer after AI review passes or upon deadlock on a GitHub PR.
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

## Edge cases

- **PR author is the requested reviewer.** GitHub returns HTTP 422 with
  `"Review cannot be requested from pull request author"`. Surface this
  explicitly to the user — don't silently swallow the error.

- **Other reviewers already requested.** The endpoint adds to the existing
  list rather than replacing it, so this is safe to run alongside
  pre-configured CODEOWNERS or workflow-added reviewers.

## Scope

Applies by default to all GitHub repos. If the user tells you a specific
repo shouldn't auto-request d-morrison, honor that override per-repo via a
project-level memory.

### Exception: `Lacaedemon/sparta`

Never request `d-morrison` as a reviewer on a PR in sparta.

The exception is repo-scoped, not rule-wide.
Requesting `d-morrison` everywhere else stays correct and unchanged, on PR
creation and on deadlock alike, and that includes `Morrison-Lab/ai-config`,
which is emphatically not covered.
Within sparta the exception covers every path that would reach a request: the
standing post-`gh pr create` request above, and the deadlock escalation below.

A skill inherits this exception only where it actually routes through here.
`st` does, citing this skill by name and nothing else.
`ard`, `ardi`, and `merge-it` did **not**: each named the raw
`gh pr edit <N> --add-reviewer d-morrison` command, which reaches GitHub
without passing through this file, so the exception could not reach it.
`merge-it` was the worst of the three -- its `BLOCKED`-state fix step never
mentioned this skill at all, so running it on a sparta PR awaiting an
approving review would have requested `d-morrison` outright.
All three now carry the guard inline.

The general rule is that **a raw command inherits nothing**;
only a reference to this skill does.
So when adding a repo exception here, grep for the raw command as well as for this skill's name:

```sh
git grep -nE 'add-reviewer d-morrison|requested_reviewers.*d-morrison' -- skills/
```

Both literal forms are matched: the `gh pr edit <N> --add-reviewer d-morrison` command, and the workflow `gh api ... requested_reviewers -f "reviewers[]=d-morrison"` form.
Then judge each hit rather than editing all of them.
`skill-builder` and `agent-builder` name the raw command but are **correct as they stand**, because the PR they open always lands in ai-config, which this exception does not cover.
A hit needs a guard only where the PR could be a sparta one.
That grep is how the `merge-it` gap was found.
The widened form also catches `claude-agent-workflow`'s `requested_reviewers` line, now guarded for sparta.
So the sweep is worth running -- and worth reading, not applying blindly.

**A review deadlock on a sparta PR escalates to the user in chat, not to a
review request.**
Escalation is re-routed, not retired: its purpose was always that a human
decides, and that is unchanged.
Post a boxed `BLOCKER` (per `CLAUDE.md`'s chat-output-tagging convention)
naming the PR, the single disputed item, and both sides of the exchange, then
stop iterating that item and wait for the user's call.

- **Do:** open a sparta PR with no human reviewer requested, and keep
  requesting `d-morrison` on every other repo's PRs, ai-config's included.
- **Do:** take a sparta deadlock to the user in chat as a boxed `BLOCKER`.
- **Don't:** run `gh pr edit --add-reviewer d-morrison`, or POST to
  `requested_reviewers` with that login, against a sparta PR.
  Not on creation, and not as a deadlock escalation.
- **Don't:** read this as ending escalation on sparta.
  An unresolved deadlock still needs a human, and chat is now where it goes.

(Directive from the user, 2026-08-05: "cai: stop requesting reviews from
d-morrison in this repo", then, correcting the scope shortly after, "cai: stop
requesting reviews from d-morrison in sparta, not in ai-config".
The first reading took "this repo" to mean ai-config, since that was where the
PRs under discussion sat, and shipped the exception pointed at the wrong repo
in ai-config#1177 --- which also reverted the reviewer request in six skills
that ship to ai-config and should have kept it.
Recorded because the near-miss is the transferable part: "this repo" resolves
against the repo the *work* is about, which need not be the repo whose PRs
happen to be in front of you.
When a repo-scoped directive arrives during cross-repo work, name the repo
back explicitly before encoding it.
No reason for the rule was given, and none is invented here.)
