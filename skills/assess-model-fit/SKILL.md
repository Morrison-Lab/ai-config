---
name: assess-model-fit
description: "Assess model fit for task."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# assess-model-fit — Evaluate current model capability

Determine whether the current Claude model is sufficient for your task, or recommend
escalation to a higher-level model.
Runs in **procedural mode** (checklist guidance)
or **executable mode** (analyze a task and auto-recommend).

## Procedure

### Assess model fit (manual, procedural mode)

1. **Identify the current model.** Check your session or settings.
   Common tiers:
   - Tier 1: Fable 5, Opus 4.8, Gemini Pro
   - Tier 2: Sonnet 5 / 4.6, Gemini Flash, Codex
   - Tier 3: Haiku 4.5, Gemini Flash-Lite

2. **Score your task against these criteria.** A task needs escalation or orchestrator-worker delegation if it hits any of these:
   - **Deep multi-step reasoning:** more than 5 logical steps, complex dependencies, or
     architectural design decisions
   - **Code review rigor:** assessing code for subtle bugs, security gaps, performance,
     or architectural issues (not just syntax)
   - **Large context window needed:** task involves many files, long documents, or
     substantial history to reason over
   - **Complex decomposition:** breaking down an ambiguous problem into sub-tasks and
     choosing the right approach (not following a clear spec)
   - **Uncertain scope:** task requirements are vague and need clarification by reasoning
   - **Novel problem:** no standard solution applies; requires creative or exploratory thinking

3. **Determine Orchestration Strategy:**
   - **Solo Executor (Tier 2/3):** The task is straightforward, bounded, well-specified, and single-purpose.
   - **Orchestrator + Worker Delegation (Tier 1 Conductor + Tier 2 Workers):** The task is large, multi-stage, or complex. Use Tier 1 to plan and decompose into tasks with strict stop conditions, spawn Tier 2 workers to implement, and audit before merging.
   - **Escalate Model:** If the current model struggles with reasoning or loops on a bug, escalate immediately to Tier 1.

4. **If escalation needed,** invoke `/select-model` to determine the target.
   Describe your task, and `select-model` will recommend the optimal tier and suggest
   a config update if desired.

### Executable mode (auto-analysis and auto-chaining)

Instead of running the checklist manually, invoke the skill with a task description.
The script will analyze the task, output an assessment, and if escalation is needed,
automatically call `select-model`:

```
/assess-model-fit --task "I need to refactor a large REST API module and add comprehensive unit tests"
```

The script reads your current model, evaluates the task complexity, and either gives
you a go-ahead or chains into `select-model` with your task details.

## How to use

- **Procedural mode (manual checklist):** Read this procedure, run through the
  scoring criteria, decide if escalation is needed.
- **Executable mode (auto-analysis):** Invoke `/assess-model-fit --task "<your task description>"`
  and let the script recommend a verdict and model.
- **When in doubt:** Use executable mode — it's faster and catches nuance the
  manual checklist might miss.
