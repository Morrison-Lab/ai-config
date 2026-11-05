R package dev with devtools, testthat, and roxygen2.

Author

Simon P. Couch (@simonpcouch)

# R package development

## Key commands

    # Run code in the package
    Rscript -e "devtools::load_all(); code"

    # Run all tests
    Rscript -e "devtools::test()"

    # Run all tests for files starting with {name}
    Rscript -e "devtools::test(filter = '^{name}')"

    # Run all tests for R/{name}.R
    Rscript -e "devtools::test_active_file('R/{name}.R')"

    # Run a single test "blah" for R/{name}.R
    Rscript -e "devtools::test_active_file('R/{name}.R', desc = 'blah')"

    # Redocument the package
    Rscript -e "devtools::document()"

    # Check pkgdown documentation
    Rscript -e "pkgdown::check_pkgdown()"

    # Check the package with R CMD check
    Rscript -e "devtools::check()"

    # Format code
    air format .

## Coding

- Before writing custom helper functions or hand-rolling utilities, research existing functions in base R, tidyverse/r-lib, ropensci, or existing dependencies per [`prefer-packaged-functions`](../../shared/coding/prefer-packaged-functions.md) and [`prefer-upstream`](../../skills/prefer-upstream/SKILL.llms.md).
- Always run `air format .` after generating code.
- Use the base pipe operator (`|>`) not the magrittr pipe (`%>%`).
- Use `\() ...` for single-line anonymous functions. For all other cases, use `function() {...}`.

## Testing

For the full testthat API (fixtures, mocking, snapshots, BDD-style tests), see [`testing-r-packages`](../../skills/testing-r-packages/SKILL.llms.md). Match the package’s existing `expect_error()`/`expect_warning()` or snapshot-testing style where precedent exists. On a fresh package with no precedent, follow testing-r-packages’ preference for snapshot-based error/warning tests.

- Tests for `R/{name}.R` go in `tests/testthat/test-{name}.R`.
- All new code should have an accompanying test.
- If there are existing tests, place new tests next to similar existing tests.
- Strive to keep tests minimal with few comments.
- Avoid `expect_true()` and `expect_false()` in favour of a specific expectation which will give a better failure message.
- When testing errors and warnings, match the package’s existing precedent where one exists (see above). On a fresh package with no precedent, use `expect_snapshot(error = TRUE)` for errors and `expect_snapshot()` for warnings, not `expect_error()` or `expect_warning()`. A snapshot lets the user review the full text of the output.

## Documentation

- Every user-facing function should be exported and have roxygen2 documentation.
- Wrap roxygen comments at 80 characters.
- Internal functions should not have roxygen documentation.
- Whenever you add a new (non-internal) documentation topic, also add the topic to `_pkgdown.yml`.
- Always re-document the package after changing a roxygen2 comment.
- Use `pkgdown::check_pkgdown()` to check that all topics are included in the reference index.

## `NEWS.md`

This is the tidyverse-style default. When the package already has an established `NEWS.md` style, match that existing style instead — see [`r-pkg-news`](../../skills/r-pkg-news/SKILL.llms.md), whose whole job is reading a package’s precedent before drafting a new entry.

- Every user-facing change should be given a bullet in `NEWS.md`. Do not add bullets for small documentation changes or internal refactorings.
- Each bullet should briefly describe the change to the end user.
- If the change is related to a function, put the name of the function early in the bullet.
- If the bullet is related to a GitHub issue or pull request, reference it by number in parentheses before the final period: `(#123).`.
- Order bullets alphabetically by function name. Put all bullets that don’t mention function names at the beginning.

## Relationship to other skills

This skill is a day-to-day dev-loop reference (load, test, document, format) with this author’s own conventions. It does not replace, and does not cover:

- [`prefer-packaged-functions`](../../shared/coding/prefer-packaged-functions.md) and [`prefer-upstream`](../../skills/prefer-upstream/SKILL.llms.md) — researching existing functions and package solutions before hand-rolling custom code.
- [`r-pkg-check`](../../skills/r-pkg-check/SKILL.llms.md) — running and triaging `devtools::check()` output.
- [`r-pkg-cran-checklist`](../../skills/r-pkg-cran-checklist/SKILL.llms.md) — the CRAN release mechanics (win-builder, revdep checks, `devtools::release()`).
- [`cran-extrachecks`](../../skills/cran-extrachecks/SKILL.llms.md) — the ad-hoc/stylistic CRAN checklist (Title case, `@return` tags, URL hygiene) that `devtools::check()` doesn’t catch on its own.
- [`r-pkg-news`](../../skills/r-pkg-news/SKILL.llms.md) — matching a package’s existing `NEWS.md` style, which overrides this skill’s own default above.
- [`testing-r-packages`](../../skills/testing-r-packages/SKILL.llms.md) — the full testthat API (fixtures, mocking, snapshots, BDD-style tests). Match the package’s existing `expect_error()`/`expect_warning()` or snapshot-testing style where precedent exists. On a fresh package with no precedent, follow testing-r-packages’ preference for snapshot-based error/warning tests, which agrees with this skill’s own default above.

Back to top

## Reuse

MIT
