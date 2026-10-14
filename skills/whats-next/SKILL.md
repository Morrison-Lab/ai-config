---
name: whats-next
description: "Recommend concrete next step or action."
user-invocable: true
allowed-tools:
  - Bash
  - Read
---

# whats-next --- recommend concrete next step or action (wn)

Survey the current repository state, in-flight worktrees, open PRs and issues, active batch mandates, and context health to recommend the single most appropriate next action.
Whether the recommendation is for the agent to continue working, for the user to make a decision, or to archive the session and start fresh, always give a clear, explicit recommendation with rationale.

## When this fires

- Explicit invocation: `/whats-next`, `/wn`, `wn`, "what's next", "what's next?", "what should we do next?", "what next?", "where should we go from here?".
- When an in-flight milestone or task completes and the next objective is not predetermined.
- When resuming an ambiguous session where the immediate priority is unclear.

> **Contrast with `/next`:** `/next <instruction>` modifies the execution queue by inserting a task right after the currently in-progress task.
> `/whats-next` (or `wn`) is an inspection and recommendation skill that answers the question "what should we do next?".

## Core Principle: Always recommend a concrete path

Whenever `whats-next` is invoked, provide a concrete recommendation.
Do not dump a passive list of possibilities without choosing one.
Evaluate the options, declare the single best path forward, and explain why:

```markdown
**Recommendation: <action>** --- <rationale>.
```

If multiple viable paths exist, state the recommended primary action first, then briefly list the alternative options.

## Assessment Procedure

Work through these tiers in order of precedence.
The highest tier with matching work dictates the primary recommendation.

### 1. In-flight local work (highest priority)

Check whether local changes or detached worktrees are uncommitted or unpushed:

```bash
git status --short
git diff --stat
git worktree list
```

- **Uncommitted edits or unpushed commits:** Recommend completing the delivery cycle in the current worktree (run tests, commit, adversarial review, push, and open or update a PR).
  Agents do not leave half-finished work in a dirty worktree.
- **Detached or stale worktrees:** If an idle worktree holds completed or abandoned work, recommend pruning it or completing its delivery.

### 2. Open pull requests authored by this session or user

Check the status of open pull requests:

```bash
gh pr list -R <owner>/<repo> --author "@me" --state open
```

- **PR is waiting on CI or automated review:** Recommend checking checks and driving the PR to clean (`ardi` / `clean-pr`):
  ```bash
  gh pr checks <number> -R <owner>/<repo>
  python3 scripts/check-pr-fully-clean.py <number> -R <owner>/<repo>
  ```
- **PR has outstanding review findings:** Recommend addressing, rebutting, or deferring review comments (`ard` / `ardi`).
- **PR is fully clean and approved under MWC (`merge-when-confident`):** Recommend squash-merging the PR, fast-forwarding `main`, cleaning up the worktree, and closing the tracking issue (`merge-it` / `post-merge`).
- **PR is waiting for human review:** If automated review is clean and no automated merge grant applies, confirm it is marked ready and waiting on human review.

### 3. Open questions and pending decisions

Check if progress is blocked on unanswered questions:

- **Unanswered questions asked of the user in this conversation:** If previous turns posed questions to the user that were never answered, recommend addressing the most blocking question (refer to [`prompt-me`](../prompt-me/SKILL.md) / `pm`).
- **Issues or PRs waiting on user decisions across the forge:** If tracker items are awaiting human input or design choices, recommend reviewing the top pending decision (refer to [`pending-decisions`](../pending-decisions/SKILL.md) / `pd`).

### 4. Active multi-task batch mandate

Check whether the current session is executing a multi-task mandate (such as `/gia`, `/gii`, `/gip`, or a prioritized backlog sweep):

```bash
gh issue list -R <owner>/<repo> --state open --limit 10
```

- If an overarching batch command is active, recommend claiming and implementing the next highest-priority issue from the queue under that mandate.

### 5. Session health and context budget

Inspect context usage and session depth:

- **Heavy context or long multi-turn session:** If the conversation transcript is very long, multiple large tasks have already completed in this session, or context compaction is near, recommend archiving the session:
  1. Verify working tree is clean and worktrees are swept.
  2. Run [`ums`](../ums/SKILL.md) to persist accumulated learnings.
  3. Provide a concise handoff summary.
  4. Recommend ending this session and starting a fresh session for the next task.

### 6. Clean baseline: select the next backlog task

If the local checkout is clean, 0 open PRs remain, and no active batch mandate is in flight, query open issues:

```bash
gh issue list -R <owner>/<repo> --state open --label "P1" --limit 5
gh issue list -R <owner>/<repo> --state open --label "P2" --limit 5
```

- Select the top P1 or P2 issue, summarize its scope, and recommend claiming and implementing it (`gi <number>`).
- If no high-priority issues exist, recommend wrapping up cleanly (`wrap-up`).

## Recommendation Categories

A recommendation produced by `whats-next` falls into one of three categories:

1. **Agent Action:** Work the agent should execute immediately under standing grants (e.g., "Implement issue #4363 in a dedicated worktree", "Address review feedback on PR #123", "Run UMS and wrap up").
2. **User Decision / Action:** Action required from the user before work can proceed (e.g., "Confirm preferred API syntax for feature X", "Review and merge external PR #456").
3. **Session Lifecycle:** Session boundary transitions (e.g., "Archive session and start fresh in a new conversation to reset context", "Wrap up and file follow-up issues").

## Relationship to other skills

- **[`status`](../status/SKILL.md):** Diagnoses stalls, dropped balls, unhandled tool errors, and reports current progress.
  `whats-next` is forward-looking: it synthesizes all signals to recommend what to do next.
- **[`next`](../next/SKILL.md):** Command queue modifier (`/next <task>` inserts a task immediately after the in-flight task).
  `whats-next` is a status and advisory inquiry.
- **[`prompt-me`](../prompt-me/SKILL.md) / [`pm`](../pm/SKILL.md):** Surfaces unanswered questions posed to the user in the current conversation.
- **[`pending-decisions`](../pending-decisions/SKILL.md) / [`pd`](../pd/SKILL.md):** Surfaces issues and PRs across the forge waiting on human decisions.
- **[`wrap-up`](../wrap-up/SKILL.md):** Executes end-of-session verification, worktree sweep, and UMS recording when work is finished.
- **[`rec`](../rec/SKILL.md):** General rule and skill for providing concrete recommendations alongside questions and choices.

## Anti-patterns

- **Don't present an uncurated menu:** Never list five possible tasks without recommending which one to do.
  Always declare: "I recommend X because Y."
- **Don't skip active work:** Never recommend grabbing a new issue from the backlog if an uncommitted edit, unpushed commit, or open PR is still active.
- **Don't ignore context exhaustion:**
  Never recommend taking on a massive new multi-file refactor in a session that has already consumed most of its context window.
  Instead, recommend archiving and restarting.
