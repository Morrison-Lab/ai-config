# spell — spell-check a change the way CI does

Runs the spelling checker the repository’s CI runs, on the files a change touches, and reports what it finds. The notes repositories carried their own copies of this command, which had drifted ([ai-config#4927](https://github.com/Morrison-Lab/ai-config/issues/4927)); this skill replaces them.

## When to run

Before committing prose or code comments. A repository’s `CLAUDE.md` pre-commit checklist usually names this step.

## Procedure

1.  **Find the checker CI uses.** Read the spelling workflow under `.github/workflows/`:

    - `check-typos.yml`, or a `_typos.toml` at the root (lds as of 2026-11-19): the checker is [`typos`](https://github.com/crate-ci/typos).
    - `check-spelling.yaml` with an `inst/WORDLIST` (rme, sds, pds and mds as of 2026-11-19): the checker is `spelling::spell_check_package()`.

    A repository with both runs both.

2.  **With `typos`**, check the changed files:

    ``` sh
    git diff --name-only --diff-filter=AMR origin/main...HEAD | xargs typos
    ```

    Install it with `pip install typos` if it is missing. A correctly spelled term it misreads goes in `_typos.toml`, never in a disabled check.

3.  **With `spelling`**, follow [`r-pkg-spellcheck`](../../skills/r-pkg-spellcheck/SKILL.llms.md) steps 2 through 5. It runs the same command, and says how to add a word to `inst/WORDLIST` without breaking its sort order and line endings.

4.  **Report** the misspellings grouped by file. Fix only those your change introduced; say so when none remain.

## Relationship to other skills

- [`lint`](../../skills/lint/SKILL.llms.md) is the R-lint counterpart.
- [`r-pkg-spellcheck`](../../skills/r-pkg-spellcheck/SKILL.llms.md) is the full `spelling` procedure this skill defers to.

Back to top
