# Prefer systemic solutions over one-off fixes

When addressing a defect, failure, edge case, or recurring mistake, prefer systemic, structural solutions over one-off, ad-hoc patches.
Fix the underlying mechanism that allowed the error to occur, and install an automated guard, type constraint, or architectural invariant that prevents the entire class of defects from recurring.

## Why

A one-off fix patches only the single symptom or instance that happened to be noticed.
Because the underlying cause, blind spot, or process remains unaddressed, the exact same defect inevitably recurs in another file, on another branch, or during a future refactor.
Relying on human memory, vigilance, or repeated review rounds to catch identical mistakes wastes time and accumulates technical debt.

A systemic solution addresses the problem at its structural root.
By eliminating the condition that made the bug possible, or by automating its detection mechanically, systemic solutions resolve the issue permanently for all current and future occurrences.

## The Pattern

When resolving an issue or defect:

1. **Diagnose the systemic root cause.**
   Ask why the defect was able to happen in the first place.
   Was a check missing from CI?
   Was a type too permissive?
   Was a contract unenforced?
   Was a script relying on manual steps rather than automation?
2. **Fix the class of problems, not just the instance.**
   Survey where else the same pattern, assumption, or defect exists across the repository.
   Repair all instances across the codebase in the same turn, not just the one named in the initial report.
3. **Automate enforcement at the earliest possible stage.**
   Install an automated mechanism that detects or prevents the defect mechanically:
   - A pre-commit or CI check script (see [`algorithmatize-checks`](../workflow/algorithmatize-checks.md)).
   - A runtime assertion or invariant (see [`fail-fast`](fail-fast.md)).
   - A schema validation, tighter data type, or structural guard.
   - An enforcement hook (see [`deterministic-tools`](deterministic-tools.md)).
4. **Fix at the source of truth.**
   Never patch generated files, copies, or downstream consumers.
   Update the generator, canonical definition, or shared library so that all downstream artifacts benefit automatically (see [`dont-reinvent-wheel`](dont-reinvent-wheel.md) and DRY).

## One-off patch vs systemic solution

| Defect / Scenario | One-off patch (avoid) | Systemic solution (prefer) |
|---|---|---|
| A broken relative link in documentation | Fix the single URL by hand | Add a link checker script to CI (`check-links.py`) and fix all broken links |
| A command fails on a malformed payload | Wrap only that specific call site in a manual check | Harden the shared payload parser or type contract to handle malformed shapes safely |
| Inconsistent prose formatting or line wrapping | Reformat lines manually in the edited paragraph | Use an automated formatting tool (`semantic-line-breaks.py`) enforced by CI |
| An unreviewed push reaches the remote | Tell authors to remember self-review | Install a pre-push review enforcement hook (`no-push-without-self-review.py`) |
| An out-of-sync generated file | Hand-edit the generated copy | Run the generation script in CI with a `--check` drift flag |

## Boundary with KISS and YAGNI

Preferring systemic solutions does not license speculative architecture or over-engineering:

- **KISS** remains binding: the simplest systemic solution is the best one.
  A 20-line standalone Python verification script wired into CI is far more systemic and maintainable than an elaborate, multi-layered framework.
- **YAGNI** bounds the *scope of the defect*: solve the problem class that has actually been observed and diagnosed, not theoretical problems that have never occurred.
- **`dont-incur-technical-debt`** demands that the systemic fix be implemented as part of the current turn rather than deferred to a hypothetical future task.

## Provenance

(User directive, 2026-09-18, Issue #3777: `prefer systemic solutions over one-off fixes`.)

## Do / Don't

- **Do:** diagnose the root cause of failures and fix the underlying mechanism.
- **Do:** install automated, deterministic checks or structural invariants that prevent recurrence of the defect class.
- **Do:** audit the repository for other instances of the same flaw when a bug is identified.
- **Do:** fix defects at the authoritative source of truth rather than patching generated copies or downstream symptoms.
- **Don't:** settle for a one-off patch that leaves the defect class open to recur elsewhere.
- **Don't:** rely on human memory, agent discipline, or review vigilance when a mechanical check can enforce the rule.
- **Don't:** over-engineer speculative frameworks under the guise of systemic solutions;
  build the simplest automated guard that solves the diagnosed problem.

## In review

Flag diffs that:
- Fix an instance of a defect in one file while ignoring identical instances in siblings.
- Paper over a symptom by adding an exception or silencing a warning without addressing why the warning fired.
- Hand-edit generated artifacts instead of modifying the source template or generation script.
