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

When auditing or reviewing a codebase, identify and prune these four categories:

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

## Systematic elimination workflow

Eliminate dead code systematically using a four-stage process:

1. **Detect with deterministic tools.**
   Use static analysis linters and search tools rather than memory:
   - Python: `vulture`, `ruff` / `flake8` (`F401` unused imports, `F841` unused variables), `coverage.py`.
   - JavaScript / TypeScript: `knip`, `ts-prune`, `depcheck`, `eslint` (`no-unused-vars`).
   - R: `lintr` (`unused_import_linter`), `covr`, `pkgload::check()`.
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
- **Don't:** keep obsolete functions or orphaned configs as harmless clutter; they actively degrade agent context and developer focus.
- **Don't:** leave deprecated symbols without a formal deprecation schedule and warning mechanism.

## In review

Flag dead code and commented-out blocks in every review:
- Ask the author to remove commented-out code blocks and rely on git history.
- Check whether new changes leave orphaned helper functions, unused variables, or dead config files behind.
- Verify that refactors clean up superseded functions and their test fixtures completely.

