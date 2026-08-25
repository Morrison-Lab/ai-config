---
name: select-model
description: "Select Claude model for task."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# select-model — Choose the right Claude model

Determine which Claude model (Fable 5, Haiku 4.5, Sonnet 4.6, or Opus 4.8) is
best for your task. Runs in **procedural mode** (decision tree reference) or
**executable mode** (analyze a task and recommend a model with optional config update).

## Procedure

### Model tiers at a glance

**Fable 5 / Opus 4.8 / Gemini Pro** (Tier 1: Conductor & Deep Reasoning)
- Highest reasoning depth, strategic planning, adversarial review
- Handles ambiguous requirements, complex architectural refactors, multi-step dependencies
- Best for: Orchestrator session conductor, adversarial self-review, subtle debugging, security analysis
- Strategy: Use for high-leverage judgment, planning, and final auditing

**Sonnet 5 / 4.6 / Gemini Flash / Codex** (Tier 2: High-Velocity Execution)
- Balanced: strong coding capability, fast execution, cost-effective
- Handles task execution, test generation, refactoring, boilerplate
- Best for: Subagent worker execution, feature implementation from clear specs, documentation
- Strategy: Delegate bounded implementation sub-tasks to maximize speed and token efficiency

**Haiku 4.5 / Gemini Flash-Lite** (Tier 3: Fast Verification & Scans)
- Speed + lightweight focused reasoning
- Best for: Simple queries, single-file regex/syntax checks, triage, shallow unit tests
- Limitations: Not suited for cross-file architecture or deep review

### Orchestrator-Worker Delegation Pattern

When orchestrating complex or multi-step work:
1. **Conductor (Tier 1):** Breaks down the objective into modular, bounded sub-tasks with strict checklists and unambiguous acceptance criteria.
2. **Workers (Tier 2/3):** Subagents execute bounded tasks with tight stop conditions (preventing open-ended token burns or side quests).
3. **Verification (Tier 1):** Conductor audits worker diffs and runs adversarial review before committing.

### Decision tree: Pick your model

1. **Is the task trivial or a fast scan?** (single query, shallow check)
   - YES → **Haiku 4.5 / Flash-Lite** (save cost)
   - NO → Continue

2. **Is the task bounded implementation from a clear spec?** (writing code, generating tests, refactoring)
   - YES → **Sonnet / Flash / Codex** (high-velocity executor)
   - NO → Continue

3. **Does the task require high-level orchestration, deep design, or adversarial review?** (architectural decisions, subtle bugs, security audit, orchestrator loop)
   - YES → **Fable 5 / Opus / Gemini Pro** (most capable)

### Task → Model mapping

| Task Category | Complexity | Recommended Tier | Rationale |
|---|---|---|---|
| Simple query / scan | ⭐ | Tier 3 (Haiku / Flash-Lite) | Minimal reasoning; speed matters |
| Code snippet / boilerplate | ⭐ | Tier 2 (Sonnet / Codex) | Fast and accurate generation |
| Bug fix (clear pattern) | ⭐ | Tier 2 (Sonnet / Flash) | Clear problem, straightforward fix |
| Refactor (bounded) | ⭐⭐ | Tier 2 (Sonnet / Flash) | Follows established architecture |
| Subagent execution | ⭐⭐ | Tier 2 (Sonnet / Flash / Codex) | High throughput, token efficient |
| Multi-file architecture | ⭐⭐⭐ | Tier 1 (Fable / Opus / Pro) | Needs high reasoning; conductor tier |
| Subtle bug hunt | ⭐⭐⭐ | Tier 1 (Fable / Opus / Pro) | Deep lateral reasoning required |
| Adversarial review | ⭐⭐⭐ | Tier 1 (Fable / Opus / Pro) | Strict verification against subtle issues |
| Orchestration & planning | ⭐⭐⭐ | Tier 1 (Fable / Opus / Pro) | Decomposes task DAGs with stop criteria |

### Model selection factors

- **Reasoning depth:** Tier 3 < Tier 2 < Tier 1
- **Code generation:** Tier 2 provides optimal throughput/cost balance; Tier 1 handles architectural nuance
- **Code review:** Tier 1 recommended for adversarial passes
- **Token efficiency:** Use Tier 1 for judgment and Tier 2/3 for generation

### Executable mode (auto-recommend and config update)

Instead of consulting the decision tree manually, invoke the skill with a task
description. The script will analyze complexity, check your current settings,
recommend the right model, and optionally suggest a config update:

```
/select-model --task "I need to refactor a critical payment module with security implications"
```

The script outputs a recommendation and optionally suggests updating `~/.claude/settings.json`
to use the recommended model for future sessions.

## How to use

- **Procedural mode (manual decision tree):** Read this procedure, follow the
  decision tree or task mapping, choose your model.
- **Executable mode (auto-recommend):** Invoke `/select-model --task "<task description>"`
  and the script provides a personalized recommendation and config suggestion.
- **Chained from assess-model-fit:** If `/assess-model-fit` recommends escalation,
  it auto-invokes `select-model` with your task details.

## FAQ

**Q: I'm using Haiku but it keeps failing. What now?**
A: Escalate to Sonnet or Opus. Use this skill to confirm the better tier for your task.

**Q: Opus is expensive. Can I use Sonnet instead?**
A: Yes, if your task doesn't need deep reasoning. Use the decision tree above to verify.
If unsure, try Sonnet first; if it struggles, escalate to Opus mid-session.

**Q: Should I always use the highest model?**
A: No—higher models are slower and costlier. Match the model to task complexity.
Use Haiku for simple work, Sonnet for medium, Opus for hard problems.

**Q: Can I pick a model manually without using this skill?**
A: Yes. This skill is advisory. You can always override and choose your own model.
