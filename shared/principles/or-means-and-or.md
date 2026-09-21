# "Or" always means "and/or", not xor, unless xor is explicitly specified

In instructions, requirements, prompts, checklists, and specifications, treat "or" as inclusive ("and/or") unless exclusive choice is explicitly stated.
Never interpret an unadorned "or" as an exclusive disjunction (XOR) that excuses dropping, ignoring, or omitting one of the alternatives when both apply.

## Why

Language models and automated agents frequently treat natural-language disjunctions as mutually exclusive choices (XOR).
Given an instruction such as "update the documentation or add unit tests", an agent often performs only one action and ignores the other, believing that satisfying either branch fulfills the prompt.
Similarly, when analyzing requirements ("check CI run logs or review comments"), an agent might check only the first source and stop, missing critical failures or findings present in the second.

In human communication and software engineering instructions, "or" is standardly inclusive unless exclusivity is actively specified.
Treating "or" as XOR introduces false trade-offs, incomplete implementations, and dropped requirements.
When multiple alternatives are relevant, applicable, and safe to execute, an agent should address both.

## The Principle

1. **Default to inclusive disjunction ("and/or").**
   Unless the context or author explicitly mandates choosing exactly one option, evaluate all alternatives in the disjunction.
   If both (or all) alternatives are applicable, execute or verify all of them.
2. **Require explicit phrasing for exclusive disjunction (XOR).**
   Exclusivity must be stated unambiguously: "either A or B, but not both", "mutually exclusive", "choose exactly one of the following", or "XOR".
   Without such explicit wording, assume all listed alternatives may be combined or executed.
3. **Maximize safe progress across all branches.**
   Consistent with the universal instruction to interpret requests broadly, satisfying all applicable parts of an instruction delivers a complete, robust solution rather than an arbitrary subset.

## When genuine mutual exclusivity applies

Exclusivity is legitimate and binding when:

- **The prompt or specification explicitly specifies XOR** (e.g., "choose either option A or option B, but not both").
- **The alternatives are physically, logically, or architecturally incompatible** (e.g., "revert the commit or squash-merge it" --- a PR cannot be both reverted and merged at the same time).
- **The user explicitly asks to pick a single preferred option from a list.**

Outside those cases, treat "or" as inclusive.

## Boundary with KISS, YAGNI, and specific-beats-general

This principle does not mandate speculative work or unnecessary complexity:

- **KISS and YAGNI** continue to bound *scope of implementation*: do not invent unrequested features.
  When an instruction directly offers multiple relevant paths ("add a CLI flag or environment variable"), providing both or choosing the one that best integrates optionality (see [`prefer-optionality-over-removal`](prefer-optionality-over-removal.md)) respects the prompt rather than guessing future requirements.
- **[`specific-beats-general`](specific-beats-general.md)** governs *rule conflicts*: if a specific guideline explicitly orders a single selection, that specific instruction outranks the default inclusive interpretation.

## Provenance

(User directive, 2026-09-18, Issue #3776: `"or" always means "and/or", not xor, unless xor is explicitly specified`.)

## Do / Don't

- **Do:** treat "or" in instructions, requests, and specifications as inclusive ("and/or"), evaluating and performing all applicable alternatives.
- **Do:** explicitly specify mutual exclusivity (e.g. "either X or Y, but not both") when authoring instructions intended as exclusive choices.
- **Do:** inspect all named sources when diagnosing issues (e.g., "check the workflow run logs or review comments").
- **Don't:** treat an unadorned "or" as an exclusive disjunction (XOR) that licenses dropping, ignoring, or omitting one of the alternatives.
- **Don't:** assume satisfying one branch of an instruction excuses failing to satisfy another when both are applicable and relevant.

## In review

Flag diffs, plans, or review comments that:
- Interpret user or reviewer instructions with "or" as an exclusive choice, omitting an in-scope requirement.
- Arbitrarily choose between testing and documentation when the prompt requested both via "or".
