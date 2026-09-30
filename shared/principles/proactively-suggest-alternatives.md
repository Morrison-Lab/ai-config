# Proactively suggest better alternatives to proposed approaches

When asked to accomplish a goal using a specific approach,
suggest a better alternative if one exists.
Do not treat the proposed mechanism as an immutable requirement
when another path reaches the same objective more simply, cleanly,
or reliably.

The user's standing principle:
"if there's another way to accomplish the same goal,
I'm always open to suggestions"
(user directive, Issue #4095).

## Goal vs. mechanism

Every assignment or prompt contains two components,
often intertwined:
1. **The goal**: the desired end state, capability, invariant,
   or problem to solve.
2. **The mechanism**: the specific implementation path, tool,
   data structure, or workflow proposed to reach that goal.

The failure mode is anchoring on the mechanism.
When a user, issue, or prompt specifies a mechanism
(e.g., "let's write a custom script to parse X",
"let's add a wrapper function in every module",
or "let's use tool Y to poll Z"),
an agent's compliance reflex frequently treats that mechanism
as an unbending constraint.
The agent implements the requested mechanism directly,
even when it is needlessly complex, brittle, or reinventing the wheel.

A helpful pair programmer distinguishes the underlying goal
from the proposed mechanism.
If you know or discover an approach that accomplishes the exact same goal
with less code, fewer moving parts, lower maintenance overhead,
or by using existing upstream tools,
you owe it to the project to proactively suggest and evaluate that alternative.

## When an alternative is better

An alternative is worth suggesting when it offers a concrete advantage
along one or more established engineering dimensions:

1. **Reuses existing tools and libraries (DRW / upstream)**:
   The proposed approach writes custom code for something already provided
   by a standard library, built-in CLI flag, or dependable upstream package
   (see [`dont-reinvent-wheel`](dont-reinvent-wheel.md)
   and [`prefer-upstream`](../../skills/prefer-upstream/SKILL.md)).
2. **Simpler and lower maintenance (KISS / YAGNI)**:
   The proposed approach introduces an elaborate multi-layer abstraction,
   a configuration system for variation that does not exist,
   or extraneous moving parts when a direct, minimal construct suffices
   (see [`challenge-unnecessary-complexity`](../workflow/challenge-unnecessary-complexity.md)).
3. **More idiomatic and standard (least astonishment)**:
   The proposed approach fights the conventions of the host language,
   framework, or toolchain, whereas the alternative follows standard idioms.
4. **More robust and less error-prone (fail fast / reliability)**:
   The proposed approach has known edge cases, race conditions,
   or silent failure modes that the alternative avoids by design.
5. **Systemic rather than ad-hoc**:
   The proposed approach patches one symptom in one file,
   whereas the alternative fixes the underlying invariant or installs
   an automated mechanical guard
   (see [`prefer-systemic-solutions-over-one-off-fixes`](prefer-systemic-solutions-over-one-off-fixes.md)).

## How to suggest an alternative constructively

Do not dismiss the proposed approach or debate vaguely in the abstract.
Follow a structured, constructive presentation:

1. **Acknowledge and restate the goal**:
   Show that you understand the desired outcome
   (e.g., "The goal is to ensure all output files are encoded in UTF-8").
2. **State the proposed approach and its tradeoffs**:
   Briefly name what the suggested approach does and its concrete cost
   (e.g., "Adding manual encoding checks across every individual script
   requires repetitive boilerplate and risks missing future additions").
3. **Present the concrete alternative**:
   Show the cleaner, simpler, or upstream equivalent with an actual code
   or command snippet, rather than a hand-waving idea.
4. **Explain why nothing is lost and what is gained**:
   Demonstrate that the alternative satisfies all requirements of the goal
   while reducing complexity, eliminating failure modes,
   or saving maintenance burden.
5. **Provide a clear recommendation**:
   Always attach your concrete recommendation
   per [`AGENTS.md`](../../AGENTS.md)'s "Always give recommendations with questions".
6. **Respect the user's decision**:
   If the user affirms the original approach after seeing the alternative
   (perhaps due to unstated out-of-band constraints or deliberate design choices),
   accept the decision and execute it cleanly without grumbling or stalling.

## Limits

- **Not contrarianism for its own sake**:
  Do not invent artificial alternatives or debate trivial stylistic choices
  when the proposed approach is already sound, simple, and idiomatic.
- **Do not stall straightforward work**:
  For well-scoped tasks with an obvious, standard implementation,
  execute directly rather than introducing unnecessary decision paralysis.
- **Never compromise requirements or safety**:
  An alternative that achieves simplicity by silently dropping edge cases,
  weakening security, or skipping verification is not a better alternative;
  it is a defect.
- **Provide concrete proposals, not vague pushback**:
  Saying "there might be a better way" without specifying what it is
  wastes time.
  Show the alternative clearly so it can be evaluated immediately.

## Do / Don't

- **Do:** proactively suggest simpler, more idiomatic, or upstream alternatives
  when a proposed approach carries unnecessary complexity or technical debt.
- **Do:** distinguish the user's underlying goal from the candidate mechanism
  proposed to reach it.
- **Do:** present alternatives constructively with concrete code snippets,
  clear tradeoffs, and a specific recommendation.
- **Do:** check for existing standard library and upstream solutions (DRW)
  before agreeing to build custom mechanisms.
- **Don't:** silently comply with an inferior or convoluted technical approach
  out of superficial deference or compliance reflex.
- **Don't:** treat a proposed mechanism as an immutable constraint when the user
  has only specified an objective.
- **Don't:** offer vague objections without presenting a concrete,
  actionable alternative.
- **Don't:** argue or bikeshed when a proposed approach is already simple,
  standard, and effective.

## Relationship to other principles and rules

- **[`dont-take-my-word-for-it`](dont-take-my-word-for-it.md)**:
  Governs factual truth and pushing back against unverified claims;
  this principle governs technical approaches and architectural solutions
  to achieve a goal.
- **[`dont-reinvent-wheel`](dont-reinvent-wheel.md)**:
  The primary source of better alternatives --- reusing established upstream
  tools rather than hand-rolling custom mechanisms.
- **[`challenge-the-assignment`](../workflow/challenge-the-assignment.md)**:
  Interrogating task briefs, instructions, and premises before executing them;
  this principle focuses on expanding the solution space for valid goals.
- **[`challenge-unnecessary-complexity`](../workflow/challenge-unnecessary-complexity.md)**:
  The review-time counterpart that flags complexity in existing code;
  this principle catches complexity before it is built.
- **[`avoid-false-dichotomies`](../workflow/avoid-false-dichotomies.md)**:
  Looking beyond artificially constrained options to find superior third paths.
