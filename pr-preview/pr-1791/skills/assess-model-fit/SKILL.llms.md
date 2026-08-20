# assess-model-fit — Evaluate current model capability

Determine whether the current Claude model is sufficient for your task, or recommend escalation to a higher-level model. Runs in **procedural mode** (checklist guidance) or **executable mode** (analyze a task and auto-recommend).

## Procedure

### Assess model fit (manual, procedural mode)

1.  **Identify the current model.** Check your Claude Code session or settings.json. Common models: Fable 5 (`claude-fable-5`), Haiku 4.5 (`claude-haiku-4-5-20251001`), Sonnet 4.6 (`claude-sonnet-4-6`), Opus 4.8 (`claude-opus-4-8`).

2.  **Score your task against these criteria.** A task needs escalation (higher model) if it hits any of these red flags:

    - **Deep multi-step reasoning:** more than 5 logical steps, complex dependencies, or architectural design decisions
    - **Code review rigor:** assessing code for subtle bugs, security gaps, performance, or architectural issues (not just syntax)
    - **Large context window needed:** task involves many files, long documents, or substantial history to reason over
    - **Complex decomposition:** breaking down an ambiguous problem into sub-tasks and choosing the right approach (not following a clear spec)
    - **Uncertain scope:** task requirements are vague and need clarification by reasoning
    - **Novel problem:** no standard solution applies; requires creative or exploratory thinking

3.  **Make a go/no-go decision:**

    - **Current model is adequate** if:
      - Task is straightforward, well-specified, and mostly single-purpose
      - Reasoning is shallow (1–3 steps) and the path is clear
      - Code generation or simple Q&A, not deep review or design
      - Context is small (single file, short query)
    - **Escalate to higher model** if you checked yes on any red flag above

4.  **If escalation needed,** invoke `/select-model` to determine the target. Describe your task, and `select-model` will recommend Sonnet or Opus and suggest a config update if you want it.

### Executable mode (auto-analysis and auto-chaining)

Instead of running the checklist manually, invoke the skill with a task description. The script will analyze the task, output an assessment, and if escalation is needed, automatically call `select-model`:

    /assess-model-fit --task "I need to refactor a large REST API module and add comprehensive unit tests"

The script reads your current model, evaluates the task complexity, and either gives you a go-ahead or chains into `select-model` with your task details.

## How to use

- **Procedural mode (manual checklist):** Read this procedure, run through the scoring criteria, decide if escalation is needed.
- **Executable mode (auto-analysis):** Invoke `/assess-model-fit --task "<your task description>"` and let the script recommend a verdict and model.
- **When in doubt:** Use executable mode — it’s faster and catches nuance the manual checklist might miss.

Back to top
