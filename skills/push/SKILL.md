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

`hooks/no-push-without-self-review.py` gates this on Claude Code.
Morrison-Lab/ai-config's Cursor adapter skips that script
until [#2241](https://github.com/Morrison-Lab/ai-config/issues/2241)
([`memories/cursor.md`](../../memories/cursor.md)).
On Cursor Cloud, when `Task` lists `adversarial-reviewer`,
call `parse_report()` from the worktree's
[`hooks/no-push-without-self-review.py`](../../hooks/no-push-without-self-review.py)
on the report recovered from the child's transcript
when the worktree hook script exists
(see [`memories/cursor.md`](../../memories/cursor.md)).
Do not import `~/.claude/hooks/`:
it is a different revision from the branch under review.
When the three-dot diff includes
`hooks/no-push-without-self-review.py`,
also parse with `origin/<default-branch>`'s copy, or obtain a CLI review.
If the worktree script is missing, obtain a CLI review
(see [`adversarial-self-review`](../../shared/workflow/adversarial-self-review.md)).
If the verdict is not `clean`, or there is no fingerprint,
or the fingerprint does not prefix-match HEAD, do not push.
If there is no fingerprint
(including a stale-registered persona),
obtain a CLI review, write that reviewer's report to a file
under `/tmp`, and call `parse_report()` on that file.
On Claude Code the guard admits a verdict only from that subagent's own call result, only when the verdict is a verdict *line* rather than a sentence quoting one, and only when the report names the commit it read (`Reviewed-Commit: <sha>`, after the verdict) and that commit is what the push would actually ship --- refspec resolved, so `push origin some-other-branch` is not covered by a verdict for `HEAD`.
So an inline pass under a reviewer framing, a verdict quoted out of a file, the guard's own denial message, and a verdict for an earlier commit all fail to satisfy it.
Review after committing, therefore, not before.

Override by prefixing the push itself with `ALLOW_UNREVIEWED_PUSH=1` when no verdict can exist for the guard to check --- and say in your reply that you used it and why:

- the initial empty PR branch under [`pr-on-claim`](../../shared/workflow/pr-on-claim.md), which carries nothing to review;
- a review delivered by a separate CLI rather than a subagent, whose verdict never becomes an `Agent` call's result;
- a session where the reviewer agent is unregistered ([ai-config#1921](https://github.com/Morrison-Lab/ai-config/issues/1921)) or registered from a stale definition, which is the case on any rollout of a change to the persona itself;
- an emergency.

On a session whose pushes go through Morrison-Lab/ai-config's
Cursor adapter, default: do not prefix.
The prefix is inert for the adapter
until [#2241](https://github.com/Morrison-Lab/ai-config/issues/2241)
makes the adapter run that guard
(the skip and the `parse_report` gate are earlier in this step).
If a native `PreToolUse` deny from
`no-push-without-self-review` is observed on the push,
prefix for that native guard.
The empty [`pr-on-claim`](../../shared/workflow/pr-on-claim.md)
`--allow-empty` branch
has no report to parse: do not invent one,
do not refuse that push for lack of a verdict,
and say in the reply that the carve-out was used.
The carve-out is `git rev-list --count origin/<default-branch>..HEAD`
equal to 1 and `git diff --quiet HEAD^ HEAD` exit 0
in the checkout whose push follows.
Exit 1 means a diff; exit 128 means the command failed.
Both conditions passing is the `--allow-empty` pr-on-claim commit.
`git diff origin/<default-branch>...HEAD` empty is tree equality,
not "this branch carries nothing".
A net-zero tree of other commits is not the carve-out.
After [#2241](https://github.com/Morrison-Lab/ai-config/issues/2241)
makes the adapter run that guard,
the prefix is the documented escape
when the guard cannot see a verdict.
The adapter skip makes the prefix inert for the adapter only.
Do not pair the project adapter with native Claude hooks
(desktop Cursor with third-party Claude hooks plus this project adapter;
see [`memories/cursor.md`](../../memories/cursor.md)).

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

**Take this reading immediately before the push**, not at the start of the round and not when you last synced.
A fetch from earlier in the session is a measurement of a moment that has passed, and it stopped being evidence the instant somebody else pushed --- see [`check-before-pushing`](../../shared/workflow/check-before-pushing.md).

```bash
BRANCH=$(git rev-parse --abbrev-ref HEAD)
git ls-remote --heads origin "$BRANCH"   # LS_REMOTE --- read-only; updates no ref
```

If the tip it reports is not an ancestor of the ref you are **pushing** (`git merge-base --is-ancestor <tip> <source>`), **back off** --- another session (or the author) is driving this branch right now.
`<source>` is `HEAD` only when the refspec says so: `git push origin feature-x` from `main` pushes local `feature-x`, and comparing against `HEAD` there reads a divergence as a fast-forward.
Do not push (a plain push will be rejected anyway, and you must not force-push over their work).
Ask the user.

Fetch to see *what* they pushed, once you already know something is there:

```bash
git fetch origin "$BRANCH" 2>/dev/null   # FETCH
git log --oneline HEAD.."origin/$BRANCH" 2>/dev/null
```

An object you cannot resolve locally is the **stronger** signal, not the milder one: the remote moved after your last fetch and you cannot see what is there.

### 3. Claim comment by someone else

Look at the open PR for this branch for a claim comment posted by **another**
session or person. (Your own most-recent "I'm working on this" comment is fine —
that's your claim.)

```bash
PR=$(gh pr view --json number,headRefName -q .number 2>/dev/null)   # VIEW_PR
gh pr view "$PR" --json comments \
  -q '.comments[] | select(.body | test("hold off|paws off|back off|unclaim|released|PR is free|now mergeable"; "i")) | "\(.author.login): \(.body)"'   # READ_PR_COMMENTS
```

The alternation is deliberate, and it covers RELEASES as well as claims.
Claims posted before 2026-08-24 say "paws off", and a claim stays live on activity rather than on age, so an old-wording claim can be live right now.
The release terms matter because the old wording made them free: `paws off released` contains `paws off`, so one grep surfaced both sides of the exchange.
`claim released` contains neither claim term, so a claim-only query returns the claim and not its release --- and this check asks whether the claim "hasn't been unclaimed", which a claim-only output cannot answer.
A released PR would read as live-claimed, and this skill would refuse a legitimate push.
Derive the release terms rather than copying this list, which is a snapshot of what the corpus posts today: `grep -rn "unclaim\|released\|PR is free\|now mergeable" skills/ commands/`.
A matcher narrowed to the new phrase returns nothing on such a thread, which reads exactly like an unclaimed one --- see [`claim-pr`](../../shared/workflow/claim-pr.md).

The query returns the whole claim/release exchange, newest last, so read its **last** member: if that is a *claim* rather than a release, and it is from someone **other than you**, and it is still live --- the PR shows a push or comment within the last 2 hours, per [`claim-pr`](../../shared/workflow/claim-pr.md)'s expiration rule --- **do not push.**
Ask the user.
An expired claim (over 2 idle hours) no longer blocks on its own, but take it over with a fresh claim comment and run this skill's other checks (branch-head advance, `@claude` run in flight) before pushing.

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

`--force-if-includes` (added in Git 2.30.0) is the half usually left off, and without it the lease is defeatable: `--force-with-lease` compares against your *remote-tracking ref*, so any background fetch --- a poller, another tool in the same checkout, a `--recurse-submodules` fetch --- silently refreshes that ref and the lease then passes over the very commits it existed to protect.
`--force-if-includes` closes that by checking the remote-tracking tip against the local branch's reflog.
It is an *ancillary* option, so it only does anything alongside a bare `--force-with-lease`.

A `stale info` refusal is **not** a reason to force, and reaching for one there is the reflex `memories/git-branches.md` exists to stop: the lease is unsatisfiable rather than violated, so `--force` is unnecessary and there is nothing to race.
`git ls-remote --heads origin <branch>` settles existence --- empty output means the next push *creates* the branch.
Query `gh pr list --state all --head <branch>` first:
MERGED means auto-delete, not a first publish, so do not recreate
(see [`use-existing-pr-branch`](../../shared/workflow/use-existing-pr-branch.md)
and [`check-before-pushing`](../../shared/workflow/check-before-pushing.md)).
Otherwise a plain push is the fix (or `git fetch --prune` and a retry).
`ALLOW_FORCE_PUSH=1` is an escape valve for a case the guard did not foresee.
Say what the lease refused and why forcing is right when you use it.

`hooks/no-clobbering-push.py` enforces this half mechanically --- it refuses a bare force push and warns on a divergence --- so it fires whether or not this skill was invoked.

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

- **`claim-pr`** — posts/removes the claim comment this skill reads in check #3.
  `push` is the read side; `claim-pr` is the write side.
- **`session-lock` / `deconflict-sessions`** — the local-checkout counterpart: it keeps parallel sessions on one machine from sharing a working tree.
  `push` guards the *remote* branch; `session-lock` guards the *local* tree.
- **`sync-pr-branch` / `merge-main`** — when check #2 fires because `main` (not the branch) moved ahead, sync the branch first, then push.
  `sync-pr-branch` ends in a push and should itself honor these checks.
- **`ardi`** — its push step should run these checks; the "detect an active
  parallel session before pushing" note in `claim-pr` is the same guard.
- **[`check-before-pushing`](../../shared/workflow/check-before-pushing.md)** --- the standing rule these checks implement, and the home of the immediacy argument and the `--force-if-includes` mechanism.
  `hooks/no-clobbering-push.py` is its instrument, and it runs on the `git push` itself rather than waiting to be invoked --- so it covers the bare push in the middle of an ARDI round that never reaches this skill.

## Anti-patterns

- ❌ Force-pushing over commits another session added (check #2)
- ❌ Bare `git push --force` instead of `--force-with-lease --force-if-includes` (check #6)
- ❌ Reusing an earlier fetch as the check --- the reading has to be taken immediately before the push (check #2)
- ❌ Pushing past a fresh claim comment from someone else (check #3)
- ❌ Pushing onto a `do-not-merge` / `hold` PR without asking (check #4)
- ❌ Pushing while a `@claude` run is mid-session on the branch (check #5)
- ❌ Pushing directly to `main` / the default branch (check #1)
- ❌ Reporting "pushed" when a check stopped you — say what fired and that you're
  waiting on the user
