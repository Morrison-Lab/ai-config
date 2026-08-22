# select-model — Choose the right Claude model

Determine which Claude model (Fable 5, Haiku 4.5, Sonnet 4.6, or Opus 4.8) is best for your task. Runs in **procedural mode** (decision tree reference) or **executable mode** (analyze a task and recommend a model with optional config update).

## Procedure

### Model tiers at a glance

**Fable 5** (`claude-fable-5`) - Fastest, lowest cost - Minimal reasoning, narrow focus - Best for: Trivial tasks, high-volume throughput, cost optimization - Not recommended for: Complex reasoning, multi-step planning, code review

**Haiku 4.5** (`claude-haiku-4-5-20251001`) - Speed + focused reasoning - Handles simple queries and straightforward code tasks - Best for: Simple Q&A, basic code generation, narrow-scope work - Limitations: Shallow reasoning (1–2 steps), limited code review depth

**Sonnet 4.6** (`claude-sonnet-4-6`) - Balanced: good reasoning + acceptable speed - Handles multi-step tasks and moderate code review - Best for: Multi-step problem solving, code review (medium rigor), refactoring, multi-file tasks - Limitations: Not ideal for deep architectural design or subtle security analysis

**Opus 4.8** (`claude-opus-4-8`) - Deepest reasoning, most thorough analysis - Excels at design, complex decomposition, sophisticated code review - Best for: Complex architecture, multi-file refactors with design decisions, R&D, subtle bugs - Trade-off: Slower, higher cost (justified for hard problems)

### Decision tree: Pick your model

1.  **Is the task trivial?** (single query, no reasoning)
    - YES → **Fable 5** (save cost)
    - NO → Continue
2.  **Does the task fit in a narrow scope?** (single file, simple logic, \<5 steps)
    - YES → **Haiku 4.5** (fast, focused)
    - NO → Continue
3.  **Does the task involve multi-step reasoning or moderate complexity?** (refactoring, multi-file changes, moderate code review)
    - YES → **Sonnet 4.6** (balanced tier)
    - NO → Continue
4.  **Does the task require deep reasoning, sophisticated design, or rigorous review?** (architecture, complex refactor, subtle bugs, security analysis)
    - YES → **Opus 4.8** (most capable)

### Task → Model mapping

| Task Category | Complexity | Recommended | Rationale |
|----|----|----|----|
| Simple query | ⭐ | Fable or Haiku | Minimal reasoning; speed matters |
| Code snippet gen | ⭐ | Haiku | Straightforward; Haiku is fast enough |
| Bug fix (obvious) | ⭐ | Haiku | Clear problem, known fix pattern |
| Refactor (small scope) | ⭐⭐ | Haiku or Sonnet | If single file + clear pattern → Haiku; else → Sonnet |
| Multi-file refactor | ⭐⭐ | Sonnet | Needs coordination across files; Sonnet handles this well |
| Moderate code review | ⭐⭐ | Sonnet | Checks logic, style, obvious bugs |
| Complex refactor | ⭐⭐⭐ | Sonnet or Opus | If risky or touches architecture → Opus |
| Architecture design | ⭐⭐⭐ | Opus | Needs deep reasoning; Opus’s strength |
| Subtle bug hunt | ⭐⭐⭐ | Opus | Requires deep analysis, lateral thinking |
| Security review | ⭐⭐⭐ | Opus | Risk of missing subtle vulns with lower models |
| Research/exploration | ⭐⭐⭐ | Opus | Ambiguous scope; Opus excels at decomposition |

### Model selection factors

- **Context window:** All models have large windows, but Opus handles complex multi-file reasoning best
- **Reasoning depth:** Fable \< Haiku \< Sonnet \< Opus (in that order)
- **Code generation:** Haiku and Sonnet both strong; Opus overkill for boilerplate
- **Code review:** Haiku weak at subtle issues; Sonnet good; Opus best
- **Multi-step planning:** Haiku struggles; Sonnet solid; Opus excellent
- **Speed:** Fable \> Haiku \> Sonnet \> Opus (tradeoff with capability)
- **Cost:** Fable \< Haiku \< Sonnet \< Opus

### Executable mode (auto-recommend and config update)

Instead of consulting the decision tree manually, invoke the skill with a task description. The script will analyze complexity, check your current settings, recommend the right model, and optionally suggest a config update:

    /select-model --task "I need to refactor a critical payment module with security implications"

The script outputs a recommendation and optionally suggests updating `~/.claude/settings.json` to use the recommended model for future sessions.

## How to use

- **Procedural mode (manual decision tree):** Read this procedure, follow the decision tree or task mapping, choose your model.
- **Executable mode (auto-recommend):** Invoke `/select-model --task "<task description>"` and the script provides a personalized recommendation and config suggestion.
- **Chained from assess-model-fit:** If `/assess-model-fit` recommends escalation, it auto-invokes `select-model` with your task details.

## FAQ

**Q: I’m using Haiku but it keeps failing. What now?** A: Escalate to Sonnet or Opus. Use this skill to confirm the better tier for your task.

**Q: Opus is expensive. Can I use Sonnet instead?** A: Yes, if your task doesn’t need deep reasoning. Use the decision tree above to verify. If unsure, try Sonnet first; if it struggles, escalate to Opus mid-session.

**Q: Should I always use the highest model?** A: No—higher models are slower and costlier. Match the model to task complexity. Use Haiku for simple work, Sonnet for medium, Opus for hard problems.

**Q: Can I pick a model manually without using this skill?** A: Yes. This skill is advisory. You can always override and choose your own model.

Back to top
