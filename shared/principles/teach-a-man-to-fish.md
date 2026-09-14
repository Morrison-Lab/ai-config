# Teach a man to fish: help subagents do it themselves, never absorb their mistakes

When an agent, subagent, or assistant produces defective, incomplete, or misaligned work,
do not absorb the defect by quietly fixing it yourself.
Help the agent fix it itself:
send the correction back with the concrete finding,
the counterexample that broke it,
and the standard to meet.
Have the agent execute the repair and record the learning in its own memory or ledger.

## The illusion of quick manual patches

When supervising subagents,
patching small defects by hand creates an illusion of efficiency:
correcting a typo,
refining a regex,
or adjusting a flag directly feels faster than another round trip.
That calculation ignores the structural debt:
an uncorrected agent repeats the identical mistake across subsequent tasks,
and omitting the feedback loop prevents recording the failure class.
The operational mechanics and incident history are detailed in
[`improve-your-subagents`](../workflow/improve-your-subagents.md#send-the-correction-back-to-the-agent-never-absorb-it-yourself).

At the principle level,
absorbing mistakes trades sustainable capability for temporary convenience.
Teaching the agent to fish is building durable competence across four commitments:

1. **Re-dispatch with actionable feedback.**
   Provide the concrete counterexample or failing input,
   not an abstract adjective.
   Let the subagent make the edit.

2. **Require learning and ledger recording.**
   Ensure the correction round requires updating the agent's memory,
   skill instructions,
   or standing rules ledger.
   If an agent fixes code without recording the pattern and anti-pattern,
   the fix is incomplete.

3. **Provide deterministic infrastructure.**
   Equip subagents with deterministic checks,
   linters,
   test harnesses,
   and hooks.
   When an agent struggles with a rule,
   introduce an automated check so enforcement is mechanical rather than relying on LLM memory alone.

4. **Emergency pairing: never commit a manual fix alone.**
   When extraordinary operational constraints force an immediate manual repair,
   the fix and the standing brief update must land in the same commit.
   A manual fix without an accompanying rule or test addition leaves the system unimproved.

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
