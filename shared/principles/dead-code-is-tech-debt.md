# Dead code is technical debt

Dead code is not harmless surplus;
it is active technical debt that accumulates carrying costs on every reader,
coding agent, search tool, and test suite pass.
Treat obsolete functions, orphaned configuration files, unreferenced memory entries,
and commented-out code as defects to be eliminated systematically and promptly,
not as historical archives to be preserved in place.

## Why dead code is technical debt

Unused code and orphaned assets impose substantial, ongoing operational costs:

1. **Cognitive and LLM context bloat.**
   Dead functions, stale files, and commented-out blocks consume token budget
   and inflate context windows.
   Language models and human engineers waste reasoning capacity analyzing dead paths,
   attempting to reconcile obsolete signatures, or hallucinating interactions
   with dead symbols.
2. **False positives in search and refactoring.**
   Grep sweeps, symbol renames, and type migrations hit dead occurrences,
   wasting engineering effort updating or testing code that has no live callers.
3. **Commented-out code rots silently.**
   Code disabled behind comment markers does not execute, compile, or run in CI.
   It cannot be type-checked or linted, and its assumptions quickly drift from reality.
   Version control (`git`) is the immutable archive of history;
   source files must reflect only live, active logic.
4. **Orphaned configs and memory entries mislead agents and operators.**
   Unreferenced configurations (`.json`, `.yml`, `.toml`) and stale memory records
   induce workflows to configure nonexistent tools or follow deprecated policies.
5. **Masked bugs and false coverage.**
   Dead test fixtures or uncalled validation helpers can pass indefinitely,
   giving false confidence while masking missing test assertions or unexercised paths.

## Categories of dead artifacts

When auditing or reviewing a codebase, identify and prune these five categories:

### 1. Obsolete and uncalled functions, modules, and exports

- Functions, classes, methods, or helper utilities with zero live callers across the repository.
- Dead branches guarded by conditions that are statically false or obsolete feature flags.
- Exported package symbols that have been superseded and are no longer part of the public interface.

### 2. Orphaned configuration files and scripts

- CI/CD workflow files, hook scripts, or build configs that are no longer invoked, registered in manifests, or supported.
- Configuration templates or schema definitions for discarded tools or workflows.
- Standalone helper scripts whose dependencies or callers have been removed.

### 3. Unreferenced memory entries and documentation

- Memory files (`memories/*.md`) or documentation fragments not linked from active indices, rules, or workflows.
- Guides documenting deleted tools, flags, or procedures that no longer exist in the repository.
- Stale case studies or rationale records whose referenced implementations were deleted.

### 4. Commented-out code blocks

- Blocks of code commented out with `#`, `//`, `/* ... */`, or HTML comments in active source files.
- Disabled test cases left without an explicit tracking issue or active skip annotation.

### 5. Inert conjuncts in live, executing conditions

A boolean operand that can never resolve differently from a constant, given the control flow around it, is dead code that still runs on every call.
It costs a reader's attention each time the line is read, and it is invisible to line coverage and to a mutation run alike: removing an always-true conjunct changes no observable behaviour, so no test can fail against its removal.

- A conjunct guaranteed by an earlier `return`/`raise` in the same function (e.g. `if x and not y:` right after a prior branch that already returned whenever `y` was true).
- A conjunct guaranteed by a sibling condition a few lines above, once *that* condition has been simplified --- the guarantee can shift onto a line the edit never touched.

**A cleanup's own justification does not inoculate the rest of the diff against the same defect, and the code nearest a stated principle is where it is checked least.**
Citing a principle while removing two instances of a pattern reads as having swept the diff for it, but a third, structurally identical instance a few lines away is exactly as likely to remain --- more so, because a reader's guard drops immediately after a comment that says "this is now proven redundant."

(Morrison-Lab/ai-config#3707, commits `6ed5807` and `0a125ec`, 2026-09-17: a hook's provenance check removed an `and not saw_reviewer_call` conjunct from two conditions, with a comment proving both could never be false and citing this principle by name.
Three lines later, in an adjacent condition the same commit left untouched, `transcript_path and not os.path.exists(transcript_path)` carried an equally inert `transcript_path and` --- the immediately preceding statement, `if not transcript_path: return ...`, already guaranteed `transcript_path` truthy by that point.
No mutation run ever flagged it, for the reason given above: removing `transcript_path and` changes nothing a test can observe.
A later review round found it only by re-deriving what the code immediately above the condition actually guarantees.)

## Systematic elimination workflow

Eliminate dead code systematically using a four-stage process:

1. **Detect with deterministic tools.**
   Use static analysis linters and search tools rather than memory:
   - Python: `vulture`, `ruff` / `flake8` (`F401` unused imports, `F841` unused variables), `coverage.py`.
   - JavaScript / TypeScript: `knip`, `ts-prune`, `depcheck`, `eslint` (`no-unused-vars`).
   - R: `lintr` (`unused_import_linter`), `covr`, `devtools::check()`.
   - Manifest audits: check `hooks/hooks.json`, `plugins/`, and `skills/` for unregistered scripts or missing wrapper bindings.
2. **Verify live reachability and API boundaries.**
   Before deleting an apparently uncalled symbol:
   - Grep across the workspace for dynamic invocations, reflection, CLI dispatch names, or string keys.
   - For published libraries or public APIs, verify whether the symbol is part of the documented, versioned public API contract.
3. **Delete completely across all layers.**
   Never comment out obsolete code or leave empty stub functions behind.
   Delete the entire artifact and all its satellites:
   - The implementation and internal helpers.
   - Unit tests, integration tests, and test fixtures dedicated to it.
   - Docstrings, API manual entries, and index listings.
   - Manifest registrations and dependency declarations.
4. **Verify test suites and linters pass.**
   Run the full test suite, link checker, and linters to confirm no active subsystem depended on the removed symbols.

## Boundary with prefer-optionality-over-removal

This principle complements rather than contradicts [`prefer-optionality-over-removal`](prefer-optionality-over-removal.md):

- **[`prefer-optionality-over-removal`](prefer-optionality-over-removal.md)** governs *active capabilities with legitimate callers*:
  when an issue reports that a default behavior is problematic,
  do not resolve the issue by deleting the capability entirely if other callers or workflows rely on it.
  Make the improved behavior the default, and retain the alternative behavior as a configurable option.
- **`dead-code-is-tech-debt`** governs *uncalled, orphaned, unreachable, or commented-out code*:
  when code has no live callers, serves no supported use case, and is provably dead,
  retaining it as "optional" or commented-out is tech debt.
  Provably dead code must be deleted.

## Do / Don't

- **Do:** delete dead code, orphaned configs, unreferenced memories, and commented-out code completely.
- **Do:** rely on git history as the permanent archive instead of preserving dead code in source files.
- **Do:** remove associated tests, documentation, and manifest registrations when removing dead symbols.
- **Do:** use deterministic static analysis tools to verify zero callers before deletion.
- **Don't:** comment out code blocks "in case we need them later" --- git history preserves them.
- **Do:** when a comment proves one conjunct redundant, grep the same file for the identical operand and check whether a nearby condition carries it too --- the removal you just made can be exactly the fact that makes a sibling conjunct provably dead as well.
- **Don't:** keep obsolete functions or orphaned configs as harmless clutter;
  they actively degrade agent context and developer focus.
- **Don't:** leave deprecated symbols without a formal deprecation schedule and warning mechanism.
- **Don't:** treat a passing mutation run as evidence a conjunct isn't inert;
  an always-true operand produces no observable difference when removed, so no test can fail against its removal.

## In review

Flag dead code and commented-out blocks in every review:
- Ask the author to remove commented-out code blocks and rely on git history.
- Check a condition's conjuncts against what the code immediately above it guarantees, especially right after a comment that just proved a sibling conjunct redundant --- the same reasoning often applies a few lines further than the diff addressed.
- Check whether new changes leave orphaned helper functions, unused variables, or dead config files behind.
- Verify that refactors clean up superseded functions and their test fixtures completely.

