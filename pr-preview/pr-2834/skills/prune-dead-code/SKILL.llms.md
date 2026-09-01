# prune-dead-code

Audit the codebase to systematically detect and remove dead code, obsolete functions, orphaned configuration files, unreferenced memory entries, and commented-out code blocks. Operationalizes the [dead-code-is-tech-debt](../../shared/principles/dead-code-is-tech-debt.md) principle.

## When this fires

- User says `/prune-dead-code`, `/pdc`, “remove dead code”, “clean up unused functions”, “find commented-out code”, or “audit for dead assets”.
- After a major refactoring, migration, or feature consolidation.
- Routine repository hygiene and maintenance passes.

## Scope

If the user specifies a directory, file, or component, restrict the audit to that scope. Otherwise, perform a repository-wide sweep.

## Audit and elimination procedure

Follow this step-by-step workflow:

### Step 1: Commented-out code sweep

Search for blocks of code disabled behind comment characters:

1.  Grep for common commented code patterns:
    - Python: `grep -rnE '^\s*#\s*(def |class |import |from |return |if __name__)' <path>`
    - JavaScript/TypeScript: `grep -rnE '^\s*//\s*(function |class |import |export |const |let |var )' <path>`
    - R: `grep -rnE '^\s*#\s*([a-zA-Z0-9_.]+\s*<-\s*function|library\(|source\()' <path>`
    - Shell: `grep -rnE '^\s*#\s*(function |alias |export )' <path>`
2.  Distinguish informative comments (explanations, rationale, citations, constraints) from disabled code blocks.
3.  Remove disabled code blocks completely. Rely on git history as the permanent archive.

### Step 2: Unused symbols, functions, and imports

Detect uncalled functions, unused variables, and dangling imports using language-specific tools:

- **Python:**
  - Run `ruff check --select F401,F841 <path>` or `flake8 --select=F401,F841 <path>` to find unused imports and variables.
  - Run `vulture <path>` (if installed) or grep for defined `def` / `class` names across the repository to verify callers.
- **JavaScript / TypeScript:**
  - Run `npx knip` or `npx ts-prune` to find unused exports and files.
  - Run `npx eslint` for `no-unused-vars` / `@typescript-eslint/no-unused-vars`.
- **R:**
  - Check with `lintr::lint(path, linters = lintr::unused_import_linter())`.
  - Check test coverage with `covr::package_coverage()` to identify unexercised functions.
- **Shell / Scripts:**
  - Audit function declarations in scripts: search for function names across all callers.

### Step 3: Orphaned configurations and scripts

Identify files no longer connected to the build, test, or execution pipeline:

1.  **Manifest and registration audit:**
    - In `ai-config`: verify every script in `hooks/` has an entry in `hooks/hooks.json` and a test in `hooks/test-*.py`.
    - Verify every skill in `skills/` has a valid `SKILL.md` and corresponding `codex-skills/` wrapper.
    - Verify plugin declarations in `plugins/` match active manifests.
2.  **CI/CD workflows:**
    - Check `.github/workflows/` for references to scripts, actions, or steps that no longer exist.
3.  **Orphaned dotfiles and templates:**
    - Identify unused configuration files for tools no longer used in the project.

### Step 4: Unreferenced memory entries and documentation

Detect stale memories and documentation orphans:

1.  Check `memories/` for files not linked from `memories/README.md` or referenced in any active rules/skills.
2.  Check for documentation referencing deleted CLI commands, removed options, or obsolete architecture.
3.  Run `python3 scripts/check-links.py` (or repo link checker) to ensure no broken relative links exist.

### Step 5: Verify reachability and boundaries

Before deleting any symbol or file: 1. Grep for string references, dynamic lookups, reflection, CLI entry points, and environment variable dispatch. 2. For published libraries or packages, verify whether the symbol is part of the documented public API export contract. 3. If an active capability serves legitimate users and was questioned only because a default behavior was problematic, follow [prefer-optionality-over-removal](../../shared/principles/prefer-optionality-over-removal.md) instead of deleting it.

### Step 6: Atomic deletion and dependency cleanup

When removing dead code: 1. Delete the implementation. 2. Delete corresponding unit tests, integration tests, and test fixtures that only tested the dead code. 3. Delete documentation entries, manual pages, docstrings, and export declarations. 4. Delete manifest bindings, wrapper files, and build script entries.

### Step 7: Validation and verification

Run all verification suites: 1. Execute test suites (e.g. `pytest`, `npm test`, `Rscript -e 'devtools::test()'`). 2. Run linters and link checkers (e.g. `python3 scripts/validate-skills.py`, `python3 scripts/check-links.py`, `npx markdownlint-cli2`). 3. Confirm clean test passes with zero regressions.

## Report format

Summarize removals clearly:

``` markdown
### Dead Code Pruning Summary

- **Commented-out code:** <N> blocks removed (<file paths>)
- **Obsolete symbols/functions:** <N> functions removed (<symbol names & files>)
- **Orphaned configs/scripts:** <N> files removed (<file paths>)
- **Unreferenced docs/memories:** <N> files/sections updated
- **Total lines removed:** <N> lines
- **Verification status:** Tests passing (<test summary>)
```

Back to top
