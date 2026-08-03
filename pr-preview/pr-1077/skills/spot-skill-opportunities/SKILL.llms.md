# spot-skill-opportunities — notice when work is skill-shaped

The recognition half of “always look for opportunities to create new reusable skills” (`memories/preferences.md`). `skill-builder` is the construction half — it scaffolds a skill once one is needed. This skill is what decides *that* one is needed, and it fires continuously, in the middle of ordinary work, not only at a session or PR-end checkpoint.

The same recognition applies one level down: if the emerging pattern is really a **dedicated, read-only fan-out worker** a heavy skill’s per-item step needs (not a new user-invocable workflow), hand off to `agent-builder` instead of `skill-builder`.

## When this fires

- You repeat a multi-step procedure you (or another session) already did earlier — in this conversation or a prior one recorded in memory.
- You improvise a workaround, diagnostic recipe, or decision framework that is clearly general enough to recur (not a one-off fix specific to this bug).
- The user says “again”, “like last time”, “we did this before”, “every time you…”, or gives a verbal standing rule (“always do X”) that isn’t yet backed by a skill.
- A review round (human or bot) surfaces the same correction more than once.
- As a standing checklist item inside `record-learnings` (continuous), `ums` (explicit checkpoint), `wrap-up` (session end), and `post-merge` (PR end) — those skills defer the recognition judgment call to this one.

## Procedure

1.  **Name the candidate pattern.** State in one sentence what the repeatable unit is (the trigger, the steps, the output) — if you can’t state it crisply, it probably isn’t skill-shaped yet.

2.  **Rule out one-off.** Would this plausibly recur across sessions, repos, or users of this config — or is it specific to this single task? Only the former is worth a skill. When in doubt, lean toward surfacing it anyway and let the user decide (see step 4).

3.  **Check it isn’t already covered.** Search for an existing skill, an in-flight branch, or an **open PR** before proposing a new one:

    ``` bash
    grep -ril "<keywords>" skills/*/SKILL.md
    ```

    (see [`check-open-prs-before-duplicating`](../../shared/workflow/check-open-prs-before-duplicating.md) for the PR check). If something already owns this concern, suggest extending it — or, if a PR is already building it, redirect to that PR — instead of proposing a new skill.

4.  **Surface the suggestion — don’t build silently.** Per the standing preference, *propose* creating the skill (or agent); don’t scaffold one unasked mid-task (that would derail the task at hand). The exception: when you’re already inside an explicit authoring context (mid-`ums`, mid-`skill-builder`, mid-`agent-builder`), hand off directly without waiting for user confirmation.

5.  **Hand off to the right builder.** A new user-invocable workflow goes to `skill-builder`; a dedicated read-only fan-out worker persona for an existing heavy skill goes to `agent-builder`. Once the user agrees (or the context already sanctioned it), let that skill do its own extend-first check and scaffolding — don’t duplicate its step 0 here.

## Relationship to other skills

- **`skill-builder`** — the construction step this hands off to. This skill never scaffolds a `SKILL.md` itself; it only recognizes the need and routes there.
- **`agent-builder`** — the construction step for the fan-out-worker case: when the recurring pattern is a dedicated read-only subagent for a heavy skill’s per-item step, rather than a new user-invocable workflow.
- **`record-learnings`** — passive and continuous like this skill, but covers the broader category of learnings (facts, tool quirks, preferences). Its “if it’s a skill, create it” step is this skill’s specific case.
- **`ums`** — the explicit checkpoint version. Its checklist item “did a workflow emerge that could be a new skill?” is this skill’s standing version, run continuously instead of only at the checkpoint.
- **`wrap-up` / `post-merge`** — session- and PR-level bookends that already embed a UMS pass looking for exactly this signal; this skill is what fires *during* the work, so the pattern is caught before the bookend rather than only at it.
- **`consolidate-skills` / `find-overlap`** — the cleanup counterparts for skills that already shipped and turned out to overlap; this skill tries to prevent that overlap from being created in the first place by checking for an existing owner before proposing a new skill.
- **`config-ai`** — the explicit, user-invoked counterpart: this skill proactively notices a skill/agent opportunity mid-task; `config-ai` is what fires when the user directly states a capability and doesn’t yet know (or care) whether it’s a skill, agent, memory, hook, or `gha` capability.

## Anti-patterns

- ❌ Proposing a skill for a genuinely one-off task with no plausible recurrence.
- ❌ Scaffolding a skill mid-task without surfacing the suggestion first — that derails the task at hand and skips the user’s call.
- ❌ Skipping the existing-skill check and proposing a near-duplicate.
- ❌ Only noticing the pattern at session end (`wrap-up`) instead of live, in the moment when the repetition first appears.
- ❌ Staying silent when a clear multi-step recipe repeats — the standing preference is to *always* surface it, not to wait to be asked.

Back to top
