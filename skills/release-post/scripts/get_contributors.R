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

# use_tidy_thanks() invisibly returns the sorted character vector of
# bare GitHub usernames; its own markdown-formatted acknowledgment text
# is only displayed through cli's message stream, which goes to stderr
# under Rscript. Build the markdown-linked list here from the returned
# usernames so genuinely markdown-formatted output reaches stdout.
if (length(contributors) == 0) {
  cat("No contributors found for this range.\n", file = stderr())
} else {
  linked <- paste0("[@", contributors, "](https://github.com/", contributors, ")")
  cat(paste(linked, collapse = ", "), "\n", sep = "")
}
