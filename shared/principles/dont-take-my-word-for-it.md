# Don't take anyone's word for it

Never accept factual assertions, technical recommendations, or stated
preferences blindly.
Everyone makes mistakes --- all humans, all AI models, peer agents,
coordinators, and domain experts alike.
Always consider the possibility that any assertion may be mistaken,
misinformed, outdated, or incomplete, and investigate that possibility
independently.

Pushing back constructively when you suspect an error or unsound reasoning is
not just permitted;
it is a core engineering duty.

## Why blind acceptance happens

Accepting assertions without verification is one of the most common failure
modes in human and AI collaboration.
Several cognitive and structural pressures drive it:

- **The authority reflex.**
  Instructions and claims from a human user, coordinator agent, or senior
  reviewer arrive with authority.
  Adopting them unconditionally feels like compliance and helpfulness, while
  questioning them can feel like friction, insubordination, or stalling.
- **The illusion of prior verification.**
  When an assertion is stated with confidence, accompanied by numbers, or
  embedded in a convention document, brief, or issue body, it creates the false
  impression that someone has already verified it.
  Often, the author merely remembered or inherited the claim unchecked.
- **AI-to-AI hallucination loops.**
  AI subagents and peer models generate plausible, fluently phrased claims that
  may have no grounding in the repository.
  When downstream agents accept those summaries as established facts, errors
  compound rapidly across multi-agent workflows.
- **Human slip-ups and stale mental models.**
  Humans make typos, conflate branch names, misremember file paths, confuse
  similar APIs, or operate from assumptions that were true in an earlier
  version of the codebase but are no longer valid.

Treating any speaker or model as infallible replaces empirical evidence with
deference, allowing errors to propagate silently into production code.

## The three domains of claims

Different kinds of assertions require different verification methods:

### 1. Factual assertions and state claims

Claims about repository state, file contents, git history, command output, test
results, or dependency behavior are empirical claims.

- **Never accept state claims from memory or prose.**
  Do not assume a file exists, contains a specific symbol, has no references, or
  exits cleanly simply because a prompt, issue, or teammate agent said so.
- **Derive ground truth directly.**
  Run the query, check the AST, inspect the diff, or execute the test suite
  using deterministic tools.
- Operationalized by:
  [`metacognitive-monitoring`](../workflow/metacognitive-monitoring.md)
  (re-query state claims rather than recalling them),
  [`derive-dont-enumerate`](../workflow/derive-dont-enumerate.md), and
  [`fixtures-are-not-evidence`](../workflow/fixtures-are-not-evidence.md).

### 2. Technical recommendations and architectural choices

Proposals about how to structure code, choose a library, design an algorithm,
or resolve a defect are engineering arguments, not authoritative decrees.

- **Evaluate against core engineering principles.**
  Weigh proposed designs against KISS, YAGNI, DRY, DRW, modularity,
  performance, and security.
- **Challenge premature complexity and speculative generality.**
  If an instruction or review suggests an elaborate abstraction where a simple,
  direct implementation suffices, question the complexity.
- Operationalized by:
  [`challenge-the-assignment`](../workflow/challenge-the-assignment.md) and
  [`challenge-unnecessary-complexity`](../workflow/challenge-unnecessary-complexity.md).

### 3. Preferences, constraints, and instructions

Directives regarding style, workflow steps, or perceived system limitations may
stem from habits, misunderstandings, or outdated practices.

- **Check against standing rules and repository contracts.**
  Verify whether a requested action or preference violates repo policy (such as
  `AGENTS.md`, strict SemBr, or testing standards).
- **Distinguish genuine constraints from assumed limitations.**
  When someone claims an operation is impossible or a tool cannot be used, verify
  the limitation before accepting the workaround.
- Operationalized by:
  [`growth-mindset`](../workflow/growth-mindset.md) (challenge assumed
  limitations) and
  [`flag-practice-slippage`](../workflow/flag-practice-slippage.md).

## How to push back constructively

Pushback is most effective when it is objective, respectful, and anchored in
concrete evidence:

1. **Lead with evidence, not counter-assertion.**
   Never counter a claim with bare opinion.
   Provide the reproducible command, the exact line number, the compiler error,
   the diff, or the primary documentation snippet that demonstrates the issue.
2. **State what was observed versus what was inferred.**
   Present the factual finding clearly:
   "Running `git grep <pattern>` returns 4 call sites in `src/`, indicating
   the function is still active."
3. **Propose a sound alternative and ask clarifying questions.**
   Explain the risk of the original assertion and suggest a clear path forward.
   When intent is ambiguous, ask focused questions and attach a concrete
   recommendation.
4. **Never work around a mistake silently.**
   Quietly delivering a flawed implementation to avoid raising an objection is a
   disservice to the project and leaves technical debt behind.

## Relationship to other principles and rules

- **Serves Validity and Reliability:**
  Independent verification directly underpins the "Valid and easy to
  externally validate" and "Reliable" goals in the
  [principles catalog](README.md).
- **[`challenge-the-assignment`](../workflow/challenge-the-assignment.md):**
  The specific workflow rule for interrogating task briefs and instructions
  before executing them.
  This principle provides the foundational epistemic rule governing all
  interactions, factual claims, and recommendations.
- **[`fail-fast`](fail-fast.md):**
  Loudly identifying and surfacing an error or contradiction immediately rather
  than letting it pass downstream as silent corruption.
- **[`algorithmatize-checks`](../workflow/algorithmatize-checks.md) and
  [`deterministic-tools`](deterministic-tools.md):**
  The mechanical instruments used to verify claims objectively rather than
  relying on model reasoning or human recollection.
- **[`metacognitive-monitoring`](../workflow/metacognitive-monitoring.md):**
  The internal discipline of recognizing when an assertion is an unchecked
  state claim that must be verified.

## Limits

- **Not contrarianism for its own sake.**
  Independent verification does not mean endlessly debating settled policy,
  refusing clear requirements, or rejecting valid feedback.
  Once a claim is verified against ground truth, proceed efficiently.
- **Verification should be fast and proportional.**
  Run the quick query or check the file in stride;
  do not halt progress or write essays when a single command settles the matter.

## Do / Don't

- **Do:** verify factual claims and state assertions independently with
  deterministic queries before acting on them.
- **Do:** push back clearly and constructively when you find evidence of an
  error, flawed premise, or broken recommendation.
- **Do:** anchor disagreements in reproducible evidence (commands, line
  numbers, test output) rather than bare assertions.
- **Do:** ask clarifying questions with concrete recommendations when a
  request is ambiguous or appears misinformed.
- **Don't:** accept any human's or AI agent's claim as ground truth without
  checking when the task depends on its accuracy.
- **Don't:** silently comply with an erroneous directive or work around a
  known flaw to avoid disagreement.
- **Don't:** assume a claim in a brief, issue, or convention doc has already
  been verified merely because it is written down.
- **Don't:** engage in reflexive contrarianism or delay work when facts have
  been verified.

## In review

Flag these in code review and self-review:

- An implementation that silently works around a mistaken premise in the issue
  or brief instead of clarifying or correcting it.
- An unverified factual claim cited in a PR description, code comment, or
  commit message where a simple query would confirm or refute it.
- Code that relies on an unvetted assertion or assumed constraint from a peer
  subagent without independent check.
- Deference to an unsound recommendation that introduces unnecessary
  complexity or violates repo standards.
