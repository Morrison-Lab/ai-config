# lint — lint changed R code the way CI does

Lints the R code a change touches, in `.R`, `.qmd` and `.Rmd` files, with the same linters the repository’s CI applies, and reports what it finds. The notes repositories (lds, rme, sds, pds, mds) each carried a copy of this command, and the copies had drifted ([ai-config#4927](https://github.com/Morrison-Lab/ai-config/issues/4927)); this skill replaces them.

## When to run

Before committing a change to R code or to a `.qmd` or `.Rmd` file with R chunks. A repository’s `CLAUDE.md` pre-commit checklist usually names this step.

## Procedure

1.  **List the changed files.**

    ``` sh
    git diff --name-only --diff-filter=AMR origin/main...HEAD -- '*.R' '*.qmd' '*.Rmd'
    git diff --name-only --diff-filter=AMR HEAD -- '*.R' '*.qmd' '*.Rmd'
    ```

    The first line lists committed changes and the second staged and unstaged ones; lint the union.

2.  **Pick the linters CI uses.** Read the repository’s lint workflows under `.github/workflows/` (in the lab, `lint-changed-lines.yaml` and `lint-changed-files.yaml`) and use the linters they name:

    - A workflow that passes `lms::default_linters(nested_calls = TRUE)` (lds, sds, pds and mds as of 2026-11-19) lints with those. Install `lms` at the commit the workflow pins as `lms-ref`: `Rscript -e 'remotes::install_github("Morrison-Lab/psc/lms@<lms-ref>")'`.
    - Otherwise lint against the repository’s `.lintr` or `.lintr.R`, which `lintr::lint()` reads by itself.

3.  **Lint each changed file by path.**

    ``` sh
    Rscript -e 'lintr::lint("path/to/file.qmd", linters = lms::default_linters(nested_calls = TRUE))'
    Rscript -e 'lintr::lint("path/to/file.R")'
    ```

    Use the first form when step 2 found `lms`, the second otherwise. Lint a `.qmd` or `.Rmd` file itself, not an extracted script: `lintr` reads its R chunks.

4.  **For a whole-repository sweep, check for a self-referential symlink first.** `lintr::lint_dir()` follows symlinks, so a repository that links its own name to `.` (sds’s `sds -> .`, pds’s `pds -> .`) reports every lint many times over, and no `.lintr.R` exclusion can skip the link without also skipping the files it aliases.

    ``` sh
    find . -maxdepth 1 -type l -lname . -print
    ```

    Remove each link that prints (`rm -f <name>`, which deletes only the link), run `lintr::lint_dir()` with the linters step 2 chose (`Rscript -e 'lintr::lint_dir(linters = lms::default_linters(nested_calls = TRUE))'` when CI uses `lms`, a bare `lintr::lint_dir()` otherwise), then restore it with `git checkout -- <name>`. Step 3’s per-file lint never meets the link, so prefer it whenever the change is known.

5.  **Report** the findings grouped by file, each with its line number, the linter that fired, and a one-line fix. Fix only findings in code your change added or edited, since the lab’s rule is that unrelated pre-existing lint stays out of the PR; say so when none remain.

## Relationship to other skills

- [`spell`](../../skills/spell/SKILL.llms.md) is the spelling counterpart.
- [`r-pkg-check`](../../skills/r-pkg-check/SKILL.llms.md) runs `devtools::check()`, which is all rme’s `check` command did, so that command needs no skill of its own.
- A repository’s own `render` and `new-chapter` commands stay in the repository, since what they render and scaffold differs per site.

Back to top
