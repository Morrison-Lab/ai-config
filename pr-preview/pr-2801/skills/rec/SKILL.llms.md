# rec — provide recommendations for choices and questions

Whenever posing a choice or asking a question to the user, always provide a clear, specific, and grounded recommendation. Never present an unweighted list of options or ask “what should I do?” without declaring your own recommended path.

This skill is invoked proactively before presenting decisions or questions, or reactively when the user invokes `/rec`, `/recommend`, or asks what the agent recommends after an unweighted question was asked.

## When this fires

- **Proactively**: whenever presenting options for a genuine decision, asking a clarifying or architectural question, or using interactive question modals (`AskUserQuestion` / `ask_user_question` / `ask_question`).
- **Reactively**:
  - Explicit invocation: `/rec`, `/recommend`, “recommend”, “rec”.
  - The user asks “what do you recommend?”, “what’s your recommendation?”, “which one should we pick?”, or “give me a recommendation”.
  - The agent previously asked a question without a recommendation and needs to supply one now.

## Core Rules

### 1. Always include a concrete recommendation

Never leave a decision or question open-ended without a recommended option. State the specific recommendation clearly (e.g., “Recommendation: Proceed with Option A because…”).

### 2. Interactive tools format: put recommendation first

When using interactive question tools (`AskUserQuestion`, `ask_user_question`, or `ask_question`): - Place the recommended option **first** in the options array. - Prefix the label with `(Recommended)` (e.g., `(Recommended) Option A: ...`).

### 3. Visual tagging in chat output

In conversational responses, format recommendations using the standard category box:

``` markdown
🧭 **RECOMMENDATION:** <action>. <concise rationale>
```

Lead with the specific action, followed by the trade-off rationale.

### 4. Do not offer authorized work as an optional choice

Distinguish genuine decisions from authorized or standard workflow steps: - If an action is already in scope or required by standing rules (e.g., running tests, fixing lints, ARDI loops, drafting issues), perform the work and report in the past tense rather than asking “Let me know if you want me to do X”. - Reserve recommendations for genuine forks in design, architecture, scope trade-offs, or external intent.

## Procedure

### Step 1 — Identify the choice or question

- **Proactive**: State the decision point, the context that makes it necessary, and the distinct feasible options.
- **Reactive** (`/rec` / `/recommend`): Scan back through recent conversation turns to locate the latest question or unresolved decision point, restating the options if context is needed.

### Step 2 — Evaluate trade-offs

Weigh the alternatives across: - **Simplicity and minimal blast radius**: least complex change that solves the issue. - **Project conventions**: alignment with existing codebase patterns and rules. - **Safety and reversibility**: lower operational and maintenance risk. - **Token and execution efficiency**: avoiding unnecessary overhead.

Select the single strongest path as the recommendation.

### Step 3 — Present the recommendation

Present the question or decision with its structured recommendation:

- **For interactive GUI modals** (`AskUserQuestion`, `ask_user_question`, or `ask_question`): List the recommended choice as option 1 with the `(Recommended)` prefix.
- **For inline chat questions**: State the context, outline the trade-offs, and attach the boxed recommendation:

``` markdown
❓ **QUESTION:** <clear question>

- **Option A**: <summary of option A and trade-offs>
- **Option B**: <summary of option B and trade-offs>

🧭 **RECOMMENDATION:** Proceed with Option A because <rationale>.
```

## Relationship to other skills and rules

- **`AGENTS.md` (“Always give recommendations with questions”)**: Universal baseline rule requiring recommendations on all questions.
- **[`prompt-me`](../../skills/prompt-me/SKILL.llms.md) / [`pm`](../../skills/pm/SKILL.llms.md)**: Surfaces pending questions; pair with `rec` if a surfaced question lacked a recommendation.
- **[`pending-decisions`](../../skills/pending-decisions/SKILL.llms.md) / [`pd`](../../skills/pd/SKILL.llms.md)**: Presents tracker-level decisions sequentially, with recommendations.
- **[`brainstorm`](../../skills/brainstorm/SKILL.llms.md)**: Interactive Socratic planning loop before implementation; uses `rec` principles to guide trade-offs.

## Anti-patterns

- ❌ Asking “Which option do you prefer?” or “Should I do A or B?” without declaring a recommendation.
- ❌ Using “Let me know if…” to pose authorized work as a choice instead of performing it.
- ❌ Providing an ambiguous or fence-sitting recommendation (“Either A or B is fine”).
- ❌ Placing the recommended option anywhere other than first in interactive choice lists.

Back to top
