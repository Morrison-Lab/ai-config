---
name: recm
description: "Recommend harness, provider, model, and engine for a repo or task."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
---

# recm --- Recommend Harness, Provider, Model, and Engine

Determine the optimal execution environment (harness CLI or IDE),
billing provider tier, model capability,
and review engine for a repository, issue, or task.
Aliases: [`rech`](../rech/SKILL.md) (recommend harness),
[`rechme`](../rechme/SKILL.md) (recommend harness/model/engine).

This skill synthesizes task shape, token budget, tool requirements,
deterministic testability, and data sensitivity into an actionable recommendation.

## When this fires

- "recommend a harness", "recommend a model", "recommend an engine", "recm", "rech", "rechme".
- When sizing a new repository, major feature, or complex issue to determine the most cost-effective and capable execution stack.
- Proactively before kicking off heavy tasks to decide between inline execution, subagent fan-out, sidecar CLI delegation, or multi-engine review.

## The 5 Dimensions of Recommendation

Selecting the right stack requires evaluating five distinct axes:

```
                      ┌────────────────────────────────────────┐
                      │             TASK / ISSUE               │
                      └───────────────────┬────────────────────┘
                                          │
        ┌───────────────────┬─────────────┴───────┬────────────────────┐
        ▼                   ▼                     ▼                    ▼
 1. Harness / CLI     2. Provider Tier     3. Model Tier        4. Review Engine
(Claude Code, agy,    (Free Hosted,        (Tier 1 Conductor,   (Sonnet 4.6, adv,
 Codex, OpenCode,     Subscription Window,  Tier 2 Worker,       Cross-family
 Cursor, adv)         Prepaid, Claude)      Tier 3 Scan)         subagent)
        ▲                   ▲                     ▲                    ▲
        └───────────────────┴─────────────┬───────┴────────────────────┘
                                          │
                      ┌───────────────────┴────────────────────┐
                      │    5. Governing Policy Guards          │
                      │  - Ban on local/on-device inference    │
                      │  - No LLM algorithmic thinking         │
                      │  - Data sensitivity overrides          │
                      └────────────────────────────────────────┘
```

---

### Dimension 1: Harness & CLI Selection

Choose the primary interactive harness or non-interactive sidecar CLI based on repo integration and workflow needs:

| Harness / CLI | Primary Role | Ideal Workload | Key Invocation & Nuance |
|---|---|---|---|
| **Claude Code** | Primary Orchestrator & Conductor | Multi-turn reasoning, project context closure, git workflows, subagent management | Interactive terminal CLI; manages workflows and tool execution. |
| **Antigravity / Gemini CLI (`agy`)** | DeepMind Ecosystem Harness & Sidecar | Antigravity plugins/skills discovery (`plugins/ai-config`), interactive UI, headless sidecar | Headless: `agy --print "<prompt>"`. **Note**: API route retired; CLI available. Keep prompt immediately after `--print`. |
| **Codex CLI (`codex`)** | Mechanical Sidecar Executor | Heavy parallelizable read/draft/verify, bounded implementation from clear specs | `codex exec -C <repo> -s read-only --skip-git-repo-check - < prompt.txt`. Sunk ChatGPT plan (~5h window). |
| **OpenCode CLI (`opencode`)** | Zero-Cost & Multi-Provider Sidecar | Mechanical edits with deterministic test suites, OpenRouter stealth previews | `opencode run -m <id>`. Free hosted tier (`opencode/*`) & Zen, or `$10/mo` Go window. |
| **Cursor / VS Code** | Interactive Editor & Visual IDE | Interactive human editing, real-time typing autocomplete, visual diff navigation | IDE harness; probe CLI automation before relying on headless runs. |
| **`adv` / `pre-push-review.py`** | Multi-Engine Review Harness | Adversarial self-review across diverse model families prior to pushing code | Dedicated review dispatch runner (`adv` skill). |

---

### Dimension 2: Provider Tier & Budget Ladder

Apply the standing quota optimization rule: **spend CLI-reachable free tiers and subscription windows before consuming orchestrator/Claude budget.**

1. **Tier A: Hosted Free (`opencode/*` hosted-free & Zen)**
   - *Cost*: $0, no usage window to exhaust.
   - *Best For*: Well-specified, mechanical edits and boilerplate where a deterministic test suite verifies correctness.
   - *Rule*: Goes ahead of metered subscription windows when capability and tooling suffice.
2. **Tier B: Metered Subscription Windows (`codex`, `agy` CLI, `opencode-go/*`)**
   - *Cost*: Sunk cost within the current usage window (e.g. Codex ~5h window, OpenCode Go $10/mo window).
   - *Best For*: Heavy read fan-outs, multi-file auditing, drafting N artifacts, bounded implementation briefs.
   - *Rule*: Exhaust current subscription window before falling back to Claude tokens.
3. **Tier C: Prepaid Credit Balance (`openrouter/*`)**
   - *Cost*: Pay-per-token draw on prepaid balance.
   - *Best For*: Frontier stealth previews and capable models when free and windowed tiers are exhausted.
4. **Tier D: Orchestrator Claude Tiers (Haiku 4.5, Sonnet 4.6, Opus 4.8 / Fable 5)**
   - *Cost*: Direct API / session token quota.
   - *Best For*: Conductor orchestration, complex judgment, ambiguous design, adversarial review.
   - *Rule*: Conserve orchestrator budget by delegating bounded sub-tasks to Tiers A–B.

---

### Dimension 3: Model Capability & Task Complexity

Match model intelligence to the intrinsic reasoning depth required:

| Model Tier | Representative Models | Reasoning Depth | Best For |
|---|---|---|---|
| **Tier 1: Conductor & Deep Reasoning** | Claude Opus 4.8, Claude Fable 5 | Highest | Orchestrator conductor, architectural design, subtle debugging, security audits, ambiguous spec decomposition. |
| **Tier 2: High-Velocity Execution & Review** | Claude Sonnet 4.6, GPT-5 / Codex | Strong & Fast | Subagent worker implementation, bounded refactoring, test suite generation, adversarial code review. |
| **Tier 3: Fast Scans & Lightweight Verification** | Claude Haiku 4.5, Nemotron Free | Fast & Focused | Shallow triage, single-file regex/syntax checks, simple queries, boilerplate with mechanical verification. |

---

### Dimension 4: Review Engine Selection

Adversarial self-review is governed by **independence-first**, not cost-first:

- **Primary Review Engine**: Claude Sonnet 4.6 (or Opus 4.8 for critical security/architectural changes).
- **Cross-Family Verification**: Codex or `agy` CLI pointing at Claude-generated diffs to eliminate shared blind spots.
- **Local Multi-Engine Review**: Dispatch via [`adv`](../adv/SKILL.md) (`pre-push-review.py`).

---

### Dimension 5: Governing Policy Constraints & Overrides

Always enforce these strict repository principles:

1. **Local Inference Prohibited**:
   - **Never** run Ollama, LM Studio, llama.cpp, or on-device local models.
   - Local inference can crash the user's computer.
   - "Local" strictly means *reachable through this computer's CLI* (hosted/cloud models), not running on local hardware.
2. **No LLM Algorithmic Thinking**:
   - **Never** rely on LLM probabilistic reasoning for counting, sorting, arithmetic, regex verification, math derivations, or AST linting.
   - Always use validated deterministic software (e.g. Python scripts, `grep -c`, `wc -l`, SymPy, R, formal linters).
3. **Data Sensitivity Overrides Cost**:
   - Hosted CLIs (`codex`, `agy`, `opencode`) send payloads off-machine.
   - When handling confidential, restricted, or unapproved data, keep work in the local orchestrator session using deterministic tools (a data trigger overrides cost ladder exceptions).

---

## Step-by-Step Decision Procedure

When evaluating a repository, issue, or task, follow these steps:

### Step 1: Check Data Sensitivity & Repository Boundaries
- Does the repository or task touch restricted, private, or sensitive data?
  - **YES** → Keep work in the local orchestrator session;
    do not dispatch off-machine to third-party hosted CLIs unless explicitly approved.
    Use deterministic tools.
  - **NO** → Proceed to Step 2.

### Step 2: Check Deterministic Testability & Task Shape
- Is the task an algorithmic or deterministic calculation (counting lines, sorting, regex validation, math)?
  - **YES** → Write and run a deterministic script (Python/Bash/R);
    do not delegate to an LLM.
- Is the task a heavy, parallelizable read / audit / draft of multiple files?
  - **YES** → Route to sidecar CLI (`codex` or `opencode` free) via [`delegate-to-codex`](../delegate-to-codex/SKILL.md) or [`delegate-to-opencode`](../delegate-to-opencode/SKILL.md).
- Is the task a bounded implementation from a clear spec with an automated test suite?
  - **YES** → Route to `opencode` free hosted tier or `codex` window.
- Does the task require ambiguous requirements resolution, deep architecture, or orchestration?
  - **YES** → Use Tier 1 / Tier 2 in Claude Code (Orchestrator).

### Step 3: Check Quota & Metered Windows
- Is `opencode` hosted-free tier suitable and verified? → Use `opencode` free.
- Is the `codex` ChatGPT plan window (~5h) available? → Delegate via `codex exec`.
- Is the `agy` CLI window available? → Delegate via `agy --print`.
- Are subscription windows exhausted? → Fall back to Claude Code (Haiku for scans, Sonnet for subagents, Opus for conductor).

### Step 4: Select Adversarial Review Engine
- Use [`adv`](../adv/SKILL.md) / Sonnet 4.6 subagent for pre-push review against `git diff origin/<default-branch>...HEAD`.

---

## Quick Reference Matrix

| Scenario / Task Type | Recommended Harness | Provider Tier | Recommended Model | Review Engine |
|---|---|---|---|---|
| **Orchestrator Conductor / Complex Architecture** | Claude Code | Direct Claude | Opus 4.8 / Fable 5 | Sonnet 4.6 Subagent |
| **Bounded Code Implementation (with test suite)** | Codex CLI / Claude Code | ChatGPT Window / OpenCode Free | Codex / Sonnet 4.6 | `adv` / Sonnet 4.6 |
| **Heavy Fan-out File Audit / Backlog Scoping** | Codex CLI / OpenCode | Free Hosted / ChatGPT Window | Nemotron Free / Codex | Orchestrator Conductor |
| **Mechanical Refactor / Boilerplate Generation** | OpenCode CLI | Free Hosted Tier | OpenCode Free | Test Suite + Sonnet |
| **Fast Syntax / Link / Triage Scans** | Claude Code | Direct Claude | Haiku 4.5 | Deterministic Lint |
| **Restricted / Sensitive Data Analysis** | Claude Code | Local Session Only | Approved Model | Deterministic Scripts |
| **Antigravity Plugin / Extension Integration** | Antigravity / Gemini CLI | DeepMind Ecosystem | Gemini Pro | Sonnet 4.6 |

---

## Relationship to Other Skills

- **[`select-model`](../select-model/SKILL.md)**: Focuses narrowly on choosing among Claude model tiers (Fable, Haiku, Sonnet, Opus).
- **[`assess-model-fit`](../assess-model-fit/SKILL.md)**: Assesses whether the active model tier is struggling and warrants escalation.
- **[`delegate-to-codex`](../delegate-to-codex/SKILL.md) (`dtc`)**: Operationalizes background dispatch, schema enforcement, and fallback mechanics for Codex.
- **[`delegate-to-opencode`](../delegate-to-opencode/SKILL.md) (`dto`)**: Operationalizes dispatch to OpenCode free, Go, and OpenRouter tiers.
- **[`adv`](../adv/SKILL.md)**: Operationalizes multi-engine adversarial code review prior to pushing.
