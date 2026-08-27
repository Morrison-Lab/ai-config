#!/usr/bin/env Rscript
# Fetch contributors for a package release using usethis::use_tidy_thanks()
#
# Usage:
#   Rscript get_contributors.R <repo> [<from>]
#
# Arguments:
#   repo: GitHub repository in "owner/repo" format (e.g., "tidyverse/dplyr")
#   from: Optional git ref (tag/SHA) to use as the starting point
#         If omitted, uses the previous release
#
# Output:
#   Markdown-formatted list of contributors printed to stdout, suitable
#   for blog post acknowledgments
#   Informational messages are printed to stderr
#
# Examples:
#   Rscript get_contributors.R "tidyverse/dplyr"
#   Rscript get_contributors.R "tidyverse/dplyr" "v1.0.0"

args <- commandArgs(trailingOnly = TRUE)

if (length(args) == 0) {
  cat("Error: Repository argument required\n", file = stderr())
  cat("Usage: Rscript get_contributors.R <repo> [<from>]\n", file = stderr())
  cat("Example: Rscript get_contributors.R 'tidyverse/dplyr'\n", file = stderr())
  quit(status = 1)
}

repo <- args[1]
from <- if (length(args) >= 2) args[2] else NULL

# Check if usethis is installed
if (!requireNamespace("usethis", quietly = TRUE)) {
  cat("Error: usethis package is not installed\n", file = stderr())
  cat("Install it with: install.packages('usethis')\n", file = stderr())
  quit(status = 1)
}

# Fetch contributors
cat("Fetching contributors for", repo, "...\n\n", file = stderr())

if (is.null(from)) {
  contributors <- usethis::use_tidy_thanks(repo)
} else {
  contributors <- usethis::use_tidy_thanks(repo, from = from)
}

# use_tidy_thanks() returns the markdown text (invisibly on some
# usethis versions) rather than guaranteeing it prints to the console
# itself --- print it explicitly so the markdown always reaches stdout
# regardless of that return-visibility detail.
cat(contributors, sep = "\n")
