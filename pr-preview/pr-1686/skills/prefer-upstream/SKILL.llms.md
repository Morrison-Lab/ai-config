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

Every row of that table is a fact about the world. Before using one, check that it is. A constraint your own change authored — “this script runs with no packages installed”, “this PR decided not to add a dependency” — belongs in none of those cells, because the change it would justify is what created it. Relax it (add the dependency, fix the CI job) and re-read the table against the relaxed environment. See the DRW fragment’s “A constraint your own change authored is not evidence against an upstream”.

## Process

1.  **Identify the generic problem** — separate project-specific logic from the reusable utility layer
2.  **Search** — check the relevant ecosystem orgs, package indices, and GitHub/GitLab
3.  **Evaluate** — is it actively maintained? Good test coverage? Reasonable dependencies? Compatible license?
4.  **Classify any constraint that rules a candidate out** as external (a platform limit, an upstream API, a license, a policy) or self-imposed (a choice in this change or an earlier one of ours). Relax a self-imposed one and re-evaluate; only an external one may stand as a reason.
5.  **Recommend** — if a good upstream exists, suggest it to the user before writing custom code. Include:
    - Package name and link
    - How it solves the problem
    - Any wrapping needed
6.  **If a close-but-not-exact match exists** — prefer contributing the missing piece upstream, or forking, over re-building from scratch (see the DRW fragment’s fork-or-contribute section and its `upstream-issues` / `scout-peers` gates)
7.  **If no upstream exists** — proceed with custom implementation, but note in comments that you checked and nothing fit, and record the search terms and every candidate found in the PR body — review is a weak layer for catching a reimplementation, so the written record is what a later reader has instead

## Anti-patterns to avoid

- Reimplementing `glue::glue()` with `paste0()` and manual substitution
- Writing custom YAML/JSON parsers when `yaml`/`jsonlite` exist
- Hand-rolling HTTP retry logic when `httr2` handles it
- Building custom test infrastructure when `testthat` covers the need
- Writing shell scripts for tasks that `usethis` or `devtools` already do

Back to top
