# Use real-world examples for general practice

When we do or see something that would be a good example for general practice,
use it.
When authoring, reviewing, or observing work that exemplifies good general
engineering, writing, or architectural practice,
actively capture and incorporate it as a concrete before-and-after example
in shared guides, rules, and documentation.

The user's standing directive:
"when we do or see something that would be a good example for general practice,
use it"
(user directive, Issue #4093).

## Why real-world examples matter

Abstract guidelines and principles
("write concisely", "avoid unnecessary complexity", "make definitions explicit",
"prefer systemic solutions")
are easy to agree to in theory but difficult to apply consistently without
concrete reference points.
Real-world examples from actual project history ground abstract maxims in practice:

1. **Concrete contrast (Before vs. After)**:
   A "before" state illustrates the seductive or common pattern that seemed
   sufficient initially,
   accompanied by an explicit critique of its hidden costs
   (redundancy, clutter, un-citable assertions, or brittle coupling).
   The "after" state demonstrates the improved solution,
   showing readers both the target standard and the exact mechanism of improvement.
2. **Authentic battle-tested context**:
   Real PRs and refactors from our own repositories
   (such as `pds`, `mln`, `rme`, `psw`, or `gha`)
   navigate authentic constraints, notations, and cross-references.
   Synthetic examples often omit the subtle edge cases that make real-world
   adherence challenging.
3. **Cross-repository learning**:
   Every repository serves as an experimental environment.
   When an edit in one project achieves greater clarity,
   conciseness, or architectural elegance,
   leaving that breakthrough buried in a closed PR diff limits its value.
   Promoting it to shared documentation (`ai-config`, `psw`)
   ensures that every subsequent session across all repositories benefits.

## What makes an exemplary case

Look for real-world edits and patterns that demonstrate:

- **Tightening definitions and removing redundancy**:
  Eliminating repetitive preambles, tautological clauses,
  or unnecessary bullet lists while preserving complete mathematical
  and semantic precision.
  For example, `Morrison-Lab/pds#22` streamlined `def-probability`
  by recognizing that being a measure already entails assigning numbers to events,
  turning a cluttered multi-bullet definition into one clean,
  display-math sentence.
- **Elevating informal commentary into citable constructs**:
  Taking important mathematical equivalences, claims,
  or properties buried in informal `::: notes` or code comments
  and formalizing them into first-class, citable theorems, types,
  or definitions with explicit proofs.
  For example, `Morrison-Lab/pds#22` extracted an informal equivalence claim
  from notes into `thm-kolmogorov-axioms` with a rigorous two-direction proof,
  giving downstream course notes a stable anchor (`@thm-kolmogorov-axioms`)
  to cite.
- **Structural decomposition (KISS / modularity)**:
  Breaking monolithic functions, multi-concept divs,
  or sprawling files into single-purpose, composable units.
- **Upstream adoption over custom wheels (DRW)**:
  Replacing hand-rolled scripts or bespoke wrappers with standard library
  functions, idiomatic CLI flags, or established packages.
- **Systemic fixes over point patches**:
  Replacing an ad-hoc local workaround with an automated mechanical check
  or type invariant that eliminates an entire class of mistakes.

## How to document a before-and-after example

When adding an example to shared guides or documentation,
structure it for immediate scannability:

1. **Source citation**:
   Link directly to the original pull request, commit, or issue
   (e.g., `[Morrison-Lab/pds#22](https://github.com/Morrison-Lab/pds/pull/22)`).
2. **Before snippet**:
   Show the original snippet, kept concise and focused on the relevant issue.
3. **Critique**:
   State clearly what made the original construct suboptimal
   (redundant conditions, un-citable claims, hidden assumptions).
4. **After snippet**:
   Show the refactored, improved construct.
5. **Key takeaway**:
   Explain the generalizable principle or technique that applies
   to future work.

## Limits

- **Avoid synthetic or contrived examples**:
  Prefer authentic project cases over invented ones whenever real data
  or commits exist
  (see [`detect-hypothetical-examples`](../../skills/detect-hypothetical-examples/SKILL.md)).
- **Keep snippets minimal**:
  Do not paste entire multi-page diffs;
  extract only the lines necessary to illustrate the contrast.
- **Ensure scanner safety**:
  When examples contain code spans or pattern triggers,
  render them safely so they do not trip line-oriented scanners
  or linters checking for the pattern
  (see [`examples-are-scanned`](../writing/examples-are-scanned.md)).

## Do / Don't

- **Do:** proactively capture exemplary edits, refactors, and solutions from real PRs
  and add them as before-and-after cases in shared documentation.
- **Do:** pair every before-and-after example with an explicit critique explaining
  *why* the change improved clarity, structure, or conciseness.
- **Do:** cite the authentic repository source (PR, issue, or commit) for provenance.
- **Do:** look across all active repositories (`pds`, `mln`, `psw`, `gha`, `ai-config`)
  for candidate examples during development and review.
- **Don't:** leave great examples of general practice isolated in closed PR diffs
  where future sessions cannot learn from them.
- **Don't:** invent artificial or toy examples when authentic project refactors exist.
- **Don't:** present an "after" example without explaining what made the "before"
  suboptimal.

## Relationship to other principles and rules

- **[`dont-reinvent-wheel`](dont-reinvent-wheel.md)**:
  Reusing proven solutions and examples across repositories rather than
  redesigning conventions from scratch.
- **[`informal-definitions`](../writing/informal-definitions.md)**:
  Demonstrates how informal notes are elevated into formal definitions
  and theorems using real before-and-after cases from `pds#22`.
- **[`examples-are-scanned`](../writing/examples-are-scanned.md)**:
  Ensures that illustrative examples written in documentation do not
  inadvertently trip automated linting scanners.
- **[`prefer-systemic-solutions-over-one-off-fixes`](prefer-systemic-solutions-over-one-off-fixes.md)**:
  Capturing exemplary systemic guards so other repositories can adopt
  the same automated patterns.
