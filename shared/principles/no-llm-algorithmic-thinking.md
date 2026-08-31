Never use LLMs for algorithmic thinking --- use validated algorithmic software instead.
When an operation is algorithmic --- counting, arithmetic, algebra,
derivatives, integrals, linear algebra, sorting, or mathematical proof verification ---
delegate the computation to validated, deterministic software rather than
generating answers through autoregressive language model reasoning in context.
Where no validated software or package is at hand for the task,
write the algorithmic software and validate it yourself before consuming its output.

## Why LLMs fail at algorithmic thinking

Autoregressive language models generate tokens based on statistical transition probabilities
over text representations.
They do not execute state machines, exact algebraic simplification rules,
or formal verification engines inside their token generation passes.
When asked to perform algorithmic operations in context,
models exhibit characteristic and unavoidable failure modes:

- **Counting and tokenization artifacts**:
  Models do not perceive text as characters or lines directly;
  they perceive token chunks.
  Line counts, character offsets, frequency tallies, and population sizes
  derived in-context regularly suffer from off-by-one errors and hallucinations.
- **Arithmetic drift**:
  Multi-digit arithmetic, floating-point operations, percentage ratios,
  and compounding calculations lose precision or produce plausible-sounding but wrong digits.
- **Algebraic and symbolic manipulation errors**:
  Expanding, factoring, simplifying polynomials, or solving systems of equations
  in text frequently drops terms, flips signs, or invents algebraic identities.
- **Calculus inaccuracies**:
  Symbolic derivatives, definite and indefinite integrals, limits,
  and series expansions produce superficially convincing forms
  that violate fundamental calculus theorems upon substitution.
- **Linear algebra failures**:
  Matrix multiplications, inversions, determinant evaluations,
  and eigenvalue decompositions degrade rapidly with dimension when attempted in text.
- **Permutation and sorting bugs**:
  Ordering lists or priority queues in-context misses items,
  duplicates entries, or violates transitivity.
- **Unsound proof steps**:
  Conversational mathematical derivations often jump across logical gaps
  with confident prose that masks invalid deductive steps.

Model confidence does not correlate with algebraic or mathematical correctness.
A model can produce an elegant, well-structured derivation
carrying a fatal arithmetic or algebraic blunder in the middle.

## Domains of algorithmic thinking and validated software equivalents

Always route algorithmic tasks to validated software:

| Domain | In-context LLM anti-pattern | Validated software equivalent |
|---|---|---|
| **Counting & sizing** | Eyeballing line counts, token estimates, or match tallies | `wc -l`, `grep -c`, Python `len()`, `sum()`, `scripts/check-context-closure.py` |
| **Arithmetic & numeric** | Mental arithmetic, speedup ratios, rate-of-change math | Python `math`/`decimal`/`fractions`, `bc`, `awk`, R, Julia |
| **Symbolic algebra** | Factoring polynomials, simplifying expressions by hand | Computer Algebra Systems (CAS): SymPy (`sympy.simplify`, `sympy.factor`, `sympy.solve`), Maxima, SageMath |
| **Calculus** | Computing symbolic derivatives or integrals in prose | SymPy (`sympy.diff`, `sympy.integrate`), R (`stats::deriv`, `stats::integrate`), SciPy (`scipy.integrate`) |
| **Linear algebra** | Matrix products, determinants, eigenvalues in text | NumPy (`numpy.linalg`), SciPy, BLAS/LAPACK, base R / Matrix package |
| **Sorting** | Manual ordering of lists, tables, or backlog items | `sort`, Python `sorted()` / `list.sort()`, R `order()` / `sort()` |
| **Proof verification** | Conversational assertions of proof validity | Interactive/automated theorem provers (Lean 4, Coq/Rocq, Isabelle/HOL), SMT solvers (Z3, CVC5) |

## Write and validate it yourself when no tool exists

When no off-the-shelf software, CLI utility, or library function covers
the specific calculation, transformation, or verification at hand:

1. **Write the algorithmic software**:
   Author a focused, deterministic script or function in a standard programming language
   (such as Python, R, or Bash).
2. **Validate it thoroughly**:
   Test the script against known analytical solutions, reference benchmark cases,
   property-based tests, or negative controls before relying on its output.
3. **Execute the software in a real environment**:
   Run the code via shell or tool execution, capturing actual stdout and stderr.
4. **Consume the validated output**:
   Let the agent and human review and incorporate the computed results,
   rather than simulating execution in text.

Never excuse in-context calculation on the grounds that the problem looks simple.
A simple calculation is the easiest kind to write a one-line script or test for.

## Relationship to sibling principles

This principle works alongside the broader engineering principles in this catalog:

- [`deterministic-tools`](deterministic-tools.md) is the umbrella principle
  for replacing model judgment with automation across the entire development workflow.
- [`algorithmatize-checks`](../workflow/algorithmatize-checks.md) is the verification-focused
  rule governing test suites, CI checks, and diagnostic assertions.
- [`avoid-hardcoding-external-data`](../coding/avoid-hardcoding-external-data.md) prevents
  hand-typing derived or externally authoritative values into code or documentation.
- [`least-flexible-tool`](../coding/least-flexible-tool.md) prefers the narrowest construct
  capable of performing a coding task.

This principle specifically governs **algorithmic operations themselves**:
whenever a task requires algorithmic reasoning,
delegate the computation to validated software rather than language model inference.

## Do / Don't

- **Do:** delegate all counting, arithmetic, algebraic, calculus, linear algebra,
  sorting, and proof verification tasks to validated software.
- **Do:** write a deterministic script and test it against benchmark cases
  when no off-the-shelf tool exists.
- **Do:** execute the script in a real environment and consume the actual output.
- **Do:** use Computer Algebra Systems (like SymPy) for symbolic derivations
  and theorem provers / SMT solvers for formal proof verification.
- **Don't:** compute arithmetic, algebra, derivatives, integrals, or matrix products
  in LLM reasoning.
- **Don't:** count lines, items, tokens, or pattern matches by reading text in-context
  when an inspection command can count them.
- **Don't:** trust a plausible-looking mathematical proof or algebraic simplification
  generated in chat without software-backed verification.
- **Don't:** simulate code execution or calculation in text instead of running the code.

## In review

Flag these during code and prose review:

- Mathematical formulas, algebraic simplifications, or calculus steps in PR descriptions,
  documentation, or comments that lack execution scripts or CAS verification.
- Hand-counted metrics, totals, or percentages reported in comments or PR bodies
  that differ from what deterministic counting tools produce.
- Manual rearrangements or in-context sorting of large collections
  where a deterministic sorting routine should be used.
- Analytical model implementations whose mathematical derivations were composed in chat
  without accompanying test suites or analytical validation benchmarks.
