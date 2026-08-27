#!/usr/bin/env Rscript
# Generate a release checklist for an R package
#
# Usage:
#   Rscript generate_checklist.R <new_version> [github_url]
#
# Arguments:
#   new_version: Target version for the release (e.g., "1.2.0")
#   github_url: (Optional) Full GitHub repository URL (e.g., "https://github.com/owner/repo")
#
# Output:
#   Markdown-formatted release checklist printed to stdout
#   Informational messages are printed to stderr
#
# Examples:
#   Rscript generate_checklist.R "1.2.0" "https://github.com/tidyverse/dplyr"
#   Rscript generate_checklist.R "1.2.0"

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) {
  cat("usage: Rscript generate_checklist.R <new_version> [github_url]\n", file = stderr())
  quit(status = 1)
}

if (!requireNamespace("usethis", quietly = TRUE)) {
  cat("Error: usethis package is not installed\n")
  cat("Install it with: install.packages('usethis')\n")
  quit(status = 1)
}

new_version <- args[1]
url <- if (length(args) >= 2) args[2] else NULL

# `cran_version()` and `release_checklist()` are unexported usethis
# internals --- this script generates the checklist TEXT only, so the
# customization loop in this skill's Step 4 can run before the issue is
# filed, which usethis's own exported `use_release_issue()` doesn't allow
# (it creates the issue immediately, with no interactive review step).
# An unexported signature can change between usethis releases with no
# deprecation warning, so fail with a concrete fallback rather than a raw
# error.
fallback_message <- paste(
  "Error: could not generate the checklist. This may be an ordinary",
  "failure (not run from inside a package directory, no network access,",
  "not a git repository) or it may mean usethis's internal checklist API",
  "has changed --- this script calls unexported usethis:::cran_version()",
  "and usethis:::release_checklist(), which carry no compatibility",
  "guarantee. Fall back to running usethis::use_release_issue() directly",
  "--- it creates the release issue itself, without this skill's",
  "interactive customization step.",
  sep = "\n"
)

checklist <- tryCatch(
  {
    on_cran <- !is.null(usethis:::cran_version())
    target_repo <- if (!is.null(url)) list(url = url) else NULL
    usethis:::release_checklist(new_version, on_cran, target_repo)
  },
  error = function(e) {
    cat(fallback_message, "\n", file = stderr())
    cat("Original error: ", conditionMessage(e), "\n", file = stderr())
    quit(status = 1)
  }
)
cat(checklist, sep = "\n")
