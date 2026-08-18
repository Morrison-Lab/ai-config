# r-pkg-cran-checklist

Walks through the standard items CRAN expects before accepting a package submission or update. This skill doesn’t duplicate the mechanics of a full check or a NEWS entry — it points at `r-pkg-check` and `r-pkg-news` for those sub-steps and covers everything else.

**Why this exists:** nothing in the repo tracked the CRAN-specific items beyond a plain package check — version bump discipline, `cran-comments.md`, reverse-dependency checks, and the win-builder/rhub cross-platform checks CRAN’s own submission form expects an answer about.

## Procedure

Work through each item; don’t submit until every one is checked.

1.  **Clean `R CMD check --as-cran`.** Run the [`r-pkg-check`](../../skills/r-pkg-check/SKILL.llms.md) skill, using `devtools::check(args = "--as-cran")` as the invocation (that skill notes this variant for CRAN submissions), and resolve every NOTE, WARNING, and ERROR it reports — CRAN’s own submission processing runs this exact check and rejects anything short of clean or fully-explained.

2.  **Version bump.** Confirm `DESCRIPTION`’s `Version:` field increased from the last version CRAN has (check `https://cran.r-project.org/package=<pkg>` or `available.packages()["<pkg>", "Version"]`), following semantic versioning appropriate to the change (patch for a fix, minor for a new feature, major for a breaking change).

3.  **NEWS.md entry.** Confirm an entry exists for the version being submitted, under a heading matching that version. Use [`r-pkg-news`](../../skills/r-pkg-news/SKILL.llms.md) to draft one if it’s missing.

4.  **`cran-comments.md`.** Confirm the package root has a `cran-comments.md` (CRAN’s expected file for submission notes) stating:

    - The R versions and platforms checked (typically via `devtools::check()` locally, `devtools::check_win_devel()`/`check_win_release()` for win-builder, and `rhub::rhub_check()` for cross-platform checks).
    - Any remaining NOTEs and why they’re expected/harmless (e.g. “This is a new submission” or a known false-positive spelling flag).
    - A `## Downstream dependencies` section, even if just “There are currently no downstream dependencies for this package” — required for every submission, not just ones with revdeps.

5.  **win-builder and r-hub checks.** Run (or confirm recently run):

    ``` r
    devtools::check_win_devel()
    devtools::check_win_release()
    rhub::rhub_check()
    ```

    These catch platform-specific failures (Windows path handling, Solaris/ macOS compiler differences) that a local check on one platform can’t. Wait for the emailed/posted results before submitting if they were just triggered — they run asynchronously.

6.  **Reverse-dependency checks.** If the package has downstream dependents (check `https://cran.r-project.org/package=<pkg>` “Reverse dependencies” or run `tools::package_dependencies(<pkg>, reverse = TRUE)`), run their checks against this version (`revdepcheck::revdep_check()`) and report any new failures to their maintainers before submitting, per CRAN policy. Skip this step only if there truly are no reverse dependencies — state that explicitly in `cran-comments.md` either way (step 4).

7.  **Submit** via `devtools::release()` (interactive, walks through a final confirmation of the above) or the CRAN web form at <https://cran.r-project.org/submit.html>, attaching the built tarball from `devtools::build()`.

## Related

- [`r-pkg-check`](../../skills/r-pkg-check/SKILL.llms.md) — the full-check sub-step (item 1).
- [`r-pkg-news`](../../skills/r-pkg-news/SKILL.llms.md) — the NEWS.md entry sub-step (item 3).
- [`r-pkg-spellcheck`](../../skills/r-pkg-spellcheck/SKILL.llms.md) — run before this checklist so documentation and NEWS.md text are clean going in.

Back to top
