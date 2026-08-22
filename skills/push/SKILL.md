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

### 1. Protected branch

```bash
git rev-parse --abbrev-ref HEAD
```

If the current branch is `main` (or `master` / the repo's default branch),
**do not push.** Pushing to the default branch is almost never intended — surface
it and ask whether to branch first.

### 2. Remote HEAD advanced past your last commit

Another session or the author may have pushed since your last fetch.

**Take this reading immediately before the push**, not at the start of the round and not when you last synced.
A fetch from earlier in the session is a measurement of a moment that has passed, and it stopped being evidence the instant somebody else pushed — see [`check-before-pushing`](../../shared/workflow/check-before-pushing.md).

```bash
BRANCH=$(git rev-parse --abbrev-ref HEAD)
git ls-remote --heads origin "$BRANCH"   # LS_REMOTE — read-only; updates no ref
```

If the tip it reports is not an ancestor of your `HEAD` (`git merge-base --is-ancestor <tip> HEAD`), **back off** — another session (or the author) is driving this branch right now.
Do not push (a plain push will be rejected anyway, and you must not force-push over their work).
Ask the user.

Fetch to see *what* they pushed, once you already know something is there:

```bash
git fetch origin "$BRANCH" 2>/dev/null   # FETCH
git log --oneline HEAD.."origin/$BRANCH" 2>/dev/null
```

An object you cannot resolve locally is the **stronger** signal, not the milder one: the remote moved after your last fetch and you cannot see what is there.

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

### 6. The push's own form

Never `git push --force` / `-f`.
It overwrites the remote tip unconditionally, including commits another agent pushed since you last looked.

```bash
git push --force-with-lease --force-if-includes
```

`--force-if-includes` (added in Git 2.30.0) is the half usually left off, and without it the lease is defeatable: `--force-with-lease` compares against your *remote-tracking ref*, so any background fetch — a poller, another tool in the same checkout, a `--recurse-submodules` fetch — silently refreshes that ref and the lease then passes over the very commits it existed to protect.
`--force-if-includes` closes that by checking the remote-tracking tip against the local branch's reflog.
It is an *ancillary* option, so it only does anything alongside a bare `--force-with-lease`.

The one case that needs bare `--force` is a lease that is **unsatisfiable** rather than violated: a `stale info` failure after a squash-merge with auto-delete removed the branch your ref still names (`memories/git.md`).
Prefix that with `ALLOW_FORCE_PUSH=1`.

`hooks/no-clobbering-push.py` enforces this half mechanically — it refuses a bare force push and warns on a divergence — so it fires whether or not this skill was invoked.

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
git push -u origin "$BRANCH"   # PUSH
```

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
- **[`check-before-pushing`](../../shared/workflow/check-before-pushing.md)** — the standing rule these checks implement, and the home of the immediacy argument and the `--force-if-includes` mechanism.
  `hooks/no-clobbering-push.py` is its instrument, and it runs on the `git push` itself rather than waiting to be invoked — so it covers the bare push in the middle of an ARDI round that never reaches this skill.

## Anti-patterns

- ❌ Force-pushing over commits another session added (check #2)
- ❌ Bare `git push --force` instead of `--force-with-lease --force-if-includes` (check #6)
- ❌ Reusing an earlier fetch as the check — the reading has to be taken immediately before the push (check #2)
- ❌ Pushing past a fresh "paws off" claim from someone else (check #3)
- ❌ Pushing onto a `do-not-merge` / `hold` PR without asking (check #4)
- ❌ Pushing while a `@claude` run is mid-session on the branch (check #5)
- ❌ Pushing directly to `main` / the default branch (check #1)
- ❌ Reporting "pushed" when a check stopped you — say what fired and that you're
  waiting on the user
