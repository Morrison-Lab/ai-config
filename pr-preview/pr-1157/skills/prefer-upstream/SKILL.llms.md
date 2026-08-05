# prefer-upstream

Before writing custom code for a common task, search for existing well-maintained packages or tools that already solve the problem.

This skill is the search procedure for the don’t-reinvent-the-wheel (DRW) principle — see [`shared/principles/dont-reinvent-wheel.md`](../../shared/principles/dont-reinvent-wheel.md) for the umbrella statement, including checking our own repos, the fork-or-contribute preference for close-but-not-exact matches, and the review-side application.

## When this fires (automatically)

- About to write a utility function (string manipulation, file parsing, API wrappers, data transformation)
- Implementing something that “feels generic” — not specific to this project
- Building CI/CD helpers, linters, formatters, or test infrastructure
- Any time you think “surely someone has done this before”

## Where to look (by ecosystem)

### R

- **r-lib** org: usethis, devtools, pkgdown, lintr, styler, testthat, covr, rcmdcheck, desc, fs, cli, rlang, withr, callr, processx
- **tidyverse** org: dplyr, tidyr, purrr, stringr, readr, forcats, lubridate, glue, tibble
- **ropensci** org: specialized packages for data access, APIs, etc.
- **CRAN Task Views**: curated lists by topic

### Python

- PyPI standard ecosystem: requests, click, rich, pydantic, httpx
- Scientific: numpy, pandas, scipy, scikit-learn

### Shell / CI

- Your project’s shared CI templates (e.g., reusable workflow libraries)
- Standard Unix tools before custom scripts
- GitHub Actions marketplace / GitLab CI templates

### JavaScript/TypeScript

- npm ecosystem: well-maintained packages with good test coverage

## Decision criteria

| Factor                                         | Build custom | Use upstream |
|------------------------------------------------|--------------|--------------|
| Exact match exists with active maintenance     | ❌           | ✅           |
| Close match exists, needs minor wrapping       | ❌           | ✅ (wrap it) |
| Upstream exists but unmaintained (\>2yr)       | Maybe        | ⚠️ Evaluate  |
| Problem is highly project-specific             | ✅           | ❌           |
| Upstream has heavy dependencies you don’t want | ✅           | ❌           |
| Learning exercise / pedagogical code           | ✅           | ❌           |

## Process

1.  **Identify the generic problem** — separate project-specific logic from the reusable utility layer
2.  **Search** — check the relevant ecosystem orgs, package indices, and GitHub/GitLab
3.  **Evaluate** — is it actively maintained? Good test coverage? Reasonable dependencies? Compatible license?
4.  **Recommend** — if a good upstream exists, suggest it to the user before writing custom code. Include:
    - Package name and link
    - How it solves the problem
    - Any wrapping needed
5.  **If a close-but-not-exact match exists** — prefer contributing the missing piece upstream, or forking, over re-building from scratch (see the DRW fragment’s fork-or-contribute section and its `upstream-issues` / `scout-peers` gates)
6.  **If no upstream exists** — proceed with custom implementation, but note in comments that you checked and nothing fit

## Anti-patterns to avoid

- Reimplementing `glue::glue()` with `paste0()` and manual substitution
- Writing custom YAML/JSON parsers when `yaml`/`jsonlite` exist
- Hand-rolling HTTP retry logic when `httr2` handles it
- Building custom test infrastructure when `testthat` covers the need
- Writing shell scripts for tasks that `usethis` or `devtools` already do

Back to top
