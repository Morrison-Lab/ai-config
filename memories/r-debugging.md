# R debugging notes

R-specific debugging gotchas: verifying R-package tests, regenerating snapshot tests, model-fitting defaults that silently drop or misalign rows, and `gsub()` replacement semantics.
Split out of [`debugging.md`](debugging.md) at its line gate (ai-config#2329).
For the R toolchain itself (`renv`, CI gates, `{cli}`), see [`r-quarto.md`](r-quarto.md).

## Verifying R-package tests: install + testthat, never `source()` the R files
Hit on ucdavis/ettbc#14.
The env had no `devtools`/`renv`, so I "verified" the new tests by `sys.source()`-ing every `R/*.R` file and re-running the assertions by hand.
They passed — but CI's `R CMD check` failed with `could not find function "run_augment_one"`.
Two lessons:
- **testthat runs each test file top-to-bottom, and `test_that()` executes immediately.**
  Helper functions (and file-scope fixtures) must be defined **above** the `test_that()` blocks that call them.
  A helper defined at the bottom of the file is undefined when the earlier tests run.
  Manual sourcing hides this because you naturally define helpers before use in the REPL.
- **Don't emulate the test run by sourcing `R/`.**
  It reproduces neither testthat's execution model nor the package namespace (internal, unexported functions resolve under `source()` but the suite's `test_check` exposes them differently).
  Install the toolchain from the Posit package manager and run it the way CI does: `install.packages(c("testthat","cli", <Suggests used>), repos="https://packagemanager.posit.co/cran/__linux__/noble/latest")`, then `R CMD INSTALL .`, then `testthat::test_dir("tests/testthat", load_package="installed")`. roxygen2, lintr, and spelling install the same way — so `roxygenise()` (diff check), `lint_package()`, and `spell_check_package()` are all runnable locally even when `renv::restore()` can't reach the full dependency set.
  **Caution: a full `test_dir()` / `devtools::test()` pass can PRUNE `_snaps/` files whose snapshot test was skipped or went unrun this pass** (e.g. snapr tests skipped because `NOT_CRAN` is unset) — see the snapr section below before running it with `git add -A` in scope.

## R snapshot tests (snapr / testthat) — regenerating without collateral damage
Hit across ucdavis/bcs#264 (the snapr-based `expect_snapshot_data` suite):
- **When a snapshot's test is skipped or doesn't run in a given pass, a full `testthat::test_dir()` / `devtools::test()` run PRUNES its now-orphaned `_snaps/` file** (not every routine run — the trigger is the snapshot going unproduced this pass).
  On #264 the snapr tests were skipped (`NOT_CRAN` unset, see below), so a `test_dir()` pass treated their snapshots as orphaned and deleted 23 of them;
  `git add -A` then silently staged every deletion.
  (Stock testthat 3.x gates orphan *deletion* on snapshot-update mode — a normal run only warns — so the #264 prune was likely either an implicit update pass or snapr's own `expect_snapshot_data` pruning path;
  I didn't pin down which.
  The defense below holds either way.)
  Regenerate **per file** with `testthat::test_file("tests/testthat/test-<fn>.R")`, stage only the snapshots you meant to touch (`git add "tests/testthat/_snaps/<fn>.md"`), and if the suite did prune others, restore them: `git checkout origin/main -- tests/testthat/_snaps`.
- **snapr snapshot tests are skipped unless `NOT_CRAN=true`** (they're guarded like `skip_on_cran()`);
  locally you must set the env var or every snapshot silently no-ops and "passes" without comparing.
- **`furrr`/`future` parallel workers cannot load a `pkgload::load_all()`'d package** — a worker starts a fresh R process that only sees installed packages, so any snapshot that runs the analysis under `future_map` errors or produces nothing.
  Regenerate those snapshots in a **sequential** plan (`future::plan("sequential")` / set workers to 1), then copy the result into the parallel snapshot path — verify seq==par output on `main` first so the copy is sound.
- **A failed CI snapshot run may still upload the authoritative `.new` files.**
  When a reusable snapshot updater cannot commit because unrelated tests fail, download its or the coverage job's failure artifact and copy only the generated `*_*.new.*` files over their matching committed snapshots;
  do not regenerate a partial suite locally and assume skipped parallel tests are covered.
  Confirm the artifact head SHA matches the PR head before accepting it.
- **`require-review` failure caused by dispatch winning the concurrency race.**
  `cancel-in-progress: true` on a concurrency group means a newly-dispatched review cancels the still-running push-triggered review.
  The push-triggered run's `require-review` gate then shows as failed (cancelled parent = failed dependent), while the dispatched run's `require-review` is green.
  The PR shows `mergeable_state: unstable` from the cancelled run but is still mergeable — GitHub uses the most recent check run per name and commit SHA, so the dispatched run's passing `require-review` replaces the cancelled push run's check in branch protection.
  Confirm the dispatched run posted a clean verdict and proceed to merge;
  don't re-trigger.
  (gha#133.)
- **`tests/testthat.R` runs with `stop_on_warning = TRUE`**, so any warning during a test FAILS CI even with 0 test failures (shows as `WARN N`).
  When you hit it, don't guess the source — **capture the actual messages** (`withCallingHandlers(..., warning = \(w) {message(conditionMessage(w)); ...})`).
  On #264 the GLM "fitted probabilities 0 or 1" / "did not converge" warnings were a red herring;
  the real one was a `cli::cli_warn("risk ratio is undefined")` from a zero-risk group at small n.
  Muffle expected small-sample warnings in BOTH the package source (a `suppress_*_warnings()` helper wrapping the fit chain) AND the test helper, matching every pattern the fits actually emit.

## R: `glm()`'s default `na.action = na.omit` silently MISALIGNS `fitted()`

`stats::glm()` defaults to `na.action = na.omit`, which **drops** rows with any missing predictor.
`stats::fitted()` then returns a vector **shorter than the data frame**, so writing it back onto the full frame is wrong.
How it fails depends on how you write it back — and only one of the two is loud:

```r
data <- dplyr::mutate(data, p = stats::fitted(fit))  # ERRORS (size N vs size k)
data$p <- stats::fitted(fit)                         # SILENT when k divides N:
                                                     # base R recycles -> wrong rows
```

Verified on R 4.5 / dplyr 1.2 with `nrow = 100` and 50 complete cases: `dplyr::mutate()` aborts with a size mismatch, while base `$<-` **silently recycles** the 50 fitted values twice, assigning each prediction to two different subjects.
(Base `$<-` errors instead when `k` does *not* divide `N` — so the same code is loud or silent depending on the data, which is worse than either.)
The same silent misalignment reaches you through any downstream join/index pattern where the short vector escapes undetected.

Fix: `na.action = stats::na.exclude`, which pads `fitted()`/`residuals()` back out to the full row count with `NA` at the dropped positions, preserving alignment.

```r
fit <- stats::glm(f, data = data, family = binomial(), na.action = stats::na.exclude)
data <- dplyr::mutate(data, p = stats::fitted(fit))   # aligned; dropped rows are NA
```

**This is a latent landmine, not a hypothetical.**
Code that has always been fed fully-imputed (NA-free) data works perfectly and hides the bug — it only fires the day a covariate with real missingness is added.
If you see `fitted(fit)`/`residuals(fit)` written back onto a data frame anywhere, check the `na.action`, even if the code currently "works".
(Found on ucdavis/bcs#349, where adding a covariate that SAS deliberately leaves unimputed would have activated it.)

## R: `mice` silently DROPS collinear columns instead of imputing them

`mice::mice()` runs a collinearity check and quietly removes offending predictors — the evidence is only in `mi_result$loggedEvents` (`meth = "collinear"`), not in a warning you'd notice.
The completed dataset then still has `NA` in the "imputed" column, and an `expect_false(anyNA(x))` test fails with no obvious cause.

The usual trigger in a **test fixture**: covariates derived deterministically from the row index (`race = k %% 2`, `bmi = 22 + k %% 11`, ...).
That makes every covariate an exact function of every other, so `mice` flags most of them collinear and imputes nothing.
The fixture *looks* rich and is actually rank-1.

Fixes:
- Build the fixture by **sampling under a fixed seed** (`withr::with_seed()`), not by deriving from the index — reproducible *and* genuinely varied.
- When `mice` doesn't impute something, `print(mi_result$loggedEvents)` first.
  It names the variable and the reason and saves a long hunt.

Note the same index-derived-fixture degeneracy also makes GLM coefficients alias (NA coefficients) — which can be harmless if the test only asserts on *fitted values* — so it can lurk in a fixture for a long time before `mice` finally trips over it.
(ucdavis/bcs#349.)

## R `gsub()` correction: `fixed = TRUE` keeps replacement literal

Correction to an earlier note: with `gsub(..., fixed = TRUE)`, both matching and replacement are treated literally (no backreferences), so this mode does *not* interpret replacement escapes like `\\1`.

If you do need regex matching (`fixed = FALSE`), replacement escapes can still apply, so validate any claim about replacement behavior against a runnable example before recording a generalized rule.
(Correction logged from review on Morrison-Lab/ai-config#641, 2026-07-22.)
