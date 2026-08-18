---
name: r-pkg-check
description: "Run devtools::check() and triage."
user-invocable: true
allowed-tools:
  - Read
  - Edit
  - Write
  - Bash
---

# r-pkg-check

Runs a full package check — the superset check that unit tests alone don't
cover — and triages every NOTE, WARNING, and ERROR it reports before a
release or CRAN submission.

**Why this exists:** `devtools::test()` only runs unit tests; it says
nothing about documentation completeness, example runnability, DESCRIPTION
metadata, or the CRAN-policy checks that `R CMD check` applies. A package
whose tests pass can still fail `R CMD check` on an undocumented argument, a
broken `\dontrun{}` example, or a non-portable file name — issues that only
surface by running the full check.

## When to run

Before a release, before a CRAN submission, or whenever asked to check a
package end to end — not during ordinary iteration (use `test` for that).

## Procedure

1. **Confirm this is an R package.** Check that `DESCRIPTION` exists at the
   repo root. If not, skip — this skill doesn't apply.

2. **Run the same check CI runs:**

   ```sh
   Rscript -e 'devtools::check()'
   ```

   Check this repo's own `.github/workflows/` for an `R CMD check`-style
   job first — if one pins specific flags (e.g. `--as-cran`,
   `--no-manual`), run that exact invocation instead so local results match
   CI. Absent such a workflow, `devtools::check()` is the default; add
   `args = "--as-cran"` when preparing a CRAN submission specifically (see
   `r-pkg-cran-checklist`).

   - If `devtools` isn't installed:
     `Rscript -e 'install.packages("devtools")'` then retry. If R isn't
     available at all, fall back to step 5.

3. **Triage each NOTE, WARNING, and ERROR:**
   - Real problem (missing documentation, broken example, undeclared
     dependency) → fix it in the source.
   - A NOTE that's a known, accepted false positive (e.g. a package name
     CRAN's spell-checker doesn't recognize) → document why in a
     `cran-comments.md` entry (see `r-pkg-cran-checklist`) rather than
     silently ignoring it.
   - Never leave an ERROR or WARNING unaddressed — both block a CRAN
     submission and usually indicate a real defect.

4. **Re-run step 2** to confirm a clean check (0 errors, 0 warnings, and
   every remaining NOTE accounted for) before pushing or submitting.

5. **If R isn't available**, manually review the diff for the shapes
   `R CMD check` usually flags: new exported functions without `@param`/
   `@return` docs, examples that call network or interactive code without
   `\dontrun{}`/`\donttest{}`, and new dependencies missing from
   `DESCRIPTION`'s `Imports`/`Suggests`.

## Related

- [`test`](../test/SKILL.md) runs `devtools::test()` — unit tests only, for
  ordinary iteration. This skill is the superset full check (docs,
  examples, CRAN-policy NOTEs) to run before a release.
- [`r-pkg-spellcheck`](../r-pkg-spellcheck/SKILL.md) spellchecks
  documentation and NEWS.md text — a narrower, faster check this skill
  doesn't replace (spelling isn't part of `R CMD check`'s own coverage).
- [`r-pkg-cran-checklist`](../r-pkg-cran-checklist/SKILL.md) is the larger
  submission checklist this skill's clean check is one step of.
