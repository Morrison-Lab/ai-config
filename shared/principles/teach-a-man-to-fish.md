# Teach a man to fish: help subagents do it themselves, never absorb their mistakes

When an agent, subagent, or assistant produces defective, incomplete, or misaligned work,
do not absorb the defect by quietly fixing it yourself.
Help the agent fix it itself:
send the correction back with the concrete finding,
the counterexample that broke it,
and the standard to meet.
Have the agent execute the repair and record the learning in its own memory or ledger.

## The one-minute trap

When an orchestrator reviews a subagent's work and notices a small defect,
the immediate temptation is to fix it directly.
The defect is often minor:
a one-line syntax fix,
an incomplete regex,
a slightly misaligned argument,
a commit message variable expansion,
or a missed edge case.
The internal calculation feels straightforward:
fixing the line directly takes one minute,
whereas re-dispatching the subagent with feedback takes twenty minutes or an extra round trip.

That calculation is illusory.
The minute saved is paid immediately,
but the saving is false:
the subagent never learned the rule,
its prompt and standing rules were not updated,
and the mistake class was never recorded.
On the next dispatch,
and on every subsequent task,
the agent will make the exact same error,
and the orchestrator will spend another minute fixing it by hand.

The cost of absorbing a mistake is not the single fix.
The cost is every future instance of the class,
plus the permanent maintenance burden on the orchestrator.

## Teach rather than absorb

Follow the classic principle:
"give a man a fish and you feed him for a day;
teach a man to fish and you feed him for a lifetime."
In agentic workflows,
absorbing mistakes is giving a fish.
Teaching the agent to fish is building durable competence:

1. **Re-dispatch with actionable feedback.**
   Do not just tell the subagent that its output was wrong or low-quality.
   State the exact finding,
   provide the concrete counterexample or test input that failed,
   and specify the precise standard to satisfy.
   Let the subagent make the edit.

2. **Require learning and ledger recording.**
   When a subagent makes an avoidable mistake,
   ensure the correction round requires updating the agent's memory,
   skill instructions,
   or standing rules ledger.
   If an agent fixes the bug without recording the pattern and anti-pattern,
   the fix is incomplete.

3. **Provide deterministic infrastructure.**
   Help subagents succeed by equipping them with deterministic checks,
   linters,
   test harnesses,
   and hooks.
   When an agent struggles with a rule,
   ask whether an automated check can prevent the mistake mechanically rather than relying on LLM memory alone.

4. **The emergency exception: fix and update in one commit.**
   On the rare occasion where strict time or operational limits genuinely prevent an extra dispatch round,
   the fix and the standing rule update must land together.
   Write the rule into the agent's standing prompt,
   memory,
   or hooks in the very same commit that carries the hand-applied fix.
   Never commit the fix alone.

## In development and review

- **In orchestration and delegation:**
  Treat the impulse to "just clean this up quickly before pushing" as a warning signal.
  If a subagent wrote the code,
  send the diff back with instructions.
  Do not become a manual cleanup worker for subagents.
- **In code review:**
  Verify that agent fixes are accompanied by updated prompts,
  standing rules,
  or automated tests.
  Flag PRs where an orchestrator repeatedly patches over subagent errors without improving the subagent's brief or tools.

## Relation to other principles

- **Complements Don't Incur Technical Debt** ([`dont-incur-technical-debt`](dont-incur-technical-debt.md)):
  Absorbing an agent's mistake is taking on unrecorded technical debt.
  Teaching the agent pays the debt immediately.
- **Complements Automate Everything** ([`deterministic-tools`](deterministic-tools.md)):
  Equipping subagents with automated linters and hooks turns human and orchestrator corrections into permanent deterministic instruments.
- **Operationalized by:**
  [`improve-your-subagents`](../workflow/improve-your-subagents.md#send-the-correction-back-to-the-agent-never-absorb-it-yourself)
  (the workflow procedure)
  and [`use-subagents`](../workflow/use-subagents.md).
