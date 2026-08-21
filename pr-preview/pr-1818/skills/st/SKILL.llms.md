# st — Start Task (issue-first)

Kick off a new piece of work **issue-first**: never jump straight into a PR. Every new task gets a tracking issue before any branch or edit. This is the complement to `gi` — `gi` grabs an issue that already exists; `st` is for work you have in mind that isn’t tracked yet, so you write the issue first and then flow into the same implement → PR → ARDI tail.

## When this fires

- “st”, “start a task”, “start a new task”, “new task”, “let’s work on X” where X has no open issue yet.
- Any time you’re about to start coding something that isn’t already covered by an open tracking issue.

## Core rule: issue before PR

Before branching or editing, ensure an issue exists:

1.  **Search** the tracker for an existing issue covering the task.
2.  **Exists** → use it — this is just `gi` on that number.
3.  **None** → **file one first**, then proceed.

Why issue-first: the issue is the durable record of intent, scope, and “done” criteria. It gives reviewers context, lets the PR auto-close it via `Closes #N`, prevents duplicate/undiscoverable work, and means there’s a tracked home for the task even if the PR stalls.

## Procedure

### 1. Restate the task and “done” criteria

One or two sentences: what’s the change, why, and what “done” looks like. If you can’t state “done”, the issue isn’t ready to write yet — clarify scope first.

### 2. Search for an existing issue

``` bash
# GitHub — open first, then all states (it may already be filed or closed)
gh issue list --state open --search "<keywords>" --json number,title,url | cat   # SEARCH_ISSUES
gh issue list --state all  --search "<keywords>" --limit 10 \
  --json number,title,state,url | cat   # SEARCH_ISSUES

# GitLab
glab issue list --search "<keywords>" --per-page=20 2>&1 | cat
```

- **Open match** → an issue already exists, so this is just `gi` on that number: invoke the `gi` skill from its claim step onward (claim → check history → branch → open draft PR → implement → mark ready → ARDI). Skip the rest of `st` — you don’t need to file anything.
- **Closed match** → surface it (“looks like \#N already covered this and was closed”) and confirm with the user before re-doing the work.

### 3. File the issue (if none exists)

``` bash
# GitHub
gh issue create --title "<concise title>" --body "<what & why>

**Done when:** <acceptance criteria>
<scope notes / out-of-scope>"   # CREATE_ISSUE

# GitLab
glab issue create --title "<concise title>" --description "<what & why>

**Done when:** <acceptance criteria>"
```

- Keep scope tight — **one concern per issue** (see `split-concerns`). If the task is really several concerns, file several issues.

- Capture acceptance criteria so “done” is unambiguous later.

- Label it if the repo uses labels.

- Then **claim it** (`claim-pr` pattern) so a parallel session / the `@claude` bot doesn’t collide:

  ``` bash
  gh issue comment <N> --body "Claude Code CLI (local session) is working on this — paws off until I'm done."   # COMMENT_ISSUE
  ```

### 4. Check history

Invoke `check-history` before implementing — review merged/closed MRs that touched the same area so you don’t undo past progress.

### 5. Branch → open draft PR → implement → ready → ARDI

From here the tail is identical to `gi`:

``` bash
git fetch origin main                       # FETCH
git checkout -b <type>/<slug> origin/main   # CREATE_BRANCH — fix/ feat/ docs/ refactor/
```

- **Open the draft PR now**, before implementing — an empty commit gives the branch a diff to open against, kept as a draft so the review bot doesn’t run on an empty diff (see [`pr-on-claim`](../../shared/workflow/pr-on-claim.md)):

  ``` bash
  git commit --allow-empty -m "start: <title> (closes #<N>)"   # COMMIT
  git push -u origin <type>/<slug>                              # PUSH
  gh pr create --draft --title "<title>" --body "Closes #<N>

  WIP — opened up front to claim the issue; implementing now."   # CREATE_PR
  ```

- Implement (code, tests, docs), run the repo’s standard checks, and push the implementation onto the PR, committing with a message referencing the issue (`fix: … (closes #N)`).

- **Mark the PR ready for review** (`gh pr ready <N>` — `MARK_PR_READY`) and request `d-morrison` as reviewer (`request-pr-review`).

- **ARDI** the PR to a clean verdict (`ardi`). Don’t merge unless asked.

### 6. Report

Linked issue + PR, ARDI round count, and any deferred follow-up issues.

## Relationship to other skills

- **`brainstorm`** — when the task’s shape isn’t settled yet (multiple reasonable interpretations, a real design tradeoff, “done” can’t yet be stated in one sentence), run `brainstorm` first to resolve that through a Socratic Q&A loop and a plan file, then hand the result to this skill’s “restate the task and ‘done’ criteria” step instead of starting from scratch.
- **`gi`** — once the issue exists, the implement → PR → ARDI tail is the same; `st` is “`gi`, but you write the issue first.”
- **`defer-issue`** — same issue-creation mechanics, for sub-tasks that emerge.
- **`check-history`**, **`claim-pr`**, **`pr-on-claim`**, **`request-pr-review`**, **`ardi`**, **`split-concerns`** — invoked along the way (`pr-on-claim` is the “open the draft PR before implementing” step).
- **`post-merge`** — closes the lifecycle that `st` opens, once the PR lands.

## Anti-patterns

- ❌ Opening a PR with no tracking issue behind it.
- ❌ Filing a duplicate without searching open **and** closed issues first.
- ❌ A vague issue with no “done” criteria.
- ❌ Re-doing already-closed work without flagging it to the user.
- ❌ Cramming multiple independent concerns into one issue/PR.

Back to top
