# Rendered code shows output and nothing else

Code in the notes prints its output and no warning or non-output message (Ezra, 2026-10-26, Morrison-Lab/lds#1440).
A reader should never see "`geom_smooth()` using formula = 'y ~ x'", "`stat_bin()` using `bins = 30`", a package-loading banner or a deprecation warning under a chunk.

## Fix the cause, not the display

- Name the argument that the message announces a default for: `geom_smooth(method = "lm", formula = y ~ x)`, `geom_histogram(bins = 30)` or `binwidth = `.
- Fix the code that raises a warning.
- Silence a message only when it cannot be avoided and carries no information a reader needs (`suppressPackageStartupMessages()` for a package that prints a banner).
- Never hide a real warning with `warning: false` or `message: false` to make a page look clean: that hides a defect from the author as well.

## Mechanism

The gha check `check-code-messages` ([Morrison-Lab/gha#1261](https://github.com/Morrison-Lab/gha/pull/1261)) enforces the rule two ways:

- a source lint flags `geom_smooth()` or `stat_smooth()` with no `formula`, and `geom_histogram()` or `stat_bin()` with none of `bins`, `binwidth` and `breaks`, on lines a PR adds;
- a scan of the rendered site flags every Quarto `cell-output-stderr` block, where knitr, reticulate and Jupyter put every warning and message.

Add a function to the lint's rule table in that check when a render shows another message that a missing argument causes.
