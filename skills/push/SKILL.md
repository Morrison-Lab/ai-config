---
name: push
description: "Pre-push check for active sessions."
user-invocable: true
allowed-tools:
  - Bash
  - AskUserQuestion
---

# push

A guard you run **right before `git push`**. Other sessions, reviewers, and the
`@claude` CI bot can all be working the same branch. Pushing blind risks
clobbering their work or shoving commits onto a branch someone explicitly held.
This skill runs a short pre-push check, and if anything looks off it **stops and
asks you** rather than pushing.

## When this fires

- The user says "push", "push this", "push my changes", or `/push`.
- Any time you're about to push commits to a **shared** branch (one with an open
  PR, or one another session may be driving).

It does **not** need to fire for a brand-new branch that has never been pushed
and has no PR — there's nothing to collide with. Still run the protected-branch
check in that case.

## Pre-push checks

Run these in order. Stop at the first one that fires and ask the user (see
[Asking for guidance](#asking-for-guidance)).

### 0. A separate subagent reviewed this diff and cleared it

Before pushing, dispatch the [`adversarial-reviewer`](../../.claude/agents/adversarial-reviewer.md) subagent against `git diff origin/<default-branch>...HEAD` and wait for its verdict.
Dispatch it in the **foreground** --- a background dispatch returns an agent id rather than a report, and you are waiting on the answer anyway.
Brief it with the base ref, the paths, and the standards that apply.
Never brief it with your rationale for the change, per [`adversarial-self-review`](../../shared/workflow/adversarial-self-review.md).

Address, rebut, or defer every finding it returns, then re-dispatch it, so the clean verdict describes the tree you are about to push rather than an earlier one.

`hooks/no-push-without-self-review.py` gates this.
It admits a verdict only from that subagent's own call result, only when the verdict is a verdict *line* rather than a sentence quoting one, and only when the report names the commit it read (`Reviewed-Commit: <sha>`, after the verdict) and that commit is what the push would actually ship --- refspec resolved, so `push origin some-other-branch` is not covered by a verdict for `HEAD`.
So an inline pass under a reviewer framing, a verdict quoted out of a file, the guard's own denial message, and a verdict for an earlier commit all fail to satisfy it.
Review after committing, therefore, not before.

Override by prefixing the push itself with `ALLOW_UNREVIEWED_PUSH=1` when no verdict can exist for the guard to check --- and say in your reply that you used it and why:

- the initial empty PR branch under [`pr-on-claim`](../../shared/workflow/pr-on-claim.md), which carries nothing to review;
- a review delivered by a separate CLI rather than a subagent, whose verdict never becomes an `Agent` call's result;
- a session where the reviewer agent is unregistered ([ai-config#1921](https://github.com/Morrison-Lab/ai-config/issues/1921)) or registered from a stale definition, which is the case on any rollout of a change to the persona itself;
- an emergency.

The prefix has to be on the pushing command, not merely somewhere on the line: an override the guard accepted from anywhere was how a commit message quoting this very paragraph disarmed it.

### 1. Protected branch

```bash
git rev-parse --abbrev-ref HEAD
```

If the current branch is `main` (or `master` / the repo's default branch),
**do not push.** Pushing to the default branch is almost never intended — surface
it and ask whether to branch first.

### 2. Remote HEAD advanced past your last commit

Another session or the author may have pushed since your last fetch.

```bash
BRANCH=$(git rev-parse --abbrev-ref HEAD)
git fetch origin "$BRANCH" 2>/dev/null   # FETCH
# Commits on the remote that you don't have locally:
git log --oneline HEAD.."origin/$BRANCH" 2>/dev/null
```

If `origin/$BRANCH` has commits you didn't push, **back off** — another session
(or the author) is driving this branch right now. Do not push (a plain push will
be rejected anyway, and you must not force-push over their work). Ask the user.

### 3. "Paws off" claim by someone else

Look at the open PR for this branch for a claim comment posted by **another**
session or person. (Your own most-recent "I'm working on this" comment is fine —
that's your claim.)

```bash
PR=$(gh pr view --json number,headRefName -q .number 2>/dev/null)   # VIEW_PR
gh pr view "$PR" --json comments \
  -q '.comments[] | select(.body | test("paws off"; "i")) | "\(.author.login): \(.body)"'   # READ_PR_COMMENTS
```

If the latest "paws off" comment is from someone **other than you**, hasn't
been unclaimed, and is still live --- the PR shows a push or comment within
the last 2 hours, per
[`claim-pr`](../../shared/workflow/claim-pr.md)'s expiration rule ---
**do not push.** Ask the user.
An expired claim (over 2 idle hours) no longer blocks on its own, but take it
over with a fresh claim comment and run this skill's other checks (branch-head
advance, `@claude` run in flight) before pushing.

### 4. Hold / block labels

```bash
gh pr view "$PR" --json labels -q '.labels[].name'   # VIEW_PR
```

If any label signals a hold — case-insensitive matches on `do-not-merge`,
`do not merge`, `WIP`, `hold`, `blocked`, `on hold`, `dont-merge` — **do not
push.** Ask the user.

### 5. `@claude` agent run in flight

Don't push while the bot is mid-session on the branch — your push can collide
with its commits or trigger a redundant re-run.

```bash
gh run list --branch "$BRANCH" --json status,name \
  -q '.[] | select(.status=="in_progress" or .status=="queued") | .name'
```

If a `@claude` / review workflow is `in_progress` or `queued`, wait for it to
finish, then re-check. If it's stuck, ask the user.

## Asking for guidance

When a check fires, **do not push.** Use `AskUserQuestion` to surface exactly
what fired and let the user decide. Give concrete options, e.g.:

- **Wait / re-check** — back off and re-run the checks shortly (HEAD-advanced or
  `@claude`-in-flight cases).
- **Push anyway** — the user knows the signal is stale (e.g. their own old hold
  label, a resolved claim).
- **Branch first** — for the protected-branch case, create a feature branch and
  push that instead.
- **Skip the push** — leave the commits local for now.

Include the specifics in the question (which label, whose claim, how many
commits ahead) so the user can answer without digging.

## Pushing (checks clean)

Once every check passes, push with the standard upstream + retry backoff:

```bash
git push -u origin HEAD   # PUSH
```

`HEAD` rather than `"$BRANCH"`, deliberately: a shell variable reaches the pre-push guard unexpanded, so it cannot resolve which commits the push would ship and refuses.
`-u origin HEAD` sets the upstream to the current branch just the same.

If the push fails on a **network** error, retry up to 4 times with exponential
backoff (2s, 4s, 8s, 16s). Do **not** retry — and do **not** force-push — if it
fails because the remote rejected a non-fast-forward (that's check #2 surfacing
late: fetch, reconcile, re-run the checks).

After a successful push, if the branch has no PR yet, open one (ready for
review, not a draft).

## Relationship to other skills

- **`claim-pr`** — posts/removes the "paws off" claim comment this skill reads
  in check #3. `push` is the read side; `claim-pr` is the write side.
- **`session-lock` / `deconflict-sessions`** — the local-checkout counterpart:
  it keeps parallel sessions on one machine from sharing a working tree. `push`
  guards the *remote* branch; `session-lock` guards the *local* tree.
- **`sync-pr-branch` / `merge-main`** — when check #2 fires because `main` (not
  the branch) moved ahead, sync the branch first, then push. `sync-pr-branch`
  ends in a push and should itself honor these checks.
- **`ardi`** — its push step should run these checks; the "detect an active
  parallel session before pushing" note in `claim-pr` is the same guard.

## Anti-patterns

- ❌ Force-pushing over commits another session added (check #2)
- ❌ Pushing past a fresh "paws off" claim from someone else (check #3)
- ❌ Pushing onto a `do-not-merge` / `hold` PR without asking (check #4)
- ❌ Pushing while a `@claude` run is mid-session on the branch (check #5)
- ❌ Pushing directly to `main` / the default branch (check #1)
- ❌ Reporting "pushed" when a check stopped you — say what fired and that you're
  waiting on the user
