# Rendered code shows output and nothing else

Code in the notes prints its output and no warning or non-output message (Ezra, 2026-10-26, [Morrison-Lab/lds#1440](https://github.com/Morrison-Lab/lds/issues/1440)).
A reader should never see "`geom_smooth()` using formula = 'y ~ x'", "`stat_bin()` using `bins = 30`", a package-loading banner or a deprecation warning under a chunk.

## Fix the cause, not the display

- Name every argument whose default makes ggplot2 print a message.
  `geom_smooth()` and `stat_smooth()` need both `method` and `formula`: `geom_smooth(method = "lm", formula = y ~ x)`.
  `geom_histogram()` and `stat_bin()` need one of `bins`, `binwidth` or `breaks`: `geom_histogram(binwidth = 1)`.
- Fix the code that raises a warning, unless the warning is the expected result of what the page shows, as in the `warning: false` bullet below.
- Silence a message only when it cannot be avoided and carries no information a reader needs.
  Keep the code readers see plain: set the chunk option `#| message: false` on a chunk that loads a package, rather than wrapping `library(pkg)` in `suppressPackageStartupMessages()` (cross-harness review, 2026-10-26).
  A chunk option silences every message in its chunk, so keep such a chunk to the package load or to the one call whose message is expected.
- Use `#| warning: false` only for a warning that is expected and understood.
  Check the invariant the result relies on, such as `stopifnot(fit$converged)`, in a hidden chunk (`#| echo: false`), unless the check is what the page teaches.
  Where the page quotes the warning, repeat the call in that hidden chunk under `withCallingHandlers()`, keep the warning text, and assert it with `stopifnot()`, so a different warning fails the render.
- Never hide a message or warning that has not been read and understood, by a chunk option or by a wrapper such as `suppressWarnings()`, `suppressMessages()` or `warnings.filterwarnings("ignore")`: that hides a defect from the author as well.

## Mechanism

The gha check `check-code-messages` enforces the rule two ways ([Morrison-Lab/gha#1261](https://github.com/Morrison-Lab/gha/pull/1261);
the script is `check-code-messages/check-code-messages.py` in Morrison-Lab/gha):

- a source lint flags `geom_smooth()` or `stat_smooth()` missing `method` or `formula`, and `geom_histogram()` or `stat_bin()` with none of `bins`, `binwidth` or `breaks`, on lines a PR adds;
- a scan of the rendered site flags every Quarto `cell-output-stderr` block, where knitr, reticulate and Jupyter put every warning and message.

Add a function to the lint's rule table in that script when a render shows another message that a missing argument causes.
